"""Eventos, ocurrencias, tablero y archivos del Mega-Bloque E."""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pymongo import ReturnDocument

from operations_engine import (
    audit, can_checkin, can_manage, can_reports, materialize_event, now_utc,
    require_operations_manage, require_operations_view, serialize,
)
from operations_models import EventCreate, EventUpdate
from server import db


router = APIRouter(prefix="/api/operations", tags=["operations-events"])
ATTACHMENT_BUCKET = "operation_attachments"
ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024
ALLOWED_FILES = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


def attachment_bucket():
    return AsyncIOMotorGridFSBucket(db, bucket_name=ATTACHMENT_BUCKET)


def _safe_name(value: Optional[str]) -> str:
    return re.sub(r"[^A-Za-z0-9._ -]", "_", value or "archivo")[:180] or "archivo"


def _permissions(user: dict) -> dict:
    return {"view": True, "manage": can_manage(user), "checkin": can_checkin(user), "reports": can_reports(user)}


async def _event_or_404(event_id: str) -> dict:
    event = await db.operation_events.find_one({"event_id": event_id, "status": {"$ne": "archived"}}, {"_id": 0})
    if not event: raise HTTPException(status_code=404, detail="Evento no encontrado")
    return event


async def _occurrence_summaries(event_id: str) -> list[dict]:
    occurrences = await db.operation_event_occurrences.find({"event_id": event_id}, {"_id": 0}).sort("starts_at", 1).limit(300).to_list(300)
    for item in occurrences:
        occurrence_id = item["occurrence_id"]
        item["registrations"] = await db.operation_registrations.count_documents({"occurrence_id": occurrence_id, "status": {"$ne": "cancelled"}})
        item["checkins"] = await db.operation_checkins.count_documents({"occurrence_id": occurrence_id, "status": "active"})
        item["volunteers"] = await db.operation_volunteer_assignments.count_documents({"occurrence_id": occurrence_id, "status": {"$in": ["confirmed", "checked_in"]}})
    return serialize(occurrences)


@router.get("/dashboard", response_model=dict)
async def operations_dashboard(current_user: dict = Depends(require_operations_view)):
    now = now_utc(); week_end = now + timedelta(days=7); day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    upcoming = await db.operation_event_occurrences.find({"starts_at": {"$gte": now, "$lte": week_end}, "status": {"$in": ["scheduled", "checkin_open"]}}, {"_id": 0}).sort("starts_at", 1).limit(12).to_list(12)
    event_ids = list({item["event_id"] for item in upcoming}); events = await db.operation_events.find({"event_id": {"$in": event_ids}}, {"_id": 0, "event_id": 1, "title": 1, "location": 1, "event_type": 1, "recurrence.frequency": 1}).to_list(100)
    event_map = {item["event_id"]: item for item in events}
    for occurrence in upcoming: occurrence["event"] = event_map.get(occurrence["event_id"], {})
    shift_ids = await db.operation_shifts.distinct("shift_id", {"occurrence_id": {"$in": [item["occurrence_id"] for item in upcoming]}, "status": "open"})
    shifts = await db.operation_shifts.find({"shift_id": {"$in": shift_ids}}, {"_id": 0, "shift_id": 1, "required_volunteers": 1}).to_list(1000)
    confirmed = await db.operation_volunteer_assignments.count_documents({"shift_id": {"$in": shift_ids}, "status": {"$in": ["confirmed", "checked_in"]}})
    required = sum(item.get("required_volunteers", 0) for item in shifts)
    upcoming_total = await db.operation_event_occurrences.count_documents({"starts_at": {"$gte": now, "$lte": week_end}, "status": {"$in": ["scheduled", "checkin_open"]}})
    checkins_today = await db.operation_checkins.count_documents({"checked_in_at": {"$gte": day_start}, "status": "active"})
    notifications = await db.operation_notifications.find({"recipient_user_id": current_user["user_id"], "read_at": None}, {"_id": 0}).sort("created_at", -1).limit(8).to_list(8)
    return serialize({"metrics": {"upcoming_occurrences": upcoming_total, "checkins_today": checkins_today, "volunteers_confirmed": confirmed, "open_volunteer_slots": max(0, required - confirmed)}, "upcoming": upcoming, "notifications": notifications, "permissions": _permissions(current_user)})


