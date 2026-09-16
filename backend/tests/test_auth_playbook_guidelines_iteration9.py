"""Pruebas del contrato JWT Bearer documentado, bcrypt, CORS y lockout."""

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


def _require_env(var: str, value: str | None):
    if not value:
        pytest.skip(f"{var} no definido")
    return value


def _base_url() -> str:
    return _require_env("REACT_APP_BACKEND_URL", BASE_URL).rstrip("/")


def _mongo_db():
    mongo = _require_env("MONGO_URL", MONGO_URL)
    db_name = _require_env("DB_NAME", DB_NAME)
    return MongoClient(mongo)[db_name]


def _attempt_identifier(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


# módulo: hash bcrypt en base de datos
def test_password_hashes_start_with_2b_for_seed_accounts():
    db = _mongo_db()
    for email in [
        "coreqa.pastor@example.com",
        "coreqa.leader@example.com",
        "coreqa.member@example.com",
    ]:
        user = db.users.find_one({"email": email}, {"password": 1})
        assert user, f"Usuario QA no encontrado: {email}"
        password_hash = user.get("password")
        assert isinstance(password_hash, str) and password_hash.startswith("$2b$"), email


# módulo: JWT Bearer explícito; la aplicación no usa cookies de sesión
def test_login_uses_documented_bearer_contract_without_application_cookie():
    response = requests.post(
        f"{_base_url()}/api/auth/login",
        json={"email": "coreqa.pastor@example.com", "password": "CoreQA2026!Pastor"},
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("token"), str) and len(payload["token"]) > 20
    lower_cookie = response.headers.get("set-cookie", "").lower()
    assert not any(name in lower_cookie for name in ["auth=", "session=", "access_token=", "token=", "jwt="])


# módulo: CORS con credenciales y origin explícito
def test_cors_explicit_origin_allows_credentials():
    origin = _base_url()
    response = requests.options(
        f"{_base_url()}/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=20,
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


# módulo: brute force lockout tras 5 fallos
def test_bruteforce_lockout_after_five_failed_attempts_then_valid_password_is_blocked():
    email = "coreqa.leader@example.com"
    wrong_password = f"wrong-{uuid.uuid4()}"

    for _ in range(5):
        bad = requests.post(
            f"{_base_url()}/api/auth/login",
            json={"email": email, "password": wrong_password},
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        assert bad.status_code == 401

    blocked = requests.post(
        f"{_base_url()}/api/auth/login",
        json={"email": email, "password": "CoreQA2026!Leader"},
        headers={"Content-Type": "application/json"},
        timeout=20,
    )
    assert blocked.status_code == 401

    # Cleanup lock entry to avoid side effects for other test agents
    db = _mongo_db()
    db.login_attempts.delete_one({"identifier": _attempt_identifier(email)})


# módulo: no existe seed_admin automático en runtime
def test_runtime_does_not_expose_a_seed_admin_endpoint():
    response = requests.post(f"{_base_url()}/api/seed_admin", timeout=20)
    assert response.status_code in (404, 405)
