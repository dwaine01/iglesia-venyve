"""Gobierno, scope y trazabilidad del Mega-Bloque D."""
import math
from datetime import date, datetime, timezone
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException

from access_control import DOORS_MANAGE, is_global_pastoral_authority
from door_board_catalog import BOARD_ID


def now_utc(): return datetime.now(timezone.utc)


BOARD_PERMISSIONS = {
    "board.read", "board.meetings.write", "board.notes.write", "board.vote",
    "board.actions.write", "board.audio.manage", "board.minutes.review", "board.audit.read",
}
BOARD_POSITION_PERMISSIONS = {
    "president": {"board.read", "board.meetings.write", "board.vote", "board.actions.write"},
    "vice_president": {"board.read", "board.meetings.write", "board.vote", "board.actions.write"},
    "secretary": {"board.read", "board.meetings.write", "board.notes.write", "board.vote", "board.actions.write", "board.audio.manage", "board.minutes.review"},
    "treasurer": {"board.read", "board.vote"},
    "vocal": {"board.read", "board.vote"},
    "member": {"board.read", "board.vote"},
}


def effective_board_permissions(membership: dict) -> set[str]:
    ceiling = BOARD_POSITION_PERMISSIONS.get(membership.get("position_key"), {"board.read"})
    requested = set(membership.get("permissions") or ceiling)
    effective = requested.intersection(ceiling)
    effective.add("board.read")
    if not membership.get("voting_rights", False):
        effective.discard("board.vote")
    return effective


def serialize(value):
    if isinstance(value, dict): return {key: serialize(item) for key, item in value.items() if key != "_id"}
    if isinstance(value, list): return [serialize(item) for item in value]
    if isinstance(value, ObjectId): return str(value)
    if isinstance(value, (datetime, date)): return value.isoformat().replace("+00:00", "Z")
    return value


async def ensure_person(db, person_id: str) -> dict:
    if not ObjectId.is_valid(person_id): raise HTTPException(status_code=404, detail="Persona no encontrada")
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 1, "nombre": 1, "apellido": 1, "apellidos": 1, "person_number": 1})
    if not person: raise HTTPException(status_code=404, detail="Persona no encontrada")
    return person


async def person_summary(db, person_id: str) -> dict | None:
    if not ObjectId.is_valid(person_id): return None
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 0, "nombre": 1, "apellido": 1, "apellidos": 1, "person_number": 1})
    if not person: return None
    last = person.get("apellido") or person.get("apellidos") or ""
    return {"person_id": person_id, "name": f"{person.get('nombre', '')} {last}".strip(), "person_number": person.get("person_number"), "profile_path": f"/personas/{person_id}"}


async def active_board_membership(db, person_id: str, board_id: str = BOARD_ID) -> dict | None:
    return await db.board_memberships.find_one({"board_id": board_id, "person_id": person_id, "active": True}, {"_id": 0})


async def ensure_board_access(db, current_user: dict, permission: str = "board.read", board_id: str = BOARD_ID) -> dict | None:
    if is_global_pastoral_authority(current_user):
        return {"pastoral_full_access": True, "permissions": sorted(BOARD_PERMISSIONS), "position_key": "pastor"}
    membership = await active_board_membership(db, current_user.get("person_id"), board_id)
    if not membership:
        raise HTTPException(status_code=403, detail="La Junta Directiva requiere una membresía formal activa")
    permissions = effective_board_permissions(membership)
    if permission not in permissions:
        raise HTTPException(status_code=403, detail="Permiso de Junta insuficiente")
    return {**membership, "permissions": sorted(permissions), "pastoral_full_access": False}


async def board_access_snapshot(db, current_user: dict, board_id: str = BOARD_ID) -> dict:
    if is_global_pastoral_authority(current_user):
        return {"allowed": True, "full_access": True, "position_key": "pastor", "permissions": sorted(BOARD_PERMISSIONS), "data_classification": "board_institutional"}
    membership = await active_board_membership(db, current_user.get("person_id"), board_id)
    if not membership:
        return {"allowed": False, "full_access": False, "position_key": None, "permissions": [], "data_classification": "board_institutional"}
    return {"allowed": True, "full_access": False, "position_key": membership.get("position_key"), "permissions": sorted(effective_board_permissions(membership)), "membership_id": membership.get("membership_id"), "data_classification": "board_institutional"}


