"""Transcripción progresiva por ventanas y reconciliación diarizada final."""
import asyncio
import difflib
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pymongo import ReturnDocument

from meeting_transcription import TranscriptionProviderUnavailable, get_transcription_provider


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def speaker_name(index: int) -> str:
    return f"SPEAKER_{index:02d}"


def segment_values(segment: dict, offset: float) -> dict:
    start = float(segment.get("start", segment.get("start_seconds", 0)) or 0) + offset
    end = float(segment.get("end", segment.get("end_seconds", start)) or start) + offset
    return {
        "raw_speaker": str(segment.get("speaker") or segment.get("speaker_label") or "A"),
        "start_seconds": round(start, 3), "end_seconds": round(max(start, end), 3),
        "text": str(segment.get("text") or "").strip(),
    }


async def staged_audio(db, upload_id: str, path: Path) -> int:
    files = await db["board_recording_staging.files"].find(
        {"metadata.upload_id": upload_id}, {"_id": 1, "metadata.seq": 1}
    ).sort("metadata.seq", 1).to_list(10000)
    bucket = AsyncIOMotorGridFSBucket(db, bucket_name="board_recording_staging")
    written = 0
    with path.open("wb") as target:
        for item in files:
            source = await bucket.open_download_stream(item["_id"])
            while True:
                block = await source.read(1024 * 1024)
                if not block: break
                target.write(block); written += len(block)
            source.close()
    return written


async def recording_audio(db, recording_id: str, path: Path) -> dict:
    file_doc = await db["board_recordings.files"].find_one({"_id": ObjectId(recording_id)})
    if not file_doc: raise RuntimeError("Grabación no encontrada")
    source = await AsyncIOMotorGridFSBucket(db, bucket_name="board_recordings").open_download_stream(file_doc["_id"])
    with path.open("wb") as target:
        while True:
            block = await source.read(1024 * 1024)
            if not block: break
            target.write(block)
    source.close()
    return file_doc


