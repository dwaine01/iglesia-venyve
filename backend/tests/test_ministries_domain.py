"""Central Ministry domain and canonical Person integration tests."""
import os
import uuid

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ley7semanas_test_db")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

import server  # noqa: E402
from access_control import access_defaults_for_role  # noqa: E402
from ministries import ensure_indexes_and_seed  # noqa: E402
from person_core_expansion import ensure_indexes_and_seed as ensure_talents  # noqa: E402


@pytest.mark.asyncio
async def test_ministry_catalog_assignments_profile_and_directory_are_one_relation():
    await ensure_indexes_and_seed()
    await ensure_talents()
    unique = uuid.uuid4().hex
    email = f"ministries.{unique}@example.com"
    password = "MinistriesTestPass!"
    user_result = await server.db.users.insert_one({
        "nombre": "Ministry Tester", "email": email,
        "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "rol": "lider", "is_active": True, "token_version": 1,
        **access_defaults_for_role("lider"),
    })
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    client.headers.update({"Authorization": f"Bearer {login.json()['token']}"})
    person_ids = []
    ministry_id = None
    try:
        for name in ("Christopher", "María"):
            created = await client.post(
                "/api/core/persons",
                json={
                    "nombre": name, "apellido": f"Ministerio {unique[:5]}",
                    "fecha_nacimiento": "1990-01-01",
                    "idempotency_key": str(uuid.uuid4()),
                },
            )
            assert created.status_code == 201
            person_ids.append(created.json()["person_id"])

        catalog = await client.get("/api/ministries")
        assert catalog.status_code == 200
        assert {"Niños", "Media", "Sonido"}.issubset(
            {item["nombre"] for item in catalog.json()["items"]}
        )
        created_ministry = await client.post(
            "/api/ministries",
            json={
                "nombre": f"Comunicaciones {unique[:6]}",
                "descripcion": "Ministerio administrable de prueba",
                "suggested_age_groups": [],
            },
        )
        assert created_ministry.status_code == 201
        ministry_id = created_ministry.json()["ministry_id"]
        empty_detail = await client.get(f"/api/ministries/{ministry_id}")
        assert empty_detail.status_code == 200
        assert empty_detail.json()["active_people_count"] == 0
        assert empty_detail.json()["leadership_vacancy"] is True

        roles = await client.get("/api/ministries/roles/catalog")
        role_map = {item["nombre"]: item["role_id"] for item in roles.json()["items"]}
        participant_role = role_map["Participante"]
        director_role = role_map["Director/a"]
        first_assignment = await client.post(
            f"/api/ministries/person/{person_ids[0]}/assignments",
            json={
                "person_id": person_ids[0], "ministry_id": ministry_id,
                "role_id": participant_role, "activo": True,
                "fecha_inicio": "2025-07-01",
            },
        )
        assert first_assignment.status_code == 201
        detail_without_leader = await client.get(f"/api/ministries/{ministry_id}")
        assert detail_without_leader.json()["active_people_count"] == 1
        assert detail_without_leader.json()["leadership_vacancy"] is True

        leader_assignment = await client.post(
            f"/api/ministries/person/{person_ids[1]}/assignments",
            json={
                "person_id": person_ids[1], "ministry_id": ministry_id,
                "role_id": director_role, "activo": True,
                "fecha_inicio": "2025-07-02",
            },
        )
        assert leader_assignment.status_code == 201
        detail = await client.get(f"/api/ministries/{ministry_id}")
        assert detail.json()["active_people_count"] == 2
        assert detail.json()["leadership_vacancy"] is False
        assert {item["person_id"] for item in detail.json()["members"]} == set(person_ids)
        assert all(item["canonical_profile_path"].startswith("/personas/") for item in detail.json()["members"])

        person_assignments = await client.get(
            f"/api/ministries/person/{person_ids[0]}/assignments"
        )
        assert person_assignments.status_code == 200
        assert person_assignments.json()["items"][0]["ministry_id"] == ministry_id
        duplicate = await client.post(
            f"/api/ministries/person/{person_ids[0]}/assignments",
            json={
                "person_id": person_ids[0], "ministry_id": ministry_id,
                "role_id": participant_role, "activo": True,
                "fecha_inicio": "2025-07-03",
            },
        )
        assert duplicate.status_code == 409

        profile = await client.get(f"/api/core/persons/{person_ids[0]}/profile")
        assert profile.status_code == 200
        assert profile.json()["ministerios"][0]["ministry_name"] == created_ministry.json()["nombre"]
        ministry_card = next(
            item for item in profile.json()["sections"]
            if item["section_key"] == "ministerio_servicio"
        )
        assert ministry_card["status_code"] == "has_summary"
        assert ministry_card["route"] == f"/ministerios/{ministry_id}"

        directory = await client.get(
            "/api/core/persons/directory/search",
            params={"ministry_id": ministry_id, "ministry_role_id": director_role},
        )
        assert directory.status_code == 200
        assert [item["person_id"] for item in directory.json()["items"]] == [person_ids[1]]
        assert directory.json()["items"][0]["ministries"][0]["ministry_id"] == ministry_id
        assert directory.json()["items"][0]["ministries"][0]["role_name"] == "Director/a"

        for person_id in person_ids:
            person_doc = await server.db.persons.find_one({"_id": ObjectId(person_id)})
            assert "ministerios" not in person_doc
            assert "ministry_assignments" not in person_doc

        archive = await client.post(f"/api/ministries/{ministry_id}/archive")
        assert archive.status_code == 200
        assert await server.db.ministry_assignments.count_documents({"ministry_id": ministry_id}) == 2
    finally:
        await client.aclose()
        if ministry_id:
            await server.db.ministry_assignments.delete_many({"ministry_id": ministry_id})
            await server.db.ministry_catalog.delete_one({"_id": ministry_id})
        await server.db.person_activity.delete_many({"person_id": {"$in": person_ids}})
        await server.db.persons.delete_many({
            "_id": {"$in": [ObjectId(item) for item in person_ids]}
        })
        await server.db.users.delete_one({"_id": user_result.inserted_id})
