import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from geo_provider import FallbackGeocodingProvider, GeocodeResult, set_geocoding_provider_for_tests
from geo_address import normalize_address_document
from geo_sector_service import point_in_polygon, validate_polygon
from geo_service import geographic_classification


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


class FixedProvider:
    def __init__(self, result): self.result = result; self.calls = 0
    async def geocode(self, address): self.calls += 1; return self.result


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
    memberships = await server.db.household_memberships.find({"person_id": {"$in": person_ids}}, {"_id": 0, "household_id": 1}).to_list(100)
    household_ids = list({item["household_id"] for item in memberships})
    await server.db.household_memberships.delete_many({"$or": [{"person_id": {"$in": person_ids}}, {"household_id": {"$in": household_ids}}]})
    await server.db.households.delete_many({"_id": {"$in": household_ids}})
    await server.db.process_enrollments.delete_many({"person_id": {"$in": person_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [item["_id"] for item in people]}})
    await server.db.users.delete_many({"email": {"$regex": "^qa\\.geo\\.test\\."}})
    await server.db.geo_sectors.delete_many({"created_by": {"$in": user_ids}})
    await server.db.geo_sector_counters.delete_many({})
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
        assert any(any(resident["person_id"] == person_id for resident in item["properties"].get("residents", [])) for item in precise.json()["features"])
        assert fake.calls == 1
        notes = await client.put(f"/api/core/persons/{person_id}/addresses/{address_id}", json={"notas": "Sin cambiar domicilio"}, headers=headers)
        assert notes.status_code == 200 and fake.calls == 1
        moved = await client.put(f"/api/core/persons/{person_id}/addresses/{address_id}", json={"linea1": "642 Demorest Rd"}, headers=headers)
        assert moved.status_code == 200 and fake.calls == 2
        stored = await server.db.person_addresses.find_one({"_id": ObjectId(address_id)})
        assert stored["address_version"] == 2
        assert stored["verification_status"] == "verified"
        assert stored["normalized_address_key"]
        assert stored["address_complete"] is True
        assert stored["zone_number"] in {1, 2, 3, 4}
        assert stored["subzone_key"] in {f"{number}-{letter}" for number in range(1, 5) for letter in "ABC"}
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


@pytest.mark.asyncio
async def test_census_falls_back_to_geocodio_before_manual_review():
    census = FixedProvider(GeocodeResult(status="not_found", provider="census"))
    geocodio = FixedProvider(GeocodeResult(status="matched", provider="geocodio", latitude=39.92, longitude=-83.2, confidence="high", confidence_score=0.99, accuracy="rooftop"))
    result = await FallbackGeocodingProvider(census, geocodio).geocode({"street": "6553 Bellmouth Rd", "city": "Galloway", "state": "OH", "zip": "43119"})
    assert result.status == "matched" and result.provider == "geocodio"
    assert census.calls == 1 and geocodio.calls == 1
    assert result.provider_metadata["attempted_providers"] == ["census", "geocodio"]


def test_cardinal_zones_and_distance_subzones_are_mutually_exclusive():
    examples = [(40.02, -83.08, 1), (39.95, -82.98, 2), (39.86, -83.08, 3), (39.95, -83.19, 4)]
    for latitude, longitude, number in examples:
        classification = geographic_classification(latitude, longitude)
        assert classification["zone_number"] == number
        assert classification["subzone_key"].startswith(f"{number}-")


def test_address_normalization_groups_suffix_variants_but_preserves_units():
    variants = [
        {"linea1": "123 Main Street", "ciudad": "Columbus", "provincia": "OH", "codigo_postal": "43204"},
        {"linea1": "123 MAIN ST.", "ciudad": "columbus", "provincia": "oh", "codigo_postal": "43204-1200"},
    ]
    keys = [normalize_address_document(item)["normalized_address_key"] for item in variants]
    assert keys[0] == keys[1]
    apt1 = normalize_address_document({**variants[0], "linea2": "Apt 1"})["normalized_address_key"]
    apt2 = normalize_address_document({**variants[0], "linea2": "Apt 2"})["normalized_address_key"]
    assert apt1 != apt2 and apt1 != keys[0]


