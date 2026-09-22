from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from access_control import (
    FORMATION_ATTENDANCE_WRITE, FORMATION_COHORTS_MANAGE,
    FORMATION_ENROLL, FORMATION_GRADES_READ, FORMATION_GRADES_WRITE,
    FORMATION_HISTORICAL_CREDIT_MANAGE, FORMATION_PROGRAMS_MANAGE,
    FORMATION_PROGRESS_MANAGE, FORMATION_PROMOTE, FORMATION_READ,
    can_access_person, has_capability, is_global_pastoral_authority,
)
from formation_engine import (
    audit, canonical_person, module_eligibility, next_recommended_module,
    now_utc, recalculate_enrollment, require_cohort_access,
    require_person_access, serialize,
)
from formation_models import (
    AssessmentInput, AttendanceBulkInput, CohortInput, CohortStaffInput,
    EnrollmentInput, EnrollmentStatusInput, GradeBulkInput,
    HistoricalCreditInput, ManualApprovalInput, ModuleInput, ProgramInput, PromotionInput,
    PrerequisitesInput, SessionInput,
)
from server import db, get_current_user


router = APIRouter(prefix="/api/formation", tags=["formation"])


def require(user: dict, capability: str) -> None:
    if not is_global_pastoral_authority(user) and not has_capability(user, capability):
        raise HTTPException(status_code=403, detail="Sin permiso para esta operación educativa")


async def program_doc(program_id: str) -> dict:
    item = await db.formation_programs.find_one({"program_id": program_id}, {"_id": 0})
    if not item: raise HTTPException(status_code=404, detail="Programa no encontrado")
    return item


async def module_doc(module_id: str) -> dict:
    item = await db.formation_modules.find_one({"module_id": module_id}, {"_id": 0})
    if not item: raise HTTPException(status_code=404, detail="Módulo no encontrado")
    return item


async def cohort_doc(cohort_id: str) -> dict:
    item = await db.formation_cohorts.find_one({"cohort_id": cohort_id}, {"_id": 0})
    if not item: raise HTTPException(status_code=404, detail="Cohorte no encontrada")
    return item


@router.get("/programs", response_model=dict)
async def list_programs(include_inactive: bool = False, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_READ)
    query = {} if include_inactive and (is_global_pastoral_authority(current_user) or has_capability(current_user, FORMATION_PROGRAMS_MANAGE)) else {"active": True}
    items = await db.formation_programs.find(query, {"_id": 0}).sort("name", 1).to_list(1000)
    return {"items": serialize(items), "total": len(items)}


