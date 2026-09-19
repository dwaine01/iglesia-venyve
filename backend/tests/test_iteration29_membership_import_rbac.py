import io
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import CORE_ACCESS_MANAGE, access_defaults_for_role


PASSWORD = "FeatureFlow2026!"
PREFIX = "qa.iter29.membership."


# Membership direct-create and import DRY-RUN RBAC regression coverage.
async def create_user(role: str = "pastor", coordinator: bool = False):
    user_id = ObjectId()
    email = f"{PREFIX}{uuid.uuid4().hex[:10]}@example.com"
    defaults = access_defaults_for_role(role)
    if coordinator:
        defaults["capabilities"] = sorted(set(defaults.get("capabilities", []) + [CORE_ACCESS_MANAGE]))
        defaults["access_level"] = "coordinador_general"
    await server.db.users.insert_one(
        {
            "_id": user_id,
            "nombre": "QA Iter29",
            "email": email,
            "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "rol": role,
            "is_active": True,
            "token_version": 1,
            "created_at": datetime.now(timezone.utc),
            **defaults,
        }
    )
    return str(user_id), email


async def login_client(email: str):
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


async def cleanup():
    users = await server.db.users.find({"email": {"$regex": f"^{PREFIX}"}}, {"_id": 1}).to_list(200)
    user_ids = [str(item["_id"]) for item in users]

    people = await server.db.persons.find(
        {
            "$or": [
                {"created_by": {"$in": user_ids}},
                {"idempotency_key": {"$regex": "^qa:iter29:"}},
            ]
        },
        {"_id": 1},
    ).to_list(200)
    person_ids = [str(item["_id"]) for item in people]

    memberships = await server.db.person_memberships.find(
        {"person_id": {"$in": person_ids}}, {"_id": 0, "member_number": 1}
    ).to_list(200)

    await server.db.membership_number_registry.delete_many(
        {"member_number": {"$in": [item["member_number"] for item in memberships]}}
    )
    await server.db.membership_events.delete_many({"person_id": {"$in": person_ids}})
    await server.db.person_memberships.delete_many({"person_id": {"$in": person_ids}})
    await server.db.person_activity.delete_many({"person_id": {"$in": person_ids}})
    await server.db.person_contacts.delete_many({"person_id": {"$in": person_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [item["_id"] for item in people]}})
    await server.db.users.delete_many({"email": {"$regex": f"^{PREFIX}"}})


@pytest.mark.asyncio
async def test_normal_person_create_without_direct_membership():
    await cleanup()
    _, leader_email = await create_user("lider")
    client, headers = await login_client(leader_email)
    try:
        payload = {
            "nombre": "Carlos",
            "apellido": "Regular",
            "telefono": "6145551010",
            "idempotency_key": f"qa:iter29:{uuid.uuid4()}",
            "preexisting_active_member": False,
        }
        response = await client.post("/api/core/persons", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        data = response.json()
        assert data.get("membership") is None
        stored = await server.db.person_memberships.find_one({"person_id": data["person_id"]}, {"_id": 0})
        assert stored is None
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_import_rejects_unsupported_extension_and_rbac():
    await cleanup()
    _, pastor_email = await create_user("pastor")
    _, leader_email = await create_user("lider")
    _, persona_email = await create_user("persona")
    pastor, pastor_headers = await login_client(pastor_email)
    leader, leader_headers = await login_client(leader_email)
    persona, persona_headers = await login_client(persona_email)
    try:
        bad_ext = await pastor.post(
            "/api/membership/import/dry-run",
            files={"file": ("members.txt", b"not,valid", "text/plain")},
            headers=pastor_headers,
        )
        assert bad_ext.status_code == 415

        csv_payload = b"Nombre,Apellido,Correo\nAna,Rios,ana@example.com\n"
        leader_denied = await leader.post(
            "/api/membership/import/dry-run",
            files={"file": ("members.csv", csv_payload, "text/csv")},
            headers=leader_headers,
        )
        assert leader_denied.status_code == 403

        persona_denied = await persona.post(
            "/api/membership/import/dry-run",
            files={"file": ("members.csv", csv_payload, "text/csv")},
            headers=persona_headers,
        )
        assert persona_denied.status_code == 403
    finally:
        await pastor.aclose()
        await leader.aclose()
        await persona.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_dry_run_returns_duplicate_review_and_zero_writes():
    await cleanup()
    _, pastor_email = await create_user("pastor")
    client, headers = await login_client(pastor_email)
    try:
        before = {
            name: await server.db[name].count_documents({})
            for name in ["persons", "person_memberships", "households", "person_contacts"]
        }
        csv_data = (
            "Nombre,Apellido,Correo,Telefono,Direccion,Ciudad,Estado,ZIP,Fecha de nacimiento\n"
            "Maria,Rios,maria@example.com,6145550101,123 Main Street,Columbus,OH,43204,1990-01-01\n"
            "Maria,Rios,maria@example.com,6145550101,123 Main St.,Columbus,OH,43204,1990-01-01\n"
            "NoLast,,badmail,111, ,Columbus,OH,43204,\n"
        )
        response = await client.post(
            "/api/membership/import/dry-run",
            files={"file": ("members.csv", csv_data.encode(), "text/csv")},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["dry_run"] is True
        assert data["database_writes"] == 0
        assert data["summary"]["total"] == 3
        assert data["summary"]["review"] >= 1
        assert data["summary"]["error"] >= 1
        assert any("posible_duplicado" in row["review_reasons"] for row in data["rows"])

        after = {name: await server.db[name].count_documents({}) for name in before}
        assert before == after
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_direct_membership_stamps_document_eligibility_fields():
    await cleanup()
    _, pastor_email = await create_user("pastor")
    client, headers = await login_client(pastor_email)
    try:
        payload = {
            "nombre": "Lucia",
            "apellido": "Historica",
            "telefono": "6145559090",
            "idempotency_key": f"qa:iter29:{uuid.uuid4()}",
            "preexisting_active_member": True,
            "existing_member_number": "A-9292",
        }
        response = await client.post("/api/core/persons", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["membership"]["direct"] is True

        membership = await server.db.person_memberships.find_one({"person_id": data["person_id"]}, {"_id": 0})
        assert membership["direct_membership"] is True
        assert membership["status"] == "active"
        assert membership.get("card_eligible_at") is not None
        assert membership.get("certificate_eligible_at") is not None
    finally:
        await client.aclose()
        await cleanup()
