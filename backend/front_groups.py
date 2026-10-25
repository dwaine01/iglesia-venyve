"""Grupos Frontales: árbol recursivo, membresías canónicas y scope jerárquico."""
import re
import asyncio
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from access_control import (
    FRONT_GROUPS_MANAGE, FRONT_GROUPS_VIEW, MENTOR_QUALIFICATIONS_MANAGE,
    has_capability, is_general_coordinator, is_global_pastoral_authority,
)
from front_group_tree import (
    build_tree, direct_assignments, group_in_scope as tree_group_in_scope, lineage_for_parent,
    load_group, manageable_group_ids, member_group_ids, readable_group_ids, support_group_ids, move_subtree,
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
    co_leader_person_id: Optional[str] = None
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
    co_leader_person_id: Optional[str] = None
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


class DeleteReason(BaseModel):
    reason: str = Field(min_length=3, max_length=600)


async def record_admin_deletion(collection: str, target_id: str, current_user: dict, reason: str, detail: dict) -> None:
    """Borrado total (admin): el documento desaparece, pero queda este
    registro de auditoría independiente (quién, cuándo, por qué, qué se
    borró) para que nunca sea un borrado sin rastro."""
    await db.admin_deletions.insert_one({
        "_id": str(uuid4()), "collection": collection, "target_id": target_id, "reason": reason,
        "detail": serialize(detail), "actor_user_id": current_user["user_id"], "actor_person_id": current_user.get("person_id"),
        "deleted_at": now_utc(),
    })


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


async def require_admin_delete(current_user: dict = Depends(get_current_user)) -> dict:
    """Borrar (no archivar) es una potestad de administrador: autoridad
    pastoral global o capability `front_groups.manage` — un líder/colíder de
    rama real NO puede borrar, solo archivar."""
    if is_global_pastoral_authority(current_user) or has_capability(current_user, FRONT_GROUPS_MANAGE):
        return current_user
    raise HTTPException(status_code=403, detail="Solo la autoridad pastoral o un administrador de Grupos Frontales puede borrar")


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


async def person_names(person_ids) -> dict[str, Optional[str]]:
    """`person_name` para varias personas con una sola consulta."""
    oids = [ObjectId(item) for item in {item for item in person_ids if item} if ObjectId.is_valid(item)]
    if not oids: return {}
    names = {}
    async for person in db.persons.find({"_id": {"$in": oids}}, {"nombre": 1, "apellido": 1}):
        names[str(person["_id"])] = " ".join(part for part in [person.get("nombre"), person.get("apellido")] if part) or None
    return names


_UNSET = object()


async def group_summary(group: dict, current_user: dict, manageable=_UNSET, supportable=_UNSET) -> dict:
    """Resumen de un grupo. `manageable`/`supportable` se pueden pasar ya
    calculados cuando se resumen muchos grupos para la misma cuenta."""
    item = serialize(group)
    if manageable is _UNSET:
        manageable = await manageable_group_ids(db, current_user)
    if supportable is _UNSET:
        supportable = await support_group_ids(db, current_user)
    item["primary_leader_name"], item["co_leader_name"], item["team_count"], item["active_process_count"] = await asyncio.gather(
        person_name(group.get("primary_leader_person_id")),
        person_name(group.get("co_leader_person_id")),
        db.front_group_assignments.count_documents({"front_group_id": group["front_group_id"], "active": True}),
        db.process_enrollments.count_documents({"front_group_id": group["front_group_id"], "process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}}),
    )
    item["display_name"] = item.get("name") or (f"Equipo de {item['primary_leader_name']}" if item["primary_leader_name"] else "Equipo sin líder")
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
    items = await visible_group_items(query, current_user)
    return {"items": items, "total": len(items)}


@router.get("/tree", response_model=dict)
async def front_group_tree(current_user: dict = Depends(require_read)):
    items = await visible_group_items({"status": {"$ne": "archived"}}, current_user)
    return {"items": build_tree(items), "total": len(items)}


async def visible_group_items(query: dict, current_user: dict) -> list[dict]:
    """Grupos legibles con su resumen completo + los grupos donde solo es
    integrante, en vista mínima (nombre, líder y colíder; sin conteos)."""
    allowed = await readable_group_ids(db, current_user)
    member_only: set[str] = set()
    if allowed is not None:
        member_only = await member_group_ids(db, current_user.get("person_id")) - allowed
        query = {**query, "front_group_id": {"$in": [*allowed, *member_only]}}
    groups = await db.front_groups.find(query, {"_id": 0}).sort([("depth", 1), ("rotation_order", 1), ("name", 1)]).to_list(10000)
    manageable, supportable = await asyncio.gather(manageable_group_ids(db, current_user), support_group_ids(db, current_user))

    async def group_item(group: dict) -> dict:
        if group["front_group_id"] in member_only:
            item = await member_view(group)
            item.update({"parent_group_id": group.get("parent_group_id"), "depth": group.get("depth", 0), "rotation_order": group.get("rotation_order", 0), "permissions": {"manage": False, "support": False}})
            return item
        return await group_summary(group, current_user, manageable, supportable)

    items = []
    for start in range(0, len(groups), 25):
        items.extend(await asyncio.gather(*(group_item(group) for group in groups[start:start + 25])))
    return items


@router.post("", response_model=dict, status_code=201)
async def create_front_group(payload: FrontGroupCreate, current_user: dict = Depends(require_manage)):
    if not payload.parent_group_id and not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Solo la autoridad pastoral puede crear un Grupo Frontal raíz")
    if payload.parent_group_id:
        await assert_group_scope(payload.parent_group_id, current_user, leader_required=True)
    if payload.co_leader_person_id and payload.co_leader_person_id == payload.primary_leader_person_id:
        raise HTTPException(status_code=422, detail="El líder y el colíder deben ser personas distintas")
    if payload.primary_leader_person_id:
        await load_person(payload.primary_leader_person_id)
        if not await db.users.find_one({"person_id": payload.primary_leader_person_id, "is_active": {"$ne": False}}, {"_id": 1}):
            raise HTTPException(status_code=409, detail="El líder principal necesita una cuenta activa en Plataforma 360")
    if payload.co_leader_person_id:
        await load_person(payload.co_leader_person_id)
    now = now_utc(); group_id = str(uuid4()); lineage = await lineage_for_parent(db, group_id, payload.parent_group_id)
    document = {
        "_id": group_id, "front_group_id": group_id,
        **payload.model_dump(exclude={"parent_group_id", "linked_structures", "primary_leader_person_id", "co_leader_person_id", "leadership_reason"}), **lineage,
        "linked_structures": [item.model_dump() for item in payload.linked_structures],
        "primary_leader_person_id": payload.primary_leader_person_id, "co_leader_person_id": payload.co_leader_person_id, "tree_version": 1,
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
        # Aditivo: antes solo las rutas /leader y /co-leader otorgaban la
        # capability; un líder designado AQUÍ (al crear) no la recibía y
        # podía no ver el acceso a su propio panel.
        await ensure_front_group_capability(payload.primary_leader_person_id)
    if payload.co_leader_person_id:
        co_assignment_id = str(uuid4())
        await db.front_group_assignments.insert_one({
            "_id": co_assignment_id, "assignment_id": co_assignment_id, "front_group_id": group_id,
            "person_id": payload.co_leader_person_id, "role": "co_leader", "active": True,
            "started_at": now, "ended_at": None, "notes": payload.leadership_reason or "Asignación al crear la rama",
            "assigned_by_user_id": current_user["user_id"], "created_at": now,
        })
        await ensure_front_group_capability(payload.co_leader_person_id)
    await audit(group_id, current_user, "group_created", {"parent_group_id": payload.parent_group_id, "co_leader_person_id": payload.co_leader_person_id})
    return serialize(document)


async def member_view(group: dict) -> dict:
    """Lo único que ve un simple integrante de su grupo: nombre, líder y
    colíder. Nunca la lista de integrantes ni sus procesos."""
    leader_name = await person_name(group.get("primary_leader_person_id"))
    return {
        "front_group_id": group["front_group_id"], "name": group.get("name"),
        "display_name": group.get("name") or (f"Equipo de {leader_name}" if leader_name else "Equipo sin líder"),
        "status": group.get("status"), "pastoral_main": bool(group.get("pastoral_main")),
        "primary_leader_name": leader_name, "co_leader_name": await person_name(group.get("co_leader_person_id")),
        "member_view": True,
    }


@router.get("/{group_id}", response_model=dict)
async def front_group_detail(group_id: str, current_user: dict = Depends(require_read)):
    if not await group_in_scope(group_id, current_user) and group_id in await member_group_ids(db, current_user.get("person_id")):
        return await member_view(await load_group(db, group_id))
    group = await assert_group_scope(group_id, current_user)
    assignments = await db.front_group_assignments.find({"front_group_id": group_id}, {"_id": 0}).sort("started_at", -1).to_list(2000)
    for item in assignments:
        person = await db.persons.find_one({"_id": ObjectId(item["person_id"])}, {"nombre": 1, "apellido": 1, "auth_user_id": 1}) if ObjectId.is_valid(item["person_id"]) else None
        item["person_name"] = " ".join(part for part in [(person or {}).get("nombre"), (person or {}).get("apellido")] if part) or None
        item["has_account"] = bool((person or {}).get("auth_user_id"))
    child_count = await db.front_groups.count_documents({"parent_group_id": group_id, "status": {"$ne": "archived"}})
    group = await group_summary(group, current_user)
    group["assignments"] = serialize(assignments)
    parent = await db.front_groups.find_one({"front_group_id": group.get("parent_group_id")}, {"_id": 0, "name": 1, "pastoral_main": 1}) if group.get("parent_group_id") else None
    group["parent_group_name"] = (parent or {}).get("name")
    group["parent_is_pastoral_main"] = bool((parent or {}).get("pastoral_main"))
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
    """Colíder del equipo de liderazgo: ve y registra en el grupo y sus
    ramas (soporte), pero nunca gestiona estructura (eso sigue siendo del
    Líder o una autoridad superior)."""
    await assert_group_scope(group_id, current_user, leader_required=True); await load_person(payload.person_id)
    group = await load_group(db, group_id)
    if group.get("primary_leader_person_id") == payload.person_id:
        raise HTTPException(status_code=422, detail="El líder y el colíder deben ser personas distintas")
    return serialize(await replace_co_leader(group_id, payload.person_id, payload.reason, current_user, now_utc()))


async def replace_co_leader(group_id: str, person_id: str, reason: str, current_user: dict, now: datetime) -> dict:
    """Un solo colíder activo por grupo: cierra el anterior y abre el nuevo."""
    await db.front_group_assignments.update_many({"front_group_id": group_id, "role": "co_leader", "active": True}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "end_reason": reason}})
    assignment_id = str(uuid4())
    assignment = {"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id, "person_id": person_id, "role": "co_leader", "active": True, "started_at": now, "ended_at": None, "notes": reason, "assigned_by_user_id": current_user["user_id"], "created_at": now}
    await db.front_group_assignments.insert_one(assignment)
    await db.front_groups.update_one({"front_group_id": group_id}, {"$set": {"co_leader_person_id": person_id, "updated_at": now, "updated_by_user_id": current_user["user_id"]}})
    await ensure_front_group_capability(person_id)
    await audit(group_id, current_user, "co_leader_assigned", {"assignment_id": assignment_id, "person_id": person_id, "reason": reason})
    return assignment


@router.post("/{parent_id}/designations", response_model=dict, status_code=201)
async def create_designation(parent_id: str, payload: DesignationCreate, current_user: dict = Depends(require_manage)):
    """A3/A4: designa un equipo de liderazgo Líder+Colíder para un grupo dependiente de
    `parent_id`. Crea el grupo dependiente en el acto (status=pending_formation);
    'Conformar mi grupo' reutiliza ese MISMO grupo, nunca crea otro."""
    await assert_group_scope(parent_id, current_user, leader_required=True)
    return await designate(parent_id, payload, current_user)


async def designate(parent_id: str, payload: "DesignationCreate", current_user: dict) -> dict:
    """Núcleo de la designación (el permiso lo valida quien llama)."""
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
        await db.front_group_assignments.insert_one({"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": parent_id, "person_id": person_id, "role": "member", "active": True, "started_at": now, "ended_at": None, "notes": "Agregado al designar equipo de liderazgo", "assigned_by_user_id": current_user["user_id"], "created_at": now})
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
    await db.front_group_assignments.insert_one({"_id": leader_assignment_id, "assignment_id": leader_assignment_id, "front_group_id": group_id, "person_id": payload.leader_person_id, "role": "leader", "active": True, "started_at": now, "ended_at": None, "notes": payload.reason or "Designación de equipo de liderazgo", "assigned_by_user_id": current_user["user_id"], "created_at": now})
    if payload.co_leader_person_id:
        co_assignment_id = str(uuid4())
        await db.front_group_assignments.insert_one({"_id": co_assignment_id, "assignment_id": co_assignment_id, "front_group_id": group_id, "person_id": payload.co_leader_person_id, "role": "co_leader", "active": True, "started_at": now, "ended_at": None, "notes": payload.reason or "Designación de equipo de liderazgo", "assigned_by_user_id": current_user["user_id"], "created_at": now})
    await ensure_front_group_capability(payload.leader_person_id)
    await ensure_front_group_capability(payload.co_leader_person_id)
    await audit(group_id, current_user, "group_designated", {"parent_group_id": parent_id, "leader_person_id": payload.leader_person_id, "co_leader_person_id": payload.co_leader_person_id, "reason": payload.reason})
    await audit(parent_id, current_user, "child_designated", {"child_group_id": group_id, "leader_person_id": payload.leader_person_id, "co_leader_person_id": payload.co_leader_person_id, "reason": payload.reason})
    return await group_summary(document, current_user)


class RosterEntry(BaseModel):
    """Una persona sola (individuo) o dos personas (equipo)."""
    person_ids: list[str] = Field(min_length=1, max_length=2)


class RosterSave(BaseModel):
    entries: list[RosterEntry] = Field(default_factory=list, max_length=300)


class LeaderPrivilege(BaseModel):
    person_id: str
    co_leader_person_id: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=600)


async def user_name(user_id: Optional[str]) -> Optional[str]:
    if not user_id or not ObjectId.is_valid(user_id): return None
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"nombre": 1})
    return (user or {}).get("nombre")


