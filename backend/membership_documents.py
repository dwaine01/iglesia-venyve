"""Carnet y certificado oficial vinculados a la Persona 360 canónica."""
import base64
import hashlib
import hmac
import io
import os
import re
from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from PIL import Image
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from access_control import MEMBERSHIP_DOCUMENTS_MANAGE, has_capability
from door_board_engine import active_board_membership
from person_profile_domains import assignment_items
from server import db, get_current_user


router = APIRouter(tags=["membership-documents"])
SIGNATURE_MAX_BYTES = 500 * 1024
SIGNATURE_BUCKET = "membership_signatures"
TOKEN_SECRET = os.environ.get("JWT_SECRET")
if not TOKEN_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")


class MembershipSettingsInput(BaseModel):
    expiration_months: int = Field(ge=1, le=120)
    authorized_signer_name: str = Field(default="", max_length=160)
    authorized_signer_title: str = Field(default="", max_length=160)
    organization_name: str = Field(default="Casa de Oración Ven y Ve", min_length=2, max_length=200)


class IssueDocumentInput(BaseModel):
    issue_date: date = Field(default_factory=date.today)
    existing_member_number: Optional[str] = Field(default=None, pattern=r"^\d{1,10}$")


class RenewCardInput(BaseModel):
    issue_date: date = Field(default_factory=date.today)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def signature_bucket():
    return AsyncIOMotorGridFSBucket(db, bucket_name=SIGNATURE_BUCKET)


def require_document_manager(current_user: dict) -> None:
    if current_user.get("rol") != "pastor" and not has_capability(current_user, MEMBERSHIP_DOCUMENTS_MANAGE):
        raise HTTPException(status_code=403, detail="No tiene permiso para emitir documentos oficiales de membresía")


def require_pastor(current_user: dict) -> None:
    if current_user.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo Pastor/Pastora puede configurar documentos oficiales")


async def managed_user(current_user: dict = Depends(get_current_user)) -> dict:
    require_document_manager(current_user)
    return current_user


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


async def canonical_person(person_id: str) -> dict:
    queries = [{"person_id": person_id}, {"_id": person_id}]
    if ObjectId.is_valid(person_id):
        queries.append({"_id": ObjectId(person_id)})
    person = await db.persons.find_one({"$or": queries})
    if not person:
        raise HTTPException(status_code=404, detail="Persona 360 no encontrada")
    person["person_id"] = person.get("person_id") or str(person["_id"])
    return person


def full_name(person: dict) -> str:
    for key in ["display_name", "full_name", "nombre_completo"]:
        if person.get(key):
            return str(person[key]).strip()
    first = person.get("first_name") or person.get("nombre") or ""
    last = person.get("last_name") or person.get("apellido") or ""
    return " ".join(part for part in [first, last] if part).strip() or "Miembro"


