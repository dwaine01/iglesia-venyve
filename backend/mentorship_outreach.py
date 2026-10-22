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
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import (
    MENTORSHIP_OUTREACH_ASSIGN,
    MENTORSHIP_OUTREACH_REPORT,
    has_capability,
    is_global_pastoral_authority,
)
from consolidation_service import assert_mentor_eligible, assign_mentor, configure_entry_stages, load_person, mentor_qualification
from core_person import _normalize as normalize_person_name, next_person_number
from process_engine import create_enrollment, now_utc, serialize
from server import db, get_current_user


router = APIRouter(prefix="/api/mentorship/outreach", tags=["mentorship-outreach"])

VISIT_STATUSES = ("assigned", "not_found", "visited", "rejected", "wants_followup")
LBS_DECISIONS = ("none", "accepted", "needs_lbs")


class CampaignInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    zone_notes: Optional[str] = Field(default=None, max_length=1000)


class CampaignUpdateInput(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    zone_notes: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[Literal["active", "closed"]] = None


class VisitCreateInput(BaseModel):
    contact_type: Literal["new", "existing"]
    person_id: Optional[str] = None
    contact_name: Optional[str] = Field(default=None, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=40)
    contact_zone: Optional[str] = Field(default=None, max_length=300)
    campaign_id: Optional[str] = None
    mentor_person_id: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=1000)


class VisitReportInput(BaseModel):
    status: Literal["assigned", "not_found", "visited", "rejected", "wants_followup"]
    visit_date: Optional[date] = None
    received_mcd: Optional[bool] = None
    received_npt: Optional[bool] = None
    lbs_decision: Optional[Literal["none", "accepted", "needs_lbs"]] = None
    note: Optional[str] = Field(default=None, max_length=1000)


class VisitTransferInput(BaseModel):
    new_mentor_person_id: str
    reason: Optional[str] = Field(default=None, max_length=500)


def normalize_phone(value: Optional[str]) -> str:
    """Últimos 10 dígitos (mismo criterio que membership_import.py) para que un
    prefijo de país opcional (+58, 0, etc.) no impida detectar duplicados."""
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else digits


def is_outreach_leader(current_user: dict) -> bool:
    return is_global_pastoral_authority(current_user) or has_capability(current_user, MENTORSHIP_OUTREACH_ASSIGN)


async def is_active_mentor(person_id: Optional[str]) -> bool:
    if not person_id:
        return False
    badge = await db.mentor_badges.find_one({"person_id": person_id, "active": True}, {"_id": 1})
    return bool(badge)


async def can_use_outreach(current_user: dict) -> bool:
    if is_outreach_leader(current_user) or has_capability(current_user, MENTORSHIP_OUTREACH_REPORT):
        return True
    return await is_active_mentor(current_user.get("person_id"))


def reveal_contact(visit: dict, current_user: dict) -> bool:
    return is_outreach_leader(current_user) or visit.get("mentor_person_id") == current_user.get("person_id")


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
    results = []
    for visit in visits:
        reveal = reveal_contact(visit, current_user)
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
            "status": visit.get("status"),
            "visit_date": visit.get("visit_date"),
            "received_mcd": bool(visit.get("received_mcd")),
            "received_npt": bool(visit.get("received_npt")),
            "lbs_decision": visit.get("lbs_decision", "none"),
            "note": visit.get("note"),
            "enrollment_id": visit.get("enrollment_id"),
            "created_at": serialize(visit.get("created_at")),
            "updated_at": serialize(visit.get("updated_at")),
        }
        if reveal:
            item["contact_phone"] = visit.get("contact_phone")
            item["contact_zone"] = visit.get("contact_zone")
        results.append(item)
    return results


