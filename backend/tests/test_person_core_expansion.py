"""Person Core expansion regression: canonical family and structured talents."""
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
from person_core_expansion import ensure_indexes_and_seed  # noqa: E402
from ministries import ensure_indexes_and_seed as ensure_ministries  # noqa: E402


@pytest.mark.asyncio
async def test_canonical_family_household_talents_and_directory():
    await ensure_indexes_and_seed()
    await ensure_ministries()
    unique = uuid.uuid4().hex
    email = f"core.expansion.{unique}@example.com"
    password = "CoreExpansionPass!"
    user_doc = {
        "nombre": "Core Expansion Tester",
        "email": email,
        "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "rol": "lider",
        "is_active": True,
        "token_version": 1,
        **access_defaults_for_role("lider"),
    }
    user_result = await server.db.users.insert_one(user_doc)
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    client.headers.update({"Authorization": f"Bearer {login.json()['token']}"})
    created = await client.post(
        "/api/core/persons",
        json={
            "nombre": "Josué",
            "apellido": f"Prueba {unique[:6]}",
            "fecha_nacimiento": "1988-02-10",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert created.status_code == 201, created.text
    parent_id = created.json()["person_id"]
    child_id = None
    household_id = None
    try:
        catalog = await client.get("/api/core/talents/catalog")
        assert catalog.status_code == 200
        mechanic = next(item for item in catalog.json()["items"] if item["nombre"] == "Mecánico")
        painter = next(item for item in catalog.json()["items"] if item["nombre"] == "Pintor")
        custom = await client.post(
            "/api/core/talents/catalog",
            json={"nombre": "Electricidad automotriz", "tipo": "habilidad"},
        )
        assert custom.status_code == 201
        talents = await client.put(
            f"/api/core/persons/{parent_id}/talents",
            json={
                "ocupacion_principal_id": mechanic["talent_id"],
                "habilidad_ids": [painter["talent_id"], custom.json()["talent_id"]],
            },
        )
        assert talents.status_code == 200
        assert talents.json()["ocupacion_principal"]["nombre"] == "Mecánico"
        assert {item["nombre"] for item in talents.json()["habilidades"]} == {
            "Pintor", "Electricidad automotriz"
        }

        by_text = await client.get("/api/core/persons/directory/search", params={"q": "Mecánico"})
        by_skill = await client.get(
            "/api/core/persons/directory/search", params={"talent_id": painter["talent_id"]}
        )
        by_occupation_and_skill = await client.get(
            "/api/core/persons/directory/search",
            params={
                "occupation_id": mechanic["talent_id"],
                "skill_id": custom.json()["talent_id"],
                "age_group": "adulto",
            },
        )
        assert by_text.status_code == 200
        assert by_skill.status_code == 200
        assert by_occupation_and_skill.status_code == 200
        assert {item["person_id"] for item in by_text.json()["items"]} == {parent_id}
        assert {item["person_id"] for item in by_skill.json()["items"]} == {parent_id}
        assert [item["person_id"] for item in by_occupation_and_skill.json()["items"]] == [parent_id]
        assert by_occupation_and_skill.json()["has_more"] is False
        membership_filter = await client.get(
            "/api/core/persons/directory/search", params={"membership_status": "activo"}
        )
        assert membership_filter.status_code == 409
        assert "Membresía" in membership_filter.json()["detail"]

        ministries = await client.get("/api/ministries")
        ministry_id = next(
            item["ministry_id"] for item in ministries.json()["items"] if item["nombre"] == "Niños"
        )
        ministry_roles = await client.get("/api/ministries/roles/catalog")
        participant_role_id = next(
            item["role_id"] for item in ministry_roles.json()["items"]
            if item["nombre"] == "Participante"
        )
        quick = await client.post(
            f"/api/core/persons/{parent_id}/family/quick-create",
            json={
                "nombre": "Abigail",
                "apellido": f"Prueba {unique[:6]}",
                "fecha_nacimiento": "2017-09-14",
                "genero": "femenino",
                "telefono": "809-555-0142",
                "linea1": "Calle Familia 10",
                "ciudad": "Santo Domingo",
                "relation_type": "parent_of",
                "same_household": True,
                "ministry_assignments": [
                    {"ministry_id": ministry_id, "role_id": participant_role_id}
                ],
            },
        )
        assert quick.status_code == 201, quick.text
        child_id = quick.json()["person_id"]
        assert child_id != parent_id
        assert quick.json()["person_number"].startswith("VV-")
        assert quick.json()["canonical_profile_path"] == f"/personas/{child_id}"

        parent_family = await client.get(f"/api/core/persons/{parent_id}/relationships")
        child_family = await client.get(f"/api/core/persons/{child_id}/relationships")
        assert parent_family.status_code == 200
        assert child_family.status_code == 200
        assert parent_family.json()["items"][0]["related_person_id"] == child_id
        assert parent_family.json()["items"][0]["relation_label"] == "Padre/Madre"
        assert child_family.json()["items"][0]["related_person_id"] == parent_id
        assert child_family.json()["items"][0]["relation_label"] == "Hijo/a"
        assert child_family.json()["items"][0]["relationship_id"] == parent_family.json()["items"][0]["relationship_id"]

        duplicate_relation = await client.post(
            f"/api/core/persons/{parent_id}/relationships",
            json={
                "related_person_id": child_id,
                "relation_type": "parent_of",
                "same_household": False,
            },
        )
        assert duplicate_relation.status_code == 409
        duplicate_person = await client.post(
            f"/api/core/persons/{parent_id}/family/quick-create",
            json={
                "nombre": "Abigail",
                "apellido": f"Prueba {unique[:6]}",
                "fecha_nacimiento": "2017-09-14",
                "genero": "femenino",
                "relation_type": "parent_of",
                "same_household": False,
            },
        )
        assert duplicate_person.status_code == 409

        household = await client.get(f"/api/core/persons/{parent_id}/household-membership")
        assert household.status_code == 200
        household_id = household.json()["record"]["household_id"]
        assert {item["person_id"] for item in household.json()["record"]["members"]} == {
            parent_id, child_id
        }

        child_profile = await client.get(f"/api/core/persons/{child_id}/profile")
        assert child_profile.status_code == 200
        assert child_profile.json()["canonical_profile_path"] == f"/personas/{child_id}"
        assert child_profile.json()["header"]["age_group"] == "ninez"
        assert child_profile.json()["header"]["age_category"] == "menor"
        assert child_profile.json()["familia"][0]["related_person_id"] == parent_id
        assert child_profile.json()["ministerios"][0]["ministry_id"] == ministry_id
        assert child_profile.json()["ministerios"][0]["role_name"] == "Participante"

        directory_by_ministry_text = await client.get(
            "/api/core/persons/directory/search", params={"q": "Niños"}
        )
        assert directory_by_ministry_text.status_code == 200
        child_directory_item = next(
            item for item in directory_by_ministry_text.json()["items"]
            if item["person_id"] == child_id
        )
        assert child_directory_item["ministries"][0]["ministry_id"] == ministry_id
        assert child_directory_item["ministries"][0]["role_name"] == "Participante"

        parent_profile = await client.get(f"/api/core/persons/{parent_id}/profile")
        assert parent_profile.json()["header"]["ocupacion"] == "Mecánico"
        assert {item["nombre"] for item in parent_profile.json()["header"]["habilidades"]} == {
            "Pintor", "Electricidad automotriz"
        }

        invalid_demographics = await client.put(
            f"/api/core/persons/{parent_id}/profile-basics",
            json={"genero": "texto libre", "estado_civil": "cualquier cosa"},
        )
        assert invalid_demographics.status_code == 422
        legacy_family = await client.post(
            f"/api/core/persons/{parent_id}/family",
            json={"nombre": "String prohibido", "relacion": "Hija"},
        )
        assert legacy_family.status_code in {410, 422}

        parent_doc = await server.db.persons.find_one({"_id": ObjectId(parent_id)})
        child_doc = await server.db.persons.find_one({"_id": ObjectId(child_id)})
        for doc in (parent_doc, child_doc):
            for forbidden in ("familia", "relationships", "household", "talents", "habilidades"):
                assert forbidden not in doc
    finally:
        await client.aclose()
        await server.db.person_relationships.delete_many({
            "$or": [{"person_a_id": parent_id}, {"person_b_id": parent_id}]
        })
        if household_id:
            await server.db.household_memberships.delete_many({"household_id": household_id})
            await server.db.households.delete_one({"_id": household_id})
        await server.db.person_talents.delete_many({"_id": {"$in": [parent_id, child_id]}})
        await server.db.ministry_assignments.delete_many({"person_id": {"$in": [parent_id, child_id]}})
        await server.db.person_contacts.delete_many({"person_id": child_id})
        await server.db.person_addresses.delete_many({"person_id": child_id})
        await server.db.person_activity.delete_many({"person_id": {"$in": [parent_id, child_id]}})
        person_ids = [ObjectId(item) for item in [parent_id, child_id] if item]
        await server.db.persons.delete_many({"_id": {"$in": person_ids}})
        await server.db.users.delete_one({"_id": user_result.inserted_id})
        await server.db.talent_catalog.delete_one({"_id": custom.json()["talent_id"]}) if 'custom' in locals() and custom.status_code == 201 else None
