import hashlib
import os
from typing import Literal
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field

from access_control import (
    BAPTISM_READ, BAPTISM_WRITE, FORMATION_CERTIFICATES_ISSUE,
    FORMATION_HISTORICAL_CREDIT_MANAGE, FORMATION_READ,
    has_capability, is_global_pastoral_authority,
)
from formation_engine import audit, canonical_person, now_utc, require_person_access, serialize
from server import db, get_current_user


router = APIRouter(prefix="/api/formation", tags=["formation-documents"])
BUCKET = "formation_documents"
MAX_BYTES = int(os.environ.get("MAX_FORMATION_DOCUMENT_BYTES", str(10 * 1024 * 1024)))
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def bucket(): return AsyncIOMotorGridFSBucket(db, bucket_name=BUCKET)


class CertificateIssueInput(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    allow_historical_reissue: bool = False


def capability_for_purpose(purpose: str, write: bool = False) -> str:
    if purpose == "historical_credit": return FORMATION_HISTORICAL_CREDIT_MANAGE
    if purpose == "baptism": return BAPTISM_WRITE if write else BAPTISM_READ
    return FORMATION_CERTIFICATES_ISSUE if write else FORMATION_READ


@router.post("/persons/{person_id}/documents", status_code=201, response_model=dict)
async def upload_document(person_id: str, purpose: Literal["historical_credit", "baptism", "certificate"] = Form(...), file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    await require_person_access(db, current_user, person_id, capability_for_purpose(purpose, True))
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_TYPES: raise HTTPException(status_code=415, detail="Tipo de documento no permitido")
    data = await file.read(MAX_BYTES + 1)
    if not data: raise HTTPException(status_code=422, detail="Documento vacío")
    if len(data) > MAX_BYTES: raise HTTPException(status_code=413, detail="Documento excede el límite")
    document_id, now = ObjectId(), now_utc(); digest = hashlib.sha256(data).hexdigest()
    await bucket().upload_from_stream_with_id(document_id, file.filename or "documento", data, metadata={"person_id": person_id, "purpose": purpose, "content_type": content_type, "size": len(data), "sha256": digest, "uploaded_by_user_id": current_user["user_id"], "uploaded_at": now, "active": True})
    result = {"document_id": str(document_id), "person_id": person_id, "purpose": purpose, "filename": file.filename, "content_type": content_type, "size": len(data), "sha256": digest, "uploaded_at": now}
    await audit(db, current_user, "formation_document_uploaded", "formation_document", str(document_id), None, result, person_id=person_id)
    return serialize(result)


@router.get("/documents/{document_id}")
async def download_document(document_id: str, current_user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(document_id): raise HTTPException(status_code=404, detail="Documento no encontrado")
    file_doc = await db[f"{BUCKET}.files"].find_one({"_id": ObjectId(document_id), "metadata.active": True})
    if not file_doc: raise HTTPException(status_code=404, detail="Documento no encontrado")
    metadata = file_doc.get("metadata") or {}; await require_person_access(db, current_user, metadata["person_id"], capability_for_purpose(metadata.get("purpose", "certificate")))
    stream = await bucket().open_download_stream(ObjectId(document_id))
    return StreamingResponse(stream, media_type=metadata.get("content_type", "application/octet-stream"), headers={"Content-Disposition": f'attachment; filename="{file_doc.get("filename", "documento")}"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/achievements/{achievement_id}/certificates", status_code=201, response_model=dict)
async def issue_certificate_record(achievement_id: str, payload: CertificateIssueInput, current_user: dict = Depends(get_current_user)):
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, FORMATION_CERTIFICATES_ISSUE): raise HTTPException(status_code=403, detail="Sin permiso para certificados de formación")
    achievement = await db.formation_achievements.find_one({"achievement_id": achievement_id, "active": True}, {"_id": 0})
    if not achievement: raise HTTPException(status_code=404, detail="Logro no encontrado")
    module = await db.formation_modules.find_one({"module_id": achievement["module_id"]}, {"_id": 0})
    program = await db.formation_programs.find_one({"program_id": achievement["program_id"]}, {"_id": 0})
    enabled = bool((module or {}).get("certificate_enabled") or (program or {}).get("certificate_enabled"))
    if not enabled: raise HTTPException(status_code=409, detail="Este programa o módulo no genera certificado")
    if achievement.get("source") == "historical_accreditation" and not (payload.allow_historical_reissue and achievement.get("evidence_document_id")):
        raise HTTPException(status_code=409, detail="Una acreditación histórica no genera certificado sin evidencia y autorización explícita")
    existing = await db.formation_certificate_issuances.find_one({"achievement_id": achievement_id, "status": {"$ne": "revoked"}}, {"_id": 0})
    if existing: return serialize(existing)
    issuance_id, now = str(uuid4()), now_utc(); doc = {"_id": issuance_id, "issuance_id": issuance_id, "achievement_id": achievement_id, "person_id": achievement["person_id"], "program_id": achievement["program_id"], "module_id": achievement["module_id"], "program_name_snapshot": achievement["program_name_snapshot"], "module_name_snapshot": achievement["module_name_snapshot"], "status": "eligible_for_generation", "document_id": None, "reason": payload.reason, "issued_by_user_id": current_user["user_id"], "issued_at": now}
    await db.formation_certificate_issuances.insert_one(doc); await audit(db, current_user, "formation_certificate_authorized", "formation_certificate_issuance", issuance_id, None, doc, payload.reason, achievement["person_id"])
    return serialize(doc)


async def ensure_document_indexes():
    await db[f"{BUCKET}.files"].create_index([("metadata.person_id", 1), ("metadata.purpose", 1), ("uploadDate", -1)])
    await db.formation_certificate_issuances.create_index("issuance_id", unique=True)
    await db.formation_certificate_issuances.create_index([("achievement_id", 1), ("status", 1)])