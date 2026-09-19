"""Migración explícita y no destructiva de residuos QA de Grupos Frontales."""
from datetime import datetime, timezone
from uuid import uuid4


APPROVED_QA_GROUP_IDS = [
    "3f39f97c-6f3f-42c6-ac4e-efc52c715396", "5b00d1e3-cf6d-4d21-8560-1b76bcc9805f",
    "9b15937a-bdc9-4c2f-8f2a-7651fb7991d7", "a3eacd0c-dddf-411d-b1de-b4b6dda02772",
    "a69694a4-d70a-41d6-85b2-f1820b9585a0", "aa5733c4-75b0-4a37-aaf6-74e8d44236db",
    "ac022607-d519-47b7-8bef-660b36c9898a", "b5ecb49b-6dc3-483a-a6a2-6f5bb0e715b6",
    "c3f3b8e0-2180-4100-8ede-809f8d848926", "e2dd2428-cd4f-47ea-ab3b-94671436393a",
    "e70de771-61a8-426e-a83c-1623ea44b96e", "1cb6c29b-0a4f-4d9c-b91a-1aa624a5c688",
    "5cd7cfe4-166f-4c3b-afbb-7a148fab25cf", "c7f6cb6e-1ec5-4307-a7e1-fe37ca8a1115",
    "d327ede2-0c80-4bab-84dd-a48d93582631", "d88695d6-636a-4d8e-8506-8dd831b48b25",
    "e13797a8-7d77-408b-b780-149568fbdc44", "e2c05220-880d-48f7-9612-b66b30922186",
    "f19f57cf-6ccf-4671-b8ad-90de29902e36", "ff547dbc-3fb9-4c03-aa55-258f5cab5758",
]
MIGRATION_KEY = "front_groups_phase0_qa_archive_v1"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def diagnose_approved_qa_groups(db) -> dict:
    groups = await db.front_groups.find(
        {"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}}, {"_id": 0}
    ).sort("name", 1).to_list(100)
    found_ids = {item["front_group_id"] for item in groups}
    unexpected = [item["front_group_id"] for item in groups if not str(item.get("name") or "").startswith("QA Grupo ")]
    dependency_collections = {
        "process_enrollments": "front_group_id",
        "op72_records": "front_group_id",
        "evangelism_targets": "front_group_id",
        "cells": "front_group_id",
        "person_memberships": "front_group_id",
    }
    blocking_dependencies = {}
    for collection, field in dependency_collections.items():
        count = await db[collection].count_documents({field: {"$in": APPROVED_QA_GROUP_IDS}})
        if count:
            blocking_dependencies[collection] = count
    return {
        "migration_key": MIGRATION_KEY,
        "writes_performed": False,
        "expected_group_count": len(APPROVED_QA_GROUP_IDS),
        "found_group_count": len(groups),
        "missing_group_ids": sorted(set(APPROVED_QA_GROUP_IDS) - found_ids),
        "unexpected_name_group_ids": unexpected,
        "blocking_dependencies": blocking_dependencies,
        "groups": groups,
        "related": {
            "front_group_assignments": await db.front_group_assignments.count_documents({"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}}),
            "mentor_qualifications": await db.mentor_qualifications.count_documents({"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}}),
            "mentor_assignments": await db.mentor_assignments.count_documents({"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}}),
            "mentor_evaluations": await db.mentor_evaluations.count_documents({"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}}),
            "person_leadership_status": await db.person_leadership_status.count_documents({"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}}),
            "leadership_promotions": await db.leadership_promotions.count_documents({"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}}),
        },
    }


async def archive_approved_qa_groups(db, actor_user_id: str) -> dict:
    previous = await db.core_migrations.find_one({"migration_key": MIGRATION_KEY}, {"_id": 0})
    if previous:
        return {**previous.get("result", {}), "already_applied": True}
    diagnosis = await diagnose_approved_qa_groups(db)
    if diagnosis["unexpected_name_group_ids"] or diagnosis["blocking_dependencies"]:
        raise RuntimeError("El diagnóstico encontró datos no aprobados o dependencias operativas; no se archivó nada")
    now = now_utc(); reason = "Archivado QA aprobado por usuario en Fase 0"
    group_result = await db.front_groups.update_many(
        {"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}, "status": {"$ne": "archived"}},
        {"$set": {"status": "archived", "qa_artifact": True, "archived_at": now, "archived_by_user_id": actor_user_id, "archive_reason": reason, "updated_at": now}},
    )
    assignment_result = await db.front_group_assignments.update_many(
        {"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}, "active": True},
        {"$set": {"active": False, "archived": True, "ended_at": now, "ended_by_user_id": actor_user_id, "end_reason": reason}},
    )
    qualification_result = await db.mentor_qualifications.update_many(
        {"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}, "active": True},
        {"$set": {"active": False, "archived": True, "archived_at": now, "archive_reason": reason, "updated_at": now}},
    )
    mentor_result = await db.mentor_assignments.update_many(
        {"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}, "active": True},
        {"$set": {"active": False, "archived": True, "ended_at": now, "ended_by_user_id": actor_user_id, "end_reason": reason}},
    )
    leadership_result = await db.person_leadership_status.update_many(
        {"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}, "status": "leader"},
        {"$set": {"status": "archived", "archived": True, "archived_at": now, "archive_reason": reason, "updated_at": now}},
    )
    promotion_result = await db.leadership_promotions.update_many(
        {"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}},
        {"$set": {"archived": True, "archived_at": now, "archive_reason": reason}},
    )
    evaluation_result = await db.mentor_evaluations.update_many(
        {"front_group_id": {"$in": APPROVED_QA_GROUP_IDS}},
        {"$set": {"archived": True, "archived_at": now, "archive_reason": reason}},
    )
    audit_events = [{
        "_id": str(uuid4()), "event_id": str(uuid4()), "front_group_id": group_id,
        "action": "qa_group_archived", "actor_user_id": actor_user_id,
        "reason": reason, "occurred_at": now,
    } for group_id in APPROVED_QA_GROUP_IDS]
    if audit_events:
        await db.front_group_audit_events.insert_many(audit_events)
    result = {
        "migration_key": MIGRATION_KEY,
        "already_applied": False,
        "archived_groups": group_result.modified_count,
        "deactivated_assignments": assignment_result.modified_count,
        "deactivated_qualifications": qualification_result.modified_count,
        "deactivated_mentor_assignments": mentor_result.modified_count,
        "archived_leadership_statuses": leadership_result.modified_count,
        "archived_promotions": promotion_result.modified_count,
        "archived_mentor_evaluations": evaluation_result.modified_count,
        "preserved_group_ids": APPROVED_QA_GROUP_IDS,
        "completed_at": now,
    }
    await db.core_migrations.insert_one({
        "_id": str(uuid4()), "migration_key": MIGRATION_KEY, "actor_user_id": actor_user_id,
        "completed_at": now, "result": result,
    })
    return result