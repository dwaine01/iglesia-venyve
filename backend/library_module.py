"""Librería 360 (Fase 1): catálogo maestro, inventario tipo ledger, cadena de
custodia, entrega desde Persona 360, solicitudes internas y enlace con Finanzas.
"""
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4
import re

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from access_control import (
    LIBRARY_CATALOG_MANAGE, LIBRARY_DELIVER, LIBRARY_INVENTORY_MANAGE, LIBRARY_REPORTS_READ,
    has_capability, is_general_coordinator, is_global_pastoral_authority,
)
from server import db, get_current_user

router = APIRouter(prefix="/api/library", tags=["library"])

MOVEMENT_TYPES = Literal[
    "PURCHASE_RECEIPT", "TRANSFER", "ASSIGNMENT", "DELIVERY", "RETURN", "DAMAGE",
    "LOSS", "ADJUSTMENT", "RESERVATION", "RESERVATION_RELEASE", "LOAN", "LOAN_RETURN",
]
HOLDER_TYPES = Literal["warehouse", "user", "person", "writeoff"]
PAYMENT_STATUSES = Literal["pagado", "pendiente", "exonerado", "beca", "descuento", "pago_parcial", "no_aplica"]
SCAN_METHODS = Literal["QR_SCAN", "BARCODE_SCAN", "MANUAL"]
CENTRAL_HOLDER = {"type": "warehouse", "id": "central"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items() if key != "_id"}
    return value


def is_library_manager(current_user: dict) -> bool:
    return (
        is_global_pastoral_authority(current_user)
        or is_general_coordinator(current_user)
        or has_capability(current_user, LIBRARY_CATALOG_MANAGE)
        or has_capability(current_user, LIBRARY_INVENTORY_MANAGE)
    )


def require_library_manager(current_user: dict) -> None:
    if not is_library_manager(current_user):
        raise HTTPException(status_code=403, detail="Solo Encargado de Librería, Pastor/a o Coordinación General")


def require_library_participant(current_user: dict) -> None:
    if not (is_library_manager(current_user) or has_capability(current_user, LIBRARY_DELIVER)):
        raise HTTPException(status_code=403, detail="No tiene acceso a Librería 360")


def manager(current_user: dict = Depends(get_current_user)) -> dict:
    require_library_manager(current_user)
    return current_user


def participant(current_user: dict = Depends(get_current_user)) -> dict:
    require_library_participant(current_user)
    return current_user


async def canonical_person(person_id: str) -> dict:
    queries = [{"person_id": person_id}, {"_id": person_id}]
    if ObjectId.is_valid(person_id):
        queries.append({"_id": ObjectId(person_id)})
    person = await db.persons.find_one({"$or": queries})
    if not person or person.get("is_archived") is True:
        raise HTTPException(status_code=404, detail="Persona 360 no encontrada")
    person["person_id"] = person.get("person_id") or str(person["_id"])
    return person


def person_display_name(person: dict) -> str:
    for key in ["display_name", "full_name", "nombre_completo"]:
        if person.get(key):
            return str(person[key]).strip()
    first = person.get("first_name") or person.get("nombre") or ""
    last = person.get("last_name") or person.get("apellido") or ""
    return " ".join(part for part in [first, last] if part).strip() or "Persona"


async def holder_label(holder: Optional[dict]) -> str:
    if not holder:
        return "—"
    holder_type, holder_id = holder.get("type"), holder.get("id")
    if holder_type == "warehouse":
        return "Inventario Central" if holder_id == "central" else f"Almacén {holder_id}"
    if holder_type == "writeoff":
        return {"damage": "Dañado", "loss": "Perdido", "adjustment": "Ajuste"}.get(holder_id, "Baja de inventario")
    if holder_type == "user":
        queries = [{"user_id": holder_id}, {"_id": holder_id}]
        if ObjectId.is_valid(holder_id):
            queries.append({"_id": ObjectId(holder_id)})
        user_doc = await db.users.find_one({"$or": queries}, {"_id": 0, "nombre": 1, "email": 1})
        return (user_doc or {}).get("nombre") or (user_doc or {}).get("email") or holder_id
    if holder_type == "person":
        try:
            person_doc = await canonical_person(holder_id)
            return person_display_name(person_doc)
        except HTTPException:
            return holder_id
    return str(holder_id)


def user_id_query(user_id: str) -> dict:
    queries = [{"_id": user_id}]
    if ObjectId.is_valid(user_id):
        queries.append({"_id": ObjectId(user_id)})
    return {"$or": queries}


