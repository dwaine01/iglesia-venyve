"""Backend tests for the new Dedication (Presentación de Niños) module (iteration 54).

Covers:
- Access control (pastor / coordinador_general / lider / persona) on events, standalone, certificate.
- Event CRUD (create + list + get).
- Roster: add candidate with child + mother + father, capacity 409, complete.
- Standalone dedication registration (no event) succeeds and returns render data.
- parent_of relationship auto-linking via person_core_expansion.
- Certificate issuance -> 409 without signature, then success once signature configured.
- Public /api/public/dedications/verify/{token} endpoint (valid + invalid).
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
    DEDICATION_CERTIFICATES_ISSUE,
    DEDICATION_EVENTS_MANAGE,
    DEDICATION_READ,
    access_defaults_for_role,
)

FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV["REACT_APP_BACKEND_URL"]).rstrip("/")
CLIENT = MongoClient(BACKEND_ENV["MONGO_URL"])
DB = CLIENT[BACKEND_ENV["DB_NAME"]]
PASSWORD = "QaDedication54!"
TAG = f"qa.dedication54.{uuid4().hex[:6]}"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_person(nombre, apellido, fecha_nacimiento=None):
    person_id = ObjectId()
    now = datetime.now(timezone.utc)
    doc = {
        "_id": person_id,
        "person_number": f"VV-D54-{str(person_id)[-6:]}",
        "nombre": nombre,
        "apellido": apellido,
        "search_key": f"{nombre.lower()} {apellido.lower()}",
        "idempotency_key": f"{TAG}:person:{person_id}",
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    if fecha_nacimiento:
        doc["fecha_nacimiento"] = fecha_nacimiento
    DB.persons.insert_one(doc)
    return str(person_id)


def create_user(label, role="persona", access_level="persona", capabilities=None, scope=None):
    user_id = ObjectId()
    person_id = ObjectId()
    now = datetime.now(timezone.utc)
    email = f"{TAG}.{label}.{uuid4().hex[:6]}@example.com"
    defaults = access_defaults_for_role(access_level)
    DB.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-D54-{str(person_id)[-6:]}",
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
        "access_policy_version": 24,
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
        capabilities=[DEDICATION_READ, DEDICATION_EVENTS_MANAGE, DEDICATION_CERTIFICATES_ISSUE],
        scope={"persons": "all"},
    )
    lider = create_user("lider", role="lider", access_level="lider")
    persona = create_user("persona", role="persona", access_level="persona")

    child_a = create_person("Bebe", "Uno", fecha_nacimiento="2024-03-10")
    child_b = create_person("Bebe", "Dos", fecha_nacimiento="2024-06-20")
    child_c = create_person("Bebe", "Tres", fecha_nacimiento="2024-08-01")
    mother = create_person("Ana", "Madre")
    father = create_person("Luis", "Padre")

    yield {
        "pastor": pastor, "coord": coord, "lider": lider, "persona": persona,
        "child_a": child_a, "child_b": child_b, "child_c": child_c,
        "mother": mother, "father": father,
    }

    # Teardown
    DB.dedication_events.delete_many({"created_by_user_id": {"$in": [pastor["user_id"], coord["user_id"]]}})
    DB.person_dedications.delete_many({"child_person_id": {"$in": [child_a, child_b, child_c]}})
    DB.dedication_document_issuances.delete_many({"child_person_id": {"$in": [child_a, child_b, child_c]}})
    DB.person_relationships.delete_many({"person_a_id": {"$in": [mother, father]}})
    DB.users.delete_many({"email": {"$regex": f"^{TAG}"}})
    DB.persons.delete_many({"idempotency_key": {"$regex": f"^{TAG}"}})


# ---------- Access control ----------
def test_lider_cannot_list_events(state):
    r = requests.get(f"{BASE_URL}/api/dedications/events", headers=auth(state["lider"]["token"]), timeout=30)
    assert r.status_code == 403, r.text


def test_lider_cannot_create_event(state):
    r = requests.post(f"{BASE_URL}/api/dedications/events", headers=auth(state["lider"]["token"]),
                     json={"name": "Presentacion QA", "event_date": "2027-05-12"}, timeout=30)
    assert r.status_code == 403


def test_persona_cannot_manage_events(state):
    r = requests.post(f"{BASE_URL}/api/dedications/events", headers=auth(state["persona"]["token"]),
                     json={"name": "Presentacion QA", "event_date": "2027-05-12"}, timeout=30)
    assert r.status_code == 403


def test_persona_cannot_register_standalone(state):
    r = requests.post(
        f"{BASE_URL}/api/dedications/children",
        headers=auth(state["persona"]["token"]),
        json={"child_person_id": state["child_c"], "dedication_date": "2026-06-01"},
        timeout=30,
    )
    assert r.status_code == 403


def test_public_verification_unauth_access(state):
    r = requests.get(f"{BASE_URL}/api/public/dedications/verify/not-a-real-token", timeout=30)
    assert r.status_code == 200
    assert r.json()["valid"] is False


# ---------- Event CRUD ----------
def test_pastor_creates_and_lists_event(state):
    r = requests.post(f"{BASE_URL}/api/dedications/events", headers=auth(state["pastor"]["token"]),
                     json={"name": "Presentacion Mayo 2026 QA", "event_date": "2026-05-15",
                           "location": "Santuario Central", "officiant_name": "Pastora QA",
                           "capacity": 1, "notes": "Prueba"}, timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Presentacion Mayo 2026 QA"
    assert body["capacity"] == 1
    assert body["status"] == "scheduled"
    state["event_id"] = body["event_id"]

    lst = requests.get(f"{BASE_URL}/api/dedications/events", headers=auth(state["pastor"]["token"]), timeout=30)
    assert lst.status_code == 200
    ids = [e["event_id"] for e in lst.json()["items"]]
    assert state["event_id"] in ids


def test_coordinador_adds_candidate_and_links_parents(state):
    r = requests.post(
        f"{BASE_URL}/api/dedications/events/{state['event_id']}/candidates",
        headers=auth(state["coord"]["token"]),
        json={
            "child_person_id": state["child_a"],
            "mother_person_id": state["mother"],
            "father_person_id": state["father"],
            "presented_by": "Familia QA",
            "witnesses": ["Testigo Uno", "Testigo Dos"],
            "dedication_verse": "Proverbios 22:6",
        },
        timeout=30,
    )
    assert r.status_code == 201, r.text
    roster = r.json()["roster"]
    match = [c for c in roster if c["child_person_id"] == state["child_a"]]
    assert match and match[0]["status"] == "scheduled"
    assert match[0]["mother_person_id"] == state["mother"]
    assert match[0]["father_person_id"] == state["father"]

    # Verify parent_of relationships were created in DB
    mother_rel = DB.person_relationships.find_one(
        {"person_a_id": state["mother"], "person_b_id": state["child_a"], "relation_type": "parent_of"}
    )
    father_rel = DB.person_relationships.find_one(
        {"person_a_id": state["father"], "person_b_id": state["child_a"], "relation_type": "parent_of"}
    )
    assert mother_rel is not None, "mother parent_of relationship not created"
    assert father_rel is not None, "father parent_of relationship not created"


def test_capacity_limit_returns_409(state):
    r = requests.post(
        f"{BASE_URL}/api/dedications/events/{state['event_id']}/candidates",
        headers=auth(state["pastor"]["token"]),
        json={"child_person_id": state["child_b"]},
        timeout=30,
    )
    assert r.status_code == 409, r.text
    assert "cupo" in r.json()["detail"].lower()


def test_complete_candidate(state):
    r = requests.post(
        f"{BASE_URL}/api/dedications/events/{state['event_id']}/candidates/{state['child_a']}/complete",
        headers=auth(state["pastor"]["token"]),
        json={"presented_by": "Familia QA definitiva", "dedication_verse": "Salmos 127:3"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    roster = r.json()["roster"]
    assert any(c["child_person_id"] == state["child_a"] and c["status"] == "completed" for c in roster)


def test_certificate_requires_signature_returns_409(state):
    DB.membership_document_settings.update_one(
        {"settings_id": "primary"}, {"$set": {"signature_file_id": None}}, upsert=True,
    )
    r = requests.post(
        f"{BASE_URL}/api/dedications/children/{state['child_a']}/certificate/issue",
        headers=auth(state["pastor"]["token"]), json={}, timeout=30,
    )
    assert r.status_code == 409, r.text
    assert "firma" in r.json()["detail"].lower()


def test_certificate_success_after_signature_uploaded(state):
    img = Image.new("RGBA", (400, 120), (0, 0, 0, 0))
    for y in range(50, 70):
        for x in range(20, 380):
            img.putpixel((x, y), (0, 0, 0, 255))
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    up = requests.post(
        f"{BASE_URL}/api/membership/settings/signature",
        headers=auth(state["pastor"]["token"]),
        files={"file": ("firma.png", buf, "image/png")}, timeout=30,
    )
    assert up.status_code == 200, up.text

    r = requests.post(
        f"{BASE_URL}/api/dedications/children/{state['child_a']}/certificate/issue",
        headers=auth(state["pastor"]["token"]), json={}, timeout=30,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["action"] == "issued"
    data = body["data"]
    assert data["child"]["person_id"] == state["child_a"]
    assert data["dedication"]["status"] == "completed"
    assert data["dedication"].get("mother_name")
    assert data["dedication"].get("father_name")
    assert data["certificate"]["has_signature"] is True
    assert data["verification_path"].startswith("/verificar/presentacion/")
    state["verification_path"] = data["verification_path"]


def test_public_verification_valid(state):
    token = state["verification_path"].split("/")[-1]
    r = requests.get(f"{BASE_URL}/api/public/dedications/verify/{token}", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is True
    assert "Bebe Uno" in body["child_name"]
    assert body["location"] == "Santuario Central"
    assert body["mother_name"]
    assert body["father_name"]


def test_persona_cannot_issue_certificate(state):
    r = requests.post(
        f"{BASE_URL}/api/dedications/children/{state['child_a']}/certificate/issue",
        headers=auth(state["persona"]["token"]), json={}, timeout=30,
    )
    assert r.status_code == 403


# ---------- Standalone (no event) ----------
def test_standalone_dedication_registers_and_links_parents(state):
    r = requests.post(
        f"{BASE_URL}/api/dedications/children",
        headers=auth(state["pastor"]["token"]),
        json={
            "child_person_id": state["child_c"],
            "mother_person_id": state["mother"],
            "father_person_id": state["father"],
            "dedication_date": "2026-07-04",
            "location": "Casa de Oración",
            "officiant_name": "Pastor QA",
            "presented_by": "Familia standalone",
            "witnesses": ["Testigo A"],
            "dedication_verse": "Deuteronomio 6:6-7",
            "status": "completed",
        },
        timeout=30,
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["child"]["person_id"] == state["child_c"]
    assert data["dedication"]["status"] == "completed"
    assert data["dedication"]["event_id"] is None
    assert data["dedication"]["mother_name"]
    assert data["dedication"]["father_name"]

    # parent_of relationships also created for standalone
    mrel = DB.person_relationships.find_one(
        {"person_a_id": state["mother"], "person_b_id": state["child_c"], "relation_type": "parent_of"}
    )
    assert mrel is not None


def test_dedication_read_returns_persisted_record(state):
    r = requests.get(
        f"{BASE_URL}/api/dedications/children/{state['child_a']}",
        headers=auth(state["pastor"]["token"]), timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["exists"] is True
    assert body["data"]["dedication"]["status"] == "completed"
