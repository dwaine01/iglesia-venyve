import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from membership_documents import verification_token
from operations_engine import ensure_operations_indexes, recurrence_starts
from operations_models import RecurrenceRule


PREFIX = "operations.e2e."
PASSWORD = "OperationsE2E2026!"


async def make_user(role, name):
    user_id, person_id = ObjectId(), ObjectId(); email = f"{PREFIX}{uuid.uuid4().hex[:8]}@example.com"; now = datetime.now(timezone.utc)
    await server.db.persons.insert_one({"_id": person_id, "person_number": f"VV-OP{str(person_id)[-6:].upper()}", "nombre": name, "apellido": "Operaciones", "search_key": f"{name} operaciones".lower(), "idempotency_key": f"operations:e2e:{email}", "version": 1, "auth_user_id": str(user_id), "created_at": now, "updated_at": now})
    await server.db.users.insert_one({"_id": user_id, "nombre": name, "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": str(person_id), "is_active": True, "token_version": 1, **access_defaults_for_role(role)})
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email, "name": name}


async def login(email):
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client, {"Authorization": f"Bearer {response.json()['token']}"}


async def cleanup():
    events = await server.db.operation_events.find({"title": {"$regex": "^OPS E2E"}}, {"_id": 0, "event_id": 1, "attachments": 1}).to_list(100)
    event_ids = [item["event_id"] for item in events]; file_ids = [ObjectId(file["file_id"]) for item in events for file in item.get("attachments", []) if ObjectId.is_valid(file.get("file_id"))]
    occurrence_ids = await server.db.operation_event_occurrences.distinct("occurrence_id", {"event_id": {"$in": event_ids}})
    shift_ids = await server.db.operation_shifts.distinct("shift_id", {"event_id": {"$in": event_ids}})
    assignment_ids = await server.db.operation_volunteer_assignments.distinct("assignment_id", {"event_id": {"$in": event_ids}})
    registration_ids = await server.db.operation_registrations.distinct("registration_id", {"event_id": {"$in": event_ids}})
    await server.db.operation_audit_events.delete_many({"entity_id": {"$in": event_ids + occurrence_ids + shift_ids + assignment_ids + registration_ids}})
    for collection in ["operation_event_occurrences", "operation_shift_templates", "operation_shifts", "operation_volunteer_assignments", "operation_registrations", "operation_checkins", "operation_notifications"]:
        await server.db[collection].delete_many({"event_id": {"$in": event_ids}})
    await server.db.operation_events.delete_many({"event_id": {"$in": event_ids}})
    if file_ids:
        await server.db["operation_attachments.chunks"].delete_many({"files_id": {"$in": file_ids}}); await server.db["operation_attachments.files"].delete_many({"_id": {"$in": file_ids}})
    users = await server.db.users.find({"email": {"$regex": f"^{PREFIX}"}}, {"_id": 1, "person_id": 1}).to_list(100)
    person_ids = [item["person_id"] for item in users if item.get("person_id")]
    memberships = await server.db.person_memberships.find({"person_id": {"$in": person_ids}}, {"_id": 0, "membership_id": 1}).to_list(100)
    await server.db.person_memberships.delete_many({"person_id": {"$in": person_ids}}); await server.db.membership_number_registry.delete_many({"person_id": {"$in": person_ids}})
    await server.db.person_attendance.delete_many({"person_id": {"$in": person_ids}, "actividad": {"$regex": "^OPS E2E"}})
    await server.db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in person_ids]}}); await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})


def test_recurrence_engine_supports_unique_weekly_and_monthly_without_schema_change():
    start = datetime(2026, 1, 31, 15, 0, tzinfo=timezone.utc)
    assert len(recurrence_starts(start, "America/New_York", RecurrenceRule(), 365)) == 1
    weekly = recurrence_starts(start, "America/New_York", RecurrenceRule(frequency="weekly", weekdays=[start.astimezone().weekday()], end_mode="count", count=4), 365)
    monthly = recurrence_starts(start, "America/New_York", RecurrenceRule(frequency="monthly", month_day=31, end_mode="count", count=3), 365)
    assert len(weekly) == 4 and all((weekly[index + 1] - weekly[index]).days == 7 for index in range(3))
    assert len(monthly) == 3 and monthly[1].month == 2 and monthly[2].month == 3