async def door_scope(db, current_user: dict) -> dict:
    if DOORS_MANAGE in current_user.get("capabilities", []):
        return {"global": True, "door_keys": await db.door_catalog.distinct("door_key", {"active": True}), "manageable": await db.door_catalog.distinct("door_key", {"active": True})}
    person_id = current_user.get("person_id")
    assignments = await db.door_assignments.find({"person_id": person_id, "active": True}, {"_id": 0, "door_key": 1, "role": 1}).to_list(100)
    keys = {item["door_key"] for item in assignments}
    manageable = {item["door_key"] for item in assignments if item["role"] in {"supervisor", "door_leader", "assistant"}}
    board = await active_board_membership(db, person_id)
    if board:
        keys.update(board.get("supervised_door_keys", [])); manageable.update(board.get("supervised_door_keys", []))
    return {"global": False, "door_keys": sorted(keys), "manageable": sorted(manageable)}


async def ensure_door_access(db, current_user: dict, door_key: str, manage: bool = False) -> dict:
    door = await db.door_catalog.find_one({"door_key": door_key, "active": True}, {"_id": 0})
    if not door: raise HTTPException(status_code=404, detail="Puerta no encontrada")
    scope = await door_scope(db, current_user)
    allowed = scope["manageable"] if manage else scope["door_keys"]
    if not scope["global"] and door_key not in allowed: raise HTTPException(status_code=403, detail="Fuera del alcance de Puerta")
    return door


async def record_case_event(db, case_id: str, actor_user_id: str, event_type: str, summary: str, changes: dict | None = None):
    await db.door_case_events.insert_one({"_id": str(uuid4()), "event_id": str(uuid4()), "case_id": case_id, "event_type": event_type, "summary": summary, "changes": changes or {}, "actor_user_id": actor_user_id, "occurred_at": now_utc()})


async def record_board_audit(db, actor_user_id: str, event_type: str, entity_type: str, entity_id: str, changes: dict | None = None):
    event_id = str(uuid4())
    await db.board_audit_events.insert_one({"_id": event_id, "event_id": event_id, "event_type": event_type, "entity_type": entity_type, "entity_id": entity_id, "changes": serialize(changes or {}), "actor_user_id": actor_user_id, "occurred_at": now_utc()})


async def upsert_case_from_cell_need(db, need: dict, actor_user_id: str) -> dict | None:
    door_key = need.get("assigned_door_key") or need.get("suggested_door_key")
    if not door_key: return None
    existing = await db.door_cases.find_one({"source_type": "cell_need", "source_id": need["need_id"]}, {"_id": 0})
    now = now_utc()
    if existing:
        updates = {"door_key": door_key, "priority": need.get("priority"), "status": "resolved" if need.get("status") in {"resolved", "closed"} else existing.get("status", "triage"), "updated_at": now}
        await db.door_cases.update_one({"case_id": existing["case_id"]}, {"$set": updates})
        await db.cell_needs.update_one({"need_id": need["need_id"]}, {"$set": {"door_case_id": existing["case_id"], "assigned_door_key": door_key, "updated_at": now}})
        return {**existing, **updates}
    case_id = str(uuid4())
    doc = {"_id": case_id, "case_id": case_id, "source_type": "cell_need", "source_id": need["need_id"], "person_id": need.get("person_id"), "cell_id": need.get("cell_id"), "meeting_id": need.get("meeting_id"), "door_key": door_key, "need_type": need.get("need_type"), "description": need.get("description"), "priority": need.get("priority", "medium"), "status": "triage", "responsible_person_id": need.get("responsible_person_id"), "next_action": None, "next_action_at": None, "resolution": None, "created_by_user_id": actor_user_id, "created_at": now, "updated_at": now}
    await db.door_cases.insert_one(doc)
    await db.cell_needs.update_one({"need_id": need["need_id"]}, {"$set": {"door_case_id": case_id, "assigned_door_key": door_key, "updated_at": now}})
    await record_case_event(db, case_id, actor_user_id, "intake", "Necesidad celular recibida por Puertas", {"door_key": door_key})
    await record_board_audit(db, actor_user_id, "cell_need_intake", "door_case", case_id, {"need_id": need["need_id"], "door_key": door_key, "person_id": need.get("person_id")})
    return doc


