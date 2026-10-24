"""FASE 6B: confirmación desde el portal, conteos reales, asistencia, avisos
y push preparado pero apagado."""
import uuid
from datetime import date, timedelta

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server


@pytest.mark.asyncio
async def test_respond_counts_attendance_and_notifications():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        lead_id, mentor_id, collab_id, other_id = [await fx.person(f"{name}{tag}") for name in ("Encargado", "Mentor", "Colab", "Ajeno")]
        lead = await fx.account(lead_id, "persona")
        mentor = await fx.account(mentor_id, "persona")
        collab = await fx.account(collab_id, "persona")
        other = await fx.account(other_id, "persona")
        await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": mentor_id, "active": True})
        start = date.today() + timedelta(days=4)
        created = await pastora.post("/api/invasions", json={
            "name": f"Invasión {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": start.isoformat(),
            "general_lead_person_id": lead_id, "mentor_person_ids": [mentor_id], "collaborator_person_ids": [collab_id],
        })
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]

        # El invitado ve su invitación en el portal; el aviso enlaza a su portal.
        mine = (await collab.get("/api/invasions/mine/invitations")).json()["items"]
        assert [item["campaign_id"] for item in mine] == [campaign_id] and mine[0]["status"] == "invited" and mine[0]["role_labels"] == ["Colaborador"]
        notice = next(item for item in (await collab.get("/api/notifications")).json()["items"] if item["type"] == "invasion_invited")
        assert notice["link"] == f"/mi-perfil?invasion={campaign_id}"
        assert (await other.get("/api/invasions/mine/invitations")).json()["items"] == []

        # Responder: confirmar / no podré; un ajeno y la pastora no.
        assert (await collab.post(f"/api/invasions/{campaign_id}/respond", json={"response": "confirmed"})).json()["status"] == "confirmed"
        declined = await mentor.post(f"/api/invasions/{campaign_id}/respond", json={"response": "declined", "note": "Trabajo ese día"})
        assert declined.status_code == 200
        assert (await other.post(f"/api/invasions/{campaign_id}/respond", json={"response": "confirmed"})).status_code == 403
        assert (await pastora.post(f"/api/invasions/{campaign_id}/respond", json={"response": "confirmed"})).status_code == 409
        # El organizador recibe el aviso de las respuestas.
        types = [item["title"] for item in (await pastora.get("/api/notifications")).json()["items"] if item["type"] == "invasion_response"]
        assert any("confirmó" in title for title in types) and any("no podrá" in title for title in types)

        # Mentor cambia de opinión: el roster operativo (Visitas/Supervisión) queda igual.
        await mentor.post(f"/api/invasions/{campaign_id}/respond", json={"response": "confirmed"})
        assert (await server.db.outreach_participations.find_one({"campaign_id": campaign_id, "mentor_person_id": mentor_id}))["status"] == "confirmed"
        await mentor.post(f"/api/invasions/{campaign_id}/respond", json={"response": "declined"})
        assert (await server.db.outreach_participations.find_one({"campaign_id": campaign_id, "mentor_person_id": mentor_id}))["status"] == "assigned"

        # Conteos reales (la pastora nunca cuenta).
        listing = (await lead.get(f"/api/invasions/{campaign_id}/participants")).json()
        assert listing["counts"] == {"total": 3, "invited": 1, "confirmed": 1, "declined": 1, "attended": 0, "no_response": 1}
        assert next(item for item in listing["items"] if item["person_id"] == mentor_id)["status_label"] == "No participará"
        summary = (await pastora.get("/api/invasions/participants/summary")).json()["items"][campaign_id]
        assert summary == {"total": 3, "confirmed": 1, "no_response": 1, "declined": 1, "attended": 0}
        assert campaign_id not in (await mentor.get("/api/invasions/participants/summary")).json()["items"]

        # Asistencia: la marca el encargado general; registrar actividad también cuenta.
        assert (await mentor.put(f"/api/invasions/{campaign_id}/participants/{collab_id}/attendance", json={"attended": True})).status_code == 403
        marked = (await lead.put(f"/api/invasions/{campaign_id}/participants/{collab_id}/attendance", json={"attended": True})).json()
        assert marked["counts"]["attended"] == 1
        await mentor.post("/api/mentorship/outreach/households", json={"campaign_id": campaign_id, "address_line1": "1 Main St", "latitude": 39.9, "longitude": -83.0})
        after = (await pastora.get(f"/api/invasions/{campaign_id}/participants")).json()
        assert after["counts"]["attended"] == 2
        assert (await mentor.get("/api/invasions/mine/invitations")).json()["items"][0]["status_label"] == "Asistió"

        # Confirmar desde el flujo anterior de Visitas también actualiza la lista.
        await server.db.invasion_participants.update_one({"campaign_id": campaign_id, "person_id": mentor_id}, {"$set": {"status": "invited"}})
        await server.db.outreach_participations.update_one({"campaign_id": campaign_id, "mentor_person_id": mentor_id}, {"$set": {"status": "assigned"}})
        assert (await mentor.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/participate")).status_code == 200
        assert (await server.db.invasion_participants.find_one({"campaign_id": campaign_id, "person_id": mentor_id}))["status"] == "confirmed"

        # Push: preparado pero apagado (sin claves VAPID ni interruptor).
        assert (await mentor.get("/api/notifications/push/config")).json() == {"enabled": False, "public_key": None}
        refused = await mentor.post("/api/notifications/push/subscribe", json={"endpoint": "https://push.example.com/abc", "keys": {"p256dh": "x" * 20, "auth": "y" * 10}})
        assert refused.status_code == 409
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_participations", "invasion_participants", "outreach_campaigns"):
                await server.db[collection].delete_many({"campaign_id": campaign_id})
        await server.db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_push_works_only_when_switch_keys_and_library_exist(monkeypatch):
    """Con interruptor + claves + librería (aquí simulada) se suscribe y envía;
    sin ellas no hace nada. No se agrega ninguna dependencia real."""
    import asyncio
    import sys
    import types

    sent = []
    fake = types.ModuleType("pywebpush")
    class WebPushException(Exception):
        pass
    fake.WebPushException = WebPushException
    fake.webpush = lambda **kwargs: sent.append(kwargs)
    monkeypatch.setitem(sys.modules, "pywebpush", fake)
    for key, value in {"PUSH_NOTIFICATIONS_ENABLED": "true", "VAPID_PUBLIC_KEY": "pub-key", "VAPID_PRIVATE_KEY": "priv-key", "VAPID_SUBJECT": "mailto:test@example.com"}.items():
        monkeypatch.setenv(key, value)
    fx = Fixture()
    endpoint = f"https://push.example.com/{uuid.uuid4().hex}"
    try:
        client = await fx.account(await fx.person(f"Push{uuid.uuid4().hex[:6]}"), "persona")
        assert (await client.get("/api/notifications/push/config")).json() == {"enabled": True, "public_key": "pub-key"}
        assert (await client.post("/api/notifications/push/subscribe", json={"endpoint": endpoint, "keys": {"p256dh": "x" * 20, "auth": "y" * 10}})).status_code == 200
        from portal_notifications import notify_users
        await notify_users([str(fx.user_ids[-1])], "test", "Hola", "Mensaje", "/mi-perfil")
        for _ in range(40):
            if sent:
                break
            await asyncio.sleep(0.05)
        assert sent and sent[0]["subscription_info"]["endpoint"] == endpoint and sent[0]["vapid_claims"] == {"sub": "mailto:test@example.com"}
        monkeypatch.setenv("PUSH_NOTIFICATIONS_ENABLED", "false")
        assert (await client.get("/api/notifications/push/config")).json()["enabled"] is False
    finally:
        await server.db.push_subscriptions.delete_many({"endpoint": endpoint})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
