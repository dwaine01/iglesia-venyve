"""APIs operativas de las 9 Puertas y la Junta Directiva."""
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from access_control import BOARD_CONFIDENTIAL_ACCESS, DOORS_MANAGE
from door_board_catalog import BOARD_ID
from door_board_engine import (
    active_board_membership, door_scope, ensure_board_access, ensure_door_access,
    ensure_person, now_utc, person_summary, quorum_summary, record_case_event,
    serialize, upsert_case_from_cell_need, record_board_audit,
)
from server import db, get_current_user

router = APIRouter(prefix="/api", tags=["doors-board"])

DOOR_ROLES = {"supervisor", "door_leader", "assistant", "collaborator", "server"}
BOARD_PERMISSIONS = {"board.read", "board.meetings.write", "board.notes.write", "board.vote", "board.actions.write", "board.audio.manage", "board.minutes.review", "board.audit.read", "doors.assignments.manage"}


def require_staff(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("rol") == "persona": raise HTTPException(status_code=403, detail="Acceso institucional requerido")
    return current_user


def ensure_pastor(current_user: dict):
    if DOORS_MANAGE not in current_user.get("capabilities", []): raise HTTPException(status_code=403, detail="Gobierno institucional requerido")


class PositionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    order: int = Field(default=100, ge=1, le=1000)
    voting_default: bool = True


class BoardMemberCreate(BaseModel):
    person_id: str
    position_key: str
    started_at: date = Field(default_factory=date.today)
    voting_rights: bool = True
    permissions: list[str] = Field(default_factory=lambda: ["board.read", "board.vote"], max_length=20)
    supervised_door_keys: list[str] = Field(default_factory=list, max_length=9)
    ministry_ids: list[str] = Field(default_factory=list, max_length=50)


class BoardMemberEnd(BaseModel):
    ended_at: date = Field(default_factory=date.today)
    reason: str = Field(min_length=3, max_length=500)


class DoorAssignmentCreate(BaseModel):
    person_id: str
    role: str
    started_at: date = Field(default_factory=date.today)
    notes: Optional[str] = Field(default=None, max_length=1000)


class DoorAssignmentEnd(BaseModel):
    ended_at: date = Field(default_factory=date.today)
    reason: str = Field(min_length=3, max_length=500)


class DoorCaseUpdate(BaseModel):
    door_key: Optional[str] = None
    status: Optional[Literal["triage", "assigned", "in_progress", "waiting", "resolved", "closed"]] = None
    priority: Optional[Literal["low", "medium", "high", "urgent"]] = None
    responsible_person_id: Optional[str] = None
    next_action: Optional[str] = Field(default=None, max_length=1000)
    next_action_at: Optional[datetime] = None
    resolution: Optional[str] = Field(default=None, max_length=3000)


class BoardSettingsUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    quorum_type: Optional[Literal["percentage", "fixed"]] = None
    quorum_value: Optional[float] = Field(default=None, ge=1, le=100)
    tie_rule: Optional[Literal["presiding_vote", "rejected", "postponed"]] = None


class MeetingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    scheduled_at: datetime
    location: str = Field(min_length=2, max_length=250)
    modality: Literal["in_person", "virtual", "hybrid"] = "in_person"
    chair_person_id: str
    secretary_person_id: str
    planned_duration_minutes: int = Field(default=90, ge=5, le=720)
    purpose: str = Field(min_length=3, max_length=2000)
    recording_notice: str = Field(default="Esta reunión será grabada y transcrita para elaborar la minuta.", min_length=10, max_length=1000)
    agenda_titles: list[str] = Field(default_factory=list, max_length=50)


class AttendanceItem(BaseModel):
    person_id: str
    status: Literal["present", "absent", "excused", "remote", "late", "left_early"]
    checked_in_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None
    recording_notice_acknowledged: bool = False


class AttendanceBulk(BaseModel):
    items: list[AttendanceItem] = Field(max_length=100)


class MeetingStart(BaseModel):
    recording_notice_confirmed: bool


class AgendaCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=3000)
    responsible_person_id: Optional[str] = None
    estimated_minutes: int = Field(default=10, ge=1, le=240)
    voting_enabled: bool = False


class AgendaUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=3000)
    responsible_person_id: Optional[str] = None
    status: Optional[Literal["pending", "in_progress", "completed", "postponed"]] = None
    discussion: Optional[str] = Field(default=None, max_length=10000)
    decision: Optional[str] = Field(default=None, max_length=5000)
    estimated_minutes: Optional[int] = Field(default=None, ge=1, le=240)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class SecretaryNoteUpdate(BaseModel):
    content: str = Field(max_length=100000)


class ProposalCreate(BaseModel):
    agenda_item_id: Optional[str] = None
    proposer_person_id: str
    text: str = Field(min_length=3, max_length=5000)
    seconder_person_id: Optional[str] = None


class ProposalUpdate(BaseModel):
    status: Literal["draft", "presented", "in_discussion", "ready_for_vote", "approved", "rejected", "postponed", "withdrawn"]
    discussion: Optional[str] = Field(default=None, max_length=10000)


