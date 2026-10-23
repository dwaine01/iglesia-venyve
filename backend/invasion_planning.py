"""FASE 6A — Solicitud, creación y planificación de una invasión.

Extiende las invasiones existentes (`outreach_campaigns`, mismo documento y
mismo roster de mentores/participaciones) con los datos del formulario por
pasos: propósito, jornadas, encargados, puntos de encuentro y período de
preparación en oración.

- Crear una invasión OFICIAL: solo pastor/pastora general y coordinadores
  generales (`can_manage_outreach_campaigns`, validado aquí en el backend).
- Un líder o colíder de Grupo Frontal envía una SOLICITUD (lugar y fecha
  propuestos) a una de esas autoridades, que puede aprobarla (al crear la
  invasión oficial con esa información), rechazarla o pedir cambios.
- Cada paso notifica dentro del portal (`portal_notifications`)."""
from datetime import date, timedelta
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from access_control import is_general_coordinator, is_global_pastoral_authority
from mentorship_outreach import (
    CampaignInput, MentorRosterEntry, can_manage_outreach_campaigns, create_campaign, now_utc, person_display_name, serialize,
)
from invasion_participants import can_edit_participants, sync_participants
from portal_notifications import notify_persons, notify_users
from server import db, get_current_user

router = APIRouter(prefix="/api/invasions", tags=["invasion-planning"])

PRAYER_DAYS_DEFAULT = 7


class ScheduleDay(BaseModel):
    day: date
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    duration_minutes: int = Field(ge=15, le=24 * 60)


class EmergencyContact(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=4, max_length=40)


class SiteMeetingPoint(BaseModel):
    address: Optional[str] = Field(default=None, max_length=300)
    reference: Optional[str] = Field(default=None, max_length=300)
    maps_url: Optional[str] = Field(default=None, max_length=500)


class InvasionPlanFields(BaseModel):
    purpose: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = Field(default=None, max_length=3000)
    schedule_days: list[ScheduleDay] = Field(default_factory=list, max_length=60)
    general_lead_person_id: Optional[str] = None
    logistics_lead_person_id: Optional[str] = None
    emergency_contact: Optional[EmergencyContact] = None
    departure_point: Optional[str] = Field(default="La iglesia", max_length=300)
    site_meeting_point: Optional[SiteMeetingPoint] = None
    prayer_start_date: Optional[date] = None
    invited_front_group_ids: list[str] = Field(default_factory=list, max_length=50)


class InvasionCreate(InvasionPlanFields):
    name: str = Field(min_length=2, max_length=200)
    location: str = Field(min_length=2, max_length=300)
    start_date: date
    end_date: date
    mentor_person_ids: list[str] = Field(default_factory=list, max_length=300)
    # Colaboradores: registran personas y hogares; no reciben cuenta ni módulos.
    collaborator_person_ids: list[str] = Field(default_factory=list, max_length=300)
    # Mismos campos del formulario anterior de invasiones (un solo formulario):
    # roster con credenciales para mentores sin cuenta, sectores y notas.
    assigned_mentors: list[MentorRosterEntry] = Field(default_factory=list, max_length=300)
    sectors: list[str] = Field(default_factory=list, max_length=50)
    zone_notes: Optional[str] = Field(default=None, max_length=1000)
    instructions: Optional[str] = Field(default=None, max_length=2000)
    request_id: Optional[str] = None

    @model_validator(mode="after")
    def check_dates(self):
        validate_plan_dates(self.start_date, self.end_date, self.schedule_days, self.prayer_start_date)
        return self


class InvasionUpdate(InvasionPlanFields):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    location: Optional[str] = Field(default=None, min_length=2, max_length=300)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    sectors: Optional[list[str]] = Field(default=None, max_length=50)
    zone_notes: Optional[str] = Field(default=None, max_length=1000)
    instructions: Optional[str] = Field(default=None, max_length=2000)


class RequestCreate(BaseModel):
    authority_user_id: str
    front_group_id: Optional[str] = None
    proposed_name: Optional[str] = Field(default=None, max_length=200)
    proposed_location: str = Field(min_length=2, max_length=300)
    proposed_start_date: date
    proposed_end_date: date
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_dates(self):
        if self.proposed_end_date < self.proposed_start_date:
            raise ValueError("La fecha de fin no puede ser anterior a la de inicio")
        return self


