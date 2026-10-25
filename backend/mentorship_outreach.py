"""Visitas / Invasiones con informe por persona (Fase 2 de Mentoría).

Construido sobre lo existente: reutiliza `assert_mentor_eligible`, `assign_mentor`,
`configure_entry_stages` y `create_enrollment` de Consolidación v2, y `mentor_badges` /
`mentor_qualifications` de `mentorship.py` (Fase 1). No duplica esas colecciones.

Reglas de acceso (ver requisito 9 del dueño):
- `mentorship.outreach.assign` (o autoridad pastoral): ve y asigna/reasigna TODO, crea
  campañas, abre el panel de líderes.
- `mentorship.outreach.report`: puede rendir informe (igual que un mentor con insignia).
- Un mentor con insignia activa (`mentor_badges`) puede usar el módulo aunque no tenga
  ninguna capability: solo ve y edita SUS PROPIAS visitas, nunca las de otros.
"""
import re
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from access_control import (
    MENTORSHIP_OUTREACH_ASSIGN,
    MENTORSHIP_OUTREACH_REPORT,
    has_capability,
    is_general_coordinator,
    is_global_pastoral_authority,
)
from consolidation_service import assert_mentor_eligible, assign_mentor, configure_entry_stages, load_person, mentor_qualification
from core_governance import UserAccessCreate, create_user_access_core
from front_group_tree import descendant_group_ids, load_group as load_front_group, support_group_ids
from geo_address import normalize_address_document
from geo_service import enqueue_geo_job, pending_geo_fields, process_geo_job
from library_module import CENTRAL_HOLDER, HolderInput, MovementInput, apply_movement, deliver_from_mentor_to_person
from person_matching import PersonQuickCreate, quick_create_person
from process_engine import create_enrollment, now_utc, serialize
from participation_scope import principal_authority_person_ids, without
from server import db, get_current_user


router = APIRouter(prefix="/api/mentorship/outreach", tags=["mentorship-outreach"])

VISIT_STATUSES = ("assigned", "not_found", "visited", "rejected", "wants_followup")
LBS_DECISIONS = ("none", "accepted", "needs_lbs")
CALL_SCHEDULES = ("morning", "midday", "night")
OUTREACH_PROCESS_KEY = "outreach_invasion"
# Etapa 2: "estados de decisión" del contacto, independientes de `status` (que sigue
# describiendo el intento físico de visita). Se derivan de forma determinística de
# `status`/`agreed_start_date` — ver `compute_decision_status` — así la migración es
# idempotente y nunca inventa un dato que no estuviera ya en el registro.
DECISION_STATUSES = ("pending", "no_response", "pending_decision", "desisted", "accepted", "start_scheduled")
ATTEMPT_RESULTS = ("no_answer", "not_home", "refused", "contacted")
PARTICIPATION_STATUSES = ("assigned", "confirmed", "active")


class MentorRosterEntry(BaseModel):
    """Un mentor del roster de la invasión. Si el mentor aún no tiene cuenta,
    `email`/`temporary_password` son obligatorios para auto-crearla en el mismo
    paso (reutiliza `create_user_access_core` con `mentor_access=True`)."""
    person_id: str
    email: Optional[EmailStr] = None
    temporary_password: Optional[str] = Field(default=None, min_length=10, max_length=128)


class AddMentorsInput(BaseModel):
    """Para AGREGAR mentores a una invasión ya creada (pedido explícito del
    dueño): nunca reemplaza el roster. `emails` solo hace falta para quienes
    aún no tienen cuenta — si no se da contraseña, se invita de forma segura
    (igual que el alta normal de usuarios, sin pedirle clave al coordinador)."""
    person_ids: list[str] = Field(default_factory=list, max_length=200)
    front_group_ids: list[str] = Field(default_factory=list, max_length=50)
    emails: dict[str, EmailStr] = Field(default_factory=dict)


class RemoveMentorInput(BaseModel):
    reason: str = Field(min_length=3, max_length=600)


class BookAssignmentEntry(BaseModel):
    mentor_person_id: str
    book_id: str
    quantity: int = Field(gt=0, le=1000)


class BookAssignmentInput(BaseModel):
    assignments: list[BookAssignmentEntry] = Field(min_length=1)


class CampaignInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=300)
    start_date: date
    end_date: date
    zone_notes: Optional[str] = Field(default=None, max_length=1000)
    meeting_time: Optional[str] = Field(default=None, max_length=40)
    meeting_place: Optional[str] = Field(default=None, max_length=300)
    sectors: list[str] = Field(default_factory=list, max_length=50)
    instructions: Optional[str] = Field(default=None, max_length=2000)
    assigned_mentors: list[MentorRosterEntry] = Field(default_factory=list)


class CampaignUpdateInput(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    location: Optional[str] = Field(default=None, min_length=1, max_length=300)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    zone_notes: Optional[str] = Field(default=None, max_length=1000)
    meeting_time: Optional[str] = Field(default=None, max_length=40)
    meeting_place: Optional[str] = Field(default=None, max_length=300)
    sectors: Optional[list[str]] = Field(default=None, max_length=50)
    instructions: Optional[str] = Field(default=None, max_length=2000)
    assigned_mentors: Optional[list[MentorRosterEntry]] = None
    status: Optional[Literal["active", "closed"]] = None


class HouseholdInput(BaseModel):
    campaign_id: Optional[str] = None
    mentor_person_id: Optional[str] = None
    address_line1: Optional[str] = Field(default=None, max_length=220)
    address_line2: Optional[str] = Field(default=None, max_length=220)
    address_city: Optional[str] = Field(default=None, max_length=120)
    address_state: Optional[str] = Field(default=None, max_length=120)
    address_zip: Optional[str] = Field(default=None, max_length=30)
    sector: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=1000)
    is_draft: bool = False
    available: bool = False
    # Ubicación (opcional): "Usar mi ubicación actual" (gps) o punto manual.
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    location_accuracy_m: Optional[float] = Field(default=None, ge=0, le=100000)
    location_source: Optional[Literal["gps", "manual"]] = None
    location_reference: Optional[str] = Field(default=None, max_length=300)


class HouseholdImportEntry(BaseModel):
    address_line1: Optional[str] = Field(default=None, max_length=220)
    sector: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=1000)
    location_reference: Optional[str] = Field(default=None, max_length=300)


class HouseholdImportInput(BaseModel):
    entries: list[HouseholdImportEntry] = Field(min_length=1, max_length=300)


class HouseholdAssignInput(BaseModel):
    mentor_person_id: str


class HouseholdUpdateInput(BaseModel):
    address_line1: Optional[str] = Field(default=None, max_length=220)
    address_line2: Optional[str] = Field(default=None, max_length=220)
    address_city: Optional[str] = Field(default=None, max_length=120)
    address_state: Optional[str] = Field(default=None, max_length=120)
    address_zip: Optional[str] = Field(default=None, max_length=30)
    sector: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=1000)
    is_draft: Optional[bool] = None


class VisitEventPersonEntry(BaseModel):
    contact_type: Literal["new", "existing"]
    person_id: Optional[str] = None
    contact_name: Optional[str] = Field(default=None, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=40)


class VisitEventInput(BaseModel):
    """Intento de visita a un Hogar. Si `result` no es 'contacted', nunca debe
    traer `persons` (no se inventan datos de un intento sin respuesta)."""
    result: Literal["no_answer", "not_home", "refused", "contacted"]
    note: Optional[str] = Field(default=None, max_length=1000)
    is_draft: bool = False
    persons: list[VisitEventPersonEntry] = Field(default_factory=list, max_length=20)


class VisitCreateInput(BaseModel):
    contact_type: Literal["new", "existing"]
    person_id: Optional[str] = None
    contact_name: Optional[str] = Field(default=None, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=40)
    contact_zone: Optional[str] = Field(default=None, max_length=300)
    campaign_id: Optional[str] = None
    mentor_person_id: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=1000)
    # Jornada de la invasión (día) en la que se registró, p. ej. desde el "+"
    # de la barra inferior móvil. Requiere campaign_id y estar dentro de sus fechas.
    invasion_day: Optional[date] = None


class VisitReportInput(BaseModel):
    status: Literal["assigned", "not_found", "visited", "rejected", "wants_followup"]
    visit_date: Optional[date] = None
    received_mcd: Optional[bool] = None
    received_npt: Optional[bool] = None
    lbs_decision: Optional[Literal["none", "accepted", "needs_lbs"]] = None
    contact_birth_date: Optional[date] = None
    spiritual_status: Optional[Literal["cristiano", "no_cristiano"]] = None
    attends_church: Optional[bool] = None
    is_backslidden: Optional[bool] = None
    address_line1: Optional[str] = Field(default=None, max_length=220)
    address_line2: Optional[str] = Field(default=None, max_length=220)
    address_city: Optional[str] = Field(default=None, max_length=120)
    address_state: Optional[str] = Field(default=None, max_length=120)
    address_zip: Optional[str] = Field(default=None, max_length=30)
    agreed_start_date: Optional[date] = None
    call_schedule: Optional[Literal["morning", "midday", "night"]] = None
    note: Optional[str] = Field(default=None, max_length=1000)
    # Etapa 3: para resolver la Persona 360 sin crear/fusionar en silencio
    # (ver `resolve_or_create_target_person`) cuando la entrega de MCD/NPT
    # dispara una coincidencia fuerte/posible. Nunca se persisten en la visita.
    person_id: Optional[str] = None
    confirm_distinct_person: bool = False
    distinct_reason: Optional[str] = Field(default=None, max_length=400)


class VisitTransferInput(BaseModel):
    new_mentor_person_id: str
    reason: Optional[str] = Field(default=None, max_length=500)


class StartSevenWeeksInput(BaseModel):
    """Igual idea que `VisitReportInput`: resolver la Persona 360 sin crear
    ni fusionar en silencio cuando hay una coincidencia fuerte/posible."""
    person_id: Optional[str] = None
    confirm_distinct_person: bool = False
    distinct_reason: Optional[str] = Field(default=None, max_length=400)


def normalize_phone(value: Optional[str]) -> str:
    """Últimos 10 dígitos (mismo criterio que membership_import.py) para que un
    prefijo de país opcional (+58, 0, etc.) no impida detectar duplicados."""
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else digits


def is_outreach_leader(current_user: dict) -> bool:
    return is_global_pastoral_authority(current_user) or has_capability(current_user, MENTORSHIP_OUTREACH_ASSIGN)


def can_manage_outreach_campaigns(current_user: dict) -> bool:
    """Crear invasiones (lugar/nombre/fecha) y asignar su roster de mentores
    queda reservado a la pastora/pastor y a los coordinadores generales
    (pedido explícito del dueño), más restrictivo que `is_outreach_leader`."""
    return is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)


async def is_active_mentor(person_id: Optional[str]) -> bool:
    if not person_id:
        return False
    badge = await db.mentor_badges.find_one({"person_id": person_id, "active": True}, {"_id": 1})
    return bool(badge)


async def mentor_user_id_for(mentor_person_id: str) -> str:
    """ID de la cuenta del mentor (para mover su inventario de Librería 360).
    Lanza 409 si el mentor aún no tiene cuenta — no debería pasar si se asignó
    el roster con auto-creación, pero protege llamadas directas/legadas."""
    user_doc = await db.users.find_one({"person_id": mentor_person_id}, {"_id": 1})
    if not user_doc:
        raise HTTPException(status_code=409, detail="El mentor responsable no tiene cuenta; no se puede verificar su inventario de Librería")
    return str(user_doc["_id"])


async def can_use_outreach(current_user: dict) -> bool:
    if is_outreach_leader(current_user) or has_capability(current_user, MENTORSHIP_OUTREACH_REPORT):
        return True
    if await is_active_mentor(current_user.get("person_id")):
        return True
    # Líder/colíder de Grupo Frontal sin capacidad de invasiones: se le deja
    # entrar al módulo (en modo lectura) en cuanto lidera/colidera alguna
    # rama, sin importar si ya tiene mentores asignados hoy — así no pierde
    # acceso justo cuando se le asigna el primero. La visibilidad real de
    # datos sigue acotada por `supervised_mentor_person_ids`/`can_view_household`.
    branch_ids = await support_group_ids(db, current_user)
    return bool(branch_ids)


