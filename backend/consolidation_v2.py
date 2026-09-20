"""API oficial de Consolidación v2: cuatro entradas, Fiesta, Retiro y Discipulado."""
from datetime import datetime, timezone
from typing import Literal, Optional
import re
import unicodedata

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import (
    CONSOLIDATION_ASSIGN,
    CONSOLIDATION_MENTOR_TRANSFER,
    CONSOLIDATION_RETREAT_CLOSE,
    MEMBERSHIP_ACCEPTANCE_MANAGE,
    PROCESSES_READ,
    PROCESSES_WRITE,
    has_capability,
    is_global_pastoral_authority,
)
from consolidation_service import (
    assert_consolidation_scope,
    assign_mentor,
    configure_entry_stages,
    enrollment_detail,
    ensure_consolidation_indexes,
    evaluate_current_mentor,
    load_consolidation,
    load_person,
    mentor_qualification,
)
from front_groups import assert_group_scope, group_in_scope
from front_group_routing import confirm_routing, routing_recommendation
from front_group_tree import readable_group_ids
from front_group_work import create_source_work_assignment
from membership_documents import activate_membership_from_acceptance
from process_engine import create_enrollment, now_utc, record_event, serialize
from process_engine import access_person_ids
from server import db, get_current_user


router = APIRouter(prefix="/api/processes/consolidation", tags=["consolidation-v2"])


class ConsolidationIntake(BaseModel):
    person_id: str
    entry_mode: Literal["complete_cycle", "direct_church", "cell", "visitor_followup"]
    front_group_id: Optional[str] = None
    mentor_person_id: Optional[str] = None
    source_cell_id: Optional[str] = None
    source_reference: Optional[str] = Field(default=None, max_length=200)
    next_followup_at: Optional[datetime] = None
    initial_result: Optional[str] = Field(default=None, max_length=1200)
    routing_policy_id: Optional[str] = None
    assignment_reason: Optional[str] = Field(default=None, max_length=1000)


class ConsolidationBatchItem(BaseModel):
    person_id: str
    entry_mode: Literal["complete_cycle", "direct_church", "cell", "visitor_followup"] = "direct_church"
    source_cell_id: Optional[str] = None
    source_reference: Optional[str] = Field(default=None, max_length=200)
    initial_result: Optional[str] = Field(default=None, max_length=1200)


class ConsolidationBatchAssignment(BaseModel):
    items: list[ConsolidationBatchItem] = Field(min_length=1, max_length=100)
    front_group_id: str
    routing_policy_id: Optional[str] = None
    reason: str = Field(min_length=3, max_length=1000)


class ConsolidationGroupAssignment(BaseModel):
    front_group_id: str
    routing_policy_id: Optional[str] = None
    reason: str = Field(min_length=3, max_length=1000)


class VisitorStart(BaseModel):
    mentor_person_id: str
    response_result: str = Field(min_length=2, max_length=1200)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MentorTransfer(BaseModel):
    new_mentor_person_id: str
    reason: str = Field(min_length=2, max_length=1000)


class MembershipAcceptance(BaseModel):
    signed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = Field(default=None, max_length=1200)


class RetreatClose(BaseModel):
    retreat_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    certificate_delivery_status: Literal["delivered", "pending_exception"]
    card_delivery_status: Literal["delivered", "pending", "not_applicable"]
    delivery_notes: Optional[str] = Field(default=None, max_length=1200)


