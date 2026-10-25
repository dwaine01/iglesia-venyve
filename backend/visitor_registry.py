"""Registro digital de visitantes (V1): tabletas en modo quiosco.

Seguridad del quiosco:
- Cada tableta se empareja desde el panel con un código de un solo uso (24 h);
  recibe un TOKEN DE DISPOSITIVO (solo se guarda su hash) cuyo ÚNICO permiso es
  crear registros: no puede leer nada. Se desactiva desde el panel.
- Sin sesiones de personal en la tableta.

Registro:
- Número único ATÓMICO en el servidor (V-AAAA-000001), nunca en la tableta.
- Clave de idempotencia ÚNICA por envío: un doble toque o un reintento sin
  internet devuelven el mismo registro.
- Persona 360: misma búsqueda de duplicados del directorio (teléfono, correo,
  nombre + nacimiento). Una coincidencia clara se vincula; una dudosa queda como
  «posible coincidencia» para que el personal confirme (nunca se fusiona sola).
- Datos separados: bienvenida (solo nombre preferido + consentimientos),
  contacto y RESTRINGIDOS (oración, consejería, necesidades) en otra colección.
- Textos editables (bienvenida, aviso de privacidad versionado, confirmación) y
  la versión del aviso aceptado queda en cada registro. Auditoría de todo."""
import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from access_control import (
    VISITORS_DEVICES_MANAGE, VISITORS_FOLLOWUP_MANAGE, VISITORS_READ, VISITORS_RESTRICTED_READ, VISITORS_TEXTS_MANAGE, VISITORS_WELCOME_OPERATE,
    has_capability, is_global_pastoral_authority,
)
from server import db, get_current_user