class HolderInput(BaseModel):
    type: HOLDER_TYPES
    id: str


class LibraryBookInput(BaseModel):
    sku: Optional[str] = Field(default=None, max_length=40)
    name: str = Field(min_length=2, max_length=200)
    cover_image_url: Optional[str] = None
    description: str = Field(default="", max_length=2000)
    item_type: Literal["libro", "manual", "cuaderno", "guia", "material_retiro", "otro"] = "libro"
    process_key: Optional[str] = Field(default=None, max_length=80)
    level: Optional[str] = Field(default=None, max_length=80)
    edition: Optional[str] = Field(default=None, max_length=80)
    provider: Optional[str] = Field(default=None, max_length=160)
    cost_price_cents: int = Field(default=0, ge=0)
    member_price_cents: int = Field(default=0, ge=0)
    inventory_kind: Literal["consumable", "loanable"] = "consumable"
    is_active: bool = True
    min_stock: int = Field(default=0, ge=0)
    ideal_stock: int = Field(default=0, ge=0)
    location: Optional[str] = Field(default=None, max_length=160)
    qr_code: Optional[str] = Field(default=None, max_length=120)
    barcode: Optional[str] = Field(default=None, max_length=64)


class MovementInput(BaseModel):
    book_id: str
    movement_type: MOVEMENT_TYPES
    quantity: int = Field(gt=0)
    from_holder: Optional[HolderInput] = None
    to_holder: Optional[HolderInput] = None
    person_id: Optional[str] = None
    process_key: Optional[str] = Field(default=None, max_length=80)
    payment_status: Optional[PAYMENT_STATUSES] = None
    amount_charged_cents: Optional[int] = Field(default=None, ge=0)
    amount_paid_cents: Optional[int] = Field(default=None, ge=0)
    payment_method: Optional[str] = Field(default=None, max_length=40)
    due_date: Optional[date] = None
    notes: str = Field(default="", max_length=1000)
    scan_method: Optional[SCAN_METHODS] = None

    @model_validator(mode="after")
    def validate_holders(self):
        needs_from = {"TRANSFER", "ASSIGNMENT", "DELIVERY", "RETURN", "DAMAGE", "LOSS", "LOAN", "LOAN_RETURN"}
        needs_to = {"PURCHASE_RECEIPT", "TRANSFER", "ASSIGNMENT", "DELIVERY", "LOAN", "RETURN"}
        if self.movement_type in needs_from and not self.from_holder:
            raise ValueError("Este movimiento requiere origen (from_holder)")
        if self.movement_type in needs_to and not self.to_holder:
            raise ValueError("Este movimiento requiere destino (to_holder)")
        if self.movement_type in {"RESERVATION"} and not self.to_holder:
            raise ValueError("La reserva requiere un responsable (to_holder)")
        if self.movement_type in {"RESERVATION_RELEASE"} and not self.from_holder:
            raise ValueError("La liberación de reserva requiere el responsable (from_holder)")
        if self.movement_type == "LOAN" and not self.due_date:
            raise ValueError("Un préstamo requiere fecha esperada de devolución")
        return self


class DeliverBookInput(BaseModel):
    book_id: str
    quantity: int = Field(default=1, gt=0)
    from_holder: Optional[HolderInput] = None
    process_key: Optional[str] = Field(default=None, max_length=80)
    payment_status: PAYMENT_STATUSES = "no_aplica"
    amount_paid_cents: int = Field(default=0, ge=0)
    payment_method: Optional[str] = Field(default=None, max_length=40)
    notes: str = Field(default="", max_length=1000)
    as_loan: bool = False
    due_date: Optional[date] = None
    scan_method: Optional[SCAN_METHODS] = None


class RequestBookInput(BaseModel):
    book_id: str
    quantity: int = Field(gt=0)
    notes: str = Field(default="", max_length=500)


class ResolveRequestInput(BaseModel):
    quantity_approved: int = Field(ge=0)
    notes: str = Field(default="", max_length=500)


class LibrarianGrantInput(BaseModel):
    user_id: str


