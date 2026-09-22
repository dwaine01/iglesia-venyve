import json
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

from access_control import CORE_ACCESS_MANAGE, DOORS_MANAGE, access_defaults_for_role


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
PASSWORD = "QaBoardRestricted2026!"


def auth(token): return {"Authorization": f"Bearer {token}"}


def login(email, password=PASSWORD):
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()["token"], response.json()["user"]


def create_account(label, access_level="lider", extra_capabilities=None):
    user_id, person_id = ObjectId(), ObjectId(); email = f"qa.iter39.{label}.{uuid4().hex[:7]}@example.com"; now = datetime.now(timezone.utc)
    defaults = access_defaults_for_role("lider"); capabilities = sorted(set([*defaults["capabilities"], *(extra_capabilities or [])]))
    DB.persons.insert_one({"_id": person_id, "person_number": f"VV-I39-{str(person_id)[-5:].upper()}", "nombre": "QA", "apellido": label.title(), "search_key": f"qa {label}", "idempotency_key": f"qa:iter39:{email}", "auth_user_id": str(user_id), "version": 1, "created_at": now, "updated_at": now})
    DB.users.insert_one({"_id": user_id, "nombre": f"QA {label.title()}", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": "lider", "access_level": access_level, "person_id": str(person_id), "capabilities": capabilities, "access_scope": {"persons": "all" if access_level == "coordinador_general" else "created_by"}, "privilege_groups": [], "is_active": True, "token_version": 1, "access_policy_version": 20, "must_change_password": False, "onboarding_required": False, "created_at": now, "updated_at": now})
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email}


@pytest.fixture(scope="module")
def board_matrix_fixture():
    accounts = {
        "coordinator": create_account("coordinator", "coordinador_general", [CORE_ACCESS_MANAGE, DOORS_MANAGE]),
        "secretary": create_account("secretary"),
        "vocal": create_account("vocal"),
        "treasurer": create_account("treasurer"),
    }
    pastor_token, pastor = login("coreqa.pastor@example.com", "CoreQA2026!Pastor")
    created = {"accounts": accounts, "pastor_token": pastor_token, "pastor": pastor, "memberships": [], "meetings": [], "actions": [], "documents": []}
    yield created
    person_ids = [item["person_id"] for item in accounts.values()]
    user_ids = [ObjectId(item["user_id"]) for item in accounts.values()]
    meeting_ids = DB.board_meetings.distinct("meeting_id", {"qa_run": "iteration39"})
    for bucket_name in ["board_documents", "board_recordings", "board_recording_staging"]:
        bucket = GridFSBucket(DB, bucket_name=bucket_name)
        for item in list(DB[f"{bucket_name}.files"].find({"metadata.qa_run": "iteration39"}, {"_id": 1})):
            bucket.delete(item["_id"])
    for collection in ["board_agenda_items", "board_attendance", "board_proposals", "board_votes", "board_actions", "board_minutes", "board_ai_artifacts", "board_secretary_notes", "board_secretary_note_versions", "board_transcript_versions", "board_transcript_segments"]:
        DB[collection].delete_many({"meeting_id": {"$in": meeting_ids}})
    DB.board_meetings.delete_many({"meeting_id": {"$in": meeting_ids}})
    DB.door_assignments.delete_many({"source_board_membership_id": {"$in": created["memberships"]}})
    DB.board_memberships.delete_many({"membership_id": {"$in": created["memberships"]}})
    DB.person_activity.delete_many({"person_id": {"$in": person_ids}})
    DB.users.delete_many({"_id": {"$in": user_ids}})
    DB.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in person_ids]}})


def add_member(fixture, person_id, position_key, permissions=None):
    response = requests.post(f"{BASE_URL}/api/board/members", headers=auth(fixture["pastor_token"]), json={"person_id": person_id, "position_key": position_key, "voting_rights": True, "permissions": permissions or [], "supervised_door_keys": [], "ministry_ids": []}, timeout=30)
    if response.status_code == 201: fixture["memberships"].append(response.json()["membership_id"])
    return response


