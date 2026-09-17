import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from qa_demo_cleanup import delete_qa_artifacts


PASSWORD = "JourneyV2Pass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA",
        "apellido": label,
        "idempotency_key": f"qa:journey:{uuid.uuid4()}",
        "version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None) -> tuple[str, str]:
    user_id = ObjectId(); slug = label.lower().replace(" ", "."); email = f"qa.journey.{slug}.{uuid.uuid4().hex[:6]}@example.com"
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


async def complete_stage(client: AsyncClient, headers: dict, enrollment_id: str, stage_key: str):
    detail = (await client.get(f"/api/processes/consolidation/{enrollment_id}", headers=headers)).json()
    stage = next(item for item in detail["stages"] if item["stage_key"] == stage_key)
    for task in stage.get("tasks", []):
        if not task.get("completed"):
            response = await client.put(f"/api/processes/enrollments/{enrollment_id}/stages/{stage_key}/tasks/{task['task_id']}", json={"completed": True}, headers=headers)
            assert response.status_code == 200, response.text
    response = await client.put(f"/api/processes/enrollments/{enrollment_id}/stages/{stage_key}", json={"status": "completed"}, headers=headers)
    assert response.status_code == 200, response.text


async def cleanup():
    await delete_qa_artifacts(server.db)


@pytest.mark.asyncio
async def test_core_access_contract_persists_and_revokes_delegated_capabilities():
    await cleanup()
    _, pastor_email = await create_user("Access Pastor", "pastor")
    target_id, _ = await create_user("Access Secretary", "lider")
    client, headers = await auth_client(pastor_email)
    try:
        users = await client.get("/api/core/governance/users", headers=headers)
        assert users.status_code == 200
        assert any(item["user_id"] == target_id for item in users.json()["items"])
        payload = {
            "access_level": "secretario",
            "is_active": True,
            "privilege_groups": ["membership"],
            "capabilities": ["membership.documents.manage", "membership.acceptance.manage", "leadership.promote"],
        }
        saved = await client.put(f"/api/core/governance/users/{target_id}/access", json=payload, headers=headers)
        assert saved.status_code == 200, saved.text
        assert saved.json()["access_level"] == "secretario"
        assert "membership.acceptance.manage" in saved.json()["capabilities"]
        revoked = await client.put(f"/api/core/governance/users/{target_id}/access", json={**payload, "capabilities": []}, headers=headers)
        assert revoked.status_code == 200
        assert "membership.documents.manage" not in revoked.json()["capabilities"]
        stored = await server.db.users.find_one({"_id": ObjectId(target_id)})
        assert stored["rol"] == "lider"
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_four_entry_modes_preserve_origin_and_converge():
    await cleanup()
    _, pastor_email = await create_user("Entry Pastor", "pastor")
    mentor_person_id = await create_person("Mentor Entradas")
    await create_user("Mentor Entradas", "lider", mentor_person_id)
    client, headers = await auth_client(pastor_email)
    try:
        expected = {"complete_cycle": "prayer", "direct_church": "mcd", "cell": "mcd", "visitor_followup": "visitor_followup"}
        for mode, stage in expected.items():
            person_id = await create_person(f"Entrada {mode}")
            payload = {"person_id": person_id, "entry_mode": mode, "mentor_person_id": None if mode == "visitor_followup" else mentor_person_id, "source_cell_id": "CELL-QA-01" if mode == "cell" else None, "next_followup_at": datetime.now(timezone.utc).isoformat() if mode == "visitor_followup" else None}
            response = await client.post("/api/processes/consolidation/intakes", json=payload, headers=headers)
            assert response.status_code == 201, response.text
            assert response.json()["entry_mode"] == mode
            assert response.json()["current_stage_key"] == stage
            if mode == "direct_church":
                premature_document = await client.post(f"/api/membership/persons/{person_id}/documents/certificate/issue", json={}, headers=headers)
                assert premature_document.status_code == 409
                assert "Carta de Membresía" in premature_document.json()["detail"]
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_fiesta_membership_retreat_discipleship_and_scoped_leadership():
    await cleanup()
    _, pastor_email = await create_user("Flow Pastor", "pastor")
    mentor_person_id = await create_person("Mentor LBS")
    await create_user("Mentor LBS", "lider", mentor_person_id)
    candidate_person_id = await create_person("Candidato Integral")
    candidate_user_id, _ = await create_user("Candidato Integral", "persona", candidate_person_id)
    front_leader_person_id = await create_person("Lider Frontal")
    _, front_leader_email = await create_user("Lider Frontal", "lider", front_leader_person_id, ["leadership.promote"])
    client, headers = await auth_client(pastor_email)
    try:
        group = await client.post("/api/front-groups", json={"name": "QA Grupo Frontal Integral", "description": "E2E", "linked_structures": []}, headers=headers)
        assert group.status_code == 201, group.text
        group_id = group.json()["front_group_id"]
        assert (await client.post(f"/api/front-groups/{group_id}/leader", json={"person_id": front_leader_person_id, "reason": "Responsabilidad E2E"}, headers=headers)).status_code == 200
        assert (await client.post(f"/api/front-groups/{group_id}/members", json={"person_id": candidate_person_id, "role": "team", "notes": "Candidato"}, headers=headers)).status_code == 201
        qualification = await client.put(f"/api/front-groups/mentors/{mentor_person_id}/qualification", json={"front_group_id": group_id, "can_teach_lbs": True}, headers=headers)
        assert qualification.status_code == 200, qualification.text
        intake = await client.post("/api/processes/consolidation/intakes", json={"person_id": candidate_person_id, "entry_mode": "direct_church", "front_group_id": group_id, "mentor_person_id": mentor_person_id}, headers=headers)
        assert intake.status_code == 201, intake.text
        enrollment_id = intake.json()["enrollment_id"]
        await complete_stage(client, headers, enrollment_id, "mcd")
        await complete_stage(client, headers, enrollment_id, "npt")
        evaluated = await client.post(f"/api/processes/consolidation/{enrollment_id}/mentor/evaluate", json={}, headers=headers)
        assert evaluated.status_code == 200 and evaluated.json()["qualified_for_lbs"] is True
        accepted = await client.post(f"/api/processes/consolidation/{enrollment_id}/membership-acceptance", json={"notes": "Carta firmada en Fiesta"}, headers=headers)
        assert accepted.status_code == 200, accepted.text
        member_number = accepted.json()["membership"]["member_number"]
        assert member_number != candidate_person_id
        assert accepted.json()["membership"]["certificate_delivery_status"] == "pending_retreat"
        repeated_acceptance = await client.post(f"/api/processes/consolidation/{enrollment_id}/membership-acceptance", json={"notes": "Reintento idempotente"}, headers=headers)
        assert repeated_acceptance.status_code == 200
        assert repeated_acceptance.json()["created"] is False
        assert repeated_acceptance.json()["membership"]["member_number"] == member_number
        assert await server.db.membership_number_registry.find_one({"member_number": member_number, "person_id": candidate_person_id})
        await complete_stage(client, headers, enrollment_id, "welcome_party")
        for stage in ["lbs_1", "lbs_2", "lbs_3"]:
            await complete_stage(client, headers, enrollment_id, stage)
        closed = await client.post(f"/api/processes/consolidation/{enrollment_id}/retreat-close", json={"certificate_delivery_status": "pending_exception", "card_delivery_status": "not_applicable", "delivery_notes": "Entrega documentada como pendiente"}, headers=headers)
        assert closed.status_code == 200, closed.text
        assert closed.json()["consolidation_status"] == "completed"
        assert closed.json()["discipleship"]["process_key"] == "discipleship"
        discipleship_id = closed.json()["discipleship"]["enrollment_id"]
        await server.db.process_enrollments.update_one({"enrollment_id": discipleship_id}, {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}})
        await server.db.cap_assessments.insert_one({"_id": str(uuid.uuid4()), "person_id": candidate_person_id, "status": "completed", "selected_door_key": "service"})
        await server.db.ministry_assignments.insert_one({"_id": str(uuid.uuid4()), "person_id": candidate_person_id, "activo": True, "ministry_id": "qa-service", "role": "server"})

        leader_client, leader_headers = await auth_client(front_leader_email)
        try:
            outsider_person_id = await create_person("Fuera de Scope")
            outside = await leader_client.get(f"/api/leadership/candidates/{outsider_person_id}/eligibility?front_group_id={group_id}", headers=leader_headers)
            assert outside.status_code == 403
            eligibility = await leader_client.get(f"/api/leadership/candidates/{candidate_person_id}/eligibility?front_group_id={group_id}", headers=leader_headers)
            assert eligibility.status_code == 200, eligibility.text
            assert eligibility.json()["eligible"] is True
            promoted = await leader_client.post(f"/api/leadership/candidates/{candidate_person_id}/promote", json={"front_group_id": group_id, "observations": "Requisitos revisados y aprobados"}, headers=leader_headers)
            assert promoted.status_code == 201, promoted.text
            assert promoted.json()["requirements_snapshot"]
            duplicate = await leader_client.post(f"/api/leadership/candidates/{candidate_person_id}/promote", json={"front_group_id": group_id, "observations": "No debe duplicarse"}, headers=leader_headers)
            assert duplicate.status_code == 409
        finally:
            await leader_client.aclose()
        candidate_user = await server.db.users.find_one({"_id": ObjectId(candidate_user_id)})
        assert candidate_user["rol"] == "persona"
        assert await server.db.person_leadership_status.find_one({"person_id": candidate_person_id, "status": "leader"})
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_leadership_requirements_are_configurable_and_soft_removable():
    await cleanup()
    _, pastor_email = await create_user("Requirements Pastor", "pastor")
    client, headers = await auth_client(pastor_email)
    try:
        created = await client.post("/api/leadership/requirements", json={"name": "QA Requisito configurable", "description": "Evidencia manual", "source_type": "manual", "required": False, "active": True, "order": 50}, headers=headers)
        assert created.status_code == 201, created.text
        requirement_id = created.json()["requirement_id"]
        updated = await client.put(f"/api/leadership/requirements/{requirement_id}", json={"name": "QA Requisito actualizado", "required": True, "order": 51}, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["name"] == "QA Requisito actualizado"
        removed = await client.delete(f"/api/leadership/requirements/{requirement_id}", headers=headers)
        assert removed.status_code == 200
        stored = await server.db.leadership_requirement_catalog.find_one({"requirement_id": requirement_id})
        assert stored["active"] is False
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_welcome_party_blocks_unqualified_mentor_until_formal_transfer():
    await cleanup()
    _, pastor_email = await create_user("Transfer Pastor", "pastor")
    old_mentor_id = await create_person("Mentor No LBS")
    await create_user("Mentor No LBS", "lider", old_mentor_id)
    new_mentor_id = await create_person("Mentor Calificado")
    await create_user("Mentor Calificado", "lider", new_mentor_id)
    person_id = await create_person("Transferencia Formal")
    client, headers = await auth_client(pastor_email)
    try:
        group = await client.post("/api/front-groups", json={"name": "QA Grupo Transferencias", "linked_structures": []}, headers=headers)
        group_id = group.json()["front_group_id"]
        qualified = await client.put(f"/api/front-groups/mentors/{new_mentor_id}/qualification", json={"front_group_id": group_id, "can_teach_lbs": True}, headers=headers)
        assert qualified.status_code == 200
        intake = await client.post("/api/processes/consolidation/intakes", json={"person_id": person_id, "entry_mode": "direct_church", "front_group_id": group_id, "mentor_person_id": old_mentor_id}, headers=headers)
        enrollment_id = intake.json()["enrollment_id"]
        await complete_stage(client, headers, enrollment_id, "mcd")
        await complete_stage(client, headers, enrollment_id, "npt")
        evaluated = await client.post(f"/api/processes/consolidation/{enrollment_id}/mentor/evaluate", json={}, headers=headers)
        assert evaluated.status_code == 200 and evaluated.json()["qualified_for_lbs"] is False
        assert (await client.post(f"/api/processes/consolidation/{enrollment_id}/membership-acceptance", json={}, headers=headers)).status_code == 200
        detail = (await client.get(f"/api/processes/consolidation/{enrollment_id}", headers=headers)).json()
        welcome = next(item for item in detail["stages"] if item["stage_key"] == "welcome_party")
        for task in welcome["tasks"]:
            if not task["completed"]:
                await client.put(f"/api/processes/enrollments/{enrollment_id}/stages/welcome_party/tasks/{task['task_id']}", json={"completed": True}, headers=headers)
        blocked = await client.put(f"/api/processes/enrollments/{enrollment_id}/stages/welcome_party", json={"status": "completed"}, headers=headers)
        assert blocked.status_code == 409
        transferred = await client.post(f"/api/processes/consolidation/{enrollment_id}/mentor/transfer", json={"new_mentor_person_id": new_mentor_id, "reason": "Mentor anterior no autorizado para LBS"}, headers=headers)
        assert transferred.status_code == 200, transferred.text
        history = transferred.json()["enrollment"]["mentor_assignments"]
        assert len(history) == 2
        assert any(item["previous_mentor_person_id"] == old_mentor_id for item in history if item["active"])
        completed = await client.put(f"/api/processes/enrollments/{enrollment_id}/stages/welcome_party", json={"status": "completed"}, headers=headers)
        assert completed.status_code == 200, completed.text
    finally:
        await client.aclose(); await cleanup()