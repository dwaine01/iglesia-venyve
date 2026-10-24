"""FASE 6B — Notificaciones push (PREPARADO, APAGADO hasta que el dueño apruebe).

Las notificaciones dentro del portal siempre funcionan. El push al celular se
suma encima y queda activo SOLO si se cumplen TODAS estas condiciones:
  1. Variable de entorno PUSH_NOTIFICATIONS_ENABLED=true (interruptor explícito).
  2. VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY y VAPID_SUBJECT (ej. "mailto:...")
     configuradas en Railway. Nunca se guardan claves en el repositorio.
  3. La dependencia `pywebpush` instalada (NO está en requirements.txt: se
     agrega solo cuando el dueño lo apruebe).
Si falta cualquiera, /config responde enabled=false y nada se envía."""
import asyncio
import json
import logging
import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server import db, get_current_user, utc_now

router = APIRouter(prefix="/api/notifications/push", tags=["push-notifications"])
logger = logging.getLogger(__name__)


def _webpush():
    try:
        from pywebpush import WebPushException, webpush  # type: ignore
        return webpush, WebPushException
    except ImportError:
        return None, None


def push_settings() -> dict:
    return {
        "switch": (os.environ.get("PUSH_NOTIFICATIONS_ENABLED") or "").strip().lower() == "true",
        "public_key": os.environ.get("VAPID_PUBLIC_KEY") or None,
        "private_key": os.environ.get("VAPID_PRIVATE_KEY") or None,
        "subject": os.environ.get("VAPID_SUBJECT") or None,
    }


def push_enabled() -> bool:
    settings = push_settings()
    return bool(settings["switch"] and settings["public_key"] and settings["private_key"] and settings["subject"] and _webpush()[0])


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=300)
    auth: str = Field(min_length=8, max_length=100)


class SubscriptionInput(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: SubscriptionKeys


@router.get("/config", response_model=dict)
async def push_config(current_user: dict = Depends(get_current_user)):
    enabled = push_enabled()
    return {"enabled": enabled, "public_key": push_settings()["public_key"] if enabled else None}


@router.post("/subscribe", response_model=dict)
async def subscribe(payload: SubscriptionInput, current_user: dict = Depends(get_current_user)):
    if not push_enabled():
        raise HTTPException(status_code=409, detail="Las notificaciones push todavía no están activadas")
    now = utc_now()
    await db.push_subscriptions.update_one(
        {"endpoint": payload.endpoint},
        {"$set": {"user_id": current_user["user_id"], "keys": payload.keys.model_dump(), "updated_at": now},
         "$setOnInsert": {"_id": str(uuid4()), "created_at": now}},
        upsert=True,
    )
    return {"subscribed": True}


@router.delete("/subscribe", response_model=dict)
async def unsubscribe(payload: SubscriptionInput, current_user: dict = Depends(get_current_user)):
    await db.push_subscriptions.delete_many({"endpoint": payload.endpoint, "user_id": current_user["user_id"]})
    return {"subscribed": False}


async def _send(user_ids: list[str], title: str, message: str, link: Optional[str]) -> None:
    webpush, web_push_exception = _webpush()
    settings = push_settings()
    body = json.dumps({"title": title, "body": message, "url": link or "/"})
    async for subscription in db.push_subscriptions.find({"user_id": {"$in": user_ids}}):
        info = {"endpoint": subscription["endpoint"], "keys": subscription["keys"]}
        try:
            await asyncio.to_thread(webpush, subscription_info=info, data=body, vapid_private_key=settings["private_key"], vapid_claims={"sub": settings["subject"]})
        except web_push_exception as error:  # suscripción vencida: se borra
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status in (404, 410):
                await db.push_subscriptions.delete_one({"_id": subscription["_id"]})
            else:
                logger.warning("push: envío fallido (%s)", status)
        except Exception as error:  # el push nunca rompe el aviso del portal
            logger.warning("push: %s", type(error).__name__)


_tasks: set = set()


def send_push_background(user_ids: list[str], title: str, message: str, link: Optional[str]) -> None:
    """Se llama al crear avisos del portal; no hace nada si el push está apagado."""
    if not user_ids or not push_enabled():
        return
    try:
        task = asyncio.get_running_loop().create_task(_send(user_ids, title, message, link))
    except RuntimeError:
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def ensure_indexes() -> None:
    await db.push_subscriptions.create_index("endpoint", unique=True)
    await db.push_subscriptions.create_index("user_id")
