"""Eliminar la CUENTA de un líder (Panel General → Líderes y su Desempeño).

Solo la autoridad pastoral. Nunca a sí misma ni a otro pastor.

Qué pasa con la cuenta: queda DESACTIVADA y marcada como eliminada (no se borra de la base; se puede
revisar o reactivar). Sus sesiones dejan de valer al instante (cada petición busca la cuenta) y se
borran sus avisos del portal.

Su trabajo pendiente NO puede quedar huérfano (auditoría 5/10): la vista previa muestra discípulos en
Consolidación, contactos y visitas por hacer, viviendas, seguimientos de tableta, transferencias y
libros en su poder; si tiene algo, hay que elegir a qué mentor pasarlo (work_handover).

Qué NO se borra: las personas ni su historial de Persona 360, incluida la ficha
360 del propio líder. Las personas asignadas al líder quedan sin líder
(`leader_id: None`, con `previous_leader_id` para trazabilidad) y siguen
visibles en el Panel General para reasignarlas.

Referencias que se limpian o se marcan inactivas:
- Grupos Frontales: sus asignaciones activas terminan (con motivo) y deja de
  figurar como líder/colíder de los grupos (quedan "por definir").
- Invasiones ACTIVAS (fin hoy o después): sale del roster de mentores y de la
  lista de participantes si no registró hogares ni visitas; si registró, se
  conserva como historial con la participación marcada inactiva. Sus casas
  sin visitas vuelven a "disponibles". Las invasiones pasadas no se tocan.
- Insignia de mentor: se desactiva (con historial).
- Códigos de invitación pendientes creados por él o que asignaban a él: vencen.
- Cuentas que dependían de él (`parent_user_id`) pasan a quien elimina.
Todo queda en `admin_deletions` (Historial de borrados)."""
import re
import unicodedata
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import is_global_pastoral_authority
from server import db, get_current_user, utc_now
from count_rules import church_today  # «hoy» en la zona de la iglesia (auditoría 7/10)

router = APIRouter(prefix="/api/pastor/leaders", tags=["leader-accounts"])

PASTOR_ROLES = {"pastor", "pastora", "admin", "superadmin"}


class LeaderDeleteInput(BaseModel):
    confirm_name: str = Field(min_length=1, max_length=200)
    reason: Optional[str] = Field(default=None, max_length=500)
    # A quién pasar su trabajo pendiente (obligatorio si tiene algo).
    reassign_to_person_id: Optional[str] = Field(default=None, max_length=80)


def _plain(value: Optional[str]) -> str:
    raw = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", raw).strip()


def require_pastoral(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Solo la autoridad pastoral puede eliminar cuentas de líderes")
    return current_user


async def load_target(user_id: str, current_user: dict) -> dict:
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=404, detail="Líder no encontrado")
    if user_id == current_user.get("user_id"):
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")
    target = await db.users.find_one({"_id": ObjectId(user_id), "account_deleted_at": {"$exists": False}})
    if not target:
        raise HTTPException(status_code=404, detail="Líder no encontrado")
    if is_global_pastoral_authority(target) or target.get("rol") in PASTOR_ROLES:
        raise HTTPException(status_code=403, detail="No se puede eliminar la cuenta de un pastor desde aquí")
    return target


async def _activity_in(campaign_id: str, person_id: str) -> bool:
    if await db.outreach_visits.find_one({"campaign_id": campaign_id, "mentor_person_id": person_id}, {"_id": 1}):
        return True
    household_ids = await db.outreach_households.distinct("household_id", {"campaign_id": campaign_id, "mentor_person_id": person_id})
    return bool(household_ids and await db.outreach_visit_events.find_one({"household_id": {"$in": household_ids}}, {"_id": 1}))


async def impact(target: dict, work: Optional[dict] = None) -> dict:
    from work_handover import pending_work, public
    user_id = str(target["_id"])
    person_id = target.get("person_id")
    work = work or await pending_work(person_id, [user_id])
    today = (await church_today()).isoformat()
    active_campaigns = await db.outreach_campaigns.find(
        {"assigned_mentor_ids": person_id, "end_date": {"$gte": today}}, {"_id": 0, "campaign_id": 1, "name": 1},
    ).to_list(200) if person_id else []
    return {
        "user_id": user_id, "name": target.get("nombre"), "email": target.get("email"), "rol": target.get("rol"),
        "person_id": person_id,
        "people_assigned": await db.people.count_documents({"leader_id": user_id}),
        "front_group_assignments": await db.front_group_assignments.count_documents({"person_id": person_id, "active": True}) if person_id else 0,
        "groups_led": await db.front_groups.count_documents({"status": {"$ne": "archived"}, "$or": [{"primary_leader_person_id": person_id}, {"co_leader_person_id": person_id}]}) if person_id else 0,
        "active_invasions": [item["name"] for item in active_campaigns],
        "mentor_badge_active": bool(person_id and await db.mentor_badges.find_one({"person_id": person_id, "active": True}, {"_id": 1})),
        "pending_work": public(work),
    }


@router.get("/{user_id}/delete-preview", response_model=dict)
async def delete_preview(user_id: str, current_user: dict = Depends(require_pastoral)):
    return await impact(await load_target(user_id, current_user))


