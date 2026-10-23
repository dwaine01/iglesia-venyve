"""Agregar/quitar mentores de una invasión YA CREADA sin reemplazar el roster
(pedido del dueño, prioridad sobre Etapa 4). Cubre:
- POST .../mentors agrega (persona explícita e invitación sin contraseña).
- Idempotente: repetir la misma llamada no duplica ni falla.
- Mentor sin insignia activa es rechazado (409).
- Rol no autorizado recibe 403.
- Quitar bloqueado si tiene visitas/hogares/libros en custodia; informa cuáles.
- Quitar funciona y queda auditado cuando no hay nada pendiente.
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

PASSWORD = "AddMentorsEtapa4Pass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA", "apellido": label, "idempotency_key": f"qa:add-mentors:{uuid.uuid4()}",
        "version": 1, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str) -> tuple:
    user_id = ObjectId()
    email = f"qa.addmentors.{label.lower().replace(' ', '.')}.{uuid.uuid4().hex[:6]}@example.com"
    defaults = access_defaults_for_role(role)
    await server.db.users.insert_one({
        "_id": user_id, "nombre": f"QA {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "person_id": person_id, "is_active": True, "token_version": 1,
        "created_at": datetime.now(timezone.utc), **defaults,
    })
    return str(user_id), email


async def give_badge(person_id: str) -> None:
    await server.db.mentor_badges.update_one({"person_id": person_id}, {"$set": {"person_id": person_id, "active": True, "created_at": datetime.now(timezone.utc)}}, upsert=True)


async def auth_client(email: str) -> tuple:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


@pytest.mark.asyncio
async def test_add_mentor_explicit_is_additive_and_idempotent():
    await cleanup()
    pastor_pid = await create_person("Pastor Add")
    mentor_pid = await create_person("Mentor Add")
    _, pastor_email = await create_user("Pastor Add", "pastor", pastor_pid)
    _, mentor_email = await create_user("Mentor Add", "persona", mentor_pid)
    await give_badge(mentor_pid)
    client, headers = await auth_client(pastor_email)
    try:
        campaign = await client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasión Add Mentors", "location": "Sector", "start_date": "2026-11-01", "end_date": "2026-11-02", "assigned_mentors": []},
            headers=headers,
        )
        assert campaign.status_code == 201, campaign.text
        campaign_id = campaign.json()["campaign_id"]

        first = await client.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors", json={"person_ids": [mentor_pid]}, headers=headers)
        assert first.status_code == 200, first.text
        assert first.json()["added"] == [mentor_pid]

        after_first = await client.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/delete-preview", headers=headers)
        assert after_first.json()["participations"] == 1

        second = await client.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors", json={"person_ids": [mentor_pid]}, headers=headers)
        assert second.status_code == 200
        assert second.json()["added"] == [] and second.json()["already_assigned"] == [mentor_pid], "repetir no debe duplicar ni fallar"

        participation = await server.db.outreach_participations.count_documents({"campaign_id": campaign_id, "mentor_person_id": mentor_pid})
        assert participation == 1, "no debe haber participaciones duplicadas"

        detail = await client.get("/api/mentorship/outreach/campaigns", headers=headers)
        found = next(item for item in detail.json()["items"] if item["campaign_id"] == campaign_id)
        assert mentor_pid in found["assigned_mentor_ids"]
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_add_mentor_without_account_invites_without_password():
    await cleanup()
    pastor_pid = await create_person("Pastor Invite")
    mentor_pid = await create_person("Mentor SinCuenta")
    _, pastor_email = await create_user("Pastor Invite", "pastor", pastor_pid)
    await give_badge(mentor_pid)
    client, headers = await auth_client(pastor_email)
    try:
        campaign = await client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasión Invite", "location": "Sector", "start_date": "2026-11-01", "end_date": "2026-11-02", "assigned_mentors": []},
            headers=headers,
        )
        campaign_id = campaign.json()["campaign_id"]
        new_email = f"qa.addmentors.invited.{uuid.uuid4().hex[:6]}@example.com"

        missing_email = await client.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors", json={"person_ids": [mentor_pid]}, headers=headers)
        assert missing_email.status_code == 200
        assert missing_email.json()["rejected"][0]["person_id"] == mentor_pid, "sin cuenta y sin correo debe quedar en 'rejected', no fallar todo"

        added = await client.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors", json={"person_ids": [mentor_pid], "emails": {mentor_pid: new_email}}, headers=headers)
        assert added.status_code == 200, added.text
        assert added.json()["added"] == [mentor_pid]
        assert added.json()["accounts_created"][0]["email"] == new_email

        user_doc = await server.db.users.find_one({"email": new_email}, {"password": 1})
        assert user_doc is not None, "debe haberse creado la cuenta"
        login_attempt = await client.post("/api/auth/login", json={"email": new_email, "password": ""})
        assert login_attempt.status_code in (401, 422), "no se definió contraseña manual: el flujo es por invitación, no por clave en el request"
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_add_mentor_without_badge_rejected_and_unauthorized_role_forbidden():
    await cleanup()
    pastor_pid = await create_person("Pastor NoBadge")
    leader_pid = await create_person("Lider NoAuth")
    no_badge_pid = await create_person("SinInsignia")
    _, pastor_email = await create_user("Pastor NoBadge", "pastor", pastor_pid)
    _, leader_email = await create_user("Lider NoAuth", "lider", leader_pid)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    leader_client, leader_headers = await auth_client(leader_email)
    try:
        campaign = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasión NoBadge", "location": "Sector", "start_date": "2026-11-01", "end_date": "2026-11-02", "assigned_mentors": []},
            headers=pastor_headers,
        )
        campaign_id = campaign.json()["campaign_id"]

        rejected = await pastor_client.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors", json={"person_ids": [no_badge_pid]}, headers=pastor_headers)
        assert rejected.status_code == 409
        assert "insignia" in rejected.json()["detail"].lower()

        forbidden = await leader_client.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors", json={"person_ids": [no_badge_pid]}, headers=leader_headers)
        assert forbidden.status_code == 403
    finally:
        await pastor_client.aclose(); await leader_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_remove_mentor_blocked_with_activity_then_allowed_and_audited():
    await cleanup()
    pastor_pid = await create_person("Pastor Remove")
    mentor_pid = await create_person("Mentor Remove")
    _, pastor_email = await create_user("Pastor Remove", "pastor", pastor_pid)
    _, mentor_email = await create_user("Mentor Remove", "persona", mentor_pid)
    await give_badge(mentor_pid)
    client, headers = await auth_client(pastor_email)
    try:
        campaign = await client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasión Remove", "location": "Sector", "start_date": "2026-11-01", "end_date": "2026-11-02", "assigned_mentors": []},
            headers=headers,
        )
        campaign_id = campaign.json()["campaign_id"]
        add = await client.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors", json={"person_ids": [mentor_pid]}, headers=headers)
        assert add.status_code == 200

        household_id = str(uuid.uuid4())
        await server.db.outreach_households.insert_one({
            "_id": household_id, "household_id": household_id, "campaign_id": campaign_id, "mentor_person_id": mentor_pid,
            "address_line1": "Calle Falsa 123", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        })

        preview = await client.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors/{mentor_pid}/remove-preview", headers=headers)
        assert preview.status_code == 200
        assert preview.json()["blocked"] is True
        assert preview.json()["households"] == 1

        blocked = await client.request("DELETE", f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors/{mentor_pid}", json={"reason": "prueba bloqueo"}, headers=headers)
        assert blocked.status_code == 409
        assert "hogar" in blocked.json()["detail"].lower()

        await server.db.outreach_households.delete_one({"_id": household_id})
        removed = await client.request("DELETE", f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors/{mentor_pid}", json={"reason": "prueba quitar ok"}, headers=headers)
        assert removed.status_code == 200, removed.text

        still_there = await server.db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "assigned_mentor_ids": 1})
        assert mentor_pid not in still_there["assigned_mentor_ids"]
        participation_gone = await server.db.outreach_participations.count_documents({"campaign_id": campaign_id, "mentor_person_id": mentor_pid})
        assert participation_gone == 0

        audit = await server.db.admin_deletions.find_one({"collection": "outreach_campaign_mentors", "target_id": f"{campaign_id}:{mentor_pid}"})
        assert audit is not None and audit["reason"] == "prueba quitar ok"
    finally:
        await client.aclose()
        await cleanup()
