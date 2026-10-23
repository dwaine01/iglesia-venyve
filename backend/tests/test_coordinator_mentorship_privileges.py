"""Privilegios de mentoría/invasión para el nivel coordinador_general.

A pedido del dueño: "el coordinador general tiene que tener el privilegio de
elegir los mentores para asignarles libros e invasión". Cubre:

1. Cuentas NUEVAS: `access_defaults("coordinador_general", ...)` en
   core_governance.py ahora incluye `mentorship.badge.manage`,
   `mentorship.outreach.assign` y `consolidation.mentor.transfer` por defecto
   (sin tener que delegarlo a mano desde Core > Accesos).
2. Cuentas EXISTENTES: `ensure_access_defaults(db)` en access_control.py (ya
   se ejecuta en cada arranque del backend, ver server.py) ahora también les
   agrega esas 3 capacidades vía `$addToSet` (aditivo, nunca pisa capacidades
   que ya tuvieran).
3. Funcional: un coordinador_general puede dar/quitar la insignia de Mentor,
   crear campañas de invasión y asignar visitas a CUALQUIER mentor, y ver el
   panel de líderes — pero sigue sin autoridad pastoral (no puede listar ni
   gestionar pastores).
"""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import ensure_access_defaults, CORE_ACCESS_MANAGE
from core_governance import access_defaults
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "CoordinatorPrivPass123!"


def test_access_defaults_grants_mentorship_and_transfer_capabilities_to_new_coordinator():
    defaults = access_defaults("coordinador_general")
    caps = set(defaults["capabilities"])
    assert "mentorship.badge.manage" in caps
    assert "mentorship.outreach.assign" in caps
    assert "consolidation.mentor.transfer" in caps
    # outreach.report no se agrega explicitamente: outreach.assign ya cubre
    # todo lo que un lider de invasiones necesita (ver mentorship_outreach.py).
    assert defaults["access_level"] == "coordinador_general"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA",
        "apellido": label,
        "idempotency_key": f"qa:coordpriv:{uuid.uuid4()}",
        "version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_coordinator_general_user(label: str, extra_capabilities: list[str] | None = None) -> tuple[str, str]:
    """Inserta una cuenta coordinador_general ya lista para usar (sin pasar por
    must_change_password/onboarding) con los defaults reales de access_defaults()."""
    person_id = await create_person(label)
    defaults = access_defaults("coordinador_general")
    if extra_capabilities:
        defaults["capabilities"] = sorted(set(defaults["capabilities"] + extra_capabilities))
    email = f"qa.coordpriv.{label.lower().replace(' ', '.')}.{uuid.uuid4().hex[:6]}@example.com"
    document = {
        "nombre": f"QA {label}",
        "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "person_id": person_id,
        "is_active": True,
        "token_version": 1,
        "created_at": datetime.now(timezone.utc),
        **defaults,
    }
    await server.db.users.insert_one(document)
    return email, person_id


