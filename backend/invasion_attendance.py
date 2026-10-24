"""Asistencia POR JORNADA y Programa de cada invasión (barra inferior móvil).

- Asistencia: una marca por persona y por día (`invasion_participants.attended_days`).
  `attended` (la marca única de 6B que usan el reporte y las métricas) queda en
  True mientras haya al menos una jornada marcada o actividad registrada.
  Solo la marcan: autoridad pastoral / coordinadores generales, el organizador y
  el encargado general de esa invasión (`can_edit_participants`). La autoridad
  pastoral principal nunca aparece ni cuenta en los porcentajes.
- Programa: lectura para todos los invitados de esa invasión; editar sigue
  siendo del organizador/autoridad con el formulario por pasos (PUT /api/invasions/{id})."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from invasion_participants import (
    ROLE_LABELS, ROLES, STATUS_LABELS, add_role, can_edit_participants, load_campaign, sync_participants,
)
from mentorship_outreach import can_manage_outreach_campaigns, now_utc, person_display_name, serialize
from participation_scope import principal_authority_person_ids
from server import db, get_current_user

router = APIRouter(prefix="/api/invasions", tags=["invasion-attendance"])


class DayAttendanceInput(BaseModel):
    day: date
    attended: bool


class WalkInInput(BaseModel):
    person_id: str
    day: date


def campaign_days(campaign: dict) -> list[dict]:
    """Jornadas de la invasión: las programadas o, si no hay, cada día del rango."""
    scheduled = campaign.get("schedule_days") or []
    if scheduled:
        return [{"day": item["day"], "start_time": item.get("start_time"), "duration_minutes": item.get("duration_minutes")} for item in sorted(scheduled, key=lambda entry: entry["day"])]
    start = date.fromisoformat(campaign["start_date"])
    end = date.fromisoformat(campaign.get("end_date") or campaign["start_date"])
    return [{"day": (start + timedelta(days=offset)).isoformat(), "start_time": campaign.get("meeting_time"), "duration_minutes": None} for offset in range(min((end - start).days, 30) + 1)]


def default_day(days: list[dict]) -> Optional[str]:
    today = date.today().isoformat()
    if not days:
        return None
    if any(item["day"] == today for item in days):
        return today
    past = [item["day"] for item in days if item["day"] < today]
    return past[-1] if past else days[0]["day"]


async def require_attendance_access(campaign_id: str, current_user: dict) -> dict:
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="La asistencia solo la ven y marcan coordinadores generales, la autoridad pastoral, el organizador y el encargado general")
    return campaign


async def managed_invasions(current_user: dict) -> list[dict]:
    """Invasiones cuya asistencia puede marcar la persona (no cerradas y sin
    más de 7 días de terminadas), la de hoy primero."""
    today = date.today()
    since = (today - timedelta(days=7)).isoformat()
    query: dict = {"status": {"$ne": "closed"}, "$or": [{"end_date": {"$gte": since}}, {"end_date": None, "start_date": {"$gte": since}}]}
    if not can_manage_outreach_campaigns(current_user):
        mine = [{"created_by_user_id": current_user.get("user_id")}]
        if current_user.get("person_id"):
            mine.append({"general_lead_person_id": current_user["person_id"]})
        query = {"$and": [query, {"$or": mine}]}
    items = []
    async for campaign in db.outreach_campaigns.find(query, {"_id": 0, "campaign_id": 1, "name": 1, "location": 1, "start_date": 1, "end_date": 1}).limit(100):
        start, end = campaign.get("start_date") or "", campaign.get("end_date") or campaign.get("start_date") or ""
        items.append({**campaign, "active_today": start <= today.isoformat() <= end})
    items.sort(key=lambda item: (not item["active_today"], item.get("start_date") or ""))
    return items


async def front_group_names(person_ids: list[str]) -> dict[str, str]:
    group_of: dict[str, str] = {}
    assignments = await db.front_group_assignments.find({"person_id": {"$in": person_ids}, "active": True}, {"_id": 0, "person_id": 1, "front_group_id": 1, "role": 1}).to_list(5000)
    for item in sorted(assignments, key=lambda entry: {"leader": 0, "co_leader": 1}.get(entry.get("role"), 2)):
        group_of.setdefault(item["person_id"], item["front_group_id"])
    names = {doc["front_group_id"]: doc.get("name") or "Grupo sin nombre" async for doc in db.front_groups.find({"front_group_id": {"$in": list(set(group_of.values()))}}, {"_id": 0, "front_group_id": 1, "name": 1})}
    return {person_id: names.get(group_id) for person_id, group_id in group_of.items()}


async def attendance_view(campaign: dict, day: str) -> dict:
    authorities = await principal_authority_person_ids(db)
    rows = [row for row in await db.invasion_participants.find({"campaign_id": campaign["campaign_id"]}, {"_id": 0}).to_list(3000) if row["person_id"] not in authorities]
    groups = await front_group_names([row["person_id"] for row in rows])
    items = []
    for row in rows:
        roles = [role for role in ROLES if role in row.get("roles", [])]
        days = row.get("attended_days") or []
        items.append({"person_id": row["person_id"], "name": await person_display_name(row["person_id"]) or "Persona", "roles": roles,
                      "role_labels": [ROLE_LABELS[role] for role in roles], "front_group": groups.get(row["person_id"]),
                      "status": row.get("status"), "status_label": STATUS_LABELS.get(row.get("status"), row.get("status")),
                      "walk_in": bool(row.get("walk_in")), "attended_day": day in days, "attended_days": days, "attended_any": bool(row.get("attended"))})
    items.sort(key=lambda item: item["name"].lower())
    invited = len(items)
    attended = sum(1 for item in items if item["attended_day"])
    counts = {"invited": invited, "confirmed": sum(1 for item in items if item["status"] == "confirmed"),
              "no_response": sum(1 for item in items if item["status"] == "invited"), "declined": sum(1 for item in items if item["status"] == "declined"),
              "attended_day": attended, "pct_day": round(attended / invited * 100) if invited else None}
    days = campaign_days(campaign)
    by_day = {item["day"]: 0 for item in days}
    for item in items:
        for value in item["attended_days"]:
            if value in by_day:
                by_day[value] += 1
    return {"campaign_id": campaign["campaign_id"], "name": campaign.get("name"), "location": campaign.get("location"),
            "day": day, "days": [{**item, "attended": by_day.get(item["day"], 0)} for item in days], "counts": counts, "items": items}


def check_day(campaign: dict, day: date) -> str:
    value = day.isoformat()
    if value not in {item["day"] for item in campaign_days(campaign)}:
        raise HTTPException(status_code=422, detail="Ese día no es una jornada de esta invasión")
    return value


@router.get("/{campaign_id}/attendance", response_model=dict)
async def get_attendance(campaign_id: str, day: Optional[date] = Query(None), current_user: dict = Depends(get_current_user)):
    campaign = await require_attendance_access(campaign_id, current_user)
    await sync_participants(campaign, None)
    selected = check_day(campaign, day) if day else default_day(campaign_days(campaign))
    return await attendance_view(campaign, selected)


@router.put("/{campaign_id}/attendance/{person_id}", response_model=dict)
async def set_day_attendance(campaign_id: str, person_id: str, payload: DayAttendanceInput, current_user: dict = Depends(get_current_user)):
    """Un toque = asistió en esa jornada; otro toque lo deshace."""
    campaign = await require_attendance_access(campaign_id, current_user)
    day = check_day(campaign, payload.day)
    row = await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": person_id}, {"_id": 0})
    if not row or person_id in await principal_authority_person_ids(db):
        raise HTTPException(status_code=404, detail="Esa persona no está en la lista de esta invasión")
    days = set(row.get("attended_days") or [])
    if payload.attended:
        days.add(day)
    else:
        days.discard(day)
    now = now_utc()
    # La marca general sigue viva si hay otra jornada o actividad registrada en campo.
    attended = bool(days) or row.get("attendance_source") == "activity"
    await db.invasion_participants.update_one({"campaign_id": campaign_id, "person_id": person_id}, {"$set": {
        "attended_days": sorted(days), "attended": attended, "attended_at": (row.get("attended_at") or now) if attended else None,
        "attendance_source": row.get("attendance_source") if row.get("attendance_source") == "activity" else "manual",
        "attendance_marked_by_user_id": current_user["user_id"], "updated_at": now,
    }})
    return {"person_id": person_id, "day": day, "attended_day": payload.attended, "attended_any": attended}


@router.post("/{campaign_id}/attendance/walk-in", response_model=dict)
async def add_walk_in(campaign_id: str, payload: WalkInInput, current_user: dict = Depends(get_current_user)):
    """Llegó sin estar invitado: se agrega como colaborador confirmado y se marca."""
    campaign = await require_attendance_access(campaign_id, current_user)
    day = check_day(campaign, payload.day)
    if payload.person_id in await principal_authority_person_ids(db):
        raise HTTPException(status_code=409, detail="La autoridad pastoral principal supervisa la invasión; no se marca como participante")
    from bson import ObjectId
    if not ObjectId.is_valid(payload.person_id) or not await db.persons.find_one({"_id": ObjectId(payload.person_id), "is_archived": {"$ne": True}}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Esa persona no existe en Persona 360")
    existing = await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": payload.person_id}, {"_id": 1})
    if not existing:
        await add_role(campaign_id, payload.person_id, "collaborator", current_user["user_id"])
        await db.invasion_participants.update_one({"campaign_id": campaign_id, "person_id": payload.person_id}, {"$set": {"status": "confirmed", "walk_in": True}})
    return await set_day_attendance(campaign_id, payload.person_id, DayAttendanceInput(day=payload.day, attended=True), current_user) | {"added": not existing, "day": day}


@router.get("/{campaign_id}/program", response_model=dict)
async def get_program(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Programa de la invasión: lectura para sus invitados; editable por la autoridad."""
    from invasion_planning import invasion_view
    campaign = await load_campaign(campaign_id)
    person_id = current_user.get("person_id")
    involved = bool(person_id) and (person_id in (campaign.get("assigned_mentor_ids") or []) or person_id in (campaign.get("general_lead_person_id"), campaign.get("logistics_lead_person_id"))
                                     or bool(await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": person_id}, {"_id": 1})))
    manager = can_edit_participants(current_user, campaign)
    if not manager and not involved:
        raise HTTPException(status_code=403, detail="Sin acceso al programa de esta invasión")
    view = await invasion_view(campaign)
    meetings = await db.invasion_prayer_meetings.find({"campaign_id": campaign_id}, {"_id": 0, "meeting_id": 1, "day": 1, "time": 1, "place": 1, "note": 1, "title": 1}).sort([("day", 1), ("time", 1)]).to_list(100)
    keys = ("campaign_id", "name", "location", "purpose", "description", "start_date", "end_date", "sectors", "zone_notes", "instructions", "departure_point",
            "meeting_place", "meeting_time", "site_meeting_point", "prayer_start_date", "emergency_contact", "general_lead", "logistics_lead", "status")
    return {**{key: view.get(key) for key in keys}, "schedule_days": campaign_days(campaign), "prayer_meetings": serialize(meetings),
            "can_edit": can_manage_outreach_campaigns(current_user), "can_take_attendance": manager}
