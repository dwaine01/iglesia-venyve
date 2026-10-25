"""L3 · consulta y recorrido: resumen por mentor y por material, cifras con
detalle (destinatario, dirección, seguimiento), recorrido del libro,
permisos (mentor solo lo suyo, encargados ven todo, 403 al pedir otro) y el
reporte de invasión leyendo estos datos."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


def door(number, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "opened": True, "contact_level": "brief", **extra}


@pytest.mark.asyncio
async def test_trace_summary_items_journey_permissions_and_report():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    book_id = f"bk-{tag}"
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, beto_id, lead_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto", "Lead")]
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        lead = await fx.account(lead_id, "persona")
        await db.users.update_one({"person_id": lead_id}, {"$addToSet": {"capabilities": "consolidation.assign"}})
        ana_user = str((await db.users.find_one({"person_id": ana_id}, {"_id": 1}))["_id"])
        beto_user = str((await db.users.find_one({"person_id": beto_id}, {"_id": 1}))["_id"])
        for pid in (ana_id, beto_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{pid}", "person_id": pid, "active": True})
        await db.library_books.insert_one({"_id": book_id, "book_id": book_id, "sku": f"T{tag}".upper(), "name": f"Libro {tag}", "is_active": True, "member_price_cents": 0})
        await pastora.post("/api/library/adjustments", json={"book_id": book_id, "direction": "increase", "quantity": 20, "reason": "Compra"})
        today = date.today().isoformat()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today, "end_date": today, "mentor_person_ids": [ana_id, beto_id]})).json()["campaign_id"]
        for user in (ana_user, beto_user):
            await pastora.post("/api/library/movements", json={"book_id": book_id, "movement_type": "ASSIGNMENT", "quantity": 4, "campaign_id": campaign_id, "from_holder": {"type": "warehouse", "id": "central"}, "to_holder": {"type": "user", "id": user}})
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await ana.put(f"{base}/my-street", json={"street_name": "Calle 18"})
        # Ana: 1 sin nombre, 2 a Rosa (acepta seguimiento), y 3 sin existencias (pendientes).
        await ana.post(f"{base}/doors", json=door("10", books=[{"book": book_id, "quantity": 1}]))
        await ana.post(f"{base}/doors", json=door("12", unit="3", books=[{"book": book_id, "quantity": 2}], followup="yes", followup_next_action="Llamar por teléfono", person={"contact_name": f"Rosa {tag}"}))
        await ana.post(f"{base}/doors", json=door("14", books=[{"book": book_id, "quantity": 3}]))

        # Mentor: solo lo suyo. Ana: 4 recibidos · 3 entregados · 1 disponible · 3 sin conciliar.
        mine = (await ana.get("/api/library/ledger/trace/summary")).json()
        assert mine["scope"] == "mine" and len(mine["rows"]) == 1
        row = mine["rows"][0]
        assert (row["received"], row["delivered"], row["available"], row["pending"], row["followup"]) == (4, 3, 1, 3, 2)
        assert row["identified"] == 2 and row["unidentified"] == 4
        assert (await ana.get("/api/library/ledger/trace/summary", params={"mentor_user_id": beto_user})).status_code == 403
        assert (await beto.get("/api/library/ledger/trace/items", params={"metric": "delivered", "mentor_user_id": ana_user})).status_code == 403

        # Encargados (Consolidación / pastoral): todos, por mentor y por material; filtro por invasión.
        everyone = (await lead.get("/api/library/ledger/trace/summary", params={"campaign_id": campaign_id})).json()
        by_name = {item["key"]: item for item in everyone["rows"]}
        assert by_name[ana_user]["delivered"] == 3 and by_name[beto_user]["received"] == 4 and by_name[beto_user]["delivered"] == 0
        material = (await pastora.get("/api/library/ledger/trace/summary", params={"group_by": "material", "campaign_id": campaign_id})).json()
        assert next(item for item in material["rows"] if item["key"] == book_id)["received"] == 8

        # Cifras con detalle: destinatario, dirección/apartamento y seguimiento.
        followed = (await ana.get("/api/library/ledger/trace/items", params={"metric": "followup"})).json()
        assert followed["total"] == 1
        item = followed["items"][0]
        assert item["recipient_name"] == f"Rosa {tag}" and item["address_line1"] == "12 Calle 18" and item["address_line2"] == "Apt 3"
        assert item["followup"]["accepted"] is True and item["followup"]["next_action"] == "Llamar por teléfono"
        assert (await ana.get("/api/library/ledger/trace/items", params={"metric": "pending"})).json()["total"] == 1
        assert (await ana.get("/api/library/ledger/trace/items", params={"metric": "unidentified"})).json()["total"] == 2
        assert (await ana.get("/api/library/ledger/trace/items", params={"metric": "received"})).json()["total"] == 1

        # Recorrido del libro.
        journey = (await ana.get(f"/api/library/ledger/trace/movement/{item['movement_id']}")).json()
        assert [step["step"] for step in journey["steps"]] == ["library", "delivery", "recipient", "followup"]
        assert (await beto.get(f"/api/library/ledger/trace/movement/{item['movement_id']}")).status_code == 403

        # Reporte de invasión: libros entregados, con destinatario y con seguimiento.
        report = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        assert report["books_trace"] == {"delivered": 6, "pending_reconciliation": 3, "identified": 2, "unidentified": 4, "with_followup": 2}
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns", "library_movements"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.library_movements.delete_many({"book_id": book_id})
        await db.library_books.delete_many({"_id": book_id})
        await db.library_holdings.delete_many({"book_id": book_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
