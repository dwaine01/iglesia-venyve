"""Botón «Necesito ayuda»: solo participantes de la invasión activa lo lanzan;
solo responsables lo ven y resuelven; idempotente y 1 por persona cada 30 s;
aviso en la campana y resumen en el reporte."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server

db = server.db


def help_body(**extra):
    return {"client_request_id": f"help-{uuid.uuid4().hex}", "reason": "support", **extra}


@pytest.mark.asyncio
async def test_help_alert_permissions_idempotency_rate_limit_and_report():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_ids = []
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        coordinator = await fx.account(await fx.person(f"Coord{tag}"), "lider", access_level="coordinador_general")
        lead_id, ana_id, collab_id, outsider_id = [await fx.person(f"{name}{tag}") for name in ("Encargado", "Ana", "Colab", "Ajeno")]
        lead = await fx.account(lead_id, "persona")
        ana = await fx.account(ana_id, "persona")
        collab = await fx.account(collab_id, "persona")
        outsider = await fx.account(outsider_id, "persona")
        await db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": ana_id, "active": True})
        today = date.today()
        for name, start in (("Hoy", today), ("Futura", today + timedelta(days=5))):
            created = await pastora.post("/api/invasions", json={"name": f"{name} {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": start.isoformat(),
                                                                  "general_lead_person_id": lead_id, "mentor_person_ids": [ana_id], "collaborator_person_ids": [collab_id]})
            assert created.status_code == 201, created.text
            campaign_ids.append(created.json()["campaign_id"])
        active_id, future_id = campaign_ids

        # Solo participantes de la invasión ACTIVA; la pastora supervisa (no lanza).
        assert (await outsider.post(f"/api/invasions/{active_id}/help", json=help_body())).status_code == 403
        assert (await pastora.post(f"/api/invasions/{active_id}/help", json=help_body())).status_code == 403
        assert (await ana.post(f"/api/invasions/{future_id}/help", json=help_body())).status_code == 409
        body = help_body(reason="risk", note="Perro suelto en la esquina", latitude=41.85, longitude=-87.66, accuracy_m=12)
        sent = await ana.post(f"/api/invasions/{active_id}/help", json=body)
        assert sent.status_code == 201, sent.text
        alert = sent.json()
        assert alert["reason_label"] == "Situación de riesgo" and alert["status"] == "open" and alert["latitude"] == 41.85 and alert["notified"] >= 3
        # Doble toque: misma clave → mismo aviso, sin duplicar.
        again = (await ana.post(f"/api/invasions/{active_id}/help", json=body)).json()
        assert again["duplicate"] is True and again["alert_id"] == alert["alert_id"]
        assert await db.invasion_help_alerts.count_documents({"campaign_id": active_id}) == 1
        # Otra alerta en menos de 30 s: 429; el colaborador sí puede.
        assert (await ana.post(f"/api/invasions/{active_id}/help", json=help_body())).status_code == 429
        assert (await collab.post(f"/api/invasions/{active_id}/help", json=help_body(reason="prayer"))).status_code == 201

        # Aviso en la campana del encargado, coordinador y pastora (no del ajeno).
        for client in (lead, coordinator, pastora):
            items = (await client.get("/api/notifications")).json()["items"]
            assert any(item["type"] == "invasion_help" and item["link"] == f"/invasiones/{active_id}/ayuda" for item in items)
        assert not any(item["type"] == "invasion_help" for item in (await outsider.get("/api/notifications")).json()["items"])

        # Ver y resolver: solo responsables.
        for client in (ana, collab, outsider):
            assert (await client.get(f"/api/invasions/{active_id}/help")).status_code == 403
            assert (await client.put(f"/api/invasions/{active_id}/help/{alert['alert_id']}", json={"status": "resolved"})).status_code == 403
        listing = (await lead.get(f"/api/invasions/{active_id}/help")).json()
        assert listing["open"] == 2 and len(listing["items"]) == 2
        await db.invasion_help_alerts.update_one({"alert_id": alert["alert_id"]}, {"$set": {"created_at": datetime.now(timezone.utc) - timedelta(minutes=4)}})
        acked = (await lead.put(f"/api/invasions/{active_id}/help/{alert['alert_id']}", json={"status": "acknowledged"})).json()
        assert acked["status"] == "acknowledged" and acked["acknowledged_by_name"] and 3.5 <= acked["response_minutes"] <= 4.5
        resolved = (await coordinator.put(f"/api/invasions/{active_id}/help/{alert['alert_id']}", json={"status": "resolved", "note": "Se acompañó"})).json()
        assert resolved["status"] == "resolved" and resolved["resolved_by_name"] and resolved["acknowledged_by_name"] == acked["acknowledged_by_name"]
        assert any(item["type"] == "invasion_help_ack" for item in (await ana.get("/api/notifications")).json()["items"])

        # Reporte de invasión: número de alertas y tiempo de respuesta.
        summary = (await pastora.get(f"/api/invasions/{active_id}/report")).json()["help_alerts"]
        assert summary["total"] == 2 and summary["resolved"] == 1 and summary["open"] == 1 and 3.5 <= summary["avg_response_minutes"] <= 4.5
        assert {row["reason"]: row["total"] for row in summary["by_reason"]}["risk"] == 1
    finally:
        for collection in ("invasion_help_alerts", "outreach_participations", "invasion_participants", "invasion_reports", "outreach_campaigns"):
            await db[collection].delete_many({"campaign_id": {"$in": campaign_ids}})
        await db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