async def find_or_create_person_for_visit(contact_name: Optional[str], contact_phone: Optional[str], user_id: str) -> tuple:
    """Deduplica por teléfono (contra person_contacts) y, si no hay teléfono, por nombre
    exacto (igual criterio que campaign_venycome.find_or_create_person); si no encuentra
    nada, crea una Persona 360 mínima."""
    phone_digits = normalize_phone(contact_phone)
    if phone_digits:
        contacts = await db.person_contacts.find({"tipo": {"$in": ["telefono", "whatsapp"]}}, {"_id": 0, "person_id": 1, "valor": 1}).to_list(5000)
        for contact in contacts:
            if normalize_phone(contact.get("valor")) == phone_digits and ObjectId.is_valid(contact.get("person_id", "")):
                person = await db.persons.find_one({"_id": ObjectId(contact["person_id"]), "is_archived": {"$ne": True}}, {"_id": 1})
                if person:
                    return contact["person_id"], False
    if contact_name and contact_name.strip():
        norm = normalize_person_name(contact_name)
        if norm:
            candidates = await db.persons.find({"search_key": norm, "is_archived": {"$ne": True}}, {"_id": 1}).to_list(5)
            if len(candidates) == 1:
                return str(candidates[0]["_id"]), False
    now = now_utc()
    tokens = (contact_name or "Contacto Invasión").strip().split()
    nombre = tokens[0] if tokens else "Contacto"
    apellido = " ".join(tokens[1:]) if len(tokens) > 1 else ""
    doc = {
        "nombre": nombre, "apellido": apellido, "fecha_nacimiento": None, "age_category": None,
        "person_number": await next_person_number(), "search_key": normalize_person_name(contact_name or nombre),
        "idempotency_key": str(uuid4()), "version": 1, "created_by": user_id,
        "created_at": now, "updated_at": now, "source": "mentorship_outreach",
    }
    result = await db.persons.insert_one(doc)
    new_person_id = str(result.inserted_id)
    if phone_digits:
        await db.person_contacts.insert_one({
            "_id": str(uuid4()), "person_id": new_person_id, "tipo": "telefono",
            "valor": contact_phone, "es_principal": True, "created_at": now,
        })
    return new_person_id, True


@router.post("/campaigns", response_model=dict, status_code=201)
async def create_campaign(payload: CampaignInput, current_user: dict = Depends(get_current_user)):
    if not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para crear campañas de invasión")
    now = now_utc()
    campaign_id = str(uuid4())
    doc = {
        "_id": campaign_id, "campaign_id": campaign_id, "name": payload.name.strip(),
        "start_date": payload.start_date.isoformat() if payload.start_date else None,
        "end_date": payload.end_date.isoformat() if payload.end_date else None,
        "zone_notes": payload.zone_notes, "status": "active",
        "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.outreach_campaigns.insert_one(doc)
    return serialize(doc)


@router.get("/campaigns", response_model=dict)
async def list_campaigns(current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar invasiones")
    items = await db.outreach_campaigns.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"items": serialize(items)}


@router.put("/campaigns/{campaign_id}", response_model=dict)
async def update_campaign(campaign_id: str, payload: CampaignUpdateInput, current_user: dict = Depends(get_current_user)):
    if not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para administrar campañas de invasión")
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    fields = payload.dict(exclude_unset=True)
    if fields.get("start_date") is not None:
        fields["start_date"] = fields["start_date"].isoformat()
    if fields.get("end_date") is not None:
        fields["end_date"] = fields["end_date"].isoformat()
    fields["updated_at"] = now_utc()
    await db.outreach_campaigns.update_one({"campaign_id": campaign_id}, {"$set": fields})
    return serialize(await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0}))


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
    phone_digits = None
    person_id = None
    if payload.contact_type == "existing":
        if not payload.person_id:
            raise HTTPException(status_code=422, detail="Seleccione la persona existente")
        await load_person(db, payload.person_id)
        duplicate = await db.outreach_visits.find_one({"person_id": payload.person_id, "archived": {"$ne": True}}, {"_id": 0, "mentor_person_id": 1})
        if duplicate:
            mentor_name = await person_display_name(duplicate.get("mentor_person_id"))
            raise HTTPException(status_code=409, detail=f"Esta persona ya tiene una visita activa registrada (mentor: {mentor_name or 'desconocido'})")
        person_id = payload.person_id
    else:
        if not payload.contact_name or not payload.contact_name.strip():
            raise HTTPException(status_code=422, detail="El nombre del contacto es obligatorio")
        phone_digits = normalize_phone(payload.contact_phone)
        if phone_digits:
            duplicate = await db.outreach_visits.find_one({"phone_normalized": phone_digits, "archived": {"$ne": True}}, {"_id": 0, "mentor_person_id": 1})
            if duplicate:
                mentor_name = await person_display_name(duplicate.get("mentor_person_id"))
                raise HTTPException(status_code=409, detail=f"Ya existe una visita registrada con ese teléfono (mentor: {mentor_name or 'desconocido'})")
    if payload.campaign_id:
        campaign = await db.outreach_campaigns.find_one({"campaign_id": payload.campaign_id}, {"_id": 1})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
    now = now_utc()
    visit_id = str(uuid4())
    doc = {
        "_id": visit_id, "visit_id": visit_id, "campaign_id": payload.campaign_id,
        "mentor_person_id": mentor_person_id, "contact_type": payload.contact_type,
        "person_id": person_id, "contact_name": payload.contact_name.strip() if payload.contact_name else None,
        "contact_phone": payload.contact_phone, "contact_zone": payload.contact_zone,
        "phone_normalized": phone_digits, "status": "assigned", "visit_date": None,
        "received_mcd": False, "received_npt": False, "lbs_decision": "none",
        "note": payload.note, "enrollment_id": None, "converted_person_id": None, "converted_at": None,
        "archived": False, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now,
    }
    await db.outreach_visits.insert_one(doc)
    await log_visit_history(visit_id, current_user, "visit_created", {"mentor_person_id": mentor_person_id, "contact_type": payload.contact_type})
    return (await serialize_visits([doc], current_user))[0]


