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
            "attendance": pastoral or coordinator or has_capability(current_user, OPERATIONS_REPORTS)}


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
    return {"period": period_out(p), "cards": cards, "finance_available": False,
            "finance_note": "Los ingresos (diezmos, ofrendas, proyectos) se muestran en la sección Finanzas, solo con permiso de Finanzas."}


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
