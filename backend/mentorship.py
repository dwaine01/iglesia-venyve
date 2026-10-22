"""Insignia de Mentor y calificación LBS (Fase 1).

Construido sobre lo existente: reutiliza `mentor_qualifications`
(mismo esquema que `front_groups.py`, con `front_group_id=None` para
"todos los grupos") y `mentor_assignments` de `consolidation_service.py`.
No duplica esas colecciones; solo agrega la insignia general de Mentor
(`mentor_badges`) y un listado de mentores activos para los selectores
de Consolidación.
"""
import re
from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import (
    MENTOR_QUALIFICATIONS_MANAGE,
    MENTORSHIP_BADGE_MANAGE,
    PERSON_CONTACTS_READ,
    PROCESSES_READ,
    can_access_person,
    has_capability,
    is_global_pastoral_authority,
)
from consolidation_service import load_person, mentor_qualification
from core_person import require_person_profile_user
from server import db, get_current_user


router = APIRouter(prefix="/api/mentorship", tags=["mentorship"])


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items() if key != "_id"}
    return value


class MentorBadgeInput(BaseModel):
    active: bool
    since: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=1000)


class MentorLbsInput(BaseModel):
    can_teach_lbs: bool
    note: Optional[str] = Field(default=None, max_length=1000)


def can_manage_badges(current_user: dict) -> bool:
    return (
        is_global_pastoral_authority(current_user)
        or has_capability(current_user, MENTORSHIP_BADGE_MANAGE)
        or has_capability(current_user, MENTOR_QUALIFICATIONS_MANAGE)
    )


def require_badge_manager(current_user: dict = Depends(get_current_user)) -> dict:
    if not can_manage_badges(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para administrar la insignia de Mentor")
    return current_user


async def assert_profile_scope(person_id: str, current_user: dict, person_doc: dict) -> None:
    if is_global_pastoral_authority(current_user):
        return
    linked_account = await db.users.find_one({"person_id": person_id}, {"_id": 0, "user_id": 1})
    person_payload = {
        "person_id": person_id,
        "created_by": person_doc.get("created_by"),
        "auth_user_id": linked_account.get("user_id") if linked_account else None,
    }
    if not can_access_person(current_user, person_payload):
        raise HTTPException(status_code=403, detail="Acceso no autorizado para esta persona")


async def audit(person_id: str, current_user: dict, action: str, detail: dict) -> None:
    history_id = str(uuid4())
    await db.mentor_badge_history.insert_one({
        "_id": history_id,
        "history_id": history_id,
        "person_id": person_id,
        "action": action,
        "detail": serialize(detail),
        "actor_user_id": current_user["user_id"],
        "actor_person_id": current_user.get("person_id"),
        "occurred_at": now_utc(),
    })


async def person_name(person_id: Optional[str]) -> Optional[str]:
    if not person_id or not ObjectId.is_valid(person_id):
        return None
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 0, "nombre": 1, "apellido": 1})
    return " ".join(part for part in [(person or {}).get("nombre"), (person or {}).get("apellido")] if part) or None


