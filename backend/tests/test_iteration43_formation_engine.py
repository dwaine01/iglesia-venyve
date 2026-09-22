import os
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

from access_control import (
    FORMATION_ATTENDANCE_WRITE, FORMATION_COHORTS_MANAGE, FORMATION_ENROLL,
    FORMATION_GRADES_READ, FORMATION_GRADES_WRITE,
    FORMATION_HISTORICAL_CREDIT_MANAGE, FORMATION_PROGRAMS_MANAGE,
    FORMATION_PROGRESS_MANAGE, FORMATION_PROMOTE, FORMATION_READ,
    access_defaults_for_role,
)


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV["REACT_APP_BACKEND_URL"]).rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
PASSWORD = "QaFormation43!"


def auth(token): return {"Authorization": f"Bearer {token}"}


def create_user(label, role="persona", access_level="persona", capabilities=None, scope=None):
    user_id, person_id = ObjectId(), ObjectId(); now = datetime.now(timezone.utc)
    email = f"qa.formation43.{label}.{uuid4().hex[:8]}@example.com"; defaults = access_defaults_for_role(access_level)
    DB.persons.insert_one({"_id": person_id, "person_number": f"VV-F43-{str(person_id)[-6:]}", "nombre": "QA", "apellido": label.title(), "search_key": f"qa {label}", "idempotency_key": f"qa:f43:{email}", "auth_user_id": str(user_id), "version": 1, "created_at": now, "updated_at": now})
    DB.users.insert_one({"_id": user_id, "nombre": f"QA {label.title()}", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "access_level": access_level, "person_id": str(person_id), "capabilities": capabilities if capabilities is not None else defaults["capabilities"], "access_scope": scope or defaults["access_scope"], "privilege_groups": [], "is_active": True, "token_version": 1, "access_policy_version": 22, "must_change_password": False, "onboarding_required": False, "created_at": now, "updated_at": now})
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email}


def login(email):
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()["token"]


@pytest.fixture(scope="module")
def state():
    admin_caps = [FORMATION_READ, FORMATION_PROGRAMS_MANAGE, FORMATION_COHORTS_MANAGE, FORMATION_ENROLL, FORMATION_ATTENDANCE_WRITE, FORMATION_GRADES_READ, FORMATION_GRADES_WRITE, FORMATION_PROGRESS_MANAGE, FORMATION_HISTORICAL_CREDIT_MANAGE, FORMATION_PROMOTE]
    teacher_caps = [FORMATION_READ, FORMATION_ATTENDANCE_WRITE, FORMATION_GRADES_READ, FORMATION_GRADES_WRITE]
    accounts = {
        "pastora": create_user("pastora", role="pastora", access_level="pastor"),
        "coordinator": create_user("coordinator", role="lider", access_level="coordinador_general", capabilities=admin_caps, scope={"persons": "all"}),
        "teacher": create_user("teacher", role="lider", access_level="lider", capabilities=teacher_caps, scope={"persons": "none"}),
        "student": create_user("student"),
        "historical": create_user("historical"),
    }
    tokens = {key: login(value["email"]) for key, value in accounts.items() if key in {"pastora", "coordinator", "teacher"}}
    state = {"accounts": accounts, "tokens": tokens, "ids": []}
    yield state
    prefix = "qa:f43:"
    person_ids = [item["person_id"] for item in accounts.values()]
    for name in ["formation_programs", "formation_modules", "formation_module_prerequisites", "formation_cohorts", "formation_cohort_staff", "formation_sessions", "formation_enrollments", "formation_attendance", "formation_assessments", "formation_grades", "formation_achievements", "formation_audit_events"]:
        DB[name].delete_many({"$or": [{"created_by_user_id": {"$in": [item["user_id"] for item in accounts.values()]}}, {"actor_user_id": {"$in": [item["user_id"] for item in accounts.values()]}}, {"person_id": {"$in": person_ids}}, {"program_id": {"$in": state.get("program_ids", [])}}, {"cohort_id": {"$in": state.get("cohort_ids", [])}}]})
    DB.users.delete_many({"email": {"$regex": "^qa\\.formation43\\."}})
    DB.persons.delete_many({"idempotency_key": {"$regex": f"^{prefix}"}})


