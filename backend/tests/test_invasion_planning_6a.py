"""FASE 6A: solicitud de invasión por un líder, revisión por la autoridad,
creación oficial con el formulario completo y notificaciones del portal."""
import uuid
from datetime import date, timedelta

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server


@pytest.mark.asyncio
async def test_request_review_create_and_notify():
    await server.db.front_groups.update_many({"pastoral_main": True}, {"$unset": {"pastoral_main": ""}})
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_ids = []
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        coordinator = await fx.account(await fx.person(f"Coord{tag}"), "lider", access_level="coordinador_general")
        leader_id, member_id, mentor_id, lead_id = [await fx.person(f"{name}{tag}") for name in ("Lider", "Miembro", "Mentor", "Encargado")]
        leader = await fx.account(leader_id, "lider", capabilities=[], permissions_mode="manual")
        member = await fx.account(member_id, "persona")
        mentor = await fx.account(mentor_id, "persona")
        outsider = await fx.account(await fx.person(f"Ajeno{tag}"), "persona")
        await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": mentor_id, "active": True})

        main_id = (await pastora.put("/api/pastoral-front-group", json={"name": f"Grupo {tag}"})).json()["group"]["front_group_id"]
        await pastora.put(f"/api/front-groups/{main_id}/roster", json={"entries": [{"person_ids": [leader_id]}, {"person_ids": [member_id]}]})
        child_id = (await pastora.post(f"/api/front-groups/{main_id}/leader-privilege", json={"person_id": leader_id})).json()["front_group_id"]
        await leader.put(f"/api/front-groups/{child_id}/conform", json={"name": f"Grupo Lider {tag}"})

        authorities = (await leader.get("/api/invasions/authorities")).json()["items"]
        pastora_user_id = str(fx.user_ids[0])
        assert any(item["user_id"] == pastora_user_id and item["title"] == "Pastor general" for item in authorities)
        start = date.today() + timedelta(days=20)
        request_body = {"authority_user_id": pastora_user_id, "front_group_id": child_id, "proposed_location": "Barrio Norte",
                        "proposed_start_date": start.isoformat(), "proposed_end_date": (start + timedelta(days=1)).isoformat(), "notes": "Dos jornadas"}
        # Solo líderes/colíderes de un Grupo Frontal solicitan; la autoridad debe ser válida.
        assert (await member.post("/api/invasions/requests", json=request_body)).status_code == 403
        assert (await leader.post("/api/invasions/requests", json={**request_body, "authority_user_id": "no-existe"})).status_code == 422
        created = await leader.post("/api/invasions/requests", json=request_body)
        assert created.status_code == 201, created.text
        request_id = created.json()["request_id"]
        assert created.json()["status"] == "pending" and created.json()["front_group_name"] == f"Grupo Lider {tag}"
        inbox = (await pastora.get("/api/notifications")).json()
        assert any(item["type"] == "invasion_request_submitted" and item["ref"].get("request_id") == request_id for item in inbox["items"])

        assert (await leader.get("/api/invasions/requests")).json()["can_review"] is False
        assert (await leader.post(f"/api/invasions/requests/{request_id}/review", json={"decision": "reject", "note": "No"})).status_code == 403
        changes = await pastora.post(f"/api/invasions/requests/{request_id}/review", json={"decision": "request_changes", "note": "Propón otra fecha"})
        assert changes.json()["status"] == "changes_requested"
        leader_inbox = (await leader.get("/api/notifications")).json()
        notice = next(item for item in leader_inbox["items"] if item["type"] == "invasion_request_changes_requested")
        assert notice["message"] == "Propón otra fecha" and leader_inbox["unread"] >= 1
        assert (await leader.post(f"/api/notifications/{notice['notification_id']}/read")).json()["read"] is True
        resubmitted = await leader.put(f"/api/invasions/requests/{request_id}", json={**request_body, "proposed_start_date": (start + timedelta(days=7)).isoformat(), "proposed_end_date": (start + timedelta(days=8)).isoformat()})
        assert resubmitted.json()["status"] == "pending"

        # Crear oficial: solo pastor general / coordinador general.
        invasion = {
            "name": "Invasión Barrio Norte", "location": "Barrio Norte", "purpose": "Alcanzar familias", "description": "Visitas casa por casa",
            "start_date": (start + timedelta(days=7)).isoformat(), "end_date": (start + timedelta(days=8)).isoformat(),
            "schedule_days": [{"day": (start + timedelta(days=7)).isoformat(), "start_time": "09:00", "duration_minutes": 180},
                              {"day": (start + timedelta(days=8)).isoformat(), "start_time": "15:00", "duration_minutes": 120}],
            "general_lead_person_id": lead_id, "logistics_lead_person_id": leader_id,
            "emergency_contact": {"name": "Hermano Pérez", "phone": "8095550000"},
            "departure_point": "La iglesia", "site_meeting_point": {"address": "Calle 1 #2", "reference": "Frente al colmado"},
            "invited_front_group_ids": [child_id], "mentor_person_ids": [mentor_id], "request_id": request_id,
        }
        assert (await leader.post("/api/invasions", json=invasion)).status_code == 403
        bad = dict(invasion, schedule_days=[{"day": (start + timedelta(days=30)).isoformat(), "start_time": "09:00", "duration_minutes": 60}])
        assert (await pastora.post("/api/invasions", json=bad)).status_code == 422
        assert (await pastora.post("/api/invasions", json=dict(invasion, prayer_start_date=(start + timedelta(days=9)).isoformat()))).status_code == 422
        result = await pastora.post("/api/invasions", json=invasion)
        assert result.status_code == 201, result.text
        body = result.json()
        campaign_ids.append(body["campaign_id"])
        # Oración por defecto: una semana antes de salir.
        assert body["prayer_start_date"] == start.isoformat() and body["prayer_default"] is True
        assert body["general_lead"]["person_id"] == lead_id and body["emergency_contact"]["phone"] == "8095550000"
        assert [item["start_time"] for item in body["schedule_days"]] == ["09:00", "15:00"]
        assert body["invited_front_groups"][0]["front_group_id"] == child_id and body["mentors"][0]["person_id"] == mentor_id
        assert (await server.db.outreach_participations.find_one({"campaign_id": body["campaign_id"], "mentor_person_id": mentor_id}))["status"] == "assigned"
        approved = (await leader.get("/api/invasions/requests")).json()["items"][0]
        assert approved["status"] == "approved" and approved["campaign_id"] == body["campaign_id"]
        assert any(item["type"] == "invasion_request_approved" for item in (await leader.get("/api/notifications")).json()["items"])
        assert any(item["type"] == "invasion_invited" for item in (await mentor.get("/api/notifications")).json()["items"])
        # No se aprueba dos veces la misma solicitud.
        assert (await pastora.post("/api/invasions", json=invasion)).status_code == 409

        # Ver y actualizar: el invitado ve; un ajeno no; la actualización avisa a los invitados.
        assert (await mentor.get(f"/api/invasions/{body['campaign_id']}")).status_code == 200
        assert (await outsider.get(f"/api/invasions/{body['campaign_id']}")).status_code == 403
        update = {key: value for key, value in invasion.items() if key not in {"mentor_person_ids", "request_id"}}
        updated = await pastora.put(f"/api/invasions/{body['campaign_id']}", json={**update, "prayer_start_date": start.isoformat(), "description": "Cambio de horario"})
        assert updated.status_code == 200 and updated.json()["prayer_default"] is False and updated.json()["plan_version"] == 2
        assert any(item["type"] == "invasion_updated" for item in (await mentor.get("/api/notifications")).json()["items"])
        coord = await coordinator.post("/api/invasions", json={**{k: v for k, v in invasion.items() if k != "request_id"}, "name": "Invasión del coordinador", "mentor_person_ids": []})
        assert coord.status_code == 201, coord.text
        campaign_ids.append(coord.json()["campaign_id"])
    finally:
        await server.db.outreach_campaign_requests.delete_many({"requested_by_person_id": {"$in": fx.person_ids}})
        await server.db.invasion_participants.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.outreach_participations.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.outreach_campaigns.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await server.db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_single_form_keeps_legacy_fields_and_old_invasions():
    """Un solo formulario: guarda también los campos del formulario anterior
    (sectores, notas, instrucciones, hora de encuentro), excluye a la pastora
    del roster y abre/edita invasiones creadas antes (sin campos de plan)."""
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_ids = []
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        mentor_id = await fx.person(f"Mentor{tag}")
        await fx.account(mentor_id, "persona")
        for person_id in (pastora_id, mentor_id):
            await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        start = date.today() + timedelta(days=10)
        body = {
            "name": f"Invasión {tag}", "location": "Lincoln Park", "start_date": start.isoformat(), "end_date": start.isoformat(),
            "schedule_days": [{"day": start.isoformat(), "start_time": "10:30", "duration_minutes": 120}],
            "sectors": ["Calle 1", " ", "Calle 2"], "zone_notes": "Zona tranquila", "instructions": "Llevar agua",
            "assigned_mentors": [{"person_id": mentor_id}, {"person_id": pastora_id}],
        }
        created = await pastora.post("/api/invasions", json=body)
        assert created.status_code == 201, created.text
        data = created.json(); campaign_ids.append(data["campaign_id"])
        assert data["assigned_mentor_ids"] == [mentor_id]  # la pastora supervisa, no participa
        assert data["sectors"] == ["Calle 1", "Calle 2"] and data["zone_notes"] == "Zona tranquila" and data["instructions"] == "Llevar agua"
        assert data["meeting_time"] == "10:30" and data["meeting_place"] == "La iglesia"
        # Sigue apareciendo en la lista de invasiones existente.
        listing = (await pastora.get("/api/mentorship/outreach/campaigns")).json()["items"]
        assert any(item["campaign_id"] == data["campaign_id"] for item in listing)

        # Invasión creada con el formulario anterior (sin campos de plan).
        old = await pastora.post("/api/mentorship/outreach/campaigns", json={
            "name": f"Ganadores de Almas {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": start.isoformat(),
            "meeting_time": "08:00", "meeting_place": "Parqueo", "sectors": ["A"], "instructions": "Antiguas", "assigned_mentors": [{"person_id": mentor_id}],
        })
        assert old.status_code == 201, old.text
        old_id = old.json()["campaign_id"]; campaign_ids.append(old_id)
        opened = await pastora.get(f"/api/invasions/{old_id}")
        assert opened.status_code == 200 and opened.json()["meeting_place"] == "Parqueo" and opened.json().get("schedule_days") in (None, [])
        edited = await pastora.put(f"/api/invasions/{old_id}", json={"purpose": "Nuevo propósito", "departure_point": "Parqueo", "sectors": ["A", "B"]})
        assert edited.status_code == 200, edited.text
        result = edited.json()
        assert result["purpose"] == "Nuevo propósito" and result["sectors"] == ["A", "B"] and result["instructions"] == "Antiguas"
        assert result["assigned_mentor_ids"] == [mentor_id] and result["start_date"] == start.isoformat()
    finally:
        await server.db.invasion_participants.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.outreach_participations.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.outreach_campaigns.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await server.db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_participants_roles_permissions_and_no_module_access():
    """Mentores, colaboradores y grupos invitados; la lista la modifican la
    autoridad y el encargado general; la pastora nunca es participante; ser
    colaborador no crea cuenta ni da módulos."""
    await server.db.front_groups.update_many({"pastoral_main": True}, {"$unset": {"pastoral_main": ""}})
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_ids = []
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        lead_id, mentor_id, collab_id, member_id, other_id = [await fx.person(f"{name}{tag}") for name in ("Encargado", "Mentor", "Colab", "Miembro", "Otro")]
        lead = await fx.account(lead_id, "persona")
        mentor = await fx.account(mentor_id, "persona")
        other = await fx.account(await fx.person(f"Ajeno{tag}"), "persona")
        for person_id in (mentor_id, pastora_id):
            await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        group_id = (await pastora.put("/api/pastoral-front-group", json={"name": f"Grupo {tag}"})).json()["group"]["front_group_id"]
        await pastora.put(f"/api/front-groups/{group_id}/roster", json={"entries": [{"person_ids": [member_id]}]})

        start = date.today() + timedelta(days=15)
        created = await pastora.post("/api/invasions", json={
            "name": f"Invasión {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": start.isoformat(),
            "general_lead_person_id": lead_id, "mentor_person_ids": [mentor_id, pastora_id],
            "collaborator_person_ids": [collab_id, pastora_id], "invited_front_group_ids": [group_id],
        })
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]; campaign_ids.append(campaign_id)
        listing = (await pastora.get(f"/api/invasions/{campaign_id}/participants")).json()
        roles = {item["person_id"]: item["roles"] for item in listing["items"]}
        # La pastora es líder del grupo invitado y fue elegida como mentora/colaboradora: igual queda fuera.
        assert pastora_id not in roles
        assert roles[lead_id] == ["general_lead"] and roles[mentor_id] == ["mentor"] and roles[collab_id] == ["collaborator"] and roles[member_id] == ["collaborator"]
        assert all(item["status"] == "invited" and item["status_label"] == "Sin responder" for item in listing["items"])
        assert listing["counts"]["total"] == 4 and listing["can_edit"] is True
        # Ser colaborador no crea cuenta ni da acceso a módulos.
        assert await server.db.users.count_documents({"person_id": {"$in": [collab_id, member_id]}}) == 0
        assert not await server.db.outreach_participations.find_one({"campaign_id": campaign_id, "mentor_person_id": collab_id})

        # El encargado general modifica la lista; un mentor invitado la ve pero no la edita; un ajeno no la ve.
        assert (await mentor.get(f"/api/invasions/{campaign_id}/participants")).json()["can_edit"] is False
        assert (await mentor.post(f"/api/invasions/{campaign_id}/participants", json={"role": "collaborator", "person_ids": [other_id]})).status_code == 403
        assert (await other.get(f"/api/invasions/{campaign_id}/participants")).status_code == 403
        added = await lead.post(f"/api/invasions/{campaign_id}/participants", json={"role": "collaborator", "person_ids": [other_id, pastora_id]})
        assert added.status_code == 200, added.text
        assert added.json()["added"] == [other_id] and added.json()["rejected"][0]["person_id"] == pastora_id
        no_badge = (await lead.post(f"/api/invasions/{campaign_id}/participants", json={"role": "mentor", "person_ids": [collab_id]})).json()
        assert no_badge["rejected"][0]["reason"] == "No tiene insignia de Mentor activa"
        removed = await lead.delete(f"/api/invasions/{campaign_id}/participants/{other_id}", params={"role": "collaborator"})
        assert other_id not in {item["person_id"] for item in removed.json()["items"]}
        await lead.delete(f"/api/invasions/{campaign_id}/participants/{mentor_id}", params={"role": "mentor"})
        campaign = await server.db.outreach_campaigns.find_one({"campaign_id": campaign_id})
        assert mentor_id not in campaign["assigned_mentor_ids"]
        assert not await server.db.outreach_participations.find_one({"campaign_id": campaign_id, "mentor_person_id": mentor_id})
    finally:
        await server.db.invasion_participants.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.invasion_participants.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.outreach_participations.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.outreach_campaigns.delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.admin_deletions.delete_many({"target_id": {"$regex": "|".join(campaign_ids) or "^$"}})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await server.db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
