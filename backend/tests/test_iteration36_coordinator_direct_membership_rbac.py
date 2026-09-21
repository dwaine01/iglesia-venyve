"""Iteración 36: RBAC de membresía directa para Coordinación General/Pastor."""

import hashlib
import os
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

from access_control import CORE_ACCESS_MANAGE, access_defaults_for_role


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "").strip('"')
DB_NAME = os.environ.get("DB_NAME", "").strip('"')
PASSWORD = "Iter36Coord!2026"


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _attempt_identifier(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _create_user(db, *, prefix: str, role: str, name: str, access_level: str | None = None, extra_caps: list[str] | None = None):
    user_id = ObjectId()
    person_id = ObjectId()
    email = f"{prefix}.{name.replace(' ', '').lower()}@example.com"
    defaults = access_defaults_for_role(role)
    capabilities = sorted(set((defaults.get("capabilities") or []) + (extra_caps or [])))
    now = datetime.now(timezone.utc)

    db.persons.insert_one(
        {
            "_id": person_id,
            "person_number": f"VV-I36{str(person_id)[-6:].upper()}",
            "nombre": name,
            "apellido": "QA",
            "search_key": f"{name} qa".lower(),
            "idempotency_key": f"qa:iter36:acct:{email}",
            "version": 1,
            "auth_user_id": str(user_id),
            "created_at": now,
            "updated_at": now,
        }
    )
    db.users.insert_one(
        {
            "_id": user_id,
            "nombre": name,
            "email": email,
            "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "rol": role,
            "person_id": str(person_id),
            "is_active": True,
            "token_version": 1,
            "created_at": now,
            "capabilities": capabilities,
            "access_scope": defaults.get("access_scope") or {"persons": "none"},
            "access_policy_version": 19,
            **({"access_level": access_level} if access_level else {}),
        }
    )
    return {
        "user_id": str(user_id),
        "person_id": str(person_id),
        "email": email,
        "name": name,
    }


def _login(email: str):
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": PASSWORD},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert isinstance(token, str) and len(token) > 20
    return token, response.json()


# Módulo: setup/cleanup de cuentas QA efímeras para RBAC de membresía directa.
@pytest.fixture(scope="module")
def qa_env():
    db = _db()
    prefix = f"qa.iter36.{uuid.uuid4().hex[:8]}"

    coordinator = _create_user(
        db,
        prefix=prefix,
        role="lider",
        name="Iter36 Coordinator Legacy",
        access_level="lider",
        extra_caps=[CORE_ACCESS_MANAGE],
    )
    ordinary_leader = _create_user(
        db,
        prefix=prefix,
        role="lider",
        name="Iter36 Ordinary Leader",
        access_level="lider",
    )
    director = _create_user(
        db,
        prefix=prefix,
        role="lider",
        name="Iter36 Director",
        access_level="director",
        extra_caps=[CORE_ACCESS_MANAGE],
    )
    pastor = _create_user(
        db,
        prefix=prefix,
        role="pastor",
        name="Iter36 Pastor",
        access_level="pastor",
    )

    env = {
        "prefix": prefix,
        "coordinator": coordinator,
        "ordinary_leader": ordinary_leader,
        "director": director,
        "pastor": pastor,
    }
    yield env

    user_ids = [env[key]["user_id"] for key in ["coordinator", "ordinary_leader", "director", "pastor"]]
    person_ids = [env[key]["person_id"] for key in ["coordinator", "ordinary_leader", "director", "pastor"]]

    created_people = list(
        db.persons.find(
            {
                "$or": [
                    {"created_by": {"$in": user_ids}},
                    {"idempotency_key": {"$regex": "^qa:iter36:"}},
                ]
            },
            {"_id": 1},
        )
    )
    created_person_ids = [str(item["_id"]) for item in created_people]
    all_person_ids = sorted(set([*person_ids, *created_person_ids]))

    memberships = list(
        db.person_memberships.find(
            {"person_id": {"$in": all_person_ids}},
            {"_id": 0, "member_number": 1},
        )
    )
    member_numbers = [item.get("member_number") for item in memberships if item.get("member_number")]

    db.membership_number_registry.delete_many({"member_number": {"$in": member_numbers}})
    db.membership_events.delete_many({"person_id": {"$in": all_person_ids}})
    db.person_memberships.delete_many({"person_id": {"$in": all_person_ids}})
    db.person_activity.delete_many({"person_id": {"$in": all_person_ids}})
    db.person_contacts.delete_many({"person_id": {"$in": all_person_ids}})
    db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in all_person_ids if ObjectId.is_valid(item)]}})
    db.users.delete_many({"email": {"$regex": f"^{prefix}\\."}})
    db.login_attempts.delete_many(
        {
            "identifier": {
                "$in": [
                    _attempt_identifier(env[key]["email"])
                    for key in ["coordinator", "ordinary_leader", "director", "pastor"]
                ]
            }
        }
    )


