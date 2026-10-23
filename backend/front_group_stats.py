"""ETAPA 5C-3 — Estadísticas, semáforo y ranking de Grupos Frontales.

Mismos registros que Invasión/Consolidación/Supervisión (sin reportes
paralelos): `outreach_households`, `outreach_visit_events` (todos los
intentos, incluidos "sin respuesta"), `outreach_visits` (personas
alcanzadas), `process_enrollments` y `consolidation_activities`. Cada
métrica se calcula por persona (`mentor_person_id`) y se agrega por grupo y
por rama sumando personas DISTINTAS: quien es integrante de un grupo y líder
de otro cuenta una sola vez en la rama.

Semáforo con criterios visibles y configurables (umbrales de Supervisión):
participación (integrantes con actividad / integrantes) y actividades de
consolidación vencidas. Permisos iguales a la exploración por niveles."""
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from front_group_structure import assert_explorable, explorable_ids
from front_group_tree import descendant_group_ids
from front_groups import person_name
from server import db, get_current_user
from supervision_analytics import ACCEPTED_OR_LATER, CONSOLIDATION_KEY, compute_semaphore, load_thresholds

router = APIRouter(prefix="/api/front-group-structure", tags=["front-group-stats"])

ATTEMPT_RESULTS = ["contacted", "no_answer", "not_home", "refused"]
# Puntaje de avance (visible en pantalla): pesa más lo que más cuesta lograr.
SCORE_WEIGHTS = {"persons_reached": 3, "households": 2, "attempts": 1, "accepted": 5, "activities_done": 1}
SCORE_LABEL = "Avance = personas alcanzadas×3 + hogares×2 + intentos de visita×1 + aceptaron consolidación×5 + actividades realizadas×1"
SEVERITY = {"green": 0, "yellow": 1, "red": 2}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def resolve_period(period: str, campaign_id: Optional[str]) -> dict:
    now = now_utc()
    if period == "week":
        return {"key": "week", "label": "Últimos 7 días", "date_from": now - timedelta(days=7), "date_to": now, "campaign": None, "bucket": "day"}
    if period == "month":
        return {"key": "month", "label": "Últimos 30 días", "date_from": now - timedelta(days=30), "date_to": now, "campaign": None, "bucket": "day"}
    if period == "invasion":
        query = {"campaign_id": campaign_id} if campaign_id else {}
        campaign = await db.outreach_campaigns.find_one(query, {"_id": 0, "campaign_id": 1, "name": 1, "start_date": 1, "end_date": 1}, sort=[("start_date", -1)])
        if campaign_id and not campaign:
            raise HTTPException(status_code=404, detail="Invasión no encontrada")
        return {"key": "invasion", "label": f"Invasión: {campaign['name']}" if campaign else "Sin invasiones registradas", "date_from": None, "date_to": None, "campaign": campaign, "bucket": "day"}
    return {"key": "all", "label": "Todo el historial", "date_from": None, "date_to": None, "campaign": None, "bucket": "month"}


def period_match(period: dict, date_field: str) -> dict:
    match: dict = {}
    if period["key"] == "invasion":
        match["campaign_id"] = (period["campaign"] or {}).get("campaign_id", "__none__")
    if period["date_from"]:
        match[date_field] = {"$gte": period["date_from"], "$lte": period["date_to"]}
    return match


async def _count_by_mentor(collection: str, match: dict) -> dict:
    rows = await db[collection].aggregate([{"$match": match}, {"$group": {"_id": "$mentor_person_id", "total": {"$sum": 1}}}]).to_list(10000)
    return {row["_id"]: row["total"] for row in rows}


