"""ETAPA 5C — Grupo Frontal principal de la pastora.

Reutiliza `front_groups` y `front_group_assignments` (no crea colecciones ni
duplica personas): el grupo principal es un Grupo Frontal raíz marcado con
`pastoral_main`, liderado por la pastora. Su lista (individuos y parejas) y
la asignación de líderes usan los mismos endpoints genéricos de cualquier
grupo (`/api/front-groups/{id}/roster` y `/leader-privilege`).

Solo la autoridad pastoral y el coordinador general ven el conjunto completo;
solo la autoridad pastoral lo crea o renombra. Pertenecer no da permisos."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import is_general_coordinator, is_global_pastoral_authority
from front_groups import (
    CoLeaderAssignment, FrontGroupCreate, assign_co_leader, audit, create_front_group,
    load_person, now_utc, person_name, roster_view,
)
from self_portal import person_activity
from server import db, get_current_user

router = APIRouter(prefix="/api/pastoral-front-group", tags=["pastoral-front-group"])


def require_viewer(current_user: dict = Depends(get_current_user)) -> dict:
    if is_global_pastoral_authority(current_user) or is_general_coordinator(current_user):
        return current_user
    raise HTTPException(status_code=403, detail="Solo la pastora, el pastor o el coordinador general ven este grupo")


def require_owner(current_user: dict = Depends(get_current_user)) -> dict:
    if is_global_pastoral_authority(current_user):
        return current_user
    raise HTTPException(status_code=403, detail="Solo la autoridad pastoral administra su grupo frontal principal")


class PastoralGroupSave(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    co_leader_person_id: Optional[str] = None


async def main_group() -> Optional[dict]:
    return await db.front_groups.find_one({"pastoral_main": True, "status": {"$ne": "archived"}}, {"_id": 0})


async def require_main_group() -> dict:
    group = await main_group()
    if not group:
        raise HTTPException(status_code=404, detail="El grupo frontal principal aún no ha sido creado")
    return group


async def person_card(person_id: Optional[str]) -> Optional[dict]:
    if not person_id:
        return None
    has_account = bool(await db.users.find_one({"person_id": person_id, "is_active": {"$ne": False}}, {"_id": 1}))
    return {"person_id": person_id, "name": await person_name(person_id), "has_account": has_account, "profile_path": f"/personas/{person_id}"}


async def group_view(group: Optional[dict], current_user: dict) -> dict:
    if not group:
        return {"group": None, "roster": None, "can_edit": is_global_pastoral_authority(current_user)}
    return {
        "group": {
            "front_group_id": group["front_group_id"], "name": group.get("name"), "status": group.get("status"),
            "leader": await person_card(group.get("primary_leader_person_id")),
            "co_leader": await person_card(group.get("co_leader_person_id")),
        },
        "roster": await roster_view(group),
        "can_edit": is_global_pastoral_authority(current_user),
    }


@router.get("", response_model=dict)
async def get_pastoral_group(current_user: dict = Depends(require_viewer)):
    return await group_view(await main_group(), current_user)


@router.put("", response_model=dict)
async def save_pastoral_group(payload: PastoralGroupSave, current_user: dict = Depends(require_owner)):
    """Crea (o adopta, si la pastora ya lidera un grupo raíz) su grupo
    frontal principal y fija su nombre y colíder. Nunca crea un segundo."""
    if payload.co_leader_person_id:
        if payload.co_leader_person_id == current_user.get("person_id"):
            raise HTTPException(status_code=422, detail="El líder y el colíder deben ser personas distintas")
        await load_person(payload.co_leader_person_id)
    group = await main_group()
    if not group:
        adopt = await db.front_groups.find_one(
            {"parent_group_id": None, "primary_leader_person_id": current_user.get("person_id"), "status": {"$ne": "archived"}},
            {"_id": 0}, sort=[("created_at", 1)],
        ) if current_user.get("person_id") else None
        if adopt:
            group_id = adopt["front_group_id"]
        else:
            created = await create_front_group(FrontGroupCreate(name=payload.name, primary_leader_person_id=current_user.get("person_id"), leadership_reason="Grupo frontal principal de la pastora"), current_user)
            group_id = created["front_group_id"]
        await db.front_groups.update_one({"front_group_id": group_id}, {"$set": {"pastoral_main": True}})
        await audit(group_id, current_user, "pastoral_main_marked", {"adopted": bool(adopt)})
        group = await main_group()
    group_id = group["front_group_id"]
    if payload.name != group.get("name"):
        await db.front_groups.update_one({"front_group_id": group_id}, {"$set": {"name": payload.name, "updated_at": now_utc(), "updated_by_user_id": current_user["user_id"]}})
    if payload.co_leader_person_id and payload.co_leader_person_id != group.get("co_leader_person_id"):
        await db.front_group_assignments.update_many({"front_group_id": group_id, "person_id": payload.co_leader_person_id, "role": "member", "active": True}, {"$set": {"active": False, "ended_at": now_utc(), "end_reason": "Pasa a colíder del grupo"}})
        await assign_co_leader(group_id, CoLeaderAssignment(person_id=payload.co_leader_person_id, reason="Colíder del grupo frontal principal"), current_user)
    return await group_view(await main_group(), current_user)


@router.get("/members/{person_id}/activity", response_model=dict)
async def member_activity(person_id: str, current_user: dict = Depends(require_viewer)):
    """Actividad de un integrante como persona, líder y mentor."""
    group = await require_main_group()
    if not await db.front_group_assignments.find_one({"front_group_id": group["front_group_id"], "person_id": person_id, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Esta persona no pertenece al grupo frontal principal")
    processes = await db.process_enrollments.find(
        {"person_id": person_id}, {"_id": 0, "process_key": 1, "status": 1, "current_stage_name": 1}
    ).to_list(50)
    led_groups = await db.front_group_assignments.count_documents({"person_id": person_id, "role": {"$in": ["leader", "co_leader"]}, "active": True})
    return {
        "person": await person_card(person_id),
        "as_person": {"processes": processes, "led_group_count": led_groups},
        **await person_activity(person_id),
    }
