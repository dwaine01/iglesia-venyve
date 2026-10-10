"""Campaña Ven y Come — panel de control del operador + pantalla pública en vivo."""
import secrets
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator

from access_control import CAMPAIGN_VENYCOME_MANAGE, has_capability, is_general_coordinator, is_global_pastoral_authority
from server import db, get_authenticated_user, get_current_user

router = APIRouter(prefix="/api/campaigns/venycome", tags=["campaign-venycome"])

MAX_AMOUNT_CENTS = 10_000_000  # tope defensivo ($100,000) contra error de dedo
DONATION_TYPES = Literal["promise", "received"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize(item) for item in doc]
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def is_campaign_operator(user: dict) -> bool:
    return is_global_pastoral_authority(user) or is_general_coordinator(user) or has_capability(user, CAMPAIGN_VENYCOME_MANAGE)


def operator(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_campaign_operator(current_user):
        raise HTTPException(status_code=403, detail="No tiene permiso de Operador de Campaña Ven y Come")
    return current_user


async def audit(action: str, donation_id: Optional[str], actor_user_id: str, before: Optional[dict], after: Optional[dict]):
    await db.campaign_audit_events.insert_one({
        "_id": str(uuid4()), "action": action, "donation_id": donation_id,
        "actor_user_id": actor_user_id, "before": before, "after": after, "created_at": now_utc(),
    })


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, message: dict):
        stale = []
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()


class DonationInput(BaseModel):
    donor_name: Optional[str] = Field(default=None, max_length=120)
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)
    donation_type: DONATION_TYPES = "received"
    anonymous: bool = False
    consent_show_name: bool = False
    idempotency_key: Optional[str] = Field(default=None, max_length=80)

    @field_validator("donor_name")
    @classmethod
    def strip_name(cls, value):
        if value is None:
            return value
        cleaned = value.strip()[:120]
        return cleaned or None


class DonationUpdateInput(BaseModel):
    donor_name: Optional[str] = Field(default=None, max_length=120)
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)
    donation_type: DONATION_TYPES
    anonymous: bool = False
    consent_show_name: bool = False


class SettingsInput(BaseModel):
    goal_cents: int = Field(gt=0, le=1_000_000_000)
    counting_rule: Literal["committed", "received_only"] = "committed"
    mode: Literal["production", "rehearsal"] = "rehearsal"


class PresentationLinkInput(BaseModel):
    label: Optional[str] = Field(default=None, max_length=120)


async def get_settings() -> dict:
    settings = await db.campaign_settings.find_one({"_id": "venycome"}, {"_id": 0})
    if not settings:
        settings = {"goal_cents": 1_200_000, "counting_rule": "committed", "mode": "rehearsal", "updated_at": now_utc(), "updated_by_user_id": None}
        await db.campaign_settings.update_one({"_id": "venycome"}, {"$set": settings}, upsert=True)
    return settings


async def compute_summary(mode: str) -> dict:
    settings = await get_settings()
    is_rehearsal = mode == "rehearsal"
    cursor = db.campaign_donations.find({"status": "active", "is_rehearsal": is_rehearsal}, {"_id": 0, "amount_cents": 1, "donation_type": 1})
    received_cents = 0
    pending_cents = 0
    async for item in cursor:
        if item["donation_type"] == "received":
            received_cents += item["amount_cents"]
        else:
            pending_cents += item["amount_cents"]
    committed_cents = received_cents + pending_cents
    goal_cents = settings["goal_cents"]
    counted_cents = committed_cents if settings["counting_rule"] == "committed" else received_cents
    percent = min(1.0, counted_cents / goal_cents) if goal_cents else 0.0
    return {
        "mode": mode, "goal_cents": goal_cents, "counting_rule": settings["counting_rule"],
        "received_cents": received_cents, "pending_cents": pending_cents, "committed_cents": committed_cents,
        "counted_cents": counted_cents, "percent": round(percent, 6),
    }


def donor_label(donation: dict) -> str:
    if donation.get("anonymous") or not donation.get("consent_show_name"):
        return "Donante anónimo"
    return donation.get("donor_name") or "Donante anónimo"


