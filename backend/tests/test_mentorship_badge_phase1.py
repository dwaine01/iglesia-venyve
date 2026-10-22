"""Fase 1 — Insignia de Mentor + calificación LBS (mentorship.py).

Cubre:
- Alternar la insignia de Mentor y su historial (quién/cuándo).
- Reutilizar `mentor_qualifications` (front_group_id=None = todos los grupos)
  para la capacitación LBS, vía el nuevo capability `mentorship.badge.manage`.
- Permisos: 403 sin capability, 200 con capability otorgada (incluida la
  validación de gobernanza que antes rechazaba capabilities nuevas).
- Listado de mentores activos (insignia + cuenta activa) para los selectores
  de Consolidación, con teléfono condicionado a `person.contacts.read`.
- `assign_mentor` ahora acepta un mentor nivel "persona" con insignia activa,
  sin romper la ruta pastor/líder existente.
"""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "MentorBadgePass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA",
        "apellido": label,
        "idempotency_key": f"qa:mentorbadge:{uuid.uuid4()}",
        "version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None) -> tuple[str, str]:
    user_id = ObjectId()
    slug = label.lower().replace(" ", ".")
    email = f"qa.mentorbadge.{slug}.{uuid.uuid4().hex[:6]}@example.com"
    defaults = access_defaults_for_role(role)
    defaults["capabilities"] = sorted(set(defaults.get("capabilities", []) + (capabilities or [])))
    document = {
        "_id": user_id,
        "nombre": f"QA {label}",
        "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role,
        "is_active": True,
        "token_version": 1,
        "created_at": datetime.now(timezone.utc),
        **defaults,
    }
    if person_id:
        document["person_id"] = person_id
    await server.db.users.insert_one(document)
    return str(user_id), email


