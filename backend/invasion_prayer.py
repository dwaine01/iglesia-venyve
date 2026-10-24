"""FASE 6C — Preparación en oración (primera etapa de cada invasión).

- Período: desde `prayer_start_date` (por defecto una semana antes) hasta el
  día anterior a la invasión. Se puede seguir marcando durante la invasión.
- Cada participante marca desde su portal "Hoy oré en casa" (una vez por día).
- El encargado / organizador / autoridad crea las reuniones de oración en la
  iglesia, registra la asistencia y puede marcar la oración de alguien.
- El panel muestra el avance: quién registró oración, asistencia a reuniones y
  quién necesita seguimiento (regla explicable abajo).

Cuenta la lista de participantes que no respondió "No podré participar"; la
autoridad pastoral principal nunca cuenta (no está en la lista).

Colecciones: `invasion_prayer_logs` (una fila por persona y día de oración en
casa) y `invasion_prayer_meetings` (reuniones con su lista de asistentes)."""
from datetime import date, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from invasion_participants import can_edit_participants, load_campaign
from mentorship_outreach import now_utc, person_display_name
from participation_scope import principal_authority_person_ids
from server import db, get_current_user

router = APIRouter(prefix="/api/invasions", tags=["invasion-prayer"])

FOLLOWUP_RATIO = 0.5   # menos de la mitad de los días transcurridos → seguimiento
FOLLOWUP_GAP_DAYS = 3  # o sin registrar oración en los últimos 3 días del período


class HomePrayerInput(BaseModel):
    day: Optional[date] = None
    prayed: bool = True


class MeetingInput(BaseModel):
    day: date
    time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    place: str = Field(default="La iglesia", min_length=2, max_length=200)
    note: Optional[str] = Field(default=None, max_length=500)


class MeetingAttendanceInput(BaseModel):
    person_id: str
    attended: bool


def prayer_period(campaign: dict) -> tuple[date, date, date]:
    """(inicio de oración, último día de preparación, fin de la invasión)."""
    start = date.fromisoformat(campaign["start_date"][:10])
    end = date.fromisoformat((campaign.get("end_date") or campaign["start_date"])[:10])
    prayer_start = date.fromisoformat(campaign["prayer_start_date"][:10]) if campaign.get("prayer_start_date") else start - timedelta(days=7)
    return prayer_start, max(prayer_start, start - timedelta(days=1)), end


def expected_days(campaign: dict, today: Optional[date] = None) -> int:
    today = today or date.today()
    prayer_start, prep_end, _ = prayer_period(campaign)
    if today < prayer_start:
        return 0
    return (min(today, prep_end) - prayer_start).days + 1


async def counted_participants(campaign_id: str) -> list[dict]:
    authorities = await principal_authority_person_ids(db)
    rows = await db.invasion_participants.find({"campaign_id": campaign_id, "status": {"$ne": "declined"}}, {"_id": 0, "person_id": 1, "roles": 1, "status": 1}).to_list(2000)
    return [row for row in rows if row["person_id"] not in authorities]


def needs_followup(days: list[str], expected: int, today: date, prep_end: date) -> Optional[str]:
    """Regla explicable de seguimiento (o None si va bien)."""
    if expected <= 0:
        return None
    if len(days) < expected * FOLLOWUP_RATIO:
        return f"Registró {len(days)} de {expected} día(s) de oración"
    reference = min(today, prep_end)
    if not any(reference - timedelta(days=FOLLOWUP_GAP_DAYS - 1) <= date.fromisoformat(day) <= reference for day in days):
        return f"Sin registrar oración en los últimos {FOLLOWUP_GAP_DAYS} días"
    return None