class VoteCreate(BaseModel):
    choice: Literal["yes", "no", "abstain"]
    comment: Optional[str] = Field(default=None, max_length=1000)


class ActionCreate(BaseModel):
    agenda_item_id: Optional[str] = None
    action_type: Literal["agreement", "task"] = "task"
    title: str = Field(min_length=3, max_length=300)
    description: Optional[str] = Field(default=None, max_length=3000)
    responsible_person_id: str
    due_at: Optional[datetime] = None


class ActionUpdate(BaseModel):
    status: Literal["open", "in_progress", "completed", "cancelled"]
    result: Optional[str] = Field(default=None, max_length=3000)


class ManualMinuteUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=200000)


class MinuteStatusUpdate(BaseModel):
    status: Literal["review", "official", "rejected"]
    review_note: Optional[str] = Field(default=None, max_length=3000)


@router.get("/doors/catalog", response_model=dict)
async def doors_catalog(current_user: dict = Depends(require_staff)):
    scope = await door_scope(db, current_user)
    query = {"active": True} if scope["global"] else {"door_key": {"$in": scope["door_keys"]}, "active": True}
    doors = await db.door_catalog.find(query, {"_id": 0}).sort("number", 1).to_list(20)
    return {"items": serialize(doors), "scope": scope}


@router.get("/doors/dashboard", response_model=dict)
async def doors_dashboard(current_user: dict = Depends(require_staff)):
    scope = await door_scope(db, current_user); keys = scope["door_keys"]
    doors = await db.door_catalog.find({"door_key": {"$in": keys}, "active": True}, {"_id": 0}).sort("number", 1).to_list(20)
    items = []
    for door in doors:
        item = serialize(door)
        item["team_count"] = await db.door_assignments.count_documents({"door_key": door["door_key"], "active": True})
        item["open_cases"] = await db.door_cases.count_documents({"door_key": door["door_key"], "status": {"$nin": ["resolved", "closed"]}})
        item["urgent_cases"] = await db.door_cases.count_documents({"door_key": door["door_key"], "status": {"$nin": ["resolved", "closed"]}, "priority": "urgent"})
        items.append(item)
    board_access = True
    try: await ensure_board_access(db, current_user, "board.read")
    except HTTPException: board_access = False
    return {"doors": items, "metrics": {"doors": len(items), "open_cases": sum(item["open_cases"] for item in items), "urgent_cases": sum(item["urgent_cases"] for item in items), "active_servers": sum(item["team_count"] for item in items)}, "board_access": board_access}


@router.get("/doors/{door_key}", response_model=dict)
async def door_detail(door_key: str, current_user: dict = Depends(require_staff)):
    door = await ensure_door_access(db, current_user, door_key)
    assignments = await db.door_assignments.find({"door_key": door_key}, {"_id": 0}).sort("started_at", -1).to_list(1000)
    team = [{**serialize(item), "person": await person_summary(db, item["person_id"])} for item in assignments]
    cases = await db.door_cases.find({"door_key": door_key}, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)
    return {**serialize(door), "team": team, "cases": serialize(cases)}