@router.get("/catalog", response_model=dict)
async def operations_catalog(current_user: dict = Depends(require_operations_view)):
    ministries = await db.ministry_catalog.find({"activo": True}, {"_id": 1, "nombre": 1}).sort("nombre", 1).to_list(500)
    cells = await db.cells.find({"status": "active"}, {"_id": 0, "cell_id": 1, "name": 1}).sort("name", 1).to_list(500)
    return {"ministries": [{"ministry_id": str(item["_id"]), "name": item.get("nombre") or "Ministerio"} for item in ministries], "cells": cells, "permissions": _permissions(current_user)}


@router.get("/events", response_model=dict)
async def list_events(event_status: Optional[str] = Query(default=None, alias="status"), current_user: dict = Depends(require_operations_view)):
    query = {"status": {"$ne": "archived"}}
    if event_status: query["status"] = event_status
    items = await db.operation_events.find(query, {"_id": 0}).sort("starts_at", 1).limit(500).to_list(500)
    for item in items:
        item["occurrence_count"] = await db.operation_event_occurrences.count_documents({"event_id": item["event_id"]})
        item["next_occurrence"] = await db.operation_event_occurrences.find_one({"event_id": item["event_id"], "starts_at": {"$gte": now_utc()}, "status": {"$ne": "cancelled"}}, {"_id": 0}, sort=[("starts_at", 1)])
    return serialize({"items": items, "permissions": _permissions(current_user)})


