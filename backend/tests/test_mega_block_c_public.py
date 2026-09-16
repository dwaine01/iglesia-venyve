"""Regresión pública integral del Mega-Bloque C con limpieza obligatoria de QA."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")).rstrip("/")
BACKEND_ENV = dotenv_values("/app/backend/.env")
MONGO_URL = (os.environ.get("MONGO_URL") or BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (os.environ.get("DB_NAME") or BACKEND_ENV.get("DB_NAME") or "").strip('"')
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
PERSONA = ("coreqa.member@example.com", "CoreQA2026!Member")
RUN = uuid.uuid4().hex[:8]
QA_PREFIX = f"QA MegaC {RUN}"


def url(path): return f"{BASE_URL}{path}"
def headers(token): return {"Authorization": f"Bearer {token}"}
def login(credentials):
    response = requests.post(url("/api/auth/login"), json={"email": credentials[0], "password": credentials[1]}, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="module")
def mongo_db():
    if not MONGO_URL or not DB_NAME: pytest.skip("Mongo requerido para validar y limpiar QA")
    client = MongoClient(MONGO_URL); database = client[DB_NAME]
    yield database
    qa_people = list(database.persons.find({"qa_run": RUN}, {"_id": 1}))
    person_ids = [str(item["_id"]) for item in qa_people]
    cell_ids = database.cells.distinct("cell_id", {"qa_run": RUN})
    network_ids = database.cell_networks.distinct("network_id", {"qa_run": RUN})
    meeting_ids = database.cell_meetings.distinct("meeting_id", {"cell_id": {"$in": cell_ids}})
    need_ids = database.cell_needs.distinct("need_id", {"cell_id": {"$in": cell_ids}})
    door_case_ids = database.door_cases.distinct("case_id", {"source_type": "cell_need", "source_id": {"$in": need_ids}})
    for collection in ["cell_network_assignments"]: database[collection].delete_many({"network_id": {"$in": network_ids}})
    for collection in ["cell_role_assignments", "cell_memberships", "cell_followups", "cell_needs", "cell_health_snapshots", "cell_multiplication_reviews", "cell_timeline"]: database[collection].delete_many({"cell_id": {"$in": cell_ids}})
    database.cell_meeting_attendance.delete_many({"meeting_id": {"$in": meeting_ids}})
    database.person_attendance.delete_many({"activity_type": "cell_meeting", "source_id": {"$in": meeting_ids}})
    database.cell_meetings.delete_many({"cell_id": {"$in": cell_ids}})
    database.door_case_events.delete_many({"case_id": {"$in": door_case_ids}})
    database.door_cases.delete_many({"case_id": {"$in": door_case_ids}})
    database.board_audit_events.delete_many({"$or": [{"entity_id": {"$in": door_case_ids}}, {"changes.need_id": {"$in": need_ids}}]})
    database.cell_assignment_events.delete_many({"$or": [{"cell_id": {"$in": cell_ids}}, {"person_id": {"$in": person_ids}}]})
    database.cell_multiplications.delete_many({"$or": [{"mother_cell_id": {"$in": cell_ids}}, {"daughter_cell_id": {"$in": cell_ids}}]})
    database.cells.delete_many({"cell_id": {"$in": cell_ids}}); database.cell_networks.delete_many({"network_id": {"$in": network_ids}})
    for collection in ["person_contacts", "person_activity", "process_enrollments", "process_stage_progress", "process_timeline", "process_alerts"]: database[collection].delete_many({"person_id": {"$in": person_ids}})
    database.persons.delete_many({"qa_run": RUN})
    assert database.cell_needs.count_documents({"need_id": {"$in": need_ids}}) == 0
    client.close()


def create_person(token, mongo_db, suffix):
    response = requests.post(url("/api/core/persons"), headers=headers(token), json={"nombre": "QA", "apellido": f"MegaC{RUN}{suffix}", "telefono": f"+1614{uuid.uuid4().int % 10000000:07d}", "idempotency_key": f"qa-megac-{RUN}-{suffix}"}, timeout=30)
    assert response.status_code == 201, response.text
    person_id = response.json()["person_id"]
    from bson import ObjectId
    mongo_db.persons.update_one({"_id": ObjectId(person_id)}, {"$set": {"qa_run": RUN}})
    return person_id


def test_cellular_end_to_end_and_cleanup_contract(mongo_db):
    session = login(PASTOR); token = session["token"]; pastor_person_id = session["user"]["person_id"]
    guide = requests.get(url("/api/guides/cellular_meeting"), headers=headers(token), timeout=30)
    assert guide.status_code == 200 and guide.json().get("steps")
    catalog = requests.get(url("/api/cellular/catalog"), headers=headers(token), timeout=30)
    assert catalog.status_code == 200 and len(catalog.json().get("networks", [])) >= 4

    network = requests.post(url("/api/cellular/networks"), headers=headers(token), json={"name": QA_PREFIX, "description": "Regresión temporal", "status": "active"}, timeout=30)
    assert network.status_code == 201, network.text
    network_id = network.json()["network_id"]
    mongo_db.cell_networks.update_one({"network_id": network_id}, {"$set": {"qa_run": RUN}})
    assignment = requests.post(url(f"/api/cellular/networks/{network_id}/assignments"), headers=headers(token), json={"person_id": pastor_person_id, "role": "supervisor"}, timeout=30)
    assert assignment.status_code == 201, assignment.text

    def make_cell(code, name):
        response = requests.post(url("/api/cellular/cells"), headers=headers(token), json={"name": name, "code": code, "network_id": network_id, "address": "Columbus, Ohio", "meeting_day": "Sábado", "meeting_time": "19:00", "capacity": 20, "opened_at": datetime.now(timezone.utc).date().isoformat(), "status": "active"}, timeout=30)
        assert response.status_code == 201, response.text
        cell_id = response.json()["cell_id"]
        mongo_db.cells.update_one({"cell_id": cell_id}, {"$set": {"qa_run": RUN}})
        return cell_id

    cell_a = make_cell(f"QAC{RUN[:5]}A", f"{QA_PREFIX} A"); cell_b = make_cell(f"QAC{RUN[:5]}B", f"{QA_PREFIX} B")
    role = requests.post(url(f"/api/cellular/cells/{cell_a}/roles"), headers=headers(token), json={"person_id": pastor_person_id, "role": "cell_leader"}, timeout=30)
    assert role.status_code == 201, role.text

    person_id = create_person(token, mongo_db, "A")
    membership = requests.post(url(f"/api/cellular/cells/{cell_a}/memberships"), headers=headers(token), json={"person_id": person_id, "membership_type": "primary", "role": "member", "source": "qa_regression"}, timeout=30)
    assert membership.status_code == 201, membership.text
    duplicate = requests.post(url(f"/api/cellular/cells/{cell_a}/memberships"), headers=headers(token), json={"person_id": person_id, "membership_type": "primary", "role": "member"}, timeout=30)
    assert duplicate.status_code == 201 and duplicate.json()["membership_id"] == membership.json()["membership_id"]

    meeting = requests.post(url(f"/api/cellular/cells/{cell_a}/meetings"), headers=headers(token), json={"scheduled_at": datetime.now(timezone.utc).isoformat(), "leader_person_id": pastor_person_id, "topic": "Regresión Mega C", "tasks": ["Confirmar asistencia"]}, timeout=30)
    assert meeting.status_code == 201, meeting.text
    meeting_id = meeting.json()["meeting_id"]; task_id = meeting.json()["tasks"][0]["task_id"]
    assert requests.post(url(f"/api/cellular/meetings/{meeting_id}/start"), headers=headers(token), json={}, timeout=30).status_code == 200
    tasks = requests.put(url(f"/api/cellular/meetings/{meeting_id}/tasks"), headers=headers(token), json={"entries": [{"task_id": task_id, "completed": True}]}, timeout=30)
    assert tasks.status_code == 200 and tasks.json()["tasks"][0]["completed"] is True
    attendance_payload = {"entries": [{"person_id": person_id, "status": "present", "is_visitor": True, "is_new": True}], "conversion_person_ids": [person_id], "petitions": ["Petición QA"], "results": "Cierre QA", "complete_meeting": True}
    attendance = requests.put(url(f"/api/cellular/meetings/{meeting_id}/attendance"), headers=headers(token), json=attendance_payload, timeout=30)
    assert attendance.status_code == 200, attendance.text
    assert mongo_db.person_attendance.count_documents({"person_id": person_id, "activity_type": "cell_meeting", "source_id": meeting_id, "estado": "presente"}) == 1
    repeat = requests.put(url(f"/api/cellular/meetings/{meeting_id}/attendance"), headers=headers(token), json=attendance_payload, timeout=30)
    assert repeat.status_code == 200 and mongo_db.person_attendance.count_documents({"source_id": meeting_id, "person_id": person_id}) == 1

    need = requests.post(url("/api/cellular/needs"), headers=headers(token), json={"cell_id": cell_a, "meeting_id": meeting_id, "person_id": person_id, "need_type": "illness", "description": "Necesidad temporal de regresión", "priority": "high"}, timeout=30)
    assert need.status_code == 201 and need.json()["suggested_door_key"] == "door_6"
    resolved = requests.put(url(f"/api/cellular/needs/{need.json()['need_id']}"), headers=headers(token), json={"status": "resolved", "resolution": "Validación cerrada"}, timeout=30)
    assert resolved.status_code == 200 and resolved.json()["status"] == "resolved"
    followup = requests.post(url("/api/cellular/followups"), headers=headers(token), json={"cell_id": cell_a, "person_id": person_id, "followup_type": "visit", "responsible_person_id": pastor_person_id, "due_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), "priority": "high", "next_action": "Visita temporal"}, timeout=30)
    assert followup.status_code == 201, followup.text
    completed = requests.put(url(f"/api/cellular/followups/{followup.json()['followup_id']}"), headers=headers(token), json={"status": "completed", "result": "Realizado"}, timeout=30)
    assert completed.status_code == 200

    persona_session = login(PERSONA); persona_token = persona_session["token"]; persona_person_id = persona_session["user"]["person_id"]
    persona_membership = requests.post(url(f"/api/cellular/cells/{cell_a}/memberships"), headers=headers(token), json={"person_id": persona_person_id, "membership_type": "primary", "role": "member", "source": "qa_security"}, timeout=30)
    assert persona_membership.status_code == 201, persona_membership.text
    private_cell = requests.get(url(f"/api/cellular/cells/{cell_a}"), headers=headers(persona_token), timeout=30)
    assert private_cell.status_code == 200, private_cell.text
    assert {item["person_id"] for item in private_cell.json()["memberships"]} == {persona_person_id}
    assert private_cell.json()["needs"] == [] and private_cell.json()["followups"] == []
    assert private_cell.json()["timeline"] == []
    sensitive_metrics = {"open_needs", "open_followups", "visitors", "conversions", "retention"}
    assert not sensitive_metrics.intersection(private_cell.json()["metrics"])
    for private_meeting in private_cell.json()["meetings"]:
        assert set(private_meeting).issubset({"meeting_id", "cell_id", "scheduled_at", "topic", "status"})
    private_meetings = requests.get(url(f"/api/cellular/cells/{cell_a}/meetings"), headers=headers(persona_token), timeout=30)
    assert private_meetings.status_code == 200
    assert private_meetings.json()["items"]
    for private_meeting in private_meetings.json()["items"]:
        assert set(private_meeting).issubset({"meeting_id", "cell_id", "scheduled_at", "topic", "status"})
    private_meeting_detail = requests.get(url(f"/api/cellular/meetings/{meeting_id}"), headers=headers(persona_token), timeout=30)
    assert private_meeting_detail.status_code == 200
    assert set(private_meeting_detail.json()).issubset({"meeting_id", "cell_id", "scheduled_at", "topic", "status"})
    private_health = requests.get(url(f"/api/cellular/health?cell_id={cell_a}"), headers=headers(persona_token), timeout=30)
    assert private_health.status_code == 200
    for snapshot in private_health.json()["items"]:
        assert not {"open_needs", "open_followups", "conversions", "visitors", "retention"}.intersection(snapshot)
    private_reviews = requests.get(url("/api/cellular/multiplication/reviews"), headers=headers(persona_token), timeout=30)
    assert private_reviews.status_code == 200
    for review in private_reviews.json()["items"]:
        assert not {"open_needs", "open_followups", "conversions", "visitors", "retention"}.intersection(review.get("facts", {}).get("metrics", {}))
    assert requests.get(url("/api/cellular/needs"), headers=headers(persona_token), timeout=30).status_code == 403
    assert requests.get(url("/api/cellular/followups"), headers=headers(persona_token), timeout=30).status_code == 403
    private_dashboard = requests.get(url("/api/cellular/dashboard"), headers=headers(persona_token), timeout=30)
    assert private_dashboard.status_code == 200 and private_dashboard.json()["needs"] == [] and private_dashboard.json()["followups"] == []
    assert not {"new_visitors", "conversions", "open_needs", "pending_followups"}.intersection(private_dashboard.json()["metrics"])
    for private_dashboard_cell in private_dashboard.json()["cells"]:
        assert not sensitive_metrics.intersection(private_dashboard_cell["metrics"])
    private_cell_list = requests.get(url("/api/cellular/cells"), headers=headers(persona_token), timeout=30)
    assert private_cell_list.status_code == 200
    for private_list_item in private_cell_list.json()["items"]:
        assert not sensitive_metrics.intersection(private_list_item["metrics"])

    profile = requests.get(url(f"/api/core/persons/{person_id}/profile"), headers=headers(token), timeout=30)
    assert profile.status_code == 200 and profile.json().get("celula")
    transfer = requests.post(url("/api/cellular/memberships/transfer"), headers=headers(token), json={"person_id": person_id, "target_cell_id": cell_b, "reason": "Prueba histórica", "transferred_at": datetime.now(timezone.utc).date().isoformat()}, timeout=30)
    assert transfer.status_code == 200
    history = list(mongo_db.cell_memberships.find({"person_id": person_id, "membership_type": "primary"}))
    assert len(history) == 2 and sum(1 for item in history if item.get("active")) == 1

    ready_person = create_person(token, mongo_db, "B")
    enrollment_id = f"qa-ready-{RUN}"
    mongo_db.process_enrollments.insert_one({"_id": enrollment_id, "enrollment_id": enrollment_id, "person_id": ready_person, "process_key": "cap", "status": "completed", "ready_for_cellular": True, "completed_at": datetime.now(timezone.utc), "created_by_user_id": session["user"]["id"], "qa_run": RUN})
    inbox = requests.get(url("/api/cellular/ready-inbox"), headers=headers(token), timeout=30)
    assert inbox.status_code == 200 and any(item["person_id"] == ready_person for item in inbox.json()["items"])
    ready_assign = requests.post(url("/api/cellular/ready-inbox/assign"), headers=headers(token), json={"person_id": ready_person, "cell_id": cell_b, "responsible_person_id": pastor_person_id, "first_followup_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), "first_followup_action": "Bienvenida QA"}, timeout=30)
    assert ready_assign.status_code == 201, ready_assign.text
    assert mongo_db.process_enrollments.find_one({"enrollment_id": enrollment_id})["ready_for_cellular"] is False

    for path in ["/api/cellular/dashboard", "/api/cellular/health", "/api/cellular/genealogy", "/api/cellular/multiplication/reviews"]:
        response = requests.get(url(path), headers=headers(token), timeout=30); assert response.status_code == 200, response.text
    evaluated = requests.post(url(f"/api/cellular/cells/{cell_b}/multiplication/evaluate"), headers=headers(token), json={}, timeout=30)
    assert evaluated.status_code == 200 and "eligible" in evaluated.json()
    migrated = requests.post(url("/api/cellular/migrate"), headers=headers(token), json={}, timeout=30)
    assert migrated.status_code == 200 and "conflict_count" in migrated.json()


def test_cellular_rbac_persona_cannot_manage(mongo_db):
    session = login(PERSONA); token = session["token"]
    dashboard = requests.get(url("/api/cellular/dashboard"), headers=headers(token), timeout=30)
    assert dashboard.status_code == 200, dashboard.text
    forbidden = requests.post(url("/api/cellular/networks"), headers=headers(token), json={"name": "No permitido", "status": "active"}, timeout=30)
    assert forbidden.status_code == 403