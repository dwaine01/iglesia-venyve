"""Canonical Person expansion: relationships, households and talent directory.

FROZEN: relationships connect two canonical person_ids. Household membership
and structured talents remain separate domains; neither is embedded in persons.
"""
import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from access_control import (
    PERSON_DIRECTORY_SEARCH,
    PERSON_FAMILY_READ,
    PERSON_FAMILY_WRITE,
    PERSON_HOUSEHOLD_READ,
    PERSON_HOUSEHOLD_WRITE,
    PERSON_MINISTRIES_WRITE,
    PERSON_TALENTS_READ,
    PERSON_TALENTS_WRITE,
    authorize_person,
    can_access_person,
    has_capability,
)
from core_person import db, next_person_number, now_utc, require_person_profile_user

router = APIRouter(tags=["canonical-person-expansion"])

GENDERS = {"masculino", "femenino", "no_especificado"}
CIVIL_STATUSES = {
    "soltero", "casado", "divorciado", "viudo", "separado", "otro", "no_especificado"
}
RELATION_LABELS = {
    "parent_of": ("Padre/Madre", "Hijo/a"),
    "child_of": ("Hijo/a", "Padre/Madre"),
    "spouse_of": ("Cónyuge", "Cónyuge"),
    "sibling_of": ("Hermano/a", "Hermano/a"),
    "grandparent_of": ("Abuelo/a", "Nieto/a"),
    "grandchild_of": ("Nieto/a", "Abuelo/a"),
    "guardian_of": ("Tutor/a", "Persona tutelada"),
    "other": ("Familiar", "Familiar"),
}
INITIAL_TALENTS = [
    "Plomero", "Electricista", "Pintor", "Albañil", "Mecánico", "Carpintero",
    "Soldador", "Técnico HVAC", "Construcción", "Contabilidad", "Enfermería",
    "Maestro/a", "Cocina", "Fotografía", "Video", "Sonido", "Música",
    "Informática", "Diseño gráfico", "Transporte",
]
DEFAULT_AGE_RULES = [
    {"key": "ninez", "label": "Niñez", "min_age": 0, "max_age": 11},
    {"key": "adolescencia", "label": "Adolescencia", "min_age": 12, "max_age": 17},
    {"key": "adulto", "label": "Adulto", "min_age": 18, "max_age": 120},
]


def normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return " ".join(
        "".join(char for char in normalized if not unicodedata.combining(char)).lower().split()
    )


