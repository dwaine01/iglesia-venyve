"""Visitantes V3: bienvenida en pantallas.

- Pantalla del salón (TV de 40" leída a ~12 m) y pantalla de la pastora: son
  dispositivos emparejados como las tabletas (código de un solo uso), con un
  token cuyo ÚNICO permiso es leer los nombres autorizados. No registran nada.
- LISTA BLANCA: la pantalla solo recibe nombres (texto) y el estado de la
  presentación; nunca teléfonos, direcciones, fechas, oración ni consejería.
  El salón muestra a quien autorizó «mostrar en pantallas»; la pastora ve a quien
  autorizó «anunciar mi nombre» (y a sus familiares solo si también lo autorizó).
- El operador (visitors.welcome.operate) elige servicio y modo (uno por uno o
  lista lenta), pausa, adelanta o retrocede, corrige un nombre o lo quita de la
  pantalla SIN borrar el registro. Todo queda auditado.
- El avance automático se calcula en el servidor (índice + hora de inicio), así
  la pantalla y el panel del operador siempre muestran lo mismo."""
import math
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from access_control import VISITORS_WELCOME_OPERATE
from server import db, get_current_user
from visitor_registry import audit, current_service, now_utc, paired_device, require

operator_router = APIRouter(prefix="/api/visitors/welcome", tags=["visitor-welcome"])
screen_router = APIRouter(prefix="/api/screen", tags=["visitor-screen"])

AUDIENCES = {"tv": "Pantalla de bienvenida (salón)", "pastora": "Pantalla de la pastora"}
SCREEN_KIND = {"screen_tv": "tv", "screen_pastora": "pastora"}
PAGE_SIZE = {"one": 1, "list": 4}
DEFAULT_STATE = {"mode": "one", "paused": False, "seconds": 8, "index": 0, "anchor": None, "service_date": None, "service_kind": None}


def default_name(doc: dict) -> str:
    preferred = (doc.get("welcome") or {}).get("preferred_name") or doc["first_name"]
    last = (doc.get("last_name") or "").split()
    return f"{preferred} {last[0]}" if last else preferred


def shown_name(doc: dict, audience: str) -> str:
    name = (doc.get("welcome") or {}).get("display_name") or default_name(doc)
    if audience == "pastora" and (doc.get("consents") or {}).get("family_announce"):
        family = [item["name"] for item in doc.get("family") or [] if item.get("name")]
        if family:
            name = f"{name} y su familia: {', '.join(family)}"
    return name


def consent_key(audience: str) -> str:
    return "consents.screens" if audience == "tv" else "consents.announce"


async def load_state(audience: str) -> dict:
    doc = await db.app_settings.find_one({"_id": f"visitor_welcome_state_{audience}"}, {"_id": 0}) or {}
    return {**DEFAULT_STATE, **{key: value for key, value in doc.items() if key in DEFAULT_STATE}}


async def save_state(audience: str, state: dict, actor: str) -> None:
    await db.app_settings.update_one({"_id": f"visitor_welcome_state_{audience}"}, {"$set": {**{key: state[key] for key in DEFAULT_STATE}, "updated_at": now_utc(), "updated_by": actor}}, upsert=True)


async def service_filter(state: dict) -> dict:
    service_date = state.get("service_date") or (await current_service())["date"]
    query = {"service.date": service_date}
    if state.get("service_kind"):
        query["service.kind"] = state["service_kind"]
    return query


async def eligible(audience: str, state: dict) -> list:
    """Solo quien autorizó para esa pantalla y no fue quitado; en orden de llegada."""
    query = {**await service_filter(state), consent_key(audience): True, "welcome.hidden": {"$ne": True}}
    return await db.visitor_registrations.find(query, {"_id": 0}).sort("created_at", 1).to_list(500)


