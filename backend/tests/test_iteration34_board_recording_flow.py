"""Iteración 34: contratos críticos de reunión/grabación de Junta (start/upload/abort/download)."""

import os
import uuid
import hashlib
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required")
BASE_URL = BASE_URL.rstrip("/")

BACKEND_ENV = dotenv_values("/app/backend/.env")
MONGO_URL = BACKEND_ENV.get("MONGO_URL")
DB_NAME = BACKEND_ENV.get("DB_NAME")
if not MONGO_URL or not DB_NAME:
    raise RuntimeError("MONGO_URL and DB_NAME are required")

DB = MongoClient(MONGO_URL)[DB_NAME]

LOGIN_CANDIDATES = [
    ("qa.board.recorder.pastor@example.com", "BoardRecorderQA2026!"),
    ("coreqa.pastor@example.com", "CoreQA2026!Pastor"),
]


def _auth_session():
    for email, password in LOGIN_CANDIDATES:
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=25,
        )
        if response.status_code == 200 and response.json().get("token"):
            token = response.json()["token"]
            session.headers.update({"Authorization": f"Bearer {token}"})
            return session, email
    pytest.skip("No se pudo autenticar con credenciales QA disponibles")


@pytest.fixture(scope="module")
def api_client():
    return _auth_session()


@pytest.fixture(scope="module")
def synthetic_open_meeting(api_client):
    # módulo/feature: upload en vivo (meeting open + notice confirmed)
    _session, auth_email = api_client
    meeting_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    DB.board_meetings.insert_one(
        {
            "_id": meeting_id,
            "meeting_id": meeting_id,
            "title": f"TEST_ITER34_OPEN_{meeting_id[:8]}",
            "board_id": "board.main",
            "status": "open",
            "recording_notice_confirmed": True,
            "started_at": now,
            "created_by_user_id": auth_email,
            "created_at": now,
            "updated_at": now,
        }
    )
    yield meeting_id
    DB.board_meetings.delete_one({"meeting_id": meeting_id})


@pytest.fixture(scope="module")
def synthetic_closed_meeting(api_client):
    # módulo/feature: reunión cerrada no puede reabrirse
    _session, auth_email = api_client
    meeting_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    DB.board_meetings.insert_one(
        {
            "_id": meeting_id,
            "meeting_id": meeting_id,
            "title": f"TEST_ITER34_CLOSED_{meeting_id[:8]}",
            "board_id": "board.main",
            "status": "closed",
            "recording_notice_confirmed": True,
            "started_at": now,
            "ended_at": now,
            "created_by_user_id": auth_email,
            "created_at": now,
            "updated_at": now,
        }
    )
    yield meeting_id
    DB.board_meetings.delete_one({"meeting_id": meeting_id})


def test_meeting_start_is_idempotent_for_open_meeting(api_client, synthetic_open_meeting):
    # módulo/feature: start idempotente
    client, _ = api_client
    payload = {"recording_notice_confirmed": True}
    first = client.post(f"{BASE_URL}/api/board/meetings/{synthetic_open_meeting}/start", json=payload, timeout=30)
    second = client.post(f"{BASE_URL}/api/board/meetings/{synthetic_open_meeting}/start", json=payload, timeout=30)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json().get("started_at") == second.json().get("started_at")
    assert second.json().get("status") == "open"


def test_closed_meeting_cannot_reopen(api_client, synthetic_closed_meeting):
    # módulo/feature: reunión cerrada no reabre
    client, _ = api_client
    response = client.post(
        f"{BASE_URL}/api/board/meetings/{synthetic_closed_meeting}/start",
        json={"recording_notice_confirmed": True},
        timeout=30,
    )
    assert response.status_code == 409
    assert "cerrada" in str(response.json().get("detail", "")).lower()