@router.get("/visits", response_model=dict)
async def list_visits(mentor_person_id: Optional[str] = None, campaign_id: Optional[str] = None, status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    if not await can_use_outreach(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar visitas")
    query: dict = {"archived": {"$ne": True}}
    if not is_outreach_leader(current_user):
        query["mentor_person_id"] = current_user.get("person_id")
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
    if visit.get("enrollment_id") and fields.get("status") and fields["status"] != "wants_followup":
        raise HTTPException(status_code=409, detail="Ya inició la Ley de las 7 Semanas; el estado no se puede cambiar")
    if fields.get("visit_date") is not None:
        fields["visit_date"] = fields["visit_date"].isoformat()
    fields["updated_at"] = now_utc()
    await db.outreach_visits.update_one({"visit_id": visit_id}, {"$set": fields})
    await log_visit_history(visit_id, current_user, "report_updated", fields)
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


@router.post("/visits/{visit_id}/start-seven-weeks", response_model=dict)
async def start_seven_weeks(visit_id: str, current_user: dict = Depends(get_current_user)):
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
    if visit["contact_type"] == "existing":
        person_id = visit["person_id"]
        created_person = False
    else:
        person_id, created_person = await find_or_create_person_for_visit(visit.get("contact_name"), visit.get("contact_phone"), current_user["user_id"])
    enrollment, created_enrollment = await create_enrollment(
        db, "consolidation", person_id, mentor_person_id, current_user["user_id"],
        status="active", next_action="Dar seguimiento al visitante", source="mentorship_outreach", source_id=visit_id,
    )
    if created_enrollment:
        await configure_entry_stages(db, enrollment, "visitor_followup", current_user["user_id"])
        enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
        await assign_mentor(db, enrollment, mentor_person_id, current_user["user_id"], "Inicia la Ley de las 7 Semanas desde una invasión")
    now = now_utc()
    await db.outreach_visits.update_one({"visit_id": visit_id}, {"$set": {
        "enrollment_id": enrollment["enrollment_id"], "converted_person_id": person_id, "converted_at": now, "updated_at": now,
    }})
    await log_visit_history(visit_id, current_user, "seven_weeks_started", {
        "enrollment_id": enrollment["enrollment_id"], "person_id": person_id, "reused_existing_enrollment": not created_enrollment,
    })
    updated = await load_visit(visit_id)
    enriched = (await serialize_visits([updated], current_user))[0]
    enriched["enrollment_created"] = created_enrollment
    enriched["person_created"] = created_person
    return enriched


@router.get("/dashboard", response_model=dict)
async def outreach_dashboard(current_user: dict = Depends(get_current_user)):
    if not is_outreach_leader(current_user):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar el panel de invasiones")
    visits = await db.outreach_visits.find({"archived": {"$ne": True}}, {"_id": 0}).to_list(20000)
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


async def ensure_outreach_indexes() -> None:
    await db.outreach_campaigns.create_index("campaign_id", unique=True)
    await db.outreach_visits.create_index("visit_id", unique=True)
    await db.outreach_visits.create_index("mentor_person_id")
    await db.outreach_visits.create_index("campaign_id")
    await db.outreach_visits.create_index("phone_normalized")
    await db.outreach_visits.create_index("person_id")
    await db.outreach_visit_history.create_index("history_id", unique=True)
    await db.outreach_visit_history.create_index([("visit_id", 1), ("occurred_at", -1)])