async def ensure_indexes_and_seed() -> None:
    await db.library_books.create_index("book_id", unique=True)
    await db.library_movements.create_index("movement_id", unique=True)
    await db.library_movements.create_index([("book_id", 1), ("occurred_at", -1)])
    await db.library_movements.create_index([("person_id", 1)])
    await db.library_holdings.create_index([("book_id", 1), ("holder_type", 1), ("holder_id", 1)], unique=True)
    await db.library_requests.create_index("request_id", unique=True)

    if await db.library_books.count_documents({}) == 0:
        now = now_utc()
        seed = [
            {"sku": "LBS1", "name": "LBS 1 · Liberación", "process_key": "seven_weeks", "member_price_cents": 0, "cost_price_cents": 300},
            {"sku": "LBS2", "name": "LBS 2 · Bendición", "process_key": "seven_weeks", "member_price_cents": 0, "cost_price_cents": 300},
            {"sku": "LBS3", "name": "LBS 3 · Sanidad", "process_key": "seven_weeks", "member_price_cents": 0, "cost_price_cents": 300},
            {"sku": "MCD", "name": "MCD", "process_key": "seven_weeks", "member_price_cents": 0, "cost_price_cents": 200},
            {"sku": "NPT", "name": "Nací Para Triunfar", "process_key": "seven_weeks", "member_price_cents": 0, "cost_price_cents": 250},
            {"sku": "DISC1", "name": "Discipulado 1", "process_key": "discipleship", "member_price_cents": 1500, "cost_price_cents": 700},
            {"sku": "DISC2", "name": "Discipulado 2", "process_key": "discipleship", "member_price_cents": 1500, "cost_price_cents": 800},
            {"sku": "DISC3", "name": "Discipulado 3", "process_key": "discipleship", "member_price_cents": 1500, "cost_price_cents": 800},
            {"sku": "DISC4", "name": "Discipulado 4", "process_key": "discipleship", "member_price_cents": 1500, "cost_price_cents": 800},
            {"sku": "RETIRO", "name": "Cuaderno de Retiro", "process_key": "seven_weeks", "item_type": "material_retiro", "member_price_cents": 500, "cost_price_cents": 300},
            {"sku": "MENTORIA", "name": "Guía de Mentoría", "process_key": "mentorship", "item_type": "guia", "member_price_cents": 0, "cost_price_cents": 400},
            {"sku": "CAP", "name": "Manual CAP", "process_key": "cap", "item_type": "manual", "member_price_cents": 0, "cost_price_cents": 400},
        ]
        docs = []
        for item in seed:
            book_id = str(uuid4())
            docs.append({
                "_id": book_id, "book_id": book_id, "sku": item["sku"], "name": item["name"],
                "cover_image_url": None, "description": "Catálogo de ejemplo — ajuste precios y existencias según su iglesia.",
                "item_type": item.get("item_type", "libro"), "process_key": item.get("process_key"),
                "level": None, "edition": None, "provider": None,
                "cost_price_cents": item["cost_price_cents"], "member_price_cents": item["member_price_cents"],
                "inventory_kind": "consumable", "is_active": True, "min_stock": 10, "ideal_stock": 40,
                "location": "Bodega principal", "qr_code": item["sku"], "is_example_seed": True,
                "created_by_user_id": "system:seed", "created_at": now, "updated_at": now,
            })
        await db.library_books.insert_many(docs)
    await ensure_library_finance_category()


async def canonical_book(book_id: str) -> dict:
    book = await db.library_books.find_one({"book_id": book_id}, {"_id": 0})
    if not book:
        raise HTTPException(status_code=404, detail="Material no encontrado en el catálogo")
    return book


async def get_holding(book_id: str, holder: dict) -> dict:
    doc = await db.library_holdings.find_one({"book_id": book_id, "holder_type": holder["type"], "holder_id": holder["id"]})
    return doc or {"quantity_on_hand": 0, "reserved_qty": 0}


async def adjust_holding(book_id: str, holder: dict, on_hand_delta: int = 0, reserved_delta: int = 0) -> None:
    now = now_utc()
    result = await db.library_holdings.find_one_and_update(
        {"book_id": book_id, "holder_type": holder["type"], "holder_id": holder["id"]},
        {"$inc": {"quantity_on_hand": on_hand_delta, "reserved_qty": reserved_delta}, "$set": {"updated_at": now},
         "$setOnInsert": {"_id": str(uuid4())}},
        upsert=True, return_document=True,
    )
    if (result.get("quantity_on_hand", 0) < 0) or (result.get("reserved_qty", 0) < 0):
        await db.library_holdings.update_one(
            {"book_id": book_id, "holder_type": holder["type"], "holder_id": holder["id"]},
            {"$inc": {"quantity_on_hand": -on_hand_delta, "reserved_qty": -reserved_delta}},
        )
        raise HTTPException(status_code=409, detail="Existencias insuficientes en el origen del movimiento")


