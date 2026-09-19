"""Audio protegido, transcript versionado y asociación Speaker → Persona."""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from access_control import DOORS_MANAGE
from board_ai_provider import BoardAIProviderDegraded, BoardAIProviderUnavailable, get_board_ai_provider
from board_ai_service import generate_board_artifacts, transcribe_recording
from door_board_engine import ensure_board_access, person_summary, record_board_audit, serialize
from meeting_transcription import get_transcription_provider
from server import db, get_current_user

router = APIRouter(prefix="/api/board", tags=["board-recordings-ai"])


def positive_int_setting(name: str, fallback: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return fallback
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


MAX_AUDIO_BYTES = positive_int_setting("MAX_AUDIO_BYTES", 24 * 1024 * 1024)
MAX_AUDIO_SECONDS = positive_int_setting("MAX_AUDIO_SECONDS", 4 * 60 * 60)
MAX_DOCUMENT_BYTES = positive_int_setting("MAX_BOARD_DOCUMENT_BYTES", 10 * 1024 * 1024)
CHUNK_SIZE = 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "text/plain", "image/png", "image/jpeg"}


def stage_bucket(): return AsyncIOMotorGridFSBucket(db, bucket_name="board_recording_staging")
def recording_bucket(): return AsyncIOMotorGridFSBucket(db, bucket_name="board_recordings")
def document_bucket(): return AsyncIOMotorGridFSBucket(db, bucket_name="board_documents")


class UploadStart(BaseModel):
    meeting_id: str
    content_type: str = Field(pattern=r"^audio/(webm|wav|mpeg|mp4|ogg|aac|flac)")


class UploadComplete(BaseModel):
    duration_seconds: float = Field(gt=0)


class SpeakerMappingUpdate(BaseModel):
    speaker_label: str = Field(min_length=1, max_length=80)
    person_id: str
    external_processing_acknowledged: bool


class TranscriptSegmentCorrection(BaseModel):
    segment_id: str
    text: str = Field(min_length=1, max_length=10000)
    external_processing_acknowledged: bool


class AiDraftRequest(BaseModel):
    external_processing_acknowledged: bool


def queue_ai_regeneration(background: BackgroundTasks, meeting_id: str, user_id: str, reason: str) -> str:
    if not get_board_ai_provider().is_configured():
        return "regeneration_blocked"
    background.add_task(generate_board_artifacts, db, meeting_id, user_id, reason)
    return "regeneration_queued"


async def ensure_recording_access(current_user: dict, permission: str):
    await ensure_board_access(db, current_user, permission)


