"""Mega‑Bloque G: APIs financieras con contabilidad por fondos y RBAC estricto."""
import csv
import io
import os
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, model_validator
from pymongo.errors import DuplicateKeyError

from finance_engine import audit, create_journal, ensure_open_period, now_utc, require_finance_manage, require_finance_read, serialize, validate_lines
from server import db, get_current_user

router = APIRouter(prefix="/api/finance", tags=["finance"])


def reader(current_user: dict = Depends(get_current_user)) -> dict: require_finance_read(current_user); return current_user
def manager(current_user: dict = Depends(get_current_user)) -> dict: require_finance_manage(current_user); return current_user


class FundCreate(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=120)
    restriction_type: Literal["unrestricted", "donor_restricted", "board_designated"]
    purpose: str = Field(min_length=2, max_length=500)


class AccountCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=120)
    account_type: Literal["asset", "liability", "net_assets", "revenue", "expense"]


class JournalLine(BaseModel):
    account_id: str
    fund_id: str
    debit_cents: int = Field(default=0, ge=0)
    credit_cents: int = Field(default=0, ge=0)
    description: str = Field(default="", max_length=250)
    campaign_id: Optional[str] = None
    ministry_id: Optional[str] = None
    cost_center: Optional[str] = None


class JournalCreate(BaseModel):
    entry_date: date
    memo: str = Field(min_length=3, max_length=500)
    lines: list[JournalLine] = Field(min_length=2, max_length=100)


class Allocation(BaseModel):
    fund_id: str
    amount_cents: int = Field(gt=0)
    contribution_type: Optional[str] = Field(default=None, min_length=2, max_length=80)
    campaign_id: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=500)
    annual_statement_eligible: Optional[bool] = None


class ContributionCreate(BaseModel):
    person_id: Optional[str] = None
    household_id: Optional[str] = None
    anonymous: bool = False
    contribution_type: Optional[str] = Field(default=None, min_length=2, max_length=80)
    amount_cents: int = Field(gt=0)
    received_date: date
    accounting_date: Optional[date] = None
    payment_method: Literal["cash", "check", "zelle", "card", "ach", "transfer", "pushpay", "other"]
    reference: Optional[str] = Field(default=None, max_length=120)
    allocations: list[Allocation] = Field(min_length=1, max_length=20)
    source: Literal["manual", "csv", "pushpay"] = "manual"
    external_transaction_id: Optional[str] = Field(default=None, max_length=200)
    campaign_id: Optional[str] = None
    envelope_number: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)
    batch_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_external_transaction(self):
        if self.external_transaction_id is not None:
            self.external_transaction_id = self.external_transaction_id.strip() or None
        if self.source in {"csv", "pushpay"} and not self.external_transaction_id:
            raise ValueError("Las contribuciones externas requieren un identificador de transacción")
        if not self.contribution_type and any(not item.contribution_type for item in self.allocations):
            raise ValueError("Cada concepto debe indicar un tipo de contribución")
        return self


class VendorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: Optional[str] = None
    phone: Optional[str] = None
    tax_id_last4: Optional[str] = Field(default=None, max_length=4)


class ExpenseCreate(BaseModel):
    vendor_id: Optional[str] = None
    requested_by_person_id: Optional[str] = None
    invoice_number: Optional[str] = None
    expense_date: date
    due_date: Optional[date] = None
    description: str = Field(min_length=3, max_length=500)
    total_cents: int = Field(gt=0)
    allocations: list[JournalLine] = Field(min_length=1, max_length=50)
    document_reference: Optional[str] = None
    receipt_confirmed: bool = False
    ministry_id: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=120)
    cost_center: Optional[str] = Field(default=None, max_length=120)
    expense_nature: Literal["fixed", "variable"] = "variable"
    beneficiary_type: Literal["vendor", "employee", "pastor", "ministry", "other"] = "vendor"
    compensation_classification: Optional[str] = Field(default=None, max_length=200)
    recurring_obligation_id: Optional[str] = None
    document_ids: list[str] = Field(default_factory=list, max_length=20)


class PaymentCreate(BaseModel):
    payment_date: date
    bank_account_id: str
    payment_method: Literal["check", "zelle", "ach", "transfer", "card", "cash", "other"]
    reference: Optional[str] = None


class PaymentSchedule(BaseModel):
    scheduled_date: date
    bank_account_id: str
    payment_method: Literal["check", "zelle", "ach", "transfer", "card", "cash", "other"]
    reference: Optional[str] = Field(default=None, max_length=160)


class DepositCreate(BaseModel):
    deposit_date: date
    bank_account_id: str
    contribution_ids: list[str] = Field(min_length=1, max_length=1000)
    reference: Optional[str] = None
    batch_id: Optional[str] = None


class BudgetCreate(BaseModel):
    fiscal_year: int = Field(ge=2000, le=2200)
    fund_id: str
    account_id: str
    amount_cents: int = Field(ge=0)
    ministry_id: Optional[str] = None
    campaign_id: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=120)


class ReconciliationCreate(BaseModel):
    bank_account_id: str
    statement_end_date: date
    statement_starting_balance_cents: int = 0
    statement_ending_balance_cents: int
    cleared_entry_ids: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class PeriodCreate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    year: Optional[int] = Field(default=None, ge=2000, le=2200)
    month: Optional[int] = Field(default=None, ge=1, le=12)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def derive_period_identity(self):
        self.year = self.year or self.start_date.year
        self.month = self.month or self.start_date.month
        self.name = self.name or f"{self.year}-{self.month:02d}"
        if self.end_date < self.start_date:
            raise ValueError("La fecha final debe ser posterior a la inicial")
        return self


class CampaignCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    fund_id: str
    goal_cents: int = Field(gt=0)
    budget_cents: int = Field(default=0, ge=0)
    project_type: Literal["campaign", "project", "special_destination"] = "campaign"
    description: Optional[str] = Field(default=None, max_length=500)
    start_date: date
    end_date: Optional[date] = None


class PromiseCreate(BaseModel):
    campaign_id: str
    person_id: str
    promised_cents: int = Field(gt=0)
    due_date: Optional[date] = None


class BatchCreate(BaseModel):
    batch_date: date
    contribution_ids: list[str] = Field(default_factory=list, max_length=2000)
    service_name: str = Field(default="Servicio", min_length=2, max_length=160)
    service_date: Optional[date] = None
    expected_envelope_count: Optional[int] = Field(default=None, ge=0, le=5000)
    location: Optional[str] = Field(default=None, max_length=160)
    notes: Optional[str] = Field(default=None, max_length=500)


class BatchCount(BaseModel):
    cash_cents: int = Field(ge=0)
    check_cents: int = Field(ge=0)
    other_cents: int = Field(ge=0)
    envelope_count: Optional[int] = Field(default=None, ge=0, le=5000)
    notes: Optional[str] = Field(default=None, max_length=500)