class RequestReview(BaseModel):
    decision: Literal["reject", "request_changes"]
    note: str = Field(min_length=3, max_length=2000)


def validate_plan_dates(start: date, end: date, days: list[ScheduleDay], prayer_start: Optional[date]) -> None:
    if end < start:
        raise ValueError("La fecha de fin no puede ser anterior a la de inicio")
    for item in days:
        if item.day < start or item.day > end:
            raise ValueError("Cada jornada debe estar entre la fecha de inicio y la de fin")
    if len({item.day for item in days}) != len(days):
        raise ValueError("Hay dos jornadas con la misma fecha")
    if prayer_start and prayer_start > start:
        raise ValueError("La preparación en oración debe empezar antes o el mismo día de la invasión")


def require_authority(current_user: dict = Depends(get_current_user)) -> dict:
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo el pastor general o un coordinador general puede crear o aprobar invasiones oficiales")
    return current_user


async def led_group_ids(person_id: Optional[str]) -> list[str]:
    if not person_id:
        return []
    return await db.front_group_assignments.distinct("front_group_id", {"person_id": person_id, "role": {"$in": ["leader", "co_leader"]}, "active": True})


async def authority_users() -> list[dict]:
    users = await db.users.find({"is_active": {"$ne": False}}, {"_id": 1, "nombre": 1, "rol": 1, "role": 1, "access_level": 1, "capabilities": 1, "access_title": 1}).to_list(5000)
    return [user for user in users if is_global_pastoral_authority(user) or is_general_coordinator(user)]


async def person_card(person_id: Optional[str]) -> Optional[dict]:
    if not person_id:
        return None
    return {"person_id": person_id, "name": await person_display_name(person_id)}


def plan_fields(payload: InvasionPlanFields, start: date) -> dict:
    prayer = payload.prayer_start_date or (start - timedelta(days=PRAYER_DAYS_DEFAULT))
    return {
        "purpose": payload.purpose, "description": payload.description,
        "schedule_days": [{"day": item.day.isoformat(), "start_time": item.start_time, "duration_minutes": item.duration_minutes} for item in sorted(payload.schedule_days, key=lambda entry: entry.day)],
        "general_lead_person_id": payload.general_lead_person_id, "logistics_lead_person_id": payload.logistics_lead_person_id,
        "emergency_contact": payload.emergency_contact.model_dump() if payload.emergency_contact else None,
        "departure_point": payload.departure_point or "La iglesia",
        "site_meeting_point": payload.site_meeting_point.model_dump() if payload.site_meeting_point else None,
        "prayer_start_date": prayer.isoformat(), "prayer_default": payload.prayer_start_date is None,
        "invited_front_group_ids": sorted(set(payload.invited_front_group_ids)),
    }


async def validate_people(ids: list[Optional[str]]) -> None:
    for person_id in [item for item in ids if item]:
        if not ObjectId.is_valid(person_id) or not await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}}, {"_id": 1}):
            raise HTTPException(status_code=404, detail="Una de las personas elegidas no existe en Persona 360")


async def invasion_view(campaign: dict) -> dict:
    item = serialize(campaign)
    item["general_lead"] = await person_card(campaign.get("general_lead_person_id"))
    item["logistics_lead"] = await person_card(campaign.get("logistics_lead_person_id"))
    item["mentors"] = [await person_card(person_id) for person_id in campaign.get("assigned_mentor_ids") or []]
    groups = await db.front_groups.find({"front_group_id": {"$in": campaign.get("invited_front_group_ids") or []}}, {"_id": 0, "front_group_id": 1, "name": 1}).to_list(50)
    item["invited_front_groups"] = groups
    return item


