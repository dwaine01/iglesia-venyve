"""Auth hardening + RBAC public checks for Mega-Bloque C scope behavior."""
import os
import uuid
import hashlib

import pytest
import requests
from dotenv import dotenv_values
from bson import ObjectId
from pymongo import MongoClient


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL", "")).rstrip("/")
BACKEND_ENV = dotenv_values("/app/backend/.env")
MONGO_URL = (os.environ.get("MONGO_URL") or BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (os.environ.get("DB_NAME") or BACKEND_ENV.get("DB_NAME") or "").strip('"')

PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
LEADER = ("coreqa.leader@example.com", "CoreQA2026!Leader")
PERSONA = ("coreqa.member@example.com", "CoreQA2026!Member")
FRONTEND_ORIGIN = BASE_URL


def url(path: str) -> str:
    return f"{BASE_URL}{path}"


def login_raw(credentials: tuple[str, str]) -> requests.Response:
    return requests.post(
        url("/api/auth/login"),
        json={"email": credentials[0], "password": credentials[1]},
        timeout=30,
    )


def login_token(credentials: tuple[str, str]) -> str:
    response = login_raw(credentials)
    assert response.status_code == 200, response.text
    return response.json()["token"]


@pytest.fixture(scope="module")
def mongo_db():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("Mongo requerido para verificaciones auth-hardening")
    client = MongoClient(MONGO_URL)
    database = client[DB_NAME]
    yield database
    qa_users = list(database.users.find({"email": {"$regex": r"^qa\.lockout\.", "$options": "i"}}, {"_id": 1, "person_id": 1, "email": 1}))
    person_ids = [item["person_id"] for item in qa_users if item.get("person_id")]
    if person_ids:
        for collection in ["person_contacts", "person_activity", "process_enrollments", "cell_memberships", "cell_followups", "cell_needs"]:
            database[collection].delete_many({"person_id": {"$in": person_ids}})
        database.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in person_ids if ObjectId.is_valid(item)]}})
    if qa_users:
        database.users.delete_many({"_id": {"$in": [item["_id"] for item in qa_users]}})
        database.login_attempts.delete_many({"identifier": {"$in": [hashlib.sha256(item["email"].lower().encode()).hexdigest() for item in qa_users]}})
    client.close()


def test_auth_hash_format_and_password_not_exposed(mongo_db):
    """Auth data safety: bcrypt prefix + password not returned by login API."""
    response = login_raw(PASTOR)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "password" not in body.get("user", {})

    users = list(
        mongo_db.users.find(
            {"email": {"$in": [PASTOR[0], LEADER[0], PERSONA[0]]}},
            {"_id": 0, "email": 1, "password": 1},
        )
    )
    assert len(users) >= 2
    for user in users:
        assert isinstance(user.get("password"), str)
        assert user["password"].startswith("$2b$"), f"bcrypt prefix inválido para {user['email']}"


def test_auth_login_sets_http_only_cookie():
    """Auth session hardening: login should emit at least one HttpOnly cookie."""
    response = login_raw(PASTOR)
    assert response.status_code == 200, response.text
    set_cookie_headers = []
    if hasattr(response.raw, "headers") and hasattr(response.raw.headers, "get_all"):
        set_cookie_headers = response.raw.headers.get_all("Set-Cookie") or []
    elif "Set-Cookie" in response.headers:
        set_cookie_headers = [response.headers.get("Set-Cookie", "")]

    assert set_cookie_headers, "Login no devuelve Set-Cookie"
    assert any("httponly" in cookie.lower() for cookie in set_cookie_headers), "Cookie HttpOnly ausente"


def test_cors_credentials_with_explicit_origin_header():
    """CORS hardening: credentials true + explicit allow-origin must be returned."""
    response = requests.options(
        url("/api/auth/login"),
        headers={
            "Origin": FRONTEND_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=30,
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == FRONTEND_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_auth_bruteforce_lockout_after_five_failures():
    """Auth abuse protection: account should lock after repeated failed attempts."""
    email = f"qa.lockout.{uuid.uuid4().hex[:8]}@example.com"
    password = "CoreQaLockout2026!"

    register = requests.post(
        url("/api/auth/register"),
        json={"nombre": "QA Lockout", "email": email, "password": password, "rol": "persona"},
        timeout=30,
    )
    assert register.status_code in (200, 201), register.text

    for _ in range(5):
        failed = requests.post(url("/api/auth/login"), json={"email": email, "password": "wrong-pass"}, timeout=30)
        assert failed.status_code == 401

    should_be_locked = requests.post(url("/api/auth/login"), json={"email": email, "password": password}, timeout=30)
    assert should_be_locked.status_code == 401, should_be_locked.text


def test_cellular_rbac_matrix_basic():
    """Cellular RBAC: pastor global, leader/persona blocked from network management."""
    pastor_token = login_token(PASTOR)
    leader_token = login_token(LEADER)
    persona_token = login_token(PERSONA)

    pastor_dash = requests.get(url("/api/cellular/dashboard"), headers={"Authorization": f"Bearer {pastor_token}"}, timeout=30)
    leader_dash = requests.get(url("/api/cellular/dashboard"), headers={"Authorization": f"Bearer {leader_token}"}, timeout=30)
    persona_dash = requests.get(url("/api/cellular/dashboard"), headers={"Authorization": f"Bearer {persona_token}"}, timeout=30)
    assert pastor_dash.status_code == 200
    assert leader_dash.status_code == 200
    assert persona_dash.status_code == 200

    forbidden_payload = {"name": "QA-RBAC", "description": "N/A", "status": "active"}
    leader_create = requests.post(url("/api/cellular/networks"), headers={"Authorization": f"Bearer {leader_token}"}, json=forbidden_payload, timeout=30)
    persona_create = requests.post(url("/api/cellular/networks"), headers={"Authorization": f"Bearer {persona_token}"}, json=forbidden_payload, timeout=30)
    assert leader_create.status_code == 403
    assert persona_create.status_code == 403
