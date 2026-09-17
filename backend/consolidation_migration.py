"""Migración append-only de recorridos históricos hacia Consolidación v2."""
from datetime import datetime, timezone

from consolidation_service import configure_entry_stages
from process_engine import create_enrollment, recalculate_enrollment


STAGE_MAP = {
    "prayer": "prayer",
    "invasion": "invasion",
    "mcd": "mcd",
    "npt": "npt",
    "new_visitor": "visitor_followup",
    "contacted": "visitor_followup",
    "first_visit": "visitor_followup",
    "follow_up": "visitor_followup",
    "integrated": "mcd",
    "ready_for_activation": "mcd",
}


async def migrate_historical_consolidation(db) -> dict:
    migration_id = "consolidation_v2_historical_links"
    previous = await db.core_migrations.find_one({"migration_id": migration_id}, {"_id": 0})
    if previous:
        return previous
    migrated = 0; linked = 0
    legacy_items = await db.process_enrollments.find(
        {"$or": [{"process_key": "seven_weeks"}, {"process_key": "consolidation", "definition_version": {"$lt": 2}}]},
        {"_id": 0},
    ).sort("created_at", 1).to_list(50000)
    for legacy in legacy_items:
        existing = await db.process_enrollments.find_one({"process_key": "consolidation", "definition_version": 2, "person_id": legacy["person_id"]}, {"_id": 0})
        if existing:
            await db.process_enrollments.update_one({"enrollment_id": legacy["enrollment_id"]}, {"$set": {"migrated_to_consolidation_v2": existing["enrollment_id"], "migration_linked_at": datetime.now(timezone.utc)}})
            linked += 1
            continue
        entry_mode = "complete_cycle" if legacy["process_key"] == "seven_weeks" else "visitor_followup"
        enrollment, created = await create_enrollment(
            db,
            "consolidation",
            legacy["person_id"],
            legacy.get("responsible_person_id"),
            legacy.get("created_by_user_id") or "system:migration",
            cycle_id=f"legacy-v2:{legacy['enrollment_id']}",
            status="active" if legacy.get("status") != "completed" else "completed",
            next_action="Revisar expediente migrado",
            source=f"legacy_{legacy['process_key']}",
            source_id=legacy["enrollment_id"],
            allow_parallel_versions=True,
        )
        if not created:
            continue
        await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": {"legacy_source_snapshot": legacy, "migration_review_required": True, "front_group_id": legacy.get("front_group_id")}})
        enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0})
        await configure_entry_stages(db, enrollment, entry_mode, legacy.get("created_by_user_id") or "system:migration")
        legacy_stages = await db.process_stage_progress.find({"enrollment_id": legacy["enrollment_id"], "status": "completed"}, {"_id": 0}).to_list(100)
        for stage in legacy_stages:
            mapped = STAGE_MAP.get(stage.get("stage_key"))
            if mapped:
                await db.process_stage_progress.update_one({"enrollment_id": enrollment["enrollment_id"], "stage_key": mapped}, {"$set": {"status": "completed", "completed_at": stage.get("completed_at"), "legacy_stage_snapshot": stage, "updated_at": datetime.now(timezone.utc)}})
        await recalculate_enrollment(db, enrollment["enrollment_id"], legacy.get("created_by_user_id") or "system:migration", allow_automation=False)
        await db.process_enrollments.update_one({"enrollment_id": legacy["enrollment_id"]}, {"$set": {"migrated_to_consolidation_v2": enrollment["enrollment_id"], "migration_linked_at": datetime.now(timezone.utc)}})
        migrated += 1
    result = {"migration_id": migration_id, "migrated": migrated, "linked": linked, "completed_at": datetime.now(timezone.utc)}
    await db.core_migrations.insert_one({"_id": migration_id, **result})
    return result