@router.post("", response_model=dict, status_code=201)
async def create_invasion(payload: InvasionCreate, current_user: dict = Depends(require_authority)):
    """Crea la invasión oficial (formulario por pasos ya revisado en pantalla).
    Si viene de una solicitud, la marca como aprobada con este campaign_id."""
    request = None
    if payload.request_id:
        request = await db.outreach_campaign_requests.find_one({"request_id": payload.request_id}, {"_id": 0})
        if not request or request["status"] not in {"pending", "changes_requested"}:
            raise HTTPException(status_code=409, detail="La solicitud ya no está pendiente")
    await validate_people([payload.general_lead_person_id, payload.logistics_lead_person_id, *payload.collaborator_person_ids])
    for group_id in payload.invited_front_group_ids:
        if not await db.front_groups.find_one({"front_group_id": group_id, "status": {"$ne": "archived"}}, {"_id": 1}):
            raise HTTPException(status_code=404, detail="Uno de los Grupos Frontales invitados no existe")
    roster = {entry.person_id: entry for entry in payload.assigned_mentors if entry.person_id}
    for person_id in payload.mentor_person_ids:
        roster.setdefault(person_id, MentorRosterEntry(person_id=person_id))
    first_day = min(payload.schedule_days, key=lambda item: item.day) if payload.schedule_days else None
    # create_campaign valida permisos y excluye a la autoridad pastoral principal del roster.
    created = await create_campaign(CampaignInput(
        name=payload.name, location=payload.location, start_date=payload.start_date, end_date=payload.end_date,
        meeting_place=payload.departure_point, meeting_time=first_day.start_time if first_day else None,
        instructions=payload.instructions, zone_notes=payload.zone_notes, sectors=payload.sectors,
        assigned_mentors=list(roster.values()),
    ), current_user)
    extra = {**plan_fields(payload, payload.start_date), "request_id": payload.request_id, "plan_version": 1}
    await db.outreach_campaigns.update_one({"campaign_id": created["campaign_id"]}, {"$set": extra})
    campaign = await db.outreach_campaigns.find_one({"campaign_id": created["campaign_id"]}, {"_id": 0})
    if request:
        await db.outreach_campaign_requests.update_one({"request_id": request["request_id"]}, {"$set": {
            "status": "approved", "campaign_id": created["campaign_id"], "reviewed_by_user_id": current_user["user_id"], "reviewed_at": now_utc(), "updated_at": now_utc(),
        }, "$push": {"history": {"at": now_utc(), "by_user_id": current_user["user_id"], "action": "approved", "note": None}}})
        await notify_users([request["requested_by_user_id"]], "invasion_request_approved", "Solicitud de invasión aprobada",
                           f"Se creó la invasión «{payload.name}» con tu solicitud.", f"/procesos/consolidacion?invasion={created['campaign_id']}", {"campaign_id": created["campaign_id"]})
    invited = await sync_participants(campaign, current_user["user_id"], payload.collaborator_person_ids, payload.invited_front_group_ids)
    await notify_persons(invited, "invasion_invited", f"Te invitaron a la invasión «{payload.name}»",
                         f"{payload.location} · del {payload.start_date.isoformat()} al {payload.end_date.isoformat()}. Confirma si vas a participar.",
                         f"/procesos/consolidacion?invasion={created['campaign_id']}", {"campaign_id": created["campaign_id"]})
    return {**await invasion_view(campaign), "accounts_created": created.get("accounts_created", [])}


@router.get("/authorities", response_model=dict)
async def list_authorities(current_user: dict = Depends(get_current_user)):
    """A quién puede dirigir un líder su solicitud de invasión."""
    users = await authority_users()
    return {"items": [{"user_id": str(user["_id"]), "name": user.get("nombre"), "title": user.get("access_title") or ("Pastor general" if is_global_pastoral_authority(user) else "Coordinador general")} for user in users]}


@router.post("/requests", response_model=dict, status_code=201)
async def create_request(payload: RequestCreate, current_user: dict = Depends(get_current_user)):
    groups = await led_group_ids(current_user.get("person_id"))
    if not groups:
        raise HTTPException(status_code=403, detail="Solo los líderes y colíderes de un Grupo Frontal pueden solicitar una invasión")
    if payload.front_group_id and payload.front_group_id not in groups:
        raise HTTPException(status_code=403, detail="Ese Grupo Frontal no lo lideras")
    authorities = {str(user["_id"]): user for user in await authority_users()}
    if payload.authority_user_id not in authorities:
        raise HTTPException(status_code=422, detail="Elige al pastor general o a un coordinador general")
    now = now_utc(); request_id = str(uuid4())
    doc = {
        "_id": request_id, "request_id": request_id, "status": "pending",
        "requested_by_user_id": current_user["user_id"], "requested_by_person_id": current_user.get("person_id"),
        "front_group_id": payload.front_group_id or groups[0], "authority_user_id": payload.authority_user_id,
        "proposed_name": payload.proposed_name, "proposed_location": payload.proposed_location,
        "proposed_start_date": payload.proposed_start_date.isoformat(), "proposed_end_date": payload.proposed_end_date.isoformat(),
        "notes": payload.notes, "review_note": None, "campaign_id": None,
        "history": [{"at": now, "by_user_id": current_user["user_id"], "action": "submitted", "note": payload.notes}],
        "created_at": now, "updated_at": now,
    }
    await db.outreach_campaign_requests.insert_one(doc)
    requester = await person_display_name(current_user.get("person_id")) or current_user.get("nombre") or "Un líder"
    await notify_users([payload.authority_user_id], "invasion_request_submitted", "Nueva solicitud de invasión",
                       f"{requester} propone una invasión en {payload.proposed_location} ({payload.proposed_start_date.isoformat()}).",
                       f"/procesos/consolidacion?solicitud={request_id}", {"request_id": request_id})
    return await request_view(doc)


