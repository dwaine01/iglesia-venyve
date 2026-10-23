"""Cuentas de acceso para mentores, creadas por pastor o coordinador_general.

A pedido del dueño: "cada mentor tiene que tener su panel con sus
credenciales, que las crea el coordinador o el pastor general".

Reutiliza el flujo EXISTENTE `POST /api/core/governance/users`
(core_governance.py) sin duplicar lógica: se le agregó un campo opcional
`mentor_access: bool` que, combinado con `access_level="persona"`, agrega
`mentorship.outreach.report` + las capacidades de perfil propio
(`PERSON_SELF_CAPABILITIES`, para que el mentor vea su Perfil 360 e insignia)
a los defaults de esa cuenta. La contraseña temporal y el
`must_change_password=True` del primer ingreso ya existían en ese mismo
endpoint.

Cubre:
- Pastor y coordinador_general pueden crear la cuenta de un mentor.
- Un mentor/persona NO puede crear cuentas (ni la suya propia ni de otros).
- `mentor_access=True` exige `access_level="persona"` (400 en cualquier otro
  nivel).
- La cuenta nueva tiene los defaults de persona + sus capacidades de perfil
  propio + outreach.report (nada de badge.manage/outreach.assign).
- `GET /api/mentorship/badge/{person_id}` ahora informa `has_account`,
  `account_email` y `can_create_account` (solo true para pastor/coordinador).
- El mentor recién creado, al entrar, solo ve sus propias visitas y no puede
  usar nada administrativo (crear campañas, ver dashboard de líderes).
"""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role, PERSON_SELF_CAPABILITIES
from core_governance import access_defaults
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "MentorAccountPass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA",
        "apellido": label,
        "idempotency_key": f"qa:mentoracc:{uuid.uuid4()}",
        "version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str, extra_defaults: dict | None = None) -> str:
    defaults = access_defaults_for_role(role) if role != "coordinador_general" else access_defaults("coordinador_general")
    if extra_defaults:
        defaults.update(extra_defaults)
    email = f"qa.mentoracc.{label.lower().replace(' ', '.')}.{uuid.uuid4().hex[:6]}@example.com"
    document = {
        "nombre": f"QA {label}",
        "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": "lider" if role == "coordinador_general" else role,
        "person_id": person_id,
        "is_active": True,
        "token_version": 1,
        "created_at": datetime.now(timezone.utc),
        **defaults,
    }
    await server.db.users.insert_one(document)
    return email


