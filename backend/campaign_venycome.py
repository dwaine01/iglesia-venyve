"""Campaña Ven y Come — panel de control del operador + pantalla pública en vivo."""
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId

from access_control import CAMPAIGN_VENYCOME_MANAGE, has_capability, is_general_coordinator, is_global_pastoral_authority
from core_person import _normalize as normalize_person_name, next_person_number
from finance_engine import create_journal
from person_domains import contact_items
from server import db, get_current_user

router = APIRouter(prefix="/api/campaigns/venycome", tags=["campaign-venycome"])

MAX_AMOUNT_CENTS = 10_000_000  # tope defensivo ($100,000) contra error de dedo
DONATION_TYPES = Literal["promise", "received"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def serialize(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize(item) for item in doc]
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def is_campaign_operator(user: dict) -> bool:
    return is_global_pastoral_authority(user) or is_general_coordinator(user) or has_capability(user, CAMPAIGN_VENYCOME_MANAGE)


def operator(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_campaign_operator(current_user):
        raise HTTPException(status_code=403, detail="No tiene permiso de Operador de Campaña Ven y Come")
    return current_user


def receiver(current_user: dict = Depends(get_current_user)) -> dict:
    """Decisión del dueño: «Recibido» (el dinero llegó y pasa a Finanzas) lo confirma SOLO el encargado de la
    campaña, con el permiso Operador Ven y Come. La pastora no (aunque tenga Acceso Maestro)."""
    if is_global_pastoral_authority(current_user) or not has_capability(current_user, CAMPAIGN_VENYCOME_MANAGE):
        raise HTTPException(status_code=403, detail="«Recibido» lo confirma solo el encargado de la campaña (permiso Operador Ven y Come); la pastora no")
    return current_user


async def audit(action: str, donation_id: Optional[str], actor_user_id: str, before: Optional[dict], after: Optional[dict]):
    await db.campaign_audit_events.insert_one({
        "_id": str(uuid4()), "action": action, "donation_id": donation_id,
        "actor_user_id": actor_user_id, "before": before, "after": after, "created_at": now_utc(),
    })


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, message: dict):
        stale = []
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()


class DonationInput(BaseModel):
    donor_name: Optional[str] = Field(default=None, max_length=120)
    person_id: Optional[str] = None
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)
    donation_type: DONATION_TYPES = "received"
    anonymous: bool = False
    consent_show_name: bool = False
    idempotency_key: Optional[str] = Field(default=None, max_length=80)

    @field_validator("donor_name")
    @classmethod
    def strip_name(cls, value):
        if value is None:
            return value
        cleaned = value.strip()[:120]
        return cleaned or None


class DonationUpdateInput(BaseModel):
    donor_name: Optional[str] = Field(default=None, max_length=120)
    person_id: Optional[str] = None
    amount_cents: int = Field(gt=0, le=MAX_AMOUNT_CENTS)
    donation_type: DONATION_TYPES
    anonymous: bool = False
    consent_show_name: bool = False


class VerifyDonationInput(BaseModel):
    payment_method: Literal["zelle", "cash"]


class ContactNoteInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("La nota no puede estar vacía")
        return cleaned[:500]


class SettingsInput(BaseModel):
    goal_cents: int = Field(gt=0, le=1_000_000_000)
    counting_rule: Literal["committed", "received_only"] = "committed"
    mode: Literal["production", "rehearsal"] = "rehearsal"
    zelle_info: Optional[str] = Field(default=None, max_length=200)


class PresentationLinkInput(BaseModel):
    label: Optional[str] = Field(default=None, max_length=120)


async def get_settings() -> dict:
    settings = await db.campaign_settings.find_one({"_id": "venycome"}, {"_id": 0})
    if not settings:
        settings = {"goal_cents": 1_200_000, "counting_rule": "committed", "mode": "rehearsal", "zelle_info": None, "updated_at": now_utc(), "updated_by_user_id": None}
        await db.campaign_settings.update_one({"_id": "venycome"}, {"$set": settings}, upsert=True)
    return settings


