"""Grupos Frontales: estructura propia, equipo, liderazgo, mentores y scopes."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import (
    FRONT_GROUPS_MANAGE,
    MENTOR_QUALIFICATIONS_MANAGE,
    PROCESSES_READ,
    has_capability,
)
from server import db, get_current_user


router = APIRouter(prefix="/api/front-groups", tags=["front-groups"])


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items() if key != "_id"}
    return value


class LinkedStructure(BaseModel):
    type: Literal["network", "ministry", "door", "cell"]
    id: str
    label: Optional[str] = Field(default=None, max_length=160)


class FrontGroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=1200)
    status: Literal["active", "inactive"] = "active"
    linked_structures: list[LinkedStructure] = Field(default_factory=list, max_length=50)


class FrontGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=1200)
    status: Optional[Literal["active", "inactive"]] = None
    linked_structures: Optional[list[LinkedStructure]] = Field(default=None, max_length=50)


class MemberAssignment(BaseModel):
    person_id: str
    role: Literal["team", "mentor"] = "team"
    notes: Optional[str] = Field(default=None, max_length=600)


class LeaderAssignment(BaseModel):
    person_id: str
    reason: str = Field(min_length=2, max_length=600)


class MentorQualificationInput(BaseModel):
    front_group_id: Optional[str] = None
    can_teach_lbs: bool
    valid_until: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


def require_read(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("rol") != "pastor" and not has_capability(current_user, PROCESSES_READ):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar Grupos Frontales")
    return current_user


def require_manage(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("rol") != "pastor" and not has_capability(current_user, FRONT_GROUPS_MANAGE):
        raise HTTPException(status_code=403, detail="Sin permiso para administrar Grupos Frontales")
    return current_user


def require_qualification_manager(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("rol") != "pastor" and not has_capability(current_user, MENTOR_QUALIFICATIONS_MANAGE):
        raise HTTPException(status_code=403, detail="Sin permiso para calificar mentores LBS")
    return current_user


async def load_person(person_id: str) -> dict:
    if not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=400, detail="person_id inválido")
    person = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}}, {"_id": 1, "nombre": 1, "apellido": 1})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return person


async def group_in_scope(group_id: str, current_user: dict, leader_required: bool = False) -> bool:
    if current_user.get("rol") == "pastor":
        return True
    role_query = "leader" if leader_required else {"$in": ["leader", "team", "mentor"]}
    return bool(await db.front_group_assignments.find_one({
        "front_group_id": group_id,
        "person_id": current_user.get("person_id"),
        "role": role_query,
        "active": True,
    }, {"_id": 1}))


async def assert_group_scope(group_id: str, current_user: dict, leader_required: bool = False) -> dict:
    group = await db.front_groups.find_one({"front_group_id": group_id}, {"_id": 0})
    if not group:
        raise HTTPException(status_code=404, detail="Grupo Frontal no encontrado")
    if not await group_in_scope(group_id, current_user, leader_required):
        raise HTTPException(status_code=403, detail="Grupo Frontal fuera de su ámbito")
    return group


async def person_name(person_id: Optional[str]) -> Optional[str]:
    if not person_id or not ObjectId.is_valid(person_id):
        return None
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 0, "nombre": 1, "apellido": 1})
    return " ".join(part for part in [(person or {}).get("nombre"), (person or {}).get("apellido")] if part) or None


@router.get("", response_model=dict)
async def list_front_groups(current_user: dict = Depends(require_read)):
    query = {}
    if current_user.get("rol") != "pastor" and not has_capability(current_user, FRONT_GROUPS_MANAGE):
        group_ids = await db.front_group_assignments.distinct("front_group_id", {"person_id": current_user.get("person_id"), "active": True})
        query["front_group_id"] = {"$in": group_ids}
    groups = await db.front_groups.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    items = []
    for group in groups:
        group["primary_leader_name"] = await person_name(group.get("primary_leader_person_id"))
        group["team_count"] = await db.front_group_assignments.count_documents({"front_group_id": group["front_group_id"], "active": True})
        group["active_process_count"] = await db.process_enrollments.count_documents({"front_group_id": group["front_group_id"], "process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}})
        items.append(serialize(group))
    return {"items": items, "total": len(items)}


@router.post("", response_model=dict, status_code=201)
async def create_front_group(payload: FrontGroupCreate, current_user: dict = Depends(require_manage)):
    now = now_utc(); group_id = str(uuid4())
    document = {
        "_id": group_id,
        "front_group_id": group_id,
        **payload.model_dump(),
        "linked_structures": [item.model_dump() for item in payload.linked_structures],
        "primary_leader_person_id": None,
        "created_by_user_id": current_user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    await db.front_groups.insert_one(document)
    return serialize(document)


@router.get("/{group_id}", response_model=dict)
async def front_group_detail(group_id: str, current_user: dict = Depends(require_read)):
    group = await assert_group_scope(group_id, current_user)
    assignments = await db.front_group_assignments.find({"front_group_id": group_id}, {"_id": 0}).sort("started_at", -1).to_list(2000)
    for item in assignments:
        item["person_name"] = await person_name(item["person_id"])
    group["assignments"] = assignments
    group["stats"] = {
        "people_reached": len(await db.process_enrollments.distinct("person_id", {"front_group_id": group_id, "process_key": "consolidation"})),
        "active_processes": await db.process_enrollments.count_documents({"front_group_id": group_id, "process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}}),
        "members": await db.person_memberships.count_documents({"front_group_id": group_id, "status": "active"}),
        "retreat_completed": await db.process_enrollments.count_documents({"front_group_id": group_id, "retreat_completed_at": {"$exists": True}}),
        "leaders_promoted": await db.leadership_promotions.count_documents({"front_group_id": group_id, "decision": "approved"}),
    }
    return serialize(group)


@router.put("/{group_id}", response_model=dict)
async def update_front_group(group_id: str, payload: FrontGroupUpdate, current_user: dict = Depends(require_manage)):
    update = payload.model_dump(exclude_none=True)
    if "linked_structures" in update:
        update["linked_structures"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in payload.linked_structures]
    update.update({"updated_by_user_id": current_user["user_id"], "updated_at": now_utc()})
    result = await db.front_groups.update_one({"front_group_id": group_id}, {"$set": update})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Grupo Frontal no encontrado")
    return serialize(await db.front_groups.find_one({"front_group_id": group_id}, {"_id": 0}))


@router.post("/{group_id}/members", response_model=dict, status_code=201)
async def assign_member(group_id: str, payload: MemberAssignment, current_user: dict = Depends(require_manage)):
    await assert_group_scope(group_id, current_user)
    await load_person(payload.person_id)
    now = now_utc()
    existing = await db.front_group_assignments.find_one({"front_group_id": group_id, "person_id": payload.person_id, "role": payload.role, "active": True}, {"_id": 0})
    if existing:
        return serialize(existing)
    assignment_id = str(uuid4())
    document = {"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id, **payload.model_dump(), "active": True, "started_at": now, "ended_at": None, "assigned_by_user_id": current_user["user_id"], "created_at": now}
    await db.front_group_assignments.insert_one(document)
    return serialize(document)


@router.post("/{group_id}/leader", response_model=dict)
async def assign_primary_leader(group_id: str, payload: LeaderAssignment, current_user: dict = Depends(require_manage)):
    await assert_group_scope(group_id, current_user)
    await load_person(payload.person_id)
    if not await db.users.find_one({"person_id": payload.person_id, "is_active": {"$ne": False}}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="El líder principal necesita una cuenta activa en Plataforma 360")
    now = now_utc()
    await db.front_group_assignments.update_many({"front_group_id": group_id, "role": "leader", "active": True}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "end_reason": payload.reason}})
    assignment_id = str(uuid4())
    assignment = {"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id, "person_id": payload.person_id, "role": "leader", "active": True, "started_at": now, "ended_at": None, "notes": payload.reason, "assigned_by_user_id": current_user["user_id"], "created_at": now}
    await db.front_group_assignments.insert_one(assignment)
    await db.front_groups.update_one({"front_group_id": group_id}, {"$set": {"primary_leader_person_id": payload.person_id, "updated_at": now, "updated_by_user_id": current_user["user_id"]}})
    return serialize(assignment)


@router.get("/{group_id}/qualified-mentors", response_model=dict)
async def qualified_mentors(group_id: str, current_user: dict = Depends(require_read)):
    await assert_group_scope(group_id, current_user)
    now = now_utc()
    qualifications = await db.mentor_qualifications.find({
        "active": True,
        "can_teach_lbs": True,
        "$or": [{"front_group_id": group_id}, {"front_group_id": None}],
        "$and": [{"$or": [{"valid_until": None}, {"valid_until": {"$gte": now}}]}],
    }, {"_id": 0}).to_list(2000)
    for item in qualifications:
        item["person_name"] = await person_name(item["person_id"])
    return {"items": serialize(qualifications), "total": len(qualifications)}


@router.put("/mentors/{person_id}/qualification", response_model=dict)
async def set_mentor_qualification(person_id: str, payload: MentorQualificationInput, current_user: dict = Depends(require_qualification_manager)):
    await load_person(person_id)
    if payload.front_group_id:
        await assert_group_scope(payload.front_group_id, current_user)
    now = now_utc()
    query = {"person_id": person_id, "front_group_id": payload.front_group_id}
    fields = {**payload.model_dump(), "person_id": person_id, "active": True, "approved_by_user_id": current_user["user_id"], "approved_at": now, "updated_at": now}
    await db.mentor_qualifications.update_one(query, {"$set": fields, "$setOnInsert": {"qualification_id": str(uuid4()), "created_at": now}}, upsert=True)
    return serialize(await db.mentor_qualifications.find_one(query, {"_id": 0}))


async def ensure_front_group_indexes() -> None:
    await db.front_groups.create_index("front_group_id", unique=True)
    await db.front_groups.create_index([("status", 1), ("name", 1)])
    await db.front_group_assignments.create_index("assignment_id", unique=True)
    await db.front_group_assignments.create_index([("front_group_id", 1), ("person_id", 1), ("role", 1), ("active", 1)])
    await db.mentor_qualifications.create_index([("person_id", 1), ("front_group_id", 1)], unique=True)