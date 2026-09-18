import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from geo_provider import GeocodeResult, set_geocoding_provider_for_tests


PASSWORD = "GeoMapsPass2026!"


class FakeGeocoder:
    def __init__(self):
        self.calls = 0
        self.result = GeocodeResult(
            status="matched", latitude=39.9411, longitude=-83.0895, confidence="high",
            confidence_score=1, matched_address="640 DEMOREST RD, COLUMBUS, OH, 43204",
            provider_result_id="fake-line", provider_metadata={"benchmark": "TEST"},
        )

    async def geocode(self, address: dict) -> GeocodeResult:
        self.calls += 1
        return self.result


async def create_user(role="pastor", capabilities=None):
    defaults = access_defaults_for_role(role)
    defaults["capabilities"] = sorted(set((capabilities or []) + defaults.get("capabilities", [])))
    email = f"qa.geo.test.{uuid.uuid4().hex[:8]}@example.com"
    user_id = ObjectId()
    await server.db.users.insert_one({
        "_id": user_id, "nombre": "QA Geo", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "is_active": True, "token_version": 1,
        "created_at": datetime.now(timezone.utc), **defaults,
    })
    return user_id, email


async def create_person(label="Member"):
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id, "person_number": f"VV-QG{uuid.uuid4().hex[:6].upper()}",
        "nombre": "QA", "apellido": label, "search_key": f"qa {label.lower()}", "idempotency_key": f"qa:geo:{uuid.uuid4()}",
        "status": "active", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def client_for(email):
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client, {"Authorization": f"Bearer {response.json()['token']}"}


async def cleanup():
    users = await server.db.users.find({"email": {"$regex": "^qa\\.geo\\.test\\."}}, {"_id": 1}).to_list(100)
    user_ids = [str(item["_id"]) for item in users]
    people = await server.db.persons.find({"person_number": {"$regex": "^VV-QG"}}, {"_id": 1}).to_list(100)
    person_ids = [str(item["_id"]) for item in people]
    addresses = await server.db.person_addresses.find({"person_id": {"$in": person_ids}}, {"_id": 1}).to_list(100)
    address_ids = [str(item["_id"]) for item in addresses]
    await server.db.geo_jobs.delete_many({"entity_id": {"$in": address_ids}})
    await server.db.geo_review_queue.delete_many({"entity_id": {"$in": address_ids}})
    await server.db.geo_location_history.delete_many({"entity_id": {"$in": address_ids}})
    await server.db.geo_audit_log.delete_many({"actor_user_id": {"$in": user_ids}})
    await server.db.person_addresses.delete_many({"person_id": {"$in": person_ids}})
    await server.db.person_contacts.delete_many({"person_id": {"$in": person_ids}})
    await server.db.process_enrollments.delete_many({"person_id": {"$in": person_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [item["_id"] for item in people]}})
    await server.db.users.delete_many({"email": {"$regex": "^qa\\.geo\\.test\\."}})
    set_geocoding_provider_for_tests(None)


@pytest.mark.asyncio
async def test_address_geocodes_once_and_map_reads_persisted_coordinates():
    await cleanup(); fake = FakeGeocoder(); set_geocoding_provider_for_tests(fake)
    _, email = await create_user(); person_id = await create_person("Persistent")
    client, headers = await client_for(email)
    try:
        created = await client.post(f"/api/core/persons/{person_id}/addresses", json={
            "tipo": "casa", "linea1": "640 Demorest Rd", "ciudad": "Columbus",
            "provincia": "OH", "codigo_postal": "43204", "pais": "Estados Unidos", "es_principal": True,
        }, headers=headers)
        assert created.status_code == 201, created.text
        assert fake.calls == 1
        address_id = created.json()["address_id"]
        precise = await client.get("/api/geo/precise?entity_kind=people", headers=headers)
        assert precise.status_code == 200, precise.text
        assert any(item["properties"]["entity_id"] == person_id for item in precise.json()["features"])
        assert fake.calls == 1
        notes = await client.put(f"/api/core/persons/{person_id}/addresses/{address_id}", json={"notas": "Sin cambiar domicilio"}, headers=headers)
        assert notes.status_code == 200 and fake.calls == 1
        moved = await client.put(f"/api/core/persons/{person_id}/addresses/{address_id}", json={"linea1": "642 Demorest Rd"}, headers=headers)
        assert moved.status_code == 200 and fake.calls == 2
        stored = await server.db.person_addresses.find_one({"_id": ObjectId(address_id)})
        assert stored["address_version"] == 2
        assert stored["verification_status"] == "verified"
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_low_confidence_enters_review_and_manual_pin_has_priority():
    await cleanup(); fake = FakeGeocoder(); fake.result = GeocodeResult(status="needs_verification", latitude=39.9, longitude=-83.1, confidence="medium", confidence_score=0.75)
    set_geocoding_provider_for_tests(fake)
    _, email = await create_user(); person_id = await create_person("Review")
    client, headers = await client_for(email)
    try:
        created = await client.post(f"/api/core/persons/{person_id}/addresses", json={"linea1": "Unknown 10", "ciudad": "Columbus", "provincia": "OH", "codigo_postal": "43204", "pais": "Estados Unidos"}, headers=headers)
        assert created.status_code == 201
        queue = await client.get("/api/geo/review-queue", headers=headers)
        assert queue.status_code == 200
        matching = next(item for item in queue.json()["items"] if item["entity_id"] == created.json()["address_id"])
        assert matching["candidate_location"] == {"latitude": 39.9, "longitude": -83.1}
        review_id = matching["review_id"]
        resolved = await client.post(f"/api/geo/review-queue/{review_id}/resolve", json={"latitude": 39.95, "longitude": -83.08, "reason": "Ubicación confirmada"}, headers=headers)
        assert resolved.status_code == 200
        address = await server.db.person_addresses.find_one({"_id": ObjectId(created.json()["address_id"])})
        assert address["manual_override"] is True
        assert address["verification_status"] == "manual_verified"
        assert address["longitude"] == -83.08
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_geo_rbac_and_remote_intake_search():
    await cleanup(); person_id = await create_person("Searchable")
    await server.db.person_contacts.insert_one({"person_id": person_id, "tipo": "telefono", "valor": "6145550199", "es_principal": True, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    _, pastor_email = await create_user()
    aggregate_id, aggregate_email = await create_user("lider", ["geo.view_aggregate"])
    await server.db.users.update_one({"_id": aggregate_id}, {"$set": {"capabilities": ["geo.view_aggregate"]}})
    denied_id, denied_email = await create_user("persona")
    await server.db.users.update_one({"_id": denied_id}, {"$set": {"capabilities": []}})
    try:
        pastor, pastor_headers = await client_for(pastor_email)
        result = await pastor.get("/api/processes/consolidation/intake-candidates?search=614555", headers=pastor_headers)
        assert result.status_code == 200
        assert any(item["person_id"] == person_id for item in result.json()["items"])
        await pastor.aclose()
        aggregate, aggregate_headers = await client_for(aggregate_email)
        assert (await aggregate.get("/api/geo/config", headers=aggregate_headers)).status_code == 200
        assert (await aggregate.get("/api/geo/precise", headers=aggregate_headers)).status_code == 403
        await aggregate.aclose()
        denied, denied_headers = await client_for(denied_email)
        assert (await denied.get("/api/geo/config", headers=denied_headers)).status_code == 403
        await denied.aclose()
    finally:
        await cleanup()