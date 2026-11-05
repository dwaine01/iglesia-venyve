"""Bienvenida SINCRONIZADA: todas las pantallas abiertas (tableta, navegador de ProPresenter, otra pestaña) y
el panel del operador muestran el mismo nombre.

- POSICIÓN en la base, por servicio (`visitor_welcome_positions`): el registration_id del nombre mostrado,
  su orden de lectura y un número de VERSIÓN. No es un índice: si llega un visitante nuevo, o el operador
  quita o corrige uno, todas siguen en la misma persona. Si quitan justo a la persona mostrada, todas pasan a
  la siguiente en la lista (la misma regla en todas).
- MOVER («siguiente», «anterior», «primero», «último»): el cliente manda la versión que veía; el servidor
  solo acepta si coincide (la versión sube en 1). Si dos dispositivos presionan a la vez, el segundo llega
  con versión vieja y se ignora: nunca salta dos nombres.
- TIEMPO REAL por WebSocket en este mismo backend (como el radio, sin dependencias nuevas), con boleto de UN
  SOLO USO y 60 s: el enlace de la pantalla nunca va en la dirección del WebSocket. Respaldo: si el
  WebSocket no conecta, la pantalla consulta cada 2 s y mueve por HTTP con la misma regla de versión.
- El enlace de pantalla puede: leer los nombres (lista blanca, sin cambios) y mover la posición del servicio
  que se muestra. Nada más.
- Las conexiones viven en memoria (Railway corre un solo proceso, como el radio); la posición vive en la
  base y sobrevive un reinicio."""
import asyncio
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from access_control import VISITORS_WELCOME_OPERATE
from server import db, get_current_user, session_payload, user_is_active, user_token_version
from visitor_registry import link_access, load_links, now_utc, require

logger = logging.getLogger(__name__)
screen_sync_router = APIRouter(prefix="/api/screen/welcome", tags=["visitor-screen"])
operator_sync_router = APIRouter(prefix="/api/visitors/welcome", tags=["visitor-welcome"])
TICKET_SECONDS = 60
ACTIONS = ("next", "prev", "first", "last")


# ------------------------------------------------------------------ lista y posición (una sola regla)
async def visible_docs() -> tuple[str, list]:
    """(clave del servicio que muestra la pantalla, nombres visibles en orden de lectura)."""
    from visitor_welcome import in_order, load_state, service_query
    from visitor_registry import current_service
    state = await load_state()
    key = f"{state.get('service_date') or (await current_service())['date']}|{state.get('service_kind') or 'all'}"
    docs = await db.visitor_registrations.find({**await service_query(state), "welcome.hidden": {"$ne": True}},
                                               {"_id": 0, "registration_id": 1, "welcome": 1, "created_at": 1}).sort("created_at", 1).to_list(500)
    return key, in_order(docs)


def resolve(docs: list, stored: Optional[dict]) -> int:
    """Índice de la persona mostrada. Si ya no está (la quitaron), la siguiente en orden de lectura."""
    from visitor_welcome import order_of
    if not docs:
        return -1
    if stored and stored.get("registration_id"):
        for index, doc in enumerate(docs):
            if doc["registration_id"] == stored["registration_id"]:
                return index
        order = stored.get("order")
        if order is not None:
            return next((index for index, doc in enumerate(docs) if order_of(doc) >= order), len(docs) - 1)
    return 0


def position_view(key: str, docs: list, stored: Optional[dict]) -> dict:
    index = resolve(docs, stored)
    return {"type": "position", "service_key": key, "registration_id": docs[index]["registration_id"] if index >= 0 else None,
            "index": index, "total": len(docs), "version": int((stored or {}).get("version") or 0)}


async def current_position() -> dict:
    key, docs = await visible_docs()
    return position_view(key, docs, await db.visitor_welcome_positions.find_one({"_id": key}, {"_id": 0}))