async def auth_client(email: str, password: str = PASSWORD) -> tuple[AsyncClient, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


@pytest.mark.asyncio
async def test_pastor_can_create_mentor_account_with_outreach_report_only():
    await cleanup()
    pastor_person_id = await create_person("Pastor Creator")
    target_person_id = await create_person("Mentor New Account")
    pastor_email = await create_user("Pastor Creator", "pastor", pastor_person_id)
    client, headers = await auth_client(pastor_email)
    try:
        email = f"qa.mentoracc.newmentor.{uuid.uuid4().hex[:6]}@example.com"
        response = await client.post(
            "/api/core/governance/users",
            json={
                "person_id": target_person_id, "email": email,
                "temporary_password": "MentorTempPass123!", "access_level": "persona", "mentor_access": True,
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        caps = set(response.json()["capabilities"])
        expected = set(access_defaults("persona")["capabilities"]) | set(PERSON_SELF_CAPABILITIES) | {"mentorship.outreach.report", "processes.participate", "library.deliver"}
        assert caps == expected, f"debe ser persona + sus capacidades de perfil propio + outreach.report, obtuvo {caps}"

        login = await client.post("/api/auth/login", json={"email": email, "password": "MentorTempPass123!"})
        assert login.status_code == 200
        assert login.json()["user"]["must_change_password"] is True, "debe forzar cambio de clave en el primer ingreso"

        mentor_client, mentor_headers = await auth_client(email, "MentorTempPass123!")
        try:
            change = await mentor_client.post(
                "/api/auth/change-password",
                json={"current_password": "MentorTempPass123!", "new_password": "MentorNewPass456!"},
                headers=mentor_headers,
            )
            assert change.status_code == 200, change.text
            mentor_headers = {"Authorization": f"Bearer {change.json()['token']}"}
            own_profile = await mentor_client.get(f"/api/core/persons/{target_person_id}/profile", headers=mentor_headers)
            assert own_profile.status_code == 200, f"el mentor debe poder ver su propio Perfil 360: {own_profile.text}"
            own_badge = await mentor_client.get(f"/api/mentorship/badge/{target_person_id}", headers=mentor_headers)
            assert own_badge.status_code == 200, f"el mentor debe poder ver su propia insignia: {own_badge.text}"
        finally:
            await mentor_client.aclose()
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_coordinador_general_can_create_mentor_account():
    await cleanup()
    coord_person_id = await create_person("Coordinator Creator")
    target_person_id = await create_person("Mentor By Coordinator")
    coord_email = await create_user("Coordinator Creator", "coordinador_general", coord_person_id)
    client, headers = await auth_client(coord_email)
    try:
        email = f"qa.mentoracc.bycoord.{uuid.uuid4().hex[:6]}@example.com"
        response = await client.post(
            "/api/core/governance/users",
            json={
                "person_id": target_person_id, "email": email,
                "temporary_password": "MentorTempPass123!", "access_level": "persona", "mentor_access": True,
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        assert "mentorship.outreach.report" in response.json()["capabilities"]
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_mentor_or_persona_cannot_create_accounts():
    await cleanup()
    mentor_person_id = await create_person("Mentor No Create")
    other_person_id = await create_person("Other Target No Create")
    mentor_email = await create_user(
        "Mentor No Create", "persona", mentor_person_id,
        extra_defaults={"capabilities": [*access_defaults_for_role("persona")["capabilities"], "mentorship.outreach.report"]},
    )
    client, headers = await auth_client(mentor_email)
    try:
        response = await client.post(
            "/api/core/governance/users",
            json={
                "person_id": other_person_id, "email": f"qa.mentoracc.blocked.{uuid.uuid4().hex[:6]}@example.com",
                "temporary_password": "ShouldNotWork123!", "access_level": "persona",
            },
            headers=headers,
        )
        assert response.status_code == 403
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_mentor_access_flag_requires_persona_level():
    await cleanup()
    pastor_person_id = await create_person("Pastor Creator Guard")
    target_person_id = await create_person("Target Guard")
    pastor_email = await create_user("Pastor Creator Guard", "pastor", pastor_person_id)
    client, headers = await auth_client(pastor_email)
    try:
        response = await client.post(
            "/api/core/governance/users",
            json={
                "person_id": target_person_id, "email": f"qa.mentoracc.guard.{uuid.uuid4().hex[:6]}@example.com",
                "temporary_password": "ShouldNotWork123!", "access_level": "lider", "mentor_access": True,
            },
            headers=headers,
        )
        assert response.status_code == 400
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_badge_endpoint_reports_account_status_and_create_permission():
    await cleanup()
    pastor_person_id = await create_person("Pastor Viewer")
    lider_person_id = await create_person("Lider Viewer No Manage")
    target_person_id = await create_person("Target Status")
    pastor_email = await create_user("Pastor Viewer", "pastor", pastor_person_id)
    lider_email = await create_user("Lider Viewer No Manage", "lider", lider_person_id, extra_defaults={"access_scope": {"persons": "all"}})
    pastor_client, pastor_headers = await auth_client(pastor_email)
    lider_client, lider_headers = await auth_client(lider_email)
    try:
        before = await pastor_client.get(f"/api/mentorship/badge/{target_person_id}", headers=pastor_headers)
        assert before.status_code == 200
        assert before.json()["has_account"] is False
        assert before.json()["can_create_account"] is True

        lider_view = await lider_client.get(f"/api/mentorship/badge/{target_person_id}", headers=lider_headers)
        assert lider_view.status_code == 200
        assert lider_view.json()["can_create_account"] is False, "un lider sin badge.manage/CORE_ACCESS_MANAGE no debe poder crear accesos"

        email = f"qa.mentoracc.status.{uuid.uuid4().hex[:6]}@example.com"
        await pastor_client.post(
            "/api/core/governance/users",
            json={
                "person_id": target_person_id, "email": email,
                "temporary_password": "MentorTempPass123!", "access_level": "persona", "mentor_access": True,
            },
            headers=pastor_headers,
        )
        after = await pastor_client.get(f"/api/mentorship/badge/{target_person_id}", headers=pastor_headers)
        assert after.json()["has_account"] is True
        assert after.json()["account_email"] == email
    finally:
        await pastor_client.aclose()
        await lider_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_new_mentor_sees_only_own_visits_and_no_admin_capability():
    await cleanup()
    pastor_person_id = await create_person("Pastor For Scope Test")
    target_person_id = await create_person("Mentor Scope Test")
    pastor_email = await create_user("Pastor For Scope Test", "pastor", pastor_person_id)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    try:
        email = f"qa.mentoracc.scope.{uuid.uuid4().hex[:6]}@example.com"
        await pastor_client.post(
            "/api/core/governance/users",
            json={
                "person_id": target_person_id, "email": email,
                "temporary_password": "MentorTempPass123!", "access_level": "persona", "mentor_access": True,
            },
            headers=pastor_headers,
        )
        mentor_client, mentor_headers = await auth_client(email, password="MentorTempPass123!")
        try:
            changed = await mentor_client.post(
                "/api/auth/change-password", json={"current_password": "MentorTempPass123!", "new_password": "MentorFinalPass456!"}, headers=mentor_headers,
            )
            assert changed.status_code == 200
            mentor_headers = {"Authorization": f"Bearer {changed.json()['token']}"}

            visits = await mentor_client.get("/api/mentorship/outreach/visits", headers=mentor_headers)
            assert visits.status_code == 200
            assert visits.json()["items"] == []

            dashboard = await mentor_client.get("/api/mentorship/outreach/dashboard", headers=mentor_headers)
            assert dashboard.status_code == 403

            campaign = await mentor_client.post("/api/mentorship/outreach/campaigns", json={"name": "No deberia poder", "location": "Zona QA", "start_date": "2026-03-01", "end_date": "2026-03-07"}, headers=mentor_headers)
            assert campaign.status_code == 403
        finally:
            await mentor_client.aclose()
    finally:
        await pastor_client.aclose()
        await cleanup()