async def auth_client(email: str) -> tuple[AsyncClient, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


@pytest.mark.asyncio
async def test_pastor_can_toggle_mentor_badge_with_history_and_profile_header():
    await cleanup()
    target_person_id = await create_person("Target Mentor Badge")
    _, pastor_email = await create_user("Badge Pastor", "pastor")
    client, headers = await auth_client(pastor_email)
    try:
        activate = await client.put(
            f"/api/mentorship/badge/{target_person_id}",
            json={"active": True, "since": "2026-02-01", "note": "Mentor zona norte"},
            headers=headers,
        )
        assert activate.status_code == 200, activate.text
        assert activate.json()["active"] is True

        detail = await client.get(f"/api/mentorship/badge/{target_person_id}", headers=headers)
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["active"] is True
        assert payload["since"] == "2026-02-01"
        assert payload["can_manage"] is True
        assert len(payload["history"]) == 1
        assert payload["history"][0]["action"] == "mentor_badge_activated"

        profile = await client.get(f"/api/core/persons/{target_person_id}/profile", headers=headers)
        assert profile.status_code == 200
        header = profile.json()["header"]
        assert header["mentor_badge"]["active"] is True
        assert header["mentor_badge_can_manage"] is True

        deactivate = await client.put(
            f"/api/mentorship/badge/{target_person_id}",
            json={"active": False, "note": "Ya no participa en invasiones"},
            headers=headers,
        )
        assert deactivate.status_code == 200
        assert deactivate.json()["active"] is False

        detail_after = await client.get(f"/api/mentorship/badge/{target_person_id}", headers=headers)
        assert len(detail_after.json()["history"]) == 2
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_lbs_toggle_reuses_mentor_qualifications_for_all_groups():
    await cleanup()
    target_person_id = await create_person("Target LBS Global")
    _, pastor_email = await create_user("LBS Pastor", "pastor")
    client, headers = await auth_client(pastor_email)
    try:
        response = await client.put(
            f"/api/mentorship/lbs/{target_person_id}",
            json={"can_teach_lbs": True, "note": "Capacitado 2025"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["front_group_id"] is None
        assert response.json()["can_teach_lbs"] is True

        from consolidation_service import mentor_qualification
        qualified_for_any_group = await mentor_qualification(server.db, target_person_id, "some-other-front-group-id")
        assert qualified_for_any_group is not None

        badge_detail = await client.get(f"/api/mentorship/badge/{target_person_id}", headers=headers)
        assert badge_detail.json()["lbs_qualified"] is True
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_persona_without_capability_gets_403():
    await cleanup()
    target_person_id = await create_person("Target 403")
    persona_person_id = await create_person("Persona Sin Capability")
    _, persona_email = await create_user("Persona Sin Capability", "persona", persona_person_id)
    client, headers = await auth_client(persona_email)
    try:
        response = await client.put(f"/api/mentorship/badge/{target_person_id}", json={"active": True}, headers=headers)
        assert response.status_code == 403
        response_lbs = await client.put(f"/api/mentorship/lbs/{target_person_id}", json={"can_teach_lbs": True}, headers=headers)
        assert response_lbs.status_code == 403
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_persona_with_granted_capability_can_manage_badge():
    await cleanup()
    target_person_id = await create_person("Target Granted")
    persona_person_id = await create_person("Persona Con Capability")
    _, persona_email = await create_user("Persona Con Capability", "persona", persona_person_id, capabilities=["mentorship.badge.manage"])
    client, headers = await auth_client(persona_email)
    try:
        response = await client.put(
            f"/api/mentorship/badge/{target_person_id}",
            json={"active": True, "since": "2026-02-10"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["active"] is True
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_governance_accepts_mentorship_badge_manage_capability():
    await cleanup()
    member_person_id = await create_person("Governance Target")
    member_user_id, _ = await create_user("Governance Target", "persona", member_person_id)
    _, pastor_email = await create_user("Governance Pastor", "pastor")
    client, headers = await auth_client(pastor_email)
    try:
        existing = await server.db.users.find_one({"_id": ObjectId(member_user_id)}, {"capabilities": 1})
        new_caps = sorted(set(existing.get("capabilities", []) + ["mentorship.badge.manage"]))
        response = await client.put(
            f"/api/core/governance/users/{member_user_id}/access",
            json={"access_level": "persona", "privilege_groups": [], "capabilities": new_caps, "is_active": True},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert "mentorship.badge.manage" in response.json()["capabilities"]
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_mentors_list_shows_all_active_badges_with_account_flags_and_hides_phone_without_capability():
    await cleanup()
    mentor_with_account_pid = await create_person("Mentor Con Cuenta")
    _, mentor_email = await create_user("Mentor Con Cuenta", "persona", mentor_with_account_pid)
    mentor_without_account_pid = await create_person("Mentor Sin Cuenta")
    _, pastor_email = await create_user("Mentors List Pastor", "pastor")
    client, headers = await auth_client(pastor_email)
    try:
        for pid in (mentor_with_account_pid, mentor_without_account_pid):
            activate = await client.put(f"/api/mentorship/badge/{pid}", json={"active": True}, headers=headers)
            assert activate.status_code == 200

        await server.db.person_contacts.insert_one({
            "_id": str(uuid.uuid4()), "person_id": mentor_with_account_pid, "tipo": "telefono",
            "valor": "809-555-0100", "es_principal": True, "created_at": datetime.now(timezone.utc),
        })

        listing = await client.get("/api/mentorship/mentors", headers=headers)
        assert listing.status_code == 200
        items = {item["person_id"]: item for item in listing.json()["items"]}
        assert mentor_with_account_pid in items, "mentor con insignia y cuenta activa debe aparecer"
        assert mentor_without_account_pid in items, "mentor con insignia pero SIN cuenta también debe aparecer (regla del dueño)"
        assert items[mentor_with_account_pid]["has_account"] is True
        assert items[mentor_with_account_pid]["account_active"] is True
        assert items[mentor_without_account_pid]["has_account"] is False
        assert items[mentor_without_account_pid]["account_active"] is False
        assert items[mentor_with_account_pid]["phone"] == "809-555-0100", "pastor tiene person.contacts.read"

        limited_person_id = await create_person("Limited Viewer")
        _, limited_email = await create_user("Limited Viewer", "persona", limited_person_id, capabilities=["processes.read"])
        # El rol "persona" otorga person.contacts.read por defecto (autoservicio);
        # se sobreescribe para simular un operador sin ese permiso explícito.
        await server.db.users.update_one({"email": limited_email}, {"$set": {"capabilities": ["processes.read"]}})
        limited_client, limited_headers = await auth_client(limited_email)
        try:
            limited_listing = await limited_client.get("/api/mentorship/mentors", headers=limited_headers)
            assert limited_listing.status_code == 200
            limited_items = {item["person_id"]: item for item in limited_listing.json()["items"]}
            assert limited_items[mentor_with_account_pid]["phone"] is None, "sin person.contacts.read no debe ver el teléfono"
        finally:
            await limited_client.aclose()
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_assign_mentor_accepts_persona_account_with_active_badge():
    await cleanup()
    candidate_person_id = await create_person("Candidato Badge Mentor")
    mentor_person_id = await create_person("Mentor Persona Badge")
    _, mentor_user_email = await create_user("Mentor Persona Badge", "persona", mentor_person_id)
    _, pastor_email = await create_user("Assign Pastor", "pastor")
    client, headers = await auth_client(pastor_email)
    try:
        activate = await client.put(f"/api/mentorship/badge/{mentor_person_id}", json={"active": True}, headers=headers)
        assert activate.status_code == 200

        intake = await client.post(
            "/api/processes/consolidation/intakes",
            json={"person_id": candidate_person_id, "entry_mode": "direct_church", "mentor_person_id": mentor_person_id},
            headers=headers,
        )
        assert intake.status_code == 201, intake.text
        assert intake.json()["mentor_person_id"] == mentor_person_id
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_assign_mentor_rejects_persona_account_without_badge():
    await cleanup()
    candidate_person_id = await create_person("Candidato Sin Badge")
    mentor_person_id = await create_person("Mentor Persona Sin Badge")
    await create_user("Mentor Persona Sin Badge", "persona", mentor_person_id)
    _, pastor_email = await create_user("Assign Reject Pastor", "pastor")
    client, headers = await auth_client(pastor_email)
    try:
        intake = await client.post(
            "/api/processes/consolidation/intakes",
            json={"person_id": candidate_person_id, "entry_mode": "direct_church", "mentor_person_id": mentor_person_id},
            headers=headers,
        )
        assert intake.status_code == 409
        assert "insignia de Mentor" in intake.json()["detail"]
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_mentors_list_shows_deactivated_account_as_inactive_not_hidden():
    await cleanup()
    mentor_person_id = await create_person("Mentor Cuenta Desactivada")
    _, mentor_email = await create_user("Mentor Cuenta Desactivada", "persona", mentor_person_id)
    await server.db.users.update_one({"email": mentor_email}, {"$set": {"is_active": False}})
    _, pastor_email = await create_user("Deactivated Mentors Pastor", "pastor")
    client, headers = await auth_client(pastor_email)
    try:
        activate = await client.put(f"/api/mentorship/badge/{mentor_person_id}", json={"active": True}, headers=headers)
        assert activate.status_code == 200

        listing = await client.get("/api/mentorship/mentors", headers=headers)
        assert listing.status_code == 200
        items = {item["person_id"]: item for item in listing.json()["items"]}
        assert mentor_person_id in items, "mentor con insignia debe aparecer aunque su cuenta esté desactivada"
        assert items[mentor_person_id]["has_account"] is True
        assert items[mentor_person_id]["account_active"] is False
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_assign_mentor_without_account_blocks_with_clear_access_message():
    """El mensaje 409 debe decir claramente que falta crear el acceso del mentor,
    no un genérico 'cuenta activa'. assert_mentor_eligible sigue exigiendo cuenta
    activa (no se relaja), sólo se mejora el texto del error."""
    await cleanup()
    candidate_person_id = await create_person("Candidato Sin Acceso Mentor")
    mentor_person_id = await create_person("Mentor Con Insignia Sin Cuenta")
    _, pastor_email = await create_user("Assign No Account Pastor", "pastor")
    client, headers = await auth_client(pastor_email)
    try:
        activate = await client.put(f"/api/mentorship/badge/{mentor_person_id}", json={"active": True}, headers=headers)
        assert activate.status_code == 200

        intake = await client.post(
            "/api/processes/consolidation/intakes",
            json={"person_id": candidate_person_id, "entry_mode": "direct_church", "mentor_person_id": mentor_person_id},
            headers=headers,
        )
        assert intake.status_code == 409, intake.text
        detail = intake.json()["detail"].lower()
        assert "acceso" in detail and "mentor" in detail, detail
    finally:
        await client.aclose()
        await cleanup()

