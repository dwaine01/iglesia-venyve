"""Eliminar la cuenta de un líder desde el Panel General: solo autoridad
pastoral, nunca a sí misma ni a un pastor, confirmación por nombre, personas
y Persona 360 conservadas, referencias limpiadas y auditoría."""
import uuid
from datetime import date, timedelta

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server


@pytest.mark.asyncio
async def test_delete_leader_account_keeps_people_and_cleans_references():
    await server.db.front_groups.update_many({"pastoral_main": True}, {"$unset": {"pastoral_main": ""}})
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_ids, legacy_ids = [], []
    josue_user_id = None
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        pastora_user_id = str(fx.user_ids[-1])
        other_pastor = await fx.account(await fx.person(f"Pastor{tag}"), "pastor")
        other_pastor_user_id = str(fx.user_ids[-1])
        coordinator = await fx.account(await fx.person(f"Coord{tag}"), "lider", access_level="coordinador_general")
        josue_id = await fx.person(f"Josue{tag}")
        josue = await fx.account(josue_id, "lider")
        josue_user_id = str(fx.user_ids[-1])
        josue_name = (await server.db.users.find_one({"_id": ObjectId(josue_user_id)}))["nombre"]
        await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": josue_id, "active": True})

        # 6 personas asignadas (modelo de líderes del Panel General).
        for index in range(6):
            legacy_ids.append((await server.db.people.insert_one({"nombre": f"Persona{index}{tag}", "leader_id": josue_user_id, "estado": "en_proceso"})).inserted_id)
        # Grupo frontal que lidera y dos invasiones activas: una sin actividad y otra con visitas.
        group_id = (await pastora.put("/api/pastoral-front-group", json={"name": f"Grupo {tag}"})).json()["group"]["front_group_id"]
        await pastora.put(f"/api/front-groups/{group_id}/roster", json={"entries": [{"person_ids": [josue_id]}]})
        child_id = (await pastora.post(f"/api/front-groups/{group_id}/leader-privilege", json={"person_id": josue_id})).json()["front_group_id"]
        start = date.today() + timedelta(days=5)
        for name in ("sin actividad", "con actividad"):
            created = await pastora.post("/api/invasions", json={"name": f"Invasión {name} {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": start.isoformat(), "mentor_person_ids": [josue_id]})
            assert created.status_code == 201, created.text
            campaign_ids.append(created.json()["campaign_id"])
        await server.db.outreach_visits.insert_one({"_id": f"visit-{tag}", "visit_id": f"visit-{tag}", "campaign_id": campaign_ids[1], "mentor_person_id": josue_id, "archived": False})
        free_house = (await josue.post("/api/mentorship/outreach/households", json={"campaign_id": campaign_ids[0], "address_line1": "1 Main St"})).json()["household_id"]

        # Permisos.
        assert (await coordinator.get(f"/api/pastor/leaders/{josue_user_id}/delete-preview")).status_code == 403
        assert (await coordinator.request("DELETE", f"/api/pastor/leaders/{josue_user_id}", json={"confirm_name": josue_name})).status_code == 403
        assert (await josue.request("DELETE", f"/api/pastor/leaders/{josue_user_id}", json={"confirm_name": josue_name})).status_code == 403
        assert (await pastora.request("DELETE", f"/api/pastor/leaders/{pastora_user_id}", json={"confirm_name": "x"})).status_code == 400
        assert (await pastora.request("DELETE", f"/api/pastor/leaders/{other_pastor_user_id}", json={"confirm_name": "x"})).status_code == 403
        assert (await pastora.request("DELETE", f"/api/pastor/leaders/{josue_user_id}", json={"confirm_name": "Otro nombre"})).status_code == 422

        preview = (await pastora.get(f"/api/pastor/leaders/{josue_user_id}/delete-preview")).json()
        assert preview["people_assigned"] == 6 and preview["mentor_badge_active"] is True and len(preview["active_invasions"]) == 2
        assert preview["groups_led"] == 1

        deleted = await pastora.request("DELETE", f"/api/pastor/leaders/{josue_user_id}", json={"confirm_name": f"  {josue_name.upper()} "})
        assert deleted.status_code == 200, deleted.text
        body = deleted.json()
        assert body["people_unassigned"] == 6 and body["invasions_removed"] == [campaign_ids[0]] and body["invasions_kept_as_history"] == [campaign_ids[1]]

        # La cuenta ya no existe y su sesión deja de valer.
        assert not await server.db.users.find_one({"_id": ObjectId(josue_user_id)})
        assert (await josue.get("/api/core/me/profile")).status_code == 401
        # Personas y Persona 360 conservadas: quedan sin líder y visibles para reasignar.
        people = await server.db.people.find({"_id": {"$in": legacy_ids}}).to_list(10)
        assert len(people) == 6 and all(item["leader_id"] is None and item["previous_leader_id"] == josue_user_id for item in people)
        assert await server.db.persons.find_one({"_id": ObjectId(josue_id)})
        dashboard = (await pastora.get("/api/dashboard/role-based")).json()
        assert {f"Persona{index}{tag}" for index in range(6)} <= {item["nombre"] for item in dashboard["personas_sin_lider"]}
        assert josue_user_id not in {item["_id"] for item in dashboard["lideres"]}
        # Referencias limpiadas.
        assert not await server.db.front_group_assignments.find_one({"person_id": josue_id, "active": True})
        assert (await server.db.front_groups.find_one({"front_group_id": child_id}))["primary_leader_person_id"] is None
        assert (await server.db.mentor_badges.find_one({"_id": f"badge-{tag}"}))["active"] is False
        first = await server.db.outreach_campaigns.find_one({"campaign_id": campaign_ids[0]})
        assert josue_id not in first["assigned_mentor_ids"] and not await server.db.invasion_participants.find_one({"campaign_id": campaign_ids[0], "person_id": josue_id})
        assert (await server.db.outreach_households.find_one({"household_id": free_house}))["status"] == "available"
        second = await server.db.outreach_campaigns.find_one({"campaign_id": campaign_ids[1]})
        assert josue_id in second["assigned_mentor_ids"]  # historial con actividad conservado
        assert (await server.db.outreach_participations.find_one({"campaign_id": campaign_ids[1], "mentor_person_id": josue_id}))["status"] == "inactive"
        audit = await server.db.admin_deletions.find_one({"collection": "users", "target_id": josue_user_id})
        assert audit and audit["detail"]["people_assigned"] == 6 and audit["actor_user_id"] == pastora_user_id
        assert (await other_pastor.get("/api/dashboard/role-based")).status_code == 200
    finally:
        await server.db.people.delete_many({"_id": {"$in": legacy_ids}})
        for collection in ("outreach_households", "outreach_visits", "outreach_participations", "invasion_participants", "outreach_campaigns"):
            await server.db[collection].delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.admin_deletions.delete_many({"target_id": josue_user_id})
        await server.db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
