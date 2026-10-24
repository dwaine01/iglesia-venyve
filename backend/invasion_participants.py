"""FASE 6A — Lista de participantes de una invasión (base para 6B–6F).

Modelo de datos de la invasión (un solo documento `outreach_campaigns` más
colecciones relacionadas por `campaign_id`):

- `outreach_campaigns`: datos y plan (propósito, jornadas, encargados, puntos
  de encuentro, inicio de la semana de oración `prayer_start_date`).
- `invasion_participants` (este módulo): una fila por persona y por invasión.
    roles   ⊂ {mentor, collaborator, general_lead, logistics}
    status  ∈ {invited, confirmed, declined}   (invited = sin responder)
    attended / attended_at                     (asistió; se marca en 6B/6D)
    invited_via_front_group_id, invited_by_user_id, responded_at
- `outreach_participations` (existente): roster OPERATIVO de mentores que ya
  usan Visitas, Supervisión y métricas. Se mantiene sincronizado para el rol
  mentor; los colaboradores NO entran ahí (no son mentores en las métricas).
- Siguientes tramos sobre el mismo `campaign_id`: oración (6C), registros de
  visitas `outreach_visits` / hogares `outreach_households` (6D), etapas
  habilitadas por mentor y solicitudes de transferencia (6E).

Reglas del dueño aplicadas aquí (backend):
- La autoridad pastoral principal no es participante: nunca entra a la lista
  de confirmación ni a las métricas (`participation_scope`).
- Ser mentor o colaborador NO da acceso a módulos: no se crean cuentas ni se
  cambian capabilities (matriz 5A). Los colaboradores registran personas y
  hogares, pero no dirigen etapas sin autorización.
- Editan la lista: pastor general / coordinadores generales, el organizador
  (quien creó la invasión) y el encargado general."""
from datetime import date
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mentorship_outreach import (
    can_manage_outreach_campaigns, can_use_outreach, ensure_participation, is_active_mentor, now_utc, person_display_name, serialize,
)
from participation_scope import principal_authority_person_ids, without
from portal_notifications import notify_persons, notify_users
from server import db, get_current_user

router = APIRouter(prefix="/api/invasions", tags=["invasion-participants"])

ROLES = ("mentor", "collaborator", "general_lead", "logistics")
ROLE_LABELS = {"mentor": "Mentor", "collaborator": "Colaborador", "general_lead": "Encargado general", "logistics": "Logística"}
STATUS_LABELS = {"invited": "Sin responder", "confirmed": "Confirmado", "declined": "No participará"}


class ResponseInput(BaseModel):
    response: Literal["confirmed", "declined"]
    note: Optional[str] = Field(default=None, max_length=500)


class AttendanceInput(BaseModel):
    attended: bool


def portal_link(campaign_id: str) -> str:
    """Enlace para los invitados: su portal (Mi perfil) siempre lo pueden abrir."""
    return f"/mi-perfil?invasion={campaign_id}"


class ParticipantsAdd(BaseModel):
    role: Literal["mentor", "collaborator"]
    person_ids: list[str] = Field(default_factory=list, max_length=300)
    front_group_ids: list[str] = Field(default_factory=list, max_length=50)


def can_edit_participants(current_user: dict, campaign: dict) -> bool:
    if can_manage_outreach_campaigns(current_user):
        return True
    if campaign.get("created_by_user_id") and campaign.get("created_by_user_id") == current_user.get("user_id"):
        return True
    person_id = current_user.get("person_id")
    return bool(person_id and person_id == campaign.get("general_lead_person_id"))


async def load_campaign(campaign_id: str) -> dict:
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    return campaign


