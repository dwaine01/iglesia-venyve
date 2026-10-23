"""Etapa 4 — Supervisión de arriba hacia abajo (C9/A14-A16/E), migración C11
y utilidades de borrado administrativo (preview + historial).

Cubre:
- Alcance: pastor ve global; líder ve solo su rama; mentor ve solo lo suyo
  (overview/groups/mentors/disciples/indicators).
- Semáforo y umbrales: lectura abierta, escritura solo pastoral/coordinador.
- Indicador "actividades vencidas" abre el detalle exacto que lo explica.
- Delete-preview de campaña/grupo (conteo antes de borrar) y bloqueo si el
  grupo tiene procesos de Consolidación activos debajo.
- Historial de borrados (`/api/admin/audit/deletions`) solo pastoral.
- C11: diagnóstico no destructivo + aplicación idempotente del único caso
  seguro (mentor con una sola rama activa).
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "SupervisionEtapa4Pass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA", "apellido": label, "idempotency_key": f"qa:supervision:etapa4:{uuid.uuid4()}",
        "version": 1, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None) -> tuple[str, str]:
    user_id = ObjectId()
    slug = label.lower().replace(" ", ".")
    email = f"qa.supervision.etapa4.{slug}.{uuid.uuid4().hex[:6]}@example.com"
    defaults = access_defaults_for_role(role)
    defaults["capabilities"] = sorted(set(defaults.get("capabilities", []) + (capabilities or [])))
    document = {
        "_id": user_id, "nombre": f"QA {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "is_active": True, "token_version": 1, "created_at": datetime.now(timezone.utc), **defaults,
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


async def make_front_group(name: str, leader_pid: str, leader_user_id: str, parent_id: str | None = None) -> str:
    front_group_id = str(uuid.uuid4())
    ancestors = []
    if parent_id:
        parent = await server.db.front_groups.find_one({"front_group_id": parent_id}, {"_id": 0, "ancestor_group_ids": 1})
        ancestors = [parent_id, *(parent or {}).get("ancestor_group_ids", [])]
    await server.db.front_groups.insert_one({
        "_id": front_group_id, "front_group_id": front_group_id, "name": name, "parent_group_id": parent_id,
        "ancestor_group_ids": ancestors, "depth": len(ancestors), "status": "active", "primary_leader_person_id": leader_pid,
        "created_by_user_id": leader_user_id, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    assignment_id = str(uuid.uuid4())
    await server.db.front_group_assignments.insert_one({
        "_id": assignment_id, "assignment_id": assignment_id, "front_group_id": front_group_id, "person_id": leader_pid, "role": "leader",
        "active": True, "created_at": datetime.now(timezone.utc),
    })
    return front_group_id


async def add_member(front_group_id: str, person_id: str, role: str = "mentor") -> None:
    assignment_id = str(uuid.uuid4())
    await server.db.front_group_assignments.insert_one({
        "_id": assignment_id, "assignment_id": assignment_id, "front_group_id": front_group_id, "person_id": person_id, "role": role,
        "active": True, "created_at": datetime.now(timezone.utc),
    })


async def make_enrollment(person_id: str, mentor_pid: str, front_group_id: str | None, decision_status: str = "accepted", source: str | None = None, source_id: str | None = None, current_stage_key: str = "mcd") -> str:
    enrollment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await server.db.process_enrollments.insert_one({
        "_id": enrollment_id, "enrollment_id": enrollment_id, "process_key": "consolidation", "person_id": person_id,
        "mentor_person_id": mentor_pid, "front_group_id": front_group_id, "decision_status": decision_status,
        "current_stage_key": current_stage_key, "status": "active", "source": source, "source_id": source_id,
        "created_at": now, "updated_at": now,
    })
    return enrollment_id


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])
    await server.db.supervision_thresholds.delete_many({"_id": {"$ne": "default"}})
    await server.db.migration_runs.delete_many({"migration": "c11", "detail": {"$regex": "etapa4-c11-qa"}})


@pytest.mark.asyncio
async def test_scope_permissions_global_branch_self():
    await cleanup()
    pastor_pid = await create_person("Pastor Scope")
    leader_pid = await create_person("Lider Scope")
    other_leader_pid = await create_person("Lider Otro Scope")
    mentor_pid = await create_person("Mentor Scope")
    pastor_uid, pastor_email = await create_user("Pastor Scope", "pastor", pastor_pid)
    _, leader_email = await create_user("Lider Scope", "lider", leader_pid)
    _, other_leader_email = await create_user("Lider Otro Scope", "lider", other_leader_pid)
    _, mentor_email = await create_user("Mentor Scope", "persona", mentor_pid)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    leader_client, leader_headers = await auth_client(leader_email)
    other_client, other_headers = await auth_client(other_leader_email)
    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        group_a = await make_front_group("Rama A Scope", leader_pid, pastor_uid)
        group_b = await make_front_group("Rama B Scope", other_leader_pid, pastor_uid)
        await add_member(group_a, mentor_pid, role="mentor")
        target_person = await create_person("Discipulo Scope")
        other_person = await create_person("Discipulo Otra Rama")
        await make_enrollment(target_person, mentor_pid, group_a)
        await make_enrollment(other_person, other_leader_pid, group_b)

        pastor_overview = await pastor_client.get("/api/supervision/overview", headers=pastor_headers)
        assert pastor_overview.status_code == 200
        assert pastor_overview.json()["scope_level"] == "global"

        leader_overview = await leader_client.get("/api/supervision/overview", headers=leader_headers)
        assert leader_overview.status_code == 200
        assert leader_overview.json()["scope_level"] == "branch"

        leader_disciples = await leader_client.get("/api/supervision/disciples", headers=leader_headers)
        ids_seen = {item["person_id"] for item in leader_disciples.json()["items"]}
        assert target_person in ids_seen and other_person not in ids_seen, "el líder debe ver solo su rama, nunca la ajena"

        forbidden = await leader_client.get(f"/api/supervision/groups?front_group_id={group_b}", headers=leader_headers)
        assert forbidden.status_code == 403, "un líder no puede consultar un Grupo Frontal fuera de su rama"

        mentor_overview = await mentor_client.get("/api/supervision/overview", headers=mentor_headers)
        assert mentor_overview.status_code == 200
        assert mentor_overview.json()["scope_level"] == "self"
        mentor_disciples = await mentor_client.get("/api/supervision/disciples", headers=mentor_headers)
        mentor_ids_seen = {item["person_id"] for item in mentor_disciples.json()["items"]}
        assert target_person in mentor_ids_seen and other_person not in mentor_ids_seen, "el mentor solo ve lo suyo"
    finally:
        await pastor_client.aclose(); await leader_client.aclose(); await other_client.aclose(); await mentor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_indicator_detail_explains_overdue_activities():
    await cleanup()
    pastor_pid = await create_person("Pastor Indicador")
    mentor_pid = await create_person("Mentor Indicador")
    _, pastor_email = await create_user("Pastor Indicador", "pastor", pastor_pid)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    try:
        person_id = await create_person("Discipulo Vencido")
        enrollment_id = await make_enrollment(person_id, mentor_pid, None)
        past_date = (datetime.now(timezone.utc) - timedelta(days=5)).date().isoformat()
        activity_id = str(uuid.uuid4())
        await server.db.consolidation_activities.insert_one({
            "_id": activity_id, "activity_id": activity_id, "enrollment_id": enrollment_id, "stage_key": "mcd",
            "scheduled_date": past_date, "status": "pending", "created_at": datetime.now(timezone.utc),
        })
        overview = await pastor_client.get("/api/supervision/overview", headers=pastor_headers)
        assert overview.json()["consolidation"]["activities_overdue"] >= 1

        detail = await pastor_client.get("/api/supervision/indicators/activities_overdue", headers=pastor_headers)
        assert detail.status_code == 200
        ids = [item["enrollment_id"] for item in detail.json()["items"]]
        assert enrollment_id in ids, "el indicador debe abrir el detalle exacto que lo explica"
    finally:
        await pastor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_thresholds_read_open_write_pastoral_only():
    await cleanup()
    pastor_pid = await create_person("Pastor Umbral")
    leader_pid = await create_person("Lider Umbral")
    _, pastor_email = await create_user("Pastor Umbral", "pastor", pastor_pid)
    _, leader_email = await create_user("Lider Umbral", "lider", leader_pid)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    leader_client, leader_headers = await auth_client(leader_email)
    try:
        read = await leader_client.get("/api/supervision/thresholds", headers=leader_headers)
        assert read.status_code == 200
        assert read.json()["mentor_inactivity_days"]["status"] == "propuesta"

        denied = await leader_client.put("/api/supervision/thresholds/mentor_inactivity_days", json={"value": 3}, headers=leader_headers)
        assert denied.status_code == 403

        updated = await pastor_client.put("/api/supervision/thresholds/mentor_inactivity_days", json={"value": 3}, headers=pastor_headers)
        assert updated.status_code == 200
        assert updated.json()["mentor_inactivity_days"]["value"] == 3
        assert updated.json()["mentor_inactivity_days"]["status"] == "confirmado"
    finally:
        await pastor_client.aclose(); await leader_client.aclose()
        await server.db.supervision_thresholds.update_one({"_id": "default"}, {"$set": {"mentor_inactivity_days": {"value": 7, "label": "Días sin registrar ninguna visita para marcar al mentor en rojo", "status": "propuesta"}}})
        await cleanup()


@pytest.mark.asyncio
async def test_campaign_and_front_group_delete_preview_and_audit_history():
    await cleanup()
    pastor_pid = await create_person("Pastor Preview")
    leader_pid = await create_person("Lider Preview")
    pastor_uid, pastor_email = await create_user("Pastor Preview", "pastor", pastor_pid)
    _, leader_email = await create_user("Lider Preview", "lider", leader_pid)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    leader_client, leader_headers = await auth_client(leader_email)
    try:
        campaign = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasión Preview E4", "location": "Sector Preview", "start_date": "2026-09-01", "end_date": "2026-09-02", "assigned_mentors": []},
            headers=pastor_headers,
        )
        assert campaign.status_code == 201, campaign.text
        campaign_id = campaign.json()["campaign_id"]
        preview = await pastor_client.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/delete-preview", headers=pastor_headers)
        assert preview.status_code == 200
        assert preview.json() == {"campaign_name": "Invasión Preview E4", "households": 0, "visits": 0, "attempts": 0, "participations": 0}
        denied_preview = await leader_client.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/delete-preview", headers=leader_headers)
        assert denied_preview.status_code == 403

        group_id = await make_front_group("Rama Preview E4", leader_pid, pastor_uid)
        blocked_person = await create_person("Discipulo Bloqueo")
        await make_enrollment(blocked_person, leader_pid, group_id)
        await server.db.process_enrollments.update_one({"front_group_id": group_id}, {"$set": {"status": "active"}})
        blocked_preview = await pastor_client.get(f"/api/front-groups/{group_id}/delete-preview", headers=pastor_headers)
        assert blocked_preview.status_code == 200
        assert blocked_preview.json()["blocked"] is True
        assert blocked_preview.json()["active_process_count"] == 1

        delete_blocked = await pastor_client.request("DELETE", f"/api/front-groups/{group_id}", json={"reason": "prueba E4 bloqueo"}, headers=pastor_headers)
        assert delete_blocked.status_code == 409

        await server.db.process_enrollments.delete_many({"front_group_id": group_id})
        unblocked_preview = await pastor_client.get(f"/api/front-groups/{group_id}/delete-preview", headers=pastor_headers)
        assert unblocked_preview.json()["blocked"] is False
        assert unblocked_preview.json()["assignments"] == 1

        deleted = await pastor_client.request("DELETE", f"/api/front-groups/{group_id}", json={"reason": "prueba E4 borrado"}, headers=pastor_headers)
        assert deleted.status_code == 200

        deleted_campaign = await pastor_client.request("DELETE", f"/api/mentorship/outreach/campaigns/{campaign_id}", json={"reason": "prueba E4 borrado campaña"}, headers=pastor_headers)
        assert deleted_campaign.status_code == 200

        history = await pastor_client.get("/api/admin/audit/deletions", headers=pastor_headers)
        assert history.status_code == 200
        collections_seen = {item["collection"] for item in history.json()["items"][:10]}
        assert "front_groups" in collections_seen and "outreach_campaigns" in collections_seen

        denied_history = await leader_client.get("/api/admin/audit/deletions", headers=leader_headers)
        assert denied_history.status_code == 403
    finally:
        await pastor_client.aclose(); await leader_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_migration_c11_diagnose_and_idempotent_apply():
    await cleanup()
    pastor_pid = await create_person("Pastor C11")
    mentor_pid = await create_person("Mentor C11")
    leader_pid = await create_person("Lider C11")
    pastor_uid, pastor_email = await create_user("Pastor C11", "pastor", pastor_pid)
    _, leader_email = await create_user("Lider C11", "lider", leader_pid)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    leader_client, leader_headers = await auth_client(leader_email)
    try:
        group_id = await make_front_group("Rama C11", mentor_pid, pastor_uid)
        person_id = await create_person("Discipulo C11")
        enrollment_id = await make_enrollment(person_id, mentor_pid, None, source="mentorship_outreach", source_id=str(uuid.uuid4()))

        denied = await leader_client.get("/api/admin/migrations/c11?mode=diagnose", headers=leader_headers)
        assert denied.status_code == 403

        diagnosis = await pastor_client.get("/api/admin/migrations/c11?mode=diagnose", headers=pastor_headers)
        assert diagnosis.status_code == 200
        rows = {item["enrollment_id"]: item for item in diagnosis.json()["enrollments_missing_front_group"]}
        assert enrollment_id in rows
        assert rows[enrollment_id]["proposed_front_group_id"] == group_id, "debe proponer la única rama activa del mentor"

        applied = await pastor_client.get("/api/admin/migrations/c11?mode=apply", headers=pastor_headers)
        assert applied.status_code == 200
        assert applied.json()["enrollments_fixed"] >= 1
        fixed = await server.db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0, "front_group_id": 1})
        assert fixed["front_group_id"] == group_id

        second_run = await pastor_client.get("/api/admin/migrations/c11?mode=apply", headers=pastor_headers)
        assert second_run.status_code == 200
        still = await server.db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0, "front_group_id": 1})
        assert still["front_group_id"] == group_id, "segunda corrida es idempotente: no debe romper el valor ya corregido"
    finally:
        await pastor_client.aclose(); await leader_client.aclose()
        await cleanup()
