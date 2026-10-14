"""Iteration 29 (updated): Donor messaging feature backend tests for Ven y
Come campaign. Messages are now generated with static Spanish templates in
campaign_messaging.py (NOT via emergentintegrations/AI) — see DEPLOYMENT.md
portability note: emergentintegrations is intentionally excluded from
production (Railway) and must never be imported by this module.

Covers:
- GET /api/campaigns/venycome/messages/pending
- GET /api/campaigns/venycome/messages/never-donated
- POST /api/campaigns/venycome/messages/draft  (static templates)
- POST /api/campaigns/venycome/messages/{person_id}/mark-contacted
- RBAC regression: persona-level member with only campaign.venycome.manage can
  reach messaging endpoints but gets 403 on /api/core/persons.

Uses direct pymongo to seed two temporary persons with telefono contacts and
cleans everything up at the end.
"""
import os
import time
import uuid

from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MSG_BASE = f"{BASE_URL}/api/campaigns/venycome/messages"

PASTOR_EMAIL = "qa.baptismui53.pastor@example.com"
PASTOR_PASS = "QaBaptismUI53!"
MEMBER_EMAIL = "coreqa.member@example.com"
MEMBER_PASS = "MemberQA2026!"
MEMBER_USER_ID = "6ab4897333f15d6b82918f62"

ORIGINAL_MEMBER_CAPS = [
    "baptism.read", "cellular.read", "dedication.read", "formation.read",
    "operations.view", "operations.volunteer", "person.addresses.read", "person.addresses.write",
    "person.arrival.read", "person.attendance.read", "person.contacts.read", "person.contacts.write",
    "person.family.read", "person.history.read", "person.household.read", "person.ministries.read",
    "person.notes.read", "person.profile.sensitive.read", "person.profile.write",
    "person.talents.read", "person.talents.write", "processes.participate", "processes.read",
]


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def pastor_headers():
    return {"Authorization": f"Bearer {_login(PASTOR_EMAIL, PASTOR_PASS)}"}


@pytest.fixture(scope="module")
def db_handle():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest.fixture(scope="module")
def ensure_zelle_configured(pastor_headers):
    """reminder/invite drafts require zelle_info to be set; save/restore the
    previous value so this test doesn't leave permanent QA data behind."""
    settings_url = f"{BASE_URL}/api/campaigns/venycome/settings"
    before = requests.get(settings_url, headers=pastor_headers, timeout=15).json()
    requests.put(settings_url, json={
        "goal_cents": before["goal_cents"], "counting_rule": before["counting_rule"],
        "mode": before["mode"], "zelle_info": "qa-test-zelle@example.com",
    }, headers=pastor_headers, timeout=15)
    yield
    requests.put(settings_url, json={
        "goal_cents": before["goal_cents"], "counting_rule": before["counting_rule"],
        "mode": before["mode"], "zelle_info": before.get("zelle_info"),
    }, headers=pastor_headers, timeout=15)


@pytest.fixture(scope="module")
def seeded_people(db_handle, pastor_headers):
    """Seed two temp persons:
    - pending_person: with phone contact + an unverified campaign donation
    - never_person:   with phone contact + ZERO campaign donations
    """
    stamp = int(time.time())
    pending_person_id = ObjectId()
    never_person_id = ObjectId()
    db_handle.persons.insert_many([
        {"_id": pending_person_id, "nombre": "TESTAI_Pendiente", "apellido": f"S{stamp}",
         "estado": "activo", "person_number": f"TESTAI-{stamp}-1-{uuid.uuid4().hex[:6]}",
         "idempotency_key": f"testai-{uuid.uuid4().hex}"},
        {"_id": never_person_id, "nombre": "TESTAI_Nueva", "apellido": f"S{stamp}",
         "estado": "activo", "person_number": f"TESTAI-{stamp}-2-{uuid.uuid4().hex[:6]}",
         "idempotency_key": f"testai-{uuid.uuid4().hex}"},
    ])
    pending_pid = str(pending_person_id)
    never_pid = str(never_person_id)

    now = datetime.now(timezone.utc)
    contact_docs = [
        {"_id": ObjectId(), "person_id": pending_pid, "tipo": "telefono", "valor": "7865550111",
         "es_principal": True, "created_at": now, "updated_at": now},
        {"_id": ObjectId(), "person_id": never_pid, "tipo": "telefono", "valor": "7865550222",
         "es_principal": True, "created_at": now, "updated_at": now},
    ]
    db_handle.person_contacts.insert_many(contact_docs)

    # Create unverified donation for pending_pid via API
    r = requests.post(
        f"{BASE_URL}/api/campaigns/venycome/donations",
        json={
            "donor_name": "TESTAI_Pendiente S",
            "person_id": pending_pid,
            "amount_cents": 7500,
            "donation_type": "promise",
            "anonymous": False,
            "consent_show_name": True,
        },
        headers=pastor_headers, timeout=15,
    )
    assert r.status_code in (200, 201), r.text
    donation = r.json()

    yield {
        "pending_pid": pending_pid,
        "never_pid": never_pid,
        "donation": donation,
        "contact_ids": [c["_id"] for c in contact_docs],
    }

    # Cleanup
    try:
        requests.delete(
            f"{BASE_URL}/api/campaigns/venycome/donations/{donation['donation_id']}",
            headers=pastor_headers, timeout=10,
        )
    except Exception:
        pass
    db_handle.persons.delete_many({"_id": {"$in": [pending_person_id, never_person_id]}})
    db_handle.person_contacts.delete_many({"_id": {"$in": [c["_id"] for c in contact_docs]}})
    db_handle.campaign_message_log.delete_many({"person_id": {"$in": [pending_pid, never_pid]}})


