"""C2 · Panorama de Consolidación: «cómo anda Consolidación» en una sola vista.

Alcance (backend):
- completo: autoridad pastoral, coordinador general y encargados de
  Consolidación (capacidad `consolidation.assign`);
- un mentor activo ve solo sus personas;
- cualquier otra cuenta recibe 403 (también por URL).

Definiciones aprobadas por el dueño:
- «Nuevas en el periodo» = expedientes creados en ese periodo.
- «Sin atender» = expediente activo con más de 48 h sin ninguna actividad
  realizada (consolidation_activities status=done).
- «Sin próxima acción» = expediente activo sin `next_action_at`.
Cuenta PERSONAS ÚNICAS (un expediente por persona; los repetidos son
historial) y nunca los archivados.
Lee lo que ya existe (process_enrollments v2, consolidation_activities,
mentor_assignments, person_memberships); no crea colecciones."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from access_control import CONSOLIDATION_ASSIGN, has_capability, is_general_coordinator, is_global_pastoral_authority
from participation_scope import principal_authority_person_ids
from server import db, get_current_user

router = APIRouter(prefix="/api/consolidation/panorama", tags=["consolidation-panorama"])

UNATTENDED_HOURS = 48
STAGES = ["visitor_followup", "prayer", "invasion", "mcd", "npt", "welcome_party", "lbs_1", "lbs_2", "lbs_3", "retreat", "discipleship_handoff"]
STAGE_LABELS = {"visitor_followup": "Nuevo y seguimiento", "prayer": "Oración", "invasion": "Invasión", "mcd": "MCD", "npt": "Nací Para Triunfar",
                "welcome_party": "Fiesta de Bienvenida", "lbs_1": "LBS 1", "lbs_2": "LBS 2", "lbs_3": "LBS 3", "retreat": "Retiro", "discipleship_handoff": "Educación / Discipulado"}
PERIOD_DAYS = {"week": 7, "month": 30, "quarter": 90}
METRICS = ("total", "new", "unattended", "no_next_action", "transfers", "first_contact", "memberships")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def aware(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


async def panorama_scope(current_user: dict) -> dict:
    if is_global_pastoral_authority(current_user) or is_general_coordinator(current_user) or has_capability(current_user, CONSOLIDATION_ASSIGN):
        return {"level": "all"}
    from mentorship_outreach import is_active_mentor
    person_id = current_user.get("person_id")
    if person_id and await is_active_mentor(person_id):
        return {"level": "mine", "mentor_person_id": person_id}
    raise HTTPException(status_code=403, detail="Sin acceso al panorama de Consolidación")


def stage_index(item: dict) -> int:
    if item.get("status") == "completed":
        return len(STAGES) - 1
    try:
        return STAGES.index(item.get("current_stage_key"))
    except ValueError:
        return 0


async def load_population(current_user: dict, campaign_id: Optional[str], mentor_person_id: Optional[str], front_group_id: Optional[str], stage_key: Optional[str]) -> tuple[dict, list[dict], dict]:
    scope = await panorama_scope(current_user)
    query: dict = {"process_key": "consolidation", "definition_version": 2, "status": {"$ne": "archived"}}
    if scope["level"] == "mine":
        query["mentor_person_id"] = scope["mentor_person_id"]
    elif mentor_person_id:
        query["mentor_person_id"] = mentor_person_id
    if campaign_id:
        query["campaign_id"] = campaign_id
    if front_group_id:
        query["front_group_id"] = front_group_id
    if stage_key:
        query["current_stage_key"] = stage_key
    items = await db.process_enrollments.find(query, {"_id": 0}).to_list(20000)
    # PERSONAS ÚNICAS: un expediente por persona (el activo, o el más avanzado/reciente);
    # los demás de la misma persona son historial y no inflan las cifras.
    from enrollment_cleanup import representatives
    items, _ = representatives(items)
    ids = [item["enrollment_id"] for item in items]
    # Primera actividad realizada y la más reciente, por expediente (una consulta agregada).
    activity: dict = {}
    if ids:
        async for row in db.consolidation_activities.aggregate([
            {"$match": {"enrollment_id": {"$in": ids}, "status": "done"}},
            {"$group": {"_id": "$enrollment_id", "first": {"$min": "$completed_at"}, "last": {"$max": "$completed_at"}, "done": {"$sum": 1}}},
        ]):
            activity[row["_id"]] = row
    return scope, items, activity


def is_unattended(item: dict, activity: dict, now: datetime) -> bool:
    created = aware(item.get("created_at"))
    return item.get("status") == "active" and not activity.get(item["enrollment_id"]) and bool(created) and (now - created) > timedelta(hours=UNATTENDED_HOURS)


def period_start(period: str, now: datetime, campaign: Optional[dict]) -> tuple[Optional[datetime], Optional[datetime]]:
    """(inicio, inicio del periodo anterior) del periodo pedido."""
    if period == "invasion" and campaign and campaign.get("start_date"):
        start = aware(f"{campaign['start_date']}T00:00:00")
        length = timedelta(days=max(7, ((aware(f"{campaign.get('end_date') or campaign['start_date']}T23:59:59") - start).days + 1)))
        return start, start - length
    days = PERIOD_DAYS.get(period)
    if not days:
        return None, None
    return now - timedelta(days=days), now - timedelta(days=2 * days)


@router.get("", response_model=dict)
async def panorama(period: Literal["week", "month", "quarter", "invasion", "all"] = "month", campaign_id: Optional[str] = None,
                   mentor_person_id: Optional[str] = None, front_group_id: Optional[str] = None, stage_key: Optional[str] = None,
                   current_user: dict = Depends(get_current_user)):
    scope, items, activity = await load_population(current_user, campaign_id, mentor_person_id, front_group_id, stage_key)
    now = now_utc()
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "name": 1, "start_date": 1, "end_date": 1}) if campaign_id else None
    start, previous_start = period_start(period, now, campaign)
    created = {item["enrollment_id"]: aware(item.get("created_at")) for item in items}
    in_period = [item for item in items if start and created[item["enrollment_id"]] and created[item["enrollment_id"]] >= start]
    in_previous = [item for item in items if previous_start and created[item["enrollment_id"]] and previous_start <= created[item["enrollment_id"]] < start]
    active = [item for item in items if item.get("status") == "active"]
    person_ids = list({item["person_id"] for item in items})
    members = set(await db.person_memberships.distinct("person_id", {"person_id": {"$in": person_ids}, "status": "active"})) if person_ids else set()

    # Embudo: personas que alcanzaron al menos cada paso.
    reached = [stage_index(item) for item in items]
    funnel = [
        {"key": "contacted", "label": "Contactadas", "value": len(items)},
        {"key": "assigned", "label": "Con mentor asignado", "value": sum(1 for item in items if item.get("mentor_person_id"))},
        {"key": "mcd", "label": "En ruta MCD", "value": sum(1 for value in reached if value >= STAGES.index("mcd"))},
        {"key": "npt", "label": "NPT", "value": sum(1 for value in reached if value >= STAGES.index("npt"))},
        {"key": "lbs", "label": "LBS", "value": sum(1 for value in reached if value >= STAGES.index("lbs_1"))},
        {"key": "retreat", "label": "Retiro", "value": sum(1 for item, value in zip(items, reached) if value >= STAGES.index("retreat") or item.get("retreat_completed_at"))},
        {"key": "membership", "label": "Membresía", "value": sum(1 for item in items if item["person_id"] in members)},
        {"key": "discipleship", "label": "Educación / Discipulado", "value": sum(1 for value in reached if value >= STAGES.index("discipleship_handoff"))},
    ]
    by_stage = Counter(item.get("current_stage_key") or "visitor_followup" for item in active)

    # Primer contacto (horas) y alertas.
    first_hours = [(aware(activity[item["enrollment_id"]]["first"]) - created[item["enrollment_id"]]).total_seconds() / 3600
                   for item in items if activity.get(item["enrollment_id"]) and aware(activity[item["enrollment_id"]].get("first")) and created[item["enrollment_id"]]]
    first_hours = [value for value in first_hours if value >= 0]
    unattended = [item for item in items if is_unattended(item, activity, now)]
    no_next = [item for item in active if not item.get("next_action_at")]
    transfers = [item for item in active if item.get("mentor_transfer_required") is True]

    # Carga por mentor (la autoridad pastoral principal no cuenta) y desbalance.
    authorities = await principal_authority_person_ids(db)
    load = Counter(item["mentor_person_id"] for item in active if item.get("mentor_person_id") and item["mentor_person_id"] not in authorities)
    from mentorship_outreach import person_display_name
    loads = sorted([{"mentor_person_id": key, "name": await person_display_name(key) or "Mentor", "active": value} for key, value in load.items()], key=lambda row: -row["active"])
    average = round(sum(load.values()) / len(load), 1) if load else 0
    for row in loads:
        row["above_average"] = bool(average and row["active"] > 2 * average)

    # Avance por invasión de origen.
    by_campaign_rows: dict = defaultdict(list)
    for item, value in zip(items, reached):
        if item.get("campaign_id"):
            by_campaign_rows[item["campaign_id"]].append((item, value))
    names = {doc["campaign_id"]: doc.get("name") async for doc in db.outreach_campaigns.find({"campaign_id": {"$in": list(by_campaign_rows)}}, {"_id": 0, "campaign_id": 1, "name": 1})}
    by_campaign = sorted(({"campaign_id": key, "name": names.get(key) or "Invasión", "total": len(rows), "in_route": sum(1 for _, value in rows if value >= STAGES.index("mcd")),
                           "retreat": sum(1 for _, value in rows if value >= STAGES.index("retreat")), "unattended": sum(1 for item, _ in rows if is_unattended(item, activity, now))}
                          for key, rows in by_campaign_rows.items()), key=lambda row: -row["total"])

    # Tendencia semanal (8 semanas): expedientes nuevos y actividades realizadas.
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    weeks = [week_start - timedelta(weeks=offset) for offset in range(7, -1, -1)]
    activities_done = []
    if items:
        activities_done = [aware(row.get("completed_at")) async for row in db.consolidation_activities.find({"enrollment_id": {"$in": [item["enrollment_id"] for item in items]}, "status": "done", "completed_at": {"$gte": weeks[0]}}, {"_id": 0, "completed_at": 1})]
    trend = []
    for index, begin in enumerate(weeks):
        end = weeks[index + 1] if index + 1 < len(weeks) else now + timedelta(seconds=1)
        trend.append({"week": begin.date().isoformat(), "label": begin.strftime("%d/%m"),
                      "new": sum(1 for value in created.values() if value and begin <= value < end),
                      "activities": sum(1 for value in activities_done if value and begin <= value < end)})

    def delta(current: int, previous: int) -> Optional[int]:
        return None if not previous_start else current - previous
    return {
        "scope": scope["level"], "period": period, "period_start": start.isoformat() if start else None,
        "filters": {"campaign_id": campaign_id, "campaign_name": (campaign or {}).get("name"), "mentor_person_id": mentor_person_id if scope["level"] == "all" else scope.get("mentor_person_id"), "front_group_id": front_group_id, "stage_key": stage_key},
        "figures": {
            "total": len(items), "active": len(active), "new": len(in_period), "new_previous": len(in_previous), "new_delta": delta(len(in_period), len(in_previous)),
            "unattended": len(unattended), "no_next_action": len(no_next), "transfers": len(transfers), "memberships": len(members),
            "first_contact_avg_hours": round(sum(first_hours) / len(first_hours), 1) if first_hours else None, "first_contact_count": len(first_hours),
        },
        "funnel": funnel,
        "by_stage": [{"stage_key": key, "label": STAGE_LABELS[key], "active": by_stage.get(key, 0)} for key in STAGES if by_stage.get(key)],
        "mentor_load": {"items": loads, "average": average, "mentors": len(loads)},
        "by_campaign": by_campaign, "trend": trend, "unattended_hours": UNATTENDED_HOURS,
    }


@router.get("/list/{metric}", response_model=dict)
async def panorama_list(metric: str, campaign_id: Optional[str] = None, mentor_person_id: Optional[str] = None, front_group_id: Optional[str] = None,
                        stage_key: Optional[str] = None, period: Literal["week", "month", "quarter", "invasion", "all"] = "month",
                        offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), current_user: dict = Depends(get_current_user)):
    """Las personas detrás de cada cifra (paginado), con enlace a su expediente."""
    if metric not in METRICS and not metric.startswith(("stage:", "funnel:")):
        raise HTTPException(status_code=404, detail="Indicador desconocido")
    scope, items, activity = await load_population(current_user, campaign_id, mentor_person_id, front_group_id, stage_key)
    now = now_utc()
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "start_date": 1, "end_date": 1}) if campaign_id else None
    start, _ = period_start(period, now, campaign)
    members = set(await db.person_memberships.distinct("person_id", {"person_id": {"$in": list({item["person_id"] for item in items})}, "status": "active"})) if items else set()
    if metric == "new":
        rows = [item for item in items if start and aware(item.get("created_at")) and aware(item["created_at"]) >= start]
    elif metric == "unattended":
        rows = [item for item in items if is_unattended(item, activity, now)]
    elif metric == "no_next_action":
        rows = [item for item in items if item.get("status") == "active" and not item.get("next_action_at")]
    elif metric == "transfers":
        rows = [item for item in items if item.get("status") == "active" and item.get("mentor_transfer_required") is True]
    elif metric == "first_contact":
        rows = [item for item in items if activity.get(item["enrollment_id"])]
    elif metric == "memberships":
        rows = [item for item in items if item["person_id"] in members]
    elif metric.startswith("stage:"):
        rows = [item for item in items if item.get("status") == "active" and (item.get("current_stage_key") or "visitor_followup") == metric.split(":", 1)[1]]
    elif metric.startswith("funnel:"):
        step = metric.split(":", 1)[1]
        thresholds = {"mcd": "mcd", "npt": "npt", "lbs": "lbs_1", "retreat": "retreat", "discipleship": "discipleship_handoff"}
        if step == "assigned":
            rows = [item for item in items if item.get("mentor_person_id")]
        elif step == "membership":
            rows = [item for item in items if item["person_id"] in members]
        elif step in thresholds:
            rows = [item for item in items if stage_index(item) >= STAGES.index(thresholds[step])]
        else:
            rows = items
    else:
        rows = items
    rows.sort(key=lambda item: aware(item.get("created_at")) or now, reverse=True)
    page = rows[offset:offset + limit]
    from mentorship_outreach import person_display_name
    out = []
    for item in page:
        stats = activity.get(item["enrollment_id"]) or {}
        out.append({"enrollment_id": item["enrollment_id"], "person_id": item["person_id"], "name": await person_display_name(item["person_id"]) or "Persona",
                    "mentor_person_id": item.get("mentor_person_id"), "mentor_name": await person_display_name(item.get("mentor_person_id")) if item.get("mentor_person_id") else None,
                    "stage_key": item.get("current_stage_key"), "stage_label": STAGE_LABELS.get(item.get("current_stage_key"), item.get("current_stage_key")), "status": item.get("status"),
                    "created_at": aware(item.get("created_at")).isoformat() if aware(item.get("created_at")) else None,
                    "last_activity_at": aware(stats.get("last")).isoformat() if aware(stats.get("last")) else None,
                    "next_action": item.get("next_action"), "next_action_at": item.get("next_action_at").isoformat() if isinstance(item.get("next_action_at"), datetime) else item.get("next_action_at"),
                    "campaign_id": item.get("campaign_id")})
    return {"metric": metric, "total": len(rows), "items": out, "scope": scope["level"]}
