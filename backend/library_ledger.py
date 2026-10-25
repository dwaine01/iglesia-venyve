"""L1 · Trazabilidad de libros: UNA sola bitácora (`library_movements`).

- Cada movimiento puede llevar `idempotency_key` (única: el doble toque nunca
  descuenta dos veces), vínculos `household_id` / `visit_id` /
  `visit_event_id`, estado del destinatario (`identified` /
  `unidentified`) y `already_counted` + `completes_movement_id` (completar
  un destinatario sin volver a descontar; lo usa L2).
- Entrega «sin descuento de inventario» (el libro no estaba cargado o el
  mentor no tenía existencias): se registra igual en la bitácora como
  `DELIVERY_PENDING` (`inventory_status=pending_reconciliation`) y NO resta
  del saldo del mentor hasta que Librería la concilie (entonces pasa a
  `DELIVERY` y descuenta).
- Saldo del mentor calculado de la bitácora, por material:
  recibidos − entregados − devueltos ± transferidos (± correcciones).
  `library_holdings` sigue como resumen rápido; si no cuadra se muestra la
  diferencia a Librería para conciliar. Nada se corrige solo.
- Migración segura e idempotente de lo ya entregado (puerta a puerta y
  visitas con MCD/NPT).

«Librería» = quien gestiona Librería 360 (`is_library_manager`: autoridad
pastoral, coordinador general, `library.catalog.manage`,
`library.inventory.manage`); lectura también con `library.reports.read`."""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from access_control import LIBRARY_REPORTS_READ, has_capability
from library_module import CENTRAL_HOLDER, HolderInput, MovementInput, adjust_holding, apply_movement, holder_label, is_library_manager, serialize
from server import db, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/library/ledger", tags=["library-ledger"])

PENDING_TYPE = "DELIVERY_PENDING"
RESERVATION_TYPES = {"RESERVATION", "RESERVATION_RELEASE"}
DOOR_DELIVERY_HOLDER = {"type": "writeoff", "id": "door_delivery"}
MIGRATION_KEY = "library_ledger_migration_v1"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def can_read_ledger(current_user: dict) -> bool:
    return is_library_manager(current_user) or has_capability(current_user, LIBRARY_REPORTS_READ)


# ------------------------------------------------------------------ entrega pendiente de conciliar
async def record_pending_delivery(*, book_id: Optional[str], book_label: str, quantity: int, mentor_user_id: Optional[str], person_id: Optional[str],
                                  campaign_id: Optional[str], process_key: Optional[str], idempotency_key: str, reason: str, actor_user_id: str,
                                  household_id: Optional[str] = None, visit_id: Optional[str] = None, visit_event_id: Optional[str] = None,
                                  occurred_at: Optional[datetime] = None, notes: str = "") -> dict:
    """Entrega real que no pudo descontar: queda en la bitácora sin tocar
    existencias ni saldo. Idempotente por `idempotency_key`."""
    existing = await db.library_movements.find_one({"idempotency_key": idempotency_key}, {"_id": 0})
    if existing:
        return existing
    from_holder = {"type": "user", "id": mentor_user_id} if mentor_user_id else None
    to_holder = {"type": "person", "id": person_id} if person_id else DOOR_DELIVERY_HOLDER
    movement_id = str(uuid4())
    when = occurred_at or now_utc()
    doc = {
        "_id": movement_id, "movement_id": movement_id, "book_id": book_id, "book_name": book_label, "movement_type": PENDING_TYPE, "quantity": quantity,
        "from_holder": from_holder, "to_holder": to_holder, "from_holder_label": await holder_label(from_holder) if from_holder else "Mentor sin cuenta",
        "to_holder_label": await holder_label(to_holder), "person_id": person_id, "process_key": process_key, "campaign_id": campaign_id,
        "notes": notes or "Entregado sin descuento de inventario (pendiente de conciliar)", "actor_user_id": actor_user_id, "scan_method": "MANUAL",
        "occurred_at": when, "created_at": now_utc(), "is_reversal": False, "reversed_movement_id": None, "reversed_by_movement_id": None,
        "idempotency_key": idempotency_key, "household_id": household_id, "visit_id": visit_id, "visit_event_id": visit_event_id,
        "recipient_status": "identified" if (person_id or visit_id) else "unidentified", "already_counted": False, "completes_movement_id": None,
        "inventory_status": "pending_reconciliation", "counts_in_balance": False, "pending_reason": reason,
    }
    try:
        await db.library_movements.insert_one(doc)
    except DuplicateKeyError:
        return await db.library_movements.find_one({"idempotency_key": idempotency_key}, {"_id": 0})
    return doc