def map_payment_method(value: Optional[str]) -> str:
    mapping = {"efectivo": "cash", "cash": "cash", "tarjeta": "card", "card": "card", "transferencia": "transfer",
               "transfer": "transfer", "zelle": "zelle", "cheque": "check", "check": "check", "ach": "ach"}
    return mapping.get((value or "").strip().lower(), "other")


async def record_library_income(person: dict, book: dict, amount_cents: int, payment_method: Optional[str], actor_user_id: str, movement_id: str) -> Optional[str]:
    if amount_cents <= 0:
        return None
    try:
        from finance_routes import Allocation, ContributionCreate, contribution_create
        fund = await db.finance_funds.find_one({"code": "GENERAL", "active": True}, {"_id": 0, "fund_id": 1})
        if not fund:
            return None
        payload = ContributionCreate(
            person_id=person["person_id"], amount_cents=amount_cents, received_date=date.today(),
            payment_method=map_payment_method(payment_method),
            allocations=[Allocation(fund_id=fund["fund_id"], amount_cents=amount_cents, contribution_type="libreria_material_educativo",
                                     description=f"Librería · {book['name']} · {person_display_name(person)}")],
            description=f"Pago de material educativo · {book['name']}", source="manual",
        )
        contribution = await contribution_create(payload, {"user_id": actor_user_id})
        await db.library_movements.update_one({"movement_id": movement_id}, {"$set": {"finance_contribution_id": contribution["contribution_id"]}})
        return contribution["contribution_id"]
    except Exception as exc:
        await db.library_movements.update_one({"movement_id": movement_id}, {"$set": {"finance_sync_error": str(exc)}})
        return None


async def ensure_library_finance_category() -> None:
    account = await db.finance_accounts.find_one({"code": "4060"})
    if not account:
        account_id = str(uuid4())
        await db.finance_accounts.insert_one({"_id": account_id, "account_id": account_id, "code": "4060", "name": "Ingresos por Librería y Materiales", "account_type": "revenue", "active": True, "created_at": now_utc()})
        account = {"account_id": account_id}
    if not await db.finance_contribution_types.find_one({"type_key": "libreria_material_educativo"}):
        await db.finance_contribution_types.insert_one({
            "_id": str(uuid4()), "type_key": "libreria_material_educativo", "name": "Librería / Material Educativo",
            "revenue_account_id": account["account_id"], "annual_statement_eligible": False, "active": True, "created_at": now_utc(),
        })


async def apply_movement(payload: MovementInput, actor_user_id: str, is_reversal: bool = False, reversed_movement_id: Optional[str] = None) -> dict:
    book = await canonical_book(payload.book_id)
    if payload.payment_status == "pagado":
        list_price_cents = book.get("member_price_cents", 0)
        if (payload.amount_paid_cents or 0) < list_price_cents:
            raise HTTPException(status_code=422, detail=f"payment_status='pagado' requiere amount_paid_cents >= {list_price_cents} (precio de lista). Use 'pago_parcial', 'exonerado' o 'beca' si corresponde.")
    from_holder = payload.from_holder.model_dump() if payload.from_holder else None
    to_holder = payload.to_holder.model_dump() if payload.to_holder else None
    reservation_types = {"RESERVATION", "RESERVATION_RELEASE"}
    if payload.movement_type in reservation_types:
        holder = to_holder if payload.movement_type == "RESERVATION" else from_holder
        delta = payload.quantity if payload.movement_type == "RESERVATION" else -payload.quantity
        await adjust_holding(book["book_id"], holder, reserved_delta=delta)
    else:
        if from_holder:
            await adjust_holding(book["book_id"], from_holder, on_hand_delta=-payload.quantity)
        if to_holder:
            await adjust_holding(book["book_id"], to_holder, on_hand_delta=payload.quantity)
    movement_id = str(uuid4())
    now = now_utc()
    doc = {
        "_id": movement_id, "movement_id": movement_id, "book_id": book["book_id"], "book_name": book["name"],
        "movement_type": payload.movement_type, "quantity": payload.quantity, "from_holder": from_holder, "to_holder": to_holder,
        "from_holder_label": await holder_label(from_holder), "to_holder_label": await holder_label(to_holder),
        "person_id": payload.person_id, "process_key": payload.process_key,
        "payment_status": payload.payment_status, "amount_charged_cents": payload.amount_charged_cents,
        "amount_paid_cents": payload.amount_paid_cents, "payment_method": payload.payment_method,
        "due_date": payload.due_date, "notes": payload.notes, "actor_user_id": actor_user_id,
        "scan_method": payload.scan_method or "MANUAL", "list_price_cents": book.get("member_price_cents", 0),
        "occurred_at": now, "created_at": now, "is_reversal": is_reversal, "reversed_movement_id": reversed_movement_id,
        "reversed_by_movement_id": None, "finance_contribution_id": None,
    }
    await db.library_movements.insert_one(doc)
    if payload.movement_type == "LOAN":
        await db.library_loans.insert_one({"_id": movement_id, "loan_id": movement_id, "movement_id": movement_id, "book_id": book["book_id"], "person_id": payload.person_id, "loaned_at": now, "due_date": payload.due_date, "status": "on_loan", "returned_movement_id": None})
    if payload.movement_type == "LOAN_RETURN" and payload.person_id:
        await db.library_loans.update_many({"book_id": book["book_id"], "person_id": payload.person_id, "status": "on_loan"}, {"$set": {"status": "returned", "returned_movement_id": movement_id}})
    return doc


