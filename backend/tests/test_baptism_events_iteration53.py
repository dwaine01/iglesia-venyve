"""Backend tests for the new Baptism Events + Certificate module (iteration 53).

Covers:
- Access control (pastor / coordinador_general / lider / persona).
- Event CRUD (create + list + get).
- Roster: search a real person, add candidate, capacity 409, remove, complete.
- Certificate issuance -> 409 without signature, then success once signature configured.
- Public /api/public/baptism/verify/{token} endpoint.
"""
import io
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from PIL import Image
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from access_control import (  # noqa: E402
    BAPTISM_CERTIFICATES_ISSUE,
    BAPTISM_EVENTS_MANAGE,
    BAPTISM_READ,
    BAPTISM_WRITE,
    access_defaults_for_role,
)

FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV["REACT_APP_BACKEND_URL"]).rstrip("/")
CLIENT = MongoClient(BACKEND_ENV["MONGO_URL"])
DB = CLIENT[BACKEND_ENV["DB_NAME"]]
PASSWORD = "QaBaptism53!"
TAG = f"qa.baptism53.{uuid4().hex[:6]}"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_person(nombre, apellido):
    person_id = ObjectId()
    now = datetime.now(timezone.utc)
    DB.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-B53-{str(person_id)[-6:]}",
        "nombre": nombre,
        "apellido": apellido,
        "search_key": f"{nombre.lower()} {apellido.lower()}",
        "idempotency_key": f"{TAG}:person:{person_id}",
        "version": 1,
        "created_at": now,
        "updated_at": now,
    })
    return str(person_id)


def create_user(label, role="persona", access_level="persona", capabilities=None, scope=None):
    user_id = ObjectId()
    person_id = ObjectId()
    now = datetime.now(timezone.utc)
    email = f"{TAG}.{label}.{uuid4().hex[:6]}@example.com"
    defaults = access_defaults_for_role(access_level)
    DB.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-B53-{str(person_id)[-6:]}",
        "nombre": "QA",
        "apellido": label.title(),
        "search_key": f"qa {label}",
        "idempotency_key": f"{TAG}:user:{email}",
        "auth_user_id": str(user_id),
        "version": 1,
        "created_at": now,
        "updated_at": now,
    })
    DB.users.insert_one({
        "_id": user_id,
        "nombre": f"QA {label.title()}",
        "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role,
        "access_level": access_level,
        "person_id": str(person_id),
        "capabilities": capabilities if capabilities is not None else defaults["capabilities"],
        "access_scope": scope or defaults["access_scope"],
        "privilege_groups": [],
        "is_active": True,
        "token_version": 1,
        "access_policy_version": 23,
        "must_change_password": False,
        "onboarding_required": False,
        "created_at": now,
        "updated_at": now,
    })
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30)
    assert response.status_code == 200, response.text
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email, "token": response.json()["token"]}


@pytest.fixture(scope="module")
def state():
    pastor = create_user("pastor", role="pastora", access_level="pastor")
    coord = create_user(
        "coord",
        role="lider",
        access_level="coordinador_general",
        capabilities=[BAPTISM_READ, BAPTISM_WRITE, BAPTISM_EVENTS_MANAGE, BAPTISM_CERTIFICATES_ISSUE],
        scope={"persons": "all"},
    )
    lider = create_user("lider", role="lider", access_level="lider")
    persona = create_user("persona", role="persona", access_level="persona")
    candidate_a = create_person("Juan", "Perez")
    candidate_b = create_person("Maria", "Lopez")
    yield {
        "pastor": pastor, "coord": coord, "lider": lider, "persona": persona,
        "cand_a": candidate_a, "cand_b": candidate_b,
    }

    # Teardown
    DB.baptism_events.delete_many({"created_by_user_id": {"$in": [pastor["user_id"], coord["user_id"]]}})
    DB.person_baptisms.delete_many({"person_id": {"$in": [candidate_a, candidate_b]}})
    DB.baptism_document_issuances.delete_many({"person_id": {"$in": [candidate_a, candidate_b]}})
    DB.users.delete_many({"email": {"$regex": f"^{TAG}"}})
    DB.persons.delete_many({"idempotency_key": {"$regex": f"^{TAG}"}})


# ---------- Access control ----------
def test_lider_cannot_list_events(state):
    r = requests.get(f"{BASE_URL}/api/baptism/events", headers=auth(state["lider"]["token"]), timeout=30)
    assert r.status_code == 403, r.text


def test_lider_cannot_create_event(state):
    r = requests.post(f"{BASE_URL}/api/baptism/events", headers=auth(state["lider"]["token"]),
                     json={"name": "Bautismo QA", "event_date": "2027-05-12"}, timeout=30)
    assert r.status_code == 403


def test_persona_cannot_manage_events(state):
    r = requests.post(f"{BASE_URL}/api/baptism/events", headers=auth(state["persona"]["token"]),
                     json={"name": "Bautismo QA", "event_date": "2027-05-12"}, timeout=30)
    assert r.status_code == 403


