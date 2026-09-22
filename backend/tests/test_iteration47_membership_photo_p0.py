"""Iteración 47 - Contrato P0 foto canónica ↔ emisión de carnet (API pública)."""

# Módulo: auth + Persona 360 + Membresía + RBAC para emisión de carnet
import base64
import os
from datetime import datetime, timezone
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
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV["REACT_APP_BACKEND_URL"]).rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


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


def _auth_headers(email: str, password: str) -> dict:
    login = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


@pytest.fixture(scope="module")
def qa_state():
    suffix = uuid4().hex[:10]
    now = datetime.now(timezone.utc)

    pastor_person_id = ObjectId()
    member_photo_person_id = ObjectId()
    member_no_photo_person_id = ObjectId()
    outsider_person_id = ObjectId()

    pastor_email = f"qa.photo.pastora.{suffix}@example.com"
    outsider_email = f"qa.photo.persona.{suffix}@example.com"
    pastor_password = "QaPhotoP0!Pastora47"
    outsider_password = "QaPhotoP0!Persona47"

    person_docs = [
        {
            "_id": pastor_person_id,
            "person_number": f"VV-P47-{suffix[:6]}",
            "nombre": "Pastora",
            "apellido": "Contrato QA",
            "search_key": "pastora contrato qa",
            "idempotency_key": f"qa:iter47:pastora:{suffix}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": member_photo_person_id,
            "person_number": f"VV-M47P-{suffix[:5]}",
            "nombre": "Miembro",
            "apellido": "Con Foto",
            "search_key": "miembro con foto",
            "idempotency_key": f"qa:iter47:member-photo:{suffix}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": member_no_photo_person_id,
            "person_number": f"VV-M47N-{suffix[:5]}",
            "nombre": "Miembro",
            "apellido": "Sin Foto",
            "search_key": "miembro sin foto",
            "idempotency_key": f"qa:iter47:member-nophoto:{suffix}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": outsider_person_id,
            "person_number": f"VV-M47R-{suffix[:5]}",
            "nombre": "Usuario",
            "apellido": "SinPermiso",
            "search_key": "usuario sinpermiso",
            "idempotency_key": f"qa:iter47:outsider:{suffix}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        },
    ]
    DB.persons.insert_many(person_docs)

    pastor_person_str = str(pastor_person_id)
    outsider_person_str = str(outsider_person_id)
    pastor_user = _mk_user(pastor_email, pastor_password, "Pastora Contrato QA", "pastora", pastor_person_str)
    outsider_user = _mk_user(outsider_email, outsider_password, "Persona Sin Permiso QA", "persona", outsider_person_str)
    DB.users.insert_many([pastor_user, outsider_user])
    DB.persons.update_one({"_id": pastor_person_id}, {"$set": {"auth_user_id": str(pastor_user["_id"]), "updated_at": now}})
    DB.persons.update_one({"_id": outsider_person_id}, {"$set": {"auth_user_id": str(outsider_user["_id"]), "updated_at": now}})

    membership_photo_id = str(uuid4())
    membership_no_photo_id = str(uuid4())
    member_photo_person_str = str(member_photo_person_id)
    member_no_photo_person_str = str(member_no_photo_person_id)

    DB.person_memberships.insert_many([
        {
            "_id": membership_photo_id,
            "membership_id": membership_photo_id,
            "person_id": member_photo_person_str,
            "member_number": f"I47P-{suffix.upper()}",
            "status": "active",
            "legacy_membership": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": membership_no_photo_id,
            "membership_id": membership_no_photo_id,
            "person_id": member_no_photo_person_str,
            "member_number": f"I47N-{suffix.upper()}",
            "status": "active",
            "legacy_membership": True,
            "created_at": now,
            "updated_at": now,
        },
    ])
    DB.membership_number_registry.insert_many([
        {"_id": f"I47P-{suffix.upper()}", "member_number": f"I47P-{suffix.upper()}", "person_id": member_photo_person_str, "reserved_at": now, "source": "iter47"},
        {"_id": f"I47N-{suffix.upper()}", "member_number": f"I47N-{suffix.upper()}", "person_id": member_no_photo_person_str, "reserved_at": now, "source": "iter47"},
    ])

    state = {
        "suffix": suffix,
        "pastor_email": pastor_email,
        "pastor_password": pastor_password,
        "outsider_email": outsider_email,
        "outsider_password": outsider_password,
        "member_photo_person_id": member_photo_person_str,
        "member_no_photo_person_id": member_no_photo_person_str,
        "membership_photo_id": membership_photo_id,
        "membership_no_photo_id": membership_no_photo_id,
        "upload_ids": [],
    }

    yield state

    # Cleanup QA: usuarios, Personas, membresías, fotos, emisiones, eventos y cargas.
    DB.person_photo_chunks.delete_many({"upload_id": {"$in": state["upload_ids"]}})
    DB.person_photo_uploads.delete_many({"person_id": {"$in": [state["member_photo_person_id"], state["member_no_photo_person_id"]]}})
    DB.person_photos.delete_many({"person_id": {"$in": [state["member_photo_person_id"], state["member_no_photo_person_id"]]}})
    DB.membership_document_issuances.delete_many({"person_id": {"$in": [state["member_photo_person_id"], state["member_no_photo_person_id"]]}})
    DB.membership_events.delete_many({"person_id": {"$in": [state["member_photo_person_id"], state["member_no_photo_person_id"]]}})
    DB.person_activity.delete_many({"person_id": {"$in": [state["member_photo_person_id"], state["member_no_photo_person_id"]]}})
    DB.membership_number_registry.delete_many({"person_id": {"$in": [state["member_photo_person_id"], state["member_no_photo_person_id"]]}})
    DB.person_memberships.delete_many({"_id": {"$in": [state["membership_photo_id"], state["membership_no_photo_id"]]}})
    DB.users.delete_many({"email": {"$in": [state["pastor_email"], state["outsider_email"]]}})
    DB.persons.delete_many({"idempotency_key": {"$regex": f"^qa:iter47:.*:{state['suffix']}$"}})


def test_contract_photo_upload_visible_and_card_issue_with_historical_photo(qa_state):
    """Flujo positivo: upload+chunk+complete -> header/photo ok -> emitir 201 aun sin is_current."""
    headers = _auth_headers(qa_state["pastor_email"], qa_state["pastor_password"])
    member_id = qa_state["member_photo_person_id"]

    init_resp = requests.post(
        f"{BASE_URL}/api/core/persons/{member_id}/photo/uploads",
        headers=headers,
        json={"content_type": "image/png", "total_size": len(PNG_1X1), "total_chunks": 1},
        timeout=30,
    )
    assert init_resp.status_code == 201, init_resp.text
    upload_id = init_resp.json()["upload_id"]
    qa_state["upload_ids"].append(upload_id)

    chunk_resp = requests.put(
        f"{BASE_URL}/api/core/persons/{member_id}/photo/uploads/{upload_id}/chunks/0",
        headers={**headers, "Content-Type": "application/octet-stream"},
        data=PNG_1X1,
        timeout=30,
    )
    assert chunk_resp.status_code == 200, chunk_resp.text

    complete_resp = requests.post(
        f"{BASE_URL}/api/core/persons/{member_id}/photo/uploads/{upload_id}/complete",
        headers=headers,
        json={},
        timeout=30,
    )
    assert complete_resp.status_code == 200, complete_resp.text
    stored = DB.person_photos.find_one({"person_id": member_id})
    assert stored is not None and stored.get("is_current") is True

    profile_resp = requests.get(f"{BASE_URL}/api/core/persons/{member_id}/profile", headers=headers, timeout=30)
    photo_resp = requests.get(f"{BASE_URL}/api/core/persons/{member_id}/photo", headers=headers, timeout=30)
    assert profile_resp.status_code == 200, profile_resp.text
    assert profile_resp.json()["header"]["photo_available"] is True
    assert photo_resp.status_code == 200 and photo_resp.content == PNG_1X1

    DB.person_photos.update_one({"person_id": member_id}, {"$unset": {"is_current": ""}})
    issued = requests.post(
        f"{BASE_URL}/api/membership/persons/{member_id}/documents/card/issue",
        headers=headers,
        json={"issue_date": "2026-02-01"},
        timeout=30,
    )
    assert issued.status_code == 201, issued.text
    payload = issued.json()
    assert payload["data"]["person"]["has_profile_photo"] is True

    history = requests.get(f"{BASE_URL}/api/membership/persons/{member_id}/issuances", headers=headers, timeout=30)
    assert history.status_code == 200, history.text
    items = history.json().get("items", [])
    assert any(item.get("document_type") == "card" for item in items)


def test_negative_person_without_photo_still_gets_422_on_issue(qa_state):
    """Flujo negativo: persona sin documento en person_photos devuelve 422."""
    headers = _auth_headers(qa_state["pastor_email"], qa_state["pastor_password"])
    member_id = qa_state["member_no_photo_person_id"]
    issued = requests.post(
        f"{BASE_URL}/api/membership/persons/{member_id}/documents/card/issue",
        headers=headers,
        json={"issue_date": "2026-02-01"},
        timeout=30,
    )
    assert issued.status_code == 422, issued.text
    assert "fotograf" in issued.json().get("detail", "").lower()


def test_rbac_user_without_manage_or_institutional_authority_gets_403(qa_state):
    """RBAC: usuario sin membership.documents.manage y sin autoridad institucional recibe 403."""
    outsider_headers = _auth_headers(qa_state["outsider_email"], qa_state["outsider_password"])
    member_id = qa_state["member_photo_person_id"]
    response = requests.post(
        f"{BASE_URL}/api/membership/persons/{member_id}/documents/card/issue",
        headers=outsider_headers,
        json={"issue_date": "2026-02-01"},
        timeout=30,
    )
    assert response.status_code == 403, response.text