PIECE_VALUE_CENTS = 10_000  # $100 por pieza


def compute_pieces_and_feed(donations: list, counting_rule: str, total_pieces: int) -> tuple:
    """Atribuye piezas del rompecabezas a quien la completa (cruza el umbral de $100)
    y construye el feed completo de donantes, para que ningún nombre/monto se pierda."""
    pieces = [{"status": "empty", "donor_label": None, "fill_ratio": 0.0} for _ in range(total_pieces)]
    feed = []
    donor_totals: dict = {}
    cumulative = 0
    ceiling_cents = total_pieces * PIECE_VALUE_CENTS
    for item in donations:
        label = donor_label(item)
        feed.append({
            "donor_label": label, "amount_cents": item["amount_cents"],
            "donation_type": item["donation_type"], "created_at": item["created_at"].isoformat(),
        })
        donor_totals[label] = donor_totals.get(label, 0) + item["amount_cents"]
        if counting_rule == "received_only" and item["donation_type"] != "received":
            continue
        remaining = item["amount_cents"]
        while remaining > 0 and cumulative < ceiling_cents:
            piece_idx = cumulative // PIECE_VALUE_CENTS
            filled_in_piece = cumulative % PIECE_VALUE_CENTS
            space_left = PIECE_VALUE_CENTS - filled_in_piece
            take = min(remaining, space_left)
            cumulative += take
            remaining -= take
            new_filled = cumulative % PIECE_VALUE_CENTS
            if new_filled == 0:
                pieces[piece_idx] = {"status": "full", "donor_label": label, "fill_ratio": 1.0}
            else:
                pieces[piece_idx] = {"status": "partial", "donor_label": label, "fill_ratio": round(new_filled / PIECE_VALUE_CENTS, 4)}
    feed.reverse()
    return pieces, feed[:40], donor_totals


async def compute_summary(mode: str) -> dict:
    settings = await get_settings()
    is_rehearsal = mode == "rehearsal"
    cursor = db.campaign_donations.find(
        {"status": "active", "is_rehearsal": is_rehearsal},
        {"_id": 0, "amount_cents": 1, "donation_type": 1, "donor_name": 1, "anonymous": 1, "consent_show_name": 1, "created_at": 1},
    ).sort("created_at", 1)
    donations = await cursor.to_list(5000)
    received_cents = 0
    pending_cents = 0
    for item in donations:
        if item["donation_type"] == "received":
            received_cents += item["amount_cents"]
        else:
            pending_cents += item["amount_cents"]
    committed_cents = received_cents + pending_cents
    goal_cents = settings["goal_cents"]
    counted_cents = committed_cents if settings["counting_rule"] == "committed" else received_cents
    percent = min(1.0, counted_cents / goal_cents) if goal_cents else 0.0
    total_pieces = max(1, round(goal_cents / PIECE_VALUE_CENTS))
    pieces, feed, donor_totals = compute_pieces_and_feed(donations, settings["counting_rule"], total_pieces)
    return {
        "mode": mode, "goal_cents": goal_cents, "counting_rule": settings["counting_rule"],
        "received_cents": received_cents, "pending_cents": pending_cents, "committed_cents": committed_cents,
        "counted_cents": counted_cents, "percent": round(percent, 6),
        "remaining_cents": max(0, goal_cents - committed_cents),
        "total_pieces": total_pieces, "pieces": pieces, "donor_feed": feed, "donor_totals": donor_totals,
    }


def donor_label(donation: dict) -> str:
    if donation.get("anonymous") or not donation.get("consent_show_name"):
        return "Donante anónimo"
    return donation.get("donor_name") or "Donante anónimo"


def donor_private_label(donation: dict) -> str:
    """Nombre real para los registros contables/pastorales (Finanzas, Persona 360).
    El consentimiento de mostrar nombre solo aplica a la pantalla pública del bus;
    la pastora y contabilidad siempre deben ver quién donó realmente."""
    if donation.get("anonymous"):
        return "Donante anónimo"
    return donation.get("donor_name") or "Donante anónimo"