# ------------------------------------------------------------------ saldo desde la bitácora
def _counts(movement: dict) -> bool:
    return movement.get("movement_type") not in RESERVATION_TYPES | {PENDING_TYPE} and movement.get("counts_in_balance", True) is not False


async def ledger_balances(user_ids: Optional[list[str]] = None) -> dict[tuple[str, str], dict]:
    """{(user_id, book_id): recibidos, entregados, devueltos, transferidos, correcciones, saldo, pendientes}."""
    match: dict = {"$or": [{"to_holder.type": "user"}, {"from_holder.type": "user"}]}
    if user_ids is not None:
        match = {"$or": [{"to_holder.type": "user", "to_holder.id": {"$in": user_ids}}, {"from_holder.type": "user", "from_holder.id": {"$in": user_ids}}]}
    rows: dict[tuple[str, str], dict] = defaultdict(lambda: {"received": 0, "delivered": 0, "returned": 0, "transferred_in": 0, "transferred_out": 0,
                                                             "other_out": 0, "corrections": 0, "pending_delivered": 0})
    async for movement in db.library_movements.find(match, {"_id": 0, "movement_type": 1, "quantity": 1, "from_holder": 1, "to_holder": 1, "book_id": 1,
                                                            "is_reversal": 1, "counts_in_balance": 1}):
        kind, quantity = movement.get("movement_type"), movement.get("quantity") or 0
        to_holder, from_holder = movement.get("to_holder") or {}, movement.get("from_holder") or {}
        if kind == PENDING_TYPE:
            if from_holder.get("type") == "user" and (user_ids is None or from_holder.get("id") in user_ids):
                rows[(from_holder["id"], movement.get("book_id") or "")]["pending_delivered"] += quantity
            continue
        if not _counts(movement):
            continue
        if to_holder.get("type") == "user" and (user_ids is None or to_holder.get("id") in user_ids):
            row = rows[(to_holder["id"], movement["book_id"])]
            if movement.get("is_reversal"):
                row["corrections"] += quantity
            elif kind == "TRANSFER":
                row["transferred_in"] += quantity
            else:
                row["received"] += quantity
        if from_holder.get("type") == "user" and (user_ids is None or from_holder.get("id") in user_ids):
            row = rows[(from_holder["id"], movement["book_id"])]
            if movement.get("is_reversal"):
                row["corrections"] -= quantity
            elif kind in {"DELIVERY", "LOAN"}:
                row["delivered"] += quantity
            elif kind == "RETURN":
                row["returned"] += quantity
            elif kind == "TRANSFER":
                row["transferred_out"] += quantity
            else:
                row["other_out"] += quantity
    for row in rows.values():
        row["balance"] = row["received"] - row["delivered"] - row["returned"] + row["transferred_in"] - row["transferred_out"] - row["other_out"] + row["corrections"]
    return rows


async def _books(book_ids) -> dict:
    ids = [item for item in set(book_ids) if item]
    return {doc["book_id"]: doc for doc in await db.library_books.find({"book_id": {"$in": ids}}, {"_id": 0, "book_id": 1, "name": 1, "sku": 1}).to_list(len(ids) or 1)}


