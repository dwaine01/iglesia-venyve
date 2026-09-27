"""Eventos de Presentación de Niños + certificado oficial de dedicación."""
import base64
import hashlib
import hmac
import os
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from access_control import DEDICATION_CERTIFICATES_ISSUE, DEDICATION_EVENTS_MANAGE, DEDICATION_READ, has_capability, is_general_coordinator, is_global_pastoral_authority
from membership_documents import canonical_person, full_name, settings_document
from person_core_expansion import create_relationship
from server import db, get_current_user

router = APIRouter(tags=["dedication-documents"])
TOKEN_SECRET = os.environ.get("JWT_SECRET")
if not TOKEN_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items() if key != "_id"}
    return value


def is_events_manager(current_user: dict) -> bool:
    return is_global_pastoral_authority(current_user) or is_general_coordinator(current_user) or has_capability(current_user, DEDICATION_EVENTS_MANAGE)


def require_events_manager(current_user: dict) -> None:
    if not is_events_manager(current_user):
        raise HTTPException(status_code=403, detail="Solo Pastor/Pastora o Coordinación General puede administrar presentaciones de niños")


def is_certificate_manager(current_user: dict) -> bool:
    return is_global_pastoral_authority(current_user) or is_general_coordinator(current_user) or has_capability(current_user, DEDICATION_CERTIFICATES_ISSUE)


def require_certificate_manager(current_user: dict) -> None:
    if not is_certificate_manager(current_user):
        raise HTTPException(status_code=403, detail="Solo Pastor/Pastora o Coordinación General puede emitir el certificado de presentación")


def require_dedication_reader(current_user: dict) -> None:
    if not has_capability(current_user, DEDICATION_READ):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar Presentación de Niños")


async def events_manager_user(current_user: dict = Depends(get_current_user)) -> dict:
    require_events_manager(current_user)
    return current_user


async def certificate_manager_user(current_user: dict = Depends(get_current_user)) -> dict:
    require_certificate_manager(current_user)
    return current_user


async def dedication_reader_user(current_user: dict = Depends(get_current_user)) -> dict:
    require_dedication_reader(current_user)
    return current_user


def valid_iso_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Fecha inválida") from exc
    return value


class DedicationEventInput(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    event_date: str
    location: Optional[str] = Field(default=None, max_length=180)
    officiant_name: Optional[str] = Field(default=None, max_length=140)
    capacity: Optional[int] = Field(default=None, ge=1, le=500)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("event_date")
    @classmethod
    def check_event_date(cls, value: str) -> str:
        valid_iso_date(value)
        return value


class DedicationEventUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=160)
    event_date: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=180)
    officiant_name: Optional[str] = Field(default=None, max_length=140)
    capacity: Optional[int] = Field(default=None, ge=1, le=500)
    notes: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[Literal["scheduled", "completed", "cancelled"]] = None

    @field_validator("event_date")
    @classmethod
    def check_event_date(cls, value: Optional[str]) -> Optional[str]:
        return valid_iso_date(value)


class DedicationCandidateInput(BaseModel):
    child_person_id: str
    mother_person_id: Optional[str] = None
    father_person_id: Optional[str] = None
    presented_by: Optional[str] = Field(default=None, max_length=200)
    witnesses: list[str] = Field(default_factory=list)
    dedication_verse: Optional[str] = Field(default=None, max_length=500)


class DedicationStandaloneInput(DedicationCandidateInput):
    dedication_date: str
    location: Optional[str] = Field(default=None, max_length=180)
    officiant_name: Optional[str] = Field(default=None, max_length=140)
    status: Literal["scheduled", "completed"] = "completed"

    @field_validator("dedication_date")
    @classmethod
    def check_dedication_date(cls, value: str) -> str:
        valid_iso_date(value)
        return value


class CompleteCandidateInput(BaseModel):
    dedication_date: Optional[str] = None
    presented_by: Optional[str] = Field(default=None, max_length=200)
    witnesses: Optional[list[str]] = None
    dedication_verse: Optional[str] = Field(default=None, max_length=500)

    @field_validator("dedication_date")
    @classmethod
    def check_dedication_date(cls, value: Optional[str]) -> Optional[str]:
        return valid_iso_date(value)


class IssueCertificateInput(BaseModel):
    issue_date: date = Field(default_factory=date.today)


