"""Central Ministry domain linked only by canonical person_id."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from access_control import (
    MINISTRIES_CATALOG_MANAGE,
    PERSON_MINISTRIES_READ,
    PERSON_MINISTRIES_WRITE,
    authorize_person,
    can_access_person,
    has_capability,
)
from core_person import db, now_utc, require_person_profile_user

router = APIRouter(prefix="/api/ministries", tags=["ministries"])
LEADERSHIP_NAMES = {"director/a", "líder", "coordinador/a"}


def normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def iso_z(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class MinistryPayload(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=140)
    descripcion: Optional[str] = Field(default=None, max_length=1000)
    suggested_age_groups: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("nombre")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.strip().split())


class MinistryRolePayload(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    ministry_id: Optional[str] = None


class AssignmentPayload(BaseModel):
    person_id: str
    ministry_id: str
    role_id: str
    activo: bool = True
    fecha_inicio: str
    fecha_fin: Optional[str] = None


class AssignmentUpdate(BaseModel):
    role_id: Optional[str] = None
    activo: Optional[bool] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None


async def load_person(person_id: str) -> dict:
    if not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=400, detail="person_id invalido")
    person = await db.persons.find_one({"_id": ObjectId(person_id)})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person["person_id"] = person_id
    return person


async def authorize_person_ministry(person_id: str, user: dict, capability: str) -> dict:
    person = await load_person(person_id)
    authorize_person(user, person, capability)
    return person


async def activity(person_id: str, user: dict, summary: str) -> None:
    await db.person_activity.insert_one({
        "_id": str(uuid4()), "person_id": person_id,
        "domain": "ministerios", "action": "updated", "summary": summary,
        "actor_user_id": user.get("user_id"), "created_at": now_utc(),
    })


def serialize_ministry(doc: dict, active_count: int = 0, has_leader: bool = False) -> dict:
    return {
        "ministry_id": doc["_id"],
        "nombre": doc["nombre"],
        "descripcion": doc.get("descripcion"),
        "activo": bool(doc.get("activo", True)),
        "suggested_age_groups": doc.get("suggested_age_groups", []),
        "active_people_count": active_count,
        "leadership_vacancy": not has_leader,
        "canonical_ministry_path": f"/ministerios/{doc['_id']}",
    }


async def assignment_items(person_id: str) -> list[dict]:
    docs = await db.ministry_assignments.find({"person_id": person_id}).sort("fecha_inicio", -1).to_list(200)
    ministry_ids = list({doc["ministry_id"] for doc in docs})
    role_ids = list({doc["role_id"] for doc in docs})
    ministries = {doc["_id"]: doc async for doc in db.ministry_catalog.find({"_id": {"$in": ministry_ids}})}
    roles = {doc["_id"]: doc async for doc in db.ministry_roles.find({"_id": {"$in": role_ids}})}
    return [
        {
            "assignment_id": doc["_id"],
            "person_id": person_id,
            "ministry_id": doc["ministry_id"],
            "ministry_name": ministries.get(doc["ministry_id"], {}).get("nombre", "Ministerio archivado"),
            "ministry_path": f"/ministerios/{doc['ministry_id']}",
            "role_id": doc["role_id"],
            "role_name": roles.get(doc["role_id"], {}).get("nombre", "Función archivada"),
            "activo": bool(doc.get("activo", True)),
            "fecha_inicio": doc.get("fecha_inicio"),
            "fecha_fin": doc.get("fecha_fin"),
            "version": doc.get("version", 1),
            "updated_at": iso_z(doc.get("updated_at")),
        }
        for doc in docs
    ]


@router.get("")
async def list_ministries(
    include_archived: bool = False,
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, PERSON_MINISTRIES_READ):
        raise HTTPException(status_code=403, detail="Ministerios restringidos")
    query = {} if include_archived else {"activo": True}
    docs = await db.ministry_catalog.find(query).sort("nombre", 1).to_list(500)
    items = []
    for doc in docs:
        assignments = await db.ministry_assignments.find(
            {"ministry_id": doc["_id"], "activo": True}
        ).to_list(1000)
        role_ids = [item["role_id"] for item in assignments]
        leadership = await db.ministry_roles.count_documents({
            "_id": {"$in": role_ids}, "normalized_name": {"$in": list(LEADERSHIP_NAMES)}
        })
        items.append(serialize_ministry(doc, len(assignments), bool(leadership)))
    return {"items": items}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ministry(
    payload: MinistryPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, MINISTRIES_CATALOG_MANAGE):
        raise HTTPException(status_code=403, detail="Catálogo de Ministerios restringido")
    normalized = normalize(payload.nombre)
    existing = await db.ministry_catalog.find_one({"normalized_name": normalized})
    if existing:
        return serialize_ministry(existing)
    doc = {
        "_id": str(uuid4()), "nombre": payload.nombre,
        "normalized_name": normalized, "descripcion": payload.descripcion,
        "suggested_age_groups": payload.suggested_age_groups, "activo": True,
        "created_by": current_user["user_id"], "created_at": now_utc(), "updated_at": now_utc(),
    }
    await db.ministry_catalog.insert_one(doc)
    return serialize_ministry(doc)


@router.put("/{ministry_id}")
async def update_ministry(
    ministry_id: str,
    payload: MinistryPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, MINISTRIES_CATALOG_MANAGE):
        raise HTTPException(status_code=403, detail="Catálogo de Ministerios restringido")
    result = await db.ministry_catalog.update_one(
        {"_id": ministry_id},
        {"$set": {
            "nombre": payload.nombre, "normalized_name": normalize(payload.nombre),
            "descripcion": payload.descripcion,
            "suggested_age_groups": payload.suggested_age_groups,
            "updated_at": now_utc(),
        }},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Ministerio no encontrado")
    return serialize_ministry(await db.ministry_catalog.find_one({"_id": ministry_id}))


@router.post("/{ministry_id}/archive")
async def archive_ministry(
    ministry_id: str,
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, MINISTRIES_CATALOG_MANAGE):
        raise HTTPException(status_code=403, detail="Catálogo de Ministerios restringido")
    result = await db.ministry_catalog.update_one(
        {"_id": ministry_id}, {"$set": {"activo": False, "updated_at": now_utc()}}
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Ministerio no encontrado")
    return {"message": "Ministerio archivado"}


@router.get("/roles/catalog")
async def list_ministry_roles(
    ministry_id: Optional[str] = None,
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, PERSON_MINISTRIES_READ):
        raise HTTPException(status_code=403, detail="Ministerios restringidos")
    query = {"activo": True, "$or": [{"ministry_id": None}, {"ministry_id": ministry_id}]}
    docs = await db.ministry_roles.find(query).sort("nombre", 1).to_list(500)
    return {"items": [{"role_id": doc["_id"], "nombre": doc["nombre"], "ministry_id": doc.get("ministry_id")} for doc in docs]}


@router.post("/roles/catalog", status_code=status.HTTP_201_CREATED)
async def create_ministry_role(
    payload: MinistryRolePayload,
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, PERSON_MINISTRIES_WRITE):
        raise HTTPException(status_code=403, detail="Funciones ministeriales restringidas")
    normalized = normalize(payload.nombre)
    existing = await db.ministry_roles.find_one({
        "normalized_name": normalized, "ministry_id": payload.ministry_id
    })
    if existing:
        return {"role_id": existing["_id"], "nombre": existing["nombre"], "ministry_id": existing.get("ministry_id")}
    doc = {
        "_id": str(uuid4()), "nombre": payload.nombre,
        "normalized_name": normalized, "ministry_id": payload.ministry_id,
        "activo": True, "created_by": current_user["user_id"], "created_at": now_utc(),
    }
    await db.ministry_roles.insert_one(doc)
    return {"role_id": doc["_id"], "nombre": doc["nombre"], "ministry_id": doc.get("ministry_id")}


@router.get("/person/{person_id}/assignments")
async def list_person_assignments(
    person_id: str,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_person_ministry(person_id, current_user, PERSON_MINISTRIES_READ)
    return {"items": await assignment_items(person_id)}


@router.post("/person/{person_id}/assignments", status_code=status.HTTP_201_CREATED)
async def add_person_assignment(
    person_id: str,
    payload: AssignmentPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_person_ministry(person_id, current_user, PERSON_MINISTRIES_WRITE)
    if payload.person_id != person_id:
        raise HTTPException(status_code=400, detail="person_id inconsistente")
    ministry = await db.ministry_catalog.find_one({"_id": payload.ministry_id, "activo": True})
    role = await db.ministry_roles.find_one({"_id": payload.role_id, "activo": True})
    if not ministry or not role or role.get("ministry_id") not in (None, payload.ministry_id):
        raise HTTPException(status_code=400, detail="Ministerio o función inválidos")
    duplicate = await db.ministry_assignments.find_one({
        "person_id": person_id, "ministry_id": payload.ministry_id,
        "role_id": payload.role_id, "activo": True,
    })
    if duplicate:
        raise HTTPException(status_code=409, detail="Asignación ministerial duplicada")
    now = now_utc()
    doc = {
        "_id": str(uuid4()), **payload.model_dump(),
        "registered_by": current_user["user_id"], "version": 1,
        "created_at": now, "updated_at": now,
    }
    await db.ministry_assignments.insert_one(doc)
    await activity(person_id, current_user, f"Asignación en {ministry['nombre']} registrada")
    items = await assignment_items(person_id)
    return next(item for item in items if item["assignment_id"] == doc["_id"])


@router.put("/assignments/{assignment_id}")
async def update_assignment(
    assignment_id: str,
    payload: AssignmentUpdate,
    current_user: dict = Depends(require_person_profile_user),
):
    assignment = await db.ministry_assignments.find_one({"_id": assignment_id})
    if not assignment:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    await authorize_person_ministry(
        assignment["person_id"], current_user, PERSON_MINISTRIES_WRITE
    )
    update = payload.model_dump(exclude_none=True)
    update["updated_at"] = now_utc()
    await db.ministry_assignments.update_one(
        {"_id": assignment_id}, {"$set": update, "$inc": {"version": 1}}
    )
    await activity(assignment["person_id"], current_user, "Asignación ministerial actualizada")
    return {"message": "Asignación actualizada"}


@router.get("/{ministry_id}")
async def get_ministry(
    ministry_id: str,
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, PERSON_MINISTRIES_READ):
        raise HTTPException(status_code=403, detail="Ministerios restringidos")
    ministry = await db.ministry_catalog.find_one({"_id": ministry_id})
    if not ministry:
        raise HTTPException(status_code=404, detail="Ministerio no encontrado")
    assignments = await db.ministry_assignments.find(
        {"ministry_id": ministry_id, "activo": True}
    ).sort("fecha_inicio", 1).to_list(2000)
    role_ids = list({item["role_id"] for item in assignments})
    roles = {doc["_id"]: doc async for doc in db.ministry_roles.find({"_id": {"$in": role_ids}})}
    people = {}
    if assignments:
        people = {
            str(doc["_id"]): doc
            async for doc in db.persons.find({
                "_id": {"$in": [ObjectId(item["person_id"]) for item in assignments]}
            })
        }
    members = []
    for assignment in assignments:
        person = people.get(assignment["person_id"], {})
        person["person_id"] = assignment["person_id"]
        if not can_access_person(current_user, person):
            continue
        role = roles.get(assignment["role_id"], {})
        members.append({
            "assignment_id": assignment["_id"],
            "person_id": assignment["person_id"],
            "person_number": person.get("person_number"),
            "nombre_completo": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
            "role_id": assignment["role_id"], "role_name": role.get("nombre"),
            "fecha_inicio": assignment.get("fecha_inicio"),
            "photo_available": bool(await db.person_photos.find_one({"person_id": assignment["person_id"]}, {"_id": 1})),
            "canonical_profile_path": f"/personas/{assignment['person_id']}",
        })
    has_leader = any(normalize(item.get("role_name", "")) in LEADERSHIP_NAMES for item in members)
    return {**serialize_ministry(ministry, len(members), has_leader), "members": members}


async def ensure_indexes_and_seed() -> None:
    await db.ministry_catalog.create_index("normalized_name", unique=True)
    await db.ministry_roles.create_index(
        [("normalized_name", 1), ("ministry_id", 1)], unique=True
    )
    await db.ministry_assignments.create_index(
        [("person_id", 1), ("ministry_id", 1), ("role_id", 1), ("activo", 1)]
    )
    seed_dir = Path(__file__).parent / "seed_data"
    ministries = json.loads((seed_dir / "ministries.json").read_text(encoding="utf-8"))
    roles = json.loads((seed_dir / "ministry_roles.json").read_text(encoding="utf-8"))
    for item in ministries:
        await db.ministry_catalog.update_one(
            {"normalized_name": normalize(item["nombre"])},
            {"$setOnInsert": {
                "_id": str(uuid4()), "nombre": item["nombre"],
                "normalized_name": normalize(item["nombre"]),
                "descripcion": None,
                "suggested_age_groups": item.get("suggested_age_groups", []),
                "activo": True, "created_at": now_utc(), "updated_at": now_utc(),
            }},
            upsert=True,
        )
    for name in roles:
        await db.ministry_roles.update_one(
            {"normalized_name": normalize(name), "ministry_id": None},
            {"$setOnInsert": {
                "_id": str(uuid4()), "nombre": name,
                "normalized_name": normalize(name), "ministry_id": None,
                "activo": True, "created_at": now_utc(),
            }},
            upsert=True,
        )