async def leader_privilege_for(group_id: str, person_id: str) -> Optional[dict]:
    """Privilegio 'Líder de Grupo Frontal' que esta persona recibió desde
    este grupo (= designación de un grupo dependiente)."""
    child = await db.front_groups.find_one(
        {"parent_group_id": group_id, "status": {"$ne": "archived"}, "$or": [{"primary_leader_person_id": person_id}, {"co_leader_person_id": person_id}]},
        {"_id": 0}, sort=[("created_at", 1)],
    )
    if not child: return None
    return {
        "front_group_id": child["front_group_id"], "name": child.get("name"), "status": child.get("status"),
        "as": "leader" if child.get("primary_leader_person_id") == person_id else "co_leader",
        "assigned_by_name": await user_name(child.get("designated_by_user_id") or child.get("created_by_user_id")),
        "assigned_at": serialize(child.get("designated_at") or child.get("created_at")),
    }


async def leader_privileges_for(group_id: str, person_ids: list[str]) -> dict[str, dict]:
    """`leader_privilege_for` para todo el roster: una consulta de grupos hijos
    (el más antiguo por persona, igual que la versión individual)."""
    wanted = set(person_ids)
    if not wanted: return {}
    children = await db.front_groups.find(
        {"parent_group_id": group_id, "status": {"$ne": "archived"}, "$or": [{"primary_leader_person_id": {"$in": list(wanted)}}, {"co_leader_person_id": {"$in": list(wanted)}}]},
        {"_id": 0},
    ).sort("created_at", 1).to_list(2000)
    first_child: dict[str, dict] = {}
    for child in children:
        for person_id in (child.get("primary_leader_person_id"), child.get("co_leader_person_id")):
            if person_id in wanted: first_child.setdefault(person_id, child)
    result = {}
    for person_id, child in first_child.items():
        result[person_id] = {
            "front_group_id": child["front_group_id"], "name": child.get("name"), "status": child.get("status"),
            "as": "leader" if child.get("primary_leader_person_id") == person_id else "co_leader",
            "assigned_by_name": await user_name(child.get("designated_by_user_id") or child.get("created_by_user_id")),
            "assigned_at": serialize(child.get("designated_at") or child.get("created_at")),
        }
    return result


