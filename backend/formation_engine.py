from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException

from access_control import can_access_person, has_capability, is_global_pastoral_authority


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


async def audit(db, user: dict, action: str, entity_type: str, entity_id: str, before=None, after=None, reason=None, person_id=None):
    event_id = str(uuid4())
    await db.formation_audit_events.insert_one({
        "_id": event_id, "event_id": event_id, "action": action,
        "entity_type": entity_type, "entity_id": entity_id,
        "person_id": person_id, "actor_user_id": user.get("user_id"),
        "actor_person_id": user.get("person_id"), "before": serialize(before),
        "after": serialize(after), "reason": reason, "occurred_at": now_utc(),
    })


async def canonical_person(db, person_id: str) -> dict:
    if not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=422, detail="Seleccione una Persona 360 válida")
    person = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}}, {"_id": 1, "nombre": 1, "apellido": 1, "person_number": 1, "created_by": 1, "auth_user_id": 1})
    if not person:
        raise HTTPException(status_code=404, detail="Persona 360 no encontrada")
    return {"person_id": str(person["_id"]), "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(), "person_number": person.get("person_number"), "created_by": person.get("created_by"), "auth_user_id": person.get("auth_user_id")}


async def require_person_access(db, user: dict, person_id: str, capability: str) -> dict:
    person = await canonical_person(db, person_id)
    if not is_global_pastoral_authority(user):
        if not has_capability(user, capability):
            raise HTTPException(status_code=403, detail="Sin acceso a la formación de esta Persona")
        if not can_access_person(user, person):
            assigned_cohorts = await db.formation_cohort_staff.distinct("cohort_id", {"person_id": user.get("person_id"), "active": True})
            assigned_student = bool(assigned_cohorts and await db.formation_enrollments.find_one({"person_id": person_id, "cohort_id": {"$in": assigned_cohorts}}, {"_id": 1}))
            if not assigned_student:
                raise HTTPException(status_code=403, detail="Sin acceso a la formación de esta Persona")
    return person


async def is_active_cohort_staff(db, cohort_id: str, user: dict) -> bool:
    return bool(user.get("person_id") and await db.formation_cohort_staff.find_one({"cohort_id": cohort_id, "person_id": user["person_id"], "active": True}, {"_id": 1}))


async def require_cohort_access(db, cohort: dict, user: dict, capability: str, allow_global: bool = True) -> None:
    if is_global_pastoral_authority(user):
        return
    if not has_capability(user, capability):
        raise HTTPException(status_code=403, detail="Sin permiso para esta operación educativa")
    if allow_global and user.get("access_scope", {}).get("persons") == "all":
        return
    if not await is_active_cohort_staff(db, cohort["cohort_id"], user):
        raise HTTPException(status_code=403, detail="La cohorte no está asignada a este profesor")


async def module_eligibility(db, person_id: str, module: dict) -> dict:
    links = await db.formation_module_prerequisites.find({"module_id": module["module_id"], "active": True}, {"_id": 0}).to_list(200)
    required = [item["prerequisite_module_id"] for item in links]
    completed = set(await db.formation_achievements.distinct("module_id", {"person_id": person_id, "status": {"$in": ["completed", "historical_accredited"]}, "active": True}))
    mode = links[0].get("mode", "all") if links else "all"
    eligible = not required or (all(item in completed for item in required) if mode == "all" else any(item in completed for item in required))
    return {"eligible": eligible, "required_module_ids": required, "completed_prerequisite_ids": sorted(completed.intersection(required)), "mode": mode}


async def next_recommended_module(db, person_id: str, program_id: str | None = None) -> dict | None:
    query = {"active": True}
    if program_id:
        query["program_id"] = program_id
    modules = await db.formation_modules.find(query, {"_id": 0}).sort([("program_id", 1), ("order", 1)]).to_list(10000)
    achieved = set(await db.formation_achievements.distinct("module_id", {"person_id": person_id, "active": True, "status": {"$in": ["completed", "historical_accredited"]}}))
    enrolled = set(await db.formation_enrollments.distinct("module_id", {"person_id": person_id, "status": {"$in": ["enrolled", "in_progress"]}}))
    for module in modules:
        if module["module_id"] in achieved or module["module_id"] in enrolled:
            continue
        eligibility = await module_eligibility(db, person_id, module)
        if eligibility["eligible"]:
            return {**serialize(module), "eligibility": eligibility}
    return None


def attendance_value(status: str, policy: dict) -> tuple[float, float]:
    if status == "present": return 1, 1
    if status == "late": return float(policy.get("late_weight", 0.5)), 1
    if status == "excused":
        mode = policy.get("excused_policy", "exclude")
        if mode == "valid": return 1, 1
        if mode == "absent": return 0, 1
        return 0, 0
    return 0, 1


async def recalculate_enrollment(db, enrollment_id: str, user: dict, reason: str = "Cálculo automático") -> dict:
    enrollment = await db.formation_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    if not enrollment:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada")
    cohort = await db.formation_cohorts.find_one({"cohort_id": enrollment["cohort_id"]}, {"_id": 0})
    module = await db.formation_modules.find_one({"module_id": enrollment["module_id"]}, {"_id": 0})
    policy = (module or {}).get("approval_policy") or {}
    sessions = await db.formation_sessions.find({"cohort_id": cohort["cohort_id"], "required": True, "status": {"$ne": "cancelled"}}, {"_id": 0, "session_id": 1}).to_list(1000)
    session_ids = [item["session_id"] for item in sessions]
    attendance = await db.formation_attendance.find({"enrollment_id": enrollment_id, "session_id": {"$in": session_ids}}, {"_id": 0}).to_list(1000)
    earned = possible = 0.0
    for item in attendance:
        value, denominator = attendance_value(item["status"], policy); earned += value; possible += denominator
    attendance_pct = round(earned / possible * 100, 2) if possible else 0.0
    assessments = await db.formation_assessments.find({"cohort_id": cohort["cohort_id"], "active": True}, {"_id": 0}).to_list(1000)
    grades = {item["assessment_id"]: item async for item in db.formation_grades.find({"enrollment_id": enrollment_id}, {"_id": 0})}
    weighted = total_weight = 0.0
    for item in assessments:
        grade = grades.get(item["assessment_id"])
        if not grade: continue
        weighted += min(100, float(grade["score"]) / float(item["max_score"]) * 100) * float(item["weight"])
        total_weight += float(item["weight"])
    grade_pct = round(weighted / total_weight, 2) if total_weight else None
    method = policy.get("method", "attendance_only")
    attendance_met = attendance_pct >= float(policy.get("minimum_attendance_pct", 80))
    grade_met = grade_pct is not None and grade_pct >= float(policy.get("minimum_grade_pct", 70))
    meets = attendance_met if method == "attendance_only" else grade_met if method == "grade_only" else attendance_met and grade_met if method in {"attendance_and_grade", "custom"} else False
    status = enrollment.get("status", "enrolled")
    if meets and not policy.get("manual_confirmation_required") and method != "manual": status = "completed"
    elif attendance or grades: status = "remediation_required" if cohort.get("status") == "completed" else "in_progress"
    progress_pct = min(100, round(((len(attendance) / len(sessions) * 100) if sessions else 0) * 0.6 + ((len(grades) / len(assessments) * 100) if assessments else 100) * 0.4, 2))
    before = serialize(enrollment)
    now = now_utc(); updates = {"attendance_pct": attendance_pct, "final_grade_pct": grade_pct, "progress_pct": progress_pct, "criteria_met": meets, "status": status, "updated_at": now}
    if status == "completed": updates["completed_at"] = enrollment.get("completed_at") or now
    await db.formation_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": updates})
    updated = await db.formation_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    if status == "completed":
        achievement_id = str(uuid4())
        await db.formation_achievements.update_one({"person_id": enrollment["person_id"], "module_id": enrollment["module_id"], "active": True}, {"$setOnInsert": {"_id": achievement_id, "achievement_id": achievement_id, "person_id": enrollment["person_id"], "program_id": enrollment["program_id"], "module_id": enrollment["module_id"], "status": "completed", "source": "calculated_completion", "enrollment_id": enrollment_id, "program_name_snapshot": enrollment["program_name_snapshot"], "module_name_snapshot": enrollment["module_name_snapshot"], "completed_at": updates["completed_at"], "attendance_pct": attendance_pct, "final_grade_pct": grade_pct, "active": True, "created_at": now}}, upsert=True)
    if before.get("status") != status:
        await audit(db, user, "enrollment_status_calculated", "formation_enrollment", enrollment_id, before, updated, reason, enrollment["person_id"])
    return serialize(updated)


async def ensure_formation_indexes(db):
    await db.formation_programs.create_index("program_id", unique=True)
    await db.formation_programs.create_index([("active", 1), ("name", 1)])
    await db.formation_modules.create_index("module_id", unique=True)
    await db.formation_modules.create_index([("program_id", 1), ("order", 1)])
    await db.formation_module_prerequisites.create_index([("module_id", 1), ("prerequisite_module_id", 1)], unique=True)
    await db.formation_cohorts.create_index("cohort_id", unique=True)
    await db.formation_cohorts.create_index([("module_id", 1), ("status", 1)])
    await db.formation_cohort_staff.create_index([("cohort_id", 1), ("person_id", 1), ("role", 1)], unique=True)
    await db.formation_sessions.create_index("session_id", unique=True)
    await db.formation_sessions.create_index([("cohort_id", 1), ("session_date", 1)])
    await db.formation_enrollments.create_index("enrollment_id", unique=True)
    await db.formation_enrollments.create_index([("cohort_id", 1), ("person_id", 1)], unique=True)
    await db.formation_enrollments.create_index([("person_id", 1), ("module_id", 1), ("status", 1)])
    await db.formation_attendance.create_index([("session_id", 1), ("enrollment_id", 1)], unique=True)
    await db.formation_assessments.create_index("assessment_id", unique=True)
    await db.formation_grades.create_index([("assessment_id", 1), ("enrollment_id", 1)], unique=True)
    await db.formation_achievements.create_index("achievement_id", unique=True)
    await db.formation_achievements.create_index([("person_id", 1), ("module_id", 1), ("active", 1)], unique=True)
    await db.formation_audit_events.create_index([("entity_type", 1), ("entity_id", 1), ("occurred_at", -1)])
    await db.formation_audit_events.create_index([("person_id", 1), ("occurred_at", -1)])
    await db.formation_recommendations.create_index([("person_id", 1), ("module_id", 1), ("status", 1)], unique=True)