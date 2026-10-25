"""Perfil 360 · «Contactado por»: de dónde llegó la persona.

Lectura pura (backfill al vuelo, nada se duplica): visitas de invasión
(`outreach_visits`), intentos en la vivienda (`outreach_visit_events`),
bitácora de la visita (`outreach_visit_history`) y la bitácora de libros
(`library_movements`). «Mentor actual» sigue siendo SOLO la asignación de
Consolidación; quien la contactó se muestra aparte.

Asignar al mentor del contacto es un toque explícito (consolidation.assign,
con confirmación en la ficha) y usa el mismo mecanismo de «Iniciar 7
Semanas». Entregar un libro NUNCA abre Consolidación por sí solo."""
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import (
    CONSOLIDATION_ASSIGN,
    can_access_person,
    has_capability,
    is_global_pastoral_authority,
    normalized_capabilities,
)
from process_engine import serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/persons", tags=["person-contact"])

ACTIVE = ["planned", "active", "paused"]
BOOK_TYPES = ["DELIVERY", "LOAN", "DELIVERY_PENDING"]
OUTCOME_LABELS = {"conversation": "Conversó", "prayer": "Oró con la familia", "not_interested": "No le interesa", "return": "Volver otro día"}


async def load_person(person_id: str) -> dict:
    if not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=400, detail="person_id inválido")
    doc = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return {"person_id": person_id, "created_by": doc.get("created_by"), "auth_user_id": doc.get("auth_user_id")}


async def _names(person_ids) -> dict:
    oids = [ObjectId(item) for item in {pid for pid in person_ids if pid} if ObjectId.is_valid(item)]
    if not oids:
        return {}
    return {str(doc["_id"]): " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) or "Persona"
            async for doc in db.persons.find({"_id": {"$in": oids}}, {"nombre": 1, "apellido": 1})}


def _address(house: Optional[dict], visit: Optional[dict] = None) -> Optional[str]:
    source = house or visit or {}
    return " · ".join(filter(None, [source.get("address_line1"), source.get("address_line2")])) or (house or {}).get("street_name") or (visit or {}).get("contact_zone") or None


async def gather(person_id: str) -> dict:
    """Visitas, libros y expediente de la persona (sin escribir nada)."""
    visits = await db.outreach_visits.find({"$or": [{"person_id": person_id}, {"converted_person_id": person_id}], "archived": {"$ne": True}}, {"_id": 0}).sort("created_at", 1).to_list(50)
    books = await db.library_movements.find({"person_id": person_id, "movement_type": {"$in": BOOK_TYPES}, "is_reversal": {"$ne": True}}, {"_id": 0}).sort("occurred_at", 1).to_list(200)
    enrollment = await db.process_enrollments.find_one({"person_id": person_id, "process_key": "consolidation", "status": {"$in": ACTIVE}}, {"_id": 0}, sort=[("created_at", -1)])
    assignment = await db.mentor_assignments.find_one({"person_id": person_id, "active": True}, {"_id": 0}, sort=[("started_at", -1)])
    # Libros sin visita propia: la visita/hogar sale del movimiento.
    visit_ids = {item.get("visit_id") for item in books if item.get("visit_id")} - {item["visit_id"] for item in visits}
    if visit_ids:
        visits += await db.outreach_visits.find({"visit_id": {"$in": list(visit_ids)}, "archived": {"$ne": True}}, {"_id": 0}).to_list(50)
    house_ids = {item.get("household_id") for item in visits + books if item.get("household_id")}
    houses = {doc["household_id"]: doc async for doc in db.outreach_households.find({"household_id": {"$in": list(house_ids)}}, {"_id": 0})} if house_ids else {}
    campaign_ids = {item.get("campaign_id") for item in visits + books + list(houses.values()) if item.get("campaign_id")}
    campaigns = {doc["campaign_id"]: doc.get("name") or "Invasión" async for doc in db.outreach_campaigns.find({"campaign_id": {"$in": list(campaign_ids)}}, {"_id": 0, "campaign_id": 1, "name": 1})} if campaign_ids else {}
    # Quién entregó: el usuario dueño del inventario → su persona.
    user_ids = {(item.get("from_holder") or {}).get("id") for item in books if (item.get("from_holder") or {}).get("type") == "user"} | {item.get("actor_user_id") for item in books}
    keys = [uid for uid in user_ids if uid] + [ObjectId(uid) for uid in user_ids if uid and ObjectId.is_valid(uid)]
    user_person = {str(doc["_id"]): doc.get("person_id") async for doc in db.users.find({"_id": {"$in": keys}}, {"person_id": 1})} if keys else {}
    for item in books:
        holder = item.get("from_holder") or {}
        item["_mentor_person_id"] = user_person.get(holder.get("id")) if holder.get("type") == "user" else None
        if not item["_mentor_person_id"] and item.get("household_id") in houses:
            item["_mentor_person_id"] = houses[item["household_id"]].get("mentor_person_id")
    # Registro de visitantes (tabletas): número, servicio y fecha; nada confidencial.
    visitor_regs = await db.visitor_registrations.find({"person_id": person_id}, {"_id": 0, "visitor_number": 1, "service": 1, "created_at": 1, "visit": 1, "followup.status": 1}).sort("created_at", 1).to_list(50)
    return {"visits": visits, "books": books, "enrollment": enrollment, "assignment": assignment, "houses": houses, "campaigns": campaigns, "visitor_regs": visitor_regs}


