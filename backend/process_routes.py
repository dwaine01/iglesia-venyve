"""API operacional del Mega-Bloque B: procesos, SLA, Mentoría y CAP."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from access_control import (
    PROCESS_ALERTS_MANAGE,
    PROCESSES_MANAGE,
    PROCESSES_PARTICIPATE,
    PROCESSES_READ,
    PROCESSES_WRITE,
    authorize_person,
    has_capability,
)
from canonical_identity import normalize
from process_engine import (
    access_person_ids,
    create_enrollment,
    enrollment_in_scope,
    evaluate_alerts,
    get_definition,
    iso_z,
    migrate_legacy_processes,
    now_utc,
    recalculate_enrollment,
    record_event,
    serialize,
)
from server import db, get_current_user

router = APIRouter(prefix="/api/processes", tags=["processes"])
PROCESS_KEYS = {"seven_weeks", "consolidation", "mentorship", "cap", "discipleship"}


class ItemList(BaseModel):
    items: list[dict]
    total: int


class CatalogResponse(BaseModel):
    definitions: list[dict]
    doors: list[dict]
    assignees: list[dict]


class CycleCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    start_date: str
    end_date: str
    capacity: Optional[int] = Field(default=None, ge=1, le=5000)
    coordinator_person_id: Optional[str] = None
    status: Literal["planned", "active", "completed", "cancelled"] = "planned"

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        datetime.fromisoformat(value)
        return value


class CycleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=120)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    capacity: Optional[int] = Field(default=None, ge=1, le=5000)
    coordinator_person_id: Optional[str] = None
    status: Optional[Literal["planned", "active", "completed", "cancelled"]] = None


class EnrollmentCreate(BaseModel):
    process_key: Literal["seven_weeks", "consolidation"]
    person_id: str
    cycle_id: Optional[str] = None
    responsible_person_id: Optional[str] = None
    status: Literal["planned", "active"] = "active"
    next_action: Optional[str] = Field(default=None, max_length=300)
    next_action_at: Optional[datetime] = None


class EnrollmentUpdate(BaseModel):
    responsible_person_id: Optional[str] = None
    status: Optional[Literal["planned", "active", "paused", "cancelled"]] = None
    next_action: Optional[str] = Field(default=None, max_length=300)
    next_action_at: Optional[datetime] = None
    result: Optional[str] = Field(default=None, max_length=1500)


class StageUpdate(BaseModel):
    status: Optional[Literal["open", "in_progress", "completed"]] = None
    attendance: Optional[Literal["pending", "present", "absent", "excused"]] = None
    result: Optional[str] = Field(default=None, max_length=1500)
    notes: Optional[str] = Field(default=None, max_length=2000)
    next_action: Optional[str] = Field(default=None, max_length=300)
    next_action_at: Optional[datetime] = None


class TaskUpdate(BaseModel):
    completed: bool


class EvidenceCreate(BaseModel):
    stage_key: str
    task_id: Optional[str] = None
    kind: Literal["note", "link", "reference"] = "note"
    title: str = Field(..., min_length=2, max_length=160)
    note: Optional[str] = Field(default=None, max_length=3000)
    url: Optional[str] = Field(default=None, max_length=1000)


class ContactCreate(BaseModel):
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    channel: Literal["call", "message", "visit", "meeting", "other"]
    outcome: str = Field(..., min_length=2, max_length=1000)
    next_contact_at: Optional[datetime] = None
    next_action: Optional[str] = Field(default=None, max_length=300)
    advance_stage: bool = False


class MentorshipCreate(BaseModel):
    person_id: str
    mentor_person_id: str
    goals: list[str] = Field(default_factory=list, max_length=20)
    next_meeting_at: Optional[datetime] = None


class MentorshipMeetingCreate(BaseModel):
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attended: bool = True
    lesson_key: Optional[str] = Field(default=None, max_length=100)
    lesson_title: Optional[str] = Field(default=None, max_length=180)
    notes: Optional[str] = Field(default=None, max_length=3000)
    commitments: list[str] = Field(default_factory=list, max_length=20)
    next_meeting_at: Optional[datetime] = None


class CapCreate(BaseModel):
    person_id: str
    responsible_person_id: Optional[str] = None
    gifts: list[str] = Field(default_factory=list, max_length=30)
    interests: list[str] = Field(default_factory=list, max_length=30)
    availability_days: list[str] = Field(default_factory=list, max_length=7)
    availability_notes: Optional[str] = Field(default=None, max_length=500)


class CapUpdate(BaseModel):
    gifts: Optional[list[str]] = Field(default=None, max_length=30)
    interests: Optional[list[str]] = Field(default=None, max_length=30)
    availability_days: Optional[list[str]] = Field(default=None, max_length=7)
    availability_notes: Optional[str] = Field(default=None, max_length=500)
    selected_door_key: Optional[str] = None
    coverage_person_id: Optional[str] = None
    activation_evidence: Optional[str] = Field(default=None, max_length=2000)
    continuous_training: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[Literal["assessment", "door_suggested", "door_selected", "activated", "continuous_training", "completed"]] = None


class AlertAction(BaseModel):
    status: Literal["acknowledged", "resolved"]
    resolution: Optional[str] = Field(default=None, max_length=1000)


class AlertRuleUpdate(BaseModel):
    enabled: Optional[bool] = None
    threshold: Optional[int] = Field(default=None, ge=0, le=8760)
    severity: Optional[Literal["info", "warning", "critical"]] = None


class MigrationResponse(BaseModel):
    people_migrated: int
    leader_records_migrated: int
    stage_records_migrated: int
    conflict_count: int
    conflicts: list[dict]


def require_read(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_capability(current_user, PROCESSES_READ):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar procesos")
    return current_user


def require_write(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_capability(current_user, PROCESSES_WRITE):
        raise HTTPException(status_code=403, detail="Sin permiso para gestionar procesos")
    return current_user


def require_participate(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_capability(current_user, PROCESSES_PARTICIPATE):
        raise HTTPException(status_code=403, detail="Sin permiso para actualizar progreso")
    return current_user


def require_manage(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_capability(current_user, PROCESSES_MANAGE):
        raise HTTPException(status_code=403, detail="Configuración restringida")
    return current_user


async def load_person(person_id: str) -> dict:
    if not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=400, detail="person_id inválido")
    person = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person["person_id"] = person_id
    return person


async def validate_staff_assignee(person_id: str, current_user: dict) -> None:
    await load_person(person_id)
    account = await db.users.find_one(
        {"person_id": person_id, "is_active": {"$ne": False}, "rol": {"$in": ["pastor", "lider"]}},
        {"_id": 0, "person_id": 1},
    )
    if not account:
        raise HTTPException(status_code=400, detail="La asignación requiere una cuenta pastoral o de liderazgo activa")
    if current_user.get("rol") != "pastor" and person_id != current_user.get("person_id"):
        raise HTTPException(status_code=403, detail="Solo puede asignarse a sí mismo dentro de su alcance")


async def load_enrollment(enrollment_id: str, current_user: dict) -> dict:
    enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")
    if not await enrollment_in_scope(db, enrollment, current_user):
        raise HTTPException(status_code=403, detail="Inscripción fuera de su alcance")
    return enrollment


async def person_summary(person_id: str) -> dict:
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 0, "nombre": 1, "apellido": 1, "person_number": 1})
    return {
        "person_id": person_id,
        "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip() if person else "Persona no encontrada",
        "person_number": person.get("person_number") if person else None,
        "profile_path": f"/personas/{person_id}",
    }


async def enrich_enrollment(item: dict) -> dict:
    current_stage = await db.process_stage_progress.find_one({"enrollment_id": item["enrollment_id"], "stage_key": item.get("current_stage_key")}, {"_id": 0})
    result = serialize(item)
    result["person"] = await person_summary(item["person_id"])
    result["current_stage"] = serialize(current_stage) if current_stage else None
    if item.get("responsible_person_id"):
        result["responsible"] = await person_summary(item["responsible_person_id"])
    return result


async def scoped_enrollment_query(current_user: dict, base: dict) -> dict:
    allowed = await access_person_ids(db, current_user)
    if allowed is not None:
        base["person_id"] = {"$in": list(allowed)}
    return base


async def mark_prior_stages(enrollment: dict, target_stage_key: str, actor_user_id: str) -> None:
    definition = await get_definition(db, enrollment["process_key"], enrollment.get("definition_version"))
    target = next((item for item in definition["stages"] if item["key"] == target_stage_key), None)
    if not target:
        raise HTTPException(status_code=400, detail="Etapa inválida")
    now = now_utc()
    for stage in definition["stages"]:
        if stage["order"] < target["order"]:
            progress = await db.process_stage_progress.find_one({"enrollment_id": enrollment["enrollment_id"], "stage_key": stage["key"]})
            tasks = progress.get("tasks", []) if progress else []
            for task in tasks:
                task.update({"completed": True, "completed_at": task.get("completed_at") or now})
            await db.process_stage_progress.update_one(
                {"enrollment_id": enrollment["enrollment_id"], "stage_key": stage["key"]},
                {"$set": {"status": "completed", "tasks": tasks, "completed_at": now, "updated_at": now}},
            )
        elif stage["order"] == target["order"]:
            await db.process_stage_progress.update_one(
                {"enrollment_id": enrollment["enrollment_id"], "stage_key": stage["key"]},
                {"$set": {"status": "open", "opened_at": now, "due_at": now + __import__('datetime').timedelta(hours=stage.get("sla_hours", 0)) if stage.get("sla_hours") else None, "updated_at": now}},
            )
    await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": {"current_stage_key": target_stage_key, "status": "active", "last_activity_at": now, "updated_at": now}})
    await recalculate_enrollment(db, enrollment["enrollment_id"], actor_user_id, allow_automation=False)


@router.get("/catalog", response_model=CatalogResponse)
async def catalog(current_user: dict = Depends(require_read)):
    definitions = await db.process_definitions.aggregate([
        {"$match": {"active": True, "process_key": {"$ne": "seven_weeks"}}},
        {"$sort": {"process_key": 1, "version": -1}},
        {"$group": {"_id": "$process_key", "item": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$item"}},
        {"$project": {"_id": 0}},
        {"$sort": {"name": 1}},
    ]).to_list(20)
    doors = await db.door_catalog.find({"active": True}, {"_id": 0}).sort("number", 1).to_list(20)
    user_query = {"is_active": {"$ne": False}, "rol": {"$in": ["pastor", "lider"]}, "person_id": {"$exists": True}}
    if current_user.get("rol") == "lider":
        led_group_ids = await db.front_group_assignments.distinct("front_group_id", {"person_id": current_user.get("person_id"), "role": "leader", "active": True})
        scoped_person_ids = await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": led_group_ids}, "active": True}) if led_group_ids else []
        user_query["person_id"] = {"$in": list(set(scoped_person_ids + [current_user.get("person_id")]))}
    elif current_user.get("rol") == "persona":
        user_query["_id"] = {"$exists": False}
    users = await db.users.find(user_query, {"_id": 0, "person_id": 1, "nombre": 1, "rol": 1}).sort("nombre", 1).to_list(1000)
    assignees = [{"person_id": item["person_id"], "name": item["nombre"], "role": item["rol"], "profile_path": f"/personas/{item['person_id']}"} for item in users]
    return {"definitions": serialize(definitions), "doors": serialize(doors), "assignees": assignees}


@router.get("/cycles", response_model=ItemList)
async def list_cycles(status_filter: Optional[str] = None, current_user: dict = Depends(require_read)):
    query = {"process_key": "seven_weeks"}
    if status_filter: query["status"] = status_filter
    items = await db.process_cycles.find(query, {"_id": 0}).sort("start_date", -1).to_list(1000)
    return {"items": serialize(items), "total": len(items)}


@router.post("/cycles", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_cycle(payload: CycleCreate, current_user: dict = Depends(require_write)):
    if datetime.fromisoformat(payload.end_date) < datetime.fromisoformat(payload.start_date):
        raise HTTPException(status_code=400, detail="La fecha final debe ser posterior a la inicial")
    if payload.coordinator_person_id: await validate_staff_assignee(payload.coordinator_person_id, current_user)
    now = now_utc(); cycle_id = str(uuid4())
    doc = {"_id": cycle_id, "cycle_id": cycle_id, "process_key": "seven_weeks", **payload.model_dump(), "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.process_cycles.insert_one(doc)
    return serialize(doc)


@router.put("/cycles/{cycle_id}", response_model=dict)
async def update_cycle(cycle_id: str, payload: CycleUpdate, current_user: dict = Depends(require_write)):
    update = payload.model_dump(exclude_none=True)
    if update.get("coordinator_person_id"): await validate_staff_assignee(update["coordinator_person_id"], current_user)
    update["updated_at"] = now_utc()
    result = await db.process_cycles.update_one({"cycle_id": cycle_id}, {"$set": update})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Ciclo no encontrado")
    return serialize(await db.process_cycles.find_one({"cycle_id": cycle_id}, {"_id": 0}))


@router.get("/enrollments", response_model=ItemList)
async def list_enrollments(process_key: Optional[str] = None, cycle_id: Optional[str] = None, status_filter: Optional[str] = None, current_user: dict = Depends(require_read)):
    query = {}
    if process_key: query["process_key"] = process_key
    if cycle_id: query["cycle_id"] = cycle_id
    if status_filter: query["status"] = status_filter
    query = await scoped_enrollment_query(current_user, query)
    docs = await db.process_enrollments.find(query, {"_id": 0}).sort("updated_at", -1).to_list(10000)
    return {"items": [await enrich_enrollment(item) for item in docs], "total": len(docs)}


@router.post("/enrollments", status_code=status.HTTP_201_CREATED, response_model=dict)
async def enroll(payload: EnrollmentCreate, current_user: dict = Depends(require_write)):
    if payload.process_key == "consolidation":
        raise HTTPException(status_code=409, detail="Las nuevas inscripciones de Consolidación se realizan por el intake oficial")
    person = await load_person(payload.person_id)
    authorize_person(current_user, person, PROCESSES_WRITE)
    responsible = payload.responsible_person_id or current_user.get("person_id")
    if responsible: await validate_staff_assignee(responsible, current_user)
    if payload.process_key == "seven_weeks":
        if not payload.cycle_id: raise HTTPException(status_code=400, detail="7 Semanas requiere un ciclo")
        if not await db.process_cycles.find_one({"cycle_id": payload.cycle_id, "status": {"$in": ["planned", "active"]}}):
            raise HTTPException(status_code=400, detail="Ciclo no disponible")
    item, created = await create_enrollment(
        db, payload.process_key, payload.person_id, responsible, current_user["user_id"], payload.cycle_id,
        payload.status, payload.next_action, payload.next_action_at, "manual",
    )
    if not created: raise HTTPException(status_code=409, detail="La Persona ya tiene una inscripción activa en este proceso")
    await evaluate_alerts(db)
    return await enrich_enrollment(item)


@router.get("/enrollments/{enrollment_id}", response_model=dict)
async def enrollment_detail(enrollment_id: str, current_user: dict = Depends(require_read)):
    enrollment = await load_enrollment(enrollment_id, current_user)
    stages = await db.process_stage_progress.find({"enrollment_id": enrollment_id}, {"_id": 0}).sort("stage_order", 1).to_list(100)
    evidence = await db.process_evidence.find({"enrollment_id": enrollment_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    timeline = await db.process_timeline.find({"enrollment_id": enrollment_id}, {"_id": 0}).sort("occurred_at", -1).to_list(500)
    result = await enrich_enrollment(enrollment)
    result.update({"stages": serialize(stages), "evidence": serialize(evidence), "timeline": serialize(timeline)})
    return result


@router.put("/enrollments/{enrollment_id}", response_model=dict)
async def update_enrollment(enrollment_id: str, payload: EnrollmentUpdate, current_user: dict = Depends(require_write)):
    enrollment = await load_enrollment(enrollment_id, current_user)
    update = payload.model_dump(exclude_none=True)
    if update.get("responsible_person_id"): await validate_staff_assignee(update["responsible_person_id"], current_user)
    if update.get("status") == "active" and enrollment.get("status") == "planned":
        update["started_at"] = now_utc()
        current = await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": enrollment["current_stage_key"]})
        if current and current.get("status") == "locked":
            await db.process_stage_progress.update_one({"_id": current["_id"]}, {"$set": {"status": "open", "opened_at": now_utc()}})
    if update.get("status") == "paused" and enrollment.get("status") == "active":
        update["paused_at"] = now_utc()
        update["pause_reason"] = payload.result or payload.next_action or "Proceso pausado"
    if update.get("status") == "active" and enrollment.get("status") == "paused":
        update["reactivated_at"] = now_utc()
        update["reactivation_reason"] = payload.result or payload.next_action or "La Persona regresó al proceso"
    update.update({"last_activity_at": now_utc(), "updated_at": now_utc()})
    mongo_update = {"$set": update}
    if update.get("status") == "active" and enrollment.get("status") == "paused":
        mongo_update["$inc"] = {"reactivation_count": 1}
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, mongo_update)
    if update.get("status") == "paused" and enrollment.get("status") == "active":
        await record_event(db, enrollment, current_user["user_id"], "paused", "Proceso pausado sin perder progreso", update.get("pause_reason", ""))
    elif update.get("status") == "active" and enrollment.get("status") == "paused":
        await record_event(db, enrollment, current_user["user_id"], "reactivated", "Proceso reactivado desde la última etapa válida", f"Continúa en {enrollment.get('current_stage_key')}")
    else:
        await record_event(db, enrollment, current_user["user_id"], "updated", "Inscripción actualizada", payload.next_action or payload.status or "")
    await evaluate_alerts(db)
    return await enrich_enrollment(await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0}))


@router.put("/enrollments/{enrollment_id}/stages/{stage_key}", response_model=dict)
async def update_stage(enrollment_id: str, stage_key: str, payload: StageUpdate, current_user: dict = Depends(require_participate)):
    enrollment = await load_enrollment(enrollment_id, current_user)
    if current_user.get("rol") == "persona" and enrollment["person_id"] != current_user.get("person_id"):
        raise HTTPException(status_code=403, detail="Solo puede actualizar su propio proceso")
    stage_doc = await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": stage_key})
    if not stage_doc: raise HTTPException(status_code=404, detail="Etapa no encontrada")
    update = payload.model_dump(exclude_none=True)
    if update.get("status") == "completed":
        if enrollment.get("process_key") == "consolidation" and enrollment.get("definition_version", 1) >= 2:
            if stage_doc.get("status") not in {"open", "in_progress"}:
                raise HTTPException(status_code=409, detail="Solo puede completar la etapa activa")
            if stage_key in {"retreat", "discipleship_handoff"}:
                raise HTTPException(status_code=409, detail="Cierre el Retiro desde la acción formal para registrar documentos y Discipulado")
            if stage_key == "welcome_party":
                membership = await db.person_memberships.find_one({"person_id": enrollment["person_id"], "status": "active", "acceptance_signed_at": {"$exists": True}}, {"_id": 1})
                if not membership:
                    raise HTTPException(status_code=409, detail="Registre la firma de la Carta de Membresía antes de cerrar la Fiesta")
                if enrollment.get("mentor_lbs_qualified") is not True:
                    raise HTTPException(status_code=409, detail="Evalúe o transfiera al mentor antes de iniciar LBS")
        missing = [item["label"] for item in stage_doc.get("tasks", []) if item.get("required") and not item.get("completed")]
        if missing: raise HTTPException(status_code=400, detail={"message": "Complete las tareas requeridas", "missing": missing})
        if enrollment["process_key"] == "seven_weeks" and (payload.attendance or stage_doc.get("attendance")) == "pending":
            raise HTTPException(status_code=400, detail="Registre la asistencia antes de completar la semana")
        update["completed_at"] = now_utc()
    if payload.attendance and payload.attendance != "pending": update["attendance_at"] = now_utc()
    update["updated_at"] = now_utc()
    await db.process_stage_progress.update_one({"_id": stage_doc["_id"]}, {"$set": update})
    enrollment_update = {"last_activity_at": now_utc(), "updated_at": now_utc()}
    if payload.next_action is not None: enrollment_update["next_action"] = payload.next_action
    if payload.next_action_at is not None: enrollment_update["next_action_at"] = payload.next_action_at
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": enrollment_update})
    await record_event(db, enrollment, current_user["user_id"], "stage_updated", f"Etapa {stage_doc['stage_name']} actualizada", payload.result or "")
    updated_enrollment = await recalculate_enrollment(db, enrollment_id, current_user["user_id"])
    await evaluate_alerts(db)
    return {"enrollment": updated_enrollment, "stage": serialize(await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": stage_key}, {"_id": 0}))}


@router.put("/enrollments/{enrollment_id}/stages/{stage_key}/tasks/{task_id}", response_model=dict)
async def update_task(enrollment_id: str, stage_key: str, task_id: str, payload: TaskUpdate, current_user: dict = Depends(require_participate)):
    enrollment = await load_enrollment(enrollment_id, current_user)
    stage_doc = await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": stage_key})
    if not stage_doc: raise HTTPException(status_code=404, detail="Etapa no encontrada")
    if enrollment.get("process_key") == "consolidation" and enrollment.get("definition_version", 1) >= 2 and stage_doc.get("status") == "locked":
        raise HTTPException(status_code=409, detail="La tarea pertenece a una etapa todavía bloqueada")
    tasks = stage_doc.get("tasks", []); found = False; now = now_utc()
    for task in tasks:
        if task["task_id"] == task_id:
            task["completed"] = payload.completed; task["completed_at"] = now if payload.completed else None; found = True; break
    if not found: raise HTTPException(status_code=404, detail="Tarea no encontrada")
    await db.process_stage_progress.update_one({"_id": stage_doc["_id"]}, {"$set": {"tasks": tasks, "status": "in_progress", "updated_at": now}})
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {"last_activity_at": now, "updated_at": now}})
    await record_event(db, enrollment, current_user["user_id"], "task_updated", "Tarea completada" if payload.completed else "Tarea reabierta", next(item["label"] for item in tasks if item["task_id"] == task_id))
    await evaluate_alerts(db)
    return {"tasks": serialize(tasks)}


@router.post("/enrollments/{enrollment_id}/evidence", status_code=status.HTTP_201_CREATED, response_model=dict)
async def add_evidence(enrollment_id: str, payload: EvidenceCreate, current_user: dict = Depends(require_participate)):
    enrollment = await load_enrollment(enrollment_id, current_user)
    if not payload.note and not payload.url: raise HTTPException(status_code=400, detail="Incluya nota o enlace de evidencia")
    stage = await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": payload.stage_key})
    if not stage: raise HTTPException(status_code=404, detail="Etapa no encontrada")
    evidence_id = str(uuid4()); now = now_utc()
    doc = {"_id": evidence_id, "evidence_id": evidence_id, "enrollment_id": enrollment_id, "person_id": enrollment["person_id"], **payload.model_dump(), "created_by_user_id": current_user["user_id"], "created_at": now}
    await db.process_evidence.insert_one(doc)
    if payload.task_id:
        tasks = stage.get("tasks", [])
        for task in tasks:
            if task["task_id"] == payload.task_id: task["evidence_count"] = task.get("evidence_count", 0) + 1
        await db.process_stage_progress.update_one({"_id": stage["_id"]}, {"$set": {"tasks": tasks, "updated_at": now}})
    await record_event(db, enrollment, current_user["user_id"], "evidence_added", "Evidencia registrada", payload.title)
    return serialize(doc)


@router.post("/enrollments/{enrollment_id}/contacts", status_code=status.HTTP_201_CREATED, response_model=dict)
async def add_contact(enrollment_id: str, payload: ContactCreate, current_user: dict = Depends(require_write)):
    enrollment = await load_enrollment(enrollment_id, current_user)
    if enrollment["process_key"] not in {"consolidation", "mentorship"}: raise HTTPException(status_code=400, detail="Contacto no aplica a este proceso")
    if payload.advance_stage and enrollment.get("process_key") == "consolidation" and enrollment.get("definition_version", 1) >= 2 and enrollment.get("current_stage_key") == "visitor_followup":
        raise HTTPException(status_code=409, detail="Inicie MCD desde la acción formal para asignar mentor y registrar la respuesta")
    update = {"last_contact_at": payload.occurred_at, "next_contact_at": payload.next_contact_at, "next_action": payload.next_action, "next_action_at": payload.next_contact_at, "last_activity_at": now_utc(), "updated_at": now_utc()}
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": update})
    if payload.advance_stage:
        definition = await get_definition(db, enrollment["process_key"], enrollment.get("definition_version"))
        current_index = next((index for index, item in enumerate(definition["stages"]) if item["key"] == enrollment["current_stage_key"]), 0)
        target = definition["stages"][min(current_index + 1, len(definition["stages"]) - 1)]["key"]
        await mark_prior_stages(enrollment, target, current_user["user_id"])
    await record_event(db, enrollment, current_user["user_id"], "contact", f"Contacto por {payload.channel}", payload.outcome)
    await evaluate_alerts(db)
    return await enrich_enrollment(await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0}))


@router.get("/mentorships", response_model=ItemList)
async def list_mentorships(current_user: dict = Depends(require_read)):
    allowed = await access_person_ids(db, current_user); query = {} if allowed is None else {"person_id": {"$in": list(allowed)}}
    docs = await db.mentorships.find(query, {"_id": 0}).sort("updated_at", -1).to_list(10000)
    items = []
    for doc in docs:
        item = serialize(doc); item["person"] = await person_summary(doc["person_id"]); item["mentor"] = await person_summary(doc["mentor_person_id"]); items.append(item)
    return {"items": items, "total": len(items)}


@router.post("/mentorships", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_mentorship(payload: MentorshipCreate, current_user: dict = Depends(require_write)):
    person = await load_person(payload.person_id); authorize_person(current_user, person, PROCESSES_WRITE); await validate_staff_assignee(payload.mentor_person_id, current_user)
    if await db.mentorships.find_one({"person_id": payload.person_id, "status": {"$in": ["active", "planned"]}}):
        raise HTTPException(status_code=409, detail="La Persona ya tiene una Mentoría activa")
    enrollment, _ = await create_enrollment(db, "mentorship", payload.person_id, current_user.get("person_id"), current_user["user_id"], status="active", next_action="Realizar primer encuentro", next_action_at=payload.next_meeting_at)
    await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": {"mentor_person_id": payload.mentor_person_id}})
    now = now_utc(); mentorship_id = str(uuid4())
    doc = {"_id": mentorship_id, "mentorship_id": mentorship_id, "enrollment_id": enrollment["enrollment_id"], **payload.model_dump(), "status": "active", "progress_pct": 0, "meeting_count": 0, "last_meeting_at": None, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.mentorships.insert_one(doc); await evaluate_alerts(db)
    return serialize(doc)


@router.get("/mentorships/{mentorship_id}", response_model=dict)
async def mentorship_detail(mentorship_id: str, current_user: dict = Depends(require_read)):
    doc = await db.mentorships.find_one({"mentorship_id": mentorship_id}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Mentoría no encontrada")
    enrollment = await load_enrollment(doc["enrollment_id"], current_user)
    meetings = await db.mentorship_meetings.find({"mentorship_id": mentorship_id}, {"_id": 0}).sort("occurred_at", -1).to_list(500)
    result = serialize(doc); result.update({"person": await person_summary(doc["person_id"]), "mentor": await person_summary(doc["mentor_person_id"]), "meetings": serialize(meetings), "enrollment": serialize(enrollment)})
    return result


@router.post("/mentorships/{mentorship_id}/meetings", status_code=status.HTTP_201_CREATED, response_model=dict)
async def add_mentorship_meeting(mentorship_id: str, payload: MentorshipMeetingCreate, current_user: dict = Depends(require_write)):
    mentorship = await db.mentorships.find_one({"mentorship_id": mentorship_id})
    if not mentorship: raise HTTPException(status_code=404, detail="Mentoría no encontrada")
    enrollment = await load_enrollment(mentorship["enrollment_id"], current_user)
    meeting_id = str(uuid4()); now = now_utc(); doc = {"_id": meeting_id, "meeting_id": meeting_id, "mentorship_id": mentorship_id, **payload.model_dump(), "recorded_by_user_id": current_user["user_id"], "created_at": now}
    await db.mentorship_meetings.insert_one(doc)
    count = await db.mentorship_meetings.count_documents({"mentorship_id": mentorship_id, "attended": True}); progress = min(100, count * 10)
    await db.mentorships.update_one({"mentorship_id": mentorship_id}, {"$set": {"meeting_count": count, "progress_pct": progress, "last_meeting_at": payload.occurred_at, "next_meeting_at": payload.next_meeting_at, "updated_at": now}})
    await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": {"last_contact_at": payload.occurred_at, "next_action": "Próximo encuentro de Mentoría", "next_action_at": payload.next_meeting_at, "last_activity_at": now, "updated_at": now}})
    if count == 1: await mark_prior_stages(enrollment, "active", current_user["user_id"])
    await record_event(db, enrollment, current_user["user_id"], "mentorship_meeting", "Encuentro de Mentoría registrado", payload.lesson_title or payload.notes or "")
    await evaluate_alerts(db); return serialize(doc)


async def cap_suggestions(person_id: str, gifts: list[str], interests: list[str]) -> list[dict]:
    talent = await db.person_talents.find_one({"person_id": person_id}, {"_id": 0}) or {}
    catalog_ids = [item for item in [talent.get("ocupacion_principal_id"), *(talent.get("habilidad_ids") or [])] if item]
    talents = await db.talent_catalog.find({"_id": {"$in": catalog_ids}}, {"_id": 0, "nombre": 1}).to_list(100)
    text = normalize(" ".join([*gifts, *interests, *(item.get("nombre", "") for item in talents)]))
    doors = await db.door_catalog.find({"active": True}, {"_id": 0}).sort("number", 1).to_list(20)
    suggestions = []
    for door in doors:
        matches = [keyword for keyword in door.get("keywords", []) if normalize(keyword) in text]
        suggestions.append({"door_key": door["door_key"], "name": door["name"], "score": min(100, 20 + len(matches) * 20) if matches else 10, "reasons": matches or ["Revisión humana recomendada"]})
    return sorted(suggestions, key=lambda item: (-item["score"], item["door_key"]))[:3]


@router.get("/cap", response_model=ItemList)
async def list_cap(current_user: dict = Depends(require_read)):
    allowed = await access_person_ids(db, current_user); query = {} if allowed is None else {"person_id": {"$in": list(allowed)}}
    docs = await db.cap_assessments.find(query, {"_id": 0}).sort("updated_at", -1).to_list(10000)
    items = []
    for doc in docs:
        item = serialize(doc); item["person"] = await person_summary(doc["person_id"]); items.append(item)
    return {"items": items, "total": len(items)}


@router.post("/cap", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_cap(payload: CapCreate, current_user: dict = Depends(require_write)):
    person = await load_person(payload.person_id); authorize_person(current_user, person, PROCESSES_WRITE)
    if await db.cap_assessments.find_one({"person_id": payload.person_id, "status": {"$ne": "completed"}}): raise HTTPException(status_code=409, detail="La Persona ya tiene una evaluación CAP activa")
    responsible = payload.responsible_person_id or current_user.get("person_id")
    if responsible: await validate_staff_assignee(responsible, current_user)
    enrollment, _ = await create_enrollment(db, "cap", payload.person_id, responsible, current_user["user_id"], status="active", next_action="Revisar dones y puertas sugeridas")
    suggestions = await cap_suggestions(payload.person_id, payload.gifts, payload.interests); now = now_utc(); cap_id = str(uuid4())
    doc = {"_id": cap_id, "cap_id": cap_id, "enrollment_id": enrollment["enrollment_id"], **payload.model_dump(), "suggested_doors": suggestions, "selected_door_key": None, "coverage_person_id": None, "activation_evidence": None, "continuous_training": None, "status": "door_suggested" if suggestions else "assessment", "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.cap_assessments.insert_one(doc)
    await mark_prior_stages(enrollment, doc["status"], current_user["user_id"]); await evaluate_alerts(db)
    return serialize(doc)


@router.put("/cap/{cap_id}", response_model=dict)
async def update_cap(cap_id: str, payload: CapUpdate, current_user: dict = Depends(require_write)):
    cap = await db.cap_assessments.find_one({"cap_id": cap_id})
    if not cap: raise HTTPException(status_code=404, detail="CAP no encontrado")
    enrollment = await load_enrollment(cap["enrollment_id"], current_user); update = payload.model_dump(exclude_none=True)
    gifts = update.get("gifts", cap.get("gifts", [])); interests = update.get("interests", cap.get("interests", []))
    if "gifts" in update or "interests" in update: update["suggested_doors"] = await cap_suggestions(cap["person_id"], gifts, interests)
    if update.get("selected_door_key") and not await db.door_catalog.find_one({"door_key": update["selected_door_key"], "active": True}): raise HTTPException(status_code=400, detail="Puerta inválida")
    if update.get("coverage_person_id"): await validate_staff_assignee(update["coverage_person_id"], current_user)
    target_status = update.get("status")
    if target_status == "completed":
        effective = {**cap, **update}
        missing = [label for field, label in [("selected_door_key", "puerta"), ("activation_evidence", "evidencia de servicio"), ("coverage_person_id", "cobertura"), ("continuous_training", "formación continua")] if not effective.get(field)]
        if missing: raise HTTPException(status_code=400, detail={"message": "CAP incompleto", "missing": missing})
    update["updated_at"] = now_utc(); await db.cap_assessments.update_one({"cap_id": cap_id}, {"$set": update})
    if target_status: await mark_prior_stages(enrollment, target_status, current_user["user_id"])
    if target_status == "completed":
        current_stage = await db.process_stage_progress.find_one({"enrollment_id": enrollment["enrollment_id"], "stage_key": "completed"})
        tasks = current_stage.get("tasks", []) if current_stage else []
        for task in tasks: task.update({"completed": True, "completed_at": now_utc()})
        await db.process_stage_progress.update_one({"enrollment_id": enrollment["enrollment_id"], "stage_key": "completed"}, {"$set": {"tasks": tasks, "status": "completed", "completed_at": now_utc()}})
        await recalculate_enrollment(db, enrollment["enrollment_id"], current_user["user_id"])
    await record_event(db, enrollment, current_user["user_id"], "cap_updated", "CAP actualizado", target_status or "Evaluación actualizada")
    await evaluate_alerts(db); return serialize(await db.cap_assessments.find_one({"cap_id": cap_id}, {"_id": 0}))


@router.get("/alerts", response_model=ItemList)
async def list_alerts(status_filter: str = "open", severity: Optional[str] = None, current_user: dict = Depends(require_read)):
    await evaluate_alerts(db); query = {"status": status_filter}
    if severity: query["severity"] = severity
    allowed = await access_person_ids(db, current_user)
    if allowed is not None: query["person_id"] = {"$in": list(allowed)}
    docs = await db.process_alerts.find(query, {"_id": 0}).sort([("severity", 1), ("detected_at", -1)]).to_list(10000)
    items = []
    for doc in docs:
        item = serialize(doc); item["person"] = await person_summary(doc["person_id"]); items.append(item)
    return {"items": items, "total": len(items)}


@router.put("/alerts/{alert_id}", response_model=dict)
async def update_alert(alert_id: str, payload: AlertAction, current_user: dict = Depends(require_write)):
    alert = await db.process_alerts.find_one({"alert_id": alert_id})
    if not alert: raise HTTPException(status_code=404, detail="Alerta no encontrada")
    enrollment = await load_enrollment(alert["enrollment_id"], current_user); now = now_utc()
    update = {"status": payload.status, "resolution": payload.resolution, "updated_at": now, "handled_by_user_id": current_user["user_id"]}
    if payload.status == "resolved": update["resolved_at"] = now
    await db.process_alerts.update_one({"_id": alert["_id"]}, {"$set": update})
    await record_event(db, enrollment, current_user["user_id"], "alert_updated", f"Alerta {payload.status}", payload.resolution or alert["fact"])
    return serialize(await db.process_alerts.find_one({"alert_id": alert_id}, {"_id": 0}))


@router.get("/alert-rules", response_model=ItemList)
async def list_alert_rules(current_user: dict = Depends(require_read)):
    docs = await db.process_alert_rules.find({}, {"_id": 0}).sort("name", 1).to_list(100)
    return {"items": serialize(docs), "total": len(docs)}


@router.put("/alert-rules/{rule_key}", response_model=dict)
async def update_alert_rule(rule_key: str, payload: AlertRuleUpdate, current_user: dict = Depends(require_manage)):
    if not has_capability(current_user, PROCESS_ALERTS_MANAGE): raise HTTPException(status_code=403, detail="Configuración de alertas restringida")
    update = payload.model_dump(exclude_none=True); update["updated_at"] = now_utc()
    result = await db.process_alert_rules.update_one({"rule_key": rule_key}, {"$set": update})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Regla no encontrada")
    await evaluate_alerts(db); return serialize(await db.process_alert_rules.find_one({"rule_key": rule_key}, {"_id": 0}))


@router.get("/dashboard", response_model=dict)
async def dashboard(current_user: dict = Depends(require_read)):
    await evaluate_alerts(db); query = await scoped_enrollment_query(current_user, {})
    enrollments = await db.process_enrollments.find(query, {"_id": 0}).to_list(10000); now = now_utc()
    metrics = {"total": len({item["person_id"] for item in enrollments}), "on_sla": 0, "due_soon": 0, "overdue": 0, "without_responsible": 0, "without_next_action": 0, "completed": 0, "stalled": 0}
    by_stage = {}; progress_values = []
    for item in enrollments:
        by_stage[f"{item['process_key']}:{item.get('current_stage_key')}"] = by_stage.get(f"{item['process_key']}:{item.get('current_stage_key')}", 0) + 1
        if not item.get("responsible_person_id") and item.get("status") != "completed": metrics["without_responsible"] += 1
        if not item.get("next_action") and item.get("status") != "completed": metrics["without_next_action"] += 1
        if item.get("status") == "completed": metrics["completed"] += 1
        progress_values.append(item.get("progress_pct", 0))
        stage = await db.process_stage_progress.find_one({"enrollment_id": item["enrollment_id"], "stage_key": item.get("current_stage_key")}, {"_id": 0})
        due = stage.get("due_at") if stage else item.get("next_action_at")
        if due:
            due = due.replace(tzinfo=timezone.utc) if due.tzinfo is None else due
            hours = (due - now).total_seconds() / 3600
            if hours < 0: metrics["overdue"] += 1; metrics["stalled"] += 1
            elif hours <= 48: metrics["due_soon"] += 1
            else: metrics["on_sla"] += 1
        elif item.get("status") == "active": metrics["on_sla"] += 1
    metrics["average_progress"] = round(sum(progress_values) / max(1, len(progress_values)), 1)
    eligible = [item for item in enrollments if item.get("status") not in {"planned", "cancelled"}]
    metrics["retention"] = round((len([item for item in eligible if item.get("status") in {"active", "completed"}]) / max(1, len(eligible))) * 100, 1)
    alert_query = {"status": "open"}; allowed = await access_person_ids(db, current_user)
    if allowed is not None: alert_query["person_id"] = {"$in": list(allowed)}
    alerts = await db.process_alerts.find(alert_query, {"_id": 0}).sort("detected_at", -1).limit(12).to_list(12)
    metrics["critical_alerts"] = sum(1 for item in alerts if item.get("severity") == "critical")
    alert_items = []
    for item in alerts:
        enriched = serialize(item); enriched["person"] = await person_summary(item["person_id"]); alert_items.append(enriched)
    definitions = await db.process_definitions.find({"active": True}, {"_id": 0, "process_key": 1, "name": 1, "stages": 1}).to_list(20)
    return {"metrics": metrics, "by_stage": by_stage, "alerts": alert_items, "definitions": serialize(definitions), "generated_at": iso_z(now), "scope": "global" if current_user.get("rol") == "pastor" else "assigned"}


@router.post("/migrate", response_model=MigrationResponse)
async def migrate(current_user: dict = Depends(require_manage)):
    result = await migrate_legacy_processes(db, current_user["user_id"]); await evaluate_alerts(db)
    await db.process_migrations.insert_one({"_id": str(uuid4()), "migration_key": "mega_block_b_v1", "actor_user_id": current_user["user_id"], "result": result, "completed_at": now_utc()})
    return result