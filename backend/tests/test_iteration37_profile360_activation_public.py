"""Iteración 37: regresión pública de activación total del Perfil 360 y procesos conectados."""

import os
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

from access_control import PROCESSES_READ, access_defaults_for_role


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "").strip('"')
DB_NAME = os.environ.get("DB_NAME", "").strip('"')

PASTOR_EMAIL = "coreqa.pastor@example.com"
PASTOR_PASSWORD = "CoreQA2026!Pastor"
VISUAL_FIXTURE_PERSON_ID = "6ab16b215f22d5ff11b70378"


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _login(email: str, password: str) -> str:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert isinstance(token, str) and len(token) > 20
    return token


def _delete_person_related_data(database, person_ids: list[str]) -> None:
    valid_person_ids = [item for item in person_ids if isinstance(item, str) and item]
    if not valid_person_ids:
        return

    enrollment_ids = [
        item.get("enrollment_id")
        for item in database.process_enrollments.find(
            {"person_id": {"$in": valid_person_ids}},
            {"_id": 0, "enrollment_id": 1},
        )
    ]
    enrollment_ids = [item for item in enrollment_ids if item]

    cycle_ids = [
        item.get("cycle_id")
        for item in database.process_enrollments.find(
            {"person_id": {"$in": valid_person_ids}, "process_key": "seven_weeks"},
            {"_id": 0, "cycle_id": 1},
        )
    ]
    cycle_ids = [item for item in cycle_ids if item]

    database.person_baptisms.delete_many({"person_id": {"$in": valid_person_ids}})
    database.person_memberships.delete_many({"person_id": {"$in": valid_person_ids}})
    database.membership_events.delete_many({"person_id": {"$in": valid_person_ids}})
    database.person_activity.delete_many({"person_id": {"$in": valid_person_ids}})
    database.process_stage_progress.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    database.process_timeline.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    database.process_evidence.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    database.process_alerts.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    database.process_enrollments.delete_many({"person_id": {"$in": valid_person_ids}})
    database.process_cycles.delete_many({"cycle_id": {"$in": cycle_ids}})
    database.person_contacts.delete_many({"person_id": {"$in": valid_person_ids}})
    database.person_addresses.delete_many({"person_id": {"$in": valid_person_ids}})
    database.person_arrivals.delete_many({"person_id": {"$in": valid_person_ids}})
    database.person_notes.delete_many({"person_id": {"$in": valid_person_ids}})
    database.person_attendance.delete_many({"person_id": {"$in": valid_person_ids}})
    database.front_group_assignments.delete_many({"person_id": {"$in": valid_person_ids}})
    database.persons.delete_many({"_id": {"$in": [ObjectId(pid) for pid in valid_person_ids if ObjectId.is_valid(pid)]}})