def contact_mentor_ids(data: dict) -> set:
    ids = {item.get("mentor_person_id") for item in data["visits"]} | {item.get("_mentor_person_id") for item in data["books"]}
    ids |= {house.get("mentor_person_id") for house in data["houses"].values()}
    if data["enrollment"]:
        ids.add(data["enrollment"].get("mentor_person_id"))
    return {item for item in ids if item}


def can_assign(current_user: dict) -> bool:
    return is_global_pastoral_authority(current_user) or has_capability(current_user, CONSOLIDATION_ASSIGN)


async def can_read(person: dict, current_user: dict, data: dict) -> bool:
    if is_global_pastoral_authority(current_user) or current_user.get("person_id") == person["person_id"]:
        return True
    capabilities = normalized_capabilities(current_user)
    if any(item.startswith("person.") for item in capabilities) and can_access_person(current_user, person):
        return True
    if can_assign(current_user):
        return True
    # El mentor que la contactó o la acompaña ve solo esto (sin datos sensibles).
    return bool(current_user.get("person_id")) and current_user["person_id"] in contact_mentor_ids(data)


async def is_contact_mentor(person_id: str, current_user: dict) -> bool:
    if not current_user.get("person_id") or not ObjectId.is_valid(person_id):
        return False
    return current_user["person_id"] in contact_mentor_ids(await gather(person_id))


def build(data: dict, names: dict) -> dict:
    houses, campaigns = data["houses"], data["campaigns"]
    # Primer contacto: la visita más antigua; si no hay, el primer libro.
    first = None
    if data["visits"]:
        visit = data["visits"][0]
        house = houses.get(visit.get("household_id"))
        book = next((item for item in data["books"] if item.get("visit_id") == visit["visit_id"] or (item.get("household_id") and item.get("household_id") == visit.get("household_id"))), None)
        first = {"mentor_person_id": visit.get("mentor_person_id"), "at": visit.get("visit_date") or visit.get("created_at"), "campaign_id": visit.get("campaign_id"),
                 "household_id": visit.get("household_id"), "visit_id": visit["visit_id"], "address": _address(house, visit), "book": book}
    elif data["books"]:
        book = data["books"][0]
        first = {"mentor_person_id": book.get("_mentor_person_id"), "at": book.get("occurred_at"), "campaign_id": book.get("campaign_id") or (houses.get(book.get("household_id")) or {}).get("campaign_id"),
                 "household_id": book.get("household_id"), "visit_id": book.get("visit_id"), "address": _address(houses.get(book.get("household_id"))), "book": book}
    if first:
        book = first.pop("book")
        first.update({"mentor_name": names.get(first["mentor_person_id"]), "campaign_name": campaigns.get(first["campaign_id"]),
                      "book": {"movement_id": book["movement_id"], "book_name": book.get("book_name"), "quantity": book.get("quantity")} if book else None})
    books = [{"movement_id": item["movement_id"], "book_name": item.get("book_name"), "quantity": item.get("quantity"), "movement_type": item.get("movement_type"), "at": item.get("occurred_at"),
              "delivered_by": names.get(item.get("_mentor_person_id")) or item.get("from_holder_label"), "campaign_id": item.get("campaign_id") or (houses.get(item.get("household_id")) or {}).get("campaign_id"),
              "address": _address(houses.get(item.get("household_id")))} for item in data["books"]]
    for item in books:
        item["campaign_name"] = campaigns.get(item["campaign_id"])
    enrollment, assignment = data["enrollment"], data["assignment"]
    current = (assignment or {}).get("mentor_person_id") or (enrollment or {}).get("mentor_person_id")
    return {"first_contact": serialize(first), "books": serialize(books),
            "current_mentor": {"person_id": current, "name": names.get(current)} if current else None,
            "enrollment_id": (enrollment or {}).get("enrollment_id")}


