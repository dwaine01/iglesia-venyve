"""Invitaciones seguras (C5): establecer contraseña sobre una cuenta ya creada
por core_governance.create_user_access_core, sin que quien la crea deba
escribir (ni ver) una contraseña temporal. El token en claro se genera, se
devuelve UNA sola vez a quien crea la cuenta y nunca se guarda ni se registra;
solo se persiste su hash SHA-256."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import bcrypt
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import is_global_pastoral_authority
from server import db, get_current_user

router = APIRouter(prefix="/api", tags=["access-invitations"])

INVITATION_TTL_HOURS = 72


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_invitation(db, user_id: str, person_id: Optional[str], actor_user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    invitation_id = str(uuid4())
    now = now_utc()
    await db.access_invitations.insert_one({
        "_id": invitation_id, "invitation_id": invitation_id, "user_id": user_id, "person_id": person_id,
        "token_hash": _hash_token(token), "expires_at": now + timedelta(hours=INVITATION_TTL_HOURS),
        "used_at": None, "revoked_at": None, "created_by_user_id": actor_user_id, "created_at": now,
    })
    return token


class AcceptInvitation(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)


@router.post("/auth/accept-invitation", response_model=dict)
async def accept_invitation(payload: AcceptInvitation):
    invitation = await db.access_invitations.find_one({"token_hash": _hash_token(payload.token)})
    now = now_utc()
    expires_at = invitation["expires_at"] if invitation else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not invitation or invitation.get("used_at") or invitation.get("revoked_at") or expires_at <= now:
        raise HTTPException(status_code=400, detail="Invitación inválida o vencida")
    if not ObjectId.is_valid(invitation["user_id"]):
        raise HTTPException(status_code=400, detail="Invitación inválida o vencida")
    user = await db.users.find_one({"_id": ObjectId(invitation["user_id"])})
    if not user:
        raise HTTPException(status_code=400, detail="Invitación inválida o vencida")
    await db.users.update_one({"_id": user["_id"]}, {
        "$set": {
            "password": bcrypt.hashpw(payload.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "must_change_password": False, "is_active": True, "updated_at": now,
        },
        "$inc": {"token_version": 1},
    })
    await db.access_invitations.update_one({"_id": invitation["_id"]}, {"$set": {"used_at": now}})
    return {"email": user.get("email"), "accepted": True}


@router.post("/core/access/invitations/{user_id}/reissue", response_model=dict)
async def reissue_invitation(user_id: str, current_user: dict = Depends(get_current_user)):
    from core_governance import require_access_manager
    require_access_manager(current_user)
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="user_id inválido")
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not is_global_pastoral_authority(current_user) and target.get("parent_user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Solo puede reenviar invitaciones de cuentas creadas bajo su responsabilidad")
    await db.access_invitations.update_many({"user_id": user_id, "used_at": None, "revoked_at": None}, {"$set": {"revoked_at": now_utc()}})
    token = await issue_invitation(db, user_id, target.get("person_id"), current_user["user_id"])
    return {"invitation_token": token}


async def ensure_indexes() -> None:
    await db.access_invitations.create_index("invitation_id", unique=True)
    await db.access_invitations.create_index("token_hash", unique=True)
    await db.access_invitations.create_index("expires_at")
