import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from care_service import ensure_care_indexes


PREFIX = "care.e2e."
PASSWORD = "CareE2E2026!"


async def make_user(role: str, name: str, created_by: str | None = None):
    user_id, person_id = ObjectId(), ObjectId(); email = f"{PREFIX}{uuid.uuid4().hex[:8]}@example.com"; now = datetime.now(timezone.utc)
    await server.db.persons.insert_one({"_id": person_id, "person_number": f"VV-CARE{str(person_id)[-5:].upper()}", "nombre": name, "apellido": "E2E", "search_key": f"{name} e2e".lower(), "idempotency_key": f"care:e2e:{email}", "version": 1, "auth_user_id": str(user_id), "created_by": created_by or str(user_id), "created_at": now, "updated_at": now})
    await server.db.users.insert_one({"_id": user_id, "nombre": name, "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": str(person_id), "is_active": True, "token_version": 1, **access_defaults_for_role(role)})
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email}


async def make_person(name: str, created_by: str):
    person_id = ObjectId(); now = datetime.now(timezone.utc)
    await server.db.persons.insert_one({"_id": person_id, "person_number": f"VV-CARE{str(person_id)[-5:].upper()}", "nombre": name, "apellido": "E2E", "search_key": f"{name} e2e".lower(), "idempotency_key": f"care:e2e:person:{person_id}", "version": 1, "created_by": created_by, "created_at": now, "updated_at": now})
    return str(person_id)


async def login(email: str):
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client, {"Authorization": f"Bearer {response.json()['token']}"}


async def cleanup():
    users = await server.db.users.find({"email": {"$regex": f"^{PREFIX}"}}, {"_id": 1, "person_id": 1}).to_list(100)
    person_ids = [item["person_id"] for item in users if item.get("person_id")]
    extra_people = await server.db.persons.find({"idempotency_key": {"$regex": "^care:e2e:"}}, {"_id": 1}).to_list(100)
    all_person_ids = list(set(person_ids + [str(item["_id"]) for item in extra_people]))
    cases = await server.db.pastoral_cases.find({"person_id": {"$in": all_person_ids}}, {"_id": 0, "case_id": 1}).to_list(100)
    case_ids = [item["case_id"] for item in cases]
    visits = await server.db.pastoral_visitation_participants.distinct("visit_id", {"person_id": {"$in": all_person_ids}})
    for collection in ["pastoral_case_assignments", "pastoral_contact_attempts", "pastoral_case_notes", "care_alerts"]:
        await server.db[collection].delete_many({"case_id": {"$in": case_ids}})
    await server.db.op72_records.delete_many({"person_id": {"$in": all_person_ids}})
    await server.db.pastoral_cases.delete_many({"case_id": {"$in": case_ids}})
    await server.db.care_audit_events.delete_many({"$or": [{"entity_id": {"$in": case_ids + visits}}, {"actor_user_id": {"$in": [str(item["_id"]) for item in users]}}]})
    await server.db.pastoral_visitation_summaries.delete_many({"visit_id": {"$in": visits}})
    await server.db.pastoral_visitation_participants.delete_many({"visit_id": {"$in": visits}})
    await server.db.pastoral_visitations.delete_many({"visit_id": {"$in": visits}})
    household_ids = await server.db.household_memberships.distinct("household_id", {"person_id": {"$in": all_person_ids}})
    await server.db.household_memberships.delete_many({"person_id": {"$in": all_person_ids}}); await server.db.households.delete_many({"_id": {"$in": household_ids}})
    enrollments = await server.db.process_enrollments.find({"person_id": {"$in": all_person_ids}, "source": "care_op72"}, {"_id": 0, "enrollment_id": 1}).to_list(100)
    enrollment_ids = [item["enrollment_id"] for item in enrollments]
    for collection in ["process_stage_progress", "process_timeline", "process_evidence", "process_alerts"]:
        await server.db[collection].delete_many({"enrollment_id": {"$in": enrollment_ids}})
    await server.db.process_enrollments.delete_many({"enrollment_id": {"$in": enrollment_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in all_person_ids]}})
    await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})


