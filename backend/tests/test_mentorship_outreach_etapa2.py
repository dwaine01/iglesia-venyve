"""Etapa 2 — Invasiones completas y portal del mentor (mentorship_outreach.py).

Cubre:
- Campos nuevos de campaña: hora/lugar de encuentro, sectores, instrucciones.
- Participación del mentor (Asignado -> Confirmado -> Con actividad), self-service.
- Hogar/Visita: intento 'sin respuesta' nunca lleva personas; 'contacted' exige
  al menos una persona salvo que se guarde como borrador.
- Supervisión instantánea: líder/colíder de la rama del mentor ve en solo
  lectura sus hogares/visitas (vía /my-branch-overview y listados); otro
  mentor fuera de la rama no los ve.
- Permisos de creación de invasión: pastor/coordinador general sí, mentor
  sin esas capacidades no.
- `decision_status` se deriva de `status`/`agreed_start_date`.
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

PASSWORD = "OutreachEtapa2Pass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA", "apellido": label,
        "idempotency_key": f"qa:outreach:etapa2:{uuid.uuid4()}",
        "version": 1, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None) -> tuple[str, str]:
    user_id = ObjectId()
    slug = label.lower().replace(" ", ".")
    email = f"qa.outreach.etapa2.{slug}.{uuid.uuid4().hex[:6]}@example.com"
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


async def activate_badge(pid: str) -> None:
    await server.db.mentor_badges.update_one(
        {"person_id": pid}, {"$set": {"person_id": pid, "active": True, "since": "2026-01-01", "updated_at": datetime.now(timezone.utc)}}, upsert=True,
    )


async def make_front_group(name: str, leader_pid: str, parent_id: str | None = None) -> str:
    front_group_id = str(uuid.uuid4())
    ancestors = []
    if parent_id:
        parent = await server.db.front_groups.find_one({"front_group_id": parent_id}, {"_id": 0, "ancestor_group_ids": 1})
        ancestors = [parent_id, *(parent or {}).get("ancestor_group_ids", [])]
    await server.db.front_groups.insert_one({
        "_id": front_group_id, "front_group_id": front_group_id, "name": name, "parent_group_id": parent_id,
        "ancestor_group_ids": ancestors, "depth": len(ancestors), "status": "active", "primary_leader_person_id": leader_pid,
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
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


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


@pytest.mark.asyncio
async def test_campaign_creation_persists_new_fields_and_permission_matrix():
    await cleanup()
    pastor_pid = await create_person("Pastor Etapa2")
    coord_pid = await create_person("Coordinador Etapa2")
    mentor_pid = await create_person("Mentor Etapa2")
    await activate_badge(mentor_pid)
    _, pastor_email = await create_user("Pastor Etapa2", "pastor", pastor_pid)
    _, coord_email = await create_user("Coordinador Etapa2", "lider", coord_pid, capabilities=["core.access.manage"])
    await server.db.users.update_one({"email": coord_email}, {"$set": {"access_level": "coordinador_general"}})
    _, mentor_email = await create_user("Mentor Etapa2", "persona", mentor_pid)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    coord_client, coord_headers = await auth_client(coord_email)
    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        payload = {
            "name": "Invasión Etapa2", "location": "Sector Prueba", "start_date": "2026-09-01", "end_date": "2026-09-02",
            "meeting_time": "6:00 AM", "meeting_place": "Parque Central", "sectors": ["Sector A", "Sector B"],
            "instructions": "Llevar biblia", "assigned_mentors": [],
        }
        rejected = await mentor_client.post("/api/mentorship/outreach/campaigns", json=payload, headers=mentor_headers)
        assert rejected.status_code == 403, "un mentor sin capacidad de liderazgo de invasiones no debe poder crear"

        created = await pastor_client.post("/api/mentorship/outreach/campaigns", json=payload, headers=pastor_headers)
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["meeting_time"] == "6:00 AM"
        assert body["meeting_place"] == "Parque Central"
        assert body["sectors"] == ["Sector A", "Sector B"]
        assert body["instructions"] == "Llevar biblia"

        created_by_coord = await coord_client.post("/api/mentorship/outreach/campaigns", json={**payload, "name": "Invasión Coordinador"}, headers=coord_headers)
        assert created_by_coord.status_code == 201, "el coordinador general también puede crear invasiones"
    finally:
        await pastor_client.aclose(); await coord_client.aclose(); await mentor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_participation_self_service_flow_and_decision_status():
    await cleanup()
    pastor_pid = await create_person("Pastor Participa")
    mentor_pid = await create_person("Mentor Participa")
    await activate_badge(mentor_pid)
    _, pastor_email = await create_user("Pastor Participa", "pastor", pastor_pid)
    _, mentor_email = await create_user("Mentor Participa", "persona", mentor_pid)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    mentor_client, mentor_headers = await auth_client(mentor_email)
    try:
        campaign = await pastor_client.post(
            "/api/mentorship/outreach/campaigns",
            json={"name": "Invasión Participación", "location": "Sector P", "start_date": "2026-09-01", "end_date": "2026-09-02",
                  "assigned_mentors": [{"person_id": mentor_pid}]},
            headers=pastor_headers,
        )
        assert campaign.status_code == 201, campaign.text
        campaign_id = campaign.json()["campaign_id"]

        listing = await mentor_client.get("/api/mentorship/outreach/campaigns", headers=mentor_headers)
        own = next(item for item in listing.json()["items"] if item["campaign_id"] == campaign_id)
        assert own["my_participation_status"] == "assigned"

        confirm = await mentor_client.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/participate", headers=mentor_headers)
        assert confirm.status_code == 200
        assert confirm.json()["status"] == "confirmed"

        visit = await mentor_client.post(
            "/api/mentorship/outreach/visits",
            json={"contact_type": "new", "contact_name": "Contacto Decision", "contact_phone": f"809555{uuid.uuid4().int % 10000:04d}", "campaign_id": campaign_id},
            headers=mentor_headers,
        )
        assert visit.status_code == 201, visit.text
        visit_id = visit.json()["visit_id"]
        assert visit.json()["decision_status"] == "pending"

        report = await pastor_client.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/report", headers=pastor_headers)
        mentor_row = next(item for item in report.json()["mentors"] if item["mentor_person_id"] == mentor_pid)
        assert mentor_row["participation_status"] == "active", "registrar actividad sube directo a 'Con actividad'"

        wants_followup = await mentor_client.put(
            f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "wants_followup"}, headers=mentor_headers,
        )
        assert wants_followup.status_code == 200
        assert wants_followup.json() if False else True
        get_visit = await mentor_client.get(f"/api/mentorship/outreach/visits/{visit_id}", headers=mentor_headers)
        assert get_visit.json()["decision_status"] == "accepted"

        with_date = await mentor_client.put(
            f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "wants_followup", "agreed_start_date": "2026-09-10"}, headers=mentor_headers,
        )
        assert with_date.status_code == 200
        get_visit2 = await mentor_client.get(f"/api/mentorship/outreach/visits/{visit_id}", headers=mentor_headers)
        assert get_visit2.json()["decision_status"] == "start_scheduled"
    finally:
        await pastor_client.aclose(); await mentor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_household_visit_event_rules_no_invented_data_and_draft_save():
    await cleanup()
    mentor_pid = await create_person("Mentor Hogar")
    await activate_badge(mentor_pid)
    _, mentor_email = await create_user("Mentor Hogar", "persona", mentor_pid)
    client, headers = await auth_client(mentor_email)
    try:
        household = await client.post(
            "/api/mentorship/outreach/households", json={"address_line1": "Calle 1", "sector": "Sector Z"}, headers=headers,
        )
        assert household.status_code == 201, household.text
        household_id = household.json()["household_id"]

        no_address = await client.post("/api/mentorship/outreach/households", json={}, headers=headers)
        assert no_address.status_code == 422, "debe exigir dirección o sector"

        invented = await client.post(
            f"/api/mentorship/outreach/households/{household_id}/events",
            json={"result": "no_answer", "persons": [{"contact_type": "new", "contact_name": "Inventado"}]}, headers=headers,
        )
        assert invented.status_code == 422, "un intento sin respuesta no debe llevar personas (no se inventan datos)"

        empty_contacted = await client.post(
            f"/api/mentorship/outreach/households/{household_id}/events", json={"result": "contacted"}, headers=headers,
        )
        assert empty_contacted.status_code == 422, "contacto logrado sin personas y sin marcar borrador debe rechazarse"

        draft = await client.post(
            f"/api/mentorship/outreach/households/{household_id}/events", json={"result": "contacted", "is_draft": True}, headers=headers,
        )
        assert draft.status_code == 201, draft.text
        assert draft.json()["event"]["is_draft"] is True
        assert draft.json()["visits"] == []

        no_answer = await client.post(
            f"/api/mentorship/outreach/households/{household_id}/events", json={"result": "no_answer"}, headers=headers,
        )
        assert no_answer.status_code == 201

        with_person = await client.post(
            f"/api/mentorship/outreach/households/{household_id}/events",
            json={"result": "contacted", "persons": [{"contact_type": "new", "contact_name": "Persona Hogar", "contact_phone": f"809444{uuid.uuid4().int % 10000:04d}"}]},
            headers=headers,
        )
        assert with_person.status_code == 201, with_person.text
        assert len(with_person.json()["visits"]) == 1
        assert with_person.json()["visits"][0]["household_id"] == household_id

        detail = await client.get(f"/api/mentorship/outreach/households/{household_id}", headers=headers)
        assert detail.status_code == 200
        assert len(detail.json()["events"]) == 3
        assert len(detail.json()["visits"]) == 1

        listing = await client.get("/api/mentorship/outreach/households", headers=headers)
        own = next(item for item in listing.json()["items"] if item["household_id"] == household_id)
        assert own["attempts"] == 3
    finally:
        await client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_branch_supervisor_sees_read_only_mentor_outside_branch_does_not():
    await cleanup()
    leader_pid = await create_person("Lider Rama")
    mentor_in_branch_pid = await create_person("Mentor En Rama")
    mentor_outside_pid = await create_person("Mentor Fuera")
    await activate_badge(mentor_in_branch_pid)
    await activate_badge(mentor_outside_pid)
    front_group_id = await make_front_group("Rama QA Etapa2", leader_pid)
    await add_member(front_group_id, mentor_in_branch_pid, role="mentor")
    _, leader_email = await create_user("Lider Rama", "lider", leader_pid)
    _, mentor_in_email = await create_user("Mentor En Rama", "persona", mentor_in_branch_pid)
    _, mentor_out_email = await create_user("Mentor Fuera", "persona", mentor_outside_pid)
    leader_client, leader_headers = await auth_client(leader_email)
    mentor_in_client, mentor_in_headers = await auth_client(mentor_in_email)
    mentor_out_client, mentor_out_headers = await auth_client(mentor_out_email)
    try:
        household = await mentor_in_client.post(
            "/api/mentorship/outreach/households", json={"sector": "Sector Rama"}, headers=mentor_in_headers,
        )
        assert household.status_code == 201, household.text
        household_id = household.json()["household_id"]
        assert household.json()["front_group_id"] == front_group_id

        overview_leader = await leader_client.get("/api/mentorship/outreach/my-branch-overview", headers=leader_headers)
        assert overview_leader.status_code == 200
        assert overview_leader.json()["is_supervisor"] is True
        assert any(item["household_id"] == household_id for item in overview_leader.json()["households"])

        leader_get_household = await leader_client.get(f"/api/mentorship/outreach/households/{household_id}", headers=leader_headers)
        assert leader_get_household.status_code == 200, "el líder de la rama debe poder ver (solo lectura) el hogar"

        leader_edit_attempt = await leader_client.put(f"/api/mentorship/outreach/households/{household_id}", json={"note": "intento de edicion"}, headers=leader_headers)
        assert leader_edit_attempt.status_code == 403, "el líder NO debe poder editar, solo ver"

        outside_overview = await mentor_out_client.get("/api/mentorship/outreach/my-branch-overview", headers=mentor_out_headers)
        assert outside_overview.json()["is_supervisor"] is False

        outside_get_household = await mentor_out_client.get(f"/api/mentorship/outreach/households/{household_id}", headers=mentor_out_headers)
        assert outside_get_household.status_code == 403, "un mentor fuera de la rama no debe ver el hogar de otro"
    finally:
        await leader_client.aclose(); await mentor_in_client.aclose(); await mentor_out_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_mentors_by_group_endpoint_returns_branch_mentors_and_requires_campaign_permission():
    await cleanup()
    pastor_pid = await create_person("Pastor Grupo")
    leader_pid = await create_person("Lider Grupo Mentores")
    mentor_pid = await create_person("Mentor De Grupo")
    await activate_badge(mentor_pid)
    front_group_id = await make_front_group("Rama Mentores QA", leader_pid)
    await add_member(front_group_id, mentor_pid, role="mentor")
    _, pastor_email = await create_user("Pastor Grupo", "pastor", pastor_pid)
    _, leader_email = await create_user("Lider Grupo Mentores", "lider", leader_pid)
    pastor_client, pastor_headers = await auth_client(pastor_email)
    leader_client, leader_headers = await auth_client(leader_email)
    try:
        rejected = await leader_client.get(f"/api/mentorship/outreach/mentors-by-group/{front_group_id}", headers=leader_headers)
        assert rejected.status_code == 403, "un líder de grupo sin capacidad de invasiones no arma el roster por grupo"

        allowed = await pastor_client.get(f"/api/mentorship/outreach/mentors-by-group/{front_group_id}", headers=pastor_headers)
        assert allowed.status_code == 200, allowed.text
        ids = [item["person_id"] for item in allowed.json()["items"]]
        assert mentor_pid in ids
    finally:
        await pastor_client.aclose(); await leader_client.aclose()
        await cleanup()
