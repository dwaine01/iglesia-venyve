"""Regla del dueño: la autoridad pastoral principal (pastor/pastora general)
supervisa y administra, pero NO es participante: no está en el roster que
confirma, ni en conteos, métricas, rankings o gráficas de desempeño. Sí crea,
administra y consulta todos los reportes."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server


@pytest.mark.asyncio
async def test_principal_authority_is_not_counted_but_sees_everything():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        luis_id = await fx.person(f"Luis{tag}")
        luis = await fx.account(luis_id, "persona")
        coord_id = await fx.person(f"Coord{tag}")
        await fx.account(coord_id, "lider", access_level="coordinador_general")
        for person_id in (pastora_id, luis_id, coord_id):
            await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})

        # Lista de mentores para invitar/asignar: sin la pastora; el coordinador-mentor sí (caso pendiente del dueño).
        mentors = {item["person_id"] for item in (await pastora.get("/api/mentorship/mentors", params={"search": tag})).json()["items"]}
        assert luis_id in mentors and coord_id in mentors and pastora_id not in mentors

        start = date.today()
        created = await pastora.post("/api/mentorship/outreach/campaigns", json={
            "name": f"Invasión {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": (start + timedelta(days=1)).isoformat(),
            "assigned_mentors": [{"person_id": pastora_id}, {"person_id": luis_id}],
        })
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]
        assert created.json()["assigned_mentor_ids"] == [luis_id]
        added = (await pastora.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/mentors", json={"person_ids": [pastora_id]})).json()
        assert added["added"] == [] and added["rejected"][0]["person_id"] == pastora_id
        assert (await pastora.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/participate")).status_code == 409

        # Datos heredados: aunque la pastora hubiera quedado en el roster y registrado actividad, no cuenta.
        await server.db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$addToSet": {"assigned_mentor_ids": pastora_id}})
        await server.db.outreach_participations.insert_one({"_id": f"part-{tag}", "participation_id": f"part-{tag}", "campaign_id": campaign_id, "mentor_person_id": pastora_id, "status": "active"})
        now = datetime.now(timezone.utc)
        for index, mentor in enumerate((pastora_id, pastora_id, luis_id)):
            await server.db.outreach_visits.insert_one({"_id": f"v-{tag}-{index}", "visit_id": f"v-{tag}-{index}", "campaign_id": campaign_id, "mentor_person_id": mentor, "status": "wants_followup", "archived": False, "created_at": now})
            await server.db.outreach_visit_events.insert_one({"_id": f"e-{tag}-{index}", "visit_event_id": f"e-{tag}-{index}", "household_id": f"h-{tag}", "campaign_id": campaign_id, "mentor_person_id": mentor, "result": "contacted", "occurred_at": now, "created_at": now})

        listing = (await pastora.get("/api/mentorship/outreach/campaigns")).json()["items"]
        assert next(item for item in listing if item["campaign_id"] == campaign_id).get("my_participation_status") is None

        report = await pastora.get(f"/api/mentorship/outreach/campaigns/{campaign_id}/report")
        assert report.status_code == 200
        assert [item["mentor_person_id"] for item in report.json()["mentors"]] == [luis_id]

        dashboard = (await pastora.get("/api/mentorship/outreach/dashboard")).json()
        assert pastora_id not in {item["mentor_person_id"] for item in dashboard["by_mentor"]}
        campaign_row = next(item for item in dashboard["by_campaign"] if item["campaign_id"] == campaign_id)
        assert campaign_row["total"] == 1

        overview = await pastora.get("/api/supervision/overview", params={"campaign_id": campaign_id})
        assert overview.status_code == 200
        invasion = overview.json()["invasion"]
        assert invasion["visits_total"] == 1 and invasion["mentors_with_activity"] == 0 and invasion["mentors_assigned"] == 1
        drill = (await pastora.get("/api/supervision/mentors", params={"campaign_id": campaign_id})).json()["mentors"]
        assert [item["mentor_person_id"] for item in drill] == [luis_id]

        # El mentor ve lo suyo (no cambia nada para los participantes).
        assert (await luis.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/participate")).status_code == 200
    finally:
        if campaign_id:
            for collection in ("outreach_visits", "outreach_visit_events", "outreach_participations", "outreach_campaigns"):
                await server.db[collection].delete_many({"campaign_id": campaign_id})
        await server.db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
