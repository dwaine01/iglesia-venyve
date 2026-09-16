"""API completa del Mega-Bloque C — Sistema Celular."""
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from access_control import (
    CELLULAR_ATTENDANCE,
    CELLULAR_MANAGE,
    CELLULAR_MULTIPLY,
    CELLULAR_NEEDS,
    CELLULAR_READ,
    CELLULAR_SENSITIVE_READ,
    CELLULAR_WRITE,
    has_capability,
)
from cellular_engine import (
    can_access_cell,
    cellular_scope,
    current_cell_metrics,
    evaluate_multiplication,
    migrate_cellular,
    now_utc,
    person_summary,
    ready_inbox,
    record_cell_event,
    serialize,
    snapshot_cell_health,
    suggested_door,
)
from server import db, get_current_user

router = APIRouter(prefix="/api/cellular", tags=["cellular"])
PUBLIC_MEETING_FIELDS = {"meeting_id", "cell_id", "scheduled_at", "topic", "status"}
SENSITIVE_HEALTH_FIELDS = {"open_needs", "open_followups", "conversions", "visitors", "retention"}


class ItemList(BaseModel):
    items: list[dict]
    total: int


def sanitize_meeting(meeting: dict, include_sensitive: bool) -> dict:
    serialized = serialize(meeting)
    return serialized if include_sensitive else {key: value for key, value in serialized.items() if key in PUBLIC_MEETING_FIELDS}


def sanitize_health(item: dict, include_sensitive: bool) -> dict:
    serialized = serialize(item)
    return serialized if include_sensitive else {key: value for key, value in serialized.items() if key not in SENSITIVE_HEALTH_FIELDS}


class NetworkCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    campus_id: Optional[str] = Field(default=None, max_length=100)
    status: Literal["active", "archived"] = "active"


class NetworkAssignment(BaseModel):
    person_id: str
    role: Literal["general_coordinator", "network_director", "supervisor"]


class CellCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=140)
    code: str = Field(..., min_length=2, max_length=30)
    network_id: str
    campus_id: Optional[str] = Field(default=None, max_length=100)
    address: str = Field(..., min_length=3, max_length=500)
    meeting_day: str = Field(..., min_length=2, max_length=30)
    meeting_time: str = Field(..., min_length=4, max_length=10)
    capacity: int = Field(default=15, ge=1, le=500)
    opened_at: date
    mother_cell_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    status: Literal["planned", "active", "paused", "closed"] = "active"


class CellUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=140)
    network_id: Optional[str] = None
    campus_id: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = Field(default=None, max_length=500)
    meeting_day: Optional[str] = Field(default=None, max_length=30)
    meeting_time: Optional[str] = Field(default=None, max_length=10)
    capacity: Optional[int] = Field(default=None, ge=1, le=500)
    notes: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[Literal["planned", "active", "paused", "closed"]] = None


class CellRoleCreate(BaseModel):
    person_id: str
    role: Literal["cell_leader", "assistant", "host", "intercessor"]


class MembershipCreate(BaseModel):
    person_id: str
    membership_type: Literal["primary", "service"] = "primary"
    role: Literal["member", "visitor", "leader", "assistant", "host", "intercessor"] = "member"
    joined_at: date = Field(default_factory=date.today)
    source: str = Field(default="manual", max_length=60)


class TransferCreate(BaseModel):
    person_id: str
    target_cell_id: str
    reason: str = Field(..., min_length=3, max_length=500)
    transferred_at: date = Field(default_factory=date.today)


class ReadyAssignment(BaseModel):
    person_id: str
    cell_id: str
    responsible_person_id: str
    first_followup_at: datetime
    first_followup_action: str = Field(..., min_length=3, max_length=500)


class MeetingCreate(BaseModel):
    scheduled_at: datetime
    host_person_id: Optional[str] = None
    leader_person_id: str
    topic: str = Field(..., min_length=2, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=3000)
    tasks: list[str] = Field(default_factory=list, max_length=30)


class MeetingTaskUpdate(BaseModel):
    task_id: str
    completed: bool


class MeetingTasksBulk(BaseModel):
    entries: list[MeetingTaskUpdate] = Field(default_factory=list, max_length=30)


class AttendanceEntry(BaseModel):
    person_id: str
    status: Literal["present", "absent", "excused"]
    is_visitor: bool = False
    is_new: bool = False


class AttendanceBulk(BaseModel):
    entries: list[AttendanceEntry] = Field(..., min_length=1, max_length=500)
    conversion_person_ids: list[str] = Field(default_factory=list, max_length=100)
    petitions: list[str] = Field(default_factory=list, max_length=100)
    results: Optional[str] = Field(default=None, max_length=3000)
    complete_meeting: bool = True

    @model_validator(mode="after")
    def unique_people(self):
        person_ids = [item.person_id for item in self.entries]
        if len(person_ids) != len(set(person_ids)):
            raise ValueError("No repita una Persona en la misma asistencia")
        return self


class NeedCreate(BaseModel):
    cell_id: str
    meeting_id: Optional[str] = None
    person_id: Optional[str] = None
    family_person_id: Optional[str] = None
    need_type: Literal["illness", "urgent_prayer", "crisis", "new_believer", "absent", "family_need", "ready_for_discipleship", "special_event", "first_visit", "other"]
    description: str = Field(..., min_length=3, max_length=3000)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    responsible_person_id: Optional[str] = None
    next_action: Optional[str] = Field(default=None, max_length=500)
    assigned_door_key: Optional[str] = None


class NeedUpdate(BaseModel):
    priority: Optional[Literal["low", "medium", "high", "urgent"]] = None
    status: Optional[Literal["open", "assigned", "in_progress", "resolved", "closed"]] = None
    responsible_person_id: Optional[str] = None
    next_action: Optional[str] = Field(default=None, max_length=500)
    assigned_door_key: Optional[str] = None
    resolution: Optional[str] = Field(default=None, max_length=2000)


class FollowupCreate(BaseModel):
    cell_id: str
    person_id: str
    need_id: Optional[str] = None
    followup_type: Literal["call", "visit", "prayer", "pastoral_care", "task", "followup", "door_need"]
    responsible_person_id: str
    due_at: datetime
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    next_action: str = Field(..., min_length=2, max_length=500)


