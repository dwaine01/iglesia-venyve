"""Puerta a puerta (salida evangelística): calle activa, vivienda por número y
apartamento, e intentos de visita con pocos toques.

Reutiliza las colecciones existentes, sin colecciones paralelas:
- `outreach_households` = VIVIENDA. Nuevos campos: `street_name`,
  `house_number`, `unit` (cada apartamento es una vivienda) y `door_key`
  (único por invasión) para no duplicar la misma puerta. Estado de la puerta
  derivado del último intento: `door_status` ∈ {pending_revisit, opened,
  followup_scheduled}; `attempts_count`, `last_result`, `last_attempt_at`.
- `outreach_visit_events` = INTENTO (una vivienda puede tener muchos).
  Nuevos campos: `opened`, `contact_level`, `actions`, `books`,
  `books_total`, `other_material_count`, `followup`, `followup_date`,
  `language`, `language_basis`, `religion`/`origin` (solo si la persona lo
  compartió: `shared_by_person`), `client_request_id` (idempotencia).
- `outreach_visits` = PERSONA contactada (sigue siendo la que se vincula con
  Persona 360 y Consolidación; se crea con el mismo núcleo de siempre).
- `outreach_participations.active_street` = la calle activa del mentor
  (historial de calles en `street_sessions`, ver door_streets.py).

Reglas: el registro en la calle NUNCA se bloquea por inventario (los libros
se descuentan del inventario del mentor si se puede; si no, quedan
"sin descuento de inventario" para conciliar) ni por un contacto repetido.
El doble toque no duplica: la misma `client_request_id` devuelve lo ya guardado."""
import logging
import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from pymongo.errors import DuplicateKeyError

from mentorship_outreach import (
    OUTREACH_PROCESS_KEY, campaign_roster, can_use_outreach, is_active_mentor, is_outreach_leader,
    mark_participation_active, now_utc, resolve_and_insert_contact_visit, serialize, serialize_visits, supervision_snapshot,
)
from server import db, get_current_user

router = APIRouter(prefix="/api/mentorship/outreach", tags=["outreach-doors"])

DOOR_DELIVERY_HOLDER = {"type": "writeoff", "id": "door_delivery"}
CONVERSED = {"conversation", "invited_in"}
ACTIONS = Literal["invitation", "prayer", "book", "other_material"]


class StreetInput(BaseModel):
    street_name: str = Field(min_length=2, max_length=160)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    location_accuracy_m: Optional[float] = Field(default=None, ge=0, le=100000)
    location_source: Optional[Literal["gps", "manual"]] = None


class BookEntry(BaseModel):
    # "MCD", "NPT" o el book_id de otro material del inventario.
    book: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=50)


class PersonEntry(BaseModel):
    contact_type: Literal["new", "existing"] = "new"
    person_id: Optional[str] = None
    contact_name: Optional[str] = Field(default=None, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=40)


class AttemptInput(BaseModel):
    client_request_id: str = Field(min_length=8, max_length=80)
    opened: bool
    contact_level: Optional[Literal["brief", "conversation", "invited_in"]] = None
    actions: list[ACTIONS] = Field(default_factory=list, max_length=4)
    books: list[BookEntry] = Field(default_factory=list, max_length=10)
    other_material_count: int = Field(default=0, ge=0, le=200)
    followup: Literal["yes", "no", "not_asked"] = "not_asked"
    followup_date: Optional[date] = None
    # L2: seguimiento con responsable y próxima acción (mismo modelo que Consolidación; no la inicia).
    followup_next_action: Optional[str] = Field(default=None, max_length=160)
    followup_responsible_person_id: Optional[str] = Field(default=None, max_length=80)
    # MT1: resultados de la vivienda. «Solicitaron regresar» pide fecha; «No desean más visitas»
    # la retira de pendientes (el historial se conserva).
    outcome: Optional[Literal["requested_return", "no_more_visits"]] = None
    return_date: Optional[date] = None
    language: Optional[Literal["es", "en", "other", "unknown"]] = None
    language_other: Optional[str] = Field(default=None, max_length=60)
    language_basis: Optional[Literal["confirmed", "impression"]] = None
    # Solo si la persona lo compartió (nunca se infiere por apariencia); religión y origen van separados.
    religion: Optional[str] = Field(default=None, max_length=80)
    origin: Optional[str] = Field(default=None, max_length=80)
    shared_by_person: bool = False
    person: Optional[PersonEntry] = None
    note: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check(self):
        if (self.religion or self.origin) and not self.shared_by_person:
            raise ValueError("Religión u origen solo se registran si la persona lo compartió")
        if self.followup_date and self.followup != "yes":
            raise ValueError("Solo se programa seguimiento si la persona lo aceptó")
        if self.outcome and not self.opened:
            raise ValueError("Ese resultado solo se registra si abrieron")
        if self.outcome == "requested_return" and not self.return_date:
            raise ValueError("Indique la fecha en que pidieron que regresen")
        if self.return_date and self.outcome != "requested_return":
            raise ValueError("La fecha de regreso va con «Solicitaron regresar»")
        return self


class DoorInput(AttemptInput):
    house_number: str = Field(min_length=1, max_length=20)
    unit: Optional[str] = Field(default=None, max_length=20)
    street_name: Optional[str] = Field(default=None, max_length=160)


def _norm(text: Optional[str]) -> str:
    value = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", value)).strip()


def door_key(street: str, number: str, unit: Optional[str]) -> str:
    """Misma puerta aunque se escriba distinto ("Calle 18 #2" / "calle 18, 2")."""
    unit_key = re.sub(r"^(apt|apto|apartamento|unit|depto|dpto|suite|ste)\s*", "", _norm(unit))
    return f"{_norm(street)}|{_norm(number).replace(' ', '')}|{unit_key.replace(' ', '')}"


