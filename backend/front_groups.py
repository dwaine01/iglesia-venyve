"""Grupos Frontales: árbol recursivo, membresías canónicas y scope jerárquico."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from access_control import (
    FRONT_GROUPS_MANAGE, FRONT_GROUPS_VIEW, MENTOR_QUALIFICATIONS_MANAGE,
    has_capability, is_global_pastoral_authority,
)
from front_group_tree import (
    build_tree, group_in_scope as tree_group_in_scope, lineage_for_parent,
    load_group, manageable_group_ids, readable_group_ids, move_subtree,
)
from server import db, get_current_user


router = APIRouter(prefix="/api/front-groups", tags=["front-groups"])


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, ObjectId): return str(value)
    if isinstance(value, list): return [serialize(item) for item in value]
    if isinstance(value, dict): return {key: serialize(item) for key, item in value.items() if key != "_id"}
    return value


class LinkedStructure(BaseModel):
    type: Literal["network", "ministry", "door", "cell"]
    id: str
    label: Optional[str] = Field(default=None, max_length=160)


class FrontGroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=1200)
    parent_group_id: Optional[str] = None
    status: Literal["active", "inactive"] = "active"
    routing_enabled: bool = True
    rotation_order: int = Field(default=0, ge=0, le=100000)
    linked_structures: list[LinkedStructure] = Field(default_factory=list, max_length=50)
    primary_leader_person_id: Optional[str] = None
    leadership_reason: Optional[str] = Field(default=None, max_length=600)


class FrontGroupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=1200)
    status: Optional[Literal["active", "inactive"]] = None
    routing_enabled: Optional[bool] = None
    rotation_order: Optional[int] = Field(default=None, ge=0, le=100000)
    linked_structures: Optional[list[LinkedStructure]] = Field(default=None, max_length=50)


class FrontGroupMove(BaseModel):
    parent_group_id: Optional[str] = None
    reason: str = Field(min_length=3, max_length=600)


class MemberAssignment(BaseModel):
    person_id: str
    role: Literal["member", "team", "mentor"] = "member"
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
    if not is_global_pastoral_authority(current_user) and not any(has_capability(current_user, item) for item in (FRONT_GROUPS_VIEW, FRONT_GROUPS_MANAGE)):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar Grupos Frontales")
    return current_user


def require_manage(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, FRONT_GROUPS_MANAGE):
        raise HTTPException(status_code=403, detail="Sin permiso para administrar Grupos Frontales")
    return current_user


def require_qualification_manager(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, MENTOR_QUALIFICATIONS_MANAGE):
        raise HTTPException(status_code=403, detail="Sin permiso para calificar mentores LBS")
    return current_user


async def audit(group_id: str, current_user: dict, action: str, detail: dict | None = None) -> None:
    event_id = str(uuid4())
    await db.front_group_audit_events.insert_one({
        "_id": event_id, "event_id": event_id, "front_group_id": group_id,
        "action": action, "detail": serialize(detail or {}),
        "actor_user_id": current_user["user_id"], "actor_person_id": current_user.get("person_id"),
        "occurred_at": now_utc(),
    })


async def load_person(person_id: str) -> dict:
    if not ObjectId.is_valid(person_id): raise HTTPException(status_code=400, detail="person_id inválido")
    person = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}}, {"_id": 1, "nombre": 1, "apellido": 1})
    if not person: raise HTTPException(status_code=404, detail="Persona no encontrada")
    return person


async def group_in_scope(group_id: str, current_user: dict, leader_required: bool = False) -> bool:
    return await tree_group_in_scope(db, group_id, current_user, leader_required)


async def assert_group_scope(group_id: str, current_user: dict, leader_required: bool = False) -> dict:
    group = await load_group(db, group_id)
    if not await group_in_scope(group_id, current_user, leader_required):
        raise HTTPException(status_code=403, detail="Grupo Frontal fuera de su ámbito")
    return group


async def person_name(person_id: Optional[str]) -> Optional[str]:
    if not person_id or not ObjectId.is_valid(person_id): return None
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 0, "nombre": 1, "apellido": 1})
    return " ".join(part for part in [(person or {}).get("nombre"), (person or {}).get("apellido")] if part) or None


async def group_summary(group: dict, current_user: dict) -> dict:
    item = serialize(group)
    item["primary_leader_name"] = await person_name(group.get("primary_leader_person_id"))
    item["team_count"] = await db.front_group_assignments.count_documents({"front_group_id": group["front_group_id"], "active": True})
    item["active_process_count"] = await db.process_enrollments.count_documents({"front_group_id": group["front_group_id"], "process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}})
    manageable = await manageable_group_ids(db, current_user)
    item["permissions"] = {"manage": manageable is None or group["front_group_id"] in manageable}
    return item


@router.get("", response_model=dict)
async def list_front_groups(include_archived: bool = Query(False), current_user: dict = Depends(require_read)):
    if include_archived and not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Solo la autoridad pastoral puede consultar grupos archivados")
    query = {} if include_archived else {"status": {"$ne": "archived"}}
    allowed = await readable_group_ids(db, current_user)
    if allowed is not None: query["front_group_id"] = {"$in": list(allowed)}
    groups = await db.front_groups.find(query, {"_id": 0}).sort([("depth", 1), ("rotation_order", 1), ("name", 1)]).to_list(10000)
    items = [await group_summary(group, current_user) for group in groups]
    return {"items": items, "total": len(items)}


@router.get("/tree", response_model=dict)
async def front_group_tree(current_user: dict = Depends(require_read)):
    allowed = await readable_group_ids(db, current_user)
    query = {"status": {"$ne": "archived"}}
    if allowed is not None: query["front_group_id"] = {"$in": list(allowed)}
    groups = await db.front_groups.find(query, {"_id": 0}).to_list(10000)
    items = [await group_summary(group, current_user) for group in groups]
    return {"items": build_tree(items), "total": len(items)}


@router.post("", response_model=dict, status_code=201)
async def create_front_group(payload: FrontGroupCreate, current_user: dict = Depends(require_manage)):
    if not payload.parent_group_id and not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Solo la autoridad pastoral puede crear un Grupo Frontal raíz")
    if payload.parent_group_id:
        await assert_group_scope(payload.parent_group_id, current_user, leader_required=True)
    if payload.primary_leader_person_id:
        await load_person(payload.primary_leader_person_id)
        if not await db.users.find_one({"person_id": payload.primary_leader_person_id, "is_active": {"$ne": False}}, {"_id": 1}):
            raise HTTPException(status_code=409, detail="El líder principal necesita una cuenta activa en Plataforma 360")
    now = now_utc(); group_id = str(uuid4()); lineage = await lineage_for_parent(db, group_id, payload.parent_group_id)
    document = {
        "_id": group_id, "front_group_id": group_id,
        **payload.model_dump(exclude={"parent_group_id", "linked_structures", "primary_leader_person_id", "leadership_reason"}), **lineage,
        "linked_structures": [item.model_dump() for item in payload.linked_structures],
        "primary_leader_person_id": payload.primary_leader_person_id, "tree_version": 1,
        "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.front_groups.insert_one(document)
    if payload.primary_leader_person_id:
        assignment_id = str(uuid4())
        await db.front_group_assignments.insert_one({
            "_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id,
            "person_id": payload.primary_leader_person_id, "role": "leader", "active": True,
            "started_at": now, "ended_at": None, "notes": payload.leadership_reason or "Asignación al crear la rama",
            "assigned_by_user_id": current_user["user_id"], "created_at": now,
        })
    await audit(group_id, current_user, "group_created", {"parent_group_id": payload.parent_group_id})
    return serialize(document)


@router.get("/{group_id}", response_model=dict)
async def front_group_detail(group_id: str, current_user: dict = Depends(require_read)):
    group = await assert_group_scope(group_id, current_user)
    assignments = await db.front_group_assignments.find({"front_group_id": group_id}, {"_id": 0}).sort("started_at", -1).to_list(2000)
    for item in assignments: item["person_name"] = await person_name(item["person_id"])
    child_count = await db.front_groups.count_documents({"parent_group_id": group_id, "status": {"$ne": "archived"}})
    group = await group_summary(group, current_user)
    group["assignments"] = serialize(assignments)
    group["stats"] = {
        "people_reached": len(await db.process_enrollments.distinct("person_id", {"front_group_id": group_id, "process_key": "consolidation"})),
        "active_processes": group["active_process_count"], "members": group["team_count"],
        "children": child_count,
        "retreat_completed": await db.process_enrollments.count_documents({"front_group_id": group_id, "retreat_completed_at": {"$exists": True}}),
        "leaders_promoted": await db.leadership_promotions.count_documents({"front_group_id": group_id, "decision": "approved", "archived": {"$ne": True}}),
    }
    return group


@router.put("/{group_id}", response_model=dict)
async def update_front_group(group_id: str, payload: FrontGroupUpdate, current_user: dict = Depends(require_manage)):
    await assert_group_scope(group_id, current_user, leader_required=True)
    update = payload.model_dump(exclude_none=True)
    if "linked_structures" in update:
        update["linked_structures"] = [item.model_dump() for item in payload.linked_structures]
    update.update({"updated_by_user_id": current_user["user_id"], "updated_at": now_utc()})
    await db.front_groups.update_one({"front_group_id": group_id, "status": {"$ne": "archived"}}, {"$set": update})
    await audit(group_id, current_user, "group_updated", {"fields": sorted(update.keys() - {"updated_at", "updated_by_user_id"})})
    return serialize(await load_group(db, group_id))


@router.post("/{group_id}/move", response_model=dict)
async def move_front_group(group_id: str, payload: FrontGroupMove, current_user: dict = Depends(require_manage)):
    await assert_group_scope(group_id, current_user, leader_required=True)
    if payload.parent_group_id:
        await assert_group_scope(payload.parent_group_id, current_user, leader_required=True)
    previous = await load_group(db, group_id)
    moved = await move_subtree(db, group_id, payload.parent_group_id, current_user["user_id"])
    await audit(group_id, current_user, "group_moved", {"from": previous.get("parent_group_id"), "to": payload.parent_group_id, "reason": payload.reason})
    return serialize(moved)


@router.post("/{group_id}/members", response_model=dict, status_code=201)
async def assign_member(group_id: str, payload: MemberAssignment, current_user: dict = Depends(require_manage)):
    await assert_group_scope(group_id, current_user, leader_required=True); await load_person(payload.person_id)
    now = now_utc(); role = "member" if payload.role == "team" else payload.role
    existing = await db.front_group_assignments.find_one({"front_group_id": group_id, "person_id": payload.person_id, "role": role, "active": True}, {"_id": 0})
    if existing: return serialize(existing)
    assignment_id = str(uuid4())
    document = {"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id, "person_id": payload.person_id, "role": role, "notes": payload.notes, "active": True, "started_at": now, "ended_at": None, "assigned_by_user_id": current_user["user_id"], "created_at": now}
    await db.front_group_assignments.insert_one(document)
    await audit(group_id, current_user, "member_assigned", {"assignment_id": assignment_id, "person_id": payload.person_id, "role": role})
    return serialize(document)


@router.post("/{group_id}/leader", response_model=dict)
async def assign_primary_leader(group_id: str, payload: LeaderAssignment, current_user: dict = Depends(require_manage)):
    await assert_group_scope(group_id, current_user, leader_required=True); await load_person(payload.person_id)
    if not await db.users.find_one({"person_id": payload.person_id, "is_active": {"$ne": False}}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="El líder principal necesita una cuenta activa en Plataforma 360")
    now = now_utc()
    await db.front_group_assignments.update_many({"front_group_id": group_id, "role": "leader", "active": True}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "end_reason": payload.reason}})
    assignment_id = str(uuid4())
    assignment = {"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id, "person_id": payload.person_id, "role": "leader", "active": True, "started_at": now, "ended_at": None, "notes": payload.reason, "assigned_by_user_id": current_user["user_id"], "created_at": now}
    await db.front_group_assignments.insert_one(assignment)
    await db.front_groups.update_one({"front_group_id": group_id}, {"$set": {"primary_leader_person_id": payload.person_id, "updated_at": now, "updated_by_user_id": current_user["user_id"]}})
    await audit(group_id, current_user, "primary_leader_assigned", {"assignment_id": assignment_id, "person_id": payload.person_id, "reason": payload.reason})
    return serialize(assignment)


@router.get("/{group_id}/qualified-mentors", response_model=dict)
async def qualified_mentors(group_id: str, current_user: dict = Depends(require_read)):
    await assert_group_scope(group_id, current_user); now = now_utc()
    qualifications = await db.mentor_qualifications.find({"active": True, "archived": {"$ne": True}, "can_teach_lbs": True, "$or": [{"front_group_id": group_id}, {"front_group_id": None}], "$and": [{"$or": [{"valid_until": None}, {"valid_until": {"$gte": now}}]}]}, {"_id": 0}).to_list(2000)
    for item in qualifications: item["person_name"] = await person_name(item["person_id"])
    return {"items": serialize(qualifications), "total": len(qualifications)}


@router.put("/mentors/{person_id}/qualification", response_model=dict)
async def set_mentor_qualification(person_id: str, payload: MentorQualificationInput, current_user: dict = Depends(require_qualification_manager)):
    await load_person(person_id)
    if payload.front_group_id: await assert_group_scope(payload.front_group_id, current_user, leader_required=True)
    now = now_utc(); query = {"person_id": person_id, "front_group_id": payload.front_group_id}
    fields = {**payload.model_dump(), "person_id": person_id, "active": True, "archived": False, "approved_by_user_id": current_user["user_id"], "approved_at": now, "updated_at": now}
    await db.mentor_qualifications.update_one(query, {"$set": fields, "$setOnInsert": {"qualification_id": str(uuid4()), "created_at": now}}, upsert=True)
    return serialize(await db.mentor_qualifications.find_one(query, {"_id": 0}))


async def ensure_front_group_indexes() -> None:
    await db.front_groups.create_index("front_group_id", unique=True)
    await db.front_groups.create_index([("status", 1), ("parent_group_id", 1), ("rotation_order", 1), ("name", 1)])
    await db.front_groups.create_index([("root_group_id", 1), ("depth", 1)])
    await db.front_groups.create_index("ancestor_group_ids")
    await db.front_group_assignments.create_index("assignment_id", unique=True)
    await db.front_group_assignments.create_index([("front_group_id", 1), ("person_id", 1), ("role", 1), ("active", 1)])
    await db.mentor_qualifications.create_index([("person_id", 1), ("front_group_id", 1)], unique=True)
    await db.front_group_audit_events.create_index("event_id", unique=True)
    await db.front_group_audit_events.create_index([("front_group_id", 1), ("occurred_at", -1)])