# Public-URL regression for add/remove mentors on an existing invasion (T1, iteration 49).
# Requires: python3 tests/seed_t1_add_mentors.py (writes /tmp/t1_add_mentors_seed.json) and coreqa accounts.
import json
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/mentorship/outreach"
SEED = json.load(open("/tmp/t1_add_mentors_seed.json"))
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
STATE = {}


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def pastor():
    return login("coreqa.pastor@example.com", "CoreQA2026!Pastor")


@pytest.fixture(scope="module")
def leader():
    return login("coreqa.leader@example.com", "CoreQA2026!Leader")


@pytest.fixture(scope="module")
def campaign_id(pastor):
    r = requests.post(f"{API}/campaigns", json={"name": f"TEST_T1 Invasion {SEED['tag']}", "location": "Sector T1", "start_date": "2026-11-01",
                                                "end_date": "2026-11-05", "assigned_mentors": [{"person_id": SEED["mentor_d_busy"]}]}, headers=pastor, timeout=30)
    assert r.status_code == 201, r.text
    STATE["campaign_id"] = r.json()["campaign_id"]
    return STATE["campaign_id"]


def get_campaign(headers, cid):
    items = requests.get(f"{API}/campaigns", headers=headers, timeout=30).json()["items"]
    return next((c for c in items if c["campaign_id"] == cid), None)


# Authorization
def test_leader_forbidden_add_preview_delete(leader, campaign_id):
    assert requests.post(f"{API}/campaigns/{campaign_id}/mentors", json={"person_ids": [SEED["mentor_a"]]}, headers=leader, timeout=30).status_code == 403
    assert requests.get(f"{API}/campaigns/{campaign_id}/mentors/{SEED['mentor_d_busy']}/remove-preview", headers=leader, timeout=30).status_code == 403
    assert requests.delete(f"{API}/campaigns/{campaign_id}/mentors/{SEED['mentor_d_busy']}", json={"reason": "no auth"}, headers=leader, timeout=30).status_code == 403


# Validation
def test_add_without_badge_409(pastor, campaign_id):
    r = requests.post(f"{API}/campaigns/{campaign_id}/mentors", json={"person_ids": [SEED["no_badge"]]}, headers=pastor, timeout=30)
    assert r.status_code == 409 and "insignia" in r.json()["detail"].lower()


def test_add_empty_payload_422_and_unknown_campaign_404(pastor):
    assert requests.post(f"{API}/campaigns/{STATE['campaign_id']}/mentors", json={}, headers=pastor, timeout=30).status_code == 422
    assert requests.post(f"{API}/campaigns/nope-{uuid.uuid4()}/mentors", json={"person_ids": [SEED["mentor_a"]]}, headers=pastor, timeout=30).status_code == 404


# Additive + idempotent
def test_add_explicit_additive_idempotent(pastor, campaign_id):
    r1 = requests.post(f"{API}/campaigns/{campaign_id}/mentors", json={"person_ids": [SEED["mentor_a"]]}, headers=pastor, timeout=30)
    assert r1.status_code == 200 and r1.json()["added"] == [SEED["mentor_a"]]
    r2 = requests.post(f"{API}/campaigns/{campaign_id}/mentors", json={"person_ids": [SEED["mentor_a"]]}, headers=pastor, timeout=30)
    assert r2.status_code == 200 and r2.json()["added"] == [] and SEED["mentor_a"] in r2.json()["already_assigned"]
    c = get_campaign(pastor, campaign_id)
    assert set(c["assigned_mentor_ids"]) == {SEED["mentor_d_busy"], SEED["mentor_a"]}
    assert db.outreach_participations.count_documents({"campaign_id": campaign_id, "mentor_person_id": SEED["mentor_a"]}) == 1


# Group branch
def test_mentors_by_group_and_add_branch(pastor, campaign_id):
    r = requests.get(f"{API}/mentors-by-group/{SEED['group_parent']}", headers=pastor, timeout=30)
    assert r.status_code == 200 and SEED["mentor_c_group"] in [i["person_id"] for i in r.json()["items"]]
    a = requests.post(f"{API}/campaigns/{campaign_id}/mentors", json={"front_group_ids": [SEED["group_parent"]]}, headers=pastor, timeout=30)
    assert a.status_code == 200 and a.json()["added"] == [SEED["mentor_c_group"]]
    assert SEED["mentor_c_group"] in get_campaign(pastor, campaign_id)["assigned_mentor_ids"]