async def extract_mp3(source: Path, target: Path, start_seconds: float | None = None, duration_seconds: float | None = None) -> None:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if start_seconds is not None: command.extend(["-ss", str(max(0, start_seconds))])
    command.extend(["-i", str(source)])
    if duration_seconds is not None: command.extend(["-t", str(max(1, duration_seconds))])
    command.extend(["-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(target)])
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()
    if process.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        raise RuntimeError(f"No se pudo preparar audio para STT: {stderr.decode(errors='ignore')[-300:]}")


def match_speakers(raw_segments: list[dict], existing: list[dict]) -> dict[str, str]:
    votes: dict[str, Counter] = defaultdict(Counter)
    for new in raw_segments:
        for old in existing:
            if abs(new["start_seconds"] - float(old.get("start_seconds", 0))) > 3.0: continue
            similarity = difflib.SequenceMatcher(None, new["text"].lower(), str(old.get("text") or "").lower()).ratio()
            if similarity >= 0.35: votes[new["raw_speaker"]][old["speaker_label"]] += similarity
    mapping = {raw: counts.most_common(1)[0][0] for raw, counts in votes.items() if counts}
    used = {item.get("speaker_label") for item in existing} | set(mapping.values())
    next_index = 0
    for raw in dict.fromkeys(item["raw_speaker"] for item in raw_segments):
        if raw in mapping: continue
        while speaker_name(next_index) in used: next_index += 1
        mapping[raw] = speaker_name(next_index); used.add(mapping[raw]); next_index += 1
    return mapping


async def save_live_segments(db, upload: dict, raw_segments: list[dict], offset: float) -> int:
    meeting_id = upload["meeting_id"]
    version = await db.board_transcript_versions.find_one({"meeting_id": meeting_id, "kind": "live_provisional", "source_upload_id": upload["upload_id"]}, {"_id": 0})
    if not version:
        latest = await db.board_transcript_versions.find_one({"meeting_id": meeting_id}, {"_id": 0, "version": 1}, sort=[("version", -1)])
        version_id = str(uuid4())
        version = {"_id": version_id, "transcript_version_id": version_id, "meeting_id": meeting_id, "source_upload_id": upload["upload_id"], "source_recording_id": None, "version": int((latest or {}).get("version", 0)) + 1, "kind": "live_provisional", "immutable": False, "status": "streaming", "provider": "openai_diarized", "full_text": "", "created_at": now_utc(), "updated_at": now_utc()}
        await db.board_transcript_versions.insert_one(version)
    version_id = version["transcript_version_id"]
    existing = await db.board_transcript_segments.find({"meeting_id": meeting_id, "transcript_version_id": version_id}, {"_id": 0}).sort("start_seconds", 1).to_list(50000)
    normalized = [segment_values(item, offset) for item in raw_segments if str(item.get("text") or "").strip()]
    mapping = match_speakers(normalized, [item for item in existing if float(item.get("end_seconds", 0)) >= max(0, offset - 3)])
    await db.board_transcript_segments.delete_many({"meeting_id": meeting_id, "transcript_version_id": version_id, "start_seconds": {"$gte": max(0, offset - 1)}})
    documents = []
    preserved = [item for item in existing if float(item.get("start_seconds", 0)) < max(0, offset - 1)]
    for sequence, item in enumerate(normalized):
        segment_id = f"live-{upload['upload_id']}-{round(item['start_seconds'] * 1000)}-{sequence}"
        documents.append({"_id": segment_id, "segment_id": segment_id, "meeting_id": meeting_id, "transcript_version_id": version_id, "source_upload_id": upload["upload_id"], "source_recording_id": None, "order": len(preserved) + sequence, "sequence": len(preserved) + sequence, "start_seconds": item["start_seconds"], "end_seconds": item["end_seconds"], "speaker_label": mapping[item["raw_speaker"]], "raw_speaker_label": item["raw_speaker"], "person_id": None, "text": item["text"], "confidence": None, "provisional": True, "created_at": now_utc()})
    if documents: await db.board_transcript_segments.insert_many(documents)
    complete_segments = preserved + documents
    await db.board_transcript_versions.update_one({"transcript_version_id": version_id}, {"$set": {"updated_at": now_utc(), "status": "streaming", "segment_count": len(complete_segments), "full_text": " ".join(item.get("text", "") for item in complete_segments).strip()}})
    return len(documents)


async def transcribe_live_upload(db, upload_id: str) -> None:
    upload = await db.board_recording_uploads.find_one_and_update(
        {"upload_id": upload_id, "status": "uploading", "live_job_active": {"$ne": True}},
        {"$set": {"live_job_active": True, "live_transcription_status": "processing", "live_job_started_at": now_utc()}},
        return_document=ReturnDocument.AFTER,
    )
    if not upload: return
    provider = get_transcription_provider()
    if not provider.is_configured():
        await db.board_recording_uploads.update_one({"upload_id": upload_id}, {"$set": {"live_job_active": False, "live_transcription_status": "blocked", "live_transcription_message": "Proveedor STT no configurado", "updated_at": now_utc()}}); return
    elapsed = float(upload.get("elapsed_seconds") or 0); window_seconds = min(60.0, max(20.0, elapsed)); offset = max(0.0, elapsed - window_seconds)
    try:
        with tempfile.TemporaryDirectory(prefix="board-live-") as folder:
            source = Path(folder) / "live.webm"; target = Path(folder) / "window.mp3"
            if await staged_audio(db, upload_id, source) == 0: return
            await extract_mp3(source, target, offset, window_seconds)
            result = await provider.transcribe_path(target)
        current = await db.board_recording_uploads.find_one({"upload_id": upload_id}, {"_id": 0, "status": 1})
        if not current or current.get("status") != "uploading": return
        count = await save_live_segments(db, upload, result.get("segments", []), offset)
        await db.board_recording_uploads.update_one({"upload_id": upload_id}, {"$set": {"live_transcription_status": "streaming", "last_live_segment_count": count, "last_transcribed_seq": upload.get("next_seq", 0), "live_transcribed_at": now_utc(), "updated_at": now_utc()}})
    except Exception as exc:
        await db.board_recording_uploads.update_one({"upload_id": upload_id}, {"$set": {"live_transcription_status": "retry", "live_transcription_message": type(exc).__name__, "updated_at": now_utc()}})
    finally:
        await db.board_recording_uploads.update_one({"upload_id": upload_id}, {"$set": {"live_job_active": False, "updated_at": now_utc()}})


async def transcribe_final_recording(db, recording_id: str) -> dict:
    provider = get_transcription_provider()
    if not provider.is_configured(): raise TranscriptionProviderUnavailable("Proveedor STT no configurado")
    with tempfile.TemporaryDirectory(prefix="board-final-") as folder:
        source = Path(folder) / "recording.webm"; file_doc = await recording_audio(db, recording_id, source)
        duration = float(file_doc.get("metadata", {}).get("duration_seconds") or 0)
        windows = [] if duration else [(0.0, None)]
        if duration:
            start = 0.0
            while start < duration:
                windows.append((start, min(1200.0, duration - start))); start += 1170.0
        all_segments = []
        for index, (start, length) in enumerate(windows):
            target = Path(folder) / f"final-{index}.mp3"; await extract_mp3(source, target, start if start else None, length)
            result = await provider.transcribe_path(target)
            window_segments = [segment_values(item, start) for item in result.get("segments", []) if str(item.get("text") or "").strip()]
            speaker_mapping = match_speakers(window_segments, all_segments)
            for item in window_segments:
                item["speaker_label"] = speaker_mapping[item["raw_speaker"]]
            all_segments.extend(window_segments)
    stitched = []
    for item in sorted(all_segments, key=lambda value: value["start_seconds"]):
        duplicate = next((old for old in reversed(stitched[-20:]) if abs(item["start_seconds"] - old["start_seconds"]) < 3 and difflib.SequenceMatcher(None, item["text"].lower(), old["text"].lower()).ratio() > 0.65), None)
        if duplicate: continue
        stitched.append(item)
    meeting_id = file_doc["metadata"]["meeting_id"]
    latest = await db.board_transcript_versions.find_one({"meeting_id": meeting_id}, {"_id": 0}, sort=[("version", -1)])
    version_id = str(uuid4()); version = int((latest or {}).get("version", 0)) + 1; now = now_utc()
    version_doc = {"_id": version_id, "transcript_version_id": version_id, "meeting_id": meeting_id, "source_recording_id": recording_id, "recording_id": recording_id, "version": version, "kind": "final_reconciled", "immutable": True, "status": "complete", "provider": provider.provider_key, "model": provider.model, "full_text": " ".join(item["text"] for item in stitched).strip(), "created_at": now, "completed_at": now}
    await db.board_transcript_versions.insert_one(version_doc)
    documents = []
    for sequence, item in enumerate(stitched):
        segment_id = str(uuid4()); documents.append({"_id": segment_id, "segment_id": segment_id, "meeting_id": meeting_id, "transcript_version_id": version_id, "source_recording_id": recording_id, "order": sequence, "sequence": sequence, "start_seconds": item["start_seconds"], "end_seconds": item["end_seconds"], "speaker_label": item["speaker_label"], "raw_speaker_label": item["raw_speaker"], "person_id": None, "text": item["text"], "confidence": None, "provisional": False, "created_at": now})
    if documents: await db.board_transcript_segments.insert_many(documents)
    await db.board_transcript_versions.update_many({"meeting_id": meeting_id, "kind": "live_provisional", "status": "streaming"}, {"$set": {"status": "superseded", "superseded_by_version_id": version_id, "updated_at": now}})
    await db["board_recordings.files"].update_one({"_id": ObjectId(recording_id)}, {"$set": {"metadata.transcription_status": "completed", "metadata.transcript_version_id": version_id, "metadata.transcription_provider": provider.provider_key, "metadata.transcription_model": provider.model, "metadata.transcribed_at": now}, "$unset": {"metadata.transcription_error": ""}})
    await db.board_recording_uploads.update_one({"recording_id": ObjectId(recording_id)}, {"$set": {"live_transcription_status": "completed", "live_job_active": False, "updated_at": now}, "$unset": {"live_transcription_message": ""}})
    await db.board_meetings.update_one({"meeting_id": meeting_id}, {"$set": {"transcription_status": "completed", "final_transcript_version_id": version_id, "updated_at": now}})
    return {"meeting_id": meeting_id, "transcript_version_id": version_id, "segments": len(documents)}