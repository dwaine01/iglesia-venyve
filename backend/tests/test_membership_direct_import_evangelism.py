import io
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook

import server
from access_control import CORE_ACCESS_MANAGE, access_defaults_for_role
from geo_provider import GeocodeResult, set_geocoding_provider_for_tests


PASSWORD = "DirectMember2026!"
PREFIX = "qa.newfeatures."


class TargetGeocoder:
    async def geocode(self, address):
        return GeocodeResult(status="matched", latitude=39.9411, longitude=-83.0895, confidence="high", confidence_score=1, accuracy="rooftop", provider="test")


async def create_user(role="pastor", coordinator=False):
    user_id = ObjectId(); email = f"{PREFIX}{uuid.uuid4().hex[:8]}@example.com"; defaults = access_defaults_for_role(role)
    if coordinator:
        defaults["capabilities"] = sorted(set(defaults["capabilities"] + [CORE_ACCESS_MANAGE]))
    await server.db.users.insert_one({"_id": user_id, "nombre": "QA Nuevas Funciones", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "is_active": True, "token_version": 1, "created_at": datetime.now(timezone.utc), **defaults})
    return str(user_id), email


async def client_for(email):
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


async def cleanup():
    users = await server.db.users.find({"email": {"$regex": f"^{PREFIX}"}}, {"_id": 1}).to_list(100)
    user_ids = [str(item["_id"]) for item in users]
    people = await server.db.persons.find({"idempotency_key": {"$regex": "^qa:newfeatures:"}}, {"_id": 1}).to_list(100)
    person_ids = [str(item["_id"]) for item in people]
    memberships = await server.db.person_memberships.find({"person_id": {"$in": person_ids}}, {"_id": 0, "member_number": 1}).to_list(100)
    await server.db.membership_number_registry.delete_many({"member_number": {"$in": [item["member_number"] for item in memberships]}})
    await server.db.membership_events.delete_many({"person_id": {"$in": person_ids}})
    await server.db.person_memberships.delete_many({"person_id": {"$in": person_ids}})
    await server.db.person_activity.delete_many({"person_id": {"$in": person_ids}})
    await server.db.person_contacts.delete_many({"person_id": {"$in": person_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [item["_id"] for item in people]}})
    targets = await server.db.evangelism_targets.find({"created_by_user_id": {"$in": user_ids}}, {"_id": 0, "target_id": 1}).to_list(100)
    await server.db.evangelism_target_events.delete_many({"target_id": {"$in": [item["target_id"] for item in targets]}})
    await server.db.evangelism_targets.delete_many({"created_by_user_id": {"$in": user_ids}})
    await server.db.users.delete_many({"email": {"$regex": f"^{PREFIX}"}})
    set_geocoding_provider_for_tests(None)