# Invite without password
def test_add_without_account_requires_email_then_invites(pastor, campaign_id):
    pid = SEED["mentor_b_noaccount"]
    r = requests.post(f"{API}/campaigns/{campaign_id}/mentors", json={"person_ids": [pid]}, headers=pastor, timeout=30)
    assert r.status_code == 200 and r.json()["rejected"][0]["person_id"] == pid and r.json()["added"] == []
    email = f"qa.addmentors.t1invited.{SEED['tag'].lower()}@example.com"
    r = requests.post(f"{API}/campaigns/{campaign_id}/mentors", json={"person_ids": [pid], "emails": {pid: email}}, headers=pastor, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["added"] == [pid] and r.json()["accounts_created"][0]["email"] == email
    u = db.users.find_one({"email": email})
    assert u and u.get("person_id") == pid
    STATE["invited_email"] = email


# Mentor portal
def test_added_mentor_sees_campaign_and_participates(campaign_id):
    h = login(SEED["mentor_a_email"], SEED["password"])
    c = get_campaign(h, campaign_id)
    assert c is not None and c["my_participation_status"] == "assigned"
    p = requests.post(f"{API}/campaigns/{campaign_id}/participate", headers=h, timeout=30)
    assert p.status_code == 200 and p.json()["status"] == "confirmed"


# Remove blocked
def test_remove_blocked_with_activity(pastor, campaign_id):
    mid = SEED["mentor_d_busy"]
    hid = str(uuid.uuid4())
    db.outreach_households.insert_one({"_id": hid, "household_id": hid, "campaign_id": campaign_id, "mentor_person_id": mid, "address_line1": "Calle T1",
                                       "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    vid = str(uuid.uuid4())
    db.outreach_visits.insert_one({"_id": vid, "visit_id": vid, "campaign_id": campaign_id, "mentor_person_id": mid, "status": "assigned", "contact_name": "QA T1",
                                   "archived": False, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    user_id = str(db.users.find_one({"person_id": mid})["_id"])
    db.library_movements.insert_one({"_id": str(uuid.uuid4()), "movement_type": "ASSIGNMENT", "campaign_id": campaign_id, "quantity": 2,
                                     "to_holder": {"type": "mentor", "id": user_id}, "from_holder": {"type": "central", "id": "central"}, "qa_t1": True,
                                     "created_at": datetime.now(timezone.utc)})
    pv = requests.get(f"{API}/campaigns/{campaign_id}/mentors/{mid}/remove-preview", headers=pastor, timeout=30).json()
    assert pv == {"households": 1, "visits": 1, "books_in_custody": 2, "blocked": True}
    d = requests.delete(f"{API}/campaigns/{campaign_id}/mentors/{mid}", json={"reason": "prueba bloqueo"}, headers=pastor, timeout=30)
    assert d.status_code == 409 and "1 hogar(es), 1 visita(s) y 2 libro(s)" in d.json()["detail"]
    assert mid in get_campaign(pastor, campaign_id)["assigned_mentor_ids"]


# Remove allowed + audit
def test_remove_allowed_and_audited(pastor, campaign_id):
    mid = SEED["mentor_a"]
    pv = requests.get(f"{API}/campaigns/{campaign_id}/mentors/{mid}/remove-preview", headers=pastor, timeout=30).json()
    assert pv["blocked"] is False
    assert requests.delete(f"{API}/campaigns/{campaign_id}/mentors/{mid}", json={"r": "x"}, headers=pastor, timeout=30).status_code == 422
    reason = f"TEST_T1 motivo exacto {SEED['tag']}"
    d = requests.delete(f"{API}/campaigns/{campaign_id}/mentors/{mid}", json={"reason": reason}, headers=pastor, timeout=30)
    assert d.status_code == 200 and d.json()["removed"] is True
    c = get_campaign(pastor, campaign_id)
    assert mid not in c["assigned_mentor_ids"] and SEED["mentor_d_busy"] in c["assigned_mentor_ids"] and SEED["mentor_c_group"] in c["assigned_mentor_ids"]
    audit = db.admin_deletions.find_one({"collection": "outreach_campaign_mentors", "target_id": f"{campaign_id}:{mid}"})
    assert audit and audit["reason"] == reason
    assert requests.delete(f"{API}/campaigns/{campaign_id}/mentors/{mid}", json={"reason": reason}, headers=pastor, timeout=30).status_code == 404
    # removed mentor no longer participates
    h = login(SEED["mentor_a_email"], SEED["password"])
    assert get_campaign(h, campaign_id)["my_participation_status"] is None
    # re-add works
    r = requests.post(f"{API}/campaigns/{campaign_id}/mentors", json={"person_ids": [mid]}, headers=pastor, timeout=30)
    assert r.json()["added"] == [mid]