def require_read(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_capability(current_user, PROCESSES_READ):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar Consolidación")
    return current_user


def require_write(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_capability(current_user, PROCESSES_WRITE):
        raise HTTPException(status_code=403, detail="Sin permiso para gestionar Consolidación")
    return current_user


def require_sensitive(current_user: dict, capability: str, message: str) -> None:
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, capability):
        raise HTTPException(status_code=403, detail=message)


async def load_scoped(enrollment_id: str, current_user: dict, leader_required: bool = False) -> dict:
    enrollment = await load_consolidation(db, enrollment_id)
    await assert_consolidation_scope(db, enrollment, current_user, leader_required)
    return enrollment


@router.get("/dashboard", response_model=dict)
async def consolidation_dashboard(current_user: dict = Depends(require_read)):
    query = {"process_key": "consolidation", "definition_version": 2}
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, CONSOLIDATION_ASSIGN):
        group_ids = list(await readable_group_ids(db, current_user) or [])
        query["$or"] = [{"front_group_id": {"$in": group_ids}}, {"person_id": current_user.get("person_id")}, {"mentor_person_id": current_user.get("person_id")}]
    items = await db.process_enrollments.find(query, {"_id": 0}).to_list(10000)
    by_entry = {key: 0 for key in ["complete_cycle", "direct_church", "cell", "visitor_followup"]}
    by_stage = {}
    for item in items:
        by_entry[item.get("entry_mode", "visitor_followup")] = by_entry.get(item.get("entry_mode", "visitor_followup"), 0) + 1
        by_stage[item.get("current_stage_key", "unknown")] = by_stage.get(item.get("current_stage_key", "unknown"), 0) + 1
    person_ids = list({item["person_id"] for item in items})
    memberships = await db.person_memberships.find({"person_id": {"$in": person_ids}, "status": "active"}, {"_id": 0, "person_id": 1, "acceptance_signed_at": 1}).to_list(10000) if person_ids else []
    signed_dates = {item["person_id"]: item.get("acceptance_signed_at") for item in memberships}
    durations = []
    for item in items:
        started = item.get("process_started_at") or item.get("created_at")
        signed = signed_dates.get(item["person_id"])
        if isinstance(started, datetime) and isinstance(signed, datetime) and signed >= started:
            durations.append((signed - started).total_seconds() / 86400)
    group_ids = list({item.get("front_group_id") for item in items if item.get("front_group_id")})
    groups = await db.front_groups.find({"front_group_id": {"$in": group_ids}, "status": {"$ne": "archived"}}, {"_id": 0, "front_group_id": 1, "name": 1}).to_list(1000) if group_ids else []
    by_front_group = [{"front_group_id": group["front_group_id"], "name": group["name"], "total": sum(1 for item in items if item.get("front_group_id") == group["front_group_id"]), "completed": sum(1 for item in items if item.get("front_group_id") == group["front_group_id"] and item.get("status") == "completed")} for group in groups]
    active_alerts = await db.process_alerts.count_documents({"enrollment_id": {"$in": [item["enrollment_id"] for item in items]}, "status": "open"}) if items else 0
    return {
        "total": len(items),
        "active": sum(1 for item in items if item.get("status") == "active"),
        "followup_pending": sum(1 for item in items if item.get("consolidation_status") == "followup_pending"),
        "members": len(memberships),
        "retreat_completed": sum(1 for item in items if item.get("retreat_completed_at")),
        "mentor_transfer_required": sum(1 for item in items if item.get("mentor_transfer_required") is True),
        "by_entry": by_entry,
        "by_stage": by_stage,
        "by_front_group": by_front_group,
        "membership_conversion_pct": round(len(memberships) / len(items) * 100, 1) if items else 0,
        "retreat_conversion_pct": round(sum(1 for item in items if item.get("retreat_completed_at")) / len(items) * 100, 1) if items else 0,
        "avg_days_to_membership": round(sum(durations) / len(durations), 1) if durations else None,
        "active_alerts": active_alerts,
    }


