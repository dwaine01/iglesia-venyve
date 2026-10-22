"""Fase 1 Mentor badge + LBS — public URL regression (iteration 30).

Covers: badge toggle + history, LBS toggle, profile header pills, RBAC 403,
governance grant of mentorship.badge.manage, /api/mentorship/mentors listing
(phone gating), assign_mentor via consolidation intake (persona w/ badge OK,
persona w/o badge 409, leader OK).
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
MEMBER = ("coreqa.member@example.com", "CoreQA2026!Member")
LEADER = ("coreqa.leader@example.com", "CoreQA2026!Leader")
TEMP_PWD = "TestMentor2026!Pwd"


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code} {r.text[:200]}")
    data = r.json()
    return {"Authorization": f"Bearer {data['token']}"}, data["user"]


@pytest.fixture(scope="module")
def pastor():
    return login(*PASTOR)


@pytest.fixture(scope="module")
def member():
    return login(*MEMBER)


@pytest.fixture(scope="module")
def leader():
    return login(*LEADER)


def create_person(headers, label):
    r = requests.post(f"{BASE_URL}/api/core/persons", headers=headers, json={
        "nombre": "TEST_Mentor", "apellido": f"{label}{uuid.uuid4().hex[:5]}",
        "idempotency_key": f"test-mentor-{uuid.uuid4()}",
    }, timeout=30)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    return body.get("person_id") or body.get("id") or body.get("person", {}).get("person_id")


def create_account(headers, person_id, level="persona"):
    email = f"test.mentor.{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/core/governance/users", headers=headers, json={
        "person_id": person_id, "email": email, "temporary_password": TEMP_PWD, "access_level": level,
    }, timeout=30)
    assert r.status_code in (200, 201), r.text
    return r.json(), email


@pytest.fixture(scope="module")
def state(pastor):
    """Shared TEST_ data: target person, persona mentor w/ account, persona w/o badge."""
    headers, _ = pastor
    s = {"created_persons": [], "created_users": []}
    s["target"] = create_person(headers, "Target")
    s["mentor_p"] = create_person(headers, "PersonaMentor")
    acc, email = create_account(headers, s["mentor_p"])
    s["mentor_user"] = acc
    s["mentor_email"] = email
    s["nobadge_p"] = create_person(headers, "NoBadge")
    acc2, _ = create_account(headers, s["nobadge_p"])
    s["created_users"] += [acc["user_id"], acc2["user_id"]]
    s["created_persons"] += [s["target"], s["mentor_p"], s["nobadge_p"]]
    yield s
    for uid in s["created_users"]:
        requests.put(f"{BASE_URL}/api/core/governance/users/{uid}/access", headers=headers,
                     json={"access_level": "persona", "is_active": False}, timeout=30)


# --- Badge toggle + history
class TestBadge:
    def test_activate_badge_with_note_and_since(self, pastor, state):
        h, _ = pastor
        r = requests.put(f"{BASE_URL}/api/mentorship/badge/{state['target']}", headers=h,
                         json={"active": True, "since": "2025-11-01", "note": "TEST nota activación"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["active"] is True and r.json()["since"] == "2025-11-01"
        g = requests.get(f"{BASE_URL}/api/mentorship/badge/{state['target']}", headers=h, timeout=30).json()
        assert g["active"] is True and g["note"] == "TEST nota activación" and g["can_manage"] is True
        assert g["history"][0]["action"] == "mentor_badge_activated"
        assert g["history"][0]["actor_name"]

    def test_profile_header_pill_active(self, pastor, state):
        h, _ = pastor
        r = requests.get(f"{BASE_URL}/api/core/persons/{state['target']}/profile", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        header = r.json()["header"]
        assert header["mentor_badge"]["active"] is True
        assert header["mentor_badge"]["since"] == "2025-11-01"
        assert header["mentor_badge_can_manage"] is True

    def test_deactivate_accumulates_history(self, pastor, state):
        h, _ = pastor
        r = requests.put(f"{BASE_URL}/api/mentorship/badge/{state['target']}", headers=h, json={"active": False}, timeout=30)
        assert r.status_code == 200
        g = requests.get(f"{BASE_URL}/api/mentorship/badge/{state['target']}", headers=h, timeout=30).json()
        assert g["active"] is False
        actions = [x["action"] for x in g["history"]]
        assert actions[:2] == ["mentor_badge_deactivated", "mentor_badge_activated"]
        header = requests.get(f"{BASE_URL}/api/core/persons/{state['target']}/profile", headers=h, timeout=30).json()["header"]
        assert header["mentor_badge"]["active"] is False

    def test_lbs_toggle(self, pastor, state):
        h, _ = pastor
        r = requests.put(f"{BASE_URL}/api/mentorship/lbs/{state['target']}", headers=h, json={"can_teach_lbs": True, "note": "TEST lbs"}, timeout=30)
        assert r.status_code == 200 and r.json()["can_teach_lbs"] is True and r.json()["front_group_id"] is None
        g = requests.get(f"{BASE_URL}/api/mentorship/badge/{state['target']}", headers=h, timeout=30).json()
        assert g["lbs_qualified"] is True and g["lbs_note"] == "TEST lbs"
        header = requests.get(f"{BASE_URL}/api/core/persons/{state['target']}/profile", headers=h, timeout=30).json()["header"]
        assert header["mentor_lbs_qualified"] is True
        r = requests.put(f"{BASE_URL}/api/mentorship/lbs/{state['target']}", headers=h, json={"can_teach_lbs": False}, timeout=30)
        assert r.status_code == 200
        g = requests.get(f"{BASE_URL}/api/mentorship/badge/{state['target']}", headers=h, timeout=30).json()
        assert g["lbs_qualified"] is False
        assert g["history"][0]["action"] == "mentor_lbs_disabled"

    def test_unknown_person_404(self, pastor):
        h, _ = pastor
        r = requests.put(f"{BASE_URL}/api/mentorship/badge/000000000000000000000000", headers=h, json={"active": True}, timeout=30)
        assert r.status_code in (404, 400), r.text


# --- RBAC
class TestRbac:
    def test_member_put_403(self, member, state):
        h, _ = member
        r = requests.put(f"{BASE_URL}/api/mentorship/badge/{state['target']}", headers=h, json={"active": True}, timeout=30)
        assert r.status_code == 403
        r = requests.put(f"{BASE_URL}/api/mentorship/lbs/{state['target']}", headers=h, json={"can_teach_lbs": True}, timeout=30)
        assert r.status_code == 403

    def test_member_own_badge_read_only(self, member):
        h, user = member
        r = requests.get(f"{BASE_URL}/api/mentorship/badge/{user['person_id']}", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["can_manage"] is False

    def test_unauthenticated_401(self, state):
        r = requests.get(f"{BASE_URL}/api/mentorship/mentors", timeout=30)
        assert r.status_code in (401, 403)

    def test_grant_capability_via_governance(self, pastor, state):
        h, _ = pastor
        uid = state["mentor_user"]["user_id"]
        r = requests.put(f"{BASE_URL}/api/core/governance/users/{uid}/access", headers=h, json={
            "access_level": "persona", "is_active": True, "capabilities": ["mentorship.badge.manage"]}, timeout=30)
        assert r.status_code == 200, r.text
        assert "mentorship.badge.manage" in r.json()["capabilities"]
        mh, _ = login(state["mentor_email"], TEMP_PWD)
        cp = requests.post(f"{BASE_URL}/api/auth/change-password", headers=mh, json={"current_password": TEMP_PWD, "new_password": TEMP_PWD + "x"}, timeout=30)
        assert cp.status_code == 200, cp.text
        mh, _ = login(state["mentor_email"], TEMP_PWD + "x")
        r = requests.put(f"{BASE_URL}/api/mentorship/badge/{state['target']}", headers=mh, json={"active": True, "note": "TEST by delegated"}, timeout=30)
        assert r.status_code == 200, r.text
        g = requests.get(f"{BASE_URL}/api/mentorship/badge/{state['target']}", headers=h, timeout=30).json()
        assert g["active"] is True


# --- Mentors list + assign_mentor
class TestMentorsAndAssign:
    def test_mentors_list_includes_badge_persona(self, pastor, state):
        h, _ = pastor
        requests.put(f"{BASE_URL}/api/mentorship/badge/{state['mentor_p']}", headers=h, json={"active": True}, timeout=30)
        requests.put(f"{BASE_URL}/api/mentorship/lbs/{state['mentor_p']}", headers=h, json={"can_teach_lbs": True}, timeout=30)
        r = requests.get(f"{BASE_URL}/api/mentorship/mentors", headers=h, params={"limit": 100}, timeout=30)
        assert r.status_code == 200, r.text
        items = {i["person_id"]: i for i in r.json()["items"]}
        assert state["mentor_p"] in items
        assert items[state["mentor_p"]]["lbs_qualified"] is True
        assert "phone" in items[state["mentor_p"]]
        assert items[state["mentor_p"]]["has_account"] is True
        # target has badge but no account -> still included, flagged has_account=False (regla del dueño)
        assert state["target"] in items
        assert items[state["target"]]["has_account"] is False
        assert items[state["target"]]["account_active"] is False

    def test_mentors_list_search(self, pastor, state):
        h, _ = pastor
        r = requests.get(f"{BASE_URL}/api/mentorship/mentors", headers=h, params={"search": "PersonaMentor"}, timeout=30)
        assert r.status_code == 200
        assert any(i["person_id"] == state["mentor_p"] for i in r.json()["items"])

    def test_mentors_phone_hidden_for_member(self, member):
        h, _ = member
        r = requests.get(f"{BASE_URL}/api/mentorship/mentors", headers=h, timeout=30)
        assert r.status_code in (200, 403), r.text
        if r.status_code == 200:
            assert all(i["phone"] is None for i in r.json()["items"])

    def _intake(self, h, mentor_id):
        pid = create_person(h, "Intake")
        return requests.post(f"{BASE_URL}/api/processes/consolidation/intakes", headers=h, json={
            "person_id": pid, "entry_mode": "direct_church", "mentor_person_id": mentor_id}, timeout=60), pid

    def test_assign_persona_with_badge_ok(self, pastor, state):
        h, _ = pastor
        r, _ = self._intake(h, state["mentor_p"])
        assert r.status_code == 201, r.text
        assert r.json().get("mentor_person_id") == state["mentor_p"]

    def test_assign_persona_without_badge_409(self, pastor, state):
        h, _ = pastor
        r, _ = self._intake(h, state["nobadge_p"])
        assert r.status_code == 409, r.text
        assert "insignia" in r.json()["detail"].lower()

    def test_assign_leader_ok(self, pastor, leader):
        h, _ = pastor
        _, leader_user = leader
        r, _ = self._intake(h, leader_user["person_id"])
        assert r.status_code == 201, r.text
        assert r.json().get("mentor_person_id") == leader_user["person_id"]