async def find_or_create_person(donor_name: Optional[str], user_id: str) -> tuple:
    """Busca una Persona 360 por nombre para vincular el depósito de Finanzas.
    Si encuentra exactamente una coincidencia la reutiliza; si no encuentra ninguna,
    crea un registro mínimo; si hay varias coincidencias ambiguas, no adivina (anónimo)."""
    if not donor_name or not donor_name.strip():
        return None, False
    norm = normalize_person_name(donor_name)
    if not norm:
        return None, False
    pattern = r"(^|\s)" + re.escape(norm) + r"(\s|$)"
    candidates = await db.persons.find({"search_key": {"$regex": pattern}}, {"_id": 1}).to_list(5)
    if len(candidates) == 1:
        return str(candidates[0]["_id"]), False
    if len(candidates) > 1:
        return None, False
    tokens = donor_name.strip().split()
    nombre = tokens[0]
    apellido = " ".join(tokens[1:]) if len(tokens) > 1 else ""
    now = now_utc()
    doc = {
        "nombre": nombre, "apellido": apellido, "fecha_nacimiento": None, "age_category": None,
        "person_number": await next_person_number(), "search_key": norm, "idempotency_key": str(uuid4()),
        "version": 1, "created_by": user_id, "created_at": now, "updated_at": now,
        "source": "campaign_venycome",
    }
    result = await db.persons.insert_one(doc)
    return str(result.inserted_id), True


async def resolve_donation_person(donation: dict, user_id: str) -> tuple:
    """Si el operador vinculó explícitamente una Persona 360 al registrar el donativo,
    se respeta esa elección (la forma más confiable); si no, se recurre al match por nombre."""
    explicit_person_id = donation.get("person_id")
    if explicit_person_id:
        exists = await db.persons.find_one({"_id": ObjectId(explicit_person_id)}, {"_id": 1}) if ObjectId.is_valid(explicit_person_id) else None
        if exists:
            return explicit_person_id, False
    return await find_or_create_person(donation.get("donor_name"), user_id)


VEN_Y_COME_CAMPAIGN_NAME = "Ven y Come · Bus de comida"


async def get_or_create_ven_y_come_finance_campaign(fund_id: str, user_id: str) -> dict:
    """Obtiene (o crea una sola vez) el proyecto de Finanzas 'Ven y Come' para que todas las
    contribuciones de esta campaña queden etiquetadas con su nombre en Finanzas y en el
    perfil 360 de cada donante, distinguiéndolas de otros ingresos de Pro-Templo."""
    campaign = await db.finance_campaigns.find_one({"name": VEN_Y_COME_CAMPAIGN_NAME}, {"_id": 0})
    if campaign:
        return campaign
    settings = await get_settings()
    campaign_id = str(uuid4())
    now = now_utc()
    doc = {
        "_id": campaign_id, "campaign_id": campaign_id, "name": VEN_Y_COME_CAMPAIGN_NAME,
        "fund_id": fund_id, "goal_cents": settings.get("goal_cents", 1200000), "budget_cents": 0,
        "project_type": "campaign", "description": "Recaudación de fondos para la compra del autobús/camión de comida 'Ven y Come'.",
        "start_date": now.date().isoformat(), "end_date": None, "status": "active",
        "created_by_user_id": user_id, "created_at": now,
    }
    await db.finance_campaigns.insert_one(doc)
    return doc