async def prayer_summary(campaign: dict) -> dict:
    """Avance completo (agregado en pocas consultas, sin N+1)."""
    campaign_id = campaign["campaign_id"]
    today = date.today()
    prayer_start, prep_end, end = prayer_period(campaign)
    expected = expected_days(campaign, today)
    participants = await counted_participants(campaign_id)
    person_ids = [row["person_id"] for row in participants]
    days_by_person: dict[str, list[str]] = {}
    async for log in db.invasion_prayer_logs.find({"campaign_id": campaign_id, "person_id": {"$in": person_ids}}, {"_id": 0, "person_id": 1, "day": 1}):
        days_by_person.setdefault(log["person_id"], []).append(log["day"])
    meetings = await db.invasion_prayer_meetings.find({"campaign_id": campaign_id}, {"_id": 0}).sort([("day", 1), ("time", 1)]).to_list(100)
    held = [meeting for meeting in meetings if meeting["day"] <= today.isoformat()]
    items = []
    for row in participants:
        days = sorted(set(days_by_person.get(row["person_id"], [])))
        attended = [meeting["meeting_id"] for meeting in meetings if row["person_id"] in (meeting.get("attendee_ids") or [])]
        items.append({
            "person_id": row["person_id"], "name": await person_display_name(row["person_id"]) or "Persona", "roles": row.get("roles", []),
            "status": row.get("status"), "prayer_days": days, "prayer_count": len(days),
            "meetings_attended": attended, "meetings_attended_count": len(attended),
            "followup_reason": needs_followup(days, expected, today, prep_end),
        })
    items.sort(key=lambda item: (item["followup_reason"] is None, item["name"]))
    total = len(items)
    prayed_any = sum(1 for item in items if item["prayer_count"])
    meeting_slots = total * len(held)
    held_ids = {meeting["meeting_id"] for meeting in held}
    meeting_attendance = sum(1 for item in items for meeting_id in item["meetings_attended"] if meeting_id in held_ids)
    return {
        "campaign_id": campaign_id,
        "period": {"prayer_start": prayer_start.isoformat(), "prep_end": prep_end.isoformat(), "end": end.isoformat(), "expected_days": expected,
                   "total_days": (prep_end - prayer_start).days + 1, "status": "upcoming" if today < prayer_start else "active" if today <= prep_end else "done"},
        "totals": {
            "participants": total, "prayed_any": prayed_any, "prayed_any_pct": round(prayed_any / total * 100) if total else None,
            "avg_days": round(sum(item["prayer_count"] for item in items) / total, 1) if total else None,
            "meetings": len(meetings), "meetings_held": len(held),
            "meeting_attendance_pct": round(meeting_attendance / meeting_slots * 100) if meeting_slots else None,
            "needs_followup": sum(1 for item in items if item["followup_reason"]),
        },
        "rule": f"Necesita seguimiento: registró menos de la mitad de los días transcurridos o no registró oración en los últimos {FOLLOWUP_GAP_DAYS} días del período.",
        "meetings": [{**meeting, "attendee_count": len(meeting.get("attendee_ids") or [])} for meeting in meetings],
        "items": items,
    }


async def require_listed_or_editor(campaign: dict, current_user: dict) -> tuple[bool, Optional[dict]]:
    editor = can_edit_participants(current_user, campaign)
    row = None
    if current_user.get("person_id"):
        row = await db.invasion_participants.find_one({"campaign_id": campaign["campaign_id"], "person_id": current_user["person_id"]}, {"_id": 0})
    if not editor and not row:
        raise HTTPException(status_code=403, detail="Sin acceso a esta invasión")
    return editor, row


