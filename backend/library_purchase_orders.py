"""Librería 360 · Fase 2: Órdenes de Compra con aprobación de Finanzas y
recepción parcial/total. Recibir SIEMPRE genera movimientos PURCHASE_RECEIPT en
el ledger existente — nunca edita el inventario directamente."""
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from access_control import has_capability, is_general_coordinator, is_global_pastoral_authority
from finance_engine import require_finance_manage
from library_module import (
    CENTRAL_HOLDER, HolderInput, MovementInput, apply_movement, canonical_book,
    is_library_manager, now_utc, require_library_manager, serialize,
)
from server import db, get_current_user

router = APIRouter(prefix="/api/library/purchase-orders", tags=["library-purchase-orders"])

PO_STATUS = Literal["draft", "submitted", "approved", "rejected", "changes_requested", "ordered", "partially_received", "received", "closed", "cancelled"]
EXPENSE_ACCOUNT_CODE = "5060"


async def ensure_indexes() -> None:
    await db.library_purchase_orders.create_index("po_id", unique=True)
    await db.library_purchase_orders.create_index("po_number", unique=True)
    await db.library_purchase_orders.create_index("status")


def can_decide_po(current_user: dict) -> bool:
    return is_global_pastoral_authority(current_user) or is_general_coordinator(current_user) or has_capability(current_user, "finance.manage")


def can_view_po(current_user: dict) -> bool:
    return is_library_manager(current_user) or can_decide_po(current_user) or has_capability(current_user, "finance.read")


def manager(current_user: dict = Depends(get_current_user)) -> dict:
    require_library_manager(current_user)
    return current_user


def viewer(current_user: dict = Depends(get_current_user)) -> dict:
    if not can_view_po(current_user):
        raise HTTPException(status_code=403, detail="No tiene acceso a Órdenes de Compra")
    return current_user


class POLineInput(BaseModel):
    book_id: str
    quantity: int = Field(gt=0)
    unit_cost_cents: int = Field(ge=0)


class POCreateInput(BaseModel):
    provider_name: str = Field(min_length=2, max_length=160)
    provider_contact: Optional[str] = Field(default=None, max_length=160)
    lines: list[POLineInput] = Field(min_length=1, max_length=50)
    tax_cents: int = Field(default=0, ge=0)
    shipping_cents: int = Field(default=0, ge=0)
    expected_date: Optional[date] = None
    notes: str = Field(default="", max_length=1000)


class PODecisionInput(BaseModel):
    action: Literal["approve", "reject", "request_changes"]
    note: str = Field(default="", max_length=1000)


class POReceiveLineInput(BaseModel):
    book_id: str
    quantity_received_now: int = Field(ge=0)


class POReceiveInput(BaseModel):
    lines: list[POReceiveLineInput]
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def non_empty(self):
        if not any(line.quantity_received_now > 0 for line in self.lines):
            raise ValueError("Debe recibir al menos una unidad")
        return self


