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

from invasion_participants import ROLE_LABELS, ROLES, can_edit_participants, load_campaign
from invasion_prayer import prayer_summary
from mentorship_outreach import campaign_book_rows, now_utc, serialize
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


def campaign_state(campaign: dict) -> str:
    today = date.today().isoformat()
    if campaign.get("status") == "closed":
        return "closed"
    if (campaign.get("start_date") or today) > today:
        return "upcoming"
    if (campaign.get("end_date") or campaign.get("start_date") or today) >= today:
        return "active"
    return "finished"


async def compute_report(campaign: dict) -> dict:
    """Todas las secciones con datos vivos (lo que se congela al cerrar)."""
    campaign_id = campaign["campaign_id"]
    authorities = await principal_authority_person_ids(db)
    participants = [row for row in await db.invasion_participants.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(3000) if row["person_id"] not in authorities]
    households = await db.outreach_households.find({"campaign_id": campaign_id, "archived": {"$ne": True}}, {"_id": 0, "household_id": 1, "mentor_person_id": 1, "sector": 1, "status": 1, "latitude": 1}).to_list(5000)
    events = await db.outreach_visit_events.find({"campaign_id": campaign_id}, {"_id": 0, "household_id": 1, "mentor_person_id": 1, "result": 1, "occurred_at": 1}).to_list(20000)
    visits = [visit for visit in await db.outreach_visits.find({"campaign_id": campaign_id, "archived": {"$ne": True}}, {"_id": 0, "visit_id": 1, "mentor_person_id": 1, "status": 1, "received_mcd": 1, "received_npt": 1, "lbs_decision": 1, "enrollment_id": 1, "contact_zone": 1, "household_id": 1, "created_at": 1, "front_group_id": 1}).to_list(20000)
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
        "participation": {"totals": participation_counts(participants), "by_role": by_role, "by_group": by_group},
        "field": {
            "houses": {"available": sum(1 for house in households if not house.get("mentor_person_id")),
                       "assigned": sum(1 for house in households if house.get("mentor_person_id")),
                       "visited": len(visited_houses & {house["household_id"] for house in households}),
                       "located": sum(1 for house in households if house.get("latitude") is not None), "total": len(households)},
            "by_day": [{"day": key, **value} for key, value in sorted(by_day.items())],
            "by_sector": sorted(({"sector": key, **value, "coverage_pct": round(value["visited"] / value["houses"] * 100) if value["houses"] else None} for key, value in by_sector.items()), key=lambda item: -item["people"]),
            "results": results,
            "attempts_by_result": [{"result": key, "label": RESULT_LABELS.get(key, key), "total": value} for key, value in attempts_by_result.items() if key],
        },
        "ranking": {"mentors": mentor_rows, "teams": teams},
        "prayer": prayer_report(prayer) if prayer else None,
        # Lo que mostraba el "Informe" anterior: libros asignados/entregados por mentor.
        "books": [row for row in await campaign_book_rows(campaign) if row["mentor_person_id"] not in authorities],
        "followup": {key: value for key, value in followup.items() if key != "unattended_items"},
        "goals": goals,
        "comparison": await comparison_section(campaign, key_figures),
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
    return {**meta, "scope": "full", **data}


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
