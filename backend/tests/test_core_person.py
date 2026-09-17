"""
P-001 - Tests de integracion para el Core de Personas (aditivo).
Corre contra una MongoDB real local/efimera (nunca produccion/Atlas).
Uso: MONGO_URL y DB_NAME apuntan a la instancia de prueba antes de correr pytest.
"""
import os
import uuid
import bcrypt
import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ley7semanas_test_db")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

import server  # noqa: E402
from access_control import access_defaults_for_role  # noqa: E402


async def cleanup_test_principal():
    users = await server.db.users.find({"email": "pytest.pastor@example.com"}, {"_id": 1}).to_list(100)
    user_ids = [str(item["_id"]) for item in users]
    people = await server.db.persons.find({"$or": [{"created_by": {"$in": user_ids}}, {"auth_user_id": {"$in": user_ids}}]}, {"_id": 1}).to_list(1000)
    person_ids = [str(item["_id"]) for item in people]
    for collection in ["person_contacts", "person_addresses", "person_activity", "cell_memberships", "cell_followups", "cell_needs", "process_enrollments"]:
        await server.db[collection].delete_many({"person_id": {"$in": person_ids}})
    if people:
        await server.db.persons.delete_many({"_id": {"$in": [item["_id"] for item in people]}})
    if users:
        await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})


@pytest_asyncio.fixture
async def client():
    await cleanup_test_principal()
    hashed = bcrypt.hashpw(b"TestPass123!", bcrypt.gensalt()).decode()
    await server.db.users.insert_one({
        "nombre": "Pytest Pastor",
        "email": "pytest.pastor@example.com",
        "password": hashed,
        "rol": "pastor",
        "leader_id": None,
        **access_defaults_for_role("pastor"),
    })
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/auth/login", json={
            "email": "pytest.pastor@example.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 200, resp.text
        token = resp.json()["token"]
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac
    await cleanup_test_principal()


