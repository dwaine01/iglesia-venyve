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
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mentorship_outreach import (
    can_manage_outreach_campaigns, ensure_participation, is_active_mentor, now_utc, person_display_name, serialize,
)
from participation_scope import principal_authority_person_ids, without
from portal_notifications import notify_persons
from server import db, get_current_user

router = APIRouter(prefix="/api/invasions", tags=["invasion-participants"])

ROLES = ("mentor", "collaborator", "general_lead", "logistics")
ROLE_LABELS = {"mentor": "Mentor", "collaborator": "Colaborador", "general_lead": "Encargado general", "logistics": "Logística"}
STATUS_LABELS = {"invited": "Sin responder", "confirmed": "Confirmado", "declined": "No participará"}


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
    counts = {"total": len(items), **{status: sum(1 for item in items if item.get("status") == status) for status in STATUS_LABELS}, "attended": sum(1 for item in items if item.get("attended"))}
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
                         f"/procesos/consolidacion?invasion={campaign_id}", {"campaign_id": campaign_id})
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


async def ensure_indexes() -> None:
    await db.invasion_participants.create_index([("campaign_id", 1), ("person_id", 1)], unique=True)
    await db.invasion_participants.create_index([("person_id", 1), ("status", 1)])