@router.get("/{campaign_id}/prayer", response_model=dict)
async def get_prayer(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Editor: avance completo. Participante: solo lo suyo y las reuniones."""
    campaign = await load_campaign(campaign_id)
    editor, row = await require_listed_or_editor(campaign, current_user)
    summary = await prayer_summary(campaign)
    if editor:
        return {**summary, "can_edit": True}
    mine = next((item for item in summary["items"] if item["person_id"] == current_user.get("person_id")), None)
    return {"campaign_id": campaign_id, "period": summary["period"], "meetings": [{key: value for key, value in meeting.items() if key != "attendee_ids"} | {"i_attended": current_user.get("person_id") in (meeting.get("attendee_ids") or [])} for meeting in summary["meetings"]],
            "mine": mine, "can_edit": False, "declined": bool(row and row.get("status") == "declined")}


def _check_day(campaign: dict, day: date) -> None:
    prayer_start, _, end = prayer_period(campaign)
    if day > date.today():
        raise HTTPException(status_code=422, detail="No se puede marcar un día que todavía no llega")
    if day < prayer_start or day > end:
        raise HTTPException(status_code=422, detail="Ese día está fuera del período de oración de esta invasión")


async def _set_home(campaign: dict, person_id: str, day: date, prayed: bool, actor: dict, source: str) -> None:
    if prayed:
        await db.invasion_prayer_logs.update_one(
            {"campaign_id": campaign["campaign_id"], "person_id": person_id, "day": day.isoformat()},
            {"$setOnInsert": {"_id": str(uuid4()), "kind": "home", "source": source, "marked_by_user_id": actor["user_id"], "created_at": now_utc()}},
            upsert=True,
        )
    else:
        await db.invasion_prayer_logs.delete_one({"campaign_id": campaign["campaign_id"], "person_id": person_id, "day": day.isoformat()})


@router.post("/{campaign_id}/prayer/home", response_model=dict)
async def mark_my_home_prayer(campaign_id: str, payload: HomePrayerInput, current_user: dict = Depends(get_current_user)):
    """"Hoy oré en casa" desde el portal del participante."""
    campaign = await load_campaign(campaign_id)
    person_id = current_user.get("person_id")
    if not person_id or person_id in await principal_authority_person_ids(db):
        raise HTTPException(status_code=409, detail="La autoridad pastoral principal no se cuenta como participante")
    row = await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": person_id}, {"_id": 0, "status": 1})
    if not row:
        raise HTTPException(status_code=403, detail="No estás invitado a esta invasión")
    if row.get("status") == "declined":
        raise HTTPException(status_code=409, detail="Respondiste que no podrás participar")
    day = payload.day or date.today()
    _check_day(campaign, day)
    await _set_home(campaign, person_id, day, payload.prayed, current_user, "self")
    return await get_prayer(campaign_id, current_user)


@router.put("/{campaign_id}/prayer/home/{person_id}", response_model=dict)
async def mark_home_prayer_for(campaign_id: str, person_id: str, payload: HomePrayerInput, current_user: dict = Depends(get_current_user)):
    """El encargado marca (o corrige) la oración de un participante."""
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo la autoridad, el organizador o el encargado general")
    if not await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": person_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Esa persona no está en la lista de esta invasión")
    day = payload.day or date.today()
    _check_day(campaign, day)
    await _set_home(campaign, person_id, day, payload.prayed, current_user, "leader")
    return {**await prayer_summary(campaign), "can_edit": True}


@router.post("/{campaign_id}/prayer/meetings", response_model=dict, status_code=201)
async def create_meeting(campaign_id: str, payload: MeetingInput, current_user: dict = Depends(get_current_user)):
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo la autoridad, el organizador o el encargado general")
    prayer_start, _, end = prayer_period(campaign)
    if payload.day < prayer_start or payload.day > end:
        raise HTTPException(status_code=422, detail="La reunión debe estar dentro del período de oración de la invasión")
    meeting_id = str(uuid4())
    await db.invasion_prayer_meetings.insert_one({
        "_id": meeting_id, "meeting_id": meeting_id, "campaign_id": campaign_id, "day": payload.day.isoformat(), "time": payload.time,
        "place": payload.place.strip(), "note": (payload.note or "").strip() or None, "attendee_ids": [],
        "created_by_user_id": current_user["user_id"], "created_at": now_utc(),
    })
    return {**await prayer_summary(campaign), "can_edit": True}


@router.delete("/{campaign_id}/prayer/meetings/{meeting_id}", response_model=dict)
async def delete_meeting(campaign_id: str, meeting_id: str, current_user: dict = Depends(get_current_user)):
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo la autoridad, el organizador o el encargado general")
    meeting = await db.invasion_prayer_meetings.find_one({"campaign_id": campaign_id, "meeting_id": meeting_id}, {"_id": 0})
    if not meeting:
        raise HTTPException(status_code=404, detail="Reunión no encontrada")
    if meeting.get("attendee_ids"):
        raise HTTPException(status_code=409, detail="Esta reunión ya tiene asistencia registrada; quita primero la asistencia")
    await db.invasion_prayer_meetings.delete_one({"meeting_id": meeting_id})
    return {**await prayer_summary(campaign), "can_edit": True}


@router.put("/{campaign_id}/prayer/meetings/{meeting_id}/attendance", response_model=dict)
async def set_meeting_attendance(campaign_id: str, meeting_id: str, payload: MeetingAttendanceInput, current_user: dict = Depends(get_current_user)):
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo la autoridad, el organizador o el encargado general registran asistencia")
    if payload.person_id in await principal_authority_person_ids(db):
        raise HTTPException(status_code=409, detail="La autoridad pastoral principal no se cuenta como participante")
    if not await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": payload.person_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Esa persona no está en la lista de esta invasión")
    meeting = await db.invasion_prayer_meetings.find_one({"campaign_id": campaign_id, "meeting_id": meeting_id}, {"_id": 0, "day": 1})
    if not meeting:
        raise HTTPException(status_code=404, detail="Reunión no encontrada")
    if meeting["day"] > date.today().isoformat():
        raise HTTPException(status_code=422, detail="La reunión todavía no se realiza")
    operator = "$addToSet" if payload.attended else "$pull"
    await db.invasion_prayer_meetings.update_one({"meeting_id": meeting_id}, {operator: {"attendee_ids": payload.person_id}})
    return {**await prayer_summary(campaign), "can_edit": True}


async def ensure_indexes() -> None:
    await db.invasion_prayer_logs.create_index([("campaign_id", 1), ("person_id", 1), ("day", 1)], unique=True)
    await db.invasion_prayer_meetings.create_index([("campaign_id", 1), ("day", 1)])