@pytest.mark.asyncio
async def test_operations_full_flow_recurring_shifts_registration_qr_checkin_close_metrics_and_files():
    await cleanup(); await ensure_operations_indexes()
    pastor = await make_user("pastor", "Pastor E2E"); leader = await make_user("lider", "Líder Checkin"); volunteer = await make_user("persona", "Voluntario E2E"); attendee = await make_user("persona", "Asistente E2E")
    membership_id = str(uuid.uuid4()); await server.db.person_memberships.insert_one({"_id": membership_id, "membership_id": membership_id, "person_id": attendee["person_id"], "member_number": "OPS-E2E-01", "status": "active", "direct_membership": True})
    pastor_client, pastor_headers = await login(pastor["email"]); leader_client, leader_headers = await login(leader["email"]); volunteer_client, volunteer_headers = await login(volunteer["email"]); attendee_client, attendee_headers = await login(attendee["email"])
    try:
        start = datetime.now(timezone.utc) + timedelta(days=2); start = start.replace(hour=23, minute=0, second=0, microsecond=0); weekday = start.astimezone().weekday()
        payload = {"title": "OPS E2E Servicio recurrente", "event_type": "service", "location": "Santuario", "timezone": "America/New_York", "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=2)).isoformat(), "capacity": 50, "registration_mode": "open", "status": "published", "recurrence": {"frequency": "weekly", "interval": 1, "weekdays": [weekday], "end_mode": "count", "count": 3}}
        created = await pastor_client.post("/api/operations/events", json=payload, headers=pastor_headers)
        assert created.status_code == 201, created.text
        event_id = created.json()["event_id"]; assert created.json()["materialization"]["created_occurrences"] == 3
        detail = await pastor_client.get(f"/api/operations/events/{event_id}", headers=pastor_headers)
        assert detail.status_code == 200 and len(detail.json()["occurrences"]) == 3
        occurrence_id = detail.json()["occurrences"][0]["occurrence_id"]

        denied_event = await volunteer_client.post("/api/operations/events", json=payload, headers=volunteer_headers)
        assert denied_event.status_code == 403
        shift = await pastor_client.post(f"/api/operations/events/{event_id}/shift-templates", json={"name": "Recepción", "role_name": "Anfitrión", "scope": "all_occurrences", "start_offset_minutes": -45, "duration_minutes": 180, "required_volunteers": 2}, headers=pastor_headers)
        assert shift.status_code == 201, shift.text
        assert shift.json()["shifts_created"] == 3
        occurrence = await pastor_client.get(f"/api/operations/occurrences/{occurrence_id}", headers=pastor_headers); shift_id = occurrence.json()["shifts"][0]["shift_id"]
        assignment = await pastor_client.post(f"/api/operations/shifts/{shift_id}/assignments", json={"person_id": volunteer["person_id"]}, headers=pastor_headers)
        assert assignment.status_code == 201, assignment.text
        assignment_id = assignment.json()["assignment_id"]
        notifications = await volunteer_client.get("/api/operations/notifications", headers=volunteer_headers)
        assert notifications.status_code == 200 and any(item["type"] == "volunteer_assignment" for item in notifications.json()["items"])
        confirmed = await volunteer_client.patch(f"/api/operations/volunteer-assignments/{assignment_id}", json={"status": "confirmed"}, headers=volunteer_headers)
        assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"

        self_registration = await attendee_client.post(f"/api/operations/occurrences/{occurrence_id}/registrations", json={"person_id": attendee["person_id"], "party_size": 1}, headers=attendee_headers)
        assert self_registration.status_code == 201
        guest = await leader_client.post(f"/api/operations/occurrences/{occurrence_id}/registrations", json={"guest_name": "Invitado E2E", "party_size": 2}, headers=leader_headers)
        assert guest.status_code == 201, guest.text
        forbidden_guest = await volunteer_client.post(f"/api/operations/occurrences/{occurrence_id}/registrations", json={"guest_name": "No permitido"}, headers=volunteer_headers)
        assert forbidden_guest.status_code == 403
        private_detail = await attendee_client.get(f"/api/operations/occurrences/{occurrence_id}", headers=attendee_headers)
        assert private_detail.status_code == 200 and len(private_detail.json()["registrations"]) == 1
        assert private_detail.json()["registrations"][0].get("guest_email") is None and private_detail.json()["assignments"] == []
        forbidden_checkin = await attendee_client.post(f"/api/operations/occurrences/{occurrence_id}/check-ins", json={"person_id": attendee["person_id"], "kind": "auto", "idempotency_key": f"ops:e2e:{uuid.uuid4()}"}, headers=attendee_headers)
        assert forbidden_checkin.status_code == 403
        forbidden_upload = await attendee_client.post(f"/api/operations/events/{event_id}/attachments", files={"file": ("operacion.pdf", b"%PDF-1.4\nOPS", "application/pdf")}, headers=attendee_headers)
        assert forbidden_upload.status_code == 403

        search = await leader_client.get(f"/api/operations/occurrences/{occurrence_id}/checkin/search", params={"q": "Asistente E2E"}, headers=leader_headers)
        assert search.status_code == 200 and any(item.get("person_id") == attendee["person_id"] for item in search.json()["items"])
        qr = verification_token(membership_id)
        first_checkin = await leader_client.post(f"/api/operations/occurrences/{occurrence_id}/check-ins", json={"code": f"https://example.test/verificar/{qr}", "kind": "auto", "idempotency_key": f"ops:e2e:{uuid.uuid4()}"}, headers=leader_headers)
        assert first_checkin.status_code == 200 and first_checkin.json()["method"] == "qr" and first_checkin.json()["duplicate"] is False
        duplicate = await leader_client.post(f"/api/operations/occurrences/{occurrence_id}/check-ins", json={"person_id": attendee["person_id"], "kind": "auto", "idempotency_key": f"ops:e2e:{uuid.uuid4()}"}, headers=leader_headers)
        assert duplicate.status_code == 200 and duplicate.json()["duplicate"] is True
        guest_checkin = await leader_client.post(f"/api/operations/occurrences/{occurrence_id}/check-ins", json={"code": guest.json()["registration_code"], "kind": "attendee", "idempotency_key": f"ops:e2e:{uuid.uuid4()}"}, headers=leader_headers)
        assert guest_checkin.status_code == 200 and guest_checkin.json()["duplicate"] is False
        volunteer_checkin = await leader_client.post(f"/api/operations/occurrences/{occurrence_id}/check-ins", json={"person_id": volunteer["person_id"], "kind": "auto", "idempotency_key": f"ops:e2e:{uuid.uuid4()}"}, headers=leader_headers)
        assert volunteer_checkin.status_code == 200 and volunteer_checkin.json()["kind"] == "volunteer"
        assert await server.db.person_attendance.count_documents({"person_id": attendee["person_id"], "actividad": "OPS E2E Servicio recurrente"}) == 1

        dashboard = await pastor_client.get("/api/operations/dashboard", headers=pastor_headers)
        assert dashboard.status_code == 200 and dashboard.json()["metrics"]["upcoming_occurrences"] >= 1
        upload = await pastor_client.post(f"/api/operations/events/{event_id}/attachments", files={"file": ("operacion.pdf", b"%PDF-1.4\nOPS E2E", "application/pdf")}, headers=pastor_headers)
        assert upload.status_code == 201, upload.text
        downloaded = await pastor_client.get(f"/api/operations/events/{event_id}/attachments/{upload.json()['file_id']}", headers=pastor_headers)
        assert downloaded.status_code == 200 and downloaded.content.startswith(b"%PDF-")
        invalid_file = await pastor_client.post(f"/api/operations/events/{event_id}/attachments", files={"file": ("falso.pdf", b"NOT-A-PDF", "application/pdf")}, headers=pastor_headers)
        assert invalid_file.status_code == 415

        closed = await pastor_client.post(f"/api/operations/occurrences/{occurrence_id}/close", json={"notes": "Cierre E2E"}, headers=pastor_headers)
        assert closed.status_code == 200 and closed.json()["occurrence"]["status"] == "closed" and closed.json()["metrics"]["checkins"] == 3
        rejected_after_close = await leader_client.post(f"/api/operations/occurrences/{occurrence_id}/check-ins", json={"registration_id": guest.json()["registration_id"], "kind": "attendee", "idempotency_key": f"ops:e2e:{uuid.uuid4()}"}, headers=leader_headers)
        assert rejected_after_close.status_code == 409
        assert await server.db.operation_audit_events.count_documents({"event_id": {"$exists": False}, "entity_id": {"$in": [event_id, occurrence_id, shift_id]}}) >= 5
    finally:
        await pastor_client.aclose(); await leader_client.aclose(); await volunteer_client.aclose(); await attendee_client.aclose(); await cleanup()