async def quorum_summary(db, meeting_id: str, board_id: str = BOARD_ID) -> dict:
    board = await db.governance_boards.find_one({"board_id": board_id}, {"_id": 0}) or {}
    eligible = await db.board_memberships.count_documents({"board_id": board_id, "active": True, "voting_rights": True})
    attendance = await db.board_meeting_attendance.find({"meeting_id": meeting_id}, {"_id": 0}).to_list(1000)
    eligible_ids = set(await db.board_memberships.distinct("person_id", {"board_id": board_id, "active": True, "voting_rights": True}))
    present_ids = {item["person_id"] for item in attendance if item.get("status") in {"present", "remote", "late"}}
    present_voting = len(eligible_ids.intersection(present_ids))
    rule = board.get("quorum_rule", {"type": "percentage", "value": 50})
    required = math.ceil(eligible * float(rule.get("value", 50)) / 100) if rule.get("type") == "percentage" else int(rule.get("value", 1))
    return {"eligible": eligible, "present_voting": present_voting, "required": required, "has_quorum": present_voting >= required and eligible > 0, "rule": rule}


async def ensure_door_board_indexes(db):
    await db.governance_boards.create_index("board_id", unique=True)
    await db.board_position_catalog.create_index("position_key", unique=True)
    await db.board_memberships.create_index([("board_id", 1), ("person_id", 1), ("active", 1)], unique=True, partialFilterExpression={"active": True}, name="unique_active_board_membership")
    await db.door_assignments.create_index([("door_key", 1), ("person_id", 1), ("role", 1), ("active", 1)], unique=True, partialFilterExpression={"active": True}, name="unique_active_door_role")
    await db.door_cases.create_index([("source_type", 1), ("source_id", 1)], unique=True)
    await db.door_cases.create_index([("door_key", 1), ("status", 1), ("priority", 1)])
    await db.door_case_events.create_index([("case_id", 1), ("occurred_at", -1)])
    await db.board_meetings.create_index([("board_id", 1), ("scheduled_at", -1)])
    await db.board_meeting_attendance.create_index([("meeting_id", 1), ("person_id", 1)], unique=True)
    await db.board_agenda_items.create_index([("meeting_id", 1), ("order", 1)])
    await db.board_proposals.create_index([("meeting_id", 1), ("status", 1)])
    await db.board_votes.create_index([("proposal_id", 1), ("person_id", 1)], unique=True)
    await db.board_actions.create_index([("board_id", 1), ("status", 1), ("due_at", 1)])
    await db.board_secretary_notes.create_index("meeting_id", unique=True)
    await db.board_secretary_note_versions.create_index([("meeting_id", 1), ("version", 1)], unique=True)
    await db.board_minutes.create_index([("meeting_id", 1), ("minute_type", 1), ("version", 1)], unique=True)
    await db.board_speaker_mappings.create_index([("meeting_id", 1), ("speaker_label", 1)], unique=True)
    await db.board_transcript_versions.create_index([("meeting_id", 1), ("version", 1)], unique=True)
    await db.board_transcript_segments.create_index([("transcript_version_id", 1), ("order", 1)])
    await db.board_recording_uploads.create_index("upload_id", unique=True)
    await db["board_recording_staging.files"].create_index([("metadata.upload_id", 1), ("metadata.seq", 1)], unique=True)
    await db["board_recordings.files"].create_index([("metadata.meeting_id", 1), ("uploadDate", -1)])
    await db["board_recordings.files"].create_index("metadata.sha256")
    await db.board_ai_artifacts.create_index([("meeting_id", 1), ("version", 1)], unique=True)
    await db.board_audit_events.create_index([("entity_type", 1), ("entity_id", 1), ("occurred_at", -1)])
    await db["board_documents.files"].create_index([("metadata.meeting_id", 1), ("uploadDate", -1)])