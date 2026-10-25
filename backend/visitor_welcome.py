"""Visitantes: pantalla de bienvenida (nombres uno por uno).

- Un ENLACE único de pantalla (token largo) cuyo ÚNICO permiso es leer los nombres
  del servicio. Sin emparejar ni iniciar sesión.
- Por decisión de la iglesia todo visitante registrado entra a la lista; el
  operador puede quitar cualquiera (sin borrar el registro) o corregirlo.
- LISTA BLANCA: la pantalla recibe solo {id, nombre, invitado por, registrando}; nunca teléfonos,
  direcciones, fechas, oración ni consejería. Los familiares que acompañan
  (incluidos menores) NO se muestran.
- La encargada avanza y retrocede en la propia pantalla (flechas o botones);
  aquí solo se entrega la lista en orden de llegada."""
from datetime import timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from access_control import VISITORS_WELCOME_OPERATE
from server import db, get_current_user
from visitor_registry import audit, current_service, link_access, load_kiosk_settings, now_utc, registration_state, require

operator_router = APIRouter(prefix="/api/visitors/welcome", tags=["visitor-welcome"])
screen_router = APIRouter(prefix="/api/screen", tags=["visitor-screen"])

STATE_ID = "visitor_welcome_state"


def default_name(doc: dict) -> str:
    if (doc.get("welcome") or {}).get("manual_name"):
        return doc["welcome"]["manual_name"]  # agregado a mano: tal como lo escribió el operador
    preferred = (doc.get("welcome") or {}).get("preferred_name") or doc["first_name"]
    last = (doc.get("last_name") or "").split()
    return f"{preferred} {last[0]}" if last else preferred


def shown_name(doc: dict) -> str:
    welcome = doc.get("welcome") or {}
    return welcome.get("display_name") or welcome.get("manual_name") or default_name(doc)


def order_of(doc: dict) -> float:
    """Orden de lectura: el de llegada, salvo que el operador lo haya puesto «Siguiente»."""
    order = (doc.get("welcome") or {}).get("order")
    if order is not None:
        return float(order)
    created = doc.get("created_at")
    return created.replace(tzinfo=created.tzinfo or timezone.utc).timestamp() if created else 0.0


def in_order(docs: list) -> list:
    return sorted(docs, key=order_of)


def default_inviter(doc: dict) -> Optional[str]:
    """Nombre completo de Persona 360 si quien invitó está allí; si no, lo que escribió el visitante."""
    welcome, visit = doc.get("welcome") or {}, doc.get("visit") or {}
    return welcome.get("invited_by") or ((visit.get("invited_by") or "").strip() or None if visit.get("invited") else None)


def shown_inviter(doc: dict) -> Optional[str]:
    return (doc.get("welcome") or {}).get("invited_by_display") or default_inviter(doc)


async def load_state() -> dict:
    doc = await db.app_settings.find_one({"_id": STATE_ID}, {"_id": 0}) or {}
    return {"service_date": doc.get("service_date"), "service_kind": doc.get("service_kind")}


async def service_query(state: dict) -> dict:
    query = {"service.date": state.get("service_date") or (await current_service())["date"]}
    if state.get("service_kind"):
        query["service.kind"] = state["service_kind"]
    return query


async def service_label(state: dict) -> Optional[str]:
    today = await current_service()
    return today["label"] if not state.get("service_date") or state["service_date"] == today["date"] else None


# ------------------------------------------------------------------ pantalla (enlace)
@screen_router.get("/welcome", response_model=dict)
async def screen_welcome(request: Request, x_link_token: Optional[str] = Header(default=None)):
    """Lista blanca: solo id y nombre, en orden de llegada, sin los quitados."""
    link = await link_access("screen", x_link_token, request)
    state = await load_state()
    docs = await db.visitor_registrations.find({**await service_query(state), "welcome.hidden": {"$ne": True}}, {"_id": 0, "registration_id": 1, "first_name": 1, "last_name": 1, "welcome": 1, "visit.invited": 1, "visit.invited_by": 1,
                                                                                                         "status": 1, "updated_at": 1, "created_at": 1, "origin": 1}) \
        .sort("created_at", 1).to_list(500)
    docs = in_order(docs)
    reset = (await load_kiosk_settings())["form_reset_seconds"]
    # El nombre aparece apenas lo escribe (borrador), con «registrando…» mientras llena el resto.
    return {"names": [{"id": doc["registration_id"], "name": shown_name(doc), "invited_by": shown_inviter(doc), "registering": registration_state(doc, reset) == "registering"} for doc in docs], "total": len(docs), "service_label": await service_label(state),
            "short_path": f"/b/{link['code']}"}


