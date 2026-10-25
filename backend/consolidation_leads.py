"""Encargados de Consolidación (C1).

La autoridad pastoral designa hasta N personas (límite configurable, 3 por
defecto) desde Persona 360. Al designarlas se les suman SOLO capacidades del
catálogo 5A (sin permisos automáticos por pertenecer a algo) y al quitarlas se
retiran únicamente las que dio esta designación (si ya las tenía por otra vía,
se conservan). Cada designación queda con quién y cuándo designó / retiró.

Colecciones: `consolidation_lead_designations` (una por designación, también
las retiradas = historial) y `app_settings` (`consolidation_leads_limit`)."""
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from access_control import (
    CONSOLIDATION_ASSIGN, CONSOLIDATION_MENTOR_TRANSFER, PERSON_DIRECTORY_SEARCH, PROCESSES_READ, PROCESSES_WRITE,
    capability_catalog_keys, is_general_coordinator, is_global_pastoral_authority,
)
from participation_scope import principal_authority_person_ids
from server import db, get_current_user

router = APIRouter(prefix="/api/consolidation/leads", tags=["consolidation-leads"])

DEFAULT_LIMIT = 3
# Ver panorama y personas, asignar/reasignar, registrar avance, atender alertas
# del proceso y contactar a las personas que acompañan.
LEAD_CAPABILITIES = sorted({PROCESSES_READ, PROCESSES_WRITE, CONSOLIDATION_ASSIGN, CONSOLIDATION_MENTOR_TRANSFER,
                            "processes.alerts.manage", PERSON_DIRECTORY_SEARCH, "person.contacts.read"})


class LeadCreate(BaseModel):
    person_id: str
    # Solo si la persona aún no tiene cuenta (misma regla del formulario de invasión: cuenta nivel persona).
    email: Optional[EmailStr] = None
    temporary_password: Optional[str] = Field(default=None, min_length=10, max_length=128)


class LeadSettings(BaseModel):
    limit: int = Field(ge=1, le=10)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def require_pastoral(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Solo la autoridad pastoral designa encargados de Consolidación")
    return current_user


def require_viewer(current_user: dict = Depends(get_current_user)) -> dict:
    if not (is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)):
        raise HTTPException(status_code=403, detail="Sin acceso a los encargados de Consolidación")
    return current_user


async def lead_limit() -> int:
    doc = await db.app_settings.find_one({"_id": "consolidation_leads_limit"}, {"_id": 0, "value": 1})
    return int((doc or {}).get("value") or DEFAULT_LIMIT)


async def is_consolidation_lead(user: dict) -> bool:
    """Para el panorama y Mi Trabajo: designación activa vigente."""
    person_id = user.get("person_id")
    return bool(person_id and await db.consolidation_lead_designations.find_one({"person_id": person_id, "active": True}, {"_id": 1}))


async def _name(person_id: Optional[str]) -> Optional[str]:
    from mentorship_outreach import person_display_name
    return await person_display_name(person_id) if person_id else None


async def _view(doc: dict) -> dict:
    user = await db.users.find_one({"_id": ObjectId(doc["user_id"])}, {"email": 1, "is_active": 1}) if doc.get("user_id") and ObjectId.is_valid(doc["user_id"]) else None
    return {
        "designation_id": doc["designation_id"], "person_id": doc["person_id"], "name": await _name(doc["person_id"]) or "Persona",
        "user_id": doc.get("user_id"), "email": (user or {}).get("email"), "account_active": bool(user and user.get("is_active", True)),
        "active": doc["active"], "granted": doc.get("granted", []), "account_created": doc.get("account_created", False),
        "designated_by_name": doc.get("designated_by_name"), "designated_at": doc["designated_at"].isoformat() if doc.get("designated_at") else None,
        "removed_by_name": doc.get("removed_by_name"), "removed_at": doc["removed_at"].isoformat() if doc.get("removed_at") else None,
    }


@router.get("", response_model=dict)
async def list_leads(current_user: dict = Depends(require_viewer)):
    docs = await db.consolidation_lead_designations.find({}, {"_id": 0}).sort("designated_at", -1).to_list(200)
    active = [await _view(doc) for doc in docs if doc["active"]]
    history = [await _view(doc) for doc in docs if not doc["active"]][:30]
    return {"limit": await lead_limit(), "items": active, "history": history, "capabilities": LEAD_CAPABILITIES,
            "can_manage": is_global_pastoral_authority(current_user)}


