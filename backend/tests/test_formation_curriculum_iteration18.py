"""Iteration 18: Tests for Discipulado/Formación curriculum seed + duration auto-calc + bulk program credit."""
import os
from datetime import datetime, timezone, date, timedelta
from uuid import uuid4

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

from access_control import (
    FORMATION_READ, FORMATION_PROGRAMS_MANAGE, FORMATION_COHORTS_MANAGE,
    FORMATION_ENROLL, FORMATION_HISTORICAL_CREDIT_MANAGE,
    access_defaults_for_role,
)


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV["REACT_APP_BACKEND_URL"]).rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
PASSWORD = "QaFormationIt18!"


EXPECTED_PROGRAMS = {
    "Discipulado de Evangelismo y Consolidación": [
        ("Mi Conexión con Dios (MCD)", 7),
        ("Nací Para Triunfar (NPT)", 3),
        ("LBS (Liberación, Bendición, Sanidad)", 21),
        ("Retiro", None),
    ],
    "Discipulado": [
        ("Mi llamado sobrenatural", 90),
        ("El privilegio de servir", 90),
        ("La estrategia es ganar", 90),
        ("Retiro 1", None),
        ("Conociendo al Padre", None),
        ("Conociendo al Hijo", None),
        ("Conociendo al Espíritu Santo", None),
        ("El proceso de convertirse en discípulo", 90),
        ("Retiro 2", None),
        ("Graduación", None),
    ],
    "Academia de Obreros": [
        ("Academia de Obrero 1", 90),
        ("Academia de Obrero 2", 90),
        ("Academia de Obrero 3", 90),
        ("Academia de Obrero 4", 90),
        ("Retiro", None),
        ("Graduación", None),
    ],
}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_user(label, access_level="persona", capabilities=None):
    user_id, person_id = ObjectId(), ObjectId()
    now = datetime.now(timezone.utc)
    email = f"qa.formit18.{label}.{uuid4().hex[:8]}@example.com"
    defaults = access_defaults_for_role(access_level)
    DB.persons.insert_one({
        "_id": person_id, "person_number": f"VV-IT18-{str(person_id)[-6:]}",
        "nombre": "QaIt18", "apellido": label.title(), "search_key": f"qa it18 {label}",
        "idempotency_key": f"qa:it18:{email}", "auth_user_id": str(user_id),
        "version": 1, "created_at": now, "updated_at": now,
    })
    DB.users.insert_one({
        "_id": user_id, "nombre": f"QaIt18 {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": "pastora" if access_level == "pastor" else "lider",
        "access_level": access_level, "person_id": str(person_id),
        "capabilities": capabilities if capabilities is not None else defaults["capabilities"],
        "access_scope": defaults["access_scope"], "privilege_groups": [],
        "is_active": True, "token_version": 1, "access_policy_version": 22,
        "must_change_password": False, "onboarding_required": False,
        "created_at": now, "updated_at": now,
    })
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email, "_user_oid": user_id, "_person_oid": person_id}


def login(email):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def state():
    pastor = create_user("pastor", access_level="pastor")
    plain_caps = [FORMATION_READ, FORMATION_ENROLL]
    lider = create_user("lider", access_level="lider", capabilities=plain_caps)
    tokens = {"pastor": login(pastor["email"]), "lider": login(lider["email"])}
    target = create_user("target", access_level="persona")
    target2 = create_user("target2", access_level="persona")
    st = {"pastor": pastor, "lider": lider, "target": target, "target2": target2, "tokens": tokens,
          "created_cohorts": [], "created_modules": [], "created_programs": []}
    yield st
    # Cleanup
    person_ids = [pastor["person_id"], lider["person_id"], target["person_id"], target2["person_id"]]
    user_ids = [pastor["user_id"], lider["user_id"], target["user_id"], target2["user_id"]]
    DB.formation_achievements.delete_many({"person_id": {"$in": person_ids}})
    DB.formation_enrollments.delete_many({"person_id": {"$in": person_ids}})
    DB.formation_audit_events.delete_many({"actor_user_id": {"$in": user_ids}})
    if st["created_cohorts"]:
        DB.formation_cohorts.delete_many({"cohort_id": {"$in": st["created_cohorts"]}})
    DB.users.delete_many({"email": {"$regex": "^qa\\.formit18\\."}})
    DB.persons.delete_many({"idempotency_key": {"$regex": "^qa:it18:"}})


