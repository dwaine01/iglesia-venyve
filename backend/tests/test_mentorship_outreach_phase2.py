"""Fase 2 — Visitas / Invasiones con informe por persona (mentorship_outreach.py).

Cubre:
- Un mentor con insignia activa solo ve y edita SUS PROPIAS visitas, nunca las
  de otro mentor (incluso intentando filtrar por `mentor_person_id` ajeno).
- La transferencia de una visita solo acepta mentores con insignia activa Y
  capacitación LBS (`mentor_qualifications.can_teach_lbs`); rechaza mentores
  sin insignia o sin LBS.
- Deduplicación por teléfono: una segunda visita de "contacto nuevo" con el
  mismo teléfono es rechazada (409) mencionando al mentor responsable actual.
- Conversión a la Ley de las 7 Semanas: solo desde estado `wants_followup`,
  crea Persona 360 (si el contacto era nuevo) + `process_enrollments` con
  `entry_mode=visitor_followup` y mentor responsable; bloquea doble conversión.
- Permisos: un nivel "persona" sin ninguna capability pero con insignia activa
  puede usar el módulo (self-service); sin insignia ni capability, 403. Solo
  `mentorship.outreach.assign` (o autoridad pastoral) puede crear campañas,
  asignar a otro mentor y ver el panel de líderes/dashboard.
- La búsqueda de personas para outreach (`/person-search`) solo expone
  nombre y person_id (no datos sensibles) y no requiere `person.directory.search`.
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

PASSWORD = "OutreachPhase2Pass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA",
        "apellido": label,
        "idempotency_key": f"qa:outreach:{uuid.uuid4()}",
        "version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None) -> tuple[str, str]:
    user_id = ObjectId()
    slug = label.lower().replace(" ", ".")
    email = f"qa.outreach.{slug}.{uuid.uuid4().hex[:6]}@example.com"
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


async def activate_badge(pid: str) -> None:
    await server.db.mentor_badges.update_one(
        {"person_id": pid},
        {"$set": {"person_id": pid, "active": True, "since": "2026-01-01", "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def grant_lbs(pid: str) -> None:
    await server.db.mentor_qualifications.update_one(
        {"person_id": pid, "front_group_id": None},
        {"$set": {"person_id": pid, "front_group_id": None, "active": True, "can_teach_lbs": True, "archived": False}},
        upsert=True,
    )


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


@pytest.mark.asyncio
async def test_mentor_cannot_see_or_edit_other_mentor_visits():
    await cleanup()
    mentor_a_pid = await create_person("Mentor A")
    mentor_b_pid = await create_person("Mentor B")
    await activate_badge(mentor_a_pid)
    await activate_badge(mentor_b_pid)
    _, mentor_a_email = await create_user("Mentor A", "persona", mentor_a_pid)
    _, mentor_b_email = await create_user("Mentor B", "persona", mentor_b_pid)
    client_a, headers_a = await auth_client(mentor_a_email)
    client_b, headers_b = await auth_client(mentor_b_email)
    try:
        created = await client_a.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Visitante A", "contact_phone": "3000000001"},
            headers=headers_a,
        )
        assert created.status_code == 201, created.text
        visit_id = created.json()["visit_id"]

        listing_b = await client_b.get("/api/mentorship/outreach/visits", headers=headers_b)
        assert listing_b.status_code == 200
        assert listing_b.json()["items"] == [], "el mentor B no debe ver visitas del mentor A"

        filtered_b = await client_b.get(f"/api/mentorship/outreach/visits?mentor_person_id={mentor_a_pid}", headers=headers_b)
        assert filtered_b.json()["items"] == [], "filtrar por otro mentor no debe exponer sus visitas a un no-líder"

        get_b = await client_b.get(f"/api/mentorship/outreach/visits/{visit_id}", headers=headers_b)
        assert get_b.status_code == 403

        report_b = await client_b.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "visited"}, headers=headers_b)
        assert report_b.status_code == 403
    finally:
        await client_a.aclose()
        await client_b.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_transfer_requires_active_badge_and_lbs_qualification():
    await cleanup()
    mentor_pid = await create_person("Mentor Transfer Origin")
    unqualified_pid = await create_person("Mentor Sin LBS")
    no_badge_pid = await create_person("Mentor Sin Insignia")
    qualified_pid = await create_person("Mentor Con LBS")
    await activate_badge(mentor_pid)
    await activate_badge(unqualified_pid)
    await activate_badge(qualified_pid)
    await grant_lbs(qualified_pid)
    _, mentor_email = await create_user("Mentor Transfer Origin", "persona", mentor_pid)
    client, headers = await auth_client(mentor_email)
    try:
        created = await client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Visitante Transfer", "contact_phone": "3000000002"},
            headers=headers,
        )
        visit_id = created.json()["visit_id"]

        reject_no_badge = await client.post(
            f"/api/mentorship/outreach/visits/{visit_id}/transfer",
            json={"new_mentor_person_id": no_badge_pid}, headers=headers,
        )
        assert reject_no_badge.status_code == 409

        reject_no_lbs = await client.post(
            f"/api/mentorship/outreach/visits/{visit_id}/transfer",
            json={"new_mentor_person_id": unqualified_pid}, headers=headers,
        )
        assert reject_no_lbs.status_code == 409

        accept = await client.post(
            f"/api/mentorship/outreach/visits/{visit_id}/transfer",
            json={"new_mentor_person_id": qualified_pid, "reason": "Necesita LBS"}, headers=headers,
        )
        assert accept.status_code == 200, accept.text
        assert accept.json()["mentor_person_id"] == qualified_pid

        gone = await client.get(f"/api/mentorship/outreach/visits/{visit_id}", headers=headers)
        assert gone.status_code == 403, "el mentor original ya no debe poder consultar la visita transferida"
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_duplicate_phone_is_rejected():
    await cleanup()
    mentor_pid = await create_person("Mentor Dedup")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Dedup", "persona", mentor_pid)
    client, headers = await auth_client(mentor_email)
    try:
        first = await client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Visitante Uno", "contact_phone": "3000000003"},
            headers=headers,
        )
        assert first.status_code == 201

        duplicate = await client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Visitante Dos", "contact_phone": "300-000-0003"},
            headers=headers,
        )
        assert duplicate.status_code == 409
        assert "teléfono" in duplicate.json()["detail"]

        duplicate_country_code = await client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Visitante Tres", "contact_phone": "+58 300-000-0003"},
            headers=headers,
        )
        assert duplicate_country_code.status_code == 409, "un prefijo de pais no debe evadir la deduplicacion"
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_duplicate_existing_person_visit_is_rejected():
    await cleanup()
    mentor_pid = await create_person("Mentor Existing Dedup")
    other_pid = await create_person("Other Mentor Existing Dedup")
    target_pid = await create_person("Visitado 360")
    await activate_badge(mentor_pid)
    await activate_badge(other_pid)
    _, mentor_email = await create_user("Mentor Existing Dedup", "persona", mentor_pid)
    _, other_email = await create_user("Other Mentor Existing Dedup", "persona", other_pid)
    client, headers = await auth_client(mentor_email)
    other_client, other_headers = await auth_client(other_email)
    try:
        first = await client.post(
            "/api/mentorship/outreach/visits", json={"contact_type": "existing", "person_id": target_pid}, headers=headers,
        )
        assert first.status_code == 201

        duplicate = await other_client.post(
            "/api/mentorship/outreach/visits", json={"contact_type": "existing", "person_id": target_pid}, headers=other_headers,
        )
        assert duplicate.status_code == 409
    finally:
        await client.aclose()
        await other_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_start_seven_weeks_creates_enrollment_and_blocks_double_conversion():
    await cleanup()
    mentor_pid = await create_person("Mentor SevenWeeks")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor SevenWeeks", "persona", mentor_pid)
    client, headers = await auth_client(mentor_email)
    try:
        created = await client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Visitante SieteSemanas", "contact_phone": "3000000004"},
            headers=headers,
        )
        visit_id = created.json()["visit_id"]

        blocked_status = await client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=headers)
        assert blocked_status.status_code == 409, "no debe poder iniciar sin estado wants_followup"

        report = await client.put(
            f"/api/mentorship/outreach/visits/{visit_id}/report",
            json={"status": "wants_followup", "lbs_decision": "accepted"}, headers=headers,
        )
        assert report.status_code == 200

        started = await client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=headers)
        assert started.status_code == 200, started.text
        body = started.json()
        assert body["person_created"] is True
        enrollment_id = body["enrollment_id"]

        enrollment = await server.db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
        # S1 (oración) y S2 (invasión) ya se vivieron con la campaña -> entry_mode "invasion",
        # abre listo en MCD (ver aclaración del dueño sobre semanas del catálogo).
        assert enrollment["entry_mode"] == "invasion"
        assert enrollment["current_stage_key"] == "mcd"
        assert enrollment["mentor_person_id"] == mentor_pid
        assert enrollment["source"] == "mentorship_outreach"

        again = await client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=headers)
        assert again.status_code == 409, "no debe convertir dos veces la misma visita"

        blocked_status_change = await client.put(
            f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "rejected"}, headers=headers,
        )
        assert blocked_status_change.status_code == 409, "no debe poder cambiar el estado luego de iniciar 7 Semanas"
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_seven_weeks_does_not_fuzzy_merge_into_unrelated_person_with_similar_name():
    await cleanup()
    mentor_pid = await create_person("Mentor NoFuzzy")
    await activate_badge(mentor_pid)
    unrelated_person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": unrelated_person_id, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "Juan", "apellido": "Perez Gomez", "search_key": "juan perez gomez",
        "idempotency_key": f"qa:outreach:{uuid.uuid4()}", "version": 1,
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    _, mentor_email = await create_user("Mentor NoFuzzy", "persona", mentor_pid)
    client, headers = await auth_client(mentor_email)
    try:
        created = await client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Juan Perez"}, headers=headers,
        )
        visit_id = created.json()["visit_id"]
        await client.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "wants_followup"}, headers=headers)
        started = await client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=headers)
        assert started.status_code == 200, started.text
        assert started.json()["person_created"] is True, "no debe fusionarse con 'Juan Perez Gomez' por coincidencia parcial"
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_create_visit_requires_mentor_to_have_active_badge():
    await cleanup()
    leader_pid = await create_person("Leader No Badge")
    no_badge_pid = await create_person("Target Mentor No Badge")
    _, leader_email = await create_user("Leader No Badge", "lider", leader_pid, capabilities=["mentorship.outreach.assign"])
    client, headers = await auth_client(leader_email)
    try:
        response = await client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Sin Mentor Valido", "mentor_person_id": no_badge_pid},
            headers=headers,
        )
        assert response.status_code == 409
        assert "insignia" in response.json()["detail"]
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_persona_without_badge_or_capability_gets_403():
    await cleanup()
    persona_pid = await create_person("Persona Sin Insignia")
    _, persona_email = await create_user("Persona Sin Insignia", "persona", persona_pid)
    client, headers = await auth_client(persona_email)
    try:
        response = await client.get("/api/mentorship/outreach/visits", headers=headers)
        assert response.status_code == 403
        create = await client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Intento Sin Permiso"}, headers=headers,
        )
        assert create.status_code == 403
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_only_leader_capability_can_create_campaigns_assign_others_and_view_dashboard():
    await cleanup()
    mentor_pid = await create_person("Mentor Under Leader")
    leader_pid = await create_person("Leader Outreach")
    await activate_badge(mentor_pid)
    await activate_badge(leader_pid)
    _, mentor_email = await create_user("Mentor Under Leader", "persona", mentor_pid)
    _, leader_email = await create_user("Leader Outreach", "lider", leader_pid, capabilities=["mentorship.outreach.assign"])
    _, pastor_email = await create_user("Pastor Campaign Owner", "pastor")
    mentor_client, mentor_headers = await auth_client(mentor_email)
    leader_client, leader_headers = await auth_client(leader_email)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    campaign_payload = {"name": "Invasion Autorizada", "location": "Barrio Las Flores", "start_date": "2026-03-01", "end_date": "2026-03-07"}
    try:
        rejected_campaign = await mentor_client.post("/api/mentorship/outreach/campaigns", json=campaign_payload, headers=mentor_headers)
        assert rejected_campaign.status_code == 403

        rejected_assign = await mentor_client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Asignado a otro", "mentor_person_id": leader_pid}, headers=mentor_headers,
        )
        assert rejected_assign.status_code == 403

        rejected_dashboard = await mentor_client.get("/api/mentorship/outreach/dashboard", headers=mentor_headers)
        assert rejected_dashboard.status_code == 403

        # Un líder con mentorship.outreach.assign puede asignar visitas, pero YA NO puede
        # crear la invasión (eso quedó reservado a pastora/pastor y coordinador general).
        rejected_leader_campaign = await leader_client.post("/api/mentorship/outreach/campaigns", json=campaign_payload, headers=leader_headers)
        assert rejected_leader_campaign.status_code == 403

        campaign = await pastor_client.post("/api/mentorship/outreach/campaigns", json=campaign_payload, headers=pastor_headers)
        assert campaign.status_code == 201, campaign.text
        assert campaign.json()["location"] == "Barrio Las Flores"

        assign_to_mentor = await leader_client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Asignado por lider", "mentor_person_id": mentor_pid, "campaign_id": campaign.json()["campaign_id"]},
            headers=leader_headers,
        )
        assert assign_to_mentor.status_code == 201
        assert assign_to_mentor.json()["mentor_person_id"] == mentor_pid

        dashboard = await leader_client.get("/api/mentorship/outreach/dashboard", headers=leader_headers)
        assert dashboard.status_code == 200
        assert dashboard.json()["totals"]["total"] == 1
    finally:
        await mentor_client.aclose()
        await leader_client.aclose()
        await pastor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_person_search_exposes_only_name_and_id():
    await cleanup()
    mentor_pid = await create_person("Mentor Search")
    findable_pid = await create_person("Buscable Fase2")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Search", "persona", mentor_pid)
    client, headers = await auth_client(mentor_email)
    try:
        response = await client.get("/api/mentorship/outreach/person-search?q=Buscable", headers=headers)
        assert response.status_code == 200
        items = response.json()["items"]
        assert any(item["person_id"] == findable_pid for item in items)
        for item in items:
            assert set(item.keys()) == {"person_id", "name"}
    finally:
        await client.aclose()
        await cleanup()