# ----- GET /pending -----
class TestPendingList:
    def test_seeded_person_in_pending(self, pastor_headers, seeded_people):
        r = requests.get(f"{MSG_BASE}/pending", headers=pastor_headers, timeout=15)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        match = next((i for i in items if i["person_id"] == seeded_people["pending_pid"]), None)
        assert match is not None, f"pending person not listed; got {len(items)} items"
        assert match["phone"] == "7865550111"
        assert match["amount_cents"] == 7500
        assert match["donation_id"] == seeded_people["donation"]["donation_id"]
        assert "last_contacted_at" in match

    def test_never_donated_person_not_in_pending(self, pastor_headers, seeded_people):
        r = requests.get(f"{MSG_BASE}/pending", headers=pastor_headers, timeout=15)
        items = r.json()["items"]
        assert not any(i["person_id"] == seeded_people["never_pid"] for i in items)


# ----- GET /never-donated -----
class TestNeverDonated:
    def test_seeded_never_person_present(self, pastor_headers, seeded_people):
        r = requests.get(f"{MSG_BASE}/never-donated", headers=pastor_headers, timeout=15)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        match = next((i for i in items if i["person_id"] == seeded_people["never_pid"]), None)
        assert match is not None, "seeded never-donated person missing"
        assert match["phone"] == "7865550222"
        assert "TESTAI_Nueva" in match["name"]

    def test_pending_person_not_in_never(self, pastor_headers, seeded_people):
        r = requests.get(f"{MSG_BASE}/never-donated", headers=pastor_headers, timeout=15)
        items = r.json()["items"]
        assert not any(i["person_id"] == seeded_people["pending_pid"] for i in items)


# ----- POST /draft (static templates, no AI) -----
class TestDraftGeneration:
    def test_thank_you_draft(self, pastor_headers, seeded_people):
        r = requests.post(f"{MSG_BASE}/draft", json={
            "kind": "thank_you", "person_id": seeded_people["pending_pid"],
            "name": "Maria", "amount_cents": 7500,
        }, headers=pastor_headers, timeout=15)
        assert r.status_code == 200, r.text
        text = r.json()["text"]
        assert isinstance(text, str) and len(text) > 10
        assert len(text) <= 300
        low = text.lower()
        assert "iglesia" in low  # signed
        assert "75.00" in text
        assert any(w in low for w in ["gracias", "agradec"]), text

    def test_reminder_draft_mentions_zelle(self, pastor_headers, seeded_people, ensure_zelle_configured):
        r = requests.post(f"{MSG_BASE}/draft", json={
            "kind": "reminder", "person_id": seeded_people["pending_pid"],
            "name": "Juan", "amount_cents": 5000,
        }, headers=pastor_headers, timeout=15)
        assert r.status_code == 200, r.text
        text = r.json()["text"].lower()
        assert "zelle" in text, f"reminder should mention zelle: {text}"

    def test_invite_draft_mentions_zelle(self, pastor_headers, seeded_people, ensure_zelle_configured):
        r = requests.post(f"{MSG_BASE}/draft", json={
            "kind": "invite", "person_id": seeded_people["never_pid"], "name": "Ana",
        }, headers=pastor_headers, timeout=15)
        assert r.status_code == 200, r.text
        text = r.json()["text"].lower()
        assert "zelle" in text, f"invite should mention zelle: {text}"

    def test_invalid_kind_rejected(self, pastor_headers, seeded_people):
        r = requests.post(f"{MSG_BASE}/draft", json={
            "kind": "bogus", "person_id": seeded_people["pending_pid"], "name": "X",
        }, headers=pastor_headers, timeout=15)
        assert r.status_code in (400, 422)

    def test_reminder_without_zelle_configured_returns_400(self, pastor_headers, seeded_people):
        settings_url = f"{BASE_URL}/api/campaigns/venycome/settings"
        before = requests.get(settings_url, headers=pastor_headers, timeout=15).json()
        requests.put(settings_url, json={
            "goal_cents": before["goal_cents"], "counting_rule": before["counting_rule"],
            "mode": before["mode"], "zelle_info": None,
        }, headers=pastor_headers, timeout=15)
        try:
            r = requests.post(f"{MSG_BASE}/draft", json={
                "kind": "reminder", "person_id": seeded_people["pending_pid"], "name": "Juan", "amount_cents": 5000,
            }, headers=pastor_headers, timeout=15)
            assert r.status_code == 400, r.text
        finally:
            requests.put(settings_url, json={
                "goal_cents": before["goal_cents"], "counting_rule": before["counting_rule"],
                "mode": before["mode"], "zelle_info": before.get("zelle_info"),
            }, headers=pastor_headers, timeout=15)