@router.delete("/{user_id}", response_model=dict)
async def delete_leader(user_id: str, payload: LeaderDeleteInput, current_user: dict = Depends(require_pastoral)):
    target = await load_target(user_id, current_user)
    if _plain(payload.confirm_name) != _plain(target.get("nombre")):
        raise HTTPException(status_code=422, detail="Escribe el nombre del líder exactamente para confirmar")
    from work_handover import blocked, hand_over, pending_work, require_handover_target
    person_id = target.get("person_id")
    work = await pending_work(person_id, [user_id])
    summary = await impact(target, work)
    now = utc_now()
    actor = current_user["user_id"]
    today = (await church_today()).isoformat()
    result: dict = {}

    # Primero su trabajo pendiente pasa a otro mentor (nunca queda asignado a una cuenta eliminada).
    if work["blocking"]:
        if not payload.reassign_to_person_id:
            raise blocked(work, "eliminar la cuenta")
        new_owner = await require_handover_target(person_id, payload.reassign_to_person_id)
        reason = (payload.reason or "").strip() or "Cuenta del líder eliminada"
        result["handover"] = {**await hand_over(person_id, work, new_owner, current_user, reason), "to_person_id": new_owner["person_id"]}

    # Personas asignadas: quedan sin líder (no se borran) y visibles para reasignar.
    result["people_unassigned"] = (await db.people.update_many(
        {"leader_id": user_id}, {"$set": {"leader_id": None, "previous_leader_id": user_id, "leader_removed_at": now}},
    )).modified_count
    # La ficha 360 del líder se conserva; solo se desvincula de la cuenta.
    await db.persons.update_many({"auth_user_id": user_id}, {"$unset": {"auth_user_id": ""}, "$set": {"updated_at": now}})

    if person_id:
        result["front_group_assignments_ended"] = (await db.front_group_assignments.update_many(
            {"person_id": person_id, "active": True},
            {"$set": {"active": False, "ended_at": now, "ended_by_user_id": actor, "end_reason": "Cuenta del líder eliminada"}},
        )).modified_count
        for field in ("primary_leader_person_id", "co_leader_person_id"):
            await db.front_groups.update_many({field: person_id}, {"$set": {field: None, "updated_at": now, "leader_removed_at": now}})
        badge = await db.mentor_badges.find_one_and_update({"person_id": person_id, "active": True}, {"$set": {"active": False, "updated_at": now}})
        if badge:
            history_id = str(uuid4())
            await db.mentor_badge_history.insert_one({"_id": history_id, "history_id": history_id, "person_id": person_id, "action": "deactivated", "detail": {"reason": "Cuenta del líder eliminada"}, "actor_user_id": actor, "actor_person_id": current_user.get("person_id"), "occurred_at": now})
        removed, kept = [], []
        async for campaign in db.outreach_campaigns.find({"assigned_mentor_ids": person_id, "end_date": {"$gte": today}}, {"_id": 0, "campaign_id": 1}):
            campaign_id = campaign["campaign_id"]
            if await _activity_in(campaign_id, person_id):
                await db.outreach_participations.update_many({"campaign_id": campaign_id, "mentor_person_id": person_id}, {"$set": {"status": "inactive", "updated_at": now}})
                await db.invasion_participants.update_many({"campaign_id": campaign_id, "person_id": person_id}, {"$set": {"status": "declined", "updated_at": now}})
                kept.append(campaign_id)
            else:
                await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$pull": {"assigned_mentor_ids": person_id}, "$set": {"updated_at": now}})
                await db.outreach_participations.delete_many({"campaign_id": campaign_id, "mentor_person_id": person_id})
                await db.invasion_participants.delete_many({"campaign_id": campaign_id, "person_id": person_id})
                removed.append(campaign_id)
            # Sus casas sin visitas en esa invasión vuelven al grupo de disponibles.
            async for house in db.outreach_households.find({"campaign_id": campaign_id, "mentor_person_id": person_id, "archived": {"$ne": True}}, {"_id": 0, "household_id": 1}):
                if not await db.outreach_visit_events.find_one({"household_id": house["household_id"]}, {"_id": 1}):
                    await db.outreach_households.update_one({"household_id": house["household_id"]}, {"$set": {"mentor_person_id": None, "status": "available", "claimed_at": None, "updated_at": now}})
        result["invasions_removed"], result["invasions_kept_as_history"] = removed, kept

    await db.invite_codes.update_many(
        {"used_at": None, "$or": [{"created_by_user_id": user_id}, {"leader_id_to_assign": user_id}]}, {"$set": {"expires_at": now}},
    )
    await db.users.update_many({"parent_user_id": user_id}, {"$set": {"parent_user_id": actor}})
    await db.portal_notifications.delete_many({"recipient_user_id": user_id})
    # La cuenta no se borra: queda desactivada y marcada (sin acceso, fuera de las listas de líderes).
    await db.users.update_one({"_id": target["_id"]}, {"$set": {"is_active": False, "account_deleted_at": now, "account_deleted_by_user_id": actor,
                                                                  "updated_at": now}, "$inc": {"token_version": 1}})
    await db.admin_deletions.insert_one({
        "_id": str(uuid4()), "collection": "users", "target_id": user_id,
        "reason": (payload.reason or "").strip() or "Eliminación de cuenta de líder desde el Panel General",
        "detail": {**{key: value for key, value in summary.items() if key != "user_id"}, **result},
        "actor_user_id": actor, "actor_person_id": current_user.get("person_id"), "deleted_at": now,
    })
    return {"deleted": True, **summary, **result}
