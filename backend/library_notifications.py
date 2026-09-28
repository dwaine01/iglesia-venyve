"""Librería 360 · Fase 5: notificaciones internas de Órdenes de Compra vencidas.
Reutiliza el mismo patrón de bandeja/historial/"marcar como visto" ya usado en
Operaciones, pero en una colección propia de Librería para no mezclar ni
alterar las notificaciones de otros módulos."""
import hmac
import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from access_control import LIBRARY_CATALOG_MANAGE, LIBRARY_INVENTORY_MANAGE, has_capability, is_general_coordinator
from library_module import now_utc, serialize
from library_purchase_orders import po_overdue_info
from server import db, get_current_user

router = APIRouter(prefix="/api/library", tags=["library-notifications"])

WEBHOOK_CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET")


async def resolve_library_notification_recipients() -> list[str]:
    users = await db.users.find({}, {"_id": 1, "capabilities": 1, "rol": 1, "role": 1, "access_level": 1,
                                      "privilege_groups": 1, "is_active": 1}).to_list(2000)
    recipients = []
    for user in users:
        if user.get("is_active") is False:
            continue
        if has_capability(user, LIBRARY_CATALOG_MANAGE) or has_capability(user, LIBRARY_INVENTORY_MANAGE) or is_general_coordinator(user):
            recipients.append(str(user["_id"]))
    return recipients


async def sync_overdue_po_notifications() -> dict:
    pos = await db.library_purchase_orders.find({"status": {"$in": ["ordered", "partially_received"]}}, {"_id": 0}).to_list(2000)
    overdue = [{**po, **po_overdue_info(po)} for po in pos]
    overdue = [po for po in overdue if po["is_overdue"]]
    if not overdue:
        return {"created": 0, "skipped": 0}
    recipients = await resolve_library_notification_recipients()
    created, skipped = 0, 0
    for po in overdue:
        existing_unread = await db.library_notifications.find_one({"reference_id": po["po_id"], "type": "po_overdue", "read_at": None})
        if existing_unread:
            skipped += 1
            continue
        title = f"Orden de compra vencida: {po['po_number']}"
        message = (f"Proveedor: {po['provider_name']} · Fecha esperada: {str(po.get('expected_date'))[:10]} · "
                    f"Días de atraso: {po['days_overdue']} · Unidades pendientes: {po['pending_quantity']}")
        now = now_utc()
        for recipient_id in recipients:
            await db.library_notifications.insert_one({
                "_id": str(uuid4()), "notification_id": str(uuid4()), "recipient_user_id": recipient_id,
                "type": "po_overdue", "reference_id": po["po_id"], "title": title, "message": message,
                "link": "/libreria/ordenes-compra", "read_at": None, "auto_resolved": False, "created_at": now,
            })
        created += 1
    return {"created": created, "skipped": skipped, "recipients": len(recipients)}


async def resolve_po_notifications(po_id: str) -> None:
    """Al recibirse por completo, cerrarse o cancelarse una PO, sus alertas de vencimiento dejan de mostrarse."""
    await db.library_notifications.update_many(
        {"reference_id": po_id, "type": "po_overdue", "read_at": None},
        {"$set": {"read_at": now_utc(), "auto_resolved": True}},
    )


async def ensure_indexes() -> None:
    await db.library_notifications.create_index("notification_id", unique=True)
    await db.library_notifications.create_index([("recipient_user_id", 1), ("read_at", 1), ("created_at", -1)])
    await db.library_notifications.create_index([("reference_id", 1), ("type", 1), ("read_at", 1)])


@router.get("/notifications", response_model=dict)
async def list_notifications(current_user: dict = Depends(get_current_user)):
    items = await db.library_notifications.find({"recipient_user_id": current_user["user_id"]}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    unread_count = sum(1 for item in items if not item.get("read_at"))
    return {"items": serialize(items), "unread_count": unread_count}


@router.patch("/notifications/{notification_id}/read", response_model=dict)
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.library_notifications.update_one(
        {"notification_id": notification_id, "recipient_user_id": current_user["user_id"]}, {"$set": {"read_at": now_utc()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return {"marked_read": True}


@router.post("/cron/overdue-notifications", status_code=202)
async def cron_overdue_notifications(background_tasks: BackgroundTasks, authorization: Optional[str] = Header(None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not WEBHOOK_CRON_SECRET or not hmac.compare_digest(token, WEBHOOK_CRON_SECRET):
        raise HTTPException(status_code=401, detail="No autorizado")
    background_tasks.add_task(sync_overdue_po_notifications)
    return {"accepted": True}
