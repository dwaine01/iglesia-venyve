"""Servicio único de coincidencias de Persona 360 (fuerte/posible) para alta
rápida en flujos operativos (hoy: Grupos Frontales). Nunca fusiona en
silencio: coincidencia FUERTE bloquea la creación y ofrece usar la existente;
coincidencia POSIBLE solo se crea con confirm_distinct_person + motivo
(auditado). Ver Parte F del encargo: /api/core/persons/check-duplicates sigue
con su lógica propia por ahora (no se tocó para no afectar su suite de
pruebas existente); este servicio es el que usan los flujos nuevos."""
import re
import unicodedata
from datetime import datetime, timezone
from typing import Literal, Optional

from bson import ObjectId
from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits[-10:] if len(digits) >= 10 else (digits or None)


class PersonMatchQuery(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    apellido: str = Field(min_length=1, max_length=120)
    fecha_nacimiento: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None


class PersonQuickCreate(PersonMatchQuery):
    idempotency_key: str = Field(min_length=8, max_length=200)
    confirm_distinct_person: bool = False
    distinct_reason: Optional[str] = Field(default=None, max_length=400)


class GroupQuickPerson(PersonQuickCreate):
    role: Literal["member", "mentor"] = "member"
    notes: Optional[str] = Field(default=None, max_length=600)


def _person_card(doc: dict) -> dict:
    return {
        "person_id": str(doc["_id"]),
        "nombre": doc.get("nombre"),
        "apellido": doc.get("apellido"),
        "person_number": doc.get("person_number"),
        "fecha_nacimiento": doc.get("fecha_nacimiento"),
    }


async def find_matches(db, query: PersonMatchQuery) -> dict:
    norm_name = normalize_text(f"{query.nombre} {query.apellido}")
    phone_norm = normalize_phone(query.telefono)
    email_norm = (query.email or "").strip().lower() or None
    strong_ids: set[str] = set()
    if email_norm:
        strong_ids.update(await db.person_contacts.distinct(
            "person_id", {"tipo": "email", "valor": {"$regex": f"^{re.escape(email_norm)}$", "$options": "i"}},
        ))
    if phone_norm:
        # Nota: sin índice sobre teléfonos normalizados históricos, se compara
        # en memoria (igual que find_or_create_person_for_visit hoy); limitar
        # a 20000 contactos es una limitación conocida, no nueva.
        candidates = await db.person_contacts.find(
            {"tipo": {"$in": ["telefono", "whatsapp"]}}, {"_id": 0, "person_id": 1, "valor": 1, "valor_normalizado": 1},
        ).to_list(20000)
        strong_ids.update(item["person_id"] for item in candidates if (item.get("valor_normalizado") or normalize_phone(item.get("valor"))) == phone_norm)
    if query.fecha_nacimiento and norm_name:
        strong_ids.update(str(item["_id"]) for item in await db.persons.find(
            {"search_key": norm_name, "fecha_nacimiento": query.fecha_nacimiento}, {"_id": 1},
        ).to_list(50))
    possible_ids: set[str] = set()
    if norm_name:
        possible_ids.update(str(item["_id"]) for item in await db.persons.find({"search_key": norm_name}, {"_id": 1}).to_list(50))
    possible_ids -= strong_ids

    async def load(ids: set[str]) -> list[dict]:
        valid = [ObjectId(item) for item in ids if ObjectId.is_valid(item)]
        if not valid:
            return []
        docs = await db.persons.find(
            {"_id": {"$in": valid}, "is_archived": {"$ne": True}},
            {"nombre": 1, "apellido": 1, "person_number": 1, "fecha_nacimiento": 1},
        ).to_list(50)
        return [_person_card(doc) for doc in docs]

    return {"strong": await load(strong_ids), "possible": await load(possible_ids)}


async def quick_create_person(db, payload: PersonQuickCreate, actor_user_id: str, source: str) -> dict:
    existing = await db.persons.find_one({"idempotency_key": payload.idempotency_key})
    if existing:
        return {"status": "created", "person": _person_card(existing), "created": False}
    matches = await find_matches(db, payload)
    if matches["strong"]:
        return {"status": "strong_match", "candidates": matches["strong"]}
    if matches["possible"] and not (payload.confirm_distinct_person and (payload.distinct_reason or "").strip()):
        return {"status": "possible_match", "candidates": matches["possible"]}
    from core_person import next_person_number
    search_key = normalize_text(f"{payload.nombre} {payload.apellido}")
    now = now_utc()
    doc = {
        "nombre": payload.nombre.strip(), "apellido": payload.apellido.strip(),
        "fecha_nacimiento": payload.fecha_nacimiento, "person_number": await next_person_number(),
        "search_key": search_key, "idempotency_key": payload.idempotency_key, "version": 1,
        "created_by_user_id": actor_user_id, "created_source": source, "created_at": now, "updated_at": now,
    }
    if matches["possible"]:
        doc["distinct_person_confirmed"] = {"reason": payload.distinct_reason, "candidates": [c["person_id"] for c in matches["possible"]], "by_user_id": actor_user_id, "at": now}
    result = await db.persons.insert_one(doc)
    doc["_id"] = result.inserted_id
    contacts = []
    if payload.telefono:
        contacts.append({"person_id": str(result.inserted_id), "tipo": "telefono", "valor": payload.telefono, "valor_normalizado": normalize_phone(payload.telefono), "es_principal": True, "created_by_user_id": actor_user_id, "created_at": now, "updated_at": now})
    if payload.email:
        contacts.append({"person_id": str(result.inserted_id), "tipo": "email", "valor": payload.email, "es_principal": not contacts, "created_by_user_id": actor_user_id, "created_at": now, "updated_at": now})
    if contacts:
        await db.person_contacts.insert_many(contacts)
    return {"status": "created", "person": _person_card(doc), "created": True}
