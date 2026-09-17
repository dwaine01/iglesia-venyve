"""Elegibilidad y promoción ministerial a Líder, independiente de users.rol."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import LEADERSHIP_PROMOTE, LEADERSHIP_REQUIREMENTS_MANAGE, LEADERSHIP_VIEW, has_capability, is_global_pastoral_authority
from front_groups import assert_group_scope, group_in_scope
from server import db, get_current_user


router = APIRouter(prefix="/api/leadership", tags=["leadership"])


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


RequirementSource = Literal["membership_active", "formation_completed", "cap_completed", "ministry_service_active", "manual"]


class RequirementCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=1200)
    source_type: RequirementSource
    required: bool = True
    active: bool = True
    order: int = Field(default=1, ge=1, le=500)


class RequirementUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=1200)
    source_type: Optional[RequirementSource] = None
    required: Optional[bool] = None
    active: Optional[bool] = None
    order: Optional[int] = Field(default=None, ge=1, le=500)


class RequirementEvidence(BaseModel):
    front_group_id: Optional[str] = None
    status: Literal["met", "pending", "not_met"]
    notes: Optional[str] = Field(default=None, max_length=1200)


class PromotionInput(BaseModel):
    front_group_id: Optional[str] = None
    observations: str = Field(min_length=2, max_length=2000)


def require_read(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user) and not any(has_capability(current_user, capability) for capability in (LEADERSHIP_VIEW, LEADERSHIP_PROMOTE, LEADERSHIP_REQUIREMENTS_MANAGE)):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar Liderazgo")
    return current_user


def require_requirements_manager(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, LEADERSHIP_REQUIREMENTS_MANAGE):
        raise HTTPException(status_code=403, detail="Sin permiso para configurar requisitos de liderazgo")
    return current_user


async def load_person(person_id: str) -> dict:
    if not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=400, detail="person_id inválido")
    person = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}}, {"_id": 0, "nombre": 1, "apellido": 1, "person_number": 1})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return person


async def assert_promotion_scope(person_id: str, front_group_id: Optional[str], current_user: dict) -> None:
    if is_global_pastoral_authority(current_user):
        if front_group_id:
            await assert_group_scope(front_group_id, current_user)
        return
    if not has_capability(current_user, LEADERSHIP_PROMOTE):
        raise HTTPException(status_code=403, detail="Sin permiso para promover liderazgo")
    if not front_group_id or not await group_in_scope(front_group_id, current_user, leader_required=True):
        raise HTTPException(status_code=403, detail="La promoción está fuera de su Grupo Frontal")
    belongs = await db.front_group_assignments.find_one({"front_group_id": front_group_id, "person_id": person_id, "active": True}, {"_id": 1})
    reached = await db.process_enrollments.find_one({"front_group_id": front_group_id, "person_id": person_id, "process_key": "consolidation"}, {"_id": 1})
    if not belongs and not reached:
        raise HTTPException(status_code=403, detail="La Persona no pertenece al ámbito de este Grupo Frontal")


async def requirement_status(person_id: str, requirement: dict, front_group_id: Optional[str]) -> dict:
    source = requirement["source_type"]
    status = "not_met"; evidence = None
    if source == "membership_active":
        item = await db.person_memberships.find_one({"person_id": person_id, "status": "active", "acceptance_signed_at": {"$exists": True}}, {"_id": 0, "member_number": 1, "acceptance_signed_at": 1})
        status = "met" if item else "not_met"; evidence = serialize(item)
    elif source == "formation_completed":
        complete = await db.process_enrollments.find_one({"person_id": person_id, "process_key": {"$in": ["mentorship", "discipleship"]}, "status": "completed"}, {"_id": 0, "process_key": 1, "completed_at": 1})
        active = await db.process_enrollments.find_one({"person_id": person_id, "process_key": {"$in": ["mentorship", "discipleship"]}, "status": {"$in": ["planned", "active", "paused"]}}, {"_id": 0, "process_key": 1, "progress_pct": 1})
        status = "met" if complete else "pending" if active else "not_met"; evidence = serialize(complete or active)
    elif source == "cap_completed":
        item = await db.cap_assessments.find_one({"person_id": person_id}, {"_id": 0, "status": 1, "selected_door_key": 1})
        status = "met" if item and item.get("status") == "completed" else "pending" if item else "not_met"; evidence = serialize(item)
    elif source == "ministry_service_active":
        ministry = await db.ministry_assignments.find_one({"person_id": person_id, "activo": True}, {"_id": 0, "ministry_id": 1, "role": 1})
        door = await db.door_assignments.find_one({"person_id": person_id, "status": {"$in": ["active", "activated"]}}, {"_id": 0, "door_key": 1, "status": 1})
        cell = await db.cell_role_assignments.find_one({"person_id": person_id, "active": True}, {"_id": 0, "cell_id": 1, "role": 1})
        status = "met" if ministry or door or cell else "not_met"; evidence = serialize(ministry or door or cell)
    else:
        manual = await db.leadership_requirement_evidence.find_one({"person_id": person_id, "requirement_id": requirement["requirement_id"], "front_group_id": front_group_id}, {"_id": 0}, sort=[("evaluated_at", -1)])
        status = manual.get("status") if manual else "not_met"; evidence = serialize(manual)
    return {**serialize(requirement), "status": status, "evidence": evidence}


async def eligibility_snapshot(person_id: str, front_group_id: Optional[str]) -> dict:
    requirements = await db.leadership_requirement_catalog.find({"active": True}, {"_id": 0}).sort("order", 1).to_list(500)
    items = [await requirement_status(person_id, requirement, front_group_id) for requirement in requirements]
    blocking = [item for item in items if item.get("required") and item["status"] != "met"]
    return {"eligible": not blocking, "requirements": items, "blocking_count": len(blocking)}


@router.get("/requirements", response_model=dict)
async def list_requirements(current_user: dict = Depends(require_read)):
    items = await db.leadership_requirement_catalog.find({}, {"_id": 0}).sort("order", 1).to_list(500)
    return {"items": serialize(items), "total": len(items)}


@router.post("/requirements", response_model=dict, status_code=201)
async def create_requirement(payload: RequirementCreate, current_user: dict = Depends(require_requirements_manager)):
    now = now_utc(); requirement_id = str(uuid4())
    document = {"_id": requirement_id, "requirement_id": requirement_id, **payload.model_dump(), "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.leadership_requirement_catalog.insert_one(document)
    return serialize(document)


@router.put("/requirements/{requirement_id}", response_model=dict)
async def update_requirement(requirement_id: str, payload: RequirementUpdate, current_user: dict = Depends(require_requirements_manager)):
    update = payload.model_dump(exclude_none=True)
    update.update({"updated_by_user_id": current_user["user_id"], "updated_at": now_utc()})
    result = await db.leadership_requirement_catalog.update_one({"requirement_id": requirement_id}, {"$set": update})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Requisito no encontrado")
    return serialize(await db.leadership_requirement_catalog.find_one({"requirement_id": requirement_id}, {"_id": 0}))


@router.delete("/requirements/{requirement_id}", response_model=dict)
async def remove_requirement(requirement_id: str, current_user: dict = Depends(require_requirements_manager)):
    now = now_utc()
    result = await db.leadership_requirement_catalog.update_one(
        {"requirement_id": requirement_id},
        {"$set": {"active": False, "removed_at": now, "removed_by_user_id": current_user["user_id"], "updated_at": now}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Requisito no encontrado")
    return {"requirement_id": requirement_id, "active": False, "removed_at": now.isoformat()}


@router.put("/candidates/{person_id}/requirements/{requirement_id}", response_model=dict)
async def record_requirement_evidence(person_id: str, requirement_id: str, payload: RequirementEvidence, current_user: dict = Depends(get_current_user)):
    await load_person(person_id)
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, LEADERSHIP_PROMOTE):
        raise HTTPException(status_code=403, detail="Sin permiso para evaluar requisitos")
    await assert_promotion_scope(person_id, payload.front_group_id, current_user)
    requirement = await db.leadership_requirement_catalog.find_one({"requirement_id": requirement_id, "active": True})
    if not requirement:
        raise HTTPException(status_code=404, detail="Requisito no encontrado")
    if requirement.get("source_type") != "manual":
        raise HTTPException(status_code=409, detail="Este requisito se calcula automáticamente")
    now = now_utc(); evidence_id = str(uuid4())
    document = {"_id": evidence_id, "evidence_id": evidence_id, "person_id": person_id, "requirement_id": requirement_id, **payload.model_dump(), "evaluated_by_user_id": current_user["user_id"], "evaluated_at": now}
    await db.leadership_requirement_evidence.insert_one(document)
    return serialize(document)


@router.get("/candidates/{person_id}/eligibility", response_model=dict)
async def candidate_eligibility(person_id: str, front_group_id: Optional[str] = None, current_user: dict = Depends(require_read)):
    person = await load_person(person_id)
    if not is_global_pastoral_authority(current_user) and current_user.get("person_id") != person_id:
        if not front_group_id:
            raise HTTPException(status_code=403, detail="Indique un Grupo Frontal dentro de su ámbito")
        await assert_promotion_scope(person_id, front_group_id, current_user)
    snapshot = await eligibility_snapshot(person_id, front_group_id)
    status = await db.person_leadership_status.find_one({"person_id": person_id}, {"_id": 0})
    return {"person": {"person_id": person_id, **person}, "front_group_id": front_group_id, "leadership_status": serialize(status), **snapshot}


@router.post("/candidates/{person_id}/promote", response_model=dict, status_code=201)
async def promote_candidate(person_id: str, payload: PromotionInput, current_user: dict = Depends(get_current_user)):
    person = await load_person(person_id)
    await assert_promotion_scope(person_id, payload.front_group_id, current_user)
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, LEADERSHIP_PROMOTE):
        raise HTTPException(status_code=403, detail="Sin permiso para promover liderazgo")
    current = await db.person_leadership_status.find_one({"person_id": person_id, "status": "leader"}, {"_id": 0})
    if current:
        raise HTTPException(status_code=409, detail="La Persona ya tiene estatus ministerial de Líder")
    snapshot = await eligibility_snapshot(person_id, payload.front_group_id)
    if not snapshot["eligible"]:
        raise HTTPException(status_code=409, detail={"message": "La Persona todavía no cumple los requisitos obligatorios", "requirements": snapshot["requirements"]})
    now = now_utc(); promotion_id = str(uuid4())
    document = {
        "_id": promotion_id,
        "promotion_id": promotion_id,
        "person_id": person_id,
        "person_name_snapshot": " ".join(part for part in [person.get("nombre"), person.get("apellido")] if part),
        "front_group_id": payload.front_group_id,
        "decision": "approved",
        "previous_status": current.get("status") if current else "candidate",
        "new_status": "leader",
        "requirements_snapshot": snapshot["requirements"],
        "approved_by_user_id": current_user["user_id"],
        "approved_by_role": current_user.get("access_title") or current_user.get("rol"),
        "observations": payload.observations,
        "approved_at": now,
    }
    await db.leadership_promotions.insert_one(document)
    await db.person_leadership_status.update_one({"person_id": person_id}, {"$set": {"person_id": person_id, "status": "leader", "front_group_id": payload.front_group_id, "promotion_id": promotion_id, "promoted_at": now, "promoted_by_user_id": current_user["user_id"], "updated_at": now}}, upsert=True)
    return serialize(document)


@router.get("/dashboard", response_model=dict)
async def leadership_dashboard(current_user: dict = Depends(require_read)):
    group_query = {}
    if not is_global_pastoral_authority(current_user):
        group_ids = await db.front_group_assignments.distinct("front_group_id", {"person_id": current_user.get("person_id"), "role": "leader", "active": True})
        group_query["front_group_id"] = {"$in": group_ids}
    promotions = await db.leadership_promotions.find(group_query, {"_id": 0}).sort("approved_at", -1).to_list(1000)
    return {"leaders_total": await db.person_leadership_status.count_documents({"status": "leader", **group_query}), "promotions": serialize(promotions[:50]), "promotions_total": len(promotions)}


DEFAULT_REQUIREMENTS = [
    ("membership-active", "Membresía activa", "Firma formal y número de membresía vigentes", "membership_active", 1),
    ("formation-completed", "Mentoría / formación completada", "Mentoría o Educación/Discipulado completados", "formation_completed", 2),
    ("cap-completed", "CAP completado", "Evaluación CAP cerrada", "cap_completed", 3),
    ("service-active", "Servicio ministerial activo", "Participación activa en Ministerio, Puerta o Célula", "ministry_service_active", 4),
]


async def ensure_leadership_indexes_and_seed() -> None:
    await db.leadership_requirement_catalog.create_index("requirement_id", unique=True)
    await db.leadership_requirement_catalog.create_index([("active", 1), ("order", 1)])
    await db.leadership_requirement_evidence.create_index([("person_id", 1), ("requirement_id", 1), ("evaluated_at", -1)])
    await db.leadership_promotions.create_index("promotion_id", unique=True)
    await db.person_leadership_status.create_index("person_id", unique=True)
    now = now_utc()
    for requirement_id, name, description, source_type, order in DEFAULT_REQUIREMENTS:
        await db.leadership_requirement_catalog.update_one(
            {"requirement_id": requirement_id},
            {"$setOnInsert": {"_id": requirement_id, "requirement_id": requirement_id, "name": name, "description": description, "source_type": source_type, "required": True, "active": True, "order": order, "created_at": now}},
            upsert=True,
        )