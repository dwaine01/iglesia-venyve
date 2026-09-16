"""Onboarding administrativo y consentimiento versionado para cuentas privilegiadas."""
from datetime import datetime, timezone
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from access_control import CORE_GOVERNANCE_MANAGE, has_capability
from server import db, get_authenticated_user

router = APIRouter(prefix="/api/access", tags=["access-onboarding"])
POLICY_KEY = "staff_confidentiality"

DEFAULT_POLICY = """Al firmar, reconozco que la información de membresía, cuidado pastoral, Junta y Finanzas es confidencial. Me comprometo a usarla únicamente para el servicio autorizado, no compartirla fuera de mi responsabilidad, proteger mis dispositivos y credenciales, y reportar inmediatamente cualquier pérdida, acceso indebido o divulgación accidental. Entiendo que el acceso puede ser retirado y que toda actividad queda registrada para proteger a las personas y a la iglesia."""


class PolicyUpdate(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    body: str = Field(min_length=100, max_length=12000)
    finance_max_users: Optional[int] = Field(default=None, ge=1, le=100)
    approval_status: Literal["pending_review", "approved"] = "pending_review"
    approved_by_name: Optional[str] = Field(default=None, max_length=160)


class OnboardingSubmit(BaseModel):
    preferred_contact_method: Literal["telefono", "correo", "whatsapp"]
    emergency_contact_name: str = Field(min_length=3, max_length=120)
    emergency_contact_phone: str = Field(min_length=7, max_length=30)
    device_ownership: Literal["personal", "iglesia", "compartido"]
    service_commitment: str = Field(min_length=20, max_length=2000)
    privacy_acknowledged: bool
    confidentiality_acknowledged: bool
    secure_device_acknowledged: bool
    incident_reporting_acknowledged: bool
    signature: str = Field(min_length=3, max_length=160)
    policy_version: int = Field(ge=1)


async def active_policy() -> dict:
    policy = await db.governance_policies.find_one({"policy_key": POLICY_KEY, "active": True}, {"_id": 0}, sort=[("version", -1)])
    if not policy:
        now = datetime.now(timezone.utc)
        policy = {"policy_key": POLICY_KEY, "version": 1, "title": "Borrador operativo de privacidad y confidencialidad", "body": DEFAULT_POLICY, "finance_max_users": None, "approval_status": "pending_review", "active": True, "created_at": now, "updated_at": now}
        await db.governance_policies.insert_one({"_id": f"{POLICY_KEY}:1", **policy})
    policy.setdefault("approval_status", "pending_review")
    if policy["approval_status"] != "approved" and not policy.get("title", "").lower().startswith("borrador"):
        policy["title"] = f"Borrador operativo — {policy.get('title', 'Privacidad y confidencialidad')}"
    return {**policy, "created_at": policy.get("created_at").isoformat().replace("+00:00", "Z") if isinstance(policy.get("created_at"), datetime) else policy.get("created_at"), "updated_at": policy.get("updated_at").isoformat().replace("+00:00", "Z") if isinstance(policy.get("updated_at"), datetime) else policy.get("updated_at")}


@router.get("/onboarding", response_model=dict)
async def get_onboarding(current_user: dict = Depends(get_authenticated_user)):
    user = await db.users.find_one({"_id": ObjectId(current_user["user_id"])}, {"password": 0})
    consent = await db.access_consents.find_one({"user_id": current_user["user_id"]}, {"_id": 0}, sort=[("accepted_at", -1)])
    return {"required": user.get("onboarding_required", False) is True, "completed": bool(user.get("onboarding_completed_at")), "policy": await active_policy(), "consent": consent}


@router.post("/onboarding", response_model=dict)
async def submit_onboarding(payload: OnboardingSubmit, request: Request, current_user: dict = Depends(get_authenticated_user)):
    if current_user.get("must_change_password"):
        raise HTTPException(status_code=409, detail="Primero debe cambiar su clave temporal")
    if not all([payload.privacy_acknowledged, payload.confidentiality_acknowledged, payload.secure_device_acknowledged, payload.incident_reporting_acknowledged]):
        raise HTTPException(status_code=422, detail="Debe aceptar los cuatro compromisos")
    policy = await active_policy()
    if payload.policy_version != policy["version"]:
        raise HTTPException(status_code=409, detail="La política cambió; revise y firme la versión vigente")
    now = datetime.now(timezone.utc)
    consent = {"consent_id": f"{current_user['user_id']}:{policy['version']}:{int(now.timestamp())}", "user_id": current_user["user_id"], "person_id": current_user.get("person_id"), "policy_key": POLICY_KEY, "policy_version": policy["version"], "policy_title": policy["title"], "policy_body_snapshot": policy["body"], "preferred_contact_method": payload.preferred_contact_method, "emergency_contact_name": payload.emergency_contact_name.strip(), "emergency_contact_phone": payload.emergency_contact_phone.strip(), "device_ownership": payload.device_ownership, "service_commitment": payload.service_commitment.strip(), "acceptances": {"privacy": True, "confidentiality": True, "secure_device": True, "incident_reporting": True}, "signature": payload.signature.strip(), "accepted_at": now, "ip_address": request.client.host if request.client else None, "user_agent": request.headers.get("user-agent")}
    await db.access_consents.insert_one({"_id": consent["consent_id"], **consent})
    await db.users.update_one({"_id": ObjectId(current_user["user_id"])}, {"$set": {"onboarding_completed_at": now, "onboarding_policy_version": policy["version"], "updated_at": now}})
    return {"completed": True, "accepted_at": now.isoformat().replace("+00:00", "Z"), "policy_version": policy["version"]}


def require_pastor(current_user: dict = Depends(get_authenticated_user)) -> dict:
    if current_user.get("rol") != "pastor" or not has_capability(current_user, CORE_GOVERNANCE_MANAGE):
        raise HTTPException(status_code=403, detail="Solo el pastor puede editar esta política")
    return current_user


@router.put("/policy", response_model=dict)
async def update_policy(payload: PolicyUpdate, current_user: dict = Depends(require_pastor)):
    if payload.approval_status == "approved" and not payload.approved_by_name:
        raise HTTPException(status_code=422, detail="Indique quién realizó la revisión pastoral/legal")
    current = await active_policy(); now = datetime.now(timezone.utc); version = int(current["version"]) + 1
    await db.governance_policies.update_many({"policy_key": POLICY_KEY, "active": True}, {"$set": {"active": False, "retired_at": now}})
    policy = {"policy_key": POLICY_KEY, "version": version, "title": payload.title.strip(), "body": payload.body.strip(), "finance_max_users": payload.finance_max_users, "approval_status": payload.approval_status, "approved_by_name": payload.approved_by_name.strip() if payload.approved_by_name else None, "approved_at": now if payload.approval_status == "approved" else None, "active": True, "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now}
    await db.governance_policies.insert_one({"_id": f"{POLICY_KEY}:{version}", **policy})
    return await active_policy()


async def ensure_indexes():
    await db.governance_policies.create_index([("policy_key", 1), ("version", -1)], unique=True)
    await db.access_consents.create_index([("user_id", 1), ("policy_version", -1)])
    await active_policy()