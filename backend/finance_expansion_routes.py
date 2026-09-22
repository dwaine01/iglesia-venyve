"""Cierre operativo del Mega-Bloque G sobre el mismo núcleo financiero."""
import calendar
import hashlib
import os
import re
from datetime import date, datetime, timedelta
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field

from access_control import is_global_pastoral_authority
from finance_engine import audit, create_journal, ensure_open_period, now_utc, require_finance_manage, require_finance_read, serialize
from finance_routes import ContributionCreate, ExpenseCreate, contribution_create, expense_create
from server import db, get_current_user


router = APIRouter(prefix="/api/finance", tags=["finance-expansion"])
MAX_DOCUMENT_BYTES = int(os.environ.get("MAX_FINANCE_DOCUMENT_BYTES", "10485760"))
ALLOWED_DOCUMENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}


def reader(current_user: dict = Depends(get_current_user)) -> dict:
    require_finance_read(current_user)
    return current_user


def manager(current_user: dict = Depends(get_current_user)) -> dict:
    require_finance_manage(current_user)
    return current_user


def require_pastor(current_user: dict) -> None:
    if not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Esta configuración corresponde a Pastor/Pastora")


class ContributionTypeInput(BaseModel):
    type_key: str = Field(pattern=r"^[a-z0-9_-]{2,80}$")
    name: str = Field(min_length=2, max_length=120)
    revenue_account_id: str
    annual_statement_eligible: bool = False
    active: bool = True


class StatementSettingsInput(BaseModel):
    organization: dict
    annual_statement_template: dict


class ContributionCorrectionRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)
    correction_date: date = Field(default_factory=date.today)
    replacement: ContributionCreate


