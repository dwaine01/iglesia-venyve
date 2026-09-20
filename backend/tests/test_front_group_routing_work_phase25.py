"""Fases 2-5: rotación, autoridad de Consolidación, trabajo descendente y continuidad."""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from qa_demo_cleanup import delete_qa_artifacts, qa_preview


PASSWORD = "RoutingWork2026!"
CELL_ID = "CELL-QA-ROUTING"


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])
    await server.db.cells.delete_many({"cell_id": CELL_ID})


async def person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA", "apellido": label, "search_key": f"qa {label}".lower(),
        "idempotency_key": f"qa:routing:{uuid.uuid4()}", "version": 1,
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def user(label: str, role: str, person_id: str | None = None, capabilities=None) -> str:
    user_id = ObjectId(); email = f"qa.routing.{uuid.uuid4().hex[:8]}@example.com"
    defaults = access_defaults_for_role(role)
    if capabilities is not None: defaults["capabilities"] = capabilities
    await server.db.users.insert_one({
        "_id": user_id, "nombre": f"QA {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "is_active": True, "token_version": 1,
        "created_at": datetime.now(timezone.utc), **defaults,
        **({"person_id": person_id} if person_id else {}),
    })
    return email


async def auth(email: str) -> tuple[AsyncClient, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


@pytest.mark.asyncio
async def test_rotation_keeps_cell_origin_and_consolidation_confirms_work_distribution():
    await cleanup()
    pastor_email = await user("Pastora Rotación", "pastor")
    coordinator_person = await person("Coordinación")
    coordinator_email = await user("Coordinación", "lider", coordinator_person, ["processes.read", "consolidation.assign"])
    josue_person = await person("Josué")
    josue_email = await user("Josué", "lider", josue_person)
    responsible_person = await person("Responsable Final")
    responsible_email = await user("Responsable Final", "persona", responsible_person)
    first_person = await person("Conversión Uno")
    second_person = await person("Conversión Dos")
    third_person = await person("Conversión Tres")
    await server.db.cells.insert_one({"_id": CELL_ID, "cell_id": CELL_ID, "name": "QA Célula origen", "status": "active", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})

    pastor, ph = await auth(pastor_email); coordinator, ch = await auth(coordinator_email)
    josue, jh = await auth(josue_email); responsible, rh = await auth(responsible_email)
    try:
        root = (await pastor.post("/api/front-groups", json={"name": "QA Raíz Operativa"}, headers=ph)).json()
        josue_group = (await pastor.post("/api/front-groups", json={"name": "QA Grupo Josué", "parent_group_id": root["front_group_id"]}, headers=ph)).json()
        other_group = (await pastor.post("/api/front-groups", json={"name": "QA Grupo Alterno", "parent_group_id": root["front_group_id"]}, headers=ph)).json()
        subbranch = (await pastor.post("/api/front-groups", json={"name": "QA Subrama Josué", "parent_group_id": josue_group["front_group_id"]}, headers=ph)).json()
        assert (await pastor.post(f"/api/front-groups/{josue_group['front_group_id']}/leader", json={"person_id": josue_person, "reason": "Responsabilidad de rama"}, headers=ph)).status_code == 200
        assert (await pastor.post(f"/api/front-groups/{subbranch['front_group_id']}/members", json={"person_id": responsible_person, "role": "member"}, headers=ph)).status_code == 201

        policy = await pastor.put("/api/front-group-routing/policies/qa-weekly", json={
            "root_group_id": root["front_group_id"],
            "ordered_group_ids": [josue_group["front_group_id"], other_group["front_group_id"]],
            "timezone_name": "America/Santo_Domingo", "week_start_day": 6, "active": True,
        }, headers=ph)
        assert policy.status_code == 200, policy.text
        overview = await coordinator.get("/api/front-group-routing/overview?policy_id=qa-weekly", headers=ch)
        assert overview.status_code == 200, overview.text
        assert overview.json()["rotation"]["week"]["selected_group_id"] == josue_group["front_group_id"]

        origin_only = await pastor.put(f"/api/front-group-routing/cell-links/{CELL_ID}", json={"front_group_id": other_group["front_group_id"], "route_conversions": False, "reason": "Solo conservar procedencia"}, headers=ph)
        assert origin_only.status_code == 200
        batch = await coordinator.post("/api/processes/consolidation/batch-assign", json={
            "items": [{"person_id": first_person, "entry_mode": "cell", "source_cell_id": CELL_ID}],
            "front_group_id": josue_group["front_group_id"], "routing_policy_id": "qa-weekly",
            "reason": "Confirmación semanal de Consolidación",
        }, headers=ch)
        assert batch.status_code == 200, batch.text
        assert batch.json()["assigned"] == 1
        enrollment_id = batch.json()["items"][0]["enrollment_id"]
        enrollment = await server.db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
        assert enrollment["source_cell_id"] == CELL_ID
        assert enrollment["front_group_id"] == josue_group["front_group_id"]
        assert enrollment["routing_decision"]["mode"] == "weekly_rotation"

        work = await josue.get(f"/api/front-group-work?group_id={josue_group['front_group_id']}", headers=jh)
        assert work.status_code == 200 and work.json()["total"] == 1, work.text
        assignment_id = work.json()["items"][0]["assignment_id"]
        delegated = await josue.post(f"/api/front-group-work/{assignment_id}/delegate", json={"assigned_group_id": subbranch["front_group_id"], "assigned_person_id": responsible_person, "reason": "Delegación a responsable final"}, headers=jh)
        assert delegated.status_code == 201, delegated.text
        own_work = await responsible.get("/api/front-group-work", headers=rh)
        assert own_work.status_code == 200 and own_work.json()["total"] == 1
        final_assignment_id = own_work.json()["items"][0]["assignment_id"]
        assert (await responsible.put(f"/api/front-group-work/{final_assignment_id}/status", json={"status": "accepted"}, headers=rh)).status_code == 200
        assert (await responsible.put(f"/api/front-group-work/{final_assignment_id}/status", json={"status": "completed", "note": "Contacto ejecutado"}, headers=rh)).status_code == 200

        retained = await pastor.put(f"/api/front-group-routing/cell-links/{CELL_ID}", json={"front_group_id": other_group["front_group_id"], "route_conversions": True, "reason": "Conversión permanece con el Grupo vinculado"}, headers=ph)
        assert retained.status_code == 200
        linked_batch = await coordinator.post("/api/processes/consolidation/batch-assign", json={
            "items": [{"person_id": second_person, "entry_mode": "cell", "source_cell_id": CELL_ID}],
            "front_group_id": other_group["front_group_id"], "routing_policy_id": "qa-weekly",
            "reason": "Confirmación de política celular",
        }, headers=ch)
        linked_enrollment = await server.db.process_enrollments.find_one({"enrollment_id": linked_batch.json()["items"][0]["enrollment_id"]}, {"_id": 0})
        assert linked_enrollment["routing_decision"]["mode"] == "cell_policy"
        assert linked_enrollment["routing_decision"]["manual_override"] is False

        override = await coordinator.post("/api/processes/consolidation/batch-assign", json={
            "items": [{"person_id": third_person, "entry_mode": "cell", "source_cell_id": CELL_ID}],
            "front_group_id": josue_group["front_group_id"], "routing_policy_id": "qa-weekly",
            "reason": "Cobertura especial autorizada por Consolidación",
        }, headers=ch)
        override_enrollment = await server.db.process_enrollments.find_one({"enrollment_id": override.json()["items"][0]["enrollment_id"]}, {"_id": 0})
        assert override_enrollment["routing_decision"]["manual_override"] is True
        assert override_enrollment["routing_decision"]["reason"] == "Cobertura especial autorizada por Consolidación"

        await server.db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {"status": "paused"}})
        resumed = await coordinator.post("/api/processes/consolidation/batch-assign", json={
            "items": [{"person_id": first_person, "entry_mode": "cell", "source_cell_id": CELL_ID}],
            "front_group_id": josue_group["front_group_id"], "routing_policy_id": "qa-weekly",
            "reason": "La Persona regresó; conservar avance y Grupo",
        }, headers=ch)
        assert resumed.json()["assigned"] == 1
        resumed_doc = await server.db.process_enrollments.find_one({"person_id": first_person, "process_key": "consolidation"}, {"_id": 0})
        assert resumed_doc["enrollment_id"] == enrollment_id
        assert resumed_doc["status"] == "active" and resumed_doc["reactivation_count"] == 1
        assert resumed_doc["source_cell_id"] == CELL_ID
        assert await server.db.process_enrollments.count_documents({"person_id": first_person, "process_key": "consolidation"}) == 1

        assert (await coordinator.get("/api/care/dashboard", headers=ch)).status_code == 403
    finally:
        await pastor.aclose(); await coordinator.aclose(); await josue.aclose(); await responsible.aclose(); await cleanup()