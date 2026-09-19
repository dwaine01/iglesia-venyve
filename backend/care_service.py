"""Servicios de dominio del Mega-Bloque F — Cuidado Pastoral."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import re
import unicodedata

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from access_control import (
    CARE_ASSIGNED_READ, CARE_ASSIGNED_WRITE, CARE_AUDIT_READ, CARE_CONFIDENTIAL_READ,
    CARE_CONFIDENTIAL_WRITE, CARE_MANAGE, has_capability, is_global_pastoral_authority,
)
from care_crypto import decrypt_text, encrypt_text
from consolidation_service import configure_entry_stages
from process_engine import create_enrollment, record_event, serialize


ACTIVE_CASE_STATUSES = {"detected", "assigned", "contacted", "follow_up", "escalated"}
TERMINAL_CASE_STATUSES = {"resolved", "closed"}
TRANSITIONS = {
    "detected": {"assigned", "escalated", "closed"},
    "assigned": {"contacted", "escalated", "closed"},
    "contacted": {"follow_up", "resolved", "closed", "escalated"},
    "follow_up": {"contacted", "resolved", "closed", "escalated"},
    "escalated": {"assigned", "contacted", "follow_up", "resolved", "closed"},
    "resolved": {"follow_up", "closed"},
    "closed": {"follow_up"},
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def is_care_authority(user: dict) -> bool:
    if is_global_pastoral_authority(user):
        return True
    scope_all = user.get("access_scope", {}).get("persons") == "all"
    return scope_all and has_capability(user, CARE_MANAGE) and has_capability(user, CARE_CONFIDENTIAL_READ)


def has_care_entry(user: dict) -> bool:
    return is_care_authority(user) or has_capability(user, CARE_ASSIGNED_READ)


async def validate_person(db, person_id: str) -> dict:
    if not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=422, detail="Seleccione una Persona 360 válida")
    person = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}}, {"_id": 1, "nombre": 1, "apellido": 1, "person_number": 1})
    if not person:
        raise HTTPException(status_code=404, detail="Persona 360 no encontrada")
    return person


async def person_summary(db, person_id: str) -> dict | None:
    if not ObjectId.is_valid(person_id):
        return None
    person = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}}, {"_id": 0, "nombre": 1, "apellido": 1, "person_number": 1})
    if not person:
        return None
    return {"person_id": person_id, "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(), "person_number": person.get("person_number"), "profile_path": f"/personas/{person_id}"}


async def record_audit(db, user: dict, action: str, entity_type: str, entity_id: str, changes: dict | None = None) -> None:
    audit_id = str(uuid4())
    await db.care_audit_events.insert_one({
        "_id": audit_id, "audit_id": audit_id, "action": action,
        "entity_type": entity_type, "entity_id": entity_id,
        "actor_user_id": user.get("user_id"), "actor_person_id": user.get("person_id"),
        "changes": serialize(changes or {}), "occurred_at": now_utc(),
    })


async def case_accessible(db, case: dict, user: dict, write: bool = False) -> bool:
    if is_care_authority(user):
        return True
    capability = CARE_ASSIGNED_WRITE if write else CARE_ASSIGNED_READ
    if not has_capability(user, capability) or not user.get("person_id"):
        return False
    return bool(await db.pastoral_case_assignments.find_one({"case_id": case["case_id"], "assignee_person_id": user["person_id"], "active": True}, {"_id": 1}))


async def load_case(db, case_id: str, user: dict, write: bool = False) -> dict:
    case = await db.pastoral_cases.find_one({"case_id": case_id}, {"_id": 0})
    if not case or not await case_accessible(db, case, user, write):
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    return case


async def visible_case_query(db, user: dict, base: dict | None = None) -> dict:
    query = dict(base or {})
    if is_care_authority(user):
        return query
    if not has_capability(user, CARE_ASSIGNED_READ) or not user.get("person_id"):
        return {"case_id": {"$in": []}}
    case_ids = await db.pastoral_case_assignments.distinct("case_id", {"assignee_person_id": user["person_id"], "active": True})
    query["case_id"] = {"$in": case_ids}
    return query


async def enrich_case(db, case: dict, user: dict) -> dict:
    assignments = await db.pastoral_case_assignments.find({"case_id": case["case_id"], "active": True}, {"_id": 0}).sort("assigned_at", 1).to_list(50)
    for assignment in assignments:
        assignment["assignee"] = await person_summary(db, assignment["assignee_person_id"])
    op72 = await db.op72_records.find_one({"case_id": case["case_id"]}, {"_id": 0})
    result = serialize(case)
    result.update({
        "person": await person_summary(db, case["person_id"]),
        "assignments": serialize(assignments), "op72": serialize(op72),
        "permissions": {
            "write": await case_accessible(db, case, user, True),
            "assign": is_care_authority(user),
            "confidential_read": is_care_authority(user) and has_capability(user, CARE_CONFIDENTIAL_READ),
            "confidential_write": is_care_authority(user) and has_capability(user, CARE_CONFIDENTIAL_WRITE),
            "audit": is_care_authority(user) and has_capability(user, CARE_AUDIT_READ),
        },
    })
    return result


async def create_case_record(db, payload: dict, user: dict) -> dict:
    await validate_person(db, payload["person_id"])
    if payload.get("household_id") and not await db.households.find_one({"_id": payload["household_id"]}, {"_id": 1}):
        raise HTTPException(status_code=422, detail="Hogar canónico no encontrado")
    if payload.get("source_id"):
        existing = await db.pastoral_cases.find_one({"source_type": payload["source_type"], "source_id": payload["source_id"], "person_id": payload["person_id"]}, {"_id": 0})
        if existing:
            return await enrich_case(db, existing, user)
    now = now_utc(); case_id = str(uuid4())
    doc = {
        "_id": case_id, "case_id": case_id, **payload, "status": "detected",
        "detected_at": now, "assigned_at": None, "first_contact_at": None,
        "resolved_at": None, "closed_at": None, "escalated_at": None,
        "created_by_user_id": user["user_id"], "updated_by_user_id": user["user_id"],
        "created_at": now, "updated_at": now, "version": 1,
    }
    await db.pastoral_cases.insert_one(doc)
    await record_audit(db, user, "case_created", "pastoral_case", case_id, {"person_id": payload["person_id"], "case_type": payload["case_type"], "priority": payload["priority"]})
    return await enrich_case(db, {key: value for key, value in doc.items() if key != "_id"}, user)


async def ensure_op72_consolidation(db, person_id: str, actor_user_id: str, source_id: str) -> dict:
    existing = await db.process_enrollments.find_one({"person_id": person_id, "process_key": "consolidation"}, {"_id": 0}, sort=[("created_at", -1)])
    if existing:
        return existing
    enrollment, created = await create_enrollment(
        db, "consolidation", person_id, None, actor_user_id,
        status="active", next_action="Realizar contacto de Operación 72",
        next_action_at=now_utc() + timedelta(hours=72), source="care_op72", source_id=source_id,
    )
    if created:
        await configure_entry_stages(db, enrollment, "visitor_followup", actor_user_id)
    return await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})


async def create_op72(db, payload: dict, user: dict) -> tuple[dict, bool]:
    await validate_person(db, payload["person_id"])
    existing = await db.op72_records.find_one({"person_id": payload["person_id"]}, {"_id": 0})
    if existing:
        existing["case"] = await enrich_case(db, await db.pastoral_cases.find_one({"case_id": existing["case_id"]}, {"_id": 0}), user)
        return serialize(existing), False
    decision_at = payload["decision_at"]
    if decision_at.tzinfo is None:
        decision_at = decision_at.replace(tzinfo=timezone.utc)
    else:
        decision_at = decision_at.astimezone(timezone.utc)
    decision_at = decision_at.replace(microsecond=(decision_at.microsecond // 1000) * 1000)
    op72_id = str(uuid4())
    enrollment = await ensure_op72_consolidation(db, payload["person_id"], user["user_id"], op72_id)
    source_cell_id = None; front_group_id = None; routing_source = None
    if payload.get("source_type") == "cell_meeting" and payload.get("source_id"):
        meeting = await db.cell_meetings.find_one({"meeting_id": payload["source_id"]}, {"_id": 0, "cell_id": 1})
        source_cell_id = (meeting or {}).get("cell_id")
        if source_cell_id:
            link = await db.cell_front_group_links.find_one({"cell_id": source_cell_id, "active": True, "route_conversions": True}, {"_id": 0})
            if link:
                front_group_id = link.get("front_group_id"); routing_source = "cell_policy"
    elif payload.get("source_type") == "evangelism_target" and payload.get("source_id"):
        target = await db.evangelism_targets.find_one({"target_id": payload["source_id"], "archived": {"$ne": True}}, {"_id": 0, "front_group_id": 1})
        if target and target.get("front_group_id"):
            front_group_id = target["front_group_id"]; routing_source = "invasion_origin"
    case = await create_case_record(db, {
        "person_id": payload["person_id"], "case_type": "first_conversion", "priority": "high",
        "source_type": payload["source_type"], "source_id": payload.get("source_id") or op72_id,
        "household_id": None, "operational_summary": "Respuesta inmediata de Operación 72",
        "next_step": "Asignar responsable y realizar primer contacto", "next_step_at": decision_at + timedelta(hours=24),
    }, user)
    now = now_utc()
    doc = {
        "_id": op72_id, "op72_id": op72_id, "person_id": payload["person_id"],
        "case_id": case["case_id"], "first_conversion_at": decision_at,
        "source_type": payload["source_type"], "source_id": payload.get("source_id"),
        "source_cell_id": source_cell_id, "front_group_id": front_group_id,
        "routing_source": routing_source,
        "assignment_deadline_at": decision_at + timedelta(hours=24),
        "contact_deadline_at": decision_at + timedelta(hours=72),
        "first_contact_at": None, "status": "active", "window_status": "open",
        "consolidation_enrollment_id": enrollment.get("enrollment_id"),
        "paused_process_enrollment_ids": [], "reactivation_count": 0,
        "created_by_user_id": user["user_id"], "created_at": now, "updated_at": now,
    }
    try:
        await db.op72_records.insert_one(doc)
    except DuplicateKeyError:
        await db.pastoral_cases.delete_one({"case_id": case["case_id"]})
        existing = await db.op72_records.find_one({"person_id": payload["person_id"]}, {"_id": 0})
        return serialize(existing), False
    await db.pastoral_cases.update_one({"case_id": case["case_id"]}, {"$set": {"op72_id": op72_id, "consolidation_enrollment_id": enrollment.get("enrollment_id"), "updated_at": now}})
    if source_cell_id or front_group_id:
        enrollment_update = {"updated_at": now}
        if source_cell_id and not enrollment.get("source_cell_id"): enrollment_update["source_cell_id"] = source_cell_id
        if front_group_id: enrollment_update.update({"front_group_id": front_group_id, "routing_decision": {"recommended_group_id": front_group_id, "assigned_group_id": front_group_id, "mode": routing_source, "confirmed": True, "manual_override": False}})
        await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": enrollment_update})
    if front_group_id:
        from front_group_work import create_source_work_assignment
        await create_source_work_assignment(source_type="op72", source_id=op72_id, source_sub_id=None, title="Operación 72 — contacto inicial", description="Realizar contacto dentro de la ventana operacional. No incluye notas de Cuidado Pastoral.", assigned_group_id=front_group_id, assigned_person_id=None, priority="urgent", due_at=decision_at + timedelta(hours=72), actor_user_id=user["user_id"], reason=f"Enrutamiento por {routing_source}")
    await record_audit(db, user, "op72_created", "op72", op72_id, {"person_id": payload["person_id"], "first_conversion_at": decision_at, "consolidation_enrollment_id": enrollment.get("enrollment_id")})
    result = serialize(doc); result["case"] = await enrich_case(db, await db.pastoral_cases.find_one({"case_id": case["case_id"]}, {"_id": 0}), user)
    return result, True


async def validate_assignee(db, person_id: str, authority_only: bool = False) -> dict:
    await validate_person(db, person_id)
    account = await db.users.find_one({"person_id": person_id, "is_active": {"$ne": False}}, {"_id": 0, "person_id": 1, "rol": 1, "role": 1, "access_level": 1, "capabilities": 1, "access_scope": 1})
    if not account:
        raise HTTPException(status_code=422, detail="El responsable necesita una cuenta activa")
    if authority_only and not is_care_authority(account):
        raise HTTPException(status_code=422, detail="Seleccione Pastor/Pastora o Coordinación General autorizada")
    return account


async def assign_case(db, case: dict, payload: dict, user: dict) -> dict:
    await validate_assignee(db, payload["assignee_person_id"])
    now = now_utc()
    if payload["assignment_role"] == "primary":
        await db.pastoral_case_assignments.update_many({"case_id": case["case_id"], "assignment_role": "primary", "active": True}, {"$set": {"active": False, "ended_at": now, "end_reason": "Reasignación", "ended_by_user_id": user["user_id"]}})
    existing = await db.pastoral_case_assignments.find_one({"case_id": case["case_id"], "assignee_person_id": payload["assignee_person_id"], "assignment_role": payload["assignment_role"], "active": True}, {"_id": 0})
    if not existing:
        assignment_id = str(uuid4())
        existing = {"_id": assignment_id, "assignment_id": assignment_id, "case_id": case["case_id"], **payload, "active": True, "assigned_at": now, "assigned_by_user_id": user["user_id"], "ended_at": None}
        await db.pastoral_case_assignments.insert_one(existing)
    updates = {"assigned_at": case.get("assigned_at") or now, "updated_at": now, "updated_by_user_id": user["user_id"]}
    if case.get("status") == "detected": updates["status"] = "assigned"
    await db.pastoral_cases.update_one({"case_id": case["case_id"]}, {"$set": updates, "$inc": {"version": 1}})
    await record_audit(db, user, "case_assigned", "pastoral_case", case["case_id"], {"assignee_person_id": payload["assignee_person_id"], "assignment_role": payload["assignment_role"], "reason": payload.get("reason")})
    return serialize(existing)


async def add_contact(db, case: dict, payload: dict, user: dict) -> dict:
    contact_id = str(uuid4()); now = now_utc()
    doc = {"_id": contact_id, "contact_id": contact_id, "case_id": case["case_id"], "person_id": case["person_id"], **payload, "recorded_by_user_id": user["user_id"], "created_at": now}
    await db.pastoral_contact_attempts.insert_one(doc)
    updates = {"last_contact_attempt_at": payload["occurred_at"], "updated_at": now, "updated_by_user_id": user["user_id"]}
    if payload.get("next_step") is not None: updates["next_step"] = payload["next_step"]
    if payload.get("next_step_at") is not None: updates["next_step_at"] = payload["next_step_at"]
    if payload["outcome"] == "successful":
        updates["first_contact_at"] = case.get("first_contact_at") or payload["occurred_at"]
        if case.get("status") in {"detected", "assigned"}: updates["status"] = "contacted"
        await db.op72_records.update_one({"case_id": case["case_id"], "first_contact_at": None}, {"$set": {"first_contact_at": payload["occurred_at"], "window_status": "met", "updated_at": now}})
    await db.pastoral_cases.update_one({"case_id": case["case_id"]}, {"$set": updates, "$inc": {"version": 1}})
    await record_audit(db, user, "contact_recorded", "pastoral_case", case["case_id"], {"contact_id": contact_id, "method": payload["method"], "outcome": payload["outcome"], "occurred_at": payload["occurred_at"]})
    return serialize(doc)


async def transition_case(db, case: dict, status: str, reason: str, user: dict) -> dict:
    if status == case.get("status"):
        return await enrich_case(db, case, user)
    if status not in TRANSITIONS.get(case.get("status"), set()):
        raise HTTPException(status_code=409, detail=f"No se permite pasar de {case.get('status')} a {status}")
    if status == "assigned" and not await db.pastoral_case_assignments.find_one({"case_id": case["case_id"], "assignment_role": "primary", "active": True}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Asigne un responsable principal antes de cambiar el estado")
    now = now_utc(); updates = {"status": status, "updated_at": now, "updated_by_user_id": user["user_id"], "status_reason": reason}
    timestamp_field = {"resolved": "resolved_at", "closed": "closed_at", "escalated": "escalated_at"}.get(status)
    if timestamp_field: updates[timestamp_field] = now
    await db.pastoral_cases.update_one({"case_id": case["case_id"]}, {"$set": updates, "$inc": {"version": 1}})
    if status in TERMINAL_CASE_STATUSES:
        await db.op72_records.update_one({"case_id": case["case_id"]}, {"$set": {"status": "completed", "completed_at": now, "updated_at": now}})
    await record_audit(db, user, "case_transition", "pastoral_case", case["case_id"], {"from": case.get("status"), "to": status, "reason": reason})
    return await enrich_case(db, await db.pastoral_cases.find_one({"case_id": case["case_id"]}, {"_id": 0}), user)


async def escalate_case(db, case: dict, authority_person_id: str, reason: str, user: dict) -> dict:
    await validate_assignee(db, authority_person_id, authority_only=True)
    await assign_case(db, case, {"assignee_person_id": authority_person_id, "assignment_role": "supervisor", "reason": reason}, user)
    now = now_utc()
    await db.pastoral_cases.update_one({"case_id": case["case_id"]}, {"$set": {"status": "escalated", "priority": "urgent", "escalated_at": now, "escalated_by_user_id": user["user_id"], "escalated_to_person_id": authority_person_id, "escalation_reason": reason, "updated_at": now}, "$inc": {"version": 1}})
    await record_audit(db, user, "urgent_escalation", "pastoral_case", case["case_id"], {"authority_person_id": authority_person_id, "reason": reason, "escalated_at": now})
    return await enrich_case(db, await db.pastoral_cases.find_one({"case_id": case["case_id"]}, {"_id": 0}), user)


async def pause_op72(db, op72: dict, reason: str, user: dict) -> dict:
    if op72.get("status") == "paused": return serialize(op72)
    now = now_utc(); process_docs = await db.process_enrollments.find({"person_id": op72["person_id"], "process_key": {"$in": ["consolidation", "seven_weeks"]}, "status": "active"}, {"_id": 0}).to_list(20)
    process_ids = []
    for enrollment in process_docs:
        process_ids.append(enrollment["enrollment_id"])
        await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": {"status": "paused", "paused_at": now, "pause_reason": reason, "updated_at": now}})
        await record_event(db, enrollment, user["user_id"], "paused", "Proceso pausado", reason)
    await db.op72_records.update_one({"op72_id": op72["op72_id"]}, {"$set": {"status": "paused", "paused_at": now, "pause_reason": reason, "paused_process_enrollment_ids": process_ids, "updated_at": now}})
    await db.pastoral_cases.update_one({"case_id": op72["case_id"]}, {"$set": {"status": "follow_up", "next_step": "Reactivar acompañamiento cuando la Persona regrese", "next_step_at": None, "updated_at": now}})
    await record_audit(db, user, "op72_paused", "op72", op72["op72_id"], {"reason": reason, "process_enrollment_ids": process_ids})
    return serialize(await db.op72_records.find_one({"op72_id": op72["op72_id"]}, {"_id": 0}))


async def reactivate_op72(db, op72: dict, reason: str, user: dict) -> dict:
    now = now_utc(); process_ids = list(op72.get("paused_process_enrollment_ids") or [])
    if not process_ids:
        process_ids = await db.process_enrollments.distinct("enrollment_id", {"person_id": op72["person_id"], "process_key": {"$in": ["consolidation", "seven_weeks"]}, "status": "paused"})
    resumed = []
    for enrollment_id in process_ids:
        enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment_id, "status": "paused"}, {"_id": 0})
        if not enrollment: continue
        await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {"status": "active", "reactivated_at": now, "reactivation_reason": reason, "last_activity_at": now, "updated_at": now}, "$inc": {"reactivation_count": 1}})
        await record_event(db, enrollment, user["user_id"], "reactivated", "Proceso reactivado desde su progreso histórico", f"Continúa en {enrollment.get('current_stage_key')}")
        resumed.append({"enrollment_id": enrollment_id, "process_key": enrollment["process_key"], "current_stage_key": enrollment.get("current_stage_key"), "progress_pct": enrollment.get("progress_pct")})
    await db.op72_records.update_one({"op72_id": op72["op72_id"]}, {"$set": {"status": "active", "reactivated_at": now, "reactivation_reason": reason, "updated_at": now}, "$inc": {"reactivation_count": 1}})
    await db.pastoral_cases.update_one({"case_id": op72["case_id"]}, {"$set": {"status": "follow_up", "next_step": "Continuar desde el último avance válido", "updated_at": now}})
    await record_audit(db, user, "op72_reactivated", "op72", op72["op72_id"], {"reason": reason, "resumed_processes": resumed, "first_conversion_at_preserved": op72["first_conversion_at"]})
    result = serialize(await db.op72_records.find_one({"op72_id": op72["op72_id"]}, {"_id": 0})); result["resumed_processes"] = resumed
    return result


async def create_note(db, case: dict, content: str, visibility: str, user: dict, addendum_to_note_id: str | None = None) -> dict:
    if visibility == "pastoral_core" and not (is_care_authority(user) and has_capability(user, CARE_CONFIDENTIAL_WRITE)):
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    if visibility == "assigned_team" and not await case_accessible(db, case, user, True):
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    if addendum_to_note_id and not await db.pastoral_case_notes.find_one({"note_id": addendum_to_note_id, "case_id": case["case_id"]}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Nota original no encontrada")
    note_id = str(uuid4()); now = now_utc(); encrypted = encrypt_text(content, case["case_id"], note_id, visibility)
    doc = {"_id": note_id, "note_id": note_id, "case_id": case["case_id"], "person_id": case["person_id"], "visibility": visibility, **encrypted, "addendum_to_note_id": addendum_to_note_id, "author_person_id": user.get("person_id"), "actor_user_id": user["user_id"], "created_at": now}
    await db.pastoral_case_notes.insert_one(doc)
    await record_audit(db, user, "note_addendum_created" if addendum_to_note_id else "note_created", "pastoral_note", note_id, {"case_id": case["case_id"], "visibility": visibility, "addendum_to_note_id": addendum_to_note_id})
    return {"note_id": note_id, "case_id": case["case_id"], "visibility": visibility, "content": content, "addendum_to_note_id": addendum_to_note_id, "author_person_id": user.get("person_id"), "created_at": now}


async def list_notes(db, case: dict, user: dict) -> list[dict]:
    allowed = ["assigned_team"]
    if is_care_authority(user) and has_capability(user, CARE_CONFIDENTIAL_READ): allowed.append("pastoral_core")
    docs = await db.pastoral_case_notes.find({"case_id": case["case_id"], "visibility": {"$in": allowed}}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    result = []
    for doc in docs:
        item = {key: value for key, value in doc.items() if key not in {"ciphertext", "nonce", "key_version"}}
        item["content"] = decrypt_text(doc, case["case_id"], doc["note_id"], doc["visibility"])
        result.append(serialize(item))
        await record_audit(db, user, "note_viewed", "pastoral_note", doc["note_id"], {"case_id": case["case_id"], "visibility": doc["visibility"]})
    return result


async def create_visit(db, payload: dict, user: dict) -> dict:
    participant_ids = [item["person_id"] for item in payload["participants"]]
    for person_id in participant_ids + [payload["lead_visitor_person_id"], *payload.get("visitor_person_ids", [])]: await validate_person(db, person_id)
    if payload.get("household_id"):
        household = await db.households.find_one({"_id": payload["household_id"]}, {"_id": 1})
        members = set(await db.household_memberships.distinct("person_id", {"household_id": payload["household_id"]}))
        if not household or not set(participant_ids).issubset(members):
            raise HTTPException(status_code=422, detail="Las Personas seleccionadas deben pertenecer al Hogar canónico")
    for item in payload["participants"]:
        if item.get("case_id"):
            case = await load_case(db, item["case_id"], user)
            if case["person_id"] != item["person_id"]: raise HTTPException(status_code=422, detail="El caso no corresponde a la Persona seleccionada")
    visit_id = str(uuid4()); now = now_utc()
    doc = {"_id": visit_id, "visit_id": visit_id, "household_id": payload.get("household_id"), "scheduled_at": payload["scheduled_at"], "lead_visitor_person_id": payload["lead_visitor_person_id"], "visitor_person_ids": list(dict.fromkeys([payload["lead_visitor_person_id"], *payload.get("visitor_person_ids", [])])), "purpose": payload["purpose"], "status": "scheduled", "started_at": None, "completed_at": None, "created_by_user_id": user["user_id"], "created_at": now, "updated_at": now}
    await db.pastoral_visitations.insert_one(doc)
    participant_docs = []
    for item in payload["participants"]:
        participant_id = str(uuid4()); participant_docs.append({"_id": participant_id, "visit_participant_id": participant_id, "visit_id": visit_id, **item, "outcome": None, "next_step": None, "next_step_at": None, "created_at": now, "updated_at": now})
    await db.pastoral_visitation_participants.insert_many(participant_docs)
    await record_audit(db, user, "visitation_scheduled", "pastoral_visitation", visit_id, {"household_id": payload.get("household_id"), "participant_person_ids": participant_ids, "scheduled_at": payload["scheduled_at"]})
    return await visit_detail(db, visit_id, user)


async def visit_detail(db, visit_id: str, user: dict) -> dict:
    visit = await db.pastoral_visitations.find_one({"visit_id": visit_id}, {"_id": 0})
    if not visit: raise HTTPException(status_code=404, detail="Visita no encontrada")
    participants = await db.pastoral_visitation_participants.find({"visit_id": visit_id}, {"_id": 0}).to_list(100)
    allowed = is_care_authority(user)
    if not allowed:
        allowed = user.get("person_id") in visit.get("visitor_person_ids", [])
        if not allowed:
            for participant in participants:
                if participant.get("case_id"):
                    case = await db.pastoral_cases.find_one({"case_id": participant["case_id"]}, {"_id": 0})
                    if case and await case_accessible(db, case, user): allowed = True; break
    if not allowed: raise HTTPException(status_code=404, detail="Visita no encontrada")
    for participant in participants: participant["person"] = await person_summary(db, participant["person_id"])
    result = serialize(visit); result["participants"] = serialize(participants)
    result["lead_visitor"] = await person_summary(db, visit["lead_visitor_person_id"])
    return result


async def complete_visit(db, visit: dict, payload: dict, user: dict) -> dict:
    if visit.get("status") == "completed": return await visit_detail(db, visit["visit_id"], user)
    existing = await db.pastoral_visitation_participants.find({"visit_id": visit["visit_id"]}, {"_id": 0}).to_list(100)
    by_person = {item["person_id"]: item for item in existing}
    if set(by_person) != {item["person_id"] for item in payload["participant_results"]}:
        raise HTTPException(status_code=422, detail="Registre el resultado de cada Persona participante")
    now = now_utc()
    for result in payload["participant_results"]:
        participant = by_person[result["person_id"]]
        await db.pastoral_visitation_participants.update_one({"visit_participant_id": participant["visit_participant_id"]}, {"$set": {**result, "updated_at": now}})
        if participant.get("case_id"):
            case = await db.pastoral_cases.find_one({"case_id": participant["case_id"]}, {"_id": 0})
            if case:
                await add_contact(db, case, {"method": "visit", "outcome": "successful" if result["outcome"] == "successful" else "no_access", "occurred_at": now, "next_step": result.get("next_step"), "next_step_at": result.get("next_step_at")}, user)
    if payload.get("confidential_summary"):
        summary_id = str(uuid4()); encrypted = encrypt_text(payload["confidential_summary"], visit["visit_id"], summary_id, "pastoral_core")
        await db.pastoral_visitation_summaries.insert_one({"_id": summary_id, "summary_id": summary_id, "visit_id": visit["visit_id"], "visibility": "pastoral_core", **encrypted, "actor_user_id": user["user_id"], "created_at": now})
    await db.pastoral_visitations.update_one({"visit_id": visit["visit_id"]}, {"$set": {"status": "completed", "completed_at": now, "updated_at": now}})
    await record_audit(db, user, "visitation_completed", "pastoral_visitation", visit["visit_id"], {"participant_results": [{"person_id": item["person_id"], "outcome": item["outcome"]} for item in payload["participant_results"]], "confidential_summary_recorded": bool(payload.get("confidential_summary"))})
    return await visit_detail(db, visit["visit_id"], user)


async def profile_care_section(db, person_id: str, user: dict) -> dict | None:
    query = await visible_case_query(db, user, {"person_id": person_id})
    cases = await db.pastoral_cases.find(query, {"_id": 0, "case_id": 1, "status": 1, "priority": 1, "updated_at": 1}).sort("updated_at", -1).to_list(100)
    if not cases: return None
    active = [item for item in cases if item.get("status") in ACTIVE_CASE_STATUSES]
    return {"section_key": "cuidado_pastoral", "status_code": "has_summary" if cases else "no_record", "status_label": "Cuidado Pastoral", "summary": f"{len(active)} expediente(s) activo(s)" if active else None, "primary_date": None, "route": f"/cuidado-pastoral/casos?person_id={person_id}", "source_domain": "care", "updated_at": cases[0].get("updated_at") if cases else None}


async def ensure_care_indexes(db) -> None:
    await db.pastoral_cases.create_index("case_id", unique=True)
    await db.pastoral_cases.create_index([("person_id", 1), ("status", 1), ("updated_at", -1)])
    await db.pastoral_cases.create_index([("status", 1), ("priority", 1), ("next_step_at", 1)])
    await db.pastoral_cases.create_index([("source_type", 1), ("source_id", 1), ("person_id", 1)], unique=True, partialFilterExpression={"source_id": {"$type": "string"}})
    await db.pastoral_case_assignments.create_index([("case_id", 1), ("assignee_person_id", 1), ("active", 1)])
    await db.pastoral_case_assignments.create_index([("case_id", 1), ("assignment_role", 1), ("active", 1)], unique=True, partialFilterExpression={"assignment_role": "primary", "active": True}, name="unique_active_primary_care_assignment")
    await db.pastoral_contact_attempts.create_index([("case_id", 1), ("occurred_at", -1)])
    await db.pastoral_case_notes.create_index("note_id", unique=True)
    await db.pastoral_case_notes.create_index([("case_id", 1), ("created_at", -1)])
    await db.op72_records.create_index("op72_id", unique=True)
    await db.op72_records.create_index("person_id", unique=True)
    await db.op72_records.create_index([("status", 1), ("contact_deadline_at", 1)])
    await db.op72_records.create_index([("front_group_id", 1), ("status", 1)])
    await db.pastoral_visitations.create_index("visit_id", unique=True)
    await db.pastoral_visitations.create_index([("household_id", 1), ("scheduled_at", 1)])
    await db.pastoral_visitation_participants.create_index([("visit_id", 1), ("person_id", 1)], unique=True)
    await db.pastoral_visitation_participants.create_index([("person_id", 1), ("visit_id", 1)])
    await db.care_alerts.create_index("alert_key", unique=True)
    await db.care_alerts.create_index([("status", 1), ("severity", 1), ("due_at", 1)])
    await db.care_audit_events.create_index([("entity_type", 1), ("entity_id", 1), ("occurred_at", -1)])