UNIT_PREFIX = re.compile(r"^(apt|apto|apartamento|unit|depto|dpto|suite|ste)\.?\s*#?\s*", re.IGNORECASE)


def door_address(street: str, number: str, unit: Optional[str]) -> tuple[str, Optional[str]]:
    clean_unit = UNIT_PREFIX.sub("", (unit or "").strip()).strip()
    return f"{number.strip()} {street.strip()}", (f"Apt {clean_unit}" if clean_unit else None)


async def _participant_check(campaign_id: str, current_user: dict) -> str:
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para registrar visitas")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "campaign_id": 1, "assigned_mentor_ids": 1, "status": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    mentor_person_id = current_user.get("person_id")
    if not mentor_person_id or not await is_active_mentor(mentor_person_id):
        raise HTTPException(status_code=409, detail="Necesita insignia de Mentor activa para registrar viviendas")
    if mentor_person_id not in (campaign.get("assigned_mentor_ids") or []) and not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="No está en el roster de mentores de esta invasión")
    return mentor_person_id


# ------------------------------------------------------------------ calle activa
# Rutas de la calle activa («Comenzar/Cambiar/Terminar/Reabrir calle»): door_streets.py


# ------------------------------------------------------------------ libros
async def discount_books(entries: list[BookEntry], mentor_person_id: str, target_person_id: Optional[str], campaign_id: Optional[str], actor_user_id: str,
                         *, base_key: Optional[str] = None, household_id: Optional[str] = None, visit_event_id: Optional[str] = None, visit_id: Optional[str] = None) -> list[dict]:
    """Descuenta del inventario del mentor (Librería 360). Nunca lanza error:
    si el libro no está cargado o no hay existencias, queda en la bitácora
    como entrega pendiente de conciliar (no resta del saldo del mentor).
    Cada fila lleva su clave (doble toque) y el vínculo con vivienda/intento/visita."""
    from library_ledger import record_pending_delivery
    from library_module import HolderInput, MovementInput, apply_movement
    mentor_user = await db.users.find_one({"person_id": mentor_person_id}, {"_id": 1})
    links = {"household_id": household_id, "visit_event_id": visit_event_id, "visit_id": visit_id}
    rows = []
    for index, entry in enumerate(entries):
        key = entry.book.strip()
        book = await db.library_books.find_one({"$or": [{"sku": key.upper()}, {"book_id": key}], "is_active": True}, {"_id": 0, "book_id": 1, "name": 1, "sku": 1})
        row = {"book": key, "book_id": (book or {}).get("book_id"), "sku": (book or {}).get("sku") or (key.upper() if key.upper() in {"MCD", "NPT"} else None),
               "name": (book or {}).get("name") or key, "quantity": entry.quantity, "inventory_status": "not_discounted", "movement_id": None, "reason": None}
        if not book:
            row["reason"] = "El libro no está cargado en Librería 360"
        elif not mentor_user:
            row["reason"] = "El mentor no tiene cuenta con inventario"
        else:
            to_holder = {"type": "person", "id": target_person_id} if target_person_id else DOOR_DELIVERY_HOLDER
            try:
                movement = await apply_movement(MovementInput(
                    book_id=book["book_id"], movement_type="DELIVERY", quantity=entry.quantity,
                    from_holder=HolderInput(type="user", id=str(mentor_user["_id"])), to_holder=HolderInput(**to_holder),
                    person_id=target_person_id, process_key=OUTREACH_PROCESS_KEY, campaign_id=campaign_id,
                    notes="Entregado en la puerta (invasión)" if not target_person_id else "Entrega en visita de invasión",
                    idempotency_key=f"door:{base_key}:{index}" if base_key else None, **links,
                    # Identificado si hay persona contactada (con nombre) en el mismo intento; si no, queda para completar.
                    recipient_status="identified" if (target_person_id or visit_id) else "unidentified",
                ), actor_user_id)
                row.update({"inventory_status": "discounted", "movement_id": movement["movement_id"]})
            except HTTPException as exc:
                row["reason"] = "Sin existencias en el inventario del mentor" if exc.status_code == 409 else str(exc.detail)
            except Exception:  # noqa: BLE001 — en la calle nunca se bloquea el registro
                row["reason"] = "No se pudo descontar del inventario"
        if row["inventory_status"] != "discounted" and visit_event_id:
            try:
                pending = await record_pending_delivery(
                    book_id=row["book_id"], book_label=row["name"], quantity=entry.quantity, mentor_user_id=str(mentor_user["_id"]) if mentor_user else None,
                    person_id=target_person_id, campaign_id=campaign_id, process_key=OUTREACH_PROCESS_KEY, idempotency_key=f"door-pending:{visit_event_id}:{index}",
                    reason=row["reason"] or "Sin descuento de inventario", actor_user_id=actor_user_id, **links)
                row["movement_id"] = pending["movement_id"]
            except Exception:  # noqa: BLE001
                logging.getLogger(__name__).warning("No se pudo registrar la entrega pendiente", exc_info=True)
        rows.append(row)
    return rows


# ------------------------------------------------------------------ seguimiento (L2)
DEFAULT_NEXT_ACTION = "Visitar de nuevo"


