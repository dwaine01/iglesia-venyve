"""Equipo y Responsables · E4: cargos que viven en su propio módulo. Esta página NO guarda copia: lee y escribe
en el registro de cada módulo, con LAS MISMAS reglas y permisos de ese módulo (una sola fuente de verdad).

- Líder de Consolidación → `consolidation_lead_designations` (Encargados de Consolidación; solo el pastor).
- Mentores → `mentor_badges` (insignia; quien administra insignias; al quitarla se exige pasar su trabajo).
- Responsable de cada grupo → `front_groups` / `front_group_assignments` (líder y colíder; su alcance).
- Responsable de cada ministerio → `ministry_assignments` con función de liderazgo (Director/a, Líder, Coordinador/a).
- Pastor principal y coordinador general → cuentas (`users`): solo se ven; se cambian en Gestión de accesos."""
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException

from access_control import is_global_pastoral_authority
from server import db

MODULE_SOURCES = {"consolidation_leads", "mentorship", "front_groups", "ministries"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ lectura (de un vistazo)
async def module_holders(person_card) -> dict:
    """{role_key: [ {unit_id, unit_name, slot, person, ref_id} ] } y puestos pendientes por unidad."""
    from ministries import LEADERSHIP_NAMES
    out, pending = {}, []
    out["lider_consolidacion"] = [{"ref_id": doc["designation_id"], "person": await person_card(doc["person_id"])}
                                  async for doc in db.consolidation_lead_designations.find({"active": True}, {"_id": 0, "designation_id": 1, "person_id": 1})]
    out["mentor"] = [{"ref_id": doc["person_id"], "person": await person_card(doc["person_id"])}
                     async for doc in db.mentor_badges.find({"active": True}, {"_id": 0, "person_id": 1})]
    groups = []
    async for group in db.front_groups.find({"status": {"$ne": "archived"}}, {"_id": 0, "front_group_id": 1, "name": 1, "primary_leader_person_id": 1, "co_leader_person_id": 1}).sort("name", 1):
        row = {"unit_id": group["front_group_id"], "unit_name": group.get("name") or "Grupo",
               "leader": await person_card(group.get("primary_leader_person_id")), "co_leader": await person_card(group.get("co_leader_person_id"))}
        groups.append(row)
        if not row["leader"]:
            pending.append({"role_key": "responsable_grupo", "unit_id": row["unit_id"], "name": f"Líder de «{row['unit_name']}»"})
    out["responsable_grupo"] = groups
    leadership = {doc["_id"]: doc["nombre"] async for doc in db.ministry_roles.find({"normalized_name": {"$in": list(LEADERSHIP_NAMES)}}, {"nombre": 1})}
    ministries = []
    async for ministry in db.ministry_catalog.find({"activo": True}, {"nombre": 1}).sort("nombre", 1):
        holders = [{"ref_id": doc["_id"], "role_name": leadership.get(doc["role_id"]), "person": await person_card(doc["person_id"])}
                   async for doc in db.ministry_assignments.find({"ministry_id": ministry["_id"], "activo": True, "role_id": {"$in": list(leadership)}})]
        ministries.append({"unit_id": ministry["_id"], "unit_name": ministry.get("nombre") or "Ministerio", "holders": holders})
        if not holders:
            pending.append({"role_key": "responsable_ministerio", "unit_id": ministry["_id"], "name": f"Responsable de «{ministry.get('nombre')}»"})
    out["responsable_ministerio"] = ministries
    pastors, coordinators = [], []
    async for user in db.users.find({"is_active": {"$ne": False}, "$or": [{"rol": {"$in": ["pastor", "pastora"]}}, {"access_level": "coordinador_general"}]}, {"person_id": 1, "rol": 1, "access_level": 1}):
        card = await person_card(user.get("person_id"))
        if card:
            (pastors if user.get("rol") in ("pastor", "pastora") else coordinators).append({"ref_id": str(user["_id"]), "person": card, "read_only": True})
    out["pastor_principal"], out["coordinador_general"] = pastors, coordinators
    if not out["lider_consolidacion"]:
        pending.append({"role_key": "lider_consolidacion", "unit_id": None, "name": "Líder de Consolidación"})
    return {"holders": out, "pending": pending}


# ------------------------------------------------------------------ validación previa (sin escribir)
async def prevalidate(change, role: dict, actor: dict) -> None:
    """Mismos permisos que el módulo, antes de aplicar nada."""
    source = role["source"]
    if change.op == "replace":
        raise HTTPException(status_code=422, detail=f"En «{role['name']}» use quitar y asignar (o asignar, que reemplaza al líder del grupo)")
    if change.op == "assign" and change.person_id == actor.get("person_id"):
        raise HTTPException(status_code=403, detail="Nadie puede asignarse a sí mismo un cargo")
    if source == "consolidation_leads":
        if not is_global_pastoral_authority(actor):
            raise HTTPException(status_code=403, detail="Los encargados de Consolidación los designa solo el pastor")
        if change.op == "remove" and not await db.consolidation_lead_designations.find_one({"designation_id": change.assignment_id, "active": True}, {"_id": 1}):
            raise HTTPException(status_code=404, detail="Esa designación no está activa")
    elif source == "mentorship":
        from mentorship import can_manage_badges
        if not can_manage_badges(actor):
            raise HTTPException(status_code=403, detail="Sin permiso para administrar la insignia de Mentor")
    elif source == "front_groups":
        if change.op != "assign" or not change.unit_id or change.slot not in ("leader", "co_leader"):
            raise HTTPException(status_code=422, detail="Indique el grupo y si es líder o colíder (para quitarlo, use Grupo Frontal)")
        from front_groups import assert_group_scope, require_manage
        await require_manage(actor)
        await assert_group_scope(change.unit_id, actor, leader_required=True)
        if change.slot == "leader" and not await db.users.find_one({"person_id": change.person_id, "is_active": {"$ne": False}}, {"_id": 1}):
            raise HTTPException(status_code=409, detail="El líder principal necesita una cuenta activa en Plataforma 360")
    elif source == "ministries":
        from access_control import PERSON_MINISTRIES_WRITE
        from ministries import authorize_person_ministry
        if change.op == "assign":
            if not change.unit_id or not await db.ministry_catalog.find_one({"_id": change.unit_id, "activo": True}, {"_id": 1}):
                raise HTTPException(status_code=404, detail="Ministerio no encontrado")
            await authorize_person_ministry(change.person_id, actor, PERSON_MINISTRIES_WRITE)
        else:
            assignment = await db.ministry_assignments.find_one({"_id": change.assignment_id, "activo": True}, {"person_id": 1})
            if not assignment:
                raise HTTPException(status_code=404, detail="Esa asignación ministerial no está activa")
            await authorize_person_ministry(assignment["person_id"], actor, PERSON_MINISTRIES_WRITE)


# ------------------------------------------------------------------ aplicar (en el módulo)
async def leadership_role_id() -> str:
    """La función «Líder» de Ministerios (la crea una vez si no existe; es de liderazgo para Ministerios)."""
    role = await db.ministry_roles.find_one({"normalized_name": "líder", "activo": True}, {"_id": 1})
    if role:
        return role["_id"]
    role_id = str(uuid4())
    await db.ministry_roles.insert_one({"_id": role_id, "nombre": "Líder", "normalized_name": "líder", "ministry_id": None, "activo": True, "created_by": "team", "created_at": _now()})
    return role_id


async def apply(change, role: dict, actor: dict) -> dict:
    source, reason = role["source"], (change.reason or "").strip() or "Equipo y Responsables"
    if source == "consolidation_leads":
        from consolidation_leads import LeadCreate, designate_lead, remove_lead
        if change.op == "assign":
            result = await designate_lead(LeadCreate(person_id=change.person_id), actor)
            return {"ref_id": result.get("designation_id")}
        await remove_lead(change.assignment_id, actor)
        return {"ref_id": change.assignment_id}
    if source == "mentorship":
        from mentorship import MentorBadgeInput, set_mentor_badge
        person_id = change.person_id if change.op == "assign" else change.assignment_id
        await set_mentor_badge(person_id, MentorBadgeInput(active=change.op == "assign", note=reason, reassign_to_person_id=change.reassign_to_person_id), actor)
        return {"ref_id": person_id}
    if source == "front_groups":
        from front_groups import CoLeaderAssignment, LeaderAssignment, assign_co_leader, assign_primary_leader
        if change.slot == "leader":
            result = await assign_primary_leader(change.unit_id, LeaderAssignment(person_id=change.person_id, reason=reason), actor)
        else:
            result = await assign_co_leader(change.unit_id, CoLeaderAssignment(person_id=change.person_id, reason=reason), actor)
        return {"ref_id": result.get("assignment_id")}
    if source == "ministries":
        from ministries import AssignmentPayload, AssignmentUpdate, add_person_assignment, update_assignment
        today = datetime.now(timezone.utc).date().isoformat()
        if change.op == "assign":
            result = await add_person_assignment(change.person_id, AssignmentPayload(person_id=change.person_id, ministry_id=change.unit_id, role_id=await leadership_role_id(), fecha_inicio=today), actor)
            return {"ref_id": result.get("assignment_id")}
        await update_assignment(change.assignment_id, AssignmentUpdate(activo=False, fecha_fin=today), actor)
        return {"ref_id": change.assignment_id}
    raise HTTPException(status_code=409, detail="Cargo sin módulo")


def ref_person(change) -> Optional[str]:
    return change.person_id
