"""Regresión E2E pública del Mega-Bloque D con limpieza total."""
import io
import hashlib
import os
import uuid
import wave
from datetime import datetime, timedelta, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/")
ENV = dotenv_values("/app/backend/.env"); RUN = uuid.uuid4().hex[:8]
CREDS = {"pastor": ("coreqa.pastor@example.com", "CoreQA2026!Pastor"), "leader": ("coreqa.leader@example.com", "CoreQA2026!Leader"), "member": ("coreqa.member@example.com", "CoreQA2026!Member")}


def api(path): return BASE_URL + path
def auth(token): return {"Authorization": f"Bearer {token}"}
def login(role):
    email, password = CREDS[role]; response = requests.post(api("/api/auth/login"), json={"email": email, "password": password}, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="module")
def database():
    client = MongoClient(ENV["MONGO_URL"]); db = client[ENV["DB_NAME"]]
    yield db
    meetings = db.board_meetings.distinct("meeting_id", {"qa_run": RUN})
    memberships = db.board_memberships.distinct("membership_id", {"qa_run": RUN})
    qa_assignments = db.door_assignments.distinct("assignment_id", {"qa_run": RUN})
    cells = db.cells.distinct("cell_id", {"qa_run": RUN}); networks = db.cell_networks.distinct("network_id", {"qa_run": RUN})
    needs = db.cell_needs.distinct("need_id", {"cell_id": {"$in": cells}})
    proposals = db.board_proposals.distinct("proposal_id", {"meeting_id": {"$in": meetings}})
    upload_ids = db.board_recording_uploads.distinct("upload_id", {"meeting_id": {"$in": meetings}})
    recordings = list(db["board_recordings.files"].find({"metadata.meeting_id": {"$in": meetings}}, {"_id": 1}))
    documents = list(db["board_documents.files"].find({"metadata.meeting_id": {"$in": meetings}}, {"_id": 1}))
    for recording in recordings:
        db["board_recordings.chunks"].delete_many({"files_id": recording["_id"]})
    db["board_recordings.files"].delete_many({"_id": {"$in": [item["_id"] for item in recordings]}})
    db["board_documents.chunks"].delete_many({"files_id": {"$in": [item["_id"] for item in documents]}})
    db["board_documents.files"].delete_many({"_id": {"$in": [item["_id"] for item in documents]}})
    staged = list(db["board_recording_staging.files"].find({"metadata.upload_id": {"$in": upload_ids}}, {"_id": 1}))
    db["board_recording_staging.chunks"].delete_many({"files_id": {"$in": [item["_id"] for item in staged]}})
    db["board_recording_staging.files"].delete_many({"_id": {"$in": [item["_id"] for item in staged]}})
    for name in ["board_meeting_attendance", "board_agenda_items", "board_secretary_notes", "board_secretary_note_versions", "board_proposals", "board_votes", "board_actions", "board_minutes", "board_transcript_versions", "board_transcript_segments", "board_speaker_mappings", "board_ai_artifacts", "board_recording_uploads"]:
        db[name].delete_many({"meeting_id": {"$in": meetings}})
    db.board_votes.delete_many({"proposal_id": {"$in": proposals}})
    db.board_meetings.delete_many({"meeting_id": {"$in": meetings}})
    db.door_assignments.delete_many({"$or": [{"source_board_membership_id": {"$in": memberships}}, {"qa_run": RUN}]})
    db.board_memberships.delete_many({"membership_id": {"$in": memberships}})
    cases = db.door_cases.distinct("case_id", {"source_type": "cell_need", "source_id": {"$in": needs}})
    db.door_case_events.delete_many({"case_id": {"$in": cases}}); db.door_cases.delete_many({"case_id": {"$in": cases}})
    entity_ids = [*meetings, *memberships, *qa_assignments, *cases, *proposals, *[str(item["_id"]) for item in recordings], *[str(item["_id"]) for item in documents]]
    db.board_audit_events.delete_many({"$or": [{"entity_id": {"$in": entity_ids}}, {"changes.meeting_id": {"$in": meetings}}, {"changes.need_id": {"$in": needs}}]})
    for name in ["cell_needs", "cell_followups", "cell_memberships", "cell_role_assignments", "cell_timeline"]: db[name].delete_many({"cell_id": {"$in": cells}})
    db.cells.delete_many({"cell_id": {"$in": cells}}); db.cell_networks.delete_many({"network_id": {"$in": networks}})
    client.close()