def verification_token(dedication_id: str) -> str:
    payload = base64.urlsafe_b64encode(dedication_id.encode()).decode().rstrip("=")
    signature = hmac.new(TOKEN_SECRET.encode(), dedication_id.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def dedication_id_from_token(token: str) -> Optional[str]:
    try:
        payload, signature = token.split(".", 1)
        dedication_id = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        expected = hmac.new(TOKEN_SECRET.encode(), dedication_id.encode(), hashlib.sha256).hexdigest()
        return dedication_id if hmac.compare_digest(signature, expected) else None
    except (ValueError, UnicodeDecodeError):
        return None


async def link_parents(child_person_id: str, mother_person_id: Optional[str], father_person_id: Optional[str], user: dict) -> None:
    for parent_id in (mother_person_id, father_person_id):
        if not parent_id:
            continue
        try:
            await create_relationship(parent_id, child_person_id, "parent_of", user)
        except HTTPException as exc:
            if exc.status_code != 409:
                raise


async def parent_names(record: dict) -> dict:
    names = {"mother_name": None, "father_name": None}
    if record.get("mother_person_id"):
        try:
            names["mother_name"] = full_name(await canonical_person(record["mother_person_id"]))
        except HTTPException:
            names["mother_name"] = None
    if record.get("father_person_id"):
        try:
            names["father_name"] = full_name(await canonical_person(record["father_person_id"]))
        except HTTPException:
            names["father_name"] = None
    return names


async def event_or_404(event_id: str) -> dict:
    event = await db.dedication_events.find_one({"event_id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Evento de presentación no encontrado")
    return event


async def event_roster(event_id: str) -> list:
    records = await db.person_dedications.find({"event_id": event_id}, {"_id": 0}).to_list(1000)
    person_ids = [ObjectId(record["child_person_id"]) for record in records if ObjectId.is_valid(record["child_person_id"])]
    people = await db.persons.find({"_id": {"$in": person_ids}}, {"nombre": 1, "apellido": 1, "person_number": 1}).to_list(1000)
    people_by_id = {str(person["_id"]): person for person in people}
    roster = []
    for record in records:
        person = people_by_id.get(record["child_person_id"], {})
        roster.append({
            **serialize(record),
            "child_name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip() or "Niño/a",
            "person_number": person.get("person_number"),
        })
    return roster


async def render_dedication_data(child: dict, record: dict) -> dict:
    settings = await settings_document()
    token = verification_token(record["dedication_id"])
    names = await parent_names(record)
    return {
        "child": {"person_id": child["person_id"], "full_name": full_name(child), "fecha_nacimiento": child.get("fecha_nacimiento")},
        "dedication": {**serialize(record), **names},
        "certificate": {
            "officiant_name": record.get("officiant_name") or "",
            "has_signature": bool(settings.get("signature_file_id")),
            "signature_path": "/api/membership/settings/signature" if settings.get("signature_file_id") else None,
        },
        "organization_name": settings.get("organization_name") or "Casa de Oración Ven y Ve",
        "verification_path": f"/verificar/presentacion/{token}",
        "template_version": 1,
    }


async def record_issuance(actor_id: str, record: dict, child: dict, action: str) -> None:
    issuance_id = str(uuid4())
    await db.dedication_document_issuances.insert_one({
        "_id": issuance_id,
        "issuance_id": issuance_id,
        "dedication_id": record["dedication_id"],
        "child_person_id": record["child_person_id"],
        "action": action,
        "child_name_snapshot": full_name(child),
        "dedication_date_snapshot": record.get("dedication_date"),
        "location_snapshot": record.get("location"),
        "officiant_snapshot": record.get("officiant_name"),
        "certificate_issue_date": record.get("certificate_issue_date"),
        "created_by_user_id": actor_id,
        "created_at": now_utc(),
    })


@router.get("/api/dedications/events", response_model=dict)
async def list_dedication_events(current_user: dict = Depends(dedication_reader_user)):
    events = await db.dedication_events.find({}, {"_id": 0}).sort("event_date", -1).to_list(500)
    counts = await db.person_dedications.aggregate([
        {"$match": {"event_id": {"$in": [event["event_id"] for event in events]}}},
        {"$group": {"_id": "$event_id", "total": {"$sum": 1}, "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}}}},
    ]).to_list(500)
    counts_by_event = {item["_id"]: item for item in counts}
    items = [{**serialize(event), "candidate_count": counts_by_event.get(event["event_id"], {}).get("total", 0), "completed_count": counts_by_event.get(event["event_id"], {}).get("completed", 0)} for event in events]
    return {"items": items, "total": len(items)}


@router.post("/api/dedications/events", response_model=dict, status_code=201)
async def create_dedication_event(payload: DedicationEventInput, current_user: dict = Depends(events_manager_user)):
    event_id = str(uuid4())
    now = now_utc()
    document = {
        "_id": event_id, "event_id": event_id, **payload.model_dump(),
        "status": "scheduled", "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.dedication_events.insert_one(document)
    return serialize(document)


@router.get("/api/dedications/events/{event_id}", response_model=dict)
async def get_dedication_event(event_id: str, current_user: dict = Depends(dedication_reader_user)):
    event = await event_or_404(event_id)
    return {"event": serialize(event), "roster": await event_roster(event_id)}


@router.put("/api/dedications/events/{event_id}", response_model=dict)
async def update_dedication_event(event_id: str, payload: DedicationEventUpdate, current_user: dict = Depends(events_manager_user)):
    await event_or_404(event_id)
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="Sin cambios para actualizar")
    updates["updated_at"] = now_utc()
    await db.dedication_events.update_one({"event_id": event_id}, {"$set": updates})
    return serialize(await event_or_404(event_id))


async def upsert_child_record(child_person_id: str, values: dict, actor_id: str) -> dict:
    existing = await db.person_dedications.find_one({"child_person_id": child_person_id}, {"_id": 0})
    if existing and existing.get("status") == "completed":
        raise HTTPException(status_code=409, detail="Este niño/a ya tiene una presentación completada registrada")
    now = now_utc()
    dedication_id = (existing or {}).get("dedication_id") or str(uuid4())
    values = {**values, "dedication_id": dedication_id, "child_person_id": child_person_id, "updated_by_user_id": actor_id, "updated_at": now}
    await db.person_dedications.update_one(
        {"child_person_id": child_person_id},
        {"$set": values, "$setOnInsert": {"created_at": now, "created_by_user_id": actor_id}},
        upsert=True,
    )
    return await db.person_dedications.find_one({"child_person_id": child_person_id}, {"_id": 0})


@router.post("/api/dedications/events/{event_id}/candidates", response_model=dict, status_code=201)
async def add_dedication_candidate(event_id: str, payload: DedicationCandidateInput, current_user: dict = Depends(events_manager_user)):
    event = await event_or_404(event_id)
    if event.get("status") != "scheduled":
        raise HTTPException(status_code=409, detail="Solo se pueden agregar niños a un evento programado")
    child = await canonical_person(payload.child_person_id)
    if event.get("capacity"):
        current_total = await db.person_dedications.count_documents({"event_id": event_id})
        if current_total >= event["capacity"]:
            raise HTTPException(status_code=409, detail="El evento alcanzó su cupo máximo")
    await link_parents(child["person_id"], payload.mother_person_id, payload.father_person_id, current_user)
    await upsert_child_record(child["person_id"], {
        "event_id": event_id, "status": "scheduled",
        "dedication_date": event["event_date"], "location": event.get("location"), "officiant_name": event.get("officiant_name"),
        "mother_person_id": payload.mother_person_id, "father_person_id": payload.father_person_id,
        "presented_by": payload.presented_by, "witnesses": payload.witnesses, "dedication_verse": payload.dedication_verse,
    }, current_user["user_id"])
    return {"event": serialize(event), "roster": await event_roster(event_id)}


@router.post("/api/dedications/children", response_model=dict, status_code=201)
async def register_standalone_dedication(payload: DedicationStandaloneInput, current_user: dict = Depends(events_manager_user)):
    child = await canonical_person(payload.child_person_id)
    await link_parents(child["person_id"], payload.mother_person_id, payload.father_person_id, current_user)
    record = await upsert_child_record(child["person_id"], {
        "event_id": None, "status": payload.status,
        "dedication_date": payload.dedication_date, "location": payload.location, "officiant_name": payload.officiant_name,
        "mother_person_id": payload.mother_person_id, "father_person_id": payload.father_person_id,
        "presented_by": payload.presented_by, "witnesses": payload.witnesses, "dedication_verse": payload.dedication_verse,
    }, current_user["user_id"])
    return {"data": await render_dedication_data(child, record)}


@router.delete("/api/dedications/events/{event_id}/candidates/{child_person_id}", response_model=dict)
async def remove_dedication_candidate(event_id: str, child_person_id: str, current_user: dict = Depends(events_manager_user)):
    await event_or_404(event_id)
    record = await db.person_dedications.find_one({"child_person_id": child_person_id, "event_id": event_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="El niño/a no está en el listado de este evento")
    if record.get("status") == "completed":
        raise HTTPException(status_code=409, detail="No se puede quitar una presentación ya completada")
    await db.person_dedications.update_one({"child_person_id": child_person_id}, {"$set": {"event_id": None, "status": "pending", "updated_at": now_utc(), "updated_by_user_id": current_user["user_id"]}})
    return {"roster": await event_roster(event_id)}


@router.post("/api/dedications/events/{event_id}/candidates/{child_person_id}/complete", response_model=dict)
async def complete_dedication_candidate(event_id: str, child_person_id: str, payload: CompleteCandidateInput, current_user: dict = Depends(events_manager_user)):
    await event_or_404(event_id)
    record = await db.person_dedications.find_one({"child_person_id": child_person_id, "event_id": event_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="El niño/a no está en el listado de este evento")
    updates = {"status": "completed", "updated_at": now_utc(), "updated_by_user_id": current_user["user_id"]}
    for field in ("dedication_date", "presented_by", "dedication_verse"):
        value = getattr(payload, field)
        if value is not None:
            updates[field] = value
    if payload.witnesses is not None:
        updates["witnesses"] = payload.witnesses
    await db.person_dedications.update_one({"child_person_id": child_person_id}, {"$set": updates})
    return {"roster": await event_roster(event_id)}


@router.get("/api/dedications/children/{child_person_id}", response_model=dict)
async def child_dedication_document(child_person_id: str, current_user: dict = Depends(dedication_reader_user)):
    child = await canonical_person(child_person_id)
    record = await db.person_dedications.find_one({"child_person_id": child["person_id"]}, {"_id": 0})
    return {"exists": bool(record), "data": await render_dedication_data(child, record) if record else {"child": {"person_id": child["person_id"], "full_name": full_name(child)}}}


@router.post("/api/dedications/children/{child_person_id}/certificate/issue", response_model=dict, status_code=201)
async def issue_dedication_certificate(child_person_id: str, payload: IssueCertificateInput, current_user: dict = Depends(certificate_manager_user)):
    child = await canonical_person(child_person_id)
    record = await db.person_dedications.find_one({"child_person_id": child["person_id"]}, {"_id": 0})
    if not record or record.get("status") != "completed":
        raise HTTPException(status_code=409, detail="La presentación debe estar completada para emitir el certificado")
    settings = await settings_document()
    if not settings.get("signature_file_id"):
        raise HTTPException(status_code=409, detail="Configure la firma autorizada en Membresía antes de emitir el certificado")
    action = "reprinted" if record.get("certificate_issue_date") else "issued"
    updates = {"updated_by_user_id": current_user["user_id"], "updated_at": now_utc()}
    if not record.get("certificate_issue_date"):
        updates["certificate_issue_date"] = payload.issue_date.isoformat()
        updates["certificate_issued_by_user_id"] = current_user["user_id"]
    await db.person_dedications.update_one({"dedication_id": record["dedication_id"]}, {"$set": updates})
    record = await db.person_dedications.find_one({"dedication_id": record["dedication_id"]}, {"_id": 0})
    await record_issuance(current_user["user_id"], record, child, action)
    return {"action": action, "data": await render_dedication_data(child, record)}


@router.get("/api/dedications/children/{child_person_id}/issuances", response_model=dict)
async def dedication_issuances(child_person_id: str, current_user: dict = Depends(dedication_reader_user)):
    child = await canonical_person(child_person_id)
    items = await db.dedication_document_issuances.find({"child_person_id": child["person_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"items": serialize(items)}


@router.get("/api/public/dedications/verify/{token}", response_model=dict)
async def public_dedication_verification(token: str):
    dedication_id = dedication_id_from_token(token)
    if not dedication_id:
        return {"valid": False, "status": "invalid"}
    record = await db.person_dedications.find_one({"dedication_id": dedication_id}, {"_id": 0})
    if not record or not record.get("certificate_issue_date"):
        return {"valid": False, "status": "invalid"}
    child = await canonical_person(record["child_person_id"])
    settings = await settings_document()
    names = await parent_names(record)
    return {
        "valid": True, "status": "active",
        "organization_name": settings.get("organization_name"),
        "child_name": full_name(child),
        "dedication_date": record.get("dedication_date"),
        "location": record.get("location"),
        "officiant_name": record.get("officiant_name"),
        "mother_name": names.get("mother_name"),
        "father_name": names.get("father_name"),
        "issued": record.get("certificate_issue_date"),
    }


async def ensure_dedication_documents() -> None:
    await db.dedication_events.create_index("event_id", unique=True)
    await db.dedication_events.create_index([("event_date", -1)])
    await db.person_dedications.create_index("child_person_id", unique=True)
    await db.person_dedications.create_index("event_id")
    await db.dedication_document_issuances.create_index("issuance_id", unique=True)
    await db.dedication_document_issuances.create_index([("child_person_id", 1), ("created_at", -1)])