@router.post("/intakes", response_model=dict, status_code=201)
async def create_intake(payload: ConsolidationIntake, current_user: dict = Depends(require_write)):
    person = await load_person(db, payload.person_id)
    decision = await confirm_routing(
        requested_group_id=payload.front_group_id, source_cell_id=payload.source_cell_id,
        policy_id=payload.routing_policy_id, reason=payload.assignment_reason, current_user=current_user,
    )
    assigned_group_id = decision["assigned_group_id"]
    if not assigned_group_id and not is_global_pastoral_authority(current_user) and not has_capability(current_user, CONSOLIDATION_ASSIGN) and current_user.get("person_id") != payload.person_id:
        raise HTTPException(status_code=403, detail="Un Líder de Grupo Frontal debe iniciar procesos dentro de su Grupo")
    if payload.entry_mode == "cell" and not payload.source_cell_id:
        raise HTTPException(status_code=422, detail="La entrada desde célula requiere identificar la célula de origen")
    assignment_authority = is_global_pastoral_authority(current_user) or has_capability(current_user, CONSOLIDATION_ASSIGN)
    if payload.entry_mode != "visitor_followup" and not payload.mentor_person_id and not assignment_authority:
        raise HTTPException(status_code=422, detail="Asigne un mentor al iniciar el proceso")
    existing = await db.process_enrollments.find_one({"process_key": "consolidation", "person_id": payload.person_id}, {"_id": 0}, sort=[("created_at", -1)])
    if existing and existing.get("status") in {"planned", "active"}:
        if assigned_group_id and assignment_authority:
            previous_group_id = existing.get("front_group_id")
            if previous_group_id and previous_group_id != assigned_group_id and not payload.assignment_reason:
                raise HTTPException(status_code=422, detail="Indique el motivo para modificar el Grupo Frontal responsable")
            now = now_utc()
            await db.process_enrollments.update_one({"enrollment_id": existing["enrollment_id"]}, {"$set": {"front_group_id": assigned_group_id, "routing_decision": decision, "updated_at": now}, "$push": {"routing_history": {**decision, "source_cell_id": payload.source_cell_id or existing.get("source_cell_id"), "actor_user_id": current_user["user_id"], "occurred_at": now}}})
            await create_source_work_assignment(source_type="consolidation", source_id=existing["enrollment_id"], source_sub_id=None, title="Ejecutar Consolidación", description="Asignación operativa de Consolidación al Grupo Frontal.", assigned_group_id=assigned_group_id, assigned_person_id=existing.get("mentor_person_id") if previous_group_id == assigned_group_id else None, priority="high", due_at=existing.get("next_action_at"), actor_user_id=current_user["user_id"], reason=payload.assignment_reason or "Confirmación de asignación de Consolidación")
            await record_event(db, existing, current_user["user_id"], "front_group_assigned", "Grupo Frontal responsable confirmado", payload.assignment_reason or assigned_group_id)
            return await enrollment_detail(db, await load_consolidation(db, existing["enrollment_id"]))
        raise HTTPException(status_code=409, detail="La Persona ya tiene una Consolidación activa")
    if existing and existing.get("status") == "completed":
        raise HTTPException(status_code=409, detail="La Persona ya completó Consolidación; continúe con el proceso siguiente")
    if existing and existing.get("status") in {"paused", "cancelled"}:
        now = now_utc(); update = {
            "status": "active", "reactivated_at": now, "reactivation_reason": payload.assignment_reason or "La Persona regresó a Consolidación",
            "updated_at": now, "last_activity_at": now,
        }
        if assigned_group_id: update["front_group_id"] = assigned_group_id
        if not existing.get("source_cell_id") and payload.source_cell_id: update["source_cell_id"] = payload.source_cell_id
        await db.process_enrollments.update_one({"enrollment_id": existing["enrollment_id"]}, {"$set": update, "$inc": {"reactivation_count": 1}, "$push": {"routing_history": {**decision, "source_cell_id": payload.source_cell_id, "actor_user_id": current_user["user_id"], "occurred_at": now}}})
        await record_event(db, existing, current_user["user_id"], "reactivated", "Consolidación reactivada desde la última etapa válida", f"Continúa en {existing.get('current_stage_key')}")
        refreshed = await db.process_enrollments.find_one({"enrollment_id": existing["enrollment_id"]}, {"_id": 0})
        if assigned_group_id:
            await create_source_work_assignment(source_type="consolidation", source_id=existing["enrollment_id"], source_sub_id=None, title="Continuar Consolidación", description="Expediente reactivado; continuar desde la etapa vigente.", assigned_group_id=assigned_group_id, assigned_person_id=refreshed.get("mentor_person_id"), priority="high", due_at=refreshed.get("next_action_at"), actor_user_id=current_user["user_id"], reason=payload.assignment_reason or "Reactivación de Consolidación")
        return await enrollment_detail(db, refreshed)
    enrollment, _ = await create_enrollment(
        db, "consolidation", payload.person_id, payload.mentor_person_id, current_user["user_id"],
        status="active", next_action="Dar seguimiento al visitante" if payload.entry_mode == "visitor_followup" else "Completar etapa actual",
        next_action_at=payload.next_followup_at, source="consolidation_v2", source_id=payload.source_reference,
    )
    arrival = await db.person_arrivals.find_one({"person_id": payload.person_id}, {"_id": 0})
    await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": {
        "front_group_id": assigned_group_id,
        "source_cell_id": payload.source_cell_id,
        "routing_decision": decision,
        "routing_history": [{**decision, "source_cell_id": payload.source_cell_id, "actor_user_id": current_user["user_id"], "occurred_at": now_utc()}],
        "origin_snapshot": serialize(arrival),
        "entry_recorded_by_user_id": current_user["user_id"],
        "entry_recorded_at": now_utc(),
        "initial_result": payload.initial_result,
    }})
    enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
    await configure_entry_stages(db, enrollment, payload.entry_mode, current_user["user_id"])
    if payload.mentor_person_id:
        enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
        await assign_mentor(db, enrollment, payload.mentor_person_id, current_user["user_id"], "Asignación inicial")
    enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
    if assigned_group_id:
        await create_source_work_assignment(source_type="consolidation", source_id=enrollment["enrollment_id"], source_sub_id=None, title="Ejecutar Consolidación", description="Asignación operativa de Consolidación al Grupo Frontal.", assigned_group_id=assigned_group_id, assigned_person_id=payload.mentor_person_id, priority="high", due_at=enrollment.get("next_action_at"), actor_user_id=current_user["user_id"], reason=payload.assignment_reason or "Asignación inicial de Consolidación")
    await db.front_group_routing_events.insert_one({"_id": str(ObjectId()), "event_id": str(ObjectId()), "action": "consolidation_routing_confirmed" if assigned_group_id else "consolidation_waiting_assignment", "enrollment_id": enrollment["enrollment_id"], "person_id": payload.person_id, "source_cell_id": payload.source_cell_id, "decision": decision, "actor_user_id": current_user["user_id"], "occurred_at": now_utc()})
    return await enrollment_detail(db, enrollment)