@router.post("/programs", status_code=201, response_model=dict)
async def create_program(payload: ProgramInput, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_PROGRAMS_MANAGE)
    program_id, now = str(uuid4()), now_utc()
    doc = {"_id": program_id, "program_id": program_id, **payload.model_dump(), "version": 1, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.formation_programs.insert_one(doc)
    await audit(db, current_user, "program_created", "formation_program", program_id, None, doc)
    return serialize(doc)


@router.put("/programs/{program_id}", response_model=dict)
async def update_program(program_id: str, payload: ProgramInput, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_PROGRAMS_MANAGE); before = await program_doc(program_id)
    updates = {**payload.model_dump(), "updated_by_user_id": current_user["user_id"], "updated_at": now_utc(), "version": int(before.get("version", 1)) + 1}
    await db.formation_programs.update_one({"program_id": program_id}, {"$set": updates})
    after = await program_doc(program_id); await audit(db, current_user, "program_updated", "formation_program", program_id, before, after)
    return serialize(after)


@router.get("/programs/{program_id}/modules", response_model=dict)
async def list_modules(program_id: str, include_inactive: bool = False, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_READ); await program_doc(program_id)
    query = {"program_id": program_id}
    if not include_inactive: query["active"] = True
    items = await db.formation_modules.find(query, {"_id": 0}).sort("order", 1).to_list(1000)
    for item in items:
        item["prerequisite_module_ids"] = await db.formation_module_prerequisites.distinct("prerequisite_module_id", {"module_id": item["module_id"], "active": True})
    return {"items": serialize(items), "total": len(items)}


@router.post("/programs/{program_id}/modules", status_code=201, response_model=dict)
async def create_module(program_id: str, payload: ModuleInput, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_PROGRAMS_MANAGE); program = await program_doc(program_id)
    module_id, now = str(uuid4()), now_utc()
    doc = {"_id": module_id, "module_id": module_id, "program_id": program_id, "program_name_snapshot": program["name"], **payload.model_dump(), "version": 1, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.formation_modules.insert_one(doc); await audit(db, current_user, "module_created", "formation_module", module_id, None, doc)
    return serialize(doc)


@router.put("/modules/{module_id}", response_model=dict)
async def update_module(module_id: str, payload: ModuleInput, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_PROGRAMS_MANAGE); before = await module_doc(module_id)
    updates = {**payload.model_dump(), "updated_by_user_id": current_user["user_id"], "updated_at": now_utc(), "version": int(before.get("version", 1)) + 1}
    await db.formation_modules.update_one({"module_id": module_id}, {"$set": updates})
    after = await module_doc(module_id); await audit(db, current_user, "module_updated", "formation_module", module_id, before, after)
    return serialize(after)


async def introduces_cycle(module_id: str, prerequisite_ids: list[str]) -> bool:
    graph = {}
    async for item in db.formation_module_prerequisites.find({"active": True}, {"_id": 0, "module_id": 1, "prerequisite_module_id": 1}):
        graph.setdefault(item["module_id"], set()).add(item["prerequisite_module_id"])
    graph[module_id] = set(prerequisite_ids)
    def visit(node, path):
        if node in path: return True
        return any(visit(child, path | {node}) for child in graph.get(node, set()))
    return visit(module_id, set())


@router.put("/modules/{module_id}/prerequisites", response_model=dict)
async def set_prerequisites(module_id: str, payload: PrerequisitesInput, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_PROGRAMS_MANAGE); module = await module_doc(module_id)
    if module_id in payload.prerequisite_module_ids: raise HTTPException(status_code=422, detail="Un módulo no puede ser su propio prerrequisito")
    prerequisites = [await module_doc(item) for item in payload.prerequisite_module_ids]
    if any(item["program_id"] != module["program_id"] for item in prerequisites): raise HTTPException(status_code=422, detail="Los prerrequisitos deben pertenecer al mismo programa")
    if await introduces_cycle(module_id, payload.prerequisite_module_ids): raise HTTPException(status_code=409, detail="Los prerrequisitos crean un ciclo")
    before = await db.formation_module_prerequisites.find({"module_id": module_id}, {"_id": 0}).to_list(1000); now = now_utc()
    await db.formation_module_prerequisites.update_many({"module_id": module_id}, {"$set": {"active": False, "updated_at": now}})
    for prerequisite_id in payload.prerequisite_module_ids:
        await db.formation_module_prerequisites.update_one({"module_id": module_id, "prerequisite_module_id": prerequisite_id}, {"$set": {"active": True, "mode": payload.mode, "updated_by_user_id": current_user["user_id"], "updated_at": now}, "$setOnInsert": {"_id": str(uuid4()), "created_at": now}}, upsert=True)
    after = await db.formation_module_prerequisites.find({"module_id": module_id, "active": True}, {"_id": 0}).to_list(1000)
    await audit(db, current_user, "module_prerequisites_updated", "formation_module", module_id, before, after)
    return {"module_id": module_id, "items": serialize(after)}


@router.get("/cohorts", response_model=dict)
async def list_cohorts(status_filter: Optional[str] = Query(default=None, alias="status"), current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_READ); query = {}
    if status_filter: query["status"] = status_filter
    if not is_global_pastoral_authority(current_user) and current_user.get("access_scope", {}).get("persons") != "all":
        cohort_ids = await db.formation_cohort_staff.distinct("cohort_id", {"person_id": current_user.get("person_id"), "active": True})
        query["cohort_id"] = {"$in": cohort_ids}
    items = await db.formation_cohorts.find(query, {"_id": 0}).sort("start_date", -1).to_list(2000)
    return {"items": serialize(items), "total": len(items)}


@router.post("/cohorts", status_code=201, response_model=dict)
async def create_cohort(payload: CohortInput, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_COHORTS_MANAGE); module = await module_doc(payload.module_id); program = await program_doc(module["program_id"])
    cohort_id, now = str(uuid4()), now_utc()
    doc = {"_id": cohort_id, "cohort_id": cohort_id, **payload.model_dump(), "program_id": module["program_id"], "program_name_snapshot": program["name"], "module_name_snapshot": module["name"], "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.formation_cohorts.insert_one(doc); await audit(db, current_user, "cohort_created", "formation_cohort", cohort_id, None, doc)
    return serialize(doc)


@router.put("/cohorts/{cohort_id}", response_model=dict)
async def update_cohort(cohort_id: str, payload: CohortInput, current_user: dict = Depends(get_current_user)):
    before = await cohort_doc(cohort_id); await require_cohort_access(db, before, current_user, FORMATION_COHORTS_MANAGE)
    if payload.module_id != before["module_id"]: raise HTTPException(status_code=409, detail="No se puede cambiar el módulo de una cohorte existente")
    updates = {**payload.model_dump(), "updated_by_user_id": current_user["user_id"], "updated_at": now_utc()}
    await db.formation_cohorts.update_one({"cohort_id": cohort_id}, {"$set": updates}); after = await cohort_doc(cohort_id)
    await audit(db, current_user, "cohort_updated", "formation_cohort", cohort_id, before, after); return serialize(after)


@router.post("/cohorts/{cohort_id}/staff", status_code=201, response_model=dict)
async def assign_staff(cohort_id: str, payload: CohortStaffInput, current_user: dict = Depends(get_current_user)):
    cohort = await cohort_doc(cohort_id); await require_cohort_access(db, cohort, current_user, FORMATION_COHORTS_MANAGE)
    person = await canonical_person(db, payload.person_id); now = now_utc()
    before = await db.formation_cohort_staff.find_one({"cohort_id": cohort_id, "person_id": payload.person_id, "role": payload.role}, {"_id": 0})
    await db.formation_cohort_staff.update_one({"cohort_id": cohort_id, "person_id": payload.person_id, "role": payload.role}, {"$set": {"active": True, "assigned_by_user_id": current_user["user_id"], "started_at": (before or {}).get("started_at") or now, "ended_at": None, "updated_at": now}, "$setOnInsert": {"_id": str(uuid4()), "created_at": now}}, upsert=True)
    after = await db.formation_cohort_staff.find_one({"cohort_id": cohort_id, "person_id": payload.person_id, "role": payload.role}, {"_id": 0})
    await audit(db, current_user, "cohort_staff_assigned", "formation_cohort_staff", f"{cohort_id}:{payload.person_id}:{payload.role}", before, after, person_id=payload.person_id)
    return serialize(after)


@router.delete("/cohorts/{cohort_id}/staff/{person_id}", response_model=dict)
async def revoke_staff(cohort_id: str, person_id: str, current_user: dict = Depends(get_current_user)):
    cohort = await cohort_doc(cohort_id); await require_cohort_access(db, cohort, current_user, FORMATION_COHORTS_MANAGE)
    before = await db.formation_cohort_staff.find({"cohort_id": cohort_id, "person_id": person_id, "active": True}, {"_id": 0}).to_list(20)
    if not before: raise HTTPException(status_code=404, detail="Profesor no asignado")
    now = now_utc(); await db.formation_cohort_staff.update_many({"cohort_id": cohort_id, "person_id": person_id, "active": True}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "updated_at": now}})
    await audit(db, current_user, "cohort_staff_revoked", "formation_cohort_staff", f"{cohort_id}:{person_id}", before, {"active": False, "ended_at": now}, person_id=person_id)
    return {"revoked": True}


@router.post("/cohorts/{cohort_id}/sessions", status_code=201, response_model=dict)
async def create_session(cohort_id: str, payload: SessionInput, current_user: dict = Depends(get_current_user)):
    cohort = await cohort_doc(cohort_id); await require_cohort_access(db, cohort, current_user, FORMATION_COHORTS_MANAGE)
    if payload.teacher_person_id: await canonical_person(db, payload.teacher_person_id)
    session_id, now = str(uuid4()), now_utc(); sequence = await db.formation_sessions.count_documents({"cohort_id": cohort_id}) + 1
    doc = {"_id": session_id, "session_id": session_id, "cohort_id": cohort_id, "module_id": cohort["module_id"], "sequence": sequence, **payload.model_dump(), "status": "scheduled", "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.formation_sessions.insert_one(doc); await audit(db, current_user, "session_created", "formation_session", session_id, None, doc)
    return serialize(doc)


@router.get("/cohorts/{cohort_id}", response_model=dict)
async def cohort_detail(cohort_id: str, current_user: dict = Depends(get_current_user)):
    cohort = await cohort_doc(cohort_id); await require_cohort_access(db, cohort, current_user, FORMATION_READ)
    sessions = await db.formation_sessions.find({"cohort_id": cohort_id}, {"_id": 0}).sort("sequence", 1).to_list(1000)
    staff = await db.formation_cohort_staff.find({"cohort_id": cohort_id, "active": True}, {"_id": 0}).to_list(100)
    enrollments = await db.formation_enrollments.find({"cohort_id": cohort_id}, {"_id": 0}).sort("person_name_snapshot", 1).to_list(5000)
    assessments = await db.formation_assessments.find({"cohort_id": cohort_id, "active": True}, {"_id": 0}).to_list(1000)
    return {"cohort": serialize(cohort), "sessions": serialize(sessions), "staff": serialize(staff), "enrollments": serialize(enrollments), "assessments": serialize(assessments)}


@router.post("/cohorts/{cohort_id}/enrollments", status_code=201, response_model=dict)
async def enroll(cohort_id: str, payload: EnrollmentInput, current_user: dict = Depends(get_current_user)):
    cohort = await cohort_doc(cohort_id); await require_cohort_access(db, cohort, current_user, FORMATION_ENROLL)
    person = await canonical_person(db, payload.person_id); module = await module_doc(cohort["module_id"]); eligibility = await module_eligibility(db, payload.person_id, module)
    if not eligibility["eligible"] and not payload.override_eligibility: raise HTTPException(status_code=409, detail="La Persona no cumple los prerrequisitos")
    count = await db.formation_enrollments.count_documents({"cohort_id": cohort_id, "status": {"$in": ["enrolled", "in_progress"]}})
    if count >= cohort["capacity"]: raise HTTPException(status_code=409, detail="La cohorte alcanzó su capacidad")
    existing = await db.formation_enrollments.find_one({"cohort_id": cohort_id, "person_id": payload.person_id}, {"_id": 0})
    if existing: return serialize(existing)
    enrollment_id, now = str(uuid4()), now_utc()
    doc = {"_id": enrollment_id, "enrollment_id": enrollment_id, "cohort_id": cohort_id, "cohort_name_snapshot": cohort["name"], "program_id": cohort["program_id"], "module_id": cohort["module_id"], "person_id": payload.person_id, "person_name_snapshot": person["name"], "program_name_snapshot": cohort["program_name_snapshot"], "module_name_snapshot": cohort["module_name_snapshot"], "status": "enrolled", "attendance_pct": 0, "final_grade_pct": None, "progress_pct": 0, "eligibility_snapshot": eligibility, "override_eligibility": payload.override_eligibility, "override_reason": payload.override_reason, "enrolled_by_user_id": current_user["user_id"], "enrolled_at": now, "created_at": now, "updated_at": now}
    await db.formation_enrollments.insert_one(doc); await audit(db, current_user, "person_enrolled", "formation_enrollment", enrollment_id, None, doc, payload.override_reason, payload.person_id)
    return serialize(doc)


@router.put("/sessions/{session_id}/attendance", response_model=dict)
async def save_attendance(session_id: str, payload: AttendanceBulkInput, current_user: dict = Depends(get_current_user)):
    session = await db.formation_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not session: raise HTTPException(status_code=404, detail="Sesión no encontrada")
    cohort = await cohort_doc(session["cohort_id"]); await require_cohort_access(db, cohort, current_user, FORMATION_ATTENDANCE_WRITE)
    changed, now = [], now_utc()
    for item in payload.items:
        enrollment = await db.formation_enrollments.find_one({"enrollment_id": item.enrollment_id, "cohort_id": cohort["cohort_id"]}, {"_id": 0})
        if not enrollment: raise HTTPException(status_code=422, detail="La inscripción no pertenece a esta cohorte")
        before = await db.formation_attendance.find_one({"session_id": session_id, "enrollment_id": item.enrollment_id}, {"_id": 0})
        attendance_id = (before or {}).get("attendance_id") or str(uuid4())
        data = {"attendance_id": attendance_id, "session_id": session_id, "cohort_id": cohort["cohort_id"], "enrollment_id": item.enrollment_id, "person_id": enrollment["person_id"], **item.model_dump(), "recorded_by_user_id": current_user["user_id"], "updated_at": now}
        await db.formation_attendance.update_one({"session_id": session_id, "enrollment_id": item.enrollment_id}, {"$set": data, "$setOnInsert": {"_id": attendance_id, "created_at": now}}, upsert=True)
        await audit(db, current_user, "attendance_changed", "formation_attendance", attendance_id, before, data, person_id=enrollment["person_id"])
        changed.append(await recalculate_enrollment(db, item.enrollment_id, current_user, "Asistencia actualizada"))
    return {"updated": len(changed), "enrollments": changed}


@router.post("/cohorts/{cohort_id}/assessments", status_code=201, response_model=dict)
async def create_assessment(cohort_id: str, payload: AssessmentInput, current_user: dict = Depends(get_current_user)):
    cohort = await cohort_doc(cohort_id); await require_cohort_access(db, cohort, current_user, FORMATION_COHORTS_MANAGE)
    existing_assessments = await db.formation_assessments.find({"cohort_id": cohort_id, "active": True}, {"_id": 0, "weight": 1}).to_list(1000)
    current_weight = sum(float(item.get("weight", 0)) for item in existing_assessments)
    if current_weight + payload.weight > 100.001: raise HTTPException(status_code=422, detail="La ponderación total supera 100%")
    assessment_id, now = str(uuid4()), now_utc(); doc = {"_id": assessment_id, "assessment_id": assessment_id, "cohort_id": cohort_id, "module_id": cohort["module_id"], **payload.model_dump(), "active": True, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.formation_assessments.insert_one(doc); await audit(db, current_user, "assessment_created", "formation_assessment", assessment_id, None, doc); return serialize(doc)


@router.put("/assessments/{assessment_id}/grades", response_model=dict)
async def save_grades(assessment_id: str, payload: GradeBulkInput, current_user: dict = Depends(get_current_user)):
    assessment = await db.formation_assessments.find_one({"assessment_id": assessment_id, "active": True}, {"_id": 0})
    if not assessment: raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    cohort = await cohort_doc(assessment["cohort_id"]); await require_cohort_access(db, cohort, current_user, FORMATION_GRADES_WRITE)
    updated, now = [], now_utc()
    for item in payload.items:
        if item.score > assessment["max_score"]: raise HTTPException(status_code=422, detail="La nota excede el máximo")
        enrollment = await db.formation_enrollments.find_one({"enrollment_id": item.enrollment_id, "cohort_id": cohort["cohort_id"]}, {"_id": 0})
        if not enrollment: raise HTTPException(status_code=422, detail="La inscripción no pertenece a esta cohorte")
        before = await db.formation_grades.find_one({"assessment_id": assessment_id, "enrollment_id": item.enrollment_id}, {"_id": 0}); grade_id = (before or {}).get("grade_id") or str(uuid4())
        data = {"grade_id": grade_id, "assessment_id": assessment_id, "cohort_id": cohort["cohort_id"], "enrollment_id": item.enrollment_id, "person_id": enrollment["person_id"], **item.model_dump(), "recorded_by_user_id": current_user["user_id"], "updated_at": now}
        await db.formation_grades.update_one({"assessment_id": assessment_id, "enrollment_id": item.enrollment_id}, {"$set": data, "$setOnInsert": {"_id": grade_id, "created_at": now}}, upsert=True)
        await audit(db, current_user, "grade_changed", "formation_grade", grade_id, before, data, person_id=enrollment["person_id"])
        updated.append(await recalculate_enrollment(db, item.enrollment_id, current_user, "Calificación actualizada"))
    return {"updated": len(updated), "enrollments": updated}


@router.put("/enrollments/{enrollment_id}/status", response_model=dict)
async def set_enrollment_status(enrollment_id: str, payload: EnrollmentStatusInput, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_PROGRESS_MANAGE); before = await db.formation_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    if not before: raise HTTPException(status_code=404, detail="Inscripción no encontrada")
    updates = {"status": payload.status, "status_reason": payload.reason, "updated_by_user_id": current_user["user_id"], "updated_at": now_utc()}
    await db.formation_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": updates}); after = await db.formation_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    await audit(db, current_user, "enrollment_status_overridden", "formation_enrollment", enrollment_id, before, after, payload.reason, before["person_id"]); return serialize(after)


@router.post("/enrollments/{enrollment_id}/approve", response_model=dict)
async def manually_approve(enrollment_id: str, payload: ManualApprovalInput, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_PROGRESS_MANAGE); before = await db.formation_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    if not before: raise HTTPException(status_code=404, detail="Inscripción no encontrada")
    now = now_utc(); updates = {"status": "completed", "completed_at": before.get("completed_at") or now, "manual_approval_reason": payload.reason, "approved_by_user_id": current_user["user_id"], "updated_at": now}
    await db.formation_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": updates}); after = await db.formation_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    achievement_id = str(uuid4())
    await db.formation_achievements.update_one({"person_id": before["person_id"], "module_id": before["module_id"], "active": True}, {"$setOnInsert": {"_id": achievement_id, "achievement_id": achievement_id, "person_id": before["person_id"], "program_id": before["program_id"], "module_id": before["module_id"], "status": "completed", "source": "manual_approval", "enrollment_id": enrollment_id, "program_name_snapshot": before["program_name_snapshot"], "module_name_snapshot": before["module_name_snapshot"], "completed_at": updates["completed_at"], "attendance_pct": before.get("attendance_pct"), "final_grade_pct": before.get("final_grade_pct"), "active": True, "created_at": now}}, upsert=True)
    await audit(db, current_user, "enrollment_manually_approved", "formation_enrollment", enrollment_id, before, after, payload.reason, before["person_id"]); return serialize(after)


@router.post("/persons/{person_id}/historical-credits", status_code=201, response_model=dict)
async def historical_credit(person_id: str, payload: HistoricalCreditInput, current_user: dict = Depends(get_current_user)):
    person = await require_person_access(db, current_user, person_id, FORMATION_HISTORICAL_CREDIT_MANAGE); module = await module_doc(payload.module_id); program = await program_doc(module["program_id"])
    before = await db.formation_achievements.find_one({"person_id": person_id, "module_id": payload.module_id, "active": True}, {"_id": 0})
    if before and before.get("status") == "completed": raise HTTPException(status_code=409, detail="El módulo ya fue completado mediante una cohorte")
    achievement_id, now = (before or {}).get("achievement_id") or str(uuid4()), now_utc()
    data = {"achievement_id": achievement_id, "person_id": person_id, "program_id": program["program_id"], "module_id": module["module_id"], "status": "historical_accredited", "source": "historical_accreditation", "program_name_snapshot": program["name"], "module_name_snapshot": module["name"], "historical_completion_date": payload.historical_completion_date, "date_precision": payload.date_precision if payload.historical_completion_date else "unknown", "evidence_document_id": payload.evidence_document_id, "observation": payload.observation, "attendance_pct": None, "final_grade_pct": None, "accredited_by_user_id": current_user["user_id"], "accredited_at": now, "active": True, "updated_at": now}
    await db.formation_achievements.update_one({"person_id": person_id, "module_id": payload.module_id, "active": True}, {"$set": data, "$setOnInsert": {"_id": achievement_id, "created_at": now}}, upsert=True)
    await audit(db, current_user, "historical_formation_accredited", "formation_achievement", achievement_id, before, data, payload.observation, person_id)
    return {**serialize(data), "person": person, "next_recommended": await next_recommended_module(db, person_id, program["program_id"])}


@router.post("/enrollments/{enrollment_id}/promote", status_code=201, response_model=dict)
async def promote(enrollment_id: str, payload: PromotionInput, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_PROMOTE); source = await db.formation_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    if not source or source.get("status") != "completed": raise HTTPException(status_code=409, detail="Complete primero el módulo actual")
    target = await cohort_doc(payload.target_cohort_id); next_module = await next_recommended_module(db, source["person_id"], source["program_id"])
    if not next_module or target["module_id"] != next_module["module_id"]: raise HTTPException(status_code=409, detail="La cohorte no corresponde al próximo módulo elegible")
    result = await enroll(target["cohort_id"], EnrollmentInput(person_id=source["person_id"]), current_user)
    await audit(db, current_user, "person_promoted", "formation_enrollment", result["enrollment_id"], source, result, payload.reason, source["person_id"])
    return result


@router.get("/persons/{person_id}/progress", response_model=dict)
async def person_progress(person_id: str, current_user: dict = Depends(get_current_user)):
    person = await require_person_access(db, current_user, person_id, FORMATION_READ)
    can_see_grades = is_global_pastoral_authority(current_user) or has_capability(current_user, FORMATION_GRADES_READ) or current_user.get("person_id") == person_id
    programs = await db.formation_programs.find({"active": True}, {"_id": 0}).sort("name", 1).to_list(1000)
    rows = []
    for program in programs:
        modules = await db.formation_modules.find({"program_id": program["program_id"], "active": True}, {"_id": 0}).sort("order", 1).to_list(1000)
        for module in modules:
            achievement = await db.formation_achievements.find_one({"person_id": person_id, "module_id": module["module_id"], "active": True}, {"_id": 0})
            enrollment = await db.formation_enrollments.find_one({"person_id": person_id, "module_id": module["module_id"]}, {"_id": 0}, sort=[("enrolled_at", -1)])
            eligibility = await module_eligibility(db, person_id, module)
            row_status = achievement.get("status") if achievement else enrollment.get("status") if enrollment else "eligible" if eligibility["eligible"] else "not_started"
            rows.append({"program_id": program["program_id"], "program_name": program["name"], "program_purpose": program.get("purpose"), "module_id": module["module_id"], "module_name": module["name"], "order": module["order"], "status": row_status, "cohort_id": (enrollment or {}).get("cohort_id"), "cohort_name": (enrollment or {}).get("cohort_name_snapshot"), "attendance_pct": (achievement or enrollment or {}).get("attendance_pct"), "final_grade_pct": (achievement or enrollment or {}).get("final_grade_pct") if can_see_grades else None, "completed_at": (achievement or enrollment or {}).get("completed_at") or (achievement or {}).get("historical_completion_date"), "eligibility": eligibility, "source": (achievement or {}).get("source")})
    legacy = await db.process_enrollments.find({"person_id": person_id, "process_key": "discipleship"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"person": person, "items": serialize(rows), "next_recommended": await next_recommended_module(db, person_id), "legacy_discipleship": serialize(legacy), "legacy_read_only": True}


@router.get("/reports/{report_key}", response_model=dict)
async def formation_report(report_key: str, program_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    require(current_user, FORMATION_READ)
    if report_key not in {"graduates", "pending", "eligible"}: raise HTTPException(status_code=404, detail="Reporte no encontrado")
    items = []
    if report_key == "pending":
        query = {"status": {"$in": ["enrolled", "in_progress", "incomplete", "remediation_required"]}}
        if program_id: query["program_id"] = program_id
        items = await db.formation_enrollments.find(query, {"_id": 0}).sort("updated_at", -1).to_list(5000)
    else:
        person_ids = await db.persons.distinct("_id", {"is_archived": {"$ne": True}})
        for oid in person_ids[:5000]:
            person_id = str(oid)
            if report_key == "eligible":
                next_module = await next_recommended_module(db, person_id, program_id)
                if next_module: items.append({"person_id": person_id, "next_recommended": next_module})
            else:
                modules = await db.formation_modules.count_documents({"program_id": program_id, "active": True}) if program_id else 0
                achievements = await db.formation_achievements.count_documents({"person_id": person_id, "program_id": program_id, "active": True, "status": {"$in": ["completed", "historical_accredited"]}}) if program_id else 0
                if modules and modules == achievements: items.append({"person_id": person_id, "program_id": program_id, "completed_modules": achievements})
    return {"report": report_key, "items": serialize(items), "total": len(items)}