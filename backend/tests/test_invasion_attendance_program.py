"""Barra móvil (ampliación): Asistencia POR JORNADA y Programa de la invasión.
Permisos en el backend: asistencia solo coordinadores generales, autoridad,
organizador y encargado general; programa de lectura para los invitados."""
import uuid
from datetime import date, timedelta

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server


@pytest.mark.asyncio
async def test_attendance_by_day_permissions_walk_in_and_program():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    today = date.today()
    tomorrow = today + timedelta(days=1)
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        coordinator = await fx.account(await fx.person(f"Coord{tag}"), "lider", access_level="coordinador_general")
        lead_id, ana_id, collab_id, outsider_id, walkin_id = [await fx.person(f"{name}{tag}") for name in ("Encargado", "Ana", "Colab", "Ajeno", "Llego")]
        lead = await fx.account(lead_id, "persona")
        ana = await fx.account(ana_id, "persona")
        collab = await fx.account(collab_id, "persona")
        outsider = await fx.account(outsider_id, "persona")
        for person_id in (ana_id, pastora_id):
            await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        created = await pastora.post("/api/invasions", json={
            "name": f"Invasión {tag}", "location": "Barrio", "start_date": today.isoformat(), "end_date": tomorrow.isoformat(),
            "general_lead_person_id": lead_id, "mentor_person_ids": [ana_id, pastora_id], "collaborator_person_ids": [collab_id],
            "schedule_days": [{"day": today.isoformat(), "start_time": "09:00", "duration_minutes": 180}, {"day": tomorrow.isoformat(), "start_time": "14:00", "duration_minutes": 120}],
            "emergency_contact": {"name": "Hno. Pedro", "phone": "555-0101"}, "site_meeting_point": {"address": "Parque Central", "maps_url": "https://maps.example/x"},
            "instructions": "Llevar agua", "sectors": ["Norte"]})
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]
        base = f"/api/invasions/{campaign_id}"

        # Permisos: mentor, colaborador y ajeno no ven ni marcan asistencia (ni por URL).
        for client in (ana, collab, outsider):
            assert (await client.get(f"{base}/attendance")).status_code == 403
            assert (await client.put(f"{base}/attendance/{ana_id}", json={"day": today.isoformat(), "attended": True})).status_code == 403
            assert (await client.post(f"{base}/attendance/walk-in", json={"person_id": walkin_id, "day": today.isoformat()})).status_code == 403
        view = (await lead.get(f"{base}/attendance")).json()
        assert view["day"] == today.isoformat() and [item["day"] for item in view["days"]] == [today.isoformat(), tomorrow.isoformat()]
        assert pastora_id not in {item["person_id"] for item in view["items"]}
        assert view["counts"] == {"invited": 3, "confirmed": 0, "no_response": 3, "declined": 0, "attended_day": 0, "pct_day": 0}
        assert (await coordinator.get(f"{base}/attendance")).status_code == 200 and (await pastora.get(f"{base}/attendance")).status_code == 200

        # Un toque marca la jornada; no afecta la otra; deshacer quita la marca general.
        marked = (await lead.put(f"{base}/attendance/{ana_id}", json={"day": today.isoformat(), "attended": True})).json()
        assert marked == {"person_id": ana_id, "day": today.isoformat(), "attended_day": True, "attended_any": True}
        today_view = (await coordinator.get(f"{base}/attendance", params={"day": today.isoformat()})).json()
        assert today_view["counts"]["attended_day"] == 1 and today_view["counts"]["pct_day"] == 33
        assert (await coordinator.get(f"{base}/attendance", params={"day": tomorrow.isoformat()})).json()["counts"]["attended_day"] == 0
        assert (await lead.put(f"{base}/attendance/{ana_id}", json={"day": (today + timedelta(days=5)).isoformat(), "attended": True})).status_code == 422
        assert (await lead.put(f"{base}/attendance/{pastora_id}", json={"day": today.isoformat(), "attended": True})).status_code == 404
        await lead.put(f"{base}/attendance/{ana_id}", json={"day": today.isoformat(), "attended": False})
        row = await server.db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": ana_id})
        assert row["attended"] is False and row["attended_days"] == []
        await lead.put(f"{base}/attendance/{ana_id}", json={"day": tomorrow.isoformat(), "attended": True})

        # Llegó sin estar invitado: se agrega y se marca; la pastora no.
        walk = (await coordinator.post(f"{base}/attendance/walk-in", json={"person_id": walkin_id, "day": today.isoformat()})).json()
        assert walk["added"] is True and walk["attended_day"] is True
        walk_row = await server.db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": walkin_id})
        assert walk_row["roles"] == ["collaborator"] and walk_row["status"] == "confirmed" and walk_row["walk_in"] is True
        assert (await coordinator.post(f"{base}/attendance/walk-in", json={"person_id": pastora_id, "day": today.isoformat()})).status_code == 409

        # El reporte recibe la asistencia por jornada.
        report = (await pastora.get(f"{base}/report")).json()
        by_day = {item["day"]: item["attended"] for item in report["participation"]["by_day"]}
        assert by_day == {today.isoformat(): 1, tomorrow.isoformat(): 1} and report["summary"]["key_figures"]["attended"] == 2

        # Programa: lectura para invitados; ajeno 403; editar solo autoridad.
        program = (await ana.get(f"{base}/program")).json()
        assert program["can_edit"] is False and program["can_take_attendance"] is False
        assert program["emergency_contact"]["phone"] == "555-0101" and program["site_meeting_point"]["maps_url"] and program["general_lead"]["person_id"] == lead_id
        assert [item["start_time"] for item in program["schedule_days"]] == ["09:00", "14:00"] and program["prayer_start_date"]
        assert (await collab.get(f"{base}/program")).status_code == 200 and (await outsider.get(f"{base}/program")).status_code == 403
        assert (await coordinator.get(f"{base}/program")).json()["can_edit"] is True
        assert (await lead.get(f"{base}/program")).json()["can_take_attendance"] is True

        # Barra: "managed" solo para quien marca asistencia.
        assert campaign_id in [item["campaign_id"] for item in (await coordinator.get("/api/invasions/mine/today")).json()["managed"]]
        lead_managed = (await lead.get("/api/invasions/mine/today")).json()["managed"]
        assert lead_managed and lead_managed[0]["campaign_id"] == campaign_id and lead_managed[0]["active_today"] is True
        assert (await ana.get("/api/invasions/mine/today")).json()["managed"] == []
    finally:
        if campaign_id:
            for collection in ("outreach_participations", "invasion_participants", "invasion_reports", "outreach_campaigns"):
                await server.db[collection].delete_many({"campaign_id": campaign_id})
        await server.db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
