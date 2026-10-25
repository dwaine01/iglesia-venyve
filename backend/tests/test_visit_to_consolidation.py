"""«Pasar a Consolidación» desde una visita en un toque: expediente en «Nuevo y seguimiento»
con origen (invasión, vivienda, quién la visitó, libros y nota), sin duplicados,
«Transferir a» otro mentor o al equipo (pendiente hasta aceptar), avisos, Mi Trabajo
(«En Consolidación») y la columna «Pasaron a Consolidación» del reporte de invasión."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_visit_to_consolidation_transfer_and_reports():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, beto_id = await fx.person(f"Ana{tag}"), await fx.person(f"Beto{tag}")
        ana, beto = await fx.account(ana_id, "persona"), await fx.account(beto_id, "persona")
        for pid in (ana_id, beto_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{pid}", "person_id": pid, "active": True})
        today = date.today().isoformat()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today, "end_date": today, "mentor_person_ids": [ana_id, beto_id]})).json()["campaign_id"]

        async def assign(name, mentor=ana_id):
            response = await pastora.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": f"{name} {tag}", "contact_zone": "Calle 18 #45",
                                                                                    "campaign_id": campaign_id, "mentor_person_id": mentor})
            assert response.status_code == 201, response.text
            return response.json()["visit_id"]

        # 1) El mentor la pasa (aunque el informe siga en «Asignado»): un toque, etapa «Nuevo y seguimiento».
        alvin = await assign("Alvin")
        await ana.put(f"/api/mentorship/outreach/visits/{alvin}/report", json={"status": "visited", "received_mcd": False, "note": "Aceptó a Jesús"})
        done = (await ana.post(f"/api/mentorship/outreach/visits/{alvin}/to-consolidation", json={"note": "Prefiere llamadas en la noche"})).json()
        assert done["created"] is True and done["already"] is False and done["message"] == f"Alvin {tag} pasó a Consolidación."
        enrollment = await db.process_enrollments.find_one({"enrollment_id": done["enrollment_id"]})
        assert enrollment["current_stage_key"] == "visitor_followup" and enrollment["mentor_person_id"] == ana_id and enrollment["status"] == "active"
        origin = enrollment["origin"]
        assert origin["visit_id"] == alvin and origin["campaign_name"] == f"Inv {tag}" and origin["address"] == "Calle 18 #45"
        assert origin["contacted_by_person_id"] == ana_id and "Aceptó a Jesús" in origin["note"] and "noche" in origin["note"]
        visit = await db.outreach_visits.find_one({"visit_id": alvin})
        assert visit["enrollment_id"] == done["enrollment_id"] and visit["status"] == "wants_followup" and visit["converted_person_id"] == enrollment["person_id"]
        # Sin duplicados: otra vez → el mismo expediente.
        again = (await ana.post(f"/api/mentorship/outreach/visits/{alvin}/to-consolidation")).json()
        assert again["already"] is True and again["enrollment_id"] == done["enrollment_id"] and "ya está en Consolidación" in again["message"]
        assert await db.process_enrollments.count_documents({"person_id": enrollment["person_id"], "process_key": "consolidation"}) == 1
        # Aviso a la pastora / encargados.
        assert await db.portal_notifications.count_documents({"type": "consolidation_new_from_visit", "ref.enrollment_id": done["enrollment_id"]}) >= 1
        # Mi Trabajo: «En Consolidación».
        people = (await ana.get("/api/my-work/people")).json()["items"]
        row = next(item for item in people if item.get("visit_id") == alvin)
        assert row["status"] == "consolidation" and row["can_start_consolidation"] is False

        # 2) «Transferir a» otro mentor: pendiente hasta que Beto acepte; Ana sigue como quien la visitó.
        ernesto = await assign("Ernesto")
        moved = (await pastora.post(f"/api/mentorship/outreach/visits/{ernesto}/to-consolidation", json={"transfer_to": beto_id})).json()
        assert moved["created"] is True and moved["transfer_pending_to"].startswith(f"Beto{tag}")
        pending = (await beto.get("/api/my-work/transfers")).json()["items"]
        assert [item["enrollment_id"] for item in pending] == [moved["enrollment_id"]] and pending[0]["from_mentor_name"].startswith(f"Ana{tag}")
        assert (await db.process_enrollments.find_one({"enrollment_id": moved["enrollment_id"]}))["mentor_transfer_required"] is True
        assert await db.portal_notifications.count_documents({"type": "consolidation_transfer_request", "ref.enrollment_id": moved["enrollment_id"]}) == 1
        assert (await ana.post(f"/api/my-work/transfers/{moved['enrollment_id']}/accept")).status_code == 403  # no es para Ana
        accepted = (await beto.post(f"/api/my-work/transfers/{moved['enrollment_id']}/accept")).json()
        assert accepted["mentor_person_id"] == beto_id
        after = await db.process_enrollments.find_one({"enrollment_id": moved["enrollment_id"]})
        assert after["mentor_person_id"] == beto_id and after["transfer_request"]["status"] == "accepted" and after["mentor_transfer_required"] is False
        assert after["origin"]["contacted_by_person_id"] == ana_id and (await db.outreach_visits.find_one({"visit_id": ernesto}))["mentor_person_id"] == ana_id
        assert (await beto.get("/api/my-work/transfers")).json()["items"] == []

        # 3) Al equipo de Consolidación: lo ve quien supervisa y asigna mentor; también se puede rechazar.
        luz = await assign("Luz")
        team = (await ana.post(f"/api/mentorship/outreach/visits/{luz}/to-consolidation", json={"transfer_to": "team"})).json()
        team_items = (await pastora.get("/api/my-work/transfers")).json()["items"]
        assert any(item["enrollment_id"] == team["enrollment_id"] and item["to_team"] for item in team_items)
        assert (await pastora.post(f"/api/my-work/transfers/{team['enrollment_id']}/accept")).status_code == 422  # falta elegir mentor
        assert (await pastora.post(f"/api/my-work/transfers/{team['enrollment_id']}/accept", json={"mentor_person_id": beto_id})).json()["mentor_person_id"] == beto_id
        mar = await assign("Mar")
        declined = (await pastora.post(f"/api/mentorship/outreach/visits/{mar}/to-consolidation", json={"transfer_to": beto_id})).json()
        assert (await beto.post(f"/api/my-work/transfers/{declined['enrollment_id']}/decline", json={"reason": "Sin tiempo"})).json()["declined"] is True
        assert (await db.process_enrollments.find_one({"enrollment_id": declined["enrollment_id"]}))["mentor_person_id"] == ana_id

        # 4) Permisos y casos que no aplican.
        sol = await assign("Sol")
        assert (await beto.post(f"/api/mentorship/outreach/visits/{sol}/to-consolidation")).status_code == 403  # visita de otro mentor
        await ana.put(f"/api/mentorship/outreach/visits/{sol}/report", json={"status": "rejected"})
        assert (await ana.post(f"/api/mentorship/outreach/visits/{sol}/to-consolidation")).status_code == 409

        # 5) Reporte de invasión: «Pasaron a Consolidación».
        report = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        assert report["summary"]["key_figures"]["to_consolidation"] == 4
    finally:
        if campaign_id:
            visit_ids = [doc["visit_id"] async for doc in db.outreach_visits.find({"campaign_id": campaign_id}, {"visit_id": 1})]
            enrollment_ids = [doc["enrollment_id"] async for doc in db.process_enrollments.find({"campaign_id": campaign_id}, {"enrollment_id": 1})]
            await db.outreach_visits.delete_many({"campaign_id": campaign_id})
            await db.outreach_visit_history.delete_many({"visit_id": {"$in": visit_ids}})
            await db.process_enrollments.delete_many({"enrollment_id": {"$in": enrollment_ids}})
            await db.process_stage_progress.delete_many({"enrollment_id": {"$in": enrollment_ids}})
            await db.portal_notifications.delete_many({"$or": [{"ref.visit_id": {"$in": visit_ids}}, {"ref.enrollment_id": {"$in": enrollment_ids}}]})
            await db.outreach_campaigns.delete_one({"campaign_id": campaign_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