def followup_plan(accepted: bool, responsible_person_id: Optional[str], next_action: Optional[str], when: Optional[date]) -> dict:
    """Campos de seguimiento en la persona contactada: responsable, próxima acción
    y fecha (`next_action` / `next_action_at`, como en Consolidación). Aceptar
    seguimiento NO inicia Consolidación."""
    from datetime import datetime, time, timezone
    if not accepted:
        return {"followup_accepted": False}
    return {"followup_accepted": True, "followup_responsible_person_id": responsible_person_id, "next_action": (next_action or "").strip() or DEFAULT_NEXT_ACTION,
            "next_action_at": datetime.combine(when, time(12, 0), tzinfo=timezone.utc) if when else None, "followup_set_at": now_utc()}


class FollowupInput(BaseModel):
    accepted: bool = True
    responsible_person_id: Optional[str] = Field(default=None, max_length=80)
    next_action: Optional[str] = Field(default=None, max_length=160)
    next_action_date: Optional[date] = None


@router.put("/visits/{visit_id}/followup", response_model=dict)
async def set_visit_followup(visit_id: str, payload: FollowupInput, current_user: dict = Depends(get_current_user)):
    """Editar el seguimiento aceptado (responsable, próxima acción y fecha)."""
    from mentorship_outreach import load_visit, log_visit_history
    visit = await load_visit(visit_id)
    if not is_outreach_leader(current_user) and visit.get("mentor_person_id") != current_user.get("person_id"):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder puede cambiar el seguimiento")
    responsible = payload.responsible_person_id or visit.get("followup_responsible_person_id") or visit.get("mentor_person_id")
    if responsible != visit.get("mentor_person_id") and not await is_active_mentor(responsible):
        raise HTTPException(status_code=422, detail="El responsable debe ser un mentor activo")
    fields = followup_plan(payload.accepted, responsible, payload.next_action, payload.next_action_date)
    if payload.accepted and visit.get("status") in {"visited", "assigned"}:
        fields["status"] = "wants_followup"
    fields["updated_at"] = now_utc()
    await db.outreach_visits.update_one({"visit_id": visit_id}, {"$set": fields})
    await log_visit_history(visit_id, current_user, "followup_updated", {key: value for key, value in fields.items() if key != "updated_at"})
    return serialize(await db.outreach_visits.find_one({"visit_id": visit_id}, {"_id": 0}))


# ------------------------------------------------------------------ estado de la puerta
async def refresh_door_status(household_id: str) -> None:
    """Estado derivado del historial completo (no se pierde ningún intento):
    sin respuesta → pendiente de nueva visita; abrieron → ya no está pendiente."""
    events = await db.outreach_visit_events.find({"household_id": household_id, "is_draft": {"$ne": True}}, {"_id": 0, "opened": 1, "result": 1, "occurred_at": 1, "followup": 1, "followup_date": 1, "contact_level": 1, "books_total": 1,
                                                                                                         "outcome": 1, "return_date": 1}).sort("occurred_at", 1).to_list(500)
    household = await db.outreach_households.find_one({"household_id": household_id}, {"_id": 0, "next_visit_date": 1, "next_visit_set_at": 1}) or {}
    # Próxima visita programada a mano («Programar»/«Reprogramar»): vale si es posterior al último intento.
    manual = household.get("next_visit_date") if household.get("next_visit_set_at") and (not events or household["next_visit_set_at"] >= events[-1].get("occurred_at")) else None
    if not events:
        await db.outreach_households.update_one({"household_id": household_id}, {"$set": {"attempts_count": 0, "door_status": "followup_scheduled" if manual else None, "last_result": None, "last_attempt_at": None,
                                                                                   "conversed_ever": False, "books_total": 0, "followup_date": manual}})
        return
    last = events[-1]
    opened = event_opened(last)
    # Cada visita resuelve el pendiente anterior: solo cuenta el seguimiento del ÚLTIMO intento (o uno programado después).
    followup_date = manual or (last.get("return_date") if last.get("outcome") == "requested_return" else None) or (last.get("followup_date") if last.get("followup") == "yes" else None)
    status = "followup_scheduled" if followup_date else ("opened" if opened else "pending_revisit")
    if last.get("outcome") == "no_more_visits" and not manual:
        status, followup_date = "no_more_visits", None  # sale de pendientes; el historial queda
    await db.outreach_households.update_one({"household_id": household_id}, {"$set": {
        "attempts_count": len(events), "opened_ever": any(event_opened(item) for item in events), "door_status": status,
        "conversed_ever": any(item.get("contact_level") in CONVERSED for item in events), "books_total": sum(item.get("books_total") or 0 for item in events),
        "last_result": last.get("outcome") or ("opened" if opened else "no_answer"), "last_attempt_at": last.get("occurred_at"), "followup_date": followup_date,
    }})


def event_opened(event: dict) -> bool:
    if event.get("opened") is not None:
        return bool(event["opened"])
    return event.get("result") in {"contacted", "refused"}


# ------------------------------------------------------------------ intento
async def _existing_attempt(client_request_id: str, current_user: dict) -> Optional[dict]:
    event = await db.outreach_visit_events.find_one({"client_request_id": client_request_id}, {"_id": 0})
    if not event:
        return None
    if event.get("created_by_user_id") != current_user["user_id"]:
        raise HTTPException(status_code=409, detail="Esa clave de registro ya fue usada")
    return await attempt_response(event, current_user, duplicate=True)


async def attempt_response(event: dict, current_user: dict, duplicate: bool = False, person_warning: Optional[str] = None) -> dict:
    household = await db.outreach_households.find_one({"household_id": event["household_id"]}, {"_id": 0})
    visits = await db.outreach_visits.find({"visit_event_id": event["visit_event_id"], "archived": {"$ne": True}}, {"_id": 0}).to_list(20)
    return {"household": serialize(household), "event": serialize(event), "visits": await serialize_visits(visits, current_user),
            "duplicate": duplicate, "person_warning": person_warning or event.get("person_warning"), "saved_at": serialize(event.get("created_at"))}


