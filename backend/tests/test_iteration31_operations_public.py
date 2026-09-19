"""Iteration 31 public API contract tests for Mega-Bloque E Operaciones."""

from __future__ import annotations

import os
import subprocess
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import dotenv_values


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL") or "").rstrip("/")
PASSWORD = "OperationsFlow2026!"
PASTOR_EMAIL = "qa.operations.pastor@example.com"
LEADER_EMAIL = "qa.operations.leader@example.com"
PERSON_EMAIL = "qa.operations.person@example.com"


@pytest.fixture(scope="module", autouse=True)
def operations_fixture():
    subprocess.run(["python", "/app/tests/ui_operations_fixture.py", "setup"], check=True, capture_output=True, text=True)
    yield
    subprocess.run(["python", "/app/tests/ui_operations_fixture.py", "cleanup"], check=True, capture_output=True, text=True)


def _login(email: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": PASSWORD},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data.get("token"), str) and data["token"]
    assert data.get("user", {}).get("email") == email
    return data


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_operations_public_rbac_recurrence_and_checkin_flow():
    pastor = _login(PASTOR_EMAIL)
    leader = _login(LEADER_EMAIL)
    person = _login(PERSON_EMAIL)

    pastor_headers = {"Authorization": f"Bearer {pastor['token']}"}
    leader_headers = {"Authorization": f"Bearer {leader['token']}"}
    person_headers = {"Authorization": f"Bearer {person['token']}"}

    start = datetime.now(timezone.utc) + timedelta(days=2)
    start = start.replace(hour=23, minute=0, second=0, microsecond=0)
    weekday = start.astimezone().weekday()

    event_payload = {
        "title": f"QA OPERACIONES I31 {uuid.uuid4().hex[:6]}",
        "event_type": "service",
        "location": "Santuario QA",
        "timezone": "America/New_York",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=2)).isoformat(),
        "capacity": 1,
        "registration_mode": "open",
        "status": "published",
        "recurrence": {
            "frequency": "weekly",
            "interval": 1,
            "weekdays": [weekday],
            "end_mode": "count",
            "count": 2,
        },
    }

    denied_create = requests.post(
        f"{BASE_URL}/api/operations/events",
        json=event_payload,
        headers=leader_headers,
        timeout=30,
    )
    assert denied_create.status_code == 403

    create = requests.post(
        f"{BASE_URL}/api/operations/events",
        json=event_payload,
        headers=pastor_headers,
        timeout=30,
    )
    assert create.status_code == 201, create.text
    created = create.json()
    assert created["materialization"]["created_occurrences"] == 2
    event_id = created["event_id"]

    detail = requests.get(
        f"{BASE_URL}/api/operations/events/{event_id}",
        headers=pastor_headers,
        timeout=30,
    )
    assert detail.status_code == 200, detail.text
    occurrences = detail.json().get("occurrences", [])
    assert len(occurrences) == 2
    occurrence_id = occurrences[0]["occurrence_id"]

    shift = requests.post(
        f"{BASE_URL}/api/operations/events/{event_id}/shift-templates",
        json={
            "name": "Recepción",
            "role_name": "Anfitrión",
            "scope": "all_occurrences",
            "start_offset_minutes": -30,
            "duration_minutes": 120,
            "required_volunteers": 1,
        },
        headers=pastor_headers,
        timeout=30,
    )
    assert shift.status_code == 201, shift.text
    assert shift.json()["shifts_created"] == 2

    occurrence_detail = requests.get(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}",
        headers=pastor_headers,
        timeout=30,
    )
    assert occurrence_detail.status_code == 200, occurrence_detail.text
    shifts = occurrence_detail.json().get("shifts", [])
    assert len(shifts) >= 1
    shift_id = shifts[0]["shift_id"]

    assign = requests.post(
        f"{BASE_URL}/api/operations/shifts/{shift_id}/assignments",
        json={"person_id": person["user"]["person_id"]},
        headers=pastor_headers,
        timeout=30,
    )
    assert assign.status_code == 201, assign.text
    assignment_id = assign.json()["assignment_id"]

    confirm = requests.patch(
        f"{BASE_URL}/api/operations/volunteer-assignments/{assignment_id}",
        json={"status": "confirmed"},
        headers=person_headers,
        timeout=30,
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "confirmed"

    forbidden_guest = requests.post(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}/registrations",
        json={"guest_name": "Invitado bloqueado", "party_size": 1},
        headers=person_headers,
        timeout=30,
    )
    assert forbidden_guest.status_code == 403

    self_registration = requests.post(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}/registrations",
        json={"person_id": person["user"]["person_id"], "party_size": 1},
        headers=person_headers,
        timeout=30,
    )
    assert self_registration.status_code == 201, self_registration.text
    registration = self_registration.json()
    assert registration["person_id"] == person["user"]["person_id"]

    duplicate_registration = requests.post(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}/registrations",
        json={"person_id": person["user"]["person_id"], "party_size": 1},
        headers=person_headers,
        timeout=30,
    )
    assert duplicate_registration.status_code == 409

    guest_registration = requests.post(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}/registrations",
        json={"guest_name": "Invitada QA", "party_size": 1},
        headers=leader_headers,
        timeout=30,
    )
    assert guest_registration.status_code == 201, guest_registration.text
    assert guest_registration.json()["status"] == "waitlisted"

    person_occurrence = requests.get(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}",
        headers=person_headers,
        timeout=30,
    )
    assert person_occurrence.status_code == 200, person_occurrence.text
    person_view = person_occurrence.json()
    assert len(person_view.get("registrations", [])) == 1
    assert person_view.get("assignments", [])[0]["person_id"] == person["user"]["person_id"]

    search = requests.get(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}/checkin/search",
        params={"q": "QA Voluntario"},
        headers=leader_headers,
        timeout=30,
    )
    assert search.status_code == 200, search.text
    assert any(item.get("person_id") == person["user"]["person_id"] for item in search.json().get("items", []))

    first_checkin = requests.post(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}/check-ins",
        json={
            "person_id": person["user"]["person_id"],
            "kind": "auto",
            "idempotency_key": f"i31:{uuid.uuid4()}",
        },
        headers=leader_headers,
        timeout=30,
    )
    assert first_checkin.status_code == 200, first_checkin.text
    assert first_checkin.json()["duplicate"] is False

    duplicate_checkin = requests.post(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}/check-ins",
        json={
            "registration_id": registration["registration_id"],
            "kind": "auto",
            "idempotency_key": f"i31:{uuid.uuid4()}",
        },
        headers=leader_headers,
        timeout=30,
    )
    assert duplicate_checkin.status_code == 200, duplicate_checkin.text
    assert duplicate_checkin.json()["duplicate"] is True

    close = requests.post(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}/close",
        json={"notes": "Cierre QA i31"},
        headers=pastor_headers,
        timeout=30,
    )
    assert close.status_code == 200, close.text
    assert close.json()["occurrence"]["status"] == "closed"

    blocked_after_close = requests.post(
        f"{BASE_URL}/api/operations/occurrences/{occurrence_id}/check-ins",
        json={
            "person_id": person["user"]["person_id"],
            "kind": "auto",
            "idempotency_key": f"i31:{uuid.uuid4()}",
        },
        headers=leader_headers,
        timeout=30,
    )
    assert blocked_after_close.status_code == 409

    dashboard = requests.get(
        f"{BASE_URL}/api/operations/dashboard",
        headers=pastor_headers,
        timeout=30,
    )
    assert dashboard.status_code == 200, dashboard.text
    metrics = dashboard.json().get("metrics", {})
    assert all(
        key in metrics
        for key in [
            "upcoming_occurrences",
            "checkins_today",
            "volunteers_confirmed",
            "open_volunteer_slots",
        ]
    )