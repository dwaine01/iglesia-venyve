"""ETAPA 5C-2 — Estructura por niveles y exploración de la rama.

Lee los mismos `front_groups` y `front_group_assignments` (sin copias): cada
nivel muestra su líder/colíder, sus personas y equipos, los grupos de los
líderes que salieron de él y los totales del grupo y de toda su rama.
Una persona que es integrante de un grupo y líder de otro se cuenta UNA sola
vez en los totales de la rama (conteo por person_id distinto).

Permisos (backend): pastora/pastor y coordinador general ven todo; un
líder/colíder ve su rama (su grupo y los descendientes); un integrante no
explora (solo ve nombre, líder y colíder en su portal)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from access_control import is_general_coordinator, is_global_pastoral_authority
from front_group_tree import descendant_group_ids, load_group, readable_group_ids
from front_groups import person_name, roster_view
from participation_scope import principal_authority_person_ids, without
from server import db, get_current_user

router = APIRouter(prefix="/api/front-group-structure", tags=["front-group-structure"])


async def explorable_ids(current_user: dict) -> Optional[set[str]]:
    """None = toda la estructura. Conjunto = solo esas ramas."""
    if is_global_pastoral_authority(current_user) or is_general_coordinator(current_user):
        return None
    return await readable_group_ids(db, current_user) or set()


async def assert_explorable(group_id: str, current_user: dict) -> dict:
    group = await load_group(db, group_id)
    allowed = await explorable_ids(current_user)
    if allowed is not None and group_id not in allowed:
        raise HTTPException(status_code=403, detail="Ese Grupo Frontal no está en su rama")
    return group


async def branch_totals(group_id: str) -> dict:
    """Totales de la rama completa sin contar dos veces a nadie."""
    branch_ids = await descendant_group_ids(db, group_id)
    authorities = await principal_authority_person_ids(db)
    # La autoridad pastoral principal supervisa: no cuenta como integrante ni líder operativo.
    people = without(await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": branch_ids}, "active": True}), authorities)
    pairs = await db.front_group_assignments.distinct("pair_id", {"front_group_id": {"$in": branch_ids}, "active": True, "role": "member", "pair_id": {"$ne": None}})
    leaders = without(await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": branch_ids}, "active": True, "role": {"$in": ["leader", "co_leader"]}}), authorities)
    complete_pairs = 0
    for pair_id in pairs:
        if await db.front_group_assignments.count_documents({"pair_id": pair_id, "active": True}) >= 2:
            complete_pairs += 1
    return {"groups": len(branch_ids), "people": len(people), "pairs": complete_pairs, "leaders": len(leaders)}


async def direct_totals(group_id: str) -> dict:
    members = await db.front_group_assignments.find({"front_group_id": group_id, "role": "member", "active": True}, {"_id": 0, "pair_id": 1}).to_list(5000)
    pair_counts: dict[str, int] = {}
    for item in members:
        if item.get("pair_id"):
            pair_counts[item["pair_id"]] = pair_counts.get(item["pair_id"], 0) + 1
    pairs = sum(1 for count in pair_counts.values() if count >= 2)
    return {"people": len(members), "pairs": pairs, "individuals": len(members) - pairs * 2}


async def group_card(group: dict) -> dict:
    return {
        "front_group_id": group["front_group_id"],
        "name": group.get("name") or (f"Equipo de {await person_name(group.get('primary_leader_person_id'))}" if group.get("primary_leader_person_id") else "Grupo sin nombre"),
        "status": group.get("status"),
        "pastoral_main": bool(group.get("pastoral_main")),
        "depth": group.get("depth", 0),
        "leader": {"person_id": group.get("primary_leader_person_id"), "name": await person_name(group.get("primary_leader_person_id"))} if group.get("primary_leader_person_id") else None,
        "co_leader": {"person_id": group.get("co_leader_person_id"), "name": await person_name(group.get("co_leader_person_id"))} if group.get("co_leader_person_id") else None,
        "direct": await direct_totals(group["front_group_id"]),
        "branch": await branch_totals(group["front_group_id"]),
        "children_count": await db.front_groups.count_documents({"parent_group_id": group["front_group_id"], "status": {"$ne": "archived"}}),
    }


@router.get("/start", response_model=dict)
async def structure_start(current_user: dict = Depends(get_current_user)):
    """Punto de entrada: la pastora/coordinador empiezan en el grupo de la
    pastora (o en los grupos raíz); el líder, en los grupos que lidera."""
    allowed = await explorable_ids(current_user)
    if allowed is None:
        main = await db.front_groups.find_one({"pastoral_main": True, "status": {"$ne": "archived"}}, {"_id": 0})
        roots = [main] if main else await db.front_groups.find({"parent_group_id": None, "status": {"$ne": "archived"}}, {"_id": 0}).sort("name", 1).to_list(100)
    else:
        led = await db.front_group_assignments.distinct("front_group_id", {"person_id": current_user.get("person_id"), "role": {"$in": ["leader", "co_leader"]}, "active": True})
        roots = await db.front_groups.find({"front_group_id": {"$in": [item for item in led if item in allowed]}, "status": {"$ne": "archived"}}, {"_id": 0}).sort("depth", 1).to_list(100)
        top_ids = {item["front_group_id"] for item in roots}
        # Si lidera un grupo y también uno de sus descendientes, se entra por el más alto.
        roots = [item for item in roots if not set(item.get("ancestor_group_ids") or []) & top_ids]
    return {"groups": [await group_card(group) for group in roots], "scope": "global" if allowed is None else "branch"}


@router.get("/groups/{group_id}", response_model=dict)
async def structure_node(group_id: str, current_user: dict = Depends(get_current_user)):
    """Un nivel de la estructura: el grupo, sus personas/equipos, los grupos
    hijos (de los líderes que salieron de él) y el camino para volver."""
    group = await assert_explorable(group_id, current_user)
    allowed = await explorable_ids(current_user)
    breadcrumbs = []
    for ancestor_id in group.get("ancestor_group_ids") or []:
        if allowed is not None and ancestor_id not in allowed:
            continue
        ancestor = await db.front_groups.find_one({"front_group_id": ancestor_id}, {"_id": 0})
        if ancestor:
            breadcrumbs.append({"front_group_id": ancestor_id, "name": ancestor.get("name") or "Grupo sin nombre"})
    parent = await db.front_groups.find_one({"front_group_id": group.get("parent_group_id")}, {"_id": 0, "front_group_id": 1, "name": 1, "pastoral_main": 1}) if group.get("parent_group_id") else None
    children = await db.front_groups.find({"parent_group_id": group_id, "status": {"$ne": "archived"}}, {"_id": 0}).sort([("rotation_order", 1), ("name", 1)]).to_list(500)
    return {
        "group": await group_card(group),
        "parent": {"front_group_id": parent["front_group_id"], "name": parent.get("name"), "pastoral_main": bool(parent.get("pastoral_main")), "explorable": allowed is None or parent["front_group_id"] in allowed} if parent else None,
        "breadcrumbs": breadcrumbs,
        "roster": await roster_view(group),
        "children": [await group_card(child) for child in children],
    }
