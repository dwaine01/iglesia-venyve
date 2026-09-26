"""Eventos de Bautismo + certificado oficial vinculados a la Persona 360 canónica."""
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

from access_control import BAPTISM_CERTIFICATES_ISSUE, BAPTISM_EVENTS_MANAGE, BAPTISM_READ, has_capability, is_general_coordinator, is_global_pastoral_authority
from membership_documents import canonical_person, full_name, settings_document
from server import db, get_current_user

router = APIRouter(tags=["baptism-documents"])
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
    return is_global_pastoral_authority(current_user) or is_general_coordinator(current_user) or has_capability(current_user, BAPTISM_EVENTS_MANAGE)


def require_events_manager(current_user: dict) -> None:
    if not is_events_manager(current_user):
        raise HTTPException(status_code=403, detail="Solo Pastor/Pastora o Coordinación General puede administrar eventos de bautismo")


def is_certificate_manager(current_user: dict) -> bool:
    return is_global_pastoral_authority(current_user) or is_general_coordinator(current_user) or has_capability(current_user, BAPTISM_CERTIFICATES_ISSUE)


def require_certificate_manager(current_user: dict) -> None:
    if not is_certificate_manager(current_user):
        raise HTTPException(status_code=403, detail="Solo Pastor/Pastora o Coordinación General puede emitir el certificado de bautismo")


def require_baptism_reader(current_user: dict) -> None:
    if not has_capability(current_user, BAPTISM_READ):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar Bautismo")


async def events_manager_user(current_user: dict = Depends(get_current_user)) -> dict:
    require_events_manager(current_user)
    return current_user


async def certificate_manager_user(current_user: dict = Depends(get_current_user)) -> dict:
    require_certificate_manager(current_user)
    return current_user


async def baptism_reader_user(current_user: dict = Depends(get_current_user)) -> dict:
    require_baptism_reader(current_user)
    return current_user


def valid_iso_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Fecha inválida") from exc
    return value


class BaptismEventInput(BaseModel):
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


class BaptismEventUpdate(BaseModel):
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


class CandidateInput(BaseModel):
    person_id: str


class CompleteCandidateInput(BaseModel):
    baptism_date: Optional[str] = None
    testimony: Optional[str] = Field(default=None, max_length=3000)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("baptism_date")
    @classmethod
    def check_baptism_date(cls, value: Optional[str]) -> Optional[str]:
        return valid_iso_date(value)


class IssueCertificateInput(BaseModel):
    issue_date: date = Field(default_factory=date.today)