async def person_metrics(person_ids: list[str], period: dict) -> dict[str, dict]:
    """Métricas por persona en el período (una consulta agregada por fuente)."""
    if not person_ids:
        return {}
    mentors = {"mentor_person_id": {"$in": person_ids}}
    households = await _count_by_mentor("outreach_households", {**mentors, "archived": {"$ne": True}, **period_match(period, "created_at")})
    attempts_rows = await db.outreach_visit_events.aggregate([
        {"$match": {**mentors, **period_match(period, "occurred_at")}},
        {"$group": {"_id": {"mentor": "$mentor_person_id", "result": "$result"}, "total": {"$sum": 1}}},
    ]).to_list(10000)
    reached = await _count_by_mentor("outreach_visits", {**mentors, "archived": {"$ne": True}, **period_match(period, "created_at")})
    followups = await _count_by_mentor("outreach_visits", {**mentors, "archived": {"$ne": True}, "status": "wants_followup", **period_match(period, "created_at")})
    enrollment_match = {**mentors, "process_key": CONSOLIDATION_KEY}
    if period["date_from"]:
        enrollment_match["created_at"] = {"$gte": period["date_from"], "$lte": period["date_to"]}
    accepted = await _count_by_mentor("process_enrollments", {**enrollment_match, "decision_status": {"$in": ACCEPTED_OR_LATER}})
    enrollments = await db.process_enrollments.find({**mentors, "process_key": CONSOLIDATION_KEY}, {"_id": 0, "enrollment_id": 1, "mentor_person_id": 1}).to_list(20000)
    mentor_by_enrollment = {item["enrollment_id"]: item["mentor_person_id"] for item in enrollments}
    activities_done: dict[str, int] = {}
    activities_overdue: dict[str, int] = {}
    activities_total: dict[str, int] = {}
    if mentor_by_enrollment:
        done_match = {"enrollment_id": {"$in": list(mentor_by_enrollment)}, "status": "done"}
        if period["date_from"]:
            done_match["completed_at"] = {"$gte": period["date_from"], "$lte": period["date_to"]}
        today_iso = date.today().isoformat()
        for target, match in (
            (activities_done, done_match),
            (activities_overdue, {"enrollment_id": {"$in": list(mentor_by_enrollment)}, "status": "pending", "scheduled_date": {"$lt": today_iso}}),
            (activities_total, {"enrollment_id": {"$in": list(mentor_by_enrollment)}}),
        ):
            rows = await db.consolidation_activities.aggregate([{"$match": match}, {"$group": {"_id": "$enrollment_id", "total": {"$sum": 1}}}]).to_list(20000)
            for row in rows:
                mentor = mentor_by_enrollment.get(row["_id"])
                target[mentor] = target.get(mentor, 0) + row["total"]
    result = {}
    for person_id in person_ids:
        by_result = {key: 0 for key in ATTEMPT_RESULTS}
        for row in attempts_rows:
            if row["_id"]["mentor"] == person_id and row["_id"].get("result") in by_result:
                by_result[row["_id"]["result"]] += row["total"]
        metrics = {
            "households": households.get(person_id, 0), "attempts": sum(by_result.values()), "attempts_by_result": by_result,
            "persons_reached": reached.get(person_id, 0), "followups": followups.get(person_id, 0),
            "accepted": accepted.get(person_id, 0), "activities_done": activities_done.get(person_id, 0),
            "activities_overdue": activities_overdue.get(person_id, 0), "activities_total": activities_total.get(person_id, 0),
        }
        metrics["active"] = bool(metrics["households"] or metrics["attempts"] or metrics["persons_reached"] or metrics["activities_done"])
        metrics["score"] = sum(metrics[key] * weight for key, weight in SCORE_WEIGHTS.items())
        result[person_id] = metrics
    return result


def participation_semaphore(ratio: float, thresholds: dict) -> str:
    if ratio >= thresholds["participation_ratio_green"]["value"]:
        return "green"
    if ratio >= thresholds["participation_ratio_yellow"]["value"]:
        return "yellow"
    return "red"


def aggregate(person_ids: list[str], metrics: dict[str, dict], thresholds: dict) -> dict:
    """Suma sobre personas DISTINTAS + semáforo con sus motivos."""
    people = sorted(set(person_ids))
    keys = ["households", "attempts", "persons_reached", "followups", "accepted", "activities_done", "activities_overdue", "activities_total", "score"]
    totals = {key: sum(metrics.get(person_id, {}).get(key, 0) for person_id in people) for key in keys}
    totals["attempts_by_result"] = {result: sum(metrics.get(person_id, {}).get("attempts_by_result", {}).get(result, 0) for person_id in people) for result in ATTEMPT_RESULTS}
    participants = sum(1 for person_id in people if metrics.get(person_id, {}).get("active"))
    ratio = participants / len(people) if people else 0
    by_participation = participation_semaphore(ratio, thresholds)
    by_overdue = compute_semaphore(totals["activities_total"], totals["activities_overdue"], thresholds)
    semaphore = max((by_participation, by_overdue), key=lambda value: SEVERITY[value])
    return {
        **totals, "people": len(people), "participants": participants, "participation_ratio": round(ratio, 3),
        "semaphore": semaphore,
        "semaphore_reasons": {"participation": by_participation, "overdue": by_overdue},
    }


def member_semaphore(metrics: dict, thresholds: dict) -> str:
    if not metrics["active"]:
        return "red"
    return compute_semaphore(metrics["activities_total"], metrics["activities_overdue"], thresholds)


async def group_people(group_id: str, branch: bool) -> list[str]:
    group_ids = await descendant_group_ids(db, group_id) if branch else [group_id]
    return await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": group_ids}, "active": True})


async def ranking(person_ids: list[str], metrics: dict, thresholds: dict, roles: dict[str, str]) -> list[dict]:
    rows = []
    for person_id in sorted(set(person_ids)):
        item = metrics.get(person_id) or {}
        rows.append({
            "person_id": person_id, "name": await person_name(person_id) or "Persona", "role": roles.get(person_id, "member"),
            **{key: item.get(key, 0) for key in ("score", "persons_reached", "households", "attempts", "accepted", "activities_done", "activities_overdue")},
            "active": item.get("active", False), "semaphore": member_semaphore(item, thresholds) if item else "red",
        })
    rows.sort(key=lambda row: (-row["score"], -row["persons_reached"], row["name"]))
    best = rows[0]["score"] if rows else 0
    for position, row in enumerate(rows, start=1):
        row["rank"] = position
        row["highlight"] = "top" if best > 0 and row["score"] == best else ("needs_support" if row["semaphore"] == "red" else None)
    return rows


