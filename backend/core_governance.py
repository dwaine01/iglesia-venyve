"""Gobierno e integridad del Mega-Bloque A — Core."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import (
    CELLULAR_CAPABILITIES,
    DOOR_BOARD_CAPABILITIES,
    CORE_GOVERNANCE_MANAGE,
    PROCESS_CAPABILITIES,
    PERSON_DOMAIN_CAPABILITIES,
    PERSON_PASTORAL_NOTES_READ,
    access_defaults_for_role,
    has_capability,
)
from canonical_identity import ensure_user_person_link, migrate_core_identity
from server import db, get_current_user

router = APIRouter(prefix="/api/core/governance", tags=["core-governance"])


class IntegrityCounts(BaseModel):
    users: int
    persons: int
    legacy_people: int
    households: int
    relationships: int
    ministries: int
    ministry_assignments: int


class IntegrityIssues(BaseModel):
    users_without_person: int
    legacy_people_without_person: int
    access_policy_outdated: int
    orphan_ministry_assignments: int
    orphan_relationships: int
    duplicate_candidate_groups: int


class IntegrityResponse(BaseModel):
    status: str
    score: int
    counts: IntegrityCounts
    issues: IntegrityIssues
    duplicate_candidates: list[dict]
    last_migration: Optional[dict] = None


class MigrationResponse(BaseModel):
    migration_id: str
    completed_at: str
    users_linked: int
    persons_created_for_users: int
    legacy_people_linked: int
    persons_created_for_legacy: int
    conflict_count: int
    conflicts: list[dict]


class UserAccessItem(BaseModel):
    user_id: str
    nombre: str
    email: str
    rol: str
    is_active: bool
    person_id: Optional[str] = None
    canonical_profile_path: Optional[str] = None
    capabilities: list[str]
    access_scope: dict
    token_version: int


class UserAccessList(BaseModel):
    items: list[UserAccessItem]


class AccessUpdate(BaseModel):
    rol: Literal["pastor", "lider", "persona"]
    is_active: bool
    capabilities: Optional[list[str]] = Field(default=None, max_length=100)


def require_governance(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("rol") != "pastor" or not has_capability(current_user, CORE_GOVERNANCE_MANAGE):
        raise HTTPException(status_code=403, detail="Gobierno del núcleo restringido")
    return current_user


def serialize_user(user: dict) -> dict:
    person_id = user.get("person_id")
    return {
        "user_id": str(user["_id"]),
        "nombre": user.get("nombre", ""),
        "email": user.get("email", ""),
        "rol": user.get("rol", "persona"),
        "is_active": user.get("is_active", True) is True,
        "person_id": person_id,
        "canonical_profile_path": f"/personas/{person_id}" if person_id else None,
        "capabilities": sorted(user.get("capabilities") or []),
        "access_scope": user.get("access_scope") or {"persons": "none"},
        "token_version": user.get("token_version", 1),
    }


async def duplicate_candidates() -> list[dict]:
    groups = []
    name_pipeline = [
        {"$match": {"search_key": {"$nin": [None, ""]}, "fecha_nacimiento": {"$nin": [None, ""]}}},
        {"$group": {"_id": {"name": "$search_key", "dob": "$fecha_nacimiento"}, "person_ids": {"$push": {"$toString": "$_id"}}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$limit": 20},
    ]
    for item in await db.persons.aggregate(name_pipeline).to_list(20):
        groups.append({
            "match_type": "nombre_fecha_nacimiento",
            "value": f"{item['_id']['name']} · {item['_id']['dob']}",
            "person_ids": item["person_ids"],
        })
    contact_pipeline = [
        {"$match": {"tipo": {"$in": ["email", "telefono", "whatsapp"]}, "valor": {"$nin": [None, ""]}}},
        {"$group": {"_id": {"type": "$tipo", "value": {"$toLower": "$valor"}}, "person_ids": {"$addToSet": "$person_id"}}},
        {"$project": {"person_ids": 1, "count": {"$size": "$person_ids"}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$limit": 20},
    ]
    for item in await db.person_contacts.aggregate(contact_pipeline).to_list(20):
        groups.append({
            "match_type": item["_id"]["type"],
            "value": item["_id"]["value"],
            "person_ids": item["person_ids"],
        })
    return groups[:30]


async def integrity_snapshot() -> dict:
    person_ids = {str(item["_id"]) async for item in db.persons.find({}, {"_id": 1})}
    assignments = await db.ministry_assignments.find({}, {"_id": 0, "person_id": 1}).to_list(10000)
    relationships = await db.person_relationships.find({}, {"_id": 0, "person_a_id": 1, "person_b_id": 1}).to_list(10000)
    duplicates = await duplicate_candidates()
    issues = {
        "users_without_person": await db.users.count_documents({"$or": [{"person_id": {"$exists": False}}, {"person_id": None}]}),
        "legacy_people_without_person": await db.people.count_documents({"$or": [{"canonical_person_id": {"$exists": False}}, {"canonical_person_id": None}]}),
        "access_policy_outdated": await db.users.count_documents({"$or": [
            {"access_policy_version": {"$ne": 11}},
            {"capabilities": {"$exists": False}},
            {"access_scope": {"$exists": False}},
        ]}),
        "orphan_ministry_assignments": sum(1 for item in assignments if item.get("person_id") not in person_ids),
        "orphan_relationships": sum(
            1 for item in relationships
            if item.get("person_a_id") not in person_ids or item.get("person_b_id") not in person_ids
        ),
        "duplicate_candidate_groups": len(duplicates),
    }
    weighted = (
        issues["users_without_person"] * 10
        + issues["legacy_people_without_person"] * 8
        + issues["access_policy_outdated"] * 4
        + issues["orphan_ministry_assignments"] * 8
        + issues["orphan_relationships"] * 8
        + issues["duplicate_candidate_groups"] * 3
    )
    last = await db.core_migrations.find_one({}, {"_id": 0}, sort=[("completed_at", -1)])
    if last and isinstance(last.get("completed_at"), datetime):
        last["completed_at"] = last["completed_at"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "status": "healthy" if weighted == 0 else "attention_required",
        "score": max(0, 100 - weighted),
        "counts": {
            "users": await db.users.count_documents({}),
            "persons": len(person_ids),
            "legacy_people": await db.people.count_documents({}),
            "households": await db.households.count_documents({}),
            "relationships": await db.person_relationships.count_documents({}),
            "ministries": await db.ministry_catalog.count_documents({"activo": True}),
            "ministry_assignments": await db.ministry_assignments.count_documents({"activo": True}),
        },
        "issues": issues,
        "duplicate_candidates": duplicates,
        "last_migration": last,
    }


@router.get("/integrity", response_model=IntegrityResponse)
async def get_integrity(current_user: dict = Depends(require_governance)):
    return await integrity_snapshot()


@router.post("/migrate", response_model=MigrationResponse)
async def run_migration(current_user: dict = Depends(require_governance)):
    result = await migrate_core_identity(db, current_user["user_id"])
    now = datetime.now(timezone.utc)
    migration = {
        "migration_id": str(uuid4()),
        "migration_key": "mega_block_a_identity_v1",
        "actor_user_id": current_user["user_id"],
        "completed_at": now,
        **result,
    }
    await db.core_migrations.insert_one({"_id": migration["migration_id"], **migration})
    return {**migration, "completed_at": now.isoformat().replace("+00:00", "Z")}


@router.get("/users", response_model=UserAccessList)
async def list_users(current_user: dict = Depends(require_governance)):
    users = await db.users.find({}, {"password": 0}).sort([("rol", 1), ("nombre", 1)]).to_list(10000)
    return {"items": [serialize_user(user) for user in users]}


@router.put("/users/{user_id}/access", response_model=UserAccessItem)
async def update_user_access(
    user_id: str,
    payload: AccessUpdate,
    current_user: dict = Depends(require_governance),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="user_id inválido")
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user_id == current_user["user_id"] and (not payload.is_active or payload.rol != "pastor"):
        raise HTTPException(status_code=400, detail="No puede retirar su propio acceso de pastor")
    if target.get("rol") == "pastor" and (payload.rol != "pastor" or not payload.is_active):
        active_pastors = await db.users.count_documents({"rol": "pastor", "is_active": {"$ne": False}})
        if active_pastors <= 1:
            raise HTTPException(status_code=400, detail="Debe existir al menos un pastor activo")
    defaults = access_defaults_for_role(payload.rol)
    allowed = set(PERSON_DOMAIN_CAPABILITIES + PROCESS_CAPABILITIES + CELLULAR_CAPABILITIES + DOOR_BOARD_CAPABILITIES + [PERSON_PASTORAL_NOTES_READ, CORE_GOVERNANCE_MANAGE])
    capabilities = defaults["capabilities"]
    if payload.capabilities is not None:
        invalid = sorted(set(payload.capabilities) - allowed)
        if invalid:
            raise HTTPException(status_code=400, detail=f"Capabilities inválidas: {', '.join(invalid)}")
        capabilities = sorted(set(payload.capabilities))
        if payload.rol == "pastor" and CORE_GOVERNANCE_MANAGE not in capabilities:
            capabilities.append(CORE_GOVERNANCE_MANAGE)
    changed = (
        target.get("rol") != payload.rol
        or target.get("is_active", True) is not payload.is_active
        or sorted(target.get("capabilities") or []) != sorted(capabilities)
        or target.get("access_scope") != defaults["access_scope"]
    )
    update = {
        "rol": payload.rol,
        "is_active": payload.is_active,
        "capabilities": capabilities,
        "access_scope": defaults["access_scope"],
        "access_policy_version": 11,
        "updated_at": datetime.now(timezone.utc),
    }
    if changed:
        update["token_version"] = target.get("token_version", 1) + 1
    await db.users.update_one({"_id": target["_id"]}, {"$set": update})
    await ensure_user_person_link(db, user_id, current_user["user_id"])
    updated = await db.users.find_one({"_id": target["_id"]}, {"password": 0})
    return serialize_user(updated)


async def ensure_indexes() -> None:
    await db.users.create_index("person_id", unique=True, sparse=True)
    await db.persons.create_index("auth_user_id", unique=True, sparse=True)
    await db.people.create_index("canonical_person_id")
    await db.core_migrations.create_index("completed_at")