async def balance_view(user_id: str) -> dict:
    rows = await ledger_balances([user_id])
    cache = {doc["book_id"]: doc.get("quantity_on_hand", 0) async for doc in db.library_holdings.find({"holder_type": "user", "holder_id": user_id}, {"_id": 0, "book_id": 1, "quantity_on_hand": 1})}
    books = await _books([key[1] for key in rows] + list(cache))
    items = []
    for book_id in sorted({key[1] for key in rows} | set(cache), key=lambda item: (books.get(item, {}).get("name") or "zzz")):
        row = rows.get((user_id, book_id)) or {"received": 0, "delivered": 0, "returned": 0, "transferred_in": 0, "transferred_out": 0, "other_out": 0, "corrections": 0, "pending_delivered": 0, "balance": 0}
        if not book_id and not row["pending_delivered"]:
            continue
        items.append({"book_id": book_id or None, "name": books.get(book_id, {}).get("name") or "Libro sin cargar en Librería", "sku": books.get(book_id, {}).get("sku"),
                      **row, "cached_on_hand": cache.get(book_id) if book_id else None, "discrepancy": (cache.get(book_id, 0) - row["balance"]) if book_id else 0})
    return {"user_id": user_id, "items": items, "pending_total": sum(item["pending_delivered"] for item in items)}


@router.get("/my-balance", response_model=dict)
async def my_balance(current_user: dict = Depends(get_current_user)):
    """Saldo propio calculado de la bitácora (el mentor ve solo lo suyo)."""
    return await balance_view(current_user["user_id"])


@router.get("/balances/{user_id}", response_model=dict)
async def user_balance(user_id: str, current_user: dict = Depends(get_current_user)):
    if user_id != current_user["user_id"] and not can_read_ledger(current_user):
        raise HTTPException(status_code=403, detail="Solo Librería ve el saldo de otras personas")
    return await balance_view(user_id)


@router.get("/discrepancies", response_model=dict)
async def discrepancies(current_user: dict = Depends(get_current_user)):
    """Resumen rápido (`library_holdings`) vs bitácora, y entregas pendientes de
    conciliar por mentor. Solo informa: no corrige nada."""
    if not can_read_ledger(current_user):
        raise HTTPException(status_code=403, detail="Solo Librería")
    rows = await ledger_balances()
    cache = {(doc["holder_id"], doc["book_id"]): doc.get("quantity_on_hand", 0) async for doc in db.library_holdings.find({"holder_type": "user"}, {"_id": 0, "holder_id": 1, "book_id": 1, "quantity_on_hand": 1})}
    keys = {key for key in rows if key[1]} | set(cache)
    books = await _books([key[1] for key in keys])
    from bson import ObjectId
    user_ids = list({key[0] for key in keys} | {key[0] for key, row in rows.items() if row["pending_delivered"]})
    users = {str(doc["_id"]): doc.get("nombre") or doc.get("email") async for doc in db.users.find({"_id": {"$in": [ObjectId(item) for item in user_ids if ObjectId.is_valid(item)]}}, {"nombre": 1, "email": 1})}
    differences = []
    for key in keys:
        ledger = (rows.get(key) or {}).get("balance", 0)
        cached = cache.get(key, 0)
        if ledger != cached:
            differences.append({"user_id": key[0], "user_name": users.get(key[0]) or "Cuenta", "book_id": key[1], "book_name": books.get(key[1], {}).get("name") or key[1],
                                "ledger_balance": ledger, "cached_on_hand": cached, "difference": cached - ledger})
    pending: dict[str, dict] = defaultdict(lambda: {"quantity": 0, "movements": 0})
    async for movement in db.library_movements.find({"movement_type": PENDING_TYPE}, {"_id": 0, "from_holder": 1, "quantity": 1}):
        holder = (movement.get("from_holder") or {}).get("id") or "sin-cuenta"
        pending[holder]["quantity"] += movement.get("quantity") or 0
        pending[holder]["movements"] += 1
    differences.sort(key=lambda row: (row["user_name"], row["book_name"]))
    return {"differences": differences, "pending_by_mentor": sorted(({"user_id": key, "user_name": users.get(key) or ("Mentor sin cuenta" if key == "sin-cuenta" else "Cuenta"), **value}
                                                                     for key, value in pending.items()), key=lambda row: -row["quantity"]),
            "pending_total": sum(value["quantity"] for value in pending.values())}


