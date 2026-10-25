"""Centro de Estadísticas Globales (G1: resumen, Consolidación y asistencia).

Cada cifra sale de la MISMA fuente que su módulo, sin copiar datos:
- Personas: `persons` (Persona 360).
- Consolidación: la misma población y el mismo panorama de
  `consolidation_panorama` (personas únicas, sin archivados).
- Asistencia: `person_attendance` (Persona 360), que ya recibe los check-ins de
  Operaciones y la asistencia de Células; el tipo de servicio sale del día de la
  ocurrencia (domingo / miércoles / actividad especial). Invasiones: asistencia
  por jornada de `invasion_participants`.
- Libros: bitácora `library_movements`. Invasiones: `outreach_campaigns` / `outreach_visits`.
La autoridad pastoral principal y las cuentas de prueba no cuentan en
participación. Cada indicador trae su definición, unidad, fuente y, si no hay
datos, el motivo. Finanzas llega en G2 con su permiso propio."""
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from access_control import CONSOLIDATION_ASSIGN, OPERATIONS_REPORTS, has_capability, is_general_coordinator, is_global_pastoral_authority
from server import db, get_current_user

router = APIRouter(prefix="/api/global-stats", tags=["global-stats"])

PERIODS = ("today", "week", "month", "quarter", "year", "custom")
PERIOD_LABELS = {"today": "Hoy", "week": "Esta semana", "month": "Este mes", "quarter": "Este trimestre", "year": "Este año", "custom": "Rango personalizado"}
SERVICE_LABELS = {"sunday": "Servicio del domingo", "wednesday": "Servicio del miércoles", "special": "Actividades especiales", "cell": "Células", "other": "Otros registros de asistencia"}


# ------------------------------------------------------------------ permisos
def sections_for(current_user: dict) -> dict:
    pastoral = is_global_pastoral_authority(current_user)
    coordinator = is_general_coordinator(current_user)
    consolidation = has_capability(current_user, CONSOLIDATION_ASSIGN)
    return {"summary": pastoral or coordinator, "consolidation": pastoral or coordinator or consolidation,
            "attendance": pastoral or coordinator or has_capability(current_user, OPERATIONS_REPORTS),
            "finance": finance_allowed(current_user),
            "activities": pastoral or coordinator or has_capability(current_user, OPERATIONS_REPORTS),
            "invasions": pastoral or coordinator, "books": pastoral or coordinator, "groups": pastoral or coordinator, "education": pastoral or coordinator}


def finance_allowed(current_user: dict) -> bool:
    """Mismo permiso del módulo Finanzas: autoridad pastoral, o el grupo de
    privilegio de Finanzas + finance.read concedido explícitamente."""
    from finance_engine import require_finance_read
    try:
        require_finance_read(current_user)
        return True
    except HTTPException:
        return False


def require_section(current_user: dict, section: str) -> None:
    if not sections_for(current_user).get(section):
        raise HTTPException(status_code=403, detail="Sin acceso a esta sección de Estadísticas Globales")