class FollowupUpdate(BaseModel):
    status: Literal["open", "in_progress", "completed", "cancelled"]
    next_action: Optional[str] = Field(default=None, max_length=500)
    due_at: Optional[datetime] = None
    result: Optional[str] = Field(default=None, max_length=2000)


class MultiplicationRuleUpdate(BaseModel):
    min_active_members: Optional[int] = Field(default=None, ge=2, le=200)
    target_members: Optional[int] = Field(default=None, ge=2, le=300)
    min_stable_meetings: Optional[int] = Field(default=None, ge=1, le=100)
    min_average_attendance: Optional[int] = Field(default=None, ge=1, le=300)
    requires_leader_in_training: Optional[bool] = None
    requires_new_host: Optional[bool] = None
    enabled: Optional[bool] = None


class MultiplicationAction(BaseModel):
    action: Literal["under_review", "postpone", "approve"]
    reason: Optional[str] = Field(default=None, max_length=1000)
    daughter_cell: Optional[CellCreate] = None
    daughter_leader_person_id: Optional[str] = None
    transferred_person_ids: list[str] = Field(default_factory=list, max_length=100)


def require_capability(capability: str):
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if not has_capability(current_user, capability):
            raise HTTPException(status_code=403, detail="Sin permiso para esta operación celular")
        return current_user
    return dependency


require_read = require_capability(CELLULAR_READ)
require_write = require_capability(CELLULAR_WRITE)
require_manage = require_capability(CELLULAR_MANAGE)
require_attendance = require_capability(CELLULAR_ATTENDANCE)
require_needs = require_capability(CELLULAR_NEEDS)
require_sensitive_read = require_capability(CELLULAR_SENSITIVE_READ)
require_multiply = require_capability(CELLULAR_MULTIPLY)


async def ensure_person(person_id: str) -> None:
    if not ObjectId.is_valid(person_id) or not await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Persona canónica no encontrada")


async def ensure_staff(person_id: str) -> None:
    await ensure_person(person_id)
    if not await db.users.find_one({"person_id": person_id, "is_active": {"$ne": False}, "rol": {"$in": ["pastor", "lider"]}}, {"_id": 1}):
        raise HTTPException(status_code=400, detail="La función requiere una cuenta pastor/líder activa")


async def ensure_cell_access(cell_id: str, current_user: dict, write: bool = False) -> dict:
    cell = await db.cells.find_one({"cell_id": cell_id}, {"_id": 0})
    if not cell:
        raise HTTPException(status_code=404, detail="Célula no encontrada")
    if not await can_access_cell(db, current_user, cell_id, write):
        raise HTTPException(status_code=403, detail="Célula fuera de su alcance")
    return cell


async def network_manageable(network_id: str, current_user: dict) -> bool:
    scope = await cellular_scope(db, current_user)
    if scope["global"]:
        return True
    return network_id in scope["network_ids"] and bool({"network_director", "supervisor"}.intersection(scope["roles"]))


