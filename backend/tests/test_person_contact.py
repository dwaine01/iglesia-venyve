"""Perfil 360 · «Contactado por»: el mentor que entregó el libro en la
invasión aparece en la ficha (primer contacto, libros con quién/dónde,
historial de visitas) sin abrir Consolidación; «Asignar a <mentor>» solo con
consolidation.assign y con el mismo mecanismo de 7 Semanas; el mentor ve solo
a sus personas y sin datos sensibles."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
NAMES = ("Ernesto", "Karla", "Elvido", "Selena", "Yadira", "Filibetto", "Manuel", "Paulo")


def door(number, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "opened": True, "contact_level": "conversation", **extra}


@pytest.mark.asyncio
async def test_contact_origin_books_history_and_assign():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    book_id = f"bk-{tag}"
    people = {}
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        luis_id = await fx.person(f"Luis{tag}")
        luis = await fx.account(luis_id, "persona")
        luis_user = str((await db.users.find_one({"person_id": luis_id}, {"_id": 1}))["_id"])
        await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{luis_id}", "person_id": luis_id, "active": True})
        outsider = await fx.account(await fx.person(f"Ajeno{tag}"), "persona")
        assigner = await fx.account(await fx.person(f"Asigna{tag}"), "lider", capabilities=["consolidation.assign"], permissions_mode="manual")
        for name in NAMES:
            people[name] = await fx.person(f"{name}{tag}")
        await db.library_books.insert_one({"_id": book_id, "book_id": book_id, "sku": f"T{tag}".upper(), "name": "MCD", "is_active": True, "member_price_cents": 0})
        await pastora.post("/api/library/adjustments", json={"book_id": book_id, "direction": "increase", "quantity": 10, "reason": "Compra"})
        await pastora.post("/api/library/movements", json={"book_id": book_id, "movement_type": "ASSIGNMENT", "quantity": 8, "from_holder": {"type": "warehouse", "id": "central"}, "to_holder": {"type": "user", "id": luis_user}})
        today = date.today().isoformat()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Invasión {tag}", "location": "Lincoln Park", "start_date": today, "end_date": today, "mentor_person_ids": [luis_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await luis.put(f"{base}/my-street", json={"street_name": "Lincoln Park"})
        # Elvido: primero no abrieron, luego abrieron y recibió el MCD.
        assert (await luis.post(f"{base}/doors", json=door("4247", opened=False, contact_level=None))).status_code == 201
        for index, name in enumerate(NAMES):
            number = "4247" if name == "Elvido" else str(4300 + index)
            response = await luis.post(f"{base}/doors", json=door(number, books=[{"book": book_id, "quantity": 1}], followup="yes" if name == "Karla" else "no",
                                                                   person={"contact_type": "existing", "person_id": people[name]}))
            assert response.status_code == 201, response.text
        # Entregar el libro NO abre Consolidación.
        assert await db.process_enrollments.count_documents({"person_id": {"$in": list(people.values())}}) == 0

        elvido = people["Elvido"]
        counts = {name: await db[name].count_documents({}) for name in ("outreach_visit_events", "outreach_visits", "library_movements")}
        origin = (await luis.get(f"/api/persons/{elvido}/contact-origin")).json()
        first = origin["first_contact"]
        assert first["mentor_name"] == f"Luis{tag} Etapa5C" and first["campaign_name"] == f"Invasión {tag}" and "4247" in first["address"]
        assert first["book"]["book_name"] == "MCD" and origin["current_mentor"] is None and origin["can_assign"] is False
        book = origin["books"][0]
        assert (book["delivered_by"], book["campaign_name"]) == (f"Luis{tag} Etapa5C", f"Invasión {tag}") and "4247" in book["address"]
        kinds = [row["kind"] for row in origin["history"]]
        titles = [row["title"] for row in origin["history"]]
        assert "Visita · no abrieron" in titles and "Visita · abrieron" in titles and "book" in kinds and "visit_created" in kinds
        assert all(row["mentor"] == f"Luis{tag} Etapa5C" for row in origin["history"] if row["kind"] in {"visit", "book"})
        # Lectura pura: no se escribió nada.
        assert counts == {name: await db[name].count_documents({}) for name in counts}
        # Los 8 casos muestran a Luis como primer contacto.
        for name, pid in people.items():
            data = (await luis.get(f"/api/persons/{pid}/contact-origin")).json()
            assert data["first_contact"]["mentor_name"] == f"Luis{tag} Etapa5C" and data["books"], name
        karla = (await luis.get(f"/api/persons/{people['Karla']}/contact-origin")).json()
        assert any(row["kind"] in {"followup", "followup_updated"} or "aceptó seguimiento" in (row.get("detail") or "") for row in karla["history"])

        # El mentor abre la ficha (vista mínima, sin datos sensibles); un ajeno no.
        profile = (await luis.get(f"/api/core/persons/{elvido}/profile")).json()
        assert profile["contact_mentor_view"] is True and "contacto" not in profile and profile["journey_status"] is None
        assert (await outsider.get(f"/api/core/persons/{elvido}/profile")).status_code == 403
        assert (await outsider.get(f"/api/persons/{elvido}/contact-origin")).status_code == 403

        # Asignar: solo consolidation.assign; mismo mecanismo de 7 Semanas.
        assert (await luis.post(f"/api/persons/{elvido}/assign-contact-mentor", json={})).status_code == 403
        assert (await assigner.get(f"/api/persons/{elvido}/contact-origin")).json()["can_assign"] is True
        assigned = await assigner.post(f"/api/persons/{elvido}/assign-contact-mentor", json={})
        assert assigned.status_code == 200, assigned.text
        enrollment = await db.process_enrollments.find_one({"enrollment_id": assigned.json()["enrollment_id"]}, {"_id": 0})
        assert enrollment["mentor_person_id"] == luis_id and enrollment["person_id"] == elvido and enrollment["source"] == "mentorship_outreach"
        visit = await db.outreach_visits.find_one({"person_id": elvido}, {"_id": 0})
        assert visit["enrollment_id"] == enrollment["enrollment_id"] and visit["converted_person_id"] == elvido
        after = (await luis.get(f"/api/persons/{elvido}/contact-origin")).json()
        assert after["current_mentor"]["name"] == f"Luis{tag} Etapa5C" and after["first_contact"]["mentor_name"] == f"Luis{tag} Etapa5C"
        assert "seven_weeks_started" in [row["kind"] for row in after["history"]]
        assert (await assigner.post(f"/api/persons/{elvido}/assign-contact-mentor", json={})).status_code == 409
        # Los demás siguen sin Consolidación.
        assert await db.process_enrollments.count_documents({"person_id": {"$in": [pid for name, pid in people.items() if name != "Elvido"]}}) == 0
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns", "library_movements"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        enrollment_ids = await db.process_enrollments.distinct("enrollment_id", {"person_id": {"$in": list(people.values())}})
        for collection in ("process_enrollments", "mentor_assignments", "process_stage_progress", "process_events", "consolidation_activities"):
            await db[collection].delete_many({"enrollment_id": {"$in": enrollment_ids}})
        await db.library_movements.delete_many({"book_id": book_id})
        await db.library_books.delete_many({"_id": book_id})
        await db.library_holdings.delete_many({"book_id": book_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