# ------------------------------------------------------------------ período
async def resolve(period: str, date_from: Optional[str], date_to: Optional[str]) -> dict:
    """Período en el día local de la iglesia + el período anterior de igual largo."""
    from report_period import report_zone
    zone = await report_zone()
    today = datetime.now(zone).date()
    if period == "today":
        first, last = today, today
    elif period == "week":
        first, last = today - timedelta(days=today.weekday()), today
    elif period == "month":
        first, last = today.replace(day=1), today
    elif period == "quarter":
        first, last = date(today.year, 3 * ((today.month - 1) // 3) + 1, 1), today
    elif period == "year":
        first, last = date(today.year, 1, 1), today
    else:
        try:
            first, last = date.fromisoformat(date_from or ""), date.fromisoformat(date_to or "")
        except ValueError:
            raise HTTPException(status_code=422, detail="Indique las fechas «desde» y «hasta» del rango")
        if last < first:
            raise HTTPException(status_code=422, detail="La fecha «hasta» debe ser posterior a «desde»")
    days = (last - first).days + 1
    prev_last = first - timedelta(days=1)
    prev_first = prev_last - timedelta(days=days - 1)

    def bounds(a: date, b: date) -> tuple[datetime, datetime]:
        return (datetime.combine(a, time.min, tzinfo=zone).astimezone(timezone.utc), datetime.combine(b + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc))
    start, end = bounds(first, last)
    prev_start, prev_end = bounds(prev_first, prev_last)
    return {"key": period, "label": PERIOD_LABELS.get(period, period), "first": first, "last": last, "start": start, "end": end, "days": days,
            "prev_first": prev_first, "prev_last": prev_last, "prev_start": prev_start, "prev_end": prev_end, "zone": zone}


def change_pct(current, previous) -> Optional[float]:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / previous * 100, 1)


def card(key: str, label: str, value, *, previous=None, unit: str = "", definition: str, source: str, empty_reason: Optional[str] = None, link: Optional[str] = None) -> dict:
    empty = value in (None, 0) and empty_reason is not None
    return {"key": key, "label": label, "value": value, "previous": previous, "change_pct": change_pct(value, previous), "unit": unit,
            "definition": definition, "source": source, "empty_reason": empty_reason if empty else None, "link": link}


def period_out(p: dict) -> dict:
    return {"key": p["key"], "label": p["label"], "from": p["first"].isoformat(), "to": p["last"].isoformat(), "days": p["days"],
            "previous_from": p["prev_first"].isoformat(), "previous_to": p["prev_last"].isoformat()}


async def excluded_ids() -> set:
    from report_period import excluded_person_ids
    return await excluded_person_ids()


# ------------------------------------------------------------------ asistencia (fuente: Persona 360)
async def attendance_rows(first: date, last: date, zone) -> list[dict]:
    """Asistencias PRESENTES por persona y día, clasificadas por tipo de servicio."""
    from report_period import local_day
    lo, hi = (first - timedelta(days=1)).isoformat(), (last + timedelta(days=2)).isoformat()
    docs = await db.person_attendance.find({"fecha": {"$gte": lo, "$lt": hi}, "estado": {"$in": ["presente", "present", None]}},
                                           {"_id": 1, "person_id": 1, "fecha": 1, "activity_type": 1, "notas": 1, "actividad": 1, "source_id": 1}).to_list(200000)
    occurrence_ids = {str(doc.get("notas") or "").split("· ")[-1].strip() for doc in docs if str(doc.get("_id", "")).startswith("operation:")}
    occurrences = {item["occurrence_id"]: item async for item in db.operation_event_occurrences.find({"occurrence_id": {"$in": list(occurrence_ids)}}, {"_id": 0, "occurrence_id": 1, "event_id": 1, "starts_at": 1})} if occurrence_ids else {}
    events = {item["event_id"]: item async for item in db.operation_events.find({"event_id": {"$in": list({item["event_id"] for item in occurrences.values()})}}, {"_id": 0, "event_id": 1, "event_type": 1, "title": 1})} if occurrences else {}
    rows = []
    for doc in docs:
        day = local_day(doc.get("fecha"), zone)
        if not day or not (first.isoformat() <= day <= last.isoformat()):
            continue
        kind, session = "other", f"manual:{day}:{doc.get('actividad') or ''}"
        if doc.get("activity_type") == "cell_meeting":
            kind, session = "cell", f"cell:{doc.get('source_id')}"
        elif str(doc.get("_id", "")).startswith("operation:"):
            occurrence = occurrences.get(str(doc.get("notas") or "").split("· ")[-1].strip())
            if occurrence:
                event = events.get(occurrence["event_id"]) or {}
                starts = occurrence["starts_at"] if occurrence["starts_at"].tzinfo else occurrence["starts_at"].replace(tzinfo=timezone.utc)
                weekday = starts.astimezone(zone).weekday()
                kind = "sunday" if event.get("event_type") == "service" and weekday == 6 else ("wednesday" if event.get("event_type") == "service" and weekday == 2 else "special")
                session = f"occurrence:{occurrence['occurrence_id']}"
            else:
                kind = "special"
        rows.append({"person_id": doc.get("person_id"), "day": day, "kind": kind, "session": session})
    return rows


def attendance_figures(rows: list[dict], excluded: set) -> dict:
    rows = [row for row in rows if row["person_id"] and row["person_id"] not in excluded]
    by_kind: dict = {}
    for kind in ("sunday", "wednesday", "special", "cell", "other"):
        items = [row for row in rows if row["kind"] == kind]
        sessions = defaultdict(set)
        for row in items:
            sessions[row["session"]].add(row["person_id"])
        total = sum(len(people) for people in sessions.values())
        by_kind[kind] = {"kind": kind, "label": SERVICE_LABELS[kind], "sessions": len(sessions), "attendance": total,
                         "average": round(total / len(sessions), 1) if sessions else None, "unique_people": len({row["person_id"] for row in items})}
    services = [by_kind[kind] for kind in ("sunday", "wednesday")]
    service_sessions = sum(item["sessions"] for item in services)
    service_total = sum(item["attendance"] for item in services)
    return {"by_kind": by_kind, "unique_people": len({row["person_id"] for row in rows}),
            "service_average": round(service_total / service_sessions, 1) if service_sessions else None, "service_sessions": service_sessions}


# ------------------------------------------------------------------ endpoints
@router.get("/access", response_model=dict)
async def access(current_user: dict = Depends(get_current_user)):
    """Secciones que esta cuenta puede ver (el backend vuelve a validar en cada una)."""
    allowed = sections_for(current_user)
    if not any(allowed.values()):
        raise HTTPException(status_code=403, detail="Las Estadísticas Globales son para la autoridad pastoral, el coordinador general y los encargados con permiso")
    return {"sections": allowed}


@router.get("/summary", response_model=dict)
async def summary(period: Literal["today", "week", "month", "quarter", "year", "custom"] = "month", date_from: Optional[str] = None, date_to: Optional[str] = None,
                  current_user: dict = Depends(get_current_user)):
    require_section(current_user, "summary")
    p = await resolve(period, date_from, date_to)
    excluded = await excluded_ids()
    persons_total = await db.persons.count_documents({"is_archived": {"$ne": True}})
    new_now = await db.persons.count_documents({"is_archived": {"$ne": True}, "created_at": {"$gte": p["start"], "$lt": p["end"]}})
    new_prev = await db.persons.count_documents({"is_archived": {"$ne": True}, "created_at": {"$gte": p["prev_start"], "$lt": p["prev_end"]}})
    rows_now, rows_prev = await attendance_rows(p["first"], p["last"], p["zone"]), await attendance_rows(p["prev_first"], p["prev_last"], p["zone"])
    att_now, att_prev = attendance_figures(rows_now, excluded), attendance_figures(rows_prev, excluded)
    campaigns_now = await db.outreach_campaigns.count_documents({"start_date": {"$lte": p["last"].isoformat()}, "$or": [{"end_date": {"$gte": p["first"].isoformat()}}, {"end_date": None, "start_date": {"$gte": p["first"].isoformat()}}], "archived": {"$ne": True}})
    reached_now = await db.outreach_visits.count_documents({"archived": {"$ne": True}, "created_at": {"$gte": p["start"], "$lt": p["end"]}, "mentor_person_id": {"$nin": list(excluded)}})
    reached_prev = await db.outreach_visits.count_documents({"archived": {"$ne": True}, "created_at": {"$gte": p["prev_start"], "$lt": p["prev_end"]}, "mentor_person_id": {"$nin": list(excluded)}})

    async def books(start, end) -> int:
        total = 0
        async for item in db.library_movements.find({"movement_type": {"$in": ["DELIVERY", "LOAN", "DELIVERY_PENDING"]}, "is_reversal": {"$ne": True}, "occurred_at": {"$gte": start, "$lt": end}}, {"_id": 0, "quantity": 1}):
            total += item.get("quantity") or 1
        return total

    async def baptisms(a: date, b: date) -> int:
        return await db.person_baptisms.count_documents({"baptized": True, "baptism_date": {"$gte": a.isoformat(), "$lte": b.isoformat()}})
    from consolidation_panorama import load_population
    _, population, _ = await load_population(current_user, None, None, None, None)

    def created_between(start, end) -> int:
        from consolidation_panorama import aware
        return sum(1 for item in population if aware(item.get("created_at")) and start <= aware(item.get("created_at")) < end)
    cards = [
        card("persons_total", "Personas en Persona 360", persons_total, unit="personas", definition="Todas las personas registradas en Persona 360 que no han sido eliminadas del directorio.", source="Persona 360", link="/personas"),
        card("persons_new", "Personas nuevas", new_now, previous=new_prev, unit="personas", definition="Personas registradas por primera vez en Persona 360 dentro del período.", source="Persona 360", empty_reason="No se registraron personas nuevas en este período."),
        card("active_people", "Personas que asistieron", att_now["unique_people"], previous=att_prev["unique_people"], unit="personas", definition="Personas distintas con al menos una asistencia registrada (servicios, actividades o células) en el período. No incluye a la pastora ni cuentas de prueba.", source="Asistencia de Persona 360 (incluye Operaciones y Células)", empty_reason="Aún no se ha registrado asistencia en este período."),
        card("service_average", "Asistencia promedio por servicio", att_now["service_average"], previous=att_prev["service_average"], unit="personas por servicio", definition="Asistentes de los servicios de domingo y miércoles ÷ número de servicios con asistencia registrada.", source="Check-ins de Operaciones", empty_reason="Aún no se ha tomado asistencia de servicios (domingo o miércoles) en este período."),
        card("consolidation_new", "Nuevas en Consolidación", created_between(p["start"], p["end"]), previous=created_between(p["prev_start"], p["prev_end"]), unit="personas", definition="Personas cuyo expediente de Consolidación se abrió en el período (personas únicas).", source="Consolidación", empty_reason="No se abrieron expedientes de Consolidación en este período.", link="/procesos/consolidacion"),
        card("invasions", "Invasiones del período", campaigns_now, unit="invasiones", definition="Invasiones cuyas fechas caen, aunque sea en parte, dentro del período.", source="Invasiones", empty_reason="No hubo invasiones en este período.", link="/mentoria/visitas"),
        card("people_reached", "Personas alcanzadas en invasiones", reached_now, previous=reached_prev, unit="personas", definition="Contactos registrados por los mentores en las visitas de invasión durante el período (sin cuentas de prueba).", source="Invasiones (visitas)", empty_reason="No se registraron personas alcanzadas en este período."),
        card("books", "Libros entregados", await books(p["start"], p["end"]), previous=await books(p["prev_start"], p["prev_end"]), unit="libros", definition="Libros entregados o prestados a personas en el período, según la bitácora de Librería (incluye entregas por conciliar).", source="Librería 360 (bitácora)", empty_reason="No se entregaron libros en este período.", link="/libreria/recorrido"),
        card("baptisms", "Bautismos", await baptisms(p["first"], p["last"]), previous=await baptisms(p["prev_first"], p["prev_last"]), unit="personas", definition="Personas marcadas como bautizadas con fecha de bautismo dentro del período.", source="Bautismos", empty_reason="No hay bautismos registrados con fecha en este período.", link="/bautismos"),
    ]
    finance_ok = finance_allowed(current_user)
    if finance_ok:
        from finance_engine import audit
        await audit(current_user["user_id"], "global_stats_finance_viewed", "global_stats", "summary", {"from": p["first"].isoformat(), "to": p["last"].isoformat()})
        received_now = sum((await contributions_by_type(p["first"], p["last"])).values())
        received_prev = sum((await contributions_by_type(p["prev_first"], p["prev_last"])).values())
        cards.insert(4, card("received", "Ingresos recibidos", money(received_now), previous=money(received_prev), unit="USD", definition="Todas las contribuciones con fecha de recibido en el período (diezmos, ofrendas, proyectos y otros), sin las corregidas. Solo el total.", source="Finanzas · contribuciones", empty_reason="Aún no se han registrado contribuciones en este período.", link="/estadisticas?seccion=finance"))
    return {"period": period_out(p), "cards": cards, "finance_available": finance_ok,
            "finance_note": None if finance_ok else "Los ingresos (diezmos, ofrendas, proyectos) solo se muestran con permiso de Finanzas."}


@router.get("/consolidation", response_model=dict)
async def consolidation(period: Literal["today", "week", "month", "quarter", "year", "custom"] = "month", date_from: Optional[str] = None, date_to: Optional[str] = None,
                        front_group_id: Optional[str] = None, campaign_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Embudo, etapas, alertas y carga por mentor: la MISMA población del panorama de Consolidación."""
    require_section(current_user, "consolidation")
    from consolidation_panorama import STAGE_LABELS, aware, panorama
    p = await resolve(period, date_from, date_to)
    base = await panorama(period="all", campaign_id=campaign_id, mentor_person_id=None, front_group_id=front_group_id, stage_key=None, current_user=current_user)
    from consolidation_panorama import load_population
    _, items, _ = await load_population(current_user, campaign_id, None, front_group_id, None)
    created = [aware(item.get("created_at")) for item in items]
    new_now = sum(1 for value in created if value and p["start"] <= value < p["end"])
    new_prev = sum(1 for value in created if value and p["prev_start"] <= value < p["prev_end"])
    statuses = Counter(item.get("status") for item in items)
    graduated = statuses.get("completed", 0)
    withdrawn = sum(count for status, count in statuses.items() if status not in {"active", "planned", "paused", "completed"})
    # Tiempo promedio por etapa: etapas cerradas (apertura → cierre) de estos expedientes.
    durations: dict = defaultdict(list)
    ids = [item["enrollment_id"] for item in items]
    if ids:
        async for stage in db.process_stage_progress.find({"enrollment_id": {"$in": ids}, "status": "completed", "opened_at": {"$ne": None}, "completed_at": {"$ne": None}}, {"_id": 0, "stage_key": 1, "opened_at": 1, "completed_at": 1}):
            opened, closed = aware(stage.get("opened_at")), aware(stage.get("completed_at"))
            if opened and closed and closed >= opened:
                durations[stage["stage_key"]].append((closed - opened).total_seconds() / 86400)
    stage_times = [{"stage_key": key, "label": STAGE_LABELS.get(key, key), "average_days": round(sum(values) / len(values), 1), "completed": len(values)} for key, values in durations.items() if key in STAGE_LABELS]
    order = list(STAGE_LABELS)
    stage_times.sort(key=lambda row: order.index(row["stage_key"]))
    # Por Grupo Frontal (personas activas por grupo del expediente).
    group_counts = Counter(item.get("front_group_id") for item in items if item.get("status") == "active")
    names = {doc["front_group_id"]: doc.get("name") async for doc in db.front_groups.find({"front_group_id": {"$in": [key for key in group_counts if key]}}, {"_id": 0, "front_group_id": 1, "name": 1})}
    by_group = sorted(({"front_group_id": key, "name": names.get(key) or ("Sin Grupo Frontal" if not key else "Grupo sin nombre"), "active": value} for key, value in group_counts.items()), key=lambda row: -row["active"])
    figures = base["figures"]
    cards = [
        card("total", "Personas en Consolidación", figures["total"], unit="personas", definition="Personas únicas con expediente de Consolidación (activo, en pausa o terminado); un expediente repetido de la misma persona no cuenta dos veces.", source="Consolidación", empty_reason="Todavía no hay expedientes de Consolidación.", link="/procesos/consolidacion"),
        card("active", "Activas ahora", figures["active"], unit="personas", definition="Expedientes con estado activo.", source="Consolidación", empty_reason="No hay expedientes activos."),
        card("new", "Nuevas en el período", new_now, previous=new_prev, unit="personas", definition="Expedientes abiertos dentro del período.", source="Consolidación", empty_reason="No se abrieron expedientes en este período."),
        card("graduated", "Terminaron el proceso", graduated, unit="personas", definition="Expedientes con estado «completado» (pasaron todas las etapas).", source="Consolidación", empty_reason="Todavía nadie ha terminado el proceso."),
        card("withdrawn", "Retiradas o cerradas sin terminar", withdrawn, unit="personas", definition="Expedientes cerrados sin completar (cancelados o retirados), sin contar los archivados.", source="Consolidación", empty_reason="No hay expedientes retirados."),
        card("unattended", "Sin atender", figures["unattended"], unit="personas", definition=f"Expedientes activos con más de {base['unattended_hours']} horas sin ninguna actividad realizada.", source="Consolidación", empty_reason="Nadie lleva más de 48 horas sin atención."),
        card("no_next_action", "Sin próxima acción", figures["no_next_action"], unit="personas", definition="Expedientes activos sin fecha de próxima acción programada.", source="Consolidación", empty_reason="Todos los expedientes activos tienen próxima acción."),
        card("first_contact", "Primer contacto (promedio)", figures["first_contact_avg_hours"], unit="horas", definition="Horas desde que se abrió el expediente hasta la primera actividad realizada (promedio).", source="Consolidación (actividades)", empty_reason="Aún no hay primeras actividades registradas."),
    ]
    return {"period": period_out(p), "cards": cards, "funnel": base["funnel"], "by_stage": base["by_stage"], "stage_times": stage_times,
            "mentor_load": base["mentor_load"], "by_group": by_group, "by_campaign": base["by_campaign"], "trend": base["trend"],
            "notes": {"funnel": "Personas que alcanzaron al menos cada paso (personas únicas, toda la historia).", "stage_times": "Días promedio entre la apertura y el cierre de cada etapa ya cerrada."}}


@router.get("/attendance", response_model=dict)
async def attendance(period: Literal["today", "week", "month", "quarter", "year", "custom"] = "month", date_from: Optional[str] = None, date_to: Optional[str] = None,
                     service: Literal["all", "sunday", "wednesday", "special", "cell"] = "all", current_user: dict = Depends(get_current_user)):
    require_section(current_user, "attendance")
    p = await resolve(period, date_from, date_to)
    excluded = await excluded_ids()
    rows_now = await attendance_rows(p["first"], p["last"], p["zone"])
    rows_prev = await attendance_rows(p["prev_first"], p["prev_last"], p["zone"])
    if service != "all":
        rows_now = [row for row in rows_now if row["kind"] == service]
        rows_prev = [row for row in rows_prev if row["kind"] == service]
    now, prev = attendance_figures(rows_now, excluded), attendance_figures(rows_prev, excluded)
    # Tendencia: 12 semanas hasta el final del período.
    week_end = p["last"]
    week_start = week_end - timedelta(days=week_end.weekday()) - timedelta(weeks=11)
    trend_rows = [row for row in await attendance_rows(week_start, week_end, p["zone"]) if row["person_id"] and row["person_id"] not in excluded and (service == "all" or row["kind"] == service)]
    trend = []
    for index in range(12):
        begin = week_start + timedelta(weeks=index)
        stop = begin + timedelta(days=6)
        items = [row for row in trend_rows if begin.isoformat() <= row["day"] <= stop.isoformat()]
        point = {"week": begin.isoformat(), "label": f"{begin.day}/{begin.month}"}
        for kind in ("sunday", "wednesday", "special", "cell"):
            sessions = defaultdict(set)
            for row in items:
                if row["kind"] == kind:
                    sessions[row["session"]].add(row["person_id"])
            point[kind] = sum(len(people) for people in sessions.values())
        trend.append(point)
    # Nuevos vs recurrentes: «nuevo» = su PRIMERA asistencia registrada cae en el período.
    people_now = {row["person_id"] for row in rows_now if row["person_id"] and row["person_id"] not in excluded}
    first_seen: dict = {}
    if people_now:
        from report_period import local_day
        async for doc in db.person_attendance.find({"person_id": {"$in": list(people_now)}, "estado": {"$in": ["presente", "present", None]}}, {"_id": 0, "person_id": 1, "fecha": 1}):
            day = local_day(doc.get("fecha"), p["zone"])
            if day and (doc["person_id"] not in first_seen or day < first_seen[doc["person_id"]]):
                first_seen[doc["person_id"]] = day
    newcomers = sum(1 for person in people_now if first_seen.get(person, "9999") >= p["first"].isoformat())
    # Ausentes frecuentes: asistían (3+ veces en las 8 semanas anteriores) y no han venido en las últimas 3.
    recent_from = p["last"] - timedelta(weeks=3) + timedelta(days=1)
    before_from = recent_from - timedelta(weeks=8)
    history = [row for row in await attendance_rows(before_from, p["last"], p["zone"]) if row["person_id"] and row["person_id"] not in excluded and row["kind"] in {"sunday", "wednesday", "cell"}]
    before = Counter(row["person_id"] for row in history if row["day"] < recent_from.isoformat())
    recent = {row["person_id"] for row in history if row["day"] >= recent_from.isoformat()}
    absent_ids = [person for person, count in before.items() if count >= 3 and person not in recent]
    from mentorship_outreach import person_display_name
    absent = [{"person_id": person, "name": await person_display_name(person) or "Persona", "previous_attendance": before[person]} for person in absent_ids[:60]]
    absent.sort(key=lambda row: -row["previous_attendance"])
    invasions = await invasion_attendance(p, excluded)
    cards = [
        card("unique_people", "Personas que asistieron", now["unique_people"], previous=prev["unique_people"], unit="personas", definition="Personas distintas con al menos una asistencia en el período (servicios, actividades y células).", source="Asistencia de Persona 360", empty_reason="Aún no se ha registrado asistencia en este período."),
        card("service_average", "Promedio por servicio", now["service_average"], previous=prev["service_average"], unit="personas por servicio", definition="Asistentes de domingo y miércoles ÷ servicios con asistencia registrada.", source="Check-ins de Operaciones", empty_reason="Aún no se ha tomado asistencia de servicios en este período."),
        card("newcomers", "Asistieron por primera vez", newcomers, unit="personas", definition="Personas cuya primera asistencia registrada en la plataforma cae dentro del período.", source="Asistencia de Persona 360", empty_reason="Nadie asistió por primera vez en este período."),
        card("returning", "Recurrentes", len(people_now) - newcomers if people_now else 0, unit="personas", definition="Personas que asistieron en el período y ya tenían asistencias anteriores.", source="Asistencia de Persona 360", empty_reason="No hay asistencias en este período."),
        card("frequent_absent", "Ausentes frecuentes", len(absent_ids), unit="personas", definition="Personas que asistieron 3 o más veces en las 8 semanas anteriores y no han venido en las últimas 3 semanas (servicios y células).", source="Asistencia de Persona 360", empty_reason="No hay personas que hayan dejado de asistir."),
    ]
    return {"period": period_out(p), "service": service, "cards": cards,
            "by_service": [{**now["by_kind"][kind], "previous_average": prev["by_kind"][kind]["average"], "change_pct": change_pct(now["by_kind"][kind]["average"], prev["by_kind"][kind]["average"])} for kind in ("sunday", "wednesday", "special", "cell", "other")],
            "trend": trend, "frequent_absent": absent, "invasions": invasions,
            "notes": {"service": "El tipo de servicio sale del día de la actividad: los servicios del domingo y del miércoles; el resto son actividades especiales.",
                      "invasions": "Asistencia por jornada de las invasiones (servidores que asistieron cada día)."}}


async def invasion_attendance(p: dict, excluded: set) -> list[dict]:
    rows = []
    async for campaign in db.outreach_campaigns.find({"start_date": {"$lte": p["last"].isoformat()}, "archived": {"$ne": True}}, {"_id": 0, "campaign_id": 1, "name": 1, "start_date": 1, "end_date": 1}).sort("start_date", -1).limit(40):
        if (campaign.get("end_date") or campaign.get("start_date") or "") < p["first"].isoformat():
            continue
        participants = [item async for item in db.invasion_participants.find({"campaign_id": campaign["campaign_id"]}, {"_id": 0, "person_id": 1, "attended_days": 1, "attended": 1}) if item["person_id"] not in excluded]
        days = Counter(day for item in participants for day in (item.get("attended_days") or []) if p["first"].isoformat() <= day <= p["last"].isoformat())
        attended = sum(1 for item in participants if item.get("attended") or any(p["first"].isoformat() <= day <= p["last"].isoformat() for day in item.get("attended_days") or []))
        rows.append({"campaign_id": campaign["campaign_id"], "name": campaign.get("name"), "invited": len(participants), "attended": attended,
                     "attendance_pct": round(attended / len(participants) * 100) if participants else None, "by_day": [{"day": day, "attended": count} for day, count in sorted(days.items())]})
    return rows


# ------------------------------------------------------------------ G2 · Finanzas (permiso propio + auditoría)
TYPE_LABELS = {"tithe": "Diezmos", "offering": "Ofrendas", "donation": "Donaciones", "missions": "Misiones", "building": "Pro-Templo", "project": "Proyectos y campañas", "other": "Otros ingresos"}
money = lambda cents: round((cents or 0) / 100, 2)  # noqa: E731


async def contributions_by_type(first: date, last: date) -> dict:
    """Igual que el reporte «contributions» de Finanzas: sin las corregidas, por fecha de recibido."""
    totals: dict = defaultdict(int)
    async for row in db.finance_contributions.aggregate([
        {"$match": {"status": {"$ne": "corrected"}, "received_date": {"$gte": first.isoformat(), "$lte": last.isoformat()}}},
        {"$unwind": "$allocations"},
        {"$group": {"_id": {"$ifNull": ["$allocations.contribution_type", "$contribution_type"]}, "amount": {"$sum": "$allocations.amount_cents"}}}]):
        totals[row["_id"] or "other"] += row["amount"]
    return dict(totals)


async def income_expense(first: date, last: date) -> dict:
    """Igual que el reporte «income-expense» de Finanzas: asientos contabilizados por fecha contable."""
    result = {"revenue": 0, "expense": 0}
    async for row in db.finance_journal_entries.aggregate([
        {"$match": {"status": "posted", "entry_date": {"$gte": first.isoformat(), "$lte": last.isoformat()}}}, {"$unwind": "$lines"},
        {"$lookup": {"from": "finance_accounts", "localField": "lines.account_id", "foreignField": "account_id", "as": "account"}}, {"$unwind": "$account"},
        {"$group": {"_id": "$account.account_type", "debit": {"$sum": "$lines.debit_cents"}, "credit": {"$sum": "$lines.credit_cents"}}}]):
        if row["_id"] == "revenue":
            result["revenue"] += row["credit"] - row["debit"]
        elif row["_id"] == "expense":
            result["expense"] += row["debit"] - row["credit"]
    return result


@router.get("/finance", response_model=dict)
async def finance(period: Literal["today", "week", "month", "quarter", "year", "custom"] = "month", date_from: Optional[str] = None, date_to: Optional[str] = None,
                  current_user: dict = Depends(get_current_user)):
    """Diezmos, ofrendas, proyectos, gastos y balance: SOLO totales (nunca por
    persona), con el mismo permiso del módulo Finanzas y auditoría de la consulta."""
    if not finance_allowed(current_user):
        raise HTTPException(status_code=403, detail="Las finanzas solo las ve la autoridad pastoral o quien tenga el permiso de Finanzas")
    from finance_engine import audit
    p = await resolve(period, date_from, date_to)
    await audit(current_user["user_id"], "global_stats_finance_viewed", "global_stats", "finance", {"from": p["first"].isoformat(), "to": p["last"].isoformat()})
    now_types, prev_types = await contributions_by_type(p["first"], p["last"]), await contributions_by_type(p["prev_first"], p["prev_last"])
    books_now, books_prev = await income_expense(p["first"], p["last"]), await income_expense(p["prev_first"], p["prev_last"])
    expenses_now: dict = defaultdict(int)
    async for row in db.finance_expenses.aggregate([
        {"$match": {"status": {"$in": ["approved", "payment_pending_posting", "paid"]}, "expense_date": {"$gte": p["first"].isoformat(), "$lte": p["last"].isoformat()}}},
        {"$group": {"_id": {"$ifNull": ["$category", "Sin categoría"]}, "amount": {"$sum": "$total_cents"}}}]):
        expenses_now[row["_id"] or "Sin categoría"] += row["amount"]
    received_now, received_prev = sum(now_types.values()), sum(prev_types.values())
    no_income = "Aún no se han registrado contribuciones en este período."
    cards = [
        card("tithes", "Diezmos", money(now_types.get("tithe")), previous=money(prev_types.get("tithe")), unit="USD", definition="Suma de las contribuciones registradas como Diezmo con fecha de recibido en el período (sin las corregidas). Solo total; nunca por persona.", source="Finanzas · contribuciones", empty_reason="Aún no se han registrado diezmos en este período.", link="/finanzas"),
        card("offerings", "Ofrendas", money(now_types.get("offering")), previous=money(prev_types.get("offering")), unit="USD", definition="Suma de las contribuciones registradas como Ofrenda en el período.", source="Finanzas · contribuciones", empty_reason="Aún no se han registrado ofrendas en este período."),
        card("projects", "Proyectos, campañas y Pro-Templo", money(now_types.get("project", 0) + now_types.get("building", 0)), previous=money(prev_types.get("project", 0) + prev_types.get("building", 0)), unit="USD", definition="Contribuciones a Proyecto/Campaña y Pro-Templo en el período.", source="Finanzas · contribuciones", empty_reason="Aún no se han registrado aportes a proyectos en este período."),
        card("received", "Total recibido", money(received_now), previous=money(received_prev), unit="USD", definition="Todas las contribuciones del período (diezmos, ofrendas, donaciones, misiones, proyectos y otros).", source="Finanzas · contribuciones", empty_reason=no_income),
        card("revenue_posted", "Ingresos contabilizados", money(books_now["revenue"]), previous=money(books_prev["revenue"]), unit="USD", definition="Ingresos de los asientos ya contabilizados con fecha contable en el período (igual que el reporte Ingresos y gastos de Finanzas).", source="Finanzas · libro diario", empty_reason="Aún no hay ingresos contabilizados en este período."),
        card("expenses_posted", "Gastos contabilizados", money(books_now["expense"]), previous=money(books_prev["expense"]), unit="USD", definition="Gastos de los asientos contabilizados con fecha contable en el período.", source="Finanzas · libro diario", empty_reason="Aún no hay gastos contabilizados en este período."),
        card("balance", "Balance del período", money(books_now["revenue"] - books_now["expense"]), previous=money(books_prev["revenue"] - books_prev["expense"]), unit="USD", definition="Ingresos contabilizados − gastos contabilizados del período.", source="Finanzas · libro diario", empty_reason="Aún no hay asientos contabilizados en este período."),
    ]
    # Tendencia: por semana (períodos de hasta 3 meses) o por mes.
    by_month = p["days"] > 93
    buckets: dict = defaultdict(lambda: defaultdict(int))
    async for item in db.finance_contributions.find({"status": {"$ne": "corrected"}, "received_date": {"$gte": p["first"].isoformat(), "$lte": p["last"].isoformat()}}, {"_id": 0, "received_date": 1, "allocations": 1, "contribution_type": 1}):
        day = date.fromisoformat(str(item["received_date"])[:10])
        key = day.strftime("%Y-%m") if by_month else (day - timedelta(days=day.weekday())).isoformat()
        for allocation in item.get("allocations") or []:
            buckets[key][allocation.get("contribution_type") or item.get("contribution_type") or "other"] += allocation.get("amount_cents") or 0
    trend = [{"bucket": key, "label": (f"{key[5:]}/{key[:4]}" if by_month else f"Semana del {int(key[8:])}/{int(key[5:7])}"), **{TYPE_LABELS.get(kind, kind): money(value) for kind, value in values.items()},
              "total": money(sum(values.values()))} for key, values in sorted(buckets.items())]
    # Proyectos (Finanzas): meta, presupuesto, recaudado y gastado (toda su vida).
    projects = []
    async for campaign in db.finance_campaigns.find({}, {"_id": 0}).sort("start_date", -1).limit(100):
        cid = campaign["campaign_id"]
        raised = 0
        async for item in db.finance_contributions.find({"status": {"$ne": "corrected"}, "$or": [{"campaign_id": cid}, {"allocations.campaign_id": cid}]}, {"_id": 0, "campaign_id": 1, "allocations": 1}):
            raised += sum(allocation.get("amount_cents") or 0 for allocation in item.get("allocations") or [] if (allocation.get("campaign_id") or item.get("campaign_id")) == cid)
        spent = 0
        async for row in db.finance_journal_entries.aggregate([{"$match": {"status": "posted", "lines.campaign_id": cid}}, {"$unwind": "$lines"}, {"$match": {"lines.campaign_id": cid}},
                                                               {"$lookup": {"from": "finance_accounts", "localField": "lines.account_id", "foreignField": "account_id", "as": "account"}}, {"$unwind": "$account"},
                                                               {"$match": {"account.account_type": "expense"}}, {"$group": {"_id": None, "debit": {"$sum": "$lines.debit_cents"}, "credit": {"$sum": "$lines.credit_cents"}}}]):
            spent += row["debit"] - row["credit"]
        goal, budget = campaign.get("goal_cents") or 0, campaign.get("budget_cents") or 0
        projects.append({"campaign_id": cid, "name": campaign.get("name"), "type": {"campaign": "Campaña", "project": "Proyecto", "special_destination": "Destino especial"}.get(campaign.get("project_type"), "Campaña"),
                         "status": campaign.get("status"), "goal": money(goal), "raised": money(raised), "goal_pct": round(raised / goal * 100) if goal else None,
                         "budget": money(budget), "spent": money(spent), "budget_pct": round(spent / budget * 100) if budget else None, "start_date": campaign.get("start_date"), "end_date": campaign.get("end_date")})
    return {"period": period_out(p), "cards": cards,
            "by_type": [{"type": kind, "label": TYPE_LABELS.get(kind, kind), "amount": money(value), "previous": money(prev_types.get(kind)), "change_pct": change_pct(value, prev_types.get(kind))} for kind, value in sorted(now_types.items(), key=lambda item: -item[1])],
            "expenses_by_category": [{"label": key, "amount": money(value)} for key, value in sorted(expenses_now.items(), key=lambda item: -item[1])],
            "trend": trend, "trend_unit": "mes" if by_month else "semana", "projects": projects,
            "notes": {"privacy": "Solo se muestran totales. Los diezmos de cada persona nunca aparecen en Estadísticas Globales.",
                      "basis": "«Total recibido» cuenta las contribuciones por fecha de recibido; «Ingresos/Gastos contabilizados» salen del libro diario ya contabilizado, como en los reportes de Finanzas."}}


# ------------------------------------------------------------------ G2 · Actividades (Operaciones)
EVENT_TYPES = {"service": "Servicio", "conference": "Conferencia", "training": "Capacitación", "outreach": "Alcance", "meeting": "Reunión", "other": "Otra actividad"}


@router.get("/activities", response_model=dict)
async def activities(period: Literal["today", "week", "month", "quarter", "year", "custom"] = "month", date_from: Optional[str] = None, date_to: Optional[str] = None,
                     current_user: dict = Depends(get_current_user)):
    """Actividades de Operaciones: realizadas en el período (inscritos, asistentes,
    voluntarios) y próximas 30 días. Mismas colecciones del módulo Operaciones."""
    require_section(current_user, "activities")
    p = await resolve(period, date_from, date_to)
    excluded = await excluded_ids()
    now = datetime.now(timezone.utc)
    occurrences = await db.operation_event_occurrences.find({"starts_at": {"$gte": p["start"], "$lt": p["end"]}, "status": {"$ne": "cancelled"}}, {"_id": 0}).sort("starts_at", 1).to_list(2000)
    upcoming = await db.operation_event_occurrences.find({"starts_at": {"$gte": now, "$lt": now + timedelta(days=30)}, "status": {"$ne": "cancelled"}}, {"_id": 0}).sort("starts_at", 1).to_list(200)
    event_ids = {item["event_id"] for item in occurrences + upcoming}
    events = {item["event_id"]: item async for item in db.operation_events.find({"event_id": {"$in": list(event_ids)}}, {"_id": 0, "event_id": 1, "title": 1, "event_type": 1, "location": 1, "status": 1})} if event_ids else {}
    ids = [item["occurrence_id"] for item in occurrences + upcoming]

    async def count_by(collection: str, match: dict, distinct_person: bool = True) -> dict:
        out: dict = defaultdict(set if distinct_person else int)
        async for item in db[collection].find({"occurrence_id": {"$in": ids}, **match}, {"_id": 0, "occurrence_id": 1, "person_id": 1}):
            if item.get("person_id") in excluded:
                continue
            if distinct_person:
                out[item["occurrence_id"]].add(item.get("person_id") or id(item))
            else:
                out[item["occurrence_id"]] += 1
        return {key: (len(value) if distinct_person else value) for key, value in out.items()}
    registered = await count_by("operation_registrations", {"status": {"$ne": "cancelled"}})
    attended = await count_by("operation_checkins", {"status": "active"})
    volunteers = await count_by("operation_volunteer_assignments", {"status": {"$in": ["invited", "confirmed"]}})
    needed: dict = defaultdict(int)
    async for shift in db.operation_shifts.find({"occurrence_id": {"$in": ids}}, {"_id": 0, "occurrence_id": 1, "required_volunteers": 1}):
        needed[shift["occurrence_id"]] += shift.get("required_volunteers") or 0

    def row(item: dict) -> dict:
        event = events.get(item["event_id"]) or {}
        starts = item["starts_at"] if item["starts_at"].tzinfo else item["starts_at"].replace(tzinfo=timezone.utc)
        return {"occurrence_id": item["occurrence_id"], "title": event.get("title") or "Actividad", "type": EVENT_TYPES.get(event.get("event_type"), "Otra actividad"), "location": event.get("location"),
                "starts_at": starts.astimezone(p["zone"]).strftime("%Y-%m-%d %H:%M"), "registered": registered.get(item["occurrence_id"], 0), "attended": attended.get(item["occurrence_id"], 0),
                "volunteers": volunteers.get(item["occurrence_id"], 0), "volunteers_needed": needed.get(item["occurrence_id"], 0), "capacity": item.get("capacity")}
    done = [row(item) for item in occurrences]
    by_type: dict = defaultdict(lambda: {"activities": 0, "attended": 0})
    for item in done:
        by_type[item["type"]]["activities"] += 1
        by_type[item["type"]]["attended"] += item["attended"]
    total_needed = sum(item["volunteers_needed"] for item in done)
    cards = [
        card("activities", "Actividades realizadas", len(done), unit="actividades", definition="Fechas de actividades de Operaciones (servicios, conferencias, capacitaciones, alcances, reuniones) dentro del período, sin las canceladas.", source="Operaciones", empty_reason="No hay actividades programadas en este período.", link="/operaciones"),
        card("attendance", "Asistentes a actividades", sum(item["attended"] for item in done), unit="asistencias", definition="Check-ins registrados en esas actividades (una persona por actividad).", source="Operaciones · check-in", empty_reason="Aún no se ha tomado asistencia en las actividades de este período."),
        card("registered", "Inscritos", sum(item["registered"] for item in done), unit="inscripciones", definition="Inscripciones activas a esas actividades.", source="Operaciones · inscripciones", empty_reason="No hubo inscripciones en este período."),
        card("volunteer_coverage", "Cobertura de voluntarios", round(sum(min(item["volunteers"], item["volunteers_needed"]) for item in done) / total_needed * 100) if total_needed else None, unit="%", definition="Voluntarios asignados ÷ voluntarios requeridos en los turnos de esas actividades.", source="Operaciones · turnos", empty_reason="No hay turnos de voluntarios con cupo definido en este período."),
        card("upcoming", "Próximas actividades (30 días)", len(upcoming), unit="actividades", definition="Fechas de actividades programadas en los próximos 30 días.", source="Operaciones", empty_reason="No hay actividades programadas en los próximos 30 días."),
    ]
    return {"period": period_out(p), "cards": cards, "done": done, "upcoming": [row(item) for item in upcoming],
            "by_type": [{"label": key, **value} for key, value in sorted(by_type.items(), key=lambda item: -item[1]["activities"])],
            "notes": {"projects": "Los proyectos con meta y presupuesto están en Finanzas (solo con permiso de Finanzas). Operaciones no registra avance porcentual de proyectos."}}


# ------------------------------------------------------------------ G3 · Invasiones (mismo cálculo del Reporte de invasión)
@router.get("/invasions", response_model=dict)
async def invasions(period: Literal["today", "week", "month", "quarter", "year", "custom"] = "month", date_from: Optional[str] = None, date_to: Optional[str] = None,
                    current_user: dict = Depends(get_current_user)):
    require_section(current_user, "invasions")
    from invasion_report import compute_report
    p = await resolve(period, date_from, date_to)
    rows = []
    async for campaign in db.outreach_campaigns.find({"start_date": {"$lte": p["last"].isoformat()}, "archived": {"$ne": True}}, {"_id": 0}).sort("start_date", -1).limit(60):
        if (campaign.get("end_date") or campaign.get("start_date") or "") < p["first"].isoformat():
            continue
        report = await compute_report(campaign)
        k = report["summary"]["key_figures"]
        rows.append({"campaign_id": campaign["campaign_id"], "name": campaign.get("name"), "start_date": campaign.get("start_date"), "end_date": campaign.get("end_date"),
                     "houses_visited": k.get("houses_visited") or 0, "people_reached": k.get("people_reached") or 0, "wants_followup": k.get("wants_followup") or 0,
                     "to_consolidation": k.get("to_consolidation") or 0, "books": (report.get("books_trace") or {}).get("delivered") or 0,
                     "attended": k.get("attended") or 0, "participants": k.get("participants") or 0, "attendance_pct": k.get("attendance_pct"),
                     "report": f"/invasiones/{campaign['campaign_id']}/reporte", "present": f"/invasiones/{campaign['campaign_id']}/reporte/presentar?dia=1"})
        if len(rows) >= 12:
            break
    total = lambda key: sum(row[key] for row in rows)  # noqa: E731
    none = "No hubo invasiones en este período."
    cards = [
        card("invasions", "Invasiones", len(rows), unit="invasiones", definition="Invasiones cuyas fechas caen, aunque sea en parte, dentro del período (máximo 12 más recientes).", source="Invasiones", empty_reason=none, link="/mentoria/visitas"),
        card("houses", "Viviendas visitadas", total("houses_visited"), unit="viviendas", definition="Suma de las viviendas visitadas de cada invasión, con el mismo cálculo del Reporte de invasión (cada vivienda cuenta una vez por invasión).", source="Reporte de invasión", empty_reason=none),
        card("people", "Personas alcanzadas", total("people_reached"), unit="personas", definition="Suma de las personas registradas en cada invasión (sin cuentas de prueba).", source="Reporte de invasión", empty_reason=none),
        card("followup", "Quieren seguimiento", total("wants_followup"), unit="personas", definition="Personas que aceptaron que un mentor las vuelva a contactar.", source="Reporte de invasión", empty_reason=none),
        card("consolidation", "Pasaron a Consolidación", total("to_consolidation"), unit="personas", definition="Personas de esas invasiones a las que se les abrió el proceso de 7 Semanas.", source="Reporte de invasión", empty_reason="Todavía no se ha pasado a ninguna persona a Consolidación."),
        card("books", "Libros entregados", total("books"), unit="libros", definition="Libros entregados en esas invasiones según la bitácora de Librería.", source="Reporte de invasión · bitácora", empty_reason=none),
    ]
    return {"period": period_out(p), "cards": cards, "items": rows,
            "notes": {"compare": "Cada fila usa el mismo cálculo del Reporte de invasión de esa invasión (semana completa). El enlace «Presentar» abre el Modo Presentar."}}


# ------------------------------------------------------------------ G3 · Libros (bitácora L1)
@router.get("/books", response_model=dict)
async def books_section(period: Literal["today", "week", "month", "quarter", "year", "custom"] = "month", date_from: Optional[str] = None, date_to: Optional[str] = None,
                        current_user: dict = Depends(get_current_user)):
    require_section(current_user, "books")
    from library_ledger import ledger_balances
    from mentorship_outreach import person_display_name
    p = await resolve(period, date_from, date_to)
    balances = await ledger_balances()
    user_ids = {key[0] for key in balances}
    users = {str(doc["_id"]): doc.get("person_id") async for doc in db.users.find({"_id": {"$in": [*user_ids, *[ObjectId(item) for item in user_ids if ObjectId.is_valid(item)]]}}, {"person_id": 1})}
    per_user: dict = defaultdict(lambda: {"received": 0, "delivered": 0, "available": 0})
    for (user_id, _book), row in balances.items():
        item = per_user[user_id]
        item["received"] += row.get("received", 0) + row.get("transferred_in", 0)
        item["delivered"] += row.get("delivered", 0) + row.get("pending_delivered", 0)
        item["available"] += max(row.get("balance", 0), 0)
    by_mentor = []
    for user_id, item in per_user.items():
        if not (item["received"] or item["delivered"]):
            continue
        by_mentor.append({"name": await person_display_name(users.get(user_id)) if users.get(user_id) else "Cuenta sin persona", **item})
    by_mentor.sort(key=lambda row: -row["delivered"])
    delivered_period: dict = defaultdict(int)
    total_period = 0
    async for item in db.library_movements.find({"movement_type": {"$in": ["DELIVERY", "LOAN", "DELIVERY_PENDING"]}, "is_reversal": {"$ne": True}, "occurred_at": {"$gte": p["start"], "$lt": p["end"]}}, {"_id": 0, "quantity": 1, "campaign_id": 1}):
        quantity = item.get("quantity") or 1
        total_period += quantity
        delivered_period[item.get("campaign_id")] += quantity
    names = {doc["campaign_id"]: doc.get("name") async for doc in db.outreach_campaigns.find({"campaign_id": {"$in": [key for key in delivered_period if key]}}, {"_id": 0, "campaign_id": 1, "name": 1})}
    by_campaign = sorted(({"name": names.get(key) or ("Fuera de invasiones" if not key else "Invasión"), "delivered": value} for key, value in delivered_period.items()), key=lambda row: -row["delivered"])
    central = 0
    async for holding in db.library_holdings.find({"holder_type": "warehouse"}, {"_id": 0, "quantity_on_hand": 1}):
        central += holding.get("quantity_on_hand") or 0
    cards = [
        card("delivered", "Libros entregados en el período", total_period, unit="libros", definition="Entregas y préstamos a personas en el período, según la bitácora (incluye entregas por conciliar).", source="Librería 360 · bitácora", empty_reason="No se entregaron libros en este período.", link="/libreria/recorrido"),
        card("mentors_available", "En manos de los mentores", sum(item["available"] for item in by_mentor), unit="libros", definition="Saldo de los mentores: recibidos − entregados − devueltos, calculado de la bitácora (hoy).", source="Librería 360 · bitácora", empty_reason="Ningún mentor tiene libros asignados."),
        card("central", "En el inventario central", central, unit="libros", definition="Existencias del almacén central de Librería (hoy).", source="Librería 360 · inventario", empty_reason="El inventario central está vacío."),
        card("mentors", "Mentores con libros", len(by_mentor), unit="mentores", definition="Cuentas que han recibido o entregado libros.", source="Librería 360 · bitácora", empty_reason="Ningún mentor ha recibido libros."),
    ]
    return {"period": period_out(p), "cards": cards, "by_mentor": by_mentor, "by_campaign": by_campaign,
            "notes": {"balances": "Recibidos, entregados y disponibles de cada mentor salen de la misma bitácora que «Mi inventario» y el Recorrido de libros (toda la historia)."}}


# ------------------------------------------------------------------ G3 · Grupos Frontales y liderazgo
@router.get("/groups", response_model=dict)
async def groups_section(period: Literal["today", "week", "month", "quarter", "year", "custom"] = "month", date_from: Optional[str] = None, date_to: Optional[str] = None,
                         current_user: dict = Depends(get_current_user)):
    require_section(current_user, "groups")
    from front_group_structure import structure_tree
    from mentorship_outreach import person_display_name
    p = await resolve(period, date_from, date_to)
    excluded = await excluded_ids()
    active_groups = await db.front_groups.count_documents({"status": "active"})
    pending = await db.front_groups.count_documents({"status": "pending_formation"})
    people = set(await db.front_group_assignments.distinct("person_id", {"active": True})) - excluded
    leaders = set(await db.front_group_assignments.distinct("person_id", {"active": True, "role": {"$in": ["leader", "co_leader"]}})) - excluded
    worked = set(await db.outreach_visit_events.distinct("mentor_person_id", {"occurred_at": {"$gte": p["start"], "$lt": p["end"]}, "is_draft": {"$ne": True}}))
    worked |= set(await db.outreach_visits.distinct("mentor_person_id", {"created_at": {"$gte": p["start"], "$lt": p["end"]}}))
    worked |= set(await db.process_enrollments.distinct("mentor_person_id", {"updated_at": {"$gte": p["start"], "$lt": p["end"]}, "process_key": "consolidation"}))
    idle_ids = sorted(leaders - worked)
    idle = [{"person_id": pid, "name": await person_display_name(pid) or "Líder"} for pid in idle_ids[:80]]
    idle.sort(key=lambda row: row["name"])
    tree = await structure_tree(root=None, period="month", levels=1, current_user=current_user)
    root = tree.get("root") or {}
    branches = [{"name": f"{team['group']['name']}" if team.get("group") else f"Equipo de {team['leader']['name'] if team.get('leader') else 'líder por definir'}",
                 "leader": (team.get("leader") or {}).get("name"), "status": {"formed": "Grupo formado", "pending": "Por formar", "not_designated": "Todavía no ha formado su grupo"}[team["status"]],
                 "people": (team.get("group") or {}).get("people_branch") or 0, "progress": (team.get("group") or {}).get("progress"), "leader_person_id": (team.get("leader") or {}).get("person_id")}
                for team in (root.get("teams") or [])]
    cards = [
        card("groups", "Grupos Frontales formados", active_groups, unit="grupos", definition="Grupos Frontales activos en todo el árbol.", source="Grupos Frontales", empty_reason="Todavía no hay Grupos Frontales formados.", link="/grupo-frontal?tab=ramas"),
        card("pending", "Grupos por formar", pending, unit="grupos", definition="Equipos ya designados cuyo líder todavía no ha formado su grupo.", source="Grupos Frontales", empty_reason="No hay grupos pendientes de formar."),
        card("people", "Personas en la estructura", len(people), unit="personas", definition="Personas distintas que pertenecen a algún Grupo Frontal (cada persona cuenta una vez). No incluye a la pastora.", source="Grupos Frontales", empty_reason="Todavía no hay personas en los Grupos Frontales."),
        card("leaders", "Líderes y colíderes", len(leaders), unit="personas", definition="Personas que lideran o colideran algún grupo.", source="Grupos Frontales", empty_reason="Todavía no hay líderes designados."),
        card("idle", "Líderes sin actividad en el período", len(idle_ids), unit="líderes", definition="Líderes y colíderes sin visitas, contactos registrados ni movimiento en sus expedientes de Consolidación durante el período.", source="Grupos Frontales + Invasiones + Consolidación", empty_reason="Todos los líderes registraron actividad en el período."),
    ]
    return {"period": period_out(p), "cards": cards, "root": {"name": root.get("name"), "people_branch": root.get("people_branch"), "progress": root.get("progress")} if root else None,
            "branches": branches, "idle_leaders": idle,
            "notes": {"branches": "Ramas del primer nivel del árbol (mismo cálculo de «Mis ramas»: personas sin contar dos veces y avance del mes).", "work": "«Ver el trabajo del líder» abre su detalle de hoy, semana y total."}}


# ------------------------------------------------------------------ G3 · Educación, bautismos, niños, formación, células y radio
@router.get("/education", response_model=dict)
async def education(period: Literal["today", "week", "month", "quarter", "year", "custom"] = "month", date_from: Optional[str] = None, date_to: Optional[str] = None,
                    current_user: dict = Depends(get_current_user)):
    require_section(current_user, "education")
    p = await resolve(period, date_from, date_to)
    first, last = p["first"].isoformat(), p["last"].isoformat()
    discipleship_active = await db.process_enrollments.count_documents({"process_key": "discipleship", "status": "active"})
    discipleship_new = await db.process_enrollments.count_documents({"process_key": "discipleship", "created_at": {"$gte": p["start"], "$lt": p["end"]}})
    discipleship_done = await db.process_enrollments.count_documents({"process_key": "discipleship", "status": "completed", "completed_at": {"$gte": p["start"], "$lt": p["end"]}})
    baptized = await db.person_baptisms.count_documents({"baptized": True, "baptism_date": {"$gte": first, "$lte": last}})
    candidates = await db.person_baptisms.count_documents({"baptized": {"$ne": True}, "status": {"$in": ["pending", "scheduled", "candidate"]}})
    dedications = await db.person_dedications.count_documents({"completed": True, "dedication_date": {"$gte": first, "$lte": last}})
    formation_active = await db.formation_enrollments.count_documents({"status": {"$in": ["active", "enrolled", "in_progress"]}})
    certificates = await db.formation_certificate_issuances.count_documents({"issued_at": {"$gte": p["start"], "$lt": p["end"]}})
    meetings = await db.cell_meetings.count_documents({"scheduled_at": {"$gte": p["start"], "$lt": p["end"]}})
    conversions = 0
    async for meeting in db.cell_meetings.find({"scheduled_at": {"$gte": p["start"], "$lt": p["end"]}}, {"_id": 0, "conversion_person_ids": 1}):
        conversions += len(meeting.get("conversion_person_ids") or [])
    radio_messages = await db.radio_voice_messages.count_documents({"created_at": {"$gte": p["start"], "$lt": p["end"]}})
    cards = [
        card("discipleship_active", "En Educación / Discipulado", discipleship_active, unit="personas", definition="Expedientes de Discipulado activos hoy.", source="Educación / Discipulado", empty_reason="No hay personas activas en Discipulado.", link="/procesos/discipulado"),
        card("discipleship_new", "Iniciaron Discipulado", discipleship_new, unit="personas", definition="Expedientes de Discipulado abiertos en el período.", source="Educación / Discipulado", empty_reason="Nadie inició Discipulado en este período."),
        card("discipleship_done", "Terminaron Discipulado", discipleship_done, unit="personas", definition="Expedientes de Discipulado completados en el período.", source="Educación / Discipulado", empty_reason="Nadie terminó Discipulado en este período."),
        card("baptized", "Bautizados", baptized, unit="personas", definition="Personas marcadas como bautizadas con fecha de bautismo en el período.", source="Bautismos", empty_reason="No hay bautismos con fecha en este período.", link="/bautismos"),
        card("candidates", "Candidatos a bautismo", candidates, unit="personas", definition="Personas en lista de bautismo que todavía no se han bautizado (hoy).", source="Bautismos", empty_reason="No hay candidatos pendientes."),
        card("dedications", "Presentación de niños", dedications, unit="niños", definition="Presentaciones de niños completadas con fecha en el período.", source="Presentación de Niños", empty_reason="No hay presentaciones de niños en este período.", link="/presentaciones"),
        card("formation_active", "Personas en Formación", formation_active, unit="matrículas", definition="Matrículas activas en programas de Formación (hoy).", source="Formación", empty_reason="No hay matrículas activas en Formación.", link="/formacion"),
        card("certificates", "Certificados de Formación", certificates, unit="certificados", definition="Certificados de Formación emitidos en el período.", source="Formación", empty_reason="No se emitieron certificados en este período."),
        card("cell_meetings", "Reuniones de células", meetings, unit="reuniones", definition="Reuniones de célula programadas en el período.", source="Sistema Celular", empty_reason="No hay reuniones de célula en este período.", link="/celulas/dashboard"),
        card("cell_conversions", "Decisiones de fe en células", conversions, unit="personas", definition="Personas marcadas como conversión en las reuniones de célula del período.", source="Sistema Celular", empty_reason="No se registraron decisiones de fe en células en este período."),
        card("radio", "Mensajes de voz en el radio", radio_messages, unit="mensajes", definition="Mensajes de voz grabados en el radio de las invasiones durante el período.", source="Radio", empty_reason="No hubo mensajes de voz en el radio en este período."),
    ]
    return {"period": period_out(p), "cards": cards}