async def create_finance_deposit_for_donation(donation: dict, payment_method: str, current_user: dict) -> dict:
    """El donativo verificado entra a Finanzas como un aporte de la colecta «Ven y Come» del día (fondo
    Pro-Templo, proyecto «Ven y Come»). Finanzas la cuadra y la envía, y una segunda persona la valida:
    recién ahí se crea la contribución contabilizada. Nadie espera a la pastora (decisión del dueño)."""
    fund = await db.finance_funds.find_one({"code": "BUILDING"}, {"_id": 0})
    if not fund:
        raise HTTPException(status_code=409, detail="Fondo Pro-Templo no configurado en Finanzas")
    finance_campaign = await get_or_create_ven_y_come_finance_campaign(fund["fund_id"], current_user["user_id"])
    person_id, created_new_person = await resolve_donation_person(donation, current_user["user_id"])
    created_at = donation.get("created_at")
    # F2: el día del donativo en la zona de la iglesia (no en UTC).
    from report_period import local_day, report_zone
    received_date = local_day(created_at if isinstance(created_at, datetime) else now_utc(), await report_zone())
    from finance_collections import register_external_item
    registered = await register_external_item(
        source="campaign_venycome", source_id=donation["donation_id"], service_date=received_date, amount_cents=donation["amount_cents"],
        method=payment_method, contribution_type="building", fund_id=fund["fund_id"], person_id=person_id,
        reference=f"Ven y Come #{donation['donation_id'][:8]}", note=f"{VEN_Y_COME_CAMPAIGN_NAME} · {donor_private_label(donation)}",
        actor_user_id=current_user["user_id"], campaign_id=finance_campaign["campaign_id"], is_test=bool(donation.get("is_test") or donation.get("is_rehearsal")))  # el ensayo no toca Finanzas real
    return {"contribution_id": None, "collection_id": registered["collection_id"], "collection_item_id": registered["item_id"],
            "person_id": person_id, "created_new_person": created_new_person}


