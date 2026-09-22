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
PASSWORD = "QaMembership42!"


def create_user(label, role="lider", access_level="lider"):
    user_id, person_id = ObjectId(), ObjectId()
    email = f"qa.membership42.{label}.{uuid4().hex[:8]}@example.com"
    defaults = access_defaults_for_role(access_level)
    now = datetime.now(timezone.utc)
    DB.persons.insert_one({"_id": person_id, "person_number": f"VV-M42-{str(person_id)[-6:]}", "nombre": "QA", "apellido": label, "search_key": f"qa {label}", "idempotency_key": f"qa:m42:{email}", "version": 1, "created_at": now, "updated_at": now})
    DB.users.insert_one({"_id": user_id, "nombre": f"QA {label}", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "access_level": access_level, "person_id": str(person_id), "capabilities": defaults["capabilities"], "access_scope": defaults["access_scope"], "privilege_groups": defaults.get("privilege_groups", []), "is_active": True, "token_version": 1, "access_policy_version": 21, "must_change_password": False, "onboarding_required": False, "created_at": now, "updated_at": now})
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email}


def login(email):
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def state():
    accounts = {
        "pastora": create_user("pastora", role="pastora", access_level="pastor"),
        "coordinator": create_user("coordinator", access_level="coordinador_general"),
        "leader": create_user("leader", access_level="lider"),
        "unknown": create_user("historical-unknown", role="persona", access_level="persona"),
        "dated": create_user("historical-dated", role="persona", access_level="persona"),
    }
    tokens = {key: login(value["email"]) for key, value in accounts.items() if key in {"pastora", "coordinator", "leader"}}
    yield {"accounts": accounts, "tokens": tokens}
    person_ids = [item["person_id"] for item in accounts.values()]
    user_ids = [ObjectId(item["user_id"]) for item in accounts.values()]
    DB.membership_events.delete_many({"person_id": {"$in": person_ids}})
    DB.membership_number_registry.delete_many({"person_id": {"$in": person_ids}})
    DB.person_memberships.delete_many({"person_id": {"$in": person_ids}})
    DB.person_activity.delete_many({"person_id": {"$in": person_ids}})
    DB.process_enrollments.delete_many({"person_id": {"$in": person_ids}})
    DB.users.delete_many({"_id": {"$in": user_ids}})
    DB.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in person_ids]}})


def test_coordinator_regularizes_without_fabricating_history_or_processes(state):
    person_id = state["accounts"]["unknown"]["person_id"]
    response = requests.post(f"{BASE_URL}/api/membership/persons/{person_id}/regularize", headers=auth(state["tokens"]["coordinator"]), json={"historical_membership_date": None, "historical_date_precision": "unknown", "reason": "Miembro activo antes de la plataforma"}, timeout=30)
    assert response.status_code == 200, response.text
    membership = response.json()["membership"]
    assert membership["status"] == "active"
    assert membership["membership_origin"] == "historical_regularization"
    assert membership["historical_membership_date"] is None
    assert membership["historical_date_precision"] == "unknown"
    assert membership.get("acceptance_signed_at") is None
    assert membership.get("regularized_at")
    assert membership["regularized_by_user_id"] == state["accounts"]["coordinator"]["user_id"]
    assert DB.process_enrollments.count_documents({"person_id": person_id}) == 0
    event = DB.membership_events.find_one({"person_id": person_id, "event_type": "membership_historical_regularized"})
    assert event and event["before"] is None and event["after"]["status"] == "active"


def test_pastora_preserves_known_historical_date_and_requested_number(state):
    person_id = state["accounts"]["dated"]["person_id"]
    requested = f"H-{uuid4().hex[:8].upper()}"
    response = requests.post(f"{BASE_URL}/api/membership/persons/{person_id}/regularize", headers=auth(state["tokens"]["pastora"]), json={"existing_member_number": requested, "historical_membership_date": "2004-06-01", "historical_date_precision": "month", "reason": "Registro histórico documentado"}, timeout=30)
    assert response.status_code == 200, response.text
    membership = response.json()["membership"]
    assert membership["member_number"] == requested
    assert membership["historical_membership_date"] == "2004-06-01"
    assert membership["historical_date_precision"] == "month"
    assert membership.get("acceptance_signed_at") is None


def test_regularization_is_idempotent_and_unauthorized_user_is_denied(state):
    person_id = state["accounts"]["unknown"]["person_id"]
    denied = requests.post(f"{BASE_URL}/api/membership/persons/{person_id}/regularize", headers=auth(state["tokens"]["leader"]), json={"historical_date_precision": "unknown", "reason": "Intento no autorizado"}, timeout=30)
    assert denied.status_code == 403
    repeat = requests.post(f"{BASE_URL}/api/membership/persons/{person_id}/regularize", headers=auth(state["tokens"]["coordinator"]), json={"historical_date_precision": "unknown", "reason": "Reintento idempotente"}, timeout=30)
    assert repeat.status_code == 200 and repeat.json()["regularized"] is False
    assert DB.membership_events.count_documents({"person_id": person_id, "event_type": "membership_historical_regularized"}) == 1