@router.post("/batch-assign", response_model=dict)
async def batch_assign_consolidation(payload: ConsolidationBatchAssignment, current_user: dict = Depends(get_current_user)):
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, CONSOLIDATION_ASSIGN):
        raise HTTPException(status_code=403, detail="Asignación por lotes reservada a Consolidación")
    results = []
    for item in payload.items:
        intake = ConsolidationIntake(**item.model_dump(), front_group_id=payload.front_group_id, routing_policy_id=payload.routing_policy_id, assignment_reason=payload.reason)
        try:
            result = await create_intake(intake, current_user)
            results.append({"person_id": item.person_id, "status": "assigned", "enrollment_id": result["enrollment_id"], "current_stage_key": result.get("current_stage_key")})
        except HTTPException as exc:
            results.append({"person_id": item.person_id, "status": "not_assigned", "detail": exc.detail})
    return {"items": results, "assigned": sum(item["status"] == "assigned" for item in results), "not_assigned": sum(item["status"] != "assigned" for item in results)}


@router.put("/{enrollment_id}/front-group", response_model=dict)
async def reassign_front_group(enrollment_id: str, payload: ConsolidationGroupAssignment, current_user: dict = Depends(get_current_user)):
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, CONSOLIDATION_ASSIGN):
        raise HTTPException(status_code=403, detail="Reasignación reservada a Consolidación")
    enrollment = await load_consolidation(db, enrollment_id)
    decision = await confirm_routing(requested_group_id=payload.front_group_id, source_cell_id=enrollment.get("source_cell_id"), policy_id=payload.routing_policy_id, reason=payload.reason, current_user=current_user)
    previous_group_id = enrollment.get("front_group_id"); now = now_utc(); mentor_id = enrollment.get("mentor_person_id")
    if mentor_id and not await db.front_group_assignments.find_one({"front_group_id": payload.front_group_id, "person_id": mentor_id, "active": True}, {"_id": 1}):
        await db.mentor_assignments.update_many({"enrollment_id": enrollment_id, "active": True}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "end_reason": payload.reason}})
        mentor_id = None
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {"front_group_id": payload.front_group_id, "mentor_person_id": mentor_id, "responsible_person_id": mentor_id, "routing_decision": decision, "updated_at": now}, "$push": {"routing_history": {**decision, "source_cell_id": enrollment.get("source_cell_id"), "actor_user_id": current_user["user_id"], "occurred_at": now}}})
    await create_source_work_assignment(source_type="consolidation", source_id=enrollment_id, source_sub_id=None, title="Ejecutar Consolidación", description="Asignación operativa de Consolidación al Grupo Frontal.", assigned_group_id=payload.front_group_id, assigned_person_id=mentor_id, priority="high", due_at=enrollment.get("next_action_at"), actor_user_id=current_user["user_id"], reason=payload.reason)
    await record_event(db, enrollment, current_user["user_id"], "front_group_reassigned", "Grupo Frontal responsable actualizado", f"{previous_group_id or 'Sin grupo'} → {payload.front_group_id}. {payload.reason}")
    return await enrollment_detail(db, await load_consolidation(db, enrollment_id))