async def donation_doc(donation_id: str) -> dict:
    doc = await db.campaign_donations.find_one({"donation_id": donation_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Donativo no encontrado")
    return doc


# ---------------- Operator endpoints (requieren capability Operador de Campaña) ----------------

@router.get("/settings", response_model=dict)
async def read_settings(current_user: dict = Depends(operator)):
    return serialize(await get_settings())


@router.put("/settings", response_model=dict)
async def update_settings(payload: SettingsInput, current_user: dict = Depends(operator)):
    data = payload.model_dump()
    data["updated_at"] = now_utc()
    data["updated_by_user_id"] = current_user["user_id"]
    await db.campaign_settings.update_one({"_id": "venycome"}, {"$set": data}, upsert=True)
    summary = await compute_summary(data["mode"])
    await manager.broadcast({"type": "summary", **summary})
    return serialize(data)


@router.get("/summary", response_model=dict)
async def operator_summary(current_user: dict = Depends(operator)):
    settings = await get_settings()
    return await compute_summary(settings["mode"])


@router.post("/donations", status_code=201, response_model=dict)
async def create_donation(payload: DonationInput, current_user: dict = Depends(operator)):
    settings = await get_settings()
    if payload.idempotency_key:
        existing = await db.campaign_donations.find_one({"idempotency_key": payload.idempotency_key, "created_by_user_id": current_user["user_id"]}, {"_id": 0})
        if existing:
            return serialize(existing)
    donation_id = str(uuid4())
    now = now_utc()
    doc = {
        "_id": donation_id, "donation_id": donation_id, "donor_name": payload.donor_name,
        "person_id": payload.person_id if not payload.anonymous else None,
        "amount_cents": payload.amount_cents, "donation_type": payload.donation_type,
        "anonymous": payload.anonymous, "consent_show_name": payload.consent_show_name,
        "is_rehearsal": settings["mode"] == "rehearsal", "status": "active",
        "idempotency_key": payload.idempotency_key, "shown_at": now, "contact_notes": [],
        "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.campaign_donations.insert_one(doc)
    await audit("donation_created", donation_id, current_user["user_id"], None, doc)
    summary = await compute_summary(settings["mode"])
    await manager.broadcast({"type": "summary", **summary})
    await manager.broadcast({"type": "announcement", "donor_label": donor_label(doc), "amount_cents": doc["amount_cents"], "donation_type": doc["donation_type"]})
    return serialize(doc)


@router.get("/donations", response_model=dict)
async def list_donations(mode: Optional[str] = None, current_user: dict = Depends(operator)):
    settings = await get_settings()
    active_mode = mode or settings["mode"]
    items = await db.campaign_donations.find({"is_rehearsal": active_mode == "rehearsal"}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return {"items": serialize(items), "mode": active_mode}


@router.put("/donations/{donation_id}", response_model=dict)
async def update_donation(donation_id: str, payload: DonationUpdateInput, current_user: dict = Depends(operator)):
    before = await donation_doc(donation_id)
    if before["status"] == "voided":
        raise HTTPException(status_code=409, detail="No se puede editar un donativo anulado")
    if before.get("verified"):
        raise HTTPException(status_code=409, detail="No se puede editar un donativo ya verificado/sellado")
    updates = payload.model_dump()
    updates["updated_at"] = now_utc()
    updates["updated_by_user_id"] = current_user["user_id"]
    await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": updates})
    after = await donation_doc(donation_id)
    await audit("donation_updated", donation_id, current_user["user_id"], before, after)
    settings = await get_settings()
    summary = await compute_summary(settings["mode"])
    await manager.broadcast({"type": "summary", **summary})
    return serialize(after)


@router.delete("/donations/{donation_id}", response_model=dict)
async def delete_donation(donation_id: str, current_user: dict = Depends(operator)):
    before = await donation_doc(donation_id)
    if before.get("verified"):
        raise HTTPException(status_code=409, detail="No se puede borrar un donativo ya verificado/sellado")
    await db.campaign_donations.delete_one({"donation_id": donation_id})
    await audit("donation_deleted", donation_id, current_user["user_id"], before, None)
    settings = await get_settings()
    summary = await compute_summary(settings["mode"])
    await manager.broadcast({"type": "summary", **summary})
    return {"ok": True}


async def receive_into_finance(donation_id: str, payment_method: str, current_user: dict) -> dict:
    """Recibido (efectivo o Zelle) → aporte de la colecta «Ven y Come» del día, UNA sola vez por donativo."""
    before = await donation_doc(donation_id)
    if before["status"] == "voided":
        raise HTTPException(status_code=409, detail="No se puede recibir un donativo anulado")
    if before.get("verified"):
        raise HTTPException(status_code=409, detail="Este donativo ya fue verificado y está en Finanzas")
    now = now_utc()
    # Reserva atómica: dos toques (o dos personas) a la vez no meten el mismo donativo dos veces.
    claimed = await db.campaign_donations.update_one({"donation_id": donation_id, "verified": {"$ne": True}, "finance_claim": {"$exists": False}, "status": {"$ne": "voided"}},
                                                     {"$set": {"finance_claim": {"by_user_id": current_user["user_id"], "at": now}}})
    if not claimed.modified_count:
        raise HTTPException(status_code=409, detail="Este donativo ya se está pasando a Finanzas")
    try:
        if before["donation_type"] != "received":
            await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": {"donation_type": "received", "received_at": now, "updated_at": now}})
            before = {**before, "donation_type": "received"}
        deposit = await create_finance_deposit_for_donation(before, payment_method, current_user)
    except Exception:
        await db.campaign_donations.update_one({"donation_id": donation_id}, {"$unset": {"finance_claim": ""}})
        raise
    await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": {
        "verified": True, "verified_at": now_utc(), "verified_by_user_id": current_user["user_id"],
        "verified_payment_method": payment_method, "finance_contribution_id": deposit["contribution_id"],
        "finance_collection_id": deposit["collection_id"], "finance_collection_item_id": deposit["collection_item_id"],
        "finance_person_id": deposit["person_id"], "updated_at": now_utc(),
    }, "$unset": {"finance_claim": ""}})
    after = await donation_doc(donation_id)
    await audit("donation_verified", donation_id, current_user["user_id"], before, after)
    settings = await get_settings()
    await manager.broadcast({"type": "summary", **(await compute_summary(settings["mode"]))})
    return serialize(after)


@router.post("/donations/{donation_id}/receive", response_model=dict)
async def receive_donation(donation_id: str, payload: VerifyDonationInput, current_user: dict = Depends(receiver)):
    """Un solo paso: «Recibido (efectivo/Zelle)». Sirve para promesas y para donativos ya anotados como recibidos."""
    return await receive_into_finance(donation_id, payload.payment_method, current_user)


@router.post("/donations/{donation_id}/verify", response_model=dict)
async def verify_donation(donation_id: str, payload: VerifyDonationInput, current_user: dict = Depends(receiver)):
    before = await donation_doc(donation_id)
    if before["donation_type"] != "received" and not before.get("verified"):
        raise HTTPException(status_code=409, detail="Solo se pueden verificar donativos marcados como recibidos")
    return await receive_into_finance(donation_id, payload.payment_method, current_user)


@router.post("/donations/{donation_id}/unverify", response_model=dict)
async def unverify_donation(donation_id: str, current_user: dict = Depends(receiver)):
    """Revierte una verificación hecha por error: anula/revierte el depósito contable en
    Finanzas (sin borrar el rastro contable) y deja el donativo activo de nuevo, para poder
    editarlo, anularlo o volver a verificarlo correctamente."""
    before = await donation_doc(donation_id)
    if not before.get("verified"):
        raise HTTPException(status_code=409, detail="Este donativo no está verificado")
    contribution_id = before.get("finance_contribution_id")
    now = now_utc()
    if before.get("finance_collection_item_id"):
        # Nuevo flujo: se anula el aporte en la colecta mientras Finanzas aún la registra (queda historial).
        from finance_collections import void_external_item
        await void_external_item(before["finance_collection_item_id"], current_user["user_id"], "Verificación revertida en campaña Ven y Come (error del operador)")
    if contribution_id:
        contribution = await db.finance_contributions.find_one({"contribution_id": contribution_id})
        if contribution and contribution.get("status") != "corrected":
            journal = await db.finance_journal_entries.find_one({"entry_id": contribution.get("journal_entry_id")})
            if journal and journal.get("status") == "posted":
                reversal_lines = [{**line, "debit_cents": line.get("credit_cents", 0), "credit_cents": line.get("debit_cents", 0), "description": f"Reversión: {line.get('description', '')}"} for line in journal.get("lines", [])]
                await create_journal(current_user["user_id"], now.date().isoformat(), "Reversión por verificación revertida (Ven y Come)", "contribution_reversal", contribution_id, reversal_lines, "submitted")
            elif journal:
                await db.finance_journal_entries.update_one({"entry_id": journal["entry_id"]}, {"$set": {
                    "status": "voided", "void_reason": "Verificación revertida en campaña Ven y Come (error del operador)",
                    "voided_by_user_id": current_user["user_id"], "voided_at": now, "updated_at": now,
                }})
            await db.finance_contributions.update_one({"contribution_id": contribution_id}, {"$set": {
                "status": "corrected", "correction_reason": "Verificación revertida en campaña Ven y Come (registrada por error)",
                "corrected_by_user_id": current_user["user_id"], "corrected_at": now,
                "updated_by_user_id": current_user["user_id"], "updated_at": now,
            }})
    await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": {
        "verified": False, "verified_at": None, "verified_by_user_id": None, "verified_payment_method": None,
        "finance_contribution_id": None, "finance_collection_id": None, "finance_collection_item_id": None, "finance_person_id": None, "updated_at": now,
    }})
    after = await donation_doc(donation_id)
    await audit("donation_unverified", donation_id, current_user["user_id"], before, after)
    return serialize(after)


