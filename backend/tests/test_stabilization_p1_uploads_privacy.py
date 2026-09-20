import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from bson import Binary, ObjectId
from httpx import ASGITransport, AsyncClient

import server
import board_recording_routes
from access_control import access_defaults_for_role
from geo_provider import GeocodeResult, set_geocoding_provider_for_tests
from person_profile_domains import cleanup_abandoned_photo_uploads


PREFIX = "stabilization.uploads."
PASSWORD = "StabilizationUploads!"


class StableGeocoder:
    async def geocode(self, address):
        return GeocodeResult(status="matched", latitude=39.9411, longitude=-83.0895, confidence="high", confidence_score=1, accuracy="rooftop", provider="test")


async def make_user(role="persona"):
    user_id, person_id = ObjectId(), ObjectId(); email = f"{PREFIX}{uuid.uuid4().hex[:8]}@example.com"; now = datetime.now(timezone.utc)
    await server.db.persons.insert_one({"_id": person_id, "person_number": f"VV-UP{str(person_id)[-6:].upper()}", "nombre": "QA Upload", "apellido": role, "search_key": f"qa upload {role}", "idempotency_key": f"stabilization:uploads:{email}", "version": 1, "auth_user_id": str(user_id), "created_at": now, "updated_at": now})
    await server.db.users.insert_one({"_id": user_id, "nombre": f"QA {role}", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": str(person_id), "is_active": True, "token_version": 1, **access_defaults_for_role(role)})
    return str(user_id), str(person_id), email


async def login(email):
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client, {"Authorization": f"Bearer {response.json()['token']}"}


async def cleanup():
    users = await server.db.users.find({"email": {"$regex": f"^{PREFIX}"}}, {"_id": 1, "person_id": 1}).to_list(100)
    user_ids = [str(item["_id"]) for item in users]; person_ids = [item["person_id"] for item in users if item.get("person_id")]
    targets = await server.db.evangelism_targets.find({"created_by_user_id": {"$in": user_ids}}, {"_id": 0, "target_id": 1}).to_list(100)
    target_ids = [item["target_id"] for item in targets]
    await server.db.evangelism_target_events.delete_many({"target_id": {"$in": target_ids}}); await server.db.evangelism_targets.delete_many({"target_id": {"$in": target_ids}})
    meeting_ids = await server.db.board_meetings.distinct("meeting_id", {"title": {"$regex": "^STABILIZATION UPLOAD"}})
    uploads = await server.db.board_recording_uploads.find({"meeting_id": {"$in": meeting_ids}}, {"_id": 0, "upload_id": 1, "recording_id": 1}).to_list(100)
    upload_ids = [item["upload_id"] for item in uploads]
    stage_file_ids = [item["_id"] async for item in server.db["board_recording_staging.files"].find({"metadata.upload_id": {"$in": upload_ids}}, {"_id": 1})]
    await server.db["board_recording_staging.chunks"].delete_many({"files_id": {"$in": stage_file_ids}}); await server.db["board_recording_staging.files"].delete_many({"_id": {"$in": stage_file_ids}})
    recording_ids = [item["recording_id"] for item in uploads if item.get("recording_id")]
    await server.db["board_recordings.chunks"].delete_many({"files_id": {"$in": recording_ids}}); await server.db["board_recordings.files"].delete_many({"_id": {"$in": recording_ids}})
    await server.db.board_recording_uploads.delete_many({"upload_id": {"$in": upload_ids}}); await server.db.board_meetings.delete_many({"meeting_id": {"$in": meeting_ids}})
    await server.db.person_photo_chunks.delete_many({"upload_id": {"$regex": "^stabilization-upload-"}}); await server.db.person_photo_uploads.delete_many({"_id": {"$regex": "^stabilization-upload-"}})
    await server.db.person_contacts.delete_many({"person_id": {"$in": person_ids}}); await server.db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in person_ids]}}); await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})
    set_geocoding_provider_for_tests(None)


@pytest.mark.asyncio
async def test_abandoned_photo_uploads_remove_expired_and_orphan_chunks_only():
    await cleanup(); now = datetime.now(timezone.utc); expired, active, orphan = "stabilization-upload-expired", "stabilization-upload-active", "stabilization-upload-orphan"
    await server.db.person_photo_uploads.insert_many([
        {"_id": expired, "person_id": "qa", "created_at": now - timedelta(hours=2), "expires_at": now - timedelta(hours=1)},
        {"_id": active, "person_id": "qa", "created_at": now, "expires_at": now + timedelta(hours=1)},
    ])
    await server.db.person_photo_chunks.insert_many([
        {"_id": f"{expired}:0", "upload_id": expired, "index": 0, "data": Binary(b"old")},
        {"_id": f"{active}:0", "upload_id": active, "index": 0, "data": Binary(b"active"), "expires_at": now + timedelta(hours=1)},
        {"_id": f"{orphan}:0", "upload_id": orphan, "index": 0, "data": Binary(b"orphan")},
    ])
    try:
        result = await cleanup_abandoned_photo_uploads()
        assert result["expired_uploads"] == 1 and result["deleted_chunks"] == 2
        assert await server.db.person_photo_uploads.count_documents({"_id": active}) == 1
        assert await server.db.person_photo_chunks.count_documents({"upload_id": active}) == 1
    finally: await cleanup()