class BatchVarianceResolution(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


@router.get("/dashboard", response_model=dict)
async def dashboard(current_user: dict = Depends(reader)):
    pipeline = [{"$match": {"status": "posted"}}, {"$unwind": "$lines"}, {"$lookup": {"from": "finance_accounts", "localField": "lines.account_id", "foreignField": "account_id", "as": "account"}}, {"$unwind": "$account"}, {"$group": {"_id": {"fund_id": "$lines.fund_id", "account_type": "$account.account_type"}, "debits": {"$sum": "$lines.debit_cents"}, "credits": {"$sum": "$lines.credit_cents"}}}]
    rows = await db.finance_journal_entries.aggregate(pipeline).to_list(5000); balances_by_fund = {}
    for row in rows:
        account_type = row["_id"]["account_type"]
        if account_type not in {"net_assets", "revenue", "expense"}: continue
        amount = row["debits"] - row["credits"] if account_type == "expense" else row["credits"] - row["debits"]
        if account_type == "expense": amount = -amount
        balances_by_fund[row["_id"]["fund_id"]] = balances_by_fund.get(row["_id"]["fund_id"], 0) + amount
    funds = {item["fund_id"]: item for item in await db.finance_funds.find({"active": True}, {"_id": 0}).to_list(1000)}
    income_cents = sum(row["credits"] - row["debits"] for row in rows if row["_id"]["account_type"] == "revenue")
    expense_cents = sum(row["debits"] - row["credits"] for row in rows if row["_id"]["account_type"] == "expense")
    cash_cents = sum(row["debits"] - row["credits"] for row in rows if row["_id"]["account_type"] == "asset")
    unpaid_items = await db.finance_expenses.find(
        {"status": {"$nin": ["paid", "rejected", "void"]}},
        {"_id": 0, "total_cents": 1, "due_date": 1, "status": 1},
    ).to_list(5000)
    budget_total_cents = sum(item.get("amount_cents", 0) for item in await db.finance_budgets.find({}, {"_id": 0, "amount_cents": 1}).to_list(5000))
    upcoming_date = date.today().isoformat()
    upcoming_expenses = sum(1 for item in unpaid_items if item.get("due_date") and item["due_date"] >= upcoming_date)
    upcoming_recurring = await db.finance_recurring_obligations.count_documents({"active": True, "next_due_date": {"$gte": upcoming_date}})
    return {
        "fund_balances": [{"fund_id": fund_id, "fund_name": funds.get(fund_id, {}).get("name", "Fondo"), "balance_cents": amount} for fund_id, amount in balances_by_fund.items()],
        "income_cents": income_cents,
        "expense_cents": expense_cents,
        "cash_cents": cash_cents,
        "net_cents": income_cents - expense_cents,
        "outstanding_payables_cents": sum(item.get("total_cents", 0) for item in unpaid_items),
        "upcoming_payments": upcoming_expenses + upcoming_recurring,
        "budget_total_cents": budget_total_cents,
        "budget_remaining_cents": budget_total_cents - expense_cents,
        "pending_entries": await db.finance_journal_entries.count_documents({"status": {"$in": ["submitted", "reviewed"]}}),
        "unreconciled_deposits": await db.finance_deposits.count_documents({"status": {"$ne": "reconciled"}}),
        "unpaid_expenses": len(unpaid_items),
        "pushpay_status": "connected" if all(os.environ.get(key) for key in ["PUSHPAY_CLIENT_ID", "PUSHPAY_CLIENT_SECRET", "PUSHPAY_ORGANIZATION_KEY", "PUSHPAY_MERCHANT_KEY"]) else "blocked_credentials_required",
    }


@router.get("/settings", response_model=dict)
async def settings(current_user: dict = Depends(reader)):
    return serialize(await db.finance_settings.find_one({"_id": "primary"}, {"_id": 0}))


@router.put("/settings", response_model=dict)
async def update_settings(payload: dict, current_user: dict = Depends(manager)):
    if current_user.get("rol") != "pastor": raise HTTPException(status_code=403, detail="Solo el pastor puede cambiar la política contable")
    allowed = {key: payload[key] for key in ["accounting_basis", "currency", "fiscal_year_start_month"] if key in payload}
    if allowed.get("accounting_basis") not in {None, "cash", "accrual", "modified_cash"}: raise HTTPException(status_code=422, detail="Base contable no válida")
    await db.finance_settings.update_one({"_id": "primary"}, {"$set": {**allowed, "updated_at": now_utc(), "updated_by_user_id": current_user["user_id"]}})
    await audit(current_user["user_id"], "settings_updated", "finance_settings", "primary", allowed); return await settings(current_user)


@router.get("/catalog", response_model=dict)
async def catalog(current_user: dict = Depends(reader)):
    return {"funds": await db.finance_funds.find({}, {"_id": 0}).sort("code", 1).to_list(1000), "accounts": await db.finance_accounts.find({}, {"_id": 0}).sort("code", 1).to_list(1000), "contribution_types": await db.finance_contribution_types.find({}, {"_id": 0}).sort("name", 1).to_list(100)}


@router.post("/funds", response_model=dict, status_code=201)
async def create_fund(payload: FundCreate, current_user: dict = Depends(manager)):
    fund_id = str(uuid4()); doc = {"_id": fund_id, "fund_id": fund_id, **payload.model_dump(), "code": payload.code.upper(), "active": True, "created_by_user_id": current_user["user_id"], "created_at": now_utc()}
    try: await db.finance_funds.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(status_code=409, detail="El código de fondo ya existe")
    await audit(current_user["user_id"], "fund_created", "fund", fund_id, payload.model_dump()); return serialize(doc)


@router.post("/accounts", response_model=dict, status_code=201)
async def create_account(payload: AccountCreate, current_user: dict = Depends(manager)):
    account_id = str(uuid4()); doc = {"_id": account_id, "account_id": account_id, **payload.model_dump(), "active": True, "created_by_user_id": current_user["user_id"], "created_at": now_utc()}
    try: await db.finance_accounts.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(status_code=409, detail="El código de cuenta ya existe")
    await audit(current_user["user_id"], "account_created", "account", account_id, payload.model_dump()); return serialize(doc)


@router.get("/periods", response_model=dict)
async def periods(current_user: dict = Depends(reader)):
    return {"items": serialize(await db.finance_periods.find({}, {"_id": 0}).sort([("year", -1), ("month", -1)]).to_list(500))}


@router.post("/periods", response_model=dict, status_code=201)
async def period_create(payload: PeriodCreate, current_user: dict = Depends(manager)):
    period_id = f"{payload.year}-{payload.month:02d}"; doc = {"_id": period_id, "period_id": period_id, **payload.model_dump(mode="json"), "status": "open", "created_by_user_id": current_user["user_id"], "created_at": now_utc()}
    try: await db.finance_periods.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(status_code=409, detail="El período ya existe")
    await audit(current_user["user_id"], "period_created", "period", period_id); return serialize(doc)


async def build_period_checklist(period: dict) -> dict:
    date_query = {"$gte": period["start_date"], "$lte": period["end_date"]}
    checks = {
        "unposted_journals": await db.finance_journal_entries.count_documents({"entry_date": date_query, "status": {"$nin": ["posted", "rejected", "voided"]}}),
        "undeposited_contributions": await db.finance_contributions.count_documents({"received_date": date_query, "status": {"$ne": "corrected"}, "deposit_id": None}),
        "open_count_sessions": await db.finance_batches.count_documents({"batch_date": date_query, "status": {"$nin": ["deposited", "cancelled"]}}),
        "unreconciled_deposits": await db.finance_deposits.count_documents({"deposit_date": date_query, "status": {"$ne": "reconciled"}}),
        "open_payables": await db.finance_expenses.count_documents({"expense_date": date_query, "status": {"$nin": ["paid", "rejected", "void"]}}),
        "unresolved_reconciliations": await db.finance_reconciliations.count_documents({"statement_end_date": date_query, "status": {"$ne": "balanced"}}),
    }
    checks["ready_to_close"] = not any(checks.values())
    return checks


@router.get("/periods/{period_id}/checklist", response_model=dict)
async def period_checklist(period_id: str, current_user: dict = Depends(reader)):
    period = await db.finance_periods.find_one({"period_id": period_id}, {"_id": 0})
    if not period:
        raise HTTPException(status_code=404, detail="Período no encontrado")
    return {"period": serialize(period), "checks": await build_period_checklist(period)}


@router.post("/periods/{period_id}/close", response_model=dict)
async def period_close(period_id: str, current_user: dict = Depends(manager)):
    if current_user.get("rol") != "pastor": raise HTTPException(status_code=403, detail="El cierre final corresponde al pastor")
    period = await db.finance_periods.find_one({"period_id": period_id})
    if not period: raise HTTPException(status_code=404, detail="Período no encontrado")
    checklist = await build_period_checklist(period)
    if not checklist["ready_to_close"]:
        blockers = ", ".join(f"{key}: {value}" for key, value in checklist.items() if key != "ready_to_close" and value)
        raise HTTPException(status_code=409, detail=f"El período no está listo para cierre ({blockers})")
    now = now_utc(); await db.finance_periods.update_one({"period_id": period_id}, {"$set": {"status": "closed", "closed_by_user_id": current_user["user_id"], "closed_at": now}}); await audit(current_user["user_id"], "period_closed", "period", period_id); return serialize(await db.finance_periods.find_one({"period_id": period_id}, {"_id": 0}))


@router.post("/periods/{period_id}/reopen", response_model=dict)
async def period_reopen(period_id: str, payload: dict, current_user: dict = Depends(manager)):
    if current_user.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo el pastor puede reabrir un período")
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Indique el motivo de reapertura")
    period = await db.finance_periods.find_one({"period_id": period_id, "status": "closed"})
    if not period:
        raise HTTPException(status_code=404, detail="Período cerrado no encontrado")
    now = now_utc()
    await db.finance_periods.update_one({"period_id": period_id}, {"$set": {"status": "open", "reopened_by_user_id": current_user["user_id"], "reopened_at": now, "reopen_reason": reason, "updated_at": now}})
    await audit(current_user["user_id"], "period_reopened", "period", period_id, {"reason": reason})
    return serialize(await db.finance_periods.find_one({"period_id": period_id}, {"_id": 0}))


@router.get("/journals", response_model=dict)
async def journals(status: Optional[str] = None, current_user: dict = Depends(reader)):
    query = {"status": status} if status else {}; return {"items": serialize(await db.finance_journal_entries.find(query, {"_id": 0}).sort([("entry_date", -1), ("entry_number", -1)]).to_list(2000))}


@router.post("/journals", response_model=dict, status_code=201)
async def journal_create(payload: JournalCreate, current_user: dict = Depends(manager)):
    return await create_journal(current_user["user_id"], payload.entry_date.isoformat(), payload.memo, "manual", str(uuid4()), [line.model_dump() for line in payload.lines])


@router.post("/journals/{entry_id}/{action}", response_model=dict)
async def journal_workflow(entry_id: str, action: Literal["submit", "review", "approve", "reject"], current_user: dict = Depends(manager)):
    entry = await db.finance_journal_entries.find_one({"entry_id": entry_id})
    if not entry: raise HTTPException(status_code=404, detail="Asiento no encontrado")
    uid = current_user["user_id"]; now = now_utc(); changes = {"updated_at": now}
    if action == "submit":
        if entry["status"] != "draft": raise HTTPException(status_code=409, detail="Solo un borrador puede enviarse")
        changes.update(status="submitted", submitted_at=now)
    elif action == "review":
        if entry["status"] != "submitted": raise HTTPException(status_code=409, detail="El asiento no está pendiente de revisión")
        if entry["prepared_by_user_id"] == uid: raise HTTPException(status_code=403, detail="El preparador no puede revisar su propio asiento")
        changes.update(status="reviewed", reviewed_by_user_id=uid, reviewed_at=now)
    elif action == "approve":
        if current_user.get("rol") != "pastor": raise HTTPException(status_code=403, detail="La aprobación final corresponde al pastor")
        if entry["status"] != "reviewed": raise HTTPException(status_code=409, detail="El asiento requiere revisión previa")
        if uid in {entry["prepared_by_user_id"], entry.get("reviewed_by_user_id")}: raise HTTPException(status_code=403, detail="Nadie puede aprobar un asiento que preparó o revisó")
        period = await db.finance_periods.find_one({"start_date": {"$lte": entry["entry_date"]}, "end_date": {"$gte": entry["entry_date"]}, "status": "closed"})
        if period: raise HTTPException(status_code=409, detail="El período está cerrado")
        changes.update(status="posted", approved_by_user_id=uid, approved_at=now, posted_at=now)
    else: changes.update(status="rejected", rejected_by_user_id=uid, rejected_at=now)
    await db.finance_journal_entries.update_one({"entry_id": entry_id}, {"$set": changes})
    if action == "approve" and entry.get("source_type") == "expense_payment":
        await db.finance_payments.update_one({"journal_entry_id": entry_id}, {"$set": {"status": "paid", "paid_at": now, "updated_at": now}})
        await db.finance_expenses.update_one({"expense_id": entry.get("source_id")}, {"$set": {"status": "paid", "paid_at": now, "updated_at": now}})
    await audit(uid, f"journal_{action}", "journal_entry", entry_id)
    return serialize(await db.finance_journal_entries.find_one({"entry_id": entry_id}, {"_id": 0}))


@router.get("/contributions", response_model=dict)
async def contributions(current_user: dict = Depends(reader)):
    return {"items": serialize(await db.finance_contributions.find({}, {"_id": 0}).sort("received_date", -1).to_list(3000))}


@router.get("/persons/{person_id}/contributions", response_model=dict)
async def person_contributions(person_id: str, scope: Literal["person", "family"] = "person", current_user: dict = Depends(reader)):
    person_ids = [person_id]
    if scope == "family":
        memberships = await db.household_memberships.find({"person_id": person_id, "active": {"$ne": False}}, {"_id": 0, "household_id": 1}).to_list(100)
        household_ids = [item["household_id"] for item in memberships]
        if household_ids: person_ids = await db.household_memberships.distinct("person_id", {"household_id": {"$in": household_ids}, "active": {"$ne": False}})
    items = await db.finance_contributions.find({"person_id": {"$in": person_ids}}, {"_id": 0}).sort("received_date", -1).to_list(5000)
    return {"scope": scope, "person_ids": person_ids, "total_cents": sum(item.get("amount_cents", 0) for item in items), "items": serialize(items)}


async def refresh_batch_totals(batch_id: str) -> dict:
    batch = await db.finance_batches.find_one({"batch_id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Sesión de conteo no encontrada")
    contributions = await db.finance_contributions.find({"contribution_id": {"$in": batch.get("contribution_ids", [])}, "status": {"$ne": "corrected"}}, {"_id": 0}).to_list(5000)
    payment_totals = {}; concept_totals = {}; fund_totals = {}
    for contribution in contributions:
        method = contribution.get("payment_method", "other")
        payment_totals[method] = payment_totals.get(method, 0) + contribution.get("amount_cents", 0)
        for allocation in contribution.get("allocations", []):
            concept = allocation.get("contribution_type") or contribution.get("contribution_type") or "other"
            concept_totals[concept] = concept_totals.get(concept, 0) + allocation.get("amount_cents", 0)
            fund_id = allocation.get("fund_id")
            fund_totals[fund_id] = fund_totals.get(fund_id, 0) + allocation.get("amount_cents", 0)
    updates = {"registered_envelope_count": len(contributions), "expected_total_cents": sum(item.get("amount_cents", 0) for item in contributions), "expected_payment_totals": payment_totals, "expected_concept_totals": concept_totals, "expected_fund_totals": fund_totals, "updated_at": now_utc()}
    if not batch.get("expected_envelope_count_locked"):
        updates["expected_envelope_count"] = len(contributions)
    await db.finance_batches.update_one({"batch_id": batch_id}, {"$set": updates})
    return {**batch, **updates}


@router.post("/contributions", response_model=dict, status_code=201)
async def contribution_create(payload: ContributionCreate, current_user: dict = Depends(manager)):
    if not payload.anonymous and not payload.person_id:
        raise HTTPException(status_code=422, detail="Seleccione una Persona 360 o marque contribución anónima")
    person_doc = None
    if payload.person_id:
        person_doc = await db.persons.find_one({"$or": [{"_id": payload.person_id}, {"person_id": payload.person_id}]}, {"_id": 0})
    if payload.person_id and not person_doc:
        from bson import ObjectId
        if ObjectId.is_valid(payload.person_id):
            person_doc = await db.persons.find_one({"_id": ObjectId(payload.person_id)}, {"_id": 0})
        if not person_doc:
            raise HTTPException(status_code=404, detail="Persona 360 no encontrada")
    if sum(item.amount_cents for item in payload.allocations) != payload.amount_cents:
        raise HTTPException(status_code=422, detail="Las asignaciones deben sumar el total de la contribución")
    if payload.external_transaction_id and await db.finance_contributions.find_one({"source": payload.source, "external_transaction_id": payload.external_transaction_id}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="La transacción externa ya fue importada")
    if payload.batch_id and not await db.finance_batches.find_one({"batch_id": payload.batch_id, "status": "collecting"}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="La sesión de conteo no está abierta para recibir sobres")
    type_keys = {item.contribution_type or payload.contribution_type for item in payload.allocations}
    type_docs = {
        item["type_key"]: item
        for item in await db.finance_contribution_types.find(
            {"type_key": {"$in": list(type_keys)}, "active": True}, {"_id": 0}
        ).to_list(100)
    }
    missing_types = sorted(type_keys - set(type_docs))
    if missing_types:
        raise HTTPException(status_code=422, detail=f"Concepto de contribución no válido: {', '.join(missing_types)}")
    campaign_ids = {item.campaign_id or payload.campaign_id for item in payload.allocations if item.campaign_id or payload.campaign_id}
    if campaign_ids:
        valid_campaigns = set(await db.finance_campaigns.distinct("campaign_id", {"campaign_id": {"$in": list(campaign_ids)}, "status": "active"}))
        if valid_campaigns != campaign_ids:
            raise HTTPException(status_code=422, detail="Proyecto o campaña no válido")
    undeposited = await db.finance_accounts.find_one({"code": "1010"}, {"_id": 0})
    if not undeposited:
        raise HTTPException(status_code=409, detail="Configure la cuenta de fondos no depositados")
    contribution_id = str(uuid4())
    normalized_allocations = []
    lines = []
    for allocation in payload.allocations:
        type_key = allocation.contribution_type or payload.contribution_type
        type_doc = type_docs[type_key]
        campaign_id = allocation.campaign_id or payload.campaign_id
        allocation_doc = {
            "fund_id": allocation.fund_id,
            "amount_cents": allocation.amount_cents,
            "contribution_type": type_key,
            "campaign_id": campaign_id,
            "description": allocation.description or payload.description,
            "annual_statement_eligible": allocation.annual_statement_eligible,
        }
        normalized_allocations.append({key: value for key, value in allocation_doc.items() if value is not None})
        description = allocation.description or type_doc["name"]
        lines.extend([
            {"account_id": undeposited["account_id"], "fund_id": allocation.fund_id, "debit_cents": allocation.amount_cents, "credit_cents": 0, "description": f"Contribución recibida · {description}"},
            {"account_id": type_doc["revenue_account_id"], "fund_id": allocation.fund_id, "debit_cents": 0, "credit_cents": allocation.amount_cents, "description": description},
        ])
    normalized_type = next(iter(type_keys)) if len(type_keys) == 1 else "mixed"
    journal_date = (payload.accounting_date or payload.received_date).isoformat()
    journal = await create_journal(current_user["user_id"], journal_date, f"Contribución recibida · {len(normalized_allocations)} concepto(s)", "contribution", contribution_id, lines, "submitted")
    contribution_data = payload.model_dump(mode="json", exclude_none=True)
    if person_doc:
        contribution_data["person_id"] = person_doc.get("person_id") or payload.person_id
        contribution_data["household_id"] = payload.household_id or person_doc.get("household_id")
    contribution_data["contribution_type"] = normalized_type
    contribution_data["allocations"] = normalized_allocations
    now = now_utc()
    doc = {"_id": contribution_id, "contribution_id": contribution_id, **contribution_data, "journal_entry_id": journal["entry_id"], "deposit_id": None, "batch_id": payload.batch_id, "status": "recorded", "created_by_user_id": current_user["user_id"], "updated_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    try: await db.finance_contributions.insert_one(doc)
    except DuplicateKeyError:
        await db.finance_journal_entries.delete_one({"entry_id": journal["entry_id"]})
        await db.finance_audit_events.delete_many({"entity_type": "journal_entry", "entity_id": journal["entry_id"]})
        raise HTTPException(status_code=409, detail="La transacción externa ya fue importada")
    if payload.batch_id:
        await db.finance_batches.update_one({"batch_id": payload.batch_id}, {"$addToSet": {"contribution_ids": contribution_id}})
        await refresh_batch_totals(payload.batch_id)
    if payload.person_id:
        campaign_totals = {}
        for allocation in normalized_allocations:
            if allocation.get("campaign_id"):
                campaign_totals[allocation["campaign_id"]] = campaign_totals.get(allocation["campaign_id"], 0) + allocation["amount_cents"]
        for campaign_id, campaign_amount in campaign_totals.items():
            promise = await db.finance_promises.find_one({"campaign_id": campaign_id, "person_id": payload.person_id, "status": "active"})
            if promise:
                fulfilled = promise.get("fulfilled_cents", 0) + campaign_amount
                await db.finance_promises.update_one({"promise_id": promise["promise_id"]}, {"$set": {"fulfilled_cents": fulfilled, "status": "completed" if fulfilled >= promise["promised_cents"] else "active", "updated_at": now_utc()}})
    await audit(current_user["user_id"], "contribution_created", "contribution", contribution_id, {"amount_cents": payload.amount_cents, "type": normalized_type, "concepts": len(normalized_allocations)})
    return serialize(doc)


@router.post("/contributions/import-csv", response_model=dict)
async def import_contributions_csv(file: UploadFile = File(...), current_user: dict = Depends(manager)):
    content = await file.read()
    try: rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    except Exception: raise HTTPException(status_code=400, detail="CSV no válido")
    imported = 0; rejected = []
    for index, row in enumerate(rows, start=2):
        try:
            fund = await db.finance_funds.find_one({"code": row["fund_code"].strip().upper(), "active": True})
            if not fund: raise ValueError("Fondo no encontrado")
            payload = ContributionCreate(person_id=row.get("person_id") or None, anonymous=(row.get("anonymous", "").lower() in {"true", "1", "sí", "si"}), contribution_type=row["contribution_type"].strip().lower(), amount_cents=int(row["amount_cents"]), received_date=date.fromisoformat(row["received_date"]), payment_method=row.get("payment_method", "other").strip().lower(), reference=row.get("reference"), allocations=[Allocation(fund_id=fund["fund_id"], amount_cents=int(row["amount_cents"]))], source="csv", external_transaction_id=row["external_transaction_id"].strip())
            await contribution_create(payload, current_user); imported += 1
        except Exception as error: rejected.append({"row": index, "reason": str(getattr(error, "detail", error))[:240]})
    return {"imported": imported, "rejected": rejected, "total": len(rows)}


@router.get("/campaigns", response_model=dict)
async def campaigns(current_user: dict = Depends(reader)):
    items = await db.finance_campaigns.find({}, {"_id": 0}).sort("start_date", -1).to_list(1000)
    for item in items:
        item["promised_cents"] = sum(p.get("promised_cents", 0) for p in await db.finance_promises.find({"campaign_id": item["campaign_id"]}, {"_id": 0, "promised_cents": 1}).to_list(10000))
    return {"items": serialize(items)}


@router.post("/campaigns", response_model=dict, status_code=201)
async def campaign_create(payload: CampaignCreate, current_user: dict = Depends(manager)):
    cid = str(uuid4()); doc = {"_id": cid, "campaign_id": cid, **payload.model_dump(mode="json"), "status": "active", "created_by_user_id": current_user["user_id"], "created_at": now_utc()}; await db.finance_campaigns.insert_one(doc); await audit(current_user["user_id"], "campaign_created", "campaign", cid); return serialize(doc)


@router.get("/promises", response_model=dict)
async def promises(campaign_id: Optional[str] = None, current_user: dict = Depends(reader)):
    return {"items": serialize(await db.finance_promises.find({"campaign_id": campaign_id} if campaign_id else {}, {"_id": 0}).sort("created_at", -1).to_list(5000))}


@router.post("/promises", response_model=dict, status_code=201)
async def promise_create(payload: PromiseCreate, current_user: dict = Depends(manager)):
    from bson import ObjectId
    if not ObjectId.is_valid(payload.person_id) or not await db.persons.find_one({"_id": ObjectId(payload.person_id)}): raise HTTPException(status_code=404, detail="Persona 360 no encontrada")
    if not await db.finance_campaigns.find_one({"campaign_id": payload.campaign_id, "status": "active"}): raise HTTPException(status_code=404, detail="Campaña activa no encontrada")
    pid = str(uuid4()); doc = {"_id": pid, "promise_id": pid, **payload.model_dump(mode="json"), "fulfilled_cents": 0, "status": "active", "created_by_user_id": current_user["user_id"], "created_at": now_utc()}; await db.finance_promises.insert_one(doc); await audit(current_user["user_id"], "promise_created", "promise", pid); return serialize(doc)


@router.get("/vendors", response_model=dict)
async def vendors(current_user: dict = Depends(reader)): return {"items": serialize(await db.finance_vendors.find({}, {"_id": 0}).sort("name", 1).to_list(2000))}


@router.get("/batches", response_model=dict)
async def batches(current_user: dict = Depends(reader)):
    return {"items": serialize(await db.finance_batches.find({}, {"_id": 0}).sort("batch_date", -1).to_list(2000))}


@router.post("/batches", response_model=dict, status_code=201)
async def batch_create(payload: BatchCreate, current_user: dict = Depends(manager)):
    contributions = await db.finance_contributions.find({"contribution_id": {"$in": payload.contribution_ids}, "batch_id": {"$in": [None, ""]}}, {"_id": 0}).to_list(2000)
    if len(contributions) != len(set(payload.contribution_ids)): raise HTTPException(status_code=422, detail="Hay contribuciones inexistentes o ya incluidas en otro conteo")
    batch_id = str(uuid4()); expected = sum(item["amount_cents"] for item in contributions)
    payment_totals = {}; concept_totals = {}; fund_totals = {}
    for contribution in contributions:
        method = contribution.get("payment_method", "other")
        payment_totals[method] = payment_totals.get(method, 0) + contribution.get("amount_cents", 0)
        for allocation in contribution.get("allocations", []):
            concept = allocation.get("contribution_type") or contribution.get("contribution_type") or "other"
            concept_totals[concept] = concept_totals.get(concept, 0) + allocation.get("amount_cents", 0)
            fund_id = allocation.get("fund_id")
            fund_totals[fund_id] = fund_totals.get(fund_id, 0) + allocation.get("amount_cents", 0)
    now = now_utc()
    doc = {"_id": batch_id, "batch_id": batch_id, **payload.model_dump(mode="json"), "service_date": (payload.service_date or payload.batch_date).isoformat(), "expected_envelope_count": payload.expected_envelope_count if payload.expected_envelope_count is not None else len(contributions), "expected_envelope_count_locked": payload.expected_envelope_count is not None, "registered_envelope_count": len(contributions), "expected_total_cents": expected, "expected_payment_totals": payment_totals, "expected_concept_totals": concept_totals, "expected_fund_totals": fund_totals, "counts": [], "status": "awaiting_first_count" if contributions else "collecting", "deposit_id": None, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.finance_batches.insert_one(doc); await db.finance_contributions.update_many({"contribution_id": {"$in": payload.contribution_ids}}, {"$set": {"batch_id": batch_id}}); await audit(current_user["user_id"], "batch_created", "batch", batch_id, {"expected_total_cents": expected}); return serialize(doc)


@router.post("/batches/{batch_id}/start-count", response_model=dict)
async def batch_start_count(batch_id: str, current_user: dict = Depends(manager)):
    batch = await refresh_batch_totals(batch_id)
    if batch.get("status") != "collecting":
        raise HTTPException(status_code=409, detail="La sesión ya inició el conteo")
    if not batch.get("contribution_ids"):
        raise HTTPException(status_code=409, detail="Registre al menos un sobre o contribución")
    now = now_utc()
    await db.finance_batches.update_one({"batch_id": batch_id}, {"$set": {"status": "awaiting_first_count", "collection_closed_by_user_id": current_user["user_id"], "collection_closed_at": now, "updated_at": now}})
    await audit(current_user["user_id"], "batch_collection_closed", "batch", batch_id, {"registered_envelope_count": batch["registered_envelope_count"]})
    return serialize(await db.finance_batches.find_one({"batch_id": batch_id}, {"_id": 0}))


@router.post("/batches/{batch_id}/counts", response_model=dict)
async def batch_count(batch_id: str, payload: BatchCount, current_user: dict = Depends(manager)):
    item = await db.finance_batches.find_one({"batch_id": batch_id})
    if not item: raise HTTPException(status_code=404, detail="Conteo no encontrado")
    if item.get("status") not in {"awaiting_first_count", "awaiting_second_count"}: raise HTTPException(status_code=409, detail="La sesión no está en etapa de conteo")
    counts = item.get("counts", [])
    if len(counts) >= 2: raise HTTPException(status_code=409, detail="El conteo ya tiene dos verificaciones")
    if counts and counts[0]["counted_by_user_id"] == current_user["user_id"]: raise HTTPException(status_code=403, detail="El segundo conteo debe realizarlo otra persona")
    total = payload.cash_cents + payload.check_cents + payload.other_cents; counts.append({**payload.model_dump(), "total_cents": total, "variance_cents": total - item["expected_total_cents"], "counted_by_user_id": current_user["user_id"], "counted_at": now_utc()})
    if len(counts) == 1: status = "awaiting_second_count"
    else:
        envelope_counts = [count.get("envelope_count") for count in counts if count.get("envelope_count") is not None]
        envelopes_match = not envelope_counts or all(count == item.get("expected_envelope_count") for count in envelope_counts)
        status = "ready_for_deposit" if counts[0]["total_cents"] == counts[1]["total_cents"] == item["expected_total_cents"] and envelopes_match else "variance_review"
    await db.finance_batches.update_one({"batch_id": batch_id}, {"$set": {"counts": counts, "status": status, "updated_at": now_utc()}}); await audit(current_user["user_id"], "batch_count_added", "batch", batch_id, {"count_number": len(counts), "total_cents": total}); return serialize(await db.finance_batches.find_one({"batch_id": batch_id}, {"_id": 0}))


@router.post("/batches/{batch_id}/resolve-variance", response_model=dict)
async def batch_resolve_variance(batch_id: str, payload: BatchVarianceResolution, current_user: dict = Depends(manager)):
    if current_user.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="La diferencia requiere autorización pastoral")
    item = await db.finance_batches.find_one({"batch_id": batch_id, "status": "variance_review"})
    if not item:
        raise HTTPException(status_code=404, detail="Conteo con diferencia no encontrado")
    now = now_utc()
    await db.finance_batches.update_one({"batch_id": batch_id}, {"$set": {"status": "ready_for_deposit", "variance_resolution": payload.reason, "variance_resolved_by_user_id": current_user["user_id"], "variance_resolved_at": now, "updated_at": now}})
    await audit(current_user["user_id"], "batch_variance_resolved", "batch", batch_id, {"reason": payload.reason})
    return serialize(await db.finance_batches.find_one({"batch_id": batch_id}, {"_id": 0}))


@router.post("/vendors", response_model=dict, status_code=201)
async def vendor_create(payload: VendorCreate, current_user: dict = Depends(manager)):
    vendor_id = str(uuid4()); doc = {"_id": vendor_id, "vendor_id": vendor_id, **payload.model_dump(), "active": True, "created_by_user_id": current_user["user_id"], "created_at": now_utc()}; await db.finance_vendors.insert_one(doc); await audit(current_user["user_id"], "vendor_created", "vendor", vendor_id); return serialize(doc)


@router.get("/expenses", response_model=dict)
async def expenses(current_user: dict = Depends(reader)): return {"items": serialize(await db.finance_expenses.find({}, {"_id": 0}).sort("expense_date", -1).to_list(3000))}


@router.post("/expenses", response_model=dict, status_code=201)
async def expense_create(payload: ExpenseCreate, current_user: dict = Depends(manager)):
    if sum(line.debit_cents for line in payload.allocations) != payload.total_cents or any(line.credit_cents for line in payload.allocations): raise HTTPException(status_code=422, detail="Las distribuciones de gasto deben sumar el total")
    if payload.vendor_id and not await db.finance_vendors.find_one({"vendor_id": payload.vendor_id, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=422, detail="Proveedor o beneficiario no válido")
    expense_id = str(uuid4()); now = now_utc(); doc = {"_id": expense_id, "expense_id": expense_id, **payload.model_dump(mode="json"), "status": "submitted", "prepared_by_user_id": current_user["user_id"], "reviewed_by_user_id": None, "approved_by_user_id": None, "payment_id": None, "journal_entry_id": None, "created_at": now, "updated_at": now}; await db.finance_expenses.insert_one(doc); await audit(current_user["user_id"], "expense_created", "expense", expense_id, {"total_cents": payload.total_cents, "beneficiary_type": payload.beneficiary_type, "category": payload.category}); return serialize(doc)


@router.post("/expenses/{expense_id}/workflow/{action}", response_model=dict)
async def expense_workflow(expense_id: str, action: Literal["review", "approve", "reject"], current_user: dict = Depends(manager)):
    item = await db.finance_expenses.find_one({"expense_id": expense_id}); uid = current_user["user_id"]; now = now_utc()
    if not item: raise HTTPException(status_code=404, detail="Gasto no encontrado")
    if action == "review":
        if item["status"] != "submitted" or item["prepared_by_user_id"] == uid: raise HTTPException(status_code=403, detail="Otro usuario financiero debe revisar este gasto")
        changes = {"status": "reviewed", "reviewed_by_user_id": uid, "reviewed_at": now}
    elif action == "approve":
        if current_user.get("rol") != "pastor" or item["status"] != "reviewed" or uid in {item["prepared_by_user_id"], item.get("reviewed_by_user_id")}: raise HTTPException(status_code=403, detail="La aprobación pastoral requiere separación de funciones")
        changes = {"status": "approved", "approved_by_user_id": uid, "approved_at": now}
    else: changes = {"status": "rejected", "rejected_by_user_id": uid, "rejected_at": now}
    await db.finance_expenses.update_one({"expense_id": expense_id}, {"$set": {**changes, "updated_at": now}}); await audit(uid, f"expense_{action}", "expense", expense_id); return serialize(await db.finance_expenses.find_one({"expense_id": expense_id}, {"_id": 0}))


@router.post("/expenses/{expense_id}/schedule", response_model=dict)
async def schedule_expense(expense_id: str, payload: PaymentSchedule, current_user: dict = Depends(manager)):
    item = await db.finance_expenses.find_one({"expense_id": expense_id})
    if not item or item.get("status") != "approved":
        raise HTTPException(status_code=409, detail="La cuenta por pagar debe estar aprobada")
    if not await db.finance_accounts.find_one({"account_id": payload.bank_account_id, "account_type": "asset", "active": True}, {"_id": 1}):
        raise HTTPException(status_code=422, detail="Cuenta bancaria no válida")
    now = now_utc()
    schedule = {**payload.model_dump(mode="json"), "scheduled_by_user_id": current_user["user_id"], "scheduled_at": now}
    await db.finance_expenses.update_one({"expense_id": expense_id}, {"$set": {"status": "scheduled", "payment_schedule": schedule, "updated_at": now}})
    await audit(current_user["user_id"], "expense_scheduled", "expense", expense_id, schedule)
    return serialize(await db.finance_expenses.find_one({"expense_id": expense_id}, {"_id": 0}))


@router.get("/payments", response_model=dict)
async def payments(current_user: dict = Depends(reader)):
    return {"items": serialize(await db.finance_payments.find({}, {"_id": 0}).sort("payment_date", -1).to_list(3000))}


@router.post("/expenses/{expense_id}/payments", response_model=dict, status_code=201)
async def pay_expense(expense_id: str, payload: PaymentCreate, current_user: dict = Depends(manager)):
    item = await db.finance_expenses.find_one({"expense_id": expense_id})
    if not item or item["status"] not in {"approved", "scheduled"}: raise HTTPException(status_code=409, detail="El gasto debe tener aprobación pastoral")
    if item.get("payment_id"):
        raise HTTPException(status_code=409, detail="El pago ya fue registrado")
    bank = await db.finance_accounts.find_one({"account_id": payload.bank_account_id, "account_type": "asset", "active": True})
    if not bank: raise HTTPException(status_code=422, detail="Cuenta bancaria no válida")
    lines = []
    for allocation in item["allocations"]: lines.extend([allocation, {"account_id": bank["account_id"], "fund_id": allocation["fund_id"], "debit_cents": 0, "credit_cents": allocation["debit_cents"], "description": "Pago de gasto"}])
    journal = await create_journal(current_user["user_id"], payload.payment_date.isoformat(), f"Pago: {item['description']}", "expense_payment", expense_id, lines, "submitted")
    payment_id = str(uuid4()); now = now_utc(); doc = {"_id": payment_id, "payment_id": payment_id, "expense_id": expense_id, **payload.model_dump(mode="json"), "amount_cents": item["total_cents"], "journal_entry_id": journal["entry_id"], "status": "pending_posting", "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}; await db.finance_payments.insert_one(doc); await db.finance_expenses.update_one({"expense_id": expense_id}, {"$set": {"status": "payment_pending_posting", "payment_id": payment_id, "journal_entry_id": journal["entry_id"], "updated_at": now}}); await audit(current_user["user_id"], "payment_created", "payment", payment_id, {"amount_cents": item["total_cents"], "payment_method": payload.payment_method}); return serialize(doc)


@router.get("/deposits", response_model=dict)
async def deposits(current_user: dict = Depends(reader)): return {"items": serialize(await db.finance_deposits.find({}, {"_id": 0}).sort("deposit_date", -1).to_list(2000))}


@router.post("/deposits", response_model=dict, status_code=201)
async def deposit_create(payload: DepositCreate, current_user: dict = Depends(manager)):
    contributions = await db.finance_contributions.find({"contribution_id": {"$in": payload.contribution_ids}, "deposit_id": None}, {"_id": 0}).to_list(1000)
    if len(contributions) != len(set(payload.contribution_ids)): raise HTTPException(status_code=422, detail="Hay contribuciones inexistentes o ya depositadas")
    if payload.batch_id:
        batch = await db.finance_batches.find_one({"batch_id": payload.batch_id})
        if not batch or batch.get("status") != "ready_for_deposit" or set(batch.get("contribution_ids", [])) != set(payload.contribution_ids): raise HTTPException(status_code=409, detail="El conteo no está listo o no coincide con el depósito")
    bank = await db.finance_accounts.find_one({"account_id": payload.bank_account_id, "account_type": "asset", "active": True}); undeposited = await db.finance_accounts.find_one({"code": "1010"})
    if not bank:
        raise HTTPException(status_code=422, detail="Cuenta bancaria no válida")
    totals = {}
    for contribution in contributions:
        for allocation in contribution["allocations"]: totals[allocation["fund_id"]] = totals.get(allocation["fund_id"], 0) + allocation["amount_cents"]
    deposit_id = str(uuid4()); lines = []
    for fund_id, amount in totals.items(): lines.extend([{"account_id": bank["account_id"], "fund_id": fund_id, "debit_cents": amount, "credit_cents": 0, "description": "Depósito bancario"}, {"account_id": undeposited["account_id"], "fund_id": fund_id, "debit_cents": 0, "credit_cents": amount, "description": "Salida de fondos no depositados"}])
    journal = await create_journal(current_user["user_id"], payload.deposit_date.isoformat(), "Depósito de contribuciones", "deposit", deposit_id, lines, "submitted")
    now = now_utc(); doc = {"_id": deposit_id, "deposit_id": deposit_id, **payload.model_dump(mode="json"), "total_cents": sum(totals.values()), "fund_totals": totals, "journal_entry_id": journal["entry_id"], "status": "pending_reconciliation", "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}; await db.finance_deposits.insert_one(doc); await db.finance_contributions.update_many({"contribution_id": {"$in": payload.contribution_ids}}, {"$set": {"deposit_id": deposit_id, "updated_at": now, "updated_by_user_id": current_user["user_id"]}})
    if payload.batch_id: await db.finance_batches.update_one({"batch_id": payload.batch_id}, {"$set": {"status": "deposited", "deposit_id": deposit_id, "deposited_at": now_utc()}})
    await audit(current_user["user_id"], "deposit_created", "deposit", deposit_id, {"total_cents": doc["total_cents"]}); return serialize(doc)


@router.post("/transfers", response_model=dict, status_code=201)
async def transfer(payload: dict, current_user: dict = Depends(manager)):
    amount = int(payload.get("amount_cents", 0)); source = payload.get("source_fund_id"); target = payload.get("target_fund_id"); account_id = payload.get("account_id")
    if amount <= 0 or not source or not target or source == target: raise HTTPException(status_code=422, detail="Transferencia no válida")
    transfer_id = str(uuid4()); lines = [{"account_id": account_id, "fund_id": target, "debit_cents": amount, "credit_cents": 0, "description": "Entrada por transferencia"}, {"account_id": account_id, "fund_id": source, "debit_cents": 0, "credit_cents": amount, "description": "Salida por transferencia"}]
    journal = await create_journal(current_user["user_id"], payload.get("transfer_date", date.today().isoformat()), payload.get("memo", "Transferencia entre fondos"), "fund_transfer", transfer_id, lines, "submitted"); await audit(current_user["user_id"], "fund_transfer_created", "fund_transfer", transfer_id, {"amount_cents": amount}); return {"transfer_id": transfer_id, "journal_entry_id": journal["entry_id"], "status": "submitted"}


@router.get("/budgets", response_model=dict)
async def budgets(fiscal_year: Optional[int] = None, current_user: dict = Depends(reader)):
    query = {"fiscal_year": fiscal_year} if fiscal_year else {}; return {"items": serialize(await db.finance_budgets.find(query, {"_id": 0}).to_list(5000))}


@router.post("/budgets", response_model=dict, status_code=201)
async def budget_create(payload: BudgetCreate, current_user: dict = Depends(manager)):
    budget_id = str(uuid4()); doc = {"_id": budget_id, "budget_id": budget_id, **payload.model_dump(), "created_by_user_id": current_user["user_id"], "created_at": now_utc()}; await db.finance_budgets.insert_one(doc); await audit(current_user["user_id"], "budget_created", "budget", budget_id); return serialize(doc)


@router.get("/reconciliations", response_model=dict)
async def reconciliations(current_user: dict = Depends(reader)): return {"items": serialize(await db.finance_reconciliations.find({}, {"_id": 0}).sort("statement_end_date", -1).to_list(1000))}


@router.post("/reconciliations", response_model=dict, status_code=201)
async def reconciliation_create(payload: ReconciliationCreate, current_user: dict = Depends(manager)):
    bank = await db.finance_accounts.find_one({"account_id": payload.bank_account_id, "account_type": "asset", "active": True}, {"_id": 1})
    if not bank:
        raise HTTPException(status_code=422, detail="Cuenta bancaria no válida")
    reused = await db.finance_journal_entries.count_documents({"entry_id": {"$in": payload.cleared_entry_ids}, "reconciliation_id": {"$ne": None}})
    if reused:
        raise HTTPException(status_code=409, detail="Hay movimientos que ya pertenecen a otra conciliación")
    entries = await db.finance_journal_entries.find({"entry_id": {"$in": payload.cleared_entry_ids}, "status": "posted", "reconciliation_id": {"$in": [None, ""]}}, {"_id": 0}).to_list(5000)
    if len(entries) != len(set(payload.cleared_entry_ids)):
        raise HTTPException(status_code=422, detail="Hay movimientos inexistentes, no contabilizados o ya conciliados")
    net_activity = sum(sum(line["debit_cents"] - line["credit_cents"] for line in item["lines"] if line["account_id"] == payload.bank_account_id) for item in entries)
    calculated_ending = payload.statement_starting_balance_cents + net_activity
    difference = payload.statement_ending_balance_cents - calculated_ending
    rid = str(uuid4()); now = now_utc(); status_value = "balanced" if difference == 0 else "needs_review"
    doc = {"_id": rid, "reconciliation_id": rid, **payload.model_dump(mode="json"), "net_activity_cents": net_activity, "calculated_ending_balance_cents": calculated_ending, "cleared_balance_cents": calculated_ending, "difference_cents": difference, "status": status_value, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.finance_reconciliations.insert_one(doc)
    if status_value == "balanced" and payload.cleared_entry_ids:
        await db.finance_journal_entries.update_many({"entry_id": {"$in": payload.cleared_entry_ids}}, {"$set": {"reconciliation_id": rid, "reconciled_at": now, "updated_at": now}})
        await db.finance_deposits.update_many({"journal_entry_id": {"$in": payload.cleared_entry_ids}}, {"$set": {"status": "reconciled", "reconciliation_id": rid, "reconciled_at": now, "updated_at": now}})
        await db.finance_payments.update_many({"journal_entry_id": {"$in": payload.cleared_entry_ids}}, {"$set": {"reconciliation_id": rid, "reconciled_at": now, "updated_at": now}})
    await audit(current_user["user_id"], "reconciliation_created", "reconciliation", rid, {"difference_cents": difference, "entry_count": len(entries)})
    return serialize(doc)


@router.get("/reports/{report_key}", response_model=dict)
async def report(report_key: Literal["income-expense", "fund-balances", "budget-vs-actual", "activity", "financial-position", "cash-flow", "contributions", "contributions-by-family", "expenses-by-ministry", "payables", "deposits", "reconciliations", "recurring", "audit"], start: Optional[str] = None, end: Optional[str] = None, current_user: dict = Depends(reader)):
    match = {"status": "posted"}
    if start or end: match["entry_date"] = {**({"$gte": start} if start else {}), **({"$lte": end} if end else {})}
    if report_key == "audit": return {"items": serialize(await db.finance_audit_events.find({}, {"_id": 0}).sort("created_at", -1).limit(5000).to_list(5000))}
    if report_key == "payables":
        query = {"expense_date": match["entry_date"]} if "entry_date" in match else {}
        return {"items": serialize(await db.finance_expenses.find(query, {"_id": 0}).sort("expense_date", -1).to_list(5000))}
    if report_key == "deposits":
        query = {"deposit_date": match["entry_date"]} if "entry_date" in match else {}
        return {"items": serialize(await db.finance_deposits.find(query, {"_id": 0}).sort("deposit_date", -1).to_list(5000))}
    if report_key == "reconciliations":
        query = {"statement_end_date": match["entry_date"]} if "entry_date" in match else {}
        return {"items": serialize(await db.finance_reconciliations.find(query, {"_id": 0}).sort("statement_end_date", -1).to_list(5000))}
    if report_key == "recurring":
        return {"items": serialize(await db.finance_recurring_obligations.find({}, {"_id": 0}).sort("next_due_date", 1).to_list(5000))}
    if report_key == "contributions":
        pipeline = [{"$match": {"status": {"$ne": "corrected"}, **({"received_date": match["entry_date"]} if "entry_date" in match else {})}}, {"$unwind": "$allocations"}, {"$lookup": {"from": "finance_funds", "localField": "allocations.fund_id", "foreignField": "fund_id", "as": "fund"}}, {"$unwind": "$fund"}, {"$group": {"_id": {"contribution_type": {"$ifNull": ["$allocations.contribution_type", "$contribution_type"]}, "fund_id": "$allocations.fund_id", "fund_name": "$fund.name", "payment_method": "$payment_method"}, "amount_cents": {"$sum": "$allocations.amount_cents"}, "count": {"$sum": 1}}}]; return {"items": serialize(await db.finance_contributions.aggregate(pipeline).to_list(1000))}
    if report_key == "contributions-by-family":
        pipeline = [{"$match": {"status": {"$ne": "corrected"}, "household_id": {"$nin": [None, ""]}, **({"received_date": match["entry_date"]} if "entry_date" in match else {})}}, {"$unwind": "$allocations"}, {"$group": {"_id": {"household_id": "$household_id", "contribution_type": {"$ifNull": ["$allocations.contribution_type", "$contribution_type"]}}, "amount_cents": {"$sum": "$allocations.amount_cents"}, "count": {"$sum": 1}}}]
        return {"items": serialize(await db.finance_contributions.aggregate(pipeline).to_list(5000))}
    if report_key == "expenses-by-ministry":
        pipeline = [{"$match": {"status": {"$in": ["approved", "payment_pending_posting", "paid"]}}}, {"$group": {"_id": {"ministry_id": "$ministry_id"}, "amount_cents": {"$sum": "$total_cents"}, "count": {"$sum": 1}}}]; return {"items": serialize(await db.finance_expenses.aggregate(pipeline).to_list(1000))}
    pipeline = [{"$match": match}, {"$unwind": "$lines"}, {"$lookup": {"from": "finance_accounts", "localField": "lines.account_id", "foreignField": "account_id", "as": "account"}}, {"$unwind": "$account"}, {"$lookup": {"from": "finance_funds", "localField": "lines.fund_id", "foreignField": "fund_id", "as": "fund"}}, {"$unwind": "$fund"}, {"$group": {"_id": {"fund_id": "$lines.fund_id", "fund_name": "$fund.name", "account_id": "$lines.account_id", "account_name": "$account.name", "account_type": "$account.account_type"}, "debit_cents": {"$sum": "$lines.debit_cents"}, "credit_cents": {"$sum": "$lines.credit_cents"}}}, {"$sort": {"_id.fund_name": 1, "_id.account_name": 1}}]
    rows = await db.finance_journal_entries.aggregate(pipeline).to_list(5000)
    for row in rows:
        account_type = row["_id"]["account_type"]
        row["amount_cents"] = row["debit_cents"] - row["credit_cents"] if account_type in {"asset", "expense"} else row["credit_cents"] - row["debit_cents"]
    if report_key == "income-expense": rows = [row for row in rows if row["_id"]["account_type"] in {"revenue", "expense"}]
    elif report_key == "financial-position": rows = [row for row in rows if row["_id"]["account_type"] in {"asset", "liability", "net_assets"}]
    elif report_key == "cash-flow": rows = [row for row in rows if row["_id"]["account_type"] == "asset"]
    elif report_key == "fund-balances":
        grouped = {}
        for row in rows:
            account_type = row["_id"]["account_type"]
            if account_type not in {"net_assets", "revenue", "expense"}: continue
            amount = -row["amount_cents"] if account_type == "expense" else row["amount_cents"]
            key = (row["_id"]["fund_id"], row["_id"]["fund_name"]); grouped[key] = grouped.get(key, 0) + amount
        rows = [{"_id": {"fund_id": key[0], "fund_name": key[1], "account_name": "Balance del fondo"}, "amount_cents": value, "debit_cents": 0, "credit_cents": 0} for key, value in grouped.items()]
    elif report_key == "budget-vs-actual":
        actual = {(row["_id"]["fund_id"], row["_id"]["account_id"]): row["amount_cents"] for row in rows if row["_id"]["account_type"] == "expense"}
        budgets = await db.finance_budgets.find({}, {"_id": 0}).to_list(5000); fund_names = {item["fund_id"]: item["name"] for item in await db.finance_funds.find({}, {"_id": 0, "fund_id": 1, "name": 1}).to_list(1000)}; account_names = {item["account_id"]: item["name"] for item in await db.finance_accounts.find({}, {"_id": 0, "account_id": 1, "name": 1}).to_list(1000)}
        rows = [{"_id": {"fund_id": item["fund_id"], "fund_name": fund_names.get(item["fund_id"], "Fondo"), "account_id": item["account_id"], "account_name": account_names.get(item["account_id"], "Cuenta")}, "budget_cents": item["amount_cents"], "actual_cents": actual.get((item["fund_id"], item["account_id"]), 0), "variance_cents": item["amount_cents"] - actual.get((item["fund_id"], item["account_id"]), 0), "amount_cents": actual.get((item["fund_id"], item["account_id"]), 0), "debit_cents": 0, "credit_cents": 0} for item in budgets]
    return {"report_key": report_key, "accounting_basis": (await db.finance_settings.find_one({"_id": "primary"}))["accounting_basis"], "items": serialize(rows)}


@router.get("/integrations/pushpay", response_model=dict)
async def pushpay_status(current_user: dict = Depends(reader)):
    configured = all(os.environ.get(key) for key in ["PUSHPAY_CLIENT_ID", "PUSHPAY_CLIENT_SECRET", "PUSHPAY_ORGANIZATION_KEY", "PUSHPAY_MERCHANT_KEY"])
    return {"provider": "pushpay", "configured": configured, "status": "ready" if configured else "blocked_credentials_required", "required_credentials": [] if configured else ["PUSHPAY_CLIENT_ID", "PUSHPAY_CLIENT_SECRET", "PUSHPAY_ORGANIZATION_KEY", "PUSHPAY_MERCHANT_KEY"], "architecture": "adapter_only"}


@router.post("/integrations/pushpay/sync", response_model=dict)
async def pushpay_sync(current_user: dict = Depends(manager)):
    if not all(os.environ.get(key) for key in ["PUSHPAY_CLIENT_ID", "PUSHPAY_CLIENT_SECRET", "PUSHPAY_ORGANIZATION_KEY", "PUSHPAY_MERCHANT_KEY"]): raise HTTPException(status_code=503, detail="Pushpay está preparado pero bloqueado hasta configurar credenciales sandbox")
    raise HTTPException(status_code=503, detail="Credenciales detectadas; complete la validación sandbox antes de activar sincronización")