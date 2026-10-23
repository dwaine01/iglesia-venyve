"""FASE 6 — Notificaciones dentro del portal (genéricas).

Bandeja por cuenta: cada aviso guarda destinatario, tipo, título, mensaje y un
enlace dentro de la app. Siempre funciona dentro del portal; el envío push
(PWA) se agregará encima, activado solo por variables de entorno."""
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from server import db, get_current_user

router = APIRouter(prefix="/api/notifications", tags=["portal-notifications"])


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def notify_users(user_ids: list[str], notification_type: str, title: str, message: str, link: Optional[str] = None, ref: Optional[dict] = None) -> int:
    """Crea un aviso por destinatario (sin duplicar destinatarios)."""
    recipients = sorted({item for item in user_ids if item})
    if not recipients:
        return 0
    now = now_utc()
    await db.portal_notifications.insert_many([{
        "_id": str(uuid4()), "recipient_user_id": recipient, "type": notification_type, "title": title,
        "message": message, "link": link, "ref": ref or {}, "read_at": None, "created_at": now,
    } for recipient in recipients])
    return len(recipients)


async def notify_persons(person_ids: list[str], notification_type: str, title: str, message: str, link: Optional[str] = None, ref: Optional[dict] = None) -> int:
    """Igual que notify_users, resolviendo las cuentas activas de esas Personas."""
    ids = [item for item in person_ids if item]
    if not ids:
        return 0
    users = await db.users.find({"person_id": {"$in": ids}, "is_active": {"$ne": False}}, {"_id": 1}).to_list(5000)
    return await notify_users([str(item["_id"]) for item in users], notification_type, title, message, link, ref)


def serialize(item: dict) -> dict:
    return {
        "notification_id": item["_id"], "type": item.get("type"), "title": item.get("title"), "message": item.get("message"),
        "link": item.get("link"), "ref": item.get("ref") or {},
        "read_at": item["read_at"].isoformat() if item.get("read_at") else None,
        "created_at": item["created_at"].isoformat() if item.get("created_at") else None,
    }


@router.get("", response_model=dict)
async def my_notifications(limit: int = Query(30, ge=1, le=100), current_user: dict = Depends(get_current_user)):
    items = await db.portal_notifications.find({"recipient_user_id": current_user["user_id"]}).sort("created_at", -1).limit(limit).to_list(limit)
    unread = await db.portal_notifications.count_documents({"recipient_user_id": current_user["user_id"], "read_at": None})
    return {"items": [serialize(item) for item in items], "unread": unread}


@router.post("/{notification_id}/read", response_model=dict)
async def mark_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.portal_notifications.update_one({"_id": notification_id, "recipient_user_id": current_user["user_id"]}, {"$set": {"read_at": now_utc()}})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Aviso no encontrado")
    return {"read": True}


@router.post("/read-all", response_model=dict)
async def mark_all_read(current_user: dict = Depends(get_current_user)):
    result = await db.portal_notifications.update_many({"recipient_user_id": current_user["user_id"], "read_at": None}, {"$set": {"read_at": now_utc()}})
    return {"updated": result.modified_count}


async def ensure_indexes() -> None:
    await db.portal_notifications.create_index([("recipient_user_id", 1), ("read_at", 1), ("created_at", -1)])