async def add_role(campaign_id: str, person_id: str, role: str, actor_user_id: Optional[str], via_group: Optional[str] = None) -> bool:
    """Agrega el rol (idempotente). Devuelve True si la persona era nueva en la lista."""
    now = now_utc()
    participant_id = str(uuid4())
    result = await db.invasion_participants.update_one(
        {"campaign_id": campaign_id, "person_id": person_id},
        {"$addToSet": {"roles": role}, "$set": {"updated_at": now}, "$setOnInsert": {
            "_id": participant_id, "participant_id": participant_id, "campaign_id": campaign_id, "person_id": person_id,
            "status": "invited", "responded_at": None, "attended": False, "attended_at": None,
            "invited_via_front_group_id": via_group, "invited_by_user_id": actor_user_id, "created_at": now,
        }},
        upsert=True,
    )
    return result.upserted_id is not None


async def sync_participants(campaign: dict, actor_user_id: Optional[str], collaborator_ids: list[str] = (), front_group_ids: list[str] = ()) -> list[str]:
    """Deja la lista coherente con el documento de la invasión: mentores del
    roster, encargados actuales, colaboradores y grupos invitados. Devuelve las
    personas nuevas (para avisarles)."""
    campaign_id = campaign["campaign_id"]
    authorities = await principal_authority_person_ids(db)
    new: list[str] = []
    # Los roles de encargado siguen al documento: quien dejó de serlo pierde el rol.
    for role, key in (("general_lead", "general_lead_person_id"), ("logistics", "logistics_lead_person_id")):
        await db.invasion_participants.update_many({"campaign_id": campaign_id, "roles": role, "person_id": {"$ne": campaign.get(key)}}, {"$pull": {"roles": role}})
        if campaign.get(key) and campaign[key] not in authorities and await add_role(campaign_id, campaign[key], role, actor_user_id):
            new.append(campaign[key])
    for person_id in without(campaign.get("assigned_mentor_ids") or [], authorities):
        if await add_role(campaign_id, person_id, "mentor", actor_user_id):
            new.append(person_id)
    for person_id in without(dict.fromkeys(collaborator_ids), authorities):
        if await add_role(campaign_id, person_id, "collaborator", actor_user_id):
            new.append(person_id)
    for group_id in dict.fromkeys(front_group_ids):
        members = await db.front_group_assignments.distinct("person_id", {"front_group_id": group_id, "active": True})
        for person_id in without(members, authorities):
            if await add_role(campaign_id, person_id, "collaborator", actor_user_id, via_group=group_id):
                new.append(person_id)
    await db.invasion_participants.delete_many({"campaign_id": campaign_id, "roles": {"$size": 0}})
    return new


async def participants_view(campaign: dict, current_user: dict) -> dict:
    rows = await db.invasion_participants.find({"campaign_id": campaign["campaign_id"]}, {"_id": 0}).to_list(2000)
    authorities = await principal_authority_person_ids(db)
    rows = [row for row in rows if row["person_id"] not in authorities]
    items = []
    for row in rows:
        roles = [role for role in ROLES if role in row.get("roles", [])]
        items.append({**serialize(row), "roles": roles, "role_labels": [ROLE_LABELS[role] for role in roles],
                      "name": await person_display_name(row["person_id"]) or "Persona",
                      "status_label": "Asistió" if row.get("attended") else STATUS_LABELS.get(row.get("status"), row.get("status"))})
    items.sort(key=lambda item: (ROLES.index(item["roles"][0]) if item["roles"] else 9, item["name"]))
    # Conteos reales de la lista (la autoridad pastoral principal nunca cuenta).
    counts = {"total": len(items), **{status: sum(1 for item in items if item.get("status") == status) for status in STATUS_LABELS}, "attended": sum(1 for item in items if item.get("attended"))}
    counts["no_response"] = counts["invited"]
    return {"campaign_id": campaign["campaign_id"], "items": items, "counts": counts, "can_edit": can_edit_participants(current_user, campaign)}


@router.get("/{campaign_id}/participants", response_model=dict)
async def list_participants(campaign_id: str, current_user: dict = Depends(get_current_user)):
    campaign = await load_campaign(campaign_id)
    person_id = current_user.get("person_id")
    listed = person_id and await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": person_id}, {"_id": 1})
    if not can_edit_participants(current_user, campaign) and not listed and person_id not in (campaign.get("assigned_mentor_ids") or []):
        raise HTTPException(status_code=403, detail="Sin acceso a esta invasión")
    # Invasiones creadas antes de la Fase 6 (o mentores agregados desde Visitas):
    # sus mentores y encargados entran a la lista al consultarla.
    await sync_participants(campaign, None)
    return await participants_view(campaign, current_user)