def current_page(state: dict, count: int) -> tuple[int, int]:
    pages = max(1, math.ceil(count / PAGE_SIZE[state["mode"]]))
    index = state.get("index") or 0
    if not state.get("paused"):
        # Sin hora de inicio guardada, avanza contando desde una fecha fija (igual para todos).
        anchor = state.get("anchor") or datetime(2026, 1, 1, tzinfo=timezone.utc)
        anchor = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
        index += int((now_utc() - anchor).total_seconds() // max(3, state["seconds"]))
    return index % pages, pages


async def presentation(audience: str) -> dict:
    """Lo que ve la pantalla: SOLO nombres y el estado (lista blanca)."""
    state = await load_state(audience)
    docs = await eligible(audience, state)
    page, pages = current_page(state, len(docs))
    size = PAGE_SIZE[state["mode"]]
    names = [shown_name(doc, audience) for doc in docs]
    service = await current_service()
    label = service["label"] if not state.get("service_date") or state["service_date"] == service["date"] else None
    return {"audience": audience, "mode": state["mode"], "paused": bool(state["paused"]), "seconds": state["seconds"], "page": page, "pages": pages,
            "names": names[page * size:(page + 1) * size], "total": len(names), "service_label": label}


# ------------------------------------------------------------------ pantalla (token de dispositivo)
async def screen_device(x_device_token: Optional[str] = Header(default=None)) -> dict:
    return await paired_device(x_device_token, set(SCREEN_KIND))


@screen_router.get("/welcome", response_model=dict)
async def screen_welcome(device: dict = Depends(screen_device)):
    return {"device_name": device["name"], **await presentation(SCREEN_KIND[device["kind"]])}


# ------------------------------------------------------------------ operador
def operator_item(doc: dict, audience: str) -> dict:
    """Lista blanca del panel: nombre, número y autorizaciones (sin contacto ni pedidos)."""
    consents = doc.get("consents") or {}
    return {"registration_id": doc["registration_id"], "visitor_number": doc["visitor_number"], "name": shown_name(doc, audience), "default_name": default_name(doc),
            "corrected": bool((doc.get("welcome") or {}).get("display_name")), "hidden": bool((doc.get("welcome") or {}).get("hidden")),
            "service_label": doc["service"]["label"], "authorized": bool(consents.get("screens" if audience == "tv" else "announce"))}


@operator_router.get("", response_model=dict)
async def operator_view(audience: Literal["tv", "pastora"] = "tv", current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_WELCOME_OPERATE)
    state = await load_state(audience)
    # El operador ve también a los quitados (para volver a mostrarlos), nunca a quien no autorizó.
    query = {**await service_filter(state), consent_key(audience): True}
    docs = await db.visitor_registrations.find(query, {"_id": 0}).sort("created_at", 1).to_list(500)
    await audit("welcome_viewed", current_user["user_id"], {"audience": audience, "count": len(docs)})
    service = await current_service()
    return {"audience": audience, "audience_label": AUDIENCES[audience], "items": [operator_item(doc, audience) for doc in docs], "presentation": await presentation(audience),
            "state": {key: state[key] for key in ("mode", "paused", "seconds", "service_date", "service_kind")}, "today": service}


class StateInput(BaseModel):
    audience: Literal["tv", "pastora"]
    mode: Optional[Literal["one", "list"]] = None
    seconds: Optional[int] = Field(default=None, ge=3, le=60)
    service_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    service_kind: Optional[Literal["sunday", "wednesday", "special", "all"]] = None
    today: bool = False


@operator_router.put("/state", response_model=dict)
async def set_state(payload: StateInput, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_WELCOME_OPERATE)
    state = await load_state(payload.audience)
    if payload.mode:
        state["mode"] = payload.mode
    if payload.seconds:
        state["seconds"] = payload.seconds
    if payload.today:
        state["service_date"] = None
    elif payload.service_date:
        state["service_date"] = payload.service_date
    if payload.service_kind:
        state["service_kind"] = None if payload.service_kind == "all" else payload.service_kind
    state.update({"index": 0, "anchor": now_utc()})
    await save_state(payload.audience, state, current_user["user_id"])
    await audit("welcome_state", current_user["user_id"], {"audience": payload.audience, **payload.model_dump(exclude_none=True)})
    return await presentation(payload.audience)


class ControlInput(BaseModel):
    audience: Literal["tv", "pastora"]
    action: Literal["next", "prev", "pause", "play"]


@operator_router.post("/control", response_model=dict)
async def control(payload: ControlInput, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_WELCOME_OPERATE)
    state = await load_state(payload.audience)
    page, pages = current_page(state, len(await eligible(payload.audience, state)))
    step = {"next": 1, "prev": -1}.get(payload.action, 0)
    state.update({"index": (page + step) % pages, "anchor": now_utc()})
    if payload.action in ("pause", "play"):
        state["paused"] = payload.action == "pause"
    await save_state(payload.audience, state, current_user["user_id"])
    return await presentation(payload.audience)


class ItemInput(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=120)
    reset_name: bool = False
    hidden: Optional[bool] = None


@operator_router.post("/items/{registration_id}", response_model=dict)
async def update_item(registration_id: str, payload: ItemInput, current_user: dict = Depends(get_current_user)):
    """Corregir cómo se muestra el nombre o quitarlo de la pantalla (el registro no se borra)."""
    require(current_user, VISITORS_WELCOME_OPERATE)
    changes: dict = {}
    if payload.reset_name:
        changes["welcome.display_name"] = None
    elif payload.display_name is not None and payload.display_name.strip():
        changes["welcome.display_name"] = " ".join(payload.display_name.split())
    if payload.hidden is not None:
        changes["welcome.hidden"] = payload.hidden
    if not changes:
        raise HTTPException(status_code=422, detail="Nada que cambiar")
    result = await db.visitor_registrations.update_one({"registration_id": registration_id}, {"$set": {**changes, "welcome.updated_at": now_utc(), "welcome.updated_by": current_user["user_id"]}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    await audit("welcome_item_changed", current_user["user_id"], {"registration_id": registration_id, **{key.split(".")[1]: value for key, value in changes.items()}})
    doc = await db.visitor_registrations.find_one({"registration_id": registration_id}, {"_id": 0})
    return {"tv": operator_item(doc, "tv"), "pastora": operator_item(doc, "pastora")}
