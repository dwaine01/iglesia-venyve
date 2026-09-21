"""Regression checks for Consolidación v2 catalog gating and legacy enrollment entry blocking."""

import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from qa_demo_cleanup import delete_qa_artifacts, qa_preview


PASSWORD = "CatalogGateV2!2026"


async def cleanup_qa():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


async def create_person(label: str) -> str:
    person_id = ObjectId()
    now = datetime.now(timezone.utc)
    await server.db.persons.insert_one(
        {
            "_id": person_id,
            "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
            "nombre": "QA",
            "apellido": label,
            "idempotency_key": f"qa:catalog:{uuid.uuid4()}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None) -> str:
    user_id = ObjectId()
    email = f"qa.catalog.{uuid.uuid4().hex[:8]}@example.com"
    defaults = access_defaults_for_role(role)
    now = datetime.now(timezone.utc)
    document = {
        "_id": user_id,
        "nombre": f"QA {label}",
        "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role,
        "is_active": True,
        "token_version": 1,
        "created_at": now,
        "updated_at": now,
        **defaults,
    }
    if person_id:
        document["person_id"] = person_id
    await server.db.users.insert_one(document)
    return email


async def auth_headers(email: str) -> dict:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    try:
        login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['token']}"}
    finally:
        await client.aclose()


# módulo: catálogo operativo sin el escritor legado de 7 Semanas
@pytest.mark.asyncio
async def test_catalog_exposes_consolidation_v2_discipleship_and_required_formation_modules():
    await cleanup_qa()
    pastor_email = await create_user("Catalog Pastor", "pastor")
    headers = await auth_headers(pastor_email)
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    try:
        response = await client.get("/api/processes/catalog", headers=headers)
        assert response.status_code == 200, response.text
        process_keys = {item["process_key"] for item in response.json().get("definitions", [])}
        assert process_keys == {"consolidation", "discipleship", "mentorship", "cap"}
        assert "seven_weeks" not in process_keys
        consolidation = next(item for item in response.json()["definitions"] if item["process_key"] == "consolidation")
        assert consolidation["version"] == 2
    finally:
        await client.aclose()
        await cleanup_qa()


# módulo: 7 Semanas vuelve a aceptar inscripciones; Consolidación conserva intake oficial
@pytest.mark.asyncio
async def test_generic_enrollment_endpoint_allows_seven_weeks_and_blocks_consolidation():
    await cleanup_qa()
    pastor_email = await create_user("Enrollment Pastor", "pastor")
    person_id = await create_person("Enrollment Candidate")
    headers = await auth_headers(pastor_email)
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    try:
        cycle = await client.post(
            "/api/processes/cycles",
            json={"name": f"QA Ley7 {uuid.uuid4().hex[:6]}", "start_date": "2026-10-01", "end_date": "2026-11-19", "status": "active"},
            headers=headers,
        )
        assert cycle.status_code == 201, cycle.text
        allowed_seven = await client.post(
            "/api/processes/enrollments",
            json={"process_key": "seven_weeks", "person_id": person_id, "cycle_id": cycle.json()["cycle_id"], "status": "active"},
            headers=headers,
        )
        assert allowed_seven.status_code == 201, allowed_seven.text
        assert allowed_seven.json()["process_key"] == "seven_weeks"

        blocked_consolidation = await client.post(
            "/api/processes/enrollments",
            json={"process_key": "consolidation", "person_id": person_id, "status": "active"},
            headers=headers,
        )
        assert blocked_consolidation.status_code == 409, blocked_consolidation.text
    finally:
        await client.aclose()
        await cleanup_qa()