@pytest.mark.asyncio
async def test_care_full_flow_unique_op72_vault_privacy_reactivation_escalation_and_household_visit():
    await cleanup(); await ensure_care_indexes(server.db)
    pastor = await make_user("pastor", "Pastor Care"); leader = await make_user("lider", "Lider Care")
    person = await make_user("persona", "Persona Cuidada", leader["user_id"]); relative_id = await make_person("Familiar Cuidado", pastor["user_id"])
    household_id = str(uuid.uuid4()); now = datetime.now(timezone.utc)
    await server.db.households.insert_one({"_id": household_id, "nombre_hogar": "Hogar Cuidado E2E", "created_by": pastor["user_id"], "created_at": now, "updated_at": now})
    await server.db.household_memberships.insert_many([{"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": person["person_id"], "created_at": now}, {"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": relative_id, "created_at": now}])
    pastor_client, pastor_headers = await login(pastor["email"]); leader_client, leader_headers = await login(leader["email"]); person_client, person_headers = await login(person["email"])
    try:
        original_date = now - timedelta(days=4)
        first = await pastor_client.post("/api/care/op72", json={"person_id": person["person_id"], "decision_at": original_date.isoformat(), "source_type": "manual"}, headers=pastor_headers)
        assert first.status_code == 201, first.text
        assert first.json()["created"] is True
        record = first.json()["record"]; op72_id, case_id = record["op72_id"], record["case_id"]
        repeated = await pastor_client.post("/api/care/op72", json={"person_id": person["person_id"], "decision_at": now.isoformat(), "source_type": "manual"}, headers=pastor_headers)
        assert repeated.status_code == 201 and repeated.json()["created"] is False
        assert repeated.json()["record"]["op72_id"] == op72_id
        assert repeated.json()["record"]["first_conversion_at"] == record["first_conversion_at"]
        assert await server.db.op72_records.count_documents({"person_id": person["person_id"]}) == 1

        alerts = await pastor_client.get("/api/care/alerts", headers=pastor_headers)
        assert alerts.status_code == 200
        assert {item["alert_type"] for item in alerts.json()["items"]} >= {"unassigned_24h", "uncontacted_72h"}
        assigned = await pastor_client.post(f"/api/care/cases/{case_id}/assignments", json={"assignee_person_id": leader["person_id"], "assignment_role": "primary"}, headers=pastor_headers)
        assert assigned.status_code == 201, assigned.text
        leader_detail = await leader_client.get(f"/api/care/cases/{case_id}", headers=leader_headers)
        assert leader_detail.status_code == 200
        denied = await person_client.get("/api/care/cases", headers=person_headers)
        assert denied.status_code == 403

        core_note_text = "Nota pastoral secreta E2E que nunca debe persistir en claro"
        core_note = await pastor_client.post(f"/api/care/cases/{case_id}/notes", json={"content": core_note_text, "visibility": "pastoral_core"}, headers=pastor_headers)
        assert core_note.status_code == 201, core_note.text
        stored_note = await server.db.pastoral_case_notes.find_one({"note_id": core_note.json()["note_id"]})
        assert core_note_text not in str(stored_note) and stored_note.get("ciphertext")
        leader_notes = await leader_client.get(f"/api/care/cases/{case_id}/notes", headers=leader_headers)
        assert leader_notes.status_code == 200 and leader_notes.json()["total"] == 0
        team_note = await leader_client.post(f"/api/care/cases/{case_id}/notes", json={"content": "Actualización del equipo asignado", "visibility": "assigned_team"}, headers=leader_headers)
        assert team_note.status_code == 201
        leader_notes = await leader_client.get(f"/api/care/cases/{case_id}/notes", headers=leader_headers)
        assert leader_notes.json()["total"] == 1 and leader_notes.json()["items"][0]["content"] == "Actualización del equipo asignado"
        assert await server.db.care_audit_events.count_documents({"action": "note_viewed", "entity_id": team_note.json()["note_id"]}) >= 1

        contact = await leader_client.post(f"/api/care/cases/{case_id}/contacts", json={"method": "call", "outcome": "successful", "occurred_at": now.isoformat(), "next_step": "Visita familiar", "next_step_at": (now + timedelta(days=2)).isoformat()}, headers=leader_headers)
        assert contact.status_code == 201, contact.text
        await leader_client.patch(f"/api/care/cases/{case_id}", json={"priority": "urgent"}, headers=leader_headers)
        escalated = await leader_client.post(f"/api/care/cases/{case_id}/escalate", json={"authority_person_id": pastor["person_id"], "reason": "Situación crítica requiere intervención inmediata"}, headers=leader_headers)
        assert escalated.status_code == 200 and escalated.json()["status"] == "escalated"
        audit = await server.db.care_audit_events.find_one({"action": "urgent_escalation", "entity_id": case_id}, {"_id": 0})
        assert audit and audit["actor_user_id"] == leader["user_id"] and audit["changes"]["reason"]

        enrollment = await server.db.process_enrollments.find_one({"enrollment_id": record["consolidation_enrollment_id"]}, {"_id": 0})
        original_stage = enrollment["current_stage_key"]
        paused = await pastor_client.post(f"/api/care/op72/{op72_id}/pause", json={"reason": "Persona se ausentó temporalmente"}, headers=pastor_headers)
        assert paused.status_code == 200 and paused.json()["status"] == "paused"
        reactivated = await pastor_client.post(f"/api/care/op72/{op72_id}/reactivate", json={"reason": "Persona regresó después de un año"}, headers=pastor_headers)
        assert reactivated.status_code == 200 and reactivated.json()["status"] == "active"
        enrollment_after = await server.db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
        op72_after = await server.db.op72_records.find_one({"op72_id": op72_id}, {"_id": 0})
        assert enrollment_after["current_stage_key"] == original_stage and enrollment_after["status"] == "active"
        expected_persisted_date = original_date.replace(tzinfo=None, microsecond=(original_date.microsecond // 1000) * 1000)
        assert op72_after["first_conversion_at"] == expected_persisted_date and await server.db.op72_records.count_documents({"person_id": person["person_id"]}) == 1

        visit = await pastor_client.post("/api/care/visitations", json={"household_id": household_id, "participants": [{"person_id": person["person_id"], "case_id": case_id}, {"person_id": relative_id}], "scheduled_at": (now + timedelta(days=1)).isoformat(), "lead_visitor_person_id": pastor["person_id"], "visitor_person_ids": [leader["person_id"]], "purpose": "Acompañamiento familiar"}, headers=pastor_headers)
        assert visit.status_code == 201, visit.text
        visit_id = visit.json()["visit_id"]
        completed = await pastor_client.post(f"/api/care/visitations/{visit_id}/complete", json={"participant_results": [{"person_id": person["person_id"], "outcome": "successful", "next_step": "Continuar seguimiento"}, {"person_id": relative_id, "outcome": "rescheduled", "next_step": "Coordinar llamada"}], "confidential_summary": "Resumen cifrado del hogar E2E"}, headers=pastor_headers)
        assert completed.status_code == 200 and completed.json()["status"] == "completed"
        participants = await server.db.pastoral_visitation_participants.find({"visit_id": visit_id}, {"_id": 0}).to_list(10)
        assert len(participants) == 2 and {item["person_id"] for item in participants} == {person["person_id"], relative_id}
        encrypted_summary = await server.db.pastoral_visitation_summaries.find_one({"visit_id": visit_id})
        assert encrypted_summary.get("ciphertext") and "Resumen cifrado" not in str(encrypted_summary)

        private_profile = await person_client.get(f"/api/core/persons/{person['person_id']}/profile", headers=person_headers)
        assert private_profile.status_code == 200 and all(section["section_key"] != "cuidado_pastoral" for section in private_profile.json()["sections"])
        authorized_profile = await pastor_client.get(f"/api/core/persons/{person['person_id']}/profile", headers=pastor_headers)
        assert authorized_profile.status_code == 200 and any(section["section_key"] == "cuidado_pastoral" for section in authorized_profile.json()["sections"])
    finally:
        await pastor_client.aclose(); await leader_client.aclose(); await person_client.aclose(); await cleanup()