def test_live_chunk_upload_and_complete_persists_sha_and_bytes(api_client, synthetic_open_meeting):
    # módulo/feature: persistencia por bloques + completo + hash
    client, _ = api_client

    start = client.post(
        f"{BASE_URL}/api/board/recordings/uploads",
        json={"meeting_id": synthetic_open_meeting, "content_type": "audio/webm"},
        timeout=30,
    )
    assert start.status_code == 201
    upload_id = start.json()["upload_id"]

    c1 = b"A" * 2048
    c2 = b"B" * 4096
    expected_sha = hashlib.sha256(c1 + c2).hexdigest()

    up1 = client.put(
        f"{BASE_URL}/api/board/recordings/uploads/{upload_id}/chunks/0",
        data=c1,
        headers={"Content-Type": "application/octet-stream", "Authorization": client.headers["Authorization"]},
        timeout=30,
    )
    up2 = client.put(
        f"{BASE_URL}/api/board/recordings/uploads/{upload_id}/chunks/1",
        data=c2,
        headers={"Content-Type": "application/octet-stream", "Authorization": client.headers["Authorization"]},
        timeout=30,
    )
    assert up1.status_code == 200 and up2.status_code == 200
    assert up2.json().get("total_bytes") == len(c1) + len(c2)

    completed = client.post(
        f"{BASE_URL}/api/board/recordings/uploads/{upload_id}/complete",
        json={"duration_seconds": 6},
        timeout=40,
    )
    assert completed.status_code == 200
    result = completed.json()
    assert result.get("bytes") == len(c1) + len(c2)
    assert result.get("sha256") == expected_sha
    assert result.get("status") == "ready"
    assert result.get("transcription_status") in {"queued", "blocked"}

    listed = client.get(f"{BASE_URL}/api/board/meetings/{synthetic_open_meeting}/recordings", timeout=30)
    assert listed.status_code == 200
    items = listed.json().get("items", [])
    hit = next((item for item in items if item.get("recording_id") == result.get("recording_id")), None)
    assert hit is not None
    assert hit.get("sha256") == expected_sha
    assert int(hit.get("bytes", 0)) == len(c1) + len(c2)


def test_download_recording_returns_authenticated_blob_and_sha_header(api_client, synthetic_open_meeting):
    # módulo/feature: escuchar/descargar blob autenticado
    client, _ = api_client
    listed = client.get(f"{BASE_URL}/api/board/meetings/{synthetic_open_meeting}/recordings", timeout=30)
    assert listed.status_code == 200
    items = listed.json().get("items", [])
    if not items:
        pytest.skip("No hay recordings para validar descarga")
    rec = items[0]
    response = client.get(f"{BASE_URL}/api/board/recordings/{rec['recording_id']}", timeout=40)
    assert response.status_code == 200
    assert response.headers.get("X-Content-SHA256") == rec.get("sha256")
    assert len(response.content) > 0


def test_abort_upload_marks_aborted_and_removes_staged_chunks(api_client, synthetic_open_meeting):
    # módulo/feature: cancelación limpia staging y deja auditoría
    client, auth_email = api_client
    started = client.post(
        f"{BASE_URL}/api/board/recordings/uploads",
        json={"meeting_id": synthetic_open_meeting, "content_type": "audio/webm"},
        timeout=30,
    )
    assert started.status_code == 201
    upload_id = started.json()["upload_id"]

    chunk = client.put(
        f"{BASE_URL}/api/board/recordings/uploads/{upload_id}/chunks/0",
        data=b"cancel-me",
        headers={"Content-Type": "application/octet-stream", "Authorization": client.headers["Authorization"]},
        timeout=30,
    )
    assert chunk.status_code == 200

    cancelled = client.delete(f"{BASE_URL}/api/board/recordings/uploads/{upload_id}", timeout=30)
    assert cancelled.status_code == 200
    assert cancelled.json().get("status") == "aborted"

    staged_count = DB["board_recording_staging.files"].count_documents({"metadata.upload_id": upload_id})
    assert staged_count == 0

    upload_doc = DB.board_recording_uploads.find_one({"upload_id": upload_id}, {"_id": 0, "status": 1, "meeting_id": 1})
    assert upload_doc and upload_doc.get("status") == "aborted"

    actor = DB.users.find_one({"email": auth_email}, {"_id": 1})
    actor_id = str(actor["_id"]) if actor else None
    audit = DB.board_audit_events.find_one(
        {
            "event_type": "recording_upload_aborted",
            "entity_type": "board_meeting",
            "entity_id": synthetic_open_meeting,
            "actor_user_id": actor_id,
            "changes.upload_id": upload_id,
        }
    )
    assert audit is not None