class POCommentInput(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


async def next_po_number() -> str:
    prefix = f"PO-{now_utc().year}-"
    latest = await db.library_purchase_orders.find({"po_number": {"$regex": f"^{prefix}"}}, {"po_number": 1}).sort("po_number", -1).limit(1).to_list(1)
    next_seq = 1
    if latest:
        try:
            next_seq = int(latest[0]["po_number"].split("-")[-1]) + 1
        except (ValueError, IndexError):
            next_seq = 1
    return f"{prefix}{next_seq:04d}"


async def canonical_po(po_id: str) -> dict:
    po = await db.library_purchase_orders.find_one({"po_id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="Orden de compra no encontrada")
    return po


async def push_status(po_id: str, status: str, actor_user_id: str, note: str = "", extra: Optional[dict] = None) -> None:
    now = now_utc()
    changes = {"status": status, "updated_at": now, **(extra or {})}
    await db.library_purchase_orders.update_one(
        {"po_id": po_id},
        {"$set": changes, "$push": {"status_history": {"status": status, "actor_user_id": actor_user_id, "at": now, "note": note}}},
    )


async def ensure_library_expense_account() -> dict:
    account = await db.finance_accounts.find_one({"code": EXPENSE_ACCOUNT_CODE})
    if account:
        return account
    account_id = str(uuid4())
    account = {"_id": account_id, "account_id": account_id, "code": EXPENSE_ACCOUNT_CODE, "name": "Compras de Materiales de Librería", "account_type": "expense", "active": True, "created_at": now_utc()}
    await db.finance_accounts.insert_one(account)
    return account


async def find_or_create_vendor(provider_name: str, actor_user_id: str) -> dict:
    vendor = await db.finance_vendors.find_one({"name": {"$regex": f"^{provider_name.strip()}$", "$options": "i"}, "active": True})
    if vendor:
        return vendor
    vendor_id = str(uuid4())
    vendor = {"_id": vendor_id, "vendor_id": vendor_id, "name": provider_name.strip(), "email": None, "phone": None, "tax_id_last4": None, "active": True, "created_by_user_id": actor_user_id, "created_at": now_utc()}
    await db.finance_vendors.insert_one(vendor)
    return vendor


async def create_linked_expense(po: dict, actor_user_id: str) -> Optional[str]:
    try:
        from finance_routes import ExpenseCreate, JournalLine, expense_create
        fund = await db.finance_funds.find_one({"code": "GENERAL", "active": True}, {"_id": 0, "fund_id": 1})
        if not fund:
            return None
        account = await ensure_library_expense_account()
        vendor = await find_or_create_vendor(po["provider_name"], actor_user_id)
        payload = ExpenseCreate(
            vendor_id=vendor["vendor_id"], expense_date=date.today(), description=f"Orden de compra {po['po_number']} · Librería 360",
            total_cents=po["total_cents"],
            allocations=[JournalLine(account_id=account["account_id"], fund_id=fund["fund_id"], debit_cents=po["total_cents"], credit_cents=0, description=f"Compra de materiales · {po['po_number']}")],
            category="Compras de Librería", beneficiary_type="vendor",
        )
        expense = await expense_create(payload, {"user_id": actor_user_id})
        await db.library_purchase_orders.update_one({"po_id": po["po_id"]}, {"$set": {"linked_expense_id": expense["expense_id"]}})
        return expense["expense_id"]
    except Exception as exc:
        await db.library_purchase_orders.update_one({"po_id": po["po_id"]}, {"$set": {"finance_sync_error": str(exc)}})
        return None


def to_datetime(value: Optional[date]) -> Optional[datetime]:
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc) if value else None


def compute_totals(lines: list[POLineInput], tax_cents: int, shipping_cents: int) -> dict:
    subtotal = sum(line.quantity * line.unit_cost_cents for line in lines)
    return {"subtotal_cents": subtotal, "tax_cents": tax_cents, "shipping_cents": shipping_cents, "total_cents": subtotal + tax_cents + shipping_cents}


async def build_lines(lines: list[POLineInput]) -> list[dict]:
    result = []
    for line in lines:
        book = await canonical_book(line.book_id)
        result.append({"book_id": book["book_id"], "book_name": book["name"], "quantity_ordered": line.quantity, "quantity_received": 0, "unit_cost_cents": line.unit_cost_cents, "line_total_cents": line.quantity * line.unit_cost_cents})
    return result


@router.get("", response_model=dict)
async def list_purchase_orders(current_user: dict = Depends(viewer), status: Optional[str] = None):
    query = {"status": status} if status else {}
    items = await db.library_purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"items": serialize(items), "can_decide": can_decide_po(current_user)}


@router.get("/{po_id}", response_model=dict)
async def get_purchase_order(po_id: str, current_user: dict = Depends(viewer)):
    po = await canonical_po(po_id)
    return {**serialize(po), "can_decide": can_decide_po(current_user)}


@router.post("", response_model=dict, status_code=201)
async def create_purchase_order(payload: POCreateInput, current_user: dict = Depends(manager)):
    po_id = str(uuid4())
    now = now_utc()
    lines = await build_lines(payload.lines)
    totals = compute_totals(payload.lines, payload.tax_cents, payload.shipping_cents)
    doc = {
        "_id": po_id, "po_id": po_id, "po_number": await next_po_number(), "status": "draft",
        "provider_name": payload.provider_name, "provider_contact": payload.provider_contact, "lines": lines,
        **totals, "expected_date": to_datetime(payload.expected_date), "notes": payload.notes,
        "requested_by_user_id": current_user["user_id"], "requested_at": None,
        "approved_by_user_id": None, "approved_at": None, "rejected_by_user_id": None, "rejected_at": None,
        "rejection_reason": None, "ordered_by_user_id": None, "ordered_at": None,
        "closed_by_user_id": None, "closed_at": None, "linked_expense_id": None, "finance_sync_error": None,
        "comments": [], "status_history": [{"status": "draft", "actor_user_id": current_user["user_id"], "at": now, "note": "Orden creada"}],
        "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.library_purchase_orders.insert_one(doc)
    return serialize(doc)


@router.put("/{po_id}", response_model=dict)
async def update_purchase_order(po_id: str, payload: POCreateInput, current_user: dict = Depends(manager)):
    po = await canonical_po(po_id)
    if po["status"] != "draft":
        raise HTTPException(status_code=409, detail="Solo se puede editar una orden en borrador")
    lines = await build_lines(payload.lines)
    totals = compute_totals(payload.lines, payload.tax_cents, payload.shipping_cents)
    await db.library_purchase_orders.update_one({"po_id": po_id}, {"$set": {
        "provider_name": payload.provider_name, "provider_contact": payload.provider_contact, "lines": lines,
        **totals, "expected_date": to_datetime(payload.expected_date), "notes": payload.notes, "updated_at": now_utc(),
    }})
    return serialize(await canonical_po(po_id))


@router.post("/{po_id}/submit", response_model=dict)
async def submit_purchase_order(po_id: str, current_user: dict = Depends(manager)):
    po = await canonical_po(po_id)
    if po["status"] not in {"draft", "changes_requested"}:
        raise HTTPException(status_code=409, detail="La orden ya fue enviada a Finanzas")
    await push_status(po_id, "submitted", current_user["user_id"], "Enviada a Finanzas", {"requested_at": now_utc()})
    return serialize(await canonical_po(po_id))


@router.post("/{po_id}/decision", response_model=dict)
async def decide_purchase_order(po_id: str, payload: PODecisionInput, current_user: dict = Depends(get_current_user)):
    require_finance_manage(current_user)
    po = await canonical_po(po_id)
    if po["status"] != "submitted":
        raise HTTPException(status_code=409, detail="La orden no está pendiente de decisión de Finanzas")
    if payload.action == "approve":
        await push_status(po_id, "approved", current_user["user_id"], payload.note, {"approved_by_user_id": current_user["user_id"], "approved_at": now_utc()})
        po = await canonical_po(po_id)
        await create_linked_expense(po, current_user["user_id"])
    elif payload.action == "reject":
        await push_status(po_id, "rejected", current_user["user_id"], payload.note, {"rejected_by_user_id": current_user["user_id"], "rejected_at": now_utc(), "rejection_reason": payload.note})
    else:
        await push_status(po_id, "changes_requested", current_user["user_id"], payload.note)
    return serialize(await canonical_po(po_id))


@router.post("/{po_id}/mark-ordered", response_model=dict)
async def mark_ordered(po_id: str, current_user: dict = Depends(manager)):
    po = await canonical_po(po_id)
    if po["status"] != "approved":
        raise HTTPException(status_code=409, detail="La orden debe estar aprobada por Finanzas")
    await push_status(po_id, "ordered", current_user["user_id"], "Pedido colocado al proveedor", {"ordered_by_user_id": current_user["user_id"], "ordered_at": now_utc()})
    return serialize(await canonical_po(po_id))


@router.post("/{po_id}/receive", response_model=dict)
async def receive_purchase_order(po_id: str, payload: POReceiveInput, current_user: dict = Depends(manager)):
    po = await canonical_po(po_id)
    if po["status"] not in {"ordered", "partially_received"}:
        raise HTTPException(status_code=409, detail="La orden debe estar ordenada para recibir mercancía")
    lines_by_book = {line["book_id"]: dict(line) for line in po["lines"]}
    for entry in payload.lines:
        line = lines_by_book.get(entry.book_id)
        if not line:
            raise HTTPException(status_code=422, detail="El material no pertenece a esta orden")
        remaining = line["quantity_ordered"] - line["quantity_received"]
        if entry.quantity_received_now > remaining:
            raise HTTPException(status_code=422, detail=f"No puede recibir más de lo pendiente para {line['book_name']} (pendiente: {remaining})")
        if entry.quantity_received_now > 0:
            movement_payload = MovementInput(book_id=entry.book_id, movement_type="PURCHASE_RECEIPT", quantity=entry.quantity_received_now, to_holder=HolderInput(**CENTRAL_HOLDER), notes=f"Recepción {po['po_number']}: {payload.notes}")
            await apply_movement(movement_payload, current_user["user_id"])
            line["quantity_received"] += entry.quantity_received_now
            lines_by_book[entry.book_id] = line
    updated_lines = list(lines_by_book.values())
    fully_received = all(line["quantity_received"] >= line["quantity_ordered"] for line in updated_lines)
    new_status = "received" if fully_received else "partially_received"
    await db.library_purchase_orders.update_one({"po_id": po_id}, {"$set": {"lines": updated_lines, "updated_at": now_utc()}})
    await push_status(po_id, new_status, current_user["user_id"], payload.notes or "Recepción de mercancía registrada")
    return serialize(await canonical_po(po_id))


@router.post("/{po_id}/close", response_model=dict)
async def close_purchase_order(po_id: str, current_user: dict = Depends(manager)):
    po = await canonical_po(po_id)
    if po["status"] not in {"received", "partially_received"}:
        raise HTTPException(status_code=409, detail="Solo se puede cerrar una orden ya recibida (total o parcialmente)")
    await push_status(po_id, "closed", current_user["user_id"], "Orden cerrada administrativamente", {"closed_by_user_id": current_user["user_id"], "closed_at": now_utc()})
    return serialize(await canonical_po(po_id))


@router.post("/{po_id}/cancel", response_model=dict)
async def cancel_purchase_order(po_id: str, current_user: dict = Depends(manager)):
    po = await canonical_po(po_id)
    if po["status"] not in {"draft", "submitted", "approved", "changes_requested"}:
        raise HTTPException(status_code=409, detail="La orden ya no puede cancelarse en su estado actual")
    await push_status(po_id, "cancelled", current_user["user_id"], "Orden cancelada")
    return serialize(await canonical_po(po_id))


@router.post("/{po_id}/comments", response_model=dict, status_code=201)
async def add_comment(po_id: str, payload: POCommentInput, current_user: dict = Depends(viewer)):
    await canonical_po(po_id)
    comment = {"comment_id": str(uuid4()), "text": payload.text, "author_user_id": current_user["user_id"], "created_at": now_utc()}
    await db.library_purchase_orders.update_one({"po_id": po_id}, {"$push": {"comments": comment}, "$set": {"updated_at": now_utc()}})
    return serialize(comment)