@router.get("/pending", response_model=dict)
async def pending_deliveries(user_id: Optional[str] = None, limit: int = 200, current_user: dict = Depends(get_current_user)):
    """Entregas sin descuento de inventario. El mentor ve las suyas; Librería, todas."""
    query: dict = {"movement_type": PENDING_TYPE}
    if not can_read_ledger(current_user):
        query["from_holder.id"] = current_user["user_id"]
    elif user_id:
        query["from_holder.id"] = user_id
    items = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).limit(max(1, min(limit, 1000))).to_list(1000)
    return {"items": serialize(items), "total": await db.library_movements.count_documents(query)}


class ReconcileInput(BaseModel):
    book_id: Optional[str] = Field(default=None, max_length=80)  # obligatorio si el libro no estaba cargado
    register_missing_assignment: bool = False  # registrar desde Central la asignación que faltaba
    notes: str = Field(default="", max_length=500)


@router.post("/pending/{movement_id}/reconcile", response_model=dict)
async def reconcile(movement_id: str, payload: ReconcileInput, current_user: dict = Depends(get_current_user)):
    """Librería concilia una entrega pendiente: (opcional) registra la
    asignación que faltaba de Central al mentor y entonces descuenta. Idempotente."""
    if not is_library_manager(current_user):
        raise HTTPException(status_code=403, detail="Solo Librería concilia entregas")
    movement = await db.library_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if movement.get("inventory_status") == "reconciled":
        return serialize(movement)
    if movement.get("movement_type") != PENDING_TYPE:
        raise HTTPException(status_code=409, detail="Este movimiento no está pendiente de conciliar")
    book_id = payload.book_id or movement.get("book_id")
    if not book_id or not await db.library_books.find_one({"book_id": book_id}, {"_id": 1}):
        raise HTTPException(status_code=422, detail="Elija el libro del catálogo al que corresponde esta entrega")
    mentor = movement.get("from_holder")
    if not mentor:
        raise HTTPException(status_code=409, detail="El mentor no tiene cuenta con inventario; regístrele una cuenta antes de conciliar")
    quantity = movement["quantity"]
    assignment_id = None
    if payload.register_missing_assignment:
        assignment = await apply_movement(MovementInput(book_id=book_id, movement_type="ASSIGNMENT", quantity=quantity, from_holder=HolderInput(**CENTRAL_HOLDER),
                                                        to_holder=HolderInput(**mentor), campaign_id=movement.get("campaign_id"),
                                                        notes=f"Asignación faltante registrada al conciliar la entrega {movement_id}",
                                                        idempotency_key=f"reconcile-assign:{movement_id}"), current_user["user_id"])
        assignment_id = assignment["movement_id"]
    # Descuenta del mentor y suma al destino (igual que una entrega normal).
    claim = await db.library_movements.update_one({"movement_id": movement_id, "movement_type": PENDING_TYPE}, {"$set": {"inventory_status": "reconciling"}})
    if not claim.modified_count:
        return serialize(await db.library_movements.find_one({"movement_id": movement_id}, {"_id": 0}))
    try:
        await adjust_holding(book_id, mentor, on_hand_delta=-quantity)
    except HTTPException:
        await db.library_movements.update_one({"movement_id": movement_id}, {"$set": {"inventory_status": "pending_reconciliation"}})
        raise HTTPException(status_code=409, detail="El mentor no tiene existencias de ese libro: marque «registrar la asignación que faltaba» o corrija su inventario")
    await adjust_holding(book_id, movement.get("to_holder") or DOOR_DELIVERY_HOLDER, on_hand_delta=quantity)
    book = await db.library_books.find_one({"book_id": book_id}, {"_id": 0, "name": 1})
    await db.library_movements.update_one({"movement_id": movement_id}, {"$set": {
        "movement_type": "DELIVERY", "book_id": book_id, "book_name": (book or {}).get("name") or movement.get("book_name"), "inventory_status": "reconciled",
        "counts_in_balance": True, "reconciled_at": now_utc(), "reconciled_by_user_id": current_user["user_id"], "reconcile_assignment_movement_id": assignment_id,
        "reconcile_notes": (payload.notes or "").strip() or None}})
    return serialize(await db.library_movements.find_one({"movement_id": movement_id}, {"_id": 0}))


