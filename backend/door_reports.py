"""Puerta a puerta · tramo 4: reportes por mentor, equipo (Grupo Frontal del
mentor), calle e invasión.

Sin duplicados: la unidad es la VIVIENDA (`outreach_households`, cada
apartamento es una vivienda). Tres visitas a una casa = 1 vivienda visitada y
3 intentos; el historial completo queda en `outreach_visit_events`. Las
personas (`outreach_visits`) se cuentan aparte (una vivienda puede tener
varias).

Idioma, religión y origen solo salen como totales agregados (nunca por
persona) y religión/origen solo de lo que la persona compartió.

Todo sale de tres consultas (viviendas, intentos, personas) sin N+1."""
from collections import Counter, defaultdict
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException

from mentorship_outreach import can_use_outreach, now_utc, serialize
from outreach_doors import CONVERSED, _norm, event_opened
from participation_scope import principal_authority_person_ids
from server import db, get_current_user

router = APIRouter(prefix="/api/mentorship/outreach", tags=["outreach-door-reports"])

METRICS = ("houses_visited", "attempts", "opened", "not_opened", "conversed", "invited_in", "houses_with_books", "books",
           "followup_houses", "followup_people", "consolidation", "people", "pending_revisit", "followup_scheduled")
LANGUAGE_LABELS = {"es": "Español", "en": "Inglés", "other": "Otro", "unknown": "No se supo"}
NO_STREET = "Sin calle registrada"


def _empty() -> dict:
    return {key: 0 for key in METRICS}


def _add(target: dict, source: dict) -> None:
    for key in METRICS:
        target[key] += source.get(key, 0)


