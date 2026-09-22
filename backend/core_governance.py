"""Gobierno e integridad del Mega-Bloque A — Core."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

import bcrypt
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from access_control import (
    ACCESS_POLICY_VERSION,
    BOARD_ACCESS,
    BOARD_CONFIDENTIAL_ACCESS,
    BOARD_AI,
    BOARD_AUDIO,
    CELLULAR_CAPABILITIES,
    CARE_CAPABILITIES,
    CORE_ACCESS_MANAGE,
    DOOR_BOARD_CAPABILITIES,
    CORE_GOVERNANCE_MANAGE,
    FINANCE_CAPABILITIES,
    JOURNEY_GOVERNANCE_CAPABILITIES,
    MEMBERSHIP_DOCUMENTS_MANAGE,
    MEMBERSHIP_DIRECT_IMPORT,
    OPERATIONS_CAPABILITIES,
    PROCESS_CAPABILITIES,
    PERSON_DOMAIN_CAPABILITIES,
    PERSON_PASTORAL_NOTES_READ,
    access_defaults_for_role,
    has_capability,
    is_global_pastoral_authority,
    normalized_capabilities,
    resolved_access_level,
)
from canonical_identity import IdentityConflictError, ensure_user_person_link, migrate_core_identity
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
    access_level: str
    must_change_password: bool
    parent_user_id: Optional[str] = None
    access_title: Optional[str] = None
    organization_scope: Optional[dict] = None
    privilege_groups: list[str] = []
    onboarding_required: bool = False
    onboarding_completed_at: Optional[str] = None


class UserAccessList(BaseModel):
    items: list[UserAccessItem]


class AccessUpdate(BaseModel):
    rol: Optional[Literal["pastor", "lider", "persona"]] = None
    access_level: Optional[Literal["pastor", "coordinador_general", "director", "secretario", "tesorero", "equipo", "lider", "persona"]] = None
    is_active: bool
    capabilities: Optional[list[str]] = Field(default=None, max_length=100)
    privilege_groups: Optional[list[Literal["membership", "board", "finance", "care"]]] = None


class UserAccessCreate(BaseModel):
    person_id: str
    email: EmailStr
    temporary_password: str = Field(min_length=10, max_length=128)
    access_level: Literal["pastor", "coordinador_general", "director", "secretario", "tesorero", "equipo", "lider", "persona"]
    access_title: Optional[str] = Field(default=None, max_length=120)
    organization_scope: Optional[dict] = None
    privilege_groups: list[Literal["membership", "board", "finance", "care"]] = []


def require_governance(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Gobierno del núcleo restringido")
    return current_user


def require_access_manager(current_user: dict = Depends(get_current_user)) -> dict:
    if is_global_pastoral_authority(current_user):
        return current_user
    if current_user.get("rol") == "lider" and has_capability(current_user, CORE_ACCESS_MANAGE):
        return current_user
    raise HTTPException(status_code=403, detail="Gestión de accesos restringida")


def access_level(user: dict) -> str:
    if is_global_pastoral_authority(user):
        return "pastor"
    return resolved_access_level(user)


def access_defaults(level: str, privilege_groups: Optional[list[str]] = None) -> dict:
    role = "persona" if level == "persona" else "pastor" if level == "pastor" else "lider"
    defaults = access_defaults_for_role(role)
    groups = sorted(set(privilege_groups or ([] if level not in {"pastor", "coordinador_general"} else ["membership"])))
    if level == "coordinador_general":
        groups = sorted(set([*groups, "care"]))
        defaults["capabilities"] = sorted(set([*defaults["capabilities"], *CARE_CAPABILITIES, MEMBERSHIP_DIRECT_IMPORT]))
    if level in {"coordinador_general", "director"}:
        defaults["capabilities"] = sorted(set([*defaults["capabilities"], CORE_ACCESS_MANAGE]))
    if "membership" not in groups:
        defaults["capabilities"] = [item for item in defaults["capabilities"] if item not in PERSON_DOMAIN_CAPABILITIES]
    if "board" in groups:
        defaults["capabilities"] = sorted(set([*defaults["capabilities"], BOARD_ACCESS]))
    if "finance" in groups:
        defaults["capabilities"] = sorted(set([*defaults["capabilities"], *FINANCE_CAPABILITIES, "person.directory.search", "person.profile.read"]))
    defaults["access_scope"] = {"persons": "all" if level == "coordinador_general" else "created_by" if role == "lider" else defaults["access_scope"]["persons"]}
    return {"rol": role, "access_level": level, "privilege_groups": groups, **defaults}


def ensure_level_allowed(actor: dict, level: str, target: Optional[dict] = None) -> None:
    if is_global_pastoral_authority(actor):
        return
    actor_level = actor.get("access_level") or "lider"
    allowed = {"coordinador_general": {"director", "lider", "persona"}, "director": {"secretario", "tesorero", "equipo", "persona"}}
    if level not in allowed.get(actor_level, set()):
        raise HTTPException(status_code=403, detail="No puede crear o elevar este nivel de acceso")
    if target and access_level(target) not in allowed.get(actor_level, set()):
        raise HTTPException(status_code=403, detail="No puede modificar este nivel de acceso")


def ensure_privileges_allowed(actor: dict, groups: list[str]) -> None:
    if is_global_pastoral_authority(actor):
        return
    if any(group in {"board", "finance", "care"} for group in groups):
        raise HTTPException(status_code=403, detail="Solo el pastor puede conceder Junta, Finanzas o Cuidado Pastoral")
    actor_groups = set(actor.get("privilege_groups") or [])
    if not set(groups).issubset(actor_groups):
        raise HTTPException(status_code=403, detail="Solo puede delegar privilegios que ya posee")


async def ensure_finance_limit(groups: list[str], target: Optional[dict] = None) -> None:
    if "finance" not in groups or (target and "finance" in (target.get("privilege_groups") or [])):
        return
    policy = await db.governance_policies.find_one({"policy_key": "staff_confidentiality", "active": True}, {"_id": 0, "finance_max_users": 1})
    maximum = (policy or {}).get("finance_max_users")
    if maximum and await db.users.count_documents({"is_active": {"$ne": False}, "privilege_groups": "finance"}) >= maximum:
        raise HTTPException(status_code=409, detail=f"Se alcanzó el máximo pastoral de {maximum} accesos a Finanzas")


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
        "capabilities": normalized_capabilities(user),
        "access_scope": user.get("access_scope") or {"persons": "none"},
        "token_version": user.get("token_version", 1),
        "access_level": access_level(user),
        "must_change_password": user.get("must_change_password", False) is True,
        "parent_user_id": user.get("parent_user_id"),
        "access_title": user.get("access_title"),
        "organization_scope": user.get("organization_scope"),
        "privilege_groups": user.get("privilege_groups") or [],
        "onboarding_required": user.get("onboarding_required", False) is True,
        "onboarding_completed_at": user.get("onboarding_completed_at").isoformat().replace("+00:00", "Z") if isinstance(user.get("onboarding_completed_at"), datetime) else user.get("onboarding_completed_at"),
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
            {"access_policy_version": {"$ne": ACCESS_POLICY_VERSION}},
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
async def list_users(current_user: dict = Depends(require_access_manager)):
    query = {} if is_global_pastoral_authority(current_user) else {"$or": [{"_id": ObjectId(current_user["user_id"])}, {"parent_user_id": current_user["user_id"]}]}
    users = await db.users.find(query, {"password": 0}).sort([("rol", 1), ("nombre", 1)]).to_list(10000)
    return {"items": [serialize_user(user) for user in users]}


@router.get("/access-candidates", response_model=dict)
async def list_access_candidates(current_user: dict = Depends(require_access_manager)):
    people = await db.persons.find(
        {"$or": [{"auth_user_id": {"$exists": False}}, {"auth_user_id": None}]},
        {"nombre": 1, "apellido": 1, "apellidos": 1, "person_number": 1},
    ).sort([("nombre", 1), ("apellido", 1)]).to_list(1000)
    items = []
    for person in people:
        person_id = str(person["_id"])
        contact = await db.person_contacts.find_one({"person_id": person_id, "tipo": "email"}, {"_id": 0, "valor": 1})
        surname = person.get("apellidos") or person.get("apellido") or ""
        items.append({
            "person_id": person_id,
            "name": " ".join(part for part in [person.get("nombre", ""), surname] if part).strip(),
            "person_number": person.get("person_number"),
            "email": (contact or {}).get("valor", ""),
        })
    return {"items": items, "total": len(items)}


@router.post("/users", response_model=UserAccessItem, status_code=201)
async def create_user_access(payload: UserAccessCreate, current_user: dict = Depends(require_access_manager)):
    ensure_level_allowed(current_user, payload.access_level)
    ensure_privileges_allowed(current_user, payload.privilege_groups)
    await ensure_finance_limit(payload.privilege_groups)
    if payload.access_level in {"director", "secretario", "tesorero", "equipo"} and not payload.organization_scope:
        raise HTTPException(status_code=400, detail="Debe indicar el área de servicio")
    if current_user.get("access_level") == "director" and payload.organization_scope != current_user.get("organization_scope"):
        raise HTTPException(status_code=403, detail="Solo puede crear cuentas dentro de su propia área")
    if not ObjectId.is_valid(payload.person_id):
        raise HTTPException(status_code=400, detail="Perfil 360 inválido")
    person = await db.persons.find_one({"_id": ObjectId(payload.person_id)})
    if not person:
        raise HTTPException(status_code=404, detail="Perfil 360 no encontrado")
    if person.get("auth_user_id") or await db.users.find_one({"person_id": payload.person_id}):
        raise HTTPException(status_code=409, detail="Este Perfil 360 ya tiene acceso")
    email = str(payload.email).strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Este correo ya tiene acceso")
    defaults = access_defaults(payload.access_level, payload.privilege_groups)
    now = datetime.now(timezone.utc)
    surname = person.get("apellidos") or person.get("apellido") or ""
    user_doc = {
        "nombre": " ".join(part for part in [person.get("nombre", ""), surname] if part).strip(),
        "email": email,
        "password": bcrypt.hashpw(payload.temporary_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        "person_id": payload.person_id,
        "is_active": True,
        "must_change_password": True,
        "onboarding_required": payload.access_level not in {"persona", "lider"} or bool(set(payload.privilege_groups) & {"board", "finance"}),
        "onboarding_completed_at": None,
        "parent_user_id": current_user["user_id"],
        "access_title": payload.access_title,
        "organization_scope": payload.organization_scope,
        "token_version": 1,
        "created_by_user_id": current_user["user_id"],
        "created_at": now,
        "updated_at": now,
        **defaults,
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    linked = await db.persons.update_one(
        {"_id": person["_id"], "$or": [{"auth_user_id": {"$exists": False}}, {"auth_user_id": None}]},
        {"$set": {"auth_user_id": user_id, "updated_at": now}},
    )
    if not linked.modified_count:
        await db.users.delete_one({"_id": result.inserted_id})
        raise HTTPException(status_code=409, detail="El Perfil 360 fue vinculado por otra operación")
    return serialize_user(user_doc)


@router.put("/users/{user_id}/access", response_model=UserAccessItem)
async def update_user_access(
    user_id: str,
    payload: AccessUpdate,
    current_user: dict = Depends(require_access_manager),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="user_id inválido")
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not is_global_pastoral_authority(current_user) and target.get("parent_user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Solo puede administrar cuentas creadas directamente bajo su responsabilidad")
    requested_level = payload.access_level or payload.rol
    if not requested_level:
        raise HTTPException(status_code=400, detail="Debe indicar el nivel de acceso")
    ensure_level_allowed(current_user, requested_level, target)
    requested_groups = payload.privilege_groups if payload.privilege_groups is not None else target.get("privilege_groups", [])
    ensure_privileges_allowed(current_user, requested_groups)
    await ensure_finance_limit(requested_groups, target)
    requested_role = "pastor" if requested_level == "pastor" else "persona" if requested_level == "persona" else "lider"
    if user_id == current_user["user_id"] and (not payload.is_active or requested_role != "pastor"):
        raise HTTPException(status_code=400, detail="No puede retirar su propio acceso de pastor")
    if target.get("rol") == "pastor" and (requested_role != "pastor" or not payload.is_active):
        active_pastors = await db.users.count_documents({"rol": "pastor", "is_active": {"$ne": False}})
        if active_pastors <= 1:
            raise HTTPException(status_code=400, detail="Debe existir al menos un pastor activo")
    defaults = access_defaults(requested_level, requested_groups)
    allowed = set(PERSON_DOMAIN_CAPABILITIES + PROCESS_CAPABILITIES + CELLULAR_CAPABILITIES + DOOR_BOARD_CAPABILITIES + FINANCE_CAPABILITIES + JOURNEY_GOVERNANCE_CAPABILITIES + OPERATIONS_CAPABILITIES + CARE_CAPABILITIES + [MEMBERSHIP_DOCUMENTS_MANAGE, MEMBERSHIP_DIRECT_IMPORT, BOARD_ACCESS, PERSON_PASTORAL_NOTES_READ, CORE_GOVERNANCE_MANAGE, CORE_ACCESS_MANAGE, "person.profile.read"])
    capabilities = defaults["capabilities"]
    if payload.capabilities is not None:
        if not is_global_pastoral_authority(current_user):
            raise HTTPException(status_code=403, detail="Solo el pastor puede personalizar capacidades")
        existing_capabilities = set(target.get("capabilities") or [])
        invalid = sorted(set(payload.capabilities) - allowed - existing_capabilities)
        if invalid:
            raise HTTPException(status_code=400, detail=f"Capabilities inválidas: {', '.join(invalid)}")
        customizable = set(JOURNEY_GOVERNANCE_CAPABILITIES + OPERATIONS_CAPABILITIES + [MEMBERSHIP_DOCUMENTS_MANAGE, MEMBERSHIP_DIRECT_IMPORT])
        non_customizable = sorted(set(payload.capabilities) - set(defaults["capabilities"]) - customizable - existing_capabilities)
        if non_customizable:
            raise HTTPException(status_code=400, detail=f"Capabilities no personalizables para este nivel: {', '.join(non_customizable)}")
        preserved_existing = set(payload.capabilities) & existing_capabilities
        capabilities = sorted(set(defaults["capabilities"]) | preserved_existing | {item for item in payload.capabilities if item in customizable})
        if requested_role == "pastor" and CORE_GOVERNANCE_MANAGE not in capabilities:
            capabilities.append(CORE_GOVERNANCE_MANAGE)
    if "finance" not in requested_groups:
        capabilities = [item for item in capabilities if item not in FINANCE_CAPABILITIES]
    if "board" not in requested_groups:
        capabilities = [item for item in capabilities if item not in {BOARD_ACCESS, BOARD_CONFIDENTIAL_ACCESS}]
    capabilities = sorted(set(capabilities))
    changed = (
        target.get("rol") != requested_role
        or target.get("is_active", True) is not payload.is_active
        or sorted(target.get("privilege_groups") or []) != sorted(requested_groups)
        or sorted(target.get("capabilities") or []) != sorted(capabilities)
        or target.get("access_scope") != defaults["access_scope"]
    )
    update = {
        "rol": requested_role,
        "access_level": requested_level,
        "privilege_groups": requested_groups,
        "is_active": payload.is_active,
        "capabilities": capabilities,
        "access_scope": defaults["access_scope"],
        "access_policy_version": ACCESS_POLICY_VERSION,
        "updated_at": datetime.now(timezone.utc),
    }
    if changed:
        update["token_version"] = target.get("token_version", 1) + 1
    await db.users.update_one({"_id": target["_id"]}, {"$set": update})
    try:
        await ensure_user_person_link(db, user_id, current_user["user_id"])
    except IdentityConflictError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc), "conflict_id": exc.conflict_id})
    updated = await db.users.find_one({"_id": target["_id"]}, {"password": 0})
    return serialize_user(updated)


async def ensure_indexes() -> None:
    await db.users.create_index("person_id", unique=True, sparse=True)
    await db.persons.create_index("auth_user_id", unique=True, sparse=True)
    await db.people.create_index("canonical_person_id")
    await db.core_migrations.create_index("completed_at")