@router.get("/dashboard", response_model=dict)
async def library_dashboard(current_user: dict = Depends(participant)):
    books = await db.library_books.find({"is_active": True}, {"_id": 0}).to_list(2000)
    holdings = await db.library_holdings.find({}, {"_id": 0}).to_list(5000)
    by_book: dict[str, list] = {}
    for holding in holdings:
        by_book.setdefault(holding["book_id"], []).append(holding)
    total_registered = 0
    total_available = 0
    total_with_leaders = 0
    total_delivered = 0
    critical, low = [], []
    for book in books:
        rows = by_book.get(book["book_id"], [])
        central = next((r for r in rows if r["holder_type"] == "warehouse" and r["holder_id"] == "central"), {"quantity_on_hand": 0, "reserved_qty": 0})
        with_leaders = sum(r["quantity_on_hand"] for r in rows if r["holder_type"] == "user")
        delivered = sum(r["quantity_on_hand"] for r in rows if r["holder_type"] == "person")
        total_registered += central.get("quantity_on_hand", 0) + with_leaders + delivered
        total_available += central.get("quantity_on_hand", 0)
        total_with_leaders += with_leaders
        total_delivered += delivered
        on_hand = central.get("quantity_on_hand", 0)
        if on_hand <= 0:
            critical.append(book["name"])
        elif on_hand <= book.get("min_stock", 0):
            low.append(book["name"])
    pending_requests = await db.library_requests.count_documents({"status": "pending"}) if is_library_manager(current_user) else 0
    overdue_pos = 0
    if is_library_manager(current_user):
        pos = await db.library_purchase_orders.find({"status": {"$in": ["ordered", "partially_received"]}}, {"_id": 0, "expected_date": 1, "lines": 1}).to_list(500)
        today = date.today()
        for po in pos:
            pending = sum(line["quantity_ordered"] - line["quantity_received"] for line in po["lines"])
            expected = po.get("expected_date")
            if expected and pending > 0:
                expected_date = expected.date() if isinstance(expected, datetime) else expected
                if expected_date < today:
                    overdue_pos += 1
    return {
        "totals": {"registered": total_registered, "available": total_available, "with_leaders": total_with_leaders, "delivered": total_delivered},
        "alerts": {"critical": critical, "low": low, "pending_requests": pending_requests, "overdue_purchase_orders": overdue_pos},
    }


@router.get("/inventory", response_model=dict)
async def library_inventory(current_user: dict = Depends(manager)):
    books = await db.library_books.find({"is_active": True}, {"_id": 0}).sort("name", 1).to_list(2000)
    holdings = await db.library_holdings.find({}, {"_id": 0}).to_list(5000)
    by_book: dict[str, list] = {}
    for holding in holdings:
        by_book.setdefault(holding["book_id"], []).append(holding)
    items = []
    for book in books:
        rows = by_book.get(book["book_id"], [])
        central = next((r for r in rows if r["holder_type"] == "warehouse" and r["holder_id"] == "central"), {"quantity_on_hand": 0, "reserved_qty": 0})
        with_leaders = sum(r["quantity_on_hand"] for r in rows if r["holder_type"] == "user")
        delivered = sum(r["quantity_on_hand"] for r in rows if r["holder_type"] == "person")
        on_hand = central.get("quantity_on_hand", 0)
        reserved = central.get("reserved_qty", 0)
        status = "critico" if on_hand <= 0 else ("bajo" if on_hand <= book.get("min_stock", 0) else "suficiente")
        items.append({**book, "available_central": on_hand, "reserved_central": reserved, "effective_stock": on_hand - reserved,
                      "with_leaders": with_leaders, "delivered": delivered, "status": status})
    return {"items": serialize(items)}


