"""Public preview regression for Mega-Bloque A core governance + auth hardening checks."""
import os
import uuid
import hashlib

import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient


# Module: env + credentials bootstrap for public endpoint testing
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL is required for public endpoint tests")
BASE_URL = BASE_URL.rstrip("/")

PASTOR_EMAIL = "coreqa.pastor@example.com"
PASTOR_PASSWORD = "CoreQA2026!Pastor"
PERSONA_EMAIL = "coreqa.member@example.com"
PERSONA_PASSWORD = "CoreQA2026!Member"
LEADER_EMAIL = "access01.ui@example.com"
LEADER_PASSWORD = "Access01UiTest!"


def api_url(path: str) -> str:
    return f"{BASE_URL}{path}"


def login(email: str, password: str):
    return requests.post(
        api_url("/api/auth/login"),
        json={"email": email, "password": password},
        timeout=20,
    )


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def pastor_session():
    response = login(PASTOR_EMAIL, PASTOR_PASSWORD)
    assert response.status_code == 200, response.text
    data = response.json()
    token = data["token"]
    user = data["user"]
    return {"token": token, "user": user}


@pytest.fixture(scope="module")
def leader_session():
    response = login(LEADER_EMAIL, LEADER_PASSWORD)
    assert response.status_code == 200, response.text
    data = response.json()
    return {"token": data["token"], "user": data["user"]}


@pytest.fixture(scope="module")
def persona_session():
    response = login(PERSONA_EMAIL, PERSONA_PASSWORD)
    assert response.status_code == 200, response.text
    data = response.json()
    return {"token": data["token"], "user": data["user"]}


# Module: governance authorization protections
def test_leader_gets_403_on_governance_routes(leader_session):
    token = leader_session["token"]
    for path in ("/api/core/governance/integrity", "/api/core/governance/users"):
        response = requests.get(api_url(path), headers=auth_headers(token), timeout=20)
        assert response.status_code == 403, response.text


def test_public_registration_cannot_create_pastor_role():
    email = f"qa.pastor.blocked.{uuid.uuid4().hex[:8]}@example.com"
    response = requests.post(
        api_url("/api/auth/register"),
        json={
            "nombre": "QA Blocked Pastor",
            "email": email,
            "password": "BlockedPastorPass2026!",
            "rol": "pastor",
        },
        timeout=20,
    )
    assert response.status_code == 403, response.text
    assert "pastor" in response.json().get("detail", "").lower()


def test_pastor_cannot_self_demote_or_deactivate(pastor_session):
    pastor_token = pastor_session["token"]
    me = requests.get(api_url("/api/auth/me"), headers=auth_headers(pastor_token), timeout=20)
    assert me.status_code == 200, me.text
    pastor_id = me.json()["id"]

    demote = requests.put(
        api_url(f"/api/core/governance/users/{pastor_id}/access"),
        headers=auth_headers(pastor_token),
        json={"rol": "lider", "is_active": True},
        timeout=20,
    )
    disable = requests.put(
        api_url(f"/api/core/governance/users/{pastor_id}/access"),
        headers=auth_headers(pastor_token),
        json={"rol": "pastor", "is_active": False},
        timeout=20,
    )

    assert demote.status_code == 400, demote.text
    assert disable.status_code == 400, disable.text


