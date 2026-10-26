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
import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from front_group_structure import assert_explorable, explorable_ids
from front_group_tree import descendant_group_ids, load_group
from front_groups import person_name, person_names, roster_view
from self_portal import person_activity
from participation_scope import participants_only, principal_authority_person_ids, without
from server import db, get_current_user
from count_rules import church_today  # «hoy» en la zona de la iglesia (auditoría 7/10)
from access_control import is_general_coordinator, is_global_pastoral_authority
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


async def campaigns_in_period(period: dict, day_from: Optional[str], day_to: Optional[str]) -> Optional[list[str]]:
    """Invasiones del período (None = todas, en 'Todo el historial')."""
    if period["key"] == "invasion":
        return [period["campaign"]["campaign_id"]] if period.get("campaign") else []
    if not day_from:
        return None
    return await db.outreach_campaigns.distinct("campaign_id", {"start_date": {"$lte": day_to}, "end_date": {"$gte": day_from}})


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
    enrollment_match = {**mentors, "process_key": CONSOLIDATION_KEY}
    if period["date_from"]:
        enrollment_match["created_at"] = {"$gte": period["date_from"], "$lte": period["date_to"]}
    # Asistencia (Persona 360: person_attendance, incluye check-ins de Operaciones
    # y células) y apoyo (turnos de servicio confirmados o con check-in). No
    # dependen de una invasión: en 'por invasión' se usan sus fechas.
    day_from, day_to = period_days(period)
    attendance_match = {"person_id": {"$in": person_ids}, "estado": "presente"}
    if day_from:
        # `fecha` es texto ISO ('YYYY-MM-DD' o con hora): el orden de texto sirve.
        next_day = (date.fromisoformat(day_to[:10]) + timedelta(days=1)).isoformat()
        attendance_match["fecha"] = {"$gte": day_from, "$lt": next_day}
    support_match = {"person_id": {"$in": person_ids}, "status": {"$in": ["confirmed", "checked_in"]}}
    if day_from:
        support_match["assigned_at"] = {"$gte": datetime.fromisoformat(day_from[:10]).replace(tzinfo=timezone.utc), "$lt": datetime.fromisoformat(next_day).replace(tzinfo=timezone.utc)}
    # ¿Existe algún registro (aunque sea 'ausente', 'invitado' o una invasión
    # asignada sin actividad)? Distingue "sin datos" de un 0 real.
    any_attendance_match = {key: value for key, value in attendance_match.items() if key != "estado"}
    any_support_match = {key: value for key, value in support_match.items() if key != "status"}

    async def count_by_person(collection: str, match: dict) -> dict:
        rows = await db[collection].aggregate([{"$match": match}, {"$group": {"_id": "$person_id", "total": {"$sum": 1}}}]).to_list(10000)
        return {row["_id"]: row["total"] for row in rows}

    async def assigned_outreach_ids() -> set:
        campaign_ids = await campaigns_in_period(period, day_from, day_to)
        participation_query = {**mentors, **({"campaign_id": {"$in": campaign_ids}} if campaign_ids is not None else {})}
        return set(await db.outreach_participations.distinct("mentor_person_id", participation_query)) if campaign_ids is None or campaign_ids else set()

    (households, attempts_rows, reached, followups, accepted, enrollments,
     attendance, support, attendance_records, support_records, assigned_outreach) = await asyncio.gather(
        _count_by_mentor("outreach_households", {**mentors, "archived": {"$ne": True}, **period_match(period, "created_at")}),
        db.outreach_visit_events.aggregate([
            {"$match": {**mentors, **period_match(period, "occurred_at")}},
            {"$group": {"_id": {"mentor": "$mentor_person_id", "result": "$result"}, "total": {"$sum": 1}}},
        ]).to_list(10000),
        _count_by_mentor("outreach_visits", {**mentors, "archived": {"$ne": True}, **period_match(period, "created_at")}),
        _count_by_mentor("outreach_visits", {**mentors, "archived": {"$ne": True}, "status": "wants_followup", **period_match(period, "created_at")}),
        _count_by_mentor("process_enrollments", {**enrollment_match, "decision_status": {"$in": ACCEPTED_OR_LATER}}),
        db.process_enrollments.find({**mentors, "process_key": CONSOLIDATION_KEY}, {"_id": 0, "enrollment_id": 1, "mentor_person_id": 1}).to_list(20000),
        count_by_person("person_attendance", attendance_match),
        count_by_person("operation_volunteer_assignments", support_match),
        count_by_person("person_attendance", any_attendance_match),
        count_by_person("operation_volunteer_assignments", any_support_match),
        assigned_outreach_ids(),
    )
    mentor_by_enrollment = {item["enrollment_id"]: item["mentor_person_id"] for item in enrollments}
    activities_done: dict[str, int] = {}
    activities_overdue: dict[str, int] = {}
    activities_total: dict[str, int] = {}
    if mentor_by_enrollment:
        done_match = {"enrollment_id": {"$in": list(mentor_by_enrollment)}, "status": "done"}
        if period["date_from"]:
            done_match["completed_at"] = {"$gte": period["date_from"], "$lte": period["date_to"]}
        today_iso = (await church_today()).isoformat()
        targets = (
            (activities_done, done_match),
            (activities_overdue, {"enrollment_id": {"$in": list(mentor_by_enrollment)}, "status": "pending", "scheduled_date": {"$lt": today_iso}}),
            (activities_total, {"enrollment_id": {"$in": list(mentor_by_enrollment)}}),
        )
        all_rows = await asyncio.gather(*(db.consolidation_activities.aggregate([{"$match": match}, {"$group": {"_id": "$enrollment_id", "total": {"$sum": 1}}}]).to_list(20000) for _, match in targets))
        for (target, _), rows in zip(targets, all_rows):
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
            "attendance": attendance.get(person_id, 0), "support_shifts": support.get(person_id, 0),
            "attendance_records": attendance_records.get(person_id, 0), "support_records": support_records.get(person_id, 0),
        }
        metrics["outreach_active"] = bool(metrics["households"] or metrics["attempts"] or metrics["persons_reached"])
        metrics["outreach_data"] = metrics["outreach_active"] or person_id in assigned_outreach
        metrics["activity_active"] = bool(metrics["support_shifts"] or metrics["activities_done"])
        metrics["activity_data"] = bool(metrics["support_records"] or metrics["activities_total"])
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
    """Participantes del grupo/rama (sin la autoridad pastoral principal)."""
    group_ids = await descendant_group_ids(db, group_id) if branch else [group_id]
    return await participants_only(db, await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": group_ids}, "active": True}))


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
    authorities = await principal_authority_person_ids(db)
    direct_assignments = [item for item in await db.front_group_assignments.find({"front_group_id": group_id, "active": True}, {"_id": 0, "person_id": 1, "role": 1}).to_list(5000) if item["person_id"] not in authorities]
    direct_roles: dict[str, str] = {}
    for item in direct_assignments:
        if item["person_id"] not in direct_roles or item["role"] in {"leader", "co_leader"}:
            direct_roles[item["person_id"]] = item["role"]
    branch_leaders = set(without(await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": await descendant_group_ids(db, group_id)}, "active": True, "role": {"$in": ["leader", "co_leader"]}}), authorities))
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
# Metas: valor real frente a la meta configurable, por período
# ---------------------------------------------------------------------------
def period_weeks(period: dict) -> Optional[float]:
    """Semanas que abarca el período para escalar metas semanales
    (por invasión cuenta como una unidad; 'Todo' no tiene meta)."""
    if period["key"] == "week": return 1.0
    if period["key"] == "month": return round(30 / 7, 2)
    if period["key"] == "invasion": return 1.0
    return None


def goal_indicators(person_ids: list[str], metrics: dict, thresholds: dict, period: dict) -> dict:
    """Cuatro indicadores con valor real, meta, período y la fórmula usada.
    Sin registros en el período → has_data False (se muestra 'sin datos')."""
    people = sorted(set(person_ids))
    total = len(people)
    rows = [metrics.get(person_id, {}) for person_id in people]

    def ratio_indicator(key, label, goal_key, active_key, data_key, numerator_label):
        numerator = sum(1 for row in rows if row.get(active_key))
        has_data = any(row.get(data_key) for row in rows)
        value = numerator / total if total else 0
        goal = thresholds[goal_key]
        return {
            "key": key, "label": label, "unit": "ratio", "has_data": has_data and total > 0,
            "value": round(value, 3), "goal": goal["value"], "goal_status": goal.get("status", "propuesta"), "goal_key": goal_key,
            "numerator": numerator, "denominator": total,
            "explanation": f"{numerator} de {total} integrantes {numerator_label} ÷ meta {round(goal['value'] * 100)}%.",
        }

    indicators = [
        ratio_indicator("attendance", "Asistencia", "goal_attendance_ratio", "attendance", "attendance_records", "con al menos una asistencia 'presente' registrada"),
        ratio_indicator("activities", "Participación en actividades", "goal_activity_ratio", "activity_active", "activity_data", "con un turno de servicio confirmado o una actividad de consolidación realizada"),
        ratio_indicator("outreach", "Impacto en invasiones", "goal_outreach_ratio", "outreach_active", "outreach_data", "con hogares, intentos de visita o personas alcanzadas"),
    ]
    weeks = period_weeks(period)
    reached = sum(row.get("persons_reached", 0) for row in rows)
    per_week = thresholds["goal_persons_reached_per_member_week"]
    goal_value = round(per_week["value"] * weeks, 2) if weeks else None
    indicators.append({
        "key": "persons_reached", "label": "Personas alcanzadas por integrante", "unit": "per_member",
        "has_data": any(row.get("outreach_data") for row in rows) and total > 0,
        "value": round(reached / total, 2) if total else 0, "goal": goal_value, "goal_status": per_week.get("status", "propuesta"),
        "goal_key": "goal_persons_reached_per_member_week", "numerator": reached, "denominator": total,
        "explanation": (f"{reached} personas alcanzadas ÷ {total} integrantes; meta {per_week['value']} por integrante por semana × {weeks} = {goal_value}." if weeks
                        else f"{reached} personas alcanzadas ÷ {total} integrantes. En 'Todo el historial' no hay meta."),
    })
    for item in indicators:
        item["progress"] = round(min(item["value"] / item["goal"], 1), 3) if item["has_data"] and item["goal"] else None
    measured = [item["progress"] for item in indicators if item["progress"] is not None]
    overall = round(sum(measured) / len(measured), 3) if measured else None
    if overall is None:
        level = None
    elif overall >= thresholds["goal_progress_green"]["value"]:
        level = "A"
    elif overall >= thresholds["goal_progress_yellow"]["value"]:
        level = "B"
    else:
        level = "C"
    return {"indicators": indicators, "overall_progress": overall, "class": level}


# ---------------------------------------------------------------------------
# Panel dinámico de "Mi Grupo Frontal": equipos (de dos integrantes o individuos) en tarjetas
# ---------------------------------------------------------------------------
UNAVAILABLE_DATA = [
    {"key": "group_meetings", "label": "Asistencia a reuniones del Grupo Frontal", "reason": "Aún no existe un registro de reuniones propias del Grupo Frontal. La asistencia que se muestra es la registrada en Persona 360 (cultos, células y eventos de Operaciones)."},
    {"key": "brought_to_church", "label": "Personas llevadas o invitadas a la iglesia", "reason": "En 'Llegada y origen' el dato 'invitado por' es texto libre y no está vinculado a una Persona 360, así que no se puede atribuir a un integrante."},
]


GOAL_KEYS = ("goal_attendance_ratio", "goal_activity_ratio", "goal_outreach_ratio", "goal_persons_reached_per_member_week", "goal_progress_green", "goal_progress_yellow")


def panel_criteria(thresholds: dict) -> dict:
    return {
        "classes": {
            "A": "Avance hacia las metas ≥ umbral A.",
            "B": "Avance hacia las metas ≥ umbral B y menor que el de A.",
            "C": "Avance hacia las metas menor que el umbral B.",
            "—": "Sin datos: ningún registro de asistencia, actividades ni invasiones en el período.",
        },
        "goals": {key: thresholds[key] for key in GOAL_KEYS},
        "overall_formula": "Avance hacia las metas = promedio de los indicadores con datos, cada uno = valor real ÷ meta (máximo 100%). Un indicador sin registros no entra en el promedio y se muestra como 'sin datos', nunca como 0%.",
        "score": SCORE_LABEL,
        "rank": "Puesto: orden por avance hacia las metas y, en empate, por puntaje de avance.",
        "attendance": "Asistencia: registros 'presente' de Persona 360 en el período (cultos, células, check-in de eventos). Hay datos si existe algún registro de asistencia (aunque sea 'ausente').",
        "activities": "Participación en actividades: turnos de servicio de Operaciones confirmados o con check-in, o actividades de consolidación realizadas en el período. Hay datos si existe algún turno asignado o alguna actividad programada.",
        "outreach": "Impacto en invasiones: hogares, intentos de visita (incluidos 'sin respuesta') o personas alcanzadas en el período. Hay datos si el integrante fue asignado a una invasión del período o registró actividad.",
        "invasion_dates": "En 'Por invasión', asistencia y apoyo usan las fechas de inicio y fin de esa invasión; la meta de personas alcanzadas es por invasión.",
        "member": "Cada persona se cuenta una sola vez aunque esté en dos equipos o grupos.",
        "editable": "Las metas y umbrales son configurables por la pastora/pastor o el coordinador general. 'propuesta' = valor inicial aún no confirmado.",
    }


async def member_cards(group_id: str, person_ids: list[str], metrics: dict, thresholds: dict, roles: dict[str, str], period: dict) -> list[dict]:
    mentors = set(await db.mentor_badges.distinct("person_id", {"person_id": {"$in": person_ids}, "active": True}))
    names = await person_names(person_ids)
    led_by_person: dict[str, dict] = {}
    async for child in db.front_groups.find(
        {"parent_group_id": group_id, "status": {"$ne": "archived"}, "$or": [{"primary_leader_person_id": {"$in": person_ids}}, {"co_leader_person_id": {"$in": person_ids}}]},
        {"_id": 0, "front_group_id": 1, "name": 1, "status": 1, "primary_leader_person_id": 1, "co_leader_person_id": 1},
    ):
        for person_id in (child.get("primary_leader_person_id"), child.get("co_leader_person_id")):
            if person_id in person_ids: led_by_person.setdefault(person_id, child)
    cards = []
    for person_id in person_ids:
        led = led_by_person.get(person_id)
        functions = []
        if roles.get(person_id) == "leader": functions.append("Líder del grupo")
        if roles.get(person_id) == "co_leader": functions.append("Colíder del grupo")
        if led: functions.append("Líder de su grupo" if led.get("primary_leader_person_id") == person_id else "Colíder de su grupo")
        if person_id in mentors: functions.append("Mentor")
        item = metrics.get(person_id) or {}
        cards.append({
            "person_id": person_id, "name": names.get(person_id) or "Persona", "functions": functions,
            "led_group": {key: led.get(key) for key in ("front_group_id", "name", "status")} if led else None,
            "metrics": {key: item.get(key, 0) for key in ("score", "persons_reached", "households", "attempts", "followups", "accepted", "activities_done", "activities_overdue", "attendance", "support_shifts")},
            "attempts_by_result": item.get("attempts_by_result", {}), "active": item.get("active", False),
            "semaphore": member_semaphore(item, thresholds) if item else "red",
            "goals": goal_indicators([person_id], metrics, thresholds, period),
        })
    return cards


@router.get("/groups/{group_id}/panel", response_model=dict)
async def group_panel(
    group_id: str,
    period: Literal["week", "month", "invasion", "all"] = Query("month"),
    campaign_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Panel de actividad del grupo: un recuadro por equipo (de dos integrantes o
    individuo según la lista registrada, más el liderazgo del grupo)."""
    group = await assert_explorable(group_id, current_user)
    resolved, thresholds, roster, authorities = await asyncio.gather(
        resolve_period(period, campaign_id), load_thresholds(), roster_view(group),
        # La autoridad pastoral principal supervisa: no aparece en equipos, conteos ni rankings.
        principal_authority_person_ids(db),
    )
    roles = {person_id: role for role, person_id in (("leader", group.get("primary_leader_person_id")), ("co_leader", group.get("co_leader_person_id"))) if person_id}
    team_defs = []
    leadership_ids = without(list(roles), authorities)
    if leadership_ids:
        team_defs.append({"team_id": "leadership", "type": "leadership", "person_ids": leadership_ids})
    for entry in roster["entries"]:
        ids = without([person["person_id"] for person in entry["people"]], authorities)
        if ids:
            team_defs.append({"team_id": entry.get("pair_id") or ids[0], "type": entry["type"] if len(ids) > 1 else "individual", "person_ids": ids})
    everyone = sorted({person_id for team in team_defs for person_id in team["person_ids"]})
    metrics = await person_metrics(everyone, resolved)
    team_members = await asyncio.gather(*(member_cards(group_id, team["person_ids"], metrics, thresholds, roles, resolved) for team in team_defs))
    teams = []
    for team, members in zip(team_defs, team_members):
        summary = aggregate(team["person_ids"], metrics, thresholds)
        goals = goal_indicators(team["person_ids"], metrics, thresholds, resolved)
        teams.append({
            "team_id": team["team_id"], "type": team["type"],
            "members": members,
            "summary": {**summary, "class": goals["class"], "overall_progress": goals["overall_progress"]},
            "goals": goals["indicators"],
        })
    best = max((team["summary"]["score"] for team in teams), default=0)
    for team in teams:
        team["summary"]["relative_pct"] = round(team["summary"]["score"] / best * 100) if best else 0
    ordered = sorted(teams, key=lambda item: (-(item["summary"]["overall_progress"] if item["summary"]["overall_progress"] is not None else -1), -item["summary"]["score"]))
    for position, team in enumerate(ordered, start=1):
        team["summary"]["rank"] = position
    totals = aggregate(everyone, metrics, thresholds)
    group_goals = goal_indicators(everyone, metrics, thresholds, resolved)
    return {
        "period": {"key": resolved["key"], "label": resolved["label"], "campaign": resolved["campaign"],
                   "date_from": resolved["date_from"].isoformat() if resolved["date_from"] else None,
                   "date_to": resolved["date_to"].isoformat() if resolved["date_to"] else None},
        "criteria": panel_criteria(thresholds),
        "unavailable": UNAVAILABLE_DATA,
        "group": {"front_group_id": group_id, "name": group.get("name"), **totals, "class": group_goals["class"], "overall_progress": group_goals["overall_progress"], "goals": group_goals["indicators"], "teams": len(teams)},
        "can_edit_goals": is_global_pastoral_authority(current_user) or is_general_coordinator(current_user),
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