@pytest.mark.asyncio
async def test_direct_membership_pastor_and_coordinator_only():
    await cleanup(); _, pastor_email = await create_user(); _, leader_email = await create_user("lider"); _, coordinator_email = await create_user("lider", coordinator=True)
    try:
        pastor, pastor_headers = await client_for(pastor_email)
        payload = {"nombre": "Ana", "apellido": "Histórica", "telefono": "6145550001", "idempotency_key": f"qa:newfeatures:{uuid.uuid4()}", "preexisting_active_member": True}
        created = await pastor.post("/api/core/persons", json=payload, headers=pastor_headers)
        assert created.status_code == 201, created.text
        assert created.json()["membership"]["direct"] is True
        membership = await server.db.person_memberships.find_one({"person_id": created.json()["person_id"]}, {"_id": 0})
        assert membership["direct_membership"] is True and membership["certificate_eligible_at"] and membership["card_eligible_at"]
        repeated = await pastor.post("/api/core/persons", json=payload, headers=pastor_headers)
        assert repeated.status_code == 201 and repeated.json()["membership"]["member_number"] == membership["member_number"]
        conflict_key = f"qa:newfeatures:{uuid.uuid4()}"
        conflict = await pastor.post("/api/core/persons", json={**payload, "telefono": "6145550099", "idempotency_key": conflict_key, "existing_member_number": membership["member_number"]}, headers=pastor_headers)
        assert conflict.status_code == 409
        assert await server.db.persons.count_documents({"idempotency_key": conflict_key}) == 0
        await pastor.aclose()

        leader, leader_headers = await client_for(leader_email)
        denied = await leader.post("/api/core/persons", json={**payload, "telefono": "6145550002", "idempotency_key": f"qa:newfeatures:{uuid.uuid4()}"}, headers=leader_headers)
        assert denied.status_code == 403
        await leader.aclose()

        coordinator, coordinator_headers = await client_for(coordinator_email)
        allowed = await coordinator.post("/api/core/persons", json={**payload, "nombre": "Luis", "telefono": "6145550003", "idempotency_key": f"qa:newfeatures:{uuid.uuid4()}"}, headers=coordinator_headers)
        assert allowed.status_code == 201 and allowed.json()["membership"]["direct"] is True
        await coordinator.aclose()
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_csv_and_xlsx_dry_run_never_write_and_suggest_household():
    await cleanup(); _, email = await create_user(); client, headers = await client_for(email)
    before = {name: await server.db[name].count_documents({}) for name in ["persons", "person_memberships", "households", "household_memberships"]}
    csv_data = "Nombre,Apellido,Correo,Telefono,Direccion,Ciudad,Estado,ZIP\nMaria,Rios,maria@example.com,6145550101,123 Main Street,Columbus,OH,43204\nJose,Rios,jose@example.com,6145550102,123 Main St.,Columbus,OH,43204\n"
    try:
        response = await client.post("/api/membership/import/dry-run", files={"file": ("miembros.csv", csv_data.encode(), "text/csv")}, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json(); assert data["dry_run"] is True and data["database_writes"] == 0
        assert data["summary"]["total"] == 2 and data["summary"]["households"] == 1
        workbook = Workbook(); sheet = workbook.active; sheet.append(["Nombre", "Apellido", "Direccion"]); sheet.append(["Eva", "Luna", "500 Broad St"]); stream = io.BytesIO(); workbook.save(stream)
        excel = await client.post("/api/membership/import/dry-run", files={"file": ("miembros.xlsx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, headers=headers)
        assert excel.status_code == 200 and excel.json()["summary"]["total"] == 1
        after = {name: await server.db[name].count_documents({}) for name in before}
        assert after == before
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_any_authenticated_user_can_manage_evangelism_targets():
    await cleanup(); user_id, email = await create_user("persona"); set_geocoding_provider_for_tests(TargetGeocoder()); client, headers = await client_for(email)
    try:
        config = await client.get("/api/geo/evangelism/config", headers=headers)
        assert config.status_code == 200 and config.json()["permissions"]["evangelism_manage"] is True
        created = await client.post("/api/geo/evangelism", json={"house_number": "640", "street_name": "Demorest Rd", "city": "Columbus", "state": "OH", "zip": "43204", "language": "spanish", "assigned_to_user_id": user_id}, headers=headers)
        assert created.status_code == 201, created.text
        target_id = created.json()["target_id"]; assert created.json()["status"] == "assigned" and created.json()["latitude"]
        listing = await client.get("/api/geo/evangelism", headers=headers)
        assert listing.status_code == 200 and any(item["properties"]["target_id"] == target_id for item in listing.json()["features"])
        updated = await client.patch(f"/api/geo/evangelism/{target_id}", json={"status": "visited", "notes": "Primera visita completada"}, headers=headers)
        assert updated.status_code == 200 and updated.json()["status"] == "visited"
        archived = await client.delete(f"/api/geo/evangelism/{target_id}", headers=headers)
        assert archived.status_code == 200 and archived.json()["archived"] is True
    finally:
        await client.aclose(); await cleanup()