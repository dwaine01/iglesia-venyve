"""Calles del puerta a puerta: terminar (idempotente), una sola activa,
cambiar cierra la anterior, reabrir, «Mis calles», cierre automático con
aviso, duración en el reporte por calle y permisos."""
import uuid
from datetime import date, timedelta

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero (orden de importación)
from door_streets import close_stale_streets

db = server.db


def door(number, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "opened": False, **extra}


@pytest.mark.asyncio
async def test_street_lifecycle_finish_change_reopen_and_auto_close():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, outsider_id = await fx.person(f"Ana{tag}"), await fx.person(f"Ajeno{tag}")
        ana = await fx.account(ana_id, "persona")
        outsider = await fx.account(outsider_id, "persona")
        await db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": ana_id, "active": True})
        today = date.today().isoformat()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today, "end_date": today, "mentor_person_ids": [ana_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"

        assert (await ana.post(f"{base}/my-street/finish", json={})).status_code == 409
        first = (await ana.put(f"{base}/my-street", json={"street_name": "Calle 18"})).json()
        session_id = first["active_street"]["street_session_id"]
        # Doble toque en «Comenzar»: el mismo tramo.
        assert (await ana.put(f"{base}/my-street", json={"street_name": "calle 18"})).json()["active_street"]["street_session_id"] == session_id
        await ana.post(f"{base}/doors", json=door("10"))
        await ana.post(f"{base}/doors", json=door("12", opened=True, contact_level="brief", books=[{"book": "MCD", "quantity": 1}]))
        event = await db.outreach_visit_events.find_one({"campaign_id": campaign_id, "house_number": {"$exists": False}}, sort=[("occurred_at", -1)])
        assert event["street_session_id"] == session_id

        # Terminar: resumen de la calle; el doble toque devuelve lo mismo sin error.
        finished = (await ana.post(f"{base}/my-street/finish", json={"street_session_id": session_id})).json()
        assert finished["active_street"] is None and finished["already_finished"] is False
        assert finished["finished"]["visited"] == 2 and finished["finished"]["opened"] == 1 and finished["finished"]["books"] == 1 and finished["finished"]["status"] == "finished"
        again = (await ana.post(f"{base}/my-street/finish", json={"street_session_id": session_id})).json()
        assert again["already_finished"] is True and again["finished"]["visited"] == 2
        # Sin calle activa no se registran viviendas.
        assert (await ana.post(f"{base}/doors", json=door("14"))).status_code == 422

        # Comenzar otra y «Cambiar calle»: la anterior se cierra sola (una sola activa).
        await ana.put(f"{base}/my-street", json={"street_name": "Avenida Sur"})
        changed = (await ana.put(f"{base}/my-street", json={"street_name": "Calle 26"})).json()
        streets = {row["street_name"]: row for row in changed["streets"]}
        assert changed["active_street"]["street_name"] == "Calle 26"
        assert streets["Avenida Sur"]["status"] == "finished" and streets["Avenida Sur"]["end_reason"] == "changed"
        assert [row["status"] for row in changed["streets"]].count("active") == 1
        participation = await db.outreach_participations.find_one({"campaign_id": campaign_id, "mentor_person_id": ana_id})
        assert sum(1 for item in participation["street_sessions"] if not item.get("ended_at")) == 1

        # Reabrir Calle 18: cierra Calle 26, mismas viviendas; agregar otra suma a la misma calle.
        reopened = (await ana.post(f"{base}/my-street/reopen", json={"street_key": "calle 18"})).json()
        assert reopened["active_street"]["street_name"] == "Calle 18" and reopened["active_street"]["reopened_from"] == session_id
        await ana.post(f"{base}/doors", json=door("10"))  # la misma puerta: otro intento, no otra vivienda
        await ana.post(f"{base}/doors", json=door("16"))
        state = (await ana.get(f"{base}/my-street")).json()
        row = next(item for item in state["streets"] if item["street_key"] == "calle 18")
        assert row["status"] == "active" and row["houses"] == 3 and row["sessions"] == 2 and row["today"] is True
        assert (await ana.post(f"{base}/my-street/reopen", json={"street_key": "no existe"})).status_code == 404

        # Cierre automático: una calle que quedó abierta de ayer se cierra y se avisa.
        await db.outreach_participations.update_one({"campaign_id": campaign_id, "mentor_person_id": ana_id},
                                                    {"$set": {"active_street.started_at": server.datetime.now(server.timezone.utc) - timedelta(days=2)}})
        assert await close_stale_streets() >= 1
        state = (await ana.get(f"{base}/my-street")).json()
        assert state["active_street"] is None
        assert next(item for item in state["streets"] if item["street_key"] == "calle 18")["end_reason"] == "auto"
        assert await db.portal_notifications.count_documents({"type": "door_street_auto_closed", "recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}}) == 1

        # El reporte por calle trae inicio, fin y duración.
        report = (await pastora.get(f"{base}/door-report")).json()
        calle = next(item for item in report["by_street"] if item["street_key"] == "calle 18")
        assert calle["started_at"] and calle["ended_at"] and calle["duration_minutes"] is not None and calle["houses_visited"] == 3

        # Permisos: fuera del roster no.
        for call in (outsider.get(f"{base}/my-street"), outsider.post(f"{base}/my-street/finish", json={}), outsider.post(f"{base}/my-street/reopen", json={"street_key": "calle 18"})):
            assert (await call).status_code in {403, 409}
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns", "library_movements"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
