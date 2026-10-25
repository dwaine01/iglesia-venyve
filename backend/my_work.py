"""MT1 · «Mi Trabajo»: una sola fuente de pendientes para el mentor.

Lee lo que ya existe (sin colecciones nuevas):
- viviendas del puerta a puerta (`outreach_households` + intentos);
- personas contactadas con seguimiento (`outreach_visits`: `next_action` /
  `next_action_at`, L2);
- expedientes de Consolidación asignados al mentor (`process_enrollments`:
  `next_action` / `next_action_at`) y sus actividades.

Pendientes: atrasados → hoy → próximos → sin fecha. Siguen aunque la
invasión haya terminado (se conserva la invasión de origen). Una vivienda
con «No desean más visitas» sale de pendientes y conserva su historial.

Mensajes neutros y orientadores: sin rankings ni semáforos.

Permisos (backend): el mentor ve SOLO su trabajo. Supervisión por mentor:
coordinador general, autoridad pastoral o `consolidation.assign`."""
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException

from access_control import CONSOLIDATION_ASSIGN, has_capability, is_general_coordinator, is_global_pastoral_authority
from mentorship_outreach import person_display_name, serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/my-work", tags=["my-work"])

ACTIVE_ENROLLMENT = ["active", "paused", "planned"]
PENDING_DOORS = ["pending_revisit", "followup_scheduled"]
STAGE_LABELS = {"visitor_followup": "Nuevo y seguimiento", "prayer": "Oración", "invasion": "Invasión", "mcd": "MCD", "npt": "Nací Para Triunfar", "welcome_party": "Fiesta de Bienvenida",
                "lbs_1": "LBS 1", "lbs_2": "LBS 2", "lbs_3": "LBS 3", "retreat": "Retiro", "discipleship_handoff": "Educación / Discipulado"}
RESULT_LABELS = {"opened": "Abrieron", "no_answer": "No abrieron", "requested_return": "Pidieron que regresen", "no_more_visits": "No desean más visitas"}
ACTIVITY_RESULTS = {"done": "Realizada", "no_answer": "Sin respuesta", "rescheduled": "Reprogramada"}
SUMMARY_METRICS = ("visited", "opened", "pending_return", "people_to_attend", "started_consolidation")


def can_supervise(current_user: dict) -> bool:
    return is_general_coordinator(current_user) or is_global_pastoral_authority(current_user) or has_capability(current_user, CONSOLIDATION_ASSIGN)


def scope_mentor(current_user: dict, mentor_person_id: Optional[str]) -> str:
    """El mentor solo ve lo suyo; ver a otro mentor requiere supervisión."""
    if mentor_person_id and mentor_person_id != current_user.get("person_id"):
        if not can_supervise(current_user):
            raise HTTPException(status_code=403, detail="Solo puede consultar su propio trabajo")
        return mentor_person_id
    if not current_user.get("person_id"):
        raise HTTPException(status_code=403, detail="Su cuenta no está vinculada a una persona")
    return current_user["person_id"]


