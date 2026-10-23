"""Grupos Frontales: árbol recursivo, membresías canónicas y scope jerárquico."""
import re
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
    build_tree, direct_assignments, group_in_scope as tree_group_in_scope, lineage_for_parent,
    load_group, manageable_group_ids, readable_group_ids, support_group_ids, move_subtree,
)
from person_matching import GroupQuickPerson, normalize_text, quick_create_person
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


class DesignationCreate(BaseModel):
    leader_person_id: str
    co_leader_person_id: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=600)


class ConformGroup(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    member_person_ids: list[str] = Field(default_factory=list, max_length=200)


class CoLeaderAssignment(BaseModel):
    person_id: str
    reason: str = Field(min_length=2, max_length=600)


class MemberEnd(BaseModel):
    reason: str = Field(min_length=3, max_length=600)


class MemberTransfer(BaseModel):
    person_id: str
    to_group_id: str
    role: Literal["member", "mentor"] = "member"
    reason: str = Field(min_length=3, max_length=600)


class FrontGroupArchive(BaseModel):
    reason: str = Field(min_length=3, max_length=600)


async def require_read(current_user: dict = Depends(get_current_user)) -> dict:
    """Lectura: capability global O coincidencia real con ALGUNA membresía
    (líder, colíder o simple integrante) — ver B2 #1: antes solo entraba quien
    tuviera la capability, dejando fuera a un líder/colíder real sin ella."""
    if is_global_pastoral_authority(current_user) or any(has_capability(current_user, item) for item in (FRONT_GROUPS_VIEW, FRONT_GROUPS_MANAGE)):
        return current_user
    if await direct_assignments(db, current_user.get("person_id")):
        return current_user
    raise HTTPException(status_code=403, detail="Sin permiso para consultar Grupos Frontales")


async def _has_real_leadership(current_user: dict) -> bool:
    assignments = await direct_assignments(db, current_user.get("person_id"))
    return any(item.get("role") in {"leader", "co_leader"} for item in assignments)


async def require_manage(current_user: dict = Depends(get_current_user)) -> dict:
    """Entrada a endpoints de gestión: capability global O una designación
    real de Líder/Colíder en algún Grupo Frontal. El alcance EXACTO (qué rama)
    lo decide `assert_group_scope` con level='lead'/'support' en cada ruta."""
    if is_global_pastoral_authority(current_user) or has_capability(current_user, FRONT_GROUPS_MANAGE):
        return current_user
    if await _has_real_leadership(current_user):
        return current_user
    raise HTTPException(status_code=403, detail="Sin permiso para administrar Grupos Frontales")


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


async def group_in_scope(group_id: str, current_user: dict, leader_required: bool = False, level: Optional[str] = None) -> bool:
    return await tree_group_in_scope(db, group_id, current_user, leader_required, level=level)


async def assert_group_scope(group_id: str, current_user: dict, leader_required: bool = False, level: Optional[str] = None) -> dict:
    group = await load_group(db, group_id)
    if not await group_in_scope(group_id, current_user, leader_required, level=level):
        raise HTTPException(status_code=403, detail="Grupo Frontal fuera de su ámbito")
    return group


async def ensure_front_group_capability(person_id: Optional[str]) -> None:
    """Otorga `front_groups.view` de forma aditiva a la cuenta vinculada a esta
    Persona si tiene una membresía activa de Líder o Colíder (ver menú lateral);
    nunca quita capacidades existentes."""
    if not person_id:
        return
    if await db.front_group_assignments.find_one({"person_id": person_id, "role": {"$in": ["leader", "co_leader"]}, "active": True}, {"_id": 1}):
        await db.users.update_many({"person_id": person_id}, {"$addToSet": {"capabilities": FRONT_GROUPS_VIEW}})


async def person_name(person_id: Optional[str]) -> Optional[str]:
    if not person_id or not ObjectId.is_valid(person_id): return None
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 0, "nombre": 1, "apellido": 1})
    return " ".join(part for part in [(person or {}).get("nombre"), (person or {}).get("apellido")] if part) or None


