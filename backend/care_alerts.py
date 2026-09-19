"""Alertas deterministas y sin contenido confidencial para Cuidado Pastoral."""
from datetime import datetime, timezone
from uuid import uuid4


ACTIVE_STATUSES = {"detected", "assigned", "contacted", "follow_up", "escalated"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value):
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def _set_alert(db, case: dict, alert_type: str, present: bool, severity: str, due_at=None) -> tuple[int, int]:
    key = f"{alert_type}:{case['case_id']}"
    existing = await db.care_alerts.find_one({"alert_key": key})
    now = now_utc()
    if present and not existing:
        alert_id = str(uuid4())
        await db.care_alerts.insert_one({
            "_id": alert_id, "alert_id": alert_id, "alert_key": key,
            "case_id": case["case_id"], "person_id": case["person_id"],
            "op72_id": case.get("op72_id"), "alert_type": alert_type,
            "severity": severity, "status": "open", "due_at": due_at,
            "detected_at": now, "updated_at": now,
        })
        return 1, 0
    if present and existing and existing.get("status") == "resolved":
        await db.care_alerts.update_one({"_id": existing["_id"]}, {"$set": {"status": "open", "severity": severity, "due_at": due_at, "detected_at": now, "resolved_at": None, "updated_at": now}})
        return 1, 0
    if present and existing:
        await db.care_alerts.update_one({"_id": existing["_id"]}, {"$set": {"severity": severity, "due_at": due_at, "updated_at": now}})
        return 0, 0
    if not present and existing and existing.get("status") in {"open", "acknowledged"}:
        await db.care_alerts.update_one({"_id": existing["_id"]}, {"$set": {"status": "resolved", "resolved_at": now, "resolution": "La condición operativa dejó de estar presente", "updated_at": now}})
        return 0, 1
    return 0, 0


async def evaluate_care_alerts(db) -> dict:
    now = now_utc(); created = resolved = 0
    cases = await db.pastoral_cases.find({}, {"_id": 0}).to_list(100000)
    op72_by_case = {item["case_id"]: item async for item in db.op72_records.find({}, {"_id": 0})}
    primary_case_ids = set(await db.pastoral_case_assignments.distinct("case_id", {"active": True, "assignment_role": "primary"}))
    for case in cases:
        active = case.get("status") in ACTIVE_STATUSES
        op72 = op72_by_case.get(case["case_id"])
        unassigned_due = _aware(op72.get("assignment_deadline_at")) if op72 else None
        no_contact_due = _aware(op72.get("contact_deadline_at")) if op72 else None
        pairs = [
            ("unassigned_24h", bool(active and op72 and case["case_id"] not in primary_case_ids and unassigned_due and now >= unassigned_due), "critical", unassigned_due),
            ("uncontacted_72h", bool(active and op72 and not op72.get("first_contact_at") and no_contact_due and now >= no_contact_due), "critical", no_contact_due),
            ("next_step_due", bool(active and _aware(case.get("next_step_at")) and now >= _aware(case.get("next_step_at"))), "warning", _aware(case.get("next_step_at"))),
            ("urgent_case", bool(active and case.get("priority") == "urgent"), "critical", now if active and case.get("priority") == "urgent" else None),
        ]
        for alert_type, present, severity, due_at in pairs:
            made, closed = await _set_alert(db, case, alert_type, present, severity, due_at)
            created += made; resolved += closed
    return {"created": created, "resolved": resolved, "evaluated_at": now}
