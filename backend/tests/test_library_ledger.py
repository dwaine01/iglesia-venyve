"""L1 · trazabilidad de libros: una sola bitácora con clave contra doble toque,
vínculos con vivienda/intento/visita, entregas «sin descuento» pendientes de
conciliar (no restan del saldo), saldo calculado de la bitácora, diferencias
con el resumen, conciliación por Librería, permisos y migración segura."""
import uuid
from datetime import date, datetime, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from library_ledger import migrate_existing_deliveries
from library_module import HolderInput, MovementInput, apply_movement

db = server.db


def door(number, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "opened": True, "contact_level": "brief", **extra}


@pytest.mark.asyncio
async def test_ledger_idempotency_links_pending_balance_reconcile_and_migration():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    book_id = f"bk-{tag}"
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id = await fx.person(f"Ana{tag}")
        ana = await fx.account(ana_id, "persona")
        ana_user = str((await db.users.find_one({"person_id": ana_id}, {"_id": 1}))["_id"])
        await db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": ana_id, "active": True})
        await db.library_books.insert_one({"_id": book_id, "book_id": book_id, "sku": f"T{tag}".upper(), "name": f"Libro {tag}", "is_active": True, "member_price_cents": 0})
        # Central recibe 10 y asigna 3 a Ana.
        assert (await pastora.post("/api/library/adjustments", json={"book_id": book_id, "direction": "increase", "quantity": 10, "reason": "Compra inicial"})).status_code == 201
        assigned = await pastora.post("/api/library/movements", json={"book_id": book_id, "movement_type": "ASSIGNMENT", "quantity": 3, "from_holder": {"type": "warehouse", "id": "central"}, "to_holder": {"type": "user", "id": ana_user}})
        assert assigned.status_code == 201, assigned.text

        # Clave idempotente en la bitácora: dos veces la misma clave = un solo descuento.
        key = f"test:{tag}"
        first = await apply_movement(MovementInput(book_id=book_id, movement_type="ADJUSTMENT", quantity=1, to_holder=HolderInput(type="warehouse", id="central"), notes="x", idempotency_key=key), "t")
        second = await apply_movement(MovementInput(book_id=book_id, movement_type="ADJUSTMENT", quantity=1, to_holder=HolderInput(type="warehouse", id="central"), notes="x", idempotency_key=key), "t")
        assert first["movement_id"] == second["movement_id"] and await db.library_movements.count_documents({"idempotency_key": key}) == 1

        today = date.today().isoformat()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today, "end_date": today, "mentor_person_ids": [ana_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await ana.put(f"{base}/my-street", json={"street_name": "Calle 18"})
        # Entrega en la puerta: 2 que sí descuentan + 1 libro no cargado (pendiente). Doble toque = nada extra.
        payload = door("10", books=[{"book": book_id, "quantity": 2}, {"book": "NO-CARGADO", "quantity": 1}])
        saved = (await ana.post(f"{base}/doors", json=payload)).json()
        again = (await ana.post(f"{base}/doors", json=payload)).json()
        assert again["duplicate"] is True
        event = saved["event"]
        rows = {row["book"]: row for row in event["books"]}
        assert rows[book_id]["inventory_status"] == "discounted" and rows["NO-CARGADO"]["inventory_status"] == "not_discounted" and rows["NO-CARGADO"]["movement_id"]
        delivered = await db.library_movements.find_one({"movement_id": rows[book_id]["movement_id"]})
        assert delivered["household_id"] == saved["household"]["household_id"] and delivered["visit_event_id"] == event["visit_event_id"]
        assert delivered["recipient_status"] == "unidentified" and delivered["idempotency_key"] == f"door:{payload['client_request_id']}:0" and delivered["already_counted"] is False
        pending_row = await db.library_movements.find_one({"movement_id": rows["NO-CARGADO"]["movement_id"]})
        assert pending_row["movement_type"] == "DELIVERY_PENDING" and pending_row["inventory_status"] == "pending_reconciliation" and pending_row["book_id"] is None
        # Sin existencias: 5 más quedan pendientes y NO restan.
        no_stock = (await ana.post(f"{base}/doors", json=door("12", books=[{"book": book_id, "quantity": 5}]))).json()
        pending_id = no_stock["event"]["books"][0]["movement_id"]
        assert (await db.library_movements.find_one({"movement_id": pending_id}))["movement_type"] == "DELIVERY_PENDING"
        assert await db.library_movements.count_documents({"visit_event_id": {"$in": [event["visit_event_id"], no_stock["event"]["visit_event_id"]]}}) == 3

        # Saldo de la bitácora: recibidos 3 − entregados 2 = 1; pendientes 6 aparte; cuadra con el resumen.
        mine = (await ana.get("/api/library/ledger/my-balance")).json()
        row = next(item for item in mine["items"] if item["book_id"] == book_id)
        assert (row["received"], row["delivered"], row["balance"], row["pending_delivered"], row["cached_on_hand"], row["discrepancy"]) == (3, 2, 1, 5, 1, 0)
        assert mine["pending_total"] == 6
        # Diferencia con el resumen: se informa, no se corrige.
        await db.library_holdings.update_one({"book_id": book_id, "holder_type": "user", "holder_id": ana_user}, {"$inc": {"quantity_on_hand": 2}})
        report = (await pastora.get("/api/library/ledger/discrepancies")).json()
        diff = next(item for item in report["differences"] if item["book_id"] == book_id and item["user_id"] == ana_user)
        assert diff["ledger_balance"] == 1 and diff["cached_on_hand"] == 3 and diff["difference"] == 2
        assert next(item for item in report["pending_by_mentor"] if item["user_id"] == ana_user)["quantity"] == 6
        assert (await db.library_holdings.find_one({"book_id": book_id, "holder_type": "user", "holder_id": ana_user}))["quantity_on_hand"] == 3
        await db.library_holdings.update_one({"book_id": book_id, "holder_type": "user", "holder_id": ana_user}, {"$inc": {"quantity_on_hand": -2}})

        # Permisos: el mentor no concilia ni ve las diferencias de todos; ve sus pendientes.
        assert (await ana.post(f"/api/library/ledger/pending/{pending_id}/reconcile", json={})).status_code == 403
        assert (await ana.get("/api/library/ledger/discrepancies")).status_code == 403
        assert (await ana.get(f"/api/library/ledger/balances/{ana_user}")).status_code == 200
        assert (await ana.get("/api/library/ledger/pending")).json()["total"] == 2

        # Conciliar: sin existencias falla claro; con «asignación que faltaba», descuenta. Idempotente.
        assert (await pastora.post(f"/api/library/ledger/pending/{pending_id}/reconcile", json={})).status_code == 409
        done = (await pastora.post(f"/api/library/ledger/pending/{pending_id}/reconcile", json={"register_missing_assignment": True})).json()
        assert done["movement_type"] == "DELIVERY" and done["inventory_status"] == "reconciled" and done["reconcile_assignment_movement_id"]
        assert (await pastora.post(f"/api/library/ledger/pending/{pending_id}/reconcile", json={"register_missing_assignment": True})).json()["inventory_status"] == "reconciled"
        row = next(item for item in (await ana.get("/api/library/ledger/my-balance")).json()["items"] if item["book_id"] == book_id)
        assert (row["received"], row["delivered"], row["balance"], row["pending_delivered"], row["discrepancy"]) == (8, 7, 1, 0, 0)
        # El libro no cargado exige elegir el material del catálogo.
        assert (await pastora.post(f"/api/library/ledger/pending/{rows['NO-CARGADO']['movement_id']}/reconcile", json={})).status_code == 422

        # Migración: un intento antiguo con una entrega sin descuento (sin movimiento) y una que descontó sin vínculos.
        legacy_move = await apply_movement(MovementInput(book_id=book_id, movement_type="DELIVERY", quantity=1, from_holder=HolderInput(type="user", id=ana_user),
                                                         to_holder=HolderInput(type="writeoff", id="door_delivery"), campaign_id=campaign_id, notes="antiguo"), "t")
        await db.library_movements.update_one({"movement_id": legacy_move["movement_id"]}, {"$unset": {"household_id": "", "visit_event_id": "", "recipient_status": ""}})
        legacy_event = f"ev-{tag}"
        await db.outreach_visit_events.insert_one({"_id": legacy_event, "visit_event_id": legacy_event, "household_id": f"hh-{tag}", "campaign_id": campaign_id, "mentor_person_id": ana_id,
                                                   "client_request_id": f"old-{tag}", "occurred_at": datetime.now(timezone.utc), "created_by_user_id": ana_user,
                                                   "books": [{"book": book_id, "book_id": book_id, "name": "x", "quantity": 1, "inventory_status": "discounted", "movement_id": legacy_move["movement_id"]},
                                                             {"book": "OTRO", "book_id": None, "name": "Otro", "quantity": 2, "inventory_status": "not_discounted", "movement_id": None, "reason": "no cargado"}]})
        holdings_before = [(doc["holder_id"], doc["book_id"], doc["quantity_on_hand"]) async for doc in db.library_holdings.find({"book_id": book_id})]
        stats = await migrate_existing_deliveries()
        assert stats["door_linked"] >= 1 and stats["door_pending_created"] >= 1
        migrated = await db.outreach_visit_events.find_one({"_id": legacy_event})
        assert migrated["books"][1]["movement_id"]
        linked = await db.library_movements.find_one({"movement_id": legacy_move["movement_id"]})
        assert linked["visit_event_id"] == legacy_event and linked["household_id"] == f"hh-{tag}" and linked["recipient_status"] == "unidentified"
        # Idempotente y sin tocar existencias.
        count = await db.library_movements.count_documents({"visit_event_id": legacy_event})
        await migrate_existing_deliveries()
        assert await db.library_movements.count_documents({"visit_event_id": legacy_event}) == count == 2
        assert [(doc["holder_id"], doc["book_id"], doc["quantity_on_hand"]) async for doc in db.library_holdings.find({"book_id": book_id})] == holdings_before
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns", "library_movements"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.outreach_visit_events.delete_many({"_id": f"ev-{tag}"})
        await db.library_movements.delete_many({"$or": [{"book_id": book_id}, {"idempotency_key": {"$regex": tag}}]})
        await db.library_books.delete_many({"_id": book_id})
        await db.library_holdings.delete_many({"book_id": book_id})
        await db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await fx.cleanup()