async def roster_view(group: dict) -> dict:
    """Integrantes del grupo organizados en individuos y equipos."""
    group_id = group["front_group_id"]
    assignments = await db.front_group_assignments.find({"front_group_id": group_id, "role": "member", "active": True}, {"_id": 0}).to_list(2000)
    # Orden en que se registró la lista (roster_order); los anteriores, por fecha de alta.
    assignments.sort(key=lambda item: (item.get("roster_order") is None, item.get("roster_order") or 0, item.get("started_at") or now_utc()))
    person_ids = [item["person_id"] for item in assignments]
    names = await person_names(person_ids)
    with_account = set(await db.users.distinct("person_id", {"person_id": {"$in": person_ids}, "is_active": {"$ne": False}})) if person_ids else set()
    privileges = await leader_privileges_for(group_id, person_ids)
    entries, by_pair = [], {}
    for item in assignments:
        card = {"person_id": item["person_id"], "name": names.get(item["person_id"]),
                "has_account": item["person_id"] in with_account,
                "leader_privilege": privileges.get(item["person_id"])}
        pair_id = item.get("pair_id")
        if pair_id and pair_id in by_pair:
            by_pair[pair_id]["people"].append(card)
            continue
        entry = {"type": "pair" if pair_id else "individual", "pair_id": pair_id, "people": [card]}
        if pair_id: by_pair[pair_id] = entry
        entries.append(entry)
    for entry in entries:  # un equipo con un solo integrante activo (el otro salió) se muestra como individuo
        if entry["type"] == "pair" and len(entry["people"]) < 2: entry["type"] = "individual"
    pairs = sum(1 for entry in entries if entry["type"] == "pair")
    return {
        "front_group_id": group_id, "entries": entries,
        "totals": {"people": len(assignments), "pairs": pairs, "individuals": len(entries) - pairs},
    }