async def auth_client(email: str) -> tuple[AsyncClient, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


@pytest.mark.asyncio
async def test_existing_coordinator_general_receives_capabilities_via_idempotent_migration():
    """Simula una cuenta coordinador_general creada ANTES de este cambio (sin las
    3 capacidades nuevas, pero con una capability a medida) y confirma que
    ensure_access_defaults() se las agrega sin tocar la que ya tenía."""
    await cleanup()
    person_id = await create_person("Legacy Coordinator")
    email = f"qa.coordpriv.legacy.{uuid.uuid4().hex[:6]}@example.com"
    legacy_doc = {
        "nombre": "QA Legacy Coordinator",
        "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": "lider",
        "access_level": "coordinador_general",
        "person_id": person_id,
        "is_active": True,
        "token_version": 1,
        "capabilities": ["care.assigned.read", "custom.marker.capability.qa"],
        "privilege_groups": ["membership"],
        "access_scope": {"persons": "all"},
        "created_at": datetime.now(timezone.utc),
    }
    await server.db.users.insert_one(legacy_doc)
    try:
        await ensure_access_defaults(server.db)
        updated = await server.db.users.find_one({"email": email}, {"_id": 0, "capabilities": 1})
        caps = set(updated["capabilities"])
        assert "mentorship.badge.manage" in caps
        assert "mentorship.outreach.assign" in caps
        assert "consolidation.mentor.transfer" in caps
        assert "custom.marker.capability.qa" in caps, "la migracion no debe pisar capacidades existentes"
        assert "care.assigned.read" in caps
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_lider_promoted_via_core_access_manage_also_receives_capabilities():
    """El alias legado (lider + CORE_ACCESS_MANAGE == coordinador_general, ver
    resolved_access_level) tambien debe recibir las 3 capacidades nuevas."""
    await cleanup()
    person_id = await create_person("Legacy Lider CoreAccess")
    email = f"qa.coordpriv.legacylider.{uuid.uuid4().hex[:6]}@example.com"
    legacy_doc = {
        "nombre": "QA Legacy Lider CoreAccess",
        "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": "lider",
        "person_id": person_id,
        "is_active": True,
        "token_version": 1,
        "capabilities": [CORE_ACCESS_MANAGE, "custom.marker.lider.qa"],
        "privilege_groups": [],
        "access_scope": {"persons": "created_by"},
        "created_at": datetime.now(timezone.utc),
    }
    await server.db.users.insert_one(legacy_doc)
    try:
        await ensure_access_defaults(server.db)
        updated = await server.db.users.find_one({"email": email}, {"_id": 0, "capabilities": 1})
        caps = set(updated["capabilities"])
        assert "mentorship.badge.manage" in caps
        assert "mentorship.outreach.assign" in caps
        assert "consolidation.mentor.transfer" in caps
        assert "custom.marker.lider.qa" in caps
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_coordinator_general_can_manage_mentors_campaigns_and_assign_to_any_mentor():
    await cleanup()
    coord_email, _ = await create_coordinator_general_user("Active Coordinator")
    target_pid = await create_person("Mentor Target")
    coord_client, coord_headers = await auth_client(coord_email)
    try:
        badge = await coord_client.put(
            f"/api/mentorship/badge/{target_pid}", json={"active": True, "note": "Otorgado por coordinador"}, headers=coord_headers,
        )
        assert badge.status_code == 200, badge.text

        campaign = await coord_client.post("/api/mentorship/outreach/campaigns", json={"name": "Invasion QA Coordinador", "location": "Zona QA Coordinador", "start_date": "2026-03-01"}, headers=coord_headers)
        assert campaign.status_code == 201, campaign.text

        visit = await coord_client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Visitante Asignado", "mentor_person_id": target_pid},
            headers=coord_headers,
        )
        assert visit.status_code == 201, visit.text
        assert visit.json()["mentor_person_id"] == target_pid

        dashboard = await coord_client.get("/api/mentorship/outreach/dashboard", headers=coord_headers)
        assert dashboard.status_code == 200
        assert dashboard.json()["totals"]["total"] == 1
    finally:
        await coord_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_coordinator_general_cannot_access_pastor_only_actions():
    await cleanup()
    coord_email, _ = await create_coordinator_general_user("Scoped Coordinator")
    coord_client, coord_headers = await auth_client(coord_email)
    try:
        listing = await coord_client.get("/api/pastor/pastors", headers=coord_headers)
        assert listing.status_code == 403

        other_pastor_id = str(ObjectId())
        reset = await coord_client.post(
            f"/api/pastor/pastors/{other_pastor_id}/reset-password", json={"password": "DoesNotMatter123!"}, headers=coord_headers,
        )
        assert reset.status_code == 403
    finally:
        await coord_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_coordinator_general_sees_mentors_without_account_in_list():
    """A pedido del dueño: el coordinador general debe ver en /api/mentorship/mentors
    a TODOS los que tengan insignia activa, incluso sin cuenta (has_account=False),
    confirmando también que tiene permiso para llamar a este endpoint."""
    await cleanup()
    coord_email, _ = await create_coordinator_general_user("Mentors Visibility Coordinator")
    mentor_without_account_pid = await create_person("Mentor Sin Acceso Visible Coordinador")
    coord_client, coord_headers = await auth_client(coord_email)
    try:
        badge = await coord_client.put(
            f"/api/mentorship/badge/{mentor_without_account_pid}", json={"active": True}, headers=coord_headers,
        )
        assert badge.status_code == 200, badge.text

        listing = await coord_client.get("/api/mentorship/mentors", headers=coord_headers)
        assert listing.status_code == 200, listing.text
        items = {item["person_id"]: item for item in listing.json()["items"]}
        assert mentor_without_account_pid in items, "regla del dueño: toda insignia activa debe listarse"
        assert items[mentor_without_account_pid]["has_account"] is False
        assert items[mentor_without_account_pid]["account_active"] is False
    finally:
        await coord_client.aclose()
        await cleanup()