async def record_attempt(household: dict, payload: AttemptInput, current_user: dict, street_session_id: Optional[str] = None) -> dict:
    mentor_person_id = household["mentor_person_id"]
    opened = payload.opened
    now = now_utc()
    event_id = str(uuid4())
    event = {
        "_id": event_id, "visit_event_id": event_id, "household_id": household["household_id"], "campaign_id": household.get("campaign_id"),
        "mentor_person_id": mentor_person_id, "result": "contacted" if opened else "no_answer", "opened": opened,
        "contact_level": payload.contact_level if opened else None,
        "actions": sorted(set(payload.actions + (["book"] if payload.books else []) + (["other_material"] if payload.other_material_count else []))),
        "books": [], "books_total": sum(item.quantity for item in payload.books), "other_material_count": payload.other_material_count,
        "followup": payload.followup if opened else "not_asked", "followup_date": payload.followup_date.isoformat() if opened and payload.followup_date else None,
        "language": payload.language if opened else None, "language_other": ((payload.language_other or "").strip() or None) if opened else None,
        "language_basis": (payload.language_basis or ("confirmed" if payload.language in {"es", "en", "other"} else None)) if opened else None,
        "religion": ((payload.religion or "").strip() or None) if opened else None, "origin": ((payload.origin or "").strip() or None) if opened else None,
        "shared_by_person": bool(payload.shared_by_person and opened and (payload.religion or payload.origin)),
        "note": (payload.note or "").strip() or None, "is_draft": False, "client_request_id": payload.client_request_id,
        "outcome": payload.outcome if opened else None, "return_date": payload.return_date.isoformat() if opened and payload.return_date else None,
        "occurred_at": now, "created_by_user_id": current_user["user_id"], "created_at": now, "source": "door_to_door",
        "street_session_id": street_session_id,
    }
    if not opened:
        # No abrieron: se guarda sin preguntas (no se inventan datos de la persona).
        event["actions"] = [item for item in event["actions"] if item in {"book", "other_material"}]
    try:
        await db.outreach_visit_events.insert_one(event)
    except DuplicateKeyError:
        existing = await _existing_attempt(payload.client_request_id, current_user)
        if existing:
            return existing
        raise
    # Persona contactada (opcional): mismo núcleo de siempre (Persona 360, duplicados por teléfono).
    person_warning = None
    visit = None
    person = payload.person
    if opened and person and (person.person_id or (person.contact_name or "").strip() or (person.contact_phone or "").strip()):
        name = (person.contact_name or "").strip() or "Contacto sin nombre"
        try:
            visit = await resolve_and_insert_contact_visit(
                person.contact_type, person.person_id, name, person.contact_phone, household.get("street_name") or household.get("sector"),
                household.get("campaign_id"), mentor_person_id, event["note"], current_user, household_id=household["household_id"], visit_event_id=event_id,
            )
            status = "wants_followup" if payload.followup == "yes" else "visited"
            followup_fields = followup_plan(payload.followup == "yes", payload.followup_responsible_person_id or mentor_person_id, payload.followup_next_action, payload.followup_date)
            await db.outreach_visits.update_one({"visit_id": visit["visit_id"]}, {"$set": {
                "status": status, "visit_date": date.today().isoformat(), "address_line1": household.get("address_line1"), "address_line2": household.get("address_line2"),
                "language": event["language"], "agreed_start_date": event["followup_date"], "updated_at": now, **followup_fields,
            }})
            visit["status"] = status
        except HTTPException as exc:
            # Nunca bloquear la calle: el intento queda guardado y se avisa.
            person_warning = exc.detail if isinstance(exc.detail, str) else "No se pudo registrar a la persona; el intento quedó guardado"
    target_person_id = visit.get("person_id") if visit and visit.get("contact_type") == "existing" else None
    books = await discount_books(payload.books, mentor_person_id, target_person_id, household.get("campaign_id"), current_user["user_id"],
                                 base_key=payload.client_request_id, household_id=household["household_id"], visit_event_id=event_id,
                                 visit_id=(visit or {}).get("visit_id")) if payload.books else []
    if visit and books:
        from mentorship_outreach import link_visit_books
        await link_visit_books({**visit, "visit_event_id": event_id}, target_person_id)  # «Recibió MCD/NPT» en la visita
    updates = {"books": books, "books_inventory_pending": any(item["inventory_status"] != "discounted" for item in books)}
    if person_warning:
        updates["person_warning"] = person_warning
    await db.outreach_visit_events.update_one({"visit_event_id": event_id}, {"$set": updates})
    event.update(updates)
    # La nueva visita resuelve la próxima visita programada antes (se puede programar otra).
    await db.outreach_households.update_one({"household_id": household["household_id"]}, {"$set": {"next_visit_date": None, "next_visit_set_at": None}})
    await refresh_door_status(household["household_id"])
    if household.get("campaign_id"):
        await mark_participation_active(household["campaign_id"], mentor_person_id)
        from invasion_participants import mark_attended_from_activity
        await mark_attended_from_activity(household["campaign_id"], mentor_person_id)
    return await attempt_response(event, current_user, person_warning=person_warning)