async def position_from_profile(person_id: str) -> str:
    board_match = await active_board_membership(db, person_id)
    if board_match:
        position = await db.board_position_catalog.find_one({"position_key": board_match.get("position_key")}, {"_id": 0, "name": 1})
        return str((position or {}).get("name") or board_match.get("position_key") or "Junta Directiva").upper()
    assignments = await assignment_items(person_id)
    active_assignment = next((item for item in assignments if item.get("activo") is True), None)
    if active_assignment:
        role = active_assignment.get("role_name") or active_assignment.get("role")
        ministry = active_assignment.get("ministry_name")
        if role and ministry and str(role).lower() not in str(ministry).lower():
            return f"{role} · {ministry}".upper()
        return str(role or ministry or "Miembro").upper()
    cell = await db.cell_role_assignments.find_one({"person_id": person_id, "active": True}, {"_id": 0, "role": 1})
    if cell and cell.get("role"):
        return str(cell["role"]).replace("_", " ").upper()
    user = await db.users.find_one({"person_id": person_id}, {"_id": 0, "access_title": 1})
    return str((user or {}).get("access_title") or "Miembro").upper()


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def verification_token(membership_id: str) -> str:
    payload = base64.urlsafe_b64encode(membership_id.encode()).decode().rstrip("=")
    signature = hmac.new(TOKEN_SECRET.encode(), membership_id.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def membership_id_from_token(token: str) -> Optional[str]:
    try:
        payload, signature = token.split(".", 1)
        membership_id = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        expected = hmac.new(TOKEN_SECRET.encode(), membership_id.encode(), hashlib.sha256).hexdigest()
        return membership_id if hmac.compare_digest(signature, expected) else None
    except (ValueError, UnicodeDecodeError):
        return None


async def settings_document() -> dict:
    settings = await db.membership_document_settings.find_one({"settings_id": "primary"}, {"_id": 0})
    if not settings:
        await ensure_membership_documents()
        settings = await db.membership_document_settings.find_one({"settings_id": "primary"}, {"_id": 0})
    return settings


async def allocate_member_number(person: dict, requested: Optional[str] = None) -> str:
    if requested:
        candidate = requested.zfill(5)
        if await db.person_memberships.find_one({"member_number": candidate}, {"_id": 1}):
            raise HTTPException(status_code=409, detail="El número de miembro ya está asignado")
        return candidate
    vv_digits = "".join(re.findall(r"\d", str(person.get("vv_number") or "")))
    if vv_digits:
        candidate = vv_digits[-5:].zfill(5)
        if not await db.person_memberships.find_one({"member_number": candidate}, {"_id": 1}):
            return candidate
    while True:
        counter = await db.membership_counters.find_one_and_update(
            {"counter_id": "member_number"},
            {"$inc": {"sequence": 1}, "$set": {"updated_at": now_utc()}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        candidate = str(counter["sequence"]).zfill(5)
        if not await db.person_memberships.find_one({"member_number": candidate}, {"_id": 1}):
            return candidate


async def get_or_create_membership(person: dict, actor_id: str, requested_number: Optional[str] = None) -> dict:
    person_id = person["person_id"]
    existing = await db.person_memberships.find_one({"person_id": person_id}, {"_id": 0})
    if existing:
        return existing
    membership_id = str(uuid4())
    member_number = await allocate_member_number(person, requested_number)
    now = now_utc()
    document = {
        "_id": membership_id,
        "membership_id": membership_id,
        "person_id": person_id,
        "member_number": member_number,
        "status": "active",
        "certificate_issue_date": None,
        "card_issue_date": None,
        "card_expiration_date": None,
        "card_position_snapshot": None,
        "created_by_user_id": actor_id,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db.person_memberships.insert_one(document)
    except DuplicateKeyError:
        return await db.person_memberships.find_one({"person_id": person_id}, {"_id": 0})
    return serialize(document)


async def render_data(person: dict, membership: dict) -> dict:
    settings = await settings_document()
    position = await position_from_profile(person["person_id"])
    token = verification_token(membership["membership_id"])
    return {
        "person": {
            "person_id": person["person_id"],
            "full_name": full_name(person),
            "position": position,
            "has_profile_photo": await db.person_photos.count_documents({"person_id": person["person_id"], "is_current": True}) > 0,
            "photo_path": f"/api/core/persons/{person['person_id']}/photo",
        },
        "membership": serialize(membership),
        "certificate": {
            "authorized_signer_name": settings.get("authorized_signer_name") or "",
            "authorized_signer_title": settings.get("authorized_signer_title") or "",
            "has_signature": bool(settings.get("signature_file_id")),
            "signature_path": "/api/membership/settings/signature" if settings.get("signature_file_id") else None,
        },
        "organization_name": settings.get("organization_name") or "Casa de Oración Ven y Ve",
        "expiration_months": settings.get("expiration_months", 12),
        "verification_path": f"/verificar/carnet/{token}",
        "template_version": 1,
    }


async def record_event(actor_id: str, membership: dict, person: dict, document_type: str, action: str, snapshot: dict) -> None:
    event_id = str(uuid4())
    await db.membership_document_issuances.insert_one({
        "_id": event_id,
        "issuance_id": event_id,
        "membership_id": membership["membership_id"],
        "person_id": membership["person_id"],
        "member_number": membership["member_number"],
        "document_type": document_type,
        "action": action,
        "person_name_snapshot": full_name(person),
        "position_snapshot": snapshot.get("person", {}).get("position"),
        "card_issue_date": membership.get("card_issue_date"),
        "card_expiration_date": membership.get("card_expiration_date"),
        "certificate_issue_date": membership.get("certificate_issue_date"),
        "created_by_user_id": actor_id,
        "created_at": now_utc(),
    })


@router.get("/api/membership/settings", response_model=dict)
async def membership_settings(current_user: dict = Depends(managed_user)):
    return serialize(await settings_document())


@router.put("/api/membership/settings", response_model=dict)
async def membership_settings_update(payload: MembershipSettingsInput, current_user: dict = Depends(get_current_user)):
    require_pastor(current_user)
    now = now_utc()
    updates = {**payload.model_dump(), "updated_by_user_id": current_user["user_id"], "updated_at": now}
    await db.membership_document_settings.update_one({"settings_id": "primary"}, {"$set": updates}, upsert=True)
    return serialize(await settings_document())


@router.post("/api/membership/settings/signature", response_model=dict)
async def membership_signature_upload(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    require_pastor(current_user)
    if file.content_type != "image/png":
        raise HTTPException(status_code=415, detail="La firma debe ser PNG transparente")
    content = await file.read(SIGNATURE_MAX_BYTES + 1)
    if len(content) > SIGNATURE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="La firma excede 500 KiB")
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="El contenido no es un PNG válido")
    try:
        image = Image.open(io.BytesIO(content)); image.load()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="No se pudo validar la imagen") from exc
    if image.width < 200 or image.height < 80 or image.width > 3000 or image.height > 1500:
        raise HTTPException(status_code=422, detail="La firma debe medir entre 200×80 y 3000×1500 px")
    if image.mode not in {"RGBA", "LA"} or not image.getchannel("A").getextrema()[0] < 255:
        raise HTTPException(status_code=422, detail="La firma debe conservar transparencia real")
    await settings_document()
    digest = hashlib.sha256(content).hexdigest(); filename = re.sub(r"[^A-Za-z0-9_.-]", "_", file.filename or "firma.png")
    stream = signature_bucket().open_upload_stream(filename, metadata={"kind": "authorized_membership_signature", "sha256": digest, "content_type": "image/png", "uploaded_by_user_id": current_user["user_id"], "uploaded_at": now_utc()})
    await stream.write(content); await stream.close(); document_id = str(stream._id)
    await db.membership_document_settings.update_one({"settings_id": "primary"}, {"$set": {"signature_file_id": document_id, "signature_sha256": digest, "updated_by_user_id": current_user["user_id"], "updated_at": now_utc()}})
    return {"signature_file_id": document_id, "sha256": digest}


@router.get("/api/membership/settings/signature")
async def membership_signature(current_user: dict = Depends(managed_user)):
    settings = await settings_document(); file_id = settings.get("signature_file_id")
    if not file_id or not ObjectId.is_valid(file_id):
        raise HTTPException(status_code=404, detail="Firma no configurada")
    stream = await signature_bucket().open_download_stream(ObjectId(file_id))
    return StreamingResponse(stream, media_type="image/png", headers={"Content-Disposition": "inline; filename=firma-autorizada.png", "Cache-Control": "private, no-store"})


@router.get("/api/membership/persons/{person_id}", response_model=dict)
async def person_membership(person_id: str, current_user: dict = Depends(managed_user)):
    person = await canonical_person(person_id)
    membership = await db.person_memberships.find_one({"person_id": person["person_id"]}, {"_id": 0})
    return {"exists": bool(membership), "data": await render_data(person, membership) if membership else {"person": {"person_id": person["person_id"], "full_name": full_name(person), "position": await position_from_profile(person["person_id"])}}}


@router.post("/api/membership/persons/{person_id}/documents/{document_type}/issue", response_model=dict, status_code=201)
async def issue_membership_document(person_id: str, document_type: Literal["card", "certificate"], payload: IssueDocumentInput, current_user: dict = Depends(managed_user)):
    person = await canonical_person(person_id)
    settings = await settings_document()
    if document_type == "card" and not await db.person_photos.find_one({"person_id": person["person_id"], "is_current": True}, {"_id": 1}):
        raise HTTPException(status_code=422, detail="La Persona 360 necesita fotografía antes de emitir el carnet")
    if document_type == "certificate" and not settings.get("signature_file_id"):
        raise HTTPException(status_code=409, detail="Configure la firma autorizada antes de emitir el certificado")
    requested_number = payload.existing_member_number if current_user.get("rol") == "pastor" else None
    membership = await get_or_create_membership(person, current_user["user_id"], requested_number)
    now = now_utc(); position = await position_from_profile(person["person_id"])
    updates = {"status": "active", "updated_by_user_id": current_user["user_id"], "updated_at": now}
    if document_type == "card":
        action = "reprinted" if membership.get("card_issue_date") else "issued"
        if not membership.get("card_issue_date"):
            updates["card_issue_date"] = payload.issue_date.isoformat()
            updates["card_expiration_date"] = add_months(payload.issue_date, settings.get("expiration_months", 12)).isoformat()
        updates["card_position_snapshot"] = position
    else:
        action = "reprinted" if membership.get("certificate_issue_date") else "issued"
        if not membership.get("certificate_issue_date"):
            updates["certificate_issue_date"] = payload.issue_date.isoformat()
    await db.person_memberships.update_one({"membership_id": membership["membership_id"]}, {"$set": updates})
    membership = await db.person_memberships.find_one({"membership_id": membership["membership_id"]}, {"_id": 0})
    snapshot = await render_data(person, membership)
    await record_event(current_user["user_id"], membership, person, document_type, action, snapshot)
    return {"action": action, "data": snapshot}


@router.post("/api/membership/persons/{person_id}/card/renew", response_model=dict)
async def renew_membership_card(person_id: str, payload: RenewCardInput, current_user: dict = Depends(managed_user)):
    person = await canonical_person(person_id); membership = await db.person_memberships.find_one({"person_id": person["person_id"]}, {"_id": 0})
    if not membership:
        raise HTTPException(status_code=404, detail="Emita primero el carnet")
    settings = await settings_document(); position = await position_from_profile(person["person_id"]); now = now_utc()
    updates = {"status": "active", "card_issue_date": payload.issue_date.isoformat(), "card_expiration_date": add_months(payload.issue_date, settings.get("expiration_months", 12)).isoformat(), "card_position_snapshot": position, "updated_by_user_id": current_user["user_id"], "updated_at": now}
    await db.person_memberships.update_one({"membership_id": membership["membership_id"]}, {"$set": updates})
    membership = await db.person_memberships.find_one({"membership_id": membership["membership_id"]}, {"_id": 0}); snapshot = await render_data(person, membership)
    await record_event(current_user["user_id"], membership, person, "card", "renewed", snapshot)
    return {"action": "renewed", "data": snapshot}


@router.get("/api/membership/persons/{person_id}/issuances", response_model=dict)
async def membership_issuances(person_id: str, current_user: dict = Depends(managed_user)):
    person = await canonical_person(person_id)
    items = await db.membership_document_issuances.find({"person_id": person["person_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"items": serialize(items)}


@router.get("/api/public/membership/verify/{token}", response_model=dict)
async def public_membership_verification(token: str):
    membership_id = membership_id_from_token(token)
    if not membership_id:
        return {"valid": False, "status": "invalid"}
    membership = await db.person_memberships.find_one({"membership_id": membership_id}, {"_id": 0})
    if not membership:
        return {"valid": False, "status": "invalid"}
    person = await canonical_person(membership["person_id"]); expiry = membership.get("card_expiration_date")
    credential_status = "inactive" if membership.get("status") != "active" else "expired" if expiry and expiry < date.today().isoformat() else "active"
    settings = await settings_document()
    return {"valid": credential_status == "active", "status": credential_status, "organization_name": settings.get("organization_name"), "member_number": membership["member_number"], "member_name": full_name(person), "position": membership.get("card_position_snapshot") or await position_from_profile(person["person_id"]), "issued": membership.get("card_issue_date"), "expires": expiry}


async def ensure_membership_documents():
    await db.person_memberships.create_index("membership_id", unique=True)
    await db.person_memberships.create_index("person_id", unique=True)
    await db.person_memberships.create_index("member_number", unique=True)
    await db.membership_document_issuances.create_index("issuance_id", unique=True)
    await db.membership_document_issuances.create_index([("person_id", 1), ("created_at", -1)])
    now = now_utc()
    await db.membership_document_settings.update_one({"settings_id": "primary"}, {"$setOnInsert": {"_id": "primary", "settings_id": "primary", "expiration_months": 12, "authorized_signer_name": "", "authorized_signer_title": "", "organization_name": "Casa de Oración Ven y Ve", "signature_file_id": None, "created_at": now}, "$set": {"updated_at": now}}, upsert=True)