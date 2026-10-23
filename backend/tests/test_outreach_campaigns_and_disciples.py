"""Invasiones con lugar/fecha/roster de mentores + 'Mis Discípulos' (Ley de las
7 Semanas) para cuentas de mentor, y vista por-mentor para líderes.

Cubre:
- Crear invasión (lugar + nombre + fecha) queda reservado a pastora/pastor y
  coordinador general (NO a cualquier líder con mentorship.outreach.assign).
- El roster `assigned_mentor_ids` de la invasión valida insignia de Mentor activa.
- El informe de visita ahora acepta fecha de nacimiento, estado espiritual
  (cristiano/no cristiano), si asiste a iglesia y si está descarriado; esos
  campos quedan ocultos para quien no es el mentor responsable ni un líder.
- Al iniciar la Ley de las 7 Semanas desde una visita, la fecha de nacimiento
  capturada se copia al perfil de la Persona 360 si no existe aún.
- `GET /api/processes/consolidation/by-mentor/{id}`: el propio mentor (con
  insignia activa) ve solo sus discípulos; un líder puede ver a cualquier
  mentor por separado; un tercero sin relación queda bloqueado.
- Una cuenta de mentor (creada con mentor_access=True) puede marcar el avance
  de etapas/tareas (MCD, NPT, LBS) de SU disciplo, pero no de uno ajeno.
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

PASSWORD = "OutreachCampaignPass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA",
        "apellido": label,
        "idempotency_key": f"qa:outreachcampaign:{uuid.uuid4()}",
        "version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None) -> tuple[str, str]:
    user_id = ObjectId()
    slug = label.lower().replace(" ", ".")
    email = f"qa.outreachcampaign.{slug}.{uuid.uuid4().hex[:6]}@example.com"
    defaults = access_defaults_for_role(role)
    defaults["capabilities"] = sorted(set(defaults.get("capabilities", []) + (capabilities or [])))
    document = {
        "_id": user_id, "nombre": f"QA {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "is_active": True, "token_version": 1,
        "created_at": datetime.now(timezone.utc), **defaults,
    }
    if person_id:
        document["person_id"] = person_id
    await server.db.users.insert_one(document)
    return str(user_id), email


async def auth_client(email: str, password: str = PASSWORD) -> tuple[AsyncClient, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


async def activate_badge(pid: str) -> None:
    await server.db.mentor_badges.update_one(
        {"person_id": pid},
        {"$set": {"person_id": pid, "active": True, "since": "2026-01-01", "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


async def _complete_stage(client: AsyncClient, headers: dict, enrollment_id: str, stage_key: str) -> dict:
    detail = (await client.get(f"/api/processes/consolidation/{enrollment_id}", headers=headers)).json()
    stage = next(item for item in detail["stages"] if item["stage_key"] == stage_key)
    for task in stage.get("tasks", []):
        if not task.get("completed"):
            response = await client.put(f"/api/processes/enrollments/{enrollment_id}/stages/{stage_key}/tasks/{task['task_id']}", json={"completed": True}, headers=headers)
            assert response.status_code == 200, response.text
    response = await client.put(f"/api/processes/enrollments/{enrollment_id}/stages/{stage_key}", json={"status": "completed"}, headers=headers)
    assert response.status_code == 200, response.text
    return (await client.get(f"/api/processes/consolidation/{enrollment_id}", headers=headers)).json()


@pytest.mark.asyncio
async def test_mentor_tracks_mcd_npt_and_lbs_steps_for_own_disciple_end_to_end():
    """El pedido central del dueño: el mentor marca/cotejar el avance de MCD,
    NPT, y dentro de LBS sus 3 pasos (Liberación, Bendición, Sanidad), sin
    duplicar el motor de Consolidación v2 ya existente."""
    await cleanup()
    pastor_person_id = await create_person("Pastor MCD NPT LBS")
    _, pastor_email = await create_user("Pastor MCD NPT LBS", "pastor", pastor_person_id)
    mentor_person_id = await create_person("Mentor MCD NPT LBS")
    await activate_badge(mentor_person_id)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    try:
        email = f"qa.outreachcampaign.mentor.mcdnptlbs.{uuid.uuid4().hex[:6]}@example.com"
        created = await pastor_client.post(
            "/api/core/governance/users",
            json={"person_id": mentor_person_id, "email": email, "temporary_password": "MentorMcdTempPass1!", "access_level": "persona", "mentor_access": True},
            headers=pastor_headers,
        )
        assert created.status_code == 201, created.text

        mentor_client, mentor_headers = await auth_client(email, password="MentorMcdTempPass1!")
        try:
            changed = await mentor_client.post("/api/auth/change-password", json={"current_password": "MentorMcdTempPass1!", "new_password": "MentorMcdFinalPass1!"}, headers=mentor_headers)
            assert changed.status_code == 200
            mentor_headers = {"Authorization": f"Bearer {changed.json()['token']}"}

            enrollment_id = await _bootstrap_disciple(mentor_person_id, email, "Discipulo MCD NPT LBS", password="MentorMcdFinalPass1!")

            # Un líder formaliza el inicio de Consolidación (requiere processes.write, que el
            # mentor no tiene) confirmando al MISMO mentor responsable.
            started = await pastor_client.post(f"/api/processes/consolidation/{enrollment_id}/start", json={"mentor_person_id": mentor_person_id, "response_result": "Acepto"}, headers=pastor_headers)
            assert started.status_code == 200, started.text
            assert started.json()["current_stage_key"] == "mcd"

            # Desde aquí, el MENTOR (con processes.participate) marca su propio avance.
            after_mcd = await _complete_stage(mentor_client, mentor_headers, enrollment_id, "mcd")
            assert after_mcd["current_stage_key"] == "npt"

            after_npt = await _complete_stage(mentor_client, mentor_headers, enrollment_id, "npt")
            assert after_npt["current_stage_key"] == "welcome_party"

            lbs_stage_keys = [stage["stage_key"] for stage in after_npt["stages"] if stage["stage_key"].startswith("lbs_")]
            assert set(lbs_stage_keys) == {"lbs_1", "lbs_2", "lbs_3"}, "LBS debe tener sus 3 pasos (Liberación, Bendición, Sanidad)"
            lbs_1 = next(stage for stage in after_npt["stages"] if stage["stage_key"] == "lbs_1")
            assert "liberaci" in lbs_1["stage_name"].lower()
        finally:
            await mentor_client.aclose()
    finally:
        await pastor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_only_pastor_and_coordinador_general_create_campaign_with_location_name_date():
    await cleanup()
    leader_pid = await create_person("Leader No Campaign")
    await activate_badge(leader_pid)
    _, leader_email = await create_user("Leader No Campaign", "lider", leader_pid, capabilities=["mentorship.outreach.assign"])
    _, pastor_email = await create_user("Pastor Campaign", "pastor")
    _, coord_email = await create_user("Coord Campaign", "lider")
    await server.db.users.update_one({"email": coord_email}, {"$set": {"access_level": "coordinador_general"}})

    leader_client, leader_headers = await auth_client(leader_email)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    coord_client, coord_headers = await auth_client(coord_email)
    try:
        missing_fields = await pastor_client.post("/api/mentorship/outreach/campaigns", json={"name": "Sin lugar ni fecha"}, headers=pastor_headers)
        assert missing_fields.status_code == 422

        rejected = await leader_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Rechazada", "location": "Sector Norte", "start_date": "2026-03-15"},
            headers=leader_headers,
        )
        assert rejected.status_code == 403

        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Sector Norte", "location": "Sector Norte", "start_date": "2026-03-15"},
            headers=pastor_headers,
        )
        assert created.status_code == 201, created.text
        assert created.json()["location"] == "Sector Norte"
        assert created.json()["start_date"] == "2026-03-15"

        created_by_coord = await coord_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Coordinador", "location": "Sector Sur", "start_date": "2026-03-20"},
            headers=coord_headers,
        )
        assert created_by_coord.status_code == 201, created_by_coord.text
    finally:
        await leader_client.aclose()
        await pastor_client.aclose()
        await coord_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_campaign_assigned_mentor_roster_requires_active_badge():
    await cleanup()
    mentor_with_badge = await create_person("Mentor Con Insignia Roster")
    mentor_without_badge = await create_person("Mentor Sin Insignia Roster")
    await activate_badge(mentor_with_badge)
    _, pastor_email = await create_user("Pastor Roster", "pastor")
    pastor_client, pastor_headers = await auth_client(pastor_email)
    try:
        rejected = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Roster Invalido", "location": "Sector Este", "start_date": "2026-03-10", "assigned_mentor_ids": [mentor_without_badge]},
            headers=pastor_headers,
        )
        assert rejected.status_code == 409

        created = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasion Roster Valido", "location": "Sector Este", "start_date": "2026-03-10", "assigned_mentor_ids": [mentor_with_badge, mentor_with_badge]},
            headers=pastor_headers,
        )
        assert created.status_code == 201, created.text
        assert created.json()["assigned_mentor_ids"] == [mentor_with_badge], "debe deduplicar el roster"
    finally:
        await pastor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_visit_report_new_fields_are_privacy_gated_and_sync_birth_date_to_new_person():
    await cleanup()
    mentor_pid = await create_person("Mentor Nuevos Campos")
    outsider_pid = await create_person("Mentor Ajeno Nuevos Campos")
    await activate_badge(mentor_pid)
    await activate_badge(outsider_pid)
    _, mentor_email = await create_user("Mentor Nuevos Campos", "persona", mentor_pid)
    _, outsider_email = await create_user("Mentor Ajeno Nuevos Campos", "persona", outsider_pid)
    _, pastor_email = await create_user("Pastor Nuevos Campos", "pastor")
    mentor_client, mentor_headers = await auth_client(mentor_email)
    outsider_client, outsider_headers = await auth_client(outsider_email)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    try:
        visit = await mentor_client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Visitado Nuevo", "contact_phone": "809-555-7777", "mentor_person_id": mentor_pid},
            headers=mentor_headers,
        )
        assert visit.status_code == 201, visit.text
        visit_id = visit.json()["visit_id"]

        report = await mentor_client.put(
            f"/api/mentorship/outreach/visits/{visit_id}/report",
            json={
                "status": "wants_followup", "contact_birth_date": "1990-05-20",
                "spiritual_status": "no_cristiano", "attends_church": False, "is_backslidden": False,
                "note": "Acepto iniciar consolidacion",
            },
            headers=mentor_headers,
        )
        assert report.status_code == 200, report.text
        assert report.json()["contact_birth_date"] == "1990-05-20"
        assert report.json()["spiritual_status"] == "no_cristiano"
        assert report.json()["attends_church"] is False

        # Un mentor ajeno (sin relación con esta visita) NO debe ver estos campos sensibles.
        outsider_view = await outsider_client.get(f"/api/mentorship/outreach/visits/{visit_id}", headers=outsider_headers)
        assert outsider_view.status_code == 403, "un mentor ajeno no puede ni abrir la visita de otro"

        # El pastor (líder) sí puede verla y ve los campos revelados.
        leader_view = await pastor_client.get(f"/api/mentorship/outreach/visits/{visit_id}", headers=pastor_headers)
        assert leader_view.status_code == 200
        assert leader_view.json()["contact_birth_date"] == "1990-05-20"
        assert leader_view.json()["spiritual_status"] == "no_cristiano"

        start = await mentor_client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=mentor_headers)
        assert start.status_code == 200, start.text
        assert start.json()["person_created"] is True
        new_person_id = start.json()["converted_person_id"]
        person = await server.db.persons.find_one({"_id": ObjectId(new_person_id)})
        assert person["fecha_nacimiento"] == "1990-05-20", "la fecha de nacimiento capturada en el informe debe quedar en su Perfil 360"
    finally:
        await mentor_client.aclose()
        await outsider_client.aclose()
        await pastor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_birth_date_fills_existing_person_only_when_missing():
    await cleanup()
    mentor_pid = await create_person("Mentor Persona Existente")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Persona Existente", "persona", mentor_pid)
    existing_person_id = await create_person("Visitado Existente")
    await server.db.persons.update_one({"_id": ObjectId(existing_person_id)}, {"$set": {"fecha_nacimiento": "1985-01-01"}})
    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        visit = await mentor_client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "existing", "person_id": existing_person_id, "mentor_person_id": mentor_pid},
            headers=mentor_headers,
        )
        assert visit.status_code == 201, visit.text
        visit_id = visit.json()["visit_id"]
        report = await mentor_client.put(
            f"/api/mentorship/outreach/visits/{visit_id}/report",
            json={"status": "wants_followup", "contact_birth_date": "1999-09-09"},
            headers=mentor_headers,
        )
        assert report.status_code == 200, report.text
        start = await mentor_client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=mentor_headers)
        assert start.status_code == 200, start.text
        person = await server.db.persons.find_one({"_id": ObjectId(existing_person_id)})
        assert person["fecha_nacimiento"] == "1985-01-01", "no debe pisar una fecha de nacimiento ya registrada"
    finally:
        await mentor_client.aclose()
        await cleanup()


async def _bootstrap_disciple(mentor_pid: str, mentor_email: str, label: str, password: str = PASSWORD) -> str:
    client, headers = await auth_client(mentor_email, password=password)
    try:
        visit = await client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": label, "contact_phone": f"809-555-{uuid.uuid4().int % 10000:04d}", "mentor_person_id": mentor_pid},
            headers=headers,
        )
        assert visit.status_code == 201, visit.text
        visit_id = visit.json()["visit_id"]
        report = await client.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "wants_followup"}, headers=headers)
        assert report.status_code == 200, report.text
        start = await client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=headers)
        assert start.status_code == 200, start.text
        return start.json()["enrollment_id"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_by_mentor_endpoint_scopes_to_self_or_leader():
    await cleanup()
    mentor_pid = await create_person("Mentor Discipulos Propios")
    other_pid = await create_person("Mentor Discipulos Otro")
    await activate_badge(mentor_pid)
    await activate_badge(other_pid)
    _, mentor_email = await create_user("Mentor Discipulos Propios", "persona", mentor_pid)
    _, other_email = await create_user("Mentor Discipulos Otro", "persona", other_pid)
    _, pastor_email = await create_user("Pastor Discipulos", "pastor")
    _, coord_email = await create_user("Coord Discipulos", "lider")
    await server.db.users.update_one({"email": coord_email}, {"$set": {"access_level": "coordinador_general"}})

    await _bootstrap_disciple(mentor_pid, mentor_email, "Discipulo Uno")
    await _bootstrap_disciple(mentor_pid, mentor_email, "Discipulo Dos")

    mentor_client, mentor_headers = await auth_client(mentor_email)
    other_client, other_headers = await auth_client(other_email)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    coord_client, coord_headers = await auth_client(coord_email)
    try:
        own_view = await mentor_client.get(f"/api/processes/consolidation/by-mentor/{mentor_pid}", headers=mentor_headers)
        assert own_view.status_code == 200, own_view.text
        assert own_view.json()["total"] == 2
        assert own_view.json()["viewer_is_mentor"] is True

        blocked = await other_client.get(f"/api/processes/consolidation/by-mentor/{mentor_pid}", headers=other_headers)
        assert blocked.status_code == 403, "un mentor sin relación no puede ver los discípulos de otro"

        pastor_view = await pastor_client.get(f"/api/processes/consolidation/by-mentor/{mentor_pid}", headers=pastor_headers)
        assert pastor_view.status_code == 200
        assert pastor_view.json()["total"] == 2
        assert pastor_view.json()["viewer_is_mentor"] is False

        coord_view = await coord_client.get(f"/api/processes/consolidation/by-mentor/{mentor_pid}", headers=coord_headers)
        assert coord_view.status_code == 200
        assert coord_view.json()["total"] == 2
    finally:
        await mentor_client.aclose()
        await other_client.aclose()
        await pastor_client.aclose()
        await coord_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_mentor_account_without_badge_cannot_use_by_mentor_self_view():
    await cleanup()
    pid = await create_person("Persona Sin Insignia ByMentor")
    _, email = await create_user("Persona Sin Insignia ByMentor", "persona", pid)
    client, headers = await auth_client(email)
    try:
        response = await client.get(f"/api/processes/consolidation/by-mentor/{pid}", headers=headers)
        assert response.status_code == 403
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_mentor_account_can_mark_stage_and_task_progress_for_own_disciple_not_for_others():
    """Verifica el otorgamiento de PROCESSES_PARTICIPATE a cuentas de mentor
    (core_governance.py, mentor_access=True) y que pueden marcar MCD/NPT/LBS
    de su propio discípulo, pero no de uno ajeno."""
    await cleanup()
    pastor_person_id = await create_person("Pastor Governance Discipulos")
    _, pastor_email = await create_user("Pastor Governance Discipulos", "pastor", pastor_person_id)
    pastor_client, pastor_headers = await auth_client(pastor_email)

    mentor_target_person_id = await create_person("Mentor Target Stage")
    await activate_badge(mentor_target_person_id)
    other_mentor_person_id = await create_person("Mentor Otro Stage")
    await activate_badge(other_mentor_person_id)
    _, other_mentor_email = await create_user("Mentor Otro Stage", "persona", other_mentor_person_id)

    try:
        email = f"qa.outreachcampaign.mentor.stage.{uuid.uuid4().hex[:6]}@example.com"
        created = await pastor_client.post(
            "/api/core/governance/users",
            json={
                "person_id": mentor_target_person_id, "email": email,
                "temporary_password": "MentorStageTempPass1!", "access_level": "persona", "mentor_access": True,
            },
            headers=pastor_headers,
        )
        assert created.status_code == 201, created.text
        assert "processes.participate" in created.json()["capabilities"]

        mentor_client, mentor_headers = await auth_client(email, password="MentorStageTempPass1!")
        changed = await mentor_client.post(
            "/api/auth/change-password", json={"current_password": "MentorStageTempPass1!", "new_password": "MentorStageFinalPass1!"}, headers=mentor_headers,
        )
        assert changed.status_code == 200
        mentor_headers = {"Authorization": f"Bearer {changed.json()['token']}"}

        own_enrollment_id = await _bootstrap_disciple(mentor_target_person_id, email, "Discipulo De Mentor Stage", password="MentorStageFinalPass1!")
        other_enrollment_id = await _bootstrap_disciple(other_mentor_person_id, other_mentor_email, "Discipulo Ajeno Stage")

        detail = (await mentor_client.get(f"/api/processes/consolidation/{own_enrollment_id}", headers=mentor_headers)).json()
        current_stage_key = detail["current_stage_key"]
        current_stage = next(item for item in detail["stages"] if item["stage_key"] == current_stage_key)
        assert current_stage["status"] in {"open", "in_progress"}, current_stage
        task = current_stage["tasks"][0]
        task_update = await mentor_client.put(
            f"/api/processes/enrollments/{own_enrollment_id}/stages/{current_stage_key}/tasks/{task['task_id']}",
            json={"completed": True}, headers=mentor_headers,
        )
        assert task_update.status_code == 200, task_update.text

        blocked_task = await mentor_client.put(
            f"/api/processes/enrollments/{other_enrollment_id}/stages/{current_stage_key}/tasks/{task['task_id']}",
            json={"completed": True}, headers=mentor_headers,
        )
        assert blocked_task.status_code == 403, "no puede tocar el proceso de un discípulo ajeno"
    finally:
        await pastor_client.aclose()
        await cleanup()