def test_hierarchy_never_opens_board_and_pastor_is_full(board_matrix_fixture):
    fixture = board_matrix_fixture
    coordinator_token, _ = login(fixture["accounts"]["coordinator"]["email"])
    denied = requests.get(f"{BASE_URL}/api/board/access", headers=auth(coordinator_token), timeout=30)
    assert denied.status_code == 200 and denied.json()["allowed"] is False
    assert requests.get(f"{BASE_URL}/api/board", headers=auth(coordinator_token), timeout=30).status_code == 403
    pastor_access = requests.get(f"{BASE_URL}/api/board/access", headers=auth(fixture["pastor_token"]), timeout=30)
    assert pastor_access.status_code == 200 and pastor_access.json()["full_access"] is True


def test_position_matrix_blocks_overgrant_and_separates_pastoral_privacy(board_matrix_fixture):
    fixture = board_matrix_fixture
    pastor_member = add_member(fixture, fixture["pastor"]["person_id"], "president")
    assert pastor_member.status_code == 201, pastor_member.text
    overgrant = add_member(fixture, fixture["accounts"]["vocal"]["person_id"], "vocal", ["board.read", "board.audio.manage"])
    assert overgrant.status_code == 422
    for key, role in [("secretary", "secretary"), ("vocal", "vocal"), ("treasurer", "treasurer")]:
        response = add_member(fixture, fixture["accounts"][key]["person_id"], role)
        assert response.status_code == 201, response.text
    for key in ["secretary", "vocal", "treasurer"]:
        user = DB.users.find_one({"_id": ObjectId(fixture["accounts"][key]["user_id"])}, {"_id": 0, "capabilities": 1})
        assert "board.access" in user["capabilities"]
        assert "board.confidential.access" not in user["capabilities"]
        assert "care.confidential.read" not in user["capabilities"]
        assert "person.pastoral_notes.read" not in user["capabilities"]
    secretary_token, _ = login(fixture["accounts"]["secretary"]["email"])
    vocal_token, _ = login(fixture["accounts"]["vocal"]["email"])
    secretary_access = requests.get(f"{BASE_URL}/api/board/access", headers=auth(secretary_token), timeout=30).json()
    vocal_access = requests.get(f"{BASE_URL}/api/board/access", headers=auth(vocal_token), timeout=30).json()
    assert "board.audio.manage" in secretary_access["permissions"] and "board.notes.write" in secretary_access["permissions"]
    assert vocal_access["permissions"] == ["board.read", "board.vote"]


