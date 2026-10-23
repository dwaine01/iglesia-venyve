"""ETAPA 5A — portal base por permisos asignados.
"Mi perfil" y "Mis estadísticas" son las DOS cosas que toda cuenta tiene
siempre, independientes de qué módulos le hayan asignado (pertenecer a un
grupo, tener un cargo y recibir permisos son cosas independientes). Ambos
endpoints solo exigen sesión válida: nunca exigen una capability, porque es
información sobre uno mismo, no un módulo que se conceda. No duplica datos:
lee directamente de las mismas colecciones que ya usan Persona 360, Grupos
Frontales y Supervisión (sin reportes paralelos)."""
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from core_person import db, serialize_person
from person_domains import address_items, contact_items
from server import get_current_user
from supervision_analytics import Filters, overview as supervision_overview

router = APIRouter(prefix="/api/core/me", tags=["self-portal"])


async def _own_person(current_user: dict) -> dict:
    person_id = current_user.get("person_id")
    if not person_id or not ObjectId.is_valid(person_id):
        raise HTTPException(status_code=404, detail="Esta cuenta no está vinculada a un Perfil 360")
    doc = await db.persons.find_one({"_id": ObjectId(person_id), "is_archived": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Perfil 360 no encontrado")
    return doc


@router.get("/profile", response_model=dict)
async def my_profile(current_user: dict = Depends(get_current_user)):
    doc = await _own_person(current_user)
    person = serialize_person(doc)
    person_id = person["person_id"]
    contacts = await contact_items(person_id)
    addresses = await address_items(person_id)
    ministries_docs = await db.ministry_assignments.find({"person_id": person_id, "activo": True}, {"_id": 0, "ministry_id": 1, "role": 1}).to_list(50)
    ministry_ids = [item["ministry_id"] for item in ministries_docs if item.get("ministry_id")]
    ministry_names = {}
    if ministry_ids:
        catalog_ids = [ObjectId(mid) for mid in ministry_ids if ObjectId.is_valid(mid)]
        async for catalog in db.ministry_catalog.find({"_id": {"$in": catalog_ids}}, {"nombre": 1}):
            ministry_names[str(catalog["_id"])] = catalog.get("nombre")
    ministries = [{"ministry_id": item["ministry_id"], "nombre": ministry_names.get(item["ministry_id"], "Ministerio"), "rol": item.get("role")} for item in ministries_docs]
    memberships = await db.front_group_assignments.find({"person_id": person_id, "active": True}, {"_id": 0, "front_group_id": 1, "role": 1}).to_list(20)
    groups = []
    for membership in memberships:
        group = await db.front_groups.find_one({"front_group_id": membership["front_group_id"]}, {"_id": 0, "front_group_id": 1, "name": 1})
        if not group:
            continue
        leader = await db.front_group_assignments.find_one({"front_group_id": membership["front_group_id"], "role": "leader", "active": True}, {"_id": 0, "person_id": 1})
        co_leader = await db.front_group_assignments.find_one({"front_group_id": membership["front_group_id"], "role": "co_leader", "active": True}, {"_id": 0, "person_id": 1})
        leader_name = None
        co_leader_name = None
        if leader and leader.get("person_id") and ObjectId.is_valid(leader["person_id"]):
            leader_doc = await db.persons.find_one({"_id": ObjectId(leader["person_id"])}, {"nombre": 1, "apellido": 1})
            leader_name = f"{leader_doc.get('nombre','')} {leader_doc.get('apellido','')}".strip() if leader_doc else None
        if co_leader and co_leader.get("person_id") and ObjectId.is_valid(co_leader["person_id"]):
            co_leader_doc = await db.persons.find_one({"_id": ObjectId(co_leader["person_id"])}, {"nombre": 1, "apellido": 1})
            co_leader_name = f"{co_leader_doc.get('nombre','')} {co_leader_doc.get('apellido','')}".strip() if co_leader_doc else None
        groups.append({
            "front_group_id": group["front_group_id"],
            "name": group.get("name"),
            "my_role": membership.get("role"),
            "leader_name": leader_name,
            "co_leader_name": co_leader_name,
        })
    mentor_badge = await db.mentor_badges.find_one({"person_id": person_id}, {"_id": 0, "active": 1, "since": 1})
    linked_user = await db.users.find_one({"person_id": person_id}, {"access_title": 1, "access_level": 1, "rol": 1})
    return {
        "person": person,
        "contacts": contacts,
        "addresses": addresses,
        "ministries": ministries,
        "front_groups": groups,
        "mentor_badge": {"active": bool(mentor_badge and mentor_badge.get("active")), "since": mentor_badge.get("since") if mentor_badge else None},
        "account": {
            "rol": (linked_user or {}).get("rol"),
            "access_level": (linked_user or {}).get("access_level"),
            "access_title": (linked_user or {}).get("access_title"),
        },
    }


@router.get("/stats", response_model=dict)
async def my_stats(current_user: dict = Depends(get_current_user)):
    """Resultados del propio trabajo (como mentor y/o como líder). Reutiliza
    exactamente la misma agregación de Supervisión, solo que el alcance
    siempre queda forzado a 'uno mismo', sin importar el cargo o permisos."""
    person_id = current_user.get("person_id")
    if not person_id:
        return {"as_mentor": None, "as_leader": None, "has_any_activity": False}
    self_ctx = {"scope": {"level": "self", "group_ids": None, "self_person_id": person_id}, "filters": Filters(), "mentor_ids": [person_id]}
    as_mentor = await supervision_overview(ctx=self_ctx)
    led_group_ids = await db.front_group_assignments.distinct("front_group_id", {"person_id": person_id, "role": {"$in": ["leader", "co_leader"]}, "active": True})
    as_leader = None
    if led_group_ids:
        from front_group_tree import descendant_group_ids
        all_branch_ids: set[str] = set()
        for group_id in led_group_ids:
            all_branch_ids.update(await descendant_group_ids(db, group_id))
        branch_mentor_ids = await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": sorted(all_branch_ids)}, "active": True})
        branch_ctx = {"scope": {"level": "branch", "group_ids": sorted(all_branch_ids), "self_person_id": person_id}, "filters": Filters(), "mentor_ids": branch_mentor_ids or None}
        as_leader = await supervision_overview(ctx=branch_ctx)
        as_leader["led_group_count"] = len(led_group_ids)
    has_activity = bool(
        as_mentor["invasion"]["visits_total"] or as_mentor["consolidation"]["accepted"]
        or (as_leader and (as_leader["invasion"]["visits_total"] or as_leader["consolidation"]["accepted"]))
    )
    return {"as_mentor": as_mentor, "as_leader": as_leader, "has_any_activity": has_activity}
