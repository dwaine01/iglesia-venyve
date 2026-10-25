"""Puerta a puerta (tramo 4): reportes por mentor, equipo, calle e invasión,
sin duplicados (vivienda vs intentos), perfil solo agregado y permisos."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero (orden de importación)

db = server.db


def door(number, unit=None, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "unit": unit, "opened": False, **extra}


@pytest.mark.asyncio
async def test_door_report_counts_houses_once_and_scopes():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        ana_id, beto_id, outsider_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto", "Ajeno")]
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        outsider = await fx.account(outsider_id, "persona")
        for person_id in (ana_id, beto_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        today = date.today().isoformat()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today, "end_date": today,
                                                                     "mentor_person_ids": [ana_id, beto_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await ana.put(f"{base}/my-street", json={"street_name": "Calle 18"})
        await beto.put(f"{base}/my-street", json={"street_name": "Avenida Sur"})

        # Ana: la misma casa 3 veces (2 sin respuesta, luego abren, entran y aceptan seguimiento) + otro apartamento.
        assert (await ana.post(f"{base}/doors", json=door("12", "1"))).status_code == 201
        assert (await ana.post(f"{base}/doors", json=door("12", "1"))).status_code == 201
        opened = await ana.post(f"{base}/doors", json=door("12", "1", opened=True, contact_level="invited_in", followup="yes", followup_date=today,
                                                           language="es", religion="católica", origin="México", shared_by_person=True,
                                                           books=[{"book": "MCD", "quantity": 2}], person={"contact_name": f"Rosa {tag}", "contact_phone": f"555{tag[:6]}"}))
        assert opened.status_code == 201, opened.text
        house_id = opened.json()["household"]["household_id"]
        await ana.post(f"{base}/doors", json=door("12", "2", opened=True, contact_level="brief", language="en", language_basis="impression"))
        # Beto: una casa sin respuesta en otra calle.
        await beto.post(f"{base}/doors", json=door("5"))

        full = (await pastora.get(f"{base}/door-report")).json()
        totals = full["totals"]
        assert full["scope"] == "all"
        assert totals["houses_visited"] == 3 and totals["attempts"] == 5 and totals["opened"] == 2 and totals["not_opened"] == 1
        assert totals["invited_in"] == 1 and totals["conversed"] == 1 and totals["houses_with_books"] == 1 and totals["books"] == 2
        assert totals["followup_houses"] == 1 and totals["followup_people"] == 1 and totals["people"] == 1 and totals["pending_revisit"] == 1 and totals["followup_scheduled"] == 1
        mentors = {row["mentor_person_id"]: row for row in full["by_mentor"]}
        assert mentors[ana_id]["houses_visited"] == 2 and mentors[ana_id]["attempts"] == 4 and mentors[beto_id]["not_opened"] == 1
        streets = {row["name"]: row for row in full["by_street"]}
        assert streets["Calle 18"]["houses_visited"] == 2 and streets["Avenida Sur"]["pending_revisit"] == 1
        assert sum(row["houses_visited"] for row in full["by_team"]) == 3
        # Perfil solo agregado: religión/origen de lo compartido; idioma con su base.
        profile = full["profile"]
        assert {row["key"]: row["total"] for row in profile["language"]} == {"es": 1, "en": 1}
        assert profile["language_impression"] == 1 and profile["shared_houses"] == 1
        assert profile["religion"] == [{"key": "Católica", "label": "Católica", "total": 1}] and profile["origin"][0]["label"] == "México"
        assert "Rosa" not in str(profile)

        # El reporte de la invasión lee los mismos datos.
        report = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        assert report["field"]["doors"]["totals"]["attempts"] == 5 and report["field"]["doors"]["totals"]["houses_visited"] == 3

        # Cifras con clic.
        listed = (await pastora.get(f"{base}/door-report/houses", params={"metric": "invited_in"})).json()
        assert listed["total"] == 1 and listed["items"][0]["household_id"] == house_id
        street_key = streets["Calle 18"]["street_key"]
        assert (await pastora.get(f"{base}/door-report/houses", params={"metric": "houses_visited", "street_key": street_key})).json()["total"] == 2

        # Mentor: solo lo suyo, sin equipos; no puede pedir a otro mentor.
        mine = (await beto.get(f"{base}/door-report")).json()
        assert mine["scope"] == "mine" and mine["totals"]["houses_visited"] == 1 and mine["by_team"] == [] and [row["mentor_person_id"] for row in mine["by_mentor"]] == [beto_id]
        assert (await beto.get(f"{base}/door-report", params={"mentor_person_id": ana_id})).status_code == 403
        assert (await beto.get(f"{base}/door-report/houses", params={"mentor_person_id": ana_id})).status_code == 403
        assert (await beto.get(f"{base}/door-report/houses")).json()["total"] == 1
        assert (await outsider.get(f"{base}/door-report")).status_code == 403
        # Supervisión: quien ve toda la invasión puede filtrar por un mentor.
        filtered = (await pastora.get(f"{base}/door-report", params={"mentor_person_id": ana_id})).json()
        assert filtered["scope"] == "mentor" and filtered["totals"]["attempts"] == 4
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns", "library_movements"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
