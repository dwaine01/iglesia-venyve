"""Voluntariado, inscripciones, check-in móvil y cierre de asistencia."""
import re
import secrets
from datetime import timezone
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from membership_documents import membership_id_from_token
from operations_engine import (
    audit, can_checkin, can_manage, can_reports, canonical_person,
    materialize_shifts_for_occurrence, notify_person, now_utc,
    require_operations_checkin, require_operations_manage,
    require_operations_view, serialize,
)
from operations_models import (
    AttendanceClose, CheckInCreate, RegistrationCreate, ShiftTemplateCreate,
    VolunteerAssignmentAction, VolunteerAssignmentCreate,
)
from server import db


router = APIRouter(prefix="/api/operations", tags=["operations-participation"])


async def _occurrence_or_404(occurrence_id: str) -> tuple[dict, dict]:
    occurrence = await db.operation_event_occurrences.find_one({"occurrence_id": occurrence_id}, {"_id": 0})
    if not occurrence: raise HTTPException(status_code=404, detail="Ocurrencia no encontrada")
    event = await db.operation_events.find_one({"event_id": occurrence["event_id"]}, {"_id": 0})
    if not event: raise HTTPException(status_code=404, detail="Evento no encontrado")
    return occurrence, event


async def _person_name_map(person_ids: list[str]) -> dict[str, dict]:
    oids = [ObjectId(item) for item in set(person_ids) if ObjectId.is_valid(item)]
    people = await db.persons.find({"_id": {"$in": oids}}, {"_id": 1, "nombre": 1, "apellido": 1, "person_number": 1}).to_list(5000)
    return {str(item["_id"]): {"name": " ".join(filter(None, [item.get("nombre"), item.get("apellido")])).strip(), "person_number": item.get("person_number")} for item in people}


async def occurrence_metrics(occurrence_id: str) -> dict:
    registrations = await db.operation_registrations.find({"occurrence_id": occurrence_id, "status": {"$ne": "cancelled"}}, {"_id": 0, "party_size": 1}).to_list(10000)
    checkins = await db.operation_checkins.count_documents({"occurrence_id": occurrence_id, "status": "active"})
    shifts = await db.operation_shifts.find({"occurrence_id": occurrence_id}, {"_id": 0, "shift_id": 1, "required_volunteers": 1}).to_list(1000)
    shift_ids = [item["shift_id"] for item in shifts]
    confirmed = await db.operation_volunteer_assignments.count_documents({"shift_id": {"$in": shift_ids}, "status": {"$in": ["confirmed", "checked_in"]}})
    volunteer_checkins = await db.operation_volunteer_assignments.count_documents({"shift_id": {"$in": shift_ids}, "status": "checked_in"})
    registered_people = sum(item.get("party_size", 1) for item in registrations)
    return {"registered_people": registered_people, "checkins": checkins, "attendance_rate": round(checkins * 100 / registered_people, 1) if registered_people else 0, "required_volunteers": sum(item.get("required_volunteers", 0) for item in shifts), "confirmed_volunteers": confirmed, "volunteer_checkins": volunteer_checkins, "open_volunteer_slots": max(0, sum(item.get("required_volunteers", 0) for item in shifts) - confirmed)}


@router.get("/occurrences/{occurrence_id}", response_model=dict)
async def occurrence_detail(occurrence_id: str, current_user: dict = Depends(require_operations_view)):
    occurrence, event = await _occurrence_or_404(occurrence_id); privileged = can_checkin(current_user) or can_manage(current_user)
    shifts = await db.operation_shifts.find({"occurrence_id": occurrence_id}, {"_id": 0}).sort("starts_at", 1).to_list(1000)
    assignments = await db.operation_volunteer_assignments.find({"occurrence_id": occurrence_id}, {"_id": 0}).to_list(5000)
    registrations = await db.operation_registrations.find({"occurrence_id": occurrence_id}, {"_id": 0}).sort("created_at", 1).to_list(10000)
    if not privileged:
        assignments = [item for item in assignments if item.get("person_id") == current_user.get("person_id")]
        registrations = [item for item in registrations if item.get("person_id") == current_user.get("person_id")]
    person_ids = [item.get("person_id") for item in assignments + registrations if item.get("person_id")]
    names = await _person_name_map(person_ids)
    for item in assignments: item["person"] = names.get(item["person_id"], {})
    for item in registrations:
        if item.get("person_id"): item["person"] = names.get(item["person_id"], {})
        if not privileged:
            item.pop("guest_email", None); item.pop("guest_phone", None); item.pop("notes", None)
    checkins = []
    if privileged:
        checkins = await db.operation_checkins.find({"occurrence_id": occurrence_id, "status": "active"}, {"_id": 0}).sort("checked_in_at", -1).limit(5000).to_list(5000)
    return serialize({"occurrence": occurrence, "event": event, "metrics": await occurrence_metrics(occurrence_id), "shifts": shifts, "assignments": assignments, "registrations": registrations, "checkins": checkins, "permissions": {"manage": can_manage(current_user), "checkin": can_checkin(current_user), "reports": can_reports(current_user)}})


