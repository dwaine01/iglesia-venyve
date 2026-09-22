import os
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from gridfs import GridFSBucket
from pymongo import MongoClient

from access_control import (
    BAPTISM_READ, BAPTISM_WRITE, FORMATION_CERTIFICATES_ISSUE,
    FORMATION_HISTORICAL_CREDIT_MANAGE, FORMATION_PROGRAMS_MANAGE,
    FORMATION_READ, PERSON_PROFILE_SENSITIVE_READ, access_defaults_for_role,
)


FRONTEND_ENV = dotenv_values("/app/frontend/.env"); BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV["REACT_APP_BACKEND_URL"]).rstrip("/")
CLIENT = MongoClient(BACKEND_ENV["MONGO_URL"]); DB = CLIENT[BACKEND_ENV["DB_NAME"]]
PASSWORD = "QaFormation44!"


def auth(token): return {"Authorization": f"Bearer {token}"}


def create_user(label, role="persona", access_level="persona", capabilities=None, scope=None):
    user_id, person_id = ObjectId(), ObjectId(); now = datetime.now(timezone.utc); email = f"qa.formation44.{label}.{uuid4().hex[:8]}@example.com"; defaults = access_defaults_for_role(access_level)
    DB.persons.insert_one({"_id": person_id, "person_number": f"VV-F44-{str(person_id)[-6:]}", "nombre": "QA", "apellido": label.title(), "search_key": f"qa {label}", "idempotency_key": f"qa:f44:{email}", "auth_user_id": str(user_id), "version": 1, "created_at": now, "updated_at": now})
    DB.users.insert_one({"_id": user_id, "nombre": f"QA {label.title()}", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "access_level": access_level, "person_id": str(person_id), "capabilities": capabilities if capabilities is not None else defaults["capabilities"], "access_scope": scope or defaults["access_scope"], "privilege_groups": [], "is_active": True, "token_version": 1, "access_policy_version": 22, "must_change_password": False, "onboarding_required": False, "created_at": now, "updated_at": now})
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30); assert response.status_code == 200
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email, "token": response.json()["token"]}


@pytest.fixture(scope="module")
def state():
    pastor = create_user("pastora", role="pastora", access_level="pastor")
    manager = create_user("manager", role="lider", access_level="coordinador_general", capabilities=[PERSON_PROFILE_SENSITIVE_READ, FORMATION_READ, FORMATION_PROGRAMS_MANAGE, FORMATION_HISTORICAL_CREDIT_MANAGE, FORMATION_CERTIFICATES_ISSUE, BAPTISM_READ, BAPTISM_WRITE], scope={"persons": "all"})
    professor = create_user("professor", role="lider", access_level="lider", capabilities=[FORMATION_READ], scope={"persons": "none"})
    student = create_user("student")
    result = {"pastor": pastor, "manager": manager, "professor": professor, "student": student, "document_ids": []}
    yield result
    for oid in result["document_ids"]:
        try: GridFSBucket(DB, bucket_name="formation_documents").delete(ObjectId(oid))
        except Exception: pass
    person_ids = [item["person_id"] for item in [pastor, manager, professor, student]]; user_ids = [item["user_id"] for item in [pastor, manager, professor, student]]
    for name in ["formation_programs", "formation_modules", "formation_achievements", "formation_certificate_issuances", "formation_audit_events", "person_baptisms", "person_activity"]:
        DB[name].delete_many({"$or": [{"person_id": {"$in": person_ids}}, {"created_by_user_id": {"$in": user_ids}}, {"actor_user_id": {"$in": user_ids}}, {"program_id": result.get("program_id")}]})
    DB.users.delete_many({"email": {"$regex": "^qa\\.formation44\\."}}); DB.persons.delete_many({"idempotency_key": {"$regex": "^qa:f44:"}})


