"""Iteration 12: auth hierarchy + junta recording regression checks on public URL."""
import os

import pytest
import requests
from dotenv import dotenv_values


# Module: environment/bootstrap for public endpoint execution
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required")
BASE_URL = BASE_URL.rstrip("/")

MEETING_ID = "1640ed37-2810-484b-a5b5-3582e553ba1b"

PASTOR_EMAIL = "coreqa.pastor@example.com"
PASTOR_PASSWORD = "CoreQA2026!Pastor"
COORD_EMAIL = "coord.uxfa9a81@example.com"
COORD_PASSWORD = "NuevaClave2026!"
LEADER_TEMP_EMAIL = "lider.uxfa9a81@example.com"
LEADER_TEMP_PASSWORD = "Temporal2026!"


def api(path: str) -> str:
    return f"{BASE_URL}{path}"


def login(email: str, password: str) -> requests.Response:
    return requests.post(
        api("/api/auth/login"),
        json={"email": email, "password": password},
        timeout=25,
    )


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def pastor_session():
    response = login(PASTOR_EMAIL, PASTOR_PASSWORD)
    if response.status_code != 200:
        pytest.skip(f"Pastor login failed: {response.status_code} {response.text}")
    payload = response.json()
    return {"token": payload["token"], "user": payload["user"]}


@pytest.fixture(scope="module")
def coordinator_session():
    response = login(COORD_EMAIL, COORD_PASSWORD)
    if response.status_code != 200:
        pytest.skip(f"Coordinator login failed: {response.status_code} {response.text}")
    payload = response.json()
    return {"token": payload["token"], "user": payload["user"]}


@pytest.fixture(scope="module")
def leader_temp_session():
    response = login(LEADER_TEMP_EMAIL, LEADER_TEMP_PASSWORD)
    if response.status_code != 200:
        pytest.skip(f"Temp leader login failed: {response.status_code} {response.text}")
    payload = response.json()
    return {"token": payload["token"], "user": payload["user"]}


# Module: auth hierarchy + forced password-change flags
def test_pastor_login_and_me_contract(pastor_session):
    me = requests.get(api("/api/auth/me"), headers=auth(pastor_session["token"]), timeout=20)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == PASTOR_EMAIL
    assert body["rol"] == "pastor"
    assert body.get("must_change_password") is False


def test_coordinator_can_list_governance_users_and_see_temp_leader(coordinator_session):
    users_response = requests.get(
        api("/api/core/governance/users"),
        headers=auth(coordinator_session["token"]),
        timeout=25,
    )
    assert users_response.status_code == 200, users_response.text
    items = users_response.json().get("items", [])
    assert isinstance(items, list)
    assert any(item.get("email") == LEADER_TEMP_EMAIL for item in items)


def test_temp_leader_login_requires_password_change_flag(leader_temp_session):
    assert leader_temp_session["user"].get("must_change_password") is True


# Module: RBAC protections for governance creation
def test_coordinator_gets_403_when_creating_pastor_or_coordinator(coordinator_session):
    headers = auth(coordinator_session["token"])
    shared = {
        "person_id": "507f1f77bcf86cd799439011",
        "email": "qa.blocked.levels@example.com",
        "temporary_password": "TemporalBloqueada2026!",
    }
    create_coord = requests.post(
        api("/api/core/governance/users"),
        headers=headers,
        json={**shared, "access_level": "coordinador_general"},
        timeout=25,
    )
    create_pastor = requests.post(
        api("/api/core/governance/users"),
        headers=headers,
        json={**shared, "access_level": "pastor"},
        timeout=25,
    )
    assert create_coord.status_code == 403, create_coord.text
    assert create_pastor.status_code == 403, create_pastor.text


def test_normal_leader_gets_403_in_governance_users(leader_temp_session):
    response = requests.get(
        api("/api/core/governance/users"),
        headers=auth(leader_temp_session["token"]),
        timeout=20,
    )
    assert response.status_code == 403, response.text


# Module: Junta fixture + recording backend contract checks
def test_junta_fixture_meeting_loads_for_pastor(pastor_session):
    detail = requests.get(
        api(f"/api/board/meetings/{MEETING_ID}"),
        headers=auth(pastor_session["token"]),
        timeout=30,
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body.get("meeting_id") == MEETING_ID
    assert body.get("status") in {"scheduled", "open", "closed"}


def test_recording_legacy_contract_initiate_content_complete_exists(pastor_session):
    """Compatibility contract used by frontend BoardRecorder (initiate/content/complete)."""
    init = requests.post(
        api(f"/api/board/meetings/{MEETING_ID}/recordings/initiate"),
        headers=auth(pastor_session["token"]),
        json={
            "content_type": "audio/webm",
            "recording_notice_acknowledged": True,
            "external_processing_acknowledged": True,
        },
        timeout=30,
    )
    assert init.status_code in (200, 201), init.text
    upload_id = init.json().get("upload_id")
    assert isinstance(upload_id, str) and len(upload_id) > 8

    content = requests.put(
        api(f"/api/board/recordings/{upload_id}/content"),
        headers={**auth(pastor_session["token"]), "Content-Type": "audio/webm"},
        data=b"RIFF\x01\x00\x00\x00WEBM",
        timeout=30,
    )
    assert content.status_code == 200, content.text

    complete = requests.post(
        api(f"/api/board/recordings/{upload_id}/complete"),
        headers=auth(pastor_session["token"]),
        json={},
        timeout=40,
    )
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert isinstance(body.get("recording_id"), str)


def test_recording_uploads_api_still_operational(pastor_session):
    upload = requests.post(
        api("/api/board/recordings/uploads"),
        headers=auth(pastor_session["token"]),
        json={"meeting_id": MEETING_ID, "content_type": "audio/webm"},
        timeout=30,
    )
    assert upload.status_code == 201, upload.text
    upload_body = upload.json()
    upload_id = upload_body.get("upload_id")
    assert isinstance(upload_id, str)
    assert upload_body.get("next_seq") == 0

    chunk = requests.put(
        api(f"/api/board/recordings/uploads/{upload_id}/chunks/0"),
        headers={**auth(pastor_session["token"]), "Content-Type": "application/octet-stream"},
        data=b"WEBM_FAKE_AUDIO_QA",
        timeout=30,
    )
    assert chunk.status_code == 200, chunk.text
    chunk_body = chunk.json()
    assert chunk_body.get("seq") == 0
    assert chunk_body.get("bytes", 0) > 0

    complete = requests.post(
        api(f"/api/board/recordings/uploads/{upload_id}/complete"),
        headers=auth(pastor_session["token"]),
        json={"duration_seconds": 0.1},
        timeout=60,
    )
    assert complete.status_code == 200, complete.text
    complete_body = complete.json()
    assert complete_body.get("status") == "ready"
    assert isinstance(complete_body.get("recording_id"), str)
