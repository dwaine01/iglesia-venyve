"""Invasiones — Entrega B: calendario individual de actividades (MCD/NPT/LBS),
registro por actividad, panel del mentor, supervisión y estados de decisión.

Cubre los 4 requisitos de prueba explícitos del dueño:
- Idempotencia del calendario (no se duplica si se regenera).
- 'Sin respuesta' NO cuenta como 'realizada' ni avanza el estado de decisión.
- Aislamiento entre mentores (uno nunca ve/edita las actividades del otro).
- Arranque en S3 (MCD) desde célula/iglesia, con el mismo expediente.
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from consolidation_activities import ensure_consolidation_calendar
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "EntregaBPass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id, "person_number": f"VV-QAB{uuid.uuid4().hex[:6].upper()}",
        "nombre": "QA", "apellido": label, "idempotency_key": f"qa:entregab:{uuid.uuid4()}",
        "version": 1, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None) -> tuple[str, str]:
    user_id = ObjectId()
    slug = label.lower().replace(" ", ".")
    email = f"qa.entregab.{slug}.{uuid.uuid4().hex[:6]}@example.com"
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


async def cleanup(campaign_ids=None):
    if campaign_ids:
        await server.db.library_movements.delete_many({"campaign_id": {"$in": campaign_ids}})
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


async def set_central_stock(sku: str, quantity: int) -> str:
    book = await server.db.library_books.find_one({"sku": sku, "is_active": True}, {"_id": 0, "book_id": 1})
    await server.db.library_holdings.update_one(
        {"book_id": book["book_id"], "holder_type": "warehouse", "holder_id": "central"},
        {"$set": {"quantity_on_hand": quantity, "reserved_qty": 0, "updated_at": datetime.now(timezone.utc)}, "$setOnInsert": {"_id": str(uuid.uuid4())}},
        upsert=True,
    )
    return book["book_id"]


async def start_invasion_consolidation(mentor_pid: str, mentor_client, mentor_headers, agreed_start_date: str, campaign_id: str | None = None) -> dict:
    """Crea una visita de invasión, la marca 'wants_followup' con fecha de
    inicio acordada, e inicia la Ley de las 7 Semanas. Devuelve la respuesta."""
    visit = await mentor_client.post(
        "/api/mentorship/outreach/visits",
        json={"contact_type": "new", "contact_name": f"Casa EntregaB {uuid.uuid4().hex[:5]}", "contact_phone": f"809555{uuid.uuid4().hex[:4]}", "mentor_person_id": mentor_pid, "campaign_id": campaign_id},
        headers=mentor_headers,
    )
    assert visit.status_code == 201, visit.text
    visit_id = visit.json()["visit_id"]
    report = await mentor_client.put(
        f"/api/mentorship/outreach/visits/{visit_id}/report",
        json={"status": "wants_followup", "agreed_start_date": agreed_start_date, "call_schedule": "morning"},
        headers=mentor_headers,
    )
    assert report.status_code == 200, report.text
    started = await mentor_client.post(f"/api/mentorship/outreach/visits/{visit_id}/start-seven-weeks", headers=mentor_headers)
    assert started.status_code == 200, started.text
    return started.json()


@pytest.mark.asyncio
async def test_calendar_generated_from_invasion_matches_weeks_and_is_idempotent():
    await cleanup()
    mentor_pid = await create_person("Mentor Calendario Invasion")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Calendario Invasion", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])

    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        future_start = (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()
        started = await start_invasion_consolidation(mentor_pid, mentor_client, mentor_headers, future_start)
        enrollment_id = started["enrollment_id"]

        activities_resp = await mentor_client.get(f"/api/processes/consolidation/{enrollment_id}/activities", headers=mentor_headers)
        assert activities_resp.status_code == 200, activities_resp.text
        items = activities_resp.json()["items"]
        assert len(items) == 54

        by_stage = {}
        for item in items:
            by_stage.setdefault(item["stage_key"], []).append(item)
        assert len(by_stage["mcd"]) == 21 and len(by_stage["npt"]) == 12
        assert len(by_stage["lbs_1"]) == 7 and len(by_stage["lbs_2"]) == 7 and len(by_stage["lbs_3"]) == 7

        from datetime import date
        start_date = date.fromisoformat(future_start)
        mcd_day1 = next(i for i in by_stage["mcd"] if i["day_number"] == 1 and i["moment_key"] == "morning")
        assert mcd_day1["scheduled_date"] == start_date.isoformat()
        npt_day1 = next(i for i in by_stage["npt"] if i["day_number"] == 1 and i["moment_key"] == "9am")
        assert npt_day1["scheduled_date"] == (start_date + timedelta(days=7)).isoformat()
        lbs1_day1 = next(i for i in by_stage["lbs_1"] if i["day_number"] == 1)
        assert lbs1_day1["scheduled_date"] == (start_date + timedelta(days=14)).isoformat()
        lbs3_day7 = next(i for i in by_stage["lbs_3"] if i["day_number"] == 7)
        assert lbs3_day7["scheduled_date"] == (start_date + timedelta(days=34)).isoformat()

        enrollment = await server.db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
        assert enrollment["decision_status"] == "start_scheduled", "fecha de inicio futura -> 'Inicio programado'"

        # Idempotencia: regenerar el calendario para el mismo expediente no debe duplicar nada.
        created_again = await ensure_consolidation_calendar(enrollment, "system:test")
        assert created_again is False
        count = await server.db.consolidation_activities.count_documents({"enrollment_id": enrollment_id})
        assert count == 54
    finally:
        await mentor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_no_answer_does_not_count_as_done_nor_advance_decision_status():
    await cleanup()
    mentor_pid = await create_person("Mentor Sin Respuesta")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Sin Respuesta", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])

    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        future_start = (datetime.now(timezone.utc).date() + timedelta(days=5)).isoformat()
        started = await start_invasion_consolidation(mentor_pid, mentor_client, mentor_headers, future_start)
        enrollment_id = started["enrollment_id"]
        activities = (await mentor_client.get(f"/api/processes/consolidation/{enrollment_id}/activities", headers=mentor_headers)).json()["items"]
        first_mcd = next(i for i in activities if i["stage_key"] == "mcd" and i["day_number"] == 1 and i["moment_key"] == "morning")

        no_answer = await mentor_client.put(
            f"/api/processes/consolidation/activities/{first_mcd['activity_id']}/result",
            json={"status": "no_answer", "note": "No contestó"}, headers=mentor_headers,
        )
        assert no_answer.status_code == 200, no_answer.text
        assert no_answer.json()["status"] == "pending", "'sin respuesta' es un intento, no cierra la actividad: sigue pendiente para poder reintentar"
        assert no_answer.json()["last_result"] == "no_answer"

        enrollment_after = await server.db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
        assert enrollment_after["decision_status"] == "start_scheduled", "'sin respuesta' no debe avanzar el estado de decisión"
        done_count = await server.db.consolidation_activities.count_documents({"enrollment_id": enrollment_id, "status": "done"})
        assert done_count == 0, "'sin respuesta' no cuenta como actividad realizada"

        # Ahora sí marca una como realizada -> decision_status avanza a 'in_progress'.
        second_mcd = next(i for i in activities if i["stage_key"] == "mcd" and i["day_number"] == 1 and i["moment_key"] == "midday")
        done = await mentor_client.put(
            f"/api/processes/consolidation/activities/{second_mcd['activity_id']}/result",
            json={"status": "done", "note": "Oramos juntos"}, headers=mentor_headers,
        )
        assert done.status_code == 200, done.text
        enrollment_final = await server.db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
        assert enrollment_final["decision_status"] == "in_progress"
    finally:
        await mentor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_mentor_isolation_cannot_see_or_update_other_mentors_activities():
    await cleanup()
    mentor_a_pid = await create_person("Mentor Aislado A")
    await activate_badge(mentor_a_pid)
    _, mentor_a_email = await create_user("Mentor Aislado A", "persona", mentor_a_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    mentor_b_pid = await create_person("Mentor Aislado B")
    await activate_badge(mentor_b_pid)
    _, mentor_b_email = await create_user("Mentor Aislado B", "persona", mentor_b_pid, capabilities=["mentorship.outreach.report", "library.deliver"])

    mentor_a_client, mentor_a_headers = await auth_client(mentor_a_email)
    mentor_b_client, mentor_b_headers = await auth_client(mentor_b_email)
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        started_a = await start_invasion_consolidation(mentor_a_pid, mentor_a_client, mentor_a_headers, today)
        enrollment_a_id = started_a["enrollment_id"]
        activities_a = (await mentor_a_client.get(f"/api/processes/consolidation/{enrollment_a_id}/activities", headers=mentor_a_headers)).json()["items"]
        first_activity_a = activities_a[0]

        # Mentor B no puede ver el expediente de A.
        forbidden_view = await mentor_b_client.get(f"/api/processes/consolidation/{enrollment_a_id}/activities", headers=mentor_b_headers)
        assert forbidden_view.status_code == 403

        # Mentor B no puede registrar una actividad de A.
        forbidden_update = await mentor_b_client.put(
            f"/api/processes/consolidation/activities/{first_activity_a['activity_id']}/result",
            json={"status": "done"}, headers=mentor_b_headers,
        )
        assert forbidden_update.status_code == 403

        # El panel de B no debe traer nada del discípulo de A.
        panel_b = await mentor_b_client.get("/api/processes/consolidation/my-panel", headers=mentor_b_headers)
        assert panel_b.status_code == 200
        assert all(item["enrollment_id"] != enrollment_a_id for item in panel_b.json()["mentees"])
    finally:
        await mentor_a_client.aclose()
        await mentor_b_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_cell_or_church_entry_starts_directly_at_mcd_with_calendar_from_today():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaB Celula")
    _, pastor_email = await create_user("Pastor EntregaB Celula", "pastor", pastor_pid)
    person_pid = await create_person("Persona Desde Celula")
    mentor_pid = await create_person("Mentor Desde Celula")
    await activate_badge(mentor_pid)
    await create_user("Mentor Desde Celula", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])

    pastor_client, pastor_headers = await auth_client(pastor_email)
    try:
        intake = await pastor_client.post(
            "/api/processes/consolidation/intakes",
            json={"person_id": person_pid, "entry_mode": "direct_church", "mentor_person_id": mentor_pid},
            headers=pastor_headers,
        )
        assert intake.status_code == 201, intake.text
        body = intake.json()
        assert body["current_stage_key"] == "mcd", "desde célula/iglesia arranca directo en S3 (MCD), mismo expediente"
        assert body["entry_mode"] == "direct_church"
        enrollment_id = body["enrollment_id"]

        prior_stages = await server.db.process_stage_progress.find(
            {"enrollment_id": enrollment_id, "stage_key": {"$in": ["visitor_followup", "prayer", "invasion"]}}, {"_id": 0},
        ).to_list(10)
        assert {s["status"] for s in prior_stages} == {"skipped"}, "desde célula/iglesia NO se usan semana de oración ni de invasión (se marcan no aplica, no completadas)"

        activities = await server.db.consolidation_activities.find({"enrollment_id": enrollment_id}, {"_id": 0}).to_list(100)
        assert len(activities) == 54
        today = datetime.now(timezone.utc).date().isoformat()
        mcd_day1 = next(a for a in activities if a["stage_key"] == "mcd" and a["day_number"] == 1 and a["moment_key"] == "morning")
        assert mcd_day1["scheduled_date"] == today
    finally:
        await pastor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_activity_result_done_with_book_delivery_is_idempotent():
    await cleanup()
    mentor_pid = await create_person("Mentor Entrega Actividad")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Entrega Actividad", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    book_id = await set_central_stock("MCD", 10)

    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        # Asigna 1 unidad de MCD directamente al inventario del mentor (vía movimiento ASSIGNMENT).
        from library_module import HolderInput, MovementInput, apply_movement, CENTRAL_HOLDER
        mentor_user = await server.db.users.find_one({"person_id": mentor_pid}, {"_id": 1})
        await apply_movement(
            MovementInput(book_id=book_id, movement_type="ASSIGNMENT", quantity=1, from_holder=HolderInput(**CENTRAL_HOLDER), to_holder=HolderInput(type="user", id=str(mentor_user["_id"]))),
            "system:test",
        )

        today = datetime.now(timezone.utc).date().isoformat()
        started = await start_invasion_consolidation(mentor_pid, mentor_client, mentor_headers, today)
        enrollment_id = started["enrollment_id"]
        activities = (await mentor_client.get(f"/api/processes/consolidation/{enrollment_id}/activities", headers=mentor_headers)).json()["items"]
        first_mcd = next(i for i in activities if i["stage_key"] == "mcd" and i["day_number"] == 1 and i["moment_key"] == "morning")

        done = await mentor_client.put(
            f"/api/processes/consolidation/activities/{first_mcd['activity_id']}/result",
            json={"status": "done", "deliver_book": True}, headers=mentor_headers,
        )
        assert done.status_code == 200, done.text
        assert done.json()["book_delivery_movement_id"]

        retry = await mentor_client.put(
            f"/api/processes/consolidation/activities/{first_mcd['activity_id']}/result",
            json={"status": "done", "deliver_book": True}, headers=mentor_headers,
        )
        assert retry.status_code == 200, retry.text
        assert retry.json()["book_delivery_movement_id"] == done.json()["book_delivery_movement_id"]

        delivery_movements = await server.db.library_movements.count_documents({"book_id": book_id, "movement_type": "DELIVERY", "person_id": started["converted_person_id"]})
        assert delivery_movements == 1, "no debe duplicar el movimiento DELIVERY en un reintento"
    finally:
        await mentor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_decision_status_pause_requires_reason_and_can_resume():
    await cleanup()
    mentor_pid = await create_person("Mentor Pausa Decision")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Pausa Decision", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])

    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        started = await start_invasion_consolidation(mentor_pid, mentor_client, mentor_headers, today)
        enrollment_id = started["enrollment_id"]

        no_reason = await mentor_client.put(f"/api/processes/consolidation/{enrollment_id}/decision-status", json={"new_status": "paused"}, headers=mentor_headers)
        assert no_reason.status_code == 422

        paused = await mentor_client.put(f"/api/processes/consolidation/{enrollment_id}/decision-status", json={"new_status": "paused", "reason": "Se mudó de ciudad"}, headers=mentor_headers)
        assert paused.status_code == 200, paused.text
        assert paused.json()["decision_status"] == "paused"

        resumed = await mentor_client.put(f"/api/processes/consolidation/{enrollment_id}/decision-status", json={"new_status": "accepted"}, headers=mentor_headers)
        assert resumed.status_code == 200
        # Reanudar no debe retroceder el progreso: como el calendario ya inició hoy,
        # el sistema recalcula a 'in_progress' en vez de devolverlo a 'accepted'.
        assert resumed.json()["decision_status"] == "in_progress"
        assert resumed.json()["decision_paused_reason"] is None

        membership = await server.db.person_memberships.find_one({"person_id": started["converted_person_id"]})
        assert membership is None, "aceptar/pausar Consolidación NO debe crear membresía"
    finally:
        await mentor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_my_panel_and_supervision_by_mentor_show_overdue_and_are_isolated():
    await cleanup()
    pastor_pid = await create_person("Pastor EntregaB Supervision")
    _, pastor_email = await create_user("Pastor EntregaB Supervision", "pastor", pastor_pid)
    mentor_pid = await create_person("Mentor Supervisado")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Supervisado", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    other_mentor_pid = await create_person("Mentor No Supervisado")
    await activate_badge(other_mentor_pid)
    _, other_email = await create_user("Mentor No Supervisado", "persona", other_mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])

    mentor_client, mentor_headers = await auth_client(mentor_email)
    other_client, other_headers = await auth_client(other_email)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    try:
        past_start = (datetime.now(timezone.utc).date() - timedelta(days=3)).isoformat()
        started = await start_invasion_consolidation(mentor_pid, mentor_client, mentor_headers, past_start)
        enrollment_id = started["enrollment_id"]

        panel = await mentor_client.get("/api/processes/consolidation/my-panel", headers=mentor_headers)
        assert panel.status_code == 200, panel.text
        assert len(panel.json()["overdue"]) > 0, "un calendario con inicio en el pasado debe mostrar actividades atrasadas"
        assert any(m["enrollment_id"] == enrollment_id for m in panel.json()["mentees"])

        other_panel = await other_client.get("/api/processes/consolidation/my-panel", headers=other_headers)
        assert other_panel.status_code == 200
        assert len(other_panel.json()["overdue"]) == 0
        assert other_panel.json()["mentees"] == []

        supervision = await pastor_client.get(f"/api/processes/consolidation/by-mentor/{mentor_pid}", headers=pastor_headers)
        assert supervision.status_code == 200, supervision.text
        assert len(supervision.json()["activity_buckets"]["overdue"]) > 0
    finally:
        await mentor_client.aclose()
        await other_client.aclose()
        await pastor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_mentor_transfer_moves_pending_activities_to_new_mentor_panel():
    await cleanup()
    old_mentor_pid = await create_person("Mentor Original Transfer")
    await activate_badge(old_mentor_pid)
    _, old_email = await create_user("Mentor Original Transfer", "persona", old_mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    new_mentor_pid = await create_person("Mentor Nuevo Transfer")
    await activate_badge(new_mentor_pid)
    _, new_email = await create_user("Mentor Nuevo Transfer", "persona", new_mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])

    old_client, old_headers = await auth_client(old_email)
    new_client, new_headers = await auth_client(new_email)
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        started = await start_invasion_consolidation(old_mentor_pid, old_client, old_headers, today)
        enrollment_id = started["enrollment_id"]
        activities = (await old_client.get(f"/api/processes/consolidation/{enrollment_id}/activities", headers=old_headers)).json()["items"]
        first_mcd = next(i for i in activities if i["stage_key"] == "mcd" and i["day_number"] == 1 and i["moment_key"] == "morning")
        await old_client.put(
            f"/api/processes/consolidation/activities/{first_mcd['activity_id']}/result",
            json={"status": "done", "note": "Primer día con el mentor original"}, headers=old_headers,
        )

        from consolidation_service import assign_mentor
        enrollment = await server.db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
        await assign_mentor(server.db, enrollment, new_mentor_pid, "system:test", "Transferencia de prueba", transfer=True)

        old_panel = await old_client.get("/api/processes/consolidation/my-panel", headers=old_headers)
        new_panel = await new_client.get("/api/processes/consolidation/my-panel", headers=new_headers)
        assert not any(m["enrollment_id"] == enrollment_id for m in old_panel.json()["mentees"]), "el mentor anterior ya no debe ver este expediente en su panel"
        assert any(m["enrollment_id"] == enrollment_id for m in new_panel.json()["mentees"]), "el nuevo mentor debe ver el expediente transferido"

        pending_for_new = await server.db.consolidation_activities.count_documents({"enrollment_id": enrollment_id, "status": "pending", "mentor_person_id": new_mentor_pid})
        done_still_old = await server.db.consolidation_activities.count_documents({"enrollment_id": enrollment_id, "status": "done", "mentor_person_id": old_mentor_pid})
        assert pending_for_new == 53, "las actividades pendientes pasan al nuevo mentor responsable"
        assert done_still_old == 1, "la actividad ya realizada conserva la atribución de quien la hizo"
    finally:
        await old_client.aclose()
        await new_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_same_book_cannot_be_delivered_twice_to_same_person_across_activities():
    await cleanup()
    mentor_pid = await create_person("Mentor Entrega Duplicada")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Entrega Duplicada", "persona", mentor_pid, capabilities=["mentorship.outreach.report", "library.deliver"])
    book_id = await set_central_stock("MCD", 10)

    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        from library_module import HolderInput, MovementInput, apply_movement, CENTRAL_HOLDER
        mentor_user = await server.db.users.find_one({"person_id": mentor_pid}, {"_id": 1})
        await apply_movement(
            MovementInput(book_id=book_id, movement_type="ASSIGNMENT", quantity=2, from_holder=HolderInput(**CENTRAL_HOLDER), to_holder=HolderInput(type="user", id=str(mentor_user["_id"]))),
            "system:test",
        )

        today = datetime.now(timezone.utc).date().isoformat()
        started = await start_invasion_consolidation(mentor_pid, mentor_client, mentor_headers, today)
        enrollment_id = started["enrollment_id"]
        activities = (await mentor_client.get(f"/api/processes/consolidation/{enrollment_id}/activities", headers=mentor_headers)).json()["items"]
        day1 = next(i for i in activities if i["stage_key"] == "mcd" and i["day_number"] == 1 and i["moment_key"] == "morning")
        day2 = next(i for i in activities if i["stage_key"] == "mcd" and i["day_number"] == 2 and i["moment_key"] == "morning")

        first_delivery = await mentor_client.put(
            f"/api/processes/consolidation/activities/{day1['activity_id']}/result",
            json={"status": "done", "deliver_book": True}, headers=mentor_headers,
        )
        assert first_delivery.status_code == 200, first_delivery.text
        assert first_delivery.json()["book_delivery_movement_id"]

        second_delivery = await mentor_client.put(
            f"/api/processes/consolidation/activities/{day2['activity_id']}/result",
            json={"status": "done", "deliver_book": True}, headers=mentor_headers,
        )
        assert second_delivery.status_code == 409, second_delivery.text

        delivery_movements = await server.db.library_movements.count_documents({"book_id": book_id, "movement_type": "DELIVERY", "person_id": started["converted_person_id"]})
        assert delivery_movements == 1, "no se debe entregar el mismo libro dos veces a la misma persona desde actividades distintas"
    finally:
        await mentor_client.aclose()
        await cleanup()
