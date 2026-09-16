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

from core_person import db, require_person_profile_user, serialize_person
from access_control import (
    PERSON_ADDRESSES_READ,
    PERSON_ADDRESSES_WRITE,
    PERSON_ARRIVAL_READ,
    PERSON_ATTENDANCE_READ,
    PERSON_CONTACTS_READ,
    PERSON_CONTACTS_WRITE,
    PERSON_FAMILY_READ,
    PERSON_HISTORY_READ,
    PERSON_HOUSEHOLD_READ,
    PERSON_NOTES_READ,
    PERSON_MINISTRIES_READ,
    PERSON_TALENTS_READ,
    PERSON_PROFILE_SENSITIVE_READ,
    PERSON_PROFILE_WRITE,
    can_access_person,
    has_capability,
)
from person_domains import address_items, contact_items
from person_profile_domains import profile_domain_snapshot
from person_core_expansion import age_info

router = APIRouter(prefix="/api/core", tags=["core-profile"])

# Catalogo del agregador 360. Cada dominio conserva su fuente de verdad;
# mientras no exista integracion real se declara module_unavailable.
PLANNED_DOMAINS = [
    ("llegada_origen", "Llegada y origen"),
    ("membership", "Membresía"),
    ("bautismo", "Bautismo"),
    ("bienvenida", "Bienvenida"),
    ("consolidacion", "Consolidación"),
    ("ley7", "Ley7"),
    ("discipulado", "Discipulado"),
    ("mentor_acompanamiento", "Mentor / Acompañamiento"),
    ("cap", "CAP"),
    ("celula", "Célula"),
    ("familia", "Familia"),
    ("household", "Household"),
    ("asistencia", "Asistencia"),
    ("historial", "Historial"),
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


def _restricted_section(key: str, label: str, tab_key: str) -> dict:
    return {
        "section_key": key,
        "status_code": "access_restricted",
        "status_label": label,
        "summary": None,
        "primary_date": None,
        "route": None,
        "tab_key": tab_key,
        "source_domain": key,
        "updated_at": None,
    }


def _domain_section(key: str, label: str, items: list[dict], summary: str | None) -> dict:
    # Filter out None values before finding max to avoid TypeError
    updated_ats = [item.get("updated_at") for item in items if item.get("updated_at") is not None]
    latest = max(updated_ats, default=None) if updated_ats else None
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
    """Project identity and authorized sensitive fields for the 360 header."""
    header = {
        "person_id": person["person_id"],
        "person_number": person["person_number"],
        "nombre": person.get("nombre"),
        "apellido": person.get("apellido"),
        "nombre_completo": f"{person.get('nombre','')} {person.get('apellido','')}".strip(),
        "initials": _initials(person.get("nombre"), person.get("apellido")),
        "age_category": person.get("age_category"),
        "photo_url": person.get("photo_url"),
    }
    if not can_access_person(current_user, person):
        return header

    if has_capability(current_user, PERSON_PROFILE_SENSITIVE_READ):
        for field in ("fecha_nacimiento", "genero", "estado_civil"):
            if person.get(field):
                header[field] = person[field]

    if has_capability(current_user, PERSON_CONTACTS_READ) and contacts:
        primary_contact = next(
            (item for item in contacts if item.get("es_principal")), contacts[0]
        )
        header["primary_contact"] = primary_contact.get("valor")
        phone = next(
            (
                item
                for item in contacts
                if item.get("tipo") in {"telefono", "whatsapp"}
                and item.get("es_principal")
            ),
            next(
                (item for item in contacts if item.get("tipo") in {"telefono", "whatsapp"}),
                None,
            ),
        )
        email = next(
            (item for item in contacts if item.get("tipo") == "email" and item.get("es_principal")),
            next((item for item in contacts if item.get("tipo") == "email"), None),
        )
        if phone:
            header["primary_phone"] = phone.get("valor")
        if email:
            header["primary_email"] = email.get("valor")

    if has_capability(current_user, PERSON_ADDRESSES_READ) and addresses:
        primary_address = next(
            (item for item in addresses if item.get("es_principal")), addresses[0]
        )
        if primary_address.get("ciudad"):
            header["city"] = primary_address["ciudad"]
    return header


@router.get("/persons/{person_id}/profile")
async def get_person_profile(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    try:
        oid = ObjectId(person_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="person_id invalido")
    doc = await db.persons.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person = serialize_person(doc)
    for optional_field in ("photo_url", "genero", "estado_civil"):
        if doc.get(optional_field):
            person[optional_field] = doc[optional_field]

    in_scope = can_access_person(current_user, person)
    can_read_contacts = in_scope and has_capability(current_user, PERSON_CONTACTS_READ)
    can_read_addresses = in_scope and has_capability(current_user, PERSON_ADDRESSES_READ)
    can_read_profile = in_scope and has_capability(current_user, PERSON_PROFILE_SENSITIVE_READ)
    can_write_profile = in_scope and has_capability(current_user, PERSON_PROFILE_WRITE)
    contacts = await contact_items(person_id) if can_read_contacts else []
    addresses = await address_items(person_id) if can_read_addresses else []
    domain_read_capabilities = (
        PERSON_PROFILE_SENSITIVE_READ,
        PERSON_HOUSEHOLD_READ,
        PERSON_FAMILY_READ,
        PERSON_ARRIVAL_READ,
        PERSON_ATTENDANCE_READ,
        PERSON_NOTES_READ,
        PERSON_HISTORY_READ,
        PERSON_MINISTRIES_READ,
        PERSON_TALENTS_READ,
    )
    can_read_any_domain = in_scope and any(
        has_capability(current_user, capability) for capability in domain_read_capabilities
    )
    snapshot = (
        await profile_domain_snapshot(person_id, current_user) if can_read_any_domain else None
    )
    header = build_header(person, current_user, contacts, addresses)
    if snapshot:
        header["photo_available"] = snapshot["photo_available"]
        header.update(await age_info(person.get("fecha_nacimiento")))
        if has_capability(current_user, PERSON_TALENTS_READ):
            occupation = snapshot["talentos"].get("ocupacion_principal")
            if occupation:
                header["ocupacion"] = occupation["nombre"]
            header["habilidades"] = snapshot["talentos"].get("habilidades", [])

    domain_sections = []
    available = ["resumen"]
    planned = []
    response = {"profile_can_write": can_write_profile}
    linked_user = await db.users.find_one(
        {"person_id": person_id},
        {"_id": 1, "rol": 1, "is_active": 1},
    )
    response["identity"] = {
        "canonical": True,
        "account_linked": bool(linked_user),
        "account_active": linked_user.get("is_active", True) if linked_user else None,
        "account_role": linked_user.get("rol") if linked_user else None,
    }

    if can_read_contacts:
        available.append("contacto")
        contact_section = _domain_section("contacto", "Contacto", contacts, _contact_summary(contacts))
        contact_section["tab_key"] = "contacto"
        domain_sections.append(contact_section)
        response["contacto"] = {
            "items": contacts,
            "can_write": has_capability(current_user, PERSON_CONTACTS_WRITE),
        }
    else:
        planned.append("contacto")
        domain_sections.append(_restricted_section("contacto", "Contacto", "contacto"))

    if can_read_addresses:
        available.append("direcciones")
        address_section = _domain_section(
            "direcciones", "Direcciones", addresses, _address_summary(addresses)
        )
        address_section["tab_key"] = "direcciones"
        domain_sections.append(address_section)
        response["direcciones"] = {
            "items": addresses,
            "can_write": has_capability(current_user, PERSON_ADDRESSES_WRITE),
        }
    else:
        planned.append("direcciones")
        domain_sections.append(_restricted_section("direcciones", "Direcciones", "direcciones"))

    built_sections = {}
    if snapshot:
        permissions = snapshot["permissions"]
        tab_access = {
            "household": permissions["household"]["read"],
            "familia": permissions["familia"]["read"],
            "procesos": permissions["procesos"]["read"] or permissions["ministerios"]["read"],
            "asistencia": permissions["asistencia"]["read"],
            "historial": permissions["historial"]["read"] or permissions["notas"]["read"],
        }
        for tab_key in ("household", "familia", "procesos", "asistencia", "historial"):
            (available if tab_access[tab_key] else planned).append(tab_key)

        household = snapshot["household"]
        family = snapshot["familia"]
        arrival = snapshot["llegada_origen"]
        attendance = snapshot["asistencia"]
        history = snapshot["historial"]
        ministries = snapshot["ministerios"]
        processes = snapshot.get("procesos", [])
        cell_memberships = snapshot.get("celula", [])
        built_sections = {
            "llegada_origen": (
                _domain_section(
                    "llegada_origen",
                    "Llegada y origen",
                    [arrival] if arrival else [],
                    f"{arrival['tipo'].capitalize()} · {arrival['fecha_llegada']}" if arrival else None,
                )
                if permissions["procesos"]["read"]
                else _restricted_section("llegada_origen", "Llegada y origen", "procesos")
            ),
            "familia": (
                _domain_section(
                    "familia",
                    "Familia",
                    family,
                    f"{len(family)} relación(es) registrada(s)" if family else None,
                )
                if permissions["familia"]["read"]
                else _restricted_section("familia", "Familia", "familia")
            ),
            "household": (
                _domain_section(
                    "household",
                    "Household",
                    [household] if household else [],
                    household.get("nombre_hogar") if household else None,
                )
                if permissions["household"]["read"]
                else _restricted_section("household", "Household", "household")
            ),
            "asistencia": (
                _domain_section(
                    "asistencia",
                    "Asistencia",
                    attendance,
                    f"Última: {attendance[0]['actividad']} · {attendance[0]['fecha']}"
                    if attendance
                    else None,
                )
                if permissions["asistencia"]["read"]
                else _restricted_section("asistencia", "Asistencia", "asistencia")
            ),
            "historial": (
                _domain_section(
                    "historial",
                    "Historial",
                    history,
                    f"{len(history)} actividad(es) registrada(s)" if history else None,
                )
                if permissions["historial"]["read"]
                else _restricted_section("historial", "Historial", "historial")
            ),
            "celula": (
                _domain_section(
                    "celula",
                    "Célula",
                    cell_memberships,
                    f"{cell_memberships[0].get('cell', {}).get('name', 'Célula')} · {'Activa' if cell_memberships[0].get('active') else 'Histórica'}" if cell_memberships else None,
                )
                if permissions.get("celula", {}).get("read")
                else _restricted_section("celula", "Célula", "procesos")
            ),
        }
        built_sections["llegada_origen"]["tab_key"] = "procesos"
        built_sections["familia"]["tab_key"] = "familia"
        built_sections["household"]["tab_key"] = "household"
        built_sections["asistencia"]["tab_key"] = "asistencia"
        built_sections["historial"]["tab_key"] = "historial"
        built_sections["celula"]["tab_key"] = "procesos"
        if cell_memberships:
            built_sections["celula"]["route"] = cell_memberships[0]["route"]
        process_domain_map = {
            "consolidacion": ("consolidation", "Consolidación"),
            "ley7": ("seven_weeks", "Ley de las 7 Semanas"),
            "mentor_acompanamiento": ("mentorship", "Mentoría"),
            "cap": ("cap", "CAP"),
        }
        for section_key, (process_key, label) in process_domain_map.items():
            enrollments = [item for item in processes if item.get("process_key") == process_key]
            if permissions["procesos"]["read"]:
                enrollment = enrollments[0] if enrollments else None
                summary = None
                if enrollment:
                    summary = enrollment.get("status_label") or enrollment.get("status")
                    if enrollment.get("current_stage_name"):
                        summary = f"{summary} · {enrollment['current_stage_name']}"
                section = _domain_section(section_key, label, enrollments, summary)
                if enrollment and enrollment.get("route"):
                    section["route"] = enrollment["route"]
            else:
                section = _restricted_section(section_key, label, "procesos")
            section["tab_key"] = "procesos"
            built_sections[section_key] = section
        
        # Ministerio/Servicio is now a real domain, add it separately
        ministries_section = (
            _domain_section(
                "ministerio_servicio",
                "Ministerio / Servicio",
                ministries,
                " · ".join(
                    f"{item['ministry_name']} — {item['role_name']}"
                    for item in ministries[:3]
                ) if ministries else None,
            )
            if permissions["ministerios"]["read"]
            else _restricted_section(
                "ministerio_servicio", "Ministerio / Servicio", "procesos"
            )
        )
        ministries_section["tab_key"] = "procesos"
        if len(ministries) == 1:
            ministries_section["route"] = ministries[0]["ministry_path"]
        domain_sections.append(ministries_section)
        
        response.update(snapshot)
    else:
        planned.extend(["household", "familia", "procesos", "asistencia", "historial"])
        built_sections = {
            "llegada_origen": _restricted_section(
                "llegada_origen", "Llegada y origen", "procesos"
            ),
            "familia": _restricted_section("familia", "Familia", "familia"),
            "household": _restricted_section("household", "Household", "household"),
            "asistencia": _restricted_section("asistencia", "Asistencia", "asistencia"),
            "historial": _restricted_section("historial", "Historial", "historial"),
        }
        # Ministerio/Servicio restricted when no snapshot
        ministries_section = _restricted_section(
            "ministerio_servicio", "Ministerio / Servicio", "procesos"
        )
        domain_sections.append(ministries_section)

    for key, label in PLANNED_DOMAINS:
        domain_sections.append(built_sections.get(key) or _unavailable_section(key, label))

    sections = [_core_section(person)] + domain_sections
    return {
        "canonical_profile_path": f"/personas/{person_id}",
        "header": header,
        "sections": sections,
        "sections_available": available,
        "sections_planned": planned,
        **response,
    }
