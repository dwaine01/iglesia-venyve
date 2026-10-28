"""R2c · El libro queda unido al expediente de Consolidación (al entregar, o al abrir el expediente después)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import server
from library_ledger import record_pending_delivery  # noqa: E402 (después de cargar el servidor)
from library_module import HolderInput, MovementInput, apply_movement
from process_engine import create_enrollment

db = server.db


@pytest.mark.asyncio
async def test_delivery_links_to_open_enrollment_and_prior_deliveries_link_on_open():
    tag = uuid.uuid4().hex[:8]
    book_id, mentor_user = f"book-{tag}", f"user-{tag}"
    people = [f"person-{tag}-{n}" for n in range(3)]
    now = datetime.now(timezone.utc)
    await db.library_books.insert_one({"_id": book_id, "book_id": book_id, "name": f"MCD {tag}", "member_price_cents": 0})
    await db.library_holdings.insert_one({"_id": f"h-{tag}", "book_id": book_id, "holder_type": "user", "holder_id": mentor_user, "quantity_on_hand": 10, "reserved_qty": 0})
    enrollment_ids = []
    try:
        def delivery(person_id):
            return MovementInput(book_id=book_id, movement_type="DELIVERY", quantity=1, from_holder=HolderInput(type="user", id=mentor_user),
                                 to_holder=HolderInput(type="person", id=person_id), person_id=person_id)
        # 1) Con expediente abierto: la entrega queda unida a él.
        open_enrollment, _ = await create_enrollment(db, "consolidation", people[0], None, "qa", source="qa_r2c")
        enrollment_ids.append(open_enrollment["enrollment_id"])
        moved = await apply_movement(delivery(people[0]), "qa")
        assert moved["enrollment_id"] == open_enrollment["enrollment_id"] and moved["enrollment_link_source"] == "delivery"

        # 2) Entregado en la puerta antes de abrir el expediente: al abrirlo se une (también la pendiente de conciliar).
        early = await apply_movement(delivery(people[1]), "qa")
        pending = await record_pending_delivery(book_id=book_id, book_label="MCD", quantity=1, mentor_user_id=mentor_user, person_id=people[1], campaign_id=None,
                                                process_key=None, idempotency_key=f"idem-{tag}", reason="qa", actor_user_id="qa")
        assert early["enrollment_id"] is None and pending["enrollment_id"] is None
        later, _ = await create_enrollment(db, "consolidation", people[1], None, "qa", source="qa_r2c")
        enrollment_ids.append(later["enrollment_id"])
        linked = await db.library_movements.find({"person_id": people[1]}, {"_id": 0, "enrollment_id": 1, "enrollment_link_source": 1}).to_list(10)
        assert {row["enrollment_id"] for row in linked} == {later["enrollment_id"]} and {row["enrollment_link_source"] for row in linked} == {"enrollment_opened"}

        # 3) Libros del expediente anterior (ya cerrado) NO pasan al expediente nuevo.
        old_id = f"old-{tag}"
        await db.process_enrollments.insert_one({"_id": old_id, "enrollment_id": old_id, "process_key": "consolidation", "person_id": people[2], "status": "completed",
                                                 "created_at": now - timedelta(days=90), "completed_at": now - timedelta(days=30)})
        enrollment_ids.append(old_id)
        movement_id = f"mv-{tag}"
        await db.library_movements.insert_one({"_id": movement_id, "movement_id": movement_id, "book_id": book_id, "movement_type": "DELIVERY", "quantity": 1, "person_id": people[2],
                                               "occurred_at": now - timedelta(days=60), "is_reversal": False})
        fresh, _ = await create_enrollment(db, "consolidation", people[2], None, "qa", source="qa_r2c")
        enrollment_ids.append(fresh["enrollment_id"])
        assert not (await db.library_movements.find_one({"movement_id": movement_id})).get("enrollment_id")
    finally:
        await db.library_movements.delete_many({"book_id": book_id})
        await db.library_holdings.delete_many({"book_id": book_id})
        await db.library_books.delete_one({"book_id": book_id})
        await db.process_stage_progress.delete_many({"enrollment_id": {"$in": enrollment_ids}})
        await db.process_timeline.delete_many({"enrollment_id": {"$in": enrollment_ids}})
        await db.process_enrollments.delete_many({"enrollment_id": {"$in": enrollment_ids}})
