"""FASE 6F (tramo 1): reporte de invasión — permisos (completo / personal /
sin acceso), pastora excluida, cifras con datos de ejemplo y reporte final
congelado que ya no cambia."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server


@pytest.mark.asyncio
async def test_report_permissions_figures_and_frozen_final():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    today = date.today()
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        lead_id, ana_id, beto_id, collab_id, other_id = [await fx.person(f"{name}{tag}") for name in ("Encargado", "Ana", "Beto", "Colab", "Ajeno")]
        lead = await fx.account(lead_id, "persona")
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        other = await fx.account(other_id, "persona")
        coordinator = await fx.account(await fx.person(f"Coord{tag}"), "lider", access_level="coordinador_general")
        for person_id in (ana_id, beto_id, pastora_id):
            await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        created = await pastora.post("/api/invasions", json={
            "name": f"Invasión {tag}", "location": "Lincoln Park", "purpose": "Alcanzar familias",
            "start_date": (today - timedelta(days=1)).isoformat(), "end_date": today.isoformat(),
            "general_lead_person_id": lead_id, "mentor_person_ids": [ana_id, beto_id, pastora_id], "collaborator_person_ids": [collab_id],
        })
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]
        # Ana: 2 casas (una visitada) y 2 personas alcanzadas; casa disponible sin tomar.
        h1 = (await ana.post("/api/mentorship/outreach/households", json={"campaign_id": campaign_id, "address_line1": "1 Main", "sector": "Norte", "latitude": 39.9, "longitude": -83.0})).json()["household_id"]
        await ana.post("/api/mentorship/outreach/households", json={"campaign_id": campaign_id, "address_line1": "2 Main", "sector": "Norte", "latitude": 39.91, "longitude": -83.0})
        await pastora.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/import", json={"entries": [{"address_line1": "3 Main", "sector": "Sur"}]})
        await ana.post(f"/api/mentorship/outreach/households/{h1}/events", json={"result": "no_answer"})
        now = datetime.now(timezone.utc)
        for index, extra in enumerate(({"status": "wants_followup", "received_mcd": True, "enrollment_id": f"enr-{tag}"}, {"status": "visited", "lbs_decision": "needs_lbs"})):
            await server.db.outreach_visits.insert_one({"_id": f"v-{tag}-{index}", "visit_id": f"v-{tag}-{index}", "campaign_id": campaign_id, "mentor_person_id": ana_id, "household_id": h1, "contact_zone": "Norte", "archived": False, "created_at": now, **extra})
        # Una visita "de la pastora" no cuenta.
        await server.db.outreach_visits.insert_one({"_id": f"v-{tag}-p", "visit_id": f"v-{tag}-p", "campaign_id": campaign_id, "mentor_person_id": pastora_id, "status": "wants_followup", "archived": False, "created_at": now})
        await beto.post(f"/api/invasions/{campaign_id}/respond", json={"response": "declined"})

        # Permisos: completo para pastora, coordinador general y encargado; personal para el mentor; nada para un ajeno.
        for client in (pastora, coordinator, lead):
            assert (await client.get(f"/api/invasions/{campaign_id}/report")).json()["scope"] == "full"
        assert (await other.get(f"/api/invasions/{campaign_id}/report")).status_code == 403
        personal = (await beto.get(f"/api/invasions/{campaign_id}/report")).json()
        assert personal["scope"] == "personal" and "ranking" not in personal and "participation" not in personal

        report = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        assert report["mode"] == "live" and report["summary"]["state"] == "active" and report["can_finalize"] is True
        figures = report["summary"]["key_figures"]
        assert figures == {"houses_visited": 1, "houses_total": 3, "people_reached": 2, "wants_followup": 1, "seven_weeks": 1,
                           "participants": 4, "attended": 1, "attendance_pct": 25}
        # Pastora fuera de participación y ranking.
        roles = {item["role"]: item for item in report["participation"]["by_role"]}
        assert roles["mentor"]["invited"] == 2 and roles["mentor"]["declined"] == 1 and roles["collaborator"]["invited"] == 1
        assert pastora_id not in {item["person_id"] for item in report["ranking"]["mentors"]}
        assert report["ranking"]["mentors"][0]["person_id"] == ana_id and report["ranking"]["mentors"][0]["people"] == 2
        field = report["field"]
        assert field["houses"] == {"available": 1, "assigned": 2, "visited": 1, "located": 2, "total": 3}
        assert field["results"]["received_mcd"] == 1 and field["results"]["lbs_pending"] == 1
        norte = next(item for item in field["by_sector"] if item["sector"] == "Norte")
        assert norte == {"sector": "Norte", "houses": 2, "visited": 1, "people": 2, "coverage_pct": 50}
        ana_personal = (await ana.get(f"/api/invasions/{campaign_id}/report")).json()
        assert ana_personal["mine"]["people"] == 2 and ana_personal["position"] == 1

        # Cerrar → reporte final congelado; lo que pase después no lo cambia.
        assert (await beto.post(f"/api/invasions/{campaign_id}/report/finalize")).status_code == 403
        final = (await lead.post(f"/api/invasions/{campaign_id}/report/finalize")).json()
        assert final["mode"] == "final" and final["summary"]["state"] == "closed" and final["can_finalize"] is False
        await server.db.outreach_visits.insert_one({"_id": f"v-{tag}-late", "visit_id": f"v-{tag}-late", "campaign_id": campaign_id, "mentor_person_id": ana_id, "status": "wants_followup", "archived": False, "created_at": now})
        again = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        assert again["summary"]["key_figures"] == final["summary"]["key_figures"] and again["frozen_at"] == final["frozen_at"]
        assert (await lead.post(f"/api/invasions/{campaign_id}/report/finalize")).json()["frozen_at"] == final["frozen_at"]
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_participations", "invasion_participants", "invasion_reports", "outreach_campaigns"):
                await server.db[collection].delete_many({"campaign_id": campaign_id})
        await server.db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