async def request_view(doc: dict) -> dict:
    item = serialize(doc)
    item["requested_by_name"] = await person_display_name(doc.get("requested_by_person_id"))
    authority = await db.users.find_one({"_id": ObjectId(doc["authority_user_id"])}, {"nombre": 1}) if ObjectId.is_valid(doc.get("authority_user_id") or "") else None
    item["authority_name"] = (authority or {}).get("nombre")
    group = await db.front_groups.find_one({"front_group_id": doc.get("front_group_id")}, {"_id": 0, "name": 1})
    item["front_group_name"] = (group or {}).get("name")
    return item


@router.get("/requests", response_model=dict)
async def list_requests(status: Optional[str] = Query(None), current_user: dict = Depends(get_current_user)):
    """Autoridad: todas (las dirigidas a ella primero). Líder: las suyas."""
    query: dict = {}
    if not can_manage_outreach_campaigns(current_user):
        query["requested_by_user_id"] = current_user["user_id"]
    if status:
        query["status"] = status
    docs = await db.outreach_campaign_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    items = [await request_view(doc) for doc in docs]
    items.sort(key=lambda item: (item["authority_user_id"] != current_user["user_id"], item["status"] not in {"pending", "changes_requested"}))
    return {"items": items, "can_review": can_manage_outreach_campaigns(current_user), "can_request": bool(await led_group_ids(current_user.get("person_id")))}


