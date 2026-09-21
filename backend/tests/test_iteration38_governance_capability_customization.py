"""Iteración 38: solo Pastor puede personalizar capacidades en Gestión de Accesos."""

import hashlib
import os
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

from access_control import CORE_ACCESS_MANAGE, MEMBERSHIP_DIRECT_IMPORT, access_defaults_for_role


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "").strip('"')
DB_NAME = os.environ.get("DB_NAME", "").strip('"')
PASSWORD = "Iter38Gov!2026"


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _attempt_identifier(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _create_user(
    db,
    *,
    prefix: str,
    role: str,
    name: str,
    access_level: str,
    parent_user_id: str | None = None,
    extra_caps: list[str] | None = None,
):
    user_id = ObjectId()
    person_id = ObjectId()
    now = datetime.now(timezone.utc)
    email = f"{prefix}.{name.replace(' ', '').lower()}@example.com"
    defaults = access_defaults_for_role(role)
    capabilities = sorted(set((defaults.get("capabilities") or []) + (extra_caps or [])))

    db.persons.insert_one(
        {
            "_id": person_id,
            "person_number": f"VV-I38{str(person_id)[-6:].upper()}",
            "nombre": name,
            "apellido": "QA",
            "search_key": f"{name} qa".lower(),
            "idempotency_key": f"qa:iter38:acct:{email}",
            "version": 1,
            "auth_user_id": str(user_id),
            "created_at": now,
            "updated_at": now,
        }
    )

    doc = {
        "_id": user_id,
        "nombre": name,
        "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role,
        "access_level": access_level,
        "person_id": str(person_id),
        "is_active": True,
        "token_version": 1,
        "created_at": now,
        "updated_at": now,
        "capabilities": capabilities,
        "access_scope": defaults.get("access_scope") or {"persons": "none"},
        "access_policy_version": 20,
    }
    if parent_user_id:
        doc["parent_user_id"] = parent_user_id
    db.users.insert_one(doc)
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email}


def _login(email: str):
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": PASSWORD},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert isinstance(token, str) and len(token) > 20
    return token


# Módulo: fixture efímera para RBAC de personalización de capacidades.
@pytest.fixture(scope="module")
def qa_env():
    db = _db()
    prefix = f"qa.iter38.{uuid.uuid4().hex[:8]}"

    pastor = _create_user(db, prefix=prefix, role="pastor", name="Iter38 Pastor", access_level="pastor")
    coordinator = _create_user(
        db,
        prefix=prefix,
        role="lider",
        name="Iter38 Coordinator",
        access_level="coordinador_general",
        parent_user_id=pastor["user_id"],
        extra_caps=[CORE_ACCESS_MANAGE],
    )
    subordinate = _create_user(
        db,
        prefix=prefix,
        role="lider",
        name="Iter38 Subordinate",
        access_level="lider",
        parent_user_id=coordinator["user_id"],
    )
    env = {"prefix": prefix, "pastor": pastor, "coordinator": coordinator, "subordinate": subordinate}
    yield env

    ids = [env[k]["person_id"] for k in ["pastor", "coordinator", "subordinate"]]
    emails = [env[k]["email"] for k in ["pastor", "coordinator", "subordinate"]]
    db.login_attempts.delete_many({"identifier": {"$in": [_attempt_identifier(email) for email in emails]}})
    db.membership_events.delete_many({"person_id": {"$in": ids}})
    db.person_memberships.delete_many({"person_id": {"$in": ids}})
    db.membership_number_registry.delete_many({"person_id": {"$in": ids}})
    db.person_contacts.delete_many({"person_id": {"$in": ids}})
    db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in ids if ObjectId.is_valid(item)]}})
    db.users.delete_many({"email": {"$regex": f"^{prefix}\\."}})


@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_coordinator_cannot_customize_capabilities_on_child_account(qa_env):
    token = _login(qa_env["coordinator"]["email"])
    target_id = qa_env["subordinate"]["user_id"]
    payload = {
        "access_level": "lider",
        "is_active": True,
        "privilege_groups": [],
        "capabilities": [MEMBERSHIP_DIRECT_IMPORT],
    }
    response = requests.put(
        f"{BASE_URL}/api/core/governance/users/{target_id}/access",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert response.status_code == 403
    assert "Solo el pastor puede personalizar capacidades" in response.text


@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_pastor_can_customize_membership_direct_import_on_target_user(qa_env):
    db = _db()
    target_id = qa_env["subordinate"]["user_id"]
    target = db.users.find_one({"_id": ObjectId(target_id)}, {"_id": 0})
    pastor_token = _login(qa_env["pastor"]["email"])

    payload = {
        "access_level": target.get("access_level") or "lider",
        "is_active": True,
        "privilege_groups": target.get("privilege_groups") or [],
        "capabilities": sorted(set([*(target.get("capabilities") or []), MEMBERSHIP_DIRECT_IMPORT])),
    }
    response = requests.put(
        f"{BASE_URL}/api/core/governance/users/{target_id}/access",
        json=payload,
        headers={"Authorization": f"Bearer {pastor_token}"},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    assert MEMBERSHIP_DIRECT_IMPORT in response.json().get("capabilities", [])
