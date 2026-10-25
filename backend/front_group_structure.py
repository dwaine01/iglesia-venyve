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
from pydantic import BaseModel, Field

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


# ------------------------------------------------------------------ árbol «Mis ramas»
async def lead_group_ids(current_user: dict) -> set[str]:
    """Grupos donde la persona es Líder o Colíder activo."""
    if not current_user.get("person_id"):
        return set()
    return set(await db.front_group_assignments.distinct("front_group_id", {"person_id": current_user["person_id"], "role": {"$in": ["leader", "co_leader"]}, "active": True}))


async def leads_above(group: dict, current_user: dict) -> bool:
    """¿Lidera el grupo padre o algún grupo por encima de este?"""
    lineage = set(group.get("ancestor_group_ids") or [])
    return bool(lineage & await lead_group_ids(current_user))


def _is_admin(current_user: dict) -> bool:
    return is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)


@router.get("/tree", response_model=dict)
async def structure_tree(root: Optional[str] = None, period: str = "month", current_user: dict = Depends(get_current_user)):
    """«Mis ramas»: el árbol hacia ABAJO desde el grupo pedido (o el primero del
    usuario). Cada equipo (líder + colíder) muestra su grupo o «todavía no ha
    formado su grupo». Personas de cada rama sin contar dos veces; avance de la
    rama = mismo indicador del resumen del grupo. Nunca muestra ramas ajenas
    ni hacia arriba (solo el nombre de su líder directo)."""
    from front_group_stats import goal_indicators, load_thresholds, person_metrics, resolve_period
    if root:
        root_group = await assert_explorable(root, current_user)
    else:
        start = await structure_start(current_user)
        if not start["groups"]:
            return {"root": None, "scope": start["scope"], "my_team": await my_pending_team(current_user)}
        root_group = await load_group(db, start["groups"][0]["front_group_id"])
    root_id = root_group["front_group_id"]
    groups = await db.front_groups.find({"status": {"$ne": "archived"}, "$or": [{"front_group_id": root_id}, {"ancestor_group_ids": root_id}]}, {"_id": 0}).to_list(5000)
    by_id = {item["front_group_id"]: item for item in groups}
    assignments = await db.front_group_assignments.find({"front_group_id": {"$in": list(by_id)}, "active": True}, {"_id": 0}).to_list(50000)
    authorities = set(await principal_authority_person_ids(db))
    names = await person_names({item["person_id"] for item in assignments} | {item.get("primary_leader_person_id") for item in groups} | {item.get("co_leader_person_id") for item in groups})
    resolved, thresholds = await resolve_period(period if period in {"week", "month", "invasion", "all"} else "month", None), await load_thresholds()
    everyone = sorted({item["person_id"] for item in assignments} - authorities)
    metrics = await person_metrics(everyone, resolved) if everyone else {}
    viewer_leads = await lead_group_ids(current_user)
    admin = _is_admin(current_user)
    viewer = current_user.get("person_id")
    children_of: dict[str, list[dict]] = {}
    for item in groups:
        if item["front_group_id"] != root_id and item.get("parent_group_id") in by_id:
            children_of.setdefault(item["parent_group_id"], []).append(item)
    members_of: dict[str, list[dict]] = {}
    for item in assignments:
        members_of.setdefault(item["front_group_id"], []).append(item)

    def can_form_under(parent_id: str, team_ids: list[str]) -> bool:
        lineage = set((by_id[parent_id].get("ancestor_group_ids") or [])) | {parent_id}
        return admin or bool(lineage & viewer_leads) or (viewer in team_ids)

    def person(pid: Optional[str]) -> Optional[dict]:
        return {"person_id": pid, "name": names.get(pid) or "Persona sin nombre"} if pid else None

    def node(group: dict) -> dict:
        gid = group["front_group_id"]
        subtree = [gid] + [item["front_group_id"] for item in groups if gid in (item.get("ancestor_group_ids") or [])]
        branch_people = sorted({item["person_id"] for g in subtree for item in members_of.get(g, [])} - authorities)
        overall = goal_indicators(branch_people, metrics, thresholds, resolved)["overall_progress"] if branch_people else None
        progress = round(overall * 100) if overall is not None else None  # % como en el resumen del grupo
        members = sorted([item for item in members_of.get(gid, []) if item.get("role") == "member"], key=lambda item: (item.get("roster_order") is None, item.get("roster_order") or 0))
        entries, by_pair = [], {}
        for item in members:
            pair = item.get("pair_id")
            if pair and pair in by_pair:
                by_pair[pair]["ids"].append(item["person_id"]); continue
            entry = {"pair_id": pair, "ids": [item["person_id"]]}
            if pair: by_pair[pair] = entry
            entries.append(entry)
        children = children_of.get(gid, [])
        used: set[str] = set()
        teams, individuals = [], []
        for entry in entries:
            child = next((item for item in children if item["front_group_id"] not in used and (item.get("primary_leader_person_id") in entry["ids"] or item.get("co_leader_person_id") in entry["ids"])), None)
            if child:
                used.add(child["front_group_id"])
            if len(entry["ids"]) < 2 and not child:
                individuals.append(person(entry["ids"][0]))
                continue
            status = "formed" if child and child.get("status") != "pending_formation" else ("pending" if child else "not_designated")
            teams.append({"key": entry["pair_id"] or entry["ids"][0], "people": [person(pid) for pid in entry["ids"]],
                          "leader": person(child.get("primary_leader_person_id") if child else entry["ids"][0]),
                          "co_leader": person(child.get("co_leader_person_id") if child else (entry["ids"][1] if len(entry["ids"]) > 1 else None)),
                          "status": status, "group": node(child) if child and status == "formed" else None,
                          "pending_group_id": child["front_group_id"] if child and status == "pending" else None,
                          "can_form": status != "formed" and can_form_under(gid, entry["ids"] + ([child.get("primary_leader_person_id")] if child else []))})
        for child in children:  # grupos de líderes que no están en la lista (designados aparte)
            if child["front_group_id"] in used:
                continue
            status = "pending" if child.get("status") == "pending_formation" else "formed"
            ids = [pid for pid in (child.get("primary_leader_person_id"), child.get("co_leader_person_id")) if pid]
            teams.append({"key": child["front_group_id"], "people": [person(pid) for pid in ids], "leader": person(child.get("primary_leader_person_id")), "co_leader": person(child.get("co_leader_person_id")),
                          "status": status, "group": node(child) if status == "formed" else None, "pending_group_id": child["front_group_id"] if status == "pending" else None,
                          "can_form": status == "pending" and can_form_under(gid, ids)})
        return {"front_group_id": gid, "name": group.get("name") or (f"Grupo de {names.get(group.get('primary_leader_person_id'))}" if group.get("primary_leader_person_id") else "Grupo sin nombre"),
                "pastoral_main": bool(group.get("pastoral_main")), "leader": person(group.get("primary_leader_person_id")), "co_leader": person(group.get("co_leader_person_id")),
                "people_direct": len(members), "people_branch": len(branch_people), "teams": teams, "individuals": individuals,
                "teams_total": len(teams), "groups_formed": sum(1 for team in teams if team["status"] == "formed"), "progress": progress}

    tree = node(root_group)
    parent = by_id.get(root_group.get("parent_group_id")) or (await db.front_groups.find_one({"front_group_id": root_group.get("parent_group_id")}, {"_id": 0}) if root_group.get("parent_group_id") else None)
    leader_id = (parent or {}).get("primary_leader_person_id")
    direct_leader = {"person_id": leader_id, "name": (await person_names([leader_id])).get(leader_id) or "Por definir"} if leader_id else None
    return {"root": tree, "direct_leader": direct_leader, "period": {"key": resolved["key"], "label": resolved["label"]},
            "scope": "global" if admin else "branch", "can_see_work": True}


