"""Auditoría 9/10: el MCD entregado en la puerta queda ligado a la visita y a la persona; marcar
«Recibió MCD» en el informe ya no descuenta otro libro."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_door_book_is_linked_and_not_delivered_twice():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    campaign_id, created_book = None, None
    try:
        pastora = await fx.account(await fx.person(f"PastoraL{tag}"), "pastora")
        mentor_id = await fx.person(f"MentorL{tag}")
        mentor = await fx.account(mentor_id, "persona")
        mentor_user = str((await db.users.find_one({"person_id": mentor_id}, {"_id": 1}))["_id"])
        await db.mentor_badges.insert_one({"_id": f"badge-l-{tag}", "person_id": mentor_id, "active": True})
        book = await db.library_books.find_one({"sku": "MCD"}, {"_id": 0, "book_id": 1})
        if not book:
            created_book = f"mcd-{tag}"
            await db.library_books.insert_one({"_id": created_book, "book_id": created_book, "sku": "MCD", "name": "MCD", "is_active": True, "member_price_cents": 0})
            book = {"book_id": created_book}
        await db.library_books.update_one({"book_id": book["book_id"]}, {"$set": {"is_active": True}})
        await pastora.post("/api/library/adjustments", json={"book_id": book["book_id"], "direction": "increase", "quantity": 3, "reason": "Compra prueba"})
        assigned = await pastora.post("/api/library/movements", json={"book_id": book["book_id"], "movement_type": "ASSIGNMENT", "quantity": 3,
                                                                       "from_holder": {"type": "warehouse", "id": "central"}, "to_holder": {"type": "user", "id": mentor_user}})
        assert assigned.status_code in (200, 201), assigned.text
        today = date.today().isoformat()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Invasión L {tag}", "location": "Calle", "start_date": today, "end_date": today, "mentor_person_ids": [mentor_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await mentor.put(f"{base}/my-street", json={"street_name": "Calle L"})
        door = await mentor.post(f"{base}/doors", json={"client_request_id": f"req-{tag}", "house_number": "12", "opened": True, "contact_level": "conversation",
                                                         "books": [{"book": "MCD", "quantity": 1}], "person": {"contact_type": "new", "contact_name": f"Rosa Puerta{tag}"}})
        assert door.status_code == 201, door.text
        visit = await db.outreach_visits.find_one({"campaign_id": campaign_id}, {"_id": 0})
        assert visit["received_mcd"] is True and visit["mcd_delivery_movement_id"]  # la visita ya sabe que recibió el MCD
        deliveries = {"campaign_id": campaign_id, "movement_type": {"$in": ["DELIVERY", "DELIVERY_PENDING"]}, "is_reversal": {"$ne": True}}
        assert await db.library_movements.count_documents(deliveries) == 1

        # El informe marca «Recibió MCD»: NO se crea otra entrega.
        report = await mentor.put(f"/api/mentorship/outreach/visits/{visit['visit_id']}/report", json={"status": "wants_followup", "received_mcd": True, "confirm_distinct_person": True, "distinct_reason": "Persona nueva de prueba"})
        assert report.status_code == 200, report.text
        assert await db.library_movements.count_documents(deliveries) == 1
        # Al pasar a Consolidación se crea la Persona 360 y el libro de la puerta pasa a ser suyo.
        started = await mentor.post(f"/api/mentorship/outreach/visits/{visit['visit_id']}/start-seven-weeks", json={})
        assert started.status_code == 200, started.text
        assert await db.library_movements.count_documents(deliveries) == 1
        visit = await db.outreach_visits.find_one({"visit_id": visit["visit_id"]}, {"_id": 0})
        person_id = visit.get("converted_person_id")
        assert person_id
        movement = await db.library_movements.find_one(deliveries, {"_id": 0})
        assert movement["person_id"] == person_id and movement["recipient_status"] == "identified"  # ligado a la persona
    finally:
        if campaign_id:
            visits = await db.outreach_visits.distinct("converted_person_id", {"campaign_id": campaign_id})
            fx.person_ids.extend([pid for pid in visits if pid])
            enrollments = await db.process_enrollments.distinct("enrollment_id", {"campaign_id": campaign_id})
            for name in ("process_enrollments", "process_stage_progress", "consolidation_activities", "mentor_assignments", "process_timeline"):
                await db[name].delete_many({"enrollment_id": {"$in": enrollments}})
            for name in ("outreach_visits", "outreach_households", "outreach_visit_events", "outreach_participations", "library_movements", "outreach_campaigns"):
                await db[name].delete_many({"campaign_id": campaign_id})
        await db.mentor_badges.delete_many({"_id": f"badge-l-{tag}"})
        if created_book:
            await db.library_books.delete_many({"book_id": created_book})
        await fx.cleanup()