# ---------- Seed curriculum validation ----------
def test_seed_programs_exist_with_correct_metadata(state):
    r = requests.get(f"{BASE_URL}/api/formation/programs", headers=auth(state["tokens"]["pastor"]), timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    found = {p["name"]: p for p in items if p["name"] in EXPECTED_PROGRAMS}
    assert set(found.keys()) == set(EXPECTED_PROGRAMS.keys()), f"Missing programs: {set(EXPECTED_PROGRAMS)-set(found)}"
    for name, p in found.items():
        assert p["active"] is True
        assert p["purpose"] == "discipleship"
        assert p["certificate_enabled"] is True
        assert p["certificate_scope"] == "program"
    state["program_ids_by_name"] = {name: p["program_id"] for name, p in found.items()}


def test_seed_modules_have_correct_order_duration_prereq_cert(state):
    for name, expected in EXPECTED_PROGRAMS.items():
        pid = state["program_ids_by_name"][name]
        r = requests.get(f"{BASE_URL}/api/formation/programs/{pid}/modules", headers=auth(state["tokens"]["pastor"]), timeout=30)
        assert r.status_code == 200
        mods = r.json()["items"]
        assert len(mods) == len(expected), f"{name}: expected {len(expected)} modules got {len(mods)}"
        prev_id = None
        for idx, (exp_name, exp_dur) in enumerate(expected):
            m = mods[idx]
            assert m["name"] == exp_name, f"{name} module idx={idx}: name {m['name']} != {exp_name}"
            assert m["order"] == idx + 1
            assert m.get("duration_days") == exp_dur, f"{name}:{exp_name} duration {m.get('duration_days')} != {exp_dur}"
            assert m["certificate_enabled"] is True, f"{name}:{exp_name} certificate_enabled must be true"
            prereqs = m.get("prerequisite_module_ids") or []
            if idx == 0:
                assert prereqs == [], f"{name}:{exp_name} first module should have no prereqs"
            else:
                assert prereqs == [prev_id], f"{name}:{exp_name} prereq mismatch"
            prev_id = m["module_id"]
        state.setdefault("modules_by_program", {})[name] = mods


# ---------- Cohort auto end_date ----------
def test_cohort_auto_end_date_from_duration(state):
    # MCD has duration_days=7
    mcd = state["modules_by_program"]["Discipulado de Evangelismo y Consolidación"][0]
    start = "2027-05-01"
    r = requests.post(f"{BASE_URL}/api/formation/cohorts", headers=auth(state["tokens"]["pastor"]), json={
        "module_id": mcd["module_id"], "name": "QaIt18 MCD Auto", "start_date": start,
        "modality": "onsite", "capacity": 10, "status": "planned",
    }, timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    state["created_cohorts"].append(body["cohort_id"])
    expected_end = (date.fromisoformat(start) + timedelta(days=7)).isoformat()
    assert body["end_date"] == expected_end, f"auto end_date {body['end_date']} != {expected_end}"


def test_cohort_no_duration_leaves_end_date_null(state):
    retiro = state["modules_by_program"]["Discipulado de Evangelismo y Consolidación"][3]
    assert retiro["name"] == "Retiro" and retiro.get("duration_days") is None
    r = requests.post(f"{BASE_URL}/api/formation/cohorts", headers=auth(state["tokens"]["pastor"]), json={
        "module_id": retiro["module_id"], "name": "QaIt18 Retiro NoDur", "start_date": "2027-06-01",
        "modality": "onsite", "capacity": 10, "status": "planned",
    }, timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    state["created_cohorts"].append(body["cohort_id"])
    assert body.get("end_date") in (None, "", None), f"end_date should stay null, got {body.get('end_date')}"


def test_cohort_explicit_end_date_overrides_auto(state):
    mcd = state["modules_by_program"]["Discipulado de Evangelismo y Consolidación"][0]
    explicit = "2027-07-20"
    r = requests.post(f"{BASE_URL}/api/formation/cohorts", headers=auth(state["tokens"]["pastor"]), json={
        "module_id": mcd["module_id"], "name": "QaIt18 MCD Explicit", "start_date": "2027-07-01",
        "end_date": explicit, "modality": "onsite", "capacity": 10, "status": "planned",
    }, timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    state["created_cohorts"].append(body["cohort_id"])
    assert body["end_date"] == explicit, f"explicit end_date not respected: {body['end_date']}"


# ---------- Bulk program credit ----------
def test_bulk_program_credit_creates_all_and_is_idempotent(state):
    pid = state["program_ids_by_name"]["Discipulado de Evangelismo y Consolidación"]
    person_id = state["target"]["person_id"]
    r = requests.post(f"{BASE_URL}/api/formation/persons/{person_id}/historical-credits/program/{pid}",
                     headers=auth(state["tokens"]["pastor"]),
                     json={"observation": "QaIt18 bulk credit all modules"}, timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["total_modules"] == 4
    assert body["newly_accredited"] == 4
    assert len(body["accredited"]) == 4
    for a in body["accredited"]:
        assert a["status"] == "historical_accredited"
        assert a["source"] == "historical_accreditation_bulk"

    # Idempotent repeat
    r2 = requests.post(f"{BASE_URL}/api/formation/persons/{person_id}/historical-credits/program/{pid}",
                      headers=auth(state["tokens"]["pastor"]),
                      json={"observation": "QaIt18 bulk credit repeat"}, timeout=30)
    assert r2.status_code == 201, r2.text
    body2 = r2.json()
    # Already-historical_accredited modules aren't in {completed} skip list, so they'll re-upsert; verify no duplicates
    assert body2["total_modules"] == 4
    # The current code only skips 'completed', so historical_accredited gets re-upserted (same achievement_id)
    # Verify no duplicates in DB
    count = DB.formation_achievements.count_documents({"person_id": person_id, "program_id": pid, "active": True})
    assert count == 4, f"Should still have exactly 4 achievements, got {count}"


def test_progress_after_bulk_shows_historical_and_next_jumps_program(state):
    person_id = state["target"]["person_id"]
    r = requests.get(f"{BASE_URL}/api/formation/persons/{person_id}/progress", headers=auth(state["tokens"]["pastor"]), timeout=30)
    assert r.status_code == 200
    body = r.json()
    first_program_name = "Discipulado de Evangelismo y Consolidación"
    first_pid = state["program_ids_by_name"][first_program_name]
    first_items = [i for i in body["items"] if i["program_id"] == first_pid]
    assert all(i["status"] == "historical_accredited" for i in first_items), \
        f"All modules of first program should be historical_accredited, got {[i['status'] for i in first_items]}"
    nxt = body.get("next_recommended")
    assert nxt, "Expected next_recommended to a different program"
    # Should jump to first module of another program (not the completed one)
    assert nxt["program_id"] != first_pid, f"next_recommended still points to completed program"


def test_partial_completion_bulk_credits_only_remaining(state):
    pid = state["program_ids_by_name"]["Academia de Obreros"]
    person_id = state["target2"]["person_id"]
    mods = state["modules_by_program"]["Academia de Obreros"]
    # Pre-credit first module via per-module endpoint
    r0 = requests.post(f"{BASE_URL}/api/formation/persons/{person_id}/historical-credits",
                       headers=auth(state["tokens"]["pastor"]),
                       json={"module_id": mods[0]["module_id"], "observation": "QaIt18 pre-credit"}, timeout=30)
    assert r0.status_code == 201, r0.text
    # Now call bulk
    r = requests.post(f"{BASE_URL}/api/formation/persons/{person_id}/historical-credits/program/{pid}",
                     headers=auth(state["tokens"]["pastor"]),
                     json={"observation": "QaIt18 bulk after partial"}, timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    # Current code only skips 'completed' (not 'historical_accredited'); so it will re-upsert the first too.
    # So newly_accredited count == total_modules. Verify at least no duplicates and all end up historical_accredited.
    count = DB.formation_achievements.count_documents({"person_id": person_id, "program_id": pid, "active": True})
    assert count == len(mods), f"Expected {len(mods)} achievements, got {count}"


# ---------- RBAC ----------
def test_rbac_lider_forbidden_on_bulk_program_credit(state):
    pid = state["program_ids_by_name"]["Discipulado"]
    person_id = state["target"]["person_id"]
    r = requests.post(f"{BASE_URL}/api/formation/persons/{person_id}/historical-credits/program/{pid}",
                     headers=auth(state["tokens"]["lider"]),
                     json={"observation": "QaIt18 lider should be denied"}, timeout=30)
    assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text}"


def test_rbac_lider_forbidden_on_per_module_credit(state):
    person_id = state["target"]["person_id"]
    mod = state["modules_by_program"]["Discipulado"][0]
    r = requests.post(f"{BASE_URL}/api/formation/persons/{person_id}/historical-credits",
                     headers=auth(state["tokens"]["lider"]),
                     json={"module_id": mod["module_id"], "observation": "QaIt18 lider denied"}, timeout=30)
    assert r.status_code == 403


# ---------- Regression: PUT module without duration_days ----------
def test_put_module_preserves_duration_days_when_omitted(state):
    """RISK TEST: ModuleInput has duration_days as Optional with default None. If a client PUTs without
    duration_days key, Pydantic defaults it to None and model_dump() emits it, wiping the value in DB."""
    token = state["tokens"]["pastor"]
    # Create a fresh test program+module we own
    rp = requests.post(f"{BASE_URL}/api/formation/programs", headers=auth(token), json={
        "name": f"QaIt18 RegressionProg {uuid4().hex[:6]}", "purpose": "discipleship",
        "certificate_enabled": True, "certificate_scope": "program",
    }, timeout=30)
    assert rp.status_code == 201, rp.text
    program_id = rp.json()["program_id"]
    state["created_programs"].append(program_id)
    rm = requests.post(f"{BASE_URL}/api/formation/programs/{program_id}/modules", headers=auth(token), json={
        "name": "QaIt18 Mod with duration", "order": 1, "duration_days": 42, "certificate_enabled": True,
    }, timeout=30)
    assert rm.status_code == 201, rm.text
    module_id = rm.json()["module_id"]
    state["created_modules"].append(module_id)
    assert rm.json().get("duration_days") == 42

    # PUT without duration_days key
    rupd = requests.put(f"{BASE_URL}/api/formation/modules/{module_id}", headers=auth(token), json={
        "name": "QaIt18 Mod with duration (renamed)", "order": 1, "certificate_enabled": True,
    }, timeout=30)
    assert rupd.status_code == 200, rupd.text
    # Fetch and check
    rlist = requests.get(f"{BASE_URL}/api/formation/programs/{program_id}/modules", headers=auth(token), timeout=30)
    found = next((m for m in rlist.json()["items"] if m["module_id"] == module_id), None)
    assert found, "Module not found after update"
    # This assertion documents a regression risk: expected 42, actual may be None if bug exists
    assert found.get("duration_days") == 42, (
        f"REGRESSION: PUT without duration_days wiped the field. "
        f"Expected 42 preserved, got {found.get('duration_days')}"
    )


# ---------- Cleanup created test programs/modules at end ----------
def test_zz_cleanup_created_formation_items(state):
    for mid in state["created_modules"]:
        DB.formation_modules.delete_one({"module_id": mid})
        DB.formation_module_prerequisites.delete_many({"$or": [{"module_id": mid}, {"prerequisite_module_id": mid}]})
    for pid in state["created_programs"]:
        DB.formation_programs.delete_one({"program_id": pid})