async def door_report_data(campaign_id: str, mentor_person_id: Optional[str] = None) -> dict:
    """Totales + filas por mentor, equipo y calle. `mentor_person_id` limita al
    trabajo de un mentor (su propio reporte)."""
    authorities = await principal_authority_person_ids(db)
    match: dict = {"campaign_id": campaign_id, "archived": {"$ne": True}}
    if mentor_person_id:
        match["mentor_person_id"] = mentor_person_id
    houses = await db.outreach_households.find(match, {"_id": 0, "household_id": 1, "mentor_person_id": 1, "front_group_id": 1, "street_name": 1, "sector": 1,
                                                       "door_status": 1}).to_list(20000)
    houses = [house for house in houses if house.get("mentor_person_id") not in authorities]
    house_ids = [house["household_id"] for house in houses]
    events = await db.outreach_visit_events.find({"household_id": {"$in": house_ids}, "is_draft": {"$ne": True}},
                                                 {"_id": 0, "household_id": 1, "opened": 1, "result": 1, "contact_level": 1, "books_total": 1, "followup": 1,
                                                  "language": 1, "language_basis": 1, "religion": 1, "origin": 1, "shared_by_person": 1, "occurred_at": 1}).to_list(60000) if house_ids else []
    visit_match = {"campaign_id": campaign_id, "archived": {"$ne": True}}
    if mentor_person_id:
        visit_match["mentor_person_id"] = mentor_person_id
    visits = [visit for visit in await db.outreach_visits.find(visit_match, {"_id": 0, "visit_id": 1, "household_id": 1, "mentor_person_id": 1, "status": 1, "enrollment_id": 1}).to_list(20000)
              if visit.get("mentor_person_id") not in authorities]

    events_of: dict[str, list] = defaultdict(list)
    for event in events:
        events_of[event["household_id"]].append(event)
    people_of: dict[str, list] = defaultdict(list)
    for visit in visits:
        people_of[visit.get("household_id") or ""].append(visit)

    # Equipo = Grupo Frontal del mentor (el de la vivienda al tomarla; si falta, la asignación activa).
    mentor_ids = {house.get("mentor_person_id") for house in houses if house.get("mentor_person_id")} | {visit.get("mentor_person_id") for visit in visits if visit.get("mentor_person_id")}
    group_of: dict[str, str] = {}
    for item in sorted(await db.front_group_assignments.find({"person_id": {"$in": list(mentor_ids)}, "active": True}, {"_id": 0, "person_id": 1, "front_group_id": 1, "role": 1}).to_list(5000),
                       key=lambda entry: {"leader": 0, "co_leader": 1}.get(entry.get("role"), 2)):
        group_of.setdefault(item["person_id"], item["front_group_id"])

    def team_of(house: dict) -> str:
        return house.get("front_group_id") or group_of.get(house.get("mentor_person_id") or "", "")

    by_mentor: dict[str, dict] = defaultdict(_empty)
    by_team: dict[str, dict] = defaultdict(_empty)
    by_street: dict[str, dict] = defaultdict(_empty)
    street_label: dict[str, str] = {}
    street_mentors: dict[str, set] = defaultdict(set)
    totals = _empty()
    language: Counter = Counter()
    language_basis: Counter = Counter()
    religion: Counter = Counter()
    origin: Counter = Counter()
    shared_houses = 0

    for house in houses:
        house_events = sorted(events_of.get(house["household_id"], []), key=lambda item: str(item.get("occurred_at") or ""))
        people = people_of.get(house["household_id"], [])
        row = _empty()
        if house_events:
            opened = any(event_opened(item) for item in house_events)
            books = sum(item.get("books_total") or 0 for item in house_events)
            row.update({
                "houses_visited": 1, "attempts": len(house_events), "opened": int(opened), "not_opened": int(not opened),
                "conversed": int(any(item.get("contact_level") in CONVERSED for item in house_events)),
                "invited_in": int(any(item.get("contact_level") == "invited_in" for item in house_events)),
                "houses_with_books": int(books > 0), "books": books,
                "followup_houses": int(any(item.get("followup") == "yes" for item in house_events)),
                "pending_revisit": int(house.get("door_status") == "pending_revisit"),
                "followup_scheduled": int(house.get("door_status") == "followup_scheduled"),
            })
            # Perfil: el último dato conocido de cada vivienda (una vivienda cuenta una vez).
            spoken = next((item for item in reversed(house_events) if item.get("language")), None)
            if spoken:
                language[spoken["language"]] += 1
                language_basis[spoken.get("language_basis") or "impression"] += 1
            shared = [item for item in house_events if item.get("shared_by_person")]
            if shared:
                shared_houses += 1
                last_religion = next((item["religion"] for item in reversed(shared) if item.get("religion")), None)
                last_origin = next((item["origin"] for item in reversed(shared) if item.get("origin")), None)
                if last_religion:
                    religion[last_religion.strip().capitalize()] += 1
                if last_origin:
                    origin[last_origin.strip().capitalize()] += 1
        row["people"] = len(people)
        row["followup_people"] = sum(1 for visit in people if visit.get("status") == "wants_followup" or visit.get("enrollment_id"))
        row["consolidation"] = sum(1 for visit in people if visit.get("enrollment_id"))
        street = (house.get("street_name") or house.get("sector") or "").strip()
        street_key = _norm(street) or ""
        street_label.setdefault(street_key, street or NO_STREET)
        if house.get("mentor_person_id"):
            street_mentors[street_key].add(house["mentor_person_id"])
        for bucket, key in ((by_mentor, house.get("mentor_person_id") or ""), (by_team, team_of(house)), (by_street, street_key)):
            _add(bucket[key], row)
        _add(totals, row)

    # Personas sin vivienda («Persona sin vivienda»): cuentan en mentor/equipo, no en una calle.
    for visit in people_of.get("", []):
        row = _empty()
        row.update({"people": 1, "followup_people": int(visit.get("status") == "wants_followup" or bool(visit.get("enrollment_id"))), "consolidation": int(bool(visit.get("enrollment_id")))})
        mentor = visit.get("mentor_person_id") or ""
        _add(by_mentor[mentor], row)
        _add(by_team[group_of.get(mentor, "")], row)
        _add(totals, row)

    from invasion_report import _names
    names = await _names(set(by_mentor) | {pid for ids in street_mentors.values() for pid in ids})
    group_names = {doc["front_group_id"]: doc.get("name") or "Grupo sin nombre"
                   async for doc in db.front_groups.find({"front_group_id": {"$in": [key for key in by_team if key]}}, {"_id": 0, "front_group_id": 1, "name": 1})}

    # Inicio, fin y duración de cada calle (tramos de «Comenzar/Terminar calle» de los mentores).
    from door_streets import street_timing
    part_match = {"campaign_id": campaign_id, "street_sessions.0": {"$exists": True}}
    if mentor_person_id:
        part_match["mentor_person_id"] = mentor_person_id
    sessions = [item async for doc in db.outreach_participations.find(part_match, {"_id": 0, "mentor_person_id": 1, "street_sessions": 1})
                if doc.get("mentor_person_id") not in authorities for item in doc.get("street_sessions") or []]
    timing = street_timing(sessions)

    def ordered(rows: list[dict]) -> list[dict]:
        # Orden por trabajo hecho, sin puntajes ni posiciones (no es un ranking).
        return sorted(rows, key=lambda item: (-item["houses_visited"], -item["people"], item["name"]))

    def top(counter: Counter, limit: int = 8) -> list[dict]:
        items = counter.most_common()
        rows = [{"key": key, "label": key, "total": value} for key, value in items[:limit]]
        rest = sum(value for _, value in items[limit:])
        if rest:
            rows.append({"key": "_other", "label": "Otros", "total": rest})
        return rows

    return {
        "totals": totals,
        "by_mentor": ordered([{"mentor_person_id": key or None, "name": names.get(key, "Sin mentor"), "front_group": group_names.get(group_of.get(key, "")), **value}
                              for key, value in by_mentor.items()]),
        "by_team": ordered([{"front_group_id": key or None, "name": group_names.get(key, "Sin Grupo Frontal"), **value} for key, value in by_team.items()]),
        "by_street": ordered([{"street_key": key, "name": street_label[key], "mentors": sorted(names.get(pid, "Mentor") for pid in street_mentors.get(key, set())),
                               **{field: (timing.get(key) or {}).get(field) for field in ("started_at", "ended_at", "duration_minutes")}, **value}
                              for key, value in by_street.items()]),
        "profile": {
            "language": [{"key": key, "label": LANGUAGE_LABELS.get(key, key), "total": value} for key, value in language.most_common()],
            "language_confirmed": language_basis.get("confirmed", 0), "language_impression": language_basis.get("impression", 0),
            "shared_houses": shared_houses, "religion": top(religion), "origin": top(origin),
        },
    }