@router.post("/campaigns/{campaign_id}/doors", response_model=dict, status_code=201)
async def register_door(campaign_id: str, payload: DoorInput, current_user: dict = Depends(get_current_user)):
    """Vivienda en la calle activa (solo número y apartamento) + su intento,
    en un solo toque. La misma puerta nunca se duplica: un segundo registro
    agrega un intento al historial de la misma vivienda."""
    existing = await _existing_attempt(payload.client_request_id, current_user)
    if existing:
        return existing
    mentor_person_id = await _participant_check(campaign_id, current_user)
    from door_streets import close_if_stale
    await close_if_stale(campaign_id, mentor_person_id)
    street_name = (payload.street_name or "").strip()
    participation = await db.outreach_participations.find_one({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id}, {"_id": 0, "active_street": 1})
    street = (participation or {}).get("active_street") or {}
    if not street_name:
        street_name = street.get("street_name") or ""
    if not street_name:
        raise HTTPException(status_code=422, detail="Primero pulse «Comenzar calle»")
    key = door_key(street_name, payload.house_number, payload.unit)
    household = await db.outreach_households.find_one({"campaign_id": campaign_id, "door_key": key, "archived": {"$ne": True}}, {"_id": 0})
    if household and household.get("mentor_person_id") not in (None, mentor_person_id) and not is_outreach_leader(current_user):
        raise HTTPException(status_code=409, detail="Esta vivienda ya la tiene otro mentor de la invasión")
    if household and not household.get("mentor_person_id"):
        household = await claim_for(household, mentor_person_id)
    if not household:
        household = await create_door(campaign_id, street_name, payload.house_number, payload.unit, key, mentor_person_id, street if _norm(street.get("street_name")) == _norm(street_name) else {}, current_user)
    # El intento queda en el tramo de la calle activa (para el inicio/fin y duración de la calle).
    session_id = street.get("street_session_id") if _norm(street.get("street_name")) == _norm(street_name) else None
    return await record_attempt(household, payload, current_user, session_id)


async def claim_for(household: dict, mentor_person_id: str) -> dict:
    snapshot = await supervision_snapshot(mentor_person_id)
    updated = await db.outreach_households.find_one_and_update(
        {"household_id": household["household_id"], "mentor_person_id": None},
        {"$set": {"mentor_person_id": mentor_person_id, "status": "assigned", "claimed_at": now_utc(), "updated_at": now_utc(),
                  "front_group_id": snapshot["front_group_id"], "front_group_ancestor_ids": snapshot["front_group_ancestor_ids"]}},
        return_document=True, projection={"_id": 0})
    if not updated:
        raise HTTPException(status_code=409, detail="Esta vivienda la acaba de tomar otro mentor")
    return updated


async def create_door(campaign_id: str, street_name: str, number: str, unit: Optional[str], key: str, mentor_person_id: str, street: dict, current_user: dict) -> dict:
    snapshot = await supervision_snapshot(mentor_person_id)
    now = now_utc()
    household_id = str(uuid4())
    line1, line2 = door_address(street_name, number, unit)
    doc = {
        "_id": household_id, "household_id": household_id, "campaign_id": campaign_id, "mentor_person_id": mentor_person_id, "status": "assigned",
        "street_name": street_name.strip(), "house_number": number.strip(), "unit": (unit or "").strip() or None, "door_key": key,
        "address_line1": line1, "address_line2": line2, "address_city": None, "address_state": None, "address_zip": None,
        "sector": None, "note": None, "is_draft": False, "front_group_id": snapshot["front_group_id"], "front_group_ancestor_ids": snapshot["front_group_ancestor_ids"],
        "archived": False, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
        "location_reference": None, "latitude": None, "longitude": None, "attempts_count": 0, "door_status": None, "source": "door_to_door",
    }
    if street.get("latitude") is not None:
        # Ubicación aproximada: el punto confirmado de la calle (se corrige desde el mapa).
        doc.update({"latitude": street["latitude"], "longitude": street["longitude"], "location_accuracy_m": street.get("location_accuracy_m"),
                    "location_source": "manual", "location_approx": True, "location_reference": f"Ubicación aproximada: inicio de {street_name.strip()}", "location_updated_at": now})
    try:
        await db.outreach_households.insert_one(doc)
    except DuplicateKeyError:
        # Dos toques simultáneos con distinta clave para la misma puerta: se usa la que quedó.
        existing = await db.outreach_households.find_one({"campaign_id": campaign_id, "door_key": key}, {"_id": 0})
        if existing.get("mentor_person_id") != mentor_person_id:
            raise HTTPException(status_code=409, detail="Esta vivienda ya la tiene otro mentor de la invasión")
        return existing
    return doc


@router.post("/households/{household_id}/attempts", response_model=dict, status_code=201)
async def register_attempt(household_id: str, payload: AttemptInput, current_user: dict = Depends(get_current_user)):
    """Nueva visita a una vivienda existente: se agrega a SU historial."""
    existing = await _existing_attempt(payload.client_request_id, current_user)
    if existing:
        return existing
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para registrar visitas")
    household = await db.outreach_households.find_one({"household_id": household_id, "archived": {"$ne": True}}, {"_id": 0})
    if not household:
        raise HTTPException(status_code=404, detail="Vivienda no encontrada")
    person_id = current_user.get("person_id")
    if not household.get("mentor_person_id"):
        if person_id not in await campaign_roster(household.get("campaign_id")) or not await is_active_mentor(person_id):
            raise HTTPException(status_code=403, detail="Solo un mentor de esta invasión puede tomar esta vivienda")
        household = await claim_for(household, person_id)
    elif household["mentor_person_id"] != person_id and not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder puede registrar visitas en esta vivienda")
    return await record_attempt(household, payload, current_user)


# ------------------------------------------------------------------ pendientes y próxima visita
class NextVisitInput(BaseModel):
    next_visit_date: Optional[date] = None  # None = quitar la programación
    note: Optional[str] = Field(default=None, max_length=300)


