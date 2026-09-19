"""Servicios idempotentes para enlazar cuentas y datos heredados con Person Core."""
import re
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId


class IdentityConflictError(ValueError):
    def __init__(self, message: str, conflict_id: str, candidate_ids: list[str]):
        super().__init__(message)
        self.conflict_id = conflict_id
        self.candidate_ids = candidate_ids


async def _record_identity_conflict(db, source_type: str, source_id: str, match_type: str, match_value: str, candidates: list[dict]) -> IdentityConflictError:
    conflict_id = f"{source_type}:{source_id}:{match_type}"
    candidate_ids = [str(item["_id"]) for item in candidates]
    now = utc_now()
    await db.identity_conflicts.update_one(
        {"_id": conflict_id},
        {"$set": {"conflict_id": conflict_id, "source_type": source_type, "source_id": source_id, "match_type": match_type, "match_value": match_value, "candidate_person_ids": candidate_ids, "status": "open", "updated_at": now}, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return IdentityConflictError("Existen varias Personas candidatas; el vínculo requiere revisión", conflict_id, candidate_ids)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.lower().split())


def split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in (full_name or "").strip().split() if part]
    if not parts:
        return "Persona", "Por completar"
    if len(parts) == 1:
        return parts[0], "Por completar"
    return " ".join(parts[:-1]), parts[-1]


def normalized_gender(value: str | None) -> str:
    return value if value in {"masculino", "femenino", "no_especificado"} else "no_especificado"


async def next_person_number(db) -> str:
    counter = await db.counters.find_one_and_update(
        {"_id": "person_number"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return f"VV-{counter['seq']:06d}"


async def _add_contact(db, person_id: str, kind: str, value: str | None, actor_id: str) -> None:
    cleaned = (value or "").strip()
    if not cleaned:
        return
    existing = await db.person_contacts.find_one({
        "person_id": person_id,
        "tipo": kind,
        "valor": {"$regex": f"^{re.escape(cleaned)}$", "$options": "i"},
    })
    if existing:
        return
    now = utc_now()
    await db.person_contacts.insert_one({
        "_id": str(uuid4()),
        "person_id": person_id,
        "tipo": kind,
        "valor": cleaned,
        "es_principal": not bool(await db.person_contacts.find_one({"person_id": person_id})),
        "source": "core_migration",
        "created_by": actor_id,
        "created_at": now,
        "updated_at": now,
    })


async def _find_person_for_user(db, user: dict) -> dict | None:
    person_id = user.get("person_id")
    if person_id and ObjectId.is_valid(person_id):
        person = await db.persons.find_one({"_id": ObjectId(person_id)})
        if person:
            return person
    user_id = str(user["_id"])
    person = await db.persons.find_one({"auth_user_id": user_id})
    if person:
        return person
    email = (user.get("email") or "").strip()
    if email:
        contact_person_ids = await db.person_contacts.distinct(
            "person_id",
            {"tipo": "email", "valor": {"$regex": f"^{re.escape(email)}$", "$options": "i"}},
        )
        candidates = await db.persons.find({
            "$and": [
                {"$or": [
                    {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}},
                    {"_id": {"$in": [ObjectId(item) for item in contact_person_ids if ObjectId.is_valid(item)]}},
                ]},
                {"$or": [{"auth_user_id": {"$exists": False}}, {"auth_user_id": user_id}]},
            ]
        }).limit(2).to_list(2)
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise await _record_identity_conflict(db, "user", user_id, "email", email.lower(), candidates)
    return None


async def ensure_user_person_link(db, user_id: str, actor_id: str) -> tuple[str, bool]:
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise ValueError("Usuario no encontrado")
    person = await _find_person_for_user(db, user)
    created = False
    now = utc_now()
    if not person:
        nombre, apellido = split_name(user.get("nombre", ""))
        person_id = ObjectId()
        person = {
            "_id": person_id,
            "person_number": await next_person_number(db),
            "nombre": nombre,
            "apellido": apellido,
            "search_key": normalize(f"{nombre} {apellido}"),
            "genero": "no_especificado",
            "age_category": None,
            "auth_user_id": user_id,
            "idempotency_key": f"identity:user:{user_id}",
            "identity_source": "auth_user",
            "created_by": user.get("leader_id") or actor_id or user_id,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        await db.persons.insert_one(person)
        created = True
    person_id = str(person["_id"])
    bound_user = person.get("auth_user_id")
    if bound_user not in (None, user_id):
        raise ValueError("La Persona ya está vinculada a otra cuenta")
    await db.persons.update_one(
        {"_id": person["_id"]},
        {"$set": {"auth_user_id": user_id, "updated_at": now}},
    )
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"person_id": person_id, "identity_policy_version": 1, "updated_at": now}},
    )
    await _add_contact(db, person_id, "email", user.get("email"), actor_id or user_id)
    return person_id, created