@router.post("/{campaign_id}/participants", response_model=dict)
async def add_participants(campaign_id: str, payload: ParticipantsAdd, current_user: dict = Depends(get_current_user)):
    """Agrega mentores o colaboradores (o los integrantes de un Grupo Frontal
    como colaboradores). Nunca crea cuentas ni da acceso a módulos."""
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo la autoridad, el organizador o el encargado general modifican la lista")
    if not payload.person_ids and not payload.front_group_ids:
        raise HTTPException(status_code=422, detail="Elige al menos una persona o un Grupo Frontal")
    authorities = await principal_authority_person_ids(db)
    rejected = [{"person_id": pid, "name": await person_display_name(pid) or "Autoridad pastoral", "reason": "La autoridad pastoral principal supervisa; no se agrega como participante"} for pid in payload.person_ids if pid in authorities]
    person_ids = without(dict.fromkeys(payload.person_ids), authorities)
    for person_id in person_ids:
        if not await person_display_name(person_id):
            raise HTTPException(status_code=404, detail="Una de las personas no existe en Persona 360")
    for group_id in payload.front_group_ids:
        if not await db.front_groups.find_one({"front_group_id": group_id, "status": {"$ne": "archived"}}, {"_id": 1}):
            raise HTTPException(status_code=404, detail="Uno de los Grupos Frontales no existe")
    new: list[str] = []
    if payload.role == "mentor":
        added_mentors = []
        for person_id in person_ids:
            name = await person_display_name(person_id)
            if not await is_active_mentor(person_id):
                rejected.append({"person_id": person_id, "name": name, "reason": "No tiene insignia de Mentor activa"}); continue
            if not await db.users.find_one({"person_id": person_id, "is_active": {"$ne": False}}, {"_id": 1}):
                rejected.append({"person_id": person_id, "name": name, "reason": "No tiene cuenta activa; créala en su perfil 360 → pestaña Mentor"}); continue
            await ensure_participation(campaign_id, person_id)
            added_mentors.append(person_id)
        if added_mentors:
            await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$addToSet": {"assigned_mentor_ids": {"$each": added_mentors}}, "$set": {"updated_at": now_utc()}})
        campaign = await load_campaign(campaign_id)
        new = await sync_participants(campaign, current_user["user_id"], front_group_ids=payload.front_group_ids)
    else:
        new = await sync_participants(campaign, current_user["user_id"], collaborator_ids=person_ids, front_group_ids=payload.front_group_ids)
    if payload.front_group_ids:
        await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$addToSet": {"invited_front_group_ids": {"$each": list(dict.fromkeys(payload.front_group_ids))}}})
    await notify_persons(new, "invasion_invited", f"Te invitaron a la invasión «{campaign['name']}»",
                         f"{campaign['location']} · del {campaign['start_date']} al {campaign['end_date']}. Confirma si vas a participar.",
                         portal_link(campaign_id), {"campaign_id": campaign_id})
    return {**await participants_view(await load_campaign(campaign_id), current_user), "added": new, "rejected": rejected}


