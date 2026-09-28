"""Librería 360 · Fase 4: escaneo de QR/código de barras para identificar
materiales y personas rápidamente. NUNCA crea un inventario paralelo — cada
acción confirmada reutiliza los mismos endpoints/ledger de Fases 1-3
(deliver/movements/receive); este módulo solo resuelve qué material o persona
corresponde a un código escaneado o buscado."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import re

from library_module import canonical_person, participant, person_display_name, serialize
from library_reservations import sync_process_reservations
from membership_documents import membership_id_from_token
from server import db

router = APIRouter(prefix="/api/library/scan", tags=["library-scan"])


class ResolvePersonInput(BaseModel):
    code: str = Field(min_length=1, max_length=500)


async def _book_holding_snapshot(book_id: str) -> dict:
    holding = await db.library_holdings.find_one({"book_id": book_id, "holder_type": "warehouse", "holder_id": "central"}, {"_id": 0})
    return {"available_central": (holding or {}).get("quantity_on_hand", 0), "reserved_central": (holding or {}).get("reserved_qty", 0)}


@router.get("/resolve-material", response_model=dict)
async def resolve_material(code: str, current_user: dict = Depends(participant)):
    raw = code.strip()
    if not raw:
        raise HTTPException(status_code=422, detail="Código vacío")
    stripped = raw[8:] if raw.upper().startswith("VYV-LIB-") else raw
    book = await db.library_books.find_one({"book_id": stripped}, {"_id": 0})
    if not book:
        book = await db.library_books.find_one({"barcode": raw}, {"_id": 0})
    if not book:
        book = await db.library_books.find_one({"qr_code": {"$regex": f"^{re.escape(raw)}$", "$options": "i"}}, {"_id": 0})
    if not book:
        book = await db.library_books.find_one({"sku": {"$regex": f"^{re.escape(raw)}$", "$options": "i"}}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="No se encontró ningún material con ese código")
    snapshot = await _book_holding_snapshot(book["book_id"])
    return serialize({**book, **snapshot})


@router.post("/resolve-person", response_model=dict)
async def resolve_person(payload: ResolvePersonInput, current_user: dict = Depends(participant)):
    code = payload.code.strip()
    membership_id = membership_id_from_token(code)
    person = None
    if membership_id:
        membership = await db.person_memberships.find_one({"membership_id": membership_id}, {"_id": 0, "person_id": 1})
        if membership:
            person = await canonical_person(membership["person_id"])
    if not person:
        membership = await db.person_memberships.find_one({"member_number": code}, {"_id": 0, "person_id": 1})
        if membership:
            person = await canonical_person(membership["person_id"])
    if not person:
        try:
            person = await canonical_person(code)
        except HTTPException:
            person = None
    if not person:
        raise HTTPException(status_code=404, detail="No se encontró ninguna persona con ese código. Intente la búsqueda manual.")
    return {"person_id": person["person_id"], "display_name": person_display_name(person)}


@router.get("/search-person", response_model=dict)
async def search_person(q: str, current_user: dict = Depends(participant)):
    query = q.strip()
    if len(query) < 2:
        return {"items": []}
    safe_query = re.escape(query)
    persons = await db.persons.find(
        {"is_archived": {"$ne": True}, "$or": [
            {"display_name": {"$regex": safe_query, "$options": "i"}},
            {"full_name": {"$regex": safe_query, "$options": "i"}},
            {"nombre_completo": {"$regex": safe_query, "$options": "i"}},
            {"nombre": {"$regex": safe_query, "$options": "i"}},
        ]},
        {"_id": 1, "person_id": 1, "display_name": 1, "full_name": 1, "nombre_completo": 1, "nombre": 1, "apellido": 1},
    ).limit(15).to_list(15)
    items = []
    for person in persons:
        person["person_id"] = person.get("person_id") or str(person["_id"])
        items.append({"person_id": person["person_id"], "display_name": person_display_name(person)})
    return {"items": items}


@router.get("/persons/{person_id}/library-snapshot", response_model=dict)
async def person_library_snapshot(person_id: str, current_user: dict = Depends(participant)):
    person = await canonical_person(person_id)
    await sync_process_reservations()
    enrollments = await db.process_enrollments.find(
        {"person_id": person["person_id"], "status": {"$in": ["planned", "active", "paused"]}},
        {"_id": 0, "process_key": 1},
    ).to_list(200)
    process_keys = list({e["process_key"] for e in enrollments})
    books = await db.library_books.find({"process_key": {"$in": process_keys}, "is_active": True}, {"_id": 0}).to_list(500) if process_keys else []
    delivered_book_ids = set(await db.library_movements.distinct("book_id", {"person_id": person["person_id"], "movement_type": {"$in": ["DELIVERY", "LOAN"]}}))
    reservations = await db.library_reservations.find({"person_id": person["person_id"], "status": "active"}, {"_id": 0}).to_list(500)
    reserved_book_ids = {r["book_id"] for r in reservations}
    materials = []
    for book in books:
        status = "received" if book["book_id"] in delivered_book_ids else ("reserved" if book["book_id"] in reserved_book_ids else "pending")
        materials.append({"book_id": book["book_id"], "book_name": book["name"], "cover_file_id": book.get("cover_file_id"),
                           "process_key": book["process_key"], "status": status})
    movements = await db.library_movements.find(
        {"person_id": person["person_id"], "payment_status": {"$in": ["pendiente", "pago_parcial"]}}, {"_id": 0},
    ).sort("occurred_at", -1).to_list(200)
    pending_payments = []
    for m in movements:
        balance = max(0, (m.get("list_price_cents") or 0) - (m.get("amount_paid_cents") or 0))
        if balance > 0:
            pending_payments.append({"movement_id": m["movement_id"], "book_name": m["book_name"], "occurred_at": m["occurred_at"],
                                      "list_price_cents": m.get("list_price_cents") or 0, "amount_paid_cents": m.get("amount_paid_cents") or 0,
                                      "balance_cents": balance, "payment_status": m.get("payment_status")})
    return serialize({"person_id": person["person_id"], "display_name": person_display_name(person), "materials": materials, "pending_payments": pending_payments})
