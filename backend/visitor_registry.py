"""Registro digital de visitantes (V1): tabletas en modo quiosco.

Seguridad del quiosco (sin fricción):
- UN enlace único para todas las tabletas, con un token largo e impredecible
  cuyo ÚNICO permiso es crear registros (no puede leer nada). «Generar enlace
  nuevo» invalida el anterior en el acto. Sin códigos ni sesiones de personal.
- Límite de frecuencia por tableta y por conexión, y un campo trampa contra robots.
- Cada tableta se nombra sola («Tableta 3F9A») solo para saber de dónde vino.

Registro:
- Número único ATÓMICO en el servidor (V-AAAA-000001), nunca en la tableta.
- Clave de idempotencia ÚNICA por envío: un doble toque o un reintento sin
  internet devuelven el mismo registro.
- Persona 360: misma búsqueda de duplicados del directorio (teléfono, correo,
  nombre + nacimiento). Una coincidencia clara se vincula; si es dudosa se crea su
  perfil igual (ningún registro queda fuera) y el personal confirma en
  Seguimiento si era una persona que ya existía (nunca se fusiona sola).
- Datos separados: bienvenida (solo el nombre para leer en voz alta),
  contacto y RESTRINGIDOS (oración, consejería, necesidades) en otra colección.
- Textos editables (bienvenida, aviso de privacidad versionado, confirmación) y
  la versión del aviso aceptado queda en cada registro. Auditoría de todo."""
import hashlib
import hmac
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from access_control import (
    VISITORS_DEVICES_MANAGE, VISITORS_FOLLOWUP_MANAGE, VISITORS_READ, VISITORS_RESTRICTED_READ, VISITORS_TEXTS_MANAGE, VISITORS_WELCOME_OPERATE,
    has_capability, is_global_pastoral_authority,
)
from server import db, get_current_user

admin_router = APIRouter(prefix="/api/visitors", tags=["visitors"])
kiosk_router = APIRouter(prefix="/api/kiosk", tags=["visitor-kiosk"])

TEXTS_ID = "visitor_texts"
# Cada línea del texto es una frase en pantalla: 1.ª título, 2.ª subtítulo, 3.ª la frase
# PRINCIPAL (bloque destacado, siempre completa) y las demás, secundarias, al final.
MAIN_PHRASE = "Esperamos que hagas de esta iglesia tu casa y de esta familia tu familia."
DEFAULT_TEXTS = {
    "welcome": "¡Bienvenido a Casa de Oración!\n¡Nos alegra que estés aquí!\n" + MAIN_PHRASE + "\nQueremos conocerte y saber cómo podemos servirte.",
    "privacy": "Usamos tus datos solo para darte la bienvenida y servirte mejor.\nNo los compartimos con nadie fuera de la iglesia.\nPuedes pedir que los corrijamos o borremos cuando quieras.",
    "confirmation": "¡Gracias por registrarte!\nYa eres parte de esta familia.\nSi necesitas algo, muestra este número a cualquier servidor de la iglesia.",
}
# Mismos textos en inglés (la persona elige el idioma en la primera pantalla de la tableta).
DEFAULT_TEXTS_EN = {
    "welcome": "Welcome to Casa de Oración!\nWe are glad you are here!\nWe hope you make this church your home and this family your family.\nWe want to get to know you and learn how we can serve you.",
    "privacy": "We use your information only to welcome you and serve you better.\nWe do not share it with anyone outside the church.\nYou can ask us to correct or delete it at any time.",
    "confirmation": "Thank you for registering!\nYou are now part of this family.\nIf you need anything, show this number to any church volunteer.",
}
LANGUAGES = {"es": "Español", "en": "English"}
# Textos de la primera versión (un solo párrafo): si siguen sin editar, se usan los nuevos.
LEGACY_TEXTS = {
    "¡Bienvenido a Casa de Oración!\n¡Nos alegra que estés aquí!\nEsperamos que hagas de esta iglesia tu casa\ny de esta familia tu familia.\nQueremos conocerte y saber cómo podemos servirte.",
    "¡Bienvenido a Casa de Oración! Nos alegra que estés aquí. Esperamos que hagas de esta iglesia tu casa y de esta familia tu familia. Queremos conocerte y saber cómo podemos servirte.",
    "Usamos tus datos solo para darte la bienvenida, comunicarnos contigo si lo autorizas y servirte mejor. Los cuida un equipo autorizado de la iglesia; no los compartimos con nadie fuera de la iglesia. Tu nombre solo se anuncia o se muestra en pantallas si tú lo autorizas. Puedes pedir en cualquier momento que corrijamos o borremos tus datos.",
    "¡Gracias por registrarte! Ya eres parte de esta familia. Si necesitas algo, muestra este número a cualquier servidor de la iglesia.",
}
from visitor_form import REQUEST_KEYS, REQUEST_LABELS, RESTRICTED_REQUESTS, alert_urgent, answers, build_tasks, merge_followup  # noqa: E402


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
    await db.visitor_registrations.create_index("person_id")
    await db.visitor_rate.create_index("expires_at", expireAfterSeconds=0)
    # Migración segura de la primera versión: una forma de contacto → lista (no se borra nada).
    await db.visitor_registrations.update_many({"contact.methods": {"$exists": False}, "contact.method": {"$in": ["call", "text", "whatsapp", "email"]}},
                                               [{"$set": {"contact.methods": ["$contact.method"]}}])
    await db.visitor_registrations.update_many({"contact.methods": {"$exists": False}}, {"$set": {"contact.methods": []}})
    _indexes_ready = True


# ------------------------------------------------------------------ textos
async def load_texts() -> dict:
    doc = await db.app_settings.find_one({"_id": TEXTS_ID}, {"_id": 0}) or {}
    pick = lambda key: doc.get(key) if doc.get(key) and doc.get(key) not in LEGACY_TEXTS else DEFAULT_TEXTS[key]  # noqa: E731
    english = {key: doc.get(f"{key}_en") or value for key, value in DEFAULT_TEXTS_EN.items()}
    return {"welcome": keep_main_phrase(pick("welcome")), "privacy": pick("privacy"), "privacy_version": (doc.get("privacy_version") or 1) + (1 if doc.get("privacy") in LEGACY_TEXTS else 0), "confirmation": pick("confirmation"),
            "welcome_en": english["welcome"], "privacy_en": english["privacy"], "confirmation_en": english["confirmation"],
            "updated_at": doc.get("updated_at"), "updated_by": doc.get("updated_by_name")}


def texts_in(texts: dict, language: Optional[str]) -> dict:
    """Los textos públicos en el idioma que eligió la persona."""
    suffix = "_en" if language == "en" else ""
    return {"welcome": texts[f"welcome{suffix}"], "privacy": texts[f"privacy{suffix}"], "confirmation": texts[f"confirmation{suffix}"], "privacy_version": texts["privacy_version"]}


def keep_main_phrase(text: str) -> str:
    """La frase principal nunca queda partida en dos líneas (se une si alguien la cortó)."""
    return re.sub(r"tu casa\s*\n\s*y de esta familia", "tu casa y de esta familia", text)