admin_router = APIRouter(prefix="/api/visitors", tags=["visitors"])
kiosk_router = APIRouter(prefix="/api/kiosk", tags=["visitor-kiosk"])

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I para leerlo sin errores
CODE_HOURS = 24
TEXTS_ID = "visitor_texts"
DEFAULT_TEXTS = {
    "welcome": "¡Bienvenido a Casa de Oración! Nos alegra que estés aquí. Esperamos que hagas de esta iglesia tu casa y de esta familia tu familia. Queremos conocerte y saber cómo podemos servirte.",
    "privacy": "Usamos tus datos solo para darte la bienvenida, comunicarnos contigo si lo autorizas y servirte mejor. Los cuida un equipo autorizado de la iglesia; no los compartimos con nadie fuera de la iglesia. Tu nombre solo se anuncia o se muestra en pantallas si tú lo autorizas. Puedes pedir en cualquier momento que corrijamos o borremos tus datos.",
    "confirmation": "¡Gracias por registrarte! Ya eres parte de esta familia. Si necesitas algo, muestra este número a cualquier servidor de la iglesia.",
}
REQUEST_KEYS = ["prayer", "visit", "info", "counseling_personal", "counseling_marriage", "counseling_family", "support_child", "other_help", "no_followup"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def can(current_user: dict, capability: str) -> bool:
    return is_global_pastoral_authority(current_user) or has_capability(current_user, capability)


def require(current_user: dict, capability: str) -> None:
    if not can(current_user, capability):
        raise HTTPException(status_code=403, detail="Sin permiso para esta función del Registro de visitantes")


async def audit(action: str, actor: str, detail: Optional[dict] = None) -> None:
    event_id = str(uuid4())
    await db.visitor_audit.insert_one({"_id": event_id, "event_id": event_id, "action": action, "actor": actor, "detail": detail or {}, "created_at": now_utc()})


_indexes_ready = False


async def ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    await db.visitor_registrations.create_index("idempotency_key", unique=True)
    await db.visitor_registrations.create_index("visitor_number", unique=True)
    await db.visitor_registrations.create_index([("service.date", -1), ("created_at", -1)])
    await db.visitor_devices.create_index("token_hash", unique=True, partialFilterExpression={"token_hash": {"$type": "string"}})
    await db.visitor_devices.create_index("code_hash", unique=True, partialFilterExpression={"code_hash": {"$type": "string"}})
    _indexes_ready = True


# ------------------------------------------------------------------ textos
async def load_texts() -> dict:
    doc = await db.app_settings.find_one({"_id": TEXTS_ID}, {"_id": 0}) or {}
    return {"welcome": doc.get("welcome") or DEFAULT_TEXTS["welcome"], "privacy": doc.get("privacy") or DEFAULT_TEXTS["privacy"],
            "privacy_version": doc.get("privacy_version") or 1, "confirmation": doc.get("confirmation") or DEFAULT_TEXTS["confirmation"],
            "updated_at": doc.get("updated_at"), "updated_by": doc.get("updated_by_name")}


class TextsInput(BaseModel):
    welcome: str = Field(min_length=10, max_length=1500)
    privacy: str = Field(min_length=20, max_length=3000)
    confirmation: str = Field(min_length=5, max_length=800)


@admin_router.get("/texts", response_model=dict)
async def get_texts(current_user: dict = Depends(get_current_user)):
    if not any(can(current_user, cap) for cap in (VISITORS_TEXTS_MANAGE, VISITORS_DEVICES_MANAGE, VISITORS_READ)):
        raise HTTPException(status_code=403, detail="Sin permiso para el Registro de visitantes")
    return await load_texts()


@admin_router.put("/texts", response_model=dict)
async def put_texts(payload: TextsInput, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_TEXTS_MANAGE)
    current = await load_texts()
    version = current["privacy_version"] + (1 if payload.privacy.strip() != current["privacy"].strip() else 0)
    await db.app_settings.update_one({"_id": TEXTS_ID}, {"$set": {"welcome": payload.welcome.strip(), "privacy": payload.privacy.strip(), "privacy_version": version,
                                                                    "confirmation": payload.confirmation.strip(), "updated_at": now_utc(), "updated_by_user_id": current_user["user_id"],
                                                                    "updated_by_name": current_user.get("nombre")},
                                                           "$push": {"history": {"privacy_version": version, "privacy": payload.privacy.strip(), "at": now_utc(), "by": current_user["user_id"]}}}, upsert=True)
    await audit("texts_updated", current_user["user_id"], {"privacy_version": version})
    return await load_texts()


# ------------------------------------------------------------------ servicio en curso
SERVICE_KINDS = {"sunday": "Servicio del domingo", "wednesday": "Servicio del miércoles", "special": "Actividad especial"}


async def current_service() -> dict:
    """Servicio del día local de la iglesia: domingo, miércoles o actividad especial
    (la administración puede nombrar la actividad especial de hoy)."""
    from report_period import report_zone
    zone = await report_zone()
    today = datetime.now(zone).date()
    override = await db.app_settings.find_one({"_id": "visitor_service_today"}, {"_id": 0}) or {}
    if override.get("date") == today.isoformat() and override.get("label"):
        return {"kind": override.get("kind") or "special", "label": override["label"], "date": today.isoformat()}
    kind = "sunday" if today.weekday() == 6 else "wednesday" if today.weekday() == 2 else "special"
    return {"kind": kind, "label": SERVICE_KINDS[kind], "date": today.isoformat()}


class ServiceInput(BaseModel):
    label: str = Field(min_length=3, max_length=120)
    kind: Literal["sunday", "wednesday", "special"] = "special"


@admin_router.put("/service-today", response_model=dict)
async def set_service_today(payload: ServiceInput, current_user: dict = Depends(get_current_user)):
    """Nombra el servicio o la actividad de hoy (p. ej. «Conferencia de mujeres»)."""
    if not (can(current_user, VISITORS_DEVICES_MANAGE) or can(current_user, VISITORS_WELCOME_OPERATE)):
        raise HTTPException(status_code=403, detail="Sin permiso para cambiar el servicio de hoy")
    service = await current_service()
    await db.app_settings.update_one({"_id": "visitor_service_today"}, {"$set": {"date": service["date"], "label": payload.label.strip(), "kind": payload.kind, "updated_at": now_utc()}}, upsert=True)
    return await current_service()


# ------------------------------------------------------------------ tabletas
class DeviceInput(BaseModel):
    name: str = Field(min_length=2, max_length=60)


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


def device_view(doc: dict) -> dict:
    return {"device_id": doc["device_id"], "name": doc["name"], "status": doc["status"], "status_label": {"pending": "Esperando emparejar", "paired": "Activa", "revoked": "Desactivada"}[doc["status"]],
            "code_expires_at": doc.get("code_expires_at").isoformat() if doc.get("code_expires_at") and doc["status"] == "pending" else None,
            "paired_at": doc.get("paired_at").isoformat() if doc.get("paired_at") else None, "last_seen_at": doc.get("last_seen_at").isoformat() if doc.get("last_seen_at") else None,
            "registrations": doc.get("registrations", 0)}


@admin_router.get("/devices", response_model=dict)
async def list_devices(current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_DEVICES_MANAGE)
    return {"items": [device_view(doc) async for doc in db.visitor_devices.find({}, {"_id": 0}).sort("name", 1)]}


async def issue_code(device_id: str) -> tuple[str, datetime]:
    for _ in range(5):
        code = new_code()
        expires = now_utc() + timedelta(hours=CODE_HOURS)
        try:
            await db.visitor_devices.update_one({"device_id": device_id}, {"$set": {"code_hash": sha(code), "code_expires_at": expires, "status": "pending", "token_hash": None, "updated_at": now_utc()}})
            return code, expires
        except DuplicateKeyError:
            continue
    raise HTTPException(status_code=500, detail="No se pudo generar el código; intente de nuevo")


@admin_router.post("/devices", response_model=dict, status_code=201)
async def create_device(payload: DeviceInput, current_user: dict = Depends(get_current_user)):
    """Registra una tableta («Tableta 1») y devuelve su código de emparejamiento UNA vez."""
    require(current_user, VISITORS_DEVICES_MANAGE)
    await ensure_indexes()
    device_id = str(uuid4())
    await db.visitor_devices.insert_one({"_id": device_id, "device_id": device_id, "name": payload.name.strip(), "status": "pending", "token_hash": None, "created_at": now_utc(), "created_by_user_id": current_user["user_id"], "registrations": 0})
    code, expires = await issue_code(device_id)
    await audit("device_created", current_user["user_id"], {"device_id": device_id, "name": payload.name})
    return {**device_view(await db.visitor_devices.find_one({"device_id": device_id}, {"_id": 0})), "pairing_code": code, "code_expires_at": expires.isoformat()}


@admin_router.post("/devices/{device_id}/new-code", response_model=dict)
async def device_new_code(device_id: str, current_user: dict = Depends(get_current_user)):
    """Nuevo código (la tableta anterior queda desconectada)."""
    require(current_user, VISITORS_DEVICES_MANAGE)
    await ensure_indexes()
    if not await db.visitor_devices.find_one({"device_id": device_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Tableta no encontrada")
    code, expires = await issue_code(device_id)
    await audit("device_new_code", current_user["user_id"], {"device_id": device_id})
    return {**device_view(await db.visitor_devices.find_one({"device_id": device_id}, {"_id": 0})), "pairing_code": code, "code_expires_at": expires.isoformat()}


@admin_router.post("/devices/{device_id}/revoke", response_model=dict)
async def revoke_device(device_id: str, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_DEVICES_MANAGE)
    result = await db.visitor_devices.update_one({"device_id": device_id}, {"$set": {"status": "revoked", "token_hash": None, "code_hash": None, "revoked_at": now_utc(), "updated_at": now_utc()}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Tableta no encontrada")
    await audit("device_revoked", current_user["user_id"], {"device_id": device_id})
    return device_view(await db.visitor_devices.find_one({"device_id": device_id}, {"_id": 0}))


# ------------------------------------------------------------------ quiosco (token de dispositivo)
class PairInput(BaseModel):
    code: str = Field(min_length=6, max_length=20)


@kiosk_router.post("/pair", response_model=dict)
async def pair(payload: PairInput):
    await ensure_indexes()
    code = payload.code.strip().upper().replace(" ", "").replace("-", "")
    device = await db.visitor_devices.find_one({"code_hash": sha(code), "status": "pending"}, {"_id": 0})
    if not device or not device.get("code_expires_at") or (device["code_expires_at"] if device["code_expires_at"].tzinfo else device["code_expires_at"].replace(tzinfo=timezone.utc)) < now_utc():
        raise HTTPException(status_code=404, detail="Código no válido o vencido. Pida un código nuevo en el panel de administración.")
    token = secrets.token_urlsafe(32)
    await db.visitor_devices.update_one({"device_id": device["device_id"], "status": "pending"}, {"$set": {"token_hash": sha(token), "code_hash": None, "status": "paired", "paired_at": now_utc(), "updated_at": now_utc()}})
    await audit("device_paired", f"device:{device['device_id']}", {"name": device["name"]})
    return {"token": token, "device_name": device["name"]}


async def kiosk_device(x_device_token: Optional[str] = Header(default=None)) -> dict:
    if not x_device_token:
        raise HTTPException(status_code=401, detail="Tableta no emparejada")
    device = await db.visitor_devices.find_one({"token_hash": sha(x_device_token), "status": "paired"}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=401, detail="Esta tableta fue desactivada o no está emparejada")
    await db.visitor_devices.update_one({"device_id": device["device_id"]}, {"$set": {"last_seen_at": now_utc()}})
    return device


@kiosk_router.get("/config", response_model=dict)
async def kiosk_config(device: dict = Depends(kiosk_device)):
    """Lo único que la tableta puede leer: textos públicos y el servicio de hoy."""
    texts = await load_texts()
    return {"device_name": device["name"], "service": await current_service(),
            "texts": {"welcome": texts["welcome"], "privacy": texts["privacy"], "privacy_version": texts["privacy_version"], "confirmation": texts["confirmation"]}}


class FamilyMember(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relation: Optional[str] = Field(default=None, max_length=60)
    is_minor: bool = False


class RegistrationInput(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=120)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    preferred_name: Optional[str] = Field(default=None, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=160)
    contact_method: Optional[Literal["call", "whatsapp", "text", "email", "none"]] = None
    city: Optional[str] = Field(default=None, max_length=120)
    address: Optional[str] = Field(default=None, max_length=300)
    birth_date: Optional[date] = None
    first_visit: Optional[bool] = None
    invited: Optional[bool] = None
    invited_by: Optional[str] = Field(default=None, max_length=120)
    visiting_from: Optional[str] = Field(default=None, max_length=160)
    other_church: Optional[bool] = None
    other_church_name: Optional[str] = Field(default=None, max_length=160)
    how_heard: Optional[str] = Field(default=None, max_length=200)
    family: list[FamilyMember] = Field(default_factory=list, max_length=12)
    requests: list[Literal["prayer", "visit", "info", "counseling_personal", "counseling_marriage", "counseling_family", "support_child", "other_help", "no_followup"]] = Field(default_factory=list)
    prayer_request: Optional[str] = Field(default=None, max_length=1500)
    counseling_note: Optional[str] = Field(default=None, max_length=1500)
    needs_note: Optional[str] = Field(default=None, max_length=1500)
    consent_followup: bool = False
    consent_announce: bool = False
    consent_screens: bool = False
    consent_family_announce: bool = False
    privacy_version: int = Field(ge=1)
    privacy_accepted: bool
    started_at: Optional[datetime] = None


async def next_number(year: int) -> str:
    counter = await db.counters.find_one_and_update({"_id": f"visitor_number_{year}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return f"V-{year}-{counter['seq']:06d}"


def kiosk_reply(doc: dict, duplicate: bool, texts: dict) -> dict:
    """La tableta solo recibe el número, el nombre para saludar y el mensaje."""
    return {"visitor_number": doc["visitor_number"], "greeting_name": doc["welcome"]["preferred_name"], "confirmation": texts["confirmation"], "duplicate": duplicate}


async def link_person(payload: RegistrationInput, device: dict) -> dict:
    """Misma búsqueda de duplicados de Persona 360; lo dudoso queda para revisión humana."""
    from person_matching import PersonQuickCreate, quick_create_person
    query = PersonQuickCreate(nombre=payload.first_name.strip(), apellido=payload.last_name.strip(), telefono=payload.phone or None, email=(payload.email or None),
                              fecha_nacimiento=payload.birth_date.isoformat() if payload.birth_date else None, idempotency_key=f"visitor:{payload.idempotency_key}")
    result = await quick_create_person(db, query, f"device:{device['device_id']}", "visitor_kiosk")
    if result["status"] == "created":
        return {"person_id": result["person"]["person_id"], "match_status": "created" if result.get("created") else "linked", "candidates": []}
    cards = result.get("candidates") or []
    candidates = [item["person_id"] for item in cards]
    if result["status"] == "strong_match" and len(cards) == 1 and name_compatible(payload, cards[0]):
        # Coincidencia clara (mismo teléfono/correo o nombre + nacimiento) Y nombre compatible: se vincula.
        return {"person_id": candidates[0], "match_status": "linked", "candidates": candidates}
    # Dudosa (p. ej. el mismo teléfono con otro nombre, o varias personas): revisión humana.
    return {"person_id": None, "match_status": "possible", "candidates": candidates}


def name_compatible(payload: "RegistrationInput", card: dict) -> bool:
    from person_matching import normalize_text
    given = set(normalize_text(f"{payload.first_name} {payload.last_name}").split())
    found = set(normalize_text(f"{card.get('nombre') or ''} {card.get('apellido') or ''}").split())
    first = normalize_text(payload.first_name).split()[:1]
    return bool(first and first[0] in found and len(given & found) >= 2) or given == found


@kiosk_router.post("/registrations", response_model=dict, status_code=201)
async def create_registration(payload: RegistrationInput, device: dict = Depends(kiosk_device)):
    await ensure_indexes()
    texts = await load_texts()
    existing = await db.visitor_registrations.find_one({"idempotency_key": payload.idempotency_key}, {"_id": 0})
    if existing:
        return kiosk_reply(existing, True, texts)
    if not payload.privacy_accepted:
        raise HTTPException(status_code=422, detail="Para registrarte necesitamos que aceptes el aviso de privacidad")
    from person_matching import normalize_phone, normalize_text
    service = await current_service()
    phone_norm = normalize_phone(payload.phone)
    name_key = normalize_text(f"{payload.first_name} {payload.last_name}")
    # La misma persona dos veces en el mismo servicio (otra tableta, incluso al mismo
    # tiempo): un candado por servicio + teléfono + nombre; nunca dos registros.
    lock_id = f"{service['date']}:{phone_norm}:{name_key}" if phone_norm else None
    if lock_id:
        try:
            await db.visitor_locks.insert_one({"_id": lock_id, "idempotency_key": payload.idempotency_key, "created_at": now_utc()})
        except DuplicateKeyError:
            import asyncio
            for _ in range(30):
                same = await db.visitor_registrations.find_one({"service.date": service["date"], "contact.phone_normalized": phone_norm, "name_key": name_key}, {"_id": 0})
                if same:
                    await audit("registration_repeat", f"device:{device['device_id']}", {"registration_id": same["registration_id"]})
                    return kiosk_reply(same, True, texts)
                await asyncio.sleep(0.2)
            raise HTTPException(status_code=409, detail="Ya se está guardando un registro igual; intente de nuevo en unos segundos")
    try:
        return await insert_registration(payload, device, service, phone_norm, name_key, texts)
    except BaseException:
        if lock_id:
            await db.visitor_locks.delete_one({"_id": lock_id, "idempotency_key": payload.idempotency_key})
        raise


async def insert_registration(payload: "RegistrationInput", device: dict, service: dict, phone_norm: Optional[str], name_key: str, texts: dict) -> dict:
    match = await link_person(payload, device)
    now = now_utc()
    registration_id = str(uuid4())
    requests = [item for item in payload.requests if item in REQUEST_KEYS]
    wants_followup = payload.consent_followup and "no_followup" not in requests
    doc = {
        "_id": registration_id, "registration_id": registration_id, "idempotency_key": payload.idempotency_key, "visitor_number": None,
        "device_id": device["device_id"], "device_name": device["name"], "service": service, "name_key": name_key,
        "person_id": match["person_id"], "match_status": match["match_status"], "possible_person_ids": match["candidates"] if match["match_status"] == "possible" else [],
        "first_name": payload.first_name.strip(), "last_name": payload.last_name.strip(),
        # Bloque de BIENVENIDA (lo único que verá el panel/pantallas, y solo si lo autorizó).
        "welcome": {"preferred_name": (payload.preferred_name or "").strip() or payload.first_name.strip(), "display_name": None, "approved": False, "hidden": False},
        # Bloque de CONTACTO (personal autorizado).
        "contact": {"phone": payload.phone, "phone_normalized": phone_norm, "email": (payload.email or "").strip() or None, "method": payload.contact_method, "city": payload.city, "address": payload.address,
                    "birth_date": payload.birth_date.isoformat() if payload.birth_date else None},
        "visit": {"first_visit": payload.first_visit, "invited": payload.invited, "invited_by": payload.invited_by if payload.invited else None, "visiting_from": payload.visiting_from,
                  "other_church": payload.other_church, "other_church_name": payload.other_church_name if payload.other_church else None, "how_heard": payload.how_heard},
        # Familiares: solo nombre y parentesco; nunca datos sensibles de menores. No se anuncian sin consentimiento.
        "family": [{"name": item.name.strip(), "relation": item.relation, "is_minor": item.is_minor} for item in payload.family],
        "requests": requests, "has_restricted": bool(payload.prayer_request or payload.counseling_note or payload.needs_note),
        "consents": {"followup": payload.consent_followup, "announce": payload.consent_announce, "screens": payload.consent_screens, "family_announce": payload.consent_family_announce},
        "privacy": {"version": payload.privacy_version, "accepted_at": now},
        "followup": {"status": "pending" if wants_followup else "not_requested", "assigned_person_id": None, "results": []},
        "test_data": False, "created_at": now, "started_at": payload.started_at,
    }
    doc["visitor_number"] = await next_number(datetime.now(timezone.utc).year)
    try:
        await db.visitor_registrations.insert_one(doc)
    except DuplicateKeyError:
        same = await db.visitor_registrations.find_one({"idempotency_key": payload.idempotency_key}, {"_id": 0})
        if same:
            return kiosk_reply(same, True, texts)
        raise
    if doc["has_restricted"]:
        await db.visitor_restricted.insert_one({"_id": registration_id, "registration_id": registration_id, "prayer_request": payload.prayer_request, "counseling_note": payload.counseling_note,
                                                "needs_note": payload.needs_note, "created_at": now})
    await db.visitor_devices.update_one({"device_id": device["device_id"]}, {"$inc": {"registrations": 1}})
    await audit("registration_created", f"device:{device['device_id']}", {"registration_id": registration_id, "visitor_number": doc["visitor_number"], "match_status": match["match_status"]})
    return kiosk_reply(doc, False, texts)


# ------------------------------------------------------------------ personal: consultar registros (V1 básico)
REQUEST_LABELS = {"prayer": "Oración", "visit": "Una visita", "info": "Información de la iglesia", "counseling_personal": "Consejería personal", "counseling_marriage": "Consejería matrimonial",
                  "counseling_family": "Consejería familiar", "support_child": "Apoyo para un hijo o familiar", "other_help": "Otro tipo de ayuda", "no_followup": "Prefiere no recibir seguimiento por ahora"}
MATCH_LABELS = {"created": "Persona nueva en Persona 360", "linked": "Vinculado a su perfil existente", "possible": "Posible coincidencia: revisar"}


def staff_view(doc: dict, restricted_ok: bool = False) -> dict:
    requests = doc.get("requests") or []
    shown = [REQUEST_LABELS[item] for item in requests if restricted_ok or item not in RESTRICTED_REQUESTS]
    if not restricted_ok and any(item in RESTRICTED_REQUESTS for item in requests):
        shown.append("Pedido confidencial")
    return {"registration_id": doc["registration_id"], "visitor_number": doc["visitor_number"], "first_name": doc["first_name"], "last_name": doc["last_name"],
            "preferred_name": doc["welcome"]["preferred_name"], "service": doc["service"], "device_name": doc.get("device_name"), "created_at": doc["created_at"].isoformat(),
            "person_id": doc.get("person_id"), "match_status": doc["match_status"], "match_label": MATCH_LABELS.get(doc["match_status"]), "possible_person_ids": doc.get("possible_person_ids") or [],
            "contact": doc["contact"], "visit": doc["visit"], "family": doc["family"], "requests": shown,
            "has_restricted": doc.get("has_restricted"), "consents": doc["consents"], "privacy_version": doc["privacy"]["version"], "followup": doc.get("followup"), "test_data": doc.get("test_data")}


@admin_router.get("/registrations", response_model=dict)
async def list_registrations(service_date: Optional[str] = None, limit: int = 200, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_READ)
    query = {"service.date": service_date} if service_date else {}
    restricted_ok = can(current_user, VISITORS_RESTRICTED_READ)
    items = [staff_view(doc, restricted_ok) async for doc in db.visitor_registrations.find(query, {"_id": 0}).sort("created_at", -1).limit(max(1, min(limit, 500)))]
    await audit("registrations_viewed", current_user["user_id"], {"service_date": service_date, "count": len(items)})
    return {"items": items}


@admin_router.get("/registrations/{registration_id}", response_model=dict)
async def get_registration(registration_id: str, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_READ)
    doc = await db.visitor_registrations.find_one({"registration_id": registration_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    view = staff_view(doc, can(current_user, VISITORS_RESTRICTED_READ))
    if doc.get("has_restricted") and can(current_user, VISITORS_RESTRICTED_READ):
        restricted = await db.visitor_restricted.find_one({"registration_id": registration_id}, {"_id": 0, "prayer_request": 1, "counseling_note": 1, "needs_note": 1})
        view["restricted"] = restricted
        await audit("restricted_viewed", current_user["user_id"], {"registration_id": registration_id})
    await audit("registration_viewed", current_user["user_id"], {"registration_id": registration_id})
    return view


# ------------------------------------------------------------------ V2: seguimiento por servicio y fecha
RESTRICTED_REQUESTS = {"counseling_personal", "counseling_marriage", "counseling_family", "support_child", "other_help"}
FOLLOWUP_LABELS = {"pending": "Pendiente de asignar", "assigned": "Asignado", "in_progress": "En contacto", "done": "Completado", "not_requested": "No pidió seguimiento"}
ATTEMPT_KINDS = {"call": "Llamada", "visit": "Visita", "message": "Mensaje"}
OUTCOMES = {"reached": "Se habló con la persona", "no_answer": "No contestó", "wrong_number": "Número equivocado", "visit_done": "Visita realizada",
            "wants_more": "Quiere más información o acompañamiento", "declined": "Prefiere no recibir seguimiento", "other": "Otro resultado"}


def followup_view(doc: dict, current_user: dict, names: dict) -> dict:
    """Lo necesario para dar seguimiento. Consejería y necesidades: el tipo de pedido
    solo lo ve quien tiene el permiso restringido; el resto ve «Pedido confidencial»."""
    restricted_ok = can(current_user, VISITORS_RESTRICTED_READ)
    requests = doc.get("requests") or []
    shown = [REQUEST_LABELS[item] for item in requests if restricted_ok or item not in RESTRICTED_REQUESTS]
    if not restricted_ok and (any(item in RESTRICTED_REQUESTS for item in requests) or doc.get("has_restricted")):
        shown.append("Pedido confidencial (lo atiende el equipo pastoral)")
    followup = doc.get("followup") or {}
    return {"registration_id": doc["registration_id"], "visitor_number": doc["visitor_number"], "name": f"{doc['first_name']} {doc['last_name']}", "preferred_name": doc["welcome"]["preferred_name"],
            "service": doc["service"], "created_at": doc["created_at"].isoformat(), "person_id": doc.get("person_id"), "match_status": doc["match_status"], "match_label": MATCH_LABELS.get(doc["match_status"]),
            "possible_person_ids": doc.get("possible_person_ids") or [], "possible_people": [{"person_id": pid, "name": names.get(pid) or "Persona sin nombre"} for pid in doc.get("possible_person_ids") or []],
            "phone": doc["contact"].get("phone"), "email": doc["contact"].get("email"), "contact_method": doc["contact"].get("method"), "city": doc["contact"].get("city"),
            "first_visit": doc["visit"].get("first_visit"), "requests": shown, "has_restricted": bool(doc.get("has_restricted") or any(item in RESTRICTED_REQUESTS for item in requests)),
            "status": followup.get("status", "pending"), "status_label": FOLLOWUP_LABELS.get(followup.get("status", "pending")),
            "assigned_person_id": followup.get("assigned_person_id"), "assigned_name": names.get(followup.get("assigned_person_id")) if followup.get("assigned_person_id") else None,
            "attempts": [{**item, "at": item["at"].isoformat() if isinstance(item.get("at"), datetime) else item.get("at"), "kind_label": ATTEMPT_KINDS.get(item.get("kind")), "outcome_label": OUTCOMES.get(item.get("outcome"))}
                         for item in followup.get("results") or []], "consent_followup": doc["consents"]["followup"]}


async def names_for(docs: list) -> dict:
    from front_groups import person_names
    ids = set()
    for doc in docs:
        ids |= set(doc.get("possible_person_ids") or [])
        ids.add((doc.get("followup") or {}).get("assigned_person_id"))
    return await person_names(ids)


def is_assignee(doc: dict, current_user: dict) -> bool:
    return bool(current_user.get("person_id")) and (doc.get("followup") or {}).get("assigned_person_id") == current_user["person_id"]


@admin_router.get("/followup", response_model=dict)
async def followup_list(service_date: Optional[str] = None, service_kind: Optional[str] = None, status: Optional[str] = None, mine: bool = False,
                        current_user: dict = Depends(get_current_user)):
    """Seguimiento por servicio y fecha. Quien no administra el seguimiento solo ve lo que le asignaron."""
    manager = can(current_user, VISITORS_FOLLOWUP_MANAGE)
    query: dict = {}
    if service_date:
        query["service.date"] = service_date
    if service_kind:
        query["service.kind"] = service_kind
    if status:
        query["followup.status"] = status
    if mine or not manager:
        if not current_user.get("person_id"):
            return {"items": [], "can_manage": False}
        query["followup.assigned_person_id"] = current_user["person_id"]
    docs = await db.visitor_registrations.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    names = await names_for(docs)
    counts: dict = {}
    for doc in docs:
        key = (doc.get("followup") or {}).get("status", "pending")
        counts[key] = counts.get(key, 0) + 1
    await audit("followup_viewed", current_user["user_id"], {"service_date": service_date, "count": len(docs)})
    return {"items": [followup_view(doc, current_user, names) for doc in docs], "can_manage": manager, "can_restricted": can(current_user, VISITORS_RESTRICTED_READ),
            "counts": [{"status": key, "label": FOLLOWUP_LABELS[key], "count": counts.get(key, 0)} for key in FOLLOWUP_LABELS]}


@admin_router.get("/followup/mine-count", response_model=dict)
async def followup_mine_count(current_user: dict = Depends(get_current_user)):
    """Para el menú: visitantes asignados a esta persona que siguen abiertos."""
    if not current_user.get("person_id"):
        return {"count": 0}
    return {"count": await db.visitor_registrations.count_documents({"followup.assigned_person_id": current_user["person_id"], "followup.status": {"$in": ["assigned", "in_progress"]}})}


@admin_router.get("/followup/assignees", response_model=dict)
async def followup_assignees(q: str = "", current_user: dict = Depends(get_current_user)):
    """Servidores con cuenta en la plataforma a quienes se puede asignar el seguimiento."""
    require(current_user, VISITORS_FOLLOWUP_MANAGE)
    from front_groups import person_names
    from person_matching import normalize_text
    person_ids = list({item["person_id"] async for item in db.users.find({"person_id": {"$nin": [None, ""]}, "is_active": {"$ne": False}}, {"_id": 0, "person_id": 1})})
    names = await person_names(person_ids)
    words = normalize_text(q).split()
    items = [{"person_id": pid, "name": names.get(pid) or "Persona sin nombre"} for pid in person_ids]
    # Sin acentos y por palabras: «luis eduardo» encuentra «Luis Eduardo Jiménez».
    items = [item for item in items if all(word in normalize_text(item["name"]) for word in words)]
    return {"items": sorted(items, key=lambda item: item["name"])[:30]}


async def load_registration(registration_id: str) -> dict:
    doc = await db.visitor_registrations.find_one({"registration_id": registration_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return doc


async def followup_reply(registration_id: str, current_user: dict) -> dict:
    doc = await load_registration(registration_id)
    return followup_view(doc, current_user, await names_for([doc]))


class AssignFollowupInput(BaseModel):
    person_id: Optional[str] = Field(default=None, max_length=80)


@admin_router.post("/registrations/{registration_id}/assign", response_model=dict)
async def assign_followup(registration_id: str, payload: AssignFollowupInput, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_FOLLOWUP_MANAGE)
    doc = await load_registration(registration_id)
    if payload.person_id and not await db.users.find_one({"person_id": payload.person_id, "is_active": {"$ne": False}}, {"_id": 1}):
        raise HTTPException(status_code=422, detail="Esa persona no tiene una cuenta activa en la plataforma")
    status = (doc.get("followup") or {}).get("status", "pending")
    if status in ("pending", "assigned", "not_requested") or not payload.person_id:
        status = "assigned" if payload.person_id else "pending"
    await db.visitor_registrations.update_one({"registration_id": registration_id}, {"$set": {"followup.assigned_person_id": payload.person_id, "followup.status": status,
                                                                                            "followup.assigned_at": now_utc(), "followup.assigned_by": current_user["user_id"]}})
    await audit("followup_assigned", current_user["user_id"], {"registration_id": registration_id, "person_id": payload.person_id})
    return await followup_reply(registration_id, current_user)


class AttemptInput(BaseModel):
    kind: Literal["call", "visit", "message"]
    outcome: Literal["reached", "no_answer", "wrong_number", "visit_done", "wants_more", "declined", "other"]
    note: Optional[str] = Field(default=None, max_length=1000)
    complete: bool = False
    idempotency_key: str = Field(min_length=8, max_length=120)


@admin_router.post("/registrations/{registration_id}/attempts", response_model=dict)
async def add_attempt(registration_id: str, payload: AttemptInput, current_user: dict = Depends(get_current_user)):
    """Llamada, visita o mensaje con su resultado (quien administra o la persona asignada)."""
    doc = await load_registration(registration_id)
    if not (can(current_user, VISITORS_FOLLOWUP_MANAGE) or is_assignee(doc, current_user)):
        raise HTTPException(status_code=403, detail="Solo quien administra el seguimiento o la persona asignada")
    if any(item.get("key") == payload.idempotency_key for item in (doc.get("followup") or {}).get("results") or []):
        return await followup_reply(registration_id, current_user)
    entry = {"key": payload.idempotency_key, "kind": payload.kind, "outcome": payload.outcome, "note": (payload.note or "").strip() or None, "at": now_utc(),
             "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre")}
    status = "done" if payload.complete or payload.outcome == "declined" else "in_progress"
    await db.visitor_registrations.update_one({"registration_id": registration_id, "followup.results.key": {"$ne": payload.idempotency_key}},
                                              {"$push": {"followup.results": entry}, "$set": {"followup.status": status, "followup.updated_at": now_utc()}})
    await audit("followup_attempt", current_user["user_id"], {"registration_id": registration_id, "kind": payload.kind, "outcome": payload.outcome})
    return await followup_reply(registration_id, current_user)


class ReopenInput(BaseModel):
    status: Literal["pending", "assigned", "in_progress", "done"]


@admin_router.post("/registrations/{registration_id}/followup-status", response_model=dict)
async def set_followup_status(registration_id: str, payload: ReopenInput, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_FOLLOWUP_MANAGE)
    await load_registration(registration_id)
    await db.visitor_registrations.update_one({"registration_id": registration_id}, {"$set": {"followup.status": payload.status, "followup.updated_at": now_utc()}})
    await audit("followup_status", current_user["user_id"], {"registration_id": registration_id, "status": payload.status})
    return await followup_reply(registration_id, current_user)


class ResolveMatchInput(BaseModel):
    person_id: Optional[str] = Field(default=None, max_length=80)
    create_new: bool = False


@admin_router.post("/registrations/{registration_id}/resolve-match", response_model=dict)
async def resolve_match(registration_id: str, payload: ResolveMatchInput, current_user: dict = Depends(get_current_user)):
    """Revisión humana de «posible coincidencia»: es la misma persona (vincular) o es otra (crear)."""
    require(current_user, VISITORS_FOLLOWUP_MANAGE)
    doc = await load_registration(registration_id)
    if doc["match_status"] != "possible":
        raise HTTPException(status_code=409, detail="Este registro ya está vinculado a Persona 360")
    if payload.create_new:
        person_id = await create_distinct_person(doc, current_user)
        status = "created"
    elif payload.person_id and payload.person_id in (doc.get("possible_person_ids") or []):
        person_id, status = payload.person_id, "linked"
    else:
        raise HTTPException(status_code=422, detail="Elija una de las personas sugeridas o «Es otra persona»")
    await db.visitor_registrations.update_one({"registration_id": registration_id, "match_status": "possible"},
                                              {"$set": {"person_id": person_id, "match_status": status, "match_resolved": {"by_user_id": current_user["user_id"], "at": now_utc()}}})
    await audit("match_resolved", current_user["user_id"], {"registration_id": registration_id, "person_id": person_id, "result": status})
    return await followup_reply(registration_id, current_user)


async def create_distinct_person(doc: dict, current_user: dict) -> str:
    """Crea la persona confirmada como distinta (p. ej. familiares que comparten teléfono)."""
    from core_person import next_person_number
    from person_matching import normalize_phone, normalize_text
    existing = await db.persons.find_one({"idempotency_key": f"visitor-distinct:{doc['registration_id']}"}, {"_id": 1})
    if existing:
        return str(existing["_id"])
    now = now_utc()
    person = {"nombre": doc["first_name"], "apellido": doc["last_name"], "fecha_nacimiento": doc["contact"].get("birth_date"), "person_number": await next_person_number(),
              "search_key": normalize_text(f"{doc['first_name']} {doc['last_name']}"), "idempotency_key": f"visitor-distinct:{doc['registration_id']}", "version": 1,
              "created_by_user_id": current_user["user_id"], "created_source": "visitor_review", "created_at": now, "updated_at": now,
              "distinct_person_confirmed": {"reason": "Revisión del registro de visitantes", "candidates": doc.get("possible_person_ids") or [], "by_user_id": current_user["user_id"], "at": now}}
    result = await db.persons.insert_one(person)
    person_id = str(result.inserted_id)
    if doc["contact"].get("phone"):
        await db.person_contacts.insert_one({"person_id": person_id, "tipo": "telefono", "valor": doc["contact"]["phone"], "valor_normalizado": normalize_phone(doc["contact"]["phone"]), "es_principal": True,
                                             "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now})
    return person_id