# ------------------------------------------------------------------ migración segura
async def migrate_existing_deliveries() -> dict:
    """Idempotente y sin borrar nada:
    1. Entregas del puerta a puerta que sí descontaron → se vinculan a su
       vivienda, intento y persona (y reciben su clave).
    2. Las «sin descuento de inventario» → `DELIVERY_PENDING` en la bitácora
       (no restan del saldo) y el intento guarda su `movement_id`.
    3. Entregas de MCD/NPT por visita → se vinculan a la visita y vivienda.
    4. Toda entrega sin estado de destinatario → identificado / sin identificar."""
    stats = {"door_linked": 0, "door_pending_created": 0, "visit_linked": 0, "recipient_marked": 0}
    async for event in db.outreach_visit_events.find({"books.0": {"$exists": True}}, {"_id": 0, "visit_event_id": 1, "household_id": 1, "campaign_id": 1, "mentor_person_id": 1,
                                                                                       "books": 1, "client_request_id": 1, "created_by_user_id": 1, "occurred_at": 1}):
        visit = await db.outreach_visits.find_one({"visit_event_id": event["visit_event_id"]}, {"_id": 0, "visit_id": 1, "person_id": 1, "converted_person_id": 1, "contact_type": 1})
        mentor = await db.users.find_one({"person_id": event.get("mentor_person_id")}, {"_id": 1}) if event.get("mentor_person_id") else None
        base_key = event.get("client_request_id") or event["visit_event_id"]
        changed = False
        books = event.get("books") or []
        for index, row in enumerate(books):
            links = {"household_id": event.get("household_id"), "visit_event_id": event["visit_event_id"], "visit_id": (visit or {}).get("visit_id")}
            if row.get("movement_id"):
                result = await db.library_movements.update_one({"movement_id": row["movement_id"], "visit_event_id": {"$in": [None]}},
                                                               {"$set": links})
                if result.modified_count:
                    stats["door_linked"] += 1
                await db.library_movements.update_one({"movement_id": row["movement_id"], "idempotency_key": {"$exists": False}}, {"$set": {"idempotency_key": f"door:{base_key}:{index}"}})
                continue
            person_id = row.get("person_id") or ((visit or {}).get("person_id") if (visit or {}).get("contact_type") == "existing" else None)
            pending = await record_pending_delivery(
                book_id=row.get("book_id"), book_label=row.get("name") or row.get("book") or "Libro", quantity=row.get("quantity") or 1,
                mentor_user_id=str(mentor["_id"]) if mentor else None, person_id=person_id, campaign_id=event.get("campaign_id"), process_key="outreach",
                idempotency_key=f"door-pending:{event['visit_event_id']}:{index}", reason=row.get("reason") or "Sin descuento de inventario",
                actor_user_id=event.get("created_by_user_id") or "system:migration", occurred_at=event.get("occurred_at"), **links)
            if pending.get("movement_id") and not row.get("movement_id"):
                books[index] = {**row, "movement_id": pending["movement_id"], "inventory_status": "not_discounted"}
                changed = True
                stats["door_pending_created"] += 1
        if changed:
            await db.outreach_visit_events.update_one({"visit_event_id": event["visit_event_id"]}, {"$set": {"books": books}})
    async for visit in db.outreach_visits.find({"$or": [{"mcd_delivery_movement_id": {"$nin": [None, ""]}}, {"npt_delivery_movement_id": {"$nin": [None, ""]}}]},
                                               {"_id": 0, "visit_id": 1, "household_id": 1, "visit_event_id": 1, "mcd_delivery_movement_id": 1, "npt_delivery_movement_id": 1}):
        for field, sku in (("mcd_delivery_movement_id", "MCD"), ("npt_delivery_movement_id", "NPT")):
            if visit.get(field):
                result = await db.library_movements.update_one({"movement_id": visit[field], "visit_id": {"$in": [None]}},
                                                               {"$set": {"visit_id": visit["visit_id"], "household_id": visit.get("household_id"), "visit_event_id": visit.get("visit_event_id")}})
                await db.library_movements.update_one({"movement_id": visit[field], "idempotency_key": {"$exists": False}}, {"$set": {"idempotency_key": f"visit:{visit['visit_id']}:{sku}"}})
                stats["visit_linked"] += result.modified_count
    for status, condition in (("identified", {"person_id": {"$nin": [None, ""]}}), ("unidentified", {"person_id": {"$in": [None, ""]}})):
        result = await db.library_movements.update_many({"movement_type": {"$in": ["DELIVERY", "LOAN"]}, "recipient_status": {"$exists": False}, **condition},
                                                        {"$set": {"recipient_status": status, "already_counted": False}})
        stats["recipient_marked"] += result.modified_count
    await db.app_settings.update_one({"_id": MIGRATION_KEY}, {"$set": {"last_run_at": now_utc(), "last_stats": stats}, "$setOnInsert": {"first_run_at": now_utc()}}, upsert=True)
    return stats


