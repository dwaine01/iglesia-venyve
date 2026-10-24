"""FASE 6C: preparación en oración — marcar oración en casa, reuniones de
oración con asistencia, avance y seguimiento; pastora y "no podré" fuera."""
import uuid
from datetime import date, timedelta

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server


@pytest.mark.asyncio
async def test_prayer_marks_meetings_progress_and_permissions():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    today = date.today()
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        lead_id, ana_id, beto_id, ceci_id, other_id = [await fx.person(f"{name}{tag}") for name in ("Encargado", "Ana", "Beto", "Ceci", "Ajeno")]
        lead = await fx.account(lead_id, "persona")
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        ceci = await fx.account(ceci_id, "persona")
        other = await fx.account(other_id, "persona")
        start = today + timedelta(days=3)
        created = await pastora.post("/api/invasions", json={
            "name": f"Invasión {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": start.isoformat(),
            "prayer_start_date": (today - timedelta(days=4)).isoformat(), "general_lead_person_id": lead_id,
            "collaborator_person_ids": [ana_id, beto_id, ceci_id, pastora_id],
        })
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]
        await ceci.post(f"/api/invasions/{campaign_id}/respond", json={"response": "declined"})

        # Ana ora 3 días (hoy, ayer, anteayer); Beto solo hace 4 días.
        for delta in (0, 1, 2):
            assert (await ana.post(f"/api/invasions/{campaign_id}/prayer/home", json={"day": (today - timedelta(days=delta)).isoformat()})).status_code == 200
        assert (await ana.post(f"/api/invasions/{campaign_id}/prayer/home", json={})).status_code == 200  # idempotente
        assert (await ana.post(f"/api/invasions/{campaign_id}/prayer/home", json={"day": (today + timedelta(days=1)).isoformat()})).status_code == 422
        assert (await ana.post(f"/api/invasions/{campaign_id}/prayer/home", json={"day": (today - timedelta(days=9)).isoformat()})).status_code == 422
        assert (await beto.post(f"/api/invasions/{campaign_id}/prayer/home", json={"day": (today - timedelta(days=4)).isoformat()})).status_code == 200
        assert (await ceci.post(f"/api/invasions/{campaign_id}/prayer/home", json={})).status_code == 409
        assert (await other.post(f"/api/invasions/{campaign_id}/prayer/home", json={})).status_code == 403
        assert (await pastora.post(f"/api/invasions/{campaign_id}/prayer/home", json={})).status_code == 409

        # Reuniones: solo el encargado/autoridad; asistencia solo de reuniones ya realizadas.
        assert (await ana.post(f"/api/invasions/{campaign_id}/prayer/meetings", json={"day": today.isoformat()})).status_code == 403
        meeting = (await lead.post(f"/api/invasions/{campaign_id}/prayer/meetings", json={"day": (today - timedelta(days=1)).isoformat(), "time": "19:00"})).json()["meetings"][0]
        future = (await lead.post(f"/api/invasions/{campaign_id}/prayer/meetings", json={"day": (today + timedelta(days=1)).isoformat()})).json()["meetings"][1]
        assert (await lead.put(f"/api/invasions/{campaign_id}/prayer/meetings/{future['meeting_id']}/attendance", json={"person_id": ana_id, "attended": True})).status_code == 422
        assert (await lead.put(f"/api/invasions/{campaign_id}/prayer/meetings/{meeting['meeting_id']}/attendance", json={"person_id": pastora_id, "attended": True})).status_code == 409
        progress = (await lead.put(f"/api/invasions/{campaign_id}/prayer/meetings/{meeting['meeting_id']}/attendance", json={"person_id": ana_id, "attended": True})).json()

        # Avance: pastora y "no podré" no cuentan; 5 días esperados; Beto necesita seguimiento.
        names = {item["person_id"]: item for item in progress["items"]}
        assert set(names) == {lead_id, ana_id, beto_id}
        assert progress["period"]["expected_days"] == 5 and progress["period"]["status"] == "active"
        assert names[ana_id]["prayer_count"] == 3 and names[ana_id]["followup_reason"] is None and names[ana_id]["meetings_attended_count"] == 1
        assert names[beto_id]["followup_reason"] == "Registró 1 de 5 día(s) de oración"
        assert names[lead_id]["followup_reason"] == "Registró 0 de 5 día(s) de oración"
        totals = progress["totals"]
        assert totals["participants"] == 3 and totals["prayed_any"] == 2 and totals["prayed_any_pct"] == 67
        assert totals["meetings"] == 2 and totals["meetings_held"] == 1 and totals["meeting_attendance_pct"] == 33 and totals["needs_followup"] == 2
        # El encargado marca la oración de Beto; no se borra una reunión con asistencia.
        fixed = (await lead.put(f"/api/invasions/{campaign_id}/prayer/home/{beto_id}", json={"day": today.isoformat()})).json()
        assert next(item for item in fixed["items"] if item["person_id"] == beto_id)["prayer_count"] == 2
        assert (await lead.delete(f"/api/invasions/{campaign_id}/prayer/meetings/{meeting['meeting_id']}")).status_code == 409
        assert (await lead.delete(f"/api/invasions/{campaign_id}/prayer/meetings/{future['meeting_id']}")).status_code == 200

        # El participante ve solo lo suyo; un ajeno nada.
        mine = (await ana.get(f"/api/invasions/{campaign_id}/prayer")).json()
        assert "items" not in mine and mine["mine"]["prayer_count"] == 3 and mine["meetings"][0]["i_attended"] is True
        assert (await other.get(f"/api/invasions/{campaign_id}/prayer")).status_code == 403
        # Desmarcar.
        undone = (await ana.post(f"/api/invasions/{campaign_id}/prayer/home", json={"prayed": False})).json()
        assert undone["mine"]["prayer_count"] == 2
    finally:
        if campaign_id:
            for collection in ("invasion_prayer_logs", "invasion_prayer_meetings", "outreach_participations", "invasion_participants", "outreach_campaigns"):
                await server.db[collection].delete_many({"campaign_id": campaign_id})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
