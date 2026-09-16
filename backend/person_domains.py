"""P-001 Slice 2B - modular Contactos and Direcciones domains."""
from datetime import datetime, timezone
from typing import Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from access_control import (
    PERSON_ADDRESSES_READ,
    PERSON_ADDRESSES_WRITE,
    PERSON_CONTACTS_READ,
    PERSON_CONTACTS_WRITE,
    authorize_person,
)
from core_person import db, now_utc, require_lider_o_pastor

router = APIRouter(prefix="/api/core/persons", tags=["person-contact-address"])


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    result = value.strip()
    return result or None


class ContactPayload(BaseModel):
    tipo: Literal["telefono", "email", "whatsapp", "otro"] = "telefono"
    valor: str = Field(..., min_length=3, max_length=180)
    etiqueta: Optional[str] = Field(default=None, max_length=80)
    es_principal: bool = False
    notas: Optional[str] = Field(default=None, max_length=500)

    @field_validator("valor")
    @classmethod
    def clean_required(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("El contacto debe tener al menos 3 caracteres")
        return cleaned

    @field_validator("etiqueta", "notas")
    @classmethod
    def clean_optional(cls, value: Optional[str]) -> Optional[str]:
        return _clean(value)


class ContactUpdate(BaseModel):
    tipo: Optional[Literal["telefono", "email", "whatsapp", "otro"]] = None
    valor: Optional[str] = Field(default=None, min_length=3, max_length=180)
    etiqueta: Optional[str] = Field(default=None, max_length=80)
    es_principal: Optional[bool] = None
    notas: Optional[str] = Field(default=None, max_length=500)

    @field_validator("valor")
    @classmethod
    def clean_value(cls, value: Optional[str]) -> Optional[str]:
        return _clean(value)

    @field_validator("etiqueta", "notas")
    @classmethod
    def clean_optional(cls, value: Optional[str]) -> Optional[str]:
        return _clean(value)


class AddressPayload(BaseModel):
    tipo: Literal["casa", "trabajo", "otra"] = "casa"
    linea1: str = Field(..., min_length=3, max_length=220)
    linea2: Optional[str] = Field(default=None, max_length=220)
    sector: Optional[str] = Field(default=None, max_length=120)
    ciudad: str = Field(..., min_length=2, max_length=120)
    provincia: Optional[str] = Field(default=None, max_length=120)
    codigo_postal: Optional[str] = Field(default=None, max_length=30)
    pais: str = Field(default="República Dominicana", min_length=2, max_length=120)
    es_principal: bool = False
    notas: Optional[str] = Field(default=None, max_length=500)

    @field_validator("linea1", "ciudad", "pais")
    @classmethod
    def clean_required(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Campo requerido")
        return cleaned

    @field_validator("linea2", "sector", "provincia", "codigo_postal", "notas")
    @classmethod
    def clean_optional(cls, value: Optional[str]) -> Optional[str]:
        return _clean(value)


class AddressUpdate(BaseModel):
    tipo: Optional[Literal["casa", "trabajo", "otra"]] = None
    linea1: Optional[str] = Field(default=None, min_length=3, max_length=220)
    linea2: Optional[str] = Field(default=None, max_length=220)
    sector: Optional[str] = Field(default=None, max_length=120)
    ciudad: Optional[str] = Field(default=None, min_length=2, max_length=120)
    provincia: Optional[str] = Field(default=None, max_length=120)
    codigo_postal: Optional[str] = Field(default=None, max_length=30)
    pais: Optional[str] = Field(default=None, min_length=2, max_length=120)
    es_principal: Optional[bool] = None
    notas: Optional[str] = Field(default=None, max_length=500)

    @field_validator("linea1", "ciudad", "pais")
    @classmethod
    def clean_required(cls, value: Optional[str]) -> Optional[str]:
        return _clean(value)

    @field_validator("linea2", "sector", "provincia", "codigo_postal", "notas")
    @classmethod
    def clean_optional(cls, value: Optional[str]) -> Optional[str]:
        return _clean(value)


async def load_person(person_id: str) -> dict:
    try:
        oid = ObjectId(person_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="person_id invalido")
    person = await db.persons.find_one({"_id": oid})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return person


def serialize_contact(doc: dict) -> dict:
    return {
        "contact_id": str(doc["_id"]),
        "person_id": doc["person_id"],
        "tipo": doc["tipo"],
        "valor": doc["valor"],
        "etiqueta": doc.get("etiqueta"),
        "es_principal": bool(doc.get("es_principal")),
        "notas": doc.get("notas"),
        "created_at": iso_z(doc["created_at"]),
        "updated_at": iso_z(doc["updated_at"]),
    }


def serialize_address(doc: dict) -> dict:
    return {
        "address_id": str(doc["_id"]),
        "person_id": doc["person_id"],
        "tipo": doc["tipo"],
        "linea1": doc["linea1"],
        "linea2": doc.get("linea2"),
        "sector": doc.get("sector"),
        "ciudad": doc["ciudad"],
        "provincia": doc.get("provincia"),
        "codigo_postal": doc.get("codigo_postal"),
        "pais": doc.get("pais") or "República Dominicana",
        "es_principal": bool(doc.get("es_principal")),
        "notas": doc.get("notas"),
        "created_at": iso_z(doc["created_at"]),
        "updated_at": iso_z(doc["updated_at"]),
    }


async def contact_items(person_id: str) -> list[dict]:
    cursor = db.person_contacts.find({"person_id": person_id}).sort(
        [("es_principal", -1), ("created_at", 1)]
    )
    return [serialize_contact(doc) async for doc in cursor]


async def address_items(person_id: str) -> list[dict]:
    cursor = db.person_addresses.find({"person_id": person_id}).sort(
        [("es_principal", -1), ("created_at", 1)]
    )
    return [serialize_address(doc) async for doc in cursor]


async def _promote_contact_if_needed(person_id: str) -> None:
    if await db.person_contacts.count_documents({"person_id": person_id, "es_principal": True}):
        return
    first = await db.person_contacts.find_one({"person_id": person_id}, sort=[("created_at", 1)])
    if first:
        await db.person_contacts.update_one({"_id": first["_id"]}, {"$set": {"es_principal": True}})


async def _promote_address_if_needed(person_id: str) -> None:
    if await db.person_addresses.count_documents({"person_id": person_id, "es_principal": True}):
        return
    first = await db.person_addresses.find_one({"person_id": person_id}, sort=[("created_at", 1)])
    if first:
        await db.person_addresses.update_one({"_id": first["_id"]}, {"$set": {"es_principal": True}})


@router.get("/{person_id}/contacts")
async def list_contacts(person_id: str, current_user: dict = Depends(require_lider_o_pastor)):
    person = await load_person(person_id)
    authorize_person(current_user, person, PERSON_CONTACTS_READ)
    return {"items": await contact_items(person_id)}


@router.post("/{person_id}/contacts", status_code=status.HTTP_201_CREATED)
async def create_contact(
    person_id: str,
    payload: ContactPayload,
    current_user: dict = Depends(require_lider_o_pastor),
):
    person = await load_person(person_id)
    authorize_person(current_user, person, PERSON_CONTACTS_WRITE)
    make_primary = payload.es_principal or not await db.person_contacts.count_documents({"person_id": person_id})
    if make_primary:
        await db.person_contacts.update_many(
            {"person_id": person_id}, {"$set": {"es_principal": False}}
        )
    now = now_utc()
    doc = {
        "person_id": person_id,
        **payload.model_dump(),
        "es_principal": make_primary,
        "created_by": current_user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.person_contacts.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_contact(doc)


@router.put("/{person_id}/contacts/{contact_id}")
async def update_contact(
    person_id: str,
    contact_id: str,
    payload: ContactUpdate,
    current_user: dict = Depends(require_lider_o_pastor),
):
    person = await load_person(person_id)
    authorize_person(current_user, person, PERSON_CONTACTS_WRITE)
    try:
        contact_oid = ObjectId(contact_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="contact_id invalido")
    existing = await db.person_contacts.find_one({"_id": contact_oid, "person_id": person_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    update = payload.model_dump(exclude_none=True)
    if update.get("es_principal") is True:
        await db.person_contacts.update_many(
            {"person_id": person_id, "_id": {"$ne": contact_oid}},
            {"$set": {"es_principal": False}},
        )
    update["updated_at"] = now_utc()
    await db.person_contacts.update_one({"_id": contact_oid}, {"$set": update})
    await _promote_contact_if_needed(person_id)
    return serialize_contact(await db.person_contacts.find_one({"_id": contact_oid}))


@router.delete("/{person_id}/contacts/{contact_id}")
async def delete_contact(
    person_id: str,
    contact_id: str,
    current_user: dict = Depends(require_lider_o_pastor),
):
    person = await load_person(person_id)
    authorize_person(current_user, person, PERSON_CONTACTS_WRITE)
    try:
        contact_oid = ObjectId(contact_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="contact_id invalido")
    result = await db.person_contacts.delete_one({"_id": contact_oid, "person_id": person_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    await _promote_contact_if_needed(person_id)
    return {"message": "Contacto eliminado"}


@router.get("/{person_id}/addresses")
async def list_addresses(person_id: str, current_user: dict = Depends(require_lider_o_pastor)):
    person = await load_person(person_id)
    authorize_person(current_user, person, PERSON_ADDRESSES_READ)
    return {"items": await address_items(person_id)}


@router.post("/{person_id}/addresses", status_code=status.HTTP_201_CREATED)
async def create_address(
    person_id: str,
    payload: AddressPayload,
    current_user: dict = Depends(require_lider_o_pastor),
):
    person = await load_person(person_id)
    authorize_person(current_user, person, PERSON_ADDRESSES_WRITE)
    make_primary = payload.es_principal or not await db.person_addresses.count_documents({"person_id": person_id})
    if make_primary:
        await db.person_addresses.update_many(
            {"person_id": person_id}, {"$set": {"es_principal": False}}
        )
    now = now_utc()
    doc = {
        "person_id": person_id,
        **payload.model_dump(),
        "es_principal": make_primary,
        "created_by": current_user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.person_addresses.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_address(doc)


@router.put("/{person_id}/addresses/{address_id}")
async def update_address(
    person_id: str,
    address_id: str,
    payload: AddressUpdate,
    current_user: dict = Depends(require_lider_o_pastor),
):
    person = await load_person(person_id)
    authorize_person(current_user, person, PERSON_ADDRESSES_WRITE)
    try:
        address_oid = ObjectId(address_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="address_id invalido")
    existing = await db.person_addresses.find_one({"_id": address_oid, "person_id": person_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Direccion no encontrada")
    update = payload.model_dump(exclude_none=True)
    if update.get("es_principal") is True:
        await db.person_addresses.update_many(
            {"person_id": person_id, "_id": {"$ne": address_oid}},
            {"$set": {"es_principal": False}},
        )
    update["updated_at"] = now_utc()
    await db.person_addresses.update_one({"_id": address_oid}, {"$set": update})
    await _promote_address_if_needed(person_id)
    return serialize_address(await db.person_addresses.find_one({"_id": address_oid}))


@router.delete("/{person_id}/addresses/{address_id}")
async def delete_address(
    person_id: str,
    address_id: str,
    current_user: dict = Depends(require_lider_o_pastor),
):
    person = await load_person(person_id)
    authorize_person(current_user, person, PERSON_ADDRESSES_WRITE)
    try:
        address_oid = ObjectId(address_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="address_id invalido")
    result = await db.person_addresses.delete_one({"_id": address_oid, "person_id": person_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Direccion no encontrada")
    await _promote_address_if_needed(person_id)
    return {"message": "Direccion eliminada"}


async def ensure_indexes() -> None:
    await db.person_contacts.create_index([("person_id", 1), ("es_principal", -1)])
    await db.person_addresses.create_index([("person_id", 1), ("es_principal", -1)])