async def group_summary(group: dict, current_user: dict) -> dict:
    item = serialize(group)
    item["primary_leader_name"] = await person_name(group.get("primary_leader_person_id"))
    item["co_leader_name"] = await person_name(group.get("co_leader_person_id"))
    item["display_name"] = item.get("name") or (f"Equipo de {item['primary_leader_name']}" if item["primary_leader_name"] else "Equipo sin líder")
    item["team_count"] = await db.front_group_assignments.count_documents({"front_group_id": group["front_group_id"], "active": True})
    item["active_process_count"] = await db.process_enrollments.count_documents({"front_group_id": group["front_group_id"], "process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}})
    manageable = await manageable_group_ids(db, current_user)
    supportable = await support_group_ids(db, current_user)
    item["permissions"] = {
        "manage": manageable is None or group["front_group_id"] in manageable,
        "support": supportable is None or group["front_group_id"] in supportable,
    }
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
    for item in assignments:
        person = await db.persons.find_one({"_id": ObjectId(item["person_id"])}, {"nombre": 1, "apellido": 1, "auth_user_id": 1}) if ObjectId.is_valid(item["person_id"]) else None
        item["person_name"] = " ".join(part for part in [(person or {}).get("nombre"), (person or {}).get("apellido")] if part) or None
        item["has_account"] = bool((person or {}).get("auth_user_id"))
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
    await assert_group_scope(group_id, current_user, level="support"); await load_person(payload.person_id)
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
    await db.front_groups.update_one({"front_group_id": group_id}, {"$set": {"primary_leader_person_id": payload.person_id, "leader_pending": False, "updated_at": now, "updated_by_user_id": current_user["user_id"]}})
    await ensure_front_group_capability(payload.person_id)
    await audit(group_id, current_user, "primary_leader_assigned", {"assignment_id": assignment_id, "person_id": payload.person_id, "reason": payload.reason})
    return serialize(assignment)


@router.post("/{group_id}/co-leader", response_model=dict)
async def assign_co_leader(group_id: str, payload: CoLeaderAssignment, current_user: dict = Depends(require_manage)):
    """Colíder de la pareja de liderazgo: ve y registra en el grupo y sus
    ramas (soporte), pero nunca gestiona estructura (eso sigue siendo del
    Líder o una autoridad superior)."""
    await assert_group_scope(group_id, current_user, leader_required=True); await load_person(payload.person_id)
    group = await load_group(db, group_id)
    if group.get("primary_leader_person_id") == payload.person_id:
        raise HTTPException(status_code=422, detail="El líder y el colíder deben ser personas distintas")
    now = now_utc()
    await db.front_group_assignments.update_many({"front_group_id": group_id, "role": "co_leader", "active": True}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "end_reason": payload.reason}})
    assignment_id = str(uuid4())
    assignment = {"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id, "person_id": payload.person_id, "role": "co_leader", "active": True, "started_at": now, "ended_at": None, "notes": payload.reason, "assigned_by_user_id": current_user["user_id"], "created_at": now}
    await db.front_group_assignments.insert_one(assignment)
    await db.front_groups.update_one({"front_group_id": group_id}, {"$set": {"co_leader_person_id": payload.person_id, "updated_at": now, "updated_by_user_id": current_user["user_id"]}})
    await ensure_front_group_capability(payload.person_id)
    await audit(group_id, current_user, "co_leader_assigned", {"assignment_id": assignment_id, "person_id": payload.person_id, "reason": payload.reason})
    return serialize(assignment)


@router.post("/{parent_id}/designations", response_model=dict, status_code=201)
async def create_designation(parent_id: str, payload: DesignationCreate, current_user: dict = Depends(require_manage)):
    """A3/A4: designa una pareja Líder+Colíder para un grupo dependiente de
    `parent_id`. Crea el grupo dependiente en el acto (status=pending_formation);
    'Conformar mi grupo' reutiliza ese MISMO grupo, nunca crea otro."""
    await assert_group_scope(parent_id, current_user, leader_required=True)
    if payload.co_leader_person_id and payload.co_leader_person_id == payload.leader_person_id:
        raise HTTPException(status_code=422, detail="El líder y el colíder deben ser personas distintas")
    await load_person(payload.leader_person_id)
    if payload.co_leader_person_id:
        await load_person(payload.co_leader_person_id)
    existing = await db.front_groups.find_one({"parent_group_id": parent_id, "primary_leader_person_id": payload.leader_person_id, "status": {"$ne": "archived"}}, {"_id": 0})
    if existing:
        return await group_summary(existing, current_user)
    now = now_utc()

    async def ensure_parent_member(person_id: str) -> str:
        found = await db.front_group_assignments.find_one({"front_group_id": parent_id, "person_id": person_id, "active": True}, {"_id": 0})
        if found: return found["assignment_id"]
        assignment_id = str(uuid4())
        await db.front_group_assignments.insert_one({"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": parent_id, "person_id": person_id, "role": "member", "active": True, "started_at": now, "ended_at": None, "notes": "Agregado al designar pareja de liderazgo", "assigned_by_user_id": current_user["user_id"], "created_at": now})
        return assignment_id

    origin_assignment_id = await ensure_parent_member(payload.leader_person_id)
    if payload.co_leader_person_id:
        await ensure_parent_member(payload.co_leader_person_id)
    group_id = str(uuid4())
    lineage = await lineage_for_parent(db, group_id, parent_id)
    document = {
        "_id": group_id, "front_group_id": group_id, "name": None, "description": None,
        "status": "pending_formation", "routing_enabled": True, "rotation_order": 0, "linked_structures": [],
        "primary_leader_person_id": payload.leader_person_id, "co_leader_person_id": payload.co_leader_person_id,
        "origin_assignment_id": origin_assignment_id, "leader_pending": False,
        "designated_by_user_id": current_user["user_id"], "designated_at": now,
        "tree_version": 1, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
        **lineage,
    }
    await db.front_groups.insert_one(document)
    leader_assignment_id = str(uuid4())
    await db.front_group_assignments.insert_one({"_id": leader_assignment_id, "assignment_id": leader_assignment_id, "front_group_id": group_id, "person_id": payload.leader_person_id, "role": "leader", "active": True, "started_at": now, "ended_at": None, "notes": payload.reason or "Designación de pareja de liderazgo", "assigned_by_user_id": current_user["user_id"], "created_at": now})
    if payload.co_leader_person_id:
        co_assignment_id = str(uuid4())
        await db.front_group_assignments.insert_one({"_id": co_assignment_id, "assignment_id": co_assignment_id, "front_group_id": group_id, "person_id": payload.co_leader_person_id, "role": "co_leader", "active": True, "started_at": now, "ended_at": None, "notes": payload.reason or "Designación de pareja de liderazgo", "assigned_by_user_id": current_user["user_id"], "created_at": now})
    await ensure_front_group_capability(payload.leader_person_id)
    await ensure_front_group_capability(payload.co_leader_person_id)
    await audit(group_id, current_user, "group_designated", {"parent_group_id": parent_id, "leader_person_id": payload.leader_person_id, "co_leader_person_id": payload.co_leader_person_id, "reason": payload.reason})
    await audit(parent_id, current_user, "child_designated", {"child_group_id": group_id, "leader_person_id": payload.leader_person_id, "co_leader_person_id": payload.co_leader_person_id, "reason": payload.reason})
    return await group_summary(document, current_user)


@router.put("/{group_id}/conform", response_model=dict)
async def conform_group(group_id: str, payload: ConformGroup, current_user: dict = Depends(get_current_user)):
    """A4: el líder DESIGNADO abre 'Conformar mi grupo frontal'. Reutiliza el
    grupo creado por la designación (status pending_formation→active); no crea
    otro. Pulsar dos veces es seguro (no duplica integrantes)."""
    group = await load_group(db, group_id)
    is_designated_leader = bool(current_user.get("person_id")) and await db.front_group_assignments.find_one({"front_group_id": group_id, "person_id": current_user.get("person_id"), "role": "leader", "active": True}, {"_id": 1})
    if not is_designated_leader and not is_global_pastoral_authority(current_user) and not has_capability(current_user, FRONT_GROUPS_MANAGE):
        raise HTTPException(status_code=403, detail="Solo el líder designado de este grupo puede conformarlo")
    now = now_utc()
    update = {"status": "active", "updated_at": now, "updated_by_user_id": current_user["user_id"]}
    if payload.name: update["name"] = payload.name
    await db.front_groups.update_one({"front_group_id": group_id}, {"$set": update})
    added = 0
    for person_id in payload.member_person_ids:
        await load_person(person_id)
        if not await db.front_group_assignments.find_one({"front_group_id": group_id, "person_id": person_id, "active": True}, {"_id": 1}):
            assignment_id = str(uuid4())
            await db.front_group_assignments.insert_one({"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id, "person_id": person_id, "role": "member", "active": True, "started_at": now, "ended_at": None, "notes": "Agregado al conformar el grupo", "assigned_by_user_id": current_user["user_id"], "created_at": now})
            added += 1
    await audit(group_id, current_user, "group_conformed", {"name": payload.name, "members_added": added})
    return await group_summary(await load_group(db, group_id), current_user)


@router.delete("/{group_id}/members/{person_id}", response_model=dict)
async def end_member(group_id: str, person_id: str, payload: MemberEnd, current_user: dict = Depends(require_manage)):
    await assert_group_scope(group_id, current_user, leader_required=True)
    now = now_utc()
    result = await db.front_group_assignments.update_many({"front_group_id": group_id, "person_id": person_id, "active": True}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "end_reason": payload.reason}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="La persona no es integrante activo de este grupo")
    group = await load_group(db, group_id)
    changes = {}
    if group.get("primary_leader_person_id") == person_id:
        changes = {"primary_leader_person_id": None, "leader_pending": True}
    elif group.get("co_leader_person_id") == person_id:
        changes = {"co_leader_person_id": None}
    if changes:
        changes.update({"updated_at": now, "updated_by_user_id": current_user["user_id"]})
        await db.front_groups.update_one({"front_group_id": group_id}, {"$set": changes})
    await audit(group_id, current_user, "member_ended", {"person_id": person_id, "reason": payload.reason})
    return {"ended": True}


@router.post("/{group_id}/members/transfer", response_model=dict)
async def transfer_member(group_id: str, payload: MemberTransfer, current_user: dict = Depends(require_manage)):
    if group_id == payload.to_group_id:
        raise HTTPException(status_code=422, detail="El grupo de origen y el destino no pueden ser el mismo")
    await assert_group_scope(group_id, current_user, leader_required=True)
    await assert_group_scope(payload.to_group_id, current_user, leader_required=True)
    if await db.front_group_assignments.find_one({"front_group_id": payload.to_group_id, "person_id": payload.person_id, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Esa persona ya es integrante activo del grupo destino")
    now = now_utc()
    result = await db.front_group_assignments.update_many({"front_group_id": group_id, "person_id": payload.person_id, "active": True}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "end_reason": payload.reason}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="La persona no es integrante activo del grupo de origen")
    assignment_id = str(uuid4())
    await db.front_group_assignments.insert_one({"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": payload.to_group_id, "person_id": payload.person_id, "role": payload.role, "active": True, "started_at": now, "ended_at": None, "notes": payload.reason, "assigned_by_user_id": current_user["user_id"], "created_at": now})
    await audit(group_id, current_user, "member_transferred_out", {"person_id": payload.person_id, "to_group_id": payload.to_group_id, "reason": payload.reason})
    await audit(payload.to_group_id, current_user, "member_transferred_in", {"person_id": payload.person_id, "from_group_id": group_id, "reason": payload.reason})
    return {"transferred": True}


@router.post("/{group_id}/archive", response_model=dict)
async def archive_front_group(group_id: str, payload: FrontGroupArchive, current_user: dict = Depends(require_manage)):
    await assert_group_scope(group_id, current_user, leader_required=True)
    dependents = await db.front_groups.count_documents({"parent_group_id": group_id, "status": {"$ne": "archived"}})
    if dependents:
        raise HTTPException(status_code=409, detail={"message": "No se puede archivar: tiene Grupos Frontales dependientes activos", "dependent_group_count": dependents})
    active_processes = await db.process_enrollments.count_documents({"front_group_id": group_id, "process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}})
    if active_processes:
        raise HTTPException(status_code=409, detail={"message": "No se puede archivar: tiene procesos de Consolidación activos", "active_process_count": active_processes})
    now = now_utc()
    await db.front_groups.update_one({"front_group_id": group_id}, {"$set": {"status": "archived", "archived_at": now, "archived_by_user_id": current_user["user_id"], "archive_reason": payload.reason, "updated_at": now}})
    await audit(group_id, current_user, "group_archived", {"reason": payload.reason})
    return serialize(await load_group(db, group_id, include_archived=True))


@router.get("/{group_id}/history", response_model=dict)
async def group_history(group_id: str, current_user: dict = Depends(require_read)):
    await assert_group_scope(group_id, current_user)
    events = await db.front_group_audit_events.find({"front_group_id": group_id}, {"_id": 0}).sort("occurred_at", -1).to_list(500)
    for item in events: item["actor_name"] = await person_name(item.get("actor_person_id"))
    return {"items": serialize(events), "total": len(events)}


@router.get("/{group_id}/person-search", response_model=dict)
async def person_search(group_id: str, search: str = Query(""), current_user: dict = Depends(require_manage)):
    """Búsqueda mínima (solo nombre/person_id) para alta rápida dentro del
    flujo de Grupos Frontales; no pasa por /api/core/persons."""
    await assert_group_scope(group_id, current_user, level="support")
    clean = search.strip()
    if len(clean) < 2: return {"items": []}
    norm = normalize_text(clean)
    docs = await db.persons.find({"search_key": {"$regex": re.escape(norm)}, "is_archived": {"$ne": True}}, {"nombre": 1, "apellido": 1, "person_number": 1}).limit(15).to_list(15)
    return {"items": [{"person_id": str(doc["_id"]), "nombre": doc.get("nombre"), "apellido": doc.get("apellido"), "person_number": doc.get("person_number")} for doc in docs]}


@router.post("/{group_id}/quick-person", response_model=dict, status_code=201)
async def quick_person(group_id: str, payload: GroupQuickPerson, current_user: dict = Depends(require_manage)):
    """C4: alta rápida de Persona 360 sin salir del flujo de Grupos Frontales.
    Coincidencia FUERTE bloquea y ofrece usar la existente; POSIBLE exige
    confirm_distinct_person + motivo (auditado)."""
    await assert_group_scope(group_id, current_user, level="support")
    result = await quick_create_person(db, payload, current_user["user_id"], "front_group")
    if result["status"] == "strong_match":
        raise HTTPException(status_code=409, detail={"message": "Ya existe una Persona 360 que coincide; use el perfil encontrado.", "candidates": result["candidates"]})
    if result["status"] == "possible_match":
        raise HTTPException(status_code=409, detail={"message": "Hay una Persona con nombre parecido. Use la existente o confirme que es alguien distinto (con un motivo).", "candidates": result["candidates"], "requires_confirmation": True})
    person = result["person"]; now = now_utc()
    existing_assignment = await db.front_group_assignments.find_one({"front_group_id": group_id, "person_id": person["person_id"], "role": payload.role, "active": True}, {"_id": 1})
    if payload.assign and not existing_assignment:
        assignment_id = str(uuid4())
        await db.front_group_assignments.insert_one({"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id, "person_id": person["person_id"], "role": payload.role, "notes": payload.notes, "active": True, "started_at": now, "ended_at": None, "assigned_by_user_id": current_user["user_id"], "created_at": now})
    await audit(group_id, current_user, "member_quick_created" if payload.assign else "person_quick_created_for_designation", {"person_id": person["person_id"], "role": payload.role, "created": result["created"], "assigned": payload.assign})
    return {"person": person, "assignment_added": payload.assign and not bool(existing_assignment)}


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
    await db.front_groups.create_index([("parent_group_id", 1), ("primary_leader_person_id", 1)])
    await db.front_group_assignments.create_index("assignment_id", unique=True)
    await db.front_group_assignments.create_index([("front_group_id", 1), ("person_id", 1), ("role", 1), ("active", 1)])
    await db.mentor_qualifications.create_index([("person_id", 1), ("front_group_id", 1)], unique=True)
    await db.front_group_audit_events.create_index("event_id", unique=True)
    await db.front_group_audit_events.create_index([("front_group_id", 1), ("occurred_at", -1)])
    await db.person_contacts.create_index("valor_normalizado")