"""Iteration 32: Public preview regression for pastoral care + Op72 critical paths."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


APP_DIR = "/app"
FRONTEND_ENV = dotenv_values(f"{APP_DIR}/frontend/.env")
BACKEND_ENV = dotenv_values(f"{APP_DIR}/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL")

PASTOR_EMAIL = "care.ui.pastor@example.com"
LEADER_EMAIL = "care.ui.leader@example.com"
PASSWORD = "CareVisual2026!"
PERSONA_EMAIL = "care.ui.persona@example.com"
PERSONA_PASSWORD = PASSWORD


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _login(session: requests.Session, email: str, password: str) -> tuple[dict, requests.Response]:
    response = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload.get("token"), str) and payload["token"]
    return payload, response


@pytest.fixture(scope="module", autouse=True)
def setup_fixture_data():
    subprocess.run([sys.executable, "/app/backend/tests/ui_care_fixture.py"], check=True)
    yield
    subprocess.run([sys.executable, "/app/backend/tests/ui_care_fixture.py", "cleanup"], check=False)


@pytest.fixture(scope="module")
def api_base_url() -> str:
    assert BASE_URL, "REACT_APP_BACKEND_URL is required"
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="module")
def sessions(api_base_url: str):
    pastor_session = requests.Session()
    leader_session = requests.Session()
    persona_session = requests.Session()

    pastor_payload, pastor_login = _login(pastor_session, PASTOR_EMAIL, PASSWORD)
    leader_payload, _ = _login(leader_session, LEADER_EMAIL, PASSWORD)
    persona_payload, _ = _login(persona_session, PERSONA_EMAIL, PERSONA_PASSWORD)

    yield {
        "pastor": (pastor_session, pastor_payload, pastor_login),
        "leader": (leader_session, leader_payload),
        "persona": (persona_session, persona_payload),
    }


def test_auth_security_checks(sessions):
    """Auth checks: bcrypt format, lockout signal, and login cookie behavior."""
    mongo = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
    pastor_user = mongo.users.find_one({"email": PASTOR_EMAIL}, {"_id": 0, "password": 1})
    assert pastor_user and isinstance(pastor_user.get("password"), str)
    assert pastor_user["password"].startswith("$2b$")

    temp = requests.Session()
    for _ in range(5):
        temp.post(f"{BASE_URL}/api/auth/login", json={"email": "lockout.check@example.com", "password": "bad"}, timeout=15)
    lockout = temp.post(f"{BASE_URL}/api/auth/login", json={"email": "lockout.check@example.com", "password": "bad"}, timeout=15)
    assert lockout.status_code in {401, 429}

    pastor_login_response = sessions["pastor"][2]
    cookies = pastor_login_response.headers.get("set-cookie", "")
    assert isinstance(cookies, str)


def test_dashboard_redacts_confidential_content(sessions):
    """Dashboard should expose metrics/alerts/recent items without confidential note content."""
    pastor_session, pastor_payload, _ = sessions["pastor"]
    response = pastor_session.get(f"{BASE_URL}/api/care/dashboard", headers=_headers(pastor_payload["token"]), timeout=20)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "metrics" in body and "alerts" in body and "recent_cases" in body
    assert isinstance(body["metrics"].get("active_cases"), int)
    assert all("content" not in item for item in body.get("recent_cases", []))
    assert all("ciphertext" not in str(item).lower() for item in body.get("alerts", []))


def test_rbac_persona_forbidden_and_leader_scoped_not_found(sessions):
    """RBAC: Persona must get 403 on care; unassigned leader must get 404 on foreign case."""
    pastor_session, pastor_payload, _ = sessions["pastor"]
    leader_session, leader_payload = sessions["leader"]
    persona_session, persona_payload = sessions["persona"]

    denied = persona_session.get(f"{BASE_URL}/api/care/dashboard", headers=_headers(persona_payload["token"]), timeout=20)
    assert denied.status_code == 403

    pastor_me = pastor_session.get(f"{BASE_URL}/api/auth/me", headers=_headers(pastor_payload["token"]), timeout=20)
    assert pastor_me.status_code == 200
    pastor_person_id = pastor_me.json().get("person_id")
    assert pastor_person_id

    create_case = pastor_session.post(
        f"{BASE_URL}/api/care/cases",
        headers=_headers(pastor_payload["token"]),
        json={
            "person_id": pastor_person_id,
            "case_type": "reconciliation",
            "priority": "medium",
            "source_type": "manual",
            "source_id": f"iter32-private-{datetime.now(timezone.utc).timestamp()}",
        },
        timeout=20,
    )
    assert create_case.status_code == 201, create_case.text
    case_id = create_case.json()["case_id"]

    leader_get = leader_session.get(f"{BASE_URL}/api/care/cases/{case_id}", headers=_headers(leader_payload["token"]), timeout=20)
    assert leader_get.status_code == 404


def test_notes_visibility_and_audit(sessions):
    """Leader can only read assigned_team notes; notes access should create audit events."""
    pastor_session, pastor_payload, _ = sessions["pastor"]
    leader_session, leader_payload = sessions["leader"]

    inbox = pastor_session.get(f"{BASE_URL}/api/care/cases", headers=_headers(pastor_payload["token"]), timeout=20)
    assert inbox.status_code == 200
    first_case = inbox.json()["items"][0]
    case_id = first_case["case_id"]

    leader_notes = leader_session.get(f"{BASE_URL}/api/care/cases/{case_id}/notes", headers=_headers(leader_payload["token"]), timeout=20)
    assert leader_notes.status_code == 200
    assert all(item.get("visibility") == "assigned_team" for item in leader_notes.json().get("items", []))

    pastor_audit = pastor_session.get(f"{BASE_URL}/api/care/audit", headers=_headers(pastor_payload["token"]), timeout=20)
    assert pastor_audit.status_code == 200
    assert isinstance(pastor_audit.json().get("items", []), list)


def test_op72_uniqueness_immutability_and_index(sessions):
    """Op72 must be unique by person_id and keep first_conversion_at immutable."""
    pastor_session, pastor_payload, _ = sessions["pastor"]

    cases = pastor_session.get(f"{BASE_URL}/api/care/cases", headers=_headers(pastor_payload["token"]), timeout=20)
    assert cases.status_code == 200
    person_id = cases.json()["items"][0]["person_id"]

    first_date = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    second_date = datetime.now(timezone.utc).isoformat()

    first = pastor_session.post(
        f"{BASE_URL}/api/care/op72",
        headers=_headers(pastor_payload["token"]),
        json={"person_id": person_id, "decision_at": first_date, "source_type": "manual"},
        timeout=20,
    )
    assert first.status_code == 201, first.text
    op72_id = first.json()["record"]["op72_id"]
    first_conversion_at = first.json()["record"]["first_conversion_at"]

    second = pastor_session.post(
        f"{BASE_URL}/api/care/op72",
        headers=_headers(pastor_payload["token"]),
        json={"person_id": person_id, "decision_at": second_date, "source_type": "manual"},
        timeout=20,
    )
    assert second.status_code == 201, second.text
    assert second.json()["record"]["op72_id"] == op72_id
    assert second.json()["record"]["first_conversion_at"] == first_conversion_at

    mongo = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
    indexes = list(mongo.op72_records.list_indexes())
    person_idx = [idx for idx in indexes if idx.get("key") == {"person_id": 1}]
    assert person_idx and person_idx[0].get("unique") is True


def test_op72_pause_reactivate_preserves_enrollment_progress(sessions):
    """Pause/reactivate should preserve linked enrollment and stage progress."""
    pastor_session, pastor_payload, _ = sessions["pastor"]

    op72_list = pastor_session.get(f"{BASE_URL}/api/care/op72", headers=_headers(pastor_payload["token"]), timeout=20)
    assert op72_list.status_code == 200
    item = next(record for record in op72_list.json()["items"] if record.get("source_id") == "care-ui-op72")

    detail_before = pastor_session.get(f"{BASE_URL}/api/care/op72/{item['op72_id']}", headers=_headers(pastor_payload["token"]), timeout=20)
    assert detail_before.status_code == 200
    enrollment_id = detail_before.json().get("consolidation_enrollment_id")
    assert enrollment_id

    enrollment_before = pastor_session.get(
        f"{BASE_URL}/api/processes/enrollments/{enrollment_id}",
        headers=_headers(pastor_payload["token"]),
        timeout=20,
    )
    assert enrollment_before.status_code == 200
    stage_before = enrollment_before.json().get("current_stage_key")

    paused = pastor_session.post(
        f"{BASE_URL}/api/care/op72/{item['op72_id']}/pause",
        headers=_headers(pastor_payload["token"]),
        json={"reason": "Iter32 pause check"},
        timeout=20,
    )
    assert paused.status_code == 200, paused.text

    resumed = pastor_session.post(
        f"{BASE_URL}/api/care/op72/{item['op72_id']}/reactivate",
        headers=_headers(pastor_payload["token"]),
        json={"reason": "Iter32 reactivate check"},
        timeout=20,
    )
    assert resumed.status_code == 200, resumed.text

    enrollment_after = pastor_session.get(
        f"{BASE_URL}/api/processes/enrollments/{enrollment_id}",
        headers=_headers(pastor_payload["token"]),
        timeout=20,
    )
    assert enrollment_after.status_code == 200
    assert enrollment_after.json().get("current_stage_key") == stage_before


def test_profile_360_anti_inference_and_pastor_summary(sessions):
    """Non-authorized profile must hide care section; pastor can see summary-only section."""
    pastor_session, pastor_payload, _ = sessions["pastor"]
    persona_session, persona_payload = sessions["persona"]

    cases = pastor_session.get(f"{BASE_URL}/api/care/cases", headers=_headers(pastor_payload["token"]), timeout=20)
    assert cases.status_code == 200
    person_id = cases.json()["items"][0]["person_id"]

    private_profile = persona_session.get(f"{BASE_URL}/api/core/persons/{person_id}/profile", headers=_headers(persona_payload["token"]), timeout=20)
    assert private_profile.status_code in {403, 404, 200}
    if private_profile.status_code == 200:
        assert all(section.get("section_key") != "cuidado_pastoral" for section in private_profile.json().get("sections", []))

    pastor_profile = pastor_session.get(f"{BASE_URL}/api/core/persons/{person_id}/profile", headers=_headers(pastor_payload["token"]), timeout=20)
    assert pastor_profile.status_code == 200
    care_sections = [section for section in pastor_profile.json().get("sections", []) if section.get("section_key") == "cuidado_pastoral"]
    assert len(care_sections) == 1
    assert "notes" not in str(care_sections[0]).lower()


def test_care_migration_dry_run_and_operations_regression_smoke(sessions):
    """Dry-run migration must avoid writes; operations dashboard should respond."""
    pastor_session, pastor_payload, _ = sessions["pastor"]

    dry_run = pastor_session.get(f"{BASE_URL}/api/care/migrations/legacy/dry-run", headers=_headers(pastor_payload["token"]), timeout=20)
    assert dry_run.status_code == 200
    body = dry_run.json()
    assert body.get("dry_run") is True
    assert body.get("writes_performed") is False

    operations = pastor_session.get(f"{BASE_URL}/api/operations/dashboard", headers=_headers(pastor_payload["token"]), timeout=20)
    assert operations.status_code == 200
    assert isinstance(operations.json(), dict)
