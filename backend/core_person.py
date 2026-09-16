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

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from bson.errors import InvalidId

from server import get_current_user
from access_control import normalized_access_scope, normalized_capabilities

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


@router.get("/persons")
async def list_persons(
    search: Optional[str] = Query(None),
    limit: int = Query(25, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(require_lider_o_pastor),
):
    query = {}
    if search:
        norm = _normalize(search)
        ors = [{"telefono": {"$regex": re.escape(search)}}]
        if norm:
            ors.append({"search_key": {"$regex": re.escape(norm)}})
        if search.upper().startswith("VV"):
            ors.append({"person_number": search.upper()})
        query = {"$or": ors}
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
    candidates = [serialize_person(doc) async for doc in cursor]
    return {"possible_duplicates": candidates, "count": len(candidates)}


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
    if duplicate_result["count"]:
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
    doc = await db.persons.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person = serialize_person(doc)
    person["sections_available"] = ["resumen"]
    person["sections_planned"] = ["contacto", "direcciones", "household", "familia", "procesos", "historial"]
    return person


async def ensure_indexes():
    await db.persons.create_index("search_key")
    await db.persons.create_index("person_number", unique=True)
    await db.persons.create_index("idempotency_key", unique=True)
    await db.persons.create_index("telefono")
    await db.counters.create_index("_id")
