"""Iteración 35: contrato API de health + transcript en vivo de Junta."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required")
BASE_URL = BASE_URL.rstrip("/")

LOGIN_EMAIL = "coreqa.pastor@example.com"
LOGIN_PASSWORD = "CoreQA2026!Pastor"
BACKEND_ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]


@pytest.fixture(scope="module")
def api_client():
    """Módulo/feature: autenticación mínima para consultas de Junta."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        timeout=25,
    )
    if response.status_code != 200 or not response.json().get("token"):
        pytest.skip("Credenciales QA no disponibles para validación pública de transcript")
    session.headers.update({"Authorization": f"Bearer {response.json()['token']}"})
    return session


@pytest.fixture(scope="module")
def transcript_fixture(api_client):
    meeting_id = f"test-iteration35-{uuid4()}"
    version_id = str(uuid4())
    upload_id = str(uuid4())
    now = datetime.now(timezone.utc)
    DB.board_meetings.insert_one({"_id": meeting_id, "meeting_id": meeting_id, "board_id": "board.main", "title": "TEST ITERATION35 TRANSCRIPT", "status": "open", "created_at": now})
    DB.board_transcript_versions.insert_one({"_id": version_id, "transcript_version_id": version_id, "meeting_id": meeting_id, "source_upload_id": upload_id, "version": 1, "kind": "live_provisional", "immutable": False, "status": "streaming", "full_text": "Buenos días. Revisemos los acuerdos.", "created_at": now})
    DB.board_transcript_segments.insert_many([
        {"_id": str(uuid4()), "segment_id": str(uuid4()), "meeting_id": meeting_id, "transcript_version_id": version_id, "order": 0, "speaker_label": "SPEAKER_00", "start_seconds": 0, "end_seconds": 2, "text": "Buenos días.", "created_at": now},
        {"_id": str(uuid4()), "segment_id": str(uuid4()), "meeting_id": meeting_id, "transcript_version_id": version_id, "order": 1, "speaker_label": "SPEAKER_01", "start_seconds": 3, "end_seconds": 6, "text": "Revisemos los acuerdos.", "created_at": now},
    ])
    DB.board_recording_uploads.insert_one({"_id": upload_id, "upload_id": upload_id, "meeting_id": meeting_id, "status": "uploading", "elapsed_seconds": 10, "live_transcription_status": "streaming", "created_at": now})
    yield meeting_id
    DB.board_transcript_segments.delete_many({"transcript_version_id": version_id})
    DB.board_transcript_versions.delete_many({"meeting_id": meeting_id})
    DB.board_recording_uploads.delete_many({"meeting_id": meeting_id})
    DB.board_meetings.delete_many({"meeting_id": meeting_id})


def test_health_endpoint_returns_ok_payload():
    """Módulo/feature: backend disponible y saludable."""
    response = requests.get(f"{BASE_URL}/api/health", timeout=20)
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"
    assert isinstance(payload.get("service"), str) and payload.get("service")


def test_board_transcript_contract_live_fixture(api_client, transcript_fixture):
    """Módulo/feature: transcript ordenado con full_text/version/live para Audio-Minuta."""
    response = api_client.get(f"{BASE_URL}/api/board/meetings/{transcript_fixture}/transcript", timeout=30)
    assert response.status_code == 200
    payload = response.json()

    assert "segments" in payload and isinstance(payload["segments"], list)
    assert "live" in payload and isinstance(payload["live"], dict)
    assert payload.get("version") is not None
    assert isinstance(payload.get("full_text", ""), str)

    segments = payload["segments"]
    assert len(segments) >= 2

    starts = [float(item.get("start_seconds", 0)) for item in segments]
    assert starts == sorted(starts)
    orders = [int(item.get("order", idx)) for idx, item in enumerate(segments)]
    assert orders == sorted(orders)

    speakers = {item.get("speaker_label") for item in segments if item.get("speaker_label")}
    assert "SPEAKER_00" in speakers and "SPEAKER_01" in speakers

    live = payload["live"]
    assert isinstance(live.get("status"), str) and live.get("status")
    assert "elapsed_seconds" in live