@router.get("/badge/{person_id}", response_model=dict)
async def get_mentor_badge(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    person_doc = await load_person(db, person_id)
    await assert_profile_scope(person_id, current_user, person_doc)
    badge = await db.mentor_badges.find_one({"person_id": person_id}, {"_id": 0})
    lbs = await mentor_qualification(db, person_id, None)
    history = await db.mentor_badge_history.find({"person_id": person_id}, {"_id": 0}).sort("occurred_at", -1).to_list(100)
    for item in history:
        item["actor_name"] = await person_name(item.get("actor_person_id"))
    return {
        "person_id": person_id,
        "active": bool(badge and badge.get("active")),
        "since": badge.get("since") if badge else None,
        "note": badge.get("note") if badge else None,
        "updated_at": serialize(badge.get("updated_at")) if badge else None,
        "lbs_qualified": bool(lbs),
        "lbs_note": (lbs or {}).get("notes"),
        "can_manage": can_manage_badges(current_user),
        "history": serialize(history),
    }


@router.put("/badge/{person_id}", response_model=dict)
async def set_mentor_badge(person_id: str, payload: MentorBadgeInput, current_user: dict = Depends(require_badge_manager)):
    await load_person(db, person_id)
    now = now_utc()
    since_value = payload.since.isoformat() if payload.since else (now.date().isoformat() if payload.active else None)
    fields = {
        "person_id": person_id,
        "active": payload.active,
        "since": since_value,
        "note": payload.note,
        "updated_by_user_id": current_user["user_id"],
        "updated_at": now,
    }
    await db.mentor_badges.update_one(
        {"person_id": person_id},
        {"$set": fields, "$setOnInsert": {"badge_id": str(uuid4()), "created_at": now}},
        upsert=True,
    )
    await audit(person_id, current_user, "mentor_badge_activated" if payload.active else "mentor_badge_deactivated", {"since": since_value, "note": payload.note})
    badge = await db.mentor_badges.find_one({"person_id": person_id}, {"_id": 0})
    return serialize(badge)


@router.put("/lbs/{person_id}", response_model=dict)
async def set_mentor_lbs(person_id: str, payload: MentorLbsInput, current_user: dict = Depends(require_badge_manager)):
    await load_person(db, person_id)
    now = now_utc()
    query = {"person_id": person_id, "front_group_id": None}
    fields = {
        "person_id": person_id,
        "front_group_id": None,
        "can_teach_lbs": payload.can_teach_lbs,
        "valid_until": None,
        "notes": payload.note,
        "active": True,
        "archived": False,
        "approved_by_user_id": current_user["user_id"],
        "approved_at": now,
        "updated_at": now,
    }
    await db.mentor_qualifications.update_one(
        query,
        {"$set": fields, "$setOnInsert": {"qualification_id": str(uuid4()), "created_at": now}},
        upsert=True,
    )
    await audit(person_id, current_user, "mentor_lbs_enabled" if payload.can_teach_lbs else "mentor_lbs_disabled", {"note": payload.note})
    return serialize(await db.mentor_qualifications.find_one(query, {"_id": 0}))


@router.get("/mentors", response_model=dict)
async def list_active_mentors(search: str = "", limit: int = 50, current_user: dict = Depends(get_current_user)):
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, PROCESSES_READ) and not can_manage_badges(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar mentores")
    limit = max(1, min(limit, 100))
    badges = await db.mentor_badges.find({"active": True}, {"_id": 0, "person_id": 1}).to_list(1000)
    person_ids = [item["person_id"] for item in badges if ObjectId.is_valid(item["person_id"])]
    if not person_ids:
        return {"items": [], "total": 0}
    query = {"_id": {"$in": [ObjectId(pid) for pid in person_ids]}, "is_archived": {"$ne": True}}
    clean_search = search.strip()
    if clean_search:
        pattern = re.escape(clean_search)
        query["$or"] = [{"nombre": {"$regex": pattern, "$options": "i"}}, {"apellido": {"$regex": pattern, "$options": "i"}}]
    people = await db.persons.find(query, {"_id": 1, "nombre": 1, "apellido": 1}).sort([("nombre", 1), ("apellido", 1)]).limit(limit).to_list(limit)
    found_ids = [str(item["_id"]) for item in people]
    if not found_ids:
        return {"items": [], "total": 0}
    accounts = await db.users.find({"person_id": {"$in": found_ids}, "is_active": {"$ne": False}}, {"_id": 0, "person_id": 1}).to_list(limit)
    account_person_ids = {item["person_id"] for item in accounts}
    lbs_docs = await db.mentor_qualifications.find(
        {"person_id": {"$in": found_ids}, "active": True, "can_teach_lbs": True, "front_group_id": None},
        {"_id": 0, "person_id": 1},
    ).to_list(limit)
    lbs_person_ids = {item["person_id"] for item in lbs_docs}
    can_see_phone = has_capability(current_user, PERSON_CONTACTS_READ)
    phones = {}
    if can_see_phone:
        contacts = await db.person_contacts.find(
            {"person_id": {"$in": found_ids}, "tipo": {"$in": ["telefono", "whatsapp"]}, "es_principal": True},
            {"_id": 0, "person_id": 1, "valor": 1},
        ).to_list(limit)
        phones = {item["person_id"]: item.get("valor") for item in contacts}
    assigned_counts: dict[str, int] = {}
    async for item in db.mentor_assignments.aggregate([
        {"$match": {"mentor_person_id": {"$in": found_ids}, "active": True}},
        {"$group": {"_id": "$mentor_person_id", "count": {"$sum": 1}}},
    ]):
        assigned_counts[item["_id"]] = item["count"]
    items = [{
        "person_id": str(person["_id"]),
        "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
        "phone": phones.get(str(person["_id"])),
        "lbs_qualified": str(person["_id"]) in lbs_person_ids,
        "assigned_count": assigned_counts.get(str(person["_id"]), 0),
    } for person in people if str(person["_id"]) in account_person_ids]
    return {"items": items, "total": len(items)}


async def ensure_mentorship_indexes() -> None:
    await db.mentor_badges.create_index("person_id", unique=True)
    await db.mentor_badges.create_index("active")
    await db.mentor_badge_history.create_index("history_id", unique=True)
    await db.mentor_badge_history.create_index([("person_id", 1), ("occurred_at", -1)])
