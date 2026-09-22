import os
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

from access_control import access_defaults_for_role


FRONTEND_ENV = dotenv_values("/app/frontend/.env"); BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV["REACT_APP_BACKEND_URL"]).rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]; PASSWORD = "QaFormation45!"


def auth(token): return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def state():
    now = datetime.now(timezone.utc); user_id, pastor_person_id, target_person_id = ObjectId(), ObjectId(), ObjectId(); email = f"qa.formation45.{uuid4().hex[:8]}@example.com"; defaults = access_defaults_for_role("pastor")
    for oid, suffix, user_link in [(pastor_person_id, "pastora", str(user_id)), (target_person_id, "target", None)]:
        DB.persons.insert_one({"_id": oid, "person_number": f"VV-F45-{str(oid)[-6:]}", "nombre": "QA", "apellido": suffix, "search_key": f"qa {suffix}", "idempotency_key": f"qa:f45:{suffix}:{email}", "auth_user_id": user_link, "version": 1, "created_at": now, "updated_at": now})
    DB.users.insert_one({"_id": user_id, "nombre": "QA Pastora 45", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": "pastora", "access_level": "pastor", "person_id": str(pastor_person_id), "capabilities": defaults["capabilities"], "access_scope": defaults["access_scope"], "privilege_groups": [], "is_active": True, "token_version": 1, "access_policy_version": 22, "must_change_password": False, "onboarding_required": False, "created_at": now, "updated_at": now})
    login = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30); assert login.status_code == 200
    program_id, module_id, enrollment_id, membership_id, legacy_id = [str(uuid4()) for _ in range(5)]
    DB.formation_programs.insert_one({"_id": program_id, "program_id": program_id, "name": "Discipulado Configurable 45", "purpose": "discipleship", "active": True, "created_at": now})
    DB.formation_modules.insert_one({"_id": module_id, "module_id": module_id, "program_id": program_id, "name": "Entrada Configurable 45", "order": 1, "active": True, "created_at": now})
    DB.person_memberships.insert_one({"_id": membership_id, "membership_id": membership_id, "person_id": str(target_person_id), "member_number": f"F45-{str(target_person_id)[-4:]}", "status": "active", "acceptance_signed_at": now, "created_at": now})
    DB.process_enrollments.insert_one({"_id": enrollment_id, "enrollment_id": enrollment_id, "process_key": "consolidation", "definition_version": 2, "person_id": str(target_person_id), "status": "active", "current_stage_key": "retreat", "created_at": now, "updated_at": now})
    for key in ["retreat", "discipleship_handoff"]:
        DB.process_stage_progress.insert_one({"_id": str(uuid4()), "enrollment_id": enrollment_id, "process_key": "consolidation", "person_id": str(target_person_id), "stage_key": key, "status": "in_progress", "tasks": [{"task_id": f"{key}_task", "completed": False}], "created_at": now, "updated_at": now})
    DB.process_enrollments.insert_one({"_id": legacy_id, "enrollment_id": legacy_id, "process_key": "discipleship", "person_id": str(target_person_id), "status": "active", "current_stage_key": "orientation", "created_at": now, "updated_at": now})
    state = {"token": login.json()["token"], "user_id": user_id, "person_ids": [pastor_person_id, target_person_id], "target": str(target_person_id), "program_id": program_id, "module_id": module_id, "enrollment_id": enrollment_id, "membership_id": membership_id, "legacy_id": legacy_id}
    yield state
    DB.formation_recommendations.delete_many({"person_id": state["target"]}); DB.formation_modules.delete_one({"module_id": module_id}); DB.formation_programs.delete_one({"program_id": program_id}); DB.process_stage_progress.delete_many({"enrollment_id": enrollment_id}); DB.process_timeline.delete_many({"enrollment_id": enrollment_id}); DB.process_enrollments.delete_many({"enrollment_id": {"$in": [enrollment_id, legacy_id]}}); DB.person_memberships.delete_one({"membership_id": membership_id}); DB.users.delete_one({"_id": user_id}); DB.persons.delete_many({"_id": {"$in": [pastor_person_id, target_person_id]}})


def test_retreat_handoff_creates_recommendation_not_legacy_enrollment(state):
    response = requests.post(f"{BASE_URL}/api/processes/consolidation/{state['enrollment_id']}/retreat-close", headers=auth(state["token"]), json={"retreat_date": datetime.now(timezone.utc).isoformat(), "certificate_delivery_status": "pending_exception", "card_delivery_status": "pending", "delivery_notes": "QA configurable"}, timeout=30)
    assert response.status_code == 200, response.text
    updated = DB.process_enrollments.find_one({"enrollment_id": state["enrollment_id"]})
    assert updated.get("formation_recommendation_id")
    assert not updated.get("discipleship_enrollment_id")
    recommendation = DB.formation_recommendations.find_one({"person_id": state["target"], "source_enrollment_id": state["enrollment_id"]})
    assert recommendation and recommendation["source"] == "consolidation_retreat"
    assert DB.process_enrollments.count_documents({"person_id": state["target"], "process_key": "discipleship"}) == 1


def test_legacy_discipleship_is_read_only_but_visible(state):
    visible = requests.get(f"{BASE_URL}/api/processes/enrollments/{state['legacy_id']}", headers=auth(state["token"]), timeout=30)
    assert visible.status_code == 200
    blocked = requests.put(f"{BASE_URL}/api/processes/enrollments/{state['legacy_id']}", headers=auth(state["token"]), json={"next_action": "Intento de escritura"}, timeout=30)
    assert blocked.status_code == 409
    assert "solo lectura" in blocked.json()["detail"].lower()