# ------------------------------------------------------------------ operador
def operator_item(doc: dict) -> dict:
    """Lista blanca del panel: nombre y número (sin contacto ni pedidos)."""
    return {"registration_id": doc["registration_id"], "visitor_number": doc["visitor_number"], "name": shown_name(doc), "default_name": default_name(doc),
            "corrected": bool((doc.get("welcome") or {}).get("display_name")), "hidden": bool((doc.get("welcome") or {}).get("hidden")), "service_label": doc["service"]["label"],
            "invited_by": shown_inviter(doc), "default_invited_by": default_inviter(doc), "invited_corrected": bool((doc.get("welcome") or {}).get("invited_by_display")),
            "registering": registration_state(doc) == "registering", "manual": doc.get("origin") == "operator"}


@operator_router.get("", response_model=dict)
async def operator_view(current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_WELCOME_OPERATE)
    state = await load_state()
    docs = in_order(await db.visitor_registrations.find({**await service_query(state), "status": {"$nin": ["discarded", "merged"]}}, {"_id": 0}).sort("created_at", 1).to_list(500))
    await audit("welcome_viewed", current_user["user_id"], {"count": len(docs)})
    return {"items": [operator_item(doc) for doc in docs], "state": state, "today": await current_service(), "service_label": await service_label(state)}


class StateInput(BaseModel):
    service_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    service_kind: Optional[Literal["sunday", "wednesday", "special", "all"]] = None
    today: bool = False


@operator_router.put("/state", response_model=dict)
async def set_state(payload: StateInput, current_user: dict = Depends(get_current_user)):
    """Qué servicio muestra la pantalla (por defecto, el de hoy)."""
    require(current_user, VISITORS_WELCOME_OPERATE)
    state = await load_state()
    if payload.today:
        state["service_date"] = None
    elif payload.service_date:
        state["service_date"] = payload.service_date
    if payload.service_kind:
        state["service_kind"] = None if payload.service_kind == "all" else payload.service_kind
    await db.app_settings.update_one({"_id": STATE_ID}, {"$set": {**state, "updated_at": now_utc(), "updated_by": current_user["user_id"]}}, upsert=True)
    await audit("welcome_state", current_user["user_id"], payload.model_dump(exclude_none=True))
    return state


class ManualInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    invited_by: Optional[str] = Field(default=None, max_length=120)
    position: Literal["next", "end"] = "end"
    after_id: Optional[str] = Field(default=None, max_length=80)