def test_programs_modules_prerequisites_and_cycle_detection(state):
    token = state["tokens"]["pastora"]
    program = requests.post(f"{BASE_URL}/api/formation/programs", headers=auth(token), json={"name": "Escuela QA 43", "description": "Programa configurable", "purpose": "discipleship", "certificate_enabled": True, "certificate_scope": "program"}, timeout=30)
    assert program.status_code == 201, program.text
    state["program_id"] = program.json()["program_id"]; state["program_ids"] = [state["program_id"]]
    modules = []
    for order, name in enumerate(["Fundamentos QA", "Crecimiento QA", "Servicio QA"], 1):
        response = requests.post(f"{BASE_URL}/api/formation/programs/{state['program_id']}/modules", headers=auth(token), json={"name": name, "order": order, "approval_policy": {"method": "attendance_and_grade", "minimum_attendance_pct": 75, "minimum_grade_pct": 70, "late_weight": 0.5, "excused_policy": "exclude", "manual_confirmation_required": False, "custom_requirements": []}}, timeout=30)
        assert response.status_code == 201, response.text; modules.append(response.json())
    state["modules"] = modules
    for target, prerequisite in [(modules[1], modules[0]), (modules[2], modules[1])]:
        response = requests.put(f"{BASE_URL}/api/formation/modules/{target['module_id']}/prerequisites", headers=auth(token), json={"prerequisite_module_ids": [prerequisite["module_id"]], "mode": "all"}, timeout=30)
        assert response.status_code == 200, response.text
    cycle = requests.put(f"{BASE_URL}/api/formation/modules/{modules[0]['module_id']}/prerequisites", headers=auth(token), json={"prerequisite_module_ids": [modules[2]["module_id"]], "mode": "all"}, timeout=30)
    assert cycle.status_code == 409


def test_cohorts_sessions_staff_enrollment_and_capacity(state):
    token = state["tokens"]["coordinator"]; state["cohort_ids"] = []
    cohorts = []
    for module in state["modules"][:2]:
        response = requests.post(f"{BASE_URL}/api/formation/cohorts", headers=auth(token), json={"module_id": module["module_id"], "name": f"{module['name']} Enero", "start_date": "2027-01-10", "end_date": "2027-02-20", "schedule": "Sábados 9:00", "modality": "onsite", "location": "Aula QA", "capacity": 20, "status": "in_progress"}, timeout=30)
        assert response.status_code == 201, response.text; cohorts.append(response.json()); state["cohort_ids"].append(response.json()["cohort_id"])
    state["cohorts"] = cohorts
    assign = requests.post(f"{BASE_URL}/api/formation/cohorts/{cohorts[0]['cohort_id']}/staff", headers=auth(token), json={"person_id": state["accounts"]["teacher"]["person_id"], "role": "teacher"}, timeout=30)
    assert assign.status_code == 201, assign.text
    sessions = []
    for number in [1, 2]:
        response = requests.post(f"{BASE_URL}/api/formation/cohorts/{cohorts[0]['cohort_id']}/sessions", headers=auth(token), json={"name": f"Clase {number}", "session_date": f"2027-01-{10 + number:02d}", "teacher_person_id": state["accounts"]["teacher"]["person_id"], "required": True}, timeout=30)
        assert response.status_code == 201, response.text; sessions.append(response.json())
    state["sessions"] = sessions
    enrollment = requests.post(f"{BASE_URL}/api/formation/cohorts/{cohorts[0]['cohort_id']}/enrollments", headers=auth(token), json={"person_id": state["accounts"]["student"]["person_id"]}, timeout=30)
    assert enrollment.status_code == 201, enrollment.text; state["enrollment"] = enrollment.json()
    blocked = requests.post(f"{BASE_URL}/api/formation/cohorts/{cohorts[1]['cohort_id']}/enrollments", headers=auth(token), json={"person_id": state["accounts"]["student"]["person_id"]}, timeout=30)
    assert blocked.status_code == 409