# Module: integrity + migration idempotency
def test_integrity_returns_real_metrics_and_serializable_payload(pastor_session):
    response = requests.get(
        api_url("/api/core/governance/integrity"),
        headers=auth_headers(pastor_session["token"]),
        timeout=25,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert isinstance(body.get("score"), int)
    assert isinstance(body.get("counts"), dict)
    assert isinstance(body.get("issues"), dict)
    assert "persons" in body["counts"]
    assert "users_without_person" in body["issues"]
    assert "$oid" not in response.text


def test_migration_is_idempotent_and_does_not_duplicate_persons(pastor_session):
    token = pastor_session["token"]
    before = requests.get(api_url("/api/core/governance/integrity"), headers=auth_headers(token), timeout=25)
    assert before.status_code == 200, before.text
    before_persons = before.json()["counts"]["persons"]

    first = requests.post(api_url("/api/core/governance/migrate"), headers=auth_headers(token), json={}, timeout=30)
    second = requests.post(api_url("/api/core/governance/migrate"), headers=auth_headers(token), json={}, timeout=30)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    second_data = second.json()
    assert second_data["persons_created_for_users"] == 0
    assert second_data["persons_created_for_legacy"] == 0

    after = requests.get(api_url("/api/core/governance/integrity"), headers=auth_headers(token), timeout=25)
    assert after.status_code == 200, after.text
    after_persons = after.json()["counts"]["persons"]
    assert after_persons == before_persons


# Module: users/access governance + JWT revocation
def test_governance_users_are_linked_with_canonical_profile_path(pastor_session):
    response = requests.get(
        api_url("/api/core/governance/users"),
        headers=auth_headers(pastor_session["token"]),
        timeout=25,
    )
    assert response.status_code == 200, response.text
    items = response.json().get("items", [])
    assert len(items) > 0
    assert all(item.get("person_id") for item in items)
    assert all(item.get("canonical_profile_path") for item in items)


def test_access_update_increments_token_version_and_revokes_previous_jwt(pastor_session, leader_session):
    pastor_token = pastor_session["token"]
    old_leader_token = leader_session["token"]

    users_response = requests.get(api_url("/api/core/governance/users"), headers=auth_headers(pastor_token), timeout=25)
    assert users_response.status_code == 200, users_response.text
    users = users_response.json()["items"]
    target = next((item for item in users if item.get("email") == LEADER_EMAIL), None)
    assert target is not None

    original_role = target["rol"]
    new_role = "persona" if original_role != "persona" else "lider"
    current_version = int(target.get("token_version", 1))

    update = requests.put(
        api_url(f"/api/core/governance/users/{target['user_id']}/access"),
        headers=auth_headers(pastor_token),
        json={"rol": new_role, "is_active": True},
        timeout=25,
    )
    assert update.status_code == 200, update.text
    update_body = update.json()
    assert update_body["rol"] == new_role
    assert int(update_body["token_version"]) == current_version + 1

    revoked_check = requests.get(api_url("/api/auth/me"), headers=auth_headers(old_leader_token), timeout=20)
    assert revoked_check.status_code == 401, revoked_check.text

    relogin = login(LEADER_EMAIL, LEADER_PASSWORD)
    assert relogin.status_code == 200, relogin.text
    new_token = relogin.json()["token"]
    new_me = requests.get(api_url("/api/auth/me"), headers=auth_headers(new_token), timeout=20)
    assert new_me.status_code == 200, new_me.text

    restore = requests.put(
        api_url(f"/api/core/governance/users/{target['user_id']}/access"),
        headers=auth_headers(pastor_token),
        json={"rol": original_role, "is_active": True},
        timeout=25,
    )
    assert restore.status_code == 200, restore.text


# Module: canonical profile + duplicate rejection
def test_persona_qa_can_open_own_profile(persona_session):
    token = persona_session["token"]
    me = requests.get(api_url("/api/auth/me"), headers=auth_headers(token), timeout=20)
    assert me.status_code == 200, me.text
    person_id = me.json().get("person_id")
    assert person_id

    profile = requests.get(api_url(f"/api/core/persons/{person_id}/profile"), headers=auth_headers(token), timeout=25)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body.get("canonical_profile_path") == f"/personas/{person_id}"


def test_canonical_create_rejects_exact_duplicate_with_409_without_new_person(pastor_session):
    token = pastor_session["token"]
    users = requests.get(api_url("/api/core/governance/users"), headers=auth_headers(token), timeout=25)
    assert users.status_code == 200, users.text
    persona_row = next((item for item in users.json()["items"] if item.get("email") == PERSONA_EMAIL), None)
    assert persona_row is not None
    person_id = persona_row["person_id"]

    profile = requests.get(api_url(f"/api/core/persons/{person_id}/profile"), headers=auth_headers(token), timeout=25)
    assert profile.status_code == 200, profile.text
    header = profile.json().get("header", {})
    nombre = header.get("nombre")
    apellido = header.get("apellido")
    assert nombre and apellido

    before = requests.get(api_url("/api/core/governance/integrity"), headers=auth_headers(token), timeout=25)
    assert before.status_code == 200
    before_persons = before.json()["counts"]["persons"]

    duplicate_try = requests.post(
        api_url("/api/core/persons"),
        headers=auth_headers(token),
        json={
            "nombre": nombre,
            "apellido": apellido,
            "idempotency_key": f"qa-dup-{uuid.uuid4().hex}",
        },
        timeout=25,
    )
    assert duplicate_try.status_code == 409, duplicate_try.text

    after = requests.get(api_url("/api/core/governance/integrity"), headers=auth_headers(token), timeout=25)
    assert after.status_code == 200
    after_persons = after.json()["counts"]["persons"]
    assert after_persons == before_persons


# Module: auth playbook checks requested for this iteration
def test_cors_credentials_uses_explicit_origin_not_wildcard():
    # El ingress reescribe Origin internamente; el middleware restaura el host
    # público autorizado antes de devolver la respuesta al navegador.
    origin = BASE_URL
    login_response = requests.post(
        api_url("/api/auth/login"),
        headers={"Origin": origin},
        json={"email": PASTOR_EMAIL, "password": PASTOR_PASSWORD},
        timeout=20,
    )
    assert login_response.status_code == 200
    assert login_response.headers.get("access-control-allow-credentials") == "true"
    allow_origin = login_response.headers.get("access-control-allow-origin")
    assert allow_origin in (origin, origin.rstrip("/")) and allow_origin != "*"


def test_login_sets_httponly_cookie():
    login_response = requests.post(
        api_url("/api/auth/login"),
        json={"email": PASTOR_EMAIL, "password": PASTOR_PASSWORD},
        timeout=20,
    )
    assert login_response.status_code == 200
    cookie_header = login_response.headers.get("set-cookie", "")
    assert "httponly" in cookie_header.lower()


def test_bruteforce_lockout_after_five_failures():
    email = f"qa.lockout.core.{uuid.uuid4().hex[:8]}@example.com"
    password = "CoreQaLockout2026!"
    registered = requests.post(api_url("/api/auth/register"), json={"nombre": "QA Lockout Core", "email": email, "password": password, "rol": "persona"}, timeout=20)
    assert registered.status_code == 200, registered.text
    try:
        for _ in range(5):
            failed = login(email, "WrongPass!2026")
            assert failed.status_code == 401
        blocked = login(email, password)
        assert blocked.status_code == 401
    finally:
        client = MongoClient(BACKEND_ENV["MONGO_URL"])
        database = client[BACKEND_ENV["DB_NAME"]]
        user = database.users.find_one({"email": email})
        if user:
            person_id = user.get("person_id")
            if person_id:
                for collection in ["person_contacts", "person_activity", "process_enrollments", "cell_memberships"]:
                    database[collection].delete_many({"person_id": person_id})
                if ObjectId.is_valid(person_id):
                    database.persons.delete_one({"_id": ObjectId(person_id)})
            database.users.delete_one({"_id": user["_id"]})
        database.login_attempts.delete_one({"identifier": hashlib.sha256(email.lower().encode()).hexdigest()})
        client.close()