# ----- POST /{person_id}/mark-contacted -----
class TestMarkContacted:
    def test_mark_updates_last_contacted(self, pastor_headers, seeded_people):
        pid = seeded_people["pending_pid"]
        # Baseline
        before = requests.get(f"{MSG_BASE}/pending", headers=pastor_headers, timeout=15).json()["items"]
        before_item = next(i for i in before if i["person_id"] == pid)
        assert before_item["last_contacted_at"] in (None, "")

        r = requests.post(
            f"{MSG_BASE}/{pid}/mark-contacted",
            json={"kind": "reminder", "text": "TESTAI_recordatorio mensaje de prueba"},
            headers=pastor_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        after = requests.get(f"{MSG_BASE}/pending", headers=pastor_headers, timeout=15).json()["items"]
        after_item = next(i for i in after if i["person_id"] == pid)
        assert after_item["last_contacted_at"], f"expected timestamp, got {after_item['last_contacted_at']}"

    def test_mark_empty_text_rejected(self, pastor_headers, seeded_people):
        pid = seeded_people["pending_pid"]
        r = requests.post(
            f"{MSG_BASE}/{pid}/mark-contacted",
            json={"kind": "reminder", "text": ""},
            headers=pastor_headers, timeout=15,
        )
        assert r.status_code in (400, 422)


# ----- RBAC regression for persona-level operator -----
class TestPersonaOperatorRBAC:
    def test_grant_campaign_capability(self, pastor_headers):
        payload = {
            "access_level": "persona",
            "privilege_groups": [],
            "capabilities": sorted(set(ORIGINAL_MEMBER_CAPS + ["campaign.venycome.manage"])),
            "is_active": True,
        }
        r = requests.put(
            f"{BASE_URL}/api/core/governance/users/{MEMBER_USER_ID}/access",
            json=payload, headers=pastor_headers, timeout=15,
        )
        assert r.status_code == 200, r.text

    def test_member_can_list_pending(self):
        token = _login(MEMBER_EMAIL, MEMBER_PASS)
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{MSG_BASE}/pending", headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        r2 = requests.get(f"{MSG_BASE}/never-donated", headers=headers, timeout=15)
        assert r2.status_code == 200, r2.text

    def test_member_still_forbidden_persons(self):
        token = _login(MEMBER_EMAIL, MEMBER_PASS)
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/core/persons", headers=headers, timeout=15)
        assert r.status_code in (401, 403)
        r2 = requests.get(f"{BASE_URL}/api/finance/contributions", headers=headers, timeout=15)
        assert r2.status_code in (401, 403)

    def test_restore_member_capabilities(self, pastor_headers):
        payload = {
            "access_level": "persona",
            "privilege_groups": [],
            "capabilities": sorted(ORIGINAL_MEMBER_CAPS),
            "is_active": True,
        }
        r = requests.put(
            f"{BASE_URL}/api/core/governance/users/{MEMBER_USER_ID}/access",
            json=payload, headers=pastor_headers, timeout=15,
        )
        assert r.status_code == 200, r.text


# ----- Unauthenticated access rejected -----
def test_endpoints_require_auth():
    for path in ["/pending", "/never-donated"]:
        r = requests.get(f"{MSG_BASE}{path}", timeout=10)
        assert r.status_code in (401, 403), f"{path} should require auth, got {r.status_code}"
