"""C11 (Etapa 4): migración de diagnóstico/aplicación — IDEMPOTENTE y NO
DESTRUCTIVA. El modo "diagnose" solo lee y reporta; el modo "apply" corrige
ÚNICAMENTE el caso seguro (expediente de invasión sin front_group_id cuando
el mentor tiene una única rama de supervisión activa), dejando constancia en
un registro propio (`migration_runs`). El resto de hallazgos (cuentas
duplicadas, cuentas sin Persona, grupos con líder sin cuenta o con más de un
líder activo) se reportan pero NO se tocan: requieren criterio pastoral.
NUNCA ejecutar "apply" contra producción sin revisión manual previa — ver
DEPLOYMENT.md."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from access_control import is_general_coordinator, is_global_pastoral_authority
from process_engine import now_utc, serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/admin/migrations/c11", tags=["admin-migrations"])


def require_pastoral(current_user: dict = Depends(get_current_user)) -> dict:
    if is_global_pastoral_authority(current_user) or is_general_coordinator(current_user):
        return current_user
    raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede ejecutar esta migración")


async def persons_with_multiple_accounts() -> list:
    rows = await db.users.aggregate([
        {"$match": {"person_id": {"$ne": None}}},
        {"$group": {"_id": "$person_id", "user_ids": {"$push": {"$toString": "$_id"}}, "total": {"$sum": 1}}},
        {"$match": {"total": {"$gt": 1}}},
    ]).to_list(500)
    return [{"person_id": row["_id"], "user_ids": row["user_ids"], "total": row["total"]} for row in rows]


async def accounts_without_person() -> list:
    users = await db.users.find({"person_id": {"$ne": None}}, {"_id": 1, "email": 1, "person_id": 1}).to_list(5000)
    person_ids = {str(p["_id"]) for p in await db.persons.find({}, {"_id": 1}).to_list(50000)}
    orphans = [u for u in users if u.get("person_id") not in person_ids]
    return [{"user_id": str(u["_id"]), "email": u.get("email"), "person_id": u.get("person_id")} for u in orphans]


async def groups_leader_issues() -> dict:
    groups = await db.front_groups.find({"status": {"$ne": "archived"}}, {"_id": 0, "front_group_id": 1, "name": 1, "primary_leader_person_id": 1}).to_list(5000)
    without_account, multiple_active = [], []
    for group in groups:
        leader_id = group.get("primary_leader_person_id")
        if leader_id and not await db.users.find_one({"person_id": leader_id, "is_active": {"$ne": False}}, {"_id": 1}):
            without_account.append({"front_group_id": group["front_group_id"], "name": group.get("name"), "leader_person_id": leader_id})
        active_leaders = await db.front_group_assignments.distinct("person_id", {"front_group_id": group["front_group_id"], "role": "leader", "active": True})
        if len(active_leaders) > 1:
            multiple_active.append({"front_group_id": group["front_group_id"], "name": group.get("name"), "active_leader_person_ids": active_leaders})
    return {"groups_leader_without_account": without_account, "groups_multiple_active_leaders": multiple_active}


async def enrollments_missing_front_group() -> list:
    """Propone front_group_id SOLO si el mentor tiene una única rama de
    supervisión activa (sin ambigüedad); si no, se reporta sin propuesta."""
    enrollments = await db.process_enrollments.find(
        {"source": "mentorship_outreach", "front_group_id": {"$in": [None, ""]}}, {"_id": 0, "enrollment_id": 1, "person_id": 1, "mentor_person_id": 1, "source_id": 1},
    ).to_list(5000)
    results = []
    for enrollment in enrollments:
        mentor_id = enrollment.get("mentor_person_id")
        proposed = None
        if mentor_id:
            own_groups = await db.front_group_assignments.distinct("front_group_id", {"person_id": mentor_id, "active": True})
            if len(own_groups) == 1:
                proposed = own_groups[0]
        results.append({"enrollment_id": enrollment["enrollment_id"], "person_id": enrollment["person_id"], "mentor_person_id": mentor_id, "proposed_front_group_id": proposed})
    return results


async def diagnose_c11() -> dict:
    duplicates = await persons_with_multiple_accounts()
    orphan_accounts = await accounts_without_person()
    leader_issues = await groups_leader_issues()
    missing_front_group = await enrollments_missing_front_group()
    applicable = [item for item in missing_front_group if item["proposed_front_group_id"]]
    return {
        "persons_with_multiple_accounts": duplicates, "accounts_without_person": orphan_accounts,
        **leader_issues, "enrollments_missing_front_group": missing_front_group,
        "summary": {
            "persons_with_multiple_accounts": len(duplicates), "accounts_without_person": len(orphan_accounts),
            "groups_leader_without_account": len(leader_issues["groups_leader_without_account"]), "groups_multiple_active_leaders": len(leader_issues["groups_multiple_active_leaders"]),
            "enrollments_missing_front_group": len(missing_front_group), "enrollments_auto_fixable": len(applicable),
        },
    }


async def apply_c11(actor_user_id: str) -> dict:
    """Idempotente: si ya tiene front_group_id, ya no entra en el filtro de
    diagnóstico, así que una segunda corrida no vuelve a tocar nada."""
    missing = await enrollments_missing_front_group()
    applied = []
    now = now_utc()
    for item in missing:
        if not item["proposed_front_group_id"]:
            continue
        await db.process_enrollments.update_one(
            {"enrollment_id": item["enrollment_id"], "front_group_id": {"$in": [None, ""]}},
            {"$set": {"front_group_id": item["proposed_front_group_id"], "updated_at": now}},
        )
        applied.append(item)
    run_id = str(uuid4())
    await db.migration_runs.insert_one({
        "_id": run_id, "migration": "c11", "mode": "apply", "actor_user_id": actor_user_id, "ran_at": now,
        "enrollments_fixed": len(applied), "detail": serialize(applied),
    })
    return {"run_id": run_id, "enrollments_fixed": len(applied), "items": serialize(applied)}


@router.get("", response_model=dict)
async def run_c11(mode: str = Query(default="diagnose", pattern="^(diagnose|apply)$"), current_user: dict = Depends(require_pastoral)):
    if mode == "diagnose":
        return await diagnose_c11()
    return await apply_c11(current_user["user_id"])


@router.get("/runs", response_model=dict)
async def list_c11_runs(current_user: dict = Depends(require_pastoral)):
    runs = await db.migration_runs.find({"migration": "c11"}, {"_id": 0}).sort("ran_at", -1).to_list(100)
    return {"items": serialize(runs)}