async def my_pending_team(current_user: dict) -> Optional[dict]:
    """Integrante de un equipo (líder + colíder) que todavía no ha formado su grupo."""
    pid = current_user.get("person_id")
    if not pid:
        return None
    mine = await db.front_group_assignments.find_one({"person_id": pid, "role": "member", "active": True, "pair_id": {"$ne": None}}, {"_id": 0}, sort=[("started_at", -1)])
    if not mine:
        return None
    pair = await db.front_group_assignments.find({"front_group_id": mine["front_group_id"], "pair_id": mine["pair_id"], "role": "member", "active": True}, {"_id": 0, "person_id": 1, "roster_order": 1}).to_list(5)
    pair.sort(key=lambda item: (item.get("roster_order") is None, item.get("roster_order") or 0))
    parent = await db.front_groups.find_one({"front_group_id": mine["front_group_id"]}, {"_id": 0, "name": 1, "primary_leader_person_id": 1})
    names = await person_names([item["person_id"] for item in pair] + [(parent or {}).get("primary_leader_person_id")])
    pending = await db.front_groups.find_one({"parent_group_id": mine["front_group_id"], "primary_leader_person_id": {"$in": [item["person_id"] for item in pair]}, "status": "pending_formation"}, {"_id": 0, "front_group_id": 1})
    return {"parent_group_id": mine["front_group_id"], "parent_name": (parent or {}).get("name"), "direct_leader": names.get((parent or {}).get("primary_leader_person_id")),
            "people": [{"person_id": item["person_id"], "name": names.get(item["person_id"]) or "Persona sin nombre"} for item in pair],
            "pending_group_id": (pending or {}).get("front_group_id")}


class FormInput(BaseModel):
    parent_group_id: str = Field(min_length=1, max_length=80)
    person_ids: list[str] = Field(min_length=1, max_length=2)


@router.post("/form", response_model=dict)
async def form_team_group(payload: FormInput, current_user: dict = Depends(get_current_user)):
    """«Formar grupo» de un equipo (líder + colíder) de la lista. Pueden: el propio
    líder del equipo, su líder superior, la pastora o el coordinador general.
    Reutiliza la designación (grupo pendiente) y devuelve el grupo para conformarlo."""
    from front_groups import DesignationCreate, designate
    parent = await load_group(db, payload.parent_group_id)
    for pid in payload.person_ids:
        if not await db.front_group_assignments.find_one({"front_group_id": parent["front_group_id"], "person_id": pid, "role": "member", "active": True}, {"_id": 1}):
            raise HTTPException(status_code=422, detail="Solo se forma el grupo de integrantes de este grupo")
    lineage = set(parent.get("ancestor_group_ids") or []) | {parent["front_group_id"]}
    if not (_is_admin(current_user) or lineage & await lead_group_ids(current_user) or current_user.get("person_id") in payload.person_ids):
        raise HTTPException(status_code=403, detail="Solo el líder del equipo, su líder superior, la pastora o el coordinador general")
    summary = await designate(parent["front_group_id"], DesignationCreate(leader_person_id=payload.person_ids[0], co_leader_person_id=payload.person_ids[1] if len(payload.person_ids) > 1 else None,
                                                                         reason="Formar grupo desde «Mis ramas»"), current_user)
    return {"front_group_id": summary.get("front_group_id"), "status": summary.get("status")}