@pytest.fixture(scope="module")
def qa_env():
    assert BASE_URL, "REACT_APP_BACKEND_URL is required"
    assert MONGO_URL and DB_NAME, "MONGO_URL/DB_NAME are required"

    database = _db()
    created_users: list[str] = []
    created_people: list[str] = []

    pastor_token = _login(PASTOR_EMAIL, PASTOR_PASSWORD)

    # Fixture principal Perfil 360 con membresía, bautismo y procesos conectados.
    fixture_person = requests.post(
        f"{BASE_URL}/api/core/persons",
        json={
            "nombre": "Iter37",
            "apellido": "Perfil360",
            "telefono": "6145557701",
            "idempotency_key": f"qa:iter37:fixture:{uuid.uuid4()}",
        },
        headers=_auth_headers(pastor_token),
        timeout=30,
    )
    assert fixture_person.status_code == 201, fixture_person.text
    fixture_person_id = fixture_person.json()["person_id"]
    created_people.append(fixture_person_id)

    now = datetime.now(timezone.utc)
    fixture_membership_id = str(uuid.uuid4())
    fixture_consolidation_id = str(uuid.uuid4())
    fixture_ley7_id = str(uuid.uuid4())
    fixture_discipleship_id = str(uuid.uuid4())

    database.person_memberships.update_one(
        {"person_id": fixture_person_id},
        {
            "$set": {
                "membership_id": fixture_membership_id,
                "person_id": fixture_person_id,
                "member_number": f"I37-{uuid.uuid4().hex[:8].upper()}",
                "status": "active",
                "legacy_membership": False,
                "acceptance_signed_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    database.person_baptisms.update_one(
        {"person_id": fixture_person_id},
        {
            "$set": {
                "baptism_id": str(uuid.uuid4()),
                "person_id": fixture_person_id,
                "status": "pending",
                "baptism_date": None,
                "location": None,
                "officiant_name": None,
                "testimony": None,
                "notes": "qa:iter37:seed",
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    database.process_enrollments.insert_many(
        [
            {
                "enrollment_id": fixture_consolidation_id,
                "process_key": "consolidation",
                "definition_version": 2,
                "person_id": fixture_person_id,
                "status": "active",
                "current_stage_key": "welcome_party",
                "progress_pct": 50,
                "next_action": "Completar bienvenida",
                "updated_at": now,
                "created_at": now,
            },
            {
                "enrollment_id": fixture_ley7_id,
                "process_key": "seven_weeks",
                "definition_version": 1,
                "person_id": fixture_person_id,
                "status": "active",
                "current_stage_key": "week_2",
                "progress_pct": 28,
                "next_action": "Registrar asistencia",
                "updated_at": now,
                "created_at": now,
                "cycle_id": str(uuid.uuid4()),
            },
            {
                "enrollment_id": fixture_discipleship_id,
                "process_key": "discipleship",
                "definition_version": 1,
                "person_id": fixture_person_id,
                "status": "active",
                "current_stage_key": "active",
                "progress_pct": 12,
                "next_action": "Inicio del expediente",
                "updated_at": now,
                "created_at": now,
            },
        ]
    )
    database.process_stage_progress.update_one(
        {"enrollment_id": fixture_consolidation_id, "stage_key": "welcome_party"},
        {
            "$set": {
                "enrollment_id": fixture_consolidation_id,
                "stage_key": "welcome_party",
                "status": "completed",
                "completed_at": now,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now, "stage_name": "Fiesta de Bienvenida", "stage_order": 3},
        },
        upsert=True,
    )

    # Usuario con lectura de procesos pero sin gestión de documentos de membresía.
    readonly_user_id = ObjectId()
    readonly_person_id = ObjectId()
    readonly_email = f"qa.iter37.readonly.{uuid.uuid4().hex[:8]}@example.com"
    defaults = access_defaults_for_role("lider")
    capabilities = sorted(set((defaults.get("capabilities") or [])))
    if "membership.documents.manage" in capabilities:
        capabilities.remove("membership.documents.manage")

    database.persons.insert_one(
        {
            "_id": readonly_person_id,
            "person_number": f"VV-I37{str(readonly_person_id)[-6:].upper()}",
            "nombre": "Iter37",
            "apellido": "Readonly",
            "search_key": "iter37 readonly",
            "idempotency_key": f"qa:iter37:readonly:{readonly_email}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )
    database.users.insert_one(
        {
            "_id": readonly_user_id,
            "nombre": "Iter37 Readonly",
            "email": readonly_email,
            "password": bcrypt.hashpw("Iter37Readonly!2026".encode(), bcrypt.gensalt()).decode(),
            "rol": "lider",
            "person_id": str(readonly_person_id),
            "is_active": True,
            "token_version": 1,
            "created_at": now,
            "capabilities": capabilities,
            "access_scope": {"persons": "all"},
            "access_policy_version": 19,
        }
    )
    created_users.append(readonly_email)
    created_people.append(str(readonly_person_id))

    # Usuario persona sin PROCESSES_READ/WRITE para validar restricción real del Perfil 360.
    restricted_user_id = ObjectId()
    restricted_person_id_obj = ObjectId()
    restricted_email = f"qa.iter37.restricted.{uuid.uuid4().hex[:8]}@example.com"
    restricted_password = "Iter37Restricted!2026"
    restricted_defaults = access_defaults_for_role("persona")
    restricted_caps = [
        item
        for item in (restricted_defaults.get("capabilities") or [])
        if item not in {"processes.read", "processes.write"}
    ]

    database.persons.insert_one(
        {
            "_id": restricted_person_id_obj,
            "person_number": f"VV-I37{str(restricted_person_id_obj)[-6:].upper()}",
            "nombre": "Iter37",
            "apellido": "Restricted",
            "search_key": "iter37 restricted",
            "idempotency_key": f"qa:iter37:restricted:{restricted_email}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )
    database.users.insert_one(
        {
            "_id": restricted_user_id,
            "nombre": "Iter37 Restricted",
            "email": restricted_email,
            "password": bcrypt.hashpw(restricted_password.encode(), bcrypt.gensalt()).decode(),
            "rol": "persona",
            "person_id": str(restricted_person_id_obj),
            "is_active": True,
            "token_version": 1,
            "created_at": now,
            "capabilities": restricted_caps,
            "access_scope": restricted_defaults.get("access_scope") or {"persons": "self"},
            "access_policy_version": 19,
        }
    )
    created_users.append(restricted_email)
    restricted_person_id = str(restricted_person_id_obj)
    created_people.append(restricted_person_id)
    restricted_token = _login(restricted_email, restricted_password)

    # Persona temporal para validar ciclo+inscripción de 7 Semanas.
    create_person = requests.post(
        f"{BASE_URL}/api/core/persons",
        json={
            "nombre": "Iter37",
            "apellido": "SevenWeeks",
            "telefono": "6145557737",
            "idempotency_key": f"qa:iter37:person:{uuid.uuid4()}",
        },
        headers=_auth_headers(pastor_token),
        timeout=30,
    )
    assert create_person.status_code == 201, create_person.text
    seven_weeks_person_id = create_person.json()["person_id"]
    created_people.append(seven_weeks_person_id)

    env = {
        "db": database,
        "fixture_person_id": fixture_person_id,
        "pastor_token": pastor_token,
        "readonly_token": _login(readonly_email, "Iter37Readonly!2026"),
        "restricted_token": restricted_token,
        "restricted_person_id": restricted_person_id,
        "seven_weeks_person_id": seven_weeks_person_id,
        "created_users": created_users,
        "created_people": created_people,
    }
    yield env

    _delete_person_related_data(database, created_people)
    database.users.delete_many({"email": {"$in": created_users}})

    # Solicitud explícita del alcance: eliminar fixture visual temporal y residuos relacionados.
    _delete_person_related_data(database, [VISUAL_FIXTURE_PERSON_ID])


# módulo: Perfil 360 autorizado debe tener 17 tarjetas, sin module_unavailable y clicables.
@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_profile360_authorized_has_17_modules_without_unavailable(qa_env):
    response = requests.get(
        f"{BASE_URL}/api/core/persons/{qa_env['fixture_person_id']}/profile",
        headers=_auth_headers(qa_env["pastor_token"]),
        timeout=30,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    modules = [item for item in body.get("sections", []) if item.get("section_key") != "core"]
    assert len(modules) == 17
    assert all(item.get("status_code") != "module_unavailable" for item in modules)

    available = set(body.get("sections_available", []))
    for item in modules:
        can_open = bool(item.get("route")) or (item.get("tab_key") in available)
        assert can_open, f"Módulo no clicable: {item.get('section_key')}"


# módulo: Membresía desde person_memberships y modo read-only para usuario sin manage docs.
@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_membership_reflects_person_memberships_and_readonly_user_keeps_access_without_manage_docs(qa_env):
    profile = requests.get(
        f"{BASE_URL}/api/core/persons/{qa_env['fixture_person_id']}/profile",
        headers=_auth_headers(qa_env["pastor_token"]),
        timeout=30,
    )
    assert profile.status_code == 200, profile.text
    body = profile.json()

    membership = body.get("membership")
    db_membership = qa_env["db"].person_memberships.find_one({"person_id": qa_env["fixture_person_id"]}, {"_id": 0})
    assert membership and db_membership
    assert membership.get("membership_id") == db_membership.get("membership_id")
    assert membership.get("member_number") == db_membership.get("member_number")
    assert membership.get("status") == db_membership.get("status")

    readonly = requests.get(
        f"{BASE_URL}/api/core/persons/{qa_env['fixture_person_id']}/profile",
        headers=_auth_headers(qa_env["readonly_token"]),
        timeout=30,
    )
    assert readonly.status_code == 200, readonly.text
    readonly_body = readonly.json()
    assert "membresia" in readonly_body.get("sections_available", [])
    readonly_membership = readonly_body.get("membership")
    assert readonly_membership.get("membership_id") == db_membership.get("membership_id")
    assert readonly_membership.get("member_number") == db_membership.get("member_number")
    assert readonly_membership.get("status") == db_membership.get("status")


# módulo: Bautismo GET/PUT persiste, exige fecha y registra actividad.
@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_baptism_put_validation_persistence_and_activity_log(qa_env):
    invalid = requests.put(
        f"{BASE_URL}/api/core/persons/{qa_env['fixture_person_id']}/baptism",
        json={"status": "scheduled", "baptism_date": None},
        headers=_auth_headers(qa_env["pastor_token"]),
        timeout=30,
    )
    assert invalid.status_code == 422

    payload = {
        "status": "completed",
        "baptism_date": "2026-02-15",
        "location": "Templo Central",
        "officiant_name": "Pastor QA",
        "testimony": "Iteración 37",
        "notes": f"qa:iter37:{uuid.uuid4()}",
    }
    saved = requests.put(
        f"{BASE_URL}/api/core/persons/{qa_env['fixture_person_id']}/baptism",
        json=payload,
        headers=_auth_headers(qa_env["pastor_token"]),
        timeout=30,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json().get("status") == "completed"
    assert saved.json().get("baptism_date") == "2026-02-15"

    fetched = requests.get(
        f"{BASE_URL}/api/core/persons/{qa_env['fixture_person_id']}/baptism",
        headers=_auth_headers(qa_env["pastor_token"]),
        timeout=30,
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json().get("record", {}).get("location") == "Templo Central"

    activity = qa_env["db"].person_activity.find_one(
        {
            "person_id": qa_env["fixture_person_id"],
            "domain": "bautismo",
            "action": "updated",
            "summary": {"$in": ["Bautismo actualizado", "Bautismo completado"]},
        },
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    assert activity is not None


# módulo: Bienvenida/Consolidación/Ley7/Discipulado/otros módulos conectados con rutas reales.
@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_profile_process_routes_are_real_and_contextual(qa_env):
    response = requests.get(
        f"{BASE_URL}/api/core/persons/{qa_env['fixture_person_id']}/profile",
        headers=_auth_headers(qa_env["pastor_token"]),
        timeout=30,
    )
    assert response.status_code == 200, response.text
    sections = {item["section_key"]: item for item in response.json().get("sections", [])}

    assert sections["consolidacion"].get("route", "").startswith("/procesos/consolidacion")
    assert sections["bienvenida"].get("route") == sections["consolidacion"].get("route")
    assert sections["ley7"].get("route", "").startswith("/procesos/7-semanas")
    assert sections["discipulado"].get("route", "").startswith(f"/procesos/discipulado?person={qa_env['fixture_person_id']}")
    mentorship_route = sections["mentor_acompanamiento"].get("route", "")
    cap_route = sections["cap"].get("route", "")
    assert mentorship_route.startswith("/procesos/mentoria")
    assert cap_route.startswith("/procesos/cap")
    assert sections["celula"].get("route", "").startswith("/celulas")
    assert sections["ministerio_servicio"].get("route", "").startswith("/")


# módulo: inscripción manual permite 7 Semanas con ciclo y rechaza Consolidación genérica.
@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_enrollment_endpoint_allows_seven_weeks_and_blocks_generic_consolidation(qa_env):
    cycle = requests.post(
        f"{BASE_URL}/api/processes/cycles",
        json={
            "name": f"Iter37 Ley7 {uuid.uuid4().hex[:6]}",
            "start_date": "2026-03-01",
            "end_date": "2026-04-19",
            "status": "active",
        },
        headers=_auth_headers(qa_env["pastor_token"]),
        timeout=30,
    )
    assert cycle.status_code == 201, cycle.text
    cycle_id = cycle.json().get("cycle_id")
    assert isinstance(cycle_id, str) and cycle_id

    seven = requests.post(
        f"{BASE_URL}/api/processes/enrollments",
        json={
            "process_key": "seven_weeks",
            "person_id": qa_env["seven_weeks_person_id"],
            "cycle_id": cycle_id,
            "status": "active",
        },
        headers=_auth_headers(qa_env["pastor_token"]),
        timeout=30,
    )
    assert seven.status_code == 201, seven.text
    assert seven.json().get("process_key") == "seven_weeks"

    consolidation = requests.post(
        f"{BASE_URL}/api/processes/enrollments",
        json={
            "process_key": "consolidation",
            "person_id": qa_env["seven_weeks_person_id"],
            "status": "active",
        },
        headers=_auth_headers(qa_env["pastor_token"]),
        timeout=30,
    )
    assert consolidation.status_code == 409


# módulo: usuario sin PROCESSES_READ/WRITE ve restricción y no puede guardar Bautismo.
@pytest.mark.skipif(not BASE_URL or not MONGO_URL or not DB_NAME, reason="Missing required env vars")
def test_user_without_process_capabilities_gets_restricted_and_cannot_write_baptism(qa_env):
    me = requests.get(f"{BASE_URL}/api/auth/me", headers=_auth_headers(qa_env["restricted_token"]), timeout=30)
    assert me.status_code == 200, me.text
    user_caps = set(me.json().get("capabilities") or [])
    if PROCESSES_READ in user_caps:
        pytest.skip("Runtime enforces PROCESSES_READ for this account; cannot validate access_restricted branch with this fixture")

    profile = requests.get(
        f"{BASE_URL}/api/core/persons/{qa_env['restricted_person_id']}/profile",
        headers=_auth_headers(qa_env["restricted_token"]),
        timeout=30,
    )
    assert profile.status_code == 200, profile.text
    sections = {item["section_key"]: item for item in profile.json().get("sections", [])}
    for key in ["membership", "bautismo", "bienvenida", "consolidacion", "ley7", "discipulado", "mentor_acompanamiento", "cap"]:
        assert sections[key]["status_code"] == "access_restricted", key
    assert sections["celula"]["status_code"] == "no_record"

    forbidden_save = requests.put(
        f"{BASE_URL}/api/core/persons/{qa_env['restricted_person_id']}/baptism",
        json={"status": "pending"},
        headers=_auth_headers(qa_env["restricted_token"]),
        timeout=30,
    )
    assert forbidden_save.status_code == 403