# ------------------------------------------------------------------ API
async def report_scope(campaign_id: str, current_user: dict) -> tuple[dict, bool]:
    from household_location import campaign_doc, sees_whole_campaign
    from invasion_participants import can_edit_participants
    campaign = await campaign_doc(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    if sees_whole_campaign(current_user, campaign) or can_edit_participants(current_user, campaign):
        return campaign, True
    if not current_user.get("person_id") or not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar el reporte")
    return campaign, False


@router.get("/campaigns/{campaign_id}/door-report", response_model=dict)
async def door_report(campaign_id: str, mentor_person_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """El mentor ve solo su trabajo (por calle). Liderazgo, organizador y
    autoridad ven toda la invasión por mentor, equipo y calle."""
    campaign, full = await report_scope(campaign_id, current_user)
    if not full:
        if mentor_person_id and mentor_person_id != current_user.get("person_id"):
            raise HTTPException(status_code=403, detail="Solo puede consultar su propio trabajo")
        mentor_person_id = current_user["person_id"]
    data = await door_report_data(campaign_id, mentor_person_id)
    if not full:
        # Su propio reporte: sin filas de otros ni equipos.
        data["by_team"] = []
        data["by_mentor"] = [row for row in data["by_mentor"] if row["mentor_person_id"] == mentor_person_id]
    return {"campaign_id": campaign_id, "campaign_name": campaign.get("name"), "scope": "all" if full and not mentor_person_id else "mine" if not full else "mentor",
            "generated_at": serialize(now_utc()), **serialize(data)}


DRILL = Literal["houses_visited", "opened", "not_opened", "conversed", "invited_in", "houses_with_books", "followup_houses", "pending_revisit", "followup_scheduled"]


@router.get("/campaigns/{campaign_id}/door-report/houses", response_model=dict)
async def door_report_houses(campaign_id: str, metric: DRILL = "houses_visited", mentor_person_id: Optional[str] = None, front_group_id: Optional[str] = None,
                             street_key: Optional[str] = None, offset: int = 0, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Las viviendas detrás de cada cifra (cifras con clic)."""
    _, full = await report_scope(campaign_id, current_user)
    if not full:
        if mentor_person_id and mentor_person_id != current_user.get("person_id"):
            raise HTTPException(status_code=403, detail="Solo puede consultar su propio trabajo")
        mentor_person_id = current_user["person_id"]
    query: dict = {"campaign_id": campaign_id, "archived": {"$ne": True}, "attempts_count": {"$gt": 0}}
    if mentor_person_id:
        query["mentor_person_id"] = mentor_person_id
    if front_group_id:
        query["front_group_id"] = front_group_id
    query.update({"opened": {"opened_ever": True}, "not_opened": {"opened_ever": {"$ne": True}}, "conversed": {"conversed_ever": True},
                  "houses_with_books": {"books_total": {"$gt": 0}}, "pending_revisit": {"door_status": "pending_revisit"},
                  "followup_scheduled": {"door_status": "followup_scheduled"}}.get(metric, {}))
    keys = {"_id": 0, "household_id": 1, "address_line1": 1, "address_line2": 1, "street_name": 1, "sector": 1, "door_status": 1, "last_result": 1, "last_attempt_at": 1,
            "attempts_count": 1, "books_total": 1, "followup_date": 1, "mentor_person_id": 1, "front_group_id": 1}
    items = await db.outreach_households.find(query, keys).sort("last_attempt_at", -1).to_list(20000)
    authorities = await principal_authority_person_ids(db)
    items = [item for item in items if item.get("mentor_person_id") not in authorities]
    if street_key is not None:
        items = [item for item in items if _norm((item.get("street_name") or item.get("sector") or "").strip()) == street_key]
    if metric in {"invited_in", "followup_houses"}:
        condition = {"contact_level": "invited_in"} if metric == "invited_in" else {"followup": "yes"}
        matching = set(await db.outreach_visit_events.distinct("household_id", {"household_id": {"$in": [item["household_id"] for item in items]}, "is_draft": {"$ne": True}, **condition}))
        items = [item for item in items if item["household_id"] in matching]
    limit = max(1, min(limit, 100))
    page = items[offset:offset + limit]
    from mentorship_outreach import person_display_name
    names = {pid: await person_display_name(pid) for pid in {item.get("mentor_person_id") for item in page} if pid}
    for item in page:
        item["mentor_name"] = names.get(item.get("mentor_person_id"))
    return {"metric": metric, "total": len(items), "items": serialize(page)}
