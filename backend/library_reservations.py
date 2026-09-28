"""Librería 360 · Fase 3: Reserva Automática basada en inscripciones a procesos
(Consolidación/Ley de 7 Semanas, LBS, Discipulados, Educación, Mentoría, CAP, y
cualquier proceso futuro vinculado por `process_key`). Calcula déficit en vivo y
reconcilia el ledger con reservas por inscripción — nunca crea, aprueba ni envía
una Orden de Compra automáticamente."""
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from library_module import (
    CENTRAL_HOLDER, HolderInput, MovementInput, apply_movement, canonical_book,
    now_utc, require_library_manager, serialize,
)
from server import db, get_current_user

router = APIRouter(prefix="/api/library/reservations", tags=["library-reservations"])

NEEDING_STATUSES = {"planned", "active", "paused"}
AUTO_RESERVATION_ACTOR = "system:auto_reservation"


def manager(current_user: dict = Depends(get_current_user)) -> dict:
    require_library_manager(current_user)
    return current_user


async def ensure_indexes() -> None:
    await db.library_reservations.create_index("reservation_id", unique=True)
    await db.library_reservations.create_index([("book_id", 1), ("status", 1)])
    await db.library_reservations.create_index([("enrollment_id", 1), ("status", 1)])


async def sync_process_reservations() -> dict:
    """Reconcilia reservas automáticas con las inscripciones activas de cada
    proceso: crea reservas nuevas para inscripciones sin reserva y libera las
    que quedaron huérfanas (inscripción cancelada/completada). Idempotente."""
    books = await db.library_books.find({"is_active": True, "process_key": {"$ne": None}}, {"_id": 0}).to_list(2000)
    books_by_process: dict[str, list[dict]] = {}
    for book in books:
        books_by_process.setdefault(book["process_key"], []).append(book)
    if not books_by_process:
        return {"created": 0, "released": 0}

    enrollments = await db.process_enrollments.find(
        {"process_key": {"$in": list(books_by_process.keys())}},
        {"_id": 0, "enrollment_id": 1, "process_key": 1, "status": 1, "person_id": 1},
    ).to_list(20000)
    status_by_enrollment = {e["enrollment_id"]: e for e in enrollments}
    needing_by_process: dict[str, list[dict]] = {}
    for e in enrollments:
        if e["status"] in NEEDING_STATUSES:
            needing_by_process.setdefault(e["process_key"], []).append(e)

    existing = await db.library_reservations.find({"status": "active"}, {"_id": 0}).to_list(20000)
    existing_by_key = {(r["book_id"], r["enrollment_id"]): r for r in existing}

    released = 0
    for reservation in existing:
        enrollment = status_by_enrollment.get(reservation["enrollment_id"])
        still_needed = bool(enrollment and enrollment["status"] in NEEDING_STATUSES)
        if still_needed:
            continue
        movement = await apply_movement(
            MovementInput(
                book_id=reservation["book_id"], movement_type="RESERVATION_RELEASE", quantity=reservation["quantity"],
                from_holder=HolderInput(**CENTRAL_HOLDER), person_id=reservation.get("person_id"),
                process_key=reservation.get("process_key"),
                notes=f"Liberación automática · inscripción {reservation['enrollment_id']} ya no requiere el material",
            ),
            AUTO_RESERVATION_ACTOR,
        )
        await db.library_reservations.update_one(
            {"reservation_id": reservation["reservation_id"]},
            {"$set": {"status": "released", "released_at": now_utc(), "release_movement_id": movement["movement_id"],
                      "release_reason": "enrollment_no_longer_active"}},
        )
        released += 1

    created = 0
    for process_key, books_in_process in books_by_process.items():
        for enrollment in needing_by_process.get(process_key, []):
            for book in books_in_process:
                key = (book["book_id"], enrollment["enrollment_id"])
                if key in existing_by_key:
                    continue
                movement = await apply_movement(
                    MovementInput(
                        book_id=book["book_id"], movement_type="RESERVATION", quantity=1,
                        to_holder=HolderInput(**CENTRAL_HOLDER), person_id=enrollment.get("person_id"),
                        process_key=process_key, notes=f"Reserva automática · inscripción {enrollment['enrollment_id']}",
                    ),
                    AUTO_RESERVATION_ACTOR,
                )
                reservation_id = str(uuid4())
                await db.library_reservations.insert_one({
                    "_id": reservation_id, "reservation_id": reservation_id, "book_id": book["book_id"],
                    "book_name": book["name"], "process_key": process_key, "enrollment_id": enrollment["enrollment_id"],
                    "person_id": enrollment.get("person_id"), "quantity": 1, "status": "active",
                    "movement_id": movement["movement_id"], "release_movement_id": None,
                    "created_at": now_utc(), "released_at": None, "release_reason": None,
                })
                created += 1
    return {"created": created, "released": released}