@router.get("/{group_id}/roster", response_model=dict)
async def get_roster(group_id: str, current_user: dict = Depends(require_read)):
    group = await assert_group_scope(group_id, current_user, level="support")
    return await roster_view(group)


@router.put("/{group_id}/roster", response_model=dict)
async def save_roster(group_id: str, payload: RosterSave, current_user: dict = Depends(require_manage)):
    """Guarda la lista confirmada (individuos y equipos). Quien no esté en la
    lista deja de ser integrante (con historial); nunca duplica personas."""
    group = await assert_group_scope(group_id, current_user, leader_required=True)
    return await apply_roster(group, payload, current_user)


async def apply_roster(group: dict, payload: RosterSave, current_user: dict) -> dict:
    group_id = group["front_group_id"]
    leadership = {item for item in [group.get("primary_leader_person_id"), group.get("co_leader_person_id")] if item}
    desired: dict[str, Optional[tuple]] = {}
    for entry in payload.entries:
        if len(set(entry.person_ids)) != len(entry.person_ids):
            raise HTTPException(status_code=422, detail="Un equipo debe tener dos personas distintas")
        for person_id in entry.person_ids:
            if person_id in desired:
                raise HTTPException(status_code=422, detail="Una misma persona aparece dos veces en la lista")
            if person_id in leadership:
                raise HTTPException(status_code=422, detail="El líder y el colíder del grupo no se agregan como integrantes")
            await load_person(person_id)
            desired[person_id] = tuple(sorted(entry.person_ids)) if len(entry.person_ids) == 2 else None
    now = now_utc()
    current = await db.front_group_assignments.find({"front_group_id": group_id, "role": "member", "active": True}, {"_id": 0}).to_list(2000)
    current_by_person = {item["person_id"]: item for item in current}
    for item in current:
        if item["person_id"] not in desired:
            await db.front_group_assignments.update_one({"assignment_id": item["assignment_id"]}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "end_reason": "Retirado de la lista del grupo"}})
    pair_ids: dict[tuple, str] = {}
    for members in {value for value in desired.values() if value}:
        existing = [current_by_person.get(person_id, {}).get("pair_id") for person_id in members]
        pair_ids[members] = existing[0] if existing[0] and existing[0] == existing[1] else str(uuid4())
    added = 0
    for order, (person_id, members) in enumerate(desired.items()):
        pair_id = pair_ids.get(members) if members else None
        existing = current_by_person.get(person_id)
        if existing:
            if existing.get("pair_id") != pair_id or existing.get("roster_order") != order:
                await db.front_group_assignments.update_one({"assignment_id": existing["assignment_id"]}, {"$set": {"pair_id": pair_id, "roster_order": order, "updated_at": now}})
            continue
        assignment_id = str(uuid4())
        await db.front_group_assignments.insert_one({"_id": assignment_id, "assignment_id": assignment_id, "front_group_id": group_id, "person_id": person_id, "role": "member", "pair_id": pair_id, "roster_order": order, "active": True, "started_at": now, "ended_at": None, "notes": "Agregado a la lista del grupo", "assigned_by_user_id": current_user["user_id"], "created_at": now})
        added += 1
    await audit(group_id, current_user, "roster_saved", {"people": len(desired), "pairs": len(pair_ids), "added": added, "removed": len([item for item in current if item["person_id"] not in desired])})
    return await roster_view(group)