# Módulo: normalización de access_level legado en login y /api/auth/me.
@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_legacy_coordinator_is_normalized_in_login_and_me(qa_env):
    token, login_data = _login(qa_env["coordinator"]["email"])
    assert login_data["user"]["access_level"] == "coordinador_general"

    me = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert me.status_code == 200, me.text
    assert me.json()["access_level"] == "coordinador_general"


# Módulo: POST /api/core/persons con preexisting_active_member según RBAC.
@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_general_coordinator_can_create_direct_membership_person(qa_env):
    db = _db()
    token, _ = _login(qa_env["coordinator"]["email"])
    payload = {
        "nombre": "Iter36",
        "apellido": "DirectMembershipCoordinator",
        "telefono": "6145553611",
        "idempotency_key": f"qa:iter36:{uuid.uuid4()}",
        "preexisting_active_member": True,
        "existing_member_number": "I36-COORD-01",
    }
    response = requests.post(
        f"{BASE_URL}/api/core/persons",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["membership"]["direct"] is True

    membership = db.person_memberships.find_one({"person_id": data["person_id"]}, {"_id": 0})
    assert membership and membership.get("direct_membership") is True


@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_ordinary_leader_forced_direct_membership_returns_403(qa_env):
    token, _ = _login(qa_env["ordinary_leader"]["email"])
    payload = {
        "nombre": "Iter36",
        "apellido": "DirectMembershipLeaderDenied",
        "telefono": "6145553612",
        "idempotency_key": f"qa:iter36:{uuid.uuid4()}",
        "preexisting_active_member": True,
    }
    response = requests.post(
        f"{BASE_URL}/api/core/persons",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert response.status_code == 403


@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_director_with_core_access_manage_is_not_treated_as_coordinator_general(qa_env):
    token, login_data = _login(qa_env["director"]["email"])
    assert login_data["user"]["access_level"] == "director"

    me = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert me.status_code == 200, me.text
    assert me.json()["access_level"] == "director"

    payload = {
        "nombre": "Iter36",
        "apellido": "DirectorDenied",
        "telefono": "6145553613",
        "idempotency_key": f"qa:iter36:{uuid.uuid4()}",
        "preexisting_active_member": True,
    }
    denied = requests.post(
        f"{BASE_URL}/api/core/persons",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert denied.status_code == 403


@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_pastor_can_still_create_direct_membership_without_regression(qa_env):
    token, _ = _login(qa_env["pastor"]["email"])
    payload = {
        "nombre": "Iter36",
        "apellido": "PastorDirectMembership",
        "telefono": "6145553614",
        "idempotency_key": f"qa:iter36:{uuid.uuid4()}",
        "preexisting_active_member": True,
        "existing_member_number": "I36-PASTOR-01",
    }
    response = requests.post(
        f"{BASE_URL}/api/core/persons",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert response.status_code == 201, response.text
    assert response.json()["membership"]["direct"] is True