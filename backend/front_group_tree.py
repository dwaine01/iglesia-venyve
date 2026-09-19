"""Servicios de árbol y alcance para Grupos Frontales recursivos."""
from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo import UpdateOne

from access_control import FRONT_GROUPS_MANAGE, has_capability, is_global_pastoral_authority


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def active_group_query(base: dict | None = None) -> dict:
    query = dict(base or {})
    query["status"] = {"$ne": "archived"}
    return query


async def load_group(db, group_id: str, include_archived: bool = False) -> dict:
    query = {"front_group_id": group_id}
    if not include_archived:
        query["status"] = {"$ne": "archived"}
    group = await db.front_groups.find_one(query, {"_id": 0})
    if not group:
        raise HTTPException(status_code=404, detail="Grupo Frontal no encontrado")
    return group


async def descendant_group_ids(db, group_id: str, include_self: bool = True) -> list[str]:
    query = {
        "status": {"$ne": "archived"},
        "$or": [{"front_group_id": group_id}, {"ancestor_group_ids": group_id}],
    }
    ids = await db.front_groups.distinct("front_group_id", query)
    if not include_self:
        ids = [item for item in ids if item != group_id]
    return ids


async def direct_assignments(db, person_id: str | None) -> list[dict]:
    if not person_id:
        return []
    assignments = await db.front_group_assignments.find(
        {"person_id": person_id, "active": True}, {"_id": 0}
    ).to_list(2000)
    if not assignments:
        return []
    active_ids = set(await db.front_groups.distinct("front_group_id", {
        "front_group_id": {"$in": [item["front_group_id"] for item in assignments]},
        "status": {"$ne": "archived"},
    }))
    return [item for item in assignments if item["front_group_id"] in active_ids]


async def readable_group_ids(db, current_user: dict) -> set[str] | None:
    if is_global_pastoral_authority(current_user):
        return None
    assignments = await direct_assignments(db, current_user.get("person_id"))
    readable = {item["front_group_id"] for item in assignments}
    leader_roots = {item["front_group_id"] for item in assignments if item.get("role") == "leader"}
    for root_id in leader_roots:
        readable.update(await descendant_group_ids(db, root_id))
    return readable


async def led_subtree_group_ids(db, current_user: dict) -> set[str] | None:
    if is_global_pastoral_authority(current_user):
        return None
    assignments = await direct_assignments(db, current_user.get("person_id"))
    led: set[str] = set()
    for assignment in assignments:
        if assignment.get("role") == "leader":
            led.update(await descendant_group_ids(db, assignment["front_group_id"]))
    return led


async def manageable_group_ids(db, current_user: dict) -> set[str] | None:
    if is_global_pastoral_authority(current_user):
        return None
    if not has_capability(current_user, FRONT_GROUPS_MANAGE):
        return set()
    return await led_subtree_group_ids(db, current_user)


async def group_in_scope(db, group_id: str, current_user: dict, leader_required: bool = False) -> bool:
    allowed = await (led_subtree_group_ids(db, current_user) if leader_required else readable_group_ids(db, current_user))
    return allowed is None or group_id in allowed


async def lineage_for_parent(db, group_id: str, parent_group_id: str | None) -> dict:
    if not parent_group_id:
        return {"parent_group_id": None, "root_group_id": group_id, "ancestor_group_ids": [], "depth": 0}
    parent = await load_group(db, parent_group_id)
    return {
        "parent_group_id": parent_group_id,
        "root_group_id": parent.get("root_group_id") or parent_group_id,
        "ancestor_group_ids": [*(parent.get("ancestor_group_ids") or []), parent_group_id],
        "depth": len(parent.get("ancestor_group_ids") or []) + 1,
    }


async def move_subtree(db, group_id: str, parent_group_id: str | None, actor_user_id: str) -> dict:
    group = await load_group(db, group_id)
    if parent_group_id == group_id:
        raise HTTPException(status_code=409, detail="Un Grupo Frontal no puede ser su propio padre")
    if parent_group_id:
        parent = await load_group(db, parent_group_id)
        if group_id in (parent.get("ancestor_group_ids") or []):
            raise HTTPException(status_code=409, detail="El movimiento crearía un ciclo en el árbol")
    lineage = await lineage_for_parent(db, group_id, parent_group_id)
    descendants = await db.front_groups.find(
        {"ancestor_group_ids": group_id, "status": {"$ne": "archived"}}, {"_id": 0}
    ).sort("depth", 1).to_list(10000)
    now = now_utc()
    operations = [UpdateOne(
        {"front_group_id": group_id},
        {"$set": {**lineage, "updated_at": now, "updated_by_user_id": actor_user_id}, "$inc": {"tree_version": 1}},
    )]
    for descendant in descendants:
        old_ancestors = descendant.get("ancestor_group_ids") or []
        suffix = old_ancestors[old_ancestors.index(group_id) + 1:] if group_id in old_ancestors else []
        ancestors = [*lineage["ancestor_group_ids"], group_id, *suffix]
        operations.append(UpdateOne(
            {"front_group_id": descendant["front_group_id"]},
            {"$set": {
                "root_group_id": lineage["root_group_id"],
                "ancestor_group_ids": ancestors,
                "depth": len(ancestors),
                "updated_at": now,
                "updated_by_user_id": actor_user_id,
            }, "$inc": {"tree_version": 1}},
        ))
    await db.front_groups.bulk_write(operations, ordered=True)
    return await load_group(db, group_id)


def build_tree(groups: list[dict]) -> list[dict]:
    nodes = {item["front_group_id"]: {**item, "children": []} for item in groups}
    roots = []
    for node in nodes.values():
        parent = nodes.get(node.get("parent_group_id"))
        if parent:
            parent["children"].append(node)
        else:
            roots.append(node)
    def sort_branch(items: list[dict]) -> None:
        items.sort(key=lambda item: ((item.get("rotation_order") or 0), (item.get("name") or "").lower()))
        for item in items:
            sort_branch(item["children"])
    sort_branch(roots)
    return roots