def test_meeting_information_is_scoped_by_function(board_matrix_fixture):
    fixture = board_matrix_fixture
    secretary_token, _ = login(fixture["accounts"]["secretary"]["email"])
    vocal_token, _ = login(fixture["accounts"]["vocal"]["email"])
    treasurer_token, _ = login(fixture["accounts"]["treasurer"]["email"])
    meeting = requests.post(f"{BASE_URL}/api/board/meetings", headers=auth(fixture["pastor_token"]), json={"title": "QA Iter39 Junta restringida", "scheduled_at": datetime.now(timezone.utc).isoformat(), "location": "Sala institucional", "modality": "in_person", "chair_person_id": fixture["pastor"]["person_id"], "secretary_person_id": fixture["accounts"]["secretary"]["person_id"], "planned_duration_minutes": 60, "purpose": "Validar acceso restringido", "agenda_titles": ["Apertura", "Acuerdos"]}, timeout=30)
    assert meeting.status_code == 201, meeting.text
    meeting_id = meeting.json()["meeting_id"]; fixture["meetings"].append(meeting_id); DB.board_meetings.update_one({"meeting_id": meeting_id}, {"$set": {"qa_run": "iteration39"}})
    created_actions = []
    for title, responsible, action_type, visibility in [
        ("Tarea Secretaría", fixture["accounts"]["secretary"]["person_id"], "task", "assigned"),
        ("Tarea Vocal", fixture["accounts"]["vocal"]["person_id"], "task", "assigned"),
        ("Acuerdo institucional", fixture["pastor"]["person_id"], "agreement", "board"),
    ]:
        response = requests.post(f"{BASE_URL}/api/board/meetings/{meeting_id}/actions", headers=auth(fixture["pastor_token"]), json={"title": title, "responsible_person_id": responsible, "action_type": action_type, "visibility": visibility}, timeout=30)
        assert response.status_code == 201, response.text; created_actions.append(response.json())
    vocal_detail = requests.get(f"{BASE_URL}/api/board/meetings/{meeting_id}", headers=auth(vocal_token), timeout=30)
    assert vocal_detail.status_code == 200
    vocal_titles = {item["title"] for item in vocal_detail.json()["actions"]}
    assert vocal_titles == {"Tarea Vocal", "Acuerdo institucional"}
    secretary_detail = requests.get(f"{BASE_URL}/api/board/meetings/{meeting_id}", headers=auth(secretary_token), timeout=30)
    assert {item["title"] for item in secretary_detail.json()["actions"]} == {"Tarea Secretaría", "Tarea Vocal", "Acuerdo institucional"}
    assert requests.get(f"{BASE_URL}/api/board/meetings/{meeting_id}/secretary-notes", headers=auth(vocal_token), timeout=30).status_code == 403
    assert requests.get(f"{BASE_URL}/api/board/meetings/{meeting_id}/recordings", headers=auth(vocal_token), timeout=30).status_code == 403
    assert requests.put(f"{BASE_URL}/api/board/actions/{created_actions[1]['action_id']}", headers=auth(vocal_token), json={"status": "in_progress"}, timeout=30).status_code == 200
    assert requests.put(f"{BASE_URL}/api/board/actions/{created_actions[0]['action_id']}", headers=auth(vocal_token), json={"status": "in_progress"}, timeout=30).status_code == 403

    shared = requests.post(f"{BASE_URL}/api/board/meetings/{meeting_id}/documents", headers=auth(secretary_token), files={"file": ("shared.txt", b"shared", "text/plain")}, data={"classification": "board_institutional", "visibility": "board"}, timeout=30)
    assigned = requests.post(f"{BASE_URL}/api/board/meetings/{meeting_id}/documents", headers=auth(secretary_token), files={"file": ("assigned.txt", b"assigned", "text/plain")}, data={"classification": "board_institutional", "visibility": "assigned", "assigned_person_ids_json": json.dumps([fixture["accounts"]["vocal"]["person_id"]])}, timeout=30)
    assert shared.status_code == 201 and assigned.status_code == 201
    fixture["documents"].extend([shared.json()["document_id"], assigned.json()["document_id"]])
    for document_id in fixture["documents"]: DB["board_documents.files"].update_one({"_id": ObjectId(document_id)}, {"$set": {"metadata.qa_run": "iteration39"}})
    vocal_docs = requests.get(f"{BASE_URL}/api/board/meetings/{meeting_id}/documents", headers=auth(vocal_token), timeout=30).json()["items"]
    treasurer_docs = requests.get(f"{BASE_URL}/api/board/meetings/{meeting_id}/documents", headers=auth(treasurer_token), timeout=30).json()["items"]
    assert {item["filename"] for item in vocal_docs} == {"shared.txt", "assigned.txt"}
    assert {item["filename"] for item in treasurer_docs} == {"shared.txt"}

    private_id = ObjectId(); GridFSBucket(DB, bucket_name="board_documents").upload_from_stream_with_id(private_id, "pastoral-private.txt", BytesIO(b"private"), metadata={"meeting_id": meeting_id, "classification": "pastoral_confidential", "visibility": "board", "qa_run": "iteration39"})
    assert not any(item["document_id"] == str(private_id) for item in requests.get(f"{BASE_URL}/api/board/meetings/{meeting_id}/documents", headers=auth(fixture["pastor_token"]), timeout=30).json()["items"])
    assert requests.get(f"{BASE_URL}/api/board/documents/{private_id}", headers=auth(fixture["pastor_token"]), timeout=30).status_code == 404


def test_ending_membership_revokes_session_and_board_access(board_matrix_fixture):
    fixture = board_matrix_fixture; vocal = fixture["accounts"]["vocal"]
    old_token, _ = login(vocal["email"])
    membership = DB.board_memberships.find_one({"person_id": vocal["person_id"], "active": True}, {"_id": 0, "membership_id": 1})
    ended = requests.put(f"{BASE_URL}/api/board/members/{membership['membership_id']}/end", headers=auth(fixture["pastor_token"]), json={"reason": "QA finalización de membresía"}, timeout=30)
    assert ended.status_code == 200, ended.text
    assert requests.get(f"{BASE_URL}/api/board/access", headers=auth(old_token), timeout=30).status_code == 401
    fresh_token, _ = login(vocal["email"])
    access = requests.get(f"{BASE_URL}/api/board/access", headers=auth(fresh_token), timeout=30)
    assert access.status_code == 200 and access.json()["allowed"] is False
    assert requests.get(f"{BASE_URL}/api/board", headers=auth(fresh_token), timeout=30).status_code == 403