@router.post("/{group_id}/leader-privilege", response_model=dict, status_code=201)
async def grant_leader_privilege(group_id: str, payload: LeaderPrivilege, current_user: dict = Depends(require_manage)):
    """Privilegio 'Líder de Grupo Frontal' desde la lista del grupo. Reutiliza
    la designación: crea el grupo dependiente pendiente → la persona ve en su
    portal 'Crear mi grupo frontal'. En un equipo se puede elegir a uno como
    líder o a ambos (uno líder y el otro colíder del nuevo grupo)."""
    await assert_group_scope(group_id, current_user, leader_required=True)
    for person_id in [payload.person_id, *([payload.co_leader_person_id] if payload.co_leader_person_id else [])]:
        if not await db.front_group_assignments.find_one({"front_group_id": group_id, "person_id": person_id, "role": "member", "active": True}, {"_id": 1}):
            raise HTTPException(status_code=422, detail="Solo se asigna como líder a integrantes de este grupo")
    if not await db.users.find_one({"person_id": payload.person_id, "is_active": {"$ne": False}}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="La persona necesita una cuenta activa en Plataforma 360 para ver y crear su grupo")
    return await create_designation(group_id, DesignationCreate(
        leader_person_id=payload.person_id, co_leader_person_id=payload.co_leader_person_id,
        reason=payload.reason or "Asignado como Líder de Grupo Frontal",
    ), current_user)


