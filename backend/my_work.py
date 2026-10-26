"""MT1–MT3 · «Mi Trabajo»: una sola fuente de pendientes para el mentor,
supervisión por mentor y reasignación con historial.

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
from pydantic import BaseModel, Field

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
    # Mismo día local que el reporte de invasión (America/New_York si la iglesia sigue en UTC).
    from report_period import report_zone
    try:
        return await report_zone()
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
    # Viviendas del periodo (cada vivienda cuenta una vez; solo las que existen, igual que sus listados).
    visited_ids = await db.outreach_visit_events.distinct("household_id", event_match)
    opened_ids = await db.outreach_visit_events.distinct("household_id", {**event_match, "$or": [{"opened": True}, {"result": {"$in": ["contacted", "refused"]}}]})
    conversed_ids = await db.outreach_visit_events.distinct("household_id", {**event_match, "contact_level": {"$in": ["conversation", "invited_in"]}})
    live = {"archived": {"$ne": True}}
    figures = {"visited": await db.outreach_households.count_documents({"household_id": {"$in": visited_ids}, **live}),
               "opened": await db.outreach_households.count_documents({"household_id": {"$in": opened_ids}, **live}),
               "conversed": await db.outreach_households.count_documents({"household_id": {"$in": conversed_ids}, **live})}
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
    pending = await pending_items(mentor, campaign_id, zone)
    assigned_visits = sum(1 for item in pending if item["kind"] == "assigned_visit")
    today_count = sum(1 for item in pending if item["bucket"] == "today")
    overdue = sum(1 for item in pending if item["bucket"] == "overdue")
    mentor_user = await db.users.find_one({"person_id": mentor}, {"_id": 1})
    books_to_complete = await db.library_movements.count_documents({"movement_type": {"$in": ["DELIVERY", "DELIVERY_PENDING"]}, "recipient_status": "unidentified",
                                                                    "household_id": {"$nin": [None, ""]}, "from_holder.id": str(mentor_user["_id"])}) if mentor_user else 0
    totals = (await mentor_totals([mentor], campaign_id)).get(mentor) or empty_totals()
    people = await people_rows(mentor, campaign_id)
    no_next = sum(1 for row in people if not row.get("due_date"))
    words = {"week": "Esta semana", "invasion": "En esta invasión", "all": "En total"}[period]
    message = (f"{words} visitaste {figures['visited']} vivienda(s), conversaste en {figures['conversed']} y {started} persona(s) comenzaron el proceso."
               + (f" Tienes {today_count} atención(es) para hoy." if today_count else ""))
    notices = []
    if overdue:
        notices.append({"key": "overdue", "text": f"Tienes {overdue} atención(es) con fecha pasada; puedes reprogramarlas."})
    if no_next:
        notices.append({"key": "no_next_action", "text": f"Tienes {no_next} persona(s) sin próxima atención programada.", "action": "personas"})
    if books_to_complete:
        notices.append({"key": "books_recipient", "text": f"Tienes {books_to_complete} libro(s) entregado(s) sin saber a quién; puedes completar el nombre."})
    return {"mentor_person_id": mentor, "period": period, "campaign_id": campaign_id, "period_start": since.isoformat() if since else None,
            "figures": {"visited": figures["visited"], "opened": figures["opened"], "conversed": figures["conversed"], "pending_return": pending_return,
                        "people_to_attend": enrollments + contacts, "started_consolidation": started},
            "today": today_count, "overdue": overdue, "assigned_visits": assigned_visits, "message": message, "notices": notices, "totals": totals}


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
        query = {"household_id": {"$in": house_ids}, "archived": {"$ne": True}}
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
# Visita registrada o asignada que aún no se hizo (sin seguimiento aceptado ni Consolidación).
ASSIGNED_VISIT = {"status": "assigned", "enrollment_id": {"$in": [None, ""]}, "followup_accepted": {"$ne": True}}


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
    # Visitas asignadas que todavía no se hicieron («Asignar visita» de un líder o anotadas por el mentor).
    async for visit in db.outreach_visits.find({**ASSIGNED_VISIT, **base}, {"_id": 0, "visit_id": 1, "contact_name": 1, "contact_zone": 1, "contact_phone": 1, "person_id": 1, "campaign_id": 1,
                                                                            "address_line1": 1, "address_line2": 1, "invasion_day": 1, "assigned_by_person_id": 1, "assigned_at": 1, "created_at": 1}):
        name = await person_display_name(visit.get("person_id")) if visit.get("person_id") else None
        by = await person_display_name(visit.get("assigned_by_person_id")) if visit.get("assigned_by_person_id") else None
        day = visit.get("invasion_day")
        items.append({"kind": "assigned_visit", "id": visit["visit_id"], "title": name or visit.get("contact_name") or "Persona por visitar",
                      "subtitle": " · ".join(filter(None, [visit.get("address_line1"), visit.get("address_line2")])) or visit.get("contact_zone"),
                      "phone": visit.get("contact_phone"), "assigned_by_name": by,
                      "last_at": visit.get("assigned_at") or visit.get("created_at"), "last_result": f"Asignada por {by}" if by else "Visita por hacer",
                      "next_action": "Visitar", "due_date": day, "bucket": _bucket(day, today, "today"), "campaign_id": visit.get("campaign_id"),
                      "visit_id": visit["visit_id"], "person_id": visit.get("person_id")})
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
        items = [item for item in items if item["kind"] in {"person", "contact", "assigned_visit"}]
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


# ------------------------------------------------------------------ MT3 · supervisión y reasignar
def require_supervisor(current_user: dict) -> None:
    if not can_supervise(current_user):
        raise HTTPException(status_code=403, detail="Solo coordinador general, autoridad pastoral o encargado de Consolidación")


@router.get("/mentors", response_model=dict)
async def my_work_mentors(current_user: dict = Depends(get_current_user)):
    """Mentores activos con su carga de pendientes (información, no ranking)."""
    require_supervisor(current_user)
    from participation_scope import principal_authority_person_ids
    authorities = await principal_authority_person_ids(db)
    mentor_ids = [doc["person_id"] for doc in await db.mentor_badges.find({"active": True}, {"_id": 0, "person_id": 1}).to_list(5000) if doc.get("person_id") not in authorities]
    items = list((await mentor_work_rows(mentor_ids)).values())
    items.sort(key=lambda row: row["name"])
    return {"items": items}


async def mentor_work_rows(mentor_ids: list[str]) -> dict:
    """UNA sola fuente para «Supervisar Mi Trabajo», la tabla «Líderes y su
    Desempeño» del Panel General y el detalle del líder: totales reales,
    pendientes, personas en Consolidación, trabajo de hoy e inventario."""
    mentor_ids = [pid for pid in dict.fromkeys(mentor_ids) if pid]
    if not mentor_ids:
        return {}
    houses = {row["_id"]: row["n"] async for row in db.outreach_households.aggregate([
        {"$match": {"mentor_person_id": {"$in": mentor_ids}, "archived": {"$ne": True}, "door_status": {"$in": PENDING_DOORS}}}, {"$group": {"_id": "$mentor_person_id", "n": {"$sum": 1}}}])}
    from count_rules import open_consolidation_by_mentor
    people = await open_consolidation_by_mentor(mentor_ids)  # personas únicas, misma regla que Consolidación
    contacts = {row["_id"]: row["n"] async for row in db.outreach_visits.aggregate([
        {"$match": {"mentor_person_id": {"$in": mentor_ids}, "archived": {"$ne": True}, "enrollment_id": {"$in": [None, ""]}, "$or": [{"followup_accepted": True}, {"status": "wants_followup"}]}},
        {"$group": {"_id": "$mentor_person_id", "n": {"$sum": 1}}}])}
    totals = await mentor_totals(mentor_ids)
    today = await today_totals(mentor_ids)
    rows = {}
    for pid in mentor_ids:
        row = totals.get(pid) or empty_totals()
        day = today.get(pid) or {"houses": 0, "books": 0, "people": 0}
        pending = houses.get(pid, 0) + people.get(pid, 0) + contacts.get(pid, 0)
        worked_today = bool(day["houses"] or day["books"] or day["people"])
        rows[pid] = {"person_id": pid, "name": await person_display_name(pid) or "Mentor", **row,
                     "pending_households": houses.get(pid, 0), "pending_people": people.get(pid, 0) + contacts.get(pid, 0),
                     "in_consolidation": people.get(pid, 0), "today": day,
                     # Compatibilidad: «households»/«people» = totales reales del trabajo (no solo pendientes).
                     "households": row["houses_visited"], "people": row["people_contacted"], "pending": pending,
                     "work_status": "worked_today" if worked_today else ("has_pending" if pending else "no_activity_today"),
                     "work_status_label": "Trabajó hoy" if worked_today else ("Tiene pendientes" if pending else "Sin actividad hoy")}
    return rows


async def _today_start() -> tuple[datetime, ZoneInfo]:
    zone = await _zone()
    start = datetime.combine(datetime.now(zone).date(), datetime.min.time(), tzinfo=zone)
    return start.astimezone(timezone.utc), zone


async def today_totals(mentor_ids: list[str]) -> dict:
    """Trabajo de HOY (día local): viviendas con intento, libros entregados y personas registradas."""
    since, _ = await _today_start()
    result = {pid: {"houses": 0, "books": 0, "people": 0} for pid in mentor_ids}
    async for row in db.outreach_visit_events.aggregate([
        {"$match": {"mentor_person_id": {"$in": mentor_ids}, "is_draft": {"$ne": True}, "occurred_at": {"$gte": since}}},
        {"$group": {"_id": "$mentor_person_id", "houses": {"$addToSet": "$household_id"}}}]):
        result[row["_id"]]["houses"] = len([item for item in row["houses"] if item])
    async for row in db.outreach_visits.aggregate([
        {"$match": {"mentor_person_id": {"$in": mentor_ids}, "archived": {"$ne": True}, "created_at": {"$gte": since}}}, {"$group": {"_id": "$mentor_person_id", "n": {"$sum": 1}}}]):
        result[row["_id"]]["people"] = row["n"]
    users = await _mentor_users(mentor_ids)
    person_of_user = {user_id: pid for pid, user_id in users.items()}
    if users:
        async for movement in db.library_movements.find({"from_holder.type": "user", "from_holder.id": {"$in": list(users.values())}, "movement_type": {"$in": BOOK_TYPES},
                                                         "is_reversal": {"$ne": True}, "occurred_at": {"$gte": since}}, {"_id": 0, "from_holder": 1, "quantity": 1}):
            pid = person_of_user.get(movement["from_holder"]["id"])
            if pid:
                result[pid]["books"] += movement.get("quantity") or 1
    return result


async def scope_leader_branch(current_user: dict, mentor_person_id: str) -> str:
    """Supervisión (como `scope_mentor`) o un líder viendo a un líder/colíder de
    un grupo de SU rama hacia abajo (Grupo Frontal › Mis ramas)."""
    if mentor_person_id == current_user.get("person_id") or can_supervise(current_user):
        return scope_mentor(current_user, mentor_person_id)
    from front_group_structure import explorable_ids, lead_group_ids
    allowed = await explorable_ids(current_user)
    mine = await lead_group_ids(current_user)
    if allowed is None or await db.front_group_assignments.find_one({"person_id": mentor_person_id, "role": {"$in": ["leader", "co_leader"]}, "active": True,
                                                                     "front_group_id": {"$in": [gid for gid in (allowed or set()) if gid not in mine]}}, {"_id": 1}):
        return mentor_person_id
    raise HTTPException(status_code=403, detail="Solo puede ver el trabajo de los líderes de su rama hacia abajo")


@router.get("/leader-detail", response_model=dict)
async def leader_detail(mentor_person_id: str, current_user: dict = Depends(get_current_user)):
    """Detalle del trabajo de un líder/mentor (Panel General › Entrar al Líder):
    resumen hoy / semana / total, su trabajo de hoy hora por hora, expedientes
    de Consolidación y asistencia a invasiones. Pendientes, personas, viviendas
    e inventario salen de los mismos endpoints de Mi Trabajo."""
    mentor = await scope_leader_branch(current_user, mentor_person_id)
    row = (await mentor_work_rows([mentor]))[mentor]
    week = await compute_summary(mentor, "week", None)
    since, zone = await _today_start()
    timeline = []
    house_ids = set()
    events = await db.outreach_visit_events.find({"mentor_person_id": mentor, "is_draft": {"$ne": True}, "occurred_at": {"$gte": since}}, {"_id": 0}).sort("occurred_at", 1).to_list(500)
    house_ids |= {item.get("household_id") for item in events if item.get("household_id")}
    visits = await db.outreach_visits.find({"mentor_person_id": mentor, "archived": {"$ne": True}, "created_at": {"$gte": since}}, {"_id": 0}).sort("created_at", 1).to_list(500)
    house_ids |= {item.get("household_id") for item in visits if item.get("household_id")}
    user = await db.users.find_one({"person_id": mentor}, {"_id": 1})
    movements = await db.library_movements.find({"from_holder.type": "user", "from_holder.id": str(user["_id"]), "movement_type": {"$in": BOOK_TYPES}, "is_reversal": {"$ne": True},
                                                 "occurred_at": {"$gte": since}}, {"_id": 0}).sort("occurred_at", 1).to_list(500) if user else []
    house_ids |= {item.get("household_id") for item in movements if item.get("household_id")}
    houses = {doc["household_id"]: doc async for doc in db.outreach_households.find({"household_id": {"$in": list(house_ids)}}, {"_id": 0, "household_id": 1, "address_line1": 1, "address_line2": 1, "street_name": 1})} if house_ids else {}
    address = lambda house_id: " · ".join(filter(None, [(houses.get(house_id) or {}).get("address_line1"), (houses.get(house_id) or {}).get("address_line2")])) or None  # noqa: E731
    for event in events:
        detail = "Abrieron" if event.get("opened") else "No abrieron"
        if event.get("books_total"):
            detail += f" · {event['books_total']} libro(s)"
        if event.get("followup") == "yes":
            detail += " · aceptó seguimiento"
        timeline.append({"kind": "visit", "at": event.get("occurred_at"), "title": f"Visitó {address(event.get('household_id')) or 'una vivienda'}", "detail": detail, "household_id": event.get("household_id")})
    for visit in visits:
        person_id = visit.get("converted_person_id") or visit.get("person_id")
        name = (await person_display_name(person_id) if person_id else None) or visit.get("contact_name") or "Persona"
        timeline.append({"kind": "person", "at": visit.get("created_at"), "title": f"Registró a {name}", "detail": address(visit.get("household_id")) or visit.get("address_line1"), "person_id": person_id})
    for movement in movements:
        name = await person_display_name(movement["person_id"]) if movement.get("person_id") else None
        timeline.append({"kind": "book", "at": movement.get("occurred_at"), "title": f"Entregó {movement.get('quantity') or 1} × {movement.get('book_name') or 'libro'}",
                         "detail": f"A {name}" if name else (f"En {address(movement.get('household_id'))} · sin nombre todavía" if movement.get("household_id") else "Sin nombre todavía"),
                         "person_id": movement.get("person_id"), "movement_id": movement.get("movement_id")})
    timeline.sort(key=lambda item: serialize(item.get("at")) or "")
    for item in timeline:
        moment = _aware(item.get("at"))
        item["time"] = moment.astimezone(zone).strftime("%H:%M") if moment else None
    enrollments = await db.process_enrollments.find({"mentor_person_id": mentor, "process_key": "consolidation", "status": {"$in": ACTIVE_ENROLLMENT}},
                                                    {"_id": 0, "enrollment_id": 1, "person_id": 1, "current_stage_key": 1, "next_action": 1, "next_action_at": 1, "status": 1}).to_list(500)
    for item in enrollments:
        item["name"] = await person_display_name(item["person_id"]) or "Persona"
        item["stage"] = STAGE_LABELS.get(item.get("current_stage_key"), item.get("current_stage_key"))
    attendance = []
    async for part in db.invasion_participants.find({"person_id": mentor}, {"_id": 0, "campaign_id": 1, "roles": 1, "attended": 1, "attended_days": 1, "response": 1}):
        campaign = await db.outreach_campaigns.find_one({"campaign_id": part["campaign_id"]}, {"_id": 0, "name": 1, "start_date": 1})
        if campaign:
            attendance.append({"campaign_id": part["campaign_id"], "name": campaign.get("name"), "start_date": campaign.get("start_date"), "roles": part.get("roles") or [],
                               "attended": bool(part.get("attended") or part.get("attended_days")), "days": len(part.get("attended_days") or [])})
    attendance.sort(key=lambda item: item.get("start_date") or "", reverse=True)
    return {"mentor_person_id": mentor, "name": row["name"], "row": row,
            "summary": {"today": row["today"], "week": {"houses": week["figures"]["visited"], "opened": week["figures"]["opened"], "started_consolidation": week["figures"]["started_consolidation"]},
                        "total": {"houses": row["houses_visited"], "people": row["people_contacted"], "books": row["books_delivered"], "in_consolidation": row["in_consolidation"], "pending": row["pending"]}},
            "timeline": serialize(timeline), "enrollments": serialize(enrollments), "attendance": attendance, "inventory": row["inventory"]}


class ReassignItem(BaseModel):
    kind: Literal["household", "contact", "assigned_visit", "person"]
    id: str = Field(min_length=1, max_length=80)


class ReassignInput(BaseModel):
    items: list[ReassignItem] = Field(min_length=1, max_length=200)
    to_mentor_person_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=3, max_length=300)


@router.post("/reassign", response_model=dict)
async def reassign_pending(payload: ReassignInput, current_user: dict = Depends(get_current_user)):
    """Reasigna pendientes a otro mentor. Quién hizo cada atención NO cambia
    (los intentos y actividades guardan su autor); queda el historial de la
    reasignación y el nuevo mentor recibe un aviso."""
    require_supervisor(current_user)
    return await reassign_items([item.model_dump() for item in payload.items], payload.to_mentor_person_id, current_user, payload.reason.strip())


async def reassign_items(items: list[dict], target: str, current_user: dict, reason: str) -> dict:
    """Mueve pendientes ({kind, id}) a otro mentor activo, con historial y aviso. Lo usa también la entrega
    de trabajo al eliminar o desactivar a un líder o mentor (work_handover)."""
    from mentorship_outreach import is_active_mentor, log_visit_history, supervision_snapshot
    if not await is_active_mentor(target):
        raise HTTPException(status_code=422, detail="El nuevo responsable debe ser un mentor activo")
    now = datetime.now(timezone.utc)
    entry = {"to_mentor_person_id": target, "by_user_id": current_user["user_id"], "at": now, "reason": reason}
    snapshot = await supervision_snapshot(target)
    done, skipped = [], []
    for raw in items:
        item = ReassignItem(**raw)
        if item.kind == "household":
            house = await db.outreach_households.find_one({"household_id": item.id, "archived": {"$ne": True}}, {"_id": 0, "mentor_person_id": 1})
            if not house or house.get("mentor_person_id") == target:
                skipped.append(item.id)
                continue
            await db.outreach_households.update_one({"household_id": item.id}, {"$set": {"mentor_person_id": target, "front_group_id": snapshot["front_group_id"],
                                                                                          "front_group_ancestor_ids": snapshot["front_group_ancestor_ids"], "updated_at": now},
                                                                                 "$push": {"reassignments": {**entry, "from_mentor_person_id": house.get("mentor_person_id")}}})
        elif item.kind in ("contact", "assigned_visit"):
            visit = await db.outreach_visits.find_one({"visit_id": item.id, "archived": {"$ne": True}}, {"_id": 0, "mentor_person_id": 1, "followup_responsible_person_id": 1})
            if not visit or visit.get("mentor_person_id") == target:
                skipped.append(item.id)
                continue
            await db.outreach_visits.update_one({"visit_id": item.id}, {"$set": {"mentor_person_id": target, "followup_responsible_person_id": target, "updated_at": now,
                                                                                 "assigned_by_person_id": current_user.get("person_id"), "assigned_by_user_id": current_user["user_id"], "assigned_at": now},
                                                                         "$push": {"reassignments": {**entry, "from_mentor_person_id": visit.get("mentor_person_id")}}})
            await log_visit_history(item.id, current_user, "reassigned", {"from": visit.get("mentor_person_id"), "to": target, "reason": reason})
        else:
            from consolidation_service import assign_mentor
            enrollment = await db.process_enrollments.find_one({"enrollment_id": item.id}, {"_id": 0})
            if not enrollment or enrollment.get("mentor_person_id") == target:
                skipped.append(item.id)
                continue
            await assign_mentor(db, enrollment, target, current_user["user_id"], reason, transfer=True)  # historial en mentor_assignments
        done.append(item.model_dump())
    if done:
        from portal_notifications import notify_persons
        await notify_persons([target], "my_work_reassigned", "Te asignaron pendientes", f"Te asignaron {len(done)} pendiente(s) en Mi Trabajo. Motivo: {reason}", "/mi-trabajo",
                             {"type": "my_work_reassign", "count": len(done)})
    return {"reassigned": len(done), "skipped": skipped, "to_mentor_person_id": target}


# ------------------------------------------------------------------ trabajo completo (no solo pendientes)
BOOK_TYPES = ["DELIVERY", "LOAN", "DELIVERY_PENDING"]
STATUS_LABELS = {"consolidation": "En Consolidación", "followup": "Seguimiento aceptado", "contacted": "Contactada"}


def empty_totals() -> dict:
    return {"houses_visited": 0, "people_contacted": 0, "books_delivered": 0, "inventory": {"received": 0, "delivered": 0, "available": 0}}


async def _mentor_users(mentor_ids: list[str]) -> dict:
    """{person_id: user_id} de las cuentas de los mentores."""
    return {doc["person_id"]: str(doc["_id"]) async for doc in db.users.find({"person_id": {"$in": mentor_ids}}, {"_id": 1, "person_id": 1})}


def _latest(current, value) -> Optional[str]:
    values = [item for item in (current, serialize(value)) if item]
    return max(str(item) for item in values) if values else None


def _visit_person(visit: dict) -> Optional[str]:
    return visit.get("converted_person_id") or visit.get("person_id")


async def mentor_totals(mentor_ids: list[str], campaign_id: Optional[str] = None) -> dict:
    """Totales reales por mentor: viviendas visitadas (incluidas visitas antiguas
    sin vivienda), personas contactadas o con libro, libros e inventario."""
    from library_ledger import ledger_balances
    if not mentor_ids:
        return {}
    users = await _mentor_users(mentor_ids)
    person_of_user = {user_id: pid for pid, user_id in users.items()}
    scope = {"campaign_id": campaign_id} if campaign_id else {}
    result = {pid: {**empty_totals(), "_people": set()} for pid in mentor_ids}
    async for row in db.outreach_households.aggregate([{"$match": {"mentor_person_id": {"$in": mentor_ids}, "archived": {"$ne": True}, "attempts_count": {"$gt": 0}, **scope}},
                                                        {"$group": {"_id": "$mentor_person_id", "n": {"$sum": 1}}}]):
        result[row["_id"]]["houses_visited"] += row["n"]
    async for visit in db.outreach_visits.find({"mentor_person_id": {"$in": mentor_ids}, "archived": {"$ne": True}, **scope},
                                               {"_id": 0, "visit_id": 1, "mentor_person_id": 1, "person_id": 1, "converted_person_id": 1, "household_id": 1, "status": 1, "received_mcd": 1, "received_npt": 1}):
        result[visit["mentor_person_id"]]["_people"].add(_visit_person(visit) or f"visit:{visit['visit_id']}")
        if not visit.get("household_id") and (visit.get("status") != "assigned" or visit.get("received_mcd") or visit.get("received_npt")):
            result[visit["mentor_person_id"]]["houses_visited"] += 1  # visita antigua sin vivienda
    async for enrollment in db.process_enrollments.find({"mentor_person_id": {"$in": mentor_ids}, "process_key": "consolidation", "status": {"$in": ACTIVE_ENROLLMENT}, **scope}, {"_id": 0, "mentor_person_id": 1, "person_id": 1}):
        result[enrollment["mentor_person_id"]]["_people"].add(enrollment["person_id"])
    if users:
        movement_match = {"from_holder.type": "user", "from_holder.id": {"$in": list(users.values())}, "movement_type": {"$in": BOOK_TYPES}, "is_reversal": {"$ne": True}, "person_id": {"$nin": [None, ""]}, **scope}
        async for movement in db.library_movements.find(movement_match, {"_id": 0, "from_holder": 1, "person_id": 1}):
            pid = person_of_user.get(movement["from_holder"]["id"])
            if pid:
                result[pid]["_people"].add(movement["person_id"])
        for (user_id, _book), row in (await ledger_balances(list(users.values()))).items():
            pid = person_of_user.get(user_id)
            if not pid:
                continue
            inventory = result[pid]["inventory"]
            inventory["received"] += row.get("received", 0) + row.get("transferred_in", 0)
            inventory["delivered"] += row.get("delivered", 0) + row.get("pending_delivered", 0)
            inventory["available"] += max(row.get("balance", 0), 0)
    for pid, row in result.items():
        row["people_contacted"] = len(row.pop("_people"))
        # Libros: los de la invasión filtrada, o el total del inventario.
        row["books_delivered"] = row["inventory"]["delivered"]
    if campaign_id and users:
        counted = {pid: 0 for pid in mentor_ids}
        async for movement in db.library_movements.find({"from_holder.type": "user", "from_holder.id": {"$in": list(users.values())}, "movement_type": {"$in": BOOK_TYPES}, "is_reversal": {"$ne": True}, "campaign_id": campaign_id}, {"_id": 0, "from_holder": 1, "quantity": 1}):
            pid = person_of_user.get(movement["from_holder"]["id"])
            if pid:
                counted[pid] += movement.get("quantity") or 1
        for pid in mentor_ids:
            result[pid]["books_delivered"] = counted[pid]
    return result


async def people_rows(mentor: str, campaign_id: Optional[str] = None) -> list[dict]:
    """TODAS las personas del mentor: visitas (también las antiguas), destinatarios
    de sus libros y expedientes de Consolidación, cada una una vez y con su estado."""
    zone = await _zone()
    scope = {"campaign_id": campaign_id} if campaign_id else {}
    rows: dict[str, dict] = {}

    def row_for(key: str) -> dict:
        return rows.setdefault(key, {"kind": "contact_person", "id": key, "person_id": None if key.startswith("visit:") else key, "visit_id": None, "enrollment_id": None,
                                     "contact_name": None, "status": "contacted", "books": 0, "last_at": None, "due_date": None, "next_action": None,
                                     "campaign_id": None, "address": None, "household_id": None, "visit_status": None})

    async for visit in db.outreach_visits.find({"mentor_person_id": mentor, "archived": {"$ne": True}, **scope}, {"_id": 0}).sort("created_at", 1):
        row = row_for(_visit_person(visit) or f"visit:{visit['visit_id']}")
        row.update({"visit_id": visit["visit_id"], "contact_name": row["contact_name"] or visit.get("contact_name"), "campaign_id": row["campaign_id"] or visit.get("campaign_id"),
                    "address": row["address"] or " · ".join(filter(None, [visit.get("address_line1"), visit.get("address_line2")])) or visit.get("contact_zone"),
                    "household_id": row["household_id"] or visit.get("household_id"), "visit_status": visit.get("status"),
                    "last_at": _latest(row["last_at"], visit.get("visit_date") or visit.get("created_at"))})
        if visit.get("received_mcd") or visit.get("received_npt"):
            row["books"] = max(row["books"], int(bool(visit.get("received_mcd"))) + int(bool(visit.get("received_npt"))))
        if visit.get("enrollment_id"):
            row.update({"status": "consolidation", "enrollment_id": visit["enrollment_id"]})
        elif row["status"] != "consolidation" and (visit.get("followup_accepted") or visit.get("status") == "wants_followup"):
            row["status"] = "followup"
        if visit.get("next_action_at") and not visit.get("enrollment_id"):
            row.update({"due_date": _local_day(visit["next_action_at"], zone), "next_action": visit.get("next_action")})
    user = await db.users.find_one({"person_id": mentor}, {"_id": 1})
    if user:
        async for movement in db.library_movements.find({"from_holder.type": "user", "from_holder.id": str(user["_id"]), "movement_type": {"$in": BOOK_TYPES}, "is_reversal": {"$ne": True},
                                                         "person_id": {"$nin": [None, ""]}, **scope}, {"_id": 0, "person_id": 1, "quantity": 1, "occurred_at": 1, "campaign_id": 1}):
            row = row_for(movement["person_id"])
            row["_logged"] = row.get("_logged", 0) + (movement.get("quantity") or 1)
            row["campaign_id"] = row["campaign_id"] or movement.get("campaign_id")
            row["last_at"] = _latest(row["last_at"], movement.get("occurred_at"))
    async for enrollment in db.process_enrollments.find({"mentor_person_id": mentor, "process_key": "consolidation", "status": {"$in": ACTIVE_ENROLLMENT}, **scope},
                                                        {"_id": 0, "enrollment_id": 1, "person_id": 1, "next_action": 1, "next_action_at": 1, "current_stage_key": 1, "campaign_id": 1}):
        row = row_for(enrollment["person_id"])
        row.update({"status": "consolidation", "enrollment_id": enrollment["enrollment_id"], "due_date": _local_day(enrollment.get("next_action_at"), zone),
                    "next_action": enrollment.get("next_action"), "stage": STAGE_LABELS.get(enrollment.get("current_stage_key"), enrollment.get("current_stage_key")),
                    "campaign_id": row["campaign_id"] or enrollment.get("campaign_id")})
    # Una persona con expediente activo con OTRO mentor también figura «En Consolidación».
    person_ids = [row["person_id"] for row in rows.values() if row["person_id"]]
    async for enrollment in db.process_enrollments.find({"person_id": {"$in": person_ids}, "process_key": "consolidation", "status": {"$in": ACTIVE_ENROLLMENT}}, {"_id": 0, "enrollment_id": 1, "person_id": 1}):
        row = rows[enrollment["person_id"]]
        if row["status"] != "consolidation":
            row.update({"status": "consolidation", "enrollment_id": enrollment["enrollment_id"]})
    campaign_ids = list({row["campaign_id"] for row in rows.values() if row["campaign_id"]})
    names = {doc["campaign_id"]: doc.get("name") async for doc in db.outreach_campaigns.find({"campaign_id": {"$in": campaign_ids}}, {"_id": 0, "campaign_id": 1, "name": 1})} if campaign_ids else {}
    items = []
    for row in rows.values():
        # Libros: la bitácora manda; las marcas de la visita (MCD/NPT) cubren lo que no se registró.
        row["books"] = max(row["books"], row.pop("_logged", 0))
        row["title"] = (await person_display_name(row["person_id"]) if row["person_id"] else None) or row["contact_name"] or "Persona contactada"
        row["campaign_name"] = names.get(row["campaign_id"])
        label = STATUS_LABELS[row["status"]]
        if row["status"] == "contacted" and not row["due_date"]:
            label = "Contactada · sin próxima atención"
        row["status_label"] = label
        # Programar = seguimiento de la visita; Pasar a Consolidación = «Iniciar 7 Semanas» (visita con seguimiento aceptado).
        row["can_schedule"] = bool(row["visit_id"]) and row["status"] != "consolidation"
        # «Pasar a Consolidación» desde cualquier visita hecha o pendiente (no si no la encontraron o la rechazó).
        row["can_start_consolidation"] = bool(row["visit_id"]) and row["status"] != "consolidation" and row["visit_status"] not in ("rejected", "not_found")
        items.append(row)
    order = {"contacted": 0, "followup": 1, "consolidation": 2}
    items.sort(key=lambda row: (order[row["status"]], row["due_date"] or "9999", row["title"]))
    return serialize(items)


@router.get("/people", response_model=dict)
async def my_work_people(status: Literal["all", "contacted", "followup", "consolidation", "no_next"] = "all", campaign_id: Optional[str] = None,
                         mentor_person_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """«Mis personas»: todas (contactadas, con seguimiento o en Consolidación)."""
    mentor = scope_mentor(current_user, mentor_person_id)
    items = await people_rows(mentor, campaign_id)
    counts = {key: sum(1 for row in items if row["status"] == key) for key in STATUS_LABELS}
    counts["no_next"] = sum(1 for row in items if not row["due_date"])
    if status == "no_next":
        items = [row for row in items if not row["due_date"]]
    elif status != "all":
        items = [row for row in items if row["status"] == status]
    return {"total": len(items), "counts": counts, "items": items}


@router.get("/households", response_model=dict)
async def my_work_households(state: Literal["pending", "visited", "all"] = "all", campaign_id: Optional[str] = None, mentor_person_id: Optional[str] = None,
                             offset: int = 0, limit: int = 100, current_user: dict = Depends(get_current_user)):
    """«Mis viviendas»: pendientes, visitadas o todas (incluidas visitas antiguas sin vivienda)."""
    mentor = scope_mentor(current_user, mentor_person_id)
    query: dict = {"mentor_person_id": mentor, "archived": {"$ne": True}}
    if campaign_id:
        query["campaign_id"] = campaign_id
    if state == "pending":
        query["door_status"] = {"$in": PENDING_DOORS}
    elif state == "visited":
        query["attempts_count"] = {"$gt": 0}
    keys = {"_id": 0, "household_id": 1, "address_line1": 1, "address_line2": 1, "door_status": 1, "last_result": 1, "last_attempt_at": 1, "attempts_count": 1,
            "followup_date": 1, "campaign_id": 1, "books_total": 1, "created_at": 1}
    houses = await db.outreach_households.find(query, keys).to_list(5000)
    rows = [{**house, "kind": "household", "id": house["household_id"], "title": " · ".join(filter(None, [house.get("address_line1"), house.get("address_line2")])) or "Vivienda",
             "pending": house.get("door_status") in PENDING_DOORS, "last_result_label": RESULT_LABELS.get(house.get("last_result"), house.get("last_result"))} for house in houses]
    if state != "pending":
        legacy = {"mentor_person_id": mentor, "archived": {"$ne": True}, "household_id": {"$in": [None, ""]}, **({"campaign_id": campaign_id} if campaign_id else {})}
        async for visit in db.outreach_visits.find(legacy, {"_id": 0}):
            visited = visit.get("status") != "assigned" or visit.get("received_mcd") or visit.get("received_npt")
            if state == "visited" and not visited:
                continue
            rows.append({"kind": "visit", "id": visit["visit_id"], "visit_id": visit["visit_id"], "title": " · ".join(filter(None, [visit.get("address_line1"), visit.get("address_line2")])) or visit.get("contact_zone") or visit.get("contact_name") or "Visita",
                         "campaign_id": visit.get("campaign_id"), "attempts_count": 1 if visited else 0, "last_attempt_at": visit.get("visit_date") or visit.get("created_at"),
                         "last_result_label": "Visita registrada (Hogar)" if visited else "Asignada", "books_total": int(bool(visit.get("received_mcd"))) + int(bool(visit.get("received_npt"))), "pending": False})
    ids = list({row["campaign_id"] for row in rows if row.get("campaign_id")})
    names = {doc["campaign_id"]: doc.get("name") async for doc in db.outreach_campaigns.find({"campaign_id": {"$in": ids}}, {"_id": 0, "campaign_id": 1, "name": 1})} if ids else {}
    for row in rows:
        row["campaign_name"] = names.get(row.get("campaign_id"))
    rows = sorted(rows, key=lambda row: str(serialize(row.get("last_attempt_at")) or ""), reverse=True)
    rows.sort(key=lambda row: not row["pending"])
    limit = max(1, min(limit, 200))
    return {"total": len(rows), "items": serialize(rows[offset:offset + limit])}


# ------------------------------------------------------------------ transferencias de Consolidación
class TransferDecision(BaseModel):
    mentor_person_id: Optional[str] = Field(default=None, max_length=80)  # equipo: el encargado elige el mentor
    reason: Optional[str] = Field(default=None, max_length=300)


@router.get("/transfers", response_model=dict)
async def my_transfers(current_user: dict = Depends(get_current_user)):
    """Personas que te quieren transferir (y, a quien supervisa, las pedidas al equipo de Consolidación)."""
    me = current_user.get("person_id")
    targets = [{"transfer_request.to_person_id": me}] if me else []
    if can_supervise(current_user):
        targets.append({"transfer_request.to_team": True})
    if not targets:
        return {"items": []}
    items = []
    async for enrollment in db.process_enrollments.find({"transfer_request.status": "pending", "$or": targets}, {"_id": 0}).sort("transfer_request.requested_at", 1):
        request = enrollment["transfer_request"]
        origin = enrollment.get("origin") or {}
        items.append({"enrollment_id": enrollment["enrollment_id"], "person_id": enrollment["person_id"], "person_name": await person_display_name(enrollment["person_id"]) or "Persona",
                      "to_team": bool(request.get("to_team")), "from_mentor_name": await person_display_name(request.get("from_mentor_person_id")),
                      "requested_by_name": await person_display_name(request.get("requested_by_person_id")), "requested_at": request.get("requested_at"), "note": request.get("note"),
                      "campaign_name": origin.get("campaign_name"), "address": origin.get("address"), "books": origin.get("books") or []})
    return {"items": serialize(items)}


async def _pending_transfer(enrollment_id: str, current_user: dict) -> tuple[dict, dict]:
    enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    request = (enrollment or {}).get("transfer_request") or {}
    if request.get("status") != "pending":
        raise HTTPException(status_code=404, detail="No hay una transferencia pendiente para esta persona")
    if not (request.get("to_person_id") == current_user.get("person_id") or can_supervise(current_user)):
        raise HTTPException(status_code=403, detail="Esta transferencia es para otra persona")
    return enrollment, request


@router.post("/transfers/{enrollment_id}/accept", response_model=dict)
async def accept_transfer(enrollment_id: str, payload: Optional[TransferDecision] = None, current_user: dict = Depends(get_current_user)):
    """Aceptar: la persona pasa al nuevo mentor (con historial). Quien la visitó sigue como «Contactado por»."""
    from consolidation_service import assert_mentor_eligible, assign_mentor
    from portal_notifications import notify_persons, notify_users
    payload = payload or TransferDecision()
    enrollment, request = await _pending_transfer(enrollment_id, current_user)
    target = request.get("to_person_id") or payload.mentor_person_id
    if not target:
        raise HTTPException(status_code=422, detail="Elija el mentor que le dará seguimiento")
    await assert_mentor_eligible(db, target)
    name = await person_display_name(enrollment["person_id"]) or "La persona"
    await assign_mentor(db, enrollment, target, current_user["user_id"], payload.reason or "Transferencia aceptada desde «Pasar a Consolidación»", transfer=True)
    now = datetime.now(timezone.utc)
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {"transfer_request.status": "accepted", "transfer_request.decided_at": now,
                                                                                        "transfer_request.decided_by_user_id": current_user["user_id"], "transfer_request.to_person_id": target,
                                                                                        "mentor_transfer_required": False, "updated_at": now}})
    target_name = await person_display_name(target)
    if target != current_user.get("person_id"):
        await notify_persons([target], "consolidation_transfer_assigned", f"Te asignaron a {name}", "Ahora le das seguimiento en Consolidación.", f"/procesos/consolidacion/{enrollment_id}",
                             {"enrollment_id": enrollment_id})
    if request.get("requested_by_user_id"):
        await notify_users([request["requested_by_user_id"]], "consolidation_transfer_accepted", f"Transferencia aceptada: {name}", f"{target_name or 'El nuevo mentor'} ahora le da seguimiento.",
                           f"/procesos/consolidacion/{enrollment_id}", {"enrollment_id": enrollment_id})
    return {"accepted": True, "enrollment_id": enrollment_id, "mentor_person_id": target, "mentor_name": target_name}


@router.post("/transfers/{enrollment_id}/decline", response_model=dict)
async def decline_transfer(enrollment_id: str, payload: Optional[TransferDecision] = None, current_user: dict = Depends(get_current_user)):
    """No puede recibirla: sigue con el mentor que la visitó y se avisa a quien la pidió."""
    from portal_notifications import notify_users
    payload = payload or TransferDecision()
    enrollment, request = await _pending_transfer(enrollment_id, current_user)
    now = datetime.now(timezone.utc)
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {"transfer_request.status": "declined", "transfer_request.decided_at": now,
                                                                                        "transfer_request.decided_by_user_id": current_user["user_id"], "transfer_request.decline_reason": payload.reason,
                                                                                        "mentor_transfer_required": False, "updated_at": now}})
    name = await person_display_name(enrollment["person_id"]) or "La persona"
    if request.get("requested_by_user_id"):
        await notify_users([request["requested_by_user_id"]], "consolidation_transfer_declined", f"Transferencia no aceptada: {name}",
                           f"Sigue con su mentor actual.{f' Motivo: {payload.reason}' if payload.reason else ''}", f"/procesos/consolidacion/{enrollment_id}", {"enrollment_id": enrollment_id})
    return {"declined": True, "enrollment_id": enrollment_id}
