import uuid
from datetime import date, datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import cellular_routes
import membership_documents
import server
from access_control import access_defaults_for_role


PREFIX = "stabilization.p0."
PASSWORD = "StabilizationP0!"


async def make_user(role="pastor", person_id=None):
    user_id = ObjectId(); email = f"{PREFIX}{uuid.uuid4().hex[:8]}@example.com"
    await server.db.users.insert_one({"_id": user_id, "nombre": "QA Stabilization", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": person_id, "is_active": True, "token_version": 1, **access_defaults_for_role(role)})
    return str(user_id), email


async def login(email, *, raise_app_exceptions=True):
    client = AsyncClient(transport=ASGITransport(app=server.app, raise_app_exceptions=raise_app_exceptions), base_url="http://test")
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client, {"Authorization": f"Bearer {response.json()['token']}"}


async def cleanup():
    users = await server.db.users.find({"email": {"$regex": f"^{PREFIX}"}}, {"_id": 1}).to_list(100)
    user_ids = [str(item["_id"]) for item in users]
    people = await server.db.persons.find({"idempotency_key": {"$regex": "^stabilization:p0:"}}, {"_id": 1}).to_list(100)
    person_ids = [str(item["_id"]) for item in people]
    network_ids = await server.db.cell_networks.distinct("network_id", {"name": {"$regex": "^STABILIZATION P0"}})
    cell_ids = await server.db.cells.distinct("cell_id", {"network_id": {"$in": network_ids}})
    review_ids = await server.db.cell_multiplication_reviews.distinct("review_id", {"cell_id": {"$in": cell_ids}})
    for collection in ["cell_role_assignments", "cell_memberships", "cell_timeline", "cell_multiplication_reviews", "cell_multiplications"]:
        await server.db[collection].delete_many({"$or": [{"cell_id": {"$in": cell_ids}}, {"mother_cell_id": {"$in": cell_ids}}, {"daughter_cell_id": {"$in": cell_ids}}, {"review_id": {"$in": review_ids}}]})
    await server.db.geo_jobs.delete_many({"entity_kind": "cell", "entity_id": {"$in": cell_ids}})
    await server.db.cells.delete_many({"cell_id": {"$in": cell_ids}}); await server.db.cell_networks.delete_many({"network_id": {"$in": network_ids}})
    for collection in ["membership_number_registry", "membership_events", "person_memberships", "person_contacts", "person_activity"]:
        await server.db[collection].delete_many({"person_id": {"$in": person_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [item["_id"] for item in people]}})
    await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})
    await server.db.qa_reference_guard.delete_many({"test_run": {"$in": user_ids}})


@pytest.mark.asyncio
async def test_direct_membership_failure_rolls_back_person_object_id(monkeypatch):
    await cleanup(); _, email = await make_user()
    async def fail_after_person(*args, **kwargs):
        raise RuntimeError("forced membership failure")
    monkeypatch.setattr(membership_documents, "activate_preexisting_membership", fail_after_person)
    client, headers = await login(email, raise_app_exceptions=False); key = f"stabilization:p0:{uuid.uuid4()}"
    try:
        response = await client.post("/api/core/persons", json={"nombre": "Rollback", "apellido": "Completo", "telefono": "6145558888", "idempotency_key": key, "preexisting_active_member": True}, headers=headers)
        assert response.status_code == 500
        assert await server.db.persons.count_documents({"idempotency_key": key}) == 0
        assert await server.db.person_contacts.count_documents({"valor": "6145558888"}) == 0
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_multiplication_approval_creates_daughter_and_transfers_member(monkeypatch):
    await cleanup(); now = datetime.now(timezone.utc)
    leader_person, member_person = ObjectId(), ObjectId()
    await server.db.persons.insert_many([
        {"_id": leader_person, "person_number": "VV-STABP0L", "nombre": "Líder", "apellido": "Hija", "search_key": "lider hija", "idempotency_key": f"stabilization:p0:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now},
        {"_id": member_person, "person_number": "VV-STABP0M", "nombre": "Miembro", "apellido": "Transferido", "search_key": "miembro transferido", "idempotency_key": f"stabilization:p0:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now},
    ])
    await make_user("lider", str(leader_person)); _, pastor_email = await make_user("pastor")
    network_id, mother_id, review_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.cell_networks.insert_one({"_id": network_id, "network_id": network_id, "name": "STABILIZATION P0 NETWORK", "status": "active", "created_at": now})
    await server.db.cells.insert_one({"_id": mother_id, "cell_id": mother_id, "name": "STABILIZATION P0 MADRE", "code": "STABP0M", "network_id": network_id, "address": "640 Demorest Rd", "meeting_day": "Viernes", "meeting_time": "19:00", "capacity": 20, "opened_at": date.today().isoformat(), "status": "active", "created_at": now, "updated_at": now})
    previous_membership = str(uuid.uuid4())
    await server.db.cell_memberships.insert_one({"_id": previous_membership, "membership_id": previous_membership, "cell_id": mother_id, "network_id": network_id, "person_id": str(member_person), "membership_type": "primary", "role": "member", "active": True, "joined_at": date.today().isoformat(), "created_at": now})
    await server.db.cell_multiplication_reviews.insert_one({"_id": review_id, "review_id": review_id, "cell_id": mother_id, "status": "pending", "facts": {}, "created_at": now, "updated_at": now})
    async def no_geo(*args, **kwargs): return None
    monkeypatch.setattr(cellular_routes, "process_geo_job", no_geo)
    client, headers = await login(pastor_email)
    try:
        payload = {"action": "approve", "reason": "Crecimiento confirmado", "daughter_leader_person_id": str(leader_person), "transferred_person_ids": [str(member_person)], "daughter_cell": {"name": "STABILIZATION P0 HIJA", "code": "STABP0H", "network_id": network_id, "address": "825 Georgesville Rd", "meeting_day": "Sábado", "meeting_time": "18:00", "capacity": 20, "opened_at": date.today().isoformat(), "status": "active"}}
        response = await client.put(f"/api/cellular/multiplication/reviews/{review_id}", json=payload, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json(); daughter_id = data["daughter_cell"]["cell_id"]
        assert data["review"]["status"] == "approved" and data["multiplication"]["mother_cell_id"] == mother_id
        assert await server.db.cells.count_documents({"cell_id": daughter_id, "mother_cell_id": mother_id}) == 1
        assert await server.db.cell_role_assignments.count_documents({"cell_id": daughter_id, "person_id": str(leader_person), "role": "cell_leader", "active": True}) == 1
        assert await server.db.cell_memberships.count_documents({"cell_id": daughter_id, "person_id": str(member_person), "active": True}) == 1
        assert await server.db.cell_memberships.count_documents({"membership_id": previous_membership, "active": False}) == 1
    finally:
        await client.aclose(); await cleanup()