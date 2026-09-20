"""Bandeja de trabajo frontal; referencia dominios existentes sin duplicarlos."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from access_control import (
    CONSOLIDATION_ASSIGN, FRONT_GROUPS_VIEW, FRONT_GROUP_WORK_ASSIGN,
    has_capability, is_global_pastoral_authority,
)
from front_group_tree import descendant_group_ids, led_subtree_group_ids, load_group, readable_group_ids
from process_engine import serialize
from server import db, get_current_user


router = APIRouter(prefix="/api/front-group-work", tags=["front-group-work"])
SOURCE_TYPES = {"direct_task", "consolidation", "op72", "seven_weeks", "evangelism_target", "cell_followup", "process_stage_task"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class WorkCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    source_type: Literal["direct_task", "consolidation", "op72", "seven_weeks", "evangelism_target", "cell_followup", "process_stage_task"] = "direct_task"
    source_id: Optional[str] = None
    source_sub_id: Optional[str] = None
    assigned_group_id: str
    assigned_person_id: Optional[str] = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_at: Optional[datetime] = None
    reason: str = Field(min_length=2, max_length=1000)


class WorkDelegate(BaseModel):
    assigned_group_id: str
    assigned_person_id: Optional[str] = None
    reason: str = Field(min_length=2, max_length=1000)


class WorkStatusUpdate(BaseModel):
    status: Literal["accepted", "in_progress", "completed", "returned"]
    note: Optional[str] = Field(default=None, max_length=1200)


def require_read(current_user: dict = Depends(get_current_user)) -> dict:
    return current_user


def require_assign(current_user: dict = Depends(get_current_user)) -> dict:
    allowed = is_global_pastoral_authority(current_user) or any(has_capability(current_user, item) for item in (FRONT_GROUP_WORK_ASSIGN, CONSOLIDATION_ASSIGN))
    if not allowed:
        raise HTTPException(status_code=403, detail="Sin permiso para asignar trabajo frontal")
    return current_user


async def validate_person(person_id: str | None) -> None:
    if not person_id:
        return
    if not ObjectId.is_valid(person_id) or not await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Persona responsable no encontrada")


async def validate_source(source_type: str, source_id: str | None, source_sub_id: str | None = None) -> None:
    if source_type == "direct_task":
        return
    if not source_id:
        raise HTTPException(status_code=422, detail="El trabajo vinculado requiere source_id")
    queries = {
        "consolidation": (db.process_enrollments, {"enrollment_id": source_id, "process_key": "consolidation"}),
        "seven_weeks": (db.process_enrollments, {"enrollment_id": source_id, "process_key": "seven_weeks"}),
        "op72": (db.op72_records, {"op72_id": source_id}),
        "evangelism_target": (db.evangelism_targets, {"target_id": source_id}),
        "cell_followup": (db.cell_followups, {"followup_id": source_id}),
        "process_stage_task": (db.process_stage_progress, {"enrollment_id": source_id, "tasks.task_id": source_sub_id}),
    }
    collection, query = queries[source_type]
    if not await collection.find_one(query, {"_id": 1}):
        raise HTTPException(status_code=404, detail="El trabajo de origen no existe")


async def ensure_person_belongs(group_id: str, person_id: str | None, source_type: str) -> None:
    await validate_person(person_id)
    if not person_id:
        return
    member = await db.front_group_assignments.find_one({"front_group_id": group_id, "person_id": person_id, "active": True}, {"_id": 1})
    qualified_mentor = await db.mentor_qualifications.find_one({"front_group_id": {"$in": [group_id, None]}, "person_id": person_id, "active": True, "archived": {"$ne": True}}, {"_id": 1})
    process_responsible = source_type in {"consolidation", "seven_weeks", "process_stage_task"} and await db.users.find_one({"person_id": person_id, "is_active": {"$ne": False}, "rol": {"$in": ["pastor", "lider"]}}, {"_id": 1})
    if not member and not qualified_mentor and not process_responsible:
        raise HTTPException(status_code=409, detail="La Persona responsable no pertenece al Grupo ni es mentor autorizado")


async def can_assign_to_group(current_user: dict, group_id: str, source_type: str) -> bool:
    if is_global_pastoral_authority(current_user):
        return True
    if source_type == "consolidation" and has_capability(current_user, CONSOLIDATION_ASSIGN):
        return True
    if not has_capability(current_user, FRONT_GROUP_WORK_ASSIGN):
        return False
    allowed = await led_subtree_group_ids(db, current_user)
    return allowed is None or group_id in allowed


async def create_source_work_assignment(
    *, source_type: str, source_id: str | None, source_sub_id: str | None,
    title: str, description: str | None, assigned_group_id: str,
    assigned_person_id: str | None, priority: str, due_at: datetime | None,
    actor_user_id: str, reason: str,
) -> dict:
    await load_group(db, assigned_group_id)
    await ensure_person_belongs(assigned_group_id, assigned_person_id, source_type)
    await validate_source(source_type, source_id, source_sub_id)
    effective_source_id = source_id or str(uuid4())
    active_query = {"source_type": source_type, "source_id": effective_source_id, "source_sub_id": source_sub_id, "active": True}
    previous = await db.front_group_work_assignments.find_one(active_query, {"_id": 0})
    if previous and previous.get("assigned_group_id") == assigned_group_id and previous.get("assigned_person_id") == assigned_person_id:
        return serialize(previous)
    now = now_utc(); assignment_id = str(uuid4()); work_id = previous.get("work_id") if previous else str(uuid4())
    if previous:
        await db.front_group_work_assignments.update_one(
            {"assignment_id": previous["assignment_id"]},
            {"$set": {"active": False, "status": "delegated", "delegated_at": now, "delegated_by_user_id": actor_user_id, "delegation_reason": reason}},
        )
    document = {
        "_id": assignment_id, "assignment_id": assignment_id, "work_id": work_id,
        "root_assignment_id": previous.get("root_assignment_id", previous.get("assignment_id")) if previous else assignment_id,
        "parent_assignment_id": previous.get("assignment_id") if previous else None,
        "source_type": source_type, "source_id": effective_source_id, "source_sub_id": source_sub_id,
        "title": title, "description": description, "origin_group_id": previous.get("origin_group_id") if previous else assigned_group_id,
        "assigned_group_id": assigned_group_id, "assigned_person_id": assigned_person_id,
        "priority": priority, "due_at": due_at, "reason": reason,
        "status": "assigned", "active": True,
        "created_by_user_id": actor_user_id, "created_at": now, "updated_at": now,
    }
    await db.front_group_work_assignments.insert_one(document)
    return serialize(document)


async def enriched(item: dict) -> dict:
    result = serialize(item)
    group = await db.front_groups.find_one({"front_group_id": item["assigned_group_id"]}, {"_id": 0, "name": 1})
    result["assigned_group_name"] = (group or {}).get("name")
    if item.get("assigned_person_id") and ObjectId.is_valid(item["assigned_person_id"]):
        person = await db.persons.find_one({"_id": ObjectId(item["assigned_person_id"])}, {"_id": 0, "nombre": 1, "apellido": 1})
        result["assigned_person_name"] = " ".join(part for part in [(person or {}).get("nombre"), (person or {}).get("apellido")] if part) or None
    return result


@router.get("", response_model=dict)
async def list_work(group_id: Optional[str] = None, include_history: bool = Query(False), current_user: dict = Depends(require_read)):
    query = {} if include_history else {"active": True}
    if is_global_pastoral_authority(current_user):
        if group_id:
            query["assigned_group_id"] = {"$in": await descendant_group_ids(db, group_id)}
    elif has_capability(current_user, CONSOLIDATION_ASSIGN):
        query["$or"] = [{"source_type": "consolidation"}, {"assigned_person_id": current_user.get("person_id")}]
        if group_id:
            query["assigned_group_id"] = {"$in": await descendant_group_ids(db, group_id)}
    else:
        can_view_group = any(has_capability(current_user, item) for item in (FRONT_GROUPS_VIEW, FRONT_GROUP_WORK_ASSIGN))
        allowed = (await readable_group_ids(db, current_user) or set()) if can_view_group else set()
        if group_id:
            requested = set(await descendant_group_ids(db, group_id))
            allowed &= requested
        query["$or"] = [{"assigned_group_id": {"$in": list(allowed)}}, {"assigned_person_id": current_user.get("person_id")}]
    items = await db.front_group_work_assignments.find(query, {"_id": 0}).sort([("due_at", 1), ("created_at", -1)]).to_list(10000)
    return {"items": [await enriched(item) for item in items], "total": len(items)}


@router.post("", response_model=dict, status_code=201)
async def create_work(payload: WorkCreate, current_user: dict = Depends(require_assign)):
    if not await can_assign_to_group(current_user, payload.assigned_group_id, payload.source_type):
        raise HTTPException(status_code=403, detail="El Grupo destino está fuera de su rama autorizada")
    return await create_source_work_assignment(**payload.model_dump(), actor_user_id=current_user["user_id"])


@router.post("/{assignment_id}/delegate", response_model=dict, status_code=201)
async def delegate_work(assignment_id: str, payload: WorkDelegate, current_user: dict = Depends(require_assign)):
    current = await db.front_group_work_assignments.find_one({"assignment_id": assignment_id, "active": True}, {"_id": 0})
    if not current:
        raise HTTPException(status_code=404, detail="Asignación activa no encontrada")
    if not await can_assign_to_group(current_user, current["assigned_group_id"], current["source_type"]):
        raise HTTPException(status_code=403, detail="No puede delegar este trabajo")
    target = await load_group(db, payload.assigned_group_id)
    if payload.assigned_group_id != current["assigned_group_id"] and current["assigned_group_id"] not in (target.get("ancestor_group_ids") or []):
        raise HTTPException(status_code=409, detail="El trabajo solo puede bajar al mismo Grupo o a una subrama")
    return await create_source_work_assignment(
        source_type=current["source_type"], source_id=current["source_id"], source_sub_id=current.get("source_sub_id"),
        title=current["title"], description=current.get("description"), assigned_group_id=payload.assigned_group_id,
        assigned_person_id=payload.assigned_person_id, priority=current.get("priority", "normal"), due_at=current.get("due_at"),
        actor_user_id=current_user["user_id"], reason=payload.reason,
    )


@router.put("/{assignment_id}/status", response_model=dict)
async def update_work_status(assignment_id: str, payload: WorkStatusUpdate, current_user: dict = Depends(require_read)):
    item = await db.front_group_work_assignments.find_one({"assignment_id": assignment_id, "active": True}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Asignación activa no encontrada")
    led = await led_subtree_group_ids(db, current_user)
    allowed = is_global_pastoral_authority(current_user) or item.get("assigned_person_id") == current_user.get("person_id") or led is None or item["assigned_group_id"] in led
    if not allowed:
        raise HTTPException(status_code=403, detail="No puede actualizar este trabajo")
    now = now_utc(); fields = {"status": payload.status, "status_note": payload.note, "updated_at": now, "updated_by_user_id": current_user["user_id"]}
    if payload.status == "completed": fields.update({"active": False, "completed_at": now})
    await db.front_group_work_assignments.update_one({"assignment_id": assignment_id}, {"$set": fields})
    return await enriched(await db.front_group_work_assignments.find_one({"assignment_id": assignment_id}, {"_id": 0}))


async def ensure_front_group_work_indexes() -> None:
    await db.front_group_work_assignments.create_index("assignment_id", unique=True)
    await db.front_group_work_assignments.create_index("work_id")
    await db.front_group_work_assignments.create_index([("assigned_group_id", 1), ("active", 1), ("due_at", 1)])
    await db.front_group_work_assignments.create_index(
        [("source_type", 1), ("source_id", 1), ("source_sub_id", 1)], unique=True,
        partialFilterExpression={"active": True}, name="one_active_assignment_per_source",
    )