class TextsInput(BaseModel):
    welcome: str = Field(min_length=10, max_length=1500)
    privacy: str = Field(min_length=20, max_length=3000)
    confirmation: str = Field(min_length=5, max_length=800)
    # En inglés (si no llegan, se conservan los actuales).
    welcome_en: Optional[str] = Field(default=None, min_length=10, max_length=1500)
    privacy_en: Optional[str] = Field(default=None, min_length=20, max_length=3000)
    confirmation_en: Optional[str] = Field(default=None, min_length=5, max_length=800)


@admin_router.get("/texts", response_model=dict)
async def get_texts(current_user: dict = Depends(get_current_user)):
    if not any(can(current_user, cap) for cap in (VISITORS_TEXTS_MANAGE, VISITORS_DEVICES_MANAGE, VISITORS_READ)):
        raise HTTPException(status_code=403, detail="Sin permiso para el Registro de visitantes")
    return await load_texts()


@admin_router.put("/texts", response_model=dict)
async def put_texts(payload: TextsInput, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_TEXTS_MANAGE)
    current = await load_texts()
    privacy_en = (payload.privacy_en or current["privacy_en"]).strip()
    changed = payload.privacy.strip() != current["privacy"].strip() or privacy_en != current["privacy_en"].strip()
    version = current["privacy_version"] + (1 if changed else 0)
    english = {"welcome_en": (payload.welcome_en or current["welcome_en"]).strip(), "privacy_en": privacy_en, "confirmation_en": (payload.confirmation_en or current["confirmation_en"]).strip()}
    await db.app_settings.update_one({"_id": TEXTS_ID}, {"$set": {"welcome": keep_main_phrase(payload.welcome.strip()), "privacy": payload.privacy.strip(), "privacy_version": version, **english,
                                                                    "confirmation": payload.confirmation.strip(), "updated_at": now_utc(), "updated_by_user_id": current_user["user_id"],
                                                                    "updated_by_name": current_user.get("nombre")},
                                                           "$push": {"history": {"privacy_version": version, "privacy": payload.privacy.strip(), "privacy_en": privacy_en, "at": now_utc(), "by": current_user["user_id"]}}}, upsert=True)
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


