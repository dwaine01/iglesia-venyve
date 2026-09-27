"""Tests for PUT /api/membership/persons/{person_id}/membership-date (iteration 55)."""
import os
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

from access_control import access_defaults_for_role


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV["REACT_APP_BACKEND_URL"]).rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
PASSWORD = "QaMembershipDate55!"


def create_user(label, role="lider", access_level="lider"):
    user_id, person_id = ObjectId(), ObjectId()
    email = f"qa.mdate55.{label}.{uuid4().hex[:8]}@example.com"
    defaults = access_defaults_for_role(access_level)
    now = datetime.now(timezone.utc)
    DB.persons.insert_one({
        "_id": person_id, "person_number": f"VV-MD55-{str(person_id)[-6:]}",
        "nombre": "QA", "apellido": label, "search_key": f"qa {label}",
        "idempotency_key": f"qa:md55:{email}", "version": 1,
        "created_at": now, "updated_at": now,
    })
    DB.users.insert_one({
        "_id": user_id, "nombre": f"QA {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "access_level": access_level, "person_id": str(person_id),
        "capabilities": defaults["capabilities"], "access_scope": defaults["access_scope"],
        "privilege_groups": defaults.get("privilege_groups", []),
        "is_active": True, "token_version": 1, "access_policy_version": 21,
        "must_change_password": False, "onboarding_required": False,
        "created_at": now, "updated_at": now,
    })
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email}


def login(email):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def state():
    accounts = {
        "pastora": create_user("pastora", role="pastora", access_level="pastor"),
        "coordinator": create_user("coordinator", access_level="coordinador_general"),
        "leader": create_user("leader", access_level="lider"),
        "member_target": create_user("membertarget", role="persona", access_level="persona"),
        "no_membership": create_user("nomembership", role="persona", access_level="persona"),
    }
    tokens = {k: login(v["email"]) for k, v in accounts.items() if k in {"pastora", "coordinator", "leader"}}

    # Regularize member_target so they have an active membership
    r = requests.post(
        f"{BASE_URL}/api/membership/persons/{accounts['member_target']['person_id']}/regularize",
        headers=auth(tokens["pastora"]),
        json={"historical_membership_date": "2010-05-15", "historical_date_precision": "exact", "reason": "seed"},
        timeout=30,
    )
    assert r.status_code == 200, r.text

    yield {"accounts": accounts, "tokens": tokens}

    person_ids = [v["person_id"] for v in accounts.values()]
    user_ids = [ObjectId(v["user_id"]) for v in accounts.values()]
    DB.membership_events.delete_many({"person_id": {"$in": person_ids}})
    DB.membership_number_registry.delete_many({"person_id": {"$in": person_ids}})
    DB.person_memberships.delete_many({"person_id": {"$in": person_ids}})
    DB.person_activity.delete_many({"person_id": {"$in": person_ids}})
    DB.users.delete_many({"_id": {"$in": user_ids}})
    DB.persons.delete_many({"_id": {"$in": [ObjectId(p) for p in person_ids]}})


def _url(person_id):
    return f"{BASE_URL}/api/membership/persons/{person_id}/membership-date"


def test_pastora_updates_membership_date_and_get_reflects(state):
    pid = state["accounts"]["member_target"]["person_id"]
    r = requests.put(_url(pid), headers=auth(state["tokens"]["pastora"]),
                     json={"historical_membership_date": "2008-03-10", "historical_date_precision": "exact", "reason": "Corrección"},
                     timeout=30)
    assert r.status_code == 200, r.text
    m = r.json()["membership"]
    assert m["historical_membership_date"] == "2008-03-10"
    assert m["historical_date_precision"] == "exact"
    assert m["membership_date_updated_by_user_id"] == state["accounts"]["pastora"]["user_id"]

    # GET reflects new value
    r2 = requests.get(f"{BASE_URL}/api/membership/persons/{pid}", headers=auth(state["tokens"]["pastora"]), timeout=30)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    data = body.get("data") or body
    mem = data.get("membership") or {}
    assert mem.get("historical_membership_date") == "2008-03-10", f"GET did not reflect update: {body}"

    # Audit event
    event = DB.membership_events.find_one({"person_id": pid, "event_type": "membership_date_updated"})
    assert event is not None
    assert event["after"]["historical_membership_date"] == "2008-03-10"
    assert event["reason"] == "Corrección"
    # person_activity entry
    act = DB.person_activity.find_one({"person_id": pid, "action": "membership_date_updated"})
    assert act is not None


def test_coordinator_updates_with_empty_reason_ok(state):
    pid = state["accounts"]["member_target"]["person_id"]
    r = requests.put(_url(pid), headers=auth(state["tokens"]["coordinator"]),
                     json={"historical_membership_date": "2012-01-01", "historical_date_precision": "year", "reason": ""},
                     timeout=30)
    assert r.status_code == 200, r.text
    m = r.json()["membership"]
    assert m["historical_membership_date"] == "2012-01-01"
    assert m["historical_date_precision"] == "year"


def test_null_date_sets_precision_unknown(state):
    pid = state["accounts"]["member_target"]["person_id"]
    r = requests.put(_url(pid), headers=auth(state["tokens"]["pastora"]),
                     json={"historical_membership_date": None, "historical_date_precision": "exact"},
                     timeout=30)
    assert r.status_code == 200, r.text
    m = r.json()["membership"]
    assert m["historical_membership_date"] is None
    assert m["historical_date_precision"] == "unknown"


def test_leader_without_capability_gets_403(state):
    pid = state["accounts"]["member_target"]["person_id"]
    r = requests.put(_url(pid), headers=auth(state["tokens"]["leader"]),
                     json={"historical_membership_date": "2015-06-01", "historical_date_precision": "exact"},
                     timeout=30)
    assert r.status_code == 403, r.text


def test_person_without_membership_returns_404(state):
    pid = state["accounts"]["no_membership"]["person_id"]
    r = requests.put(_url(pid), headers=auth(state["tokens"]["pastora"]),
                     json={"historical_membership_date": "2015-06-01", "historical_date_precision": "exact"},
                     timeout=30)
    assert r.status_code == 404, r.text


def test_invalid_date_returns_422(state):
    pid = state["accounts"]["member_target"]["person_id"]
    r = requests.put(_url(pid), headers=auth(state["tokens"]["pastora"]),
                     json={"historical_membership_date": "not-a-date", "historical_date_precision": "exact"},
                     timeout=30)
    assert r.status_code == 422, r.text


def test_unauthenticated_returns_401_or_403(state):
    pid = state["accounts"]["member_target"]["person_id"]
    r = requests.put(_url(pid),
                     json={"historical_membership_date": "2015-06-01", "historical_date_precision": "exact"},
                     timeout=30)
    assert r.status_code in (401, 403), r.text
