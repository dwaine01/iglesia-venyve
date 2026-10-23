"""Supervisión de arriba hacia abajo (Etapa 4 / C9, A14-A16, E): UN SOLO
conjunto de endpoints de agregación que todos los paneles (Pastor,
Coordinador, Líder/Colíder, Mentor) leen igual — mismos registros, sin
reportes paralelos. Permisos: pastora/pastor general y coordinador general
ven todo; líder/colíder ven su rama (grupo + descendientes); el mentor ve lo
suyo. Todo con count_documents/distinct/aggregate — nunca un to_list masivo.
Recorrido: Iglesia -> grupo/líder -> mentor -> discípulo -> etapa -> actividad.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from access_control import is_general_coordinator, is_global_pastoral_authority
from front_group_tree import descendant_group_ids, support_group_ids
from library_module import compute_library_totals
from process_engine import get_definition, now_utc, serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/supervision", tags=["supervision"])

OUTREACH_PROCESS_KEY = "outreach_invasion"
CONSOLIDATION_KEY = "consolidation"
STARTED_STATUSES = ["in_progress", "completed"]
ACCEPTED_OR_LATER = ["accepted", "start_scheduled", "in_progress", "completed"]

DEFAULT_THRESHOLDS = {
    "mentor_inactivity_days": {"value": 7, "label": "Días sin registrar ninguna visita para marcar al mentor en rojo", "status": "propuesta"},
    "overdue_activity_ratio_red": {"value": 0.30, "label": "% de actividades vencidas sobre el total para marcar el grupo/mentor en rojo", "status": "propuesta"},
    "overdue_activity_ratio_yellow": {"value": 0.10, "label": "% de actividades vencidas sobre el total para marcar el grupo/mentor en amarillo", "status": "propuesta"},
    "accepted_not_started_days": {"value": 10, "label": "Días aceptado sin pasar a 'en proceso' para contarlo como debilidad", "status": "propuesta"},
    "stage_stall_days": {"value": 14, "label": "Días de retraso en una etapa abierta para considerarla detenida", "status": "propuesta"},
}


# ---------------------------------------------------------------------------
# Alcance (permisos) — igual criterio que mentorship_outreach/front_groups
# ---------------------------------------------------------------------------
async def resolve_scope(current_user: dict) -> dict:
    if is_global_pastoral_authority(current_user) or is_general_coordinator(current_user):
        return {"level": "global", "group_ids": None, "self_person_id": current_user.get("person_id")}
    branch_ids = await support_group_ids(db, current_user)
    if branch_ids:
        return {"level": "branch", "group_ids": sorted(branch_ids), "self_person_id": current_user.get("person_id")}
    return {"level": "self", "group_ids": None, "self_person_id": current_user.get("person_id")}


async def mentor_ids_in_scope(scope: dict) -> Optional[list]:
    """None = sin restricción (global). Lista = los únicos person_id permitidos."""
    if scope["level"] == "global":
        return None
    if scope["level"] == "branch":
        return await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": scope["group_ids"]}, "active": True})
    return [scope["self_person_id"]]


class Filters(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    campaign_id: Optional[str] = None
    front_group_id: Optional[str] = None
    mentor_person_id: Optional[str] = None
    stage_key: Optional[str] = None


async def build_filters(
    date_from: Optional[date] = Query(default=None), date_to: Optional[date] = Query(default=None),
    campaign_id: Optional[str] = Query(default=None), front_group_id: Optional[str] = Query(default=None),
    mentor_person_id: Optional[str] = Query(default=None), stage_key: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> dict:
    scope = await resolve_scope(current_user)
    filters = Filters(date_from=date_from, date_to=date_to, campaign_id=campaign_id, front_group_id=front_group_id, mentor_person_id=mentor_person_id, stage_key=stage_key)
    allowed_mentor_ids = await mentor_ids_in_scope(scope)
    if filters.front_group_id:
        if scope["level"] == "branch" and filters.front_group_id not in scope["group_ids"]:
            raise HTTPException(status_code=403, detail="Ese Grupo Frontal no está en su rama")
        group_member_ids = await db.front_group_assignments.distinct("person_id", {"front_group_id": filters.front_group_id, "active": True})
        allowed_mentor_ids = group_member_ids if allowed_mentor_ids is None else sorted(set(group_member_ids) & set(allowed_mentor_ids))
    if filters.mentor_person_id:
        if allowed_mentor_ids is not None and filters.mentor_person_id not in allowed_mentor_ids:
            raise HTTPException(status_code=403, detail="Ese mentor no está en su alcance de supervisión")
        allowed_mentor_ids = [filters.mentor_person_id]
    return {"scope": scope, "filters": filters, "mentor_ids": allowed_mentor_ids}


def mentor_query(ctx: dict, field: str = "mentor_person_id") -> dict:
    return {} if ctx["mentor_ids"] is None else {field: {"$in": ctx["mentor_ids"]}}


def date_query(ctx: dict, field: str) -> dict:
    filters: Filters = ctx["filters"]
    if not filters.date_from and not filters.date_to:
        return {}
    bounds: dict = {}
    if filters.date_from:
        bounds["$gte"] = datetime.combine(filters.date_from, datetime.min.time(), tzinfo=timezone.utc)
    if filters.date_to:
        bounds["$lte"] = datetime.combine(filters.date_to, datetime.max.time(), tzinfo=timezone.utc)
    return {field: bounds}


def campaign_query(ctx: dict) -> dict:
    return {"campaign_id": ctx["filters"].campaign_id} if ctx["filters"].campaign_id else {}


# ---------------------------------------------------------------------------
# Cómputo de métricas (Invasión: outreach_*; Consolidación: process_enrollments)
# ---------------------------------------------------------------------------
async def invasion_metrics(ctx: dict) -> dict:
    visit_query = {**mentor_query(ctx), **campaign_query(ctx), **date_query(ctx, "created_at")}
    household_query = {**mentor_query(ctx), **campaign_query(ctx)}
    households_visited = await db.outreach_households.count_documents(household_query)
    visits_total = await db.outreach_visits.count_documents(visit_query)
    household_ids = await db.outreach_households.distinct("household_id", household_query)
    attempts_total = await db.outreach_visit_events.count_documents({"household_id": {"$in": household_ids}}) if household_ids else 0
    unique_persons = await db.outreach_visits.aggregate([
        {"$match": visit_query},
        {"$group": {"_id": {"$ifNull": ["$converted_person_id", "$visit_id"]}}},
        {"$count": "total"},
    ]).to_list(1)
    interested = await db.outreach_visits.count_documents({**visit_query, "status": "wants_followup"})
    contacts_without_followup = await db.outreach_visits.count_documents({
        **visit_query, "status": {"$in": ["contacted", "pending", None]}, "$or": [{"note": None}, {"note": ""}],
    })
    participation_query = {**mentor_query(ctx), **campaign_query(ctx)}
    mentors_assigned = len(await db.outreach_participations.distinct("mentor_person_id", participation_query))
    mentors_confirmed = len(await db.outreach_participations.distinct("mentor_person_id", {**participation_query, "status": {"$in": ["confirmed", "active"]}}))
    mentors_with_activity = len(await db.outreach_participations.distinct("mentor_person_id", {**participation_query, "status": "active"}))
    return {
        "households_visited": households_visited, "visits_total": visits_total, "attempts_total": attempts_total,
        "unique_persons_contacted": (unique_persons[0]["total"] if unique_persons else 0),
        "interested": interested, "contacts_without_followup": contacts_without_followup,
        "mentors_assigned": mentors_assigned, "mentors_confirmed": mentors_confirmed, "mentors_with_activity": mentors_with_activity,
    }


async def consolidation_metrics(ctx: dict) -> dict:
    enrollment_query = {**mentor_query(ctx), "process_key": CONSOLIDATION_KEY, **date_query(ctx, "created_at")}
    if ctx["filters"].stage_key:
        enrollment_query["current_stage_key"] = ctx["filters"].stage_key
    accepted = await db.process_enrollments.count_documents({**enrollment_query, "decision_status": {"$in": ACCEPTED_OR_LATER}})
    start_scheduled = await db.process_enrollments.count_documents({**enrollment_query, "decision_status": "start_scheduled"})
    started = await db.process_enrollments.count_documents({**enrollment_query, "decision_status": {"$in": STARTED_STATUSES}})
    completed = await db.process_enrollments.count_documents({**enrollment_query, "decision_status": "completed"})
    by_stage_agg = await db.process_enrollments.aggregate([
        {"$match": enrollment_query}, {"$group": {"_id": "$current_stage_key", "total": {"$sum": 1}}},
    ]).to_list(200)
    stage_names = {}
    try:
        definition = await get_definition(db, CONSOLIDATION_KEY)
        stage_names = {stage["key"]: stage["name"] for stage in definition.get("stages", [])}
    except ValueError:
        pass
    by_stage = [{"stage_key": row["_id"], "stage_name": stage_names.get(row["_id"], row["_id"] or "Sin etapa"), "total": row["total"]} for row in by_stage_agg]
    paused_agg = await db.process_enrollments.aggregate([
        {"$match": {**enrollment_query, "decision_status": "paused"}},
        {"$group": {"_id": {"$ifNull": ["$decision_paused_reason", "Sin motivo registrado"]}, "total": {"$sum": 1}}},
    ]).to_list(200)
    paused_total = sum(row["total"] for row in paused_agg)
    enrollment_ids = await db.process_enrollments.distinct("enrollment_id", enrollment_query)
    activities_done = await db.consolidation_activities.count_documents({"enrollment_id": {"$in": enrollment_ids}, "status": "done"}) if enrollment_ids else 0
    today_iso = date.today().isoformat()
    activities_overdue = await db.consolidation_activities.count_documents({"enrollment_id": {"$in": enrollment_ids}, "status": "pending", "scheduled_date": {"$lt": today_iso}}) if enrollment_ids else 0
    activities_total = await db.consolidation_activities.count_documents({"enrollment_id": {"$in": enrollment_ids}}) if enrollment_ids else 0
    return {
        "accepted": accepted, "start_scheduled": start_scheduled, "started": started, "completed": completed,
        "by_stage": by_stage, "paused_total": paused_total, "paused_by_reason": [{"reason": row["_id"], "total": row["total"]} for row in paused_agg],
        "activities_done": activities_done, "activities_overdue": activities_overdue, "activities_total": activities_total,
        "enrollment_ids": enrollment_ids,
    }


async def mentor_custody_summary(ctx: dict) -> dict:
    """Resumen de Librería ESCOPADO (asignado/entregado/devuelto/en custodia
    de los mentores en alcance) — complementa (no reemplaza) el inventario
    global de `compute_library_totals`."""
    mentor_ids = ctx["mentor_ids"]
    if mentor_ids is None:
        return {"scoped": False}
    users = await db.users.find({"person_id": {"$in": mentor_ids}}, {"_id": 1}).to_list(len(mentor_ids)) if mentor_ids else []
    user_ids = [str(u["_id"]) for u in users]
    if not user_ids:
        return {"scoped": True, "assigned": 0, "delivered": 0, "returned": 0, "in_custody": 0}
    movements = await db.library_movements.aggregate([
        {"$match": {"$or": [{"from_holder.type": "user", "from_holder.id": {"$in": user_ids}}, {"to_holder.type": "user", "to_holder.id": {"$in": user_ids}}]}},
        {"$group": {"_id": "$movement_type", "total": {"$sum": "$quantity"}}},
    ]).to_list(20)
    totals = {row["_id"]: row["total"] for row in movements}
    in_custody_agg = await db.library_holdings.aggregate([
        {"$match": {"holder_type": "user", "holder_id": {"$in": user_ids}}},
        {"$group": {"_id": None, "total": {"$sum": "$quantity_on_hand"}}},
    ]).to_list(1)
    return {
        "scoped": True, "assigned": totals.get("ASSIGNMENT", 0), "delivered": totals.get("DELIVERY", 0),
        "returned": totals.get("RETURN", 0), "in_custody": (in_custody_agg[0]["total"] if in_custody_agg else 0),
    }


def compute_semaphore(activities_total: int, activities_overdue: int, thresholds: dict) -> str:
    ratio = (activities_overdue / activities_total) if activities_total else 0
    if ratio >= thresholds["overdue_activity_ratio_red"]["value"]:
        return "red"
    if ratio >= thresholds["overdue_activity_ratio_yellow"]["value"]:
        return "yellow"
    return "green"


async def load_thresholds() -> dict:
    doc = await db.supervision_thresholds.find_one({"_id": "default"}, {"_id": 0})
    return doc or DEFAULT_THRESHOLDS


async def person_names(person_ids: list) -> dict:
    from bson import ObjectId
    valid_oids = [ObjectId(pid) for pid in set(person_ids) if pid and ObjectId.is_valid(pid)]
    if not valid_oids:
        return {}
    people = await db.persons.find({"_id": {"$in": valid_oids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(valid_oids))
    return {str(p["_id"]): f"{p.get('nombre', '')} {p.get('apellido', '')}".strip() for p in people}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/scope", response_model=dict)
async def my_scope(current_user: dict = Depends(get_current_user)):
    scope = await resolve_scope(current_user)
    groups = []
    if scope["level"] == "global":
        groups = await db.front_groups.find({"parent_group_id": None, "status": {"$ne": "archived"}}, {"_id": 0, "front_group_id": 1, "name": 1}).sort("name", 1).to_list(500)
    elif scope["level"] == "branch":
        led = await db.front_group_assignments.distinct("front_group_id", {"person_id": current_user.get("person_id"), "role": {"$in": ["leader", "co_leader"]}, "active": True})
        groups = await db.front_groups.find({"front_group_id": {"$in": led}, "status": {"$ne": "archived"}}, {"_id": 0, "front_group_id": 1, "name": 1}).to_list(50)
    return {"level": scope["level"], "root_groups": serialize(groups)}


@router.get("/overview", response_model=dict)
async def overview(ctx: dict = Depends(build_filters)):
    invasion = await invasion_metrics(ctx)
    consolidation = await consolidation_metrics(ctx)
    library_totals = await compute_library_totals(db)
    custody = await mentor_custody_summary(ctx)
    thresholds = await load_thresholds()
    semaphore = compute_semaphore(consolidation["activities_total"], consolidation["activities_overdue"], thresholds)
    weaknesses = await weakness_summary(ctx, thresholds)
    return {
        "scope_level": ctx["scope"]["level"], "invasion": invasion, "consolidation": {k: v for k, v in consolidation.items() if k != "enrollment_ids"},
        "library": {"global": library_totals, "mentor_custody": custody}, "semaphore": semaphore, "weaknesses": weaknesses,
    }


async def weakness_summary(ctx: dict, thresholds: dict) -> dict:
    mentor_ids = ctx["mentor_ids"]
    if mentor_ids is None:
        mentor_candidates = await db.outreach_participations.distinct("mentor_person_id", campaign_query(ctx))
    else:
        mentor_candidates = mentor_ids
    cutoff_inactive = now_utc() - timedelta(days=thresholds["mentor_inactivity_days"]["value"])
    mentors_without_activity = 0
    if mentor_candidates:
        active_recent = await db.outreach_visits.distinct("mentor_person_id", {"mentor_person_id": {"$in": mentor_candidates}, "created_at": {"$gte": cutoff_inactive}})
        mentors_without_activity = len(set(mentor_candidates) - set(active_recent))
    cutoff_accepted = now_utc() - timedelta(days=thresholds["accepted_not_started_days"]["value"])
    accepted_not_started = await db.process_enrollments.count_documents({
        **mentor_query(ctx), "process_key": CONSOLIDATION_KEY, "decision_status": {"$in": ["accepted", "start_scheduled"]}, "created_at": {"$lte": cutoff_accepted},
    })
    stalled_cutoff = (now_utc() - timedelta(days=thresholds["stage_stall_days"]["value"]))
    enrollment_ids = await db.process_enrollments.distinct("enrollment_id", {**mentor_query(ctx), "process_key": CONSOLIDATION_KEY})
    delayed_disciples = await db.process_stage_progress.count_documents({"enrollment_id": {"$in": enrollment_ids}, "status": "open", "due_at": {"$lt": stalled_cutoff}}) if enrollment_ids else 0
    return {
        "mentors_without_activity": mentors_without_activity, "accepted_not_started": accepted_not_started,
        "delayed_disciples": delayed_disciples, "paused_total": await db.process_enrollments.count_documents({**mentor_query(ctx), "process_key": CONSOLIDATION_KEY, "decision_status": "paused"}),
    }


@router.get("/groups", response_model=dict)
async def drilldown_groups(parent_group_id: Optional[str] = Query(default=None), ctx: dict = Depends(build_filters)):
    scope = ctx["scope"]
    query: dict = {"status": {"$ne": "archived"}}
    if parent_group_id:
        if scope["level"] == "branch" and parent_group_id not in scope["group_ids"]:
            raise HTTPException(status_code=403, detail="Ese Grupo Frontal no está en su rama")
        query["parent_group_id"] = parent_group_id
    elif scope["level"] == "global":
        query["parent_group_id"] = None
    elif scope["level"] == "branch":
        query["front_group_id"] = {"$in": scope["group_ids"]}
        query["parent_group_id"] = None
    else:
        return {"groups": []}
    groups = await db.front_groups.find(query, {"_id": 0, "front_group_id": 1, "name": 1, "primary_leader_person_id": 1, "co_leader_person_id": 1}).sort("name", 1).to_list(500)
    thresholds = await load_thresholds()
    result = []
    for group in groups:
        branch_ids = await descendant_group_ids(db, group["front_group_id"])
        mentor_ids = await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": branch_ids}, "active": True})
        enrollment_ids = await db.process_enrollments.distinct("enrollment_id", {"mentor_person_id": {"$in": mentor_ids}, "process_key": CONSOLIDATION_KEY}) if mentor_ids else []
        today_iso = date.today().isoformat()
        overdue = await db.consolidation_activities.count_documents({"enrollment_id": {"$in": enrollment_ids}, "status": "pending", "scheduled_date": {"$lt": today_iso}}) if enrollment_ids else 0
        total_activities = await db.consolidation_activities.count_documents({"enrollment_id": {"$in": enrollment_ids}}) if enrollment_ids else 0
        result.append({
            **group, "direct_members": len(await db.front_group_assignments.distinct("person_id", {"front_group_id": group["front_group_id"], "active": True})),
            "total_members": len(mentor_ids), "activities_overdue": overdue, "activities_total": total_activities,
            "semaphore": compute_semaphore(total_activities, overdue, thresholds),
        })
    return {"groups": serialize(result)}


@router.get("/mentors", response_model=dict)
async def drilldown_mentors(ctx: dict = Depends(build_filters)):
    if ctx["mentor_ids"] is None:
        mentor_ids = await db.outreach_participations.distinct("mentor_person_id", campaign_query(ctx))
    else:
        mentor_ids = ctx["mentor_ids"]
    if not mentor_ids:
        return {"mentors": []}
    thresholds = await load_thresholds()
    names = await person_names(mentor_ids)
    cutoff_inactive = now_utc() - timedelta(days=thresholds["mentor_inactivity_days"]["value"])
    today_iso = date.today().isoformat()
    result = []
    for mentor_id in mentor_ids:
        visits = await db.outreach_visits.count_documents({"mentor_person_id": mentor_id, **campaign_query(ctx)})
        last_visit = await db.outreach_visits.find_one({"mentor_person_id": mentor_id}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])
        enrollment_ids = await db.process_enrollments.distinct("enrollment_id", {"mentor_person_id": mentor_id, "process_key": CONSOLIDATION_KEY})
        overdue = await db.consolidation_activities.count_documents({"enrollment_id": {"$in": enrollment_ids}, "status": "pending", "scheduled_date": {"$lt": today_iso}}) if enrollment_ids else 0
        total_activities = await db.consolidation_activities.count_documents({"enrollment_id": {"$in": enrollment_ids}}) if enrollment_ids else 0
        has_recent_activity = bool(last_visit and last_visit.get("created_at") and last_visit["created_at"] >= cutoff_inactive)
        result.append({
            "mentor_person_id": mentor_id, "mentor_name": names.get(mentor_id, "Mentor"), "visits": visits,
            "disciples": len(enrollment_ids), "activities_overdue": overdue, "activities_total": total_activities,
            "inactive": not has_recent_activity, "semaphore": "red" if not has_recent_activity and visits > 0 else compute_semaphore(total_activities, overdue, thresholds),
        })
    return {"mentors": serialize(result)}


@router.get("/disciples", response_model=dict)
async def drilldown_disciples(ctx: dict = Depends(build_filters), skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200)):
    query = {**mentor_query(ctx), "process_key": CONSOLIDATION_KEY}
    if ctx["filters"].stage_key:
        query["current_stage_key"] = ctx["filters"].stage_key
    total = await db.process_enrollments.count_documents(query)
    enrollments = await db.process_enrollments.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    people = await person_names([enrollment["person_id"] for enrollment in enrollments])
    items = [{**enrollment, "person_name": people.get(enrollment["person_id"], "Persona")} for enrollment in enrollments]
    return {"total": total, "items": serialize(items)}


INDICATOR_KEYS = {
    "activities_overdue", "mentors_without_activity", "contacts_without_followup", "accepted_not_started", "paused",
}


@router.get("/indicators/{indicator_key}", response_model=dict)
async def indicator_detail(indicator_key: str, ctx: dict = Depends(build_filters), skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200)):
    """Cada indicador abre el detalle que lo explica (p. ej. '12 actividades
    vencidas' lista esas 12 con su responsable)."""
    if indicator_key not in INDICATOR_KEYS:
        raise HTTPException(status_code=404, detail="Indicador desconocido")
    thresholds = await load_thresholds()
    if indicator_key == "activities_overdue":
        enrollment_ids = await db.process_enrollments.distinct("enrollment_id", {**mentor_query(ctx), "process_key": CONSOLIDATION_KEY})
        today_iso = date.today().isoformat()
        query = {"enrollment_id": {"$in": enrollment_ids}, "status": "pending", "scheduled_date": {"$lt": today_iso}}
        total = await db.consolidation_activities.count_documents(query) if enrollment_ids else 0
        rows = await db.consolidation_activities.find(query, {"_id": 0}).sort("scheduled_date", 1).skip(skip).limit(limit).to_list(limit) if enrollment_ids else []
        enrollment_by_id = {e["enrollment_id"]: e for e in await db.process_enrollments.find({"enrollment_id": {"$in": [r["enrollment_id"] for r in rows]}}, {"_id": 0, "enrollment_id": 1, "person_id": 1, "mentor_person_id": 1}).to_list(limit)}
        names = await person_names([e.get("person_id") for e in enrollment_by_id.values()])
        items = [{**row, "person_name": names.get(enrollment_by_id.get(row["enrollment_id"], {}).get("person_id"), "—"), "mentor_person_id": enrollment_by_id.get(row["enrollment_id"], {}).get("mentor_person_id")} for row in rows]
        return {"total": total, "items": serialize(items)}
    if indicator_key == "mentors_without_activity":
        mentor_ids = ctx["mentor_ids"] if ctx["mentor_ids"] is not None else await db.outreach_participations.distinct("mentor_person_id", {})
        cutoff = now_utc() - timedelta(days=thresholds["mentor_inactivity_days"]["value"])
        active_recent = set(await db.outreach_visits.distinct("mentor_person_id", {"mentor_person_id": {"$in": mentor_ids}, "created_at": {"$gte": cutoff}})) if mentor_ids else set()
        inactive_ids = [m for m in mentor_ids if m not in active_recent]
        names = await person_names(inactive_ids)
        items = [{"mentor_person_id": mid, "mentor_name": names.get(mid, "Mentor")} for mid in inactive_ids[skip:skip + limit]]
        return {"total": len(inactive_ids), "items": items}
    if indicator_key == "contacts_without_followup":
        query = {**mentor_query(ctx), **campaign_query(ctx), "status": {"$in": ["contacted", "pending", None]}, "$or": [{"note": None}, {"note": ""}]}
        total = await db.outreach_visits.count_documents(query)
        rows = await db.outreach_visits.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        return {"total": total, "items": serialize(rows)}
    if indicator_key == "accepted_not_started":
        cutoff = now_utc() - timedelta(days=thresholds["accepted_not_started_days"]["value"])
        query = {**mentor_query(ctx), "process_key": CONSOLIDATION_KEY, "decision_status": {"$in": ["accepted", "start_scheduled"]}, "created_at": {"$lte": cutoff}}
        total = await db.process_enrollments.count_documents(query)
        rows = await db.process_enrollments.find(query, {"_id": 0}).sort("created_at", 1).skip(skip).limit(limit).to_list(limit)
        return {"total": total, "items": serialize(rows)}
    if indicator_key == "paused":
        query = {**mentor_query(ctx), "process_key": CONSOLIDATION_KEY, "decision_status": "paused"}
        total = await db.process_enrollments.count_documents(query)
        rows = await db.process_enrollments.find(query, {"_id": 0}).sort("updated_at", -1).skip(skip).limit(limit).to_list(limit)
        return {"total": total, "items": serialize(rows)}
    return {"total": 0, "items": []}


def require_threshold_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if is_global_pastoral_authority(current_user) or is_general_coordinator(current_user):
        return current_user
    raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede editar los umbrales")


@router.get("/thresholds", response_model=dict)
async def get_thresholds(current_user: dict = Depends(get_current_user)):
    return await load_thresholds()


class ThresholdUpdate(BaseModel):
    value: float
    label: Optional[str] = None


@router.put("/thresholds/{key}", response_model=dict)
async def update_threshold(key: str, payload: ThresholdUpdate, current_user: dict = Depends(require_threshold_admin)):
    if key not in DEFAULT_THRESHOLDS:
        raise HTTPException(status_code=404, detail="Umbral desconocido")
    current = await load_thresholds()
    entry = {**current.get(key, DEFAULT_THRESHOLDS[key]), "value": payload.value, "status": "confirmado"}
    if payload.label:
        entry["label"] = payload.label
    await db.supervision_thresholds.update_one({"_id": "default"}, {"$set": {key: entry, "updated_at": now_utc(), "updated_by_user_id": current_user["user_id"]}}, upsert=True)
    return await load_thresholds()


async def ensure_supervision_indexes() -> None:
    await db.process_enrollments.create_index([("mentor_person_id", 1), ("process_key", 1)])
    await db.process_enrollments.create_index([("front_group_id", 1), ("process_key", 1)])
    await db.consolidation_activities.create_index([("enrollment_id", 1), ("status", 1)])
    await db.outreach_visits.create_index([("mentor_person_id", 1), ("created_at", -1)])
    if not await db.supervision_thresholds.find_one({"_id": "default"}):
        await db.supervision_thresholds.insert_one({"_id": "default", **DEFAULT_THRESHOLDS, "created_at": now_utc()})