def verification_token(baptism_id: str) -> str:
    payload = base64.urlsafe_b64encode(baptism_id.encode()).decode().rstrip("=")
    signature = hmac.new(TOKEN_SECRET.encode(), baptism_id.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def baptism_id_from_token(token: str) -> Optional[str]:
    try:
        payload, signature = token.split(".", 1)
        baptism_id = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        expected = hmac.new(TOKEN_SECRET.encode(), baptism_id.encode(), hashlib.sha256).hexdigest()
        return baptism_id if hmac.compare_digest(signature, expected) else None
    except (ValueError, UnicodeDecodeError):
        return None


async def event_or_404(event_id: str) -> dict:
    event = await db.baptism_events.find_one({"event_id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Evento de bautismo no encontrado")
    return event


async def event_roster(event_id: str) -> list:
    records = await db.person_baptisms.find({"event_id": event_id}, {"_id": 0}).to_list(1000)
    person_ids = [ObjectId(record["person_id"]) for record in records if ObjectId.is_valid(record["person_id"])]
    people = await db.persons.find({"_id": {"$in": person_ids}}, {"nombre": 1, "apellido": 1, "person_number": 1}).to_list(1000)
    people_by_id = {str(person["_id"]): person for person in people}
    roster = []
    for record in records:
        person = people_by_id.get(record["person_id"], {})
        roster.append({
            **serialize(record),
            "person_name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip() or "Persona",
            "person_number": person.get("person_number"),
        })
    return roster


async def render_baptism_data(person: dict, record: dict) -> dict:
    settings = await settings_document()
    token = verification_token(record["baptism_id"])
    return {
        "person": {"person_id": person["person_id"], "full_name": full_name(person)},
        "baptism": serialize(record),
        "certificate": {
            "officiant_name": record.get("officiant_name") or "",
            "has_signature": bool(settings.get("signature_file_id")),
            "signature_path": "/api/membership/settings/signature" if settings.get("signature_file_id") else None,
        },
        "organization_name": settings.get("organization_name") or "Casa de Oración Ven y Ve",
        "verification_path": f"/verificar/bautismo/{token}",
        "template_version": 1,
    }


async def record_issuance(actor_id: str, record: dict, person: dict, action: str) -> None:
    issuance_id = str(uuid4())
    await db.baptism_document_issuances.insert_one({
        "_id": issuance_id,
        "issuance_id": issuance_id,
        "baptism_id": record["baptism_id"],
        "person_id": record["person_id"],
        "action": action,
        "person_name_snapshot": full_name(person),
        "baptism_date_snapshot": record.get("baptism_date"),
        "location_snapshot": record.get("location"),
        "officiant_snapshot": record.get("officiant_name"),
        "certificate_issue_date": record.get("certificate_issue_date"),
        "created_by_user_id": actor_id,
        "created_at": now_utc(),
    })


@router.get("/api/baptism/events", response_model=dict)
async def list_baptism_events(current_user: dict = Depends(baptism_reader_user)):
    events = await db.baptism_events.find({}, {"_id": 0}).sort("event_date", -1).to_list(500)
    counts = await db.person_baptisms.aggregate([
        {"$match": {"event_id": {"$in": [event["event_id"] for event in events]}}},
        {"$group": {"_id": "$event_id", "total": {"$sum": 1}, "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}}}},
    ]).to_list(500)
    counts_by_event = {item["_id"]: item for item in counts}
    items = [{**serialize(event), "candidate_count": counts_by_event.get(event["event_id"], {}).get("total", 0), "completed_count": counts_by_event.get(event["event_id"], {}).get("completed", 0)} for event in events]
    return {"items": items, "total": len(items)}


@router.post("/api/baptism/events", response_model=dict, status_code=201)
async def create_baptism_event(payload: BaptismEventInput, current_user: dict = Depends(events_manager_user)):
    event_id = str(uuid4())
    now = now_utc()
    document = {
        "_id": event_id, "event_id": event_id, **payload.model_dump(),
        "status": "scheduled", "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.baptism_events.insert_one(document)
    return serialize(document)


@router.get("/api/baptism/events/{event_id}", response_model=dict)
async def get_baptism_event(event_id: str, current_user: dict = Depends(baptism_reader_user)):
    event = await event_or_404(event_id)
    return {"event": serialize(event), "roster": await event_roster(event_id)}


@router.put("/api/baptism/events/{event_id}", response_model=dict)
async def update_baptism_event(event_id: str, payload: BaptismEventUpdate, current_user: dict = Depends(events_manager_user)):
    await event_or_404(event_id)
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=422, detail="Sin cambios para actualizar")
    updates["updated_at"] = now_utc()
    await db.baptism_events.update_one({"event_id": event_id}, {"$set": updates})
    return serialize(await event_or_404(event_id))


@router.post("/api/baptism/events/{event_id}/candidates", response_model=dict, status_code=201)
async def add_baptism_candidate(event_id: str, payload: CandidateInput, current_user: dict = Depends(events_manager_user)):
    event = await event_or_404(event_id)
    if event.get("status") != "scheduled":
        raise HTTPException(status_code=409, detail="Solo se pueden agregar candidatos a un evento programado")
    person = await canonical_person(payload.person_id)
    person_id = person["person_id"]
    existing = await db.person_baptisms.find_one({"person_id": person_id}, {"_id": 0})
    if existing and existing.get("status") == "completed":
        raise HTTPException(status_code=409, detail="Esta Persona ya tiene un bautismo completado registrado")
    if event.get("capacity"):
        current_total = await db.person_baptisms.count_documents({"event_id": event_id})
        if current_total >= event["capacity"]:
            raise HTTPException(status_code=409, detail="El evento alcanzó su cupo máximo")
    now = now_utc()
    baptism_id = (existing or {}).get("baptism_id") or str(uuid4())
    values = {
        "baptism_id": baptism_id, "person_id": person_id, "event_id": event_id,
        "status": "scheduled", "baptized": False,
        "baptism_date": event["event_date"], "location": event.get("location"),
        "officiant_name": event.get("officiant_name"),
        "updated_by_user_id": current_user["user_id"], "updated_at": now,
    }
    await db.person_baptisms.update_one(
        {"person_id": person_id},
        {"$set": values, "$setOnInsert": {"created_at": now, "created_by_user_id": current_user["user_id"]}},
        upsert=True,
    )
    return {"event": serialize(event), "roster": await event_roster(event_id)}


@router.delete("/api/baptism/events/{event_id}/candidates/{person_id}", response_model=dict)
async def remove_baptism_candidate(event_id: str, person_id: str, current_user: dict = Depends(events_manager_user)):
    await event_or_404(event_id)
    record = await db.person_baptisms.find_one({"person_id": person_id, "event_id": event_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="La Persona no está en el listado de este evento")
    if record.get("status") == "completed":
        raise HTTPException(status_code=409, detail="No se puede quitar un bautismo ya completado")
    await db.person_baptisms.update_one({"person_id": person_id}, {"$set": {"event_id": None, "status": "pending", "updated_at": now_utc(), "updated_by_user_id": current_user["user_id"]}})
    return {"roster": await event_roster(event_id)}


@router.post("/api/baptism/events/{event_id}/candidates/{person_id}/complete", response_model=dict)
async def complete_baptism_candidate(event_id: str, person_id: str, payload: CompleteCandidateInput, current_user: dict = Depends(events_manager_user)):
    await event_or_404(event_id)
    record = await db.person_baptisms.find_one({"person_id": person_id, "event_id": event_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="La Persona no está en el listado de este evento")
    updates = {"status": "completed", "baptized": True, "updated_at": now_utc(), "updated_by_user_id": current_user["user_id"]}
    if payload.baptism_date:
        updates["baptism_date"] = payload.baptism_date
    if payload.testimony is not None:
        updates["testimony"] = payload.testimony
    if payload.notes is not None:
        updates["notes"] = payload.notes
    await db.person_baptisms.update_one({"person_id": person_id}, {"$set": updates})
    return {"roster": await event_roster(event_id)}


@router.get("/api/baptism/persons/{person_id}", response_model=dict)
async def person_baptism_document(person_id: str, current_user: dict = Depends(baptism_reader_user)):
    person = await canonical_person(person_id)
    record = await db.person_baptisms.find_one({"person_id": person["person_id"]}, {"_id": 0})
    return {"exists": bool(record), "data": await render_baptism_data(person, record) if record else {"person": {"person_id": person["person_id"], "full_name": full_name(person)}}}


@router.post("/api/baptism/persons/{person_id}/certificate/issue", response_model=dict, status_code=201)
async def issue_baptism_certificate(person_id: str, payload: IssueCertificateInput, current_user: dict = Depends(certificate_manager_user)):
    person = await canonical_person(person_id)
    record = await db.person_baptisms.find_one({"person_id": person["person_id"]}, {"_id": 0})
    if not record or record.get("status") != "completed":
        raise HTTPException(status_code=409, detail="El bautismo debe estar completado para emitir el certificado")
    settings = await settings_document()
    if not settings.get("signature_file_id"):
        raise HTTPException(status_code=409, detail="Configure la firma autorizada en Membresía antes de emitir el certificado")
    action = "reprinted" if record.get("certificate_issue_date") else "issued"
    updates = {"updated_by_user_id": current_user["user_id"], "updated_at": now_utc()}
    if not record.get("certificate_issue_date"):
        updates["certificate_issue_date"] = payload.issue_date.isoformat()
        updates["certificate_issued_by_user_id"] = current_user["user_id"]
    await db.person_baptisms.update_one({"baptism_id": record["baptism_id"]}, {"$set": updates})
    record = await db.person_baptisms.find_one({"baptism_id": record["baptism_id"]}, {"_id": 0})
    await record_issuance(current_user["user_id"], record, person, action)
    return {"action": action, "data": await render_baptism_data(person, record)}


@router.get("/api/baptism/persons/{person_id}/issuances", response_model=dict)
async def baptism_issuances(person_id: str, current_user: dict = Depends(baptism_reader_user)):
    person = await canonical_person(person_id)
    items = await db.baptism_document_issuances.find({"person_id": person["person_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"items": serialize(items)}


@router.get("/api/public/baptism/verify/{token}", response_model=dict)
async def public_baptism_verification(token: str):
    baptism_id = baptism_id_from_token(token)
    if not baptism_id:
        return {"valid": False, "status": "invalid"}
    record = await db.person_baptisms.find_one({"baptism_id": baptism_id}, {"_id": 0})
    if not record or not record.get("certificate_issue_date"):
        return {"valid": False, "status": "invalid"}
    person = await canonical_person(record["person_id"])
    settings = await settings_document()
    return {
        "valid": True, "status": "active",
        "organization_name": settings.get("organization_name"),
        "member_name": full_name(person),
        "baptism_date": record.get("baptism_date"),
        "location": record.get("location"),
        "officiant_name": record.get("officiant_name"),
        "issued": record.get("certificate_issue_date"),
    }


async def ensure_baptism_documents() -> None:
    await db.baptism_events.create_index("event_id", unique=True)
    await db.baptism_events.create_index([("event_date", -1)])
    await db.person_baptisms.create_index("event_id")
    await db.baptism_document_issuances.create_index("issuance_id", unique=True)
    await db.baptism_document_issuances.create_index([("person_id", 1), ("created_at", -1)])
