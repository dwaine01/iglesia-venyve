"""R2 · Graduación: acto aparte después del Retiro, en un evento; solo entonces se completa y se abre Discipulado."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio

import server
from graduation import church_today
from process_engine import create_enrollment, evaluate_alerts
from tests.test_consolidation_v2_e2e import auth_client, create_person, create_user


async def at_retreat(person_id: str, actor: str, old_style: bool = False) -> str:
    """Expediente v2 listo para cerrar el Retiro. `old_style`: abierto antes del cambio (sin fila de Graduación)."""
    enrollment, _ = await create_enrollment(server.db, "consolidation", person_id, None, actor, source="qa_graduation")
    enrollment_id = enrollment["enrollment_id"]
    now = datetime.now(timezone.utc)
    async for stage in server.db.process_stage_progress.find({"enrollment_id": enrollment_id}):
        status = "completed" if stage["stage_order"] < 10 else ("open" if stage["stage_key"] == "retreat" else "locked")
        await server.db.process_stage_progress.update_one({"_id": stage["_id"]}, {"$set": {"status": status}})
    if old_style:
        await server.db.process_stage_progress.delete_one({"enrollment_id": enrollment_id, "stage_key": "graduation"})
        await server.db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "discipleship_handoff"}, {"$set": {"stage_order": 11}})
    await server.db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {"current_stage_key": "retreat", "decision_status": "accepted"}})
    membership_id = str(uuid.uuid4())
    await server.db.person_memberships.insert_one({"_id": membership_id, "membership_id": membership_id, "person_id": person_id, "status": "active",
                                                   "member_number": f"QAG-{membership_id[:6]}", "acceptance_signed_at": now, "created_at": now})
    return enrollment_id


RETREAT = {"certificate_delivery_status": "pending_exception", "card_delivery_status": "not_applicable"}


@pytest_asyncio.fixture
async def world():
    await server.db.process_definitions.delete_many({"process_key": "consolidation", "version": 2})
    from process_catalog import seed_process_catalog
    await seed_process_catalog(server.db)
    pastor_id, pastor_email = await create_user("Grad Pastor", "pastor")
    mentor_pid = await create_person("Grad Mentor")
    mentor_uid, mentor_email = await create_user("Grad Mentor", "lider", mentor_pid)
    people = [await create_person(f"Graduando {n}") for n in range(4)]
    client, headers = await auth_client(pastor_email)
    program_id, module_id = str(uuid.uuid4()), str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await server.db.formation_programs.insert_one({"_id": program_id, "program_id": program_id, "name": "QA Discipulado R2", "purpose": "discipleship", "active": True, "created_at": now - timedelta(days=3650)})
    await server.db.formation_modules.insert_one({"_id": module_id, "module_id": module_id, "program_id": program_id, "name": "QA Fundamentos R2", "order": 1, "active": True,
                                                  "approval_policy": {"method": "manual"}, "created_at": now})
    state = {"client": client, "headers": headers, "pastor_id": pastor_id, "mentor_email": mentor_email, "people": people, "program_id": program_id, "module_id": module_id}
    yield state
    await client.aclose()
    enrollment_ids = await server.db.process_enrollments.distinct("enrollment_id", {"person_id": {"$in": people}})
    for name in ["process_stage_progress", "process_timeline", "process_alerts", "graduation_records", "consolidation_activities", "mentor_assignments"]:
        await server.db[name].delete_many({"enrollment_id": {"$in": enrollment_ids}})
    await server.db.process_enrollments.delete_many({"person_id": {"$in": people}})
    await server.db.person_memberships.delete_many({"person_id": {"$in": people}})
    await server.db.graduation_events.delete_many({"name": {"$regex": "^QA Grad"}})
    await server.db.formation_recommendations.delete_many({"person_id": {"$in": people}})
    await server.db.formation_enrollments.delete_many({"person_id": {"$in": people}})
    await server.db.formation_cohorts.delete_many({"program_id": program_id})
    await server.db.formation_modules.delete_many({"program_id": program_id})
    await server.db.formation_programs.delete_one({"program_id": program_id})
    from bson import ObjectId
    await server.db.persons.delete_many({"_id": {"$in": [ObjectId(pid) for pid in people + [mentor_pid]]}})
    await server.db.users.delete_many({"email": {"$in": [pastor_email, mentor_email]}})


async def new_event(client, headers, name="QA Grad Evento", day=None):
    response = await client.post("/api/processes/consolidation/graduations", json={"name": name, "event_date": day or await church_today(), "location": "Templo"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["event_id"]


@pytest.mark.asyncio
async def test_retreat_leaves_pending_then_one_event_graduates_several(world):
    client, headers, people = world["client"], world["headers"], world["people"]
    ids = [await at_retreat(pid, world["pastor_id"], old_style=(n == 1)) for n, pid in enumerate(people[:3])]
    for enrollment_id in ids:
        closed = await client.post(f"/api/processes/consolidation/{enrollment_id}/retreat-close", json=RETREAT, headers=headers)
        assert closed.status_code == 200, closed.text
        body = closed.json()
        assert body["status"] == "active" and body["consolidation_status"] == "graduation_pending" and body["current_stage_key"] == "graduation"
        stages = {row["stage_key"]: row for row in body["stages"]}
        assert stages["retreat"]["status"] == "completed" and stages["graduation"]["status"] == "open" and stages["discipleship_handoff"]["status"] == "locked"
        assert [row["stage_key"] for row in body["stages"]][-2:] == ["graduation", "discipleship_handoff"]
        assert not body.get("formation_recommendation")
    # El expediente abierto antes del cambio recibió la fila del paso (y el traspaso pasó a ser el 12).
    assert await server.db.process_stage_progress.find_one({"enrollment_id": ids[1], "stage_key": "discipleship_handoff", "stage_order": 12})
    # Cerrar otra vez no hace nada nuevo; tampoco se puede marcar Graduación como etapa normal.
    again = await client.post(f"/api/processes/consolidation/{ids[0]}/retreat-close", json=RETREAT, headers=headers)
    assert again.status_code == 200 and again.json()["current_stage_key"] == "graduation"
    blocked = await client.put(f"/api/processes/enrollments/{ids[0]}/stages/graduation", json={"status": "completed"}, headers=headers)
    assert blocked.status_code == 409
    task_blocked = await client.put(f"/api/processes/enrollments/{ids[0]}/stages/graduation/tasks/graduation_registered", json={"completed": True}, headers=headers)
    assert task_blocked.status_code == 409

    future = await new_event(client, headers, "QA Grad Futuro", (date.fromisoformat(await church_today()) + timedelta(days=5)).isoformat())
    too_early = await client.post(f"/api/processes/consolidation/graduations/{future}/graduates", json={"enrollment_ids": ids}, headers=headers)
    assert too_early.status_code == 409

    event_id = await new_event(client, headers)
    detail = (await client.get(f"/api/processes/consolidation/graduations/{event_id}", headers=headers)).json()
    assert set(ids) <= {row["enrollment_id"] for row in detail["candidates"]}
    # Todo o nada: uno que no está pendiente de graduación detiene a todos.
    not_ready = await at_retreat(people[3], world["pastor_id"])
    mixed = await client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates", json={"enrollment_ids": ids + [not_ready]}, headers=headers)
    assert mixed.status_code == 409
    assert await server.db.graduation_records.count_documents({"event_id": event_id}) == 0

    done = await client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates", json={"enrollment_ids": ids}, headers=headers)
    assert done.status_code == 200, done.text
    assert sorted(done.json()["graduated"]) == sorted(ids) and len(done.json()["graduates"]) == 3
    for enrollment_id in ids:
        row = (await client.get(f"/api/processes/consolidation/{enrollment_id}", headers=headers)).json()
        assert row["status"] == "completed" and row["consolidation_status"] == "completed" and row["graduated_at"].startswith(await church_today())
        assert row["graduation_event"]["event_id"] == event_id
        stages = {item["stage_key"]: item for item in row["stages"]}
        assert stages["graduation"]["status"] == "completed" and stages["discipleship_handoff"]["status"] == "open"
        assert row["formation_recommendation"]["module_id"] == world["module_id"] and row["formation_recommendation"]["source"] == "consolidation_graduation"
        assert row["next_action"] == "Inscribir en QA Fundamentos R2"
        assert any(item["event_type"] == "graduated" for item in row["timeline"])
    twice = await client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates", json={"enrollment_ids": ids[:1]}, headers=headers)
    assert twice.status_code == 409
    listing = (await client.get("/api/processes/consolidation/graduations", headers=headers)).json()
    assert next(item for item in listing["items"] if item["event_id"] == event_id)["graduates_count"] == 3
    # Con graduados, la fecha del evento no se cambia ni se cancela.
    assert (await client.put(f"/api/processes/consolidation/graduations/{event_id}", json={"status": "cancelled"}, headers=headers)).status_code == 409


@pytest.mark.asyncio
async def test_handoff_closes_on_formation_enrollment_and_alert_resolves(world):
    client, headers, people = world["client"], world["headers"], world["people"]
    enrollment_id = await at_retreat(people[0], world["pastor_id"])
    assert (await client.post(f"/api/processes/consolidation/{enrollment_id}/retreat-close", json=RETREAT, headers=headers)).status_code == 200
    await evaluate_alerts(server.db, force=True)
    # Pendiente de graduación: aún no hay alerta de Discipulado.
    assert not await server.db.process_alerts.find_one({"enrollment_id": enrollment_id, "rule_key": "discipleship_handoff_missing", "status": "open"})
    event_id = await new_event(client, headers)
    assert (await client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates", json={"enrollment_ids": [enrollment_id]}, headers=headers)).status_code == 200
    await evaluate_alerts(server.db, force=True)
    assert await server.db.process_alerts.find_one({"enrollment_id": enrollment_id, "rule_key": "discipleship_handoff_missing", "status": "open"})

    cohort = await client.post("/api/formation/cohorts", json={"module_id": world["module_id"], "name": "QA Cohorte R2", "start_date": await church_today(), "status": "open"}, headers=headers)
    assert cohort.status_code == 201, cohort.text
    enrolled = await client.post(f"/api/formation/cohorts/{cohort.json()['cohort_id']}/enrollments", json={"person_id": people[0]}, headers=headers)
    assert enrolled.status_code == 201, enrolled.text
    row = (await client.get(f"/api/processes/consolidation/{enrollment_id}", headers=headers)).json()
    assert row["discipleship_enrollment_id"] == enrolled.json()["enrollment_id"]
    assert row["discipleship"]["module_name_snapshot"] == "QA Fundamentos R2"
    assert {item["stage_key"]: item for item in row["stages"]}["discipleship_handoff"]["status"] == "completed"
    assert row["progress_pct"] == 100
    assert await server.db.formation_recommendations.find_one({"source_enrollment_id": enrollment_id, "status": "fulfilled"})
    await evaluate_alerts(server.db, force=True)
    assert not await server.db.process_alerts.find_one({"enrollment_id": enrollment_id, "rule_key": "discipleship_handoff_missing", "status": "open"})
    # Ya inscrito: la graduación no se revierte desde aquí.
    revert = await client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates/{enrollment_id}/revert", json={"reason": "Prueba de reversión"}, headers=headers)
    assert revert.status_code == 409


@pytest.mark.asyncio
async def test_revert_graduation_keeps_history(world):
    client, headers, people = world["client"], world["headers"], world["people"]
    enrollment_id = await at_retreat(people[0], world["pastor_id"])
    assert (await client.post(f"/api/processes/consolidation/{enrollment_id}/retreat-close", json=RETREAT, headers=headers)).status_code == 200
    event_id = await new_event(client, headers)
    assert (await client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates", json={"enrollment_ids": [enrollment_id]}, headers=headers)).status_code == 200
    reverted = await client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates/{enrollment_id}/revert", json={"reason": "Se registró por error"}, headers=headers)
    assert reverted.status_code == 200, reverted.text
    row = (await client.get(f"/api/processes/consolidation/{enrollment_id}", headers=headers)).json()
    assert row["status"] == "active" and row["consolidation_status"] == "graduation_pending" and not row.get("graduated_at")
    assert row["decision_status"] == "accepted"
    assert {item["stage_key"]: item for item in row["stages"]}["graduation"]["status"] == "open"
    assert await server.db.graduation_records.find_one({"enrollment_id": enrollment_id, "status": "reverted", "revert_reason": "Se registró por error"})
    assert {"graduated", "graduation_reverted"} <= {item["event_type"] for item in row["timeline"]}
    # Se puede volver a graduar después de corregir.
    again = await client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates", json={"enrollment_ids": [enrollment_id]}, headers=headers)
    assert again.status_code == 200, again.text


@pytest.mark.asyncio
async def test_old_retreat_closed_records_are_not_touched_and_permissions(world):
    client, headers, people = world["client"], world["headers"], world["people"]
    # Cerró el Retiro con la regla anterior: quedó «completado» sin graduación.
    old_id = await at_retreat(people[0], world["pastor_id"], old_style=True)
    now = datetime.now(timezone.utc)
    await server.db.process_enrollments.update_one({"enrollment_id": old_id}, {"$set": {"status": "completed", "consolidation_status": "completed", "retreat_completed_at": now, "current_stage_key": "discipleship_handoff"}})
    before = await server.db.process_enrollments.find_one({"enrollment_id": old_id}, {"_id": 0})
    listing = (await client.get("/api/processes/consolidation/graduations", headers=headers)).json()
    assert listing["legacy_retreat_closed_count"] >= 1
    event_id = await new_event(client, headers)
    detail = (await client.get(f"/api/processes/consolidation/graduations/{event_id}", headers=headers)).json()
    assert old_id not in {row["enrollment_id"] for row in detail["candidates"]}
    assert (await client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates", json={"enrollment_ids": [old_id]}, headers=headers)).status_code == 409
    cohort = await client.post("/api/formation/cohorts", json={"module_id": world["module_id"], "name": "QA Cohorte R2 viejo", "start_date": await church_today(), "status": "open"}, headers=headers)
    assert (await client.post(f"/api/formation/cohorts/{cohort.json()['cohort_id']}/enrollments", json={"person_id": people[0]}, headers=headers)).status_code == 201
    after = await server.db.process_enrollments.find_one({"enrollment_id": old_id}, {"_id": 0})
    assert after == before  # ni se gradúa ni se enlaza solo
    # La alerta del expediente viejo se resuelve leyendo Formación (sin escribir en él).
    await evaluate_alerts(server.db, force=True)
    assert not await server.db.process_alerts.find_one({"enrollment_id": old_id, "rule_key": "discipleship_handoff_missing", "status": "open"})

    mentor_client, mentor_headers = await auth_client(world["mentor_email"])
    try:
        denied = await mentor_client.post("/api/processes/consolidation/graduations", json={"name": "QA Grad Mentor", "event_date": await church_today()}, headers=mentor_headers)
        assert denied.status_code == 403
        assert (await mentor_client.post(f"/api/processes/consolidation/graduations/{event_id}/graduates", json={"enrollment_ids": [old_id]}, headers=mentor_headers)).status_code == 403
    finally:
        await mentor_client.aclose()
