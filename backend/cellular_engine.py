"""Scopes, métricas, salud, genealogía y migración del Sistema Celular."""
from datetime import date, datetime, timezone
from uuid import uuid4

from bson import ObjectId

from cellular_catalog import NEED_DOOR_MAP


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value


def serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return iso_z(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items() if key != "_id"}
    return value


async def person_summary(db, person_id: str | None) -> dict | None:
    if not person_id or not ObjectId.is_valid(person_id):
        return None
    person = await db.persons.find_one(
        {"_id": ObjectId(person_id)},
        {"_id": 0, "nombre": 1, "apellido": 1, "person_number": 1},
    )
    if not person:
        return None
    return {
        "person_id": person_id,
        "name": f"{person.get('nombre', '')} {person.get('apellido', '')}".strip(),
        "person_number": person.get("person_number"),
        "profile_path": f"/personas/{person_id}",
    }


async def cellular_scope(db, current_user: dict) -> dict:
    person_id = current_user.get("person_id")
    if current_user.get("rol") == "pastor":
        return {"global": True, "network_ids": [], "cell_ids": [], "roles": ["pastor_principal"]}
    network_assignments = await db.cell_network_assignments.find(
        {"person_id": person_id, "active": True}, {"_id": 0}
    ).to_list(100)
    roles = [item["role"] for item in network_assignments]
    if "general_coordinator" in roles:
        return {"global": True, "network_ids": [], "cell_ids": [], "roles": roles}
    network_ids = list({item["network_id"] for item in network_assignments})
    cell_ids = set(await db.cells.distinct("cell_id", {"network_id": {"$in": network_ids}})) if network_ids else set()
    direct = await db.cell_role_assignments.find(
        {"person_id": person_id, "active": True}, {"_id": 0}
    ).to_list(100)
    roles.extend(item["role"] for item in direct)
    cell_ids.update(item["cell_id"] for item in direct)
    memberships = await db.cell_memberships.find(
        {"person_id": person_id, "active": True}, {"_id": 0, "cell_id": 1}
    ).to_list(20)
    cell_ids.update(item["cell_id"] for item in memberships)
    return {"global": False, "network_ids": network_ids, "cell_ids": list(cell_ids), "roles": sorted(set(roles))}


async def can_access_cell(db, current_user: dict, cell_id: str, write: bool = False) -> bool:
    scope = await cellular_scope(db, current_user)
    if scope["global"]:
        return True
    if cell_id not in scope["cell_ids"]:
        return False
    if not write:
        return True
    write_roles = {"network_director", "supervisor", "cell_leader", "assistant"}
    return bool(write_roles.intersection(scope["roles"]))


async def record_cell_event(db, cell_id: str, actor_user_id: str, event_type: str, title: str, detail: str = "", person_id: str | None = None) -> None:
    await db.cell_timeline.insert_one({
        "_id": str(uuid4()),
        "cell_id": cell_id,
        "person_id": person_id,
        "event_type": event_type,
        "title": title,
        "detail": detail,
        "actor_user_id": actor_user_id,
        "occurred_at": now_utc(),
    })


async def current_cell_metrics(db, cell_id: str) -> dict:
    active_members = await db.cell_memberships.count_documents({"cell_id": cell_id, "active": True, "membership_type": "primary"})
    meetings = await db.cell_meetings.find({"cell_id": cell_id, "status": "completed"}, {"_id": 0}).sort("scheduled_at", -1).limit(12).to_list(12)
    meeting_ids = [item["meeting_id"] for item in meetings]
    attendance = await db.cell_meeting_attendance.find({"meeting_id": {"$in": meeting_ids}}, {"_id": 0}).to_list(5000) if meeting_ids else []
    present = sum(1 for item in attendance if item.get("status") == "present")
    visitors = sum(1 for item in attendance if item.get("is_visitor"))
    conversions = sum(len(item.get("conversion_person_ids", [])) for item in meetings)
    average = round(present / max(1, len(meetings)), 1)
    return {
        "active_members": active_members,
        "meetings_count": len(meetings),
        "attendance_total": present,
        "average_attendance": average,
        "visitors": visitors,
        "conversions": conversions,
        "retention": round((active_members / max(1, visitors + active_members)) * 100, 1),
        "has_leader_in_training": bool(await db.cell_role_assignments.find_one({"cell_id": cell_id, "role": "assistant", "active": True})),
        "has_host": bool(await db.cell_role_assignments.find_one({"cell_id": cell_id, "role": "host", "active": True})),
        "open_followups": await db.cell_followups.count_documents({"cell_id": cell_id, "status": {"$in": ["open", "in_progress"]}}),
        "open_needs": await db.cell_needs.count_documents({"cell_id": cell_id, "status": {"$in": ["open", "assigned", "in_progress"]}}),
    }


async def snapshot_cell_health(db, cell_id: str, actor_user_id: str, meeting_id: str | None = None) -> dict:
    metrics = await current_cell_metrics(db, cell_id)
    now = now_utc()
    period_key = now.strftime("%Y-%m")
    snapshot_id = f"{cell_id}:{period_key}:{meeting_id or now.strftime('%Y%m%d%H%M%S')}"
    doc = {
        "_id": snapshot_id,
        "snapshot_id": snapshot_id,
        "cell_id": cell_id,
        "period_key": period_key,
        "meeting_id": meeting_id,
        **metrics,
        "recorded_by_user_id": actor_user_id,
        "recorded_at": now,
    }
    await db.cell_health_snapshots.update_one({"_id": snapshot_id}, {"$setOnInsert": doc}, upsert=True)
    return serialize(doc)