async def donation_doc(donation_id: str) -> dict:
    doc = await db.campaign_donations.find_one({"donation_id": donation_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Donativo no encontrado")
    return doc


# ---------------- Operator endpoints (requieren capability Operador de Campaña) ----------------

@router.get("/settings", response_model=dict)
async def read_settings(current_user: dict = Depends(operator)):
    return serialize(await get_settings())


@router.put("/settings", response_model=dict)
async def update_settings(payload: SettingsInput, current_user: dict = Depends(operator)):
    data = payload.model_dump()
    data["updated_at"] = now_utc()
    data["updated_by_user_id"] = current_user["user_id"]
    await db.campaign_settings.update_one({"_id": "venycome"}, {"$set": data}, upsert=True)
    summary = await compute_summary(data["mode"])
    await manager.broadcast({"type": "summary", **summary})
    return serialize(data)


@router.get("/summary", response_model=dict)
async def operator_summary(current_user: dict = Depends(operator)):
    settings = await get_settings()
    return await compute_summary(settings["mode"])


@router.post("/donations", status_code=201, response_model=dict)
async def create_donation(payload: DonationInput, current_user: dict = Depends(operator)):
    settings = await get_settings()
    if payload.idempotency_key:
        existing = await db.campaign_donations.find_one({"idempotency_key": payload.idempotency_key, "created_by_user_id": current_user["user_id"]}, {"_id": 0})
        if existing:
            return serialize(existing)
    donation_id = str(uuid4())
    now = now_utc()
    doc = {
        "_id": donation_id, "donation_id": donation_id, "donor_name": payload.donor_name,
        "amount_cents": payload.amount_cents, "donation_type": payload.donation_type,
        "anonymous": payload.anonymous, "consent_show_name": payload.consent_show_name,
        "is_rehearsal": settings["mode"] == "rehearsal", "status": "active",
        "idempotency_key": payload.idempotency_key, "shown_at": now,
        "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.campaign_donations.insert_one(doc)
    await audit("donation_created", donation_id, current_user["user_id"], None, doc)
    summary = await compute_summary(settings["mode"])
    await manager.broadcast({"type": "summary", **summary})
    await manager.broadcast({"type": "announcement", "donor_label": donor_label(doc), "amount_cents": doc["amount_cents"], "donation_type": doc["donation_type"]})
    return serialize(doc)


@router.get("/donations", response_model=dict)
async def list_donations(mode: Optional[str] = None, current_user: dict = Depends(operator)):
    settings = await get_settings()
    active_mode = mode or settings["mode"]
    items = await db.campaign_donations.find({"is_rehearsal": active_mode == "rehearsal"}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return {"items": serialize(items), "mode": active_mode}


@router.put("/donations/{donation_id}", response_model=dict)
async def update_donation(donation_id: str, payload: DonationUpdateInput, current_user: dict = Depends(operator)):
    before = await donation_doc(donation_id)
    if before["status"] == "voided":
        raise HTTPException(status_code=409, detail="No se puede editar un donativo anulado")
    updates = payload.model_dump()
    updates["updated_at"] = now_utc()
    updates["updated_by_user_id"] = current_user["user_id"]
    await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": updates})
    after = await donation_doc(donation_id)
    await audit("donation_updated", donation_id, current_user["user_id"], before, after)
    settings = await get_settings()
    summary = await compute_summary(settings["mode"])
    await manager.broadcast({"type": "summary", **summary})
    return serialize(after)


@router.post("/donations/{donation_id}/void", response_model=dict)
async def void_donation(donation_id: str, current_user: dict = Depends(operator)):
    before = await donation_doc(donation_id)
    if before["status"] == "voided":
        raise HTTPException(status_code=409, detail="Ya estaba anulado")
    await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": {"status": "voided", "updated_at": now_utc(), "voided_by_user_id": current_user["user_id"]}})
    after = await donation_doc(donation_id)
    await audit("donation_voided", donation_id, current_user["user_id"], before, after)
    settings = await get_settings()
    summary = await compute_summary(settings["mode"])
    await manager.broadcast({"type": "summary", **summary})
    return serialize(after)


@router.post("/donations/{donation_id}/mark-received", response_model=dict)
async def mark_received(donation_id: str, current_user: dict = Depends(operator)):
    before = await donation_doc(donation_id)
    if before["status"] == "voided":
        raise HTTPException(status_code=409, detail="No se puede modificar un donativo anulado")
    if before["donation_type"] == "received":
        raise HTTPException(status_code=409, detail="Ya estaba marcado como recibido")
    await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": {"donation_type": "received", "updated_at": now_utc()}})
    after = await donation_doc(donation_id)
    await audit("donation_marked_received", donation_id, current_user["user_id"], before, after)
    settings = await get_settings()
    summary = await compute_summary(settings["mode"])
    await manager.broadcast({"type": "summary", **summary})
    return serialize(after)


@router.post("/donations/{donation_id}/show", response_model=dict)
async def show_donation(donation_id: str, current_user: dict = Depends(operator)):
    doc = await donation_doc(donation_id)
    if doc["status"] == "voided":
        raise HTTPException(status_code=409, detail="No se puede mostrar un donativo anulado")
    await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": {"shown_at": now_utc()}})
    await manager.broadcast({"type": "announcement", "donor_label": donor_label(doc), "amount_cents": doc["amount_cents"], "donation_type": doc["donation_type"]})
    return {"ok": True}


@router.post("/settings/reset-rehearsal", response_model=dict)
async def reset_rehearsal(current_user: dict = Depends(operator)):
    result = await db.campaign_donations.delete_many({"is_rehearsal": True})
    await db.campaign_audit_events.insert_one({"_id": str(uuid4()), "action": "rehearsal_reset", "donation_id": None, "actor_user_id": current_user["user_id"], "before": None, "after": {"deleted_count": result.deleted_count}, "created_at": now_utc()})
    summary = await compute_summary("rehearsal")
    await manager.broadcast({"type": "summary", **summary})
    return {"deleted_count": result.deleted_count}


@router.post("/presentation-links", status_code=201, response_model=dict)
async def create_presentation_link(payload: PresentationLinkInput, current_user: dict = Depends(operator)):
    token_id = str(uuid4())
    token = secrets.token_urlsafe(24)
    now = now_utc()
    doc = {"_id": token_id, "token_id": token_id, "token": token, "label": payload.label, "active": True, "created_by_user_id": current_user["user_id"], "created_at": now, "revoked_at": None}
    await db.campaign_presentation_tokens.insert_one(doc)
    return serialize(doc)


@router.get("/presentation-links", response_model=dict)
async def list_presentation_links(current_user: dict = Depends(operator)):
    items = await db.campaign_presentation_tokens.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"items": serialize(items)}


@router.post("/presentation-links/{token_id}/revoke", response_model=dict)
async def revoke_presentation_link(token_id: str, current_user: dict = Depends(operator)):
    result = await db.campaign_presentation_tokens.update_one({"token_id": token_id}, {"$set": {"active": False, "revoked_at": now_utc()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Enlace no encontrado")
    return {"ok": True}


# ---------------- Public read-only (token de presentación o sesión autenticada) ----------------

async def resolve_public_access(token: Optional[str]) -> bool:
    if not token:
        return False
    link = await db.campaign_presentation_tokens.find_one({"token": token, "active": True}, {"_id": 0})
    if link:
        return True
    try:
        await get_authenticated_user(f"Bearer {token}")
        return True
    except HTTPException:
        return False


@router.get("/public/summary", response_model=dict)
async def public_summary(token: str):
    if not await resolve_public_access(token):
        raise HTTPException(status_code=403, detail="Token inválido o revocado")
    settings = await get_settings()
    return await compute_summary(settings["mode"])


@router.websocket("/public/ws")
async def public_ws(websocket: WebSocket, token: Optional[str] = None):
    if not await resolve_public_access(token):
        await websocket.accept()
        await websocket.close(code=4403)
        return
    await manager.connect(websocket)
    try:
        settings = await get_settings()
        await websocket.send_json({"type": "summary", **(await compute_summary(settings["mode"]))})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def ensure_indexes():
    await db.campaign_donations.create_index([("is_rehearsal", 1), ("status", 1)])
    await db.campaign_donations.create_index("idempotency_key")
    await db.campaign_presentation_tokens.create_index("token", unique=True)
