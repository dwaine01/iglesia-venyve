"""Rotación semanal y vínculo configurable Célula ↔ Grupo Frontal."""
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from access_control import (
    CONSOLIDATION_ASSIGN, FRONT_GROUP_ROTATION_MANAGE,
    has_capability, is_global_pastoral_authority,
)
from front_group_tree import descendant_group_ids, group_in_scope, load_group
from process_engine import serialize
from server import db, get_current_user


router = APIRouter(prefix="/api/front-group-routing", tags=["front-group-routing"])


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class RotationPolicyInput(BaseModel):
    root_group_id: str
    ordered_group_ids: list[str] = Field(min_length=1, max_length=500)
    timezone_name: str = Field(default="America/Santo_Domingo", min_length=3, max_length=100)
    week_start_day: int = Field(default=6, ge=0, le=6)
    active: bool = True


class CellGroupLinkInput(BaseModel):
    front_group_id: str
    route_conversions: bool = False
    reason: str = Field(min_length=3, max_length=1000)


def require_consolidation(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, CONSOLIDATION_ASSIGN):
        raise HTTPException(status_code=403, detail="Asignación reservada a Consolidación")
    return current_user


def require_rotation_manager(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, FRONT_GROUP_ROTATION_MANAGE):
        raise HTTPException(status_code=403, detail="Configuración de rotación restringida")
    return current_user


async def validate_cell(cell_id: str) -> dict:
    cell = await db.cells.find_one({"cell_id": cell_id, "status": {"$ne": "closed"}}, {"_id": 0})
    if not cell:
        raise HTTPException(status_code=404, detail="Célula de origen no encontrada")
    return cell


async def active_cell_link(cell_id: str) -> dict | None:
    return await db.cell_front_group_links.find_one({"cell_id": cell_id, "active": True}, {"_id": 0})


def week_bounds(policy: dict, moment: datetime | None = None) -> tuple[datetime, datetime, str]:
    try:
        zone = ZoneInfo(policy["timezone_name"])
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Zona horaria inválida") from exc
    local = (moment or now_utc()).astimezone(zone)
    days_back = (local.weekday() - policy["week_start_day"]) % 7
    start_date = local.date() - timedelta(days=days_back)
    local_start = datetime.combine(start_date, time.min, tzinfo=zone)
    local_end = local_start + timedelta(days=7)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc), start_date.isoformat()