async def evaluate_multiplication(db, cell_id: str, actor_user_id: str) -> dict:
    rule = await db.cell_multiplication_rules.find_one({"rule_key": "default", "enabled": True}, {"_id": 0})
    if not rule:
        return {"eligible": False, "facts": [], "missing": ["Regla no configurada"]}
    metrics = await current_cell_metrics(db, cell_id)
    facts = [
        (metrics["active_members"] >= rule["min_active_members"], f"{metrics['active_members']} miembros activos"),
        (metrics["meetings_count"] >= rule["min_stable_meetings"], f"{metrics['meetings_count']} reuniones estables"),
        (metrics["average_attendance"] >= rule["min_average_attendance"], f"Promedio {metrics['average_attendance']}"),
        (not rule.get("requires_leader_in_training") or metrics["has_leader_in_training"], "Líder en entrenamiento"),
        (not rule.get("requires_new_host") or metrics["has_host"], "Anfitrión disponible"),
    ]
    eligible = all(item[0] for item in facts)
    result = {"eligible": eligible, "facts": [label for passed, label in facts if passed], "missing": [label for passed, label in facts if not passed], "metrics": metrics}
    if eligible:
        now = now_utc()
        review = await db.cell_multiplication_reviews.find_one({"cell_id": cell_id, "status": {"$in": ["candidate", "under_review", "postponed"]}})
        if not review:
            review_id = str(uuid4())
            await db.cell_multiplication_reviews.insert_one({
                "_id": review_id,
                "review_id": review_id,
                "cell_id": cell_id,
                "rule_key": rule["rule_key"],
                "facts": result,
                "status": "candidate",
                "decision": None,
                "created_by_user_id": actor_user_id,
                "created_at": now,
                "updated_at": now,
            })
            await record_cell_event(db, cell_id, actor_user_id, "multiplication_candidate", "Célula candidata a multiplicación", "Requiere revisión humana")
    return result


async def ready_inbox(db, current_user: dict) -> list[dict]:
    query = {"ready_for_cellular": True, "status": "completed"}
    process_items = await db.process_enrollments.find(query, {"_id": 0}).sort("completed_at", -1).to_list(10000)
    scope = await cellular_scope(db, current_user)
    results = []
    seen = set()
    for item in process_items:
        person_id = item["person_id"]
        if person_id in seen or await db.cell_memberships.find_one({"person_id": person_id, "active": True, "membership_type": "primary"}):
            continue
        if not scope["global"]:
            person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"_id": 0, "created_by": 1, "auth_user_id": 1})
            assigned = current_user.get("person_id") in {item.get("responsible_person_id"), item.get("mentor_person_id")}
            owned = person and current_user.get("user_id") in {person.get("created_by"), person.get("auth_user_id")}
            if not assigned and not owned:
                continue
        seen.add(person_id)
        results.append({**serialize(item), "person": await person_summary(db, person_id)})
    return results


async def migrate_cellular(db, actor_user_id: str) -> dict:
    result = {"networks_seeded": await db.cell_networks.count_documents({"source": "institutional_catalog"}), "legacy_cells_migrated": 0, "conflict_count": 0, "conflicts": []}
    await db.cellular_migrations.update_one(
        {"migration_key": "mega_block_c_v1"},
        {"$set": {"last_run_at": now_utc(), "last_actor_user_id": actor_user_id, "result": result}, "$setOnInsert": {"_id": "mega_block_c_v1", "created_at": now_utc()}},
        upsert=True,
    )
    return result


async def ensure_cellular_indexes(db) -> None:
    await db.cell_networks.create_index("network_id", unique=True)
    await db.cell_network_assignments.create_index([("network_id", 1), ("person_id", 1), ("role", 1), ("active", 1)])
    await db.cells.create_index("cell_id", unique=True)
    await db.cells.create_index("code", unique=True)
    await db.cell_role_assignments.create_index([("cell_id", 1), ("person_id", 1), ("role", 1), ("active", 1)])
    await db.cell_memberships.create_index([("cell_id", 1), ("person_id", 1), ("active", 1)])
    await db.cell_memberships.create_index(
        [("person_id", 1), ("membership_type", 1), ("active", 1)],
        unique=True,
        partialFilterExpression={"membership_type": "primary", "active": True},
        name="unique_active_primary_cell_membership",
    )
    await db.cell_meetings.create_index("meeting_id", unique=True)
    await db.cell_meeting_attendance.create_index([("meeting_id", 1), ("person_id", 1)], unique=True)
    await db.cell_needs.create_index([("cell_id", 1), ("status", 1), ("suggested_door_key", 1)])
    await db.cell_followups.create_index([("cell_id", 1), ("status", 1), ("responsible_person_id", 1)])
    await db.cell_health_snapshots.create_index([("cell_id", 1), ("recorded_at", -1)])
    await db.cell_multiplication_reviews.create_index([("cell_id", 1), ("status", 1)])
    await db.cell_multiplications.create_index([("mother_cell_id", 1), ("multiplied_at", -1)])
    await db.cell_assignment_events.create_index([("person_id", 1), ("assigned_at", -1)])
    await db.person_attendance.create_index([("activity_type", 1), ("source_id", 1), ("person_id", 1)])


def suggested_door(need_type: str) -> str | None:
    return NEED_DOOR_MAP.get(need_type)