@router.post("/migrate", response_model=dict)
async def run_migration(current_user: dict = Depends(get_current_user)):
    """Volver a correr la migración (idempotente) y ver qué hizo."""
    if not is_library_manager(current_user):
        raise HTTPException(status_code=403, detail="Solo Librería")
    return await migrate_existing_deliveries()


async def startup_migration() -> None:
    try:
        await migrate_existing_deliveries()
    except Exception:  # noqa: BLE001 — nunca impide arrancar el servidor
        logger.warning("library ledger: la migración falló", exc_info=True)


# ------------------------------------------------------------------ L2 · completar destinatario
async def _can_touch(movement: dict, current_user: dict) -> bool:
    if is_library_manager(current_user):
        return True
    from mentorship_outreach import is_outreach_leader
    if is_outreach_leader(current_user):
        return True
    return (movement.get("from_holder") or {}).get("id") == current_user["user_id"]


@router.get("/unidentified", response_model=dict)
async def unidentified_recipients(scope: str = "mine", limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Tareas «completar nombre»: libros entregados en una vivienda sin saber a quién.
    El mentor ve las suyas; Librería y líderes de invasión pueden ver todas."""
    from mentorship_outreach import is_outreach_leader
    query: dict = {"movement_type": {"$in": ["DELIVERY", PENDING_TYPE]}, "recipient_status": "unidentified", "household_id": {"$nin": [None, ""]}}
    if scope != "all" or not (is_library_manager(current_user) or is_outreach_leader(current_user)):
        query["from_holder.id"] = current_user["user_id"]
    items = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).limit(max(1, min(limit, 500))).to_list(500)
    house_ids = list({item["household_id"] for item in items})
    houses = {doc["household_id"]: doc async for doc in db.outreach_households.find({"household_id": {"$in": house_ids}}, {"_id": 0, "household_id": 1, "address_line1": 1, "address_line2": 1, "street_name": 1, "campaign_id": 1})}
    for item in items:
        house = houses.get(item["household_id"]) or {}
        item["address_line1"], item["address_line2"] = house.get("address_line1"), house.get("address_line2")
    return {"items": serialize(items), "total": await db.library_movements.count_documents(query)}


class RecipientInput(BaseModel):
    contact_type: str = Field(default="new", pattern="^(new|existing)$")
    person_id: Optional[str] = Field(default=None, max_length=80)
    contact_name: Optional[str] = Field(default=None, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=40)


@router.post("/movements/{movement_id}/recipient", response_model=dict)
async def complete_recipient(movement_id: str, payload: RecipientInput, current_user: dict = Depends(get_current_user)):
    """Completa a quién se entregó un libro YA contado: se vincula a la persona
    (con la misma revisión de duplicados de Persona 360 / visitas) y queda un
    registro `RECIPIENT_COMPLETION` con `already_counted=True`; NO vuelve a
    descontar. Idempotente."""
    movement = await db.library_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    if not movement or movement.get("movement_type") not in {"DELIVERY", PENDING_TYPE}:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    if not await _can_touch(movement, current_user):
        raise HTTPException(status_code=403, detail="Solo quien entregó el libro, Librería o un líder de la invasión")
    if movement.get("recipient_status") == "identified":
        return {"movement": serialize(movement), "already": True}
    visit = None
    person_id = payload.person_id if payload.contact_type == "existing" else None
    household = await db.outreach_households.find_one({"household_id": movement.get("household_id")}, {"_id": 0}) if movement.get("household_id") else None
    if household and household.get("campaign_id") and household.get("mentor_person_id"):
        from mentorship_outreach import resolve_and_insert_contact_visit
        try:
            visit = await resolve_and_insert_contact_visit(
                payload.contact_type, payload.person_id, payload.contact_name, payload.contact_phone, household.get("street_name") or household.get("sector"),
                household["campaign_id"], household["mentor_person_id"], "Destinatario completado de un libro entregado", current_user,
                household_id=household["household_id"], visit_event_id=movement.get("visit_event_id"))
            await db.outreach_visits.update_one({"visit_id": visit["visit_id"]}, {"$set": {"address_line1": household.get("address_line1"), "address_line2": household.get("address_line2"), "status": "visited"}})
        except HTTPException as exc:
            # Persona existente que ya tiene su visita: se vincula sin crear otra.
            if not (exc.status_code == 409 and payload.contact_type == "existing" and payload.person_id):
                raise
    elif payload.contact_type != "existing" or not payload.person_id:
        raise HTTPException(status_code=422, detail="Elija la persona en Persona 360")
    if person_id:
        from bson import ObjectId
        if not ObjectId.is_valid(person_id) or not await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 1}):
            raise HTTPException(status_code=404, detail="Persona no encontrada")
    now = now_utc()
    completion_id = str(uuid4())
    completion = {
        "_id": completion_id, "movement_id": completion_id, "book_id": movement.get("book_id"), "book_name": movement.get("book_name"), "movement_type": "RECIPIENT_COMPLETION",
        "quantity": movement.get("quantity"), "from_holder": None, "to_holder": None, "person_id": person_id, "campaign_id": movement.get("campaign_id"),
        "process_key": movement.get("process_key"), "notes": "Destinatario completado (sin volver a descontar)", "actor_user_id": current_user["user_id"],
        "occurred_at": now, "created_at": now, "is_reversal": False, "idempotency_key": f"complete:{movement_id}", "household_id": movement.get("household_id"),
        "visit_id": (visit or {}).get("visit_id"), "visit_event_id": movement.get("visit_event_id"), "recipient_status": "identified",
        "already_counted": True, "completes_movement_id": movement_id, "counts_in_balance": False, "inventory_status": "not_applicable",
    }
    try:
        await db.library_movements.insert_one(completion)
    except DuplicateKeyError:
        return {"movement": serialize(await db.library_movements.find_one({"movement_id": movement_id}, {"_id": 0})), "already": True}
    await db.library_movements.update_one({"movement_id": movement_id}, {"$set": {
        "recipient_status": "identified", "person_id": person_id or movement.get("person_id"), "visit_id": (visit or {}).get("visit_id") or movement.get("visit_id"),
        "recipient_completed_at": now, "completed_by_movement_id": completion_id}})
    return {"movement": serialize(await db.library_movements.find_one({"movement_id": movement_id}, {"_id": 0})), "completion_id": completion_id,
            "visit_id": (visit or {}).get("visit_id"), "already": False}
