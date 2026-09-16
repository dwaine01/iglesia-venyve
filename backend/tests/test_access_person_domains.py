"""ACCESS-01 and P-001 Slice 2B integration tests."""
import os
import uuid

import bcrypt
import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ley7semanas_test_db")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

import server  # noqa: E402
from access_control import access_defaults_for_role, ensure_access_defaults  # noqa: E402


async def make_client(role="lider", explicit_access=True):
    unique = uuid.uuid4().hex
    email = f"access01.{unique}@example.com"
    password = "Access01TestPass!"
    doc = {
        "nombre": "ACCESS-01 Tester",
        "email": email,
        "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "rol": role,
        "is_active": True,
        "token_version": 1,
    }
    if explicit_access:
        doc.update(access_defaults_for_role(role))
    result = await server.db.users.insert_one(doc)
    transport = ASGITransport(app=server.app)
    client = AsyncClient(transport=transport, base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    client.headers.update({"Authorization": f"Bearer {login.json()['token']}"})
    return client, str(result.inserted_id), email


async def cleanup(user_id, email, person_ids):
    await server.db.person_contacts.delete_many({"person_id": {"$in": person_ids}})
    await server.db.person_addresses.delete_many({"person_id": {"$in": person_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [ObjectId(pid) for pid in person_ids]}})
    await server.db.users.delete_many({"email": email})


@pytest_asyncio.fixture
async def scoped_case():
    client, user_id, email = await make_client()
    created = await client.post(
        "/api/core/persons",
        json={
            "nombre": "María",
            "apellido": "Santos",
            "telefono": "8095550101",
            "email": "maria@example.com",
            "fecha_nacimiento": "1992-04-18",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert created.status_code == 201, created.text
    person_id = created.json()["person_id"]
    yield client, user_id, person_id
    await client.aclose()
    await cleanup(user_id, email, [person_id])


@pytest.mark.asyncio
async def test_explicit_capability_and_scope_enable_visible_profile_domains(scoped_case):
    client, _, person_id = scoped_case

    contact = await client.post(
        f"/api/core/persons/{person_id}/contacts",
        json={
            "tipo": "whatsapp",
            "valor": "+1 809 555 0101",
            "etiqueta": "Personal",
            "notas": "Prefiere mensajes",
        },
    )
    address = await client.post(
        f"/api/core/persons/{person_id}/addresses",
        json={
            "tipo": "casa",
            "linea1": "Calle Restauración 21",
            "sector": "Los Jardines",
            "ciudad": "Santo Domingo",
            "provincia": "Distrito Nacional",
            "pais": "República Dominicana",
        },
    )

    assert contact.status_code == 201, contact.text
    assert address.status_code == 201, address.text
    assert contact.json()["es_principal"] is True
    assert address.json()["es_principal"] is True
    assert contact.json()["created_at"].endswith("Z")
    assert address.json()["updated_at"].endswith("Z")

    profile = await client.get(f"/api/core/persons/{person_id}/profile")
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["sections_available"] == ["resumen", "contacto", "direcciones"]
    assert "contacto" not in body["sections_planned"]
    assert "direcciones" not in body["sections_planned"]
    assert body["header"]["primary_contact"] == "+1 809 555 0101"
    assert body["header"]["city"] == "Santo Domingo"
    assert body["header"]["fecha_nacimiento"] == "1992-04-18"
    assert body["contacto"]["can_write"] is True
    assert body["direcciones"]["can_write"] is True
    assert body["contacto"]["items"][0]["valor"] == "+1 809 555 0101"
    assert body["direcciones"]["items"][0]["ciudad"] == "Santo Domingo"

    domain_statuses = {
        item["section_key"]: item["status_code"] for item in body["sections"]
    }
    assert domain_statuses["contacto"] == "has_summary"
    assert domain_statuses["direcciones"] == "has_summary"


@pytest.mark.asyncio
async def test_contact_and_address_crud_preserve_single_primary(scoped_case):
    client, _, person_id = scoped_case
    first = await client.post(
        f"/api/core/persons/{person_id}/contacts",
        json={"tipo": "telefono", "valor": "809-555-0001"},
    )
    second = await client.post(
        f"/api/core/persons/{person_id}/contacts",
        json={"tipo": "email", "valor": "maria.santos@example.com", "es_principal": True},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    contacts = await client.get(f"/api/core/persons/{person_id}/contacts")
    assert contacts.status_code == 200
    assert sum(item["es_principal"] for item in contacts.json()["items"]) == 1
    assert contacts.json()["items"][0]["contact_id"] == second.json()["contact_id"]

    updated = await client.put(
        f"/api/core/persons/{person_id}/contacts/{first.json()['contact_id']}",
        json={"etiqueta": "Casa", "es_principal": True},
    )
    assert updated.status_code == 200
    assert updated.json()["etiqueta"] == "Casa"
    assert updated.json()["es_principal"] is True

    deleted = await client.delete(
        f"/api/core/persons/{person_id}/contacts/{first.json()['contact_id']}"
    )
    assert deleted.status_code == 200
    remaining = await client.get(f"/api/core/persons/{person_id}/contacts")
    assert remaining.json()["items"][0]["es_principal"] is True

    home = await client.post(
        f"/api/core/persons/{person_id}/addresses",
        json={"linea1": "Calle 1", "ciudad": "Santiago"},
    )
    assert home.status_code == 201
    updated_home = await client.put(
        f"/api/core/persons/{person_id}/addresses/{home.json()['address_id']}",
        json={"sector": "Centro", "ciudad": "Santiago de los Caballeros"},
    )
    assert updated_home.status_code == 200
    assert updated_home.json()["sector"] == "Centro"
    deleted_home = await client.delete(
        f"/api/core/persons/{person_id}/addresses/{home.json()['address_id']}"
    )
    assert deleted_home.status_code == 200


@pytest.mark.asyncio
async def test_role_without_explicit_grant_cannot_read_sensitive_domains():
    client, user_id, email = await make_client(explicit_access=False)
    person_doc = {
        "nombre": "Legacy",
        "apellido": "Sin Grant",
        "person_number": f"VV-{uuid.uuid4().int % 999999:06d}",
        "created_by": user_id,
        "fecha_nacimiento": "1980-01-01",
    }
    result = await server.db.persons.insert_one(person_doc)
    person_id = str(result.inserted_id)
    try:
        profile = await client.get(f"/api/core/persons/{person_id}/profile")
        contacts = await client.get(f"/api/core/persons/{person_id}/contacts")
        assert profile.status_code == 200
        assert profile.json()["sections_available"] == ["resumen"]
        for field in ("primary_contact", "fecha_nacimiento", "city"):
            assert field not in profile.json()["header"]
        assert contacts.status_code == 403
    finally:
        await client.aclose()
        await cleanup(user_id, email, [person_id])


@pytest.mark.asyncio
async def test_created_by_scope_denies_another_leaders_person(scoped_case):
    client, _, own_person_id = scoped_case
    other = await server.db.persons.insert_one({
        "nombre": "Otra",
        "apellido": "Persona",
        "person_number": f"VV-{uuid.uuid4().int % 999999:06d}",
        "created_by": str(ObjectId()),
    })
    other_person_id = str(other.inserted_id)
    try:
        contacts = await client.get(f"/api/core/persons/{other_person_id}/contacts")
        addresses = await client.get(f"/api/core/persons/{other_person_id}/addresses")
        assert contacts.status_code == 403
        assert addresses.status_code == 403
    finally:
        await server.db.persons.delete_one({"_id": other.inserted_id})
        await server.db.person_contacts.delete_many({"person_id": own_person_id})


@pytest.mark.asyncio
async def test_pastor_all_scope_can_read_any_person():
    client, user_id, email = await make_client(role="pastor")
    result = await server.db.persons.insert_one({
        "nombre": "Persona",
        "apellido": "Global",
        "person_number": f"VV-{uuid.uuid4().int % 999999:06d}",
        "created_by": str(ObjectId()),
    })
    person_id = str(result.inserted_id)
    try:
        contacts = await client.get(f"/api/core/persons/{person_id}/contacts")
        addresses = await client.get(f"/api/core/persons/{person_id}/addresses")
        assert contacts.status_code == 200
        assert addresses.status_code == 200
    finally:
        await client.aclose()
        await cleanup(user_id, email, [person_id])


@pytest.mark.asyncio
async def test_access_rollout_backfill_is_additive_and_idempotent():
    email = f"access01.backfill.{uuid.uuid4().hex}@example.com"
    result = await server.db.users.insert_one({
        "nombre": "Backfill User",
        "email": email,
        "password": "not-used",
        "rol": "lider",
    })
    try:
        await ensure_access_defaults(server.db)
        await ensure_access_defaults(server.db)
        user = await server.db.users.find_one({"_id": result.inserted_id})
        assert "person.contacts.read" in user["capabilities"]
        assert "person.addresses.write" in user["capabilities"]
        assert user["access_scope"] == {"persons": "created_by"}
    finally:
        await server.db.users.delete_one({"_id": result.inserted_id})