@router.post("/requests/{request_id}/review", response_model=dict)
async def review_request(request_id: str, payload: RequestReview, current_user: dict = Depends(require_authority)):
    """Rechazar o pedir cambios. Aprobar = crear la invasión con `request_id`."""
    doc = await db.outreach_campaign_requests.find_one({"request_id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if doc["status"] not in {"pending", "changes_requested"}:
        raise HTTPException(status_code=409, detail="La solicitud ya fue resuelta")
    status = "rejected" if payload.decision == "reject" else "changes_requested"
    now = now_utc()
    await db.outreach_campaign_requests.update_one({"request_id": request_id}, {"$set": {"status": status, "review_note": payload.note, "reviewed_by_user_id": current_user["user_id"], "reviewed_at": now, "updated_at": now},
                                                                              "$push": {"history": {"at": now, "by_user_id": current_user["user_id"], "action": status, "note": payload.note}}})
    title = "Solicitud de invasión rechazada" if status == "rejected" else "Te piden cambios en tu solicitud de invasión"
    await notify_users([doc["requested_by_user_id"]], f"invasion_request_{status}", title, payload.note, f"/procesos/consolidacion?solicitud={request_id}", {"request_id": request_id})
    return await request_view(await db.outreach_campaign_requests.find_one({"request_id": request_id}, {"_id": 0}))


@router.put("/requests/{request_id}", response_model=dict)
async def update_request(request_id: str, payload: RequestCreate, current_user: dict = Depends(get_current_user)):
    """El líder corrige su solicitud cuando le pidieron cambios (vuelve a pendiente)."""
    doc = await db.outreach_campaign_requests.find_one({"request_id": request_id}, {"_id": 0})
    if not doc or doc["requested_by_user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if doc["status"] not in {"pending", "changes_requested"}:
        raise HTTPException(status_code=409, detail="La solicitud ya fue resuelta")
    if payload.authority_user_id not in {str(user["_id"]) for user in await authority_users()}:
        raise HTTPException(status_code=422, detail="Elige al pastor general o a un coordinador general")
    now = now_utc()
    await db.outreach_campaign_requests.update_one({"request_id": request_id}, {"$set": {
        "status": "pending", "authority_user_id": payload.authority_user_id, "proposed_name": payload.proposed_name,
        "proposed_location": payload.proposed_location, "proposed_start_date": payload.proposed_start_date.isoformat(),
        "proposed_end_date": payload.proposed_end_date.isoformat(), "notes": payload.notes, "updated_at": now,
    }, "$push": {"history": {"at": now, "by_user_id": current_user["user_id"], "action": "resubmitted", "note": payload.notes}}})
    await notify_users([payload.authority_user_id], "invasion_request_submitted", "Solicitud de invasión corregida",
                       f"Se corrigió la solicitud para {payload.proposed_location}.", f"/procesos/consolidacion?solicitud={request_id}", {"request_id": request_id})
    return await request_view(await db.outreach_campaign_requests.find_one({"request_id": request_id}, {"_id": 0}))


@router.get("/{campaign_id}", response_model=dict)
async def get_invasion(campaign_id: str, current_user: dict = Depends(get_current_user)):
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    person_id = current_user.get("person_id")
    involved = person_id and (person_id in (campaign.get("assigned_mentor_ids") or []) or bool(await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": person_id}, {"_id": 1})))
    if not can_edit_participants(current_user, campaign) and not involved:
        raise HTTPException(status_code=403, detail="Sin acceso a esta invasión")
    return {**await invasion_view(campaign), "can_edit": can_manage_outreach_campaigns(current_user), "can_edit_participants": can_edit_participants(current_user, campaign)}


@router.put("/{campaign_id}", response_model=dict)
async def update_invasion(campaign_id: str, payload: InvasionUpdate, current_user: dict = Depends(require_authority)):
    """Reemplaza el plan completo (el formulario siempre envía todos los pasos)."""
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    start = payload.start_date or date.fromisoformat(campaign["start_date"])
    end = payload.end_date or date.fromisoformat(campaign["end_date"])
    try:
        validate_plan_dates(start, end, payload.schedule_days, payload.prayer_start_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await validate_people([payload.general_lead_person_id, payload.logistics_lead_person_id])
    update = {**plan_fields(payload, start), "start_date": start.isoformat(), "end_date": end.isoformat(), "updated_at": now_utc()}
    if payload.name: update["name"] = payload.name.strip()
    if payload.location: update["location"] = payload.location.strip()
    update["meeting_place"] = update["departure_point"]
    if payload.schedule_days:
        update["meeting_time"] = min(payload.schedule_days, key=lambda item: item.day).start_time
    if payload.sectors is not None:
        update["sectors"] = [item.strip() for item in payload.sectors if item and item.strip()]
    for key in ("zone_notes", "instructions"):
        if key in payload.model_fields_set:
            update[key] = getattr(payload, key)
    await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$set": update, "$inc": {"plan_version": 1}})
    refreshed = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    previous = set(await db.invasion_participants.distinct("person_id", {"campaign_id": campaign_id}))
    invited = await sync_participants(refreshed, current_user["user_id"], front_group_ids=payload.invited_front_group_ids)
    await notify_persons(invited, "invasion_invited", f"Te invitaron a la invasión «{refreshed['name']}»",
                         f"{refreshed['location']} · del {refreshed['start_date']} al {refreshed['end_date']}. Confirma si vas a participar.",
                         f"/procesos/consolidacion?invasion={campaign_id}", {"campaign_id": campaign_id})
    await notify_persons(sorted(previous), "invasion_updated", f"Se actualizó la invasión «{refreshed['name']}»",
                         f"{refreshed['location']} · del {refreshed['start_date']} al {refreshed['end_date']}. Revisa los cambios.",
                         f"/procesos/consolidacion?invasion={campaign_id}", {"campaign_id": campaign_id})
    return {**await invasion_view(refreshed), "can_edit": True, "can_edit_participants": True}


async def ensure_indexes() -> None:
    await db.outreach_campaign_requests.create_index("request_id", unique=True)
    await db.outreach_campaign_requests.create_index([("authority_user_id", 1), ("status", 1), ("created_at", -1)])
    await db.outreach_campaign_requests.create_index([("requested_by_user_id", 1), ("created_at", -1)])