@router.get("/intake-candidates", response_model=dict)
async def intake_candidates(search: str = "", limit: int = 20, current_user: dict = Depends(require_read)):
    clean = search.strip()
    if len(clean) < 2:
        return {"items": [], "total": 0}
    limit = max(1, min(limit, 30))
    normalized = unicodedata.normalize("NFKD", clean).encode("ascii", "ignore").decode().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    pattern = re.escape(clean)
    contact_ids = await db.person_contacts.distinct("person_id", {"valor": {"$regex": pattern, "$options": "i"}})
    query = {"status": {"$ne": "archived"}, "$or": [
        {"search_key": {"$regex": re.escape(normalized)}},
        {"person_number": {"$regex": pattern, "$options": "i"}},
        {"nombre": {"$regex": pattern, "$options": "i"}},
        {"apellido": {"$regex": pattern, "$options": "i"}},
    ]}
    valid_contact_ids = [ObjectId(item) for item in contact_ids if ObjectId.is_valid(item)]
    if valid_contact_ids:
        query["$or"].append({"_id": {"$in": valid_contact_ids}})
    allowed = await access_person_ids(db, current_user)
    if allowed is not None:
        query["_id"] = {"$in": [ObjectId(item) for item in allowed if ObjectId.is_valid(item)]}
    people = await db.persons.find(query, {"_id": 1, "person_number": 1, "nombre": 1, "apellido": 1}).sort([("nombre", 1), ("apellido", 1)]).limit(limit * 2).to_list(limit * 2)
    person_ids = [str(item["_id"]) for item in people]
    journey_docs = await db.process_enrollments.find({"process_key": "consolidation", "person_id": {"$in": person_ids}}, {"_id": 0, "person_id": 1, "status": 1, "current_stage_key": 1}).sort("created_at", -1).to_list(limit * 4)
    journey_by_person = {}
    for journey in journey_docs: journey_by_person.setdefault(journey["person_id"], journey)
    excluded_ids = {person_id for person_id, journey in journey_by_person.items() if journey.get("status") in {"planned", "active", "completed"}}
    contacts = await db.person_contacts.find({"person_id": {"$in": person_ids}, "es_principal": True}, {"_id": 0, "person_id": 1, "valor": 1}).to_list(limit * 2)
    phones = {item["person_id"]: item.get("valor") for item in contacts}
    items = [{
        "person_id": str(person["_id"]), "person_number": person.get("person_number"),
        "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
        "phone": phones.get(str(person["_id"])),
        "continuation_status": (journey_by_person.get(str(person["_id"])) or {}).get("status"),
        "current_stage_key": (journey_by_person.get(str(person["_id"])) or {}).get("current_stage_key"),
    } for person in people if str(person["_id"]) not in excluded_ids][:limit]
    return {"items": items, "total": len(items)}