def iso_z(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def load_person(person_id: str) -> dict:
    try:
        oid = ObjectId(person_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="person_id invalido")
    person = await db.persons.find_one({"_id": oid})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person["person_id"] = person_id
    return person


async def authorize(person_id: str, user: dict, capability: str) -> dict:
    person = await load_person(person_id)
    authorize_person(user, person, capability)
    return person


async def activity(person_id: str, user: dict, domain: str, summary: str) -> None:
    await db.person_activity.insert_one({
        "_id": str(uuid4()),
        "person_id": person_id,
        "domain": domain,
        "action": "updated",
        "summary": summary,
        "actor_user_id": user.get("user_id"),
        "created_at": now_utc(),
    })


def calculate_age(dob: Optional[str]) -> Optional[int]:
    if not dob:
        return None
    try:
        born = date.fromisoformat(dob)
    except ValueError:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


async def age_info(dob: Optional[str]) -> dict:
    age = calculate_age(dob)
    if age is None:
        return {"age_years": None, "age_group": None, "age_group_label": None}
    policy = await db.person_settings.find_one({"_id": "age_policy"})
    rules = (policy or {}).get("rules") or DEFAULT_AGE_RULES
    matched = next(
        (rule for rule in rules if rule["min_age"] <= age <= rule["max_age"]), None
    )
    return {
        "age_years": age,
        "age_group": matched.get("key") if matched else None,
        "age_group_label": matched.get("label") if matched else None,
    }


RelationType = Literal[
    "parent_of", "child_of", "spouse_of", "sibling_of",
    "grandparent_of", "grandchild_of", "guardian_of", "other"
]


class RelationshipPayload(BaseModel):
    related_person_id: str
    relation_type: RelationType
    same_household: bool = False


class QuickMinistryAssignment(BaseModel):
    ministry_id: str
    role_id: str


class QuickPersonPayload(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    apellido: str = Field(..., min_length=2, max_length=100)
    fecha_nacimiento: Optional[str] = None
    genero: Literal["masculino", "femenino", "no_especificado"] = "no_especificado"
    telefono: Optional[str] = Field(default=None, max_length=80)
    email: Optional[str] = Field(default=None, max_length=180)
    linea1: Optional[str] = Field(default=None, max_length=220)
    ciudad: Optional[str] = Field(default=None, max_length=120)
    relation_type: RelationType
    same_household: bool = False
    ministry_assignments: list[QuickMinistryAssignment] = Field(default_factory=list, max_length=20)

    @field_validator("nombre", "apellido")
    @classmethod
    def clean_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("fecha_nacimiento")
    @classmethod
    def valid_date(cls, value: Optional[str]) -> Optional[str]:
        if value:
            date.fromisoformat(value)
        return value


class HouseholdMembershipPayload(BaseModel):
    nombre_hogar: str = Field(..., min_length=2, max_length=140)
    rol_en_hogar: Optional[str] = Field(default=None, max_length=80)
    tipo_vivienda: Optional[str] = Field(default=None, max_length=80)
    notas: Optional[str] = Field(default=None, max_length=1000)


class TalentCatalogPayload(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    tipo: Literal["ocupacion", "habilidad", "ambos"] = "ambos"

    @field_validator("nombre")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.strip().split())


class PersonTalentsPayload(BaseModel):
    ocupacion_principal_id: Optional[str] = None
    habilidad_ids: list[str] = Field(default_factory=list, max_length=30)


class AgePolicyPayload(BaseModel):
    rules: list[dict] = Field(..., min_length=1, max_length=20)


async def serialize_person_brief(person: dict) -> dict:
    person_id = str(person["_id"])
    talents = await talent_snapshot(person_id)
    age = await age_info(person.get("fecha_nacimiento"))
    return {
        "person_id": person_id,
        "person_number": person.get("person_number"),
        "nombre": person.get("nombre"),
        "apellido": person.get("apellido"),
        "nombre_completo": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
        "genero": person.get("genero") or "no_especificado",
        "age_category": person.get("age_category"),
        **age,
        "talents": talents,
        "canonical_profile_path": f"/personas/{person_id}",
    }


async def talent_snapshot(person_id: str) -> dict:
    assignment = await db.person_talents.find_one({"_id": person_id}) or {}
    ids = [assignment.get("ocupacion_principal_id"), *assignment.get("habilidad_ids", [])]
    ids = [item for item in ids if item]
    catalog = {
        doc["_id"]: doc
        async for doc in db.talent_catalog.find({"_id": {"$in": ids}, "activo": True})
    }
    occupation_id = assignment.get("ocupacion_principal_id")
    return {
        "ocupacion_principal": (
            {"talent_id": occupation_id, "nombre": catalog[occupation_id]["nombre"]}
            if occupation_id in catalog
            else None
        ),
        "habilidades": [
            {"talent_id": item, "nombre": catalog[item]["nombre"]}
            for item in assignment.get("habilidad_ids", [])
            if item in catalog
        ],
    }


async def household_snapshot(person_id: str) -> Optional[dict]:
    membership = await db.household_memberships.find_one({"person_id": person_id})
    if not membership:
        return None
    household = await db.households.find_one({"_id": membership["household_id"]})
    if not household:
        return None
    members = await db.household_memberships.find(
        {"household_id": household["_id"]}
    ).to_list(100)
    people = {
        str(doc["_id"]): doc
        async for doc in db.persons.find(
            {"_id": {"$in": [ObjectId(item["person_id"]) for item in members]}}
        )
    }
    return {
        "household_id": household["_id"],
        "nombre_hogar": household["nombre_hogar"],
        "tipo_vivienda": household.get("tipo_vivienda"),
        "notas": household.get("notas"),
        "rol_en_hogar": membership.get("rol_en_hogar"),
        "members": [
            {
                "person_id": item["person_id"],
                "nombre_completo": f"{people.get(item['person_id'], {}).get('nombre', '')} {people.get(item['person_id'], {}).get('apellido', '')}".strip(),
                "person_number": people.get(item["person_id"], {}).get("person_number"),
                "rol_en_hogar": item.get("rol_en_hogar"),
                "canonical_profile_path": f"/personas/{item['person_id']}",
            }
            for item in members
        ],
        "updated_at": iso_z(household.get("updated_at")),
    }


async def relationship_items(person_id: str) -> list[dict]:
    docs = await db.person_relationships.find(
        {"$or": [{"person_a_id": person_id}, {"person_b_id": person_id}]}
    ).sort("created_at", 1).to_list(300)
    related_ids = [
        item["person_b_id"] if item["person_a_id"] == person_id else item["person_a_id"]
        for item in docs
    ]
    related_people = {
        str(doc["_id"]): doc
        async for doc in db.persons.find({"_id": {"$in": [ObjectId(item) for item in related_ids]}})
    }
    result = []
    for item in docs:
        forward = item["person_a_id"] == person_id
        related_id = item["person_b_id"] if forward else item["person_a_id"]
        person = related_people.get(related_id, {})
        labels = RELATION_LABELS[item["relation_type"]]
        result.append({
            "relationship_id": item["_id"],
            "related_person_id": related_id,
            "relation_type": item["relation_type"] if forward else f"inverse:{item['relation_type']}",
            "relation_label": labels[0] if forward else labels[1],
            "nombre_completo": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
            "person_number": person.get("person_number"),
            "fecha_nacimiento": person.get("fecha_nacimiento"),
            **await age_info(person.get("fecha_nacimiento")),
            "canonical_profile_path": f"/personas/{related_id}",
        })
    return result


async def create_relationship(
    person_id: str,
    related_person_id: str,
    relation_type: str,
    user: dict,
) -> dict:
    if person_id == related_person_id:
        raise HTTPException(status_code=400, detail="Una Persona no puede relacionarse consigo misma")
    related = await load_person(related_person_id)
    if not can_access_person(user, related):
        raise HTTPException(status_code=403, detail="Sin scope sobre la Persona relacionada")
    existing = await db.person_relationships.find_one({
        "$or": [
            {"person_a_id": person_id, "person_b_id": related_person_id},
            {"person_a_id": related_person_id, "person_b_id": person_id},
        ]
    })
    if existing:
        raise HTTPException(status_code=409, detail="Estas Personas ya tienen una relación")
    doc = {
        "_id": str(uuid4()),
        "pair_key": ":".join(sorted([person_id, related_person_id])),
        "person_a_id": person_id,
        "person_b_id": related_person_id,
        "relation_type": relation_type,
        "created_by": user["user_id"],
        "created_at": now_utc(),
    }
    await db.person_relationships.insert_one(doc)
    await activity(person_id, user, "familia", "Relación familiar creada")
    await activity(related_person_id, user, "familia", "Relación familiar creada")
    return doc


async def add_to_same_household(person_id: str, related_person_id: str, user: dict) -> None:
    membership = await db.household_memberships.find_one({"person_id": person_id})
    if not membership:
        person = await load_person(person_id)
        household_id = str(uuid4())
        await db.households.insert_one({
            "_id": household_id,
            "nombre_hogar": f"Hogar de {person.get('apellido') or person.get('nombre')}",
            "created_by": user["user_id"],
            "created_at": now_utc(),
            "updated_at": now_utc(),
        })
        await db.household_memberships.insert_one({
            "_id": str(uuid4()), "household_id": household_id,
            "person_id": person_id, "created_at": now_utc(),
        })
    else:
        household_id = membership["household_id"]
    await db.household_memberships.update_one(
        {"person_id": related_person_id},
        {"$setOnInsert": {
            "_id": str(uuid4()), "household_id": household_id,
            "person_id": related_person_id, "created_at": now_utc(),
        }},
        upsert=True,
    )


@router.get("/api/core/talents/catalog")
async def list_talent_catalog(
    q: str = "",
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, PERSON_TALENTS_READ):
        raise HTTPException(status_code=403, detail="Directorio de talentos restringido")
    query = {"activo": True}
    if q.strip():
        query["normalized_name"] = {"$regex": re.escape(normalize(q)), "$options": "i"}
    docs = await db.talent_catalog.find(query).sort("nombre", 1).to_list(500)
    return {"items": [{"talent_id": doc["_id"], "nombre": doc["nombre"], "tipo": doc["tipo"]} for doc in docs]}


@router.post("/api/core/talents/catalog", status_code=status.HTTP_201_CREATED)
async def create_talent_catalog(
    payload: TalentCatalogPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, PERSON_TALENTS_WRITE):
        raise HTTPException(status_code=403, detail="Catálogo de talentos restringido")
    normalized = normalize(payload.nombre)
    existing = await db.talent_catalog.find_one({"normalized_name": normalized})
    if existing:
        return {"talent_id": existing["_id"], "nombre": existing["nombre"], "tipo": existing["tipo"]}
    doc = {
        "_id": str(uuid4()), "nombre": payload.nombre,
        "normalized_name": normalized, "tipo": payload.tipo,
        "activo": True, "created_by": current_user["user_id"], "created_at": now_utc(),
    }
    await db.talent_catalog.insert_one(doc)
    return {"talent_id": doc["_id"], "nombre": doc["nombre"], "tipo": doc["tipo"]}


@router.get("/api/core/persons/directory/search")
async def search_directory(
    q: str = "",
    talent_id: Optional[str] = None,
    genero: Optional[str] = None,
    age_group: Optional[str] = None,
    ministry_id: Optional[str] = None,
    ministry_role_id: Optional[str] = None,
    membership_status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, PERSON_DIRECTORY_SEARCH):
        raise HTTPException(status_code=403, detail="Directorio interno restringido")
    if membership_status:
        raise HTTPException(status_code=409, detail="Módulo de Membresía aún no disponible")
    ministry_person_ids = None
    if ministry_id or ministry_role_id:
        assignment_query = {"activo": True}
        if ministry_id:
            assignment_query["ministry_id"] = ministry_id
        if ministry_role_id:
            assignment_query["role_id"] = ministry_role_id
        ministry_person_ids = set(
            await db.ministry_assignments.distinct("person_id", assignment_query)
        )
    query = {}
    if genero:
        query["genero"] = genero
    candidates = await db.persons.find(query).limit(500).to_list(500)
    needle = normalize(q)
    results = []
    for person in candidates:
        person["person_id"] = str(person["_id"])
        if ministry_person_ids is not None and person["person_id"] not in ministry_person_ids:
            continue
        if not can_access_person(current_user, person):
            continue
        talents = await talent_snapshot(person["person_id"])
        talent_ids = [
            talents["ocupacion_principal"]["talent_id"] if talents["ocupacion_principal"] else None,
            *[item["talent_id"] for item in talents["habilidades"]],
        ]
        searchable = normalize(
            " ".join([
                person.get("nombre", ""), person.get("apellido", ""),
                person.get("person_number", ""),
                *([talents["ocupacion_principal"]["nombre"]] if talents["ocupacion_principal"] else []),
                *[item["nombre"] for item in talents["habilidades"]],
            ])
        )
        age = await age_info(person.get("fecha_nacimiento"))
        if needle and needle not in searchable:
            continue
        if talent_id and talent_id not in talent_ids:
            continue
        if age_group and age["age_group"] != age_group:
            continue
        results.append({**await serialize_person_brief(person), "talents": talents})
        if len(results) >= limit:
            break
    return {"items": results, "total": len(results), "membership_filter_available": False}


@router.get("/api/core/persons/{person_id}/talents")
async def get_person_talents(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize(person_id, current_user, PERSON_TALENTS_READ)
    return await talent_snapshot(person_id)


@router.put("/api/core/persons/{person_id}/talents")
async def update_person_talents(
    person_id: str,
    payload: PersonTalentsPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize(person_id, current_user, PERSON_TALENTS_WRITE)
    ids = [payload.ocupacion_principal_id, *payload.habilidad_ids]
    ids = [item for item in ids if item]
    found = await db.talent_catalog.count_documents({"_id": {"$in": ids}, "activo": True})
    if found != len(set(ids)):
        raise HTTPException(status_code=400, detail="Ocupación o habilidad inválida")
    await db.person_talents.update_one(
        {"_id": person_id},
        {"$set": {
            "person_id": person_id,
            "ocupacion_principal_id": payload.ocupacion_principal_id,
            "habilidad_ids": list(dict.fromkeys(payload.habilidad_ids)),
            "updated_at": now_utc(),
            "updated_by": current_user["user_id"],
        }},
        upsert=True,
    )
    await activity(person_id, current_user, "talentos", "Ocupación y habilidades actualizadas")
    return await talent_snapshot(person_id)


@router.get("/api/core/persons/{person_id}/relationships/search")
async def search_relationship_candidates(
    person_id: str,
    q: str = Query(..., min_length=2),
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize(person_id, current_user, PERSON_FAMILY_WRITE)
    needle = normalize(q)
    contact_ids = await db.person_contacts.distinct(
        "person_id", {"valor": {"$regex": re.escape(q), "$options": "i"}}
    )
    candidates = await db.persons.find({
        "$or": [
            {"nombre": {"$regex": re.escape(q), "$options": "i"}},
            {"apellido": {"$regex": re.escape(q), "$options": "i"}},
            {"person_number": {"$regex": re.escape(q), "$options": "i"}},
            {"_id": {"$in": [ObjectId(item) for item in contact_ids if ObjectId.is_valid(item)]}},
        ]
    }).limit(30).to_list(30)
    items = []
    for person in candidates:
        candidate_id = str(person["_id"])
        person["person_id"] = candidate_id
        if candidate_id != person_id and can_access_person(current_user, person):
            brief = await serialize_person_brief(person)
            if needle in normalize(f"{brief['nombre_completo']} {brief['person_number']}") or candidate_id in contact_ids:
                items.append(brief)
    return {"items": items}


@router.get("/api/core/persons/{person_id}/relationships")
async def list_relationships(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize(person_id, current_user, PERSON_FAMILY_READ)
    return {"items": await relationship_items(person_id)}


@router.post("/api/core/persons/{person_id}/relationships", status_code=status.HTTP_201_CREATED)
async def add_relationship(
    person_id: str,
    payload: RelationshipPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize(person_id, current_user, PERSON_FAMILY_WRITE)
    doc = await create_relationship(
        person_id, payload.related_person_id, payload.relation_type, current_user
    )
    if payload.same_household:
        await add_to_same_household(person_id, payload.related_person_id, current_user)
    return {"relationship_id": doc["_id"]}


@router.delete("/api/core/persons/{person_id}/relationships/{relationship_id}")
async def delete_relationship(
    person_id: str,
    relationship_id: str,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize(person_id, current_user, PERSON_FAMILY_WRITE)
    result = await db.person_relationships.delete_one({
        "_id": relationship_id,
        "$or": [{"person_a_id": person_id}, {"person_b_id": person_id}],
    })
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Relación no encontrada")
    await activity(person_id, current_user, "familia", "Relación familiar eliminada")
    return {"message": "Relación eliminada"}


@router.post("/api/core/persons/{person_id}/family/quick-create", status_code=status.HTTP_201_CREATED)
async def quick_create_family_person(
    person_id: str,
    payload: QuickPersonPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize(person_id, current_user, PERSON_FAMILY_WRITE)
    if payload.ministry_assignments and not has_capability(
        current_user, PERSON_MINISTRIES_WRITE
    ):
        raise HTTPException(status_code=403, detail="Asignación ministerial restringida")
    validated_assignments = []
    for assignment in payload.ministry_assignments:
        ministry = await db.ministry_catalog.find_one({"_id": assignment.ministry_id, "activo": True})
        role = await db.ministry_roles.find_one({"_id": assignment.role_id, "activo": True})
        if not ministry or not role or role.get("ministry_id") not in (None, assignment.ministry_id):
            raise HTTPException(status_code=400, detail="Asignación ministerial inválida")
        validated_assignments.append(assignment)
    duplicate = await db.persons.find_one({
        "nombre": {"$regex": f"^{re.escape(payload.nombre)}$", "$options": "i"},
        "apellido": {"$regex": f"^{re.escape(payload.apellido)}$", "$options": "i"},
        **({"fecha_nacimiento": payload.fecha_nacimiento} if payload.fecha_nacimiento else {}),
    })
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Posible Persona existente; selecciónela antes de crear otra",
                "person_id": str(duplicate["_id"]),
                "person_number": duplicate.get("person_number"),
            },
        )
    new_person_id = str(ObjectId())
    now = now_utc()
    calculated_age = calculate_age(payload.fecha_nacimiento)
    person_doc = {
        "_id": ObjectId(new_person_id),
        "person_number": await next_person_number(),
        "nombre": payload.nombre,
        "apellido": payload.apellido,
        "fecha_nacimiento": payload.fecha_nacimiento,
        "genero": payload.genero,
        "age_category": (
            "adulto" if calculated_age is not None and calculated_age >= 18
            else "menor" if calculated_age is not None
            else None
        ),
        "created_by": current_user["user_id"],
        "created_at": now,
        "updated_at": now,
        "version": 1,
    }
    await db.persons.insert_one(person_doc)
    contact_docs = []
    if payload.telefono:
        contact_docs.append({
            "person_id": new_person_id, "tipo": "telefono", "valor": payload.telefono,
            "es_principal": True, "created_by": current_user["user_id"],
            "created_at": now, "updated_at": now,
        })
    if payload.email:
        contact_docs.append({
            "person_id": new_person_id, "tipo": "email", "valor": payload.email,
            "es_principal": not contact_docs, "created_by": current_user["user_id"],
            "created_at": now, "updated_at": now,
        })
    if contact_docs:
        await db.person_contacts.insert_many(contact_docs)
    if payload.linea1 and payload.ciudad:
        await db.person_addresses.insert_one({
            "person_id": new_person_id, "tipo": "casa", "linea1": payload.linea1,
            "ciudad": payload.ciudad, "pais": "República Dominicana",
            "es_principal": True, "created_by": current_user["user_id"],
            "created_at": now, "updated_at": now,
        })
    await create_relationship(person_id, new_person_id, payload.relation_type, current_user)
    if payload.same_household:
        await add_to_same_household(person_id, new_person_id, current_user)
    for assignment in validated_assignments:
        await db.ministry_assignments.insert_one({
            "_id": str(uuid4()),
            "person_id": new_person_id,
            "ministry_id": assignment.ministry_id,
            "role_id": assignment.role_id,
            "activo": True,
            "fecha_inicio": date.today().isoformat(),
            "fecha_fin": None,
            "registered_by": current_user["user_id"],
            "version": 1,
            "created_at": now,
            "updated_at": now,
        })
    return {
        "person_id": new_person_id,
        "person_number": person_doc["person_number"],
        "canonical_profile_path": f"/personas/{new_person_id}",
    }


@router.get("/api/core/persons/{person_id}/household-membership")
async def get_household_membership(
    person_id: str,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize(person_id, current_user, PERSON_HOUSEHOLD_READ)
    return {"record": await household_snapshot(person_id)}


@router.put("/api/core/persons/{person_id}/household-membership")
async def upsert_household_membership(
    person_id: str,
    payload: HouseholdMembershipPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize(person_id, current_user, PERSON_HOUSEHOLD_WRITE)
    membership = await db.household_memberships.find_one({"person_id": person_id})
    now = now_utc()
    if membership:
        household_id = membership["household_id"]
    else:
        household_id = str(uuid4())
        await db.household_memberships.insert_one({
            "_id": str(uuid4()), "household_id": household_id,
            "person_id": person_id, "created_at": now,
        })
    await db.households.update_one(
        {"_id": household_id},
        {"$set": {
            "nombre_hogar": payload.nombre_hogar,
            "tipo_vivienda": payload.tipo_vivienda,
            "notas": payload.notas,
            "updated_at": now,
        }, "$setOnInsert": {"created_by": current_user["user_id"], "created_at": now}},
        upsert=True,
    )
    await db.household_memberships.update_one(
        {"person_id": person_id}, {"$set": {"rol_en_hogar": payload.rol_en_hogar}}
    )
    await activity(person_id, current_user, "household", "Household actualizado")
    return await household_snapshot(person_id)


@router.get("/api/core/persons/age-policy")
async def get_age_policy(current_user: dict = Depends(require_person_profile_user)):
    policy = await db.person_settings.find_one({"_id": "age_policy"})
    return {"rules": (policy or {}).get("rules") or DEFAULT_AGE_RULES}


@router.put("/api/core/persons/age-policy")
async def update_age_policy(
    payload: AgePolicyPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    if not has_capability(current_user, PERSON_TALENTS_WRITE):
        raise HTTPException(status_code=403, detail="Configuración restringida")
    await db.person_settings.update_one(
        {"_id": "age_policy"},
        {"$set": {"rules": payload.rules, "updated_at": now_utc()}},
        upsert=True,
    )
    return {"rules": payload.rules}


async def ensure_indexes_and_seed() -> None:
    await db.person_relationships.create_index("pair_key", unique=True)
    await db.person_relationships.create_index([("person_a_id", 1), ("person_b_id", 1)])
    await db.household_memberships.create_index("person_id", unique=True)
    await db.household_memberships.create_index("household_id")
    await db.talent_catalog.create_index("normalized_name", unique=True)
    await db.person_talents.create_index("person_id")
    for name in INITIAL_TALENTS:
        await db.talent_catalog.update_one(
            {"normalized_name": normalize(name)},
            {"$setOnInsert": {
                "_id": str(uuid4()), "nombre": name, "normalized_name": normalize(name),
                "tipo": "ambos", "activo": True, "created_at": now_utc(),
            }},
            upsert=True,
        )
