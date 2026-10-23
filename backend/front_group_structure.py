"""ETAPA 5C-2 — Estructura por niveles y exploración de la rama.

Lee los mismos `front_groups` y `front_group_assignments` (sin copias): cada
nivel muestra su líder/colíder, sus personas y equipos, los grupos de los
líderes que salieron de él y los totales del grupo y de toda su rama.
Una persona que es integrante de un grupo y líder de otro se cuenta UNA sola
vez en los totales de la rama (conteo por person_id distinto).

Permisos (backend): pastora/pastor y coordinador general ven todo; un
líder/colíder ve su rama (su grupo y los descendientes); un integrante no
explora (solo ve nombre, líder y colíder en su portal)."""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from access_control import is_general_coordinator, is_global_pastoral_authority
from front_group_tree import descendant_group_ids, load_group, readable_group_ids
from front_groups import person_names, roster_view
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


async def branch_totals(group_id: str, authorities: Optional[set[str]] = None) -> dict:
    """Totales de la rama completa sin contar dos veces a nadie."""
    branch_ids = await descendant_group_ids(db, group_id)
    if authorities is None:
        authorities = await principal_authority_person_ids(db)
    # La autoridad pastoral principal supervisa: no cuenta como integrante ni líder operativo.
    active_in_branch = {"front_group_id": {"$in": branch_ids}, "active": True}
    people, pairs, leaders = await asyncio.gather(
        db.front_group_assignments.distinct("person_id", active_in_branch),
        db.front_group_assignments.distinct("pair_id", {**active_in_branch, "role": "member", "pair_id": {"$ne": None}}),
        db.front_group_assignments.distinct("person_id", {**active_in_branch, "role": {"$in": ["leader", "co_leader"]}}),
    )
    people, leaders = without(people, authorities), without(leaders, authorities)
    complete_pairs = 0
    if pairs:
        # Un equipo está completo con 2+ asignaciones activas (en cualquier grupo, como antes).
        sizes = await db.front_group_assignments.aggregate([
            {"$match": {"pair_id": {"$in": pairs}, "active": True}},
            {"$group": {"_id": "$pair_id", "count": {"$sum": 1}}},
        ]).to_list(None)
        complete_pairs = sum(1 for item in sizes if item["count"] >= 2)
    return {"groups": len(branch_ids), "people": len(people), "pairs": complete_pairs, "leaders": len(leaders)}


async def direct_totals(group_id: str) -> dict:
    members = await db.front_group_assignments.find({"front_group_id": group_id, "role": "member", "active": True}, {"_id": 0, "pair_id": 1}).to_list(5000)
    pair_counts: dict[str, int] = {}
    for item in members:
        if item.get("pair_id"):
            pair_counts[item["pair_id"]] = pair_counts.get(item["pair_id"], 0) + 1
    pairs = sum(1 for count in pair_counts.values() if count >= 2)
    return {"people": len(members), "pairs": pairs, "individuals": len(members) - pairs * 2}


async def group_card(group: dict, authorities: Optional[set[str]] = None) -> dict:
    if authorities is None:
        authorities = await principal_authority_person_ids(db)
    leader_id, co_leader_id = group.get("primary_leader_person_id"), group.get("co_leader_person_id")
    names, direct, branch, children_count = await asyncio.gather(
        person_names([leader_id, co_leader_id]),
        direct_totals(group["front_group_id"]),
        branch_totals(group["front_group_id"], authorities),
        db.front_groups.count_documents({"parent_group_id": group["front_group_id"], "status": {"$ne": "archived"}}),
    )
    return {
        "front_group_id": group["front_group_id"],
        "name": group.get("name") or (f"Equipo de {names.get(leader_id)}" if leader_id else "Grupo sin nombre"),
        "status": group.get("status"),
        "pastoral_main": bool(group.get("pastoral_main")),
        "depth": group.get("depth", 0),
        "leader": {"person_id": leader_id, "name": names.get(leader_id)} if leader_id else None,
        "co_leader": {"person_id": co_leader_id, "name": names.get(co_leader_id)} if co_leader_id else None,
        "direct": direct,
        "branch": branch,
        "children_count": children_count,
    }


async def group_cards(groups: list[dict]) -> list[dict]:
    authorities = await principal_authority_person_ids(db)
    return list(await asyncio.gather(*(group_card(group, authorities) for group in groups)))


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
    return {"groups": await group_cards(roots), "scope": "global" if allowed is None else "branch"}


@router.get("/groups/{group_id}", response_model=dict)
async def structure_node(group_id: str, current_user: dict = Depends(get_current_user)):
    """Un nivel de la estructura: el grupo, sus personas/equipos, los grupos
    hijos (de los líderes que salieron de él) y el camino para volver."""
    group = await assert_explorable(group_id, current_user)
    allowed = await explorable_ids(current_user)
    visible_ancestors = [item for item in group.get("ancestor_group_ids") or [] if allowed is None or item in allowed]
    ancestors = {item["front_group_id"]: item async for item in db.front_groups.find({"front_group_id": {"$in": visible_ancestors}}, {"_id": 0, "front_group_id": 1, "name": 1})}
    breadcrumbs = [{"front_group_id": ancestor_id, "name": ancestors[ancestor_id].get("name") or "Grupo sin nombre"} for ancestor_id in visible_ancestors if ancestor_id in ancestors]
    parent = await db.front_groups.find_one({"front_group_id": group.get("parent_group_id")}, {"_id": 0, "front_group_id": 1, "name": 1, "pastoral_main": 1}) if group.get("parent_group_id") else None
    children = await db.front_groups.find({"parent_group_id": group_id, "status": {"$ne": "archived"}}, {"_id": 0}).sort([("rotation_order", 1), ("name", 1)]).to_list(500)
    cards, roster = await asyncio.gather(group_cards([group, *children]), roster_view(group))
    return {
        "group": cards[0],
        "parent": {"front_group_id": parent["front_group_id"], "name": parent.get("name"), "pastoral_main": bool(parent.get("pastoral_main")), "explorable": allowed is None or parent["front_group_id"] in allowed} if parent else None,
        "breadcrumbs": breadcrumbs,
        "roster": roster,
        "children": cards[1:],
    }
