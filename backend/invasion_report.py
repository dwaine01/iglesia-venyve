"""FASE 6F — Reporte de invasión (por campaign_id).

Reemplaza el "Informe" anterior del Panel de líderes (sin duplicarlo): mismas
fuentes (`outreach_campaigns`, `invasion_participants`, `outreach_households`,
`outreach_visit_events`, `outreach_visits`, oración 6C), todo agregado en pocas
consultas (sin N+1).

Estados:
- "En curso" (datos vivos) mientras la invasión no esté cerrada.
- "Reporte final": al cerrar la invasión se guarda una foto (snapshot) en
  `invasion_reports` que ya no cambia. Lecciones aprendidas y recomendaciones
  del pastor siguen editables aparte.

Permisos (backend):
- Reporte completo: autoridad pastoral, coordinadores generales, organizador y
  encargado general (`can_edit_participants`).
- Un mentor/participante ve solo su reporte personal.
- Invitar no da acceso a datos de personas: el reporte agrega cifras; los
  nombres de mentores/participantes solo los ve quien ve el reporte completo.
- La autoridad pastoral principal no cuenta en ninguna métrica de participación."""
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from invasion_participants import ROLE_LABELS, ROLES, can_edit_participants, load_campaign
from invasion_prayer import prayer_summary
from mentorship_outreach import campaign_book_rows, now_utc, person_display_name, serialize
from participation_scope import principal_authority_person_ids
from process_engine import get_definition
from supervision_analytics import load_thresholds
from server import db, get_current_user

router = APIRouter(prefix="/api/invasions", tags=["invasion-report"])

REPORT_VERSION = 1
RESULT_LABELS = {"no_answer": "Sin respuesta", "not_home": "No estaba", "refused": "Rechazó", "contacted": "Contacto"}


def _day(value) -> Optional[str]:
    if not value:
        return None
    return value.date().isoformat() if hasattr(value, "date") else str(value)[:10]


async def _names(person_ids) -> dict:
    from bson import ObjectId
    oids = [ObjectId(item) for item in {item for item in person_ids if item} if ObjectId.is_valid(item)]
    if not oids:
        return {}
    return {str(doc["_id"]): " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) or "Persona"
            async for doc in db.persons.find({"_id": {"$in": oids}}, {"nombre": 1, "apellido": 1})}


UNATTENDED_HOURS = 48
FIRST_CONTACT_BUCKETS = [("< 24 h", 24), ("24–48 h", 48), ("2–3 días", 72), ("3–7 días", 168), ("> 7 días", None)]