@pytest.mark.asyncio
async def test_board_recording_double_finalize_creates_one_file(monkeypatch):
    await cleanup(); user_id, _, email = await make_user("pastor"); meeting_id = str(uuid.uuid4()); now = datetime.now(timezone.utc)
    await server.db.board_meetings.insert_one({"_id": meeting_id, "meeting_id": meeting_id, "title": "STABILIZATION UPLOAD BOARD", "status": "open", "recording_notice_confirmed": True, "created_at": now})
    async def no_transcription(*args, **kwargs): return None
    monkeypatch.setattr(board_recording_routes, "transcribe_recording", no_transcription)
    client, headers = await login(email)
    try:
        started = await client.post("/api/board/recordings/uploads", json={"meeting_id": meeting_id, "content_type": "audio/webm"}, headers=headers)
        assert started.status_code == 201, started.text
        upload_id = started.json()["upload_id"]
        chunk = await client.put(f"/api/board/recordings/uploads/{upload_id}/chunks/0", content=b"test-audio-content", headers={**headers, "Content-Type": "application/octet-stream"})
        assert chunk.status_code == 200, chunk.text
        first, second = await asyncio.gather(*[client.post(f"/api/board/recordings/uploads/{upload_id}/complete", json={"duration_seconds": 5}, headers=headers) for _ in range(2)])
        assert sorted([first.status_code, second.status_code]) in ([200, 200], [200, 409])
        upload = await server.db.board_recording_uploads.find_one({"upload_id": upload_id}, {"_id": 0})
        assert upload["status"] == "complete"
        assert await server.db["board_recordings.files"].count_documents({"metadata.upload_id": upload_id}) == 1
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_board_recording_requires_open_meeting_and_abort_cleans_staging():
    await cleanup(); user_id, _, email = await make_user("pastor"); meeting_id = str(uuid.uuid4()); now = datetime.now(timezone.utc)
    await server.db.board_meetings.insert_one({"_id": meeting_id, "meeting_id": meeting_id, "title": "STABILIZATION UPLOAD BOARD ABORT", "status": "scheduled", "recording_notice_confirmed": True, "created_at": now})
    client, headers = await login(email)
    try:
        blocked = await client.post("/api/board/recordings/uploads", json={"meeting_id": meeting_id, "content_type": "audio/webm"}, headers=headers)
        assert blocked.status_code == 409
        await server.db.board_meetings.update_one({"meeting_id": meeting_id}, {"$set": {"status": "open"}})
        started = await client.post("/api/board/recordings/uploads", json={"meeting_id": meeting_id, "content_type": "audio/webm"}, headers=headers)
        assert started.status_code == 201, started.text
        upload_id = started.json()["upload_id"]
        chunk = await client.put(f"/api/board/recordings/uploads/{upload_id}/chunks/0", content=b"live-audio", headers={**headers, "Content-Type": "application/octet-stream"})
        assert chunk.status_code == 200
        aborted = await client.delete(f"/api/board/recordings/uploads/{upload_id}", headers=headers)
        assert aborted.status_code == 200 and aborted.json()["status"] == "aborted"
        upload = await server.db.board_recording_uploads.find_one({"upload_id": upload_id}, {"_id": 0})
        assert upload["status"] == "aborted"
        assert await server.db["board_recording_staging.files"].count_documents({"metadata.upload_id": upload_id}) == 0
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_evangelism_minimum_privilege_preserves_collaboration():
    await cleanup(); set_geocoding_provider_for_tests(StableGeocoder())
    creator_id, _, creator_email = await make_user(); viewer_id, _, viewer_email = await make_user(); _, _, pastor_email = await make_user("pastor")
    creator, creator_headers = await login(creator_email); viewer, viewer_headers = await login(viewer_email); pastor, pastor_headers = await login(pastor_email)
    try:
        denied_notes = await creator.post("/api/geo/evangelism", json={"house_number": "901", "street_name": "Privacy Rd", "pastoral_notes": "Sensible"}, headers=creator_headers)
        assert denied_notes.status_code == 403
        created = await creator.post("/api/geo/evangelism", json={"house_number": "901", "street_name": "Privacy Rd", "notes": "Tocar después de las seis"}, headers=creator_headers)
        assert created.status_code == 201, created.text
        target_id = created.json()["target_id"]; assert created.json()["house_number"] == "901" and created.json()["can_view_precise"] is True
        pastoral_update = await pastor.patch(f"/api/geo/evangelism/{target_id}", json={"pastoral_notes": "Nota pastoral restringida"}, headers=pastor_headers)
        assert pastoral_update.status_code == 200 and pastoral_update.json()["pastoral_notes"] == "Nota pastoral restringida"
        roster = await viewer.get("/api/geo/evangelism/assignees", headers=viewer_headers)
        assert roster.status_code == 200 and all(set(item) == {"user_id", "name"} for item in roster.json()["items"])
        listing = await viewer.get("/api/geo/evangelism", headers=viewer_headers)
        safe = next(item for item in listing.json()["items"] if item["target_id"] == target_id)
        assert safe["house_number"] is None and safe["latitude"] is None and "901" not in safe["full_address"]
        assert safe["pastoral_notes"] is None and safe["notes"] == "Tocar después de las seis"
        assert not any(item["properties"]["target_id"] == target_id for item in listing.json()["features"])
        assigned = await viewer.patch(f"/api/geo/evangelism/{target_id}", json={"assigned_to_user_id": viewer_id, "status": "assigned"}, headers=viewer_headers)
        assert assigned.status_code == 200 and assigned.json()["house_number"] == "901" and assigned.json()["latitude"] is not None
        forbidden_pastoral = await viewer.patch(f"/api/geo/evangelism/{target_id}", json={"pastoral_notes": "Intento"}, headers=viewer_headers)
        assert forbidden_pastoral.status_code == 403
        refreshed = await viewer.get("/api/geo/evangelism", headers=viewer_headers)
        precise = next(item for item in refreshed.json()["items"] if item["target_id"] == target_id)
        assert precise["house_number"] == "901" and precise["pastoral_notes"] is None
    finally:
        await creator.aclose(); await viewer.aclose(); await pastor.aclose(); await cleanup()