@router.post("/donations/{donation_id}/void", response_model=dict)
async def void_donation(donation_id: str, current_user: dict = Depends(operator)):
    before = await donation_doc(donation_id)
    if before["status"] == "voided":
        raise HTTPException(status_code=409, detail="Ya estaba anulado")
    if before.get("verified"):
        raise HTTPException(status_code=409, detail="No se puede anular un donativo ya verificado/sellado")
    await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": {"status": "voided", "updated_at": now_utc(), "voided_by_user_id": current_user["user_id"]}})
    after = await donation_doc(donation_id)
    await audit("donation_voided", donation_id, current_user["user_id"], before, after)
    settings = await get_settings()
    summary = await compute_summary(settings["mode"])
    await manager.broadcast({"type": "summary", **summary})
    return serialize(after)


class MarkReceivedInput(BaseModel):
    payment_method: Optional[Literal["zelle", "cash"]] = None


@router.post("/donations/{donation_id}/mark-received", response_model=dict)
async def mark_received(donation_id: str, payload: Optional[MarkReceivedInput] = None, current_user: dict = Depends(receiver)):
    """Antes cambiaba solo el estado. Ahora «Recibido» es UN paso que también lo pasa a Finanzas: hay que decir
    si llegó en efectivo o por Zelle (así nunca queda dinero «recibido» fuera de Finanzas)."""
    if not payload or not payload.payment_method:
        raise HTTPException(status_code=422, detail="Diga si llegó en efectivo o por Zelle: al marcarlo recibido pasa a Finanzas")
    return await receive_into_finance(donation_id, payload.payment_method, current_user)