def reveal_contact(visit: dict, current_user: dict, supervised_ids: Optional[set] = None) -> bool:
    if is_outreach_leader(current_user) or visit.get("mentor_person_id") == current_user.get("person_id"):
        return True
    return bool(supervised_ids) and visit.get("mentor_person_id") in supervised_ids


def compute_decision_status(visit: dict) -> str:
    """'Estados de decisión' (Etapa 2), derivados de forma determinística de
    `status`/`agreed_start_date` — nunca se inventa un dato nuevo, solo se
    traduce lo que ya existe a un vocabulario de decisión (igual idea que
    `decision_status` en Consolidación v2)."""
    status = visit.get("status")
    if status == "wants_followup":
        return "start_scheduled" if visit.get("agreed_start_date") else "accepted"
    if status == "rejected":
        return "desisted"
    if status == "not_found":
        return "no_response"
    if status == "visited":
        return "pending_decision"
    return "pending"


async def supervision_snapshot(mentor_person_id: Optional[str]) -> dict:
    """Snapshot informativo al momento de crear el hogar/visita: Grupo Frontal
    principal del mentor + sus ancestros, para mostrar siempre con qué equipo
    se capturó el contacto aunque el mentor cambie de rama después. La
    VISIBILIDAD de solo-lectura (quién puede verlo hoy) no usa este snapshot:
    se recalcula en vivo con `supervised_mentor_person_ids`, para que un
    líder deje de ver a un mentor que ya salió de su rama."""
    if not mentor_person_id:
        return {"front_group_id": None, "front_group_ancestor_ids": []}
    assignments = await db.front_group_assignments.find(
        {"person_id": mentor_person_id, "active": True}, {"_id": 0, "front_group_id": 1, "role": 1},
    ).to_list(50)
    if not assignments:
        return {"front_group_id": None, "front_group_ancestor_ids": []}
    priority = {"mentor": 0, "leader": 1, "co_leader": 2, "member": 3, "team": 3}
    assignments.sort(key=lambda item: priority.get(item.get("role"), 9))
    front_group_id = assignments[0]["front_group_id"]
    group = await db.front_groups.find_one({"front_group_id": front_group_id}, {"_id": 0, "ancestor_group_ids": 1})
    return {"front_group_id": front_group_id, "front_group_ancestor_ids": (group or {}).get("ancestor_group_ids") or []}


async def supervised_mentor_person_ids(current_user: dict) -> set:
    """Mentores visibles en modo LECTURA para el usuario actual: él mismo, y
    cualquier mentor cuyo Grupo Frontal (snapshot) esté dentro de la rama que
    lidera/colidera (requisito del dueño: 'líder y colíder de su rama y
    ancestros ven, no editan'). `support_group_ids` ya expande hacia los
    descendientes, por eso basta comparar contra ese conjunto."""
    self_id = current_user.get("person_id")
    allowed = {self_id} if self_id else set()
    branch_ids = await support_group_ids(db, current_user)
    if not branch_ids:
        return allowed
    member_ids = await db.front_group_assignments.distinct(
        "person_id", {"front_group_id": {"$in": list(branch_ids)}, "active": True},
    )
    allowed.update(member_ids)
    return allowed


async def ensure_participation(campaign_id: str, mentor_person_id: str) -> None:
    now = now_utc()
    participation_id = str(uuid4())
    await db.outreach_participations.update_one(
        {"campaign_id": campaign_id, "mentor_person_id": mentor_person_id},
        {"$setOnInsert": {
            "_id": participation_id, "participation_id": participation_id, "campaign_id": campaign_id,
            "mentor_person_id": mentor_person_id, "status": "assigned", "confirmed_at": None,
            "first_activity_at": None, "created_at": now, "updated_at": now,
        }},
        upsert=True,
    )


async def mark_participation_active(campaign_id: Optional[str], mentor_person_id: str) -> None:
    """Al registrar la primera actividad (hogar o visita) de ESTE mentor en
    ESTA invasión, pasa directo a 'Con actividad' — sin importar si ya había
    confirmado o no (requisito del dueño: 'el propio mentor confirma', pero la
    actividad real siempre debe reflejarse)."""
    if not campaign_id:
        return
    await ensure_participation(campaign_id, mentor_person_id)
    await db.outreach_participations.update_one(
        {"campaign_id": campaign_id, "mentor_person_id": mentor_person_id, "status": {"$ne": "active"}},
        {"$set": {"status": "active", "first_activity_at": now_utc(), "updated_at": now_utc()}},
    )
    # Fase 6B: registrar actividad en la invasión cuenta como asistencia en la lista de participantes.
    from invasion_participants import mark_attended_from_activity
    await mark_attended_from_activity(campaign_id, mentor_person_id)


async def person_display_name(person_id: Optional[str]) -> Optional[str]:
    if not person_id or not ObjectId.is_valid(person_id):
        return None
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 0, "nombre": 1, "apellido": 1})
    return " ".join(part for part in [(person or {}).get("nombre"), (person or {}).get("apellido")] if part) or None


async def log_visit_history(visit_id: str, current_user: dict, action: str, detail: dict) -> None:
    history_id = str(uuid4())
    await db.outreach_visit_history.insert_one({
        "_id": history_id,
        "history_id": history_id,
        "visit_id": visit_id,
        "action": action,
        "detail": serialize(detail),
        "actor_user_id": current_user["user_id"],
        "actor_person_id": current_user.get("person_id"),
        "occurred_at": now_utc(),
    })


async def load_visit(visit_id: str) -> dict:
    visit = await db.outreach_visits.find_one({"visit_id": visit_id, "archived": {"$ne": True}}, {"_id": 0})
    if not visit:
        raise HTTPException(status_code=404, detail="Visita no encontrada")
    return visit


