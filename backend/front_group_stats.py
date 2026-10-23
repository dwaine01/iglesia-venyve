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
from front_group_tree import descendant_group_ids, load_group
from front_groups import person_name, roster_view
from self_portal import person_activity
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


def period_days(period: dict) -> tuple[Optional[str], Optional[str]]:
    """Rango en fechas ISO (YYYY-MM-DD) para registros sin invasión."""
    if period["date_from"]:
        return period["date_from"].date().isoformat(), period["date_to"].date().isoformat()
    campaign = period.get("campaign") or {}
    if period["key"] == "invasion" and campaign.get("start_date"):
        return campaign["start_date"], campaign.get("end_date") or campaign["start_date"]
    return None, None


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
    # Asistencia (Persona 360: person_attendance, incluye check-ins de Operaciones
    # y células) y apoyo (turnos de servicio confirmados o con check-in). No
    # dependen de una invasión: en 'por invasión' se usan sus fechas.
    day_from, day_to = period_days(period)
    attendance_match = {"person_id": {"$in": person_ids}, "estado": "presente"}
    if day_from:
        # `fecha` es texto ISO ('YYYY-MM-DD' o con hora): el orden de texto sirve.
        next_day = (date.fromisoformat(day_to[:10]) + timedelta(days=1)).isoformat()
        attendance_match["fecha"] = {"$gte": day_from, "$lt": next_day}
    attendance_rows = await db.person_attendance.aggregate([{"$match": attendance_match}, {"$group": {"_id": "$person_id", "total": {"$sum": 1}}}]).to_list(10000)
    attendance = {row["_id"]: row["total"] for row in attendance_rows}
    support_match = {"person_id": {"$in": person_ids}, "status": {"$in": ["confirmed", "checked_in"]}}
    if day_from:
        support_match["assigned_at"] = {"$gte": datetime.fromisoformat(day_from[:10]).replace(tzinfo=timezone.utc), "$lt": datetime.fromisoformat(next_day).replace(tzinfo=timezone.utc)}
    support_rows = await db.operation_volunteer_assignments.aggregate([{"$match": support_match}, {"$group": {"_id": "$person_id", "total": {"$sum": 1}}}]).to_list(10000)
    support = {row["_id"]: row["total"] for row in support_rows}
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
            "attendance": attendance.get(person_id, 0), "support_shifts": support.get(person_id, 0),
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
    keys = ["households", "attempts", "persons_reached", "followups", "accepted", "activities_done", "activities_overdue", "activities_total", "attendance", "support_shifts", "score"]
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


# ---------------------------------------------------------------------------
# Panel dinámico de "Mi Grupo Frontal": equipos (parejas/individuos) en tarjetas
# ---------------------------------------------------------------------------
CLASS_BY_SEMAPHORE = {"green": "A", "yellow": "B", "red": "C"}
UNAVAILABLE_DATA = [
    {"key": "group_meetings", "label": "Asistencia a reuniones del Grupo Frontal", "reason": "Aún no existe un registro de reuniones propias del Grupo Frontal. La asistencia que se muestra es la registrada en Persona 360 (cultos, células y eventos de Operaciones)."},
    {"key": "brought_to_church", "label": "Personas llevadas o invitadas a la iglesia", "reason": "En 'Llegada y origen' el dato 'invitado por' es texto libre y no está vinculado a una Persona 360, así que no se puede atribuir a un integrante."},
]


def panel_criteria(thresholds: dict) -> dict:
    return {
        "classes": {
            "A": "Verde del semáforo: participación ≥ umbral verde y actividades vencidas por debajo del umbral amarillo.",
            "B": "Amarillo: participación ≥ umbral amarillo, o actividades vencidas entre los umbrales amarillo y rojo.",
            "C": "Rojo: participación por debajo del umbral amarillo, o actividades vencidas ≥ umbral rojo.",
        },
        "participation": {key: thresholds[key] for key in ("participation_ratio_green", "participation_ratio_yellow")},
        "overdue": {key: thresholds[key] for key in ("overdue_activity_ratio_yellow", "overdue_activity_ratio_red")},
        "score": SCORE_LABEL,
        "participation_formula": "Participación = integrantes del equipo con al menos un registro en el período (hogar, intento de visita, persona alcanzada o actividad de consolidación realizada) ÷ integrantes del equipo.",
        "progress_formula": "% de avance = avance del equipo ÷ avance del equipo con más avance del mismo grupo × 100.",
        "attendance": "Asistencias: registros 'presente' de Persona 360 en el período (cultos, células, check-in de eventos).",
        "support": "Apoyo: turnos de servicio de Operaciones confirmados o con check-in, asignados en el período.",
        "invasion_dates": "En 'Por invasión', asistencia y apoyo usan las fechas de inicio y fin de esa invasión.",
        "member": "Cada persona se cuenta una sola vez aunque esté en dos equipos o grupos.",
    }


