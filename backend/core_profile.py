"""
P-001 Slice 2A - Person Profile 360 (read-model, aditivo).
Capa de lectura/navegacion pura: no persiste resumenes dentro de persons ni
crea documentos vacios de dominios que aun no existen (Membership, Welcome,
Ley7, etc.). Cada dominio sigue siendo su propia fuente de verdad; este
modulo unicamente los presenta cuando existen y estan autorizados.
No modifica people/contacts/checklists/progress/Ley7.
"""
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Depends

from core_person import db, require_lider_o_pastor, serialize_person
from access_control import (
    PERSON_ADDRESSES_READ,
    PERSON_ADDRESSES_WRITE,
    PERSON_CONTACTS_READ,
    PERSON_CONTACTS_WRITE,
    PERSON_PROFILE_SENSITIVE_READ,
    can_access_person,
    has_capability,
)
from person_domains import address_items, contact_items

router = APIRouter(prefix="/api/core", tags=["core-profile"])

# Dominios previstos por el Blueprint. En Slice 2A ninguno tiene datos
# reales todavia -- se declaran explicitamente como module_unavailable en
# vez de fabricar estados falsos (no 'pendiente', no 'no completado').
PLANNED_DOMAINS = [
    ("llegada_origen", "Llegada y origen"),
    ("membership", "Membresia"),
    ("bautismo", "Bautismo"),
    ("bienvenida", "Bienvenida"),
    ("consolidacion", "Consolidacion"),
    ("ley7", "Ley7"),
    ("discipulado", "Discipulado"),
    ("mentoria", "Mentoria"),
    ("celulas", "Celulas"),
    ("ministerios", "Ministerios / Servicio"),
    ("household_familia", "Household / Familia"),
    ("eventos", "Eventos / Asistencia"),
    ("historial", "Trayectoria / Historial"),
]


def _initials(nombre: str, apellido: str) -> str:
    a = (nombre or "").strip()[:1]
    b = (apellido or "").strip()[:1]
    result = (a + b).upper()
    return result or "?"


def _core_section(person: dict) -> dict:
    nombre_completo = f"{person.get('nombre','')} {person.get('apellido','')}".strip()
    return {
        "section_key": "core",
        "status_code": "has_summary",
        "status_label": "Identidad registrada",
        "summary": nombre_completo or "Sin nombre",
        "primary_date": person.get("created_at"),
        "route": None,
        "source_domain": "core",
        "updated_at": person.get("updated_at"),
    }


def _unavailable_section(key: str, label: str) -> dict:
    return {
        "section_key": key,
        "status_code": "module_unavailable",
        "status_label": label,
        "summary": None,
        "primary_date": None,
        "route": None,
        "source_domain": key,
        "updated_at": None,
    }


def _domain_section(key: str, label: str, items: list[dict], summary: str | None) -> dict:
    latest = max((item.get("updated_at") for item in items), default=None)
    return {
        "section_key": key,
        "status_code": "has_summary" if items else "no_record",
        "status_label": label,
        "summary": summary if items else None,
        "primary_date": None,
        "route": None,
        "source_domain": key,
        "updated_at": latest,
    }


def _contact_summary(items: list[dict]) -> str | None:
    if not items:
        return None
    primary = next((item for item in items if item.get("es_principal")), items[0])
    return primary.get("valor") or f"{len(items)} contacto(s)"


def _address_summary(items: list[dict]) -> str | None:
    if not items:
        return None
    primary = next((item for item in items if item.get("es_principal")), items[0])
    parts = [primary.get("linea1"), primary.get("sector"), primary.get("ciudad")]
    return ", ".join(part for part in parts if part)


def build_header(
    person: dict,
    current_user: dict,
    contacts: list[dict],
    addresses: list[dict],
) -> dict:
    """Project sensitive header fields only through capability + person scope."""
    header = {
        "person_id": person["person_id"],
        "person_number": person["person_number"],
        "nombre_completo": f"{person.get('nombre','')} {person.get('apellido','')}".strip(),
        "initials": _initials(person.get("nombre"), person.get("apellido")),
        "age_category": person.get("age_category"),
        "photo_url": None,
    }
    if not can_access_person(current_user, person):
        return header
    if has_capability(current_user, PERSON_PROFILE_SENSITIVE_READ):
        header["fecha_nacimiento"] = person.get("fecha_nacimiento")
    if has_capability(current_user, PERSON_CONTACTS_READ) and contacts:
        primary_contact = next(
            (item for item in contacts if item.get("es_principal")), contacts[0]
        )
        header["primary_contact"] = primary_contact.get("valor")
    if has_capability(current_user, PERSON_ADDRESSES_READ) and addresses:
        primary_address = next(
            (item for item in addresses if item.get("es_principal")), addresses[0]
        )
        header["city"] = primary_address.get("ciudad")
    return header


@router.get("/persons/{person_id}/profile")
async def get_person_profile(person_id: str, current_user: dict = Depends(require_lider_o_pastor)):
    try:
        oid = ObjectId(person_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="person_id invalido")
    doc = await db.persons.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person = serialize_person(doc)

    in_scope = can_access_person(current_user, person)
    can_read_contacts = in_scope and has_capability(current_user, PERSON_CONTACTS_READ)
    can_read_addresses = in_scope and has_capability(current_user, PERSON_ADDRESSES_READ)
    contacts = await contact_items(person_id) if can_read_contacts else []
    addresses = await address_items(person_id) if can_read_addresses else []
    header = build_header(person, current_user, contacts, addresses)

    domain_sections = []
    available = ["resumen"]
    planned = ["household", "familia", "procesos", "historial"]
    response = {}

    if can_read_contacts:
        available.append("contacto")
        domain_sections.append(
            _domain_section("contacto", "Contacto", contacts, _contact_summary(contacts))
        )
        response["contacto"] = {
            "items": contacts,
            "can_write": has_capability(current_user, PERSON_CONTACTS_WRITE),
        }
    else:
        planned.insert(0, "contacto")

    if can_read_addresses:
        available.append("direcciones")
        domain_sections.append(
            _domain_section("direcciones", "Direcciones", addresses, _address_summary(addresses))
        )
        response["direcciones"] = {
            "items": addresses,
            "can_write": has_capability(current_user, PERSON_ADDRESSES_WRITE),
        }
    else:
        planned.insert(1 if planned and planned[0] == "contacto" else 0, "direcciones")

    sections = (
        [_core_section(person)]
        + domain_sections
        + [_unavailable_section(key, label) for key, label in PLANNED_DOMAINS]
    )
    return {
        "header": header,
        "sections": sections,
        "sections_available": available,
        "sections_planned": planned,
        **response,
    }
