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


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (os.environ.get("MONGO_URL") or dotenv_values("/app/backend/.env").get("MONGO_URL") or "").strip('"')
DB_NAME = (os.environ.get("DB_NAME") or dotenv_values("/app/backend/.env").get("DB_NAME") or "").strip('"')


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _attempt_identifier(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_feature_accounts_have_bcrypt_hashes_2b_prefix():
    db = _db()
    for email in ["qa.features.pastor@example.com", "qa.features.persona@example.com"]:
        user = db.users.find_one({"email": email}, {"password": 1, "_id": 0})
        assert user, f"Missing fixture user {email}"
        assert isinstance(user.get("password"), str)
        assert user["password"].startswith("$2b$")


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_login_uses_bearer_token_and_no_app_cookie():
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "qa.features.pastor@example.com", "password": "FeatureFlow2026!"},
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
