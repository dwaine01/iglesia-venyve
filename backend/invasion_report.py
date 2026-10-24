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
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from invasion_participants import ROLE_LABELS, ROLES, can_edit_participants, load_campaign
from invasion_prayer import prayer_summary
from mentorship_outreach import campaign_book_rows, now_utc, serialize
from participation_scope import principal_authority_person_ids
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
    return {
        "version": REPORT_VERSION,
        "summary": {
            "name": campaign.get("name"), "start_date": campaign.get("start_date"), "end_date": campaign.get("end_date"),
            "location": campaign.get("location"), "purpose": campaign.get("purpose"), "description": campaign.get("description"),
            "organizer": campaign.get("created_by_name"), "general_lead": names.get(campaign.get("general_lead_person_id")),
            "logistics_lead": names.get(campaign.get("logistics_lead_person_id")), "state": campaign_state(campaign),
            "key_figures": {
                "houses_visited": len(visited_houses & {house["household_id"] for house in households}), "houses_total": len(households),
                "people_reached": len(visits), "wants_followup": results["wants_followup"], "seven_weeks": results["seven_weeks"],
                "participants": total_participants, "attended": attended_total,
                "attendance_pct": round(attended_total / total_participants * 100) if total_participants else None,
            },
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
        "prayer": {"period": prayer["period"], "totals": prayer["totals"]} if prayer else None,
        # Lo que mostraba el "Informe" anterior: libros asignados/entregados por mentor.
        "books": [row for row in await campaign_book_rows(campaign) if row["mentor_person_id"] not in authorities],
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
