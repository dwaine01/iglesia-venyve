"""Regresión Iteración 24: Front Groups/Liderazgo RBAC + privacidad Perfil 360."""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from qa_demo_cleanup import delete_qa_artifacts, qa_preview


PASSWORD = "JourneyUI2026!"


async def cleanup_qa():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


# Módulo: helpers efímeros para usuarios/personas QA
async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one(
        {
            "_id": person_id,
            "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
            "nombre": "QA",
            "apellido": label,
            "fecha_nacimiento": "1985-02-10",
            "search_key": f"qa {label}".lower(),
            "idempotency_key": f"qa:iter24:{uuid.uuid4()}",
            "version": 1,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None, access_scope=None) -> tuple[str, str]:
    user_id = ObjectId()
    email = f"qa.iter24.{label.lower().replace(' ', '.')}.{uuid.uuid4().hex[:6]}@example.com"
    defaults = access_defaults_for_role(role)
    if capabilities is not None:
        defaults["capabilities"] = sorted(set(capabilities))
    if access_scope is not None:
        defaults["access_scope"] = access_scope
    await server.db.users.insert_one(
        {
            "_id": user_id,
            "nombre": f"QA {label}",
            "email": email,
            "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "rol": role,
            "is_active": True,
            "token_version": 1,
            "created_at": datetime.now(timezone.utc),
            **defaults,
            **({"person_id": person_id} if person_id else {}),
        }
    )
    return str(user_id), email


async def auth_client(email: str) -> tuple[AsyncClient, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


# Módulo: bypass pastoral legado y capabilities explícitas de lectura
@pytest.mark.asyncio
async def test_legacy_pastor_empty_capabilities_can_read_frontgroups_and_leadership_dashboard():
    await cleanup_qa()
    _, pastor_email = await create_user("Legacy Pastor I24", "pastor", capabilities=[], access_scope={"persons": "all"})
    client, headers = await auth_client(pastor_email)
    try:
        fg = await client.get("/api/front-groups", headers=headers)
        leadership_requirements = await client.get("/api/leadership/requirements", headers=headers)
        leadership_dashboard = await client.get("/api/leadership/dashboard", headers=headers)

        assert fg.status_code == 200, fg.text
        assert leadership_requirements.status_code == 200, leadership_requirements.text
        assert leadership_dashboard.status_code == 200, leadership_dashboard.text
    finally:
        await client.aclose()
        await cleanup_qa()


# Módulo: delegación por capabilities + denegación sin permisos
@pytest.mark.asyncio
async def test_explicit_front_and_leadership_capabilities_allow_read_and_without_them_403():
    await cleanup_qa()
    leader_person = await create_person("FrontLead Viewer")
    _, leader_email = await create_user(
        "FrontLead Viewer",
        "lider",
        person_id=leader_person,
        capabilities=["front_groups.view", "leadership.view"],
        access_scope={"persons": "created_by"},
    )
    denied_person = await create_person("FrontLead Denied")
    _, denied_email = await create_user(
        "FrontLead Denied",
        "persona",
        person_id=denied_person,
        capabilities=[],
        access_scope={"persons": "self"},
    )

    allowed_client, allowed_headers = await auth_client(leader_email)
    denied_client, denied_headers = await auth_client(denied_email)
    try:
        assert (await allowed_client.get("/api/front-groups", headers=allowed_headers)).status_code == 200
        assert (await allowed_client.get("/api/leadership/dashboard", headers=allowed_headers)).status_code == 200

        assert (await denied_client.get("/api/front-groups", headers=denied_headers)).status_code == 403
        assert (await denied_client.get("/api/leadership/dashboard", headers=denied_headers)).status_code == 403
    finally:
        await allowed_client.aclose()
        await denied_client.aclose()
        await cleanup_qa()


# Módulo: core.access.manage sin rol pastoral NO otorga autoridad pastoral global
@pytest.mark.asyncio
async def test_core_access_manage_without_pastoral_role_does_not_bypass_frontlead_read_permissions():
    await cleanup_qa()
    manager_person = await create_person("Core Access Only")
    _, manager_email = await create_user(
        "Core Access Only",
        "lider",
        person_id=manager_person,
        capabilities=["core.access.manage"],
        access_scope={"persons": "all"},
    )
    client, headers = await auth_client(manager_email)
    try:
        governance = await client.get("/api/core/governance/users", headers=headers)
        fg = await client.get("/api/front-groups", headers=headers)
        leadership = await client.get("/api/leadership/dashboard", headers=headers)

        assert governance.status_code == 200, governance.text
        assert fg.status_code == 403, fg.text
        assert leadership.status_code == 403, leadership.text
    finally:
        await client.aclose()
        await cleanup_qa()


# Módulo: privacidad Perfil 360 se mantiene sin capability sensible explícita
@pytest.mark.asyncio
async def test_profile_360_privacy_pastoral_without_sensitive_capability_hides_sensitive_fields():
    await cleanup_qa()
    target_person_id = await create_person("Profile Sensitive")
    await server.db.person_contacts.insert_one(
        {
            "contact_id": str(uuid.uuid4()),
            "person_id": target_person_id,
            "tipo": "telefono",
            "valor": "8090000000",
            "es_principal": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    await server.db.person_addresses.insert_one(
        {
            "address_id": str(uuid.uuid4()),
            "person_id": target_person_id,
            "linea1": "Calle QA 24",
            "ciudad": "Santo Domingo",
            "es_principal": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    _, pastoral_email = await create_user(
        "Pastor No Sensitive",
        "pastor",
        capabilities=["person.history.read"],
        access_scope={"persons": "all"},
    )
    client, headers = await auth_client(pastoral_email)
    try:
        profile = await client.get(f"/api/core/persons/{target_person_id}/profile", headers=headers)
        assert profile.status_code == 200, profile.text
        header = profile.json().get("header", {})

        assert header.get("nombre") == "QA"
        assert "fecha_nacimiento" not in header
        assert "primary_contact" not in header
        assert "city" not in header
    finally:
        await client.aclose()
        await cleanup_qa()