async def _zone() -> ZoneInfo:
    from consolidation_activities import get_church_timezone
    try:
        return ZoneInfo(await get_church_timezone())
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _aware(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if "T" in value else datetime.combine(date.fromisoformat(value[:10]), datetime.min.time())
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _local_day(value, zone: ZoneInfo) -> Optional[str]:
    if isinstance(value, str) and len(value) == 10:
        return value  # fecha sin hora (ya es del calendario local)
    moment = _aware(value)
    return moment.astimezone(zone).date().isoformat() if moment else None


async def _period(period: str, campaign_id: Optional[str], zone: ZoneInfo) -> Optional[datetime]:
    """Inicio del periodo: esta semana (desde el lunes local) / la invasión / todo."""
    if period == "week":
        today = datetime.now(zone).date()
        monday = today - timedelta(days=today.weekday())
        return datetime.combine(monday, datetime.min.time(), tzinfo=zone).astimezone(timezone.utc)
    return None


async def _base(mentor: str, campaign_id: Optional[str]) -> dict:
    query: dict = {"mentor_person_id": mentor, "archived": {"$ne": True}}
    if campaign_id:
        query["campaign_id"] = campaign_id
    return query


# ------------------------------------------------------------------ resumen
async def compute_summary(mentor: str, period: str, campaign_id: Optional[str]) -> dict:
    zone = await _zone()
    since = await _period(period, campaign_id, zone)
    base = await _base(mentor, campaign_id)
    # Viviendas: una consulta agregada sobre los intentos del periodo (vivienda cuenta una vez).
    event_match: dict = {"mentor_person_id": mentor, "is_draft": {"$ne": True}}
    if campaign_id:
        event_match["campaign_id"] = campaign_id
    if since:
        event_match["occurred_at"] = {"$gte": since}
    houses = await db.outreach_visit_events.aggregate([
        {"$match": event_match},
        {"$group": {"_id": "$household_id", "opened": {"$max": {"$cond": [{"$or": [{"$eq": ["$opened", True]}, {"$in": ["$result", ["contacted", "refused"]]}]}, 1, 0]}},
                    "conversed": {"$max": {"$cond": [{"$in": ["$contact_level", ["conversation", "invited_in"]]}, 1, 0]}}}},
        {"$group": {"_id": None, "visited": {"$sum": 1}, "opened": {"$sum": "$opened"}, "conversed": {"$sum": "$conversed"}}},
    ]).to_list(1)
    figures = houses[0] if houses else {"visited": 0, "opened": 0, "conversed": 0}
    pending_return = await db.outreach_households.count_documents({**base, "door_status": {"$in": PENDING_DOORS}})
    enrollment_query: dict = {"mentor_person_id": mentor, "process_key": "consolidation", "status": {"$in": ACTIVE_ENROLLMENT}}
    if campaign_id:
        enrollment_query["campaign_id"] = campaign_id
    enrollments = await db.process_enrollments.count_documents(enrollment_query)
    contacts = await db.outreach_visits.count_documents({**base, "enrollment_id": {"$in": [None, ""]}, "$or": [{"followup_accepted": True}, {"status": "wants_followup"}]})
    started_query: dict = {**base, "enrollment_id": {"$nin": [None, ""]}}
    if since:
        started_query["converted_at"] = {"$gte": since}
    started = await db.outreach_visits.count_documents(started_query)
    no_next = await db.process_enrollments.count_documents({**enrollment_query, "next_action_at": None}) + await db.outreach_visits.count_documents(
        {**base, "enrollment_id": {"$in": [None, ""]}, "followup_accepted": True, "next_action_at": None})
    pending = await pending_items(mentor, campaign_id, zone)
    today_count = sum(1 for item in pending if item["bucket"] == "today")
    overdue = sum(1 for item in pending if item["bucket"] == "overdue")
    mentor_user = await db.users.find_one({"person_id": mentor}, {"_id": 1})
    books_to_complete = await db.library_movements.count_documents({"movement_type": {"$in": ["DELIVERY", "DELIVERY_PENDING"]}, "recipient_status": "unidentified",
                                                                    "household_id": {"$nin": [None, ""]}, "from_holder.id": str(mentor_user["_id"])}) if mentor_user else 0
    words = {"week": "Esta semana", "invasion": "En esta invasión", "all": "En total"}[period]
    message = (f"{words} visitaste {figures['visited']} vivienda(s), conversaste en {figures['conversed']} y {started} persona(s) comenzaron el proceso."
               + (f" Tienes {today_count} atención(es) para hoy." if today_count else ""))
    notices = []
    if overdue:
        notices.append({"key": "overdue", "text": f"Tienes {overdue} atención(es) con fecha pasada; puedes reprogramarlas."})
    if no_next:
        notices.append({"key": "no_next_action", "text": f"Tienes {no_next} persona(s) sin próxima atención programada."})
    if books_to_complete:
        notices.append({"key": "books_recipient", "text": f"Tienes {books_to_complete} libro(s) entregado(s) sin saber a quién; puedes completar el nombre."})
    return {"mentor_person_id": mentor, "period": period, "campaign_id": campaign_id, "period_start": since.isoformat() if since else None,
            "figures": {"visited": figures["visited"], "opened": figures["opened"], "conversed": figures["conversed"], "pending_return": pending_return,
                        "people_to_attend": enrollments + contacts, "started_consolidation": started},
            "today": today_count, "overdue": overdue, "message": message, "notices": notices}


@router.get("/summary", response_model=dict)
async def my_work_summary(period: Literal["week", "invasion", "all"] = "week", campaign_id: Optional[str] = None, mentor_person_id: Optional[str] = None,
                          current_user: dict = Depends(get_current_user)):
    mentor = scope_mentor(current_user, mentor_person_id)
    if period == "invasion" and not campaign_id:
        raise HTTPException(status_code=422, detail="Elija la invasión")
    data = await compute_summary(mentor, period, campaign_id)
    return {**data, "mentor_name": await person_display_name(mentor), "supervising": mentor != current_user.get("person_id")}


@router.get("/summary/{metric}", response_model=dict)
async def my_work_summary_list(metric: str, period: Literal["week", "invasion", "all"] = "week", campaign_id: Optional[str] = None, mentor_person_id: Optional[str] = None,
                               offset: int = 0, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Lo que compone cada cifra (paginado)."""
    if metric not in SUMMARY_METRICS:
        raise HTTPException(status_code=404, detail="Indicador desconocido")
    mentor = scope_mentor(current_user, mentor_person_id)
    zone = await _zone()
    since = await _period(period, campaign_id, zone)
    base = await _base(mentor, campaign_id)
    limit = max(1, min(limit, 100))
    if metric in {"visited", "opened"}:
        event_match: dict = {"mentor_person_id": mentor, "is_draft": {"$ne": True}}
        if campaign_id:
            event_match["campaign_id"] = campaign_id
        if since:
            event_match["occurred_at"] = {"$gte": since}
        if metric == "opened":
            event_match["$or"] = [{"opened": True}, {"result": {"$in": ["contacted", "refused"]}}]
        house_ids = await db.outreach_visit_events.distinct("household_id", event_match)
        query = {"household_id": {"$in": house_ids}}
    elif metric == "pending_return":
        query = {**base, "door_status": {"$in": PENDING_DOORS}}
    else:
        query = None
    if query is not None:
        total = await db.outreach_households.count_documents(query)
        keys = {"_id": 0, "household_id": 1, "address_line1": 1, "address_line2": 1, "door_status": 1, "last_result": 1, "last_attempt_at": 1, "attempts_count": 1, "followup_date": 1, "campaign_id": 1}
        items = await db.outreach_households.find(query, keys).sort("last_attempt_at", -1).skip(offset).limit(limit).to_list(limit)
        return {"metric": metric, "kind": "households", "total": total, "items": serialize(items)}
    if metric == "people_to_attend":
        items = [item for item in await pending_items(mentor, campaign_id, zone) if item["kind"] in {"person", "contact"}]
        return {"metric": metric, "kind": "people", "total": len(items), "items": items[offset:offset + limit]}
    started_query: dict = {**base, "enrollment_id": {"$nin": [None, ""]}}
    if since:
        started_query["converted_at"] = {"$gte": since}
    total = await db.outreach_visits.count_documents(started_query)
    visits = await db.outreach_visits.find(started_query, {"_id": 0, "visit_id": 1, "contact_name": 1, "person_id": 1, "converted_person_id": 1, "enrollment_id": 1, "converted_at": 1, "campaign_id": 1}).sort("converted_at", -1).skip(offset).limit(limit).to_list(limit)
    for visit in visits:
        visit["name"] = await person_display_name(visit.get("converted_person_id") or visit.get("person_id")) or visit.get("contact_name") or "Persona"
    return {"metric": metric, "kind": "people", "total": total, "items": serialize(visits)}


# ------------------------------------------------------------------ pendientes
def _bucket(day: Optional[str], today: str, undated: str) -> str:
    if not day:
        return undated
    if day < today:
        return "overdue"
    return "today" if day == today else "upcoming"


BUCKET_ORDER = {"overdue": 0, "today": 1, "upcoming": 2, "no_date": 3}


async def pending_items(mentor: str, campaign_id: Optional[str], zone: ZoneInfo) -> list[dict]:
    """Viviendas pendientes + personas (contactos con seguimiento y expedientes de
    Consolidación del mentor), ordenadas: atrasados → hoy → próximos → sin fecha."""
    today = datetime.now(zone).date().isoformat()
    base = await _base(mentor, campaign_id)
    items: list[dict] = []
    campaign_names: dict[str, str] = {}
    async for house in db.outreach_households.find({**base, "door_status": {"$in": PENDING_DOORS}}, {"_id": 0, "household_id": 1, "address_line1": 1, "address_line2": 1, "door_status": 1,
                                                                                                    "last_result": 1, "last_attempt_at": 1, "followup_date": 1, "campaign_id": 1, "next_visit_note": 1,
                                                                                                    "latitude": 1, "longitude": 1}):
        day = house.get("followup_date")
        # «Pendiente de nueva visita» sin fecha se puede atender hoy.
        items.append({"kind": "household", "id": house["household_id"], "title": " · ".join(filter(None, [house.get("address_line1"), house.get("address_line2")])) or "Vivienda",
                      "last_at": house.get("last_attempt_at"), "last_result": RESULT_LABELS.get(house.get("last_result"), house.get("last_result")),
                      "next_action": "Programada" if house.get("door_status") == "followup_scheduled" else "Pendiente de nueva visita", "next_action_note": house.get("next_visit_note"),
                      "due_date": day, "bucket": _bucket(day, today, "today"), "campaign_id": house.get("campaign_id"), "household_id": house["household_id"],
                      "latitude": house.get("latitude"), "longitude": house.get("longitude")})
    async for visit in db.outreach_visits.find({**base, "enrollment_id": {"$in": [None, ""]}, "$or": [{"followup_accepted": True}, {"status": "wants_followup"}]},
                                               {"_id": 0, "visit_id": 1, "contact_name": 1, "person_id": 1, "converted_person_id": 1, "next_action": 1, "next_action_at": 1,
                                                "visit_date": 1, "status": 1, "campaign_id": 1, "household_id": 1, "address_line1": 1, "address_line2": 1, "updated_at": 1}):
        day = _local_day(visit.get("next_action_at"), zone)
        name = await person_display_name(visit.get("converted_person_id") or visit.get("person_id")) if (visit.get("converted_person_id") or visit.get("person_id")) else None
        items.append({"kind": "contact", "id": visit["visit_id"], "title": name or visit.get("contact_name") or "Persona contactada",
                      "subtitle": " · ".join(filter(None, [visit.get("address_line1"), visit.get("address_line2")])) or None,
                      "last_at": visit.get("visit_date") or visit.get("updated_at"), "last_result": "Aceptó seguimiento", "next_action": visit.get("next_action") or "Dar seguimiento",
                      "due_date": day, "bucket": _bucket(day, today, "no_date"), "campaign_id": visit.get("campaign_id"), "visit_id": visit["visit_id"],
                      "household_id": visit.get("household_id"), "person_id": visit.get("converted_person_id") or visit.get("person_id")})
    enrollment_query: dict = {"mentor_person_id": mentor, "process_key": "consolidation", "status": {"$in": ACTIVE_ENROLLMENT}}
    if campaign_id:
        enrollment_query["campaign_id"] = campaign_id
    enrollments = await db.process_enrollments.find(enrollment_query, {"_id": 0, "enrollment_id": 1, "person_id": 1, "current_stage_key": 1, "next_action": 1, "next_action_at": 1, "campaign_id": 1, "created_at": 1}).to_list(2000)
    last_activity = {}
    if enrollments:
        async for row in db.consolidation_activities.aggregate([
            {"$match": {"enrollment_id": {"$in": [item["enrollment_id"] for item in enrollments]}, "last_result": {"$ne": None}}},
            {"$sort": {"result_at": -1}}, {"$group": {"_id": "$enrollment_id", "at": {"$first": "$result_at"}, "result": {"$first": "$last_result"}, "title": {"$first": "$title"}}},
        ]):
            last_activity[row["_id"]] = row
    for enrollment in enrollments:
        day = _local_day(enrollment.get("next_action_at"), zone)
        last = last_activity.get(enrollment["enrollment_id"]) or {}
        items.append({"kind": "person", "id": enrollment["enrollment_id"], "title": await person_display_name(enrollment["person_id"]) or "Persona",
                      "subtitle": STAGE_LABELS.get(enrollment.get("current_stage_key"), enrollment.get("current_stage_key")), "stage_key": enrollment.get("current_stage_key"),
                      "last_at": last.get("at"), "last_result": " · ".join(filter(None, [last.get("title"), ACTIVITY_RESULTS.get(last.get("result"), last.get("result"))])) or None,
                      "next_action": enrollment.get("next_action") or "Sin próxima acción", "due_date": day, "bucket": _bucket(day, today, "no_date"),
                      "campaign_id": enrollment.get("campaign_id"), "enrollment_id": enrollment["enrollment_id"], "person_id": enrollment["person_id"]})
    ids = list({item["campaign_id"] for item in items if item.get("campaign_id")})
    if ids:
        campaign_names = {doc["campaign_id"]: doc.get("name") async for doc in db.outreach_campaigns.find({"campaign_id": {"$in": ids}}, {"_id": 0, "campaign_id": 1, "name": 1})}
    for item in items:
        item["campaign_name"] = campaign_names.get(item.get("campaign_id"))  # invasión de origen (aunque haya terminado)
    items.sort(key=lambda item: (BUCKET_ORDER[item["bucket"]], item.get("due_date") or "9999", str(item.get("last_at") or "")))
    return serialize(items)


@router.get("/pending", response_model=dict)
async def my_work_pending(kind: Literal["all", "households", "people"] = "all", campaign_id: Optional[str] = None, mentor_person_id: Optional[str] = None,
                          offset: int = 0, limit: int = 50, current_user: dict = Depends(get_current_user)):
    mentor = scope_mentor(current_user, mentor_person_id)
    items = await pending_items(mentor, campaign_id, await _zone())
    if kind == "households":
        items = [item for item in items if item["kind"] == "household"]
    elif kind == "people":
        items = [item for item in items if item["kind"] in {"person", "contact"}]
    counts = {bucket: sum(1 for item in items if item["bucket"] == bucket) for bucket in BUCKET_ORDER}
    limit = max(1, min(limit, 100))
    return {"total": len(items), "counts": counts, "items": items[offset:offset + limit]}


@router.get("/campaigns", response_model=dict)
async def my_work_campaigns(mentor_person_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Invasiones donde el mentor tiene trabajo (para el filtro), incluidas las terminadas."""
    mentor = scope_mentor(current_user, mentor_person_id)
    ids = set(await db.outreach_households.distinct("campaign_id", {"mentor_person_id": mentor})) | set(await db.outreach_visits.distinct("campaign_id", {"mentor_person_id": mentor}))
    ids.discard(None)
    campaigns = await db.outreach_campaigns.find({"campaign_id": {"$in": list(ids)}}, {"_id": 0, "campaign_id": 1, "name": 1, "start_date": 1, "status": 1}).sort("start_date", -1).to_list(100)
    return {"items": campaigns}
