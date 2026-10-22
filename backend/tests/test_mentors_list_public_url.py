# Public-URL regression for GET /api/mentorship/mentors (all active-badge mentors, has_account/account_active flags) + 409 on assignment
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


def mk_person(label):
    pid = ObjectId()
    mdb.persons.insert_one({"_id": pid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "TESTMentorList", "apellido": label,
                            "idempotency_key": f"qa:mentorlist:{uuid.uuid4()}", "version": 1,
                            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    return str(pid)


@pytest.fixture(scope="module")
def seed():
    h = login(*PASTOR)
    no_acc = mk_person("SinCuenta")
    inactive = mk_person("Desactivada")
    candidate = mk_person("Candidato")
    uid = ObjectId()
    mdb.users.insert_one({"_id": uid, "nombre": "TESTMentorList Desactivada", "email": f"qa.mentorlist.{uuid.uuid4().hex[:6]}@example.com",
                          "password": "x", "rol": "persona", "is_active": False, "person_id": inactive, "token_version": 1})
    for pid in (no_acc, inactive):
        r = requests.put(f"{BASE_URL}/api/mentorship/badge/{pid}", json={"active": True}, headers=h)
        assert r.status_code == 200, r.text
    yield {"h": h, "no_acc": no_acc, "inactive": inactive, "candidate": candidate}
    ids = [no_acc, inactive, candidate]
    mdb.mentor_badges.delete_many({"person_id": {"$in": ids}})
    mdb.mentor_badge_history.delete_many({"person_id": {"$in": ids}})
    mdb.users.delete_one({"_id": uid})
    mdb.persons.delete_many({"_id": {"$in": [ObjectId(i) for i in ids]}})


def test_list_includes_no_account_and_inactive(seed):
    r = requests.get(f"{BASE_URL}/api/mentorship/mentors", headers=seed["h"])
    assert r.status_code == 200
    data = r.json()
    items = {i["person_id"]: i for i in data["items"]}
    assert items[seed["no_acc"]]["has_account"] is False and items[seed["no_acc"]]["account_active"] is False
    assert items[seed["inactive"]]["has_account"] is True and items[seed["inactive"]]["account_active"] is False
    assert data["total"] >= len(data["items"])
    for it in data["items"]:
        assert isinstance(it["has_account"], bool) and isinstance(it["account_active"], bool)


def test_total_reflects_count_before_limit(seed):
    r = requests.get(f"{BASE_URL}/api/mentorship/mentors?limit=1", headers=seed["h"])
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    assert data["total"] >= 2


def test_search_filters(seed):
    r = requests.get(f"{BASE_URL}/api/mentorship/mentors?search=SinCuenta", headers=seed["h"])
    ids = [i["person_id"] for i in r.json()["items"]]
    assert seed["no_acc"] in ids and seed["inactive"] not in ids


def test_unauthenticated_rejected():
    r = requests.get(f"{BASE_URL}/api/mentorship/mentors")
    assert r.status_code in (401, 403)


@pytest.mark.parametrize("key", ["no_acc", "inactive"])
def test_intake_with_mentor_without_active_account_409(seed, key):
    r = requests.post(f"{BASE_URL}/api/processes/consolidation/intakes",
                      json={"person_id": seed["candidate"], "entry_mode": "direct_church", "mentor_person_id": seed[key]}, headers=seed["h"])
    assert r.status_code == 409, r.text
    assert "Falta crear el acceso del mentor" in r.json()["detail"]
