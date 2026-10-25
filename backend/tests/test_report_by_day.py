"""Reporte por día (Día 1, Día 2… con fecha LOCAL de la iglesia) y exclusión
de cuentas de prueba marcadas por la autoridad pastoral."""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
NY = ZoneInfo("America/New_York")


def door(number, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "opened": True, "contact_level": "conversation", **extra}


@pytest.mark.asyncio
async def test_report_by_local_day_and_test_account_exclusion():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, beto_id, mentor_only = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto", "Otro")]
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        outsider = await fx.account(mentor_only, "persona")
        for pid in (ana_id, beto_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{pid}", "person_id": pid, "active": True})
        day1 = date.today() - timedelta(days=1)
        day2 = date.today()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": day1.isoformat(), "end_date": day2.isoformat(), "mentor_person_ids": [ana_id, beto_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        for client, street in ((ana, "Calle 18"), (beto, "Calle 26")):
            await client.put(f"{base}/my-street", json={"street_name": street})
        a1 = (await ana.post(f"{base}/doors", json=door("10", person={"contact_name": f"Rosa {tag}"}, followup="yes"))).json()
        a2 = (await ana.post(f"{base}/doors", json=door("12"))).json()
        b1 = (await beto.post(f"{base}/doors", json=door("30"))).json()
        # Día 1 a las 23:30 hora local (ya es el día siguiente en UTC) y un registro del día 2.
        night = datetime.combine(day1, time(23, 30), tzinfo=NY).astimezone(timezone.utc)
        await db.outreach_visit_events.update_many({"visit_event_id": {"$in": [a1["event"]["visit_event_id"], b1["event"]["visit_event_id"]]}}, {"$set": {"occurred_at": night}})
        await db.outreach_visits.update_many({"visit_id": a1["visits"][0]["visit_id"]}, {"$set": {"created_at": night}})
        await db.invasion_participants.update_many({"campaign_id": campaign_id, "person_id": ana_id}, {"$set": {"attended_days": [day1.isoformat()]}})

        full = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        assert full["period"]["days_total"] == 2 and full["period"]["day"] is None and full["period"]["days"][0]["day"] == day1.isoformat()
        assert full["summary"]["key_figures"]["houses_visited"] == 3
        d1 = (await pastora.get(f"/api/invasions/{campaign_id}/report", params={"day": day1.isoformat()})).json()
        assert d1["period"]["index"] == 1 and "de" in d1["period"]["label"]
        assert d1["summary"]["key_figures"]["houses_visited"] == 2 and d1["summary"]["key_figures"]["people_reached"] == 1
        assert d1["field"]["doors"]["totals"]["houses_visited"] == 2 and d1["field"]["doors"]["totals"]["attempts"] == 2
        assert d1["participation"]["totals"]["attended"] == 1 and [row["day"] for row in d1["participation"]["by_day"]] == [day1.isoformat()]
        d2 = (await pastora.get(f"/api/invasions/{campaign_id}/report", params={"day": day2.isoformat()})).json()
        assert d2["summary"]["key_figures"]["houses_visited"] == 1 and d2["participation"]["totals"]["attended"] == 1  # beto registró hoy
        assert (await pastora.get(f"/api/invasions/{campaign_id}/report", params={"day": "2001-01-01"})).status_code == 422
        assert a2["household"]["household_id"]

        # Cuentas de prueba: la autoridad las marca y no cuentan en ninguna cifra.
        assert (await outsider.get("/api/invasions/report-settings/exclusions")).status_code == 403
        current = (await pastora.get("/api/invasions/report-settings/exclusions")).json()
        before = [item["person_id"] for item in current["excluded"]]
        await pastora.put("/api/invasions/report-settings/exclusions", json={"person_ids": before + [beto_id]})
        d1x = (await pastora.get(f"/api/invasions/{campaign_id}/report", params={"day": day1.isoformat()})).json()
        assert d1x["summary"]["key_figures"]["houses_visited"] == 1 and beto_id not in {row["person_id"] for row in d1x["ranking"]["mentors"]}
        assert d1x["field"]["doors"]["totals"]["houses_visited"] == 1
        await pastora.put("/api/invasions/report-settings/exclusions", json={"person_ids": before})
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
