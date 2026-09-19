"""Núcleo contable por fondos para VEN Y VE 360."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from pymongo import ReturnDocument

from access_control import FINANCE_MANAGE, FINANCE_READ
from server import db


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, datetime): return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, list): return [serialize(item) for item in value]
    if isinstance(value, dict): return {key: serialize(item) for key, item in value.items() if key != "_id"}
    return value


def require_finance_read(current_user: dict) -> None:
    if current_user.get("rol") == "pastor": return
    if FINANCE_READ not in (current_user.get("capabilities") or []):
        raise HTTPException(status_code=403, detail="El pastor no ha concedido acceso a Finanzas")


def require_finance_manage(current_user: dict) -> None:
    require_finance_read(current_user)
    if current_user.get("rol") != "pastor" and FINANCE_MANAGE not in (current_user.get("capabilities") or []):
        raise HTTPException(status_code=403, detail="Acceso financiero de consulta solamente")


async def audit(user_id: str, action: str, entity_type: str, entity_id: str, changes: dict | None = None):
    event_id = str(uuid4())
    await db.finance_audit_events.insert_one({"_id": event_id, "event_id": event_id, "action": action, "entity_type": entity_type, "entity_id": entity_id, "actor_user_id": user_id, "changes": changes or {}, "created_at": now_utc()})


async def validate_lines(lines: list[dict]) -> tuple[int, int]:
    if len(lines) < 2: raise HTTPException(status_code=422, detail="Un asiento necesita al menos dos líneas")
    debit = sum(int(line.get("debit_cents", 0)) for line in lines); credit = sum(int(line.get("credit_cents", 0)) for line in lines)
    if debit <= 0 or debit != credit: raise HTTPException(status_code=422, detail="El asiento debe estar balanceado y ser mayor que cero")
    for line in lines:
        if line.get("debit_cents", 0) and line.get("credit_cents", 0): raise HTTPException(status_code=422, detail="Una línea no puede tener débito y crédito simultáneamente")
        if not await db.finance_accounts.find_one({"account_id": line.get("account_id"), "active": True}): raise HTTPException(status_code=422, detail="Cuenta contable no válida")
        if not await db.finance_funds.find_one({"fund_id": line.get("fund_id"), "active": True}): raise HTTPException(status_code=422, detail="Fondo no válido")
    return debit, credit


async def ensure_open_period(entry_date: str) -> None:
    closed = await db.finance_periods.find_one(
        {
            "start_date": {"$lte": entry_date},
            "end_date": {"$gte": entry_date},
            "status": "closed",
        },
        {"_id": 0, "period_id": 1},
    )
    if closed:
        raise HTTPException(
            status_code=409,
            detail=f"El período {closed['period_id']} está cerrado; registre un ajuste en un período abierto o solicite reapertura",
        )


async def reserve_entry_number(entry_id: str) -> int:
    latest = await db.finance_journal_entries.find({"entry_number": {"$type": "number"}}, {"_id": 0, "entry_number": 1}).sort("entry_number", -1).limit(1).to_list(1)
    highest = int(latest[0]["entry_number"]) if latest else 0
    await db.counters.update_one({"_id": "finance_entry_number"}, {"$max": {"seq": highest}}, upsert=True)
    counter = await db.counters.find_one_and_update({"_id": "finance_entry_number"}, {"$inc": {"seq": 1}}, return_document=ReturnDocument.AFTER)
    entry_number = int(counter["seq"])
    await db.finance_entry_number_registry.insert_one({"_id": str(entry_number), "entry_number": entry_number, "entry_id": entry_id, "reserved_at": now_utc()})
    return entry_number


async def create_journal(user_id: str, entry_date: str, memo: str, source_type: str, source_id: str, lines: list[dict], status: str = "draft") -> dict:
    await ensure_open_period(entry_date)
    debit, credit = await validate_lines(lines); entry_id = str(uuid4()); now = now_utc(); entry_number = await reserve_entry_number(entry_id)
    doc = {"_id": entry_id, "entry_id": entry_id, "entry_number": entry_number, "entry_date": entry_date, "memo": memo, "source_type": source_type, "source_id": source_id, "status": status, "lines": lines, "total_debit_cents": debit, "total_credit_cents": credit, "prepared_by_user_id": user_id, "reviewed_by_user_id": None, "approved_by_user_id": None, "submitted_at": now if status == "submitted" else None, "reviewed_at": None, "approved_at": None, "posted_at": None, "created_at": now, "updated_at": now}
    try:
        await db.finance_journal_entries.insert_one(doc)
    except Exception:
        await db.finance_entry_number_registry.delete_one({"_id": str(entry_number), "entry_id": entry_id})
        raise
    await audit(user_id, "journal_created", "journal_entry", entry_id, {"source_type": source_type, "source_id": source_id, "total_cents": debit}); return serialize(doc)


async def ensure_indexes_and_seed():
    await db.finance_funds.create_index("fund_id", unique=True); await db.finance_funds.create_index("code", unique=True)
    await db.finance_accounts.create_index("account_id", unique=True); await db.finance_accounts.create_index("code", unique=True)
    await db.finance_periods.create_index([("year", 1), ("month", 1)], unique=True)
    await db.finance_journal_entries.create_index("entry_id", unique=True)
    duplicate_number = await db.finance_journal_entries.aggregate([{"$group": {"_id": "$entry_number", "count": {"$sum": 1}}}, {"$match": {"_id": {"$ne": None}, "count": {"$gt": 1}}}, {"$limit": 1}]).to_list(1)
    if not duplicate_number:
        await db.finance_journal_entries.create_index("entry_number", unique=True)
    await db.finance_entry_number_registry.create_index("entry_number", unique=True)
    external_index = "source_1_external_transaction_id_1"
    existing_indexes = await db.finance_contributions.index_information()
    if external_index in existing_indexes and not existing_indexes[external_index].get("partialFilterExpression"):
        await db.finance_contributions.drop_index(external_index)
    await db.finance_contributions.create_index([("source", 1), ("external_transaction_id", 1)], name=external_index, unique=True, partialFilterExpression={"external_transaction_id": {"$type": "string"}})
    await db.finance_vendors.create_index("vendor_id", unique=True); await db.finance_expenses.create_index("expense_id", unique=True)
    await db.finance_deposits.create_index("deposit_id", unique=True); await db.finance_budgets.create_index("budget_id", unique=True)
    await db.finance_reconciliations.create_index("reconciliation_id", unique=True); await db.finance_audit_events.create_index([("created_at", -1)])
    await db.finance_campaigns.create_index("campaign_id", unique=True); await db.finance_promises.create_index("promise_id", unique=True)
    await db.finance_batches.create_index("batch_id", unique=True)
    await db.finance_contribution_types.create_index("type_key", unique=True)
    await db.finance_contribution_corrections.create_index("correction_id", unique=True)
    await db.finance_annual_statements.create_index("statement_id", unique=True)
    await db.finance_annual_statements.create_index([("person_id", 1), ("year", -1)])
    await db.finance_recurring_obligations.create_index("obligation_id", unique=True)
    await db.finance_recurring_obligations.create_index([("active", 1), ("next_due_date", 1)])
    await db.finance_recurring_runs.create_index([("obligation_id", 1), ("due_date", 1)], unique=True)
    await db["finance_documents.files"].create_index([("metadata.entity_type", 1), ("metadata.entity_id", 1), ("uploadDate", -1)])
    now = now_utc()
    await db.finance_settings.update_one({"_id": "primary"}, {"$setOnInsert": {"accounting_basis": "cash", "currency": "USD", "fiscal_year_start_month": 1, "approval_flow": ["preparer", "reviewer", "pastoral_approver"], "pushpay_status": "blocked_credentials_required", "organization": {"legal_name": "Casa de Oración Ven y Ve", "address": "", "city_state_zip": "Columbus, Ohio", "tax_id": "", "phone": "", "email": ""}, "annual_statement_template": {"title": "Carta anual de contribuciones", "intro_text": "", "acknowledgment_text": "", "footer_text": "", "approved": False, "version": 1}, "created_at": now}, "$set": {"updated_at": now}}, upsert=True)
    await db.finance_settings.update_one({"_id": "primary", "organization": {"$exists": False}}, {"$set": {"organization": {"legal_name": "Casa de Oración Ven y Ve", "address": "", "city_state_zip": "Columbus, Ohio", "tax_id": "", "phone": "", "email": ""}, "annual_statement_template": {"title": "Carta anual de contribuciones", "intro_text": "", "acknowledgment_text": "", "footer_text": "", "approved": False, "version": 1}, "updated_at": now}})
    funds = [("GENERAL", "Fondo General", "unrestricted"), ("MISSIONS", "Misiones", "donor_restricted"), ("BUILDING", "Pro-Templo", "donor_restricted")]
    for code, name, restriction in funds:
        await db.finance_funds.update_one({"code": code}, {"$setOnInsert": {"_id": str(uuid4()), "fund_id": str(uuid4()), "code": code, "name": name, "restriction_type": restriction, "purpose": name, "active": True, "created_at": now}}, upsert=True)
    accounts = [("1000", "Efectivo", "asset"), ("1010", "Fondos no depositados", "asset"), ("1020", "Banco principal", "asset"), ("2000", "Cuentas por pagar", "liability"), ("3000", "Activos netos sin restricción", "net_assets"), ("3100", "Activos netos con restricción", "net_assets"), ("4000", "Ingresos por diezmos", "revenue"), ("4010", "Ingresos por ofrendas", "revenue"), ("4020", "Ingresos por donaciones", "revenue"), ("4030", "Ingresos para misiones", "revenue"), ("4040", "Ingresos Pro-Templo", "revenue"), ("4050", "Ingresos de proyectos y campañas", "revenue"), ("4090", "Otros ingresos", "revenue"), ("5000", "Gastos ministeriales", "expense"), ("5010", "Gastos de misiones", "expense"), ("5020", "Gastos Pro-Templo", "expense"), ("5030", "Servicios públicos", "expense"), ("5040", "Mantenimiento y reparaciones", "expense"), ("5050", "Compensación y apoyo ministerial", "expense"), ("5090", "Otros gastos operacionales", "expense")]
    for code, name, account_type in accounts:
        await db.finance_accounts.update_one({"code": code}, {"$setOnInsert": {"_id": str(uuid4()), "account_id": str(uuid4()), "code": code, "name": name, "account_type": account_type, "active": True, "created_at": now}}, upsert=True)
    contribution_types = [
        ("tithe", "Diezmo", "4000", True),
        ("offering", "Ofrenda", "4010", True),
        ("donation", "Donación", "4020", True),
        ("missions", "Misiones", "4030", True),
        ("building", "Pro-Templo", "4040", True),
        ("project", "Proyecto / Campaña", "4050", True),
        ("other", "Otro ingreso", "4090", False),
    ]
    for key, name, account_code, annual_statement_eligible in contribution_types:
        account = await db.finance_accounts.find_one({"code": account_code}, {"_id": 0, "account_id": 1})
        await db.finance_contribution_types.update_one({"type_key": key}, {"$setOnInsert": {"_id": key, "type_key": key, "name": name, "revenue_account_id": account["account_id"], "annual_statement_eligible": annual_statement_eligible, "active": True, "created_at": now}}, upsert=True)
        await db.finance_contribution_types.update_one({"type_key": key, "annual_statement_eligible": {"$exists": False}}, {"$set": {"annual_statement_eligible": annual_statement_eligible, "updated_at": now}})