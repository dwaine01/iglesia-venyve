"""R3 · «Proceso paso a paso» por persona (solo lectura): de «conocida» a «En proceso con mentor X», origen,
los 12 pasos con estado, fecha y quién, hitos antes y después, y el mismo acceso que «Contactado por»."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_step_by_step_shows_origin_mentor_steps_and_milestones():
    from consolidation_service import assign_mentor, configure_entry_stages
    from process_catalog import seed_process_catalog
    from process_engine import create_enrollment
    await seed_process_catalog(db)
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    enrollment_id = None
    try:
        pastora = await fx.account(await fx.person(f"PastoraS{tag}"), "pastora")
        mentor_id = await fx.person(f"MentorS{tag}")
        mentor = await fx.account(mentor_id, "persona")
        await db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": mentor_id, "active": True})
        outsider = await fx.account(await fx.person(f"AjenoS{tag}"), "persona")
        target = await fx.person(f"Maria{tag}")

        # Conocida: todavía sin expediente.
        known = await pastora.get(f"/api/persons/{target}/step-by-step")
        assert known.status_code == 200, known.text
        assert known.json()["now"]["key"] == "known" and known.json()["consolidation"] is None

        enrollment, _ = await create_enrollment(db, "consolidation", target, None, "qa", source="manual")
        enrollment_id = enrollment["enrollment_id"]
        await configure_entry_stages(db, enrollment, "direct_church", "qa")
        await assign_mentor(db, await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0}), mentor_id, "qa", "Asignación QA")
        # MCD hecho por la pastora (desde la API: queda quién lo hizo); NPT con el plazo vencido.
        stage = await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": "mcd"})
        for task in stage["tasks"]:
            assert (await pastora.put(f"/api/processes/enrollments/{enrollment_id}/stages/mcd/tasks/{task['task_id']}", json={"completed": True})).status_code == 200
        assert (await pastora.put(f"/api/processes/enrollments/{enrollment_id}/stages/mcd", json={"status": "completed"})).status_code == 200
        await db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "npt"}, {"$set": {"due_at": datetime.now(timezone.utc) - timedelta(days=1)}})

        body = (await pastora.get(f"/api/persons/{target}/step-by-step")).json()
        assert body["now"]["key"] == "in_process" and body["now"]["label"] == f"En proceso con mentor MentorS{tag} Etapa5C"
        assert body["now"]["origin"] == "Iglesia" and body["now"]["step"] == "Nací Para Triunfar"
        assert body["origin"] == {"kind": "iglesia", "label": "Iglesia"}
        moment = next(row for row in body["milestones"] if row["key"] == "in_process")
        assert moment["label"] == f"En proceso con mentor MentorS{tag} Etapa5C" and moment["detail"] == "Desde Iglesia"
        steps = {row["stage_key"]: row for row in body["consolidation"]["steps"]}
        assert len(steps) == 12 and list(steps)[-2:] == ["graduation", "discipleship_handoff"]
        assert steps["prayer"]["state"] == "not_applicable"
        assert steps["mcd"]["state"] == "done" and steps["mcd"]["completed_by"] == f"PastoraS{tag} Etapa5C" and steps["mcd"]["tasks_done"] == 2
        assert steps["npt"]["state"] == "overdue" and steps["lbs_1"]["state"] == "pending"
        assert body["consolidation"]["by_the_book"]["overdue_now"] == 1

        # Acceso: el mentor que la acompaña sí; alguien sin relación no.
        assert (await mentor.get(f"/api/persons/{target}/step-by-step")).status_code == 200
        assert (await outsider.get(f"/api/persons/{target}/step-by-step")).status_code == 403
        # Solo lectura: no cambia nada.
        before = await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
        await pastora.get(f"/api/persons/{target}/step-by-step")
        assert await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0}) == before
    finally:
        if enrollment_id:
            for name in ("process_stage_progress", "process_timeline", "mentor_assignments", "consolidation_activities", "process_alerts"):
                await db[name].delete_many({"enrollment_id": enrollment_id})
            await db.process_enrollments.delete_many({"enrollment_id": enrollment_id})
        await db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await fx.cleanup()


def test_origin_labels():
    from person_steps import origin_of
    assert origin_of({"source": "mentorship_outreach"}, {"campaign_name": "Villa Norte"}, []) == {"kind": "invasion", "label": "Invasión «Villa Norte»"}
    assert origin_of({"entry_mode": "cell"}, None, [])["kind"] == "celula"
    assert origin_of({"source": "visitor_registry", "entry_mode": "visitor_followup"}, None, [])["label"] == "Iglesia · registro de visitante"
    assert origin_of({"source": "legacy_people"}, None, [])["kind"] == "manual_antiguo"
    assert origin_of(None, {"campaign_name": "Centro"}, [])["kind"] == "invasion"
    assert origin_of(None, None, [{"visitor_number": 4}])["kind"] == "iglesia"