async def serialize_visits(visits: list[dict], current_user: dict) -> list[dict]:
    person_ids = {v["person_id"] for v in visits if v.get("person_id")}
    mentor_ids = {v["mentor_person_id"] for v in visits if v.get("mentor_person_id")}
    campaign_ids = {v["campaign_id"] for v in visits if v.get("campaign_id")}
    all_person_ids = list(person_ids | mentor_ids)
    valid_oids = [ObjectId(pid) for pid in all_person_ids if ObjectId.is_valid(pid)]
    people = await db.persons.find({"_id": {"$in": valid_oids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(valid_oids)) if valid_oids else []
    names = {str(p["_id"]): f"{p.get('nombre', '')} {p.get('apellido', '')}".strip() for p in people}
    campaigns = await db.outreach_campaigns.find({"campaign_id": {"$in": list(campaign_ids)}}, {"_id": 0, "campaign_id": 1, "name": 1}).to_list(len(campaign_ids)) if campaign_ids else []
    campaign_names = {c["campaign_id"]: c["name"] for c in campaigns}
    mentor_id_list = list(mentor_ids)
    lbs_docs = await db.mentor_qualifications.find(
        {"person_id": {"$in": mentor_id_list}, "active": True, "can_teach_lbs": True, "front_group_id": None},
        {"_id": 0, "person_id": 1},
    ).to_list(len(mentor_id_list)) if mentor_id_list else []
    lbs_qualified_ids = {d["person_id"] for d in lbs_docs}
    supervised_ids = await supervised_mentor_person_ids(current_user)
    results = []
    for visit in visits:
        reveal = reveal_contact(visit, current_user, supervised_ids)
        contact_name = names.get(visit.get("person_id")) if visit.get("contact_type") == "existing" else visit.get("contact_name")
        item = {
            "visit_id": visit["visit_id"],
            "contact_type": visit.get("contact_type"),
            "person_id": visit.get("person_id"),
            "contact_name": contact_name,
            "mentor_person_id": visit.get("mentor_person_id"),
            "mentor_name": names.get(visit.get("mentor_person_id")),
            "mentor_lbs_qualified": visit.get("mentor_person_id") in lbs_qualified_ids,
            "campaign_id": visit.get("campaign_id"),
            "campaign_name": campaign_names.get(visit.get("campaign_id")),
            "household_id": visit.get("household_id"),
            "status": visit.get("status"),
            "decision_status": visit.get("decision_status") or compute_decision_status(visit),
            "visit_date": visit.get("visit_date"),
            "received_mcd": bool(visit.get("received_mcd")),
            "received_npt": bool(visit.get("received_npt")),
            "mcd_delivered": bool(visit.get("mcd_delivery_movement_id")),
            "npt_delivered": bool(visit.get("npt_delivery_movement_id")),
            "lbs_decision": visit.get("lbs_decision", "none"),
            "note": visit.get("note"),
            "enrollment_id": visit.get("enrollment_id"),
            "converted_person_id": visit.get("converted_person_id"),
            "created_at": serialize(visit.get("created_at")),
            "updated_at": serialize(visit.get("updated_at")),
            "read_only": not (is_outreach_leader(current_user) or visit.get("mentor_person_id") == current_user.get("person_id")),
        }
        if reveal:
            item["contact_phone"] = visit.get("contact_phone")
            item["contact_zone"] = visit.get("contact_zone")
            item["contact_birth_date"] = visit.get("contact_birth_date")
            item["spiritual_status"] = visit.get("spiritual_status")
            item["attends_church"] = visit.get("attends_church")
            item["is_backslidden"] = visit.get("is_backslidden")
            item["address_line1"] = visit.get("address_line1")
            item["address_line2"] = visit.get("address_line2")
            item["address_city"] = visit.get("address_city")
            item["address_state"] = visit.get("address_state")
            item["address_zip"] = visit.get("address_zip")
            item["agreed_start_date"] = visit.get("agreed_start_date")
            item["call_schedule"] = visit.get("call_schedule")
        results.append(item)
    return results


async def resolve_and_insert_contact_visit(
    contact_type: str, person_id: Optional[str], contact_name: Optional[str], contact_phone: Optional[str],
    contact_zone: Optional[str], campaign_id: Optional[str], mentor_person_id: str, note: Optional[str],
    current_user: dict, household_id: Optional[str] = None, visit_event_id: Optional[str] = None,
) -> dict:
    """Núcleo compartido de `POST /visits` y de un intento 'contacted' dentro
    de un Hogar (Etapa 2) — misma deduplicación y mismas reglas, para que un
    contacto registrado desde cualquiera de los dos caminos sea indistinguible."""
    phone_digits = None
    resolved_person_id = None
    if contact_type == "existing":
        if not person_id:
            raise HTTPException(status_code=422, detail="Seleccione la persona existente")
        await load_person(db, person_id)
        duplicate = await db.outreach_visits.find_one(
            {"$or": [{"person_id": person_id}, {"converted_person_id": person_id}], "archived": {"$ne": True}},
            {"_id": 0, "mentor_person_id": 1},
        )
        if duplicate:
            mentor_name = await person_display_name(duplicate.get("mentor_person_id"))
            raise HTTPException(status_code=409, detail=f"Esta persona ya tiene una visita activa registrada (mentor: {mentor_name or 'desconocido'})")
        resolved_person_id = person_id
    else:
        if not contact_name or not contact_name.strip():
            raise HTTPException(status_code=422, detail="El nombre del contacto es obligatorio")
        phone_digits = normalize_phone(contact_phone)
        if phone_digits:
            duplicate = await db.outreach_visits.find_one({"phone_normalized": phone_digits, "archived": {"$ne": True}}, {"_id": 0, "mentor_person_id": 1})
            if duplicate:
                mentor_name = await person_display_name(duplicate.get("mentor_person_id"))
                raise HTTPException(status_code=409, detail=f"Ya existe una visita registrada con ese teléfono (mentor: {mentor_name or 'desconocido'})")
    if campaign_id and not await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    snapshot = await supervision_snapshot(mentor_person_id)
    now = now_utc()
    visit_id = str(uuid4())
    doc = {
        "_id": visit_id, "visit_id": visit_id, "campaign_id": campaign_id,
        "mentor_person_id": mentor_person_id, "contact_type": contact_type,
        "person_id": resolved_person_id, "contact_name": contact_name.strip() if contact_name else None,
        "contact_phone": contact_phone, "contact_zone": contact_zone,
        "phone_normalized": phone_digits, "status": "assigned", "visit_date": None,
        "received_mcd": False, "received_npt": False, "mcd_delivery_movement_id": None, "npt_delivery_movement_id": None,
        "lbs_decision": "none", "contact_birth_date": None, "spiritual_status": None, "attends_church": None, "is_backslidden": None,
        "address_line1": None, "address_line2": None, "address_city": None, "address_state": None, "address_zip": None,
        "agreed_start_date": None, "call_schedule": None, "decision_status": "pending",
        "household_id": household_id, "visit_event_id": visit_event_id,
        "front_group_id": snapshot["front_group_id"], "front_group_ancestor_ids": snapshot["front_group_ancestor_ids"],
        "note": note, "enrollment_id": None, "converted_person_id": None, "converted_at": None,
        "archived": False, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.outreach_visits.insert_one(doc)
    await log_visit_history(visit_id, current_user, "visit_created", {"mentor_person_id": mentor_person_id, "contact_type": contact_type})
    if campaign_id:
        await mark_participation_active(campaign_id, mentor_person_id)
    return doc


async def resolve_or_create_target_person(
    visit: dict, current_user: dict, person_id_override: Optional[str] = None,
    confirm_distinct_person: bool = False, distinct_reason: Optional[str] = None,
) -> tuple:
    """Resuelve (y reutiliza) la Persona 360 de esta visita con el MISMO
    servicio de coincidencias (`person_matching.py`) que usan los Grupos
    Frontales: coincidencia FUERTE bloquea (409 + candidatos) y coincidencia
    POSIBLE exige elegir la existente o confirmar con motivo — nunca crea ni
    fusiona en silencio. Se usa igual desde la entrega de libro (C8) y desde
    iniciar la Ley de las 7 Semanas, así ambas terminan apuntando a la MISMA
    Persona 360."""
    created_person = False
    if visit.get("converted_person_id"):
        person_id = visit["converted_person_id"]
    elif visit.get("contact_type") == "existing" and visit.get("person_id"):
        person_id = visit["person_id"]
    elif person_id_override:
        if not ObjectId.is_valid(person_id_override) or not await db.persons.find_one({"_id": ObjectId(person_id_override), "is_archived": {"$ne": True}}, {"_id": 1}):
            raise HTTPException(status_code=404, detail="La persona seleccionada no existe")
        person_id = person_id_override
        await db.outreach_visits.update_one({"visit_id": visit["visit_id"]}, {"$set": {"converted_person_id": person_id, "updated_at": now_utc()}})
        visit["converted_person_id"] = person_id
    else:
        tokens = (visit.get("contact_name") or "Contacto Invasión").strip().split()
        nombre = tokens[0] if tokens else "Contacto"
        apellido = " ".join(tokens[1:]) if len(tokens) > 1 else "Invasión"
        match_payload = PersonQuickCreate(
            nombre=nombre, apellido=apellido, fecha_nacimiento=visit.get("contact_birth_date"), telefono=visit.get("contact_phone"),
            idempotency_key=f"outreach-visit:{visit['visit_id']}",
            confirm_distinct_person=confirm_distinct_person, distinct_reason=distinct_reason,
        )
        result = await quick_create_person(db, match_payload, current_user["user_id"], source="mentorship_outreach")
        if result["status"] == "strong_match":
            raise HTTPException(status_code=409, detail={"message": "Ya existe una Persona 360 que coincide con este contacto; use el perfil encontrado.", "candidates": result["candidates"]})
        if result["status"] == "possible_match":
            raise HTTPException(status_code=409, detail={"message": "Hay una Persona 360 con nombre parecido. Use la existente o confirme que es alguien distinto (con un motivo).", "candidates": result["candidates"], "requires_confirmation": True})
        person_id, created_person = result["person"]["person_id"], result["created"]
        await db.outreach_visits.update_one({"visit_id": visit["visit_id"]}, {"$set": {"converted_person_id": person_id, "updated_at": now_utc()}})
        visit["converted_person_id"] = person_id
    if visit.get("contact_birth_date"):
        await db.persons.update_one(
            {"_id": ObjectId(person_id), "$or": [{"fecha_nacimiento": None}, {"fecha_nacimiento": {"$exists": False}}]},
            {"$set": {"fecha_nacimiento": visit["contact_birth_date"], "updated_at": now_utc()}},
        )
    return person_id, created_person


async def deliver_outreach_book(visit: dict, sku: str, target_person_id: str, current_user: dict) -> str:
    """Descuenta 1 unidad del inventario del mentor responsable y la entrega a
    `target_person_id` (movimiento DELIVERY, library_module.py), etiquetada con
    la invasión de la visita para poder reportarla por invasión."""
    return await deliver_from_mentor_to_person(
        sku, visit["mentor_person_id"], target_person_id, current_user["user_id"],
        campaign_id=visit.get("campaign_id"), process_key=OUTREACH_PROCESS_KEY, notes="Entrega en visita de invasión",
        idempotency_key=f"visit:{visit['visit_id']}:{sku}",
        links={"visit_id": visit["visit_id"], "household_id": visit.get("household_id"), "visit_event_id": visit.get("visit_event_id")},
    )


async def sync_visit_address_to_person(visit: dict, person_id: str, current_user: dict, background_tasks: BackgroundTasks) -> None:
    """Si la casa capturó dirección completa y la persona todavía no tiene
    ninguna dirección en su Perfil 360, la crea reutilizando geo_address
    (mismo normalizador y job de geocodificación que `person_domains.py`)."""
    if not visit.get("address_line1") or await db.person_addresses.count_documents({"person_id": person_id}):
        return
    now = now_utc()
    doc = {
        "person_id": person_id, "tipo": "casa", "linea1": visit.get("address_line1"), "linea2": visit.get("address_line2"),
        "sector": visit.get("contact_zone"), "ciudad": visit.get("address_city") or "", "provincia": visit.get("address_state"),
        "codigo_postal": visit.get("address_zip"), "pais": "Estados Unidos", "notas": "Capturada en una visita de invasión",
        "es_principal": True, "created_by": current_user["user_id"], "created_at": now, "updated_at": now,
        **pending_geo_fields(1),
    }
    doc.update(normalize_address_document(doc))
    result = await db.person_addresses.insert_one(doc)
    job_id = await enqueue_geo_job(db, "person_address", str(result.inserted_id), 1, current_user["user_id"])
    background_tasks.add_task(process_geo_job, db, job_id)


@router.post("/campaigns", response_model=dict, status_code=201)
async def create_campaign(payload: CampaignInput, current_user: dict = Depends(get_current_user)):
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede crear invasiones")
    authorities = await principal_authority_person_ids(db)
    roster = [entry for entry in {entry.person_id: entry for entry in payload.assigned_mentors if entry.person_id}.values() if entry.person_id not in authorities]
    accounts_created = await ensure_mentor_roster_accounts(roster, current_user)
    now = now_utc()
    campaign_id = str(uuid4())
    doc = {
        "_id": campaign_id, "campaign_id": campaign_id, "name": payload.name.strip(), "location": payload.location.strip(),
        "start_date": payload.start_date.isoformat(), "end_date": payload.end_date.isoformat(),
        "zone_notes": payload.zone_notes, "meeting_time": payload.meeting_time, "meeting_place": payload.meeting_place,
        "sectors": [s.strip() for s in (payload.sectors or []) if s and s.strip()], "instructions": payload.instructions,
        "assigned_mentor_ids": [entry.person_id for entry in roster], "status": "active",
        "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.outreach_campaigns.insert_one(doc)
    for entry in roster:
        await ensure_participation(campaign_id, entry.person_id)
    result = serialize(doc)
    result["accounts_created"] = accounts_created
    return result


async def ensure_mentor_roster_accounts(roster: list, current_user: dict) -> list:
    """Para cada mentor del roster: exige insignia activa y, si no tiene
    cuenta, la auto-crea con `create_user_access_core` (mentor_access=True)
    usando el correo/clave temporal que escribió el coordinador en el
    formulario — la clave nunca se registra en logs.

    Valida TODO el roster primero (insignia, credenciales, correo libre y sin
    duplicados dentro del mismo roster) y solo después crea cuentas, para que
    el error de un mentor no deje cuentas huérfanas de los mentores anteriores."""
    to_create = []
    seen_emails = set()
    for entry in roster:
        if not await is_active_mentor(entry.person_id):
            name = await person_display_name(entry.person_id) or "Uno de los mentores seleccionados"
            raise HTTPException(status_code=409, detail=f"{name} no tiene insignia de Mentor activa")
        if await db.users.find_one({"person_id": entry.person_id}, {"_id": 1}):
            continue
        if not entry.email or not entry.temporary_password:
            name = await person_display_name(entry.person_id) or "Uno de los mentores seleccionados"
            raise HTTPException(status_code=422, detail=f"{name} no tiene cuenta todavía; indique un correo y una contraseña temporal (mínimo 10 caracteres) para crearla")
        email_key = str(entry.email).strip().lower()
        if email_key in seen_emails:
            raise HTTPException(status_code=422, detail=f"El correo {entry.email} se repite para más de un mentor del roster")
        seen_emails.add(email_key)
        if await db.users.find_one({"email": email_key}, {"_id": 1}):
            raise HTTPException(status_code=409, detail=f"El correo {entry.email} ya tiene acceso")
        to_create.append(entry)
    accounts_created = []
    for entry in to_create:
        created = await create_user_access_core(
            UserAccessCreate(person_id=entry.person_id, email=entry.email, temporary_password=entry.temporary_password, access_level="persona", mentor_access=True),
            current_user,
        )
        accounts_created.append({"person_id": entry.person_id, "email": created["email"]})
    return accounts_created


@router.get("/campaigns", response_model=dict)
async def list_campaigns(current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar invasiones")
    items = await db.outreach_campaigns.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    mentor_person_id = current_user.get("person_id")
    if is_global_pastoral_authority(current_user):
        mentor_person_id = None  # supervisa: nunca se le pide confirmar participación
    if mentor_person_id:
        participations = await db.outreach_participations.find(
            {"mentor_person_id": mentor_person_id}, {"_id": 0, "campaign_id": 1, "status": 1},
        ).to_list(500)
        status_by_campaign = {p["campaign_id"]: p["status"] for p in participations}
        for item in items:
            item["my_participation_status"] = status_by_campaign.get(item["campaign_id"]) if mentor_person_id in (item.get("assigned_mentor_ids") or []) else None
    return {"items": serialize(items)}


class DeleteReason(BaseModel):
    reason: str = Field(min_length=3, max_length=600)


@router.get("/campaigns/{campaign_id}/delete-preview", response_model=dict)
async def preview_delete_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Conteo exacto de lo que se borraría, para confirmar ANTES de un
    borrado total y permanente (nunca se borra a ciegas)."""
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede borrar invasiones")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "name": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    households = await db.outreach_households.count_documents({"campaign_id": campaign_id})
    visits = await db.outreach_visits.count_documents({"campaign_id": campaign_id})
    household_ids = await db.outreach_households.distinct("household_id", {"campaign_id": campaign_id})
    attempts = await db.outreach_visit_events.count_documents({"household_id": {"$in": household_ids}}) if household_ids else 0
    participations = await db.outreach_participations.count_documents({"campaign_id": campaign_id})
    return {"campaign_name": campaign.get("name"), "households": households, "visits": visits, "attempts": attempts, "participations": participations}


@router.delete("/campaigns/{campaign_id}", response_model=dict)
async def delete_campaign(campaign_id: str, payload: DeleteReason, current_user: dict = Depends(get_current_user)):
    """Borrado TOTAL y permanente de la Invasión (decisión del dueño): borra
    la campaña y TODOS sus hogares, visitas e intentos registrados. Los
    expedientes de Consolidación que ya nacieron de aquí NO se tocan (son
    historial propio de la Persona 360) ni los movimientos de Librería ya
    hechos (son ledger real de inventario); solo pierden el vínculo visible
    a esta invasión ya borrada."""
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede borrar invasiones")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "name": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    household_ids = await db.outreach_households.distinct("household_id", {"campaign_id": campaign_id})
    visits_deleted = (await db.outreach_visits.delete_many({"campaign_id": campaign_id})).deleted_count
    attempts_deleted = (await db.outreach_visit_events.delete_many({"household_id": {"$in": household_ids}})).deleted_count if household_ids else 0
    households_deleted = (await db.outreach_households.delete_many({"campaign_id": campaign_id})).deleted_count
    await db.outreach_participations.delete_many({"campaign_id": campaign_id})
    await db.outreach_campaigns.delete_one({"campaign_id": campaign_id})
    await db.admin_deletions.insert_one({
        "_id": str(uuid4()), "collection": "outreach_campaigns", "target_id": campaign_id, "reason": payload.reason,
        "detail": {"name": campaign.get("name"), "visits_deleted": visits_deleted, "households_deleted": households_deleted, "attempts_deleted": attempts_deleted},
        "actor_user_id": current_user["user_id"], "actor_person_id": current_user.get("person_id"), "deleted_at": now_utc(),
    })
    return {"deleted": True, "campaign_name": campaign.get("name"), "visits_deleted": visits_deleted, "households_deleted": households_deleted, "attempts_deleted": attempts_deleted}


@router.post("/campaigns/{campaign_id}/participate", response_model=dict)
async def participate_in_campaign(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """El propio mentor confirma su participación (Asignado → Confirmado).
    En cuanto registra su primer hogar/visita en esta invasión, el estado
    sube solo a 'Con actividad' (ver `mark_participation_active`)."""
    mentor_person_id = current_user.get("person_id")
    if not mentor_person_id:
        raise HTTPException(status_code=403, detail="Esta cuenta no está vinculada a un Perfil 360")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "assigned_mentor_ids": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=409, detail="La autoridad pastoral principal supervisa la invasión; no confirma participación")
    if mentor_person_id not in (campaign.get("assigned_mentor_ids") or []):
        raise HTTPException(status_code=403, detail="No está en el roster de mentores de esta invasión")
    await ensure_participation(campaign_id, mentor_person_id)
    now = now_utc()
    await db.outreach_participations.update_one(
        {"campaign_id": campaign_id, "mentor_person_id": mentor_person_id, "status": "assigned"},
        {"$set": {"status": "confirmed", "confirmed_at": now, "updated_at": now}},
    )
    # Mismo estado en la lista de participantes de la invasión (Fase 6B).
    await db.invasion_participants.update_many(
        {"campaign_id": campaign_id, "person_id": mentor_person_id, "status": "invited"},
        {"$set": {"status": "confirmed", "responded_at": now, "updated_at": now}},
    )
    return serialize(await db.outreach_participations.find_one({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id}, {"_id": 0}))


@router.put("/campaigns/{campaign_id}", response_model=dict)
async def update_campaign(campaign_id: str, payload: CampaignUpdateInput, current_user: dict = Depends(get_current_user)):
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede administrar invasiones")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    fields = payload.dict(exclude_unset=True)
    if fields.get("start_date") is not None:
        fields["start_date"] = fields["start_date"].isoformat()
    if fields.get("end_date") is not None:
        fields["end_date"] = fields["end_date"].isoformat()
    if "sectors" in fields:
        fields["sectors"] = [s.strip() for s in (fields["sectors"] or []) if s and s.strip()]
    accounts_created = []
    if "assigned_mentors" in fields:
        authorities = await principal_authority_person_ids(db)
        roster = [entry for entry in {entry.person_id: entry for entry in (payload.assigned_mentors or []) if entry.person_id}.values() if entry.person_id not in authorities]
        accounts_created = await ensure_mentor_roster_accounts(roster, current_user)
        fields["assigned_mentor_ids"] = [entry.person_id for entry in roster]
        del fields["assigned_mentors"]
        for entry in roster:
            await ensure_participation(campaign_id, entry.person_id)
    if fields.get("name") is not None:
        fields["name"] = fields["name"].strip()
    if fields.get("location") is not None:
        fields["location"] = fields["location"].strip()
    fields["updated_at"] = now_utc()
    await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$set": fields})
    refreshed = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if fields.get("status") == "closed":
        # Fase 6F: al cerrar la invasión se congela su "Reporte final".
        from invasion_report import freeze_report
        await freeze_report(refreshed, current_user["user_id"])
    result = serialize(refreshed)
    result["accounts_created"] = accounts_created
    return result


@router.post("/campaigns/{campaign_id}/mentors", response_model=dict)
async def add_campaign_mentors(campaign_id: str, payload: AddMentorsInput, current_user: dict = Depends(get_current_user)):
    """ADITIVO (pedido explícito del dueño): a diferencia de PUT /campaigns/{id}
    (que REEMPLAZA todo el roster), esto solo AGREGA — nunca toca a los
    mentores ya asignados ni sus libros/visitas/participación. Idempotente:
    repetir la misma llamada no duplica nada ni falla."""
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede agregar mentores a una invasión")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "name": 1, "assigned_mentor_ids": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    if not payload.person_ids and not payload.front_group_ids:
        raise HTTPException(status_code=422, detail="Seleccione al menos un mentor o un Grupo Frontal")
    existing_ids = set(campaign.get("assigned_mentor_ids") or [])

    explicit_ids = list(dict.fromkeys(payload.person_ids))
    for person_id in explicit_ids:
        if person_id in existing_ids:
            continue
        if not await is_active_mentor(person_id):
            name = await person_display_name(person_id) or "Uno de los mentores seleccionados"
            raise HTTPException(status_code=409, detail=f"{name} no tiene insignia de Mentor activa")

    group_candidate_ids: set = set()
    for front_group_id in payload.front_group_ids:
        group_candidate_ids.update(await mentor_ids_in_group_branch(front_group_id))

    already_assigned = sorted((set(explicit_ids) | group_candidate_ids) & existing_ids)
    candidate_ids = [pid for pid in explicit_ids if pid not in existing_ids]
    candidate_ids += sorted(group_candidate_ids - existing_ids - set(explicit_ids))

    added, rejected, accounts_created = [], [], []
    authorities = await principal_authority_person_ids(db)
    for person_id in [pid for pid in candidate_ids if pid in authorities]:
        if person_id in explicit_ids:
            rejected.append({"person_id": person_id, "name": await person_display_name(person_id) or "Autoridad pastoral", "reason": "Supervisa la invasión como autoridad pastoral principal; no se agrega como participante"})
    candidate_ids = without(candidate_ids, authorities)
    for person_id in candidate_ids:
        user_doc = await db.users.find_one({"person_id": person_id}, {"_id": 1})
        if not user_doc:
            email = payload.emails.get(person_id)
            name = await person_display_name(person_id) or "Uno de los mentores seleccionados"
            if not email:
                rejected.append({"person_id": person_id, "name": name, "reason": "No tiene cuenta todavía; indique un correo para invitarlo"})
                continue
            email_key = str(email).strip().lower()
            if await db.users.find_one({"email": email_key}, {"_id": 1}):
                rejected.append({"person_id": person_id, "name": name, "reason": f"El correo {email} ya tiene acceso"})
                continue
            created = await create_user_access_core(
                UserAccessCreate(person_id=person_id, email=email, temporary_password=None, access_level="persona", mentor_access=True),
                current_user,
            )
            accounts_created.append({"person_id": person_id, "email": created["email"]})
        await ensure_participation(campaign_id, person_id)
        added.append(person_id)

    if added:
        await db.outreach_campaigns.update_one(
            {"campaign_id": campaign_id},
            {"$addToSet": {"assigned_mentor_ids": {"$each": added}}, "$set": {"updated_at": now_utc()}},
        )
    return {"added": added, "already_assigned": already_assigned, "rejected": rejected, "accounts_created": accounts_created}


async def books_in_custody_for_campaign(campaign_id: str, mentor_person_id: str) -> int:
    """Libros que este mentor todavía tiene consigo de ESTA invasión
    (entradas: ASSIGNMENT/TRANSFER hacia él; salidas: DELIVERY/RETURN/TRANSFER
    desde él, filtrado por campaign_id en el ledger de Librería). 0 si nunca
    tuvo cuenta."""
    user_doc = await db.users.find_one({"person_id": mentor_person_id}, {"_id": 1})
    if not user_doc:
        return 0
    mentor_user_id = str(user_doc["_id"])
    rows = await db.library_movements.aggregate([
        {"$match": {"campaign_id": campaign_id, "$or": [{"to_holder.id": mentor_user_id}, {"from_holder.id": mentor_user_id}]}},
        {"$group": {"_id": {"type": "$movement_type", "to_me": {"$eq": ["$to_holder.id", mentor_user_id]}}, "total": {"$sum": "$quantity"}}},
    ]).to_list(50)
    incoming = sum(row["total"] for row in rows if row["_id"]["to_me"] and row["_id"]["type"] in ("ASSIGNMENT", "TRANSFER"))
    outgoing = sum(row["total"] for row in rows if not row["_id"]["to_me"] and row["_id"]["type"] in ("DELIVERY", "RETURN", "TRANSFER"))
    return max(incoming - outgoing, 0)


@router.get("/campaigns/{campaign_id}/mentors/{mentor_person_id}/remove-preview", response_model=dict)
async def preview_remove_mentor(campaign_id: str, mentor_person_id: str, current_user: dict = Depends(get_current_user)):
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede quitar mentores")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "assigned_mentor_ids": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    if mentor_person_id not in (campaign.get("assigned_mentor_ids") or []):
        raise HTTPException(status_code=404, detail="Ese mentor no está en el roster de esta invasión")
    households = await db.outreach_households.count_documents({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id})
    visits = await db.outreach_visits.count_documents({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id})
    books_in_custody = await books_in_custody_for_campaign(campaign_id, mentor_person_id)
    return {"households": households, "visits": visits, "books_in_custody": books_in_custody, "blocked": bool(households or visits or books_in_custody)}


@router.delete("/campaigns/{campaign_id}/mentors/{mentor_person_id}", response_model=dict)
async def remove_campaign_mentor(campaign_id: str, mentor_person_id: str, payload: RemoveMentorInput, current_user: dict = Depends(get_current_user)):
    """Quitar es una acción aparte de PUT (nunca reemplaza la lista completa):
    se bloquea si el mentor tiene hogares, visitas o libros en custodia de ESTA
    invasión — primero hay que transferir los contactos y devolver los libros.
    Queda auditado en `admin_deletions`."""
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede quitar mentores")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "name": 1, "assigned_mentor_ids": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    if mentor_person_id not in (campaign.get("assigned_mentor_ids") or []):
        raise HTTPException(status_code=404, detail="Ese mentor no está en el roster de esta invasión")
    households = await db.outreach_households.count_documents({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id})
    visits = await db.outreach_visits.count_documents({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id})
    books_in_custody = await books_in_custody_for_campaign(campaign_id, mentor_person_id)
    if households or visits or books_in_custody:
        name = await person_display_name(mentor_person_id) or "Este mentor"
        raise HTTPException(
            status_code=409,
            detail=f"No se puede quitar a {name}: tiene {households} hogar(es), {visits} visita(s) y {books_in_custody} libro(s) en custodia de esta invasión. Primero transfiera los contactos y devuelva los libros.",
        )
    await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$pull": {"assigned_mentor_ids": mentor_person_id}, "$set": {"updated_at": now_utc()}})
    await db.outreach_participations.delete_one({"campaign_id": campaign_id, "mentor_person_id": mentor_person_id})
    await db.admin_deletions.insert_one({
        "_id": str(uuid4()), "collection": "outreach_campaign_mentors", "target_id": f"{campaign_id}:{mentor_person_id}",
        "reason": payload.reason, "detail": {"name": campaign.get("name"), "mentor_person_id": mentor_person_id},
        "actor_user_id": current_user["user_id"], "actor_person_id": current_user.get("person_id"), "deleted_at": now_utc(),
    })
    return {"removed": True, "mentor_person_id": mentor_person_id}


@router.post("/campaigns/{campaign_id}/books", response_model=dict, status_code=201)
async def assign_campaign_books(campaign_id: str, payload: BookAssignmentInput, current_user: dict = Depends(get_current_user)):
    """Paso de libros de la invasión: por cada mentor del roster, libro y
    cantidad desde Librería 360 → movimiento ASSIGNMENT (Central → mentor)
    con process_key/campaign_id de esta invasión. Valida existencia central
    ANTES de mover nada, para un error claro y evitar asignaciones parciales."""
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede asignar libros de la invasión")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    roster = set(campaign.get("assigned_mentor_ids") or [])
    resolved = []
    needed_by_book: dict = {}
    book_names: dict = {}
    for entry in payload.assignments:
        if entry.mentor_person_id not in roster:
            name = await person_display_name(entry.mentor_person_id) or "El mentor seleccionado"
            raise HTTPException(status_code=409, detail=f"{name} no forma parte del roster de esta invasión")
        book = await db.library_books.find_one({"book_id": entry.book_id, "is_active": True}, {"_id": 0, "book_id": 1, "name": 1})
        if not book:
            raise HTTPException(status_code=404, detail="Uno de los libros seleccionados no existe o está inactivo")
        mentor_user_id = await mentor_user_id_for(entry.mentor_person_id)
        needed_by_book[entry.book_id] = needed_by_book.get(entry.book_id, 0) + entry.quantity
        book_names[entry.book_id] = book["name"]
        resolved.append((entry, mentor_user_id))
    for book_id, needed in needed_by_book.items():
        central = await db.library_holdings.find_one({"book_id": book_id, "holder_type": "warehouse", "holder_id": "central"}, {"_id": 0, "quantity_on_hand": 1})
        available = (central or {}).get("quantity_on_hand", 0)
        if available < needed:
            raise HTTPException(status_code=409, detail=f"No hay existencias suficientes de '{book_names[book_id]}' en el Inventario Central (disponible: {available}, necesario: {needed})")
    movements = []
    for entry, mentor_user_id in resolved:
        movement = await apply_movement(
            MovementInput(
                book_id=entry.book_id, movement_type="ASSIGNMENT", quantity=entry.quantity,
                from_holder=HolderInput(**CENTRAL_HOLDER), to_holder=HolderInput(type="user", id=mentor_user_id),
                process_key=OUTREACH_PROCESS_KEY, campaign_id=campaign_id, notes=f"Invasión: {campaign['name']}",
            ),
            current_user["user_id"],
        )
        movements.append(movement)
    return {"items": serialize(movements)}


@router.get("/campaigns/{campaign_id}/books", response_model=dict)
async def list_campaign_books(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Asignado/entregado/me quedan por mentor y libro para esta invasión —
    usado por el paso de libros (editar) y por el informe de líderes."""
    if not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar los libros de la invasión")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    return {"items": await campaign_book_rows(campaign)}


async def campaign_book_rows(campaign: dict) -> list:
    """Asignado/entregado por mentor y libro (también lo usa el Reporte de invasión)."""
    campaign_id = campaign["campaign_id"]
    mentor_ids = campaign.get("assigned_mentor_ids") or []
    movements = await db.library_movements.find({"campaign_id": campaign_id, "movement_type": {"$in": ["ASSIGNMENT", "DELIVERY"]}}, {"_id": 0}).to_list(5000)
    books = {b["book_id"]: b["name"] for b in await db.library_books.find({}, {"_id": 0, "book_id": 1, "name": 1}).to_list(2000)}
    users = await db.users.find({"person_id": {"$in": mentor_ids}}, {"_id": 1, "person_id": 1}).to_list(len(mentor_ids)) if mentor_ids else []
    user_to_person = {str(u["_id"]): u["person_id"] for u in users}
    valid_oids = [ObjectId(pid) for pid in mentor_ids if ObjectId.is_valid(pid)]
    people = await db.persons.find({"_id": {"$in": valid_oids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(valid_oids)) if valid_oids else []
    names = {str(p["_id"]): f"{p.get('nombre', '')} {p.get('apellido', '')}".strip() for p in people}
    buckets: dict = {}
    for movement in movements:
        holder = movement.get("to_holder") if movement["movement_type"] == "ASSIGNMENT" else movement.get("from_holder")
        mentor_person_id = user_to_person.get((holder or {}).get("id")) if (holder or {}).get("type") == "user" else None
        if not mentor_person_id:
            continue
        key = (mentor_person_id, movement["book_id"])
        bucket = buckets.setdefault(key, {
            "mentor_person_id": mentor_person_id, "mentor_name": names.get(mentor_person_id, "Mentor"),
            "book_id": movement["book_id"], "book_name": books.get(movement["book_id"], movement["book_id"]),
            "assigned": 0, "delivered": 0,
        })
        if movement["movement_type"] == "ASSIGNMENT":
            bucket["assigned"] += movement["quantity"]
        else:
            bucket["delivered"] += movement["quantity"]
    items = list(buckets.values())
    for item in items:
        item["remaining"] = item["assigned"] - item["delivered"]
    return items


@router.get("/campaigns/{campaign_id}/books/{book_id}/deliveries", response_model=dict)
async def campaign_book_deliveries(campaign_id: str, book_id: str, mentor_person_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """Para que un líder 'abra' un libro de la invasión y vea a qué personas se
    entregó. Si se indica `mentor_person_id`, se limita a las entregas hechas
    desde el inventario de ESE mentor (evita mezclar destinatarios de otros
    mentores de la misma invasión y libro)."""
    if not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar las entregas de este libro")
    query = {"campaign_id": campaign_id, "book_id": book_id, "movement_type": "DELIVERY"}
    if mentor_person_id:
        mentor_user = await db.users.find_one({"person_id": mentor_person_id}, {"_id": 1})
        if not mentor_user:
            return {"items": []}
        query["from_holder.type"] = "user"
        query["from_holder.id"] = str(mentor_user["_id"])
    movements = await db.library_movements.find(query, {"_id": 0}).sort("occurred_at", -1).to_list(500)
    person_ids = {m["person_id"] for m in movements if m.get("person_id")}
    valid_oids = [ObjectId(pid) for pid in person_ids if ObjectId.is_valid(pid)]
    people = await db.persons.find({"_id": {"$in": valid_oids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(valid_oids)) if valid_oids else []
    names = {str(p["_id"]): f"{p.get('nombre', '')} {p.get('apellido', '')}".strip() for p in people}
    items = [{
        "movement_id": m["movement_id"], "person_id": m.get("person_id"), "person_name": names.get(m.get("person_id"), "—"),
        "quantity": m["quantity"], "occurred_at": serialize(m.get("occurred_at")), "mentor_label": m.get("from_holder_label"),
    } for m in movements]
    return {"items": items}


@router.get("/campaigns/{campaign_id}/report", response_model=dict)
async def campaign_report(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Vista de líderes por invasión: por cada mentor, contactos registrados,
    cuántos aceptaron, libros asignados/entregados y si tuvo actividad."""
    if not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar el informe de la invasión")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    authorities = await principal_authority_person_ids(db)
    mentor_ids = without(campaign.get("assigned_mentor_ids") or [], authorities)
    visits = [visit for visit in await db.outreach_visits.find({"campaign_id": campaign_id, "archived": {"$ne": True}}, {"_id": 0}).to_list(5000) if visit.get("mentor_person_id") not in authorities]
    book_rows = (await list_campaign_books(campaign_id, current_user))["items"]
    valid_oids = [ObjectId(pid) for pid in mentor_ids if ObjectId.is_valid(pid)]
    people = await db.persons.find({"_id": {"$in": valid_oids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(valid_oids)) if valid_oids else []
    names = {str(p["_id"]): f"{p.get('nombre', '')} {p.get('apellido', '')}".strip() for p in people}
    participations = await db.outreach_participations.find({"campaign_id": campaign_id}, {"_id": 0, "mentor_person_id": 1, "status": 1}).to_list(len(mentor_ids) or 1)
    participation_by_mentor = {p["mentor_person_id"]: p["status"] for p in participations}
    mentors = []
    for mentor_id in mentor_ids:
        mentor_visits = [v for v in visits if v.get("mentor_person_id") == mentor_id]
        participation_status = participation_by_mentor.get(mentor_id, "assigned")
        mentors.append({
            "mentor_person_id": mentor_id, "mentor_name": names.get(mentor_id, "Mentor"),
            "participation_status": participation_status,
            "contacts_total": len(mentor_visits),
            "accepted": sum(1 for v in mentor_visits if v.get("status") == "wants_followup"),
            "books": [row for row in book_rows if row["mentor_person_id"] == mentor_id],
            "has_activity": bool(mentor_visits) or participation_status == "active",
        })
    return {"campaign": serialize(campaign), "mentors": mentors}


@router.get("/person-search", response_model=dict)
async def search_persons_for_outreach(q: str = "", limit: int = 10, current_user: dict = Depends(get_current_user)):
    """Búsqueda mínima (solo nombre y person_id) para que un mentor nivel persona pueda
    elegir una Persona 360 existente sin pasar por /api/core/persons (403 para ese nivel)."""
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para buscar personas")
    clean = q.strip()
    if len(clean) < 2:
        return {"items": []}
    limit = max(1, min(limit, 20))
    pattern = re.escape(clean)
    query = {"is_archived": {"$ne": True}, "$or": [{"nombre": {"$regex": pattern, "$options": "i"}}, {"apellido": {"$regex": pattern, "$options": "i"}}]}
    people = await db.persons.find(query, {"_id": 1, "nombre": 1, "apellido": 1}).limit(limit).to_list(limit)
    return {"items": [{"person_id": str(p["_id"]), "name": f"{p.get('nombre', '')} {p.get('apellido', '')}".strip()} for p in people]}


@router.post("/visits", response_model=dict, status_code=201)
async def create_visit(payload: VisitCreateInput, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para registrar visitas")
    mentor_person_id = payload.mentor_person_id or current_user.get("person_id")
    if not mentor_person_id:
        raise HTTPException(status_code=422, detail="No se pudo determinar el mentor responsable")
    if mentor_person_id != current_user.get("person_id") and not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Solo un líder puede asignar la visita a otro mentor")
    if not await is_active_mentor(mentor_person_id):
        raise HTTPException(status_code=409, detail="El mentor responsable necesita insignia de Mentor activa")
    if payload.invasion_day:
        campaign = await db.outreach_campaigns.find_one({"campaign_id": payload.campaign_id}, {"_id": 0, "start_date": 1, "end_date": 1}) if payload.campaign_id else None
        if not campaign:
            raise HTTPException(status_code=422, detail="La jornada necesita una invasión")
        day = payload.invasion_day.isoformat()
        if not ((campaign.get("start_date") or day) <= day <= (campaign.get("end_date") or campaign.get("start_date") or day)):
            raise HTTPException(status_code=422, detail="La jornada no está dentro de las fechas de la invasión")
    doc = await resolve_and_insert_contact_visit(
        payload.contact_type, payload.person_id, payload.contact_name, payload.contact_phone, payload.contact_zone,
        payload.campaign_id, mentor_person_id, payload.note, current_user,
    )
    if payload.invasion_day:
        doc["invasion_day"] = payload.invasion_day.isoformat()
        await db.outreach_visits.update_one({"visit_id": doc["visit_id"]}, {"$set": {"invasion_day": doc["invasion_day"]}})
    return (await serialize_visits([doc], current_user))[0]


@router.get("/visits", response_model=dict)
async def list_visits(mentor_person_id: Optional[str] = None, campaign_id: Optional[str] = None, status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar visitas")
    query: dict = {"archived": {"$ne": True}}
    if not is_outreach_leader(current_user):
        allowed = await supervised_mentor_person_ids(current_user)
        if mentor_person_id and mentor_person_id in allowed:
            query["mentor_person_id"] = mentor_person_id
        else:
            query["mentor_person_id"] = {"$in": list(allowed)}
    elif mentor_person_id:
        query["mentor_person_id"] = mentor_person_id
    if campaign_id:
        query["campaign_id"] = campaign_id
    if status:
        query["status"] = status
    visits = await db.outreach_visits.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"items": await serialize_visits(visits, current_user), "total": len(visits)}


@router.get("/visits/{visit_id}", response_model=dict)
async def get_visit(visit_id: str, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar visitas")
    visit = await load_visit(visit_id)
    if not is_outreach_leader(current_user) and visit.get("mentor_person_id") != current_user.get("person_id"):
        allowed = await supervised_mentor_person_ids(current_user)
        if visit.get("mentor_person_id") not in allowed:
            raise HTTPException(status_code=403, detail="No puede consultar visitas de otro mentor")
    enriched = (await serialize_visits([visit], current_user))[0]
    history = await db.outreach_visit_history.find({"visit_id": visit_id}, {"_id": 0}).sort("occurred_at", -1).to_list(200)
    for item in history:
        item["actor_name"] = await person_display_name(item.get("actor_person_id"))
    enriched["history"] = serialize(history)
    return enriched


@router.put("/visits/{visit_id}/report", response_model=dict)
async def update_visit_report(visit_id: str, payload: VisitReportInput, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para rendir informes de visita")
    visit = await load_visit(visit_id)
    if not is_outreach_leader(current_user) and visit.get("mentor_person_id") != current_user.get("person_id"):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder puede actualizar este informe")
    fields = payload.dict(exclude_unset=True)
    person_override = fields.pop("person_id", None)
    confirm_distinct = fields.pop("confirm_distinct_person", False)
    distinct_reason = fields.pop("distinct_reason", None)
    if visit.get("enrollment_id") and fields.get("status") and fields["status"] != "wants_followup":
        raise HTTPException(status_code=409, detail="Ya inició la Ley de las 7 Semanas; el estado no se puede cambiar")
    for sku, field_name, movement_field in (("MCD", "received_mcd", "mcd_delivery_movement_id"), ("NPT", "received_npt", "npt_delivery_movement_id")):
        if field_name not in fields:
            continue
        already_delivered = bool(visit.get(movement_field))
        if fields[field_name] is True and not already_delivered:
            target_person_id, _ = await resolve_or_create_target_person(visit, current_user, person_override, confirm_distinct, distinct_reason)
            movement_id = await deliver_outreach_book(visit, sku, target_person_id, current_user)
            # Se persiste de inmediato (no solo en `fields`): si la entrega del
            # siguiente libro falla, esta ya quedó marcada y un reintento no
            # vuelve a descontarla ni a duplicar el movimiento DELIVERY.
            visit[movement_field] = movement_id
            fields[movement_field] = movement_id
            await db.outreach_visits.update_one({"visit_id": visit_id}, {"$set": {movement_field: movement_id}})
        elif fields[field_name] is False and already_delivered:
            raise HTTPException(status_code=409, detail="Ya se entregó este material; para corregirlo use la reversión de movimientos en Librería 360")
        # True + ya entregado antes: idempotente, no se repite el movimiento ni se vuelve a descontar.
    if fields.get("visit_date") is not None:
        fields["visit_date"] = fields["visit_date"].isoformat()
    if fields.get("contact_birth_date") is not None:
        fields["contact_birth_date"] = fields["contact_birth_date"].isoformat()
    if fields.get("agreed_start_date") is not None:
        fields["agreed_start_date"] = fields["agreed_start_date"].isoformat()
    fields["updated_at"] = now_utc()
    fields["decision_status"] = compute_decision_status({**visit, **fields})
    await db.outreach_visits.update_one({"visit_id": visit_id}, {"$set": fields})
    await log_visit_history(visit_id, current_user, "report_updated", {k: v for k, v in fields.items() if k != "updated_at"})
    updated = await load_visit(visit_id)
    return (await serialize_visits([updated], current_user))[0]


@router.post("/visits/{visit_id}/transfer", response_model=dict)
async def transfer_visit(visit_id: str, payload: VisitTransferInput, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para transferir visitas")
    visit = await load_visit(visit_id)
    if not is_outreach_leader(current_user) and visit.get("mentor_person_id") != current_user.get("person_id"):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder puede transferir esta visita")
    if payload.new_mentor_person_id == visit.get("mentor_person_id"):
        raise HTTPException(status_code=422, detail="El nuevo mentor debe ser diferente al actual")
    badge = await db.mentor_badges.find_one({"person_id": payload.new_mentor_person_id, "active": True}, {"_id": 1})
    if not badge:
        raise HTTPException(status_code=409, detail="El nuevo mentor necesita insignia de Mentor activa")
    qualified = await mentor_qualification(db, payload.new_mentor_person_id, None)
    if not qualified:
        raise HTTPException(status_code=409, detail="El nuevo mentor no está capacitado para impartir LBS")
    previous_mentor = visit.get("mentor_person_id")
    await db.outreach_visits.update_one({"visit_id": visit_id}, {"$set": {"mentor_person_id": payload.new_mentor_person_id, "updated_at": now_utc()}})
    await log_visit_history(visit_id, current_user, "mentor_transferred", {"from": previous_mentor, "to": payload.new_mentor_person_id, "reason": payload.reason})
    updated = await load_visit(visit_id)
    return (await serialize_visits([updated], current_user))[0]


async def open_consolidation_from_visit(visit: dict, person_id: str, current_user: dict, reason: str = "Inicia la Ley de las 7 Semanas desde una invasión") -> tuple[dict, bool]:
    """Abre (o reutiliza) el expediente de Consolidación de la persona con el
    mentor de la visita y lo vincula a la visita. Mismo mecanismo para
    «Iniciar 7 Semanas» y para «Asignar a <mentor>» desde el Perfil 360."""
    visit_id = visit["visit_id"]
    mentor_person_id = visit["mentor_person_id"]
    enrollment, created_enrollment = await create_enrollment(
        db, "consolidation", person_id, mentor_person_id, current_user["user_id"],
        status="active", next_action="Dar seguimiento al visitante", source="mentorship_outreach", source_id=visit_id,
    )
    if created_enrollment and visit.get("front_group_id") and not enrollment.get("front_group_id"):
        # Etapa 3 (punto 1 del dueño): el expediente nace con el Grupo
        # Frontal/supervisión del mentor al momento de la visita (mismo
        # snapshot que ya se guarda en el hogar/visita).
        await db.process_enrollments.update_one(
            {"enrollment_id": enrollment["enrollment_id"]},
            {"$set": {"front_group_id": visit["front_group_id"], "front_group_ancestor_ids": visit.get("front_group_ancestor_ids") or []}},
        )
        enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
    if visit.get("agreed_start_date") or visit.get("call_schedule") or visit.get("campaign_id"):
        # Se guarda ANTES de abrir etapas: `configure_entry_stages` genera el
        # calendario individual de actividades (Entrega B) usando esta fecha de
        # inicio acordada, así que debe estar en el expediente desde antes.
        await db.process_enrollments.update_one(
            {"enrollment_id": enrollment["enrollment_id"]},
            {"$set": {"outreach_agreed_start_date": visit.get("agreed_start_date"), "outreach_call_schedule": visit.get("call_schedule"), "campaign_id": visit.get("campaign_id")}},
        )
        enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
    if created_enrollment:
        # Puerta "invasion": S1 (oración) y S2 (invasión/contacto) ya se vivieron
        # con la campaña, así que el expediente abre completo y listo para MCD.
        await configure_entry_stages(db, enrollment, "invasion", current_user["user_id"], mentor_person_id=mentor_person_id)
        enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
        await assign_mentor(db, enrollment, mentor_person_id, current_user["user_id"], reason)
    now = now_utc()
    await db.outreach_visits.update_one({"visit_id": visit_id}, {"$set": {
        "enrollment_id": enrollment["enrollment_id"], "converted_person_id": person_id, "converted_at": now, "updated_at": now,
    }})
    await log_visit_history(visit_id, current_user, "seven_weeks_started", {
        "enrollment_id": enrollment["enrollment_id"], "person_id": person_id, "reused_existing_enrollment": not created_enrollment,
    })
    return enrollment, created_enrollment


@router.post("/visits/{visit_id}/start-seven-weeks", response_model=dict)
async def start_seven_weeks(visit_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user), payload: Optional[StartSevenWeeksInput] = None):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para iniciar la Ley de las 7 Semanas")
    visit = await load_visit(visit_id)
    if not is_outreach_leader(current_user) and visit.get("mentor_person_id") != current_user.get("person_id"):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder puede iniciar este proceso")
    if visit.get("status") != "wants_followup":
        raise HTTPException(status_code=409, detail="La visita debe estar en estado 'Quiere seguimiento'")
    if visit.get("enrollment_id"):
        raise HTTPException(status_code=409, detail="Esta visita ya inició la Ley de las 7 Semanas")
    mentor_person_id = visit["mentor_person_id"]
    await assert_mentor_eligible(db, mentor_person_id)
    payload = payload or StartSevenWeeksInput()
    person_id, created_person = await resolve_or_create_target_person(visit, current_user, payload.person_id, payload.confirm_distinct_person, payload.distinct_reason)
    await sync_visit_address_to_person(visit, person_id, current_user, background_tasks)
    enrollment, created_enrollment = await open_consolidation_from_visit(visit, person_id, current_user)
    updated = await load_visit(visit_id)
    enriched = (await serialize_visits([updated], current_user))[0]
    enriched["enrollment_created"] = created_enrollment
    enriched["person_created"] = created_person
    return enriched


async def load_household(household_id: str) -> dict:
    household = await db.outreach_households.find_one({"household_id": household_id, "archived": {"$ne": True}}, {"_id": 0})
    if not household:
        raise HTTPException(status_code=404, detail="Hogar no encontrado")
    return household


async def campaign_roster(campaign_id: Optional[str]) -> list:
    if not campaign_id:
        return []
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0, "assigned_mentor_ids": 1})
    return (campaign or {}).get("assigned_mentor_ids") or []


async def can_view_household(household: dict, current_user: dict, supervised_ids: set) -> bool:
    if is_outreach_leader(current_user) or household.get("mentor_person_id") == current_user.get("person_id"):
        return True
    if household.get("status") == "available":
        roster = await campaign_roster(household.get("campaign_id"))
        return current_user.get("person_id") in roster
    return household.get("mentor_person_id") in supervised_ids


@router.post("/households", response_model=dict, status_code=201)
async def create_household(payload: HouseholdInput, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para registrar hogares")
    if not (payload.address_line1 or "").strip() and not (payload.sector or "").strip():
        raise HTTPException(status_code=422, detail="Indique al menos la dirección o el sector del hogar")
    if payload.campaign_id and not await db.outreach_campaigns.find_one({"campaign_id": payload.campaign_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if payload.available:
        if not is_outreach_leader(current_user) and not can_manage_outreach_campaigns(current_user):
            raise HTTPException(status_code=403, detail="Solo un líder autorizado puede cargar casas disponibles")
        if not payload.campaign_id:
            raise HTTPException(status_code=422, detail="Indique la invasión a la que pertenece la casa disponible")
        mentor_person_id = None
    else:
        mentor_person_id = payload.mentor_person_id or current_user.get("person_id")
        if not mentor_person_id:
            raise HTTPException(status_code=422, detail="No se pudo determinar el mentor responsable")
        if mentor_person_id != current_user.get("person_id") and not is_outreach_leader(current_user):
            raise HTTPException(status_code=403, detail="Solo un líder puede asignar el hogar a otro mentor")
        if not await is_active_mentor(mentor_person_id):
            raise HTTPException(status_code=409, detail="El mentor responsable necesita insignia de Mentor activa")
    snapshot = await supervision_snapshot(mentor_person_id)
    now = now_utc()
    household_id = str(uuid4())
    doc = {
        "_id": household_id, "household_id": household_id, "campaign_id": payload.campaign_id,
        "mentor_person_id": mentor_person_id, "status": "available" if mentor_person_id is None else "assigned",
        "address_line1": payload.address_line1, "address_line2": payload.address_line2,
        "address_city": payload.address_city, "address_state": payload.address_state, "address_zip": payload.address_zip,
        "sector": payload.sector, "note": payload.note, "is_draft": payload.is_draft,
        "front_group_id": snapshot["front_group_id"], "front_group_ancestor_ids": snapshot["front_group_ancestor_ids"],
        "archived": False, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
        "location_reference": (payload.location_reference or "").strip() or None,
    }
    with_point = payload.latitude is not None and payload.longitude is not None
    if with_point:
        doc.update({"latitude": payload.latitude, "longitude": payload.longitude, "location_accuracy_m": payload.location_accuracy_m,
                    "location_source": payload.location_source or "manual", "location_updated_at": now})
    else:
        doc.update({"latitude": None, "longitude": None})
    await db.outreach_households.insert_one(doc)
    if not with_point:
        from household_location import mark_pending_and_geocode
        await mark_pending_and_geocode([household_id])
        doc = await db.outreach_households.find_one({"household_id": household_id}, {"_id": 0}) or doc
    if payload.campaign_id and mentor_person_id:
        await mark_participation_active(payload.campaign_id, mentor_person_id)
    return serialize(doc)


@router.post("/campaigns/{campaign_id}/households/import", response_model=dict, status_code=201)
async def import_available_households(campaign_id: str, payload: HouseholdImportInput, current_user: dict = Depends(get_current_user)):
    """Carga masiva de casas DISPONIBLES (sin mentor todavía) para que los
    mentores de esta invasión las tomen desde el mapa — reservado a quien
    puede administrar la invasión (pedido del dueño: 'pastoral/coordinador/
    líder autorizado carga o importa casas')."""
    if not is_outreach_leader(current_user) and not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo un líder autorizado puede importar casas disponibles")
    if not await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    now = now_utc()
    docs = []
    skipped = 0
    for entry in payload.entries:
        if not (entry.address_line1 or "").strip() and not (entry.sector or "").strip():
            skipped += 1
            continue
        household_id = str(uuid4())
        docs.append({
            "_id": household_id, "household_id": household_id, "campaign_id": campaign_id,
            "mentor_person_id": None, "status": "available",
            "address_line1": entry.address_line1, "address_line2": None, "address_city": None, "address_state": None, "address_zip": None,
            "sector": entry.sector, "note": entry.note, "is_draft": False,
            "location_reference": entry.location_reference, "latitude": None, "longitude": None,
            "front_group_id": None, "front_group_ancestor_ids": [],
            "archived": False, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
        })
    if docs:
        await db.outreach_households.insert_many(docs)
        # Casas importadas solo con dirección: se ubican en segundo plano (estado "pending").
        from household_location import mark_pending_and_geocode
        await mark_pending_and_geocode([doc["household_id"] for doc in docs])
    return {"created": len(docs), "skipped": skipped}


async def enrich_households(households: list[dict]) -> list[dict]:
    """Adjunta `campaign_name` y conteo de intentos (`attempts`/`last_occurred_at`)
    — usado tanto en `/households` como en `/my-branch-overview` para que ambas
    vistas muestren exactamente la misma información."""
    household_ids = [h["household_id"] for h in households]
    campaign_ids = {h["campaign_id"] for h in households if h.get("campaign_id")}
    campaigns = await db.outreach_campaigns.find({"campaign_id": {"$in": list(campaign_ids)}}, {"_id": 0, "campaign_id": 1, "name": 1}).to_list(len(campaign_ids)) if campaign_ids else []
    campaign_names = {c["campaign_id"]: c["name"] for c in campaigns}
    event_stats: dict = {}
    if household_ids:
        async for item in db.outreach_visit_events.aggregate([
            {"$match": {"household_id": {"$in": household_ids}}},
            {"$group": {"_id": "$household_id", "count": {"$sum": 1}, "last_occurred_at": {"$max": "$occurred_at"}}},
        ]):
            event_stats[item["_id"]] = {"attempts": item["count"], "last_occurred_at": serialize(item["last_occurred_at"])}
    for household in households:
        household["campaign_name"] = campaign_names.get(household.get("campaign_id"))
        household.update(event_stats.get(household["household_id"], {"attempts": 0, "last_occurred_at": None}))
    return households


@router.get("/households", response_model=dict)
async def list_households(mentor_person_id: Optional[str] = None, campaign_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar hogares")
    query: dict = {"archived": {"$ne": True}}
    if not is_outreach_leader(current_user):
        allowed = await supervised_mentor_person_ids(current_user)
        if mentor_person_id and mentor_person_id in allowed:
            query["mentor_person_id"] = mentor_person_id
        else:
            query["mentor_person_id"] = {"$in": list(allowed)}
    elif mentor_person_id:
        query["mentor_person_id"] = mentor_person_id
    if campaign_id:
        query["campaign_id"] = campaign_id
    households = await db.outreach_households.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    households = await enrich_households(households)
    return {"items": serialize(households), "total": len(households)}


@router.get("/campaigns/{campaign_id}/households/available", response_model=dict)
async def list_available_households(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Casas DISPONIBLES de esta invasión: visibles para cualquier mentor en
    el roster (pool compartido para tomar) y para el líder — nunca para quien
    no participa en esta invasión."""
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar hogares")
    roster = await campaign_roster(campaign_id)
    if not is_outreach_leader(current_user) and not can_manage_outreach_campaigns(current_user) and current_user.get("person_id") not in roster:
        raise HTTPException(status_code=403, detail="No participa en esta invasión")
    households = await db.outreach_households.find(
        {"campaign_id": campaign_id, "mentor_person_id": None, "archived": {"$ne": True}}, {"_id": 0},
    ).sort("created_at", 1).to_list(500)
    households = await enrich_households(households)
    return {"items": serialize(households), "total": len(households)}


@router.post("/households/{household_id}/claim", response_model=dict)
async def claim_household(household_id: str, current_user: dict = Depends(get_current_user)):
    """El mentor TOMA una casa disponible para sí mismo: operación atómica e
    idempotente (el filtro exige `mentor_person_id: None`), así nunca dos
    mentores terminan con la misma casa aunque la toquen al mismo tiempo."""
    mentor_person_id = current_user.get("person_id")
    if not mentor_person_id:
        raise HTTPException(status_code=403, detail="Esta cuenta no está vinculada a un Perfil 360")
    if not await is_active_mentor(mentor_person_id):
        raise HTTPException(status_code=409, detail="Necesita insignia de Mentor activa para tomar una casa")
    household = await load_household(household_id)
    if household.get("mentor_person_id") == mentor_person_id:
        return serialize(household)
    roster = await campaign_roster(household.get("campaign_id"))
    if mentor_person_id not in roster:
        raise HTTPException(status_code=403, detail="No está en el roster de mentores de esta invasión")
    snapshot = await supervision_snapshot(mentor_person_id)
    now = now_utc()
    updated = await db.outreach_households.find_one_and_update(
        {"household_id": household_id, "mentor_person_id": None, "archived": {"$ne": True}},
        {"$set": {
            "mentor_person_id": mentor_person_id, "status": "assigned", "claimed_at": now, "updated_at": now,
            "front_group_id": snapshot["front_group_id"], "front_group_ancestor_ids": snapshot["front_group_ancestor_ids"],
        }},
        return_document=True, projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(status_code=409, detail="Esta casa ya fue tomada por otro mentor")
    if household.get("campaign_id"):
        await mark_participation_active(household["campaign_id"], mentor_person_id)
    return serialize(updated)


@router.post("/households/{household_id}/release", response_model=dict)
async def release_household(household_id: str, current_user: dict = Depends(get_current_user)):
    """Devuelve una casa tomada al pool de disponibles (el propio mentor que
    la tiene, o un líder). No borra el historial de intentos/visitas ya
    registrados en ella."""
    household = await load_household(household_id)
    mentor_person_id = household.get("mentor_person_id")
    if not mentor_person_id:
        raise HTTPException(status_code=409, detail="Esta casa ya está disponible")
    if mentor_person_id != current_user.get("person_id") and not is_outreach_leader(current_user) and not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder puede devolver esta casa")
    now = now_utc()
    updated = await db.outreach_households.find_one_and_update(
        {"household_id": household_id, "mentor_person_id": mentor_person_id, "archived": {"$ne": True}},
        {"$set": {"mentor_person_id": None, "status": "available", "claimed_at": None, "updated_at": now}},
        return_document=True, projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(status_code=409, detail="Esta casa ya fue modificada por otro usuario, actualice e intente de nuevo")
    return serialize(updated)


@router.post("/households/{household_id}/assign", response_model=dict)
async def assign_household(household_id: str, payload: HouseholdAssignInput, current_user: dict = Depends(get_current_user)):
    """Asignación DIRECTA de un responsable autorizado (líder de invasión) a
    un mentor puntual — solo sobre una casa hoy disponible, atómica/idempotente
    igual que `claim`, para no quitarle en silencio una casa a otro mentor."""
    if not is_outreach_leader(current_user) and not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo un responsable autorizado puede asignar casas directamente")
    if not await is_active_mentor(payload.mentor_person_id):
        raise HTTPException(status_code=409, detail="El mentor seleccionado necesita insignia de Mentor activa")
    household = await load_household(household_id)
    roster = await campaign_roster(household.get("campaign_id"))
    if payload.mentor_person_id not in roster:
        raise HTTPException(status_code=409, detail="El mentor seleccionado no está en el roster de esta invasión")
    if household.get("mentor_person_id") == payload.mentor_person_id:
        return serialize(household)
    snapshot = await supervision_snapshot(payload.mentor_person_id)
    now = now_utc()
    updated = await db.outreach_households.find_one_and_update(
        {"household_id": household_id, "mentor_person_id": None, "archived": {"$ne": True}},
        {"$set": {
            "mentor_person_id": payload.mentor_person_id, "status": "assigned", "claimed_at": now, "updated_at": now,
            "front_group_id": snapshot["front_group_id"], "front_group_ancestor_ids": snapshot["front_group_ancestor_ids"],
        }},
        return_document=True, projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(status_code=409, detail="Esta casa ya tiene un mentor asignado; devuélvala primero para reasignarla")
    if household.get("campaign_id"):
        await ensure_participation(household["campaign_id"], payload.mentor_person_id)
        await mark_participation_active(household["campaign_id"], payload.mentor_person_id)
    return serialize(updated)


@router.get("/households/{household_id}", response_model=dict)
async def get_household(household_id: str, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar hogares")
    household = await load_household(household_id)
    supervised_ids = await supervised_mentor_person_ids(current_user)
    if not await can_view_household(household, current_user, supervised_ids):
        raise HTTPException(status_code=403, detail="No puede consultar este hogar")
    events = await db.outreach_visit_events.find({"household_id": household_id}, {"_id": 0}).sort("occurred_at", -1).to_list(200)
    visits = await db.outreach_visits.find({"household_id": household_id, "archived": {"$ne": True}}, {"_id": 0}).to_list(200)
    return {"household": serialize(household), "events": serialize(events), "visits": await serialize_visits(visits, current_user)}


@router.put("/households/{household_id}", response_model=dict)
async def update_household(household_id: str, payload: HouseholdUpdateInput, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para editar hogares")
    household = await load_household(household_id)
    if not is_outreach_leader(current_user) and household.get("mentor_person_id") != current_user.get("person_id"):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder puede editar este hogar")
    fields = payload.dict(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Indique al menos un campo para actualizar")
    fields["updated_at"] = now_utc()
    address_changed = any(key in fields and fields[key] != household.get(key) for key in ("address_line1", "address_line2", "address_city", "address_state", "address_zip"))
    if address_changed and household.get("location_source") in (None, "geocoded"):
        # La ubicación geocodificada era de la dirección anterior; GPS o manual se conservan.
        fields.update({"latitude": None, "longitude": None, "location_source": None, "location_accuracy_m": None})
    await db.outreach_households.update_one({"household_id": household_id}, {"$set": fields})
    if address_changed:
        from household_location import mark_pending_and_geocode
        await mark_pending_and_geocode([household_id])
    return serialize(await load_household(household_id))


@router.post("/households/{household_id}/events", response_model=dict, status_code=201)
async def create_visit_event(household_id: str, payload: VisitEventInput, current_user: dict = Depends(get_current_user)):
    """Intento de visita a un Hogar (Etapa 2): 'sin respuesta'/'no está en
    casa'/'rechazó' NUNCA llevan personas (no se inventan datos); 'contacted'
    puede traer 0 personas solo si se guarda como borrador (`is_draft`)."""
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para registrar intentos de visita")
    household = await load_household(household_id)
    if not is_outreach_leader(current_user) and household.get("mentor_person_id") != current_user.get("person_id"):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable o un líder puede registrar un intento en este hogar")
    if payload.result != "contacted" and payload.persons:
        raise HTTPException(status_code=422, detail="Un intento sin contacto no debe llevar personas registradas (no se inventan datos)")
    if payload.result == "contacted" and not payload.persons and not payload.is_draft:
        raise HTTPException(status_code=422, detail="Registre al menos un contacto, o guarde este intento como borrador")
    now = now_utc()
    event_id = str(uuid4())
    event_doc = {
        "_id": event_id, "visit_event_id": event_id, "household_id": household_id, "campaign_id": household.get("campaign_id"),
        "mentor_person_id": household["mentor_person_id"], "result": payload.result, "note": payload.note,
        "opened": payload.result in {"contacted", "refused"},
        "is_draft": payload.is_draft, "occurred_at": now, "created_by_user_id": current_user["user_id"], "created_at": now,
    }
    await db.outreach_visit_events.insert_one(event_doc)
    created_visits = []
    for entry in payload.persons:
        visit_doc = await resolve_and_insert_contact_visit(
            entry.contact_type, entry.person_id, entry.contact_name, entry.contact_phone, household.get("sector"),
            household.get("campaign_id"), household["mentor_person_id"], None, current_user,
            household_id=household_id, visit_event_id=event_id,
        )
        created_visits.append(visit_doc)
    if household.get("campaign_id"):
        await mark_participation_active(household["campaign_id"], household["mentor_person_id"])
    from outreach_doors import refresh_door_status
    await refresh_door_status(household_id)
    return {"event": serialize(event_doc), "visits": await serialize_visits(created_visits, current_user)}


async def mentor_ids_in_group_branch(front_group_id: str) -> list:
    """Mentores (insignia activa, persona no archivada) de ese Grupo Frontal
    o de cualquiera de sus sub-grupos. Compartido por `mentors_by_group` y
    `add_campaign_mentors` para no repetir el criterio."""
    group_ids = await descendant_group_ids(db, front_group_id)
    person_ids = await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": group_ids}, "active": True})
    if not person_ids:
        return []
    badge_docs = await db.mentor_badges.find({"person_id": {"$in": person_ids}, "active": True}, {"_id": 0, "person_id": 1}).to_list(len(person_ids))
    mentor_ids = [doc["person_id"] for doc in badge_docs]
    if not mentor_ids:
        return []
    valid_oids = [ObjectId(pid) for pid in mentor_ids if ObjectId.is_valid(pid)]
    archived_ids = {str(p["_id"]) for p in await db.persons.find({"_id": {"$in": valid_oids}, "is_archived": True}, {"_id": 1}).to_list(len(valid_oids))}
    return without([pid for pid in mentor_ids if pid not in archived_ids], await principal_authority_person_ids(db))


@router.get("/mentors-by-group/{front_group_id}", response_model=dict)
async def mentors_by_group(front_group_id: str, current_user: dict = Depends(get_current_user)):
    """Para el roster de una invasión: todos los mentores (insignia activa)
    que pertenecen a ese Grupo Frontal o a cualquiera de sus sub-grupos."""
    if not can_manage_outreach_campaigns(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede armar el roster por grupo")
    await load_front_group(db, front_group_id)
    mentor_ids = await mentor_ids_in_group_branch(front_group_id)
    if not mentor_ids:
        return {"items": []}
    valid_oids = [ObjectId(pid) for pid in mentor_ids if ObjectId.is_valid(pid)]
    people = await db.persons.find({"_id": {"$in": valid_oids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(valid_oids))
    accounts = await db.users.find({"person_id": {"$in": mentor_ids}}, {"_id": 0, "person_id": 1, "is_active": 1}).to_list(len(mentor_ids))
    account_status = {item["person_id"]: bool(item.get("is_active", True)) for item in accounts}
    items = [{
        "person_id": str(p["_id"]), "name": f"{p.get('nombre', '')} {p.get('apellido', '')}".strip(),
        "has_account": str(p["_id"]) in account_status, "account_active": account_status.get(str(p["_id"]), False),
    } for p in people]
    return {"items": items}


@router.get("/my-branch-overview", response_model=dict)
async def my_branch_overview(current_user: dict = Depends(get_current_user)):
    """'Supervisión instantánea': para un Líder/Colíder de Grupo Frontal que
    NO es líder de invasiones ni mentor, ve en SOLO LECTURA los hogares y
    visitas de los mentores de su rama (y sub-ramas). Si no supervisa a
    nadie, `is_supervisor` queda en falso y el frontend no muestra nada."""
    if is_outreach_leader(current_user):
        return {"is_supervisor": False, "households": [], "visits": []}
    branch_ids = await support_group_ids(db, current_user)
    if not branch_ids:
        return {"is_supervisor": False, "households": [], "visits": []}
    self_id = current_user.get("person_id")
    mentor_ids = [pid for pid in await db.front_group_assignments.distinct(
        "person_id", {"front_group_id": {"$in": list(branch_ids)}, "active": True},
    ) if pid != self_id]
    if not mentor_ids:
        return {"is_supervisor": False, "households": [], "visits": []}
    households = await db.outreach_households.find({"mentor_person_id": {"$in": mentor_ids}, "archived": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(500)
    households = await enrich_households(households)
    visits = await db.outreach_visits.find({"mentor_person_id": {"$in": mentor_ids}, "archived": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"is_supervisor": True, "households": serialize(households), "visits": await serialize_visits(visits, current_user)}


@router.get("/my-branch-library", response_model=dict)
async def my_branch_library(current_user: dict = Depends(get_current_user)):
    """C8 (Librería): espejo de solo lectura de Librería 360 para el propio
    mentor y, si supervisa una rama, para cada mentor de su rama — asignado,
    entregado (con destinatario y fecha), devuelto y en custodia (on_hand).
    Nunca escribe movimientos de Librería; solo los refleja."""
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar materiales de invasiones")
    if is_outreach_leader(current_user):
        mentor_ids = sorted(await db.outreach_participations.distinct("mentor_person_id", {}))
    else:
        mentor_ids = sorted(await supervised_mentor_person_ids(current_user))
    if not mentor_ids:
        return {"items": []}
    users = await db.users.find({"person_id": {"$in": mentor_ids}}, {"_id": 1, "person_id": 1}).to_list(len(mentor_ids))
    user_to_person = {str(u["_id"]): u["person_id"] for u in users}
    user_ids = list(user_to_person.keys())
    if not user_ids:
        return {"items": []}
    movements = await db.library_movements.find(
        {"$or": [{"from_holder.type": "user", "from_holder.id": {"$in": user_ids}}, {"to_holder.type": "user", "to_holder.id": {"$in": user_ids}}]},
        {"_id": 0},
    ).sort("occurred_at", 1).to_list(10000)
    holdings = await db.library_holdings.find({"holder_type": "user", "holder_id": {"$in": user_ids}}, {"_id": 0}).to_list(5000)
    on_hand_by = {(h["holder_id"], h["book_id"]): h["quantity_on_hand"] for h in holdings}
    books = {b["book_id"]: b["name"] for b in await db.library_books.find({}, {"_id": 0, "book_id": 1, "name": 1}).to_list(2000)}
    recipient_ids = {m["person_id"] for m in movements if m.get("person_id")}
    valid_oids = [ObjectId(pid) for pid in recipient_ids | set(mentor_ids) if ObjectId.is_valid(pid)]
    people = await db.persons.find({"_id": {"$in": valid_oids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(valid_oids)) if valid_oids else []
    names = {str(p["_id"]): f"{p.get('nombre', '')} {p.get('apellido', '')}".strip() for p in people}
    buckets: dict = {}
    for movement in movements:
        from_h, to_h = movement.get("from_holder") or {}, movement.get("to_holder") or {}
        mentor_user_id = from_h.get("id") if from_h.get("type") == "user" and from_h.get("id") in user_ids else (to_h.get("id") if to_h.get("type") == "user" and to_h.get("id") in user_ids else None)
        if not mentor_user_id:
            continue
        mentor_person_id = user_to_person[mentor_user_id]
        key = (mentor_user_id, movement["book_id"])
        bucket = buckets.setdefault(key, {
            "mentor_person_id": mentor_person_id, "mentor_name": names.get(mentor_person_id, "Mentor"),
            "book_id": movement["book_id"], "book_name": books.get(movement["book_id"], movement["book_id"]),
            "assigned": 0, "delivered": [], "returned": 0,
        })
        if movement["movement_type"] == "ASSIGNMENT" and to_h.get("id") == mentor_user_id:
            bucket["assigned"] += movement["quantity"]
        elif movement["movement_type"] == "DELIVERY" and from_h.get("id") == mentor_user_id:
            bucket["delivered"].append({"person_id": movement.get("person_id"), "person_name": names.get(movement.get("person_id"), "—"), "quantity": movement["quantity"], "occurred_at": serialize(movement.get("occurred_at"))})
        elif movement["movement_type"] == "RETURN" and from_h.get("id") == mentor_user_id:
            bucket["returned"] += movement["quantity"]
    items = []
    for (mentor_user_id, book_id), bucket in buckets.items():
        bucket["delivered_total"] = sum(entry["quantity"] for entry in bucket["delivered"])
        bucket["in_custody"] = on_hand_by.get((mentor_user_id, book_id), 0)
        items.append(bucket)
    return {"items": items}


@router.get("/dashboard", response_model=dict)
async def outreach_dashboard(current_user: dict = Depends(get_current_user)):
    if not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar el panel de invasiones")
    authorities = await principal_authority_person_ids(db)
    # La actividad registrada por la autoridad pastoral principal no cuenta como participación.
    visits = [v for v in await db.outreach_visits.find({"archived": {"$ne": True}}, {"_id": 0}).to_list(20000) if v.get("mentor_person_id") not in authorities]
    mentor_ids = sorted({v["mentor_person_id"] for v in visits if v.get("mentor_person_id")})
    valid_oids = [ObjectId(pid) for pid in mentor_ids if ObjectId.is_valid(pid)]
    people = await db.persons.find({"_id": {"$in": valid_oids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(valid_oids)) if valid_oids else []
    names = {str(p["_id"]): f"{p.get('nombre', '')} {p.get('apellido', '')}".strip() for p in people}
    campaigns = await db.outreach_campaigns.find({}, {"_id": 0, "campaign_id": 1, "name": 1}).to_list(500)
    campaign_names = {c["campaign_id"]: c["name"] for c in campaigns}

    def summarize(items: list) -> dict:
        return {
            "total": len(items),
            "assigned": sum(1 for v in items if v["status"] == "assigned"),
            "not_found": sum(1 for v in items if v["status"] == "not_found"),
            "visited": sum(1 for v in items if v["status"] == "visited"),
            "rejected": sum(1 for v in items if v["status"] == "rejected"),
            "wants_followup": sum(1 for v in items if v["status"] == "wants_followup"),
            "received_mcd": sum(1 for v in items if v.get("received_mcd")),
            "received_npt": sum(1 for v in items if v.get("received_npt")),
            "lbs_pending": sum(1 for v in items if v.get("lbs_decision") == "needs_lbs"),
            "seven_weeks_started": sum(1 for v in items if v.get("enrollment_id")),
        }

    by_mentor = [
        {"mentor_person_id": mentor_id, "mentor_name": names.get(mentor_id, "Mentor"), **summarize([v for v in visits if v.get("mentor_person_id") == mentor_id])}
        for mentor_id in mentor_ids
    ]
    by_campaign = [
        {"campaign_id": campaign_id, "campaign_name": campaign_name, **summarize([v for v in visits if v.get("campaign_id") == campaign_id])}
        for campaign_id, campaign_name in campaign_names.items()
    ]
    no_campaign_visits = [v for v in visits if not v.get("campaign_id")]
    if no_campaign_visits:
        by_campaign.append({"campaign_id": None, "campaign_name": "Sin campaña", **summarize(no_campaign_visits)})
    return {"totals": summarize(visits), "by_mentor": by_mentor, "by_campaign": by_campaign}


async def backfill_decision_status() -> None:
    """Migración idempotente (Etapa 2): calcula `decision_status` para visitas
    que todavía no lo tienen, a partir de `status`/`agreed_start_date` — nunca
    inventa un dato, y nunca vuelve a tocar un documento ya migrado."""
    cursor = db.outreach_visits.find({"decision_status": {"$exists": False}}, {"_id": 1, "status": 1, "agreed_start_date": 1})
    async for item in cursor:
        await db.outreach_visits.update_one({"_id": item["_id"]}, {"$set": {"decision_status": compute_decision_status(item)}})


async def ensure_outreach_indexes() -> None:
    await db.outreach_campaigns.create_index("campaign_id", unique=True)
    await db.outreach_visits.create_index("visit_id", unique=True)
    await db.outreach_visits.create_index("mentor_person_id")
    await db.outreach_visits.create_index("campaign_id")
    await db.outreach_visits.create_index("phone_normalized")
    await db.outreach_visits.create_index("person_id")
    await db.outreach_visits.create_index("household_id")
    await db.outreach_visit_history.create_index("history_id", unique=True)
    await db.outreach_visit_history.create_index([("visit_id", 1), ("occurred_at", -1)])
    await db.outreach_households.create_index("household_id", unique=True)
    await db.outreach_households.create_index("mentor_person_id")
    await db.outreach_households.create_index("campaign_id")
    await db.outreach_visit_events.create_index("visit_event_id", unique=True)
    await db.outreach_visit_events.create_index([("household_id", 1), ("occurred_at", -1)])
    await db.outreach_participations.create_index([("campaign_id", 1), ("mentor_person_id", 1)], unique=True)
    await backfill_decision_status()
