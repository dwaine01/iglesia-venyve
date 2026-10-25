"""L2 · entregar libro en pocos toques: desde el perfil (mentor sin capacidad
de Librería, doble toque, sin existencias → pendiente), destinatario sin
identificar ligado a la vivienda con tarea «completar nombre» y su
completado sin volver a descontar, y seguimiento con responsable y próxima
acción que NO inicia Consolidación."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


def door(number, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "opened": True, "contact_level": "brief", **extra}


@pytest.mark.asyncio
async def test_profile_delivery_unidentified_completion_and_followup():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    book_id = f"bk-{tag}"
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, beto_id, outsider_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto", "Ajeno")]
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        outsider = await fx.account(outsider_id, "persona")
        ana_user = str((await db.users.find_one({"person_id": ana_id}, {"_id": 1}))["_id"])
        for pid in (ana_id, beto_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{pid}", "person_id": pid, "active": True})
        await db.library_books.insert_one({"_id": book_id, "book_id": book_id, "sku": f"T{tag}".upper(), "name": f"Libro {tag}", "is_active": True, "member_price_cents": 0})
        await pastora.post("/api/library/adjustments", json={"book_id": book_id, "direction": "increase", "quantity": 10, "reason": "Compra"})
        await pastora.post("/api/library/movements", json={"book_id": book_id, "movement_type": "ASSIGNMENT", "quantity": 2, "from_holder": {"type": "warehouse", "id": "central"}, "to_holder": {"type": "user", "id": ana_user}})
        today = date.today()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today.isoformat(), "end_date": today.isoformat(), "mentor_person_ids": [ana_id, beto_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await ana.put(f"{base}/my-street", json={"street_name": "Calle 18"})

        # Seguimiento con responsable y próxima acción: guarda el plan y NO inicia Consolidación.
        when = (today.replace(day=min(today.day, 28))).isoformat()
        followed = (await ana.post(f"{base}/doors", json=door("10", followup="yes", followup_date=when, followup_next_action="Llamar por teléfono", followup_responsible_person_id=beto_id,
                                                            person={"contact_name": f"Rosa {tag}", "contact_phone": f"555{tag[:6]}"}))).json()
        visit = followed["visits"][0]
        stored = await db.outreach_visits.find_one({"visit_id": visit["visit_id"]})
        assert stored["followup_accepted"] is True and stored["followup_responsible_person_id"] == beto_id and stored["next_action"] == "Llamar por teléfono"
        assert stored["next_action_at"].date().isoformat() == when and not stored.get("enrollment_id") and stored["status"] == "wants_followup"
        assert await db.process_enrollments.count_documents({"source_id": visit["visit_id"]}) == 0
        edited = await ana.put(f"/api/mentorship/outreach/visits/{visit['visit_id']}/followup", json={"accepted": True, "next_action": "Visitar el sábado", "next_action_date": when})
        assert edited.status_code == 200 and edited.json()["next_action"] == "Visitar el sábado"
        assert (await outsider.put(f"/api/mentorship/outreach/visits/{visit['visit_id']}/followup", json={"accepted": True})).status_code == 403
        assert (await ana.put(f"/api/mentorship/outreach/visits/{visit['visit_id']}/followup", json={"accepted": True, "responsible_person_id": outsider_id})).status_code == 422

        # Libro entregado en una vivienda sin saber a quién → tarea «completar nombre».
        saved = (await ana.post(f"{base}/doors", json=door("12", books=[{"book": book_id, "quantity": 1}]))).json()
        movement_id = saved["event"]["books"][0]["movement_id"]
        tasks = (await ana.get("/api/library/ledger/unidentified")).json()
        task = next(item for item in tasks["items"] if item["movement_id"] == movement_id)
        assert task["address_line1"] == "12 Calle 18" and task["recipient_status"] == "unidentified"
        assert not [item for item in (await beto.get("/api/library/ledger/unidentified")).json()["items"] if item["movement_id"] == movement_id]
        # Con persona en el mismo intento queda identificado.
        with_person = (await ana.post(f"{base}/doors", json=door("14", books=[{"book": book_id, "quantity": 1}], person={"contact_name": f"Luz {tag}"}))).json()
        assert (await db.library_movements.find_one({"movement_id": with_person["event"]["books"][0]["movement_id"]}))["recipient_status"] == "identified"

        # Completar: crea la persona contactada (misma revisión de duplicados) y NO vuelve a descontar.
        holdings_before = (await db.library_holdings.find_one({"book_id": book_id, "holder_type": "user", "holder_id": ana_user}))["quantity_on_hand"]
        assert (await beto.post(f"/api/library/ledger/movements/{movement_id}/recipient", json={"contact_type": "new", "contact_name": "X"})).status_code == 403
        dup = await ana.post(f"/api/library/ledger/movements/{movement_id}/recipient", json={"contact_type": "new", "contact_name": "Otra", "contact_phone": f"555{tag[:6]}"})
        assert dup.status_code == 409  # teléfono ya registrado: la revisión de duplicados de siempre
        done = (await ana.post(f"/api/library/ledger/movements/{movement_id}/recipient", json={"contact_type": "new", "contact_name": f"Mario {tag}"})).json()
        assert done["already"] is False and done["visit_id"] and done["movement"]["recipient_status"] == "identified"
        completion = await db.library_movements.find_one({"movement_id": done["completion_id"]})
        assert completion["already_counted"] is True and completion["completes_movement_id"] == movement_id and completion["counts_in_balance"] is False
        again = (await ana.post(f"/api/library/ledger/movements/{movement_id}/recipient", json={"contact_type": "new", "contact_name": f"Mario {tag}"})).json()
        assert again["already"] is True
        assert (await db.library_holdings.find_one({"book_id": book_id, "holder_type": "user", "holder_id": ana_user}))["quantity_on_hand"] == holdings_before
        row = next(item for item in (await ana.get("/api/library/ledger/my-balance")).json()["items"] if item["book_id"] == book_id)
        assert (row["received"], row["delivered"], row["balance"]) == (2, 2, 0)
        assert not [item for item in (await ana.get("/api/library/ledger/unidentified")).json()["items"] if item["movement_id"] == movement_id]

        # Entregar desde el perfil: el mentor de esa persona puede (sin capacidad de Librería); doble toque no duplica;
        # sin existencias → pendiente de conciliar (si lo pide), nunca bloquea en silencio.
        person_id = await fx.person(f"RosaPerfil{tag}")
        await db.outreach_visits.update_one({"visit_id": visit["visit_id"]}, {"$set": {"converted_person_id": person_id}})
        await pastora.post("/api/library/movements", json={"book_id": book_id, "movement_type": "ASSIGNMENT", "quantity": 1, "from_holder": {"type": "warehouse", "id": "central"}, "to_holder": {"type": "user", "id": ana_user}})
        key = f"profile-{tag}"
        first = await ana.post(f"/api/library/persons/{person_id}/deliver", json={"book_id": book_id, "quantity": 1, "idempotency_key": key})
        assert first.status_code == 201, first.text
        second = await ana.post(f"/api/library/persons/{person_id}/deliver", json={"book_id": book_id, "quantity": 1, "idempotency_key": key})
        assert second.json()["movement_id"] == first.json()["movement_id"]
        assert first.json()["visit_id"] == visit["visit_id"] and first.json()["household_id"] == followed["household"]["household_id"]
        no_stock = await ana.post(f"/api/library/persons/{person_id}/deliver", json={"book_id": book_id, "quantity": 1, "idempotency_key": f"{key}-2"})
        assert no_stock.status_code == 409 and no_stock.json()["detail"]["code"] == "no_stock"
        pending = (await ana.post(f"/api/library/persons/{person_id}/deliver", json={"book_id": book_id, "quantity": 1, "idempotency_key": f"{key}-3", "allow_pending": True})).json()
        assert pending["movement_type"] == "DELIVERY_PENDING" and pending["person_id"] == person_id
        assert (await outsider.post(f"/api/library/persons/{person_id}/deliver", json={"book_id": book_id, "quantity": 1})).status_code == 403
        materials = (await ana.get(f"/api/library/persons/{person_id}/materials")).json()["items"]
        assert {item["movement_type"] for item in materials} >= {"DELIVERY", "DELIVERY_PENDING"}
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns", "library_movements"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.library_movements.delete_many({"$or": [{"book_id": book_id}, {"idempotency_key": {"$regex": tag}}]})
        await db.library_books.delete_many({"_id": book_id})
        await db.library_holdings.delete_many({"book_id": book_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