async def ensure_network_access(network_id: str, current_user: dict) -> dict:
    network = await db.cell_networks.find_one({"network_id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Red no encontrada")
    if not await network_manageable(network_id, current_user):
        raise HTTPException(status_code=403, detail="Fuera del alcance de gestión de red")
    return network


async def enrich_cell(cell: dict, include_sensitive_metrics: bool = True) -> dict:
    metrics = await current_cell_metrics(db, cell["cell_id"])
    if not include_sensitive_metrics:
        metrics = {key: value for key, value in metrics.items() if key not in SENSITIVE_HEALTH_FIELDS}
    roles = await db.cell_role_assignments.find({"cell_id": cell["cell_id"], "active": True}, {"_id": 0}).to_list(20)
    role_items = []
    for item in roles:
        role_items.append({**serialize(item), "person": await person_summary(db, item["person_id"])})
    network = await db.cell_networks.find_one({"network_id": cell["network_id"]}, {"_id": 0, "name": 1})
    return {**serialize(cell), "network_name": network.get("name") if network else None, "metrics": metrics, "roles": role_items}


@router.get("/catalog", response_model=dict)
async def cellular_catalog(current_user: dict = Depends(require_read)):
    scope = await cellular_scope(db, current_user)
    network_query = {} if scope["global"] else {"network_id": {"$in": scope["network_ids"]}}
    if not scope["global"] and not scope["network_ids"]:
        network_ids = await db.cells.distinct("network_id", {"cell_id": {"$in": scope["cell_ids"]}})
        network_query = {"network_id": {"$in": network_ids}}
    cell_query = {} if scope["global"] else {"cell_id": {"$in": scope["cell_ids"]}}
    networks = await db.cell_networks.find(network_query, {"_id": 0, "network_id": 1, "name": 1, "status": 1}).sort("name", 1).to_list(1000)
    cells = await db.cells.find(cell_query, {"_id": 0, "cell_id": 1, "network_id": 1, "name": 1, "code": 1, "status": 1}).sort("name", 1).to_list(10000)
    if scope["global"]:
        person_ids = [str(item["_id"]) async for item in db.persons.find({}, {"_id": 1})]
    else:
        from process_engine import access_person_ids
        person_ids = sorted(await access_person_ids(db, current_user) or set())
    people = []
    for person_id in person_ids[:5000]:
        summary = await person_summary(db, person_id)
        if summary: people.append(summary)
    staff_query = {"is_active": {"$ne": False}, "rol": {"$in": ["pastor", "lider"]}, "person_id": {"$in": person_ids}}
    staff_docs = await db.users.find(staff_query, {"_id": 0, "person_id": 1, "nombre": 1, "rol": 1}).sort("nombre", 1).to_list(1000)
    staff = [{"person_id": item["person_id"], "name": item["nombre"], "role": item["rol"], "profile_path": f"/personas/{item['person_id']}"} for item in staff_docs]
    return {"networks": serialize(networks), "cells": serialize(cells), "people": people, "staff": staff, "scope": scope}


@router.get("/networks", response_model=ItemList)
async def list_networks(current_user: dict = Depends(require_read)):
    scope = await cellular_scope(db, current_user)
    query = {} if scope["global"] else {"network_id": {"$in": scope["network_ids"]}}
    if not scope["global"] and not scope["network_ids"]:
        cell_networks = await db.cells.distinct("network_id", {"cell_id": {"$in": scope["cell_ids"]}})
        query = {"network_id": {"$in": cell_networks}}
    docs = await db.cell_networks.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    items = []
    for doc in docs:
        item = serialize(doc)
        item["cell_count"] = await db.cells.count_documents({"network_id": doc["network_id"], "status": {"$ne": "closed"}})
        item["member_count"] = await db.cell_memberships.count_documents({"network_id": doc["network_id"], "active": True, "membership_type": "primary"})
        assignments = await db.cell_network_assignments.find({"network_id": doc["network_id"], "active": True}, {"_id": 0}).to_list(100)
        item["assignments"] = [{**serialize(assignment), "person": await person_summary(db, assignment["person_id"])} for assignment in assignments]
        items.append(item)
    return {"items": items, "total": len(items)}


@router.post("/networks", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_network(payload: NetworkCreate, current_user: dict = Depends(require_manage)):
    network_id = str(uuid4()); now = now_utc()
    doc = {"_id": network_id, "network_id": network_id, "network_key": None, **payload.model_dump(), "source": "manual", "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.cell_networks.insert_one(doc)
    return serialize(doc)


@router.put("/networks/{network_id}", response_model=dict)
async def update_network(network_id: str, payload: NetworkCreate, current_user: dict = Depends(require_manage)):
    await ensure_network_access(network_id, current_user)
    result = await db.cell_networks.update_one({"network_id": network_id}, {"$set": {**payload.model_dump(), "updated_at": now_utc()}})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Red no encontrada")
    return serialize(await db.cell_networks.find_one({"network_id": network_id}, {"_id": 0}))


@router.post("/networks/{network_id}/assignments", status_code=status.HTTP_201_CREATED, response_model=dict)
async def assign_network_role(network_id: str, payload: NetworkAssignment, current_user: dict = Depends(require_manage)):
    await ensure_network_access(network_id, current_user)
    await ensure_staff(payload.person_id); now = now_utc(); assignment_id = str(uuid4())
    existing = await db.cell_network_assignments.find_one({"network_id": network_id, "person_id": payload.person_id, "role": payload.role, "active": True}, {"_id": 0})
    if existing: return serialize(existing)
    if payload.role in {"general_coordinator", "network_director"}:
        await db.cell_network_assignments.update_many({"network_id": network_id, "role": payload.role, "active": True}, {"$set": {"active": False, "ended_at": now}})
    doc = {"_id": assignment_id, "assignment_id": assignment_id, "network_id": network_id, **payload.model_dump(), "active": True, "started_at": now, "created_by_user_id": current_user["user_id"]}
    await db.cell_network_assignments.insert_one(doc); return serialize(doc)


@router.get("/cells", response_model=ItemList)
async def list_cells(network_id: Optional[str] = None, status_filter: Optional[str] = None, current_user: dict = Depends(require_read)):
    scope = await cellular_scope(db, current_user); query = {}
    if not scope["global"]: query["cell_id"] = {"$in": scope["cell_ids"]}
    if network_id: query["network_id"] = network_id
    if status_filter: query["status"] = status_filter
    docs = await db.cells.find(query, {"_id": 0}).sort("name", 1).to_list(10000)
    include_sensitive = has_capability(current_user, CELLULAR_SENSITIVE_READ)
    return {"items": [await enrich_cell(doc, include_sensitive) for doc in docs], "total": len(docs)}


@router.post("/cells", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_cell(payload: CellCreate, current_user: dict = Depends(require_write)):
    if not await network_manageable(payload.network_id, current_user): raise HTTPException(status_code=403, detail="Sin alcance para crear células en esta red")
    if not await db.cell_networks.find_one({"network_id": payload.network_id, "status": "active"}): raise HTTPException(status_code=400, detail="Red no disponible")
    if payload.mother_cell_id and not await db.cells.find_one({"cell_id": payload.mother_cell_id}): raise HTTPException(status_code=400, detail="Célula madre no encontrada")
    cell_id = str(uuid4()); now = now_utc(); code = payload.code.strip().upper()
    if await db.cells.find_one({"code": code}): raise HTTPException(status_code=409, detail="Código de célula ya existe")
    doc = {"_id": cell_id, "cell_id": cell_id, **payload.model_dump(), "opened_at": payload.opened_at.isoformat(), "code": code, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.cells.insert_one(doc); await record_cell_event(db, cell_id, current_user["user_id"], "cell_created", "Célula creada", payload.name)
    return await enrich_cell({key: value for key, value in doc.items() if key != "_id"})


@router.get("/cells/{cell_id}", response_model=dict)
async def get_cell(cell_id: str, current_user: dict = Depends(require_read)):
    cell = await ensure_cell_access(cell_id, current_user)
    can_read_sensitive = has_capability(current_user, CELLULAR_SENSITIVE_READ)
    result = await enrich_cell(cell, can_read_sensitive)
    membership_query = {"cell_id": cell_id}
    if not can_read_sensitive:
        membership_query["person_id"] = current_user.get("person_id")
    memberships = await db.cell_memberships.find(membership_query, {"_id": 0}).sort("joined_at", -1).to_list(1000)
    result["memberships"] = [{**serialize(item), "person": await person_summary(db, item["person_id"])} for item in memberships]
    meetings = await db.cell_meetings.find({"cell_id": cell_id}, {"_id": 0}).sort("scheduled_at", -1).limit(50).to_list(50)
    result["meetings"] = [sanitize_meeting(item, can_read_sensitive) for item in meetings]
    result["needs"] = serialize(await db.cell_needs.find({"cell_id": cell_id}, {"_id": 0}).sort("reported_at", -1).limit(100).to_list(100)) if can_read_sensitive else []
    result["followups"] = serialize(await db.cell_followups.find({"cell_id": cell_id}, {"_id": 0}).sort("due_at", 1).limit(100).to_list(100)) if can_read_sensitive else []
    result["timeline"] = serialize(await db.cell_timeline.find({"cell_id": cell_id}, {"_id": 0}).sort("occurred_at", -1).limit(200).to_list(200)) if can_read_sensitive else []
    return result


@router.put("/cells/{cell_id}", response_model=dict)
async def update_cell(cell_id: str, payload: CellUpdate, current_user: dict = Depends(require_write)):
    await ensure_cell_access(cell_id, current_user, True); update = payload.model_dump(exclude_none=True)
    if update.get("network_id") and not await network_manageable(update["network_id"], current_user): raise HTTPException(status_code=403, detail="Red fuera de alcance")
    update["updated_at"] = now_utc(); await db.cells.update_one({"cell_id": cell_id}, {"$set": update})
    await record_cell_event(db, cell_id, current_user["user_id"], "cell_updated", "Datos de célula actualizados")
    return await enrich_cell(await db.cells.find_one({"cell_id": cell_id}, {"_id": 0}))


@router.post("/cells/{cell_id}/roles", status_code=status.HTTP_201_CREATED, response_model=dict)
async def assign_cell_role(cell_id: str, payload: CellRoleCreate, current_user: dict = Depends(require_write)):
    await ensure_cell_access(cell_id, current_user, True); await ensure_person(payload.person_id)
    if payload.role in {"cell_leader", "assistant"}: await ensure_staff(payload.person_id)
    now = now_utc(); role_id = str(uuid4())
    await db.cell_role_assignments.update_many({"cell_id": cell_id, "role": payload.role, "active": True}, {"$set": {"active": False, "ended_at": now}})
    doc = {"_id": role_id, "role_assignment_id": role_id, "cell_id": cell_id, **payload.model_dump(), "active": True, "started_at": now, "created_by_user_id": current_user["user_id"]}
    await db.cell_role_assignments.insert_one(doc); await record_cell_event(db, cell_id, current_user["user_id"], "role_assigned", f"Función asignada: {payload.role}", person_id=payload.person_id)
    return serialize(doc)


@router.delete("/cells/{cell_id}/roles/{role_assignment_id}", response_model=dict)
async def end_cell_role(cell_id: str, role_assignment_id: str, current_user: dict = Depends(require_write)):
    await ensure_cell_access(cell_id, current_user, True); now = now_utc()
    result = await db.cell_role_assignments.update_one({"role_assignment_id": role_assignment_id, "cell_id": cell_id, "active": True}, {"$set": {"active": False, "ended_at": now}})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Asignación no encontrada")
    return {"message": "Función finalizada sin borrar histórico"}


async def add_membership(cell_id: str, payload: MembershipCreate, current_user: dict, assignment_source_id: str | None = None) -> dict:
    cell = await ensure_cell_access(cell_id, current_user, True); await ensure_person(payload.person_id); now = now_utc()
    existing = await db.cell_memberships.find_one({"cell_id": cell_id, "person_id": payload.person_id, "membership_type": payload.membership_type, "active": True}, {"_id": 0})
    if existing: return existing
    if payload.membership_type == "primary":
        await db.cell_memberships.update_many({"person_id": payload.person_id, "membership_type": "primary", "active": True}, {"$set": {"active": False, "left_at": payload.joined_at.isoformat(), "exit_reason": "Transferencia/asignación a otra célula", "updated_at": now}})
    membership_id = str(uuid4()); doc = {"_id": membership_id, "membership_id": membership_id, "cell_id": cell_id, "network_id": cell["network_id"], **payload.model_dump(), "joined_at": payload.joined_at.isoformat(), "active": True, "left_at": None, "exit_reason": None, "assignment_source_id": assignment_source_id, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.cell_memberships.insert_one(doc); await record_cell_event(db, cell_id, current_user["user_id"], "member_joined", "Persona vinculada a la célula", person_id=payload.person_id)
    return serialize(doc)


@router.post("/cells/{cell_id}/memberships", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_membership(cell_id: str, payload: MembershipCreate, current_user: dict = Depends(require_write)):
    return await add_membership(cell_id, payload, current_user)


@router.post("/memberships/transfer", response_model=dict)
async def transfer_membership(payload: TransferCreate, current_user: dict = Depends(require_write)):
    await ensure_cell_access(payload.target_cell_id, current_user, True); await ensure_person(payload.person_id)
    await db.cell_memberships.update_many(
        {"person_id": payload.person_id, "membership_type": "primary", "active": True},
        {"$set": {"active": False, "left_at": payload.transferred_at.isoformat(), "exit_reason": payload.reason, "updated_at": now_utc()}},
    )
    membership = await add_membership(payload.target_cell_id, MembershipCreate(person_id=payload.person_id, joined_at=payload.transferred_at, source="transfer"), current_user)
    await record_cell_event(db, payload.target_cell_id, current_user["user_id"], "member_transferred", "Transferencia registrada", payload.reason, payload.person_id)
    return membership


@router.get("/ready-inbox", response_model=ItemList)
async def get_ready_inbox(current_user: dict = Depends(require_read)):
    items = await ready_inbox(db, current_user); return {"items": items, "total": len(items)}


@router.post("/ready-inbox/assign", status_code=status.HTTP_201_CREATED, response_model=dict)
async def assign_ready_person(payload: ReadyAssignment, current_user: dict = Depends(require_write)):
    await ensure_cell_access(payload.cell_id, current_user, True); await ensure_person(payload.person_id); await ensure_staff(payload.responsible_person_id)
    enrollment = await db.process_enrollments.find_one({"person_id": payload.person_id, "ready_for_cellular": True, "status": "completed"}, {"_id": 0})
    if not enrollment: raise HTTPException(status_code=409, detail="La Persona no está en la bandeja ready_for_cellular")
    assignment_id = str(uuid4()); now = now_utc()
    membership = await add_membership(payload.cell_id, MembershipCreate(person_id=payload.person_id, source="ready_for_cellular"), current_user, assignment_id)
    followup = await create_followup_record(FollowupCreate(cell_id=payload.cell_id, person_id=payload.person_id, followup_type="followup", responsible_person_id=payload.responsible_person_id, due_at=payload.first_followup_at, priority="high", next_action=payload.first_followup_action), current_user)
    cell = await db.cells.find_one({"cell_id": payload.cell_id}, {"_id": 0})
    event = {"_id": assignment_id, "assignment_id": assignment_id, "person_id": payload.person_id, "process_enrollment_id": enrollment["enrollment_id"], "network_id": cell["network_id"], "cell_id": payload.cell_id, "responsible_person_id": payload.responsible_person_id, "assigned_by_user_id": current_user["user_id"], "assigned_at": now, "first_followup_id": followup["followup_id"]}
    await db.cell_assignment_events.insert_one(event)
    await db.process_enrollments.update_many({"person_id": payload.person_id, "ready_for_cellular": True}, {"$set": {"ready_for_cellular": False, "next_action": "Participar y consolidarse en la célula asignada", "cell_id": payload.cell_id, "updated_at": now}})
    await db.person_activity.insert_one({"_id": str(uuid4()), "person_id": payload.person_id, "domain": "celula", "action": "assigned", "summary": f"Asignación a célula {cell['name']}", "actor_user_id": current_user["user_id"], "created_at": now})
    return {"assignment": serialize(event), "membership": membership, "first_followup": followup}


@router.get("/cells/{cell_id}/meetings", response_model=ItemList)
async def list_meetings(cell_id: str, current_user: dict = Depends(require_read)):
    await ensure_cell_access(cell_id, current_user); docs = await db.cell_meetings.find({"cell_id": cell_id}, {"_id": 0}).sort("scheduled_at", -1).to_list(1000)
    include_sensitive = has_capability(current_user, CELLULAR_SENSITIVE_READ)
    return {"items": [sanitize_meeting(item, include_sensitive) for item in docs], "total": len(docs)}


@router.post("/cells/{cell_id}/meetings", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_meeting(cell_id: str, payload: MeetingCreate, current_user: dict = Depends(require_write)):
    await ensure_cell_access(cell_id, current_user, True); await ensure_staff(payload.leader_person_id)
    if payload.host_person_id: await ensure_person(payload.host_person_id)
    meeting_id = str(uuid4()); now = now_utc()
    doc = {"_id": meeting_id, "meeting_id": meeting_id, "cell_id": cell_id, **payload.model_dump(exclude={"tasks"}), "tasks": [{"task_id": str(uuid4()), "label": label.strip(), "completed": False, "completed_at": None} for label in payload.tasks if label.strip()], "status": "scheduled", "conversion_person_ids": [], "petitions": [], "results": None, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.cell_meetings.insert_one(doc); await record_cell_event(db, cell_id, current_user["user_id"], "meeting_created", "Reunión registrada", payload.topic)
    return serialize(doc)


@router.post("/meetings/{meeting_id}/start", response_model=dict)
async def start_meeting(meeting_id: str, current_user: dict = Depends(require_attendance)):
    meeting = await db.cell_meetings.find_one({"meeting_id": meeting_id}, {"_id": 0})
    if not meeting: raise HTTPException(status_code=404, detail="Reunión no encontrada")
    await ensure_cell_access(meeting["cell_id"], current_user, True)
    now = now_utc()
    await db.cell_meetings.update_one({"meeting_id": meeting_id}, {"$set": {"status": "in_progress", "started_at": meeting.get("started_at") or now, "updated_at": now}})
    return serialize(await db.cell_meetings.find_one({"meeting_id": meeting_id}, {"_id": 0}))


@router.put("/meetings/{meeting_id}/tasks", response_model=dict)
async def save_meeting_tasks(meeting_id: str, payload: MeetingTasksBulk, current_user: dict = Depends(require_attendance)):
    meeting = await db.cell_meetings.find_one({"meeting_id": meeting_id})
    if not meeting: raise HTTPException(status_code=404, detail="Reunión no encontrada")
    await ensure_cell_access(meeting["cell_id"], current_user, True)
    changes = {item.task_id: item.completed for item in payload.entries}
    tasks = []
    for task in meeting.get("tasks", []):
        if isinstance(task, str):
            task = {"task_id": str(uuid4()), "label": task, "completed": False, "completed_at": None}
        if task["task_id"] in changes:
            task["completed"] = changes[task["task_id"]]
            task["completed_at"] = now_utc() if task["completed"] else None
        tasks.append(task)
    await db.cell_meetings.update_one({"_id": meeting["_id"]}, {"$set": {"tasks": tasks, "updated_at": now_utc()}})
    return {"tasks": serialize(tasks)}


@router.get("/meetings/{meeting_id}", response_model=dict)
async def meeting_detail(meeting_id: str, current_user: dict = Depends(require_read)):
    meeting = await db.cell_meetings.find_one({"meeting_id": meeting_id}, {"_id": 0})
    if not meeting: raise HTTPException(status_code=404, detail="Reunión no encontrada")
    await ensure_cell_access(meeting["cell_id"], current_user)
    if not has_capability(current_user, CELLULAR_SENSITIVE_READ):
        return sanitize_meeting(meeting, False)
    attendance = await db.cell_meeting_attendance.find({"meeting_id": meeting_id}, {"_id": 0}).to_list(1000)
    return {**serialize(meeting), "attendance": serialize(attendance)}


@router.put("/meetings/{meeting_id}/attendance", response_model=dict)
async def save_meeting_attendance(meeting_id: str, payload: AttendanceBulk, current_user: dict = Depends(require_attendance)):
    meeting = await db.cell_meetings.find_one({"meeting_id": meeting_id}, {"_id": 0})
    if not meeting: raise HTTPException(status_code=404, detail="Reunión no encontrada")
    cell = await ensure_cell_access(meeting["cell_id"], current_user, True); now = now_utc()
    person_ids = {item.person_id for item in payload.entries}
    if not set(payload.conversion_person_ids).issubset(person_ids): raise HTTPException(status_code=400, detail="Toda conversión debe corresponder a una Persona asistente")
    stale = await db.cell_meeting_attendance.find({"meeting_id": meeting_id, "person_id": {"$nin": list(person_ids)}}, {"_id": 0, "attendance_id": 1}).to_list(1000)
    stale_ids = [item["attendance_id"] for item in stale]
    if stale_ids:
        await db.cell_meeting_attendance.delete_many({"attendance_id": {"$in": stale_ids}})
        await db.person_attendance.delete_many({"_id": {"$in": stale_ids}, "activity_type": "cell_meeting", "source_id": meeting_id})
    person_status = {"present": "presente", "absent": "ausente", "excused": "justificado"}
    for entry in payload.entries:
        await ensure_person(entry.person_id)
        attendance_id = f"cell:{meeting_id}:{entry.person_id}"
        cell_doc = {"attendance_id": attendance_id, "meeting_id": meeting_id, "cell_id": meeting["cell_id"], **entry.model_dump(), "recorded_by_user_id": current_user["user_id"], "recorded_at": now, "updated_at": now}
        await db.cell_meeting_attendance.update_one({"_id": attendance_id}, {"$set": cell_doc, "$setOnInsert": {"_id": attendance_id}}, upsert=True)
        person_doc = {"person_id": entry.person_id, "fecha": meeting["scheduled_at"].date().isoformat(), "actividad": f"Célula · {cell['name']}", "estado": person_status[entry.status], "notas": "Visitante" if entry.is_visitor else None, "activity_type": "cell_meeting", "source_id": meeting_id, "cell_id": meeting["cell_id"], "created_by": current_user["user_id"], "created_at": now, "updated_at": now}
        await db.person_attendance.update_one({"_id": attendance_id}, {"$set": person_doc, "$setOnInsert": {"_id": attendance_id}}, upsert=True)
    meeting_update = {"conversion_person_ids": payload.conversion_person_ids, "petitions": payload.petitions, "results": payload.results, "status": "completed" if payload.complete_meeting else "in_progress", "completed_at": now if payload.complete_meeting else None, "updated_at": now}
    await db.cell_meetings.update_one({"meeting_id": meeting_id}, {"$set": meeting_update})
    if payload.complete_meeting:
        await snapshot_cell_health(db, meeting["cell_id"], current_user["user_id"], meeting_id)
        await evaluate_multiplication(db, meeting["cell_id"], current_user["user_id"])
    await record_cell_event(db, meeting["cell_id"], current_user["user_id"], "attendance_recorded", "Asistencia registrada", f"{len(payload.entries)} Personas")
    return await meeting_detail(meeting_id, current_user)


async def create_followup_record(payload: FollowupCreate, current_user: dict) -> dict:
    await ensure_cell_access(payload.cell_id, current_user, True); await ensure_person(payload.person_id); await ensure_staff(payload.responsible_person_id)
    followup_id = str(uuid4()); now = now_utc()
    doc = {"_id": followup_id, "followup_id": followup_id, **payload.model_dump(), "status": "open", "history": [{"status": "open", "at": now, "actor_user_id": current_user["user_id"]}], "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.cell_followups.insert_one(doc); await record_cell_event(db, payload.cell_id, current_user["user_id"], "followup_created", f"Seguimiento: {payload.followup_type}", f"Prioridad {payload.priority} · vence {payload.due_at.date().isoformat()}", payload.person_id)
    return serialize(doc)


@router.get("/followups", response_model=ItemList)
async def list_followups(status_filter: Optional[str] = None, current_user: dict = Depends(require_sensitive_read)):
    scope = await cellular_scope(db, current_user); query = {} if scope["global"] else {"cell_id": {"$in": scope["cell_ids"]}}
    if status_filter: query["status"] = status_filter
    docs = await db.cell_followups.find(query, {"_id": 0}).sort("due_at", 1).to_list(10000)
    return {"items": serialize(docs), "total": len(docs)}


@router.post("/followups", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_followup(payload: FollowupCreate, current_user: dict = Depends(require_needs)):
    return await create_followup_record(payload, current_user)


@router.put("/followups/{followup_id}", response_model=dict)
async def update_followup(followup_id: str, payload: FollowupUpdate, current_user: dict = Depends(require_needs)):
    doc = await db.cell_followups.find_one({"followup_id": followup_id})
    if not doc: raise HTTPException(status_code=404, detail="Seguimiento no encontrado")
    await ensure_cell_access(doc["cell_id"], current_user, True); now = now_utc(); update = payload.model_dump(exclude_none=True)
    history = doc.get("history", []) + [{"status": payload.status, "at": now, "actor_user_id": current_user["user_id"], "result": payload.result}]
    update.update({"history": history, "updated_at": now}); await db.cell_followups.update_one({"_id": doc["_id"]}, {"$set": update})
    return serialize(await db.cell_followups.find_one({"followup_id": followup_id}, {"_id": 0}))


@router.get("/needs", response_model=ItemList)
async def list_needs(status_filter: Optional[str] = None, current_user: dict = Depends(require_sensitive_read)):
    scope = await cellular_scope(db, current_user); query = {} if scope["global"] else {"cell_id": {"$in": scope["cell_ids"]}}
    if status_filter: query["status"] = status_filter
    docs = await db.cell_needs.find(query, {"_id": 0}).sort("reported_at", -1).to_list(10000)
    return {"items": serialize(docs), "total": len(docs)}


@router.post("/needs", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_need(payload: NeedCreate, current_user: dict = Depends(require_needs)):
    await ensure_cell_access(payload.cell_id, current_user, True)
    for person_id in [payload.person_id, payload.family_person_id, payload.responsible_person_id]:
        if person_id: await ensure_person(person_id)
    if payload.assigned_door_key and not await db.door_catalog.find_one({"door_key": payload.assigned_door_key, "active": True}): raise HTTPException(status_code=400, detail="Puerta asignada inválida")
    need_id = str(uuid4()); now = now_utc(); suggested = suggested_door(payload.need_type)
    doc = {"_id": need_id, "need_id": need_id, **payload.model_dump(), "suggested_door_key": suggested, "status": "assigned" if payload.responsible_person_id or payload.assigned_door_key else "open", "reported_by_person_id": current_user.get("person_id"), "reported_by_user_id": current_user["user_id"], "reported_at": now, "history": [{"status": "open", "at": now, "actor_user_id": current_user["user_id"]}], "updated_at": now}
    await db.cell_needs.insert_one(doc); await record_cell_event(db, payload.cell_id, current_user["user_id"], "need_detected", f"Necesidad detectada: {payload.need_type}", f"Prioridad {payload.priority} · Puerta sugerida {suggested or 'revisión humana'}", payload.person_id)
    if suggested or payload.assigned_door_key:
        from door_board_engine import upsert_case_from_cell_need
        case = await upsert_case_from_cell_need(db, doc, current_user["user_id"])
        if case:
            doc["door_case_id"] = case["case_id"]
            doc["assigned_door_key"] = case["door_key"]
    return serialize(doc)


@router.put("/needs/{need_id}", response_model=dict)
async def update_need(need_id: str, payload: NeedUpdate, current_user: dict = Depends(require_needs)):
    doc = await db.cell_needs.find_one({"need_id": need_id})
    if not doc: raise HTTPException(status_code=404, detail="Necesidad no encontrada")
    await ensure_cell_access(doc["cell_id"], current_user, True); update = payload.model_dump(exclude_none=True)
    if update.get("assigned_door_key") and not await db.door_catalog.find_one({"door_key": update["assigned_door_key"], "active": True}): raise HTTPException(status_code=400, detail="Puerta inválida")
    if update.get("responsible_person_id"): await ensure_person(update["responsible_person_id"])
    now = now_utc(); update["history"] = doc.get("history", []) + [{"status": update.get("status", doc["status"]), "at": now, "actor_user_id": current_user["user_id"], "resolution": update.get("resolution")}]; update["updated_at"] = now
    await db.cell_needs.update_one({"_id": doc["_id"]}, {"$set": update})
    updated_need = await db.cell_needs.find_one({"need_id": need_id}, {"_id": 0})
    if updated_need.get("assigned_door_key") or updated_need.get("suggested_door_key"):
        from door_board_engine import upsert_case_from_cell_need
        await upsert_case_from_cell_need(db, updated_need, current_user["user_id"])
    return serialize(await db.cell_needs.find_one({"need_id": need_id}, {"_id": 0}))


@router.get("/health", response_model=ItemList)
async def health_history(cell_id: Optional[str] = None, current_user: dict = Depends(require_read)):
    scope = await cellular_scope(db, current_user); query = {}
    if cell_id:
        await ensure_cell_access(cell_id, current_user); query["cell_id"] = cell_id
    elif not scope["global"]: query["cell_id"] = {"$in": scope["cell_ids"]}
    docs = await db.cell_health_snapshots.find(query, {"_id": 0}).sort("recorded_at", -1).to_list(10000)
    include_sensitive = has_capability(current_user, CELLULAR_SENSITIVE_READ)
    return {"items": [sanitize_health(item, include_sensitive) for item in docs], "total": len(docs)}


@router.get("/multiplication/rules", response_model=dict)
async def get_multiplication_rule(current_user: dict = Depends(require_read)):
    return serialize(await db.cell_multiplication_rules.find_one({"rule_key": "default"}, {"_id": 0}) or {})


@router.put("/multiplication/rules", response_model=dict)
async def update_multiplication_rule(payload: MultiplicationRuleUpdate, current_user: dict = Depends(require_multiply)):
    update = payload.model_dump(exclude_none=True); update["updated_at"] = now_utc(); await db.cell_multiplication_rules.update_one({"rule_key": "default"}, {"$set": update})
    return serialize(await db.cell_multiplication_rules.find_one({"rule_key": "default"}, {"_id": 0}))


@router.post("/cells/{cell_id}/multiplication/evaluate", response_model=dict)
async def evaluate_cell_multiplication(cell_id: str, current_user: dict = Depends(require_write)):
    await ensure_cell_access(cell_id, current_user, True); return await evaluate_multiplication(db, cell_id, current_user["user_id"])


@router.get("/multiplication/reviews", response_model=ItemList)
async def list_multiplication_reviews(current_user: dict = Depends(require_read)):
    scope = await cellular_scope(db, current_user); query = {} if scope["global"] else {"cell_id": {"$in": scope["cell_ids"]}}
    docs = await db.cell_multiplication_reviews.find(query, {"_id": 0}).sort("updated_at", -1).to_list(1000)
    include_sensitive = has_capability(current_user, CELLULAR_SENSITIVE_READ)
    items = serialize(docs)
    if not include_sensitive:
        for item in items:
            metrics = item.get("facts", {}).get("metrics")
            if isinstance(metrics, dict):
                item["facts"]["metrics"] = {key: value for key, value in metrics.items() if key not in SENSITIVE_HEALTH_FIELDS}
    return {"items": items, "total": len(items)}


@router.put("/multiplication/reviews/{review_id}", response_model=dict)
async def review_multiplication(review_id: str, payload: MultiplicationAction, current_user: dict = Depends(require_multiply)):
    review = await db.cell_multiplication_reviews.find_one({"review_id": review_id})
    if not review: raise HTTPException(status_code=404, detail="Revisión no encontrada")
    await ensure_cell_access(review["cell_id"], current_user, True)
    mother = await db.cells.find_one({"cell_id": review["cell_id"]}, {"_id": 0})
    if not mother: raise HTTPException(status_code=404, detail="Célula madre no encontrada")
    now = now_utc()
    if payload.action in {"under_review", "postpone"}:
        await db.cell_multiplication_reviews.update_one({"_id": review["_id"]}, {"$set": {"status": "under_review" if payload.action == "under_review" else "postponed", "decision": payload.action, "reason": payload.reason, "decided_by_user_id": current_user["user_id"], "updated_at": now}})
        return serialize(await db.cell_multiplication_reviews.find_one({"review_id": review_id}, {"_id": 0}))
    if not payload.daughter_cell or not payload.daughter_leader_person_id: raise HTTPException(status_code=400, detail="Aprobación requiere célula hija y líder")
    if payload.daughter_cell.mother_cell_id not in {None, mother["cell_id"]}: raise HTTPException(status_code=400, detail="La genealogía debe apuntar a la célula madre revisada")
    daughter_payload = payload.daughter_cell.model_copy(update={"mother_cell_id": mother["cell_id"], "network_id": mother["network_id"]})
    daughter = await create_cell(daughter_payload, current_user)
    await assign_cell_role(daughter["cell_id"], CellRoleCreate(person_id=payload.daughter_leader_person_id, role="cell_leader"), current_user)
    transferred = []
    for person_id in payload.transferred_person_ids:
        await ensure_person(person_id)
        membership = await add_membership(daughter["cell_id"], MembershipCreate(person_id=person_id, source="multiplication"), current_user, review_id)
        transferred.append(membership["membership_id"])
    multiplication_id = str(uuid4()); record = {"_id": multiplication_id, "multiplication_id": multiplication_id, "review_id": review_id, "mother_cell_id": mother["cell_id"], "daughter_cell_id": daughter["cell_id"], "leader_person_id": payload.daughter_leader_person_id, "transferred_person_ids": payload.transferred_person_ids, "transferred_membership_ids": transferred, "approved_by_user_id": current_user["user_id"], "multiplied_at": now}
    await db.cell_multiplications.insert_one(record); await db.cell_multiplication_reviews.update_one({"_id": review["_id"]}, {"$set": {"status": "approved", "decision": "approve", "reason": payload.reason, "multiplication_id": multiplication_id, "decided_by_user_id": current_user["user_id"], "updated_at": now}})
    await record_cell_event(db, mother["cell_id"], current_user["user_id"], "multiplication_approved", "Multiplicación aprobada", daughter["name"])
    return {"review": serialize(await db.cell_multiplication_reviews.find_one({"review_id": review_id}, {"_id": 0})), "multiplication": serialize(record), "daughter_cell": daughter}


@router.get("/genealogy", response_model=dict)
async def genealogy(current_user: dict = Depends(require_read)):
    scope = await cellular_scope(db, current_user); query = {} if scope["global"] else {"cell_id": {"$in": scope["cell_ids"]}}
    cells = await db.cells.find(query, {"_id": 0, "cell_id": 1, "name": 1, "code": 1, "mother_cell_id": 1, "opened_at": 1, "status": 1}).to_list(10000)
    allowed = {item["cell_id"] for item in cells}
    multiplications = await db.cell_multiplications.find({"$or": [{"mother_cell_id": {"$in": list(allowed)}}, {"daughter_cell_id": {"$in": list(allowed)}}]}, {"_id": 0}).to_list(10000)
    return {"nodes": serialize(cells), "edges": serialize(multiplications)}


@router.get("/dashboard", response_model=dict)
async def dashboard(current_user: dict = Depends(require_read)):
    scope = await cellular_scope(db, current_user); query = {} if scope["global"] else {"cell_id": {"$in": scope["cell_ids"]}}
    cells = await db.cells.find(query, {"_id": 0}).to_list(10000); cell_ids = [item["cell_id"] for item in cells]
    memberships = await db.cell_memberships.find({"cell_id": {"$in": cell_ids}, "active": True}, {"_id": 0}).to_list(50000) if cell_ids else []
    meetings = await db.cell_meetings.find({"cell_id": {"$in": cell_ids}, "status": "completed"}, {"_id": 0}).to_list(50000) if cell_ids else []
    meeting_ids = [item["meeting_id"] for item in meetings]
    attendance = await db.cell_meeting_attendance.find({"meeting_id": {"$in": meeting_ids}}, {"_id": 0}).to_list(100000) if meeting_ids else []
    ready = await ready_inbox(db, current_user)
    can_read_sensitive = has_capability(current_user, CELLULAR_SENSITIVE_READ)
    needs = await db.cell_needs.find({"cell_id": {"$in": cell_ids}, "status": {"$in": ["open", "assigned", "in_progress"]}}, {"_id": 0}).sort("reported_at", -1).limit(20).to_list(20) if cell_ids and can_read_sensitive else []
    followups = await db.cell_followups.find({"cell_id": {"$in": cell_ids}, "status": {"$in": ["open", "in_progress"]}}, {"_id": 0}).sort("due_at", 1).limit(20).to_list(20) if cell_ids and can_read_sensitive else []
    reviews = await db.cell_multiplication_reviews.count_documents({"cell_id": {"$in": cell_ids}, "status": {"$in": ["candidate", "under_review"]}}) if cell_ids else 0
    active_primary_person_ids = await db.cell_memberships.distinct("person_id", {"active": True, "membership_type": "primary"})
    if scope["global"]:
        people_without_cell = await db.persons.count_documents({"_id": {"$nin": [ObjectId(item) for item in active_primary_person_ids if ObjectId.is_valid(item)]}})
    else:
        from process_engine import access_person_ids
        allowed_person_ids = await access_person_ids(db, current_user) or set()
        people_without_cell = len(set(allowed_person_ids) - set(active_primary_person_ids))
    metrics = {
        "active_cells": sum(1 for item in cells if item.get("status") == "active"),
        "new_cells": sum(1 for item in cells if str(item.get("opened_at", ""))[:7] == now_utc().strftime("%Y-%m")),
        "attendance_total": sum(1 for item in attendance if item.get("status") == "present"),
        "average_per_cell": round(sum(1 for item in attendance if item.get("status") == "present") / max(1, len(cells)), 1),
        "active_leaders": await db.cell_role_assignments.count_documents({"cell_id": {"$in": cell_ids}, "role": "cell_leader", "active": True}) if cell_ids else 0,
        "leaders_in_training": await db.cell_role_assignments.count_documents({"cell_id": {"$in": cell_ids}, "role": "assistant", "active": True}) if cell_ids else 0,
        "multiplied_cells": await db.cell_multiplications.count_documents({"mother_cell_id": {"$in": cell_ids}}) if cell_ids else 0,
        "multiplication_candidates": reviews,
        "ready_for_cellular": len(ready),
        "people_without_cell": people_without_cell,
    }
    if can_read_sensitive:
        metrics.update({
            "new_visitors": sum(1 for item in attendance if item.get("is_new")),
            "conversions": sum(len(item.get("conversion_person_ids", [])) for item in meetings),
            "open_needs": len(needs),
            "pending_followups": len(followups),
        })
    return {"metrics": metrics, "cells": [await enrich_cell(item, can_read_sensitive) for item in cells], "ready": ready, "needs": serialize(needs), "followups": serialize(followups), "scope": scope}


@router.post("/migrate", response_model=dict)
async def migrate(current_user: dict = Depends(require_manage)):
    return await migrate_cellular(db, current_user["user_id"])