@router.post("", response_model=dict, status_code=201)
async def designate_lead(payload: LeadCreate, current_user: dict = Depends(require_pastoral)):
    if not ObjectId.is_valid(payload.person_id) or not await db.persons.find_one({"_id": ObjectId(payload.person_id), "is_archived": {"$ne": True}}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="La persona no existe en Persona 360")
    if payload.person_id in await principal_authority_person_ids(db):
        raise HTTPException(status_code=409, detail="La autoridad pastoral principal ya ve todo Consolidación; no se designa como encargada")
    if await db.consolidation_lead_designations.find_one({"person_id": payload.person_id, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Esta persona ya es encargada de Consolidación")
    limit = await lead_limit()
    if await db.consolidation_lead_designations.count_documents({"active": True}) >= limit:
        raise HTTPException(status_code=409, detail=f"Ya hay {limit} encargados de Consolidación (límite). Quite uno o cambie el límite.")
    invalid = set(LEAD_CAPABILITIES) - capability_catalog_keys()
    if invalid:  # salvaguarda: nunca capacidades fuera del catálogo 5A
        raise HTTPException(status_code=500, detail=f"Capacidades fuera del catálogo: {', '.join(sorted(invalid))}")
    user = await db.users.find_one({"person_id": payload.person_id})
    account_created = False
    if not user:
        if not payload.email or not payload.temporary_password:
            raise HTTPException(status_code=422, detail={"message": "Esta persona aún no tiene cuenta. Indique un correo y una contraseña temporal (mínimo 10 caracteres) para crearla.", "needs_account": True})
        from core_governance import UserAccessCreate, create_user_access_core
        await create_user_access_core(UserAccessCreate(person_id=payload.person_id, email=payload.email, temporary_password=payload.temporary_password,
                                                       access_level="persona", capabilities=LEAD_CAPABILITIES), current_user)
        user = await db.users.find_one({"person_id": payload.person_id})
        account_created = True
    elif user.get("is_active") is False:
        raise HTTPException(status_code=409, detail="La cuenta de esta persona está desactivada; reactívela en Gestión de accesos")
    existing = set(user.get("capabilities") or [])
    granted = LEAD_CAPABILITIES if account_created else sorted(set(LEAD_CAPABILITIES) - existing)
    if granted and not account_created:
        await db.users.update_one({"_id": user["_id"]}, {"$addToSet": {"capabilities": {"$each": granted}}, "$set": {"updated_at": now_utc()}})
    who = await _name(current_user.get("person_id")) or current_user.get("nombre")
    designation_id = str(uuid4())
    doc = {"_id": designation_id, "designation_id": designation_id, "person_id": payload.person_id, "user_id": str(user["_id"]),
           "active": True, "granted": granted, "account_created": account_created,
           "designated_by_user_id": current_user["user_id"], "designated_by_name": who, "designated_at": now_utc()}
    await db.consolidation_lead_designations.insert_one(doc)
    from portal_notifications import notify_users
    await notify_users([str(user["_id"])], "consolidation_lead", "Ahora eres encargado de Consolidación",
                       "Ya tienes acceso al módulo de Consolidación: panorama, personas, asignación y avance. Si no lo ves, cierra sesión y vuelve a entrar.", "/procesos/consolidacion")
    return await _view(doc)


@router.delete("/{designation_id}", response_model=dict)
async def remove_lead(designation_id: str, current_user: dict = Depends(require_pastoral)):
    doc = await db.consolidation_lead_designations.find_one({"designation_id": designation_id, "active": True}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Designación activa no encontrada")
    if doc.get("granted") and doc.get("user_id") and ObjectId.is_valid(doc["user_id"]):
        # Solo se retira lo que dio esta designación; se cierran sus sesiones para que el cambio rija ya.
        await db.users.update_one({"_id": ObjectId(doc["user_id"])}, {"$pull": {"capabilities": {"$in": doc["granted"]}}, "$inc": {"token_version": 1}, "$set": {"updated_at": now_utc()}})
    who = await _name(current_user.get("person_id")) or current_user.get("nombre")
    await db.consolidation_lead_designations.update_one({"designation_id": designation_id}, {"$set": {
        "active": False, "removed_by_user_id": current_user["user_id"], "removed_by_name": who, "removed_at": now_utc()}})
    return await _view(await db.consolidation_lead_designations.find_one({"designation_id": designation_id}, {"_id": 0}))


@router.put("/settings", response_model=dict)
async def update_settings(payload: LeadSettings, current_user: dict = Depends(require_pastoral)):
    active = await db.consolidation_lead_designations.count_documents({"active": True})
    if payload.limit < active:
        raise HTTPException(status_code=409, detail=f"Hay {active} encargados activos; quite alguno antes de bajar el límite a {payload.limit}")
    await db.app_settings.update_one({"_id": "consolidation_leads_limit"}, {"$set": {"value": payload.limit, "updated_by_user_id": current_user["user_id"], "updated_at": now_utc()}}, upsert=True)
    return {"limit": payload.limit}


async def ensure_indexes() -> None:
    await db.consolidation_lead_designations.create_index([("person_id", 1), ("active", 1)])
    await db.consolidation_lead_designations.create_index("designation_id", unique=True)