async def history(data: dict, names: dict) -> list:
    """Recorrido completo, incluidas visitas pasadas (lectura; nada se copia)."""
    houses, campaigns = data["houses"], data["campaigns"]
    rows = []
    house_ids = list(houses)
    visit_event_ids = {item.get("visit_event_id") for item in data["visits"] if item.get("visit_event_id")}
    events = await db.outreach_visit_events.find({"$or": [{"household_id": {"$in": house_ids}}, {"visit_event_id": {"$in": list(visit_event_ids)}}], "is_draft": {"$ne": True}}, {"_id": 0}).sort("occurred_at", 1).to_list(200) if (house_ids or visit_event_ids) else []
    for event in events:
        house = houses.get(event.get("household_id"))
        opened = event.get("opened")
        detail = [OUTCOME_LABELS.get(event.get("outcome"))] if opened and event.get("outcome") else []
        if event.get("books_total"):
            detail.append(f"{event['books_total']} libro(s)")
        if opened and event.get("followup") == "yes":
            detail.append("aceptó seguimiento")
        rows.append({"kind": "visit", "title": "Visita · abrieron" if opened else "Visita · no abrieron", "at": event.get("occurred_at"), "mentor": names.get(event.get("mentor_person_id")),
                     "campaign": campaigns.get(event.get("campaign_id")), "address": _address(house), "detail": " · ".join(filter(None, detail)) or None})
    for item in data["books"]:
        rows.append({"kind": "book", "title": f"Libro entregado · {item.get('quantity') or 1} × {item.get('book_name')}", "at": item.get("occurred_at"), "mentor": names.get(item.get("_mentor_person_id")) or item.get("from_holder_label"),
                     "campaign": campaigns.get(item.get("campaign_id") or (houses.get(item.get("household_id")) or {}).get("campaign_id")), "address": _address(houses.get(item.get("household_id"))),
                     "movement_id": item["movement_id"], "detail": "sin conciliar" if item.get("movement_type") == "DELIVERY_PENDING" else None})
    visit_ids = [item["visit_id"] for item in data["visits"]]
    logs = await db.outreach_visit_history.find({"visit_id": {"$in": visit_ids}, "action": {"$in": ["visit_created", "seven_weeks_started", "mentor_transferred", "followup_updated"]}}, {"_id": 0}).sort("occurred_at", 1).to_list(200) if visit_ids else []
    by_visit = {item["visit_id"]: item for item in data["visits"]}
    titles = {"visit_created": "Contacto registrado", "seven_weeks_started": "Inició Consolidación (7 Semanas)", "mentor_transferred": "Visita reasignada a otro mentor", "followup_updated": "Seguimiento actualizado"}
    for log in logs:
        visit = by_visit.get(log["visit_id"]) or {}
        mentor_id = (log.get("detail") or {}).get("to") or (log.get("detail") or {}).get("mentor_person_id") or visit.get("mentor_person_id")
        rows.append({"kind": log["action"], "title": titles[log["action"]], "at": log.get("occurred_at"), "mentor": names.get(mentor_id),
                     "campaign": campaigns.get(visit.get("campaign_id")), "address": _address(houses.get(visit.get("household_id")), visit)})
    for visit in data["visits"]:
        if visit.get("followup_accepted") and not any(row["kind"] == "followup_updated" for row in rows):
            rows.append({"kind": "followup", "title": "Aceptó seguimiento", "at": visit.get("updated_at"), "mentor": names.get(visit.get("followup_responsible_person_id") or visit.get("mentor_person_id")),
                         "campaign": campaigns.get(visit.get("campaign_id")), "address": _address(houses.get(visit.get("household_id")), visit),
                         "detail": " · ".join(filter(None, [visit.get("next_action"), serialize(visit.get("next_action_at"))[:10] if visit.get("next_action_at") else None])) or None})
    for item in data.get("visitor_regs") or []:
        rows.append({"kind": "visitor_registration", "title": f"Registro de visitante · {item['visitor_number']}", "at": item.get("created_at"), "mentor": None,
                     "campaign": None, "address": None,
                     "detail": " · ".join(filter(None, [(item.get("service") or {}).get("label"), "Primera visita" if (item.get("visit") or {}).get("first_visit") else None]))})
    rows.sort(key=lambda row: serialize(row.get("at")) or "")
    return serialize(rows)