@router.put("/{group_id}/conform", response_model=dict)
async def conform_group(group_id: str, payload: ConformGroup, current_user: dict = Depends(get_current_user)):
    """A4: el líder DESIGNADO abre 'Conformar mi grupo frontal'. Reutiliza el
    grupo creado por la designación (status pending_formation→active); no crea
    otro. Pulsar dos veces es seguro (no duplica integrantes)."""
    group = await load_group(db, group_id)
    is_designated_leader = bool(current_user.get("person_id")) and await db.front_group_assignments.find_one({"front_group_id": group_id, "person_id": current_user.get("person_id"), "role": "leader", "active": True}, {"_id": 1})
    if not is_designated_leader and not is_global_pastoral_authority(current_user) and not has_capability(current_user, FRONT_GROUPS_MANAGE):
        # También su líder superior (lidera un grupo por encima) o el coordinador general.
        from front_group_structure import leads_above
        if not (is_general_coordinator(current_user) or await leads_above(group, current_user)):
            raise HTTPException(status_code=403, detail="Solo el líder designado, su líder superior, la pastora o el coordinador general pueden formar este grupo")
    leader_person_id = group.get("primary_leader_person_id")
    if payload.co_leader_person_id:
        if payload.co_leader_person_id == leader_person_id:
            raise HTTPException(status_code=422, detail="El líder y el colíder deben ser personas distintas")
        await load_person(payload.co_leader_person_id)
    for person_id in payload.member_person_ids:
        await load_person(person_id)
    now = now_utc()
    update = {"status": "active", "updated_at": now, "updated_by_user_id": current_user["user_id"]}
    if payload.name: update["name"] = payload.name
    await db.front_groups.update_one({"front_group_id": group_id}, {"$set": update})
    if payload.co_leader_person_id and payload.co_leader_person_id != group.get("co_leader_person_id"):
        await replace_co_leader(group_id, payload.co_leader_person_id, "Elegido al conformar el grupo", current_user, now)
    added = 0
    for person_id in payload.member_person_ids:
        if person_id in {leader_person_id, payload.co_leader_person_id}:
            continue
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