@operator_router.post("/manual", response_model=dict, status_code=201)
async def add_manual(payload: ManualInput, current_user: dict = Depends(get_current_user)):
    """«Agregar nombre» en la bienvenida: entra YA a la lista (después del actual o al final) y queda un
    registro «Agregado a mano · por completar» para completarlo o transcribir el papel después."""
    require(current_user, VISITORS_WELCOME_OPERATE)
    from uuid import uuid4
    from person_matching import normalize_text
    from visitor_registry import next_number
    name = " ".join(payload.name.split())
    parts = name.split(" ", 1)
    name_key = normalize_text(name)
    state = await load_state()
    service = await current_service()
    if state.get("service_date") and state["service_date"] != service["date"]:
        service = {**service, "date": state["service_date"], "label": "Servicio anterior"}
    same = await db.visitor_registrations.find_one({"service.date": service["date"], "name_key": name_key, "status": {"$nin": ["discarded", "merged"]}}, {"_id": 0, "registration_id": 1})
    if same:
        raise HTTPException(status_code=409, detail=f"«{name}» ya está en la lista de hoy")
    docs = in_order(await db.visitor_registrations.find({**await service_query(state), "welcome.hidden": {"$ne": True}, "status": {"$nin": ["discarded", "merged"]}},
                                                        {"_id": 0, "registration_id": 1, "welcome": 1, "created_at": 1}).to_list(500))
    order = (order_of(docs[-1]) + 1) if docs else now_utc().timestamp()
    if payload.position == "next" and payload.after_id:
        index = next((position for position, doc in enumerate(docs) if doc["registration_id"] == payload.after_id), None)
        if index is not None:
            after = order_of(docs[index])
            following = order_of(docs[index + 1]) if index + 1 < len(docs) else after + 2
            order = (after + following) / 2
    now = now_utc()
    registration_id = str(uuid4())
    inviter = " ".join((payload.invited_by or "").split()) or None
    doc = {
        "_id": registration_id, "registration_id": registration_id, "idempotency_key": f"manual-{registration_id}", "visitor_number": await next_number(now.year),
        "status": "draft", "origin": "operator", "created_by": current_user["user_id"], "device_id": f"operator:{current_user['user_id']}", "device_name": "Agregado por el operador",
        "service": service, "name_key": name_key, "person_id": None, "match_status": "pending", "possible_person_ids": [],
        "first_name": parts[0], "last_name": parts[1] if len(parts) > 1 else "",
        "welcome": {"preferred_name": parts[0], "manual_name": name, "display_name": None, "hidden": False, "invited_by": inviter, "invited_by_display": None, "order": order},
        "contact": {"phone": None, "phone_normalized": None, "email": None, "methods": [], "city": None, "address": None, "zip_code": None, "birth_date": None},
        "visit": {"first_visit": None, "invited": bool(inviter), "invited_by": inviter, "visit_mode": None, "other_church": None, "how_heard": None},
        "faith": {}, "household": {}, "giving": {}, "family": [], "requests": [], "has_restricted": False, "consents": {"followup": None},
        "privacy": {"version": None, "accepted_at": None}, "followup": {"status": "pending", "assigned_person_id": None, "results": [], "tasks": []},
        "test_data": False, "created_at": now, "updated_at": now,
    }
    await db.visitor_registrations.insert_one(doc)
    await audit("welcome_manual_added", current_user["user_id"], {"registration_id": registration_id, "position": payload.position})
    return operator_item(doc)


class ItemInput(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=120)
    reset_name: bool = False
    invited_by_display: Optional[str] = Field(default=None, max_length=120)
    reset_invited: bool = False
    hidden: Optional[bool] = None


@operator_router.post("/items/{registration_id}", response_model=dict)
async def update_item(registration_id: str, payload: ItemInput, current_user: dict = Depends(get_current_user)):
    """Corregir cómo se lee el nombre o quitarlo de la bienvenida (el registro no se borra)."""
    require(current_user, VISITORS_WELCOME_OPERATE)
    changes: dict = {}
    if payload.reset_name:
        changes["welcome.display_name"] = None
    elif payload.display_name is not None and payload.display_name.strip():
        changes["welcome.display_name"] = " ".join(payload.display_name.split())
    if payload.reset_invited:
        changes["welcome.invited_by_display"] = None
    elif payload.invited_by_display is not None and payload.invited_by_display.strip():
        changes["welcome.invited_by_display"] = " ".join(payload.invited_by_display.split())
    if payload.hidden is not None:
        changes["welcome.hidden"] = payload.hidden
    if not changes:
        raise HTTPException(status_code=422, detail="Nada que cambiar")
    result = await db.visitor_registrations.update_one({"registration_id": registration_id}, {"$set": {**changes, "welcome.updated_at": now_utc(), "welcome.updated_by": current_user["user_id"]}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    await audit("welcome_item_changed", current_user["user_id"], {"registration_id": registration_id, **{key.split(".")[1]: value for key, value in changes.items()}})
    return operator_item(await db.visitor_registrations.find_one({"registration_id": registration_id}, {"_id": 0}))