@router.get("/{enrollment_id}", response_model=dict)
async def get_consolidation(enrollment_id: str, current_user: dict = Depends(require_read)):
    enrollment = await load_scoped(enrollment_id, current_user)
    return await enrollment_detail(db, enrollment)


@router.post("/{enrollment_id}/start", response_model=dict)
async def start_visitor_process(enrollment_id: str, payload: VisitorStart, current_user: dict = Depends(require_write)):
    enrollment = await load_scoped(enrollment_id, current_user, leader_required=not is_global_pastoral_authority(current_user))
    if enrollment.get("current_stage_key") != "visitor_followup":
        raise HTTPException(status_code=409, detail="El seguimiento inicial ya fue cerrado")
    await assign_mentor(db, enrollment, payload.mentor_person_id, current_user["user_id"], "Respuesta positiva; inicia Consolidación")
    now = now_utc()
    await db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "visitor_followup"}, {"$set": {"status": "completed", "completed_at": now, "result": payload.response_result, "updated_at": now}})
    await db.process_stage_progress.update_many({"enrollment_id": enrollment_id, "stage_key": {"$in": ["prayer", "invasion"]}}, {"$set": {"status": "skipped", "skipped_at": now, "skip_reason": "Seguimiento posterior de visitante", "updated_at": now}})
    await db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "mcd"}, {"$set": {"status": "open", "opened_at": now, "updated_at": now}})
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {"current_stage_key": "mcd", "consolidation_status": "in_progress", "process_started_at": payload.started_at, "next_action": "Completar MCD", "next_action_at": None, "updated_at": now}})
    await record_event(db, enrollment, current_user["user_id"], "visitor_started", "Visitante inició Consolidación", payload.response_result)
    return await enrollment_detail(db, await load_consolidation(db, enrollment_id))


@router.post("/{enrollment_id}/mentor/evaluate", response_model=dict)
async def evaluate_mentor(enrollment_id: str, current_user: dict = Depends(require_write)):
    enrollment = await load_scoped(enrollment_id, current_user)
    if enrollment.get("current_stage_key") != "welcome_party":
        raise HTTPException(status_code=409, detail="La evaluación formal del mentor ocurre en Fiesta de Bienvenida")
    return await evaluate_current_mentor(db, enrollment, current_user["user_id"])


@router.post("/{enrollment_id}/mentor/transfer", response_model=dict)
async def transfer_mentor(enrollment_id: str, payload: MentorTransfer, current_user: dict = Depends(get_current_user)):
    require_sensitive(current_user, CONSOLIDATION_MENTOR_TRANSFER, "Sin permiso para transferir mentores")
    enrollment = await load_scoped(enrollment_id, current_user)
    if not await mentor_qualification(db, payload.new_mentor_person_id, enrollment.get("front_group_id")):
        raise HTTPException(status_code=409, detail="El nuevo mentor no está autorizado para impartir LBS")
    assignment = await assign_mentor(db, enrollment, payload.new_mentor_person_id, current_user["user_id"], payload.reason, transfer=True)
    refreshed = await load_consolidation(db, enrollment_id)
    await evaluate_current_mentor(db, refreshed, current_user["user_id"])
    return {"assignment": assignment, "enrollment": await enrollment_detail(db, await load_consolidation(db, enrollment_id))}