@router.get("/{person_id}/contact-origin", response_model=dict)
async def contact_origin(person_id: str, current_user: dict = Depends(get_current_user)):
    person = await load_person(person_id)
    data = await gather(person_id)
    if not await can_read(person, current_user, data):
        raise HTTPException(status_code=403, detail="Sin acceso a esta persona")
    mentor_ids = contact_mentor_ids(data)
    for visit in data["visits"]:
        mentor_ids |= {visit.get("followup_responsible_person_id")}
    if data["assignment"]:
        mentor_ids.add(data["assignment"].get("mentor_person_id"))
    names = await _names(mentor_ids)
    result = build(data, names)
    first = result["first_contact"] or {}
    pending = not (result["current_mentor"] or {}).get("person_id")
    result["history"] = await history(data, names)
    result["can_assign"] = bool(pending and first.get("mentor_person_id") and can_assign(current_user))
    result["viewer_is_contact_mentor"] = bool(current_user.get("person_id")) and current_user["person_id"] in mentor_ids
    return result


class AssignInput(BaseModel):
    mentor_person_id: Optional[str] = Field(default=None, max_length=80)


@router.post("/{person_id}/assign-contact-mentor", response_model=dict)
async def assign_contact_mentor(person_id: str, payload: AssignInput, current_user: dict = Depends(get_current_user)):
    """«Asignar a <quien la contactó>»: abre o completa el expediente de
    Consolidación con el MISMO mecanismo de «Iniciar 7 Semanas»."""
    if not can_assign(current_user):
        raise HTTPException(status_code=403, detail="Solo quien asigna en Consolidación")
    await load_person(person_id)
    data = await gather(person_id)
    names = await _names(contact_mentor_ids(data))
    first = build(data, names)["first_contact"] or {}
    mentor_person_id = payload.mentor_person_id or first.get("mentor_person_id")
    if not mentor_person_id or mentor_person_id not in contact_mentor_ids(data):
        raise HTTPException(status_code=422, detail="Esta persona no tiene un mentor de contacto registrado")
    if data["assignment"]:
        raise HTTPException(status_code=409, detail="Ya tiene mentor asignado en Consolidación")
    from consolidation_service import assert_mentor_eligible, assign_mentor
    from mentorship_outreach import log_visit_history, open_consolidation_from_visit
    await assert_mentor_eligible(db, mentor_person_id)
    reason = "Asignado al mentor que la contactó (Perfil 360)"
    visit = next((item for item in data["visits"] if item.get("mentor_person_id") == mentor_person_id and not item.get("enrollment_id")), None)
    if visit and not data["enrollment"]:
        enrollment, _ = await open_consolidation_from_visit(visit, person_id, current_user, reason)
    else:
        enrollment = data["enrollment"]
        if not enrollment:
            from process_engine import create_enrollment
            from consolidation_service import configure_entry_stages
            enrollment, created = await create_enrollment(db, "consolidation", person_id, mentor_person_id, current_user["user_id"], status="active",
                                                          next_action="Dar seguimiento al visitante", source="person_contact", source_id=first.get("visit_id") or person_id)
            if created:
                await configure_entry_stages(db, enrollment, "invasion", current_user["user_id"], mentor_person_id=mentor_person_id)
                enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
        await assign_mentor(db, enrollment, mentor_person_id, current_user["user_id"], reason)
        if visit:
            await db.outreach_visits.update_one({"visit_id": visit["visit_id"]}, {"$set": {"enrollment_id": enrollment["enrollment_id"], "converted_person_id": person_id}})
            await log_visit_history(visit["visit_id"], current_user, "seven_weeks_started", {"enrollment_id": enrollment["enrollment_id"], "person_id": person_id, "reused_existing_enrollment": True})
    return {"enrollment_id": enrollment["enrollment_id"], "mentor_person_id": mentor_person_id, "mentor_name": names.get(mentor_person_id)}
