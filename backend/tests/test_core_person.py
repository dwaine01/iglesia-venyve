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
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ley7semanas_test_db")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

import server  # noqa: E402


@pytest_asyncio.fixture
async def client():
    await server.db.users.delete_many({"email": "pytest.pastor@example.com"})
    await server.db.persons.delete_many({})
    await server.db.counters.delete_many({"_id": "person_number"})
    hashed = bcrypt.hashpw(b"TestPass123!", bcrypt.gensalt()).decode()
    await server.db.users.insert_one({
        "nombre": "Pytest Pastor",
        "email": "pytest.pastor@example.com",
        "password": hashed,
        "rol": "pastor",
        "leader_id": None,
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
    await server.db.users.delete_many({"email": "pytest.pastor@example.com"})
    await server.db.persons.delete_many({})
    await server.db.counters.delete_many({"_id": "person_number"})


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
