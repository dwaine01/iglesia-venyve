"""
P-001 - Core de Personas (identidad canonica permanente).
Modulo ADITIVO: no modifica people/contacts/checklists/progress ni Ley7.
Colecciones nuevas: persons, counters.
person_id = persons._id (ObjectId nativo de Mongo) -> expuesto como string hex.
person_number = VV-XXXXXX, generado via contador atomico, nunca FK, nunca reusado.
"""
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from bson.errors import InvalidId

from server import get_current_user
from access_control import (
    PERSON_PROFILE_SENSITIVE_READ,
    authorize_person,
    can_access_person,
    normalized_access_scope,
    normalized_capabilities,
)

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
if not MONGO_URL or not DB_NAME:
    raise RuntimeError("MONGO_URL and DB_NAME environment variables are required.")
_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

router = APIRouter(prefix="/api/core", tags=["core-personas"])


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text


def require_lider_o_pastor(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("rol") not in ("lider", "pastor"):
        raise HTTPException(status_code=403, detail="No autorizado")
    return current_user


def require_pastor(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo Pastor/Pastora puede eliminar Personas del directorio")
    return current_user


def require_person_profile_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Allow any role with explicit Person capabilities and a Person scope."""
    capabilities = normalized_capabilities(current_user)
    scope = normalized_access_scope(current_user).get("persons", "none")
    if not any(item.startswith("person.") for item in capabilities) or scope == "none":
        raise HTTPException(status_code=403, detail="No autorizado para Person Profile 360")
    return current_user


async def next_person_number() -> str:
    doc = await db.counters.find_one_and_update(
        {"_id": "person_number"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = doc["seq"]
    return f"VV-{seq:06d}"


def _age_category(fecha_nacimiento: Optional[str]) -> Optional[str]:
    if not fecha_nacimiento:
        return None
    try:
        dob = datetime.fromisoformat(fecha_nacimiento)
    except ValueError:
        return None
    years = (now_utc().replace(tzinfo=None) - dob).days / 365.25
    return "menor" if years < 18 else "adulto"


def serialize_person(doc: dict) -> dict:
    if not doc:
        return None
    doc = dict(doc)
    doc["person_id"] = str(doc.pop("_id"))
    for k in ("created_at", "updated_at"):
        if isinstance(doc.get(k), datetime):
            doc[k] = doc[k].isoformat()
    return doc


class PersonCreate(BaseModel):
    nombre: str
    apellido: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    idempotency_key: str = Field(..., min_length=8)


class DuplicateCheck(BaseModel):
    nombre: str
    apellido: str
    telefono: Optional[str] = None


class PersonArchiveResponse(BaseModel):
    person_id: str
    archived: bool
    linked_account_deactivated: bool
    archived_at: str


@router.get("/persons")
async def list_persons(
    search: Optional[str] = Query(None),
    limit: int = Query(25, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(require_lider_o_pastor),
):
    query = {"is_archived": {"$ne": True}}
    if search:
        norm = _normalize(search)
        ors = [{"telefono": {"$regex": re.escape(search)}}]
        if norm:
            ors.append({"search_key": {"$regex": re.escape(norm)}})
        if search.upper().startswith("VV"):
            ors.append({"person_number": search.upper()})
        query = {"$and": [query, {"$or": ors}]}
    if current_user.get("access_scope", {}).get("persons") != "all":
        assigned_ids = []
        if current_user.get("person_id"):
            assigned_ids = await db.process_enrollments.distinct(
                "person_id",
                {"$or": [
                    {"responsible_person_id": current_user["person_id"]},
                    {"mentor_person_id": current_user["person_id"]},
                ]},
            )
        scoped_or = [
            {"created_by": current_user.get("user_id")},
            {"auth_user_id": current_user.get("user_id")},
        ]
        valid_ids = [ObjectId(item) for item in assigned_ids if ObjectId.is_valid(item)]
        if valid_ids:
            scoped_or.append({"_id": {"$in": valid_ids}})
        scope_query = {"$or": scoped_or}
        query = {"$and": [query, scope_query]}
    cursor = db.persons.find(query).skip(skip).limit(limit).sort("created_at", -1)
    items = [serialize_person(doc) async for doc in cursor]
    total = await db.persons.count_documents(query)
    return {"items": items, "total": total, "limit": limit, "skip": skip}


@router.post("/persons/check-duplicates")
async def check_duplicates(payload: DuplicateCheck, current_user: dict = Depends(require_lider_o_pastor)):
    norm = _normalize(f"{payload.nombre} {payload.apellido}")
    contact_ids = []
    if payload.telefono:
        contact_ids = await db.person_contacts.distinct(
            "person_id", {"tipo": {"$in": ["telefono", "whatsapp"]}, "valor": payload.telefono}
        )
    ors = [{"search_key": norm}]
    valid_contact_ids = [ObjectId(item) for item in contact_ids if ObjectId.is_valid(item)]
    if valid_contact_ids:
        ors.append({"_id": {"$in": valid_contact_ids}})
    cursor = db.persons.find({"$or": ors}).limit(10)
    all_candidates = [doc async for doc in cursor]
    candidates = []
    for doc in all_candidates:
        doc["person_id"] = str(doc["_id"])
        if can_access_person(current_user, doc):
            candidates.append(serialize_person(doc))
    return {"possible_duplicates": candidates, "count": len(all_candidates), "match_found": bool(all_candidates)}


@router.post("/persons", status_code=201)
async def create_person(payload: PersonCreate, current_user: dict = Depends(require_lider_o_pastor)):
    existing = await db.persons.find_one({"idempotency_key": payload.idempotency_key})
    if existing:
        return serialize_person(existing)

    duplicate_payload = DuplicateCheck(
        nombre=payload.nombre,
        apellido=payload.apellido,
        telefono=payload.telefono,
    )
    duplicate_result = await check_duplicates(duplicate_payload, current_user)
    if duplicate_result["match_found"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Posible Persona existente; use el perfil canónico encontrado",
                "candidates": duplicate_result["possible_duplicates"],
            },
        )

    search_key = _normalize(f"{payload.nombre} {payload.apellido}")
    person_number = await next_person_number()
    now = now_utc()
    doc = {
        "nombre": payload.nombre.strip(),
        "apellido": payload.apellido.strip(),
        "fecha_nacimiento": payload.fecha_nacimiento,
        "age_category": _age_category(payload.fecha_nacimiento),
        "person_number": person_number,
        "search_key": search_key,
        "idempotency_key": payload.idempotency_key,
        "version": 1,
        "created_by": current_user.get("user_id") or current_user.get("id"),
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await db.persons.insert_one(doc)
    except Exception as e:
        raise HTTPException(status_code=409, detail=f"Conflicto de creacion: {e}")
    doc["_id"] = result.inserted_id
    person_id = str(result.inserted_id)
    contact_docs = []
    for kind, value in (("telefono", payload.telefono), ("email", payload.email)):
        if value:
            contact_docs.append({
                "person_id": person_id,
                "tipo": kind,
                "valor": value,
                "es_principal": not contact_docs,
                "created_by": current_user.get("user_id"),
                "created_at": now,
                "updated_at": now,
            })
    if contact_docs:
        await db.person_contacts.insert_many(contact_docs)
    return serialize_person(doc)


@router.get("/persons/{person_id}")
async def get_person(person_id: str, current_user: dict = Depends(require_lider_o_pastor)):
    try:
        oid = ObjectId(person_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="person_id invalido")
    doc = await db.persons.find_one({"_id": oid, "is_archived": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    doc["person_id"] = person_id
    authorize_person(current_user, doc, PERSON_PROFILE_SENSITIVE_READ)
    person = serialize_person(doc)
    person["sections_available"] = ["resumen"]
    person["sections_planned"] = ["contacto", "direcciones", "household", "familia", "procesos", "historial"]
    return person


@router.delete("/persons/{person_id}", response_model=PersonArchiveResponse)
async def archive_person(person_id: str, current_user: dict = Depends(require_pastor)):
    try:
        oid = ObjectId(person_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="person_id invalido")
    person = await db.persons.find_one({"_id": oid})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    if person.get("is_archived") is True:
        archived_at = person.get("archived_at") or now_utc()
        return PersonArchiveResponse(
            person_id=person_id,
            archived=True,
            linked_account_deactivated=False,
            archived_at=archived_at.isoformat() if isinstance(archived_at, datetime) else str(archived_at),
        )
    if current_user.get("person_id") == person_id:
        raise HTTPException(status_code=409, detail="No puede eliminar su propio Perfil 360")
    linked_users = await db.users.find(
        {"person_id": person_id},
        {"_id": 1, "rol": 1},
    ).to_list(20)
    if any(item.get("rol") == "pastor" for item in linked_users):
        raise HTTPException(status_code=409, detail="No se puede eliminar el Perfil 360 de otra cuenta pastoral")

    now = now_utc()
    archived = await db.persons.update_one(
        {"_id": oid, "is_archived": {"$ne": True}},
        {
            "$set": {
                "is_archived": True,
                "archived_at": now,
                "archived_by": current_user["user_id"],
                "archive_reason": "Eliminada desde Perfil 360",
                "updated_at": now,
            },
            "$inc": {"version": 1},
        },
    )
    if archived.modified_count != 1:
        raise HTTPException(status_code=409, detail="La Persona ya fue eliminada del directorio")
    linked_update = await db.users.update_many(
        {"person_id": person_id, "rol": {"$ne": "pastor"}},
        {
            "$set": {
                "is_active": False,
                "deactivated_at": now,
                "deactivation_reason": "Perfil 360 eliminado del directorio",
            },
            "$inc": {"token_version": 1},
        },
    )
    await db.person_memberships.update_many(
        {"person_id": person_id},
        {"$set": {"status": "inactive", "updated_at": now, "updated_by_user_id": current_user["user_id"]}},
    )
    await db.person_activity.insert_one({
        "_id": str(uuid4()),
        "person_id": person_id,
        "domain": "core",
        "action": "archived",
        "summary": "Persona eliminada del directorio; historial conservado",
        "actor_user_id": current_user["user_id"],
        "created_at": now,
    })
    return PersonArchiveResponse(
        person_id=person_id,
        archived=True,
        linked_account_deactivated=linked_update.modified_count > 0,
        archived_at=now.isoformat(),
    )


async def ensure_indexes():
    await db.persons.create_index("search_key")
    await db.persons.create_index("person_number", unique=True)
    await db.persons.create_index("idempotency_key", unique=True)
    await db.persons.create_index("telefono")
    await db.persons.create_index("is_archived")
    await db.counters.create_index("_id")