async def member_cards(group_id: str, person_ids: list[str], metrics: dict, thresholds: dict, roles: dict[str, str]) -> list[dict]:
    mentors = set(await db.mentor_badges.distinct("person_id", {"person_id": {"$in": person_ids}, "active": True}))
    cards = []
    for person_id in person_ids:
        led = await db.front_groups.find_one(
            {"parent_group_id": group_id, "status": {"$ne": "archived"}, "$or": [{"primary_leader_person_id": person_id}, {"co_leader_person_id": person_id}]},
            {"_id": 0, "front_group_id": 1, "name": 1, "status": 1, "primary_leader_person_id": 1},
        )
        functions = []
        if roles.get(person_id) == "leader": functions.append("Líder del grupo")
        if roles.get(person_id) == "co_leader": functions.append("Colíder del grupo")
        if led: functions.append("Líder de su grupo" if led.get("primary_leader_person_id") == person_id else "Colíder de su grupo")
        if person_id in mentors: functions.append("Mentor")
        item = metrics.get(person_id) or {}
        cards.append({
            "person_id": person_id, "name": await person_name(person_id) or "Persona", "functions": functions,
            "led_group": {key: led.get(key) for key in ("front_group_id", "name", "status")} if led else None,
            "metrics": {key: item.get(key, 0) for key in ("score", "persons_reached", "households", "attempts", "followups", "accepted", "activities_done", "activities_overdue", "attendance", "support_shifts")},
            "attempts_by_result": item.get("attempts_by_result", {}), "active": item.get("active", False),
            "semaphore": member_semaphore(item, thresholds) if item else "red",
        })
    return cards


@router.get("/groups/{group_id}/panel", response_model=dict)
async def group_panel(
    group_id: str,
    period: Literal["week", "month", "invasion", "all"] = Query("month"),
    campaign_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Panel de actividad del grupo: un recuadro por equipo (pareja o
    individuo según la lista registrada, más el liderazgo del grupo)."""
    await assert_explorable(group_id, current_user)
    group = await load_group(db, group_id)
    resolved = await resolve_period(period, campaign_id)
    thresholds = await load_thresholds()
    roster = await roster_view(group)
    roles = {person_id: role for role, person_id in (("leader", group.get("primary_leader_person_id")), ("co_leader", group.get("co_leader_person_id"))) if person_id}
    team_defs = []
    if roles:
        team_defs.append({"team_id": "leadership", "type": "leadership", "person_ids": list(roles)})
    for entry in roster["entries"]:
        ids = [person["person_id"] for person in entry["people"]]
        team_defs.append({"team_id": entry.get("pair_id") or ids[0], "type": entry["type"], "person_ids": ids})
    everyone = sorted({person_id for team in team_defs for person_id in team["person_ids"]})
    metrics = await person_metrics(everyone, resolved)
    teams = []
    for team in team_defs:
        summary = aggregate(team["person_ids"], metrics, thresholds)
        teams.append({
            "team_id": team["team_id"], "type": team["type"],
            "members": await member_cards(group_id, team["person_ids"], metrics, thresholds, roles),
            "summary": {**summary, "class": CLASS_BY_SEMAPHORE[summary["semaphore"]]},
        })
    best = max((team["summary"]["score"] for team in teams), default=0)
    for team in teams:
        team["summary"]["progress_pct"] = round(team["summary"]["score"] / best * 100) if best else 0
    for position, team in enumerate(sorted(teams, key=lambda item: -item["summary"]["score"]), start=1):
        team["summary"]["rank"] = position
    totals = aggregate(everyone, metrics, thresholds)
    return {
        "period": {"key": resolved["key"], "label": resolved["label"], "campaign": resolved["campaign"],
                   "date_from": resolved["date_from"].isoformat() if resolved["date_from"] else None,
                   "date_to": resolved["date_to"].isoformat() if resolved["date_to"] else None},
        "criteria": panel_criteria(thresholds),
        "unavailable": UNAVAILABLE_DATA,
        "group": {"front_group_id": group_id, "name": group.get("name"), **totals, "class": CLASS_BY_SEMAPHORE[totals["semaphore"]], "teams": len(teams)},
        "teams": teams,
    }


@router.get("/people/{person_id}/activity", response_model=dict)
async def person_activity_view(
    person_id: str,
    period: Literal["week", "month", "invasion", "all"] = Query("month"),
    campaign_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Actividad individual de un integrante (como persona, líder y mentor),
    solo si pertenece a una rama que quien consulta puede explorar."""
    allowed = await explorable_ids(current_user)
    if allowed is not None and not await db.front_group_assignments.find_one({"person_id": person_id, "active": True, "front_group_id": {"$in": list(allowed)}}, {"_id": 1}):
        raise HTTPException(status_code=403, detail="Esta persona no está en su rama")
    resolved = await resolve_period(period, campaign_id)
    thresholds = await load_thresholds()
    metrics = (await person_metrics([person_id], resolved)).get(person_id, {})
    processes = await db.process_enrollments.find({"person_id": person_id}, {"_id": 0, "process_key": 1, "status": 1, "current_stage_name": 1}).to_list(50)
    groups = await db.front_group_assignments.find({"person_id": person_id, "active": True}, {"_id": 0, "front_group_id": 1, "role": 1}).to_list(50)
    group_names = {item["front_group_id"]: item.get("name") for item in await db.front_groups.find({"front_group_id": {"$in": [g["front_group_id"] for g in groups]}, "status": {"$ne": "archived"}}, {"_id": 0, "front_group_id": 1, "name": 1}).to_list(50)}
    return {
        "person": {"person_id": person_id, "name": await person_name(person_id), "profile_path": f"/personas/{person_id}"},
        "period": {"key": resolved["key"], "label": resolved["label"]},
        "in_period": {**metrics, "semaphore": member_semaphore(metrics, thresholds) if metrics else "red"},
        "as_person": {"processes": processes, "groups": [{"front_group_id": g["front_group_id"], "name": group_names[g["front_group_id"]], "role": g["role"]} for g in groups if g["front_group_id"] in group_names]},
        "is_mentor": bool(await db.mentor_badges.find_one({"person_id": person_id, "active": True}, {"_id": 1})),
        **await person_activity(person_id),
    }