@router.delete("/{campaign_id}/participants/{person_id}", response_model=dict)
async def remove_participant(campaign_id: str, person_id: str, role: Literal["mentor", "collaborator"], current_user: dict = Depends(get_current_user)):
    """Quita un rol. Un mentor con hogares o visitas en esta invasión no se
    quita (primero se transfieren sus contactos, como en Visitas)."""
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo la autoridad, el organizador o el encargado general modifican la lista")
    row = await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": person_id, "roles": role}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Esa persona no tiene ese rol en esta invasión")
    if role == "mentor":
        households = await db.outreach_households.count_documents({"campaign_id": campaign_id, "mentor_person_id": person_id})
        visits = await db.outreach_visits.count_documents({"campaign_id": campaign_id, "mentor_person_id": person_id})
        if households or visits:
            raise HTTPException(status_code=409, detail=f"Tiene {households} hogar(es) y {visits} visita(s) en esta invasión: primero transfiere sus contactos")
        await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$pull": {"assigned_mentor_ids": person_id}, "$set": {"updated_at": now_utc()}})
        await db.outreach_participations.delete_one({"campaign_id": campaign_id, "mentor_person_id": person_id})
    await db.invasion_participants.update_one({"campaign_id": campaign_id, "person_id": person_id}, {"$pull": {"roles": role}, "$set": {"updated_at": now_utc()}})
    await db.invasion_participants.delete_many({"campaign_id": campaign_id, "roles": {"$size": 0}})
    await db.admin_deletions.insert_one({
        "_id": str(uuid4()), "collection": "invasion_participants", "target_id": f"{campaign_id}:{person_id}:{role}",
        "reason": "Quitado de la lista de participantes", "detail": {"name": campaign.get("name"), "person_id": person_id, "role": role},
        "actor_user_id": current_user["user_id"], "actor_person_id": current_user.get("person_id"), "deleted_at": now_utc(),
    })
    return await participants_view(await load_campaign(campaign_id), current_user)


async def notify_organizers(campaign: dict, title: str, message: str) -> None:
    users = []
    if campaign.get("created_by_user_id"):
        users.append(campaign["created_by_user_id"])
    persons = [item for item in (campaign.get("general_lead_person_id"),) if item]
    if users:
        await notify_users(users, "invasion_response", title, message, f"/procesos/consolidacion?invasion={campaign['campaign_id']}", {"campaign_id": campaign["campaign_id"]})
    if persons:
        await notify_persons(persons, "invasion_response", title, message, portal_link(campaign["campaign_id"]), {"campaign_id": campaign["campaign_id"]})


@router.get("/participants/summary", response_model=dict)
async def participants_summary(current_user: dict = Depends(get_current_user)):
    """Conteos reales por invasión (invitados, confirmados, sin responder,
    no podrán, asistieron) para las invasiones que la cuenta administra."""
    authorities = await principal_authority_person_ids(db)
    campaigns = [item async for item in db.outreach_campaigns.find({"status": {"$ne": "closed"}}, {"_id": 0, "campaign_id": 1, "created_by_user_id": 1, "general_lead_person_id": 1})]
    allowed = [item["campaign_id"] for item in campaigns if can_edit_participants(current_user, item)]
    rows = await db.invasion_participants.aggregate([
        {"$match": {"campaign_id": {"$in": allowed}, "person_id": {"$nin": list(authorities)}}},
        {"$group": {"_id": "$campaign_id", "total": {"$sum": 1},
                    "confirmed": {"$sum": {"$cond": [{"$eq": ["$status", "confirmed"]}, 1, 0]}},
                    "no_response": {"$sum": {"$cond": [{"$eq": ["$status", "invited"]}, 1, 0]}},
                    "declined": {"$sum": {"$cond": [{"$eq": ["$status", "declined"]}, 1, 0]}},
                    "attended": {"$sum": {"$cond": [{"$eq": ["$attended", True]}, 1, 0]}}}},
    ]).to_list(None)
    return {"items": {row.pop("_id"): row for row in rows}}