@router.post("/{enrollment_id}/membership-acceptance", response_model=dict)
async def accept_membership(enrollment_id: str, payload: MembershipAcceptance, current_user: dict = Depends(get_current_user)):
    require_sensitive(current_user, MEMBERSHIP_ACCEPTANCE_MANAGE, "Sin permiso para registrar la Carta de Membresía")
    enrollment = await load_scoped(enrollment_id, current_user)
    stage = await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": "welcome_party"}, {"_id": 0})
    if not stage or stage.get("status") == "locked":
        raise HTTPException(status_code=409, detail="La Carta de Membresía se registra desde Fiesta de Bienvenida")
    person = await load_person(db, enrollment["person_id"])
    membership, created = await activate_membership_from_acceptance(person, current_user["user_id"], enrollment_id, payload.signed_at, payload.notes)
    await db.person_memberships.update_one({"membership_id": membership["membership_id"]}, {"$set": {"front_group_id": enrollment.get("front_group_id")}})
    now = now_utc(); tasks = stage.get("tasks", [])
    for task in tasks:
        if task.get("task_id") == "membership_decision":
            task.update({"completed": True, "completed_at": now})
    await db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "welcome_party"}, {"$set": {"tasks": tasks, "updated_at": now}})
    await record_event(db, enrollment, current_user["user_id"], "membership_accepted", "Carta de Membresía firmada", f"Número {membership['member_number']}")
    return {"created": created, "membership": serialize(await db.person_memberships.find_one({"membership_id": membership["membership_id"]}, {"_id": 0}))}


@router.post("/{enrollment_id}/retreat-close", response_model=dict)
async def close_retreat(enrollment_id: str, payload: RetreatClose, current_user: dict = Depends(get_current_user)):
    require_sensitive(current_user, CONSOLIDATION_RETREAT_CLOSE, "Sin permiso para cerrar Retiro")
    enrollment = await load_scoped(enrollment_id, current_user)
    if enrollment.get("retreat_completed_at"):
        return await enrollment_detail(db, enrollment)
    if enrollment.get("current_stage_key") != "retreat":
        raise HTTPException(status_code=409, detail="Complete primero las etapas anteriores al Retiro")
    membership = await db.person_memberships.find_one({"person_id": enrollment["person_id"], "status": "active"})
    if not membership:
        raise HTTPException(status_code=409, detail="La Persona debe haber firmado la Carta de Membresía")
    if payload.certificate_delivery_status == "delivered" and not membership.get("certificate_issue_date"):
        raise HTTPException(status_code=409, detail="Emita el certificado antes de registrarlo como entregado")
    now = now_utc()
    await db.person_memberships.update_one({"membership_id": membership["membership_id"]}, {"$set": {
        "certificate_delivery_status": payload.certificate_delivery_status,
        "certificate_delivered_at": payload.retreat_date if payload.certificate_delivery_status == "delivered" else None,
        "card_delivery_status": payload.card_delivery_status,
        "card_delivered_at": payload.retreat_date if payload.card_delivery_status == "delivered" else None,
        "delivery_notes": payload.delivery_notes,
        "updated_by_user_id": current_user["user_id"],
        "updated_at": now,
    }})
    discipleship, _ = await create_enrollment(db, "discipleship", enrollment["person_id"], enrollment.get("mentor_person_id"), current_user["user_id"], status="active", next_action="Realizar orientación de Discipulado", source="consolidation_retreat", source_id=enrollment_id)
    await db.process_enrollments.update_one({"enrollment_id": discipleship["enrollment_id"]}, {"$set": {"front_group_id": enrollment.get("front_group_id"), "previous_process_enrollment_id": enrollment_id, "updated_at": now}})
    for stage_key in ["retreat", "discipleship_handoff"]:
        stage = await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": stage_key})
        if stage:
            tasks = stage.get("tasks", [])
            for task in tasks:
                task.update({"completed": True, "completed_at": now})
            await db.process_stage_progress.update_one({"_id": stage["_id"]}, {"$set": {"status": "completed", "tasks": tasks, "completed_at": now, "updated_at": now}})
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {
        "status": "completed", "consolidation_status": "completed", "progress_pct": 100,
        "current_stage_key": "discipleship_handoff", "retreat_completed_at": payload.retreat_date,
        "discipleship_enrollment_id": discipleship["enrollment_id"], "completed_at": now,
        "next_action": "Continuar Educación / Discipulado", "next_action_at": None, "updated_at": now,
    }})
    await record_event(db, enrollment, current_user["user_id"], "retreat_closed", "Consolidación cerrada en Retiro", f"Discipulado {discipleship['enrollment_id']}")
    return await enrollment_detail(db, await load_consolidation(db, enrollment_id))


async def ensure_indexes() -> None:
    await ensure_consolidation_indexes(db)