@router.post("/events", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_event(payload: EventCreate, current_user: dict = Depends(require_operations_manage)):
    now = now_utc(); event_id = str(uuid4()); values = payload.model_dump()
    starts = values["starts_at"]; ends = values["ends_at"]
    if starts.tzinfo is None: starts = starts.replace(tzinfo=timezone.utc)
    if ends.tzinfo is None: ends = ends.replace(tzinfo=timezone.utc)
    doc = {"_id": event_id, "event_id": event_id, **values, "starts_at": starts.astimezone(timezone.utc), "ends_at": ends.astimezone(timezone.utc), "recurrence": values["recurrence"].model_dump() if hasattr(values["recurrence"], "model_dump") else values["recurrence"], "attachments": [], "created_by_user_id": current_user["user_id"], "updated_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.operation_events.insert_one(doc)
    materialized = await materialize_event(doc)
    await audit(current_user, "event_created", "event", event_id, {"title": doc["title"], **materialized})
    return serialize({**doc, "materialization": materialized, "permissions": _permissions(current_user)})


@router.get("/events/{event_id}", response_model=dict)
async def event_detail(event_id: str, current_user: dict = Depends(require_operations_view)):
    event = await _event_or_404(event_id)
    return serialize({**event, "occurrences": await _occurrence_summaries(event_id), "permissions": _permissions(current_user)})


@router.patch("/events/{event_id}", response_model=dict)
async def update_event(event_id: str, payload: EventUpdate, current_user: dict = Depends(require_operations_manage)):
    await _event_or_404(event_id); update = payload.model_dump(exclude_unset=True)
    if not update: raise HTTPException(status_code=422, detail="No hay cambios")
    update.update({"updated_by_user_id": current_user["user_id"], "updated_at": now_utc()})
    result = await db.operation_events.find_one_and_update({"event_id": event_id}, {"$set": update}, return_document=ReturnDocument.AFTER, projection={"_id": 0})
    if update.get("status") == "cancelled": await db.operation_event_occurrences.update_many({"event_id": event_id, "starts_at": {"$gte": now_utc()}, "status": {"$ne": "closed"}}, {"$set": {"status": "cancelled", "updated_at": now_utc()}})
    await audit(current_user, "event_updated", "event", event_id, update)
    return serialize({**result, "permissions": _permissions(current_user)})


@router.post("/events/{event_id}/materialize", response_model=dict)
async def materialize_more(event_id: str, horizon_days: int = Query(default=365, ge=30, le=730), current_user: dict = Depends(require_operations_manage)):
    event = await _event_or_404(event_id); result = await materialize_event(event, horizon_days)
    await audit(current_user, "occurrences_materialized", "event", event_id, result)
    return result


def _valid_magic(content_type: str, first_chunk: bytes) -> bool:
    if content_type == "application/pdf": return first_chunk.startswith(b"%PDF-")
    if content_type == "image/png": return first_chunk.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg": return first_chunk.startswith(b"\xff\xd8\xff")
    return False


@router.post("/events/{event_id}/attachments", status_code=status.HTTP_201_CREATED, response_model=dict)
async def upload_event_attachment(event_id: str, file: UploadFile = File(...), current_user: dict = Depends(require_operations_manage)):
    await _event_or_404(event_id)
    if file.content_type not in ALLOWED_FILES: raise HTTPException(status_code=415, detail="Use PDF, PNG o JPEG")
    safe_name = _safe_name(file.filename); stream = attachment_bucket().open_upload_stream(safe_name, metadata={"event_id": event_id, "content_type": file.content_type, "uploaded_by_user_id": current_user["user_id"]}); file_id = stream._id; total = 0; first = True
    try:
        while True:
            chunk = await file.read(256 * 1024)
            if not chunk: break
            if first and not _valid_magic(file.content_type, chunk): raise HTTPException(status_code=415, detail="La firma del archivo no coincide con su tipo")
            first = False; total += len(chunk)
            if total > ATTACHMENT_MAX_BYTES: raise HTTPException(status_code=413, detail="El archivo excede 5 MiB")
            await stream.write(chunk)
        if total == 0: raise HTTPException(status_code=422, detail="El archivo está vacío")
        await stream.close()
        attachment = {"file_id": str(file_id), "filename": safe_name, "content_type": file.content_type, "size": total, "uploaded_at": now_utc(), "uploaded_by_user_id": current_user["user_id"]}
        linked = await db.operation_events.update_one({"event_id": event_id}, {"$push": {"attachments": attachment}, "$set": {"updated_at": now_utc()}})
        if linked.matched_count != 1: raise HTTPException(status_code=404, detail="Evento no encontrado")
    except Exception:
        try: await stream.abort()
        except Exception:
            try: await attachment_bucket().delete(file_id)
            except Exception: pass
        raise
    finally: await file.close()
    await audit(current_user, "attachment_uploaded", "event", event_id, {"file_id": str(file_id), "filename": safe_name})
    return serialize(attachment)


@router.get("/events/{event_id}/attachments/{file_id}")
async def download_event_attachment(event_id: str, file_id: str, current_user: dict = Depends(require_operations_view)):
    if not ObjectId.is_valid(file_id): raise HTTPException(status_code=404, detail="Archivo no encontrado")
    event = await db.operation_events.find_one({"event_id": event_id, "attachments.file_id": file_id}, {"_id": 0, "attachments": 1})
    if not event: raise HTTPException(status_code=404, detail="Archivo no encontrado")
    attachment = next((item for item in event.get("attachments", []) if item.get("file_id") == file_id), None)
    if not attachment: raise HTTPException(status_code=404, detail="Archivo no encontrado")
    stream = await attachment_bucket().open_download_stream(ObjectId(file_id))
    async def body():
        while True:
            block = await stream.readchunk()
            if not block: break
            yield block
    return StreamingResponse(body(), media_type=attachment["content_type"], headers={"Content-Disposition": f'attachment; filename="{_safe_name(attachment["filename"])}"', "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})