"""Barra inferior móvil: contexto "mi invasión de hoy" y "+ Agregar visita"
ligada a esa invasión (campaign_id + jornada). Permisos en el backend."""
import uuid
from datetime import date, timedelta

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server


@pytest.mark.asyncio
async def test_invasion_today_context_and_visit_with_day():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_ids = []
    today = date.today()
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        ana_id, lead_id, outsider_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Encargado", "Ajeno")]
        ana = await fx.account(ana_id, "persona")
        lead = await fx.account(lead_id, "persona")
        outsider = await fx.account(outsider_id, "persona")
        await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": ana_id, "active": True})
        for name, start, end in (("Hoy A", today, today), ("Hoy B", today - timedelta(days=1), today + timedelta(days=1)), ("Próxima", today + timedelta(days=3), today + timedelta(days=3)), ("Pasada", today - timedelta(days=9), today - timedelta(days=8))):
            created = await pastora.post("/api/invasions", json={"name": f"{name} {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": end.isoformat(),
                                                                  "general_lead_person_id": lead_id, "mentor_person_ids": [ana_id],
                                                                  "schedule_days": [{"day": today.isoformat(), "start_time": "09:30", "duration_minutes": 120}] if name == "Hoy A" else []})
            assert created.status_code == 201, created.text
            campaign_ids.append(created.json()["campaign_id"])
        today_a, today_b, upcoming, past = campaign_ids

        context = (await ana.get("/api/invasions/mine/today")).json()
        assert [item["campaign_id"] for item in context["active"]] == [today_b, today_a]
        day_a = next(item for item in context["active"] if item["campaign_id"] == today_a)
        assert day_a["day"] == today.isoformat() and day_a["day_label"] == "Jornada de hoy · 09:30"
        assert context["upcoming"]["campaign_id"] == upcoming and past not in str(context)
        assert context["can_register_visits"] is True and context["pending_invitations"] == 3
        # Si declina, ya no aparece como activa.
        await ana.post(f"/api/invasions/{today_b}/respond", json={"response": "declined"})
        assert [item["campaign_id"] for item in (await ana.get("/api/invasions/mine/today")).json()["active"]] == [today_a]
        # Encargado sin insignia: ve la invasión pero no puede registrar visitas; pastora y ajeno: sin contexto.
        lead_context = (await lead.get("/api/invasions/mine/today")).json()
        assert today_a in [item["campaign_id"] for item in lead_context["active"]] and lead_context["can_register_visits"] is False
        for client in (pastora, outsider):
            context = (await client.get("/api/invasions/mine/today")).json()
            managed = context.pop("managed")
            assert context == {"today": today.isoformat(), "active": [], "upcoming": None, "pending_invitations": 0, "can_register_visits": False}
            assert bool(managed) is (client is pastora)  # la pastora supervisa (Asistencia), el ajeno no

        # "+ Agregar visita": queda con la invasión y la jornada del día.
        created = await ana.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": f"Vecino {tag}", "campaign_id": today_a, "invasion_day": today.isoformat()})
        assert created.status_code == 201, created.text
        stored = await server.db.outreach_visits.find_one({"visit_id": created.json()["visit_id"]})
        assert stored["campaign_id"] == today_a and stored["invasion_day"] == today.isoformat() and stored["mentor_person_id"] == ana_id
        # La jornada debe estar dentro de las fechas y requiere invasión.
        assert (await ana.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": "X", "campaign_id": today_a, "invasion_day": (today + timedelta(days=2)).isoformat()})).status_code == 422
        assert (await ana.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": "X", "invasion_day": today.isoformat()})).status_code == 422
        # Sin invasión sigue funcionando como antes ("Sin campaña").
        plain = await ana.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": f"Suelto {tag}"})
        assert plain.status_code == 201 and plain.json().get("campaign_id") is None
        # Sin insignia de mentor no puede registrar.
        assert (await outsider.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": "X", "campaign_id": today_a})).status_code in (403, 409)
    finally:
        for collection in ("outreach_visits", "outreach_participations", "invasion_participants", "outreach_campaigns"):
            await server.db[collection].delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.outreach_visits.delete_many({"contact_name": {"$regex": tag}})
        await server.db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
