"""Recurrencia, materialización, auditoría y permisos de Operaciones."""
import calendar
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import NAMESPACE_URL, uuid4, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import ObjectId
from fastapi import Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from access_control import (
    OPERATIONS_CHECKIN, OPERATIONS_MANAGE, OPERATIONS_REPORTS, OPERATIONS_VIEW,
    OPERATIONS_VOLUNTEER, has_capability, is_global_pastoral_authority,
)
from operations_models import RecurrenceRule
from server import db, get_current_user


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, ObjectId): return str(value)
    if isinstance(value, list): return [serialize(item) for item in value]
    if isinstance(value, dict): return {key: serialize(item) for key, item in value.items() if key != "_id"}
    return value


def _require(user: dict, capability: str, message: str) -> dict:
    if is_global_pastoral_authority(user) or has_capability(user, capability): return user
    raise HTTPException(status_code=403, detail=message)


def require_operations_view(user: dict = Depends(get_current_user)) -> dict:
    return _require(user, OPERATIONS_VIEW, "Sin acceso al módulo de Operaciones")


def require_operations_manage(user: dict = Depends(get_current_user)) -> dict:
    return _require(user, OPERATIONS_MANAGE, "Gestión de eventos restringida")


def require_operations_checkin(user: dict = Depends(get_current_user)) -> dict:
    if is_global_pastoral_authority(user) or has_capability(user, OPERATIONS_CHECKIN) or has_capability(user, OPERATIONS_MANAGE): return user
    raise HTTPException(status_code=403, detail="Check-in restringido")


def can_manage(user: dict) -> bool:
    return is_global_pastoral_authority(user) or has_capability(user, OPERATIONS_MANAGE)


def can_checkin(user: dict) -> bool:
    return can_manage(user) or has_capability(user, OPERATIONS_CHECKIN)


def can_reports(user: dict) -> bool:
    return can_manage(user) or has_capability(user, OPERATIONS_REPORTS)


async def audit(user: dict, action: str, entity_type: str, entity_id: str, details: Optional[dict] = None) -> None:
    audit_id = str(uuid4())
    await db.operation_audit_events.insert_one({"_id": audit_id, "audit_id": audit_id, "action": action, "entity_type": entity_type, "entity_id": entity_id, "actor_user_id": user["user_id"], "details": details or {}, "occurred_at": now_utc()})


async def notify_person(person_id: str, event_id: str, title: str, message: str, notification_type: str) -> None:
    user = await db.users.find_one({"person_id": person_id, "is_active": {"$ne": False}}, {"_id": 1})
    if not user: return
    notification_id = str(uuid4())
    await db.operation_notifications.insert_one({"_id": notification_id, "notification_id": notification_id, "recipient_user_id": str(user["_id"]), "event_id": event_id, "type": notification_type, "title": title, "message": message, "read_at": None, "created_at": now_utc()})