class RecurringObligationInput(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    vendor_id: Optional[str] = None
    beneficiary_type: Literal["vendor", "employee", "pastor", "ministry", "other"] = "vendor"
    compensation_classification: Optional[str] = Field(default=None, max_length=200)
    description: str = Field(min_length=3, max_length=500)
    category: Optional[str] = Field(default=None, max_length=120)
    expense_nature: Literal["fixed", "variable"] = "fixed"
    amount_cents: int = Field(gt=0)
    account_id: str
    fund_id: str
    ministry_id: Optional[str] = None
    cost_center: Optional[str] = Field(default=None, max_length=120)
    frequency: Literal["weekly", "monthly", "quarterly", "yearly"]
    next_due_date: date
    active: bool = True


def document_bucket():
    return AsyncIOMotorGridFSBucket(db, bucket_name="finance_documents")


def detect_document_type(first_chunk: bytes) -> Optional[str]:
    if first_chunk.startswith(b"%PDF-"):
        return "application/pdf"
    if first_chunk.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if first_chunk.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


async def canonical_person(person_id: str) -> dict:
    query = {"$or": [{"person_id": person_id}, {"_id": person_id}]}
    if ObjectId.is_valid(person_id):
        query["$or"].append({"_id": ObjectId(person_id)})
    person = await db.persons.find_one(query, {"_id": 0})
    if not person:
        raise HTTPException(status_code=404, detail="Persona 360 no encontrada")
    person["person_id"] = person.get("person_id") or person_id
    return person


def person_name(person: dict) -> str:
    return person.get("display_name") or " ".join(filter(None, [person.get("nombre"), person.get("apellido")])).strip() or "Persona"


def date_filter(year: Optional[int], start: Optional[date], end: Optional[date]) -> dict:
    if year:
        return {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31"}
    query = {}
    if start:
        query["$gte"] = start.isoformat()
    if end:
        query["$lte"] = end.isoformat()
    return query


async def contribution_summary(
    person_id: str,
    year: Optional[int] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    contribution_type: Optional[str] = None,
    fund_id: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> dict:
    person = await canonical_person(person_id)
    canonical_id = person["person_id"]
    query = {"person_id": canonical_id, "status": {"$ne": "corrected"}}
    received = date_filter(year, start, end)
    if received:
        query["received_date"] = received
    if payment_method:
        query["payment_method"] = payment_method
    contributions = await db.finance_contributions.find(query, {"_id": 0}).sort("received_date", -1).to_list(10000)
    type_docs = {item["type_key"]: item for item in await db.finance_contribution_types.find({}, {"_id": 0}).to_list(500)}
    funds = {item["fund_id"]: item for item in await db.finance_funds.find({}, {"_id": 0}).to_list(1000)}
    campaigns = {item["campaign_id"]: item for item in await db.finance_campaigns.find({}, {"_id": 0}).to_list(1000)}
    rows = []
    totals_by_type = {}
    totals_by_fund = {}
    totals_by_method = {}
    reportable_total = 0
    for contribution in contributions:
        for allocation in contribution.get("allocations", []):
            type_key = allocation.get("contribution_type") or contribution.get("contribution_type") or "other"
            allocation_fund_id = allocation.get("fund_id")
            if contribution_type and type_key != contribution_type:
                continue
            if fund_id and allocation_fund_id != fund_id:
                continue
            amount = int(allocation.get("amount_cents", 0))
            type_doc = type_docs.get(type_key, {})
            eligible = allocation.get("annual_statement_eligible")
            if eligible is None:
                eligible = type_doc.get("annual_statement_eligible", False)
            if eligible:
                reportable_total += amount
            totals_by_type[type_key] = totals_by_type.get(type_key, 0) + amount
            totals_by_fund[allocation_fund_id] = totals_by_fund.get(allocation_fund_id, 0) + amount
            method = contribution.get("payment_method", "other")
            totals_by_method[method] = totals_by_method.get(method, 0) + amount
            rows.append({
                "contribution_id": contribution["contribution_id"],
                "received_date": contribution["received_date"],
                "registered_at": serialize(contribution.get("created_at")),
                "contribution_type": type_key,
                "contribution_type_name": type_doc.get("name", type_key),
                "fund_id": allocation_fund_id,
                "fund_name": funds.get(allocation_fund_id, {}).get("name", "Fondo"),
                "campaign_id": allocation.get("campaign_id"),
                "campaign_name": campaigns.get(allocation.get("campaign_id"), {}).get("name"),
                "payment_method": method,
                "amount_cents": amount,
                "reference": contribution.get("reference"),
                "description": allocation.get("description") or contribution.get("description"),
                "notes": contribution.get("notes"),
                "annual_statement_eligible": bool(eligible),
                "created_by_user_id": contribution.get("created_by_user_id"),
                "updated_by_user_id": contribution.get("updated_by_user_id"),
            })
    return {
        "person": {"person_id": canonical_id, "name": person_name(person), "vv_number": person.get("vv_number")},
        "filters": {"year": year, "start": start.isoformat() if start else None, "end": end.isoformat() if end else None, "contribution_type": contribution_type, "fund_id": fund_id, "payment_method": payment_method},
        "total_cents": sum(item["amount_cents"] for item in rows),
        "reportable_total_cents": reportable_total,
        "totals_by_type": totals_by_type,
        "totals_by_fund": totals_by_fund,
        "totals_by_method": totals_by_method,
        "items": rows,
    }


@router.get("/contribution-types", response_model=dict)
async def contribution_types(current_user: dict = Depends(reader)):
    return {"items": serialize(await db.finance_contribution_types.find({}, {"_id": 0}).sort("name", 1).to_list(500))}


@router.post("/contribution-types", response_model=dict, status_code=201)
async def contribution_type_create(payload: ContributionTypeInput, current_user: dict = Depends(manager)):
    require_pastor(current_user)
    if not await db.finance_accounts.find_one({"account_id": payload.revenue_account_id, "account_type": "revenue", "active": True}, {"_id": 1}):
        raise HTTPException(status_code=422, detail="Cuenta de ingreso no válida")
    now = now_utc()
    doc = {"_id": payload.type_key, **payload.model_dump(), "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    if await db.finance_contribution_types.find_one({"type_key": payload.type_key}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="El concepto ya existe")
    await db.finance_contribution_types.insert_one(doc)
    await audit(current_user["user_id"], "contribution_type_created", "contribution_type", payload.type_key, payload.model_dump())
    return serialize(doc)


@router.put("/contribution-types/{type_key}", response_model=dict)
async def contribution_type_update(type_key: str, payload: ContributionTypeInput, current_user: dict = Depends(manager)):
    require_pastor(current_user)
    if payload.type_key != type_key:
        raise HTTPException(status_code=422, detail="La clave del concepto no puede cambiar")
    before = await db.finance_contribution_types.find_one({"type_key": type_key}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Concepto no encontrado")
    changes = {**payload.model_dump(), "updated_by_user_id": current_user["user_id"], "updated_at": now_utc()}
    await db.finance_contribution_types.update_one({"type_key": type_key}, {"$set": changes})
    await audit(current_user["user_id"], "contribution_type_updated", "contribution_type", type_key, {"before": before, "after": changes})
    return serialize(await db.finance_contribution_types.find_one({"type_key": type_key}, {"_id": 0}))


@router.get("/contributors/search", response_model=dict)
async def contributor_search(search: str = Query(min_length=2, max_length=120), current_user: dict = Depends(reader)):
    safe = re.escape(search.strip())
    people = await db.persons.find({"$or": [{"nombre": {"$regex": safe, "$options": "i"}}, {"apellido": {"$regex": safe, "$options": "i"}}, {"display_name": {"$regex": safe, "$options": "i"}}, {"email": {"$regex": safe, "$options": "i"}}]}).limit(20).to_list(20)
    items = []
    for person in people:
        pid = person.get("person_id") or str(person.get("_id"))
        items.append({"person_id": pid, "name": person_name(person), "vv_number": person.get("vv_number"), "contribution_count": await db.finance_contributions.count_documents({"person_id": pid, "status": {"$ne": "corrected"}})})
    return {"items": items}


@router.get("/contributors/{person_id}", response_model=dict)
async def contributor_detail(
    person_id: str,
    year: Optional[int] = Query(default=None, ge=2000, le=2200),
    start: Optional[date] = None,
    end: Optional[date] = None,
    contribution_type: Optional[str] = None,
    fund_id: Optional[str] = None,
    payment_method: Optional[str] = None,
    current_user: dict = Depends(reader),
):
    return await contribution_summary(person_id, year, start, end, contribution_type, fund_id, payment_method)


@router.get("/settings/annual-statements", response_model=dict)
async def annual_statement_settings(current_user: dict = Depends(reader)):
    settings = await db.finance_settings.find_one({"_id": "primary"}, {"_id": 0, "organization": 1, "annual_statement_template": 1})
    return serialize(settings or {})


@router.put("/settings/annual-statements", response_model=dict)
async def annual_statement_settings_update(payload: StatementSettingsInput, current_user: dict = Depends(manager)):
    require_pastor(current_user)
    allowed_organization = {key: str(payload.organization.get(key) or "").strip()[:500] for key in ["legal_name", "address", "city_state_zip", "tax_id", "phone", "email"]}
    template = {key: payload.annual_statement_template.get(key) for key in ["title", "intro_text", "acknowledgment_text", "footer_text", "approved", "version"]}
    template["title"] = str(template.get("title") or "Carta anual de contribuciones")[:200]
    for key in ["intro_text", "acknowledgment_text", "footer_text"]:
        template[key] = str(template.get(key) or "")[:5000]
    template["approved"] = bool(template.get("approved"))
    template["version"] = max(1, int(template.get("version") or 1))
    now = now_utc()
    if template["approved"]:
        template.update({"approved_by_user_id": current_user["user_id"], "approved_at": now})
    await db.finance_settings.update_one({"_id": "primary"}, {"$set": {"organization": allowed_organization, "annual_statement_template": template, "updated_at": now, "updated_by_user_id": current_user["user_id"]}})
    await audit(current_user["user_id"], "annual_statement_settings_updated", "finance_settings", "primary", {"template_version": template["version"], "approved": template["approved"]})
    return await annual_statement_settings(current_user)


@router.post("/contributors/{person_id}/annual-statements/{year}", response_model=dict, status_code=201)
async def annual_statement_generate(person_id: str, year: int, current_user: dict = Depends(manager)):
    if year < 2000 or year > 2200:
        raise HTTPException(status_code=422, detail="Año no válido")
    summary = await contribution_summary(person_id, year=year)
    eligible_items = [item for item in summary["items"] if item["annual_statement_eligible"]]
    settings = await db.finance_settings.find_one({"_id": "primary"}, {"_id": 0, "organization": 1, "annual_statement_template": 1}) or {}
    template = settings.get("annual_statement_template") or {}
    statement_id = str(uuid4()); now = now_utc()
    doc = {
        "_id": statement_id,
        "statement_id": statement_id,
        "person_id": summary["person"]["person_id"],
        "year": year,
        "status": "approved_template" if template.get("approved") else "draft_pending_legal_approval",
        "organization_snapshot": settings.get("organization") or {},
        "template_snapshot": template,
        "person_snapshot": summary["person"],
        "items": eligible_items,
        "total_cents": sum(item["amount_cents"] for item in eligible_items),
        "generated_by_user_id": current_user["user_id"],
        "generated_at": now,
    }
    await db.finance_annual_statements.insert_one(doc)
    await audit(current_user["user_id"], "annual_statement_generated", "annual_statement", statement_id, {"person_id": summary["person"]["person_id"], "year": year, "total_cents": doc["total_cents"], "status": doc["status"]})
    return serialize(doc)


@router.get("/contributors/{person_id}/history", response_model=dict)
async def contributor_history(person_id: str, current_user: dict = Depends(reader)):
    person = await canonical_person(person_id)
    contribution_ids = await db.finance_contributions.distinct("contribution_id", {"person_id": person["person_id"]})
    corrections = await db.finance_contribution_corrections.find({"original_contribution_id": {"$in": contribution_ids}}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    audits = await db.finance_audit_events.find({"entity_id": {"$in": contribution_ids}}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    return {"corrections": serialize(corrections), "audit_events": serialize(audits)}


@router.post("/contributions/{contribution_id}/correct", response_model=dict, status_code=201)
async def contribution_correct(contribution_id: str, payload: ContributionCorrectionRequest, current_user: dict = Depends(manager)):
    original = await db.finance_contributions.find_one({"contribution_id": contribution_id})
    if not original:
        raise HTTPException(status_code=404, detail="Contribución no encontrada")
    if original.get("status") == "corrected":
        raise HTTPException(status_code=409, detail="La contribución ya fue corregida")
    await ensure_open_period(payload.correction_date.isoformat())
    payload.replacement.accounting_date = payload.correction_date
    original_journal = await db.finance_journal_entries.find_one({"entry_id": original.get("journal_entry_id")})
    reversal = None
    if original_journal and original_journal.get("status") == "posted":
        reversal_lines = [{**line, "debit_cents": line.get("credit_cents", 0), "credit_cents": line.get("debit_cents", 0), "description": f"Reversión: {line.get('description', '')}"} for line in original_journal.get("lines", [])]
        reversal = await create_journal(current_user["user_id"], payload.correction_date.isoformat(), f"Reversión por corrección · {payload.reason}", "contribution_reversal", contribution_id, reversal_lines, "submitted")
    try:
        replacement = await contribution_create(payload.replacement, current_user)
    except Exception:
        if reversal:
            await db.finance_journal_entries.delete_one({"entry_id": reversal["entry_id"]})
            await db.finance_audit_events.delete_many({"entity_id": reversal["entry_id"]})
        raise
    now = now_utc()
    if original_journal and original_journal.get("status") != "posted":
        await db.finance_journal_entries.update_one({"entry_id": original_journal["entry_id"]}, {"$set": {"status": "voided", "void_reason": payload.reason, "voided_by_user_id": current_user["user_id"], "voided_at": now, "updated_at": now}})
    await db.finance_contributions.update_one({"contribution_id": contribution_id}, {"$set": {"status": "corrected", "replaced_by_contribution_id": replacement["contribution_id"], "correction_reason": payload.reason, "corrected_by_user_id": current_user["user_id"], "corrected_at": now, "updated_by_user_id": current_user["user_id"], "updated_at": now}})
    await db.finance_contributions.update_one({"contribution_id": replacement["contribution_id"]}, {"$set": {"corrects_contribution_id": contribution_id, "accounting_date": payload.correction_date.isoformat()}})
    if original.get("deposit_id"):
        await db.finance_deposits.update_one({"deposit_id": original["deposit_id"]}, {"$set": {"status": "adjustment_required", "updated_at": now}})
    correction_id = str(uuid4())
    correction = {"_id": correction_id, "correction_id": correction_id, "original_contribution_id": contribution_id, "replacement_contribution_id": replacement["contribution_id"], "reversal_journal_entry_id": reversal.get("entry_id") if reversal else None, "reason": payload.reason, "before": serialize(original), "after": replacement, "created_by_user_id": current_user["user_id"], "created_at": now}
    await db.finance_contribution_corrections.insert_one(correction)
    await audit(current_user["user_id"], "contribution_corrected", "contribution", contribution_id, {"correction_id": correction_id, "replacement_contribution_id": replacement["contribution_id"], "reason": payload.reason})
    return serialize(correction)


def next_due(current: date, frequency: str) -> date:
    if frequency == "weekly":
        return current + timedelta(days=7)
    if frequency == "yearly":
        year = current.year + 1
        return current.replace(year=year, day=min(current.day, calendar.monthrange(year, current.month)[1]))
    months = 3 if frequency == "quarterly" else 1
    month_index = current.month - 1 + months
    year = current.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(current.day, calendar.monthrange(year, month)[1]))


@router.get("/recurring-obligations", response_model=dict)
async def recurring_obligations(current_user: dict = Depends(reader)):
    return {"items": serialize(await db.finance_recurring_obligations.find({}, {"_id": 0}).sort("next_due_date", 1).to_list(2000))}


@router.post("/recurring-obligations", response_model=dict, status_code=201)
async def recurring_obligation_create(payload: RecurringObligationInput, current_user: dict = Depends(manager)):
    obligation_id = str(uuid4()); now = now_utc()
    doc = {"_id": obligation_id, "obligation_id": obligation_id, **payload.model_dump(mode="json"), "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.finance_recurring_obligations.insert_one(doc)
    await audit(current_user["user_id"], "recurring_obligation_created", "recurring_obligation", obligation_id, {"frequency": payload.frequency, "amount_cents": payload.amount_cents})
    return serialize(doc)


@router.post("/recurring-obligations/generate", response_model=dict)
async def recurring_obligations_generate(through_date: date = Query(default_factory=date.today), current_user: dict = Depends(manager)):
    obligations = await db.finance_recurring_obligations.find({"active": True, "next_due_date": {"$lte": through_date.isoformat()}}, {"_id": 0}).to_list(2000)
    generated = []
    for obligation in obligations:
        due = date.fromisoformat(obligation["next_due_date"])
        while due <= through_date:
            existing = await db.finance_recurring_runs.find_one({"obligation_id": obligation["obligation_id"], "due_date": due.isoformat()}, {"_id": 0})
            if not existing:
                expense_payload = ExpenseCreate(
                    vendor_id=obligation.get("vendor_id"),
                    expense_date=due,
                    due_date=due,
                    description=obligation["description"],
                    total_cents=obligation["amount_cents"],
                    allocations=[{"account_id": obligation["account_id"], "fund_id": obligation["fund_id"], "debit_cents": obligation["amount_cents"], "credit_cents": 0, "description": obligation["description"]}],
                    category=obligation.get("category"),
                    cost_center=obligation.get("cost_center"),
                    expense_nature=obligation.get("expense_nature", "fixed"),
                    beneficiary_type=obligation.get("beneficiary_type", "vendor"),
                    compensation_classification=obligation.get("compensation_classification"),
                    ministry_id=obligation.get("ministry_id"),
                    recurring_obligation_id=obligation["obligation_id"],
                )
                expense = await expense_create(expense_payload, current_user)
                run_id = str(uuid4())
                await db.finance_recurring_runs.insert_one({"_id": run_id, "run_id": run_id, "obligation_id": obligation["obligation_id"], "due_date": due.isoformat(), "expense_id": expense["expense_id"], "created_at": now_utc()})
                generated.append(expense["expense_id"])
            due = next_due(due, obligation["frequency"])
        await db.finance_recurring_obligations.update_one({"obligation_id": obligation["obligation_id"]}, {"$set": {"next_due_date": due.isoformat(), "updated_at": now_utc()}})
    await audit(current_user["user_id"], "recurring_obligations_generated", "recurring_run", through_date.isoformat(), {"expense_ids": generated})
    return {"generated": len(generated), "expense_ids": generated}


async def ensure_finance_entity(entity_type: str, entity_id: str) -> None:
    mapping = {"expense": (db.finance_expenses, "expense_id"), "payment": (db.finance_payments, "payment_id"), "deposit": (db.finance_deposits, "deposit_id")}
    if entity_type not in mapping:
        raise HTTPException(status_code=422, detail="Tipo de entidad financiera no válido")
    collection, key = mapping[entity_type]
    if not await collection.find_one({key: entity_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Registro financiero no encontrado")


def public_document(doc: dict) -> dict:
    metadata = serialize(doc.get("metadata") or {})
    return {"document_id": str(doc["_id"]), "filename": doc.get("filename"), "length": doc.get("length", 0), "upload_date": serialize(doc.get("uploadDate")), "metadata": metadata}


@router.post("/documents", response_model=dict, status_code=201)
async def finance_document_upload(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    entity_id: str = Form(...),
    current_user: dict = Depends(manager),
):
    await ensure_finance_entity(entity_type, entity_id)
    filename = file.filename or ""
    if not re.fullmatch(r"[A-Za-z0-9áéíóúÁÉÍÓÚñÑ _.-]{1,160}", filename) or ".." in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido")
    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=415, detail="Solo se permiten PDF, JPEG o PNG")
    stream = document_bucket().open_upload_stream(filename, metadata={"kind": "financial_document", "entity_type": entity_type, "entity_id": entity_id, "content_type": file.content_type, "uploaded_by_user_id": current_user["user_id"], "uploaded_at": now_utc()})
    digest = hashlib.sha256(); size = 0
    try:
        chunk = await file.read(8192)
        if detect_document_type(chunk) != file.content_type:
            raise HTTPException(status_code=415, detail="El contenido no coincide con el tipo de archivo")
        while chunk:
            size += len(chunk)
            if size > MAX_DOCUMENT_BYTES:
                raise HTTPException(status_code=413, detail="El comprobante excede el límite permitido")
            digest.update(chunk)
            await stream.write(chunk)
            chunk = await file.read(1024 * 1024)
        await stream.close()
    except Exception:
        await stream.abort()
        raise
    document_id = stream._id
    await db["finance_documents.files"].update_one({"_id": document_id}, {"$set": {"metadata.sha256": digest.hexdigest(), "metadata.bytes": size}})
    doc = await db["finance_documents.files"].find_one({"_id": document_id})
    await audit(current_user["user_id"], "financial_document_uploaded", entity_type, entity_id, {"document_id": str(document_id), "filename": filename, "sha256": digest.hexdigest()})
    return public_document(doc)


@router.get("/documents", response_model=dict)
async def finance_documents(entity_type: str, entity_id: str, current_user: dict = Depends(reader)):
    await ensure_finance_entity(entity_type, entity_id)
    docs = await db["finance_documents.files"].find({"metadata.kind": "financial_document", "metadata.entity_type": entity_type, "metadata.entity_id": entity_id}).sort("uploadDate", -1).to_list(500)
    return {"items": [public_document(doc) for doc in docs]}


@router.get("/documents/{document_id}")
async def finance_document_download(document_id: str, current_user: dict = Depends(reader)):
    if not ObjectId.is_valid(document_id):
        raise HTTPException(status_code=400, detail="Identificador de documento no válido")
    oid = ObjectId(document_id)
    doc = await db["finance_documents.files"].find_one({"_id": oid, "metadata.kind": "financial_document"})
    if not doc:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    source = await document_bucket().open_download_stream(oid)
    metadata = doc.get("metadata") or {}
    return StreamingResponse(source, media_type=metadata.get("content_type", "application/octet-stream"), headers={"Content-Disposition": f'attachment; filename="{doc.get("filename", "comprobante")}"', "X-Content-SHA256": metadata.get("sha256", "")})


@router.get("/funds/{fund_id}/activity", response_model=dict)
async def fund_activity(fund_id: str, current_user: dict = Depends(reader)):
    fund = await db.finance_funds.find_one({"fund_id": fund_id}, {"_id": 0})
    if not fund:
        raise HTTPException(status_code=404, detail="Fondo no encontrado")
    contributions = await db.finance_contributions.find({"allocations.fund_id": fund_id, "status": {"$ne": "corrected"}}, {"_id": 0}).sort("received_date", -1).to_list(5000)
    received = sum(allocation.get("amount_cents", 0) for item in contributions for allocation in item.get("allocations", []) if allocation.get("fund_id") == fund_id)
    account_types = {item["account_id"]: item["account_type"] for item in await db.finance_accounts.find({}, {"_id": 0, "account_id": 1, "account_type": 1}).to_list(2000)}
    journals = await db.finance_journal_entries.find({"status": "posted", "lines.fund_id": fund_id}, {"_id": 0}).sort("entry_date", -1).to_list(5000)
    spent = sum(line.get("debit_cents", 0) - line.get("credit_cents", 0) for entry in journals for line in entry.get("lines", []) if line.get("fund_id") == fund_id and account_types.get(line.get("account_id")) == "expense")
    budgets = await db.finance_budgets.find({"fund_id": fund_id}, {"_id": 0}).to_list(5000)
    return {"fund": serialize(fund), "received_cents": received, "spent_cents": spent, "available_cents": received - spent, "budget_cents": sum(item.get("amount_cents", 0) for item in budgets), "contributions": serialize(contributions), "journals": serialize(journals), "budgets": serialize(budgets)}


@router.get("/campaigns/{campaign_id}/activity", response_model=dict)
async def campaign_activity(campaign_id: str, current_user: dict = Depends(reader)):
    campaign = await db.finance_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Proyecto o campaña no encontrado")
    contributions = await db.finance_contributions.find({"allocations.campaign_id": campaign_id, "status": {"$ne": "corrected"}}, {"_id": 0}).sort("received_date", -1).to_list(5000)
    received = sum(allocation.get("amount_cents", 0) for item in contributions for allocation in item.get("allocations", []) if allocation.get("campaign_id") == campaign_id)
    account_types = {item["account_id"]: item["account_type"] for item in await db.finance_accounts.find({}, {"_id": 0, "account_id": 1, "account_type": 1}).to_list(2000)}
    journals = await db.finance_journal_entries.find({"status": "posted", "lines.campaign_id": campaign_id}, {"_id": 0}).sort("entry_date", -1).to_list(5000)
    spent = sum(line.get("debit_cents", 0) - line.get("credit_cents", 0) for entry in journals for line in entry.get("lines", []) if line.get("campaign_id") == campaign_id and account_types.get(line.get("account_id")) == "expense")
    budgets = await db.finance_budgets.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(5000)
    budget_total = campaign.get("budget_cents", 0) + sum(item.get("amount_cents", 0) for item in budgets)
    return {"campaign": serialize(campaign), "received_cents": received, "spent_cents": spent, "available_cents": received - spent, "budget_cents": budget_total, "contributions": serialize(contributions), "journals": serialize(journals)}