def test_baptism_preparation_is_distinct_from_actual_baptism(state):
    h = auth(state["manager"]["token"])
    program = requests.post(f"{BASE_URL}/api/formation/programs", headers=h, json={"name": "Preparación Bautismal QA", "purpose": "baptism_preparation", "certificate_enabled": False}, timeout=30); assert program.status_code == 201, program.text
    state["program_id"] = program.json()["program_id"]
    module = requests.post(f"{BASE_URL}/api/formation/programs/{state['program_id']}/modules", headers=h, json={"name": "Fundamentos del Bautismo", "order": 1, "certificate_enabled": True}, timeout=30); assert module.status_code == 201, module.text
    state["module_id"] = module.json()["module_id"]
    credit = requests.post(f"{BASE_URL}/api/formation/persons/{state['student']['person_id']}/historical-credits", headers=h, json={"module_id": state["module_id"], "date_precision": "unknown", "observation": "Preparación previa verificada"}, timeout=30); assert credit.status_code == 201, credit.text
    state["achievement_id"] = credit.json()["achievement_id"]
    pending = requests.put(f"{BASE_URL}/api/core/persons/{state['student']['person_id']}/baptism", headers=h, json={"status": "pending", "baptized": False, "preparation_achievement_id": state["achievement_id"], "notes": "Preparación completa; bautismo aún pendiente"}, timeout=30)
    assert pending.status_code == 200, pending.text
    assert pending.json()["baptized"] is False and pending.json()["status"] == "pending"
    invalid = requests.put(f"{BASE_URL}/api/core/persons/{state['student']['person_id']}/baptism", headers=h, json={"status": "completed", "preparation_achievement_id": state["achievement_id"]}, timeout=30)
    assert invalid.status_code == 422
    completed = requests.put(f"{BASE_URL}/api/core/persons/{state['student']['person_id']}/baptism", headers=h, json={"status": "completed", "baptism_date": "2027-05-12", "location": "Santuario", "church_name": "Casa QA", "officiant_person_id": state["pastor"]["person_id"], "officiant_name": "Pastora QA", "preparation_achievement_id": state["achievement_id"]}, timeout=30)
    assert completed.status_code == 200, completed.text
    assert completed.json()["baptized"] is True and completed.json()["church_name"] == "Casa QA"


def test_private_evidence_upload_download_and_professor_denial(state):
    h = auth(state["manager"]["token"]); payload = b"%PDF-1.4 QA historical evidence"
    upload = requests.post(f"{BASE_URL}/api/formation/persons/{state['student']['person_id']}/documents", headers=h, data={"purpose": "historical_credit"}, files={"file": ("evidence.pdf", BytesIO(payload), "application/pdf")}, timeout=30)
    assert upload.status_code == 201, upload.text
    state["document_ids"].append(upload.json()["document_id"]); state["evidence_id"] = upload.json()["document_id"]
    download = requests.get(f"{BASE_URL}/api/formation/documents/{state['evidence_id']}", headers=h, timeout=30)
    assert download.status_code == 200 and download.content == payload
    denied = requests.get(f"{BASE_URL}/api/formation/documents/{state['evidence_id']}", headers=auth(state["professor"]["token"]), timeout=30)
    assert denied.status_code == 403


def test_historical_certificate_requires_evidence_and_explicit_authorization(state):
    h = auth(state["manager"]["token"])
    denied = requests.post(f"{BASE_URL}/api/formation/achievements/{state['achievement_id']}/certificates", headers=h, json={"reason": "Reimpresión solicitada", "allow_historical_reissue": True}, timeout=30)
    assert denied.status_code == 409
    DB.formation_achievements.update_one({"achievement_id": state["achievement_id"]}, {"$set": {"evidence_document_id": state["evidence_id"]}})
    issued = requests.post(f"{BASE_URL}/api/formation/achievements/{state['achievement_id']}/certificates", headers=h, json={"reason": "Evidencia histórica validada", "allow_historical_reissue": True}, timeout=30)
    assert issued.status_code == 201, issued.text
    assert issued.json()["status"] == "eligible_for_generation" and issued.json()["document_id"] is None


def test_professor_cannot_modify_baptism(state):
    denied = requests.put(f"{BASE_URL}/api/core/persons/{state['student']['person_id']}/baptism", headers=auth(state["professor"]["token"]), json={"status": "pending", "baptized": False}, timeout=30)
    assert denied.status_code == 403
    assert DB.formation_audit_events.count_documents({"person_id": state["student"]["person_id"], "action": "baptism_record_changed"}) == 2