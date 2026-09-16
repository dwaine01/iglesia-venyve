"""Public preview regression for Mega-Bloque B process engine + key auth hardening checks."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Module: public URL + fixed QA credentials loaded from memory/test_credentials.md
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required for public endpoint tests")
BASE_URL = BASE_URL.rstrip("/")

PASTOR_EMAIL = "coreqa.pastor@example.com"
PASTOR_PASSWORD = "CoreQA2026!Pastor"
PERSONA_EMAIL = "coreqa.member@example.com"
PERSONA_PASSWORD = "CoreQA2026!Member"
LEADER_EMAIL = "access01.ui@example.com"
LEADER_PASSWORD = "Access01UiTest!"

BACKEND_ENV = dotenv_values("/app/backend/.env")
MONGO_URL = (os.environ.get("MONGO_URL") or BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (os.environ.get("DB_NAME") or BACKEND_ENV.get("DB_NAME") or "").strip('"')


def api_url(path: str) -> str:
    return f"{BASE_URL}{path}"


def login(email: str, password: str) -> requests.Response:
    return requests.post(
        api_url("/api/auth/login"),
        json={"email": email, "password": password},
        timeout=30,
    )


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def pastor_session():
    response = login(PASTOR_EMAIL, PASTOR_PASSWORD)
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"token": payload["token"], "user": payload["user"]}


@pytest.fixture(scope="module")
def leader_session():
    response = login(LEADER_EMAIL, LEADER_PASSWORD)
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"token": payload["token"], "user": payload["user"]}


@pytest.fixture(scope="module")
def persona_session():
    response = login(PERSONA_EMAIL, PERSONA_PASSWORD)
    assert response.status_code == 200, response.text
    payload = response.json()
    return {"token": payload["token"], "user": payload["user"]}


@pytest.fixture(scope="module")
def qa_person_id(pastor_session):
    """Module: create a canonical QA person used across process scenarios."""
    create = requests.post(
        api_url("/api/core/persons"),
        headers=auth_headers(pastor_session["token"]),
        json={
            "nombre": "QA",
            "apellido": f"MegaB{uuid.uuid4().hex[:6]}",
            "telefono": f"+1809{uuid.uuid4().int % 10000000:07d}",
            "idempotency_key": f"qa-megab-{uuid.uuid4().hex}",
        },
        timeout=30,
    )
    assert create.status_code == 201, create.text
    data = create.json()
    assert data.get("person_id")
    return data["person_id"]


@pytest.fixture(scope="module")
def qa_cycle_id(pastor_session):
    """Module: create a QA cycle for seven-weeks enrollment validations."""
    today = datetime.now(timezone.utc).date()
    payload = {
        "name": f"QA Ciclo Mega-Bloque B {uuid.uuid4().hex[:6]}",
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=56)).isoformat(),
        "capacity": 15,
        "status": "active",
    }
    response = requests.post(
        api_url("/api/processes/cycles"),
        headers=auth_headers(pastor_session["token"]),
        json=payload,
        timeout=30,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data.get("cycle_id")
    return data["cycle_id"]


# Module: auth hardening checks requested in playbook
def test_auth_cors_allows_credentials_with_explicit_origin():
    response = requests.post(
        api_url("/api/auth/login"),
        headers={"Origin": "http://localhost:3000"},
        json={"email": PASTOR_EMAIL, "password": PASTOR_PASSWORD},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-allow-origin") in {"http://localhost:3000", "http://localhost:3000/"}


def test_auth_login_sets_httponly_cookie_flag():
    response = login(PASTOR_EMAIL, PASTOR_PASSWORD)
    assert response.status_code == 200, response.text
    cookie = response.headers.get("set-cookie", "")
    assert "httponly" in cookie.lower()


def test_auth_bruteforce_lockout_after_five_failures_on_fresh_account():
    email = f"qa.lockout.{uuid.uuid4().hex[:8]}@example.com"
    password = "QaLockout2026!"
    register = requests.post(
        api_url("/api/auth/register"),
        json={"nombre": "QA Lockout", "email": email, "password": password, "rol": "persona"},
        timeout=30,
    )
    assert register.status_code == 200, register.text

    for _ in range(5):
        failed = login(email, "WrongPassword!2026")
        assert failed.status_code == 401

    blocked = login(email, password)
    assert blocked.status_code == 401, blocked.text


def test_auth_password_hash_starts_with_2b_prefix_for_known_user():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME unavailable for hash-format validation")
    client = MongoClient(MONGO_URL)
    user = client[DB_NAME].users.find_one({"email": PASTOR_EMAIL}, {"password": 1})
    assert user and isinstance(user.get("password"), str)
    assert user["password"].startswith("$2b$")


# Module: process catalog + dashboard + migration/legacy write contracts
def test_process_catalog_and_dashboard_have_real_serializable_data(pastor_session):
    token = pastor_session["token"]

    catalog = requests.get(api_url("/api/processes/catalog"), headers=auth_headers(token), timeout=30)
    assert catalog.status_code == 200, catalog.text
    catalog_data = catalog.json()
    assert len(catalog_data.get("definitions", [])) >= 4
    seven = next(item for item in catalog_data["definitions"] if item["process_key"] == "seven_weeks")
    assert len(seven.get("stages", [])) == 7
    assert len(catalog_data.get("doors", [])) == 9

    dashboard = requests.get(api_url("/api/processes/dashboard"), headers=auth_headers(token), timeout=30)
    assert dashboard.status_code == 200, dashboard.text
    metrics = dashboard.json().get("metrics", {})
    for key in [
        "total",
        "on_sla",
        "due_soon",
        "overdue",
        "without_responsible",
        "without_next_action",
        "average_progress",
        "retention",
        "completed",
        "stalled",
        "critical_alerts",
    ]:
        assert key in metrics


def test_migrate_is_idempotent_and_legacy_writes_return_410(pastor_session):
    token = pastor_session["token"]
    first = requests.post(api_url("/api/processes/migrate"), headers=auth_headers(token), json={}, timeout=60)
    second = requests.post(api_url("/api/processes/migrate"), headers=auth_headers(token), json={}, timeout=60)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    second_data = second.json()
    for key in ["people_migrated", "leader_records_migrated", "stage_records_migrated", "conflict_count", "conflicts"]:
        assert key in second_data

    legacy_progress = requests.put(
        api_url("/api/progress"),
        headers=auth_headers(token),
        json={"semana": 1, "casas_visitadas": 1, "personas_contactadas": 1, "personas_ganadas": 0, "oraciones_realizadas": 1},
        timeout=30,
    )
    legacy_checklist = requests.put(
        api_url("/api/checklists"),
        headers=auth_headers(token),
        json={"semana": 1, "tarea_id": "s1_t1", "completada": True},
        timeout=30,
    )
    seed_demo = requests.post(api_url("/api/admin/seed-demo"), headers=auth_headers(token), timeout=30)
    assert legacy_progress.status_code == 410, legacy_progress.text
    assert legacy_checklist.status_code == 410, legacy_checklist.text
    assert seed_demo.status_code == 410, seed_demo.text


# Module: cycles + enrollment contracts + weekly progression automation
def test_seven_weeks_requires_cycle_and_blocks_duplicate_active(pastor_session, qa_person_id, qa_cycle_id):
    token = pastor_session["token"]
    no_cycle = requests.post(
        api_url("/api/processes/enrollments"),
        headers=auth_headers(token),
        json={"process_key": "seven_weeks", "person_id": qa_person_id, "status": "active"},
        timeout=30,
    )
    assert no_cycle.status_code == 400, no_cycle.text

    create = requests.post(
        api_url("/api/processes/enrollments"),
        headers=auth_headers(token),
        json={
            "process_key": "seven_weeks",
            "person_id": qa_person_id,
            "cycle_id": qa_cycle_id,
            "status": "active",
            "next_action": "QA start",
        },
        timeout=30,
    )
    assert create.status_code == 201, create.text
    enrollment_id = create.json()["enrollment_id"]

    duplicate = requests.post(
        api_url("/api/processes/enrollments"),
        headers=auth_headers(token),
        json={"process_key": "seven_weeks", "person_id": qa_person_id, "cycle_id": qa_cycle_id, "status": "active"},
        timeout=30,
    )
    assert duplicate.status_code == 409, duplicate.text

    detail = requests.get(api_url(f"/api/processes/enrollments/{enrollment_id}"), headers=auth_headers(token), timeout=30)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["person_id"] == qa_person_id
    assert payload["current_stage_key"] == "week_1"


def test_week1_completion_opens_week2_and_records_timeline(pastor_session, qa_person_id, qa_cycle_id):
    token = pastor_session["token"]
    enrollments = requests.get(
        api_url("/api/processes/enrollments"),
        headers=auth_headers(token),
        params={"process_key": "seven_weeks", "cycle_id": qa_cycle_id},
        timeout=30,
    )
    assert enrollments.status_code == 200, enrollments.text
    row = next(item for item in enrollments.json().get("items", []) if item.get("person_id") == qa_person_id)
    enrollment_id = row["enrollment_id"]

    detail = requests.get(api_url(f"/api/processes/enrollments/{enrollment_id}"), headers=auth_headers(token), timeout=30)
    assert detail.status_code == 200, detail.text
    stage = next(item for item in detail.json().get("stages", []) if item.get("stage_key") == "week_1")

    for task in stage.get("tasks", []):
        done = requests.put(
            api_url(f"/api/processes/enrollments/{enrollment_id}/stages/week_1/tasks/{task['task_id']}"),
            headers=auth_headers(token),
            json={"completed": True},
            timeout=30,
        )
        assert done.status_code == 200, done.text

    complete = requests.put(
        api_url(f"/api/processes/enrollments/{enrollment_id}/stages/week_1"),
        headers=auth_headers(token),
        json={
            "status": "completed",
            "attendance": "present",
            "result": "QA week1 completed",
            "notes": "QA notes",
            "next_action": "Move to week2",
        },
        timeout=30,
    )
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["enrollment"]["current_stage_key"] == "week_2"

    detail_after = requests.get(api_url(f"/api/processes/enrollments/{enrollment_id}"), headers=auth_headers(token), timeout=30)
    assert detail_after.status_code == 200, detail_after.text
    timeline = detail_after.json().get("timeline", [])
    assert len(timeline) > 0


# Module: consolidation, mentorship, CAP contracts
def test_consolidation_contact_flow_updates_timeline_and_stage(pastor_session, qa_person_id):
    token = pastor_session["token"]
    create = requests.post(
        api_url("/api/processes/enrollments"),
        headers=auth_headers(token),
        json={
            "process_key": "consolidation",
            "person_id": qa_person_id,
            "status": "active",
            "next_action": "Primer contacto QA",
        },
        timeout=30,
    )
    assert create.status_code in (201, 409), create.text

    if create.status_code == 201:
        enrollment_id = create.json()["enrollment_id"]
    else:
        items = requests.get(
            api_url("/api/processes/enrollments"),
            headers=auth_headers(token),
            params={"process_key": "consolidation"},
            timeout=30,
        ).json()["items"]
        enrollment_id = next(item["enrollment_id"] for item in items if item["person_id"] == qa_person_id)

    contact = requests.post(
        api_url(f"/api/processes/enrollments/{enrollment_id}/contacts"),
        headers=auth_headers(token),
        json={
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "channel": "call",
            "outcome": "QA first contact",
            "next_contact_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "next_action": "QA follow-up",
            "advance_stage": True,
        },
        timeout=30,
    )
    assert contact.status_code == 201, contact.text
    data = contact.json()
    assert data.get("last_contact_at")
    assert data.get("next_contact_at")


def test_mentorship_creation_and_meeting_progress(pastor_session, qa_person_id):
    token = pastor_session["token"]
    catalog = requests.get(api_url("/api/processes/catalog"), headers=auth_headers(token), timeout=30)
    assert catalog.status_code == 200, catalog.text
    assignees = catalog.json().get("assignees", [])
    mentor = next((item for item in assignees if item.get("person_id") and item.get("person_id") != qa_person_id), None)
    if not mentor:
        pytest.skip("No mentor assignee available in catalog")

    create = requests.post(
        api_url("/api/processes/mentorships"),
        headers=auth_headers(token),
        json={
            "person_id": qa_person_id,
            "mentor_person_id": mentor["person_id"],
            "goals": ["QA goal"],
        },
        timeout=30,
    )
    assert create.status_code in (201, 409), create.text

    if create.status_code == 201:
        mentorship_id = create.json()["mentorship_id"]
    else:
        listing = requests.get(api_url("/api/processes/mentorships"), headers=auth_headers(token), timeout=30)
        assert listing.status_code == 200, listing.text
        mentorship_id = next(item["mentorship_id"] for item in listing.json()["items"] if item["person_id"] == qa_person_id)

    meeting = requests.post(
        api_url(f"/api/processes/mentorships/{mentorship_id}/meetings"),
        headers=auth_headers(token),
        json={
            "attended": True,
            "lesson_title": "QA lesson",
            "notes": "QA meeting notes",
            "commitments": ["QA commitment"],
            "next_meeting_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        },
        timeout=30,
    )
    assert meeting.status_code == 201, meeting.text

    detail = requests.get(api_url(f"/api/processes/mentorships/{mentorship_id}"), headers=auth_headers(token), timeout=30)
    assert detail.status_code == 200, detail.text
    assert len(detail.json().get("meetings", [])) >= 1


def test_cap_complete_sets_ready_for_cellular(pastor_session, qa_person_id):
    token = pastor_session["token"]
    catalog = requests.get(api_url("/api/processes/catalog"), headers=auth_headers(token), timeout=30)
    assert catalog.status_code == 200, catalog.text
    doors = catalog.json().get("doors", [])
    assignees = catalog.json().get("assignees", [])
    if not doors or not assignees:
        pytest.skip("CAP prerequisites unavailable")

    create = requests.post(
        api_url("/api/processes/cap"),
        headers=auth_headers(token),
        json={
            "person_id": qa_person_id,
            "gifts": ["servicio", "oración"],
            "interests": ["discipulado"],
            "availability_days": ["lunes"],
        },
        timeout=30,
    )
    assert create.status_code in (201, 409), create.text

    if create.status_code == 201:
        cap_id = create.json()["cap_id"]
    else:
        listing = requests.get(api_url("/api/processes/cap"), headers=auth_headers(token), timeout=30)
        assert listing.status_code == 200, listing.text
        cap_id = next(item["cap_id"] for item in listing.json()["items"] if item["person_id"] == qa_person_id)

    update = requests.put(
        api_url(f"/api/processes/cap/{cap_id}"),
        headers=auth_headers(token),
        json={
            "selected_door_key": doors[0]["door_key"],
            "coverage_person_id": assignees[0]["person_id"],
            "activation_evidence": "QA activation evidence",
            "continuous_training": "QA training plan",
            "status": "completed",
        },
        timeout=30,
    )
    assert update.status_code == 200, update.text

    cap_doc = update.json()
    assert cap_doc["status"] == "completed"

    enrollments = requests.get(
        api_url("/api/processes/enrollments"),
        headers=auth_headers(token),
        params={"process_key": "cap"},
        timeout=30,
    )
    assert enrollments.status_code == 200, enrollments.text
    cap_enrollment = next(item for item in enrollments.json()["items"] if item["person_id"] == qa_person_id)
    assert cap_enrollment.get("ready_for_cellular") is True


# Module: RBAC checks for process configuration restrictions
def test_rbac_persona_and_leader_restrictions(persona_session, leader_session):
    persona_token = persona_session["token"]
    leader_token = leader_session["token"]

    persona_cycles = requests.post(
        api_url("/api/processes/cycles"),
        headers=auth_headers(persona_token),
        json={
            "name": "Persona should not create",
            "start_date": datetime.now(timezone.utc).date().isoformat(),
            "end_date": (datetime.now(timezone.utc).date() + timedelta(days=49)).isoformat(),
            "status": "planned",
        },
        timeout=30,
    )
    assert persona_cycles.status_code == 403, persona_cycles.text

    leader_manage_rules = requests.put(
        api_url("/api/processes/alert-rules/no_next_action"),
        headers=auth_headers(leader_token),
        json={"enabled": True, "threshold": 2, "severity": "warning"},
        timeout=30,
    )
    assert leader_manage_rules.status_code == 403, leader_manage_rules.text