@router.post("/donations/{donation_id}/show", response_model=dict)
async def show_donation(donation_id: str, current_user: dict = Depends(operator)):
    doc = await donation_doc(donation_id)
    if doc["status"] == "voided":
        raise HTTPException(status_code=409, detail="No se puede mostrar un donativo anulado")
    await db.campaign_donations.update_one({"donation_id": donation_id}, {"$set": {"shown_at": now_utc()}})
    await manager.broadcast({"type": "announcement", "donor_label": donor_label(doc), "amount_cents": doc["amount_cents"], "donation_type": doc["donation_type"]})
    return {"ok": True}


@router.get("/donations/{donation_id}/contact", response_model=dict)
async def donation_contact(donation_id: str, current_user: dict = Depends(operator)):
    """Tarjeta de contacto rápido: para que el operador pueda llamar/mensajear al donante
    sin tener que entrar al directorio de Personas 360 por separado."""
    doc = await donation_doc(donation_id)
    settings = await get_settings()
    result = {
        "donor_name": doc.get("donor_name"), "amount_cents": doc["amount_cents"],
        "phone": None, "email": None, "zelle_info": settings.get("zelle_info"),
    }
    person_id = doc.get("person_id")
    if person_id:
        contacts = await contact_items(person_id)
        phone = next((item for item in contacts if item.get("tipo") in {"telefono", "whatsapp"} and item.get("es_principal")), None) \
            or next((item for item in contacts if item.get("tipo") in {"telefono", "whatsapp"}), None)
        email = next((item for item in contacts if item.get("tipo") == "email" and item.get("es_principal")), None) \
            or next((item for item in contacts if item.get("tipo") == "email"), None)
        if phone:
            result["phone"] = phone.get("valor")
        if email:
            result["email"] = email.get("valor")
    return result


@router.post("/donations/{donation_id}/notes", response_model=dict)
async def add_contact_note(donation_id: str, payload: ContactNoteInput, current_user: dict = Depends(operator)):
    """Registra una nota de seguimiento (ej. 'dijo que paga mañana por Zelle') para que
    quede en archivo y cualquier operador la vea fácilmente."""
    before = await donation_doc(donation_id)
    note = {
        "note_id": str(uuid4()), "text": payload.text,
        "created_by_user_id": current_user["user_id"],
        "created_by_name": current_user.get("email") or "Operador",
        "created_at": now_utc(),
    }
    await db.campaign_donations.update_one(
        {"donation_id": donation_id},
        {"$push": {"contact_notes": note}, "$set": {"updated_at": now_utc()}},
    )
    after = await donation_doc(donation_id)
    await audit("donation_note_added", donation_id, current_user["user_id"], before, after)
    return serialize(after)