def _aware(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


async def followup_section(visits: list[dict]) -> dict:
    """4) Seguimiento y Consolidación (por personas alcanzadas en la invasión)."""
    now = datetime.now(timezone.utc)
    enrollment_ids = [visit["enrollment_id"] for visit in visits if visit.get("enrollment_id")]
    enrollments = {item["enrollment_id"]: item async for item in db.process_enrollments.find({"enrollment_id": {"$in": enrollment_ids}}, {"_id": 0, "enrollment_id": 1, "mentor_person_id": 1, "current_stage_key": 1, "status": 1, "created_at": 1})} if enrollment_ids else {}
    first_done: dict[str, datetime] = {}
    if enrollment_ids:
        async for row in db.consolidation_activities.aggregate([
            {"$match": {"enrollment_id": {"$in": enrollment_ids}, "status": "done"}},
            {"$group": {"_id": "$enrollment_id", "first": {"$min": "$completed_at"}}},
        ]):
            first_done[row["_id"]] = _aware(row["first"])
    transferred = set(await db.mentor_assignments.distinct("enrollment_id", {"enrollment_id": {"$in": enrollment_ids}, "transfer": True})) if enrollment_ids else set()
    try:
        stages = {stage["key"]: stage["order"] for stage in (await get_definition(db, "consolidation")).get("stages", [])}
    except ValueError:
        stages = {}
    order = lambda key: stages.get(key or "", 0)  # noqa: E731
    wants = [visit for visit in visits if visit.get("status") == "wants_followup" or visit.get("enrollment_id")]
    buckets = Counter()
    unattended = []
    for visit in wants:
        created = _aware(visit.get("created_at"))
        enrollment = enrollments.get(visit.get("enrollment_id"))
        contact = first_done.get(visit.get("enrollment_id"))
        if contact and created:
            hours = (contact - created).total_seconds() / 3600
            label = next(name for name, limit in FIRST_CONTACT_BUCKETS if limit is None or hours < limit)
            buckets[label] += 1
        else:
            buckets["Sin contacto"] += 1
            age_hours = (now - created).total_seconds() / 3600 if created else 0
            if age_hours >= UNATTENDED_HOURS:
                unattended.append({"visit_id": visit.get("visit_id"), "mentor_person_id": visit.get("mentor_person_id"), "hours": round(age_hours), "has_enrollment": bool(enrollment)})
    reached_stage = lambda threshold: sum(1 for item in enrollments.values() if order(item.get("current_stage_key")) >= threshold)  # noqa: E731
    mcd, npt, lbs = stages.get("mcd", 4), stages.get("npt", 5), stages.get("lbs_1", 7)
    by_day = Counter(_day(item.get("created_at")) for item in enrollments.values() if item.get("created_at"))
    return {
        "wants_followup": len(wants), "to_consolidation": len(enrollments),
        "assigned_mentor": sum(1 for item in enrollments.values() if item.get("mentor_person_id")),
        "transferred": len(transferred), "attended": len(wants) - buckets["Sin contacto"],
        "unattended": len(unattended), "pending_recent": buckets["Sin contacto"] - len(unattended), "unattended_hours": UNATTENDED_HOURS,
        "first_contact": [{"bucket": name, "total": buckets.get(name, 0)} for name, _ in FIRST_CONTACT_BUCKETS] + [{"bucket": "Sin contacto", "total": buckets.get("Sin contacto", 0)}],
        "routes": [{"route": "MCD", "total": reached_stage(mcd)}, {"route": "NPT", "total": reached_stage(npt)}, {"route": "LBS", "total": reached_stage(lbs)}],
        "consolidation_by_day": [{"day": key, "total": value} for key, value in sorted(by_day.items())],
        "unattended_items": unattended,
    }


def semaphore(progress: Optional[float], thresholds: dict) -> str:
    if progress is None:
        return "sin_datos"
    return "verde" if progress >= thresholds["goal_progress_green"]["value"] else "ambar" if progress >= thresholds["goal_progress_yellow"]["value"] else "rojo"


def goals_section(summary_figures: dict, field: dict, followup: dict, prayer: Optional[dict], active_participants: int, thresholds: dict) -> dict:
    """6) Metas vs resultado real (umbrales 'propuesta' editables en Supervisión)."""
    def indicator(key, label, numerator, denominator, goal_key, unit="ratio", explanation=""):
        goal = thresholds[goal_key]
        value = (numerator / denominator) if denominator else None
        progress = round(min(value / goal["value"], 1), 3) if value is not None and goal["value"] else None
        return {"key": key, "label": label, "unit": unit, "value": round(value, 3) if value is not None else None, "goal": goal["value"],
                "goal_status": goal.get("status", "propuesta"), "numerator": numerator, "denominator": denominator,
                "progress": progress, "semaphore": semaphore(progress, thresholds), "explanation": explanation}
    figures = summary_figures
    attended = figures["attended"]
    items = [
        indicator("attendance", "Asistencia de invitados", attended, figures["participants"], "goal_attendance_ratio", explanation=f"{attended} de {figures['participants']} invitados asistieron"),
        indicator("outreach", "Participantes con actividad en campo", active_participants, figures["participants"], "goal_outreach_ratio", explanation=f"{active_participants} de {figures['participants']} registraron casas o personas"),
        indicator("reached", "Personas alcanzadas por asistente", figures["people_reached"], attended, "goal_persons_reached_per_member_week", unit="per_member", explanation=f"{figures['people_reached']} personas ÷ {attended} asistentes"),
        indicator("coverage", "Cobertura de casas", field["houses"]["visited"], field["houses"]["total"], "goal_invasion_house_coverage", explanation=f"{field['houses']['visited']} de {field['houses']['total']} casas visitadas"),
        indicator("consolidation", "Seguimiento que pasa a Consolidación", followup["to_consolidation"], followup["wants_followup"], "goal_invasion_followup_to_consolidation", explanation=f"{followup['to_consolidation']} de {followup['wants_followup']} personas"),
    ]
    if prayer:
        totals = prayer["totals"]
        items.append(indicator("prayer", "Preparación en oración", totals["prayed_any"], totals["participants"], "goal_invasion_prayer_ratio", explanation=f"{totals['prayed_any']} de {totals['participants']} oraron"))
    measured = [item["progress"] for item in items if item["progress"] is not None]
    overall = round(sum(measured) / len(measured), 3) if measured else None
    return {"items": items, "overall": overall, "overall_semaphore": semaphore(overall, thresholds),
            "rule": f"Verde desde {round(thresholds['goal_progress_green']['value'] * 100)}% de avance hacia la meta, ámbar desde {round(thresholds['goal_progress_yellow']['value'] * 100)}%, rojo debajo. Metas 'propuesta' editables por la pastora o el coordinador general."}


async def comparison_section(campaign: dict, current: dict) -> list[dict]:
    """7) Esta invasión y las 5 anteriores (ya iniciadas), con agregados por invasión."""
    previous = await db.outreach_campaigns.find(
        {"campaign_id": {"$ne": campaign["campaign_id"]}, "start_date": {"$lt": campaign.get("start_date") or "9999"}},
        {"_id": 0, "campaign_id": 1, "name": 1, "start_date": 1},
    ).sort("start_date", -1).limit(5).to_list(5)
    ids = [item["campaign_id"] for item in previous]
    authorities = list(await principal_authority_person_ids(db))
    visits = {row["_id"]: row async for row in db.outreach_visits.aggregate([
        {"$match": {"campaign_id": {"$in": ids}, "archived": {"$ne": True}, "mentor_person_id": {"$nin": authorities}}},
        {"$group": {"_id": "$campaign_id", "people": {"$sum": 1}, "followup": {"$sum": {"$cond": [{"$eq": ["$status", "wants_followup"]}, 1, 0]}}}},
    ])} if ids else {}
    participation = {row["_id"]: row async for row in db.invasion_participants.aggregate([
        {"$match": {"campaign_id": {"$in": ids}, "person_id": {"$nin": authorities}}},
        {"$group": {"_id": "$campaign_id", "total": {"$sum": 1}, "attended": {"$sum": {"$cond": [{"$eq": ["$attended", True]}, 1, 0]}}}},
    ])} if ids else {}
    rows = [{"campaign_id": campaign["campaign_id"], "name": campaign.get("name"), "start_date": campaign.get("start_date"), "current": True,
             "people": current["people_reached"], "followup": current["wants_followup"], "attendance_pct": current["attendance_pct"]}]
    for item in previous:
        part = participation.get(item["campaign_id"], {})
        rows.append({"campaign_id": item["campaign_id"], "name": item["name"], "start_date": item.get("start_date"), "current": False,
                     "people": visits.get(item["campaign_id"], {}).get("people", 0), "followup": visits.get(item["campaign_id"], {}).get("followup", 0),
                     "attendance_pct": round(part["attended"] / part["total"] * 100) if part.get("total") else None})
    return rows


def prayer_report(prayer: dict) -> dict:
    """5) Oración: totales, % que oró por semana y asistencia por reunión."""
    from datetime import timedelta
    period = prayer["period"]
    start, end = date.fromisoformat(period["prayer_start"]), date.fromisoformat(period["prep_end"])
    people = prayer["items"]
    weeks = []
    cursor, number = start, 1
    while cursor <= end and people:
        week_end = min(cursor + timedelta(days=6), end)
        prayed = sum(1 for item in people if any(cursor.isoformat() <= day <= week_end.isoformat() for day in item["prayer_days"]))
        weeks.append({"week": f"Semana {number}", "from": cursor.isoformat(), "to": week_end.isoformat(), "prayed": prayed, "pct": round(prayed / len(people) * 100)})
        cursor, number = week_end + timedelta(days=1), number + 1
    meetings = [{"day": meeting["day"], "place": meeting.get("place"), "attendees": meeting.get("attendee_count", 0),
                 "pct": round(meeting.get("attendee_count", 0) / len(people) * 100) if people else None} for meeting in prayer["meetings"]]
    return {"period": period, "totals": prayer["totals"], "by_week": weeks, "meetings": meetings}


# ---------------------------------------------------------------- 8) Recomendaciones por reglas
PRIORITY_ORDER = {"alta": 0, "media": 1, "baja": 2}


def build_recommendations(data: dict) -> list[dict]:
    """Recomendaciones generadas SOLO por reglas explícitas sobre los datos del
    reporte (nada inventado). Cada una lleva la regla, la evidencia (el dato que
    la dispara) y un responsable sugerido. El id es estable para guardar
    "resuelta"."""
    recs: list[dict] = []
    summary, field, part = data["summary"], data["field"], data["participation"]
    figures = summary["key_figures"]
    follow = data.get("followup") or {}
    state = summary.get("state")

    def add(rule_id, priority, title, detail, evidence_label, value, total=None, responsible="Encargado general", rule=""):
        recs.append({"id": rule_id, "priority": priority, "title": title, "detail": detail, "responsible": responsible, "rule": rule,
                     "evidence": {"label": evidence_label, "value": value, "total": total, "pct": round(value / total * 100) if total else None}})

    if follow.get("unattended"):
        add("followup:unattended", "alta", f"Atender a {follow['unattended']} persona(s) sin seguimiento",
            "Quieren seguimiento y llevan más de 48 h sin una actividad de consolidación realizada. Asignar mentor y registrar el primer contacto hoy.",
            "Personas sin atender > 48 h", follow["unattended"], follow.get("wants_followup"), "Coordinador de Consolidación",
            f"Regla: quiere seguimiento y sin primer contacto después de {follow.get('unattended_hours', 48)} h.")
    available = field["houses"]["available"]
    if available and state in {"active", "finished", "closed"}:
        share = available / field["houses"]["total"] if field["houses"]["total"] else 0
        add("houses:available", "media" if share >= 0.2 else "baja", f"{available} casa(s) disponibles sin tomar",
            "Repartirlas entre los mentores con menos casas o programar otra salida al sector.", "Casas disponibles", available, field["houses"]["total"],
            "Encargado general", "Regla: casas de la invasión sin mentor asignado.")
    for sector in field.get("by_sector", []):
        if sector["sector"] != "Sin sector" and sector["houses"] >= 3 and sector["coverage_pct"] is not None and sector["coverage_pct"] < 30:
            add(f"sector:{sector['sector']}", "media", f"Baja cobertura en {sector['sector']}",
                f"Solo {sector['visited']} de {sector['houses']} casas visitadas. Reforzar el sector con más mentores en la próxima jornada.",
                "Casas visitadas en el sector", sector["visited"], sector["houses"], "Encargado general", "Regla: sector con 3+ casas y menos de 30% visitadas.")
    idle = [row for row in data["ranking"]["mentors"] if row.get("status") != "declined" and not row["people"] and not row["houses_visited"]]
    if idle and state in {"active", "finished", "closed"}:
        names = ", ".join(row["name"] for row in idle[:5]) + ("…" if len(idle) > 5 else "")
        add("mentors:idle", "alta" if len(idle) >= 3 else "media", f"{len(idle)} mentor(es) sin visitas registradas",
            f"{names}. Verificar si salieron al campo y apoyarlos para registrar sus visitas.", "Mentores sin actividad", len(idle), len(data["ranking"]["mentors"]),
            "Líderes de Grupo Frontal", "Regla: mentor invitado (no declinó) sin personas ni casas visitadas.")
    no_response = part["totals"]["no_response"]
    if no_response and state in {"upcoming", "active"}:
        total = part["totals"]["invited"]
        add("participation:no_response", "media" if no_response / total >= 0.2 else "baja", f"{no_response} invitado(s) sin responder",
            "Llamarles o enviar un recordatorio para confirmar si participarán.", "Sin responder", no_response, total, "Organizador",
            "Regla: invitados que no respondieron mientras la invasión no termina.")
    attendance_goal = next((item for item in data.get("goals", {}).get("items", []) if item["key"] == "attendance"), None)
    if attendance_goal and attendance_goal["semaphore"] == "rojo" and state in {"finished", "closed"}:
        add("participation:low_attendance", "alta", f"Baja asistencia: {figures['attendance_pct']}%",
            "Revisar con los grupos frontales qué impidió asistir (horario, transporte, avisos) antes de la próxima invasión.",
            "Asistieron", figures["attended"], figures["participants"], "Pastor / Coordinador general", "Regla: semáforo rojo en la meta de asistencia.")
    teams = [team for team in data["ranking"]["teams"] if team.get("front_group_id")]
    if len(teams) >= 2 and teams[0]["score"]:
        for team in teams:
            if team["score"] < teams[0]["score"] * 0.5:
                add(f"team:{team['front_group_id']}", "baja", f"El equipo {team['name']} se queda atrás",
                    f"{team['score']} puntos frente a {teams[0]['score']} del primero. Acompañar al líder del grupo en la próxima salida.",
                    "Puntaje del equipo", team["score"], teams[0]["score"], "Líder del Grupo Frontal", "Regla: equipo con menos de la mitad del puntaje del primero.")
    prayer = data.get("prayer")
    if prayer and prayer["totals"].get("needs_followup"):
        add("prayer:followup", "media", f"{prayer['totals']['needs_followup']} participante(s) con poca preparación en oración",
            "Animarles y acompañarles en la oración antes de salir.", "Necesitan seguimiento", prayer["totals"]["needs_followup"], prayer["totals"]["participants"],
            "Encargado general", "Regla de oración (6C): menos de la mitad de los días o sin oración en los últimos 3 días.")
    if field["results"].get("lbs_pending"):
        add("results:lbs", "media", f"{field['results']['lbs_pending']} persona(s) con LBS pendiente",
            "Asignar un mentor habilitado para LBS.", "LBS pendiente", field["results"]["lbs_pending"], figures["people_reached"], "Coordinador de Consolidación",
            "Regla: visita con decisión 'necesita LBS'.")
    unlocated = field["houses"]["total"] - field["houses"]["located"]
    if unlocated:
        add("houses:unlocated", "baja", f"{unlocated} casa(s) sin ubicar en el mapa",
            "Ubicarlas con «Ubicar con mi ubicación» o corregir su dirección.", "Casas sin ubicar", unlocated, field["houses"]["total"], "Logística",
            "Regla: casa sin coordenadas.")
    recs.sort(key=lambda item: PRIORITY_ORDER[item["priority"]])
    return recs


class RecommendationState(BaseModel):
    resolved: bool
    note: Optional[str] = Field(default=None, max_length=500)


class ReportNotes(BaseModel):
    worked: Optional[str] = Field(default=None, max_length=4000)
    improve: Optional[str] = Field(default=None, max_length=4000)
    logistics: Optional[str] = Field(default=None, max_length=4000)
    testimonies: Optional[str] = Field(default=None, max_length=6000)
    pastor_recommendations: Optional[str] = Field(default=None, max_length=6000)


def state_key(recommendation_id: str) -> str:
    """Clave segura para Mongo (los ids pueden traer nombres de sector con puntos)."""
    return recommendation_id.replace(".", "_").replace("$", "_")[:200]


async def actor_name(current_user: dict) -> str:
    return await person_display_name(current_user.get("person_id")) or current_user.get("nombre") or current_user.get("email") or "Usuario"


async def load_notes(campaign_id: str) -> dict:
    return await db.invasion_report_notes.find_one({"campaign_id": campaign_id}, {"_id": 0}) or {"campaign_id": campaign_id, "resolved": {}}


def campaign_state(campaign: dict) -> str:
    today = date.today().isoformat()
    if campaign.get("status") == "closed":
        return "closed"
    if (campaign.get("start_date") or today) > today:
        return "upcoming"
    if (campaign.get("end_date") or campaign.get("start_date") or today) >= today:
        return "active"
    return "finished"


async def _help_alerts(campaign_id: str) -> dict:
    from invasion_alerts import help_summary
    return await help_summary(campaign_id)


STATUS_LABELS = {"assigned": "Asignada", "not_found": "No encontrada", "visited": "Visitada", "rejected": "Rechazó", "wants_followup": "Quiere seguimiento"}


async def _people_rows(visits: list[dict], mentor_names: dict, sector_of_house: dict) -> list[dict]:
    person_names = await _names({visit.get("converted_person_id") or visit.get("person_id") for visit in visits})
    rows = []
    for visit in visits[:5000]:
        pid = visit.get("converted_person_id") or visit.get("person_id")
        rows.append({"visit_id": visit["visit_id"], "name": person_names.get(pid) or visit.get("contact_name") or "Persona", "mentor": mentor_names.get(visit.get("mentor_person_id"), "Mentor"),
                     "sector": (visit.get("contact_zone") or sector_of_house.get(visit.get("household_id")) or "").strip() or "Sin sector",
                     "address": " ".join(filter(None, [visit.get("address_line1"), visit.get("address_line2")])) or None,
                     "status": STATUS_LABELS.get(visit.get("status"), visit.get("status")), "followup": bool(visit.get("followup_accepted") or visit.get("status") == "wants_followup"),
                     "next_action": visit.get("next_action"), "consolidation": bool(visit.get("enrollment_id")), "date": _day(visit.get("created_at"))})
    return rows


async def _books_trace(campaign_id: str) -> dict:
    from library_trace import campaign_books_summary
    return await campaign_books_summary(campaign_id)


async def _door_data(campaign_id: str) -> dict:
    from door_reports import door_report_data
    return await door_report_data(campaign_id)


async def compute_report(campaign: dict) -> dict:
    """Todas las secciones con datos vivos (lo que se congela al cerrar)."""
    campaign_id = campaign["campaign_id"]
    authorities = await principal_authority_person_ids(db)
    participants = [row for row in await db.invasion_participants.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(3000) if row["person_id"] not in authorities]
    households = await db.outreach_households.find({"campaign_id": campaign_id, "archived": {"$ne": True}}, {"_id": 0, "household_id": 1, "mentor_person_id": 1, "sector": 1, "status": 1, "latitude": 1}).to_list(5000)
    events = await db.outreach_visit_events.find({"campaign_id": campaign_id}, {"_id": 0, "household_id": 1, "mentor_person_id": 1, "result": 1, "occurred_at": 1}).to_list(20000)
    visits = [visit for visit in await db.outreach_visits.find({"campaign_id": campaign_id, "archived": {"$ne": True}}, {"_id": 0, "visit_id": 1, "mentor_person_id": 1, "status": 1, "received_mcd": 1, "received_npt": 1, "lbs_decision": 1, "enrollment_id": 1, "contact_zone": 1, "household_id": 1, "created_at": 1, "front_group_id": 1,
                                                                                                       "contact_name": 1, "person_id": 1, "converted_person_id": 1, "address_line1": 1, "address_line2": 1, "followup_accepted": 1, "next_action": 1}).to_list(20000)
              if visit.get("mentor_person_id") not in authorities]
    person_ids = {row["person_id"] for row in participants} | {item.get("mentor_person_id") for item in households + visits if item.get("mentor_person_id")}
    names = await _names(person_ids | {campaign.get("general_lead_person_id"), campaign.get("logistics_lead_person_id")})

    # Grupo Frontal de cada participante (asignación activa; liderazgo primero).
    group_of: dict[str, str] = {}
    assignments = await db.front_group_assignments.find({"person_id": {"$in": list(person_ids)}, "active": True}, {"_id": 0, "person_id": 1, "front_group_id": 1, "role": 1}).to_list(5000)
    for item in sorted(assignments, key=lambda entry: {"leader": 0, "co_leader": 1}.get(entry.get("role"), 2)):
        group_of.setdefault(item["person_id"], item["front_group_id"])
    group_names = {doc["front_group_id"]: doc.get("name") or "Grupo sin nombre" async for doc in db.front_groups.find({"front_group_id": {"$in": list(set(group_of.values()))}}, {"_id": 0, "front_group_id": 1, "name": 1})}

    # ---- Participación
    def participation_counts(rows: list[dict]) -> dict:
        total = len(rows)
        attended = sum(1 for row in rows if row.get("attended"))
        return {"invited": total, "confirmed": sum(1 for row in rows if row.get("status") == "confirmed"),
                "declined": sum(1 for row in rows if row.get("status") == "declined"), "no_response": sum(1 for row in rows if row.get("status") == "invited"),
                "attended": attended, "attendance_pct": round(attended / total * 100) if total else None}
    by_role = [{"role": role, "label": ROLE_LABELS[role], **participation_counts([row for row in participants if role in row.get("roles", [])])} for role in ROLES]
    # Asistencia por jornada (marcada en la pantalla móvil de Asistencia o por actividad en campo).
    from invasion_attendance import campaign_days
    attendance_by_day = []
    for item in campaign_days(campaign):
        count = sum(1 for row in participants if item["day"] in (row.get("attended_days") or []))
        attendance_by_day.append({"day": item["day"], "attended": count, "invited": len(participants), "pct": round(count / len(participants) * 100) if participants else None})
    groups_rows: dict[str, list] = defaultdict(list)
    for row in participants:
        groups_rows[group_of.get(row["person_id"], "")].append(row)
    by_group = sorted(({"front_group_id": key or None, "name": group_names.get(key, "Sin Grupo Frontal"), **participation_counts(rows)} for key, rows in groups_rows.items()), key=lambda item: -(item["attendance_pct"] or 0))

    # ---- Campo
    events_by_house = Counter(event["household_id"] for event in events)
    visited_houses = {key for key, value in events_by_house.items() if value}
    houses_by_mentor = Counter(house.get("mentor_person_id") for house in households if house.get("mentor_person_id"))
    visited_by_mentor = Counter(house.get("mentor_person_id") for house in households if house["household_id"] in visited_houses and house.get("mentor_person_id"))
    visits_by_mentor = Counter(visit.get("mentor_person_id") for visit in visits)
    sector_of_house = {house["household_id"]: (house.get("sector") or "").strip() for house in households}
    by_sector: dict[str, dict] = defaultdict(lambda: {"houses": 0, "visited": 0, "people": 0})
    for house in households:
        key = sector_of_house[house["household_id"]] or "Sin sector"
        by_sector[key]["houses"] += 1
        by_sector[key]["visited"] += int(house["household_id"] in visited_houses)
    for visit in visits:
        key = (visit.get("contact_zone") or sector_of_house.get(visit.get("household_id")) or "").strip() or "Sin sector"
        by_sector[key]["people"] += 1
    by_day: dict[str, dict] = defaultdict(lambda: {"attempts": 0, "people": 0})
    for event in events:
        if _day(event.get("occurred_at")):
            by_day[_day(event["occurred_at"])]["attempts"] += 1
    for visit in visits:
        if _day(visit.get("created_at")):
            by_day[_day(visit["created_at"])]["people"] += 1
    results = {
        "wants_followup": sum(1 for visit in visits if visit.get("status") == "wants_followup"),
        "received_mcd": sum(1 for visit in visits if visit.get("received_mcd")),
        "received_npt": sum(1 for visit in visits if visit.get("received_npt")),
        "lbs_pending": sum(1 for visit in visits if visit.get("lbs_decision") == "needs_lbs"),
        "seven_weeks": sum(1 for visit in visits if visit.get("enrollment_id")),
        "rejected": sum(1 for visit in visits if visit.get("status") == "rejected"),
    }
    attempts_by_result = Counter(event.get("result") for event in events)

    # ---- Ranking (actividad real en la invasión)
    mentor_ids = [row["person_id"] for row in participants if "mentor" in row.get("roles", [])]
    participant_by_id = {row["person_id"]: row for row in participants}
    attempts_by_mentor = Counter(event.get("mentor_person_id") for event in events)
    mentor_rows = []
    for person_id in set(mentor_ids) | set(visits_by_mentor) | set(houses_by_mentor):
        if person_id in authorities:
            continue
        row = participant_by_id.get(person_id, {})
        mentor_visits = [visit for visit in visits if visit.get("mentor_person_id") == person_id]
        mentor_rows.append({
            "person_id": person_id, "name": names.get(person_id, "Mentor"), "front_group": group_names.get(group_of.get(person_id)),
            "status": row.get("status"), "attended": bool(row.get("attended")),
            "houses": houses_by_mentor.get(person_id, 0), "houses_visited": visited_by_mentor.get(person_id, 0),
            "attempts": attempts_by_mentor.get(person_id, 0),
            "people": len(mentor_visits), "wants_followup": sum(1 for visit in mentor_visits if visit.get("status") == "wants_followup"),
            "seven_weeks": sum(1 for visit in mentor_visits if visit.get("enrollment_id")),
        })
    for item in mentor_rows:
        item["score"] = item["people"] * 3 + item["houses_visited"] * 2 + item["wants_followup"] * 2 + item["seven_weeks"] * 3
    mentor_rows.sort(key=lambda item: (-item["score"], item["name"]))
    team_rows: dict[str, dict] = defaultdict(lambda: {"people": 0, "houses_visited": 0, "mentors": 0, "score": 0})
    for item in mentor_rows:
        key = group_of.get(item["person_id"]) or ""
        team = team_rows[key]
        team["mentors"] += 1
        for field in ("people", "houses_visited", "score"):
            team[field] += item[field]
    teams = sorted(({"front_group_id": key or None, "name": group_names.get(key, "Sin Grupo Frontal"), **value} for key, value in team_rows.items()), key=lambda item: -item["score"])

    prayer = await prayer_summary(campaign) if campaign.get("start_date") else None
    total_participants = len(participants)
    attended_total = sum(1 for row in participants if row.get("attended"))
    followup = await followup_section(visits)
    key_figures = {
        "houses_visited": len(visited_houses & {house["household_id"] for house in households}), "houses_total": len(households),
        "people_reached": len(visits), "wants_followup": results["wants_followup"], "seven_weeks": results["seven_weeks"],
        "participants": total_participants, "attended": attended_total,
        "attendance_pct": round(attended_total / total_participants * 100) if total_participants else None,
        "confirmed": sum(1 for row in participants if row.get("status") == "confirmed"),
        "to_consolidation": followup["to_consolidation"], "route_started": next(item["total"] for item in followup["routes"] if item["route"] == "MCD"),
    }
    active_people = {house.get("mentor_person_id") for house in households if house.get("mentor_person_id")} | {visit.get("mentor_person_id") for visit in visits}
    field_section = {"houses": {"visited": key_figures["houses_visited"], "total": len(households)}}
    goals = goals_section(key_figures, field_section, followup, {"totals": prayer["totals"]} if prayer and prayer["period"]["expected_days"] else None,
                          sum(1 for row in participants if row["person_id"] in active_people), await load_thresholds())
    return {
        "version": REPORT_VERSION,
        "summary": {
            "name": campaign.get("name"), "start_date": campaign.get("start_date"), "end_date": campaign.get("end_date"),
            "location": campaign.get("location"), "purpose": campaign.get("purpose"), "description": campaign.get("description"),
            "organizer": campaign.get("created_by_name"), "general_lead": names.get(campaign.get("general_lead_person_id")),
            "logistics_lead": names.get(campaign.get("logistics_lead_person_id")), "state": campaign_state(campaign),
            "key_figures": key_figures,
        },
        "participation": {"totals": participation_counts(participants), "by_role": by_role, "by_group": by_group, "by_day": attendance_by_day},
        "field": {
            "houses": {"available": sum(1 for house in households if not house.get("mentor_person_id")),
                       "assigned": sum(1 for house in households if house.get("mentor_person_id")),
                       "visited": len(visited_houses & {house["household_id"] for house in households}),
                       "located": sum(1 for house in households if house.get("latitude") is not None), "total": len(households)},
            "by_day": [{"day": key, **value} for key, value in sorted(by_day.items())],
            "by_sector": sorted(({"sector": key, **value, "coverage_pct": round(value["visited"] / value["houses"] * 100) if value["houses"] else None} for key, value in by_sector.items()), key=lambda item: -item["people"]),
            "results": results,
            "attempts_by_result": [{"result": key, "label": RESULT_LABELS.get(key, key), "total": value} for key, value in attempts_by_result.items() if key],
            # Puerta a puerta (tramo 4): viviendas vs intentos, libros, abrieron/no abrieron, pendientes; por mentor, equipo y calle.
            "doors": await _door_data(campaign_id),
        },
        "ranking": {"mentors": mentor_rows, "teams": teams},
        "prayer": prayer_report(prayer) if prayer else None,
        "help_alerts": await _help_alerts(campaign["campaign_id"]),
        # Lo que mostraba el "Informe" anterior: libros asignados/entregados por mentor.
        "books": [row for row in await campaign_book_rows(campaign) if row["mentor_person_id"] not in authorities],
        # L3: libros entregados (bitácora), con destinatario y con seguimiento.
        "books_trace": await _books_trace(campaign_id),
        "followup": {key: value for key, value in followup.items() if key != "unattended_items"},
        "goals": goals,
        "comparison": await comparison_section(campaign, key_figures),
        # Sección 9: personas alcanzadas (solo en el reporte completo; el personal no la recibe).
        "people_reached": await _people_rows(visits, names, sector_of_house),
    }


def personal_view(report: dict, person_id: Optional[str]) -> dict:
    """Lo que ve un mentor/participante: su propia fila y cifras generales sin nombres."""
    mine = next((item for item in report["ranking"]["mentors"] if item["person_id"] == person_id), None)
    summary = {key: value for key, value in report["summary"].items() if key != "description"}
    return {"scope": "personal", "summary": summary, "mine": mine,
            "position": (report["ranking"]["mentors"].index(mine) + 1) if mine else None, "mentors_total": len(report["ranking"]["mentors"])}


async def final_snapshot(campaign: dict) -> Optional[dict]:
    return await db.invasion_reports.find_one({"campaign_id": campaign["campaign_id"], "final": True}, {"_id": 0})


async def freeze_report(campaign: dict, actor_user_id: Optional[str]) -> dict:
    """Congela el reporte final (idempotente: si ya existe, no lo cambia)."""
    existing = await final_snapshot(campaign)
    if existing:
        return existing
    data = await compute_report(await with_organizer({**campaign, "status": "closed"}))
    doc = {"_id": f"final-{campaign['campaign_id']}", "campaign_id": campaign["campaign_id"], "final": True, "data": data,
           "frozen_at": now_utc(), "frozen_by_user_id": actor_user_id}
    await db.invasion_reports.update_one({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True)
    return await final_snapshot(campaign)


async def report_access(campaign: dict, current_user: dict) -> str:
    if can_edit_participants(current_user, campaign):
        return "full"
    person_id = current_user.get("person_id")
    if person_id and (person_id in (campaign.get("assigned_mentor_ids") or []) or await db.invasion_participants.find_one({"campaign_id": campaign["campaign_id"], "person_id": person_id}, {"_id": 1})):
        return "personal"
    raise HTTPException(status_code=403, detail="Sin acceso al reporte de esta invasión")


async def with_organizer(campaign: dict) -> dict:
    from bson import ObjectId
    creator_id = campaign.get("created_by_user_id")
    creator = await db.users.find_one({"_id": ObjectId(creator_id)}, {"nombre": 1}) if creator_id and ObjectId.is_valid(creator_id) else None
    return {**campaign, "created_by_name": (creator or {}).get("nombre")}


@router.get("/{campaign_id}/report", response_model=dict)
async def get_report(campaign_id: str, current_user: dict = Depends(get_current_user)):
    campaign = await load_campaign(campaign_id)
    access = await report_access(campaign, current_user)
    campaign = await with_organizer(campaign)
    snapshot = None
    if campaign.get("status") == "closed":
        snapshot = await freeze_report(campaign, None)  # invasiones cerradas antes de este reporte
    data = snapshot["data"] if snapshot else await compute_report(campaign)
    meta = {"campaign_id": campaign_id, "mode": "final" if snapshot else "live",
            "frozen_at": serialize(snapshot["frozen_at"]) if snapshot else None, "generated_at": serialize(now_utc()),
            "can_finalize": access == "full" and not snapshot and campaign_state(campaign) in {"finished", "active"}}
    if access == "personal":
        return {**meta, **personal_view(data, current_user.get("person_id"))}
    notes = await load_notes(campaign_id)
    resolved = notes.get("resolved") or {}
    recommendations = []
    for item in build_recommendations(data):
        entry = resolved.get(state_key(item["id"])) or {}
        recommendations.append({**item, "resolved": bool(entry.get("resolved")), "resolved_note": entry.get("note"),
                                "resolved_by": entry.get("by_name"), "resolved_at": serialize(entry.get("at"))})
    return {**meta, "scope": "full", **data, "recommendations": recommendations,
            "notes": {key: notes.get(key) for key in ("worked", "improve", "logistics", "testimonies", "pastor_recommendations")}
            | {"updated_by": notes.get("updated_by_name"), "updated_at": serialize(notes.get("updated_at"))}}


async def _require_full(campaign_id: str, current_user: dict) -> dict:
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo la autoridad, el organizador o el encargado general")
    return campaign


@router.put("/{campaign_id}/report/recommendations/{recommendation_id:path}", response_model=dict)
async def set_recommendation_state(campaign_id: str, recommendation_id: str, payload: RecommendationState, current_user: dict = Depends(get_current_user)):
    """Marca una recomendación como resuelta (también en el reporte final)."""
    await _require_full(campaign_id, current_user)
    entry = {"resolved": payload.resolved, "note": (payload.note or "").strip() or None, "by_user_id": current_user["user_id"], "by_name": await actor_name(current_user), "at": now_utc()}
    await db.invasion_report_notes.update_one({"campaign_id": campaign_id}, {"$set": {f"resolved.{state_key(recommendation_id)}": entry}, "$setOnInsert": {"campaign_id": campaign_id}}, upsert=True)
    return {"id": recommendation_id, "resolved": payload.resolved}


@router.put("/{campaign_id}/report/notes", response_model=dict)
async def save_notes(campaign_id: str, payload: ReportNotes, current_user: dict = Depends(get_current_user)):
    """Lecciones aprendidas y recomendaciones del pastor: editables siempre,
    aunque el reporte final esté congelado."""
    await _require_full(campaign_id, current_user)
    fields = {key: (value or "").strip() or None for key, value in payload.model_dump(exclude_unset=True).items()}
    await db.invasion_report_notes.update_one({"campaign_id": campaign_id}, {"$set": {**fields, "updated_by_user_id": current_user["user_id"], "updated_by_name": await actor_name(current_user), "updated_at": now_utc()}, "$setOnInsert": {"campaign_id": campaign_id, "resolved": {}}}, upsert=True)
    notes = await load_notes(campaign_id)
    return {key: notes.get(key) for key in ("worked", "improve", "logistics", "testimonies", "pastor_recommendations")} | {"updated_by": notes.get("updated_by_name"), "updated_at": serialize(notes.get("updated_at"))}


@router.post("/{campaign_id}/report/finalize", response_model=dict)
async def finalize_report(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Cierra la invasión y congela el "Reporte final"."""
    campaign = await load_campaign(campaign_id)
    if not can_edit_participants(current_user, campaign):
        raise HTTPException(status_code=403, detail="Solo la autoridad, el organizador o el encargado general cierran la invasión")
    if campaign_state(campaign) == "upcoming":
        raise HTTPException(status_code=409, detail="La invasión todavía no empieza")
    await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$set": {"status": "closed", "closed_at": now_utc(), "closed_by_user_id": current_user["user_id"], "updated_at": now_utc()}})
    await freeze_report({**campaign, "status": "closed"}, current_user["user_id"])
    return await get_report(campaign_id, current_user)


async def ensure_indexes() -> None:
    await db.invasion_reports.create_index([("campaign_id", 1), ("final", 1)])
    await db.invasion_report_notes.create_index("campaign_id", unique=True)