def test_polygon_validation_and_point_in_polygon():
    geometry = {"type": "Polygon", "coordinates": [[[-83.10, 39.93], [-83.08, 39.93], [-83.08, 39.95], [-83.10, 39.95], [-83.10, 39.93]]]}
    assert validate_polygon(geometry) == geometry
    assert point_in_polygon(-83.09, 39.94, geometry)
    assert not point_in_polygon(-83.2, 39.94, geometry)
    with pytest.raises(ValueError):
        validate_polygon({"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0]]]})


@pytest.mark.asyncio
async def test_sector_crud_overlap_locate_and_soft_delete():
    await cleanup(); _, email = await create_user(); client, headers = await client_for(email)
    geometry = {"type": "Polygon", "coordinates": [[[-83.10, 39.93], [-83.08, 39.93], [-83.08, 39.95], [-83.10, 39.95], [-83.10, 39.93]]]}
    try:
        created = await client.post("/api/geo/sectors", json={"zone_id": "south", "name": "Sector Demorest", "color": "#2563EB", "geometry": geometry}, headers=headers)
        assert created.status_code == 201, created.text
        sector_id = created.json()["sector_id"]
        assert created.json()["order"] == 1
        located = await client.get("/api/geo/sectors/locate?latitude=39.94&longitude=-83.09", headers=headers)
        assert located.status_code == 200 and located.json()["sector_id"] == sector_id
        overlap = await client.post("/api/geo/sectors", json={"zone_id": "south", "name": "Conflicto", "geometry": geometry}, headers=headers)
        assert overlap.status_code == 409 and overlap.json()["detail"]["code"] == "SECTOR_OVERLAP"
        updated = await client.put(f"/api/geo/sectors/{sector_id}", json={"name": "Sector Oeste Uno"}, headers=headers)
        assert updated.status_code == 200 and updated.json()["name"] == "Sector Oeste Uno"
        removed = await client.delete(f"/api/geo/sectors/{sector_id}", headers=headers)
        assert removed.status_code == 200 and removed.json()["status"] == "inactive"
        active = await client.get("/api/geo/sectors", headers=headers)
        assert active.status_code == 200 and all(item["sector_id"] != sector_id for item in active.json()["items"])
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_precise_map_groups_normalized_address_and_household_members():
    await cleanup(); fake = FakeGeocoder(); set_geocoding_provider_for_tests(fake)
    _, email = await create_user(); first = await create_person("HogarUno"); second = await create_person("HogarDos"); inherited = await create_person("HogarTres")
    household_id = f"household-{uuid.uuid4()}"
    await server.db.households.insert_one({"_id": household_id, "nombre_hogar": "Hogar QA", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    await server.db.household_memberships.insert_many([
        {"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": first, "rol_en_hogar": "Responsable"},
        {"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": inherited, "rol_en_hogar": "Integrante"},
    ])
    client, headers = await client_for(email)
    try:
        for person_id, street in ((first, "123 Main Street"), (second, "123 MAIN ST.")):
            response = await client.post(f"/api/core/persons/{person_id}/addresses", json={"tipo": "casa", "linea1": street, "ciudad": "Columbus", "provincia": "OH", "codigo_postal": "43204", "pais": "US", "es_principal": True}, headers=headers)
            assert response.status_code == 201, response.text
        precise = await client.get("/api/geo/precise?entity_kind=people", headers=headers)
        assert precise.status_code == 200, precise.text
        households = [item for item in precise.json()["features"] if item["properties"]["entity_kind"] == "household" and {first, second}.issubset({resident["person_id"] for resident in item["properties"].get("residents", [])})]
        assert len(households) == 1
        assert households[0]["properties"]["resident_count"] == 3
        assert {item["person_id"] for item in households[0]["properties"]["residents"]} == {first, second, inherited}
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_unlocated_admin_flow_excludes_unambiguous_household_inheritance():
    await cleanup(); fake = FakeGeocoder(); set_geocoding_provider_for_tests(fake)
    _, email = await create_user(); located = await create_person("Located"); inherited = await create_person("Inherited"); missing = await create_person("Missing")
    household_id = f"household-{uuid.uuid4()}"
    await server.db.households.insert_one({"_id": household_id, "nombre_hogar": "Hogar QA", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    await server.db.household_memberships.insert_many([
        {"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": located, "rol_en_hogar": "Responsable"},
        {"_id": str(uuid.uuid4()), "household_id": household_id, "person_id": inherited, "rol_en_hogar": "Integrante"},
    ])
    client, headers = await client_for(email)
    try:
        created = await client.post(f"/api/core/persons/{located}/addresses", json={"tipo": "casa", "linea1": "640 Demorest Street", "ciudad": "Columbus", "provincia": "OH", "codigo_postal": "43204", "pais": "US", "es_principal": True}, headers=headers)
        assert created.status_code == 201, created.text
        response = await client.get("/api/geo/unlocated-persons", headers=headers)
        assert response.status_code == 200, response.text
        ids = {item["person_id"] for item in response.json()["items"]}
        assert missing in ids
        assert located not in ids and inherited not in ids
        missing_item = next(item for item in response.json()["items"] if item["person_id"] == missing)
        assert missing_item["reason"] == "no_address_or_household"
        summary = await client.get("/api/geo/summary", headers=headers)
        assert summary.status_code == 200 and summary.json()["unlocated_total"] >= 1
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_sector_creation_reassigns_existing_location_and_updates_stats():
    await cleanup(); fake = FakeGeocoder(); set_geocoding_provider_for_tests(fake)
    _, email = await create_user(); person_id = await create_person("SectorAuto")
    client, headers = await client_for(email)
    geometry = {"type": "Polygon", "coordinates": [[[-83.10, 39.93], [-83.08, 39.93], [-83.08, 39.95], [-83.10, 39.95], [-83.10, 39.93]]]}
    zone_id = geographic_classification(fake.result.latitude, fake.result.longitude)["zone_key"]
    try:
        address = await client.post(f"/api/core/persons/{person_id}/addresses", json={"tipo": "casa", "linea1": "640 Demorest Rd", "ciudad": "Columbus", "provincia": "OH", "codigo_postal": "43204", "pais": "US", "es_principal": True}, headers=headers)
        assert address.status_code == 201, address.text
        created = await client.post("/api/geo/sectors", json={"zone_id": zone_id, "name": "Sector Automático", "geometry": geometry}, headers=headers)
        assert created.status_code == 201, created.text
        sector_id = created.json()["sector_id"]
        stored = await server.db.person_addresses.find_one({"_id": ObjectId(address.json()["address_id"])})
        assert stored["sector_id"] == sector_id
        sectors = await client.get("/api/geo/sectors", headers=headers)
        item = next(value for value in sectors.json()["items"] if value["sector_id"] == sector_id)
        assert item["stats"]["people_count"] == 1
        assert item["stats"]["households_count"] == 1
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_failed_geocoding_still_persists_normalization_without_coordinates():
    await cleanup(); provider = FixedProvider(GeocodeResult(status="not_found", provider="census")); set_geocoding_provider_for_tests(provider)
    _, email = await create_user(); person_id = await create_person("NormalizeForward")
    client, headers = await client_for(email)
    try:
        created = await client.post(f"/api/core/persons/{person_id}/addresses", json={"tipo": "casa", "linea1": "123 Main Street", "linea2": "Apt 4", "ciudad": "Columbus", "provincia": "OH", "codigo_postal": "43204", "pais": "US"}, headers=headers)
        assert created.status_code == 201, created.text
        stored = await server.db.person_addresses.find_one({"_id": ObjectId(created.json()["address_id"])})
        assert stored["normalized_address_key"].startswith("123 MAIN ST|APT 4|")
        assert stored["address_complete"] is True
        assert stored["verification_status"] == "needs_verification"
        assert "location" not in stored
    finally:
        await client.aclose(); await cleanup()