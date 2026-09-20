"""Métricas operativas que agregan desde cada rama hacia sus ancestros."""
from fastapi import APIRouter, Depends, HTTPException

from access_control import FRONT_GROUPS_VIEW, has_capability, is_global_pastoral_authority
from front_group_tree import descendant_group_ids, group_in_scope, load_group
from process_engine import serialize
from server import db, get_current_user


router = APIRouter(prefix="/api/front-group-reports", tags=["front-group-reports"])


def require_read(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, FRONT_GROUPS_VIEW):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar reportes frontales")
    return current_user


async def metrics_for(group_ids: list[str]) -> dict:
    enrollment_query = {"front_group_id": {"$in": group_ids}, "process_key": "consolidation"}
    enrollments = await db.process_enrollments.find(enrollment_query, {"_id": 0, "enrollment_id": 1, "person_id": 1, "status": 1, "current_stage_key": 1}).to_list(50000)
    work = await db.front_group_work_assignments.find({"assigned_group_id": {"$in": group_ids}}, {"_id": 0, "work_id": 1, "status": 1, "active": 1, "due_at": 1}).to_list(50000)
    op72 = await db.op72_records.find({"front_group_id": {"$in": group_ids}}, {"_id": 0, "op72_id": 1, "person_id": 1, "status": 1, "window_status": 1}).to_list(50000)
    invasions = await db.evangelism_targets.find({"front_group_id": {"$in": group_ids}, "archived": {"$ne": True}}, {"_id": 0, "target_id": 1, "status": 1}).to_list(50000)
    membership_people = set(await db.front_group_assignments.distinct("person_id", {"front_group_id": {"$in": group_ids}, "active": True}))
    return {
        "groups": len(group_ids),
        "people": len(membership_people | {item["person_id"] for item in enrollments} | {item["person_id"] for item in op72}),
        "members": len(membership_people),
        "consolidation": {
            "total": len({item["enrollment_id"] for item in enrollments}),
            "active": sum(item.get("status") == "active" for item in enrollments),
            "paused": sum(item.get("status") == "paused" for item in enrollments),
            "completed": sum(item.get("status") == "completed" for item in enrollments),
        },
        "op72": {
            "total": len({item["op72_id"] for item in op72}),
            "active": sum(item.get("status") == "active" for item in op72),
            "window_open": sum(item.get("window_status") == "open" for item in op72),
        },
        "work": {
            "total": len({item["work_id"] for item in work}),
            "active": len({item["work_id"] for item in work if item.get("active") is True}),
            "completed": len({item["work_id"] for item in work if item.get("status") == "completed"}),
        },
        "invasions": {
            "targets": len({item["target_id"] for item in invasions}),
            "connected": sum(item.get("status") == "connected" for item in invasions),
            "follow_up": sum(item.get("status") == "follow_up" for item in invasions),
        },
    }


@router.get("/{group_id}", response_model=dict)
async def front_group_report(group_id: str, current_user: dict = Depends(require_read)):
    group = await load_group(db, group_id)
    if not await group_in_scope(db, group_id, current_user, leader_required=True):
        raise HTTPException(status_code=403, detail="Reporte fuera de su rama")
    subtree_ids = await descendant_group_ids(db, group_id)
    direct_children = await db.front_groups.find({"parent_group_id": group_id, "status": {"$ne": "archived"}}, {"_id": 0, "front_group_id": 1, "name": 1, "primary_leader_person_id": 1}).sort([("rotation_order", 1), ("name", 1)]).to_list(1000)
    branches = []
    for child in direct_children:
        child_ids = await descendant_group_ids(db, child["front_group_id"])
        branches.append({**child, "metrics": await metrics_for(child_ids)})
    ancestor_ids = group.get("ancestor_group_ids") or []
    ancestors = await db.front_groups.find({"front_group_id": {"$in": ancestor_ids}}, {"_id": 0, "front_group_id": 1, "name": 1, "depth": 1}).sort("depth", 1).to_list(1000) if ancestor_ids else []
    return serialize({
        "group": group,
        "lineage": [*ancestors, {"front_group_id": group["front_group_id"], "name": group["name"], "depth": group.get("depth", 0)}],
        "metrics": await metrics_for(subtree_ids),
        "direct_metrics": await metrics_for([group_id]),
        "branches": branches,
    })


async def ensure_front_group_report_indexes() -> None:
    await db.process_enrollments.create_index([("front_group_id", 1), ("process_key", 1), ("status", 1)])
    await db.evangelism_targets.create_index([("front_group_id", 1), ("status", 1)])