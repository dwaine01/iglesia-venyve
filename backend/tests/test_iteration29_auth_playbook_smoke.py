"""Iteration 29 auth smoke checks aligned with auth playbook constraints."""

import hashlib
import os
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient
from access_control import access_defaults_for_role


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (os.environ.get("MONGO_URL") or dotenv_values("/app/backend/.env").get("MONGO_URL") or "").strip('"')
DB_NAME = (os.environ.get("DB_NAME") or dotenv_values("/app/backend/.env").get("DB_NAME") or "").strip('"')
PASSWORD = "Iteration29SelfContained!"
PASTOR_EMAIL = "qa.iter29.self.pastor@example.com"
PERSON_EMAIL = "qa.iter29.self.person@example.com"


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _attempt_identifier(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


@pytest.fixture(scope="module", autouse=True)
def ephemeral_auth_accounts():
    db = _db(); emails = [PASTOR_EMAIL, PERSON_EMAIL]
    db.users.delete_many({"email": {"$in": emails}})
    for role, email, name in [("pastor", PASTOR_EMAIL, "QA I29 Pastor"), ("persona", PERSON_EMAIL, "QA I29 Persona")]:
        user_id, person_id = ObjectId(), ObjectId(); now = datetime.now(timezone.utc)
        db.persons.insert_one({"_id": person_id, "person_number": f"VV-I29{str(person_id)[-6:].upper()}", "nombre": name, "apellido": "Temporal", "search_key": f"{name} temporal".lower(), "idempotency_key": f"qa:i29:self:{email}", "version": 1, "auth_user_id": str(user_id), "created_at": now, "updated_at": now})
        db.users.insert_one({"_id": user_id, "nombre": name, "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": str(person_id), "is_active": True, "token_version": 1, "created_at": now, **access_defaults_for_role(role)})
    yield
    users = list(db.users.find({"email": {"$in": emails}}, {"person_id": 1}))
    person_ids = [ObjectId(item["person_id"]) for item in users if ObjectId.is_valid(item.get("person_id"))]
    db.login_attempts.delete_many({"identifier": {"$in": [_attempt_identifier(email) for email in emails]}})
    db.users.delete_many({"email": {"$in": emails}}); db.persons.delete_many({"_id": {"$in": person_ids}})


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_feature_accounts_have_bcrypt_hashes_2b_prefix():
    db = _db()
    for email in [PASTOR_EMAIL, PERSON_EMAIL]:
        user = db.users.find_one({"email": email}, {"password": 1, "_id": 0})
        assert user, f"Missing fixture user {email}"
        assert isinstance(user.get("password"), str)
        assert user["password"].startswith("$2b$")


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_login_uses_bearer_token_and_no_app_cookie():
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": PASTOR_EMAIL, "password": PASSWORD},
        timeout=25,
    )
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert isinstance(token, str) and len(token) > 20
    lower_cookie = response.headers.get("set-cookie", "").lower()
    assert not any(name in lower_cookie for name in ["auth=", "session=", "access_token=", "token=", "jwt="])


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_cors_explicit_origin_allows_credentials():
    response = requests.options(
        f"{BASE_URL}/api/auth/login",
        headers={
            "Origin": BASE_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=25,
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == BASE_URL
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_bruteforce_lockout_after_five_fails():
    db = _db()
    email = f"qa.iter29.lockout.{uuid.uuid4().hex[:10]}@example.com"
    password = "LockoutFlow2026!"
    user_id = ObjectId()
    db.users.insert_one(
        {
            "_id": user_id,
            "nombre": "QA Lockout",
            "email": email,
            "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            "rol": "persona",
            "person_id": str(ObjectId()),
            "is_active": True,
            "token_version": 1,
            "created_at": datetime.now(timezone.utc),
            "capabilities": [],
            "access_scope": {"persons": "self"},
        }
    )
    try:
        for _ in range(5):
            bad = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": email, "password": "wrong-pass"},
                timeout=25,
            )
            assert bad.status_code == 401

        blocked = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=25,
        )
        assert blocked.status_code == 401
    finally:
        db.login_attempts.delete_many({"identifier": _attempt_identifier(email)})
        db.users.delete_many({"email": email})


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_seed_admin_endpoint_not_exposed_publicly():
    response = requests.post(f"{BASE_URL}/api/seed_admin", timeout=25)
    assert response.status_code in (404, 405)