@router.get("/{group_id}/delete-preview", response_model=dict)
async def preview_delete_front_group(group_id: str, current_user: dict = Depends(require_admin_delete)):
    """Conteo exacto de lo que se borraría (y si hay algo que lo bloquea),
    para confirmar ANTES de un borrado total y permanente."""
    group = await load_group(db, group_id, include_archived=True)
    dependents = await db.front_groups.count_documents({"parent_group_id": group_id, "status": {"$ne": "archived"}})
    active_processes = await db.process_enrollments.count_documents({"front_group_id": group_id, "process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}})
    assignments = await db.front_group_assignments.count_documents({"front_group_id": group_id})
    return {
        "name": group.get("name"), "assignments": assignments, "dependent_group_count": dependents, "active_process_count": active_processes,
        "blocked": bool(dependents or active_processes),
    }


@router.delete("/{group_id}", response_model=dict)
async def delete_front_group(group_id: str, payload: DeleteReason, current_user: dict = Depends(require_admin_delete)):
    """Borrado TOTAL y permanente (decisión del dueño, a diferencia de
    archivar): el grupo y toda su membresía/historial propio desaparecen de
    verdad. Mismas salvaguardas estructurales que archivar — bloquea si tiene
    subramas o procesos de Consolidación activos debajo — para no dejar
    huérfanos; primero hay que borrar/mover esas ramas o procesos."""
    group = await load_group(db, group_id, include_archived=True)
    dependents = await db.front_groups.count_documents({"parent_group_id": group_id, "status": {"$ne": "archived"}})
    if dependents:
        raise HTTPException(status_code=409, detail={"message": "No se puede borrar: tiene Grupos Frontales dependientes activos", "dependent_group_count": dependents})
    active_processes = await db.process_enrollments.count_documents({"front_group_id": group_id, "process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}})
    if active_processes:
        raise HTTPException(status_code=409, detail={"message": "No se puede borrar: tiene procesos de Consolidación activos", "active_process_count": active_processes})
    assignments_deleted = (await db.front_group_assignments.delete_many({"front_group_id": group_id})).deleted_count
    await db.front_group_audit_events.delete_many({"front_group_id": group_id})
    await db.mentor_qualifications.delete_many({"front_group_id": group_id})
    await db.front_groups.delete_one({"front_group_id": group_id})
    await record_admin_deletion("front_groups", group_id, current_user, payload.reason, {"name": group.get("name"), "assignments_deleted": assignments_deleted})
    return {"deleted": True, "front_group_id": group_id, "name": group.get("name")}


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
    await db.admin_deletions.create_index([("collection", 1), ("deleted_at", -1)])