@router.get("/mine/invitations", response_model=dict)
async def my_invitations(current_user: dict = Depends(get_current_user)):
    """Portal del invitado: sus invasiones (no terminadas primero) con su estado."""
    person_id = current_user.get("person_id")
    if not person_id:
        return {"items": []}
    # Mentores del roster de invasiones anteriores a la Fase 6 también ven su invitación.
    async for campaign in db.outreach_campaigns.find({"assigned_mentor_ids": person_id}, {"_id": 0}):
        if not await db.invasion_participants.find_one({"campaign_id": campaign["campaign_id"], "person_id": person_id}, {"_id": 1}):
            await sync_participants(campaign, None)
    rows = await db.invasion_participants.find({"person_id": person_id}, {"_id": 0}).to_list(200)
    campaigns = {item["campaign_id"]: item async for item in db.outreach_campaigns.find({"campaign_id": {"$in": [row["campaign_id"] for row in rows]}}, {"_id": 0})}
    today = date.today().isoformat()
    items = []
    for row in rows:
        campaign = campaigns.get(row["campaign_id"])
        if not campaign or campaign.get("status") == "closed":
            continue
        roles = [role for role in ROLES if role in row.get("roles", [])]
        items.append({
            "campaign_id": campaign["campaign_id"], "name": campaign.get("name"), "location": campaign.get("location"),
            "purpose": campaign.get("purpose"), "start_date": campaign.get("start_date"), "end_date": campaign.get("end_date"),
            "schedule_days": campaign.get("schedule_days") or [], "departure_point": campaign.get("departure_point") or campaign.get("meeting_place"),
            "site_meeting_point": campaign.get("site_meeting_point"), "prayer_start_date": campaign.get("prayer_start_date"),
            "roles": roles, "role_labels": [ROLE_LABELS[role] for role in roles],
            "status": row.get("status"), "status_label": "Asistió" if row.get("attended") else STATUS_LABELS.get(row.get("status")),
            "attended": bool(row.get("attended")), "responded_at": serialize(row.get("responded_at")),
            "finished": (campaign.get("end_date") or today) < today, "can_respond": (campaign.get("end_date") or today) >= today,
        })
    items.sort(key=lambda item: (item["finished"], item["start_date"] or ""))
    return {"items": items}


def schedule_day_for(campaign: dict, day: str) -> Optional[dict]:
    """La jornada programada de ese día (si la invasión definió jornadas)."""
    return next((item for item in campaign.get("schedule_days") or [] if item.get("day") == day), None)


@router.get("/mine/today", response_model=dict)
async def my_invasion_today(current_user: dict = Depends(get_current_user)):
    """Contexto de invasión para la barra inferior móvil: las invasiones en las
    que la persona participa y están activas HOY (o la más próxima), si puede
    registrar visitas propias y cuántas invitaciones le faltan por responder.
    La pastora (autoridad principal) no participa: nunca tiene contexto."""
    person_id = current_user.get("person_id")
    today = date.today().isoformat()
    empty = {"today": today, "active": [], "upcoming": None, "pending_invitations": 0, "can_register_visits": False}
    if not person_id or person_id in await principal_authority_person_ids(db):
        return empty
    rows = {row["campaign_id"]: row async for row in db.invasion_participants.find({"person_id": person_id}, {"_id": 0, "campaign_id": 1, "status": 1, "roles": 1})}
    query = {"status": {"$ne": "closed"}, "$or": [{"campaign_id": {"$in": list(rows)}}, {"assigned_mentor_ids": person_id},
                                                 {"general_lead_person_id": person_id}, {"logistics_lead_person_id": person_id}]}
    active, upcoming, pending = [], None, 0
    async for campaign in db.outreach_campaigns.find(query, {"_id": 0, "campaign_id": 1, "name": 1, "location": 1, "start_date": 1, "end_date": 1, "schedule_days": 1}):
        row = rows.get(campaign["campaign_id"]) or {}
        if row.get("status") == "declined":
            continue
        start = campaign.get("start_date") or ""
        end = campaign.get("end_date") or start
        if end and end < today:
            continue
        if row.get("status") == "invited":
            pending += 1
        item = {"campaign_id": campaign["campaign_id"], "name": campaign.get("name"), "location": campaign.get("location"),
                "start_date": start or None, "end_date": end or None, "status": row.get("status") or "confirmed", "roles": row.get("roles") or []}
        if start and start <= today:
            day = schedule_day_for(campaign, today)
            active.append({**item, "day": today, "day_label": f"Jornada de hoy · {day['start_time']}" if day and day.get("start_time") else "Jornada de hoy"})
        elif start and (upcoming is None or start < upcoming["start_date"]):
            upcoming = item
    active.sort(key=lambda item: (item["start_date"] or "", item["name"] or ""))
    can_register = await can_use_outreach(current_user) and await is_active_mentor(person_id)
    return {**empty, "active": active, "upcoming": upcoming, "pending_invitations": pending, "can_register_visits": can_register}