# ---------- Event CRUD ----------
def test_pastor_creates_and_lists_event(state):
    r = requests.post(f"{BASE_URL}/api/baptism/events", headers=auth(state["pastor"]["token"]),
                     json={"name": "Bautismo Diciembre 2026 QA", "event_date": "2026-12-15",
                           "location": "Santuario Central", "officiant_name": "Pastora QA",
                           "capacity": 1, "notes": "Prueba"}, timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Bautismo Diciembre 2026 QA"
    assert body["capacity"] == 1
    assert body["status"] == "scheduled"
    state["event_id"] = body["event_id"]

    lst = requests.get(f"{BASE_URL}/api/baptism/events", headers=auth(state["pastor"]["token"]), timeout=30)
    assert lst.status_code == 200
    ids = [e["event_id"] for e in lst.json()["items"]]
    assert state["event_id"] in ids


def test_coordinador_can_add_candidate(state):
    # coord has BAPTISM_EVENTS_MANAGE
    r = requests.post(f"{BASE_URL}/api/baptism/events/{state['event_id']}/candidates",
                     headers=auth(state["coord"]["token"]),
                     json={"person_id": state["cand_a"]}, timeout=30)
    assert r.status_code == 201, r.text
    roster = r.json()["roster"]
    assert any(c["person_id"] == state["cand_a"] and c["status"] == "scheduled" for c in roster)


def test_capacity_limit_returns_409(state):
    r = requests.post(f"{BASE_URL}/api/baptism/events/{state['event_id']}/candidates",
                     headers=auth(state["pastor"]["token"]),
                     json={"person_id": state["cand_b"]}, timeout=30)
    assert r.status_code == 409, r.text
    assert "cupo" in r.json()["detail"].lower()


def test_remove_candidate(state):
    # remove cand_a temporarily then re-add
    r = requests.delete(f"{BASE_URL}/api/baptism/events/{state['event_id']}/candidates/{state['cand_a']}",
                        headers=auth(state["pastor"]["token"]), timeout=30)
    assert r.status_code == 200
    assert not any(c["person_id"] == state["cand_a"] for c in r.json()["roster"])
    # re-add
    r2 = requests.post(f"{BASE_URL}/api/baptism/events/{state['event_id']}/candidates",
                     headers=auth(state["pastor"]["token"]),
                     json={"person_id": state["cand_a"]}, timeout=30)
    assert r2.status_code == 201


def test_complete_candidate(state):
    r = requests.post(f"{BASE_URL}/api/baptism/events/{state['event_id']}/candidates/{state['cand_a']}/complete",
                     headers=auth(state["pastor"]["token"]),
                     json={"testimony": "Testimonio QA", "notes": "OK"}, timeout=30)
    assert r.status_code == 200, r.text
    roster = r.json()["roster"]
    assert any(c["person_id"] == state["cand_a"] and c["status"] == "completed" for c in roster)


def test_certificate_requires_signature_returns_409(state):
    # Ensure no signature configured yet
    DB.membership_document_settings.update_one(
        {"settings_id": "primary"}, {"$set": {"signature_file_id": None}}, upsert=True,
    )
    r = requests.post(f"{BASE_URL}/api/baptism/persons/{state['cand_a']}/certificate/issue",
                     headers=auth(state["pastor"]["token"]), json={}, timeout=30)
    assert r.status_code == 409, r.text
    assert "firma" in r.json()["detail"].lower()


def test_certificate_success_after_signature_uploaded(state):
    # Upload real transparent PNG (>=200x80)
    img = Image.new("RGBA", (400, 120), (0, 0, 0, 0))
    for y in range(50, 70):
        for x in range(20, 380):
            img.putpixel((x, y), (0, 0, 0, 255))
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    up = requests.post(f"{BASE_URL}/api/membership/settings/signature",
                      headers=auth(state["pastor"]["token"]),
                      files={"file": ("firma.png", buf, "image/png")}, timeout=30)
    assert up.status_code == 200, up.text

    r = requests.post(f"{BASE_URL}/api/baptism/persons/{state['cand_a']}/certificate/issue",
                     headers=auth(state["pastor"]["token"]), json={}, timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["action"] == "issued"
    data = body["data"]
    assert data["person"]["person_id"] == state["cand_a"]
    assert data["baptism"]["status"] == "completed"
    assert data["certificate"]["has_signature"] is True
    assert data["verification_path"].startswith("/verificar/bautismo/")
    state["verification_path"] = data["verification_path"]


def test_public_verification_valid(state):
    token = state["verification_path"].split("/")[-1]
    r = requests.get(f"{BASE_URL}/api/public/baptism/verify/{token}", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is True
    assert "Juan Perez" in body["member_name"]
    assert body["location"] == "Santuario Central"


def test_public_verification_invalid_token(state):
    r = requests.get(f"{BASE_URL}/api/public/baptism/verify/not-a-real-token", timeout=30)
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_persona_cannot_issue_certificate(state):
    r = requests.post(f"{BASE_URL}/api/baptism/persons/{state['cand_a']}/certificate/issue",
                     headers=auth(state["persona"]["token"]), json={}, timeout=30)
    assert r.status_code == 403


def test_person_baptism_document_read(state):
    r = requests.get(f"{BASE_URL}/api/baptism/persons/{state['cand_a']}",
                    headers=auth(state["pastor"]["token"]), timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body["exists"] is True
    assert body["data"]["baptism"]["status"] == "completed"