@router.post("/doors/{door_key}/assignments", response_model=dict, status_code=201)
async def assign_door_role(door_key: str, payload: DoorAssignmentCreate, current_user: dict = Depends(require_staff)):
    await ensure_door_access(db, current_user, door_key, True); await ensure_person(db, payload.person_id)
    if payload.role not in DOOR_ROLES: raise HTTPException(status_code=422, detail="Función de Puerta inválida")
    if payload.role == "supervisor" and not await active_board_membership(db, payload.person_id):
        raise HTTPException(status_code=409, detail="El supervisor debe ser miembro activo de Junta")
    existing = await db.door_assignments.find_one({"door_key": door_key, "person_id": payload.person_id, "role": payload.role, "active": True}, {"_id": 0})
    if existing: return serialize(existing)
    assignment_id = str(uuid4()); now = now_utc()
    doc = {"_id": assignment_id, "assignment_id": assignment_id, "door_key": door_key, **payload.model_dump(), "started_at": payload.started_at.isoformat(), "active": True, "ended_at": None, "end_reason": None, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.door_assignments.insert_one(doc)
    await record_board_audit(db, current_user["user_id"], "door_assignment_created", "door_assignment", assignment_id, {"door_key": door_key, "person_id": payload.person_id, "role": payload.role})
    return serialize(doc)


@router.put("/doors/assignments/{assignment_id}/end", response_model=dict)
async def end_door_assignment(assignment_id: str, payload: DoorAssignmentEnd, current_user: dict = Depends(require_staff)):
    assignment = await db.door_assignments.find_one({"assignment_id": assignment_id}, {"_id": 0})
    if not assignment: raise HTTPException(status_code=404, detail="Asignación no encontrada")
    await ensure_door_access(db, current_user, assignment["door_key"], True)
    await db.door_assignments.update_one({"assignment_id": assignment_id}, {"$set": {"active": False, "ended_at": payload.ended_at.isoformat(), "end_reason": payload.reason, "updated_at": now_utc()}})
    await record_board_audit(db, current_user["user_id"], "door_assignment_ended", "door_assignment", assignment_id, {"reason": payload.reason})
    return serialize(await db.door_assignments.find_one({"assignment_id": assignment_id}, {"_id": 0}))


@router.get("/doors/cases/inbox", response_model=dict)
async def case_inbox(status: Optional[str] = Query(default=None), current_user: dict = Depends(require_staff)):
    scope = await door_scope(db, current_user); query = {"door_key": {"$in": scope["door_keys"]}}
    if status: query["status"] = status
    cases = await db.door_cases.find(query, {"_id": 0}).sort([("priority", -1), ("created_at", -1)]).to_list(5000)
    items = []
    for case in cases:
        items.append({**serialize(case), "person": await person_summary(db, case.get("person_id")) if case.get("person_id") else None})
    return {"items": items, "total": len(items)}


@router.post("/doors/intake/cell-needs/{need_id}", response_model=dict)
async def intake_cell_need(need_id: str, current_user: dict = Depends(require_staff)):
    need = await db.cell_needs.find_one({"need_id": need_id}, {"_id": 0})
    if not need: raise HTTPException(status_code=404, detail="Necesidad no encontrada")
    from cellular_engine import can_access_cell
    if not await can_access_cell(db, current_user, need["cell_id"], True): raise HTTPException(status_code=403, detail="Fuera del alcance celular")
    case = await upsert_case_from_cell_need(db, need, current_user["user_id"])
    if not case: raise HTTPException(status_code=409, detail="Seleccione una Puerta para esta necesidad")
    return serialize(case)


@router.put("/doors/cases/{case_id}", response_model=dict)
async def update_case(case_id: str, payload: DoorCaseUpdate, current_user: dict = Depends(require_staff)):
    case = await db.door_cases.find_one({"case_id": case_id}, {"_id": 0})
    if not case: raise HTTPException(status_code=404, detail="Caso no encontrado")
    await ensure_door_access(db, current_user, case["door_key"], True)
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if updates.get("door_key"):
        await ensure_door_access(db, current_user, updates["door_key"], True)
    if updates.get("responsible_person_id"): await ensure_person(db, updates["responsible_person_id"])
    updates["updated_at"] = now_utc()
    await db.door_cases.update_one({"case_id": case_id}, {"$set": updates})
    if case.get("source_type") == "cell_need":
        need_updates = {"assigned_door_key": updates.get("door_key", case["door_key"]), "status": updates.get("status", case["status"]), "responsible_person_id": updates.get("responsible_person_id", case.get("responsible_person_id")), "updated_at": now_utc()}
        await db.cell_needs.update_one({"need_id": case["source_id"]}, {"$set": need_updates})
    await record_case_event(db, case_id, current_user["user_id"], "updated", "Caso actualizado", updates)
    await record_board_audit(db, current_user["user_id"], "door_case_updated", "door_case", case_id, updates)
    return serialize(await db.door_cases.find_one({"case_id": case_id}, {"_id": 0}))


@router.get("/board", response_model=dict)
async def board_detail(current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.read")
    board = await db.governance_boards.find_one({"board_id": BOARD_ID}, {"_id": 0})
    positions = await db.board_position_catalog.find({"active": True}, {"_id": 0}).sort("order", 1).to_list(100)
    memberships = await db.board_memberships.find({"board_id": BOARD_ID}, {"_id": 0}).sort("started_at", -1).to_list(1000)
    members = [{**serialize(item), "person": await person_summary(db, item["person_id"]), "position": next((p for p in positions if p["position_key"] == item["position_key"]), None)} for item in memberships]
    return {**serialize(board), "positions": serialize(positions), "members": members}


@router.put("/board", response_model=dict)
async def update_board(payload: BoardSettingsUpdate, current_user: dict = Depends(get_current_user)):
    ensure_pastor(current_user); board = await db.governance_boards.find_one({"board_id": BOARD_ID}, {"_id": 0})
    updates = {"updated_at": now_utc()}
    if payload.name: updates["name"] = payload.name
    if payload.quorum_type or payload.quorum_value: updates["quorum_rule"] = {"type": payload.quorum_type or board["quorum_rule"]["type"], "value": payload.quorum_value or board["quorum_rule"]["value"], "rounding": "ceil"}
    if payload.tie_rule: updates["voting_rule.tie"] = payload.tie_rule
    await db.governance_boards.update_one({"board_id": BOARD_ID}, {"$set": updates})
    return serialize(await db.governance_boards.find_one({"board_id": BOARD_ID}, {"_id": 0}))


@router.post("/board/positions", response_model=dict, status_code=201)
async def create_position(payload: PositionCreate, current_user: dict = Depends(get_current_user)):
    ensure_pastor(current_user); key = f"custom_{uuid4().hex[:12]}"; now = now_utc()
    doc = {"_id": key, "position_key": key, **payload.model_dump(), "active": True, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.board_position_catalog.insert_one(doc)
    await record_board_audit(db, current_user["user_id"], "board_position_created", "board_position", key, {"name": payload.name})
    return serialize(doc)


@router.post("/board/members", response_model=dict, status_code=201)
async def add_board_member(payload: BoardMemberCreate, current_user: dict = Depends(get_current_user)):
    ensure_pastor(current_user); await ensure_person(db, payload.person_id)
    if not await db.board_position_catalog.find_one({"position_key": payload.position_key, "active": True}): raise HTTPException(status_code=422, detail="Cargo no válido")
    invalid = set(payload.permissions) - BOARD_PERMISSIONS
    if invalid: raise HTTPException(status_code=422, detail=f"Permisos no válidos: {', '.join(sorted(invalid))}")
    for key in payload.supervised_door_keys:
        if not await db.door_catalog.find_one({"door_key": key, "active": True}): raise HTTPException(status_code=422, detail=f"Puerta no válida: {key}")
    existing = await active_board_membership(db, payload.person_id)
    if existing: raise HTTPException(status_code=409, detail="La Persona ya integra la Junta")
    membership_id = str(uuid4()); now = now_utc()
    doc = {"_id": membership_id, "membership_id": membership_id, "board_id": BOARD_ID, **payload.model_dump(), "started_at": payload.started_at.isoformat(), "active": True, "ended_at": None, "end_reason": None, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.board_memberships.insert_one(doc)
    await db.users.update_one({"person_id": payload.person_id}, {"$addToSet": {"capabilities": BOARD_CONFIDENTIAL_ACCESS, "privilege_groups": "board"}})
    for door_key in payload.supervised_door_keys:
        assignment_id = str(uuid4())
        await db.door_assignments.update_one(
            {"door_key": door_key, "person_id": payload.person_id, "role": "supervisor", "active": True},
            {"$setOnInsert": {"_id": assignment_id, "assignment_id": assignment_id, "door_key": door_key, "person_id": payload.person_id, "role": "supervisor", "started_at": payload.started_at.isoformat(), "notes": "Supervisión desde Junta Directiva", "active": True, "ended_at": None, "end_reason": None, "source_board_membership_id": membership_id, "created_by_user_id": current_user["user_id"], "created_at": now}, "$set": {"updated_at": now}},
            upsert=True,
        )
    await record_board_audit(db, current_user["user_id"], "board_member_added", "board_membership", membership_id, {"person_id": payload.person_id, "position_key": payload.position_key, "supervised_door_keys": payload.supervised_door_keys})
    return serialize(doc)


@router.put("/board/members/{membership_id}/end", response_model=dict)
async def end_board_member(membership_id: str, payload: BoardMemberEnd, current_user: dict = Depends(get_current_user)):
    ensure_pastor(current_user)
    result = await db.board_memberships.update_one({"membership_id": membership_id, "active": True}, {"$set": {"active": False, "ended_at": payload.ended_at.isoformat(), "end_reason": payload.reason, "updated_at": now_utc()}})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Membresía activa no encontrada")
    await db.door_assignments.update_many({"source_board_membership_id": membership_id, "active": True}, {"$set": {"active": False, "ended_at": payload.ended_at.isoformat(), "end_reason": f"Fin de membresía de Junta: {payload.reason}", "updated_at": now_utc()}})
    ended = await db.board_memberships.find_one({"membership_id": membership_id}, {"_id": 0, "person_id": 1})
    if ended and not await db.board_memberships.find_one({"person_id": ended.get("person_id"), "active": True}):
        await db.users.update_one({"person_id": ended.get("person_id")}, {"$pull": {"capabilities": BOARD_CONFIDENTIAL_ACCESS, "privilege_groups": "board"}})
    await record_board_audit(db, current_user["user_id"], "board_member_ended", "board_membership", membership_id, {"reason": payload.reason})
    return serialize(await db.board_memberships.find_one({"membership_id": membership_id}, {"_id": 0}))


@router.get("/board/dashboard", response_model=dict)
async def board_dashboard(current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.read")
    upcoming = await db.board_meetings.find({"board_id": BOARD_ID, "status": {"$in": ["draft", "scheduled", "open"]}}, {"_id": 0}).sort("scheduled_at", 1).limit(5).to_list(5)
    return {"members_current": await db.board_memberships.count_documents({"board_id": BOARD_ID, "active": True}), "meetings_held": await db.board_meetings.count_documents({"board_id": BOARD_ID, "status": "closed"}), "open_actions": await db.board_actions.count_documents({"board_id": BOARD_ID, "status": {"$in": ["open", "in_progress"]}}), "pending_votes": await db.board_proposals.count_documents({"board_id": BOARD_ID, "status": "ready_for_vote"}), "draft_minutes": await db.board_minutes.count_documents({"board_id": BOARD_ID, "status": {"$in": ["draft", "ai_draft", "review"]}}), "upcoming": serialize(upcoming)}


@router.get("/board/meetings", response_model=dict)
async def list_board_meetings(current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.read")
    docs = await db.board_meetings.find({"board_id": BOARD_ID}, {"_id": 0}).sort("scheduled_at", -1).to_list(1000)
    return {"items": serialize(docs), "total": len(docs)}


@router.post("/board/meetings", response_model=dict, status_code=201)
async def create_board_meeting(payload: MeetingCreate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.meetings.write")
    for person_id in [payload.chair_person_id, payload.secretary_person_id]:
        if not await active_board_membership(db, person_id): raise HTTPException(status_code=409, detail="Moderador y secretario deben integrar la Junta")
    meeting_id = str(uuid4()); now = now_utc()
    doc = {"_id": meeting_id, "meeting_id": meeting_id, "board_id": BOARD_ID, **payload.model_dump(exclude={"agenda_titles"}), "status": "scheduled", "started_at": None, "ended_at": None, "recording_notice_confirmed": False, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.board_meetings.insert_one(doc)
    agenda_titles = payload.agenda_titles or (await db.governance_boards.find_one({"board_id": BOARD_ID}, {"agenda_template": 1})).get("agenda_template", [])
    if agenda_titles:
        await db.board_agenda_items.insert_many([{"_id": str(uuid4()), "agenda_item_id": str(uuid4()), "meeting_id": meeting_id, "board_id": BOARD_ID, "order": index + 1, "title": title, "description": None, "responsible_person_id": None, "estimated_minutes": 10, "actual_minutes": None, "voting_enabled": title.lower() == "votaciones", "status": "pending", "discussion": None, "decision": None, "started_at": None, "ended_at": None, "created_at": now, "updated_at": now} for index, title in enumerate(agenda_titles)])
    await record_board_audit(db, current_user["user_id"], "meeting_created", "board_meeting", meeting_id, {"title": payload.title, "scheduled_at": payload.scheduled_at})
    return serialize(doc)


async def meeting_or_404(meeting_id: str) -> dict:
    meeting = await db.board_meetings.find_one({"meeting_id": meeting_id}, {"_id": 0})
    if not meeting: raise HTTPException(status_code=404, detail="Reunión no encontrada")
    return meeting


@router.get("/board/meetings/{meeting_id}", response_model=dict)
async def board_meeting_detail(meeting_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.read"); meeting = await meeting_or_404(meeting_id)
    agenda = await db.board_agenda_items.find({"meeting_id": meeting_id}, {"_id": 0}).sort("order", 1).to_list(100)
    attendance = await db.board_meeting_attendance.find({"meeting_id": meeting_id}, {"_id": 0}).to_list(100)
    attendees = [{**serialize(item), "person": await person_summary(db, item["person_id"])} for item in attendance]
    proposals = await db.board_proposals.find({"meeting_id": meeting_id}, {"_id": 0}).sort("created_at", 1).to_list(100)
    actions = await db.board_actions.find({"meeting_id": meeting_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    minutes = await db.board_minutes.find({"meeting_id": meeting_id}, {"_id": 0}).sort("version", -1).to_list(100)
    artifacts = await db.board_ai_artifacts.find({"meeting_id": meeting_id, "valid": True}, {"_id": 0}).sort("version", -1).to_list(20)
    return {**serialize(meeting), "agenda": serialize(agenda), "attendance": attendees, "proposals": serialize(proposals), "actions": serialize(actions), "minutes": serialize(minutes), "ai_artifacts": serialize(artifacts), "quorum": await quorum_summary(db, meeting_id)}


@router.put("/board/meetings/{meeting_id}/attendance", response_model=dict)
async def save_board_attendance(meeting_id: str, payload: AttendanceBulk, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.meetings.write"); await meeting_or_404(meeting_id); now = now_utc()
    allowed_ids = set(await db.board_memberships.distinct("person_id", {"board_id": BOARD_ID, "active": True}))
    if any(item.person_id not in allowed_ids for item in payload.items): raise HTTPException(status_code=422, detail="Asistencia solo admite miembros activos")
    for item in payload.items:
        attendance_id = f"{meeting_id}:{item.person_id}"; data = item.model_dump()
        await db.board_meeting_attendance.update_one({"meeting_id": meeting_id, "person_id": item.person_id}, {"$set": {**data, "attendance_id": attendance_id, "meeting_id": meeting_id, "board_id": BOARD_ID, "updated_at": now}, "$setOnInsert": {"_id": attendance_id, "created_at": now}}, upsert=True)
    await record_board_audit(db, current_user["user_id"], "attendance_saved", "board_meeting", meeting_id, {"participant_count": len(payload.items)})
    return {"quorum": await quorum_summary(db, meeting_id)}


@router.post("/board/meetings/{meeting_id}/start", response_model=dict)
async def start_board_meeting(meeting_id: str, payload: MeetingStart, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.meetings.write"); meeting = await meeting_or_404(meeting_id)
    if not payload.recording_notice_confirmed: raise HTTPException(status_code=409, detail="Debe confirmar el aviso de grabación")
    quorum = await quorum_summary(db, meeting_id)
    await db.board_meetings.update_one({"meeting_id": meeting_id}, {"$set": {"status": "open", "started_at": meeting.get("started_at") or now_utc(), "recording_notice_confirmed": True, "quorum_at_start": quorum, "updated_at": now_utc()}})
    await record_board_audit(db, current_user["user_id"], "meeting_started", "board_meeting", meeting_id, {"quorum": quorum})
    return serialize(await db.board_meetings.find_one({"meeting_id": meeting_id}, {"_id": 0}))


@router.post("/board/meetings/{meeting_id}/agenda", response_model=dict, status_code=201)
async def add_agenda_item(meeting_id: str, payload: AgendaCreate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.meetings.write"); await meeting_or_404(meeting_id)
    if payload.responsible_person_id: await ensure_person(db, payload.responsible_person_id)
    order = await db.board_agenda_items.count_documents({"meeting_id": meeting_id}) + 1; item_id = str(uuid4()); now = now_utc()
    doc = {"_id": item_id, "agenda_item_id": item_id, "meeting_id": meeting_id, "board_id": BOARD_ID, "order": order, **payload.model_dump(), "actual_minutes": None, "status": "pending", "discussion": None, "decision": None, "started_at": None, "ended_at": None, "created_at": now, "updated_at": now}
    await db.board_agenda_items.insert_one(doc)
    await record_board_audit(db, current_user["user_id"], "agenda_item_added", "board_meeting", meeting_id, {"agenda_item_id": item_id, "title": payload.title})
    return serialize(doc)


@router.put("/board/agenda/{agenda_item_id}", response_model=dict)
async def update_agenda_item(agenda_item_id: str, payload: AgendaUpdate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.meetings.write")
    item = await db.board_agenda_items.find_one({"agenda_item_id": agenda_item_id}, {"_id": 0})
    if not item: raise HTTPException(status_code=404, detail="Punto no encontrado")
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}; updates["updated_at"] = now_utc()
    if updates.get("responsible_person_id"): await ensure_person(db, updates["responsible_person_id"])
    if updates.get("ended_at") and item.get("started_at"):
        start = item["started_at"]; end = updates["ended_at"]
        if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
        updates["actual_minutes"] = round((end - start).total_seconds() / 60, 1)
    await db.board_agenda_items.update_one({"agenda_item_id": agenda_item_id}, {"$set": updates})
    await record_board_audit(db, current_user["user_id"], "agenda_item_updated", "board_meeting", item["meeting_id"], {"agenda_item_id": agenda_item_id, "status": updates.get("status")})
    return serialize(await db.board_agenda_items.find_one({"agenda_item_id": agenda_item_id}, {"_id": 0}))


@router.get("/board/meetings/{meeting_id}/secretary-notes", response_model=dict)
async def get_secretary_notes(meeting_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.read"); await meeting_or_404(meeting_id)
    note = await db.board_secretary_notes.find_one({"meeting_id": meeting_id}, {"_id": 0})
    return serialize(note or {"meeting_id": meeting_id, "content": "", "version": 0})


@router.put("/board/meetings/{meeting_id}/secretary-notes", response_model=dict)
async def save_secretary_notes(meeting_id: str, payload: SecretaryNoteUpdate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.notes.write"); meeting = await meeting_or_404(meeting_id)
    if current_user.get("person_id") != meeting["secretary_person_id"] and DOORS_MANAGE not in current_user.get("capabilities", []): raise HTTPException(status_code=403, detail="Solo Secretaría puede editar estas notas")
    existing = await db.board_secretary_notes.find_one({"meeting_id": meeting_id}, {"_id": 0}); version = int((existing or {}).get("version", 0)) + 1; now = now_utc()
    version_id = f"{meeting_id}:{version}"
    await db.board_secretary_note_versions.insert_one({"_id": version_id, "version_id": version_id, "meeting_id": meeting_id, "board_id": BOARD_ID, "version": version, "content": payload.content, "edited_by_user_id": current_user["user_id"], "created_at": now})
    await db.board_secretary_notes.update_one({"meeting_id": meeting_id}, {"$set": {"content": payload.content, "version": version, "edited_by_user_id": current_user["user_id"], "updated_at": now}, "$setOnInsert": {"_id": meeting_id, "meeting_id": meeting_id, "board_id": BOARD_ID, "created_at": now}}, upsert=True)
    await record_board_audit(db, current_user["user_id"], "secretary_notes_versioned", "board_meeting", meeting_id, {"version": version})
    return serialize(await db.board_secretary_notes.find_one({"meeting_id": meeting_id}, {"_id": 0}))


@router.post("/board/meetings/{meeting_id}/proposals", response_model=dict, status_code=201)
async def create_proposal(meeting_id: str, payload: ProposalCreate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.vote"); await meeting_or_404(meeting_id); await ensure_person(db, payload.proposer_person_id)
    if payload.proposer_person_id != current_user.get("person_id") and DOORS_MANAGE not in current_user.get("capabilities", []): raise HTTPException(status_code=403, detail="El proponente debe ser la Persona actual")
    if payload.seconder_person_id: await ensure_person(db, payload.seconder_person_id)
    proposal_id = str(uuid4()); now = now_utc(); doc = {"_id": proposal_id, "proposal_id": proposal_id, "meeting_id": meeting_id, "board_id": BOARD_ID, **payload.model_dump(), "discussion": None, "status": "draft", "result": None, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.board_proposals.insert_one(doc)
    await record_board_audit(db, current_user["user_id"], "proposal_created", "board_proposal", proposal_id, {"meeting_id": meeting_id, "proposer_person_id": payload.proposer_person_id})
    return serialize(doc)


@router.put("/board/proposals/{proposal_id}", response_model=dict)
async def update_proposal(proposal_id: str, payload: ProposalUpdate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.meetings.write")
    proposal = await db.board_proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})
    if not proposal: raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    if payload.status in {"approved", "rejected"}:
        raise HTTPException(status_code=409, detail="El resultado se deriva exclusivamente de votos y quórum")
    await db.board_proposals.update_one({"proposal_id": proposal_id}, {"$set": {**payload.model_dump(), "updated_at": now_utc()}})
    await record_board_audit(db, current_user["user_id"], "proposal_status_changed", "board_proposal", proposal_id, {"meeting_id": proposal["meeting_id"], "status": payload.status})
    return serialize(await db.board_proposals.find_one({"proposal_id": proposal_id}, {"_id": 0}))


@router.post("/board/proposals/{proposal_id}/vote", response_model=dict)
async def cast_vote(proposal_id: str, payload: VoteCreate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.vote"); proposal = await db.board_proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})
    if not proposal: raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    if proposal["status"] != "ready_for_vote": raise HTTPException(status_code=409, detail="La propuesta no está lista para votar")
    membership = await active_board_membership(db, current_user.get("person_id"))
    if not membership or not membership.get("voting_rights"): raise HTTPException(status_code=403, detail="Sin derecho a voto")
    attendance = await db.board_meeting_attendance.find_one({"meeting_id": proposal["meeting_id"], "person_id": current_user["person_id"]}, {"_id": 0})
    if not attendance or attendance.get("status") not in {"present", "remote", "late"}: raise HTTPException(status_code=409, detail="Debe constar presente para votar")
    vote_id = f"{proposal_id}:{current_user['person_id']}"; now = now_utc()
    await db.board_votes.update_one({"proposal_id": proposal_id, "person_id": current_user["person_id"]}, {"$set": {"choice": payload.choice, "comment": payload.comment, "updated_at": now}, "$setOnInsert": {"_id": vote_id, "vote_id": vote_id, "proposal_id": proposal_id, "meeting_id": proposal["meeting_id"], "board_id": BOARD_ID, "person_id": current_user["person_id"], "cast_by_user_id": current_user["user_id"], "created_at": now}}, upsert=True)
    votes = await db.board_votes.find({"proposal_id": proposal_id}, {"_id": 0}).to_list(100)
    counts = {choice: sum(1 for item in votes if item["choice"] == choice) for choice in ["yes", "no", "abstain"]}
    quorum = await quorum_summary(db, proposal["meeting_id"])
    terminal_status = None
    if quorum["has_quorum"] and len(votes) >= quorum["present_voting"]:
        if counts["yes"] > counts["no"]: terminal_status = "approved"
        elif counts["no"] > counts["yes"]: terminal_status = "rejected"
        else:
            board = await db.governance_boards.find_one({"board_id": BOARD_ID}, {"_id": 0}) or {}
            tie_rule = board.get("voting_rule", {}).get("tie", "postponed")
            if tie_rule == "rejected": terminal_status = "rejected"
            elif tie_rule == "presiding_vote":
                meeting = await db.board_meetings.find_one({"meeting_id": proposal["meeting_id"]}, {"_id": 0, "chair_person_id": 1}) or {}
                chair_vote = next((item["choice"] for item in votes if item["person_id"] == meeting.get("chair_person_id")), "abstain")
                terminal_status = "approved" if chair_vote == "yes" else "rejected" if chair_vote == "no" else "postponed"
            else: terminal_status = "postponed"
    result_payload = {"counts": counts, "quorum": quorum, "completed": bool(terminal_status), "derived_status": terminal_status}
    updates = {"result": result_payload, "updated_at": now}
    if terminal_status: updates["status"] = terminal_status
    await db.board_proposals.update_one({"proposal_id": proposal_id}, {"$set": updates})
    await record_board_audit(db, current_user["user_id"], "vote_cast", "board_proposal", proposal_id, {"ballot_recorded": True, "meeting_id": proposal["meeting_id"]})
    return {"counts": counts, "quorum": quorum, "my_vote": payload.choice}


@router.post("/board/meetings/{meeting_id}/actions", response_model=dict, status_code=201)
async def create_action(meeting_id: str, payload: ActionCreate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.actions.write"); await meeting_or_404(meeting_id); await ensure_person(db, payload.responsible_person_id)
    action_id = str(uuid4()); now = now_utc(); doc = {"_id": action_id, "action_id": action_id, "meeting_id": meeting_id, "board_id": BOARD_ID, **payload.model_dump(), "status": "open", "result": None, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.board_actions.insert_one(doc)
    await record_board_audit(db, current_user["user_id"], "action_created", "board_action", action_id, {"meeting_id": meeting_id, "responsible_person_id": payload.responsible_person_id, "action_type": payload.action_type})
    return serialize(doc)


@router.put("/board/actions/{action_id}", response_model=dict)
async def update_action(action_id: str, payload: ActionUpdate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.actions.write")
    action = await db.board_actions.find_one({"action_id": action_id}, {"_id": 0})
    if not action: raise HTTPException(status_code=404, detail="Acción no encontrada")
    result = await db.board_actions.update_one({"action_id": action_id}, {"$set": {**payload.model_dump(), "completed_at": now_utc() if payload.status == "completed" else None, "updated_at": now_utc()}})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Acción no encontrada")
    await record_board_audit(db, current_user["user_id"], "action_status_changed", "board_action", action_id, {"meeting_id": action["meeting_id"], "status": payload.status})
    return serialize(await db.board_actions.find_one({"action_id": action_id}, {"_id": 0}))


@router.put("/board/meetings/{meeting_id}/manual-minute", response_model=dict)
async def save_manual_minute(meeting_id: str, payload: ManualMinuteUpdate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.notes.write"); await meeting_or_404(meeting_id)
    current = await db.board_minutes.find_one({"meeting_id": meeting_id, "minute_type": "manual"}, {"_id": 0}, sort=[("version", -1)]); version = int((current or {}).get("version", 0)) + 1; minute_id = str(uuid4()); now = now_utc()
    doc = {"_id": minute_id, "minute_id": minute_id, "meeting_id": meeting_id, "board_id": BOARD_ID, "minute_type": "manual", "version": version, "content": payload.content, "status": "draft", "created_by_user_id": current_user["user_id"], "created_at": now}
    await db.board_minutes.insert_one(doc)
    await record_board_audit(db, current_user["user_id"], "manual_minute_versioned", "board_minute", minute_id, {"meeting_id": meeting_id, "version": version})
    return serialize(doc)


@router.get("/board/minutes", response_model=dict)
async def minutes_book(current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.read")
    docs = await db.board_minutes.find({"board_id": BOARD_ID}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    meeting_ids = list({item["meeting_id"] for item in docs})
    meetings = {item["meeting_id"]: item async for item in db.board_meetings.find({"meeting_id": {"$in": meeting_ids}}, {"_id": 0, "meeting_id": 1, "title": 1, "scheduled_at": 1})}
    return {"items": [{**serialize(item), "meeting": serialize(meetings.get(item["meeting_id"]))} for item in docs], "total": len(docs)}


@router.put("/board/minutes/{minute_id}/status", response_model=dict)
async def update_minute_status(minute_id: str, payload: MinuteStatusUpdate, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.minutes.review")
    minute = await db.board_minutes.find_one({"minute_id": minute_id}, {"_id": 0})
    if not minute: raise HTTPException(status_code=404, detail="Minuta no encontrada")
    if payload.status == "official" and minute.get("minute_type") != "manual":
        raise HTTPException(status_code=409, detail="Un borrador IA no puede convertirse directamente en minuta oficial")
    updates = {"status": payload.status, "review_note": payload.review_note, "reviewed_by_user_id": current_user["user_id"], "reviewed_at": now_utc()}
    await db.board_minutes.update_one({"minute_id": minute_id}, {"$set": updates})
    await record_board_audit(db, current_user["user_id"], f"minute_{payload.status}", "board_minute", minute_id, {"meeting_id": minute["meeting_id"]})
    return serialize(await db.board_minutes.find_one({"minute_id": minute_id}, {"_id": 0}))


@router.get("/board/audit", response_model=dict)
async def board_audit(limit: int = Query(default=200, ge=1, le=1000), current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.audit.read")
    docs = await db.board_audit_events.find({}, {"_id": 0}).sort("occurred_at", -1).limit(limit).to_list(limit)
    return {"items": serialize(docs), "total": len(docs)}


@router.post("/board/meetings/{meeting_id}/close", response_model=dict)
async def close_board_meeting(meeting_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_board_access(db, current_user, "board.meetings.write"); meeting = await meeting_or_404(meeting_id); now = now_utc()
    if not meeting.get("started_at"): raise HTTPException(status_code=409, detail="La reunión no ha iniciado")
    started_at = meeting["started_at"]
    if started_at.tzinfo is None: started_at = started_at.replace(tzinfo=timezone.utc)
    duration = round((now - started_at).total_seconds() / 60, 1)
    await db.board_meetings.update_one({"meeting_id": meeting_id}, {"$set": {"status": "closed", "ended_at": now, "actual_duration_minutes": duration, "quorum_at_close": await quorum_summary(db, meeting_id), "updated_at": now}})
    await record_board_audit(db, current_user["user_id"], "meeting_closed", "board_meeting", meeting_id, {"duration_minutes": duration})
    return serialize(await db.board_meetings.find_one({"meeting_id": meeting_id}, {"_id": 0}))