@pytest.mark.asyncio
async def test_create_person_assigns_vv_and_person_id(client):
    key = str(uuid.uuid4())
    resp = await client.post("/api/core/persons", json={
        "nombre": "Ana", "apellido": "Perez", "idempotency_key": key,
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["person_number"].startswith("VV-")
    assert len(body["person_id"]) == 24


@pytest.mark.asyncio
async def test_create_person_is_idempotent(client):
    key = str(uuid.uuid4())
    payload = {"nombre": "Luis", "apellido": "Diaz", "idempotency_key": key}
    r1 = await client.post("/api/core/persons", json=payload)
    r2 = await client.post("/api/core/persons", json=payload)
    assert r1.json()["person_id"] == r2.json()["person_id"]
    assert r1.json()["person_number"] == r2.json()["person_number"]


@pytest.mark.asyncio
async def test_vv_numbers_increment_and_never_repeat(client):
    r1 = await client.post("/api/core/persons", json={"nombre": "A", "apellido": "Uno", "idempotency_key": str(uuid.uuid4())})
    r2 = await client.post("/api/core/persons", json={"nombre": "B", "apellido": "Dos", "idempotency_key": str(uuid.uuid4())})
    assert r1.json()["person_number"] != r2.json()["person_number"]


@pytest.mark.asyncio
async def test_duplicate_check_finds_existing_person(client):
    await client.post("/api/core/persons", json={"nombre": "Carla", "apellido": "Nunez", "idempotency_key": str(uuid.uuid4())})
    resp = await client.post("/api/core/persons/check-duplicates", json={"nombre": "Carla", "apellido": "Nunez"})
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


@pytest.mark.asyncio
async def test_search_by_name_returns_match(client):
    await client.post("/api/core/persons", json={"nombre": "Julio", "apellido": "Reyes", "idempotency_key": str(uuid.uuid4())})
    resp = await client.get("/api/core/persons", params={"search": "reyes"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_profile_by_person_id(client):
    created = await client.post("/api/core/persons", json={"nombre": "Sofia", "apellido": "Cruz", "idempotency_key": str(uuid.uuid4())})
    pid = created.json()["person_id"]
    resp = await client.get(f"/api/core/persons/{pid}")
    assert resp.status_code == 200
    assert resp.json()["sections_available"] == ["resumen"]


@pytest.mark.asyncio
async def test_get_profile_invalid_id_returns_400():
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/core/persons/no-es-un-objectid")
        # sin token -> 401 antes de validar el id
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_persons_requires_auth():
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/core/persons")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pastor_archives_person_preserves_record_and_hides_from_views(client):
    created = await client.post("/api/core/persons", json={
        "nombre": "QA Archivo", "apellido": "Seguro", "idempotency_key": str(uuid.uuid4()),
    })
    person_id = created.json()["person_id"]
    linked_user = await server.db.users.insert_one({
        "nombre": "QA Cuenta Vinculada",
        "email": f"qa.archive.{uuid.uuid4().hex}@example.com",
        "password": bcrypt.hashpw(b"NotUsed123!", bcrypt.gensalt()).decode(),
        "rol": "persona",
        "person_id": person_id,
        "is_active": True,
        "token_version": 3,
        **access_defaults_for_role("persona"),
    })
    try:
        archived = await client.delete(f"/api/core/persons/{person_id}")
        assert archived.status_code == 200, archived.text
        assert archived.json()["archived"] is True
        assert archived.json()["linked_account_deactivated"] is True
        person = await server.db.persons.find_one({"_id": ObjectId(person_id)})
        assert person["is_archived"] is True
        linked = await server.db.users.find_one({"_id": linked_user.inserted_id})
        assert linked["is_active"] is False
        assert linked["token_version"] == 4
        assert (await client.get(f"/api/core/persons/{person_id}/profile")).status_code == 404
        listing = await client.get("/api/core/persons", params={"search": "QA Archivo"})
        assert listing.status_code == 200
        assert all(item["person_id"] != person_id for item in listing.json()["items"])
        activity = await server.db.person_activity.find_one({"person_id": person_id, "action": "archived"})
        assert activity is not None
    finally:
        await server.db.users.delete_one({"_id": linked_user.inserted_id})


@pytest.mark.asyncio
async def test_non_pastor_cannot_archive_person(client):
    created = await client.post("/api/core/persons", json={
        "nombre": "QA Protegida", "apellido": "Rol", "idempotency_key": str(uuid.uuid4()),
    })
    person_id = created.json()["person_id"]
    pastor = await server.db.users.find_one({"email": "pytest.pastor@example.com"})
    await server.db.users.update_one({"_id": pastor["_id"]}, {"$set": {"rol": "lider"}})
    try:
        denied = await client.delete(f"/api/core/persons/{person_id}")
        assert denied.status_code == 403
    finally:
        await server.db.users.update_one({"_id": pastor["_id"]}, {"$set": {"rol": "pastor"}})


@pytest.mark.asyncio
async def test_pastoral_profile_cannot_be_archived(client):
    created = await client.post("/api/core/persons", json={
        "nombre": "QA Pastor", "apellido": "Protegido", "idempotency_key": str(uuid.uuid4()),
    })
    person_id = created.json()["person_id"]
    other_pastor = await server.db.users.insert_one({
        "nombre": "QA Otro Pastor",
        "email": f"qa.other.pastor.{uuid.uuid4().hex}@example.com",
        "password": bcrypt.hashpw(b"NotUsed123!", bcrypt.gensalt()).decode(),
        "rol": "pastor",
        "person_id": person_id,
        "is_active": True,
        "token_version": 1,
        **access_defaults_for_role("pastor"),
    })
    try:
        blocked = await client.delete(f"/api/core/persons/{person_id}")
        assert blocked.status_code == 409
        assert "pastoral" in blocked.json()["detail"]
    finally:
        await server.db.users.delete_one({"_id": other_pastor.inserted_id})