def test_doors_board_meeting_case_and_audio_flow(database):
    pastor = login("pastor"); leader = login("leader"); member = login("member")
    pt, lt, mt = pastor["token"], leader["token"], member["token"]
    pp, lp, mp = pastor["user"]["person_id"], leader["user"]["person_id"], member["user"]["person_id"]
    assert requests.get(api("/api/board"), headers=auth(mt), timeout=30).status_code == 403
    board = requests.get(api("/api/board"), headers=auth(pt), timeout=30); assert board.status_code == 200
    positions = {item["position_key"]: item for item in board.json()["positions"]}
    member_payloads = [
        (pp, "president", ["board.read", "board.meetings.write", "board.vote", "board.actions.write"], ["door_1"]),
        (lp, "secretary", ["board.read", "board.meetings.write", "board.vote", "board.actions.write", "board.audio.manage", "board.minutes.review", "board.notes.write"], ["door_2"]),
        (mp, "member", ["board.read", "board.vote"], []),
    ]
    membership_ids = []
    for person_id, position, permissions, doors in member_payloads:
        response = requests.post(api("/api/board/members"), headers=auth(pt), json={"person_id": person_id, "position_key": position, "voting_rights": True, "permissions": permissions, "supervised_door_keys": doors, "ministry_ids": []}, timeout=30)
        assert response.status_code == 201, response.text
        membership_ids.append(response.json()["membership_id"]); database.board_memberships.update_one({"membership_id": response.json()["membership_id"]}, {"$set": {"qa_run": RUN}})
    leader = login("leader"); member = login("member")
    lt, mt = leader["token"], member["token"]
    assert requests.get(api("/api/board"), headers=auth(mt), timeout=30).status_code == 200
    assignments = list(database.door_assignments.find({"source_board_membership_id": {"$in": membership_ids}}))
    assert {(item["door_key"], item["role"]) for item in assignments} == {("door_1", "supervisor"), ("door_2", "supervisor")}
    explicit = requests.post(api("/api/doors/door_1/assignments"), headers=auth(pt), json={"person_id": pp, "role": "door_leader", "notes": "QA explícita"}, timeout=30)
    assert explicit.status_code == 201, explicit.text; database.door_assignments.update_one({"assignment_id": explicit.json()["assignment_id"]}, {"$set": {"qa_run": RUN}})
    assert database.door_assignments.count_documents({"door_key": "door_1", "person_id": pp, "active": True}) == 2

    network = requests.post(api("/api/cellular/networks"), headers=auth(pt), json={"name": f"QA D {RUN}", "status": "active"}, timeout=30); assert network.status_code == 201
    network_id = network.json()["network_id"]; database.cell_networks.update_one({"network_id": network_id}, {"$set": {"qa_run": RUN}})
    cell = requests.post(api("/api/cellular/cells"), headers=auth(pt), json={"name": f"QA D Cell {RUN}", "code": f"QAD{RUN[:6]}", "network_id": network_id, "address": "Columbus, Ohio", "meeting_day": "Sábado", "meeting_time": "19:00", "capacity": 15, "opened_at": datetime.now(timezone.utc).date().isoformat(), "status": "active"}, timeout=30); assert cell.status_code == 201, cell.text
    cell_id = cell.json()["cell_id"]; database.cells.update_one({"cell_id": cell_id}, {"$set": {"qa_run": RUN}})
    need = requests.post(api("/api/cellular/needs"), headers=auth(pt), json={"cell_id": cell_id, "person_id": mp, "need_type": "illness", "description": "QA respuesta pastoral", "priority": "high"}, timeout=30)
    assert need.status_code == 201, need.text; need_id = need.json()["need_id"]; case_id = need.json()["door_case_id"]
    assert database.door_cases.count_documents({"source_type": "cell_need", "source_id": need_id}) == 1
    intake = requests.post(api(f"/api/doors/intake/cell-needs/{need_id}"), headers=auth(pt), json={}, timeout=30); assert intake.status_code == 200 and intake.json()["case_id"] == case_id
    case_update = requests.put(api(f"/api/doors/cases/{case_id}"), headers=auth(pt), json={"status": "in_progress", "door_key": "door_1", "responsible_person_id": pp, "next_action": "Visitar", "next_action_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}, timeout=30)
    assert case_update.status_code == 200 and database.cell_needs.find_one({"need_id": need_id})["assigned_door_key"] == "door_1"

    meeting = requests.post(api("/api/board/meetings"), headers=auth(pt), json={"title": f"QA D Reunión {RUN}", "scheduled_at": datetime.now(timezone.utc).isoformat(), "location": "Columbus, Ohio", "modality": "hybrid", "chair_person_id": pp, "secretary_person_id": lp, "planned_duration_minutes": 60, "purpose": "Validar gobierno D", "agenda_titles": ["Apertura", "Sistema Celular", "Votaciones", "Cierre"]}, timeout=30)
    assert meeting.status_code == 201, meeting.text; meeting_id = meeting.json()["meeting_id"]; database.board_meetings.update_one({"meeting_id": meeting_id}, {"$set": {"qa_run": RUN}})
    attendance = requests.put(api(f"/api/board/meetings/{meeting_id}/attendance"), headers=auth(pt), json={"items": [{"person_id": pp, "status": "present", "recording_notice_acknowledged": True}, {"person_id": lp, "status": "remote", "recording_notice_acknowledged": True}, {"person_id": mp, "status": "present", "recording_notice_acknowledged": True}]}, timeout=30)
    assert attendance.status_code == 200 and attendance.json()["quorum"]["has_quorum"] is True
    started = requests.post(api(f"/api/board/meetings/{meeting_id}/start"), headers=auth(pt), json={"recording_notice_confirmed": True}, timeout=30); assert started.status_code == 200
    detail = requests.get(api(f"/api/board/meetings/{meeting_id}"), headers=auth(pt), timeout=30).json(); agenda_id = detail["agenda"][0]["agenda_item_id"]
    assert requests.put(api(f"/api/board/agenda/{agenda_id}"), headers=auth(pt), json={"status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()}, timeout=30).status_code == 200
    assert requests.put(api(f"/api/board/agenda/{agenda_id}"), headers=auth(pt), json={"status": "completed", "ended_at": (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat(), "discussion": "Discusión QA", "decision": "Decisión QA"}, timeout=30).status_code == 200
    note1 = requests.put(api(f"/api/board/meetings/{meeting_id}/secretary-notes"), headers=auth(lt), json={"content": "Notas humanas v1"}, timeout=30); note2 = requests.put(api(f"/api/board/meetings/{meeting_id}/secretary-notes"), headers=auth(lt), json={"content": "Notas humanas v2"}, timeout=30)
    assert note1.status_code == 200 and note2.json()["version"] == 2 and database.board_secretary_note_versions.count_documents({"meeting_id": meeting_id}) == 2
    proposal = requests.post(api(f"/api/board/meetings/{meeting_id}/proposals"), headers=auth(pt), json={"proposer_person_id": pp, "text": "Aprobar QA"}, timeout=30); assert proposal.status_code == 201
    proposal_id = proposal.json()["proposal_id"]
    bypass = requests.put(api(f"/api/board/proposals/{proposal_id}"), headers=auth(pt), json={"status": "approved"}, timeout=30)
    assert bypass.status_code == 409
    assert requests.put(api(f"/api/board/proposals/{proposal_id}"), headers=auth(pt), json={"status": "ready_for_vote"}, timeout=30).status_code == 200
    for token, choice in [(pt, "yes"), (lt, "yes"), (mt, "abstain")]:
        vote = requests.post(api(f"/api/board/proposals/{proposal_id}/vote"), headers=auth(token), json={"choice": choice}, timeout=30); assert vote.status_code == 200, vote.text
    assert database.board_votes.count_documents({"proposal_id": proposal_id}) == 3
    assert database.board_proposals.find_one({"proposal_id": proposal_id})["status"] == "approved"
    action = requests.post(api(f"/api/board/meetings/{meeting_id}/actions"), headers=auth(pt), json={"title": "Completar acción QA", "responsible_person_id": lp, "action_type": "task", "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()}, timeout=30); assert action.status_code == 201
    manual_minute = requests.put(api(f"/api/board/meetings/{meeting_id}/manual-minute"), headers=auth(lt), json={"content": "Minuta humana QA"}, timeout=30)
    assert manual_minute.status_code == 200

    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav: wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000); wav.writeframes(b"\x00\x00" * 800)
    raw = audio.getvalue(); upload = requests.post(api("/api/board/recordings/uploads"), headers=auth(pt), json={"meeting_id": meeting_id, "content_type": "audio/wav"}, timeout=30); assert upload.status_code == 201, upload.text
    upload_id = upload.json()["upload_id"]; chunk_headers = {**auth(pt), "Content-Type": "application/octet-stream"}
    assert requests.put(api(f"/api/board/recordings/uploads/{upload_id}/chunks/0"), headers=chunk_headers, data=raw, timeout=30).status_code == 200
    completed = requests.post(api(f"/api/board/recordings/uploads/{upload_id}/complete"), headers=auth(pt), json={"duration_seconds": 0.1}, timeout=60)
    assert completed.status_code == 200, completed.text
    recording_id = completed.json()["recording_id"]; listing = requests.get(api(f"/api/board/meetings/{meeting_id}/recordings"), headers=auth(pt), timeout=30)
    assert listing.status_code == 200 and any(item["recording_id"] == recording_id for item in listing.json()["items"])
    assert requests.get(api(f"/api/board/meetings/{meeting_id}/recordings"), headers=auth(mt), timeout=30).status_code == 403
    transcription_item = next(item for item in listing.json()["items"] if item["recording_id"] == recording_id)
    assert transcription_item["transcription_status"] in {"processing", "completed", "blocked"}
    if transcription_item["transcription_status"] == "blocked":
        assert transcription_item["transcription_message"] == "Identificación de participantes pendiente de procesamiento STT diarizado."
    retry_stt = requests.post(api(f"/api/board/recordings/{recording_id}/transcribe"), headers=auth(pt), json={}, timeout=30)
    assert retry_stt.status_code in {200, 503}
    no_ai_consent = requests.post(api(f"/api/board/meetings/{meeting_id}/ai-draft"), headers=auth(pt), json={"external_processing_acknowledged": False}, timeout=30)
    assert no_ai_consent.status_code == 409
    ai_status = requests.get(api("/api/board/ai/status"), headers=auth(pt), timeout=30)
    assert ai_status.status_code == 200 and ai_status.json()["status"] in {"READY", "BLOCKED"}
    ai_draft = requests.post(api(f"/api/board/meetings/{meeting_id}/ai-draft"), headers=auth(pt), json={"external_processing_acknowledged": True}, timeout=180)
    if ai_status.json()["status"] == "READY":
        assert ai_draft.status_code == 200, ai_draft.text
        assert ai_draft.json()["status"] == "ai_draft" and ai_draft.json()["content"].get("executive_summary") is not None
    else:
        assert ai_draft.status_code == 503 and ai_draft.json()["detail"]["status"] == "BLOCKED"
    document_bytes = b"Documento QA de Junta"
    document = requests.post(api(f"/api/board/meetings/{meeting_id}/documents"), headers=auth(pt), files={"file": ("acuerdo-qa.txt", document_bytes, "text/plain")}, timeout=30)
    assert document.status_code == 201, document.text
    document_id = document.json()["document_id"]
    documents = requests.get(api(f"/api/board/meetings/{meeting_id}/documents"), headers=auth(mt), timeout=30)
    assert documents.status_code == 200 and any(item["document_id"] == document_id for item in documents.json()["items"])
    document_download = requests.get(api(f"/api/board/documents/{document_id}"), headers=auth(mt), timeout=30)
    assert document_download.status_code == 200 and document_download.content == document_bytes
    minutes_book = requests.get(api("/api/board/minutes"), headers=auth(mt), timeout=30)
    assert minutes_book.status_code == 200 and not [item for item in minutes_book.json()["items"] if item["meeting_id"] == meeting_id]
    secretary_minutes = requests.get(api("/api/board/minutes"), headers=auth(lt), timeout=30)
    assert secretary_minutes.status_code == 200 and [item for item in secretary_minutes.json()["items"] if item["meeting_id"] == meeting_id]
    if ai_status.json()["status"] == "READY":
        ai_minute = next(item for item in minutes_book.json()["items"] if item["meeting_id"] == meeting_id and item["minute_type"] == "ai_draft")
        ai_official = requests.put(api(f"/api/board/minutes/{ai_minute['minute_id']}/status"), headers=auth(lt), json={"status": "official"}, timeout=30)
        assert ai_official.status_code == 409
    official = requests.put(api(f"/api/board/minutes/{manual_minute.json()['minute_id']}/status"), headers=auth(lt), json={"status": "official", "review_note": "Revisión humana QA"}, timeout=30)
    assert official.status_code == 200 and official.json()["status"] == "official"
    audit = requests.get(api("/api/board/audit?limit=200"), headers=auth(pt), timeout=30)
    assert audit.status_code == 200 and any(item["entity_id"] == meeting_id for item in audit.json()["items"])
    assert requests.get(api("/api/board/audit"), headers=auth(mt), timeout=30).status_code == 403
    vote_events = [item for item in audit.json()["items"] if item["event_type"] == "vote_cast"]
    assert vote_events and all("choice" not in item["changes"] and "person_id" not in item["changes"] for item in vote_events)
    downloaded = requests.get(api(f"/api/board/recordings/{recording_id}"), headers=auth(pt), timeout=30)
    assert downloaded.status_code == 200 and downloaded.content == raw and downloaded.headers.get("x-content-sha256") == hashlib.sha256(raw).hexdigest()
    closed = requests.post(api(f"/api/board/meetings/{meeting_id}/close"), headers=auth(pt), json={}, timeout=30); assert closed.status_code == 200 and closed.json()["actual_duration_minutes"] >= 0