@router.get("/my-holdings", response_model=dict)
async def my_holdings(current_user: dict = Depends(participant)):
    holdings = await db.library_holdings.find({"holder_type": "user", "holder_id": current_user["user_id"]}, {"_id": 0}).to_list(2000)
    books = {book["book_id"]: book for book in await db.library_books.find({}, {"_id": 0}).to_list(2000)}
    items = []
    for holding in holdings:
        book = books.get(holding["book_id"])
        if not book or holding["quantity_on_hand"] <= 0:
            continue
        received = await db.library_movements.count_documents({"to_holder.type": "user", "to_holder.id": current_user["user_id"], "book_id": holding["book_id"]})
        delivered_out = await db.library_movements.count_documents({"from_holder.type": "user", "from_holder.id": current_user["user_id"], "book_id": holding["book_id"]})
        items.append({"book": book, "on_hand": holding["quantity_on_hand"], "received_movements": received, "delivered_movements": delivered_out})
    return {"items": serialize(items)}


@router.get("/books", response_model=dict)
async def list_books(current_user: dict = Depends(participant), item_type: Optional[str] = None, process_key: Optional[str] = None, active: Optional[bool] = None, search: Optional[str] = None):
    query: dict = {}
    if item_type:
        query["item_type"] = item_type
    if process_key:
        query["process_key"] = process_key
    if active is not None:
        query["is_active"] = active
    if search:
        query["name"] = {"$regex": re.escape(search), "$options": "i"}
    books = await db.library_books.find(query, {"_id": 0}).sort("name", 1).to_list(2000)
    return {"items": serialize(books)}


@router.post("/books", response_model=dict, status_code=201)
async def create_book(payload: LibraryBookInput, current_user: dict = Depends(manager)):
    book_id = str(uuid4())
    now = now_utc()
    doc = {"_id": book_id, "book_id": book_id, **payload.model_dump(), "is_example_seed": False,
           "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.library_books.insert_one(doc)
    return serialize(doc)


@router.put("/books/{book_id}", response_model=dict)
async def update_book(book_id: str, payload: LibraryBookInput, current_user: dict = Depends(manager)):
    await canonical_book(book_id)
    await db.library_books.update_one({"book_id": book_id}, {"$set": {**payload.model_dump(), "updated_by_user_id": current_user["user_id"], "updated_at": now_utc()}})
    return serialize(await canonical_book(book_id))


@router.patch("/books/{book_id}/toggle-active", response_model=dict)
async def toggle_book_active(book_id: str, current_user: dict = Depends(manager)):
    book = await canonical_book(book_id)
    await db.library_books.update_one({"book_id": book_id}, {"$set": {"is_active": not book["is_active"], "updated_at": now_utc()}})
    return serialize(await canonical_book(book_id))


@router.post("/movements", response_model=dict, status_code=201)
async def create_movement(payload: MovementInput, current_user: dict = Depends(participant)):
    if not is_library_manager(current_user):
        allowed_types = {"DELIVERY", "LOAN", "RETURN", "LOAN_RETURN", "RESERVATION", "RESERVATION_RELEASE"}
        if payload.movement_type not in allowed_types:
            raise HTTPException(status_code=403, detail="Solo Encargado de Librería puede registrar este tipo de movimiento")
        holder = payload.to_holder if payload.movement_type == "RESERVATION" else payload.from_holder
        if not (holder and holder.type == "user" and holder.id == current_user["user_id"]):
            raise HTTPException(status_code=403, detail="Solo puede mover o reservar unidades de su propio inventario, no del almacén central")
    movement = await apply_movement(payload, current_user["user_id"])
    if payload.person_id and payload.amount_paid_cents:
        person = await canonical_person(payload.person_id)
        book = await canonical_book(payload.book_id)
        await record_library_income(person, book, payload.amount_paid_cents, payload.payment_method, current_user["user_id"], movement["movement_id"])
        movement = await db.library_movements.find_one({"movement_id": movement["movement_id"]}, {"_id": 0})
    return serialize(movement)


@router.get("/movements", response_model=dict)
async def list_movements(current_user: dict = Depends(participant), book_id: Optional[str] = None, person_id: Optional[str] = None, limit: int = Query(default=100, le=500)):
    query: dict = {}
    if book_id:
        query["book_id"] = book_id
    if person_id:
        query["person_id"] = person_id
    if not is_library_manager(current_user):
        query["$or"] = [{"from_holder.type": "user", "from_holder.id": current_user["user_id"]}, {"to_holder.type": "user", "to_holder.id": current_user["user_id"]}]
    movements = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).limit(limit).to_list(limit)
    return {"items": serialize(movements)}


