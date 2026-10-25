"""MT1 · Mi Trabajo: resumen (una consulta agregada por fuente), listados por
cifra, pendientes ordenados (atrasados → hoy → próximos → sin fecha) de
viviendas, contactos y expedientes, «solicitaron regresar» y «no desean más
visitas», avisos neutros y permisos (mentor solo lo suyo; supervisión)."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


def door(number, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "opened": True, "contact_level": "brief", **extra}


@pytest.mark.asyncio
async def test_my_work_summary_pending_outcomes_and_permissions():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, beto_id, rosa_id, juan_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto", "Rosa", "Juan")]
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        for pid in (ana_id, beto_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{pid}", "person_id": pid, "active": True})
        today = date.today()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today.isoformat(), "end_date": today.isoformat(), "mentor_person_ids": [ana_id, beto_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await ana.put(f"{base}/my-street", json={"street_name": "Calle 18"})
        await ana.post(f"{base}/doors", json=door("10", opened=False, contact_level=None))
        await ana.post(f"{base}/doors", json=door("12", contact_level="conversation"))
        # Validación de los resultados nuevos.
        assert (await ana.post(f"{base}/doors", json=door("14", outcome="requested_return"))).status_code == 422
        assert (await ana.post(f"{base}/doors", json=door("14", opened=False, contact_level=None, outcome="no_more_visits"))).status_code == 422
        tomorrow = (today + timedelta(days=1)).isoformat()
        returned = (await ana.post(f"{base}/doors", json=door("14", outcome="requested_return", return_date=tomorrow))).json()
        assert returned["household"]["door_status"] == "followup_scheduled" and returned["household"]["followup_date"] == tomorrow
        no_more = (await ana.post(f"{base}/doors", json=door("16", outcome="no_more_visits"))).json()
        assert no_more["household"]["door_status"] == "no_more_visits" and no_more["household"]["attempts_count"] == 1
        # Contacto con seguimiento para hoy.
        await ana.post(f"{base}/doors", json=door("18", followup="yes", followup_date=today.isoformat(), followup_next_action="Llamar por teléfono", person={"contact_name": f"Luz {tag}"}))
        # Expedientes de Consolidación de Ana: uno atrasado y uno sin próxima acción.
        now = datetime.now(timezone.utc)
        for person_id, next_at in ((rosa_id, now - timedelta(days=2)), (juan_id, None)):
            eid = f"mw-{tag}-{person_id}"
            await db.process_enrollments.insert_one({"_id": eid, "enrollment_id": eid, "process_key": "consolidation", "definition_version": 2, "person_id": person_id, "cycle_id": None,
                                                     "status": "active", "current_stage_key": "mcd", "mentor_person_id": ana_id, "next_action": "Llamar" if next_at else None,
                                                     "next_action_at": next_at, "created_at": now, "updated_at": now, "source": f"test-{tag}"})

        summary = (await ana.get("/api/my-work/summary")).json()
        fig = summary["figures"]
        assert (fig["visited"], fig["opened"], fig["conversed"], fig["pending_return"], fig["people_to_attend"]) == (5, 4, 1, 3, 3)
        assert "Esta semana visitaste 5 vivienda(s), conversaste en 1" in summary["message"] and summary["today"] >= 2 and summary["overdue"] == 1
        assert {notice["key"] for notice in summary["notices"]} >= {"overdue", "no_next_action"}
        assert all("ranking" not in notice["text"].lower() for notice in summary["notices"])

        pending = (await ana.get("/api/my-work/pending")).json()
        buckets = [item["bucket"] for item in pending["items"]]
        assert buckets == sorted(buckets, key=lambda value: {"overdue": 0, "today": 1, "upcoming": 2, "no_date": 3}[value])
        first = pending["items"][0]
        assert first["kind"] == "person" and first["bucket"] == "overdue" and first["subtitle"] == "MCD" and first["campaign_name"] is None
        titles = {item["title"] for item in pending["items"]}
        assert "16 Calle 18" not in titles and "10 Calle 18" in titles and "14 Calle 18" in titles  # «no desean más visitas» sale de pendientes
        contact = next(item for item in pending["items"] if item["kind"] == "contact")
        assert contact["bucket"] == "today" and contact["next_action"] == "Llamar por teléfono" and contact["campaign_name"] == f"Inv {tag}"
        assert pending["counts"]["upcoming"] == 1 and pending["counts"]["no_date"] == 1
        assert (await ana.get("/api/my-work/pending", params={"kind": "households"})).json()["total"] == 3
        # Las listas de cada cifra.
        assert (await ana.get("/api/my-work/summary/opened")).json()["total"] == 4
        assert (await ana.get("/api/my-work/summary/people_to_attend")).json()["total"] == 3
        # Sigue después de la invasión: se cierra y los pendientes continúan, con la invasión de origen.
        await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$set": {"status": "closed"}})
        assert (await ana.get("/api/my-work/pending")).json()["total"] == pending["total"]
        assert (await ana.get("/api/my-work/campaigns")).json()["items"][0]["campaign_id"] == campaign_id

        # Permisos: otro mentor no ve lo de Ana; la supervisión sí.
        assert (await beto.get("/api/my-work/summary", params={"mentor_person_id": ana_id})).status_code == 403
        assert (await beto.get("/api/my-work/pending", params={"mentor_person_id": ana_id})).status_code == 403
        assert (await beto.get("/api/my-work/summary")).json()["figures"]["visited"] == 0
        supervised = (await pastora.get("/api/my-work/summary", params={"mentor_person_id": ana_id, "period": "all"})).json()
        assert supervised["supervising"] is True and supervised["figures"]["visited"] == 5
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.process_enrollments.delete_many({"source": f"test-{tag}"})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