def _next_month(value: datetime, interval: int, month_day: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 + interval
    year, month = divmod(month_index, 12); month += 1
    day = min(month_day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def recurrence_starts(starts_at: datetime, timezone_name: str, rule: RecurrenceRule, horizon_days: int = 180) -> list[datetime]:
    try: zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc: raise HTTPException(status_code=422, detail="Zona horaria inválida") from exc
    start = (starts_at if starts_at.tzinfo else starts_at.replace(tzinfo=zone)).astimezone(zone)
    if rule.frequency == "none": return [start.astimezone(timezone.utc)]
    horizon = now_utc().astimezone(zone) + timedelta(days=horizon_days)
    until = rule.until.astimezone(zone) if rule.until and rule.until.tzinfo else rule.until.replace(tzinfo=zone) if rule.until else horizon
    maximum = rule.count if rule.end_mode == "count" else 200
    results = []
    if rule.frequency == "daily":
        current = start
        while len(results) < maximum and current <= horizon and current <= until:
            results.append(current.astimezone(timezone.utc)); current += timedelta(days=rule.interval)
    elif rule.frequency == "weekly":
        current = start; weekdays = set(rule.weekdays)
        while len(results) < maximum and current <= horizon and current <= until:
            week_index = (current.date() - start.date()).days // 7
            if current.weekday() in weekdays and week_index % rule.interval == 0:
                results.append(current.astimezone(timezone.utc))
            current += timedelta(days=1)
    else:
        current = start; month_day = rule.month_day or start.day
        while len(results) < maximum and current <= horizon and current <= until:
            results.append(current.astimezone(timezone.utc)); current = _next_month(current, rule.interval, month_day)
    return results


async def materialize_shifts_for_occurrence(event: dict, occurrence: dict) -> int:
    templates = await db.operation_shift_templates.find({"event_id": event["event_id"], "active": True, "$or": [{"scope": "all_occurrences"}, {"scope": "single_occurrence", "occurrence_id": occurrence["occurrence_id"]}]}, {"_id": 0}).to_list(1000)
    created = 0
    for template in templates:
        shift_id = str(uuid5(NAMESPACE_URL, f"operation-shift:{template['template_id']}:{occurrence['occurrence_id']}"))
        starts = occurrence["starts_at"] + timedelta(minutes=template["start_offset_minutes"])
        doc = {"_id": shift_id, "shift_id": shift_id, "template_id": template["template_id"], "event_id": event["event_id"], "occurrence_id": occurrence["occurrence_id"], "name": template["name"], "role_name": template["role_name"], "starts_at": starts, "ends_at": starts + timedelta(minutes=template["duration_minutes"]), "required_volunteers": template["required_volunteers"], "ministry_id": template.get("ministry_id"), "cell_id": template.get("cell_id"), "instructions": template.get("instructions"), "status": "open", "created_at": now_utc()}
        try: await db.operation_shifts.insert_one(doc); created += 1
        except DuplicateKeyError: pass
    return created


async def materialize_event(event: dict, horizon_days: int = 180) -> dict:
    rule = RecurrenceRule(**event.get("recurrence", {})); duration = event["ends_at"] - event["starts_at"]
    starts = recurrence_starts(event["starts_at"], event["timezone"], rule, horizon_days)
    created = 0; shifts_created = 0
    for start in starts:
        occurrence_id = str(uuid5(NAMESPACE_URL, f"operation-occurrence:{event['event_id']}:{start.isoformat()}"))
        doc = {"_id": occurrence_id, "occurrence_id": occurrence_id, "event_id": event["event_id"], "starts_at": start, "ends_at": start + duration, "status": "scheduled", "capacity": event.get("capacity"), "created_at": now_utc(), "updated_at": now_utc()}
        result = await db.operation_event_occurrences.update_one({"_id": occurrence_id}, {"$setOnInsert": doc}, upsert=True)
        if result.upserted_id:
            created += 1; shifts_created += await materialize_shifts_for_occurrence(event, doc)
    if starts:
        await db.operation_events.update_one({"event_id": event["event_id"]}, {"$set": {"materialized_until": max(starts), "updated_at": now_utc()}})
    return {"created_occurrences": created, "created_shifts": shifts_created, "materialized_until": max(starts).isoformat() if starts else None}


async def canonical_person(person_id: str) -> dict:
    if not ObjectId.is_valid(person_id): raise HTTPException(status_code=422, detail="Persona inválida")
    person = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}}, {"_id": 1, "person_number": 1, "nombre": 1, "apellido": 1, "search_key": 1})
    if not person: raise HTTPException(status_code=404, detail="Persona 360 no encontrada")
    return {"person_id": str(person["_id"]), "person_number": person.get("person_number"), "name": " ".join(filter(None, [person.get("nombre"), person.get("apellido")])).strip()}


async def ensure_operations_indexes() -> None:
    await db.operation_events.create_index("event_id", unique=True)
    await db.operation_event_occurrences.create_index("occurrence_id", unique=True)
    await db.operation_event_occurrences.create_index([("event_id", 1), ("starts_at", 1)], unique=True)
    await db.operation_event_occurrences.create_index([("status", 1), ("starts_at", 1)])
    await db.operation_shift_templates.create_index("template_id", unique=True)
    await db.operation_shifts.create_index("shift_id", unique=True)
    await db.operation_shifts.create_index([("occurrence_id", 1), ("starts_at", 1)])
    await db.operation_volunteer_assignments.create_index("assignment_id", unique=True)
    await db.operation_volunteer_assignments.create_index([("shift_id", 1), ("person_id", 1)], unique=True)
    await db.operation_registrations.create_index("registration_id", unique=True)
    await db.operation_registrations.create_index("registration_code", unique=True)
    await db.operation_registrations.create_index([("occurrence_id", 1), ("person_id", 1)], unique=True, sparse=True)
    await db.operation_checkins.create_index("checkin_id", unique=True)
    await db.operation_checkins.create_index("duplicate_key", unique=True)
    await db.operation_checkins.create_index("idempotency_key", unique=True)
    await db.operation_audit_events.create_index([("entity_type", 1), ("entity_id", 1), ("occurred_at", -1)])
    await db.operation_notifications.create_index([("recipient_user_id", 1), ("read_at", 1), ("created_at", -1)])