"""Servicios de dominio para la ruta única de Consolidación v2."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException

from front_groups import group_in_scope
from access_control import CONSOLIDATION_ASSIGN, has_capability, is_global_pastoral_authority
from process_engine import create_enrollment, get_definition, now_utc, record_event, serialize


ENTRY_START = {
    "complete_cycle": "prayer",
    "direct_church": "mcd",
    "cell": "mcd",
    "visitor_followup": "visitor_followup",
}


async def load_person(db, person_id: str) -> dict:
    if not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=400, detail="person_id inválido")
    person = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person["person_id"] = person_id
    return person


async def load_consolidation(db, enrollment_id: str) -> dict:
    item = await db.process_enrollments.find_one({"enrollment_id": enrollment_id, "process_key": "consolidation"}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Consolidación no encontrada")
    if item.get("definition_version", 1) < 2:
        raise HTTPException(status_code=409, detail="Este expediente es histórico; migre a Consolidación v2 antes de modificarlo")
    return item


async def assert_consolidation_scope(db, enrollment: dict, current_user: dict, leader_required: bool = False) -> None:
    if is_global_pastoral_authority(current_user) or has_capability(current_user, CONSOLIDATION_ASSIGN):
        return
    group_id = enrollment.get("front_group_id")
    if group_id and await group_in_scope(group_id, current_user, leader_required):
        return
    if current_user.get("person_id") in {enrollment.get("person_id"), enrollment.get("mentor_person_id"), enrollment.get("responsible_person_id")}:
        return
    raise HTTPException(status_code=403, detail="Consolidación fuera de su ámbito")


async def configure_entry_stages(db, enrollment: dict, entry_mode: str, actor_user_id: str) -> None:
    definition = await get_definition(db, "consolidation", 2)
    start_key = ENTRY_START[entry_mode]
    start = next(item for item in definition["stages"] if item["key"] == start_key)
    now = now_utc()
    for stage in definition["stages"]:
        if stage["order"] < start["order"]:
            status = "skipped"
            fields = {"status": status, "skipped_at": now, "skip_reason": f"No aplica para puerta {entry_mode}", "updated_at": now}
        elif stage["key"] == start_key:
            fields = {"status": "open", "opened_at": now, "due_at": now + timedelta(hours=stage.get("sla_hours", 0)) if stage.get("sla_hours") else None, "updated_at": now}
        else:
            fields = {"status": "locked", "opened_at": None, "due_at": None, "updated_at": now}
        await db.process_stage_progress.update_one({"enrollment_id": enrollment["enrollment_id"], "stage_key": stage["key"]}, {"$set": fields})
    await db.process_enrollments.update_one(
        {"enrollment_id": enrollment["enrollment_id"]},
        {"$set": {"current_stage_key": start_key, "entry_mode": entry_mode, "consolidation_status": "followup_pending" if entry_mode == "visitor_followup" else "in_progress", "updated_at": now}},
    )
    await record_event(db, enrollment, actor_user_id, "entry_configured", "Puerta de entrada registrada", entry_mode)


async def assign_mentor(db, enrollment: dict, mentor_person_id: str, actor_user_id: str, reason: str, transfer: bool = False) -> dict:
    await load_person(db, mentor_person_id)
    account = await db.users.find_one({"person_id": mentor_person_id, "is_active": {"$ne": False}, "rol": {"$in": ["pastor", "lider"]}}, {"_id": 1})
    if not account:
        raise HTTPException(status_code=409, detail="El mentor necesita una cuenta pastoral o de liderazgo activa")
    now = now_utc()
    previous = await db.mentor_assignments.find_one({"enrollment_id": enrollment["enrollment_id"], "active": True}, {"_id": 0})
    if previous and previous.get("mentor_person_id") == mentor_person_id:
        return previous
    if previous:
        await db.mentor_assignments.update_one(
            {"assignment_id": previous["assignment_id"]},
            {"$set": {"active": False, "ended_at": now, "ended_by_user_id": actor_user_id, "end_reason": reason}},
        )
    assignment_id = str(uuid4())
    document = {
        "_id": assignment_id,
        "assignment_id": assignment_id,
        "enrollment_id": enrollment["enrollment_id"],
        "person_id": enrollment["person_id"],
        "front_group_id": enrollment.get("front_group_id"),
        "mentor_person_id": mentor_person_id,
        "previous_assignment_id": previous.get("assignment_id") if previous else None,
        "previous_mentor_person_id": previous.get("mentor_person_id") if previous else None,
        "stage_key": enrollment.get("current_stage_key"),
        "reason": reason,
        "transfer": transfer,
        "active": True,
        "archived": False,
        "started_at": now,
        "ended_at": None,
        "assigned_by_user_id": actor_user_id,
        "created_at": now,
    }
    await db.mentor_assignments.insert_one(document)
    await db.process_enrollments.update_one(
        {"enrollment_id": enrollment["enrollment_id"]},
        {"$set": {"mentor_person_id": mentor_person_id, "responsible_person_id": mentor_person_id, "mentor_lbs_qualified": False, "mentor_transfer_required": False, "updated_at": now}},
    )
    await record_event(db, enrollment, actor_user_id, "mentor_transferred" if transfer else "mentor_assigned", "Mentor transferido" if transfer else "Mentor asignado", reason)
    return serialize(document)


async def mentor_qualification(db, person_id: str, front_group_id: str | None) -> dict | None:
    now = now_utc()
    return await db.mentor_qualifications.find_one({
        "person_id": person_id,
        "active": True,
        "archived": {"$ne": True},
        "can_teach_lbs": True,
        "$or": [{"front_group_id": front_group_id}, {"front_group_id": None}],
        "$and": [{"$or": [{"valid_until": None}, {"valid_until": {"$gte": now}}]}],
    }, {"_id": 0})


async def evaluate_current_mentor(db, enrollment: dict, actor_user_id: str) -> dict:
    mentor_id = enrollment.get("mentor_person_id")
    if not mentor_id:
        raise HTTPException(status_code=409, detail="Asigne un mentor antes de la evaluación de Fiesta")
    qualification = await mentor_qualification(db, mentor_id, enrollment.get("front_group_id"))
    qualified = bool(qualification)
    now = now_utc(); evaluation_id = str(uuid4())
    evaluation = {
        "_id": evaluation_id,
        "evaluation_id": evaluation_id,
        "enrollment_id": enrollment["enrollment_id"],
        "mentor_person_id": mentor_id,
        "front_group_id": enrollment.get("front_group_id"),
        "stage_key": "welcome_party",
        "qualified_for_lbs": qualified,
        "qualification_snapshot": serialize(qualification),
        "evaluated_by_user_id": actor_user_id,
        "evaluated_at": now,
    }
    await db.mentor_evaluations.insert_one(evaluation)
    await db.process_enrollments.update_one(
        {"enrollment_id": enrollment["enrollment_id"]},
        {"$set": {"mentor_lbs_qualified": qualified, "mentor_transfer_required": not qualified, "mentor_evaluated_at": now, "updated_at": now}},
    )
    stage = await db.process_stage_progress.find_one({"enrollment_id": enrollment["enrollment_id"], "stage_key": "welcome_party"})
    if stage:
        tasks = stage.get("tasks", [])
        for task in tasks:
            if task.get("task_id") == "mentor_evaluated":
                task.update({"completed": True, "completed_at": now})
        await db.process_stage_progress.update_one({"_id": stage["_id"]}, {"$set": {"tasks": tasks, "updated_at": now}})
    await record_event(db, enrollment, actor_user_id, "mentor_evaluated", "Mentor evaluado para LBS", "Autorizado" if qualified else "Transferencia requerida")
    return serialize(evaluation)


async def enrollment_detail(db, enrollment: dict) -> dict:
    stages = await db.process_stage_progress.find({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0}).sort("stage_order", 1).to_list(100)
    assignments = await db.mentor_assignments.find({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0}).sort("started_at", -1).to_list(200)
    timeline = await db.process_timeline.find({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0}).sort("occurred_at", -1).to_list(500)
    membership = await db.person_memberships.find_one({"person_id": enrollment["person_id"]}, {"_id": 0})
    discipleship = await db.process_enrollments.find_one({"process_key": "discipleship", "source_id": enrollment["enrollment_id"]}, {"_id": 0})
    formation_recommendation = await db.formation_recommendations.find_one({"source_enrollment_id": enrollment["enrollment_id"], "status": "recommended"}, {"_id": 0})
    person = await db.persons.find_one({"_id": ObjectId(enrollment["person_id"])}, {"_id": 0, "nombre": 1, "apellido": 1, "person_number": 1})
    result = serialize(enrollment)
    result.update({
        "person": {"person_id": enrollment["person_id"], "name": " ".join(part for part in [(person or {}).get("nombre"), (person or {}).get("apellido")] if part), "person_number": (person or {}).get("person_number")},
        "stages": serialize(stages),
        "mentor_assignments": serialize(assignments),
        "membership": serialize(membership),
        "discipleship": serialize(discipleship),
        "formation_recommendation": serialize(formation_recommendation),
        "timeline": serialize(timeline),
    })
    return result


async def ensure_consolidation_indexes(db) -> None:
    await db.mentor_assignments.create_index("assignment_id", unique=True)
    await db.mentor_assignments.create_index([("enrollment_id", 1), ("started_at", -1)])
    await db.mentor_evaluations.create_index([("enrollment_id", 1), ("evaluated_at", -1)])