async def household_for_edit(household_id: str, current_user: dict) -> dict:
    from household_location import campaign_doc, sees_whole_campaign
    household = await db.outreach_households.find_one({"household_id": household_id, "archived": {"$ne": True}}, {"_id": 0})
    if not household:
        raise HTTPException(status_code=404, detail="Vivienda no encontrada")
    if household.get("mentor_person_id") != current_user.get("person_id") and not sees_whole_campaign(current_user, await campaign_doc(household.get("campaign_id"))):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder de la invasión")
    return household


@router.put("/households/{household_id}/next-visit", response_model=dict)
async def set_next_visit(household_id: str, payload: NextVisitInput, current_user: dict = Depends(get_current_user)):
    """«Programar» / «Reprogramar» la próxima visita sin registrar un intento."""
    await household_for_edit(household_id, current_user)
    await db.outreach_households.update_one({"household_id": household_id}, {"$set": {
        "next_visit_date": payload.next_visit_date.isoformat() if payload.next_visit_date else None,
        "next_visit_set_at": now_utc() if payload.next_visit_date else None, "next_visit_note": (payload.note or "").strip() or None,
        "next_visit_set_by_user_id": current_user["user_id"], "updated_at": now_utc()}})
    await refresh_door_status(household_id)
    return serialize(await db.outreach_households.find_one({"household_id": household_id}, {"_id": 0}))


