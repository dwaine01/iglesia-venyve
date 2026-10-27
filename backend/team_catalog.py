"""Equipo y Responsables · E2: catálogo de áreas y cargos (todavía sin asignaciones).

Cada cargo dice su área, si es responsable principal o asistente, cuántas personas lo pueden ocupar
(máximo 3, decisión del dueño), qué permisos da (solo del catálogo existente) y DÓNDE vive el dato:
- `team`: lo guarda este módulo (Dirección-copastor, Finanzas, Librería, Educación, Operación, cargos nuevos);
- `account_role`: solo se muestra; se cambia en Gestión de accesos (pastor principal, coordinador general);
- `consolidation_leads`, `mentorship`, `front_groups`, `ministries`: se leen y escriben en su módulo (E4),
  para que no existan dos fuentes de verdad.
Lo ven y lo usan el pastor y el coordinador general. Crear o cambiar cargos: el coordinador solo con permisos
que él ya tiene y nunca de Finanzas o Junta (no puede escalar privilegios). Nada se borra: se desactiva, y
cada cambio queda en `team_catalog_events` (historial inmutable)."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import (
    BOARD_ACCESS, FINANCE_CAPABILITIES, FINANCE_COLLECTION_RECORD, FINANCE_COLLECTION_VERIFY, FINANCE_MANAGE, FINANCE_READ, FINANCE_TREASURY,
    capability_catalog_keys, is_general_coordinator, is_global_pastoral_authority, normalized_capabilities,
)
from server import db, get_current_user

router = APIRouter(prefix="/api/team", tags=["team"])

MAX_HOLDERS = 3
SOURCES = ("team", "account_role", "consolidation_leads", "mentorship", "front_groups", "ministries")
SENSITIVE_GROUPS = {"finance", "board"}

# (área, orden, [(clave, nombre, tipo, fuente, permisos, grupo de privilegio, máximo, por_unidad)])
SEED = [
    ("direccion", "Dirección", 1, [
        ("pastor_principal", "Pastor principal", "principal", "account_role", [], None, 1, None),
        ("copastor", "Copastor", "principal", "team", [], None, 3, None),
        ("coordinador_general", "Coordinador general", "principal", "account_role", [], None, 3, None),
    ]),
    ("finanzas", "Finanzas", 2, [
        ("finanzas_registra", "Encargado de Finanzas (registra y cuenta)", "principal", "team", [FINANCE_READ, FINANCE_MANAGE, FINANCE_COLLECTION_RECORD], "finance", 3, None),
        ("finanzas_verifica", "Segundo verificador (verifica)", "principal", "team", [FINANCE_READ, FINANCE_COLLECTION_VERIFY], "finance", 3, None),
        ("tesorero", "Tesorero (recibe y deposita)", "principal", "team", [FINANCE_READ, FINANCE_TREASURY], "finance", 3, None),
    ]),
    ("consolidacion", "Consolidación", 3, [
        ("lider_consolidacion", "Líder de Consolidación", "principal", "consolidation_leads", [], None, 3, None),
        ("supervisor_consolidacion", "Supervisor de Consolidación", "asistente", "team", ["processes.read", "processes.alerts.manage"], None, 3, None),
        ("mentor", "Mentores", "asistente", "mentorship", [], None, None, None),
    ]),
    ("grupos_frontales", "Grupos frontales", 4, [
        ("coordinador_grupos", "Coordinador de grupos frontales", "principal", "team", ["front_groups.view", "front_groups.manage"], None, 3, None),
        ("responsable_grupo", "Responsable de cada grupo", "principal", "front_groups", [], None, 3, "front_group"),
    ]),
    ("libreria", "Librería", 5, [
        ("encargado_libreria", "Encargado de Librería", "principal", "team", ["library.catalog.manage", "library.inventory.manage", "library.reports.read"], None, 3, None),
        ("asistente_libreria", "Asistente de Librería", "asistente", "team", ["library.deliver"], None, 3, None),
    ]),
    ("educacion", "Educación", 6, [
        ("director_educacion", "Director de Educación", "principal", "team", ["formation.read", "formation.programs.manage", "formation.cohorts.manage", "formation.progress.manage"], None, 3, None),
        ("coordinador_educacion", "Coordinador de Educación", "asistente", "team", ["formation.read", "formation.cohorts.manage", "formation.enroll"], None, 3, None),
        ("maestro", "Maestro", "asistente", "team", ["formation.read", "formation.attendance.write", "formation.grades.write"], None, 3, None),
    ]),
    ("ministerios", "Ministerios", 7, [
        ("responsable_ministerio", "Responsable de cada ministerio (Damas, Caballeros, Jóvenes, Parejas…)", "principal", "ministries", [], None, 3, "ministry"),
    ]),
    ("operacion", "Operación", 8, [
        ("recepcion", "Recepción", "principal", "team", ["operations.view", "operations.checkin"], None, 3, None),
        ("asistencia", "Asistencia", "principal", "team", ["operations.view", "operations.checkin", "operations.reports"], None, 3, None),
        ("comunicaciones", "Comunicaciones", "principal", "team", ["operations.view"], None, 3, None),
    ]),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def allowed_capabilities() -> set:
    return capability_catalog_keys() | set(FINANCE_CAPABILITIES) | {BOARD_ACCESS}


def require_team_viewer(current_user: dict = Depends(get_current_user)) -> dict:
    if not (is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)):
        raise HTTPException(status_code=403, detail="Equipo y Responsables: solo el pastor y el coordinador general")
    return current_user


def ensure_can_define(actor: dict, capabilities: list[str], privilege_group: Optional[str]) -> None:
    """El coordinador general no puede escalar: solo permisos que él ya tiene y nunca Finanzas o Junta."""
    invalid = sorted(set(capabilities) - allowed_capabilities())
    if invalid:
        raise HTTPException(status_code=422, detail=f"Permisos fuera del catálogo: {', '.join(invalid)}")
    if is_global_pastoral_authority(actor):
        return
    if privilege_group in SENSITIVE_GROUPS or set(capabilities) & (set(FINANCE_CAPABILITIES) | {BOARD_ACCESS}):
        raise HTTPException(status_code=403, detail="Los cargos de Finanzas y Junta los define solo el pastor")
    beyond = sorted(set(capabilities) - set(normalized_capabilities(actor)))
    if beyond:
        raise HTTPException(status_code=403, detail=f"Solo puede usar permisos que usted ya tiene: {', '.join(beyond)}")


async def log_event(actor: dict, action: str, entity: str, entity_id: str, before: Optional[dict], after: Optional[dict]) -> None:
    event_id = str(uuid4())
    await db.team_catalog_events.insert_one({"_id": event_id, "event_id": event_id, "action": action, "entity": entity, "entity_id": entity_id,
                                             "before": before, "after": after, "by_user_id": actor.get("user_id"), "at": _now()})


async def ensure_team_catalog() -> None:
    """Carga los cargos iniciales una sola vez (no pisa lo que el pastor ya cambió)."""
    await db.team_areas.create_index("area_id", unique=True)
    await db.team_areas.create_index("key", unique=True)
    await db.team_roles.create_index("role_id", unique=True)
    await db.team_roles.create_index("key", unique=True)
    await db.team_catalog_events.create_index([("entity_id", 1), ("at", -1)])
    now = _now()
    for area_key, area_name, order, roles in SEED:
        await db.team_areas.update_one({"key": area_key}, {"$setOnInsert": {"_id": area_key, "area_id": area_key, "key": area_key, "name": area_name, "order": order,
                                                                             "active": True, "seeded": True, "created_at": now}}, upsert=True)
        for index, (key, name, kind, source, caps, group, max_holders, per_unit) in enumerate(roles):
            await db.team_roles.update_one({"key": key}, {"$setOnInsert": {"_id": key, "role_id": key, "key": key, "area_id": area_key, "name": name, "kind": kind, "source": source,
                                                                            "capabilities": caps, "privilege_group": group, "max_holders": max_holders, "per_unit": per_unit,
                                                                            "order": index, "active": True, "seeded": True, "created_at": now}}, upsert=True)


def serialize(doc: dict) -> dict:
    return {key: (value.isoformat().replace("+00:00", "Z") if isinstance(value, datetime) else value) for key, value in doc.items() if key != "_id"}


@router.get("/catalog", response_model=dict)
async def catalog(current_user: dict = Depends(require_team_viewer)):
    areas = await db.team_areas.find({}, {"_id": 0}).sort("order", 1).to_list(200)
    roles = await db.team_roles.find({}, {"_id": 0}).sort([("area_id", 1), ("order", 1)]).to_list(1000)
    return {"areas": [{**serialize(area), "roles": [serialize(role) for role in roles if role["area_id"] == area["area_id"]]} for area in areas],
            "max_holders": MAX_HOLDERS, "can_define_sensitive": is_global_pastoral_authority(current_user)}


class AreaInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    order: Optional[int] = Field(default=None, ge=0, le=1000)
    active: Optional[bool] = None


@router.post("/areas", response_model=dict, status_code=201)
async def create_area(payload: AreaInput, current_user: dict = Depends(require_team_viewer)):
    area_id = f"area-{uuid4().hex[:10]}"
    order = payload.order if payload.order is not None else (await db.team_areas.count_documents({})) + 1
    doc = {"_id": area_id, "area_id": area_id, "key": area_id, "name": payload.name.strip(), "order": order, "active": True, "seeded": False,
           "created_by_user_id": current_user["user_id"], "created_at": _now()}
    await db.team_areas.insert_one(doc)
    await log_event(current_user, "area_created", "area", area_id, None, serialize(doc))
    return serialize(doc)


@router.put("/areas/{area_id}", response_model=dict)
async def update_area(area_id: str, payload: AreaInput, current_user: dict = Depends(require_team_viewer)):
    before = await db.team_areas.find_one({"area_id": area_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    changes = {"name": payload.name.strip(), **({"order": payload.order} if payload.order is not None else {}), **({"active": payload.active} if payload.active is not None else {}),
               "updated_at": _now(), "updated_by_user_id": current_user["user_id"]}
    await db.team_areas.update_one({"area_id": area_id}, {"$set": changes})
    after = await db.team_areas.find_one({"area_id": area_id}, {"_id": 0})
    await log_event(current_user, "area_updated", "area", area_id, serialize(before), serialize(after))
    return serialize(after)


class RoleInput(BaseModel):
    area_id: str
    name: str = Field(min_length=2, max_length=120)
    kind: Literal["principal", "asistente"] = "principal"
    max_holders: int = Field(default=MAX_HOLDERS, ge=1, le=MAX_HOLDERS)
    capabilities: list[str] = Field(default_factory=list, max_length=60)
    privilege_group: Optional[Literal["finance", "board"]] = None
    active: Optional[bool] = None


@router.post("/roles", response_model=dict, status_code=201)
async def create_role(payload: RoleInput, current_user: dict = Depends(require_team_viewer)):
    """Cargos nuevos siempre los guarda este módulo (fuente `team`)."""
    if not await db.team_areas.find_one({"area_id": payload.area_id, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Área no encontrada o desactivada")
    ensure_can_define(current_user, payload.capabilities, payload.privilege_group)
    role_id = f"cargo-{uuid4().hex[:10]}"
    order = await db.team_roles.count_documents({"area_id": payload.area_id})
    doc = {"_id": role_id, "role_id": role_id, "key": role_id, "area_id": payload.area_id, "name": payload.name.strip(), "kind": payload.kind, "source": "team",
           "capabilities": sorted(set(payload.capabilities)), "privilege_group": payload.privilege_group, "max_holders": payload.max_holders, "per_unit": None,
           "order": order, "active": True, "seeded": False, "created_by_user_id": current_user["user_id"], "created_at": _now()}
    await db.team_roles.insert_one(doc)
    await log_event(current_user, "role_created", "role", role_id, None, serialize(doc))
    return serialize(doc)


@router.put("/roles/{role_id}", response_model=dict)
async def update_role(role_id: str, payload: RoleInput, current_user: dict = Depends(require_team_viewer)):
    before = await db.team_roles.find_one({"role_id": role_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Cargo no encontrado")
    if before["area_id"] != payload.area_id and not await db.team_areas.find_one({"area_id": payload.area_id, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Área no encontrada o desactivada")
    # Los cargos que viven en otro módulo no cambian de permisos aquí (los da su módulo).
    capabilities = sorted(set(payload.capabilities)) if before["source"] == "team" else before.get("capabilities", [])
    group = payload.privilege_group if before["source"] == "team" else before.get("privilege_group")
    # Tocar un cargo de Finanzas/Junta (aunque solo sea el nombre) es solo del pastor.
    ensure_can_define(current_user, list(set(capabilities) | set(before.get("capabilities") or [])), group or before.get("privilege_group"))
    max_holders = payload.max_holders if before.get("max_holders") is not None else None
    changes = {"area_id": payload.area_id, "name": payload.name.strip(), "kind": payload.kind, "max_holders": max_holders, "capabilities": capabilities,
               "privilege_group": group, **({"active": payload.active} if payload.active is not None else {}), "updated_at": _now(), "updated_by_user_id": current_user["user_id"]}
    await db.team_roles.update_one({"role_id": role_id}, {"$set": changes})
    after = await db.team_roles.find_one({"role_id": role_id}, {"_id": 0})
    await log_event(current_user, "role_updated", "role", role_id, serialize(before), serialize(after))
    return serialize(after)


@router.get("/catalog/history", response_model=dict)
async def catalog_history(current_user: dict = Depends(require_team_viewer)):
    items = await db.team_catalog_events.find({}, {"_id": 0}).sort("at", -1).limit(200).to_list(200)
    return {"items": [serialize(item) for item in items]}