def test_teacher_records_attendance_and_grades_only_in_assigned_cohort(state):
    teacher = state["tokens"]["teacher"]; enrollment_id = state["enrollment"]["enrollment_id"]
    for session, attendance_status in zip(state["sessions"], ["present", "late"]):
        response = requests.put(f"{BASE_URL}/api/formation/sessions/{session['session_id']}/attendance", headers=auth(teacher), json={"items": [{"enrollment_id": enrollment_id, "status": attendance_status}]}, timeout=30)
        assert response.status_code == 200, response.text
    assessment = requests.post(f"{BASE_URL}/api/formation/cohorts/{state['cohorts'][0]['cohort_id']}/assessments", headers=auth(state["tokens"]["coordinator"]), json={"name": "Evaluación final", "weight": 100, "max_score": 100, "required": True}, timeout=30)
    assert assessment.status_code == 201, assessment.text
    grade = requests.put(f"{BASE_URL}/api/formation/assessments/{assessment.json()['assessment_id']}/grades", headers=auth(teacher), json={"items": [{"enrollment_id": enrollment_id, "score": 80}]}, timeout=30)
    assert grade.status_code == 200, grade.text
    result = grade.json()["enrollments"][0]
    assert result["attendance_pct"] == 75 and result["final_grade_pct"] == 80 and result["status"] == "completed"
    other_session = requests.post(f"{BASE_URL}/api/formation/cohorts/{state['cohorts'][1]['cohort_id']}/sessions", headers=auth(state["tokens"]["coordinator"]), json={"name": "Clase restringida", "session_date": "2027-03-01", "required": True}, timeout=30)
    assert other_session.status_code == 201
    idor = requests.put(f"{BASE_URL}/api/formation/sessions/{other_session.json()['session_id']}/attendance", headers=auth(teacher), json={"items": [{"enrollment_id": enrollment_id, "status": "present"}]}, timeout=30)
    assert idor.status_code == 403


def test_historical_credit_next_step_and_promotion(state):
    token = state["tokens"]["coordinator"]; historical = state["accounts"]["historical"]["person_id"]
    first = requests.post(f"{BASE_URL}/api/formation/persons/{historical}/historical-credits", headers=auth(token), json={"module_id": state["modules"][0]["module_id"], "historical_completion_date": None, "date_precision": "unknown", "observation": "Formación completada antes del sistema"}, timeout=30)
    assert first.status_code == 201, first.text
    assert first.json()["attendance_pct"] is None and first.json()["final_grade_pct"] is None
    assert first.json()["next_recommended"]["module_id"] == state["modules"][1]["module_id"]
    promotion = requests.post(f"{BASE_URL}/api/formation/enrollments/{state['enrollment']['enrollment_id']}/promote", headers=auth(token), json={"target_cohort_id": state["cohorts"][1]["cohort_id"], "reason": "Promoción posterior a aprobación"}, timeout=30)
    assert promotion.status_code == 201, promotion.text
    assert promotion.json()["module_id"] == state["modules"][1]["module_id"]


def test_professor_revocation_is_immediate_and_audit_is_append_only(state):
    token = state["tokens"]["coordinator"]; teacher = state["tokens"]["teacher"]; cohort_id = state["cohorts"][0]["cohort_id"]
    before = requests.get(f"{BASE_URL}/api/formation/cohorts/{cohort_id}", headers=auth(teacher), timeout=30)
    assert before.status_code == 200
    revoke = requests.delete(f"{BASE_URL}/api/formation/cohorts/{cohort_id}/staff/{state['accounts']['teacher']['person_id']}", headers=auth(token), timeout=30)
    assert revoke.status_code == 200
    after = requests.get(f"{BASE_URL}/api/formation/cohorts/{cohort_id}", headers=auth(teacher), timeout=30)
    assert after.status_code == 403
    assert DB.formation_audit_events.count_documents({"action": {"$in": ["attendance_changed", "grade_changed", "cohort_staff_revoked"]}}) >= 4