@router.post("/movements/{movement_id}/reverse", response_model=dict)
async def reverse_movement(movement_id: str, reason: str = Query(min_length=3, max_length=1000), current_user: dict = Depends(manager)):
    original = await db.library_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    if not original:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if original.get("reversed_by_movement_id"):
        raise HTTPException(status_code=409, detail="Este movimiento ya fue revertido")
    reversal_payload = MovementInput(
        book_id=original["book_id"], movement_type=original["movement_type"], quantity=original["quantity"],
        from_holder=original.get("to_holder"), to_holder=original.get("from_holder"),
        person_id=original.get("person_id"), process_key=original.get("process_key"), notes=f"Reversión: {reason}",
        due_date=original.get("due_date"),
    ) if original["movement_type"] not in {"RESERVATION", "RESERVATION_RELEASE"} else MovementInput(
        book_id=original["book_id"], movement_type="RESERVATION_RELEASE" if original["movement_type"] == "RESERVATION" else "RESERVATION",
        quantity=original["quantity"], from_holder=original.get("to_holder"), to_holder=original.get("from_holder"), notes=f"Reversión: {reason}",
    )
    reversal = await apply_movement(reversal_payload, current_user["user_id"], is_reversal=True, reversed_movement_id=movement_id)
    await db.library_movements.update_one({"movement_id": movement_id}, {"$set": {"reversed_by_movement_id": reversal["movement_id"], "reversal_reason": reason}})
    return serialize(reversal)


@router.get("/persons/{person_id}/materials", response_model=dict)
async def person_materials(person_id: str, current_user: dict = Depends(participant)):
    person = await canonical_person(person_id)
    query: dict = {"person_id": person["person_id"]}
    if not (is_library_manager(current_user) or has_capability(current_user, LIBRARY_REPORTS_READ)):
        query["actor_user_id"] = current_user["user_id"]
    movements = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).to_list(500)
    return {"person_id": person["person_id"], "items": serialize(movements)}


async def release_reservations_for_delivery(book_id: str, person_id: str, actor_user_id: str) -> None:
    """Al entregar un material, libera cualquier reserva automática activa de esa
    persona para ese material (la necesidad ya fue cubierta) — evita que quede
    stock reservado indefinidamente tras la entrega."""
    reservations = await db.library_reservations.find({"book_id": book_id, "person_id": person_id, "status": "active"}, {"_id": 0}).to_list(20)
    for reservation in reservations:
        movement = await apply_movement(
            MovementInput(book_id=book_id, movement_type="RESERVATION_RELEASE", quantity=reservation["quantity"],
                          from_holder=HolderInput(**CENTRAL_HOLDER), person_id=person_id, process_key=reservation.get("process_key"),
                          notes="Liberación automática · material entregado"),
            actor_user_id,
        )
        await db.library_reservations.update_one(
            {"reservation_id": reservation["reservation_id"]},
            {"$set": {"status": "released", "released_at": now_utc(), "release_movement_id": movement["movement_id"], "release_reason": "delivered"}},
        )


@router.post("/persons/{person_id}/deliver", response_model=dict, status_code=201)
async def deliver_book(person_id: str, payload: DeliverBookInput, current_user: dict = Depends(participant)):
    person = await canonical_person(person_id)
    from_holder = payload.from_holder.model_dump() if payload.from_holder else (CENTRAL_HOLDER if is_library_manager(current_user) else {"type": "user", "id": current_user["user_id"]})
    if not is_library_manager(current_user) and not (from_holder.get("type") == "user" and from_holder.get("id") == current_user["user_id"]):
        raise HTTPException(status_code=403, detail="Solo puede entregar unidades de su propio inventario")
    movement_type = "LOAN" if payload.as_loan else "DELIVERY"
    movement_payload = MovementInput(
        book_id=payload.book_id, movement_type=movement_type, quantity=payload.quantity,
        from_holder=HolderInput(**from_holder), to_holder=HolderInput(type="person", id=person["person_id"]),
        person_id=person["person_id"], process_key=payload.process_key, payment_status=payload.payment_status,
        amount_paid_cents=payload.amount_paid_cents, payment_method=payload.payment_method, notes=payload.notes,
        due_date=payload.due_date, scan_method=payload.scan_method,
    )
    movement = await apply_movement(movement_payload, current_user["user_id"])
    await release_reservations_for_delivery(payload.book_id, person["person_id"], current_user["user_id"])
    if payload.amount_paid_cents:
        book = await canonical_book(payload.book_id)
        await record_library_income(person, book, payload.amount_paid_cents, payload.payment_method, current_user["user_id"], movement["movement_id"])
        movement = await db.library_movements.find_one({"movement_id": movement["movement_id"]}, {"_id": 0})
    return serialize(movement)


