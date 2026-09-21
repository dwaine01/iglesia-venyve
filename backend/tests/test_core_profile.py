"""
P-001 Slice 2A - Pruebas del read-model Person Profile 360.
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
from core_profile import PLANNED_DOMAINS  # noqa: E402


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
        "capabilities": ["person.profile.open"],
        "access_scope": {"persons": "created_by"},
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
async def test_profile_returns_header_and_sections(client):
    created = await client.post("/api/core/persons", json={
        "nombre": "Laura",
        "apellido": "Martinez",
        "telefono": "99998888",
        "fecha_nacimiento": "1990-05-01",
        "idempotency_key": str(uuid.uuid4()),
    })
    assert created.status_code == 201, created.text
    pid = created.json()["person_id"]

    resp = await client.get(f"/api/core/persons/{pid}/profile")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    header = body["header"]
    assert header["person_id"] == pid
    assert header["person_number"].startswith("VV-")
    assert header["nombre_completo"] == "Laura Martinez"
    assert header["initials"] == "LM"
    # Con acceso canónico a la ficha pero sin capabilities sensibles,
    # estos campos se omiten para cualquier rol.
    assert "primary_contact" not in header
    assert "fecha_nacimiento" not in header
    assert "city" not in header

    sections = body["sections"]
    # 1 core + 2 real domains (contacto, direcciones) + 1 ministerio_servicio + PLANNED_DOMAINS
    assert len(sections) == 1 + 2 + 1 + len(PLANNED_DOMAINS)

    core_section = sections[0]
    assert core_section["section_key"] == "core"
    assert core_section["status_code"] == "has_summary"
    assert core_section["summary"] == "Laura Martinez"

    domain_sections = sections[1:]
    expected_keys = ["contacto", "direcciones", "ministerio_servicio", *[key for key, _ in PLANNED_DOMAINS]]
    assert [section["section_key"] for section in domain_sections] == expected_keys
    restricted_keys = {section["section_key"] for section in domain_sections}
    for section in domain_sections:
        assert section["section_key"] in restricted_keys
        assert section["status_code"] == "access_restricted"
        assert section["summary"] is None
        assert section["status_label"] not in ("Pendiente", "No completado", "No miembro")

    assert body["canonical_profile_path"] == f"/personas/{pid}"
    assert body["sections_available"] == ["resumen"]
    assert body["sections_planned"] == [
        "contacto", "direcciones", "household", "familia",
        "procesos", "asistencia", "historial",
    ]


@pytest.mark.asyncio
async def test_profile_header_omits_sensitive_fields_without_sensitive_capability(client):
    """La ficha canónica mantiene el mismo diseño, pero omite campos sensibles
    cuando el usuario solo tiene permiso para abrir la Persona."""
    created = await client.post("/api/core/persons", json={
        "nombre": "Pedro",
        "apellido": "Ramirez",
        "telefono": "77776666",
        "email": "pedro.ramirez@example.com",
        "fecha_nacimiento": "1985-02-10",
        "idempotency_key": str(uuid.uuid4()),
    })
    assert created.status_code == 201, created.text
    pid = created.json()["person_id"]

    resp = await client.get(f"/api/core/persons/{pid}/profile")
    assert resp.status_code == 200, resp.text
    header = resp.json()["header"]

    for sensitive_key in ("primary_contact", "fecha_nacimiento", "city"):
        assert sensitive_key not in header, f"{sensitive_key} no debe exponerse sin capability+scope"

    # identidad basica si debe estar presente
    assert header["nombre_completo"] == "Pedro Ramirez"
    assert header["person_number"].startswith("VV-")


@pytest.mark.asyncio
async def test_profile_invalid_id_returns_401_before_400():
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/core/persons/no-es-un-objectid/profile")
        # sin token -> 401 antes de validar el id (mismo patron que core_person)
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_profile_invalid_id_returns_400(client):
    resp = await client.get("/api/core/persons/no-es-un-objectid/profile")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_profile_not_found_returns_404(client):
    fake_id = "0" * 24
    resp = await client.get(f"/api/core/persons/{fake_id}/profile")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_profile_requires_auth():
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/core/persons/000000000000000000000000/profile")
        assert resp.status_code == 401