async def materialize_current_week(policy: dict) -> dict:
    start, end, week_key = week_bounds(policy)
    existing = await db.front_group_rotation_weeks.find_one({"policy_id": policy["policy_id"], "week_key": week_key}, {"_id": 0})
    if existing:
        return existing
    eligible = await db.front_groups.find({
        "front_group_id": {"$in": policy["ordered_group_ids"]},
        "status": "active", "routing_enabled": {"$ne": False},
    }, {"_id": 0, "front_group_id": 1}).to_list(1000)
    eligible_ids = {item["front_group_id"] for item in eligible}
    ordered = [item for item in policy["ordered_group_ids"] if item in eligible_ids]
    if not ordered:
        raise HTTPException(status_code=409, detail="La rotación no tiene Grupos activos elegibles")
    anchor = policy.get("anchor_week_start") or start
    if isinstance(anchor, str):
        anchor = datetime.fromisoformat(anchor.replace("Z", "+00:00"))
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    elapsed_weeks = max(0, int((start - anchor).total_seconds() // (7 * 86400)))
    selected_group_id = ordered[elapsed_weeks % len(ordered)]
    rotation_week_id = str(uuid4()); now = now_utc()
    document = {
        "_id": rotation_week_id, "rotation_week_id": rotation_week_id,
        "policy_id": policy["policy_id"], "root_group_id": policy["root_group_id"],
        "week_key": week_key, "week_start": start, "week_end": end,
        "selected_group_id": selected_group_id, "eligible_group_ids_snapshot": ordered,
        "algorithm": "round_robin_v1", "status": "active", "created_at": now,
    }
    try:
        await db.front_group_rotation_weeks.insert_one(document)
    except DuplicateKeyError:
        return await db.front_group_rotation_weeks.find_one({"policy_id": policy["policy_id"], "week_key": week_key}, {"_id": 0})
    return serialize(document)


async def current_rotation(policy_id: str | None = None) -> dict | None:
    query = {"active": True}
    if policy_id:
        query["policy_id"] = policy_id
    policies = await db.front_group_rotation_policies.find(query, {"_id": 0}).sort("created_at", 1).to_list(2)
    if not policies:
        return None
    if len(policies) > 1 and not policy_id:
        return None
    policy = policies[0]
    return {"policy": serialize(policy), "week": serialize(await materialize_current_week(policy))}


async def routing_recommendation(source_cell_id: str | None, policy_id: str | None = None) -> dict:
    if source_cell_id:
        await validate_cell(source_cell_id)
        link = await active_cell_link(source_cell_id)
        if link and link.get("route_conversions") is True:
            await load_group(db, link["front_group_id"])
            return {"recommended_group_id": link["front_group_id"], "mode": "cell_policy", "cell_link_id": link["link_id"], "rotation_week_id": None}
    rotation = await current_rotation(policy_id)
    if rotation:
        return {"recommended_group_id": rotation["week"]["selected_group_id"], "mode": "weekly_rotation", "cell_link_id": None, "rotation_week_id": rotation["week"]["rotation_week_id"]}
    return {"recommended_group_id": None, "mode": "unassigned", "cell_link_id": None, "rotation_week_id": None}


async def confirm_routing(
    *, requested_group_id: str | None, source_cell_id: str | None, policy_id: str | None,
    reason: str | None, current_user: dict,
) -> dict:
    recommendation = await routing_recommendation(source_cell_id, policy_id)
    chosen = requested_group_id
    if chosen:
        await load_group(db, chosen)
        has_global_assignment = is_global_pastoral_authority(current_user) or has_capability(current_user, CONSOLIDATION_ASSIGN)
        if not has_global_assignment and not await group_in_scope(db, chosen, current_user, leader_required=True):
            raise HTTPException(status_code=403, detail="Grupo Frontal fuera de su rama")
        if recommendation["recommended_group_id"] and recommendation["recommended_group_id"] != chosen and not reason:
            raise HTTPException(status_code=422, detail="Indique el motivo para modificar la asignación recomendada")
    return {
        **recommendation,
        "assigned_group_id": chosen,
        "confirmed": bool(chosen),
        "manual_override": bool(chosen and recommendation["recommended_group_id"] and chosen != recommendation["recommended_group_id"]),
        "reason": reason,
    }


@router.get("/overview", response_model=dict)
async def routing_overview(policy_id: Optional[str] = None, current_user: dict = Depends(require_consolidation)):
    rotation = await current_rotation(policy_id)
    groups = await db.front_groups.find({"status": "active", "routing_enabled": {"$ne": False}}, {"_id": 0, "front_group_id": 1, "name": 1, "parent_group_id": 1, "root_group_id": 1, "depth": 1, "rotation_order": 1}).sort([("depth", 1), ("rotation_order", 1), ("name", 1)]).to_list(10000)
    return {"rotation": rotation, "available_groups": serialize(groups)}


@router.put("/policies/{policy_id}", response_model=dict)
async def save_policy(policy_id: str, payload: RotationPolicyInput, current_user: dict = Depends(require_rotation_manager)):
    root = await load_group(db, payload.root_group_id)
    allowed_ids = set(await descendant_group_ids(db, root["front_group_id"]))
    if not set(payload.ordered_group_ids).issubset(allowed_ids):
        raise HTTPException(status_code=409, detail="Todos los Grupos de rotación deben pertenecer al árbol seleccionado")
    if len(set(payload.ordered_group_ids)) != len(payload.ordered_group_ids):
        raise HTTPException(status_code=422, detail="La rotación no admite Grupos duplicados")
    try:
        ZoneInfo(payload.timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Zona horaria inválida") from exc
    now = now_utc(); existing = await db.front_group_rotation_policies.find_one({"policy_id": policy_id}, {"_id": 0})
    fields = {**payload.model_dump(), "policy_id": policy_id, "updated_at": now, "updated_by_user_id": current_user["user_id"]}
    if not existing:
        start, _, _ = week_bounds(fields, now)
        fields.update({"created_at": now, "created_by_user_id": current_user["user_id"], "anchor_week_start": start})
    await db.front_group_rotation_policies.update_one({"policy_id": policy_id}, {"$set": fields, "$setOnInsert": {"_id": policy_id}}, upsert=True)
    await db.front_group_routing_events.insert_one({"_id": str(uuid4()), "event_id": str(uuid4()), "action": "rotation_policy_saved", "policy_id": policy_id, "actor_user_id": current_user["user_id"], "occurred_at": now})
    return serialize(await db.front_group_rotation_policies.find_one({"policy_id": policy_id}, {"_id": 0}))


@router.put("/cell-links/{cell_id}", response_model=dict)
async def save_cell_link(cell_id: str, payload: CellGroupLinkInput, current_user: dict = Depends(require_rotation_manager)):
    await validate_cell(cell_id); await load_group(db, payload.front_group_id)
    now = now_utc()
    previous = await db.cell_front_group_links.find_one({"cell_id": cell_id, "active": True}, {"_id": 0})
    if previous:
        await db.cell_front_group_links.update_one({"link_id": previous["link_id"]}, {"$set": {"active": False, "ended_at": now, "ended_by_user_id": current_user["user_id"], "end_reason": payload.reason}})
    link_id = str(uuid4())
    document = {"_id": link_id, "link_id": link_id, "cell_id": cell_id, **payload.model_dump(), "active": True, "started_at": now, "created_at": now, "created_by_user_id": current_user["user_id"]}
    await db.cell_front_group_links.insert_one(document)
    await db.front_group_routing_events.insert_one({"_id": str(uuid4()), "event_id": str(uuid4()), "action": "cell_group_link_saved", "cell_id": cell_id, "front_group_id": payload.front_group_id, "route_conversions": payload.route_conversions, "reason": payload.reason, "actor_user_id": current_user["user_id"], "occurred_at": now})
    return serialize(document)


@router.get("/cell-links/{cell_id}", response_model=dict)
async def get_cell_link(cell_id: str, current_user: dict = Depends(require_consolidation)):
    await validate_cell(cell_id)
    history = await db.cell_front_group_links.find({"cell_id": cell_id}, {"_id": 0}).sort("started_at", -1).to_list(100)
    return {"items": serialize(history), "total": len(history)}


async def ensure_front_group_routing_indexes() -> None:
    await db.front_group_rotation_policies.create_index("policy_id", unique=True)
    await db.front_group_rotation_weeks.create_index([("policy_id", 1), ("week_key", 1)], unique=True)
    await db.front_group_rotation_weeks.create_index([("selected_group_id", 1), ("week_start", -1)])
    await db.cell_front_group_links.create_index("link_id", unique=True)
    await db.cell_front_group_links.create_index("cell_id", unique=True, partialFilterExpression={"active": True}, name="one_active_front_group_link_per_cell")
    await db.front_group_routing_events.create_index("event_id", unique=True)
    await db.front_group_routing_events.create_index([("occurred_at", -1), ("action", 1)])