# ------------------------------------------------------------------ enlaces (tabletas y pantalla)
LINKS_ID = "visitor_links"
LINK_KINDS = {"tablet": "Enlace de tabletas", "screen": "Enlace de pantalla de bienvenida"}
LINK_PATHS = {"tablet": "/quiosco", "screen": "/pantalla-bienvenida"}  # enlace largo anterior (sigue funcionando hasta «Generar enlace nuevo»)
SHORT_PATHS = {"tablet": "/r", "screen": "/b"}
# Código corto: fácil de escribir y de dictar, sin letras ni números que se confunden (0/O, 1/I/L).
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
TABLET_NAME = re.compile(r"^Tableta [0-9A-F]{4}$")


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(value: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


async def load_links() -> dict:
    """Dos enlaces: código corto impredecible (31^8 combinaciones) + el token largo anterior."""
    doc = await db.app_settings.find_one({"_id": LINKS_ID}, {"_id": 0}) or {}
    changes = {}
    for kind in LINK_KINDS:
        item = dict(doc.get(kind) or {})
        if not item.get("token"):
            item.update({"token": secrets.token_urlsafe(32), "created_at": now_utc(), "created_by": None})
        if not item.get("code"):
            taken = {(doc.get(other) or {}).get("code") for other in LINK_KINDS} | {(changes.get(other) or {}).get("code") for other in LINK_KINDS}
            item["code"] = next(code for code in iter(new_code, None) if code not in taken)
        if item != (doc.get(kind) or {}):
            changes[kind] = item
    for kind, item in changes.items():
        # Solo se escribe si sigue faltando (dos pedidos a la vez no pueden dejar códigos distintos).
        missing = {"$or": [{f"{kind}.code": {"$exists": False}}, {f"{kind}.code": None}, {f"{kind}.token": {"$exists": False}}]}
        try:
            await db.app_settings.update_one({"_id": LINKS_ID, **missing}, {"$set": {kind: item}}, upsert=True)
        except DuplicateKeyError:
            pass  # otro pedido lo creó al mismo tiempo: se usa el suyo
    if changes:
        doc = await db.app_settings.find_one({"_id": LINKS_ID}, {"_id": 0})
    return doc


def link_view(kind: str, item: dict) -> dict:
    return {"kind": kind, "label": LINK_KINDS[kind], "path": f"{SHORT_PATHS[kind]}/{item['code']}", "code": item["code"], "legacy_path": f"{LINK_PATHS[kind]}/{item['token']}",
            "created_at": item["created_at"].isoformat() if item.get("created_at") else None}


@admin_router.get("/links", response_model=dict)
async def get_links(current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_DEVICES_MANAGE)
    links = await load_links()
    await audit("links_viewed", current_user["user_id"])
    return {"items": [link_view(kind, links[kind]) for kind in LINK_KINDS]}


@admin_router.post("/links/{kind}/rotate", response_model=dict)
async def rotate_link(kind: Literal["tablet", "screen"], current_user: dict = Depends(get_current_user)):
    """Enlace nuevo (por si se filtró): el código corto Y el enlace largo anteriores dejan de funcionar en el acto."""
    require(current_user, VISITORS_DEVICES_MANAGE)
    links = await load_links()
    taken = {(links.get(other) or {}).get("code") for other in LINK_KINDS}
    item = {"token": secrets.token_urlsafe(32), "code": next(code for code in iter(new_code, None) if code not in taken), "created_at": now_utc(), "created_by": current_user["user_id"]}
    await db.app_settings.update_one({"_id": LINKS_ID}, {"$set": {kind: item}})
    await audit("link_rotated", current_user["user_id"], {"kind": kind})
    return link_view(kind, item)


async def link_access(kind: str, token: Optional[str], request: Optional[Request] = None) -> dict:
    """Vale el código corto (sin importar mayúsculas, espacios o guiones) o el enlace largo anterior.
    Muchos intentos fallidos desde la misma conexión se bloquean un rato (no se puede adivinar)."""
    links = await load_links()
    item = links[kind]
    given = (token or "").strip()
    if given and (hmac.compare_digest(given, item["token"]) or hmac.compare_digest(normalize_code(given), item["code"])):
        return item
    if request is not None:
        try:
            await rate_limit(f"linkfail:{client_ip(request)}", 30, 600)
        except HTTPException:
            raise HTTPException(status_code=429, detail="Demasiados intentos con un enlace equivocado. Espere unos minutos.")
    raise HTTPException(status_code=401, detail="Este enlace ya no funciona. Pida el enlace nuevo a la administración.")


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return (forwarded.split(",")[0].strip() if forwarded else None) or (request.client.host if request.client else "desconocida")


async def rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    """Límite de frecuencia compartido entre procesos (contador por ventana en Mongo)."""
    now = now_utc()
    window = int(now.timestamp() // window_seconds)
    doc = await db.visitor_rate.find_one_and_update({"_id": f"{key}:{window}"}, {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": now + timedelta(seconds=window_seconds * 2)}},
                                                    upsert=True, return_document=ReturnDocument.AFTER)
    if doc["count"] > limit:
        raise HTTPException(status_code=429, detail="Demasiados registros seguidos desde esta tableta. Espere un minuto e intente de nuevo.")


async def kiosk_device(request: Request, x_link_token: Optional[str] = Header(default=None), x_tablet_name: Optional[str] = Header(default=None),
                       link: Optional[str] = Query(default=None, max_length=80), tablet: Optional[str] = Query(default=None, max_length=40)) -> dict:
    """Tableta: solo el enlace de tabletas. Se identifica sola («Tableta 3F9A») para trazabilidad.
    El código puede llegar en el encabezado o en la dirección (?link=…): así la lectura de la
    configuración es un pedido «simple» que el navegador no necesita autorizar antes."""
    item = await link_access("tablet", x_link_token or link, request)
    tablet_name = x_tablet_name or tablet
    name = tablet_name if tablet_name and TABLET_NAME.match(tablet_name) else "Tableta sin nombre"
    return {"device_id": name, "name": name, "ip": client_ip(request), "short_path": f"{SHORT_PATHS['tablet']}/{item['code']}"}


KIOSK_SETTINGS_ID = "visitor_kiosk_settings"
# Tiempos de espera (segundos): aviso «¿Sigues ahí?» y limpieza en el formulario,
# limpieza de la pantalla de inicio y regreso al inicio desde la confirmación.
DEFAULT_KIOSK_SETTINGS = {"form_warn_seconds": 240, "form_reset_seconds": 300, "start_reset_seconds": 600, "confirm_reset_seconds": 60}


async def load_kiosk_settings() -> dict:
    doc = await db.app_settings.find_one({"_id": KIOSK_SETTINGS_ID}, {"_id": 0}) or {}
    # «Pedir año de nacimiento»: apagado por defecto (por privacidad solo día y mes).
    return {**{key: int(doc.get(key) or value) for key, value in DEFAULT_KIOSK_SETTINGS.items()}, "ask_birth_year": bool(doc.get("ask_birth_year"))}


class KioskSettingsInput(BaseModel):
    form_warn_seconds: int = Field(ge=30, le=3600)
    form_reset_seconds: int = Field(ge=60, le=3600)
    start_reset_seconds: int = Field(ge=60, le=7200)
    confirm_reset_seconds: int = Field(ge=10, le=600)
    ask_birth_year: bool = False


@admin_router.get("/kiosk-settings", response_model=dict)
async def get_kiosk_settings(current_user: dict = Depends(get_current_user)):
    if not any(can(current_user, cap) for cap in (VISITORS_TEXTS_MANAGE, VISITORS_DEVICES_MANAGE)):
        raise HTTPException(status_code=403, detail="Sin permiso para el Registro de visitantes")
    return await load_kiosk_settings()


@admin_router.put("/kiosk-settings", response_model=dict)
async def put_kiosk_settings(payload: KioskSettingsInput, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_TEXTS_MANAGE)
    if payload.form_warn_seconds >= payload.form_reset_seconds:
        raise HTTPException(status_code=422, detail="El aviso debe salir antes de limpiar el formulario")
    await db.app_settings.update_one({"_id": KIOSK_SETTINGS_ID}, {"$set": {**payload.model_dump(), "updated_at": now_utc(), "updated_by": current_user["user_id"]}}, upsert=True)
    await audit("kiosk_settings_changed", current_user["user_id"], payload.model_dump())
    return await load_kiosk_settings()


KIOSK_API_VERSION = 5  # sube cuando cambia lo que la tableta necesita del servidor


@kiosk_router.get("/ping", response_model=dict)
async def kiosk_ping():
    """Diagnóstico de la tableta (sin datos ni permisos): ¿llega al servidor y es la versión nueva?"""
    return {"ok": True, "kiosk_api": KIOSK_API_VERSION}


@kiosk_router.get("/config", response_model=dict)
async def kiosk_config(device: dict = Depends(kiosk_device)):
    """Lo único que la tableta puede leer: textos públicos y el servicio de hoy."""
    texts = await load_texts()
    settings = await load_kiosk_settings()
    return {"device_name": device["name"], "service": await current_service(),
            "texts": texts_in(texts, "es"), "texts_en": texts_in(texts, "en"),
            "timeouts": {key: settings[key] for key in DEFAULT_KIOSK_SETTINGS}, "ask_birth_year": settings["ask_birth_year"],
            # Dirección corta de esta tableta: si se abrió con el enlace largo anterior, la página pasa a la corta.
            "short_path": device["short_path"]}


class FamilyMember(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relation: Optional[str] = Field(default=None, max_length=60)
    is_minor: bool = False


class ChildInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    age: Optional[int] = Field(default=None, ge=0, le=60)


class RegistrationInput(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=120)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    preferred_name: Optional[str] = Field(default=None, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=160)
    # Varias formas de contacto (casillas). `contact_method` (una sola) queda por registros guardados sin internet.
    contact_methods: list[Literal["call", "text", "whatsapp", "email"]] = Field(default_factory=list, max_length=4)
    contact_method: Optional[Literal["call", "whatsapp", "text", "email", "none"]] = None
    city: Optional[str] = Field(default=None, max_length=120)
    address: Optional[str] = Field(default=None, max_length=300)
    birth_date: Optional[date] = None
    # Cumpleaños SIN año (por privacidad): día y mes. El año solo si la administración lo pide.
    birth_day: Optional[int] = Field(default=None, ge=1, le=31)
    birth_month: Optional[int] = Field(default=None, ge=1, le=12)
    # Idioma que eligió en la tableta (para que el equipo sepa en qué idioma contactarle).
    language: Literal["es", "en"] = "es"
    # Sexo (solo para asignar el seguimiento; nunca se muestra en pantallas públicas).
    sex: Optional[Literal["female", "male"]] = None
    # «¿Eres nuevo en esta área?» (del papel de la iglesia).
    new_in_area: Optional[bool] = None
    first_visit: Optional[bool] = None
    invited: Optional[bool] = None
    invited_by: Optional[str] = Field(default=None, max_length=120)
    # «¿Cómo nos visitas hoy?» (ya no se pregunta; se acepta por registros viejos en cola).
    # `visiting_from` tampoco se guarda.
    visit_mode: Optional[Literal["nearby", "other_city", "passing", "new_in_area"]] = None
    zip_code: Optional[str] = Field(default=None, max_length=12)
    # Tu fe (de las hojas en papel).
    faith_christian: Optional[Literal["yes", "on_way", "not_yet"]] = None
    accept_jesus: Optional[Literal["today", "another_day"]] = None
    reconcile: bool = False
    faith_info: bool = False
    other_church_pastor: Optional[str] = Field(default=None, max_length=160)
    # Familia.
    marital_status: Optional[Literal["single", "married", "other"]] = None
    spouse_name: Optional[str] = Field(default=None, max_length=160)
    has_children: Optional[bool] = None
    children: list[ChildInput] = Field(default_factory=list, max_length=30)
    companions: Optional[str] = Field(default=None, max_length=300)
    kids_ministry: bool = False
    # Apoyo: solo el interés (nunca datos de pago); se enruta a Finanzas.
    giving_info: bool = False
    visiting_from: Optional[str] = Field(default=None, max_length=160)
    other_church: Optional[bool] = None
    other_church_name: Optional[str] = Field(default=None, max_length=160)
    how_heard: Optional[str] = Field(default=None, max_length=200)
    family: list[FamilyMember] = Field(default_factory=list, max_length=12)
    requests: list[Literal["prayer_me", "prayer_family", "call_prayer", "visit", "info", "counseling_personal", "counseling_marriage", "counseling_family", "support_child",
                           "membership", "serve", "home_service", "other_help", "no_followup", "prayer"]] = Field(default_factory=list)
    prayer_request: Optional[str] = Field(default=None, max_length=1500)
    counseling_note: Optional[str] = Field(default=None, max_length=1500)
    needs_note: Optional[str] = Field(default=None, max_length=1500)
    # Única pregunta: «¿Podemos comunicarnos contigo para darte seguimiento?» (opcional).
    consent_followup: Optional[bool] = None
    # Campo trampa: invisible para personas; si llega con texto, es un robot.
    website: Optional[str] = Field(default=None, max_length=200)
    privacy_version: int = Field(ge=1)
    privacy_accepted: bool
    started_at: Optional[datetime] = None

    @model_validator(mode="after")
    def birthday_exists(self):
        if (self.birth_day is None) != (self.birth_month is None):
            raise ValueError("Elige el día y el mes de tu cumpleaños")
        if self.birth_day and self.birth_day > [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][self.birth_month - 1]:
            raise ValueError("Esa fecha no existe")
        if self.birth_date:  # con año: el día y el mes salen de la fecha completa
            self.birth_day, self.birth_month = self.birth_date.day, self.birth_date.month
        return self


async def next_number(year: int) -> str:
    counter = await db.counters.find_one_and_update({"_id": f"visitor_number_{year}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return f"V-{year}-{counter['seq']:06d}"


def normalize_phone_digits(phone: Optional[str]) -> Optional[str]:
    from person_matching import normalize_phone
    return normalize_phone(phone)


def kiosk_reply(doc: dict, duplicate: bool, texts: dict) -> dict:
    """La tableta solo recibe el número, el nombre para saludar y el mensaje."""
    confirmation = texts["confirmation_en"] if doc.get("language") == "en" else texts["confirmation"]
    return {"visitor_number": doc["visitor_number"], "greeting_name": doc["welcome"]["preferred_name"], "confirmation": confirmation, "duplicate": duplicate}


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
    # Dudosa (p. ej. el mismo teléfono con otro nombre): se crea su perfil en Persona 360 para que
    # nunca quede fuera, y el personal confirma en Seguimiento si era la misma persona.
    person_id = await insert_person(payload.first_name.strip(), payload.last_name.strip(), payload.birth_date.isoformat() if payload.birth_date else None, payload.phone, payload.email,
                                    f"visitor:{payload.idempotency_key}", f"device:{device['device_id']}", "visitor_kiosk", candidates)
    return {"person_id": person_id, "match_status": "possible", "candidates": candidates}


async def insert_person(first: str, last: str, birth: Optional[str], phone: Optional[str], email: Optional[str], key: str, actor: str, source: str, candidates: list) -> str:
    """Persona confirmada como distinta de las sugeridas (p. ej. familiares que comparten teléfono)."""
    from core_person import next_person_number
    from person_matching import normalize_phone, normalize_text
    existing = await db.persons.find_one({"idempotency_key": key}, {"_id": 1})
    if existing:
        return str(existing["_id"])
    now = now_utc()
    doc = {"nombre": first, "apellido": last, "fecha_nacimiento": birth, "person_number": await next_person_number(), "search_key": normalize_text(f"{first} {last}"),
           "idempotency_key": key, "version": 1, "created_by_user_id": actor, "created_source": source, "created_at": now, "updated_at": now,
           "distinct_person_confirmed": {"reason": "Registro de visitantes: posible coincidencia pendiente de revisión", "candidates": candidates, "by_user_id": actor, "at": now}}
    try:
        person_id = str((await db.persons.insert_one(doc)).inserted_id)
    except DuplicateKeyError:
        return str((await db.persons.find_one({"idempotency_key": key}, {"_id": 1}))["_id"])
    contacts = []
    if phone:
        contacts.append({"person_id": person_id, "tipo": "telefono", "valor": phone, "valor_normalizado": normalize_phone(phone), "es_principal": True, "created_by_user_id": actor, "created_at": now, "updated_at": now})
    if email:
        contacts.append({"person_id": person_id, "tipo": "email", "valor": email, "es_principal": not contacts, "created_by_user_id": actor, "created_at": now, "updated_at": now})
    if contacts:
        await db.person_contacts.insert_many(contacts)
    return person_id


async def fill_person(person_id: str, payload: "RegistrationInput") -> None:
    """Persona 360: sexo y cumpleaños (día y mes) SOLO donde aún falten; nunca se cambia lo que ya tiene.
    Sin año, `fecha_nacimiento` queda vacía: la edad no se calcula ni se inventa."""
    try:
        oid = ObjectId(person_id)
    except Exception:
        return
    if payload.sex:
        await db.persons.update_one({"_id": oid, "$or": [{"genero": {"$in": [None, "", "no_especificado"]}}, {"genero": {"$exists": False}}]},
                                    {"$set": {"genero": {"female": "femenino", "male": "masculino"}[payload.sex], "updated_at": now_utc()}})
    if payload.birth_day and payload.birth_month:
        await db.persons.update_one({"_id": oid, "$or": [{"fecha_nacimiento": {"$in": [None, ""]}}, {"fecha_nacimiento": {"$exists": False}}],
                                     "cumpleanos_mes": {"$in": [None]}},
                                    {"$set": {"cumpleanos_dia": payload.birth_day, "cumpleanos_mes": payload.birth_month, "updated_at": now_utc()}})


async def resolve_inviter(text: str) -> Optional[dict]:
    """Quien invitó, si es UNA persona clara de Persona 360 (nombre y apellido): su nombre completo."""
    from person_matching import normalize_text
    words = [word for word in normalize_text(text).split() if len(word) > 1]
    if len(words) < 2:
        return None
    query = {"$and": [{"search_key": {"$regex": rf"(^|\s){re.escape(word)}"}} for word in words]}
    found = await db.persons.find(query, {"nombre": 1, "apellido": 1}).limit(2).to_list(2)
    if len(found) != 1:
        return None
    person = found[0]
    return {"person_id": str(person["_id"]), "name": " ".join(part for part in [person.get("nombre"), person.get("apellido")] if part)}


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
    draft = existing if existing and existing.get("status") in ("draft", "completing") else None
    if existing and not draft:
        return kiosk_reply(existing, True, texts)
    if not payload.privacy_accepted:
        raise HTTPException(status_code=422, detail="Para registrarte necesitamos que aceptes el aviso de privacidad")
    if payload.consent_followup and not (normalize_phone_digits(payload.phone) or (payload.email or "").strip()):
        raise HTTPException(status_code=422, detail="Para darte seguimiento necesitamos tu teléfono o tu correo")
    # Límite de frecuencia: por tableta y por conexión (las 4 tabletas comparten el internet de la iglesia).
    await rate_limit(f"tablet:{device['name']}:{device['ip']}", 12)
    await rate_limit(f"ip:{device['ip']}", 60)
    if (payload.website or "").strip():
        # Campo trampa lleno: robot. Se responde igual, pero no se guarda nada.
        await audit("bot_blocked", f"device:{device['device_id']}", {"ip": device["ip"]})
        return {"visitor_number": "V-0000-000000", "greeting_name": payload.first_name.strip(), "confirmation": texts_in(texts, payload.language)["confirmation"], "duplicate": False}
    from person_matching import normalize_phone, normalize_text
    service = draft["service"] if draft else await current_service()
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
            mine = (draft or {}).get("registration_id")
            taken = False
            for _ in range(30):
                if mine:
                    current = await db.visitor_registrations.find_one({"registration_id": mine}, {"_id": 0})
                    if current and current.get("status") == "complete":
                        return kiosk_reply(current, True, texts)  # doble toque al terminar un borrador
                # OTRO registro ya completo de la misma persona hoy (el borrador propio, que ya guarda el teléfono, no cuenta).
                same = await db.visitor_registrations.find_one({"service.date": service["date"], "contact.phone_normalized": phone_norm, "name_key": name_key,
                                                                "registration_id": {"$ne": mine}, "status": {"$nin": ["draft", "completing", "merged", "discarded"]}}, {"_id": 0})
                if same:
                    if draft:
                        # La misma persona ya quedó registrada en otra tableta: el borrador se une a ese registro.
                        await db.visitor_registrations.update_one({"registration_id": draft["registration_id"]}, {"$set": {"status": "merged", "merged_into": same["registration_id"], "welcome.hidden": True, "updated_at": now_utc()}})
                    await audit("registration_repeat", f"device:{device['device_id']}", {"registration_id": same["registration_id"]})
                    return kiosk_reply(same, True, texts)
                # Candado viejo sin registro completo (p. ej. descartado): se toma.
                stale = await db.visitor_locks.find_one_and_update({"_id": lock_id, "created_at": {"$lt": now_utc() - timedelta(seconds=20)}},
                                                                   {"$set": {"idempotency_key": payload.idempotency_key, "created_at": now_utc()}})
                if stale:
                    taken = True
                    break
                await asyncio.sleep(0.2)
            if not taken:
                raise HTTPException(status_code=409, detail="Ya se está guardando un registro igual; intente de nuevo en unos segundos")
    try:
        if draft:
            return await complete_draft(draft, payload, device, service, phone_norm, name_key, texts)
        return await insert_registration(payload, device, service, phone_norm, name_key, texts)
    except BaseException:
        if lock_id:
            await db.visitor_locks.delete_one({"_id": lock_id, "idempotency_key": payload.idempotency_key})
        raise


def draft_doc(payload: "RegistrationInput", device: dict, service: dict, name_key: str, number: str) -> dict:
    """Borrador: SOLO nombre y servicio; el resto llega al terminar. Ya entra a la bienvenida."""
    now = now_utc()
    registration_id = str(uuid4())
    return {
        "_id": registration_id, "registration_id": registration_id, "idempotency_key": payload.idempotency_key, "visitor_number": number, "status": "draft",
        "device_id": device["device_id"], "device_name": device["name"], "service": service, "name_key": name_key,
        "person_id": None, "match_status": "pending", "possible_person_ids": [],
        "first_name": payload.first_name.strip(), "last_name": payload.last_name.strip(),
        "welcome": {"preferred_name": (payload.preferred_name or "").strip() or payload.first_name.strip(), "display_name": None, "approved": False, "hidden": False, "invited_by": None, "invited_by_display": None},
        "contact": {"phone": None, "phone_normalized": None, "email": None, "methods": [], "city": None, "address": None, "birth_date": None, "birth_day": None, "birth_month": None},
        "language": payload.language, "profile": {"sex": None},
        "visit": {"first_visit": None, "invited": None, "invited_by": None, "invited_by_person_id": None, "visit_mode": None, "new_in_area": None, "other_church": None, "other_church_name": None, "how_heard": None},
        "family": [], "requests": [], "has_restricted": False, "consents": {"followup": None},
        "privacy": {"version": payload.privacy_version, "accepted_at": now},
        "followup": {"status": "pending", "assigned_person_id": None, "results": []},
        "test_data": False, "created_at": now, "updated_at": now,
    }


def keep_welcome(old: dict, fields: dict) -> dict:
    """Lo que el encargado ya corrigió, quitó o reordenó en la bienvenida se respeta."""
    welcome = old.get("welcome") or {}
    return {**fields["welcome"], **{key: welcome.get(key) for key in ("display_name", "invited_by_display", "manual_name", "order") if welcome.get(key) is not None},
            "hidden": welcome.get("hidden", False)}


async def apply_progress(doc: dict, payload: "RegistrationInput", device: dict) -> None:
    """Paso a paso: todo lo que la persona ya contestó queda en el borrador (sin tocar Persona 360)."""
    from person_matching import normalize_phone, normalize_text
    name_key = normalize_text(f"{payload.first_name} {payload.last_name}")
    fields = await registration_fields(payload, device, doc["service"], normalize_phone(payload.phone), name_key, link=False)
    fields["welcome"] = keep_welcome(doc, fields)
    fields["followup"] = merge_followup(doc.get("followup"), fields["followup"])
    result = await db.visitor_registrations.update_one({"registration_id": doc["registration_id"], "status": "draft"}, {"$set": {**fields, "updated_at": now_utc()}})
    if result.matched_count:
        fresh = await db.visitor_registrations.find_one({"registration_id": doc["registration_id"]}, {"_id": 0})
        await save_restricted(fresh, payload, now_utc())
        # «Aceptar a Jesús» u oración: el aviso sale YA, aunque la persona no termine.
        await alert_urgent(db, fresh)


@kiosk_router.post("/registrations/draft", response_model=dict)
async def save_draft(payload: RegistrationInput, device: dict = Depends(kiosk_device)):
    """Al escribir el nombre el borrador aparece YA en la bienvenida; en cada paso se guarda lo contestado.
    La tableta no recibe nada más."""
    await ensure_indexes()
    if not payload.privacy_accepted:
        raise HTTPException(status_code=422, detail="Para registrarte necesitamos que aceptes el aviso de privacidad")
    await rate_limit(f"draft:{device['name']}:{device['ip']}", 40)
    if (payload.website or "").strip():
        await audit("bot_blocked", f"device:{device['device_id']}", {"ip": device["ip"], "draft": True})
        return {"ok": True}
    from person_matching import normalize_text
    name_key = normalize_text(f"{payload.first_name} {payload.last_name}")
    existing = await db.visitor_registrations.find_one({"idempotency_key": payload.idempotency_key}, {"_id": 0})
    if existing:
        if existing.get("status") == "draft":
            await apply_progress(existing, payload, device)  # siguiente paso o corrigió su nombre
        return {"ok": True}
    service = await current_service()
    # Misma persona, misma tableta, mismo servicio (p. ej. la tableta se reinició): se retoma su borrador.
    again = await db.visitor_registrations.find_one({"service.date": service["date"], "name_key": name_key, "device_name": device["name"], "status": "draft"}, {"_id": 0})
    if again:
        try:
            await db.visitor_registrations.update_one({"registration_id": again["registration_id"], "status": "draft"}, {"$set": {"idempotency_key": payload.idempotency_key}})
        except DuplicateKeyError:
            return {"ok": True}
        await apply_progress(again, payload, device)
        return {"ok": True}
    doc = draft_doc(payload, device, service, name_key, await next_number(datetime.now(timezone.utc).year))
    try:
        await db.visitor_registrations.insert_one(doc)
    except DuplicateKeyError:
        return {"ok": True}  # doble toque: ya existe
    await apply_progress(doc, payload, device)
    await audit("registration_draft", f"device:{device['device_id']}", {"registration_id": doc["registration_id"], "visitor_number": doc["visitor_number"]})
    return {"ok": True}


async def complete_draft(draft: dict, payload: "RegistrationInput", device: dict, service: dict, phone_norm: Optional[str], name_key: str, texts: dict) -> dict:
    """«Terminar registro» ACTUALIZA el borrador creado al escribir el nombre (mismo número; nunca otro registro)."""
    claimed = await db.visitor_registrations.update_one({"registration_id": draft["registration_id"], "status": "draft"}, {"$set": {"status": "completing", "updated_at": now_utc()}})
    if not claimed.modified_count:
        # Doble toque: el otro envío ya lo está completando.
        import asyncio
        for _ in range(40):
            done = await db.visitor_registrations.find_one({"registration_id": draft["registration_id"]}, {"_id": 0})
            if done.get("status") not in ("draft", "completing"):
                return kiosk_reply(done, True, texts)
            await asyncio.sleep(0.15)
        raise HTTPException(status_code=409, detail="Ya se está guardando este registro; intente de nuevo en unos segundos")
    try:
        fields = await registration_fields(payload, device, service, phone_norm, name_key)
    except BaseException:
        await db.visitor_registrations.update_one({"registration_id": draft["registration_id"], "status": "completing"}, {"$set": {"status": "draft"}})
        raise
    # Lo que el encargado ya corrigió o quitó en la bienvenida se respeta.
    welcome = keep_welcome(draft, fields)
    fields["followup"] = merge_followup(draft.get("followup"), fields["followup"])
    now = now_utc()
    await db.visitor_registrations.update_one({"registration_id": draft["registration_id"]},
                                              {"$set": {**fields, "welcome": welcome, "status": "complete", "completed_at": now, "updated_at": now}})
    doc = await db.visitor_registrations.find_one({"registration_id": draft["registration_id"]}, {"_id": 0})
    await save_restricted(doc, payload, now)
    await alert_urgent(db, doc)
    await audit("registration_completed", f"device:{device['device_id']}", {"registration_id": doc["registration_id"], "visitor_number": doc["visitor_number"], "match_status": doc["match_status"]})
    return kiosk_reply(doc, False, texts)


async def save_restricted(doc: dict, payload: "RegistrationInput", now: datetime) -> None:
    if doc.get("has_restricted"):
        await db.visitor_restricted.replace_one({"_id": doc["registration_id"]}, {"_id": doc["registration_id"], "registration_id": doc["registration_id"], "prayer_request": payload.prayer_request,
                                                                                 "counseling_note": payload.counseling_note, "needs_note": payload.needs_note, "created_at": now}, upsert=True)


async def registration_fields(payload: "RegistrationInput", device: dict, service: dict, phone_norm: Optional[str], name_key: str, link: bool = True) -> dict:
    """Todos los datos del formulario (registro nuevo, borrador paso a paso o al completar un borrador).
    En el borrador (`link=False`) aún no se toca Persona 360."""
    match = await link_person(payload, device) if link else {"person_id": None, "match_status": "pending", "candidates": []}
    if match["person_id"]:
        await fill_person(match["person_id"], payload)
    invited = payload.invited if payload.invited is not None else bool((payload.invited_by or "").strip())
    payload.invited = invited
    methods = list(dict.fromkeys(payload.contact_methods or ([payload.contact_method] if payload.contact_method and payload.contact_method != "none" else [])))
    inviter = await resolve_inviter(payload.invited_by) if payload.invited and (payload.invited_by or "").strip() else None
    if payload.invited and (payload.invited_by or "").strip() and not inviter:
        inviter = {"person_id": None, "name": " ".join(payload.invited_by.split())}
    now = now_utc()
    requests = [item for item in payload.requests if item in REQUEST_KEYS]
    # Solo un «No» explícito (o «prefiero no recibir seguimiento») lo saca del seguimiento.
    wants_followup = payload.consent_followup is not False and "no_followup" not in requests
    fields = {
        "device_id": device["device_id"], "device_name": device["name"], "service": service, "name_key": name_key,
        "person_id": match["person_id"], "match_status": match["match_status"], "possible_person_ids": match["candidates"] if match["match_status"] == "possible" else [],
        "first_name": payload.first_name.strip(), "last_name": payload.last_name.strip(),
        # Bloque de BIENVENIDA (lo único que verá el panel/pantallas, y solo si lo autorizó).
        "welcome": {"preferred_name": (payload.preferred_name or "").strip() or payload.first_name.strip(), "display_name": None, "approved": False, "hidden": False,
                    # «Invitado por …» en la pantalla: el nombre completo de Persona 360 si quien invitó está allí.
                    "invited_by": inviter["name"] if inviter else None, "invited_by_display": None},
        # Bloque de CONTACTO (personal autorizado).
        "contact": {"phone": phone_norm, "phone_normalized": phone_norm, "email": (payload.email or "").strip() or None, "methods": methods, "city": payload.city, "address": payload.address,
                    "zip_code": (payload.zip_code or "").strip() or None,
                    "birth_date": payload.birth_date.isoformat() if payload.birth_date else None, "birth_day": payload.birth_day, "birth_month": payload.birth_month},
        # Idioma preferido y sexo: para el seguimiento (nunca en la bienvenida ni en pantallas).
        "language": payload.language, "profile": {"sex": payload.sex},
        "visit": {"first_visit": payload.first_visit, "invited": payload.invited, "invited_by": (payload.invited_by or "").strip() or None if payload.invited else None,
                  "invited_by_person_id": inviter["person_id"] if inviter else None, "visit_mode": payload.visit_mode, "new_in_area": payload.new_in_area,
                  "other_church": payload.other_church, "other_church_name": payload.other_church_name if payload.other_church else None,
                  "other_church_pastor": payload.other_church_pastor if payload.other_church else None, "how_heard": payload.how_heard},
        "faith": {"christian": payload.faith_christian, "accept_jesus": payload.accept_jesus, "reconcile": payload.reconcile, "faith_info": payload.faith_info},
        "household": {"marital_status": payload.marital_status, "spouse_name": (payload.spouse_name or "").strip() or None if payload.marital_status == "married" else None,
                      "has_children": payload.has_children, "children": [{"name": item.name.strip(), "age": item.age} for item in payload.children] if payload.has_children else [],
                      "companions": (payload.companions or "").strip() or None, "kids_ministry": payload.kids_ministry},
        "giving": {"info": payload.giving_info},
        # Familiares: solo nombre y parentesco; nunca datos sensibles de menores. No se anuncian sin consentimiento.
        "family": [{"name": item.name.strip(), "relation": item.relation, "is_minor": item.is_minor} for item in payload.family],
        "requests": requests, "has_restricted": bool(payload.prayer_request or payload.counseling_note or payload.needs_note),
        # Bienvenida: por decisión de la iglesia, todo registrado entra a la lista (el operador puede quitarlo).
        "consents": {"followup": payload.consent_followup},
        "privacy": {"version": payload.privacy_version, "accepted_at": now},
        "followup": {"status": "pending" if wants_followup else "not_requested", "assigned_person_id": None, "results": []},
        "test_data": False, "started_at": payload.started_at,
    }
    fields["followup"]["tasks"] = build_tasks(fields)
    return fields


async def insert_registration(payload: "RegistrationInput", device: dict, service: dict, phone_norm: Optional[str], name_key: str, texts: dict) -> dict:
    fields = await registration_fields(payload, device, service, phone_norm, name_key)
    now = now_utc()
    registration_id = str(uuid4())
    doc = {"_id": registration_id, "registration_id": registration_id, "idempotency_key": payload.idempotency_key, **fields, "status": "complete", "created_at": now, "updated_at": now,
           "completed_at": now, "visitor_number": await next_number(datetime.now(timezone.utc).year)}
    try:
        await db.visitor_registrations.insert_one(doc)
    except DuplicateKeyError:
        same = await db.visitor_registrations.find_one({"idempotency_key": payload.idempotency_key}, {"_id": 0})
        if same:
            return kiosk_reply(same, True, texts)
        raise
    await save_restricted(doc, payload, now)
    await alert_urgent(db, doc)
    await audit("registration_created", f"device:{device['device_id']}", {"registration_id": registration_id, "visitor_number": doc["visitor_number"], "match_status": doc["match_status"]})
    return kiosk_reply(doc, False, texts)


# ------------------------------------------------------------------ personal: consultar registros (V1 básico)
MATCH_LABELS = {"created": "Persona nueva en Persona 360", "linked": "Vinculado a su perfil existente", "possible": "Ya está en Persona 360 · confirmar si es una persona que ya existía"}


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
FOLLOWUP_LABELS = {"pending": "Pendiente de asignar", "assigned": "Asignado", "in_progress": "En contacto", "done": "Completado", "not_requested": "No pidió seguimiento"}
ATTEMPT_KINDS = {"call": "Llamada", "visit": "Visita", "message": "Mensaje"}
OUTCOMES = {"reached": "Se habló con la persona", "no_answer": "No contestó", "wrong_number": "Número equivocado", "visit_done": "Visita realizada",
            "wants_more": "Quiere más información o acompañamiento", "declined": "Prefiere no recibir seguimiento", "other": "Otro resultado"}


STATE_LABELS = {"registering": "Registrándose ahora", "incomplete": "Incompleto", "manual": "Agregado a mano · por completar", "complete": None, "discarded": "Descartado", "merged": "Unido a otro registro"}


def registration_state(doc: dict, form_reset_seconds: int = 300) -> str:
    """Borrador reciente = «registrándose»; si la persona lo dejó a medias, «incompleto»."""
    status = doc.get("status") or "complete"
    if status == "draft" and doc.get("origin") == "operator":
        return "manual"
    if status in ("draft", "completing"):
        updated = doc.get("updated_at") or doc.get("created_at")
        updated = updated if updated is None or updated.tzinfo else updated.replace(tzinfo=timezone.utc)
        return "registering" if updated and (now_utc() - updated).total_seconds() < form_reset_seconds + 60 else "incomplete"
    return status


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
            "phone": doc["contact"].get("phone"), "email": doc["contact"].get("email"), "contact_methods": doc["contact"].get("methods") or ([doc["contact"]["method"]] if doc["contact"].get("method") in ("call", "text", "whatsapp", "email") else []),
            "visit_mode": doc["visit"].get("visit_mode"), "new_in_area": doc["visit"].get("new_in_area"),
            # Idioma en que hay que contactarle y sexo (para asignar un mentor del mismo sexo).
            "language": doc.get("language") or "es", "sex": (doc.get("profile") or {}).get("sex"), "invited_by": doc["visit"].get("invited_by"), "city": doc["contact"].get("city"),
            "first_visit": doc["visit"].get("first_visit"), "requests": shown, "has_restricted": bool(doc.get("has_restricted") or any(item in RESTRICTED_REQUESTS for item in requests)),
            "status": followup.get("status", "pending"), "status_label": FOLLOWUP_LABELS.get(followup.get("status", "pending")),
            "assigned_person_id": followup.get("assigned_person_id"), "assigned_name": names.get(followup.get("assigned_person_id")) if followup.get("assigned_person_id") else None,
            "attempts": [{**item, "at": item["at"].isoformat() if isinstance(item.get("at"), datetime) else item.get("at"), "kind_label": ATTEMPT_KINDS.get(item.get("kind")), "outcome_label": OUTCOMES.get(item.get("outcome"))}
                         for item in followup.get("results") or []], "consent_followup": doc["consents"]["followup"],
            "registration_state": registration_state(doc), "registration_state_label": STATE_LABELS.get(registration_state(doc)), "origin": doc.get("origin", "tablet"),
            # Resumen legible de todas sus respuestas y las tareas que generaron (lo confidencial, solo con permiso).
            "answers": answers(doc, restricted_ok),
            "tasks": [{**task, "label": task["label"] if restricted_ok or not task.get("restricted") else "Atención pastoral confidencial"} for task in followup.get("tasks") or []]}


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
                        state: Optional[Literal["incomplete", "registering", "complete"]] = None, current_user: dict = Depends(get_current_user)):
    """Seguimiento por servicio y fecha. Quien no administra el seguimiento solo ve lo que le asignaron.
    Los registros a medias («Incompleto») también aparecen, para completarlos o descartarlos."""
    manager = can(current_user, VISITORS_FOLLOWUP_MANAGE)
    query: dict = {"status": {"$nin": ["discarded", "merged"]}}
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
    incomplete = sum(1 for doc in docs if registration_state(doc) in ("incomplete", "manual"))
    if state:
        docs = [doc for doc in docs if registration_state(doc) == state or (state == "incomplete" and registration_state(doc) == "manual")]
    names = await names_for(docs)
    counts: dict = {}
    for doc in docs:
        key = (doc.get("followup") or {}).get("status", "pending")
        counts[key] = counts.get(key, 0) + 1
    await audit("followup_viewed", current_user["user_id"], {"service_date": service_date, "count": len(docs)})
    return {"items": [followup_view(doc, current_user, names) for doc in docs], "can_manage": manager, "can_restricted": can(current_user, VISITORS_RESTRICTED_READ),
            "counts": [{"status": key, "label": FOLLOWUP_LABELS[key], "count": counts.get(key, 0)} for key in FOLLOWUP_LABELS], "incomplete": incomplete}


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


@admin_router.post("/registrations/{registration_id}/finish-incomplete", response_model=dict)
async def finish_incomplete(registration_id: str, current_user: dict = Depends(get_current_user)):
    """El equipo completa un registro que quedó a medias: se pasa a Persona 360 con su nombre
    (misma búsqueda de duplicados; lo dudoso queda como «posible coincidencia»)."""
    require(current_user, VISITORS_FOLLOWUP_MANAGE)
    doc = await load_registration(registration_id)
    if registration_state(doc) not in ("incomplete", "manual"):
        raise HTTPException(status_code=409, detail="Este registro está completo o la persona lo está llenando ahora")
    from types import SimpleNamespace
    person = SimpleNamespace(first_name=doc["first_name"], last_name=doc["last_name"], phone=None, email=None, birth_date=None, idempotency_key=doc["idempotency_key"])
    match = await link_person(person, {"device_id": f"staff:{current_user['user_id']}"})
    result = await db.visitor_registrations.update_one({"registration_id": registration_id, "status": {"$in": ["draft", "completing"]}},
                                                       {"$set": {"status": "complete", "completed_at": now_utc(), "completed_by_staff": current_user["user_id"], "updated_at": now_utc(),
                                                                 "person_id": match["person_id"], "match_status": match["match_status"],
                                                                 "possible_person_ids": match["candidates"] if match["match_status"] == "possible" else []}})
    if not result.modified_count:
        raise HTTPException(status_code=409, detail="Este registro ya está completo")
    await audit("incomplete_finished", current_user["user_id"], {"registration_id": registration_id, "match_status": match["match_status"]})
    return await followup_reply(registration_id, current_user)


@admin_router.post("/registrations/{registration_id}/discard", response_model=dict)
async def discard_registration(registration_id: str, current_user: dict = Depends(get_current_user)):
    """Descartar un registro incompleto (p. ej. una prueba): no se borra, queda oculto y auditado."""
    require(current_user, VISITORS_FOLLOWUP_MANAGE)
    doc = await load_registration(registration_id)
    if registration_state(doc) not in ("incomplete", "manual"):
        raise HTTPException(status_code=409, detail="Solo se descartan registros incompletos")
    await db.visitor_registrations.update_one({"registration_id": registration_id}, {"$set": {"status": "discarded", "welcome.hidden": True, "discarded_by": current_user["user_id"], "updated_at": now_utc()}})
    await audit("registration_discarded", current_user["user_id"], {"registration_id": registration_id})
    return {"ok": True}


@admin_router.post("/registrations/{registration_id}/mark-test", response_model=dict)
async def mark_test(registration_id: str, current_user: dict = Depends(get_current_user)):
    """«Es una prueba: quitar»: el registro se marca como prueba y sale de la bienvenida y del
    seguimiento (no se borra, queda auditado); su perfil de Persona 360 se retira si lo creó este
    registro y nada más lo usa. Así las pruebas nunca se mezclan con los registros reales."""
    require(current_user, VISITORS_FOLLOWUP_MANAGE)
    doc = await load_registration(registration_id)
    person_id = doc.get("person_id")
    await db.visitor_registrations.update_one({"registration_id": registration_id}, {"$set": {"status": "discarded", "test_data": True, "welcome.hidden": True, "person_id": None,
                                                                                            "test_marked_by": current_user["user_id"], "updated_at": now_utc()}})
    if person_id:
        await retire_provisional(person_id, doc, current_user)
    await audit("registration_marked_test", current_user["user_id"], {"registration_id": registration_id, "person_id": person_id})
    return {"ok": True}


class TaskInput(BaseModel):
    done: bool


@admin_router.post("/registrations/{registration_id}/tasks/{task_key}", response_model=dict)
async def set_task(registration_id: str, task_key: str, payload: TaskInput, current_user: dict = Depends(get_current_user)):
    """Marcar una tarea del seguimiento como hecha (quien administra o la persona asignada)."""
    doc = await load_registration(registration_id)
    if not (can(current_user, VISITORS_FOLLOWUP_MANAGE) or is_assignee(doc, current_user)):
        raise HTTPException(status_code=403, detail="Solo quien administra el seguimiento o la persona asignada")
    result = await db.visitor_registrations.update_one({"registration_id": registration_id, "followup.tasks.key": task_key},
                                                       {"$set": {"followup.tasks.$.done": payload.done, "followup.tasks.$.done_at": now_utc() if payload.done else None,
                                                                 "followup.tasks.$.done_by": current_user.get("nombre") if payload.done else None}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    await audit("followup_task", current_user["user_id"], {"registration_id": registration_id, "task": task_key, "done": payload.done})
    return await followup_reply(registration_id, current_user)


class ResolveMatchInput(BaseModel):
    person_id: Optional[str] = Field(default=None, max_length=80)
    create_new: bool = False


@admin_router.post("/registrations/{registration_id}/resolve-match", response_model=dict)
async def resolve_match(registration_id: str, payload: ResolveMatchInput, current_user: dict = Depends(get_current_user)):
    """Revisión humana de «posible coincidencia»: el registro ya tiene su perfil en
    Persona 360; aquí se confirma si es otra persona o si era la misma (se vincula a
    la existente y se retira el perfil provisional, que no tenía nada más)."""
    require(current_user, VISITORS_FOLLOWUP_MANAGE)
    doc = await load_registration(registration_id)
    if doc["match_status"] != "possible":
        raise HTTPException(status_code=409, detail="Este registro ya fue revisado")
    provisional = doc.get("person_id")
    if payload.create_new:
        person_id = provisional or await insert_person(doc["first_name"], doc["last_name"], doc["contact"].get("birth_date"), doc["contact"].get("phone"), doc["contact"].get("email"),
                                                       f"visitor-distinct:{registration_id}", current_user["user_id"], "visitor_review", doc.get("possible_person_ids") or [])
        status = "created"
    elif payload.person_id and payload.person_id in (doc.get("possible_person_ids") or []):
        person_id, status = payload.person_id, "linked"
    else:
        raise HTTPException(status_code=422, detail="Elija una de las personas sugeridas o «Es otra persona»")
    result = await db.visitor_registrations.update_one({"registration_id": registration_id, "match_status": "possible"},
                                                       {"$set": {"person_id": person_id, "match_status": status, "match_resolved": {"by_user_id": current_user["user_id"], "at": now_utc(), "provisional_person_id": provisional}}})
    if result.modified_count and status == "linked" and provisional and provisional != person_id:
        await retire_provisional(provisional, doc, current_user)
    await audit("match_resolved", current_user["user_id"], {"registration_id": registration_id, "person_id": person_id, "result": status})
    return await followup_reply(registration_id, current_user)


async def retire_provisional(person_id: str, doc: dict, current_user: dict) -> None:
    """Quita el perfil provisional SOLO si lo creó este registro y nada más lo usa."""
    if not ObjectId.is_valid(person_id):
        return
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"idempotency_key": 1})
    if not person or person.get("idempotency_key") != f"visitor:{doc['idempotency_key']}":
        return
    in_use = (await db.visitor_registrations.count_documents({"person_id": person_id}) or await db.process_enrollments.count_documents({"person_id": person_id})
              or await db.users.count_documents({"person_id": person_id}) or await db.outreach_visits.count_documents({"$or": [{"person_id": person_id}, {"converted_person_id": person_id}]}))
    if in_use:
        return
    await db.persons.delete_one({"_id": ObjectId(person_id)})
    await db.person_contacts.delete_many({"person_id": person_id})
    await audit("provisional_person_retired", current_user["user_id"], {"person_id": person_id, "registration_id": doc["registration_id"]})