@router.get("/campaigns/{campaign_id}/pending-doors", response_model=dict)
async def pending_doors(campaign_id: str, status: Literal["all", "pending_revisit", "followup_scheduled"] = "all", offset: int = 0, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Pendientes de nueva visita y seguimientos programados. El mentor ve los
    suyos; quien ve toda la invasión, todos con su mentor y equipo."""
    from household_location import campaign_doc, sees_whole_campaign
    campaign = await campaign_doc(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    full = sees_whole_campaign(current_user, campaign)
    if not full and not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar viviendas")
    query: dict = {"campaign_id": campaign_id, "archived": {"$ne": True},
                   "door_status": {"$in": ["pending_revisit", "followup_scheduled"]} if status == "all" else status}
    if not full:
        query["mentor_person_id"] = current_user.get("person_id") or "-"
    limit = max(1, min(limit, 100))
    total = await db.outreach_households.count_documents(query)
    keys = {"_id": 0, "household_id": 1, "address_line1": 1, "address_line2": 1, "street_name": 1, "house_number": 1, "unit": 1, "door_status": 1, "last_result": 1,
            "last_attempt_at": 1, "attempts_count": 1, "followup_date": 1, "next_visit_note": 1, "latitude": 1, "longitude": 1, "location_approx": 1, "location_source": 1,
            "mentor_person_id": 1, "front_group_id": 1}
    # Primero las fechas programadas (atrasadas arriba), luego las sin respuesta más antiguas.
    items = await db.outreach_households.find(query, keys).sort([("followup_date", 1), ("last_attempt_at", 1)]).to_list(2000)
    items.sort(key=lambda item: (item.get("followup_date") is None, item.get("followup_date") or "", str(item.get("last_attempt_at") or "")))
    items = items[offset:offset + limit]
    from mentorship_outreach import person_display_name
    names = {pid: await person_display_name(pid) for pid in {item.get("mentor_person_id") for item in items} if pid}
    teams = {doc["front_group_id"]: doc.get("name") async for doc in db.front_groups.find({"front_group_id": {"$in": list({item.get("front_group_id") for item in items if item.get("front_group_id")})}}, {"_id": 0, "front_group_id": 1, "name": 1})}
    today = date.today().isoformat()
    for item in items:
        item["mentor_name"] = names.get(item.get("mentor_person_id"))
        item["team_name"] = teams.get(item.get("front_group_id"))
        item["overdue"] = bool(item.get("followup_date") and item["followup_date"] < today)
        item["mine"] = item.get("mentor_person_id") == current_user.get("person_id")
    return {"total": total, "scope": "all" if full else "mine", "items": serialize(items)}


# ------------------------------------------------------------------ resumen del mentor
SUMMARY_METRICS = ("visited", "no_answer", "opened", "conversed", "books", "consolidation")


async def summary_scope(campaign_id: str, current_user: dict, mentor_person_id: Optional[str]) -> dict:
    """El mentor ve SOLO su trabajo; consultar a otro mentor queda para la
    supervisión (Mi Trabajo · MT3)."""
    if mentor_person_id and mentor_person_id != current_user.get("person_id") and not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Solo puede consultar su propio trabajo")
    person_id = mentor_person_id or current_user.get("person_id")
    if not person_id or not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar visitas")
    return {"campaign_id": campaign_id, "mentor_person_id": person_id, "archived": {"$ne": True}}


@router.get("/campaigns/{campaign_id}/door-summary", response_model=dict)
async def door_summary(campaign_id: str, mentor_person_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Resumen compacto en UNA consulta agregada sobre las viviendas (estado
    derivado de su historial) + personas en Consolidación de esta invasión."""
    match = await summary_scope(campaign_id, current_user, mentor_person_id)
    facet = await db.outreach_households.aggregate([
        {"$match": {**match, "attempts_count": {"$gt": 0}}},
        {"$group": {"_id": None, "visited": {"$sum": 1}, "opened": {"$sum": {"$cond": ["$opened_ever", 1, 0]}},
                    "conversed": {"$sum": {"$cond": ["$conversed_ever", 1, 0]}}, "books": {"$sum": {"$ifNull": ["$books_total", 0]}},
                    "attempts": {"$sum": "$attempts_count"}, "pending_revisit": {"$sum": {"$cond": [{"$eq": ["$door_status", "pending_revisit"]}, 1, 0]}}}},
    ]).to_list(1)
    totals = facet[0] if facet else {"visited": 0, "opened": 0, "conversed": 0, "books": 0, "attempts": 0, "pending_revisit": 0}
    consolidation = await db.outreach_visits.count_documents({**match, "enrollment_id": {"$nin": [None, ""]}})
    return {"campaign_id": campaign_id, "mentor_person_id": match["mentor_person_id"], "visited": totals["visited"], "opened": totals["opened"],
            "no_answer": totals["visited"] - totals["opened"], "conversed": totals["conversed"], "books": totals["books"],
            "attempts": totals["attempts"], "pending_revisit": totals["pending_revisit"], "consolidation": consolidation}


@router.get("/campaigns/{campaign_id}/door-summary/{metric}", response_model=dict)
async def door_summary_list(campaign_id: str, metric: str, mentor_person_id: Optional[str] = None, offset: int = 0, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Las direcciones y registros que componen cada cifra (paginado)."""
    if metric not in SUMMARY_METRICS:
        raise HTTPException(status_code=404, detail="Indicador desconocido")
    match = await summary_scope(campaign_id, current_user, mentor_person_id)
    limit = max(1, min(limit, 100))
    if metric == "consolidation":
        query = {**match, "enrollment_id": {"$nin": [None, ""]}}
        total = await db.outreach_visits.count_documents(query)
        visits = await db.outreach_visits.find(query, {"_id": 0}).sort("converted_at", -1).skip(offset).limit(limit).to_list(limit)
        return {"metric": metric, "total": total, "items": await serialize_visits(visits, current_user)}
    query = {**match, "attempts_count": {"$gt": 0}}
    query.update({"no_answer": {"opened_ever": {"$ne": True}}, "opened": {"opened_ever": True}, "conversed": {"conversed_ever": True},
                  "books": {"books_total": {"$gt": 0}}}.get(metric, {}))
    total = await db.outreach_households.count_documents(query)
    keys = {"_id": 0, "household_id": 1, "address_line1": 1, "address_line2": 1, "street_name": 1, "house_number": 1, "unit": 1, "door_status": 1,
            "last_result": 1, "last_attempt_at": 1, "attempts_count": 1, "books_total": 1, "followup_date": 1, "latitude": 1, "longitude": 1, "location_approx": 1}
    items = await db.outreach_households.find(query, keys).sort("last_attempt_at", -1).skip(offset).limit(limit).to_list(limit)
    return {"metric": metric, "total": total, "items": serialize(items)}


@router.get("/door-books", response_model=dict)
async def door_books(current_user: dict = Depends(get_current_user)):
    """Libros para entregar en la puerta: el inventario del mentor + MCD/NPT
    siempre visibles (si no hay existencias se registran para conciliar)."""
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso")
    user_id = current_user["user_id"]
    holdings = {row["book_id"]: row.get("quantity_on_hand", 0) async for row in db.library_holdings.find({"holder_type": "user", "holder_id": user_id}, {"_id": 0, "book_id": 1, "quantity_on_hand": 1})}
    books = await db.library_books.find({"$or": [{"book_id": {"$in": list(holdings)}}, {"sku": {"$in": ["MCD", "NPT"]}}], "is_active": True}, {"_id": 0, "book_id": 1, "sku": 1, "name": 1}).to_list(100)
    items = [{"book": book.get("sku") if book.get("sku") in {"MCD", "NPT"} else book["book_id"], "sku": book.get("sku"), "name": book["name"], "on_hand": holdings.get(book["book_id"], 0)} for book in books]
    for sku, name in (("MCD", "Mi Conexión con Dios"), ("NPT", "Nací para Triunfar")):
        if not any(item["sku"] == sku for item in items):
            items.append({"book": sku, "sku": sku, "name": name, "on_hand": 0})
    items.sort(key=lambda item: ({"MCD": 0, "NPT": 1}.get(item["sku"], 2), item["name"]))
    return {"items": items}


# ------------------------------------------------------------------ migración segura
async def migrate_legacy_visits() -> dict:
    """Idempotente y sin borrar nada: cada visita de una invasión que aún no
    tiene vivienda pasa a ser una vivienda (id determinista `mig-<visit_id>`)
    con un intento (`client_request_id` = `migration:<visit_id>`). Conserva
    persona, Persona 360, expediente de Consolidación y entregas de libros.
    Las visitas sin invasión quedan como «Persona sin vivienda». También
    completa el estado de puerta de las viviendas existentes."""
    created_households = created_events = 0
    async for visit in db.outreach_visits.find({"household_id": None, "campaign_id": {"$nin": [None, ""]}, "archived": {"$ne": True}}, {"_id": 0}):
        household_id = f"mig-{visit['visit_id']}"
        address = (visit.get("address_line1") or "").strip()
        line1 = address or (visit.get("contact_zone") or "").strip() or None
        when = visit.get("created_at") or now_utc()
        result = await db.outreach_households.update_one({"household_id": household_id}, {"$setOnInsert": {
            "_id": household_id, "household_id": household_id, "campaign_id": visit["campaign_id"], "mentor_person_id": visit.get("mentor_person_id"),
            "status": "assigned" if visit.get("mentor_person_id") else "available", "address_line1": line1, "address_line2": visit.get("address_line2"),
            "address_city": visit.get("address_city"), "address_state": visit.get("address_state"), "address_zip": visit.get("address_zip"),
            "sector": visit.get("contact_zone"), "note": None, "is_draft": False, "street_name": None, "house_number": None, "unit": None,
            "front_group_id": visit.get("front_group_id"), "front_group_ancestor_ids": visit.get("front_group_ancestor_ids") or [],
            "latitude": None, "longitude": None, "location_reference": None, "archived": False, "address_incomplete": not address,
            "migrated_from_visit_id": visit["visit_id"], "created_by_user_id": visit.get("created_by_user_id"), "created_at": when, "updated_at": now_utc(),
        }}, upsert=True)
        created_households += int(result.upserted_id is not None)
        event_id = None
        books = await visit_books(visit)
        if visit.get("status") != "assigned" or books:  # "asignada" sin visitar todavía no es un intento (salvo que entregó libro)
            event_id, created = await migration_event(visit, household_id, books)
            created_events += int(created)
        await db.outreach_visits.update_one({"visit_id": visit["visit_id"], "household_id": None}, {"$set": {"household_id": household_id, "visit_event_id": event_id or visit.get("visit_event_id")}})
    # Visitas ya con vivienda pero sin intento, que sí entregaron libro (p. ej. quedaron
    # «asignadas» aunque el mentor entregó el MCD): reciben su intento, una sola vez.
    async for visit in db.outreach_visits.find({"household_id": {"$nin": [None, ""]}, "visit_event_id": {"$in": [None, ""]}, "campaign_id": {"$nin": [None, ""]}, "archived": {"$ne": True}}, {"_id": 0}):
        books = await visit_books(visit)
        if not books and visit.get("status") == "assigned":
            continue
        if await db.outreach_visit_events.count_documents({"household_id": visit["household_id"], "is_draft": {"$ne": True}}, limit=1):
            continue  # la vivienda ya tiene su historial: no se agrega otro intento
        event_id, created = await migration_event(visit, visit["household_id"], books)
        created_events += int(created)
        await db.outreach_visits.update_one({"visit_id": visit["visit_id"], "visit_event_id": {"$in": [None, ""]}}, {"$set": {"visit_event_id": event_id}})
        await refresh_door_status(visit["household_id"])
    # Estado de puerta para viviendas anteriores (derivado; no cambia sus datos).
    refreshed = 0
    async for household in db.outreach_households.find({"$or": [{"attempts_count": {"$exists": False}}, {"conversed_ever": {"$exists": False}}]}, {"_id": 0, "household_id": 1}):
        await refresh_door_status(household["household_id"])
        refreshed += 1
    return {"households": created_households, "events": created_events, "refreshed": refreshed}


async def visit_books(visit: dict) -> int:
    """Libros entregados en esa visita (marcas de la visita o la bitácora de Librería)."""
    marked = int(bool(visit.get("received_mcd") or visit.get("mcd_delivery_movement_id"))) + int(bool(visit.get("received_npt") or visit.get("npt_delivery_movement_id")))
    person_id = visit.get("converted_person_id") or visit.get("person_id")
    query = [{"visit_id": visit["visit_id"]}]
    mentor_user = await db.users.find_one({"person_id": visit.get("mentor_person_id")}, {"_id": 1}) if visit.get("mentor_person_id") else None
    if person_id and mentor_user:
        query.append({"person_id": person_id, "from_holder.type": "user", "from_holder.id": str(mentor_user["_id"])})
    logged = 0
    async for movement in db.library_movements.find({"$or": query, "movement_type": {"$in": ["DELIVERY", "LOAN", "DELIVERY_PENDING"]}, "is_reversal": {"$ne": True}}, {"_id": 0, "quantity": 1}):
        logged += movement.get("quantity") or 1
    return max(marked, logged)


async def migration_event(visit: dict, household_id: str, books: int) -> tuple[str, bool]:
    """Intento determinista `mig-<visit_id>` (idempotente: nunca se duplica)."""
    event_id = f"mig-{visit['visit_id']}"
    opened = visit.get("status") in {"visited", "wants_followup", "rejected"} or books > 0
    when = _aware_dt(visit.get("visit_date")) or visit.get("created_at") or now_utc()
    result = await db.outreach_visit_events.update_one({"visit_event_id": event_id}, {"$setOnInsert": {
        "_id": event_id, "visit_event_id": event_id, "household_id": household_id, "campaign_id": visit["campaign_id"],
        "mentor_person_id": visit.get("mentor_person_id"), "result": "contacted" if opened else "no_answer", "opened": opened,
        "contact_level": None, "actions": ["book"] if books else [],
        "books": [], "books_total": books, "other_material_count": 0,
        "followup": "yes" if visit.get("status") == "wants_followup" else "not_asked", "followup_date": None,
        "note": None, "is_draft": False, "client_request_id": f"migration:{visit['visit_id']}", "migrated": True,
        "occurred_at": when, "created_by_user_id": visit.get("created_by_user_id"), "created_at": when, "source": "migration",
    }}, upsert=True)
    return event_id, result.upserted_id is not None


def _aware_dt(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and len(value) >= 10:
        try:
            return datetime.fromisoformat(f"{value[:10]}T16:00:00+00:00")  # fecha sin hora: mediodía local (América)
        except ValueError:
            return None
    return None


async def ensure_indexes() -> None:
    await db.outreach_visit_events.create_index("client_request_id", unique=True, partialFilterExpression={"client_request_id": {"$type": "string"}})
    await db.outreach_households.create_index([("campaign_id", 1), ("door_key", 1)], unique=True, partialFilterExpression={"door_key": {"$type": "string"}})
    await db.outreach_households.create_index([("campaign_id", 1), ("door_status", 1)])
    try:
        result = await migrate_legacy_visits()
        if any(result.values()):
            logging.getLogger(__name__).info("Migración puerta a puerta: %s", result)
    except Exception:  # noqa: BLE001 — nunca impedir que arranque el servidor
        logging.getLogger(__name__).exception("Migración puerta a puerta pendiente; se reintenta al próximo arranque")
