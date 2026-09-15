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


def build_header(person: dict, current_user: dict) -> dict:
    """Cabecera tipo ficha/pasaporte -- solo identidad basica.

    ARCHITECTURE CONFLICT resuelto (Emergent, revision de PR #3): la
    version anterior proyectaba primary_contact/fecha_nacimiento usando
    unicamente el rol legacy lider/pastor, violando la decision FROZEN de
    privacidad por campo via capability+scope (un rol generico no otorga
    acceso automatico a datos sensibles). Mientras BASE-01/ACCESS-01 no
    existan en main, esos campos (y ciudad/direccion) se OMITEN por
    completo del payload -- nunca se devuelven, ni siquiera como null --
    para ningun rol. current_user se mantiene en la firma para cuando el
    modelo de capability+scope exista y este vuelva a ser el unico punto
    de proyeccion a actualizar."""
    return {
        "person_id": person["person_id"],
        "person_number": person["person_number"],
        "nombre_completo": f"{person.get('nombre','')} {person.get('apellido','')}".strip(),
        "initials": _initials(person.get("nombre"), person.get("apellido")),
        "age_category": person.get("age_category"),
        "photo_url": None,
    }


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
    header = build_header(person, current_user)
    sections = [_core_section(person)] + [_unavailable_section(k, l) for k, l in PLANNED_DOMAINS]
    return {
        "header": header,
        "sections": sections,
        "sections_available": ["resumen"],
        "sections_planned": ["contacto", "direcciones", "household", "familia", "procesos", "historial"],
    }