@router.post("/events/{event_id}/shift-templates", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_shift_template(event_id: str, payload: ShiftTemplateCreate, current_user: dict = Depends(require_operations_manage)):
    event = await db.operation_events.find_one({"event_id": event_id, "status": {"$ne": "archived"}}, {"_id": 0})
    if not event: raise HTTPException(status_code=404, detail="Evento no encontrado")
    if payload.occurrence_id and not await db.operation_event_occurrences.find_one({"occurrence_id": payload.occurrence_id, "event_id": event_id}, {"_id": 1}): raise HTTPException(status_code=422, detail="La ocurrencia no pertenece al evento")
    now = now_utc(); template_id = str(uuid4()); doc = {"_id": template_id, "template_id": template_id, "event_id": event_id, **payload.model_dump(), "active": True, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.operation_shift_templates.insert_one(doc)
    query = {"event_id": event_id, "status": {"$in": ["scheduled", "checkin_open"]}}
    if payload.scope == "single_occurrence": query["occurrence_id"] = payload.occurrence_id
    occurrences = await db.operation_event_occurrences.find(query, {"_id": 0}).to_list(500)
    created = sum([await materialize_shifts_for_occurrence(event, item) for item in occurrences])
    await audit(current_user, "shift_template_created", "event", event_id, {"template_id": template_id, "shifts_created": created})
    return serialize({**doc, "shifts_created": created})


@router.post("/shifts/{shift_id}/assignments", status_code=status.HTTP_201_CREATED, response_model=dict)
async def assign_volunteer(shift_id: str, payload: VolunteerAssignmentCreate, current_user: dict = Depends(require_operations_manage)):
    shift = await db.operation_shifts.find_one({"shift_id": shift_id, "status": "open"}, {"_id": 0})
    if not shift: raise HTTPException(status_code=404, detail="Turno abierto no encontrado")
    person = await canonical_person(payload.person_id); assignment_id = str(uuid4()); now = now_utc()
    doc = {"_id": assignment_id, "assignment_id": assignment_id, "event_id": shift["event_id"], "occurrence_id": shift["occurrence_id"], "shift_id": shift_id, "person_id": person["person_id"], "status": "invited", "notes": payload.notes, "assigned_by_user_id": current_user["user_id"], "assigned_at": now, "updated_at": now}
    try: await db.operation_volunteer_assignments.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(status_code=409, detail="La Persona ya está asignada a este turno")
    event = await db.operation_events.find_one({"event_id": shift["event_id"]}, {"_id": 0, "title": 1})
    await notify_person(person["person_id"], shift["event_id"], "Nuevo turno de voluntariado", f"{event.get('title', 'Evento')} · {shift['name']}", "volunteer_assignment")
    await audit(current_user, "volunteer_assigned", "shift", shift_id, {"assignment_id": assignment_id, "person_id": person["person_id"]})
    return serialize({**doc, "person": person})


@router.patch("/volunteer-assignments/{assignment_id}", response_model=dict)
async def respond_assignment(assignment_id: str, payload: VolunteerAssignmentAction, current_user: dict = Depends(require_operations_view)):
    assignment = await db.operation_volunteer_assignments.find_one({"assignment_id": assignment_id}, {"_id": 0})
    if not assignment: raise HTTPException(status_code=404, detail="Asignación no encontrada")
    if not can_manage(current_user) and assignment.get("person_id") != current_user.get("person_id"): raise HTTPException(status_code=403, detail="Solo la Persona asignada puede responder")
    result = await db.operation_volunteer_assignments.find_one_and_update({"assignment_id": assignment_id}, {"$set": {"status": payload.status, "response_notes": payload.response_notes, "responded_at": now_utc(), "updated_at": now_utc()}}, return_document=ReturnDocument.AFTER, projection={"_id": 0})
    await audit(current_user, f"volunteer_{payload.status}", "volunteer_assignment", assignment_id)
    return serialize(result)


@router.post("/occurrences/{occurrence_id}/registrations", status_code=status.HTTP_201_CREATED, response_model=dict)
async def register_attendee(occurrence_id: str, payload: RegistrationCreate, current_user: dict = Depends(require_operations_view)):
    occurrence, event = await _occurrence_or_404(occurrence_id)
    if occurrence["status"] in {"closed", "cancelled"} or event["registration_mode"] == "closed": raise HTTPException(status_code=409, detail="Las inscripciones están cerradas")
    person = await canonical_person(payload.person_id) if payload.person_id else None
    if not can_checkin(current_user) and not can_manage(current_user):
        if not person or person["person_id"] != current_user.get("person_id"): raise HTTPException(status_code=403, detail="Solo puede inscribirse a sí mismo")
    current_total = sum(item.get("party_size", 1) for item in await db.operation_registrations.find({"occurrence_id": occurrence_id, "status": {"$ne": "cancelled"}}, {"_id": 0, "party_size": 1}).to_list(10000))
    registration_status = "waitlisted" if occurrence.get("capacity") and current_total + payload.party_size > occurrence["capacity"] else "registered"
    registration_id = str(uuid4()); code = f"OP-{secrets.token_hex(4).upper()}"; now = now_utc()
    doc = {"_id": registration_id, "registration_id": registration_id, "registration_code": code, "occurrence_id": occurrence_id, "event_id": event["event_id"], "status": registration_status, "party_size": payload.party_size, "source": "staff" if can_checkin(current_user) else "self", "registered_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now, "notes": payload.notes}
    if person: doc["person_id"] = person["person_id"]
    else: doc.update({"guest_name": payload.guest_name.strip(), "guest_email": str(payload.guest_email) if payload.guest_email else None, "guest_phone": payload.guest_phone})
    try: await db.operation_registrations.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(status_code=409, detail="La Persona ya está inscrita en esta ocurrencia")
    await audit(current_user, "attendee_registered", "occurrence", occurrence_id, {"registration_id": registration_id, "person_id": doc.get("person_id"), "status": registration_status})
    return serialize({**doc, "person": person})


@router.get("/occurrences/{occurrence_id}/checkin/search", response_model=dict)
async def checkin_search(occurrence_id: str, q: str = Query(min_length=2, max_length=100), current_user: dict = Depends(require_operations_checkin)):
    await _occurrence_or_404(occurrence_id); needle = re.sub(r"\s+", " ", q.strip().lower())
    people = await db.persons.find({"is_archived": {"$ne": True}, "$or": [{"search_key": {"$regex": re.escape(needle)}}, {"person_number": {"$regex": re.escape(q), "$options": "i"}}]}, {"_id": 1, "nombre": 1, "apellido": 1, "person_number": 1}).limit(20).to_list(20)
    registrations = await db.operation_registrations.find({"occurrence_id": occurrence_id, "$or": [{"guest_name": {"$regex": re.escape(q), "$options": "i"}}, {"registration_code": {"$regex": re.escape(q), "$options": "i"}}]}, {"_id": 0}).limit(20).to_list(20)
    items = []
    for person in people:
        person_id = str(person["_id"]); registration = await db.operation_registrations.find_one({"occurrence_id": occurrence_id, "person_id": person_id, "status": {"$ne": "cancelled"}}, {"_id": 0})
        duplicate = await db.operation_checkins.find_one({"occurrence_id": occurrence_id, "person_id": person_id, "status": "active"}, {"_id": 0, "checked_in_at": 1})
        items.append({"kind": "person", "person_id": person_id, "registration_id": registration.get("registration_id") if registration else None, "name": " ".join(filter(None, [person.get("nombre"), person.get("apellido")])).strip(), "person_number": person.get("person_number"), "registration_status": registration.get("status") if registration else "walk_in", "already_checked_in_at": serialize(duplicate.get("checked_in_at")) if duplicate else None})
    for registration in registrations:
        duplicate = await db.operation_checkins.find_one({"occurrence_id": occurrence_id, "registration_id": registration["registration_id"], "status": "active"}, {"_id": 0, "checked_in_at": 1})
        items.append({"kind": "guest", "registration_id": registration["registration_id"], "name": registration.get("guest_name") or "Invitado", "registration_code": registration["registration_code"], "registration_status": registration["status"], "already_checked_in_at": serialize(duplicate.get("checked_in_at")) if duplicate else None})
    return {"items": items[:30]}


async def _resolve_checkin_reference(occurrence_id: str, payload: CheckInCreate) -> tuple[Optional[str], Optional[str], str]:
    person_id, registration_id, method = payload.person_id, payload.registration_id, "manual"
    if payload.code:
        raw = payload.code.strip(); token = raw.rstrip("/").split("/")[-1]
        membership_id = membership_id_from_token(token)
        if membership_id:
            membership = await db.person_memberships.find_one({"membership_id": membership_id, "status": "active"}, {"_id": 0, "person_id": 1})
            if membership: person_id, method = membership["person_id"], "qr"
        if not person_id:
            registry = await db.membership_number_registry.find_one({"member_number": raw.upper()}, {"_id": 0, "person_id": 1})
            if registry: person_id, method = registry["person_id"], "member_number"
        if not person_id:
            registration = await db.operation_registrations.find_one({"occurrence_id": occurrence_id, "registration_code": raw.upper(), "status": {"$ne": "cancelled"}}, {"_id": 0, "registration_id": 1, "person_id": 1})
            if registration: registration_id, person_id, method = registration["registration_id"], registration.get("person_id"), "registration_code"
    if registration_id:
        registration = await db.operation_registrations.find_one({"occurrence_id": occurrence_id, "registration_id": registration_id, "status": {"$ne": "cancelled"}}, {"_id": 0})
        if not registration: raise HTTPException(status_code=404, detail="Inscripción no encontrada")
        person_id = person_id or registration.get("person_id")
    if person_id: await canonical_person(person_id)
    if not person_id and not registration_id: raise HTTPException(status_code=404, detail="Código o Persona no encontrados")
    return person_id, registration_id, method


@router.post("/occurrences/{occurrence_id}/check-ins", response_model=dict)
async def create_checkin(occurrence_id: str, payload: CheckInCreate, current_user: dict = Depends(require_operations_checkin)):
    occurrence, event = await _occurrence_or_404(occurrence_id)
    if occurrence["status"] in {"closed", "cancelled"}: raise HTTPException(status_code=409, detail="La asistencia está cerrada")
    person_id, registration_id, method = await _resolve_checkin_reference(occurrence_id, payload)
    assignment = await db.operation_volunteer_assignments.find_one({"occurrence_id": occurrence_id, "person_id": person_id, "status": {"$in": ["invited", "confirmed"]}}, {"_id": 0}) if person_id else None
    kind = "volunteer" if payload.kind == "volunteer" or payload.kind == "auto" and assignment else "attendee"
    if person_id and not registration_id:
        registration = await db.operation_registrations.find_one({"occurrence_id": occurrence_id, "person_id": person_id, "status": {"$ne": "cancelled"}}, {"_id": 0})
        if registration: registration_id = registration["registration_id"]
        else:
            registration_id = str(uuid4()); now = now_utc()
            await db.operation_registrations.insert_one({"_id": registration_id, "registration_id": registration_id, "registration_code": f"OP-{secrets.token_hex(4).upper()}", "occurrence_id": occurrence_id, "event_id": event["event_id"], "person_id": person_id, "status": "registered", "party_size": 1, "source": "walk_in", "registered_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now})
    identity = person_id or registration_id; duplicate_key = f"{occurrence_id}:{identity}"; checkin_id = str(uuid4()); now = now_utc()
    doc = {"_id": checkin_id, "checkin_id": checkin_id, "occurrence_id": occurrence_id, "event_id": event["event_id"], "registration_id": registration_id, "kind": kind, "method": method, "duplicate_key": duplicate_key, "idempotency_key": payload.idempotency_key, "checked_in_by_user_id": current_user["user_id"], "checked_in_at": now, "status": "active"}
    if person_id: doc["person_id"] = person_id
    try: await db.operation_checkins.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.operation_checkins.find_one({"$or": [{"duplicate_key": duplicate_key}, {"idempotency_key": payload.idempotency_key}]}, {"_id": 0})
        return serialize({**existing, "duplicate": True})
    await db.operation_registrations.update_one({"registration_id": registration_id}, {"$set": {"status": "checked_in", "checked_in_at": now, "updated_at": now}})
    if assignment:
        await db.operation_volunteer_assignments.update_one({"assignment_id": assignment["assignment_id"]}, {"$set": {"status": "checked_in", "checked_in_at": now, "updated_at": now}})
    await db.operation_event_occurrences.update_one({"occurrence_id": occurrence_id, "status": "scheduled"}, {"$set": {"status": "checkin_open", "checkin_opened_at": now, "updated_at": now}})
    if person_id:
        await db.person_attendance.update_one({"_id": f"operation:{checkin_id}"}, {"$setOnInsert": {"_id": f"operation:{checkin_id}", "person_id": person_id, "fecha": now.isoformat(), "actividad": event["title"], "estado": "presente", "notas": f"Operaciones · {occurrence_id}", "created_by": current_user["user_id"], "created_at": now, "updated_at": now}}, upsert=True)
    await audit(current_user, "checkin_created", "occurrence", occurrence_id, {"checkin_id": checkin_id, "person_id": person_id, "registration_id": registration_id, "method": method})
    return serialize({**doc, "duplicate": False})


@router.post("/occurrences/{occurrence_id}/close", response_model=dict)
async def close_attendance(occurrence_id: str, payload: AttendanceClose, current_user: dict = Depends(require_operations_manage)):
    occurrence, _ = await _occurrence_or_404(occurrence_id)
    if occurrence["status"] == "cancelled": raise HTTPException(status_code=409, detail="Ocurrencia cancelada")
    if occurrence["status"] == "closed": return serialize({"occurrence": occurrence, "metrics": occurrence.get("closed_metrics") or await occurrence_metrics(occurrence_id), "already_closed": True})
    metrics = await occurrence_metrics(occurrence_id); now = now_utc()
    result = await db.operation_event_occurrences.find_one_and_update({"occurrence_id": occurrence_id, "status": {"$ne": "closed"}}, {"$set": {"status": "closed", "closed_at": now, "closed_by_user_id": current_user["user_id"], "closing_notes": payload.notes, "closed_metrics": metrics, "updated_at": now}}, return_document=ReturnDocument.AFTER, projection={"_id": 0})
    await db.operation_shifts.update_many({"occurrence_id": occurrence_id, "status": "open"}, {"$set": {"status": "completed", "updated_at": now}})
    await db.operation_volunteer_assignments.update_many({"occurrence_id": occurrence_id, "status": "confirmed"}, {"$set": {"status": "no_show", "updated_at": now}})
    await audit(current_user, "attendance_closed", "occurrence", occurrence_id, metrics)
    return serialize({"occurrence": result, "metrics": metrics, "already_closed": False})


@router.get("/occurrences/{occurrence_id}/metrics", response_model=dict)
async def get_occurrence_metrics(occurrence_id: str, current_user: dict = Depends(require_operations_view)):
    occurrence, _ = await _occurrence_or_404(occurrence_id)
    return serialize({"metrics": occurrence.get("closed_metrics") or await occurrence_metrics(occurrence_id), "closed": occurrence["status"] == "closed"})


@router.get("/notifications", response_model=dict)
async def list_notifications(current_user: dict = Depends(require_operations_view)):
    items = await db.operation_notifications.find({"recipient_user_id": current_user["user_id"]}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return serialize({"items": items})


@router.patch("/notifications/{notification_id}/read", response_model=dict)
async def mark_notification_read(notification_id: str, current_user: dict = Depends(require_operations_view)):
    item = await db.operation_notifications.find_one_and_update({"notification_id": notification_id, "recipient_user_id": current_user["user_id"]}, {"$set": {"read_at": now_utc()}}, return_document=ReturnDocument.AFTER, projection={"_id": 0})
    if not item: raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return serialize(item)