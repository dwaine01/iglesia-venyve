"""Iteración 49 - Contrato backend Concepto A (documentos, verificación, RBAC)."""

# Módulo: Membresía oficial (emisión/reimpresión), verificación pública y guardas de permisos
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

from access_control import ACCESS_POLICY_VERSION, access_defaults_for_role


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
FIXTURE_PATH = Path("/app/test_reports/redesign_a_fixture.json")


def _load_fixture() -> dict:
    if not FIXTURE_PATH.exists():
        pytest.skip("No existe fixture activo redesign_a_fixture.json")
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    required = ["email", "password", "person_id"]
    for key in required:
        if not data.get(key):
            pytest.skip(f"Fixture incompleto: falta {key}")
    return data


def _login_headers(email: str, password: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    if response.status_code != 200:
        pytest.skip(f"No se pudo autenticar fixture ({response.status_code}): {response.text}")
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _mk_user(email: str, password: str, name: str, role: str, person_id: str) -> dict:
    defaults = access_defaults_for_role(role)
    now = datetime.now(timezone.utc)
    user_id = ObjectId()
    return {
        "_id": user_id,
        "nombre": name,
        "email": email,
        "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "rol": role,
        "access_level": "pastor" if role in {"pastor", "pastora"} else role,
        "person_id": person_id,
        "capabilities": defaults["capabilities"],
        "access_scope": defaults["access_scope"],
        "privilege_groups": defaults.get("privilege_groups", []),
        "is_active": True,
        "token_version": 1,
        "access_policy_version": ACCESS_POLICY_VERSION,
        "must_change_password": False,
        "onboarding_required": False,
        "created_at": now,
        "updated_at": now,
    }


@pytest.fixture(scope="module")
def qa_state():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL no está definido")

    fixture = _load_fixture()
    headers = _login_headers(fixture["email"], fixture["password"])
    suffix = uuid4().hex[:8]

    # Persona/membresía efímera para validar 422 sin foto
    no_photo_person_id = ObjectId()
    no_photo_person_id_str = str(no_photo_person_id)
    no_photo_membership_id = str(uuid4())
    now = datetime.now(timezone.utc)

    DB.persons.insert_one(
        {
            "_id": no_photo_person_id,
            "person_number": f"VV-I49-{suffix.upper()}",
            "nombre": "Miembro",
            "apellido": "SinFoto",
            "search_key": "miembro sinfoto",
            "idempotency_key": f"qa:iter49:nophoto:{suffix}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )
    DB.person_memberships.insert_one(
        {
            "_id": no_photo_membership_id,
            "membership_id": no_photo_membership_id,
            "person_id": no_photo_person_id_str,
            "member_number": f"I49NP-{suffix.upper()}",
            "status": "active",
            "legacy_membership": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    DB.membership_number_registry.insert_one(
        {
            "_id": f"I49NP-{suffix.upper()}",
            "member_number": f"I49NP-{suffix.upper()}",
            "person_id": no_photo_person_id_str,
            "reserved_at": now,
            "source": "iter49",
        }
    )

    # Usuario sin permisos para validar 403
    outsider_person_id = ObjectId()
    outsider_person_id_str = str(outsider_person_id)
    outsider_email = f"qa.iter49.persona.{suffix}@example.com"
    outsider_password = "QaIter49Persona!"

    DB.persons.insert_one(
        {
            "_id": outsider_person_id,
            "person_number": f"VV-I49R-{suffix.upper()}",
            "nombre": "Usuario",
            "apellido": "SinPermiso",
            "search_key": "usuario sinpermiso",
            "idempotency_key": f"qa:iter49:outsider:{suffix}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )
    outsider_user = _mk_user(
        outsider_email,
        outsider_password,
        "Persona Sin Permiso Iter49",
        "persona",
        outsider_person_id_str,
    )
    DB.users.insert_one(outsider_user)
    DB.persons.update_one(
        {"_id": outsider_person_id},
        {"$set": {"auth_user_id": str(outsider_user["_id"]), "updated_at": now}},
    )

    state = {
        "fixture": fixture,
        "headers": headers,
        "outsider_email": outsider_email,
        "outsider_password": outsider_password,
        "no_photo_person_id": no_photo_person_id_str,
        "no_photo_membership_id": no_photo_membership_id,
        "suffix": suffix,
    }
    yield state

    DB.membership_document_issuances.delete_many({"person_id": no_photo_person_id_str})
    DB.membership_events.delete_many({"person_id": no_photo_person_id_str})
    DB.person_activity.delete_many({"person_id": no_photo_person_id_str})
    DB.membership_number_registry.delete_many({"person_id": {"$in": [no_photo_person_id_str]}})
    DB.person_memberships.delete_many({"membership_id": no_photo_membership_id})
    DB.users.delete_many({"email": outsider_email})
    DB.persons.delete_many({"idempotency_key": {"$regex": f"^qa:iter49:(nophoto|outsider):{suffix}$"}})


def test_person_payload_uses_official_number_and_verification_path(qa_state):
    fixture = qa_state["fixture"]
    response = requests.get(
        f"{BASE_URL}/api/membership/persons/{fixture['person_id']}",
        headers=qa_state["headers"],
        timeout=30,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("exists") is True

    data = payload.get("data", {})
    member_number = data.get("membership", {}).get("member_number")
    membership_id = data.get("membership", {}).get("membership_id")
    verification_path = data.get("verification_path")

    assert isinstance(member_number, str) and member_number.strip() != ""
    assert member_number != membership_id
    assert isinstance(verification_path, str) and verification_path.startswith("/verificar/carnet/")


def test_public_verification_matches_member_number_from_private_payload(qa_state):
    fixture = qa_state["fixture"]
    private_resp = requests.get(
        f"{BASE_URL}/api/membership/persons/{fixture['person_id']}",
        headers=qa_state["headers"],
        timeout=30,
    )
    assert private_resp.status_code == 200, private_resp.text
    data = private_resp.json()["data"]
    member_number = data["membership"]["member_number"]
    token = data["verification_path"].rsplit("/", 1)[-1]

    public_resp = requests.get(f"{BASE_URL}/api/public/membership/verify/{token}", timeout=30)
    assert public_resp.status_code == 200, public_resp.text
    public_data = public_resp.json()
    assert public_data.get("status") in {"active", "expired", "inactive", "invalid"}
    assert public_data.get("member_number") == member_number


def test_card_reprint_and_issuance_history_remain_operational(qa_state):
    fixture = qa_state["fixture"]
    issue_resp = requests.post(
        f"{BASE_URL}/api/membership/persons/{fixture['person_id']}/documents/card/issue",
        headers=qa_state["headers"],
        json={"issue_date": "2026-02-10"},
        timeout=30,
    )
    assert issue_resp.status_code == 201, issue_resp.text
    assert issue_resp.json().get("action") in {"issued", "reprinted"}

    history_resp = requests.get(
        f"{BASE_URL}/api/membership/persons/{fixture['person_id']}/issuances",
        headers=qa_state["headers"],
        timeout=30,
    )
    assert history_resp.status_code == 200, history_resp.text
    items = history_resp.json().get("items", [])
    assert any(item.get("document_type") == "card" for item in items)


def test_card_issue_without_photo_remains_blocked_with_422(qa_state):
    response = requests.post(
        f"{BASE_URL}/api/membership/persons/{qa_state['no_photo_person_id']}/documents/card/issue",
        headers=qa_state["headers"],
        json={"issue_date": "2026-02-10"},
        timeout=30,
    )
    assert response.status_code == 422, response.text
    assert "fotograf" in response.json().get("detail", "").lower()


def test_user_without_manage_capability_gets_403_on_issue(qa_state):
    fixture = qa_state["fixture"]
    outsider_headers = _login_headers(qa_state["outsider_email"], qa_state["outsider_password"])
    response = requests.post(
        f"{BASE_URL}/api/membership/persons/{fixture['person_id']}/documents/card/issue",
        headers=outsider_headers,
        json={"issue_date": "2026-02-10"},
        timeout=30,
    )
    assert response.status_code == 403, response.text