async def move(action: str, version: int, by: str) -> dict:
    """Mueve solo si `version` es la vigente; si no, devuelve la posición actual sin moverla (stale)."""
    from visitor_welcome import order_of
    key, docs = await visible_docs()
    try:
        await db.visitor_welcome_positions.update_one({"_id": key}, {"$setOnInsert": {"version": 0, "registration_id": None, "order": None}}, upsert=True)
    except DuplicateKeyError:
        pass
    stored = await db.visitor_welcome_positions.find_one({"_id": key}, {"_id": 0})
    if int(stored.get("version") or 0) != int(version) or not docs:
        return {**position_view(key, docs, stored), "moved": False, "stale": int(stored.get("version") or 0) != int(version)}
    index = resolve(docs, stored)
    target = {"next": index + 1, "prev": index - 1, "first": 0, "last": len(docs) - 1}[action]
    target = min(len(docs) - 1, max(0, target))
    chosen = docs[target]
    updated = await db.visitor_welcome_positions.find_one_and_update(
        {"_id": key, "version": int(version)},
        {"$set": {"registration_id": chosen["registration_id"], "order": order_of(chosen), "updated_at": now_utc(), "updated_by": by}, "$inc": {"version": 1}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:  # otro dispositivo movió en el mismo instante: este evento se ignora
        return {**position_view(key, docs, await db.visitor_welcome_positions.find_one({"_id": key}, {"_id": 0})), "moved": False, "stale": True}
    view = {**position_view(key, docs, updated), "moved": True, "stale": False}
    hub.broadcast({key_: value for key_, value in view.items() if key_ not in {"moved", "stale"}})
    return view


# ------------------------------------------------------------------ conexiones en memoria
class Hub:
    def __init__(self):
        self.members: dict[int, dict] = {}

    def broadcast(self, message: dict, kinds: Optional[set] = None) -> None:
        for member in list(self.members.values()):
            if kinds and member["kind"] not in kinds:
                continue
            try:
                member["queue"].put_nowait(message)
            except asyncio.QueueFull:  # pantalla lenta: se queda con el último estado
                try:
                    member["queue"].get_nowait()
                    member["queue"].put_nowait(message)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass


hub = Hub()


def notify_names_changed() -> None:
    """Llegó, se quitó o se corrigió un nombre, o cambió el servicio: las pantallas vuelven a leer la lista."""
    hub.broadcast({"type": "names_changed"})


async def kick_screens() -> None:
    """Enlace nuevo: las pantallas conectadas con el anterior se desconectan en el acto."""
    for member in list(hub.members.values()):
        if member["kind"] == "screen":
            try:
                await member["websocket"].close(code=4401)
            except Exception:  # noqa: BLE001
                pass


# ------------------------------------------------------------------ boletos de un solo uso
async def issue_ticket(kind: str, owner: dict) -> dict:
    ticket = secrets.token_urlsafe(32)
    await db.visitor_welcome_tickets.insert_one({"_id": ticket, "kind": kind, **owner, "expires_at": now_utc() + timedelta(seconds=TICKET_SECONDS)})
    return {"ticket": ticket, "expires_in": TICKET_SECONDS}


async def redeem(ticket: Optional[str]) -> dict:
    doc = await db.visitor_welcome_tickets.find_one_and_delete({"_id": ticket or ""}) if ticket else None
    expires = (doc or {}).get("expires_at")
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not doc or expires is None or expires < now_utc():
        raise HTTPException(status_code=401, detail="El acceso venció. La pantalla se vuelve a conectar sola.")
    if doc["kind"] == "screen":
        if (await load_links())["screen"]["code"] != doc.get("link_code"):  # se generó un enlace nuevo
            raise HTTPException(status_code=401, detail="Este enlace ya no funciona. Pida el enlace nuevo a la administración.")
        return {"kind": "screen", "by": "screen"}
    if not ObjectId.is_valid(doc.get("user_id") or ""):
        raise HTTPException(status_code=401, detail="No autorizado")
    db_user = await db.users.find_one({"_id": ObjectId(doc["user_id"])})
    if not db_user or not user_is_active(db_user) or doc.get("token_version") != user_token_version(db_user):
        raise HTTPException(status_code=401, detail="No autorizado")
    user = session_payload(db_user, {"user_id": doc["user_id"], "email": db_user.get("email"), "rol": db_user.get("rol"), "token_version": user_token_version(db_user)})
    require(user, VISITORS_WELCOME_OPERATE)  # la misma regla que el panel del operador
    return {"kind": "operator", "by": doc["user_id"]}


class MoveInput(BaseModel):
    action: Literal["next", "prev", "first", "last"]
    version: int


@screen_sync_router.post("/ticket", response_model=dict)
async def screen_ticket(request: Request, x_link_token: Optional[str] = Header(default=None)):
    """El enlace va en el encabezado (nunca en la dirección del WebSocket)."""
    link = await link_access("screen", x_link_token, request)
    return await issue_ticket("screen", {"link_code": link["code"]})


@screen_sync_router.get("/position", response_model=dict)
async def screen_position(request: Request, x_link_token: Optional[str] = Header(default=None)):
    await link_access("screen", x_link_token, request)
    return await current_position()


@screen_sync_router.post("/position", response_model=dict)
async def screen_move(payload: MoveInput, request: Request, x_link_token: Optional[str] = Header(default=None)):
    """Respaldo sin WebSocket: mismo permiso del enlace (mover la posición) y la misma regla de versión."""
    await link_access("screen", x_link_token, request)
    return await move(payload.action, payload.version, "screen")


@operator_sync_router.post("/ticket", response_model=dict)
async def operator_ticket(current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_WELCOME_OPERATE)
    return await issue_ticket("operator", {"user_id": current_user["user_id"], "token_version": current_user.get("token_version")})


@operator_sync_router.get("/position", response_model=dict)
async def operator_position(current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_WELCOME_OPERATE)
    return await current_position()


@operator_sync_router.post("/position", response_model=dict)
async def operator_move(payload: MoveInput, current_user: dict = Depends(get_current_user)):
    require(current_user, VISITORS_WELCOME_OPERATE)
    return await move(payload.action, payload.version, current_user["user_id"])


@operator_sync_router.websocket("/ws")
async def welcome_socket(websocket: WebSocket, ticket: Optional[str] = None):
    """Pantallas y operador: se entra con un boleto de un solo uso (POST …/ticket)."""
    try:
        who = await redeem(ticket)
    except HTTPException as exc:
        await websocket.accept()
        await websocket.send_json({"type": "error", "status": exc.status_code, "detail": exc.detail})
        await websocket.close(code=4000 + exc.status_code if 400 <= exc.status_code < 1000 else 4400)
        return
    await websocket.accept()
    member = {"websocket": websocket, "kind": who["kind"], "queue": asyncio.Queue(maxsize=16)}

    async def pump():
        while True:
            await websocket.send_json(await member["queue"].get())

    hub.members[id(member)] = member
    sender = asyncio.create_task(pump())
    member["queue"].put_nowait(await current_position())  # al conectar (y reconectar): el estado actual
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            try:
                parsed = json.loads(message.get("text") or "{}")
            except ValueError:
                continue
            kind = parsed.get("type")
            if kind == "move" and parsed.get("action") in ACTIONS and isinstance(parsed.get("version"), int):
                result = await move(parsed["action"], parsed["version"], who["by"])
                if not result["moved"]:  # versión vieja: se le manda la posición vigente solo a él
                    member["queue"].put_nowait({key: value for key, value in result.items() if key not in {"moved", "stale"}})
            elif kind == "sync":
                member["queue"].put_nowait(await current_position())
            elif kind == "ping":
                member["queue"].put_nowait({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — una conexión rota nunca tumba a las demás
        logger.warning("bienvenida: conexión cerrada con error", exc_info=True)
    finally:
        hub.members.pop(id(member), None)
        sender.cancel()


async def ensure_indexes() -> None:
    await db.visitor_welcome_tickets.create_index("expires_at", expireAfterSeconds=0)  # los boletos sin usar se borran solos