async def timeline(person_ids: list[str], period: dict) -> list[dict]:
    """Avance en el período: intentos de visita y personas alcanzadas por día
    (o por mes en 'todo el historial')."""
    if not person_ids:
        return []
    fmt = "%Y-%m" if period["bucket"] == "month" else "%Y-%m-%d"
    series: dict[str, dict] = {}
    for collection, date_field, key, extra in (
        ("outreach_visit_events", "occurred_at", "attempts", {}),
        ("outreach_visits", "created_at", "persons_reached", {"archived": {"$ne": True}}),
    ):
        match = {"mentor_person_id": {"$in": person_ids}, **extra, **period_match(period, date_field)}
        rows = await db[collection].aggregate([
            {"$match": match},
            {"$group": {"_id": {"$dateToString": {"format": fmt, "date": f"${date_field}"}}, "total": {"$sum": 1}}},
        ]).to_list(1000)
        for row in rows:
            if row["_id"]:
                series.setdefault(row["_id"], {"bucket": row["_id"], "attempts": 0, "persons_reached": 0})[key] = row["total"]
    return [series[bucket] for bucket in sorted(series)][-60:]


@router.get("/groups/{group_id}/stats", response_model=dict)
async def group_stats(
    group_id: str,
    period: Literal["week", "month", "invasion", "all"] = Query("month"),
    campaign_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Estadísticas del grupo y de su rama: totales, semáforo, comparación
    entre los grupos de sus líderes, ranking de integrantes y avance."""
    await assert_explorable(group_id, current_user)
    resolved = await resolve_period(period, campaign_id)
    thresholds = await load_thresholds()
    branch_people = await group_people(group_id, branch=True)
    metrics = await person_metrics(branch_people, resolved)
    direct_assignments = await db.front_group_assignments.find({"front_group_id": group_id, "active": True}, {"_id": 0, "person_id": 1, "role": 1}).to_list(5000)
    direct_roles: dict[str, str] = {}
    for item in direct_assignments:
        if item["person_id"] not in direct_roles or item["role"] in {"leader", "co_leader"}:
            direct_roles[item["person_id"]] = item["role"]
    branch_leaders = set(await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": await descendant_group_ids(db, group_id)}, "active": True, "role": {"$in": ["leader", "co_leader"]}}))
    children = await db.front_groups.find({"parent_group_id": group_id, "status": {"$ne": "archived"}}, {"_id": 0}).sort("name", 1).to_list(500)
    comparison = []
    for child in children:
        child_people = await group_people(child["front_group_id"], branch=True)
        comparison.append({
            "front_group_id": child["front_group_id"], "name": child.get("name") or "Grupo sin nombre", "status": child.get("status"),
            "leader_name": await person_name(child.get("primary_leader_person_id")),
            "co_leader_name": await person_name(child.get("co_leader_person_id")),
            **aggregate(child_people, metrics, thresholds),
        })
    return {
        "period": {"key": resolved["key"], "label": resolved["label"], "campaign": resolved["campaign"],
                   "date_from": resolved["date_from"].isoformat() if resolved["date_from"] else None,
                   "date_to": resolved["date_to"].isoformat() if resolved["date_to"] else None},
        "criteria": {
            "score": SCORE_LABEL,
            "participation": {key: thresholds[key] for key in ("participation_ratio_green", "participation_ratio_yellow")},
            "overdue": {key: thresholds[key] for key in ("overdue_activity_ratio_yellow", "overdue_activity_ratio_red")},
            "member": "Rojo: sin actividad en el período (necesita apoyo). Con actividad: según % de actividades vencidas.",
        },
        "group": aggregate(list(direct_roles), metrics, thresholds),
        "branch": {**aggregate(branch_people, metrics, thresholds), "leaders": len(branch_leaders)},
        "children": comparison,
        "ranking_group": await ranking(list(direct_roles), metrics, thresholds, direct_roles),
        "ranking_branch": await ranking(branch_people, metrics, thresholds, {person_id: "leader" for person_id in branch_leaders}),
        "timeline": await timeline(branch_people, resolved),
    }


@router.get("/campaigns", response_model=dict)
async def campaigns_for_selector(current_user: dict = Depends(get_current_user)):
    """Invasiones disponibles para el selector de período."""
    if await explorable_ids(current_user) == set():
        raise HTTPException(status_code=403, detail="Sin grupos frontales para consultar")
    rows = await db.outreach_campaigns.find({}, {"_id": 0, "campaign_id": 1, "name": 1, "start_date": 1}).sort("start_date", -1).to_list(100)
    return {"items": rows}