@router.post("/recordings/uploads", response_model=dict, status_code=201)
async def start_recording_upload(payload: UploadStart, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.audio.manage")
    meeting = await db.board_meetings.find_one({"meeting_id": payload.meeting_id}, {"_id": 0})
    if not meeting: raise HTTPException(status_code=404, detail="Reunión no encontrada")
    if not meeting.get("recording_notice_confirmed"): raise HTTPException(status_code=409, detail="Confirme el aviso antes de grabar")
    upload_id = str(uuid4()); now = datetime.now(timezone.utc)
    await db.board_recording_uploads.insert_one({"_id": upload_id, "upload_id": upload_id, "meeting_id": payload.meeting_id, "owner_user_id": current_user["user_id"], "content_type": payload.content_type, "next_seq": 0, "bytes": 0, "status": "uploading", "created_at": now, "updated_at": now})
    return {"upload_id": upload_id, "max_bytes": MAX_AUDIO_BYTES, "max_seconds": MAX_AUDIO_SECONDS, "next_seq": 0}


@router.put("/recordings/uploads/{upload_id}/chunks/{seq}", response_model=dict)
async def upload_recording_chunk(upload_id: str, seq: int, request: Request, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.audio.manage")
    upload = await db.board_recording_uploads.find_one({"upload_id": upload_id, "owner_user_id": current_user["user_id"], "status": "uploading"})
    if not upload: raise HTTPException(status_code=404, detail="Carga no encontrada")
    if seq != upload["next_seq"]: raise HTTPException(status_code=409, detail="Secuencia inesperada")
    file_id = ObjectId(); target = stage_bucket().open_upload_stream_with_id(file_id, f"{upload_id}/{seq}", metadata={"upload_id": upload_id, "owner_user_id": current_user["user_id"], "seq": seq, "content_type": upload["content_type"]})
    received = 0
    try:
        async for part in request.stream():
            received += len(part)
            if received > 2 * 1024 * 1024 or upload["bytes"] + received > MAX_AUDIO_BYTES: raise HTTPException(status_code=413, detail="Audio excede el límite")
            await target.write(part)
        if received == 0: raise HTTPException(status_code=422, detail="Chunk vacío")
        await target.close()
    except Exception:
        try: await target.abort()
        except Exception: pass
        raise
    result = await db.board_recording_uploads.update_one({"upload_id": upload_id, "next_seq": seq, "status": "uploading"}, {"$inc": {"next_seq": 1, "bytes": received}, "$set": {"updated_at": datetime.now(timezone.utc)}})
    if not result.modified_count:
        await stage_bucket().delete(file_id); raise HTTPException(status_code=409, detail="Secuencia ya procesada")
    return {"seq": seq, "bytes": received, "total_bytes": upload["bytes"] + received}


@router.post("/recordings/uploads/{upload_id}/complete", response_model=dict)
async def complete_recording_upload(upload_id: str, payload: UploadComplete, background: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.audio.manage")
    upload = await db.board_recording_uploads.find_one({"upload_id": upload_id, "owner_user_id": current_user["user_id"]})
    if not upload: raise HTTPException(status_code=404, detail="Carga no encontrada")
    if upload["status"] == "complete": return {"recording_id": str(upload["recording_id"]), "sha256": upload["sha256"], "bytes": upload["bytes"], "status": "ready"}
    if payload.duration_seconds > MAX_AUDIO_SECONDS: raise HTTPException(status_code=413, detail="Duración excedida")
    if upload["next_seq"] == 0: raise HTTPException(status_code=409, detail="No hay audio para finalizar")
    finalization_token = str(uuid4()); claim_time = datetime.now(timezone.utc)
    upload = await db.board_recording_uploads.find_one_and_update(
        {"upload_id": upload_id, "owner_user_id": current_user["user_id"], "status": "uploading"},
        {"$set": {"status": "finalizing", "finalization_token": finalization_token, "finalization_started_at": claim_time, "updated_at": claim_time}},
        return_document=ReturnDocument.AFTER,
    )
    if not upload:
        current = await db.board_recording_uploads.find_one({"upload_id": upload_id, "owner_user_id": current_user["user_id"]})
        if current and current.get("status") == "complete": return {"recording_id": str(current["recording_id"]), "sha256": current["sha256"], "bytes": current["bytes"], "status": "ready"}
        raise HTTPException(status_code=409, detail="La carga ya está siendo finalizada")
    recording_id = ObjectId(); target = recording_bucket().open_upload_stream_with_id(recording_id, f"board-{upload['meeting_id']}-{upload_id}.webm", metadata={"meeting_id": upload["meeting_id"], "owner_user_id": current_user["user_id"], "upload_id": upload_id, "immutable": True, "content_type": upload["content_type"], "bytes": upload["bytes"], "duration_seconds": payload.duration_seconds, "sha256": None, "status": "ready", "transcription_status": "queued", "created_at": datetime.now(timezone.utc)})
    digest = hashlib.sha256(); staging = stage_bucket()
    try:
        for seq in range(upload["next_seq"]):
            file_doc = await db["board_recording_staging.files"].find_one({"metadata.upload_id": upload_id, "metadata.seq": seq})
            if not file_doc: raise HTTPException(status_code=409, detail=f"Falta chunk {seq}")
            source = await staging.open_download_stream(file_doc["_id"])
            while True:
                block = await source.read(CHUNK_SIZE)
                if not block: break
                digest.update(block); await target.write(block)
            source.close()
        await target.close()
    except Exception:
        try: await target.abort()
        except Exception: pass
        await db.board_recording_uploads.update_one({"upload_id": upload_id, "status": "finalizing", "finalization_token": finalization_token}, {"$set": {"status": "uploading", "updated_at": datetime.now(timezone.utc)}, "$unset": {"finalization_token": "", "finalization_started_at": ""}})
        raise
    sha = digest.hexdigest(); now = datetime.now(timezone.utc)
    try:
        await db["board_recordings.files"].update_one({"_id": recording_id}, {"$set": {"metadata.sha256": sha}})
        completed = await db.board_recording_uploads.update_one({"upload_id": upload_id, "status": "finalizing", "finalization_token": finalization_token}, {"$set": {"status": "complete", "recording_id": recording_id, "sha256": sha, "duration_seconds": payload.duration_seconds, "completed_at": now, "updated_at": now}, "$unset": {"finalization_token": "", "finalization_started_at": ""}})
        if completed.modified_count != 1:
            raise HTTPException(status_code=409, detail="Otra solicitud completó esta carga")
    except Exception:
        try: await recording_bucket().delete(recording_id)
        except Exception: pass
        await db.board_recording_uploads.update_one({"upload_id": upload_id, "status": "finalizing", "finalization_token": finalization_token}, {"$set": {"status": "uploading", "updated_at": datetime.now(timezone.utc)}, "$unset": {"finalization_token": "", "finalization_started_at": ""}})
        raise
    staged = await db["board_recording_staging.files"].find({"metadata.upload_id": upload_id}, {"_id": 1}).to_list(10000)
    for item in staged: await staging.delete(item["_id"])
    provider = get_transcription_provider()
    if provider.is_configured():
        background.add_task(transcribe_recording, db, str(recording_id)); transcription_status = "queued"
    else:
        transcription_status = "blocked"
        await db["board_recordings.files"].update_one({"_id": recording_id}, {"$set": {"metadata.transcription_status": "blocked", "metadata.transcription_provider": provider.provider_key, "metadata.transcription_message": "Identificación de participantes pendiente de procesamiento STT diarizado."}})
    await record_board_audit(db, current_user["user_id"], "recording_completed", "board_recording", str(recording_id), {"meeting_id": upload["meeting_id"], "bytes": upload["bytes"], "sha256": sha})
    return {"recording_id": str(recording_id), "sha256": sha, "bytes": upload["bytes"], "status": "ready", "transcription_status": transcription_status}


@router.get("/meetings/{meeting_id}/recordings", response_model=dict)
async def list_recordings(meeting_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.audio.manage")
    docs = await db["board_recordings.files"].find({"metadata.meeting_id": meeting_id}, {"_id": 1, "length": 1, "uploadDate": 1, "metadata": 1}).sort("uploadDate", -1).to_list(100)
    return {"items": [{"recording_id": str(item["_id"]), "bytes": item.get("length"), "uploaded_at": serialize(item.get("uploadDate")), **serialize(item.get("metadata", {}))} for item in docs]}


@router.get("/recordings/{recording_id}")
async def download_recording(recording_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.audio.manage")
    if not ObjectId.is_valid(recording_id): raise HTTPException(status_code=404, detail="Grabación no encontrada")
    doc = await db["board_recordings.files"].find_one({"_id": ObjectId(recording_id)})
    if not doc: raise HTTPException(status_code=404, detail="Grabación no encontrada")
    source = await recording_bucket().open_download_stream(ObjectId(recording_id))
    async def stream():
        try:
            while True:
                block = await source.read(CHUNK_SIZE)
                if not block: break
                yield block
        finally: source.close()
    return StreamingResponse(stream(), media_type=doc["metadata"].get("content_type", "audio/webm"), headers={"Content-Disposition": "attachment; filename=audio-junta.webm", "X-Content-SHA256": doc["metadata"].get("sha256", ""), "Cache-Control": "private, no-store"})


@router.post("/recordings/{recording_id}/transcribe", response_model=dict)
async def request_transcription(recording_id: str, background: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.audio.manage")
    if not ObjectId.is_valid(recording_id) or not await db["board_recordings.files"].find_one({"_id": ObjectId(recording_id)}): raise HTTPException(status_code=404, detail="Grabación no encontrada")
    provider = get_transcription_provider()
    if not provider.is_configured(): raise HTTPException(status_code=503, detail="STT diarizado: BLOCKED — external credential required")
    background.add_task(transcribe_recording, db, recording_id); return {"status": "queued", "provider": provider.provider_key}


@router.get("/meetings/{meeting_id}/transcript", response_model=dict)
async def get_transcript(meeting_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.audio.manage")
    version = await db.board_transcript_versions.find_one({"meeting_id": meeting_id}, {"_id": 0}, sort=[("version", -1)])
    if not version: return {"version": None, "segments": [], "mappings": []}
    segments = await db.board_transcript_segments.find({"transcript_version_id": version["transcript_version_id"]}, {"_id": 0}).sort("order", 1).to_list(10000)
    for segment in segments: segment["person"] = await person_summary(db, segment.get("person_id")) if segment.get("person_id") else None
    mappings = await db.board_speaker_mappings.find({"meeting_id": meeting_id}, {"_id": 0}).to_list(100)
    return {**serialize(version), "segments": serialize(segments), "mappings": serialize(mappings)}


async def create_corrected_transcript(meeting_id: str, actor_user_id: str, text_correction: TranscriptSegmentCorrection | None = None):
    latest = await db.board_transcript_versions.find_one({"meeting_id": meeting_id}, {"_id": 0}, sort=[("version", -1)])
    if not latest: raise HTTPException(status_code=409, detail="No existe transcript original")
    source_segments = await db.board_transcript_segments.find({"transcript_version_id": latest["transcript_version_id"]}, {"_id": 0}).sort("order", 1).to_list(10000)
    mappings = {item["speaker_label"]: item["person_id"] async for item in db.board_speaker_mappings.find({"meeting_id": meeting_id}, {"_id": 0})}
    transcript_id = str(uuid4()); version = latest["version"] + 1; now = datetime.now(timezone.utc); new_segments = []
    for item in source_segments:
        segment_id = str(uuid4()); text = text_correction.text if text_correction and item["segment_id"] == text_correction.segment_id else item["text"]
        new_segments.append({"_id": segment_id, "segment_id": segment_id, "transcript_version_id": transcript_id, "meeting_id": meeting_id, "order": item["order"], "speaker_label": item["speaker_label"], "person_id": mappings.get(item["speaker_label"], item.get("person_id")), "start_seconds": item.get("start_seconds"), "end_seconds": item.get("end_seconds"), "text": text, "source_segment_id": item["segment_id"], "created_at": now})
    doc = {"_id": transcript_id, "transcript_version_id": transcript_id, "meeting_id": meeting_id, "recording_id": latest.get("recording_id"), "version": version, "kind": "human_corrected", "full_text": " ".join(item["text"] for item in new_segments), "source_version_id": latest["transcript_version_id"], "immutable": True, "created_by_user_id": actor_user_id, "created_at": now}
    await db.board_transcript_versions.insert_one(doc)
    if new_segments: await db.board_transcript_segments.insert_many(new_segments)
    await db.board_ai_artifacts.update_many({"meeting_id": meeting_id, "valid": True}, {"$set": {"valid": False, "invalidated_at": now, "invalidated_reason": "transcript_corrected"}})
    return doc


@router.put("/meetings/{meeting_id}/speaker-mapping", response_model=dict)
async def update_speaker_mapping(meeting_id: str, payload: SpeakerMappingUpdate, background: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.notes.write")
    if not payload.external_processing_acknowledged: raise HTTPException(status_code=409, detail="Confirme el procesamiento externo antes de regenerar derivados")
    if not ObjectId.is_valid(payload.person_id) or not await db.persons.find_one({"_id": ObjectId(payload.person_id)}): raise HTTPException(status_code=404, detail="Persona no encontrada")
    now = datetime.now(timezone.utc); mapping_id = f"{meeting_id}:{payload.speaker_label}"
    await db.board_speaker_mappings.update_one({"meeting_id": meeting_id, "speaker_label": payload.speaker_label}, {"$set": {"person_id": payload.person_id, "corrected_by_user_id": current_user["user_id"], "updated_at": now}, "$setOnInsert": {"_id": mapping_id, "mapping_id": mapping_id, "meeting_id": meeting_id, "created_at": now}}, upsert=True)
    version = await create_corrected_transcript(meeting_id, current_user["user_id"])
    derived_status = queue_ai_regeneration(background, meeting_id, current_user["user_id"], "speaker_mapping_corrected")
    await record_board_audit(db, current_user["user_id"], "speaker_mapping_corrected", "board_meeting", meeting_id, {"speaker_label": payload.speaker_label, "person_id": payload.person_id})
    return {"mapping": {"speaker_label": payload.speaker_label, "person_id": payload.person_id}, "transcript_version": version["version"], "derived_status": derived_status}


@router.put("/meetings/{meeting_id}/transcript-segment", response_model=dict)
async def correct_transcript_segment(meeting_id: str, payload: TranscriptSegmentCorrection, background: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.notes.write")
    if not payload.external_processing_acknowledged: raise HTTPException(status_code=409, detail="Confirme el procesamiento externo antes de regenerar derivados")
    version = await create_corrected_transcript(meeting_id, current_user["user_id"], payload)
    derived_status = queue_ai_regeneration(background, meeting_id, current_user["user_id"], "transcript_text_corrected")
    await record_board_audit(db, current_user["user_id"], "transcript_text_corrected", "board_meeting", meeting_id, {"source_segment_id": payload.segment_id, "version": version["version"]})
    return {"transcript_version": version["version"], "derived_status": derived_status}


@router.get("/ai/status", response_model=dict)
async def get_ai_status(current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.minutes.review")
    return get_board_ai_provider().status()


@router.post("/meetings/{meeting_id}/ai-draft", response_model=dict)
async def generate_ai_draft(meeting_id: str, payload: AiDraftRequest, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.minutes.review")
    if not payload.external_processing_acknowledged:
        raise HTTPException(status_code=409, detail="Confirme el procesamiento externo de las fuentes para generar el borrador")
    try:
        result = await generate_board_artifacts(db, meeting_id, current_user["user_id"])
        await record_board_audit(db, current_user["user_id"], "ai_draft_generated", "board_meeting", meeting_id, {"artifact_id": result["artifact_id"], "model": result["model"]})
        return result
    except BoardAIProviderUnavailable: raise HTTPException(status_code=503, detail={"status": "BLOCKED", "error_code": "board_ai_not_configured"})
    except BoardAIProviderDegraded: raise HTTPException(status_code=503, detail={"status": "DEGRADED", "error_code": "board_ai_provider_failure"})
    except json.JSONDecodeError: raise HTTPException(status_code=502, detail="La IA no devolvió un borrador estructurado")
    except Exception as exc: raise HTTPException(status_code=502, detail=f"No se pudo generar el borrador: {type(exc).__name__}")


@router.post("/meetings/{meeting_id}/documents", response_model=dict, status_code=201)
async def upload_board_document(meeting_id: str, file: UploadFile = File(...), agenda_item_id: str | None = Form(default=None), current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.meetings.write")
    if not await db.board_meetings.find_one({"meeting_id": meeting_id}): raise HTTPException(status_code=404, detail="Reunión no encontrada")
    if file.content_type not in ALLOWED_DOCUMENT_TYPES: raise HTTPException(status_code=415, detail="Tipo de documento no permitido")
    if agenda_item_id and not await db.board_agenda_items.find_one({"agenda_item_id": agenda_item_id, "meeting_id": meeting_id}): raise HTTPException(status_code=422, detail="Punto de agenda no válido")
    filename = Path(file.filename or "documento").name[:180]; document_id = ObjectId(); target = document_bucket().open_upload_stream_with_id(document_id, filename, metadata={"meeting_id": meeting_id, "agenda_item_id": agenda_item_id, "filename": filename, "content_type": file.content_type, "owner_user_id": current_user["user_id"], "immutable": True, "sha256": None, "created_at": datetime.now(timezone.utc)})
    size = 0; digest = hashlib.sha256()
    try:
        while True:
            block = await file.read(CHUNK_SIZE)
            if not block: break
            size += len(block)
            if size > MAX_DOCUMENT_BYTES: raise HTTPException(status_code=413, detail="Documento excede el límite")
            digest.update(block); await target.write(block)
        if size == 0: raise HTTPException(status_code=422, detail="Documento vacío")
        await target.close()
    except Exception:
        try: await target.abort()
        except Exception: pass
        raise
    sha = digest.hexdigest(); await db["board_documents.files"].update_one({"_id": document_id}, {"$set": {"metadata.sha256": sha, "metadata.bytes": size}})
    await record_board_audit(db, current_user["user_id"], "document_uploaded", "board_document", str(document_id), {"meeting_id": meeting_id, "filename": filename, "sha256": sha})
    return {"document_id": str(document_id), "filename": filename, "content_type": file.content_type, "bytes": size, "sha256": sha}


@router.get("/meetings/{meeting_id}/documents", response_model=dict)
async def list_board_documents(meeting_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.read")
    docs = await db["board_documents.files"].find({"metadata.meeting_id": meeting_id}, {"_id": 1, "length": 1, "uploadDate": 1, "metadata": 1}).sort("uploadDate", -1).to_list(500)
    return {"items": [{"document_id": str(item["_id"]), "bytes": item.get("length"), "uploaded_at": serialize(item.get("uploadDate")), **serialize(item.get("metadata", {}))} for item in docs]}


@router.get("/documents/{document_id}")
async def download_board_document(document_id: str, current_user: dict = Depends(get_current_user)):
    await ensure_recording_access(current_user, "board.read")
    if not ObjectId.is_valid(document_id): raise HTTPException(status_code=404, detail="Documento no encontrado")
    doc = await db["board_documents.files"].find_one({"_id": ObjectId(document_id)})
    if not doc: raise HTTPException(status_code=404, detail="Documento no encontrado")
    source = await document_bucket().open_download_stream(ObjectId(document_id))
    async def stream():
        try:
            while True:
                block = await source.read(CHUNK_SIZE)
                if not block: break
                yield block
        finally: source.close()
    safe_name = Path(doc.get("filename") or doc["metadata"].get("filename", "documento")).name
    return StreamingResponse(stream(), media_type=doc["metadata"].get("content_type", "application/octet-stream"), headers={"Content-Disposition": f'attachment; filename="{safe_name}"', "X-Content-SHA256": doc["metadata"].get("sha256", ""), "Cache-Control": "private, no-store"})