async def _process_names() -> dict:
    definitions = await db.process_definitions.find({}, {"_id": 0, "process_key": 1, "name": 1, "version": 1}).to_list(200)
    names: dict[str, tuple[int, str]] = {}
    for d in definitions:
        current = names.get(d["process_key"])
        if not current or d["version"] > current[0]:
            names[d["process_key"]] = (d["version"], d["name"])
    return {key: value[1] for key, value in names.items()}


async def _deficit_rows(book_filter: Optional[dict] = None) -> list[dict]:
    query: dict = {"is_active": True, "process_key": {"$ne": None}}
    if book_filter:
        query.update(book_filter)
    books = await db.library_books.find(query, {"_id": 0}).sort("name", 1).to_list(2000)
    if not books:
        return []
    process_keys = {book["process_key"] for book in books}
    enrollments = await db.process_enrollments.find(
        {"process_key": {"$in": list(process_keys)}}, {"_id": 0, "process_key": 1, "status": 1},
    ).to_list(20000)
    needed_by_process: dict[str, int] = {}
    for e in enrollments:
        if e["status"] in NEEDING_STATUSES:
            needed_by_process[e["process_key"]] = needed_by_process.get(e["process_key"], 0) + 1

    book_ids = [book["book_id"] for book in books]
    holdings = await db.library_holdings.find(
        {"holder_type": "warehouse", "holder_id": "central", "book_id": {"$in": book_ids}}, {"_id": 0},
    ).to_list(5000)
    holding_by_book = {h["book_id"]: h for h in holdings}
    names = await _process_names()

    rows = []
    for book in books:
        central = holding_by_book.get(book["book_id"], {"quantity_on_hand": 0, "reserved_qty": 0})
        stock = central.get("quantity_on_hand", 0)
        total_reserved = central.get("reserved_qty", 0)
        my_reserved = await db.library_reservations.count_documents({"book_id": book["book_id"], "status": "active"})
        other_reserved = max(0, total_reserved - my_reserved)
        needed = needed_by_process.get(book["process_key"], 0)
        available_real = stock - other_reserved
        deficit = max(0, needed - available_real)
        rows.append({
            "book_id": book["book_id"], "book_name": book["name"], "cover_file_id": book.get("cover_file_id"),
            "process_key": book["process_key"], "process_name": names.get(book["process_key"], book["process_key"]),
            "enrolled_count": needed, "stock": stock, "other_reserved": other_reserved,
            "available_real": available_real, "deficit": deficit, "cost_price_cents": book.get("cost_price_cents", 0),
            "provider": book.get("provider"),
        })
    rows.sort(key=lambda item: item["deficit"], reverse=True)
    return rows


async def compute_deficit_report() -> list[dict]:
    await sync_process_reservations()
    return await _deficit_rows()


async def compute_book_deficit(book_id: str) -> dict:
    await canonical_book(book_id)
    await sync_process_reservations()
    rows = await _deficit_rows({"book_id": book_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Este material no está vinculado a ningún proceso activo")
    return rows[0]


@router.get("/deficit-report", response_model=dict)
async def deficit_report(current_user: dict = Depends(manager)):
    rows = await compute_deficit_report()
    return {"items": serialize(rows)}


@router.post("/sync", response_model=dict)
async def trigger_sync(current_user: dict = Depends(manager)):
    return await sync_process_reservations()