@router.post("/settings/reset-rehearsal", response_model=dict)
async def reset_rehearsal(current_user: dict = Depends(operator)):
    result = await db.campaign_donations.delete_many({"is_rehearsal": True})
    await db.campaign_audit_events.insert_one({"_id": str(uuid4()), "action": "rehearsal_reset", "donation_id": None, "actor_user_id": current_user["user_id"], "before": None, "after": {"deleted_count": result.deleted_count}, "created_at": now_utc()})
    summary = await compute_summary("rehearsal")
    await manager.broadcast({"type": "summary", **summary})
    return {"deleted_count": result.deleted_count}


@router.post("/presentation-links", status_code=201, response_model=dict)
async def create_presentation_link(payload: PresentationLinkInput, current_user: dict = Depends(operator)):
    token_id = str(uuid4())
    token = secrets.token_urlsafe(24)
    now = now_utc()
    doc = {"_id": token_id, "token_id": token_id, "token": token, "label": payload.label, "active": True, "created_by_user_id": current_user["user_id"], "created_at": now, "revoked_at": None}
    await db.campaign_presentation_tokens.insert_one(doc)
    return serialize(doc)


SCREEN_LINK_HOURS = 12


@router.post("/screen-link", status_code=201, response_model=dict)
async def create_screen_link(current_user: dict = Depends(get_current_user)):
    """«Ver pantalla» desde el panel: un enlace de presentación TEMPORAL (12 h) en lugar de poner la sesión
    del usuario en la dirección (quedaba en el historial, en el proyector y en los registros)."""
    token_id = str(uuid4())
    now = now_utc()
    doc = {"_id": token_id, "token_id": token_id, "token": secrets.token_urlsafe(24), "label": "Pantalla abierta desde el panel", "active": True,
           "temporary": True, "expires_at": now + timedelta(hours=SCREEN_LINK_HOURS), "created_by_user_id": current_user["user_id"], "created_at": now, "revoked_at": None}
    await db.campaign_presentation_tokens.insert_one(doc)
    return {"token": doc["token"], "expires_at": doc["expires_at"].isoformat()}


@router.get("/presentation-links", response_model=dict)
async def list_presentation_links(current_user: dict = Depends(operator)):
    items = await db.campaign_presentation_tokens.find({"temporary": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"items": serialize(items)}


@router.post("/presentation-links/{token_id}/revoke", response_model=dict)
async def revoke_presentation_link(token_id: str, current_user: dict = Depends(operator)):
    result = await db.campaign_presentation_tokens.update_one({"token_id": token_id}, {"$set": {"active": False, "revoked_at": now_utc()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Enlace no encontrado")
    return {"ok": True}


# ---------------- Public read-only (token de presentación o sesión autenticada) ----------------

async def resolve_public_access(token: Optional[str]) -> bool:
    """Solo enlaces de presentación activos (y no vencidos). Ya NO se acepta la sesión de un usuario en la dirección."""
    if not token:
        return False
    link = await db.campaign_presentation_tokens.find_one({"token": token, "active": True}, {"_id": 0})
    if not link:
        return False
    expires = link.get("expires_at")
    if expires is not None:
        expires = expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires
        if expires < now_utc():
            return False
    return True


@router.get("/public/summary", response_model=dict)
async def public_summary(token: str):
    if not await resolve_public_access(token):
        raise HTTPException(status_code=403, detail="Token inválido o revocado")
    settings = await get_settings()
    return await compute_summary(settings["mode"])


@router.websocket("/public/ws")
async def public_ws(websocket: WebSocket, token: Optional[str] = None):
    if not await resolve_public_access(token):
        await websocket.accept()
        await websocket.close(code=4403)
        return
    await manager.connect(websocket)
    try:
        settings = await get_settings()
        await websocket.send_json({"type": "summary", **(await compute_summary(settings["mode"]))})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def ensure_indexes():
    await db.campaign_donations.create_index([("is_rehearsal", 1), ("status", 1)])
    await db.campaign_donations.create_index("idempotency_key")
    await db.campaign_presentation_tokens.create_index("token", unique=True)