@router.get("/requests", response_model=dict)
async def list_requests(current_user: dict = Depends(participant)):
    query = {} if is_library_manager(current_user) else {"requester_user_id": current_user["user_id"]}
    requests = await db.library_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"items": serialize(requests)}


@router.post("/requests", response_model=dict, status_code=201)
async def create_request(payload: RequestBookInput, current_user: dict = Depends(participant)):
    book = await canonical_book(payload.book_id)
    request_id = str(uuid4())
    now = now_utc()
    doc = {"_id": request_id, "request_id": request_id, "book_id": book["book_id"], "book_name": book["name"],
           "quantity_requested": payload.quantity, "quantity_approved": None, "status": "pending", "notes": payload.notes,
           "requester_user_id": current_user["user_id"], "requester_label": await holder_label({"type": "user", "id": current_user["user_id"]}),
           "resolved_by_user_id": None, "created_at": now, "resolved_at": None}
    await db.library_requests.insert_one(doc)
    return serialize(doc)


@router.post("/requests/{request_id}/resolve", response_model=dict)
async def resolve_request(request_id: str, payload: ResolveRequestInput, current_user: dict = Depends(manager)):
    request_doc = await db.library_requests.find_one({"request_id": request_id}, {"_id": 0})
    if not request_doc:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if request_doc["status"] != "pending":
        raise HTTPException(status_code=409, detail="La solicitud ya fue resuelta")
    if payload.quantity_approved > request_doc["quantity_requested"]:
        raise HTTPException(status_code=422, detail="No puede aprobar más de lo solicitado")
    status = "rejected" if payload.quantity_approved == 0 else ("partial" if payload.quantity_approved < request_doc["quantity_requested"] else "approved")
    if payload.quantity_approved > 0:
        movement_payload = MovementInput(book_id=request_doc["book_id"], movement_type="TRANSFER", quantity=payload.quantity_approved,
                                          from_holder=HolderInput(**CENTRAL_HOLDER), to_holder=HolderInput(type="user", id=request_doc["requester_user_id"]),
                                          notes=f"Solicitud {request_id}: {payload.notes}")
        await apply_movement(movement_payload, current_user["user_id"])
    await db.library_requests.update_one({"request_id": request_id}, {"$set": {"status": status, "quantity_approved": payload.quantity_approved, "resolved_by_user_id": current_user["user_id"], "resolved_at": now_utc()}})
    return serialize(await db.library_requests.find_one({"request_id": request_id}, {"_id": 0}))


@router.get("/librarians", response_model=dict)
async def list_librarians(current_user: dict = Depends(manager)):
    users = await db.users.find({"capabilities": LIBRARY_INVENTORY_MANAGE}, {"_id": 1, "nombre": 1, "email": 1, "rol": 1}).to_list(200)
    return {"items": [{"user_id": str(item["_id"]), "nombre": item.get("nombre"), "email": item.get("email"), "rol": item.get("rol")} for item in users]}


@router.post("/librarians", response_model=dict, status_code=201)
async def grant_librarian(payload: LibrarianGrantInput, current_user: dict = Depends(get_current_user)):
    if not (is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)):
        raise HTTPException(status_code=403, detail="Solo Pastor/a o Coordinación General puede asignar Encargados de Librería")
    target = await db.users.find_one(user_id_query(payload.user_id))
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    await db.users.update_one(user_id_query(payload.user_id), {"$addToSet": {"capabilities": {"$each": [LIBRARY_CATALOG_MANAGE, LIBRARY_INVENTORY_MANAGE]}}, "$set": {"library_role": "encargado"}})
    return {"granted": True, "user_id": payload.user_id}


@router.delete("/librarians/{user_id}", response_model=dict)
async def revoke_librarian(user_id: str, current_user: dict = Depends(get_current_user)):
    if not (is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)):
        raise HTTPException(status_code=403, detail="Solo Pastor/a o Coordinación General puede quitar Encargados de Librería")
    await db.users.update_one(user_id_query(user_id), {"$pull": {"capabilities": {"$in": [LIBRARY_CATALOG_MANAGE, LIBRARY_INVENTORY_MANAGE]}}, "$unset": {"library_role": ""}})
    return {"revoked": True, "user_id": user_id}