async def _migrate_occupation(db, person_id: str, occupation: str | None, actor_id: str) -> None:
    cleaned = " ".join((occupation or "").split())
    if not cleaned:
        return
    normalized_name = normalize(cleaned)
    talent = await db.talent_catalog.find_one({"normalized_name": normalized_name})
    if not talent:
        talent = {
            "_id": str(uuid4()),
            "nombre": cleaned,
            "normalized_name": normalized_name,
            "tipo": "ocupacion",
            "activo": True,
            "created_by": actor_id,
            "created_at": utc_now(),
        }
        await db.talent_catalog.insert_one(talent)
    await db.person_talents.update_one(
        {"_id": person_id},
        {"$set": {
            "person_id": person_id,
            "ocupacion_principal_id": talent["_id"],
            "updated_at": utc_now(),
            "updated_by": actor_id,
        }, "$setOnInsert": {"habilidad_ids": []}},
        upsert=True,
    )


async def sync_legacy_person_to_canonical(db, legacy: dict, actor_id: str) -> tuple[str, bool]:
    legacy_id = str(legacy["_id"])
    canonical_id = legacy.get("canonical_person_id")
    person = None
    if canonical_id and ObjectId.is_valid(canonical_id):
        person = await db.persons.find_one({"_id": ObjectId(canonical_id)})
    if not person and legacy.get("user_id") and ObjectId.is_valid(legacy["user_id"]):
        user = await db.users.find_one({"_id": ObjectId(legacy["user_id"])})
        if user:
            canonical_id, _ = await ensure_user_person_link(db, str(user["_id"]), actor_id)
            person = await db.persons.find_one({"_id": ObjectId(canonical_id)})
    if not person and legacy.get("telefono"):
        candidate_ids = await db.person_contacts.distinct(
            "person_id",
            {"tipo": {"$in": ["telefono", "whatsapp"]}, "valor": legacy["telefono"]},
        )
        candidates = await db.persons.find({
            "_id": {"$in": [ObjectId(item) for item in candidate_ids if ObjectId.is_valid(item)]}
        }).limit(2).to_list(2)
        if len(candidates) == 1:
            person = candidates[0]
        elif len(candidates) > 1:
            raise await _record_identity_conflict(db, "legacy_people", legacy_id, "phone", legacy["telefono"], candidates)
    created = False
    now = utc_now()
    nombre, apellido = split_name(legacy.get("nombre", ""))
    if not person:
        person = {
            "_id": ObjectId(),
            "person_number": await next_person_number(db),
            "nombre": nombre,
            "apellido": apellido,
            "search_key": normalize(f"{nombre} {apellido}"),
            "genero": normalized_gender(legacy.get("genero")),
            "age_category": "adulto" if (legacy.get("edad") or 0) >= 18 else None,
            "idempotency_key": f"identity:legacy-people:{legacy_id}",
            "identity_source": "legacy_people",
            "created_by": legacy.get("leader_id") or actor_id,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        await db.persons.insert_one(person)
        created = True
    canonical_id = str(person["_id"])
    update = {
        "nombre": nombre,
        "apellido": apellido,
        "search_key": normalize(f"{nombre} {apellido}"),
        "genero": normalized_gender(legacy.get("genero")),
        "updated_at": now,
    }
    await db.persons.update_one({"_id": person["_id"]}, {"$set": update})
    await db.people.update_one(
        {"_id": legacy["_id"]},
        {"$set": {"canonical_person_id": canonical_id, "identity_policy_version": 1, "updated_at": now}},
    )
    await _add_contact(db, canonical_id, "telefono", legacy.get("telefono"), actor_id)
    await _migrate_occupation(db, canonical_id, legacy.get("ocupacion"), actor_id)
    return canonical_id, created


async def migrate_core_identity(db, actor_id: str) -> dict:
    result = {
        "users_linked": 0,
        "persons_created_for_users": 0,
        "legacy_people_linked": 0,
        "persons_created_for_legacy": 0,
        "conflicts": [],
    }
    users = await db.users.find({}).to_list(10000)
    for user in users:
        try:
            before = user.get("person_id")
            person_id, created = await ensure_user_person_link(db, str(user["_id"]), actor_id)
            if before != person_id:
                result["users_linked"] += 1
            if created:
                result["persons_created_for_users"] += 1
        except Exception as exc:
            result["conflicts"].append({"source": "users", "source_id": str(user["_id"]), "detail": str(exc)})
    legacy_people = await db.people.find({}).to_list(10000)
    for legacy in legacy_people:
        try:
            before = legacy.get("canonical_person_id")
            person_id, created = await sync_legacy_person_to_canonical(db, legacy, actor_id)
            if before != person_id:
                result["legacy_people_linked"] += 1
            if created:
                result["persons_created_for_legacy"] += 1
        except Exception as exc:
            result["conflicts"].append({"source": "people", "source_id": str(legacy["_id"]), "detail": str(exc)})
    result["conflict_count"] = len(result["conflicts"])
    return result