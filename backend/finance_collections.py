"""Nuevo flujo de Finanzas · P2: registro y cuadre de la colecta (decisión del dueño).

La encargada de Finanzas abre una colecta (fecha y servicio) y registra cada aporte: persona o
ANÓNIMO, concepto, fondo, monto, medio (efectivo, Zelle u otro) y la referencia del sobre o de la
transacción. El sistema separa efectivo, Zelle y total general:

- el efectivo contado se compara con el detalle y con los sobres;
- cada Zelle debe coincidir con UNA transacción recibida (escrita a mano o del CSV del banco), y
  cada transacción solo puede coincidir con un aporte;
- toda diferencia se muestra y queda documentada antes de enviar a validación.

Nada se borra: un aporte se anula con motivo y cada cambio guarda el valor anterior. Los asientos
contables se crean en los pasos siguientes (validación y depósito). La pastora solo consulta.
"""
import csv
import hashlib
import io
import re
from datetime import date, datetime
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from access_control import FINANCE_COLLECTION_RECORD, FINANCE_TREASURY
from finance_engine import audit, can_see_donors, has_finance_role, log_donor_view, now_utc, require_finance_read, require_finance_role, serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/finance/collections", tags=["finance-collections"])
zelle_router = APIRouter(prefix="/api/finance/zelle", tags=["finance-zelle"])

METHODS = ("cash", "zelle", "other")
OPEN_STATUSES = ("registering",)  # solo mientras se registra se edita libremente
DIFFERENCE_KINDS = ("cash", "envelopes", "zelle")


async def with_name(current_user: dict) -> dict:
    """Cada etapa guarda el NOMBRE de quien actúa (no solo su id)."""
    if not current_user.get("nombre"):
        doc = await db.users.find_one({"_id": ObjectId(current_user["user_id"])}, {"nombre": 1, "person_id": 1}) if ObjectId.is_valid(current_user.get("user_id", "")) else None
        current_user["nombre"] = (await person_label((doc or {}).get("person_id"))) or (doc or {}).get("nombre") or "Usuario"
    return current_user


async def reader(current_user: dict = Depends(get_current_user)) -> dict:
    require_finance_read(current_user)
    return await with_name(current_user)


async def recorder(current_user: dict = Depends(get_current_user)) -> dict:
    require_finance_role(current_user, FINANCE_COLLECTION_RECORD)
    return await with_name(current_user)


async def zelle_loader(current_user: dict = Depends(get_current_user)) -> dict:
    """Las transacciones Zelle recibidas las carga Finanzas o Tesorería."""
    if not (has_finance_role(current_user, FINANCE_COLLECTION_RECORD) or has_finance_role(current_user, FINANCE_TREASURY)):
        require_finance_role(current_user, FINANCE_TREASURY)
    return await with_name(current_user)


async def ensure_indexes() -> None:
    await db.finance_collections.create_index("collection_id", unique=True)
    await db.finance_collection_items.create_index("item_id", unique=True)
    await db.finance_collection_items.create_index([("collection_id", 1), ("status", 1)])
    await db.finance_zelle_received.create_index("tx_id", unique=True)
    await db.finance_zelle_received.create_index("dedupe_key", unique=True)
    # Una transacción Zelle solo puede coincidir con un aporte.
    await db.finance_zelle_received.create_index("matched_item_id", unique=True, partialFilterExpression={"matched_item_id": {"$type": "string"}})
    # Un donativo (o pago de otro módulo) solo puede estar una vez activo en una colecta.
    await db.finance_collection_items.create_index("origin_key", unique=True, partialFilterExpression={"origin_key": {"$type": "string"}, "status": "active"})
    if not await db.finance_accounts.find_one({"code": "1090"}):
        await db.finance_accounts.update_one({"code": "1090"}, {"$setOnInsert": {"_id": str(uuid4()), "account_id": str(uuid4()), "code": "1090", "name": "Diferencias de efectivo por aclarar",
                                                                                "account_type": "asset", "active": True, "created_at": now_utc()}}, upsert=True)
    if not await db.finance_contribution_types.find_one({"type_key": "special_offering"}):
        account = await db.finance_accounts.find_one({"code": "4010"}, {"_id": 0, "account_id": 1})
        if account:
            await db.finance_contribution_types.update_one({"type_key": "special_offering"}, {"$setOnInsert": {
                "_id": "special_offering", "type_key": "special_offering", "name": "Ofrenda especial", "revenue_account_id": account["account_id"],
                "annual_statement_eligible": True, "active": True, "created_at": now_utc()}}, upsert=True)