@router.post("/{campaign_id}/respond", response_model=dict)
async def respond_invitation(campaign_id: str, payload: ResponseInput, current_user: dict = Depends(get_current_user)):
    """"Voy a participar" / "No podré participar" desde el portal del invitado."""
    campaign = await load_campaign(campaign_id)
    person_id = current_user.get("person_id")
    if not person_id or person_id in await principal_authority_person_ids(db):
        raise HTTPException(status_code=409, detail="La autoridad pastoral principal supervisa la invasión; no confirma participación")
    if person_id in (campaign.get("assigned_mentor_ids") or []):
        await sync_participants(campaign, None)
    row = await db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": person_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=403, detail="No estás invitado a esta invasión")
    if (campaign.get("end_date") or "") < date.today().isoformat():
        raise HTTPException(status_code=409, detail="Esta invasión ya terminó")
    now = now_utc()
    await db.invasion_participants.update_one({"campaign_id": campaign_id, "person_id": person_id}, {"$set": {
        "status": payload.response, "responded_at": now, "response_note": (payload.note or "").strip() or None, "updated_at": now,
    }})
    if "mentor" in row.get("roles", []):
        # Mismo estado en el roster operativo de mentores (Visitas / Supervisión).
        await ensure_participation(campaign_id, person_id)
        if payload.response == "confirmed":
            await db.outreach_participations.update_one({"campaign_id": campaign_id, "mentor_person_id": person_id, "status": "assigned"}, {"$set": {"status": "confirmed", "confirmed_at": now, "updated_at": now}})
        else:
            await db.outreach_participations.update_one({"campaign_id": campaign_id, "mentor_person_id": person_id, "status": "confirmed"}, {"$set": {"status": "assigned", "confirmed_at": None, "updated_at": now}})
    name = await person_display_name(person_id) or "Un invitado"
    verb = "confirmó que va a participar" if payload.response == "confirmed" else "no podrá participar"
    await notify_organizers(campaign, f"{name} {verb}", f"Invasión «{campaign.get('name')}»" + (f": {payload.note.strip()}" if payload.note and payload.note.strip() else ""))
    return {"campaign_id": campaign_id, "status": payload.response, "status_label": STATUS_LABELS[payload.response]}


@router.put("/{campaign_id}/participants/{person_id}/attendance", response_model=dict)
async def set_attendance(campaign_id: str, person_id: str, payload: AttendanceInput, current_user: dict = Depends(get_current_user)):
    """Marca quién asistió (autoridad, organizador o encargado general)."""
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo la autoridad, el organizador o el encargado general marcan asistencia")
    now = now_utc()
    result = await db.invasion_participants.update_one({"campaign_id": campaign_id, "person_id": person_id}, {"$set": {
        "attended": payload.attended, "attended_at": now if payload.attended else None, "attendance_source": "manual",
        "attendance_marked_by_user_id": current_user["user_id"], "updated_at": now,
    }})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Esa persona no está en la lista de esta invasión")
    return await participants_view(campaign, current_user)


async def mark_attended_from_activity(campaign_id: Optional[str], person_id: str) -> None:
    """Registrar un hogar o una visita en la invasión cuenta como asistencia."""
    if not campaign_id or not person_id:
        return
    now = now_utc()
    await db.invasion_participants.update_one(
        {"campaign_id": campaign_id, "person_id": person_id, "attended": {"$ne": True}},
        {"$set": {"attended": True, "attended_at": now, "attendance_source": "activity", "updated_at": now}},
    )


async def ensure_indexes() -> None:
    await db.invasion_participants.create_index([("campaign_id", 1), ("person_id", 1)], unique=True)
    await db.invasion_participants.create_index([("person_id", 1), ("status", 1)])