async def load_collection(collection_id: str) -> dict:
    doc = await db.finance_collections.find_one({"collection_id": collection_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Colecta no encontrada")
    return doc


def require_open(collection: dict) -> None:
    if collection.get("status") not in OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="La colecta ya se envió a validación; para cambiarla use una corrección (queda historial)")


async def person_label(person_id: Optional[str]) -> Optional[str]:
    if not person_id or not ObjectId.is_valid(person_id):
        return None
    doc = await db.persons.find_one({"_id": ObjectId(person_id)}, {"nombre": 1, "apellido": 1})
    return " ".join(filter(None, [(doc or {}).get("nombre"), (doc or {}).get("apellido")])) or None


async def summary(collection: dict) -> dict:
    """Cuadre: efectivo (detalle vs. contado), sobres, Zelle (coincidencias) y total general."""
    items = await db.finance_collection_items.find({"collection_id": collection["collection_id"], "status": "active"}, {"_id": 0}).to_list(5000)
    by_method = {method: sum(item["amount_cents"] for item in items if item["method"] == method) for method in METHODS}
    cash_items = [item for item in items if item["method"] == "cash"]
    zelle_items = [item for item in items if item["method"] == "zelle"]
    count = collection.get("cash_count") or {}
    counted = count.get("counted_cash_cents")
    envelopes_registered = len({item.get("reference") or item["item_id"] for item in cash_items})
    envelopes_counted = count.get("envelope_count")
    unmatched = [item["item_id"] for item in zelle_items if not item.get("zelle_tx_id")]
    differences = []
    if counted is not None and counted != by_method["cash"]:
        differences.append({"kind": "cash", "label": "Efectivo contado distinto al detalle", "expected_cents": by_method["cash"], "actual_cents": counted, "difference_cents": counted - by_method["cash"]})
    if envelopes_counted is not None and envelopes_counted != envelopes_registered:
        differences.append({"kind": "envelopes", "label": "Sobres contados distintos a los registrados", "expected": envelopes_registered, "actual": envelopes_counted, "difference": envelopes_counted - envelopes_registered})
    if unmatched:
        differences.append({"kind": "zelle", "label": "Zelle sin transacción recibida que coincida", "items": len(unmatched), "amount_cents": sum(item["amount_cents"] for item in zelle_items if item["item_id"] in unmatched)})
    explanations = {item["kind"]: item for item in collection.get("explanations") or []}
    for item in differences:
        item["explanation"] = explanations.get(item["kind"])
    return {"cash_detail_cents": by_method["cash"], "cash_counted_cents": counted, "zelle_cents": by_method["zelle"], "other_cents": by_method["other"],
            "total_cents": sum(by_method.values()), "items": len(items), "envelopes_registered": envelopes_registered, "envelopes_counted": envelopes_counted,
            "zelle_unmatched": len(unmatched), "differences": differences, "pending_explanations": [item["kind"] for item in differences if not item["explanation"]],
            "cash_counted": counted is not None}


async def view(collection: dict, current_user: dict, with_items: bool = True) -> dict:
    """La colecta con su cuadre. Quién dio: solo la pastora, quien ella autorice y quienes trabajan la colecta
    (registrar/verificar/Tesorería necesitan el detalle para cuadrar sobres); cada vista con nombres queda registrada."""
    out = {**collection, "summary": await summary(collection)}
    if collection.get("reception"):  # P5: saldo pendiente de depositar frente al efectivo recibido
        out["deposit_pending_cents"], _ = deposit_balance(collection, await cash_by_fund(collection))
    if with_items:
        items = await db.finance_collection_items.find({"collection_id": collection["collection_id"]}, {"_id": 0}).sort("created_at", 1).to_list(5000)
        sees_names = can_see_donors(current_user) or any(has_finance_role(current_user, cap) for cap in (FINANCE_COLLECTION_RECORD, "finance.collection.verify", FINANCE_TREASURY))
        for item in items:
            if sees_names:
                item["person_name"] = "Anónimo" if item.get("anonymous") else await person_label(item.get("person_id"))
            else:
                item.pop("person_id", None)
                item["person_name"] = "Anónimo" if item.get("anonymous") else "Donante reservado"
        if sees_names and any(item.get("person_id") for item in items):
            await log_donor_view(current_user, "collection_detail", detail={"collection_id": collection["collection_id"]})
        out["items"] = items
    return serialize(out)


async def touch(collection_id: str, current_user: dict, action: str, detail: Optional[dict] = None) -> None:
    now = now_utc()
    await db.finance_collections.update_one({"collection_id": collection_id}, {"$set": {"updated_at": now},
                                                                              "$push": {"history": {"action": action, "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now, **(detail or {})}}})
    await audit(current_user["user_id"], f"collection_{action}", "collection", collection_id, detail or {})


# ------------------------------------------------------------------ colectas
class CollectionCreate(BaseModel):
    service_date: date
    service_name: str = Field(min_length=2, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=500)
    is_test: bool = False


@router.post("", response_model=dict, status_code=201)
async def open_collection(payload: CollectionCreate, current_user: dict = Depends(recorder)):
    collection_id = str(uuid4())
    now = now_utc()
    doc = {"_id": collection_id, "collection_id": collection_id, "service_date": payload.service_date.isoformat(), "service_name": payload.service_name.strip(),
           "notes": payload.notes, "is_test": payload.is_test, "status": "registering", "cash_count": None, "explanations": [],
           "opened_by_user_id": current_user["user_id"], "opened_by_name": current_user.get("nombre"), "opened_at": now,
           "timeline": [{"stage": "opened", "label": "Abierta", "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now}],
           "history": [], "created_at": now, "updated_at": now}
    await db.finance_collections.insert_one(doc)
    await audit(current_user["user_id"], "collection_opened", "collection", collection_id, {"service_date": doc["service_date"], "is_test": payload.is_test})
    return await view(await load_collection(collection_id), current_user)


@router.get("", response_model=dict)
async def list_collections(include_test: bool = False, current_user: dict = Depends(reader)):
    query = {} if include_test else {"is_test": {"$ne": True}}
    items = []
    for doc in await db.finance_collections.find(query, {"_id": 0, "history": 0}).sort([("service_date", -1), ("created_at", -1)]).to_list(500):
        items.append({**serialize(doc), "summary": await summary(doc)})
    return {"items": items}


@router.get("/{collection_id}", response_model=dict)
async def get_collection(collection_id: str, current_user: dict = Depends(reader)):
    return await view(await load_collection(collection_id), current_user)


# ------------------------------------------------------------------ aportes
class ItemInput(BaseModel):
    person_id: Optional[str] = None
    anonymous: bool = False
    contribution_type: str = Field(min_length=2, max_length=80)
    fund_id: str
    amount_cents: int = Field(gt=0, le=100_000_000)
    method: Literal["cash", "zelle", "other"]
    reference: Optional[str] = Field(default=None, max_length=120)  # número de sobre o de transacción
    note: Optional[str] = Field(default=None, max_length=500)


async def validate_item(payload: ItemInput) -> None:
    if not payload.anonymous and not payload.person_id:
        raise HTTPException(status_code=422, detail="Elija la persona o marque ANÓNIMO")
    if payload.person_id and (not ObjectId.is_valid(payload.person_id) or not await db.persons.find_one({"_id": ObjectId(payload.person_id)}, {"_id": 1})):
        raise HTTPException(status_code=404, detail="Persona 360 no encontrada")
    if not await db.finance_contribution_types.find_one({"type_key": payload.contribution_type, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=422, detail="Concepto no válido")
    if not await db.finance_funds.find_one({"fund_id": payload.fund_id, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=422, detail="Fondo no válido")


def item_fields(payload: ItemInput) -> dict:
    return {"person_id": None if payload.anonymous else payload.person_id, "anonymous": payload.anonymous, "contribution_type": payload.contribution_type,
            "fund_id": payload.fund_id, "amount_cents": payload.amount_cents, "method": payload.method,
            "reference": (payload.reference or "").strip() or None, "note": payload.note}


@router.post("/{collection_id}/items", response_model=dict, status_code=201)
async def add_item(collection_id: str, payload: ItemInput, current_user: dict = Depends(recorder)):
    collection = await load_collection(collection_id)
    require_open(collection)
    await validate_item(payload)
    item_id = str(uuid4())
    now = now_utc()
    await db.finance_collection_items.insert_one({"_id": item_id, "item_id": item_id, "collection_id": collection_id, **item_fields(payload), "zelle_tx_id": None,
                                                  "status": "active", "is_test": bool(collection.get("is_test")), "created_by_user_id": current_user["user_id"], "created_at": now,
                                                  "updated_at": now, "history": []})
    await touch(collection_id, current_user, "item_added", {"item_id": item_id, "amount_cents": payload.amount_cents, "method": payload.method})
    return await view(await load_collection(collection_id), current_user)


async def load_item(collection_id: str, item_id: str) -> dict:
    item = await db.finance_collection_items.find_one({"collection_id": collection_id, "item_id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Aporte no encontrado")
    return item


@router.put("/{collection_id}/items/{item_id}", response_model=dict)
async def update_item(collection_id: str, item_id: str, payload: ItemInput, current_user: dict = Depends(recorder)):
    collection = await load_collection(collection_id)
    require_open(collection)
    item = await load_item(collection_id, item_id)
    if item["status"] != "active":
        raise HTTPException(status_code=409, detail="El aporte está anulado")
    await validate_item(payload)
    new = item_fields(payload)
    before = {key: item.get(key) for key in new}
    unset_zelle = item.get("zelle_tx_id") and (new["method"] != "zelle" or new["amount_cents"] != item["amount_cents"])
    now = now_utc()
    await db.finance_collection_items.update_one({"item_id": item_id}, {"$set": {**new, **({"zelle_tx_id": None} if unset_zelle else {}), "updated_at": now},
                                                                        "$push": {"history": {"before": before, "by_user_id": current_user["user_id"], "at": now}}})
    if unset_zelle:  # el monto o el medio cambió: la coincidencia con el Zelle ya no vale
        await db.finance_zelle_received.update_one({"tx_id": item["zelle_tx_id"], "matched_item_id": item_id}, {"$set": {"matched_item_id": None, "matched_at": None}})
    await touch(collection_id, current_user, "item_updated", {"item_id": item_id, "before": before})
    return await view(await load_collection(collection_id), current_user)


class VoidInput(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/{collection_id}/items/{item_id}/void", response_model=dict)
async def void_item(collection_id: str, item_id: str, payload: VoidInput, current_user: dict = Depends(recorder)):
    """Quitar un aporte = anularlo con motivo (nunca se borra)."""
    collection = await load_collection(collection_id)
    require_open(collection)
    item = await load_item(collection_id, item_id)
    if item["status"] != "active":
        return await view(collection, current_user)
    now = now_utc()
    await db.finance_collection_items.update_one({"item_id": item_id}, {"$set": {"status": "voided", "void_reason": payload.reason, "voided_by_user_id": current_user["user_id"], "voided_at": now, "zelle_tx_id": None, "updated_at": now}})
    if item.get("zelle_tx_id"):
        await db.finance_zelle_received.update_one({"tx_id": item["zelle_tx_id"], "matched_item_id": item_id}, {"$set": {"matched_item_id": None, "matched_at": None}})
    await touch(collection_id, current_user, "item_voided", {"item_id": item_id, "reason": payload.reason})
    return await view(await load_collection(collection_id), current_user)


# ------------------------------------------------------------------ conteo, diferencias y envío
class CashCountInput(BaseModel):
    counted_cash_cents: int = Field(ge=0, le=1_000_000_000)
    envelope_count: Optional[int] = Field(default=None, ge=0, le=5000)
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/{collection_id}/cash-count", response_model=dict)
async def cash_count(collection_id: str, payload: CashCountInput, current_user: dict = Depends(recorder)):
    collection = await load_collection(collection_id)
    require_open(collection)
    count = {**payload.model_dump(), "counted_by_user_id": current_user["user_id"], "counted_by_name": current_user.get("nombre"), "counted_at": now_utc()}
    await db.finance_collections.update_one({"collection_id": collection_id}, {"$set": {"cash_count": count}})
    await touch(collection_id, current_user, "cash_counted", {"before": collection.get("cash_count"), "counted_cash_cents": payload.counted_cash_cents, "envelope_count": payload.envelope_count})
    return await view(await load_collection(collection_id), current_user)


class ExplanationInput(BaseModel):
    kind: Literal["cash", "envelopes", "zelle"]
    note: str = Field(min_length=5, max_length=1000)


@router.post("/{collection_id}/explanations", response_model=dict)
async def explain(collection_id: str, payload: ExplanationInput, current_user: dict = Depends(recorder)):
    """Toda diferencia queda documentada (quién, cuándo, por qué)."""
    collection = await load_collection(collection_id)
    if collection.get("status") not in ("registering", "registered"):  # también tras una corrección, antes de validar
        require_open(collection)
    entry = {"kind": payload.kind, "note": payload.note.strip(), "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now_utc()}
    explanations = [item for item in collection.get("explanations") or [] if item["kind"] != payload.kind] + [entry]
    await db.finance_collections.update_one({"collection_id": collection_id}, {"$set": {"explanations": explanations}})
    await touch(collection_id, current_user, "difference_explained", {"kind": payload.kind, "note": entry["note"]})
    return await view(await load_collection(collection_id), current_user)


@router.post("/{collection_id}/submit", response_model=dict)
async def submit(collection_id: str, current_user: dict = Depends(recorder)):
    """Registrada: lista para que una SEGUNDA persona valide el cuadre."""
    collection = await load_collection(collection_id)
    require_open(collection)
    current = await summary(collection)
    if not current["items"]:
        raise HTTPException(status_code=409, detail="Registre al menos un aporte")
    if current["cash_detail_cents"] and not current["cash_counted"]:
        raise HTTPException(status_code=409, detail="Registre el efectivo contado y los sobres antes de enviar")
    if current["pending_explanations"]:
        raise HTTPException(status_code=409, detail="Hay diferencias sin explicar: " + ", ".join(current["pending_explanations"]))
    now = now_utc()
    stage = {"stage": "registered", "label": "Registrada", "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now}
    await db.finance_collections.update_one({"collection_id": collection_id, "status": "registering"},
                                            {"$set": {"status": "registered", "registered_by_user_id": current_user["user_id"], "registered_at": now, "submitted_summary": current},
                                             "$push": {"timeline": stage}})
    await touch(collection_id, current_user, "submitted", {"total_cents": current["total_cents"], "cash_cents": current["cash_detail_cents"], "zelle_cents": current["zelle_cents"]})
    return await view(await load_collection(collection_id), current_user)


# ------------------------------------------------------------------ Zelle recibidos
class ZelleInput(BaseModel):
    received_date: date
    amount_cents: int = Field(gt=0, le=100_000_000)
    sender_name: str = Field(min_length=2, max_length=160)
    confirmation: Optional[str] = Field(default=None, max_length=120)
    memo: Optional[str] = Field(default=None, max_length=300)
    is_test: bool = False


def dedupe_key(received: str, amount_cents: int, sender: str, confirmation: Optional[str]) -> str:
    """La misma transacción nunca entra dos veces (por confirmación del banco; si no hay, fecha+monto+nombre)."""
    sender_key = re.sub(r"\s+", " ", sender.strip().lower())
    base = f"conf:{confirmation.strip().upper()}" if confirmation and confirmation.strip() else f"{received}|{amount_cents}|{sender_key}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


async def insert_zelle(fields: dict, source: str, current_user: dict) -> Optional[dict]:
    key = dedupe_key(fields["received_date"], fields["amount_cents"], fields["sender_name"], fields.get("confirmation"))
    if await db.finance_zelle_received.find_one({"dedupe_key": key}, {"_id": 1}):
        return None
    tx_id = str(uuid4())
    doc = {"_id": tx_id, "tx_id": tx_id, **fields, "dedupe_key": key, "source": source, "matched_item_id": None, "matched_at": None,
           "loaded_by_user_id": current_user["user_id"], "loaded_at": now_utc()}
    try:
        await db.finance_zelle_received.insert_one(doc)
    except Exception:  # noqa: BLE001 — carrera con otra carga igual: ya existe
        return None
    return doc


@zelle_router.post("", response_model=dict, status_code=201)
async def zelle_manual(payload: ZelleInput, current_user: dict = Depends(zelle_loader)):
    doc = await insert_zelle({**payload.model_dump(mode="json"), "sender_name": payload.sender_name.strip()}, "manual", current_user)
    if not doc:
        raise HTTPException(status_code=409, detail="Esa transacción Zelle ya está registrada")
    await audit(current_user["user_id"], "zelle_loaded", "zelle", doc["tx_id"], {"amount_cents": payload.amount_cents, "source": "manual"})
    return serialize(doc)


def _cents(value: str) -> int:
    clean = re.sub(r"[^0-9.\-]", "", value or "")
    if not clean:
        raise ValueError("monto vacío")
    return int(round(abs(float(clean)) * 100))


def _date(value: str) -> str:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"fecha no reconocida: {value}")


def _pick(row: dict, *names: str) -> str:
    lowered = {key.strip().lower(): value for key, value in row.items() if key}
    for name in names:
        if lowered.get(name):
            return lowered[name]
    return ""


@zelle_router.post("/import-csv", response_model=dict)
async def zelle_import(file: UploadFile = File(...), is_test: bool = False, current_user: dict = Depends(zelle_loader)):
    """CSV del banco (montos en DÓLARES). Columnas reconocidas: fecha/date/posting date, monto/amount,
    nombre/name/description/sender, confirmación/confirmation/reference. Solo entran créditos (montos > 0)
    y las transacciones repetidas se ignoran."""
    content = await file.read()
    if len(content) > 2_000_000:
        raise HTTPException(status_code=413, detail="El archivo es demasiado grande")
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="CSV no válido")
    loaded, repeated, rejected = 0, 0, []
    for index, row in enumerate(rows, start=2):
        try:
            raw_amount = _pick(row, "monto", "amount", "credit", "importe")
            if raw_amount.strip().startswith("-"):
                continue  # salidas de dinero: no son Zelle recibidos
            fields = {"received_date": _date(_pick(row, "fecha", "date", "posting date", "transaction date")), "amount_cents": _cents(raw_amount),
                      "sender_name": (_pick(row, "nombre", "name", "sender", "description", "descripción") or "Sin nombre").strip()[:160],
                      "confirmation": (_pick(row, "confirmación", "confirmacion", "confirmation", "reference", "referencia") or None), "memo": None, "is_test": is_test}
            if fields["amount_cents"] <= 0:
                continue
            if await insert_zelle(fields, "csv", current_user):
                loaded += 1
            else:
                repeated += 1
        except ValueError as error:
            rejected.append({"row": index, "reason": str(error)[:200]})
    await audit(current_user["user_id"], "zelle_csv_imported", "zelle", file.filename or "csv", {"loaded": loaded, "repeated": repeated, "rejected": len(rejected)})
    return {"loaded": loaded, "repeated": repeated, "rejected": rejected, "total": len(rows)}


@zelle_router.get("", response_model=dict)
async def zelle_list(unmatched: bool = False, include_test: bool = False, current_user: dict = Depends(reader)):
    query: dict = {} if include_test else {"is_test": {"$ne": True}}
    if unmatched:
        query["matched_item_id"] = None
    items = await db.finance_zelle_received.find(query, {"_id": 0, "dedupe_key": 0}).sort("received_date", -1).to_list(2000)
    if not can_see_donors(current_user) and not has_finance_role(current_user, FINANCE_COLLECTION_RECORD) and not has_finance_role(current_user, FINANCE_TREASURY):
        for item in items:
            item["sender_name"] = "Reservado"
    return {"items": serialize(items)}


class MatchInput(BaseModel):
    tx_id: str


@router.post("/{collection_id}/items/{item_id}/match-zelle", response_model=dict)
async def match_zelle(collection_id: str, item_id: str, payload: MatchInput, current_user: dict = Depends(recorder)):
    """Une un aporte Zelle con UNA transacción recibida (cada transacción solo con un aporte)."""
    collection = await load_collection(collection_id)
    require_open(collection)
    item = await load_item(collection_id, item_id)
    if item["status"] != "active" or item["method"] != "zelle":
        raise HTTPException(status_code=409, detail="Solo un aporte Zelle activo se puede unir a una transacción")
    tx = await db.finance_zelle_received.find_one({"tx_id": payload.tx_id}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transacción Zelle no encontrada")
    if tx["amount_cents"] != item["amount_cents"]:
        raise HTTPException(status_code=422, detail="El monto del aporte no coincide con la transacción Zelle")
    if bool(tx.get("is_test")) != bool(collection.get("is_test")):
        raise HTTPException(status_code=422, detail="No se mezclan datos de prueba con datos reales")
    if item.get("zelle_tx_id") == payload.tx_id:
        return await view(collection, current_user)
    try:
        claimed = await db.finance_zelle_received.find_one_and_update({"tx_id": payload.tx_id, "matched_item_id": None}, {"$set": {"matched_item_id": item_id, "matched_at": now_utc(), "matched_by_user_id": current_user["user_id"]}})
    except Exception:  # noqa: BLE001 — índice único: otra persona la tomó
        claimed = None
    if not claimed:
        raise HTTPException(status_code=409, detail="Esa transacción Zelle ya coincide con otro aporte")
    if item.get("zelle_tx_id"):
        await db.finance_zelle_received.update_one({"tx_id": item["zelle_tx_id"], "matched_item_id": item_id}, {"$set": {"matched_item_id": None, "matched_at": None}})
    await db.finance_collection_items.update_one({"item_id": item_id}, {"$set": {"zelle_tx_id": payload.tx_id, "updated_at": now_utc()}})
    await touch(collection_id, current_user, "zelle_matched", {"item_id": item_id, "tx_id": payload.tx_id})
    return await view(await load_collection(collection_id), current_user)


# ------------------------------------------------------------------ P3: validación por una segunda persona
VERIFY = "finance.collection.verify"
CORRECTABLE = ("registered", "validated")  # después de que Tesorería recibe, la diferencia se registra en la entrega


async def verifier(current_user: dict = Depends(get_current_user)) -> dict:
    require_finance_role(current_user, VERIFY)
    return await with_name(current_user)


async def registration_people(collection: dict) -> set:
    """Quienes registraron o cambiaron la colecta: ninguno puede validarla."""
    people = {collection.get("opened_by_user_id"), collection.get("registered_by_user_id"), (collection.get("cash_count") or {}).get("counted_by_user_id")}
    people |= {entry.get("by_user_id") for entry in collection.get("history") or [] if entry.get("action") not in ("validated", "returned")}
    async for item in db.finance_collection_items.find({"collection_id": collection["collection_id"]}, {"_id": 0, "created_by_user_id": 1, "history": 1}):
        people.add(item.get("created_by_user_id"))
        people |= {entry.get("by_user_id") for entry in item.get("history") or []}
    return {item for item in people if item}


async def post_collection(collection: dict, current_user: dict) -> dict:
    """Al validar: una contribución por aporte y UN asiento contabilizado (efectivo/otros → fondos no
    depositados; Zelle → banco). Reemplaza la aprobación de 3 personas para la colecta (decisión del dueño)."""
    from finance_engine import create_journal
    items = await db.finance_collection_items.find({"collection_id": collection["collection_id"], "status": "active"}, {"_id": 0}).to_list(5000)
    accounts = {doc["code"]: doc["account_id"] async for doc in db.finance_accounts.find({"code": {"$in": ["1010", "1020"]}}, {"_id": 0, "code": 1, "account_id": 1})}
    types = {doc["type_key"]: doc async for doc in db.finance_contribution_types.find({}, {"_id": 0})}
    lines, contributions = [], []
    for item in items:
        # Solo el efectivo pasa por «fondos no depositados» (Tesorería lo deposita); Zelle y otros medios llegan al banco.
        debit_account = accounts["1010"] if item["method"] == "cash" else accounts["1020"]
        name = types.get(item["contribution_type"], {}).get("name", item["contribution_type"])
        campaign = {"campaign_id": item["campaign_id"]} if item.get("campaign_id") else {}
        lines += [{"account_id": debit_account, "fund_id": item["fund_id"], "debit_cents": item["amount_cents"], "credit_cents": 0, "description": f"Colecta · {name}", **campaign},
                  {"account_id": types[item["contribution_type"]]["revenue_account_id"], "fund_id": item["fund_id"], "debit_cents": 0, "credit_cents": item["amount_cents"], "description": f"Colecta · {name}", **campaign}]
    journal = await create_journal(collection["registered_by_user_id"], collection["service_date"], f"Colecta {collection['service_name']} · {collection['service_date']}",
                                   "collection", collection["collection_id"], lines, "submitted")
    now = now_utc()
    await db.finance_journal_entries.update_one({"entry_id": journal["entry_id"]}, {"$set": {
        "status": "posted", "reviewed_by_user_id": current_user["user_id"], "reviewed_at": now, "posted_at": now, "posting_policy": "colecta_dos_personas",
        "is_test": bool(collection.get("is_test")), "updated_at": now}})
    for item in items:
        contribution_id = str(uuid4())
        contributions.append({"_id": contribution_id, "contribution_id": contribution_id, "person_id": item.get("person_id"), "anonymous": bool(item.get("anonymous")),
                              "contribution_type": item["contribution_type"], "amount_cents": item["amount_cents"], "received_date": collection["service_date"],
                              "accounting_date": collection["service_date"], "payment_method": {"cash": "cash", "zelle": "zelle"}.get(item["method"], "other"),
                              "reference": item.get("reference"), "allocations": [{"fund_id": item["fund_id"], "amount_cents": item["amount_cents"], "contribution_type": item["contribution_type"], **({"campaign_id": item["campaign_id"]} if item.get("campaign_id") else {})}],
                              "campaign_id": item.get("campaign_id"), "origin": item.get("origin"),
                              "source": "collection", "collection_id": collection["collection_id"], "collection_item_id": item["item_id"], "journal_entry_id": journal["entry_id"],
                              "deposit_id": None if item["method"] == "cash" else "directo_al_banco", "batch_id": None, "status": "recorded", "is_test": bool(collection.get("is_test")),
                              "created_by_user_id": item.get("created_by_user_id"), "validated_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now})
    if contributions:
        await db.finance_contributions.insert_many(contributions)
    return {"journal_entry_id": journal["entry_id"], "contributions": len(contributions)}


async def reverse_postings(collection: dict, current_user: dict, reason: str) -> None:
    """Si se corrige una colecta ya validada: asiento de reversión (contabilizado) y sus contribuciones
    quedan «corregidas». Nada se borra; al volver a validar se crean las nuevas."""
    from finance_engine import create_journal
    entry_id = collection.get("posted_journal_id")
    original = await db.finance_journal_entries.find_one({"entry_id": entry_id}, {"_id": 0}) if entry_id else None
    now = now_utc()
    if original:
        lines = [{**line, "debit_cents": line.get("credit_cents", 0), "credit_cents": line.get("debit_cents", 0), "description": f"Reversión: {line.get('description', '')}"} for line in original["lines"]]
        reversal = await create_journal(current_user["user_id"], (await _church_today()).isoformat(), f"Reversión por corrección de la colecta · {reason}", "collection_reversal", collection["collection_id"], lines, "submitted")
        await db.finance_journal_entries.update_one({"entry_id": reversal["entry_id"]}, {"$set": {"status": "posted", "posted_at": now, "posting_policy": "colecta_dos_personas",
                                                                                               "is_test": bool(collection.get("is_test")), "reverses_entry_id": entry_id, "updated_at": now}})
    await db.finance_contributions.update_many({"collection_id": collection["collection_id"], "status": "recorded"},
                                               {"$set": {"status": "corrected", "correction_reason": reason, "corrected_by_user_id": current_user["user_id"], "corrected_at": now, "updated_at": now}})


async def _church_today():
    from count_rules import church_today
    return await church_today()


@router.post("/{collection_id}/validate", response_model=dict)
async def validate(collection_id: str, current_user: dict = Depends(verifier)):
    """Segunda persona: revisó conteo y detalle y confirma el cuadre. Quedan ambos nombres, fecha y hora."""
    collection = await load_collection(collection_id)
    if collection.get("status") != "registered":
        raise HTTPException(status_code=409, detail="Solo una colecta registrada (enviada) se valida")
    if current_user["user_id"] in await registration_people(collection):
        raise HTTPException(status_code=403, detail="Quien registró o cambió esta colecta no puede validarla: debe hacerlo otra persona")
    current = await summary(collection)
    if current["pending_explanations"]:
        raise HTTPException(status_code=409, detail="Hay diferencias sin explicar")
    posting = await post_collection(collection, current_user)
    now = now_utc()
    stage = {"stage": "validated", "label": "Validada por segunda persona", "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now}
    result = await db.finance_collections.update_one({"collection_id": collection_id, "status": "registered"}, {"$set": {
        "status": "validated", "validated_by_user_id": current_user["user_id"], "validated_by_name": current_user.get("nombre"), "validated_at": now,
        "validated_summary": current, "posted_journal_id": posting["journal_entry_id"]}, "$push": {"timeline": stage}})
    if not result.modified_count:
        raise HTTPException(status_code=409, detail="La colecta cambió mientras se validaba; recargue")
    await touch(collection_id, current_user, "validated", {"total_cents": current["total_cents"], "journal_entry_id": posting["journal_entry_id"]})
    return await view(await load_collection(collection_id), current_user)


class ReturnInput(BaseModel):
    note: str = Field(min_length=5, max_length=1000)


@router.post("/{collection_id}/return", response_model=dict)
async def return_for_changes(collection_id: str, payload: ReturnInput, current_user: dict = Depends(verifier)):
    """La segunda persona no confirma: la devuelve a Finanzas con sus observaciones."""
    collection = await load_collection(collection_id)
    if collection.get("status") != "registered":
        raise HTTPException(status_code=409, detail="Solo una colecta registrada se puede devolver")
    if current_user["user_id"] in await registration_people(collection):
        raise HTTPException(status_code=403, detail="Quien registró esta colecta no puede revisarla")
    now = now_utc()
    stage = {"stage": "returned", "label": "Devuelta con observaciones", "note": payload.note, "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now}
    await db.finance_collections.update_one({"collection_id": collection_id}, {"$set": {"status": "registering", "registered_by_user_id": None}, "$push": {"timeline": stage}})
    await touch(collection_id, current_user, "returned", {"note": payload.note})
    return await view(await load_collection(collection_id), current_user)


# ------------------------------------------------------------------ P3: correcciones con historial
class CorrectionInput(BaseModel):
    action: Literal["add", "update", "void", "cash_count"]
    reason: str = Field(min_length=5, max_length=1000)
    item_id: Optional[str] = None
    item: Optional[ItemInput] = None
    cash_count: Optional[CashCountInput] = None


@router.post("/{collection_id}/corrections", response_model=dict)
async def correct(collection_id: str, payload: CorrectionInput, current_user: dict = Depends(recorder)):
    """Una colecta enviada o validada no se modifica en silencio: la corrección guarda valor anterior,
    motivo y quién la hizo, y la colecta vuelve a «Registrada» para que otra persona la valide otra vez."""
    collection = await load_collection(collection_id)
    if collection.get("status") not in CORRECTABLE:
        raise HTTPException(status_code=409, detail="Ya la recibió Tesorería: registre la diferencia en la entrega o en el depósito")
    now = now_utc()
    record = {"correction_id": str(uuid4()), "action": payload.action, "reason": payload.reason.strip(), "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"),
              "at": now, "previous_status": collection["status"], "item_id": payload.item_id}
    if payload.action == "add":
        if not payload.item:
            raise HTTPException(status_code=422, detail="Indique el aporte")
        await validate_item(payload.item)
        item_id = str(uuid4())
        await db.finance_collection_items.insert_one({"_id": item_id, "item_id": item_id, "collection_id": collection_id, **item_fields(payload.item), "zelle_tx_id": None, "status": "active",
                                                      "is_test": bool(collection.get("is_test")), "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
                                                      "history": [], "added_by_correction": record["correction_id"]})
        record.update({"item_id": item_id, "before": None, "after": item_fields(payload.item)})
    elif payload.action in ("update", "void"):
        item = await load_item(collection_id, payload.item_id or "")
        if item["status"] != "active":
            raise HTTPException(status_code=409, detail="El aporte está anulado")
        before = {key: item.get(key) for key in ("person_id", "anonymous", "contribution_type", "fund_id", "amount_cents", "method", "reference", "note", "zelle_tx_id")}
        if payload.action == "update":
            if not payload.item:
                raise HTTPException(status_code=422, detail="Indique el aporte corregido")
            await validate_item(payload.item)
            after = item_fields(payload.item)
            unset_zelle = item.get("zelle_tx_id") and (after["method"] != "zelle" or after["amount_cents"] != item["amount_cents"])
            await db.finance_collection_items.update_one({"item_id": item["item_id"]}, {"$set": {**after, **({"zelle_tx_id": None} if unset_zelle else {}), "updated_at": now},
                                                                                       "$push": {"history": {"before": before, "reason": record["reason"], "by_user_id": current_user["user_id"], "at": now}}})
        else:
            after = None
            unset_zelle = bool(item.get("zelle_tx_id"))
            await db.finance_collection_items.update_one({"item_id": item["item_id"]}, {"$set": {"status": "voided", "void_reason": record["reason"], "voided_by_user_id": current_user["user_id"],
                                                                                                 "voided_at": now, "zelle_tx_id": None, "updated_at": now}})
        if unset_zelle:
            await db.finance_zelle_received.update_one({"tx_id": item["zelle_tx_id"], "matched_item_id": item["item_id"]}, {"$set": {"matched_item_id": None, "matched_at": None}})
        record.update({"before": before, "after": after})
    else:
        if not payload.cash_count:
            raise HTTPException(status_code=422, detail="Indique el conteo corregido")
        count = {**payload.cash_count.model_dump(), "counted_by_user_id": current_user["user_id"], "counted_by_name": current_user.get("nombre"), "counted_at": now}
        await db.finance_collections.update_one({"collection_id": collection_id}, {"$set": {"cash_count": count}})
        record.update({"before": collection.get("cash_count"), "after": payload.cash_count.model_dump()})
    if collection["status"] == "validated":
        await reverse_postings(collection, current_user, record["reason"])
    stage = {"stage": "corrected", "label": "Corregida · falta validar otra vez", "note": record["reason"], "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now}
    await db.finance_collections.update_one({"collection_id": collection_id}, {
        "$set": {"status": "registered", "registered_by_user_id": current_user["user_id"], "registered_at": now, "validated_by_user_id": None, "validated_at": None, "posted_journal_id": None,
                 "handover": None},
        "$push": {"corrections": record, "timeline": stage}})
    await touch(collection_id, current_user, "corrected", {"correction_id": record["correction_id"], "action": payload.action, "reason": record["reason"]})
    return await view(await load_collection(collection_id), current_user)


# ------------------------------------------------------------------ P4: entrega del efectivo a Tesorería
async def treasurer(current_user: dict = Depends(get_current_user)) -> dict:
    require_finance_role(current_user, FINANCE_TREASURY)
    return await with_name(current_user)


class HandoverInput(BaseModel):
    delivered_cents: int = Field(ge=0, le=1_000_000_000)
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/{collection_id}/handover", response_model=dict)
async def handover(collection_id: str, payload: HandoverInput, current_user: dict = Depends(recorder)):
    """Finanzas registra cuánto efectivo entrega y quién lo entrega (el Zelle NO es parte del efectivo)."""
    collection = await load_collection(collection_id)
    if collection.get("status") != "validated":
        raise HTTPException(status_code=409, detail="Primero otra persona debe validar el cuadre")
    expected = (collection.get("validated_summary") or {}).get("cash_detail_cents") or 0
    record = {"delivered_cents": payload.delivered_cents, "expected_cash_cents": expected, "note": payload.note, "delivered_by_user_id": current_user["user_id"],
              "delivered_by_name": current_user.get("nombre"), "delivered_at": now_utc()}
    await db.finance_collections.update_one({"collection_id": collection_id}, {"$set": {"handover": record}})
    await touch(collection_id, current_user, "cash_handed_over", {"before": collection.get("handover"), "delivered_cents": payload.delivered_cents, "expected_cash_cents": expected})
    return await view(await load_collection(collection_id), current_user)


class ReceiveInput(BaseModel):
    received_cents: int = Field(ge=0, le=1_000_000_000)
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/{collection_id}/receive", response_model=dict)
async def receive(collection_id: str, payload: ReceiveInput, current_user: dict = Depends(treasurer)):
    """Tesorería cuenta y confirma desde su usuario (puede no haber estado en el conteo, pero nunca recibe lo
    que ella misma entregó). Si recibe otra cantidad registra el monto real y la diferencia queda por aclarar."""
    from finance_engine import create_journal
    collection = await load_collection(collection_id)
    delivered = collection.get("handover")
    if collection.get("status") != "validated" or not delivered:
        raise HTTPException(status_code=409, detail="Finanzas aún no registra la entrega del efectivo")
    if delivered.get("delivered_by_user_id") == current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Quien entrega el efectivo no puede confirmarlo: debe recibirlo otra persona de Tesorería")
    now = now_utc()
    difference = payload.received_cents - delivered["delivered_cents"]
    against_expected = payload.received_cents - (delivered.get("expected_cash_cents") or 0)
    reception = {"received_cents": payload.received_cents, "note": payload.note, "received_by_user_id": current_user["user_id"], "received_by_name": current_user.get("nombre"),
                 "received_at": now, "difference_cents": difference, "difference_vs_detail_cents": against_expected,
                 "difference_status": "pending" if (difference or against_expected) else "none", "journal_entry_id": None}
    if against_expected:
        # El efectivo que falta (o sobra) frente al detalle validado pasa a «Diferencias por aclarar».
        accounts = {doc["code"]: doc["account_id"] async for doc in db.finance_accounts.find({"code": {"$in": ["1010", "1090"]}}, {"_id": 0, "code": 1, "account_id": 1})}
        general = await db.finance_funds.find_one({"code": "GENERAL"}, {"_id": 0, "fund_id": 1})
        amount = abs(against_expected)
        source, target = (accounts["1010"], accounts["1090"]) if against_expected < 0 else (accounts["1090"], accounts["1010"])
        lines = [{"account_id": target, "fund_id": general["fund_id"], "debit_cents": amount, "credit_cents": 0, "description": "Diferencia de efectivo por aclarar"},
                 {"account_id": source, "fund_id": general["fund_id"], "debit_cents": 0, "credit_cents": amount, "description": "Diferencia de efectivo por aclarar"}]
        journal = await create_journal(current_user["user_id"], (await _church_today()).isoformat(), f"Diferencia al recibir el efectivo · {collection['service_name']} {collection['service_date']}",
                                       "collection_cash_difference", collection_id, lines, "submitted")
        await db.finance_journal_entries.update_one({"entry_id": journal["entry_id"]}, {"$set": {"status": "posted", "posted_at": now, "posting_policy": "colecta_dos_personas",
                                                                                               "is_test": bool(collection.get("is_test")), "updated_at": now}})
        reception["journal_entry_id"] = journal["entry_id"]
    stage = {"stage": "cash_received", "label": "Efectivo recibido por Tesorería", "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now,
             "note": f"Entregó {delivered.get('delivered_by_name')}: {delivered['delivered_cents'] / 100:.2f} · recibió {payload.received_cents / 100:.2f}"}
    result = await db.finance_collections.update_one({"collection_id": collection_id, "status": "validated"},
                                                     {"$set": {"status": "cash_received", "reception": reception}, "$push": {"timeline": stage}})
    if not result.modified_count:
        raise HTTPException(status_code=409, detail="La colecta cambió; recargue")
    await touch(collection_id, current_user, "cash_received", {"received_cents": payload.received_cents, "difference_cents": difference, "difference_vs_detail_cents": against_expected})
    return await view(await load_collection(collection_id), current_user)


class ClarifyInput(BaseModel):
    note: str = Field(min_length=5, max_length=1000)


@router.post("/{collection_id}/clarify-cash", response_model=dict)
async def clarify_cash(collection_id: str, payload: ClarifyInput, current_user: dict = Depends(get_current_user)):
    """Aclarar la diferencia de efectivo (Finanzas o Tesorería): queda quién, cuándo y por qué. El ajuste
    contable, si hace falta, se registra aparte; nada se borra."""
    if not (has_finance_role(current_user, FINANCE_COLLECTION_RECORD) or has_finance_role(current_user, FINANCE_TREASURY)):
        require_finance_role(current_user, FINANCE_TREASURY)
    await with_name(current_user)
    collection = await load_collection(collection_id)
    reception = collection.get("reception") or {}
    if reception.get("difference_status") != "pending":
        raise HTTPException(status_code=409, detail="No hay una diferencia de efectivo pendiente")
    clarification = {"note": payload.note.strip(), "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now_utc()}
    await db.finance_collections.update_one({"collection_id": collection_id}, {"$set": {"reception.difference_status": "clarified", "reception.clarification": clarification}})
    await touch(collection_id, current_user, "cash_difference_clarified", {"note": clarification["note"]})
    return await view(await load_collection(collection_id), current_user)


# ------------------------------------------------------------------ P5: depósito de Tesorería
class DepositInput(BaseModel):
    deposit_date: date
    bank_account_id: str
    amount_cents: int = Field(gt=0, le=1_000_000_000)
    reference: Optional[str] = Field(default=None, max_length=160)
    note: Optional[str] = Field(default=None, max_length=500)


async def cash_by_fund(collection: dict) -> dict:
    """Efectivo recibido por fondo (la diferencia al recibir ajusta el Fondo General)."""
    totals: dict = {}
    async for item in db.finance_collection_items.find({"collection_id": collection["collection_id"], "status": "active", "method": "cash"}, {"_id": 0, "fund_id": 1, "amount_cents": 1}):
        totals[item["fund_id"]] = totals.get(item["fund_id"], 0) + item["amount_cents"]
    difference = (collection.get("reception") or {}).get("difference_vs_detail_cents") or 0
    if difference:
        general = await db.finance_funds.find_one({"code": "GENERAL"}, {"_id": 0, "fund_id": 1})
        totals[general["fund_id"]] = totals.get(general["fund_id"], 0) + difference
    return totals


def deposit_balance(collection: dict, received_by_fund: dict) -> tuple[int, dict]:
    pending = dict(received_by_fund)
    for deposit in collection.get("deposits") or []:
        for fund_id, amount in (deposit.get("fund_totals") or {}).items():
            pending[fund_id] = pending.get(fund_id, 0) - amount
    return sum(pending.values()), pending


@router.post("/{collection_id}/deposits", response_model=dict, status_code=201)
async def register_deposit(collection_id: str, payload: DepositInput, current_user: dict = Depends(treasurer)):
    """Tesorería registra el depósito (monto, fecha, banco o cuenta y comprobante). Se compara con el efectivo
    recibido y queda el saldo pendiente. Un fondo con banco designado (p. ej. Pro-Templo) va a su cuenta."""
    from finance_engine import create_journal
    collection = await load_collection(collection_id)
    if collection.get("status") not in ("cash_received", "deposited"):
        raise HTTPException(status_code=409, detail="Primero Tesorería debe confirmar que recibió el efectivo")
    bank = await db.finance_accounts.find_one({"account_id": payload.bank_account_id, "account_type": "asset", "active": True}, {"_id": 0})
    if not bank or bank.get("code") in ("1010", "1090"):
        raise HTTPException(status_code=422, detail="Elija la cuenta de banco donde se depositó")
    received = (collection.get("reception") or {}).get("received_cents") or 0
    pending_total, pending = deposit_balance(collection, await cash_by_fund(collection))
    if payload.amount_cents > pending_total:
        raise HTTPException(status_code=422, detail=f"El depósito supera el efectivo pendiente de depositar ({pending_total / 100:.2f})")
    funds = {doc["fund_id"]: doc async for doc in db.finance_funds.find({"fund_id": {"$in": list(pending)}}, {"_id": 0})}
    eligible = [fund_id for fund_id, amount in pending.items() if amount > 0 and funds.get(fund_id, {}).get("default_bank_account_id") in (None, "", payload.bank_account_id)]
    if payload.amount_cents > sum(pending[fund_id] for fund_id in eligible):
        designated = [funds[fund_id]["name"] for fund_id, amount in pending.items() if amount > 0 and fund_id not in eligible]
        raise HTTPException(status_code=409, detail=f"El efectivo de {', '.join(designated)} se deposita en su cuenta designada; separe el depósito")
    remaining, fund_totals = payload.amount_cents, {}
    for fund_id in sorted(eligible, key=lambda key: funds.get(key, {}).get("code") != "GENERAL"):
        take = min(remaining, pending[fund_id])
        if take > 0:
            fund_totals[fund_id] = take
            remaining -= take
    accounts = {doc["code"]: doc["account_id"] async for doc in db.finance_accounts.find({"code": "1010"}, {"_id": 0, "code": 1, "account_id": 1})}
    lines = []
    for fund_id, amount in fund_totals.items():
        lines += [{"account_id": payload.bank_account_id, "fund_id": fund_id, "debit_cents": amount, "credit_cents": 0, "description": "Depósito de la colecta"},
                  {"account_id": accounts["1010"], "fund_id": fund_id, "debit_cents": 0, "credit_cents": amount, "description": "Depósito de la colecta"}]
    deposit_id = str(uuid4())
    now = now_utc()
    journal = await create_journal(current_user["user_id"], payload.deposit_date.isoformat(), f"Depósito · colecta {collection['service_name']} {collection['service_date']}", "collection_deposit", deposit_id, lines, "submitted")
    await db.finance_journal_entries.update_one({"entry_id": journal["entry_id"]}, {"$set": {"status": "posted", "posted_at": now, "posting_policy": "colecta_dos_personas",
                                                                                           "is_test": bool(collection.get("is_test")), "updated_at": now}})
    deposit = {"_id": deposit_id, "deposit_id": deposit_id, "collection_id": collection_id, "deposit_date": payload.deposit_date.isoformat(), "bank_account_id": payload.bank_account_id,
               "total_cents": payload.amount_cents, "fund_totals": fund_totals, "reference": payload.reference, "note": payload.note, "journal_entry_id": journal["entry_id"],
               "status": "pending_reconciliation", "is_test": bool(collection.get("is_test")), "contribution_ids": [], "created_by_user_id": current_user["user_id"],
               "created_by_name": current_user.get("nombre"), "created_at": now, "updated_at": now}
    await db.finance_deposits.insert_one(deposit)
    summary_entry = {key: deposit[key] for key in ("deposit_id", "deposit_date", "bank_account_id", "total_cents", "fund_totals", "reference", "journal_entry_id", "created_by_name", "created_at")}
    summary_entry["bank_name"] = f"{bank.get('code')} · {bank.get('name')}"
    collection.setdefault("deposits", []).append(summary_entry)
    left, _ = deposit_balance(collection, await cash_by_fund(collection))
    update: dict = {"$push": {"deposits": summary_entry}, "$set": {"deposit_pending_cents": left, "cash_received_cents": received}}
    if left == 0:
        stage = {"stage": "deposited", "label": "Depositada", "by_user_id": current_user["user_id"], "by_name": current_user.get("nombre"), "at": now}
        update["$set"]["status"] = "deposited"
        update["$push"]["timeline"] = stage
        await db.finance_contributions.update_many({"collection_id": collection_id, "status": "recorded", "payment_method": "cash"}, {"$set": {"deposit_id": deposit_id, "updated_at": now}})
    await db.finance_collections.update_one({"collection_id": collection_id}, update)
    await touch(collection_id, current_user, "deposit_registered", {"deposit_id": deposit_id, "amount_cents": payload.amount_cents, "pending_cents": left})
    return await view(await load_collection(collection_id), current_user)


# ------------------------------------------------------------------ aportes que llegan de otros módulos
# Decisión del dueño: los donativos de Ven y Come y los pagos de Librería NO crean contribuciones por su
# cuenta: entran como aportes de una colecta («Ven y Come» / «Librería» del día) que Finanzas cuadra y
# envía, y que una SEGUNDA persona valida. Nadie espera a la pastora.
EXTERNAL_SOURCES = {"campaign_venycome": "Ven y Come · donativos", "library": "Librería · pagos"}


async def register_external_item(*, source: str, source_id: str, service_date: str, amount_cents: int, method: str, contribution_type: str, fund_id: str,
                                 person_id: Optional[str], reference: Optional[str], note: Optional[str], actor_user_id: str,
                                 campaign_id: Optional[str] = None, is_test: bool = False) -> dict:
    """Agrega el aporte a la colecta abierta de ese origen y ese día (la abre si no hay). Devuelve los ids."""
    if not await db.finance_contribution_types.find_one({"type_key": contribution_type, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=409, detail=f"Concepto {contribution_type} no configurado en Finanzas")
    now = now_utc()
    query = {"source": source, "service_date": service_date, "status": "registering", "is_test": bool(is_test)}
    collection = await db.finance_collections.find_one(query, {"_id": 0})
    if not collection:
        collection_id = str(uuid4())
        name = EXTERNAL_SOURCES.get(source, source)
        collection = {"_id": collection_id, "collection_id": collection_id, "service_date": service_date, "service_name": name, "source": source,
                      "notes": "Se abre sola con los aportes de este módulo; Finanzas la cuadra y la envía, y otra persona la valida.",
                      "is_test": bool(is_test), "status": "registering", "cash_count": None, "explanations": [],
                      "opened_by_user_id": actor_user_id, "opened_by_name": name, "opened_at": now,
                      "timeline": [{"stage": "opened", "label": "Abierta", "by_user_id": actor_user_id, "by_name": name, "at": now}],
                      "history": [], "created_at": now, "updated_at": now}
        await db.finance_collections.insert_one(collection)
        await audit(actor_user_id, "collection_opened", "collection", collection_id, {"service_date": service_date, "source": source, "is_test": bool(is_test)})
    if await db.finance_collection_items.find_one({"origin_key": f"{source}:{source_id}", "status": "active"}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Ese aporte ya está en una colecta de Finanzas")
    item_id = str(uuid4())
    await db.finance_collection_items.insert_one({"_id": item_id, "item_id": item_id, "collection_id": collection["collection_id"], "person_id": person_id, "anonymous": not person_id,
                                                  "contribution_type": contribution_type, "fund_id": fund_id, "amount_cents": amount_cents, "method": method if method in METHODS else "other",
                                                  "reference": reference, "note": note, "campaign_id": campaign_id, "origin": {"source": source, "source_id": source_id}, "origin_key": f"{source}:{source_id}",
                                                  "zelle_tx_id": None, "status": "active", "is_test": bool(is_test), "created_by_user_id": actor_user_id, "created_at": now, "updated_at": now, "history": []})
    await db.finance_collections.update_one({"collection_id": collection["collection_id"]}, {"$set": {"updated_at": now}, "$push": {"history": {
        "action": "item_added", "by_user_id": actor_user_id, "at": now, "item_id": item_id, "amount_cents": amount_cents, "method": method, "source": source}}})
    await audit(actor_user_id, "collection_item_added", "collection", collection["collection_id"], {"item_id": item_id, "source": source, "source_id": source_id, "amount_cents": amount_cents})
    return {"collection_id": collection["collection_id"], "item_id": item_id}


async def void_external_item(item_id: str, actor_user_id: str, reason: str) -> None:
    """Deshacer desde el módulo de origen: solo mientras la colecta se está registrando. Después, Finanzas
    corrige la colecta (queda historial y se vuelve a validar)."""
    item = await db.finance_collection_items.find_one({"item_id": item_id}, {"_id": 0})
    if not item or item["status"] != "active":
        return
    collection = await load_collection(item["collection_id"])
    if collection.get("status") not in OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="La colecta de Finanzas ya se envió a validación; pida a Finanzas que la corrija (queda historial)")
    now = now_utc()
    await db.finance_collection_items.update_one({"item_id": item_id}, {"$set": {"status": "voided", "void_reason": reason, "voided_by_user_id": actor_user_id, "voided_at": now, "zelle_tx_id": None, "updated_at": now}})
    if item.get("zelle_tx_id"):
        await db.finance_zelle_received.update_one({"tx_id": item["zelle_tx_id"], "matched_item_id": item_id}, {"$set": {"matched_item_id": None, "matched_at": None}})
    await db.finance_collections.update_one({"collection_id": collection["collection_id"]}, {"$set": {"updated_at": now}, "$push": {"history": {
        "action": "item_voided", "by_user_id": actor_user_id, "at": now, "item_id": item_id, "reason": reason}}})
    await audit(actor_user_id, "collection_item_voided", "collection", collection["collection_id"], {"item_id": item_id, "reason": reason})
