#!/usr/bin/env python3
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from bson import ObjectId
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient


APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "backend"))
env = dotenv_values(APP / "backend" / ".env")
for key, value in env.items():
    if value is not None: os.environ.setdefault(key, str(value).strip('"'))
from access_control import access_defaults_for_role


ACCOUNTS = [
    ("pastor", "qa.operations.pastor@example.com", "QA Pastor Operaciones"),
    ("lider", "qa.operations.leader@example.com", "QA Líder Checkin"),
    ("persona", "qa.operations.person@example.com", "QA Voluntario Persona"),
]
PASSWORD = "OperationsFlow2026!"


async def cleanup(db):
    events = await db.operation_events.find({"title": {"$regex": "^QA (OPERACIONES|UI I31)"}}, {"_id": 0, "event_id": 1, "attachments": 1}).to_list(100)
    event_ids = [item["event_id"] for item in events]
    occurrence_ids = await db.operation_event_occurrences.distinct("occurrence_id", {"event_id": {"$in": event_ids}})
    entity_ids = event_ids + occurrence_ids + await db.operation_shifts.distinct("shift_id", {"event_id": {"$in": event_ids}})
    for item in events:
        for attachment in item.get("attachments", []):
            if ObjectId.is_valid(attachment.get("file_id")):
                file_id = ObjectId(attachment["file_id"]); await db["operation_attachments.chunks"].delete_many({"files_id": file_id}); await db["operation_attachments.files"].delete_one({"_id": file_id})
    for collection in ["operation_event_occurrences", "operation_shift_templates", "operation_shifts", "operation_volunteer_assignments", "operation_registrations", "operation_checkins", "operation_notifications"]:
        await db[collection].delete_many({"event_id": {"$in": event_ids}})
    await db.operation_audit_events.delete_many({"entity_id": {"$in": entity_ids}}); await db.operation_events.delete_many({"event_id": {"$in": event_ids}})
    emails = [item[1] for item in ACCOUNTS]; users = await db.users.find({"email": {"$in": emails}}, {"_id": 1, "person_id": 1}).to_list(20); person_ids = [item["person_id"] for item in users if item.get("person_id")]
    await db.person_attendance.delete_many({"person_id": {"$in": person_ids}, "actividad": {"$regex": "^QA OPERACIONES"}})
    await db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in person_ids if ObjectId.is_valid(item)]}}); await db.users.delete_many({"email": {"$in": emails}})


async def setup(db):
    await cleanup(db); now = datetime.now(timezone.utc)
    for role, email, name in ACCOUNTS:
        user_id, person_id = ObjectId(), ObjectId()
        await db.persons.insert_one({"_id": person_id, "person_number": f"VV-OP{str(person_id)[-6:].upper()}", "nombre": name, "apellido": "Temporal", "search_key": f"{name} temporal".lower(), "idempotency_key": f"ui:operations:{email}", "version": 1, "auth_user_id": str(user_id), "created_at": now, "updated_at": now})
        await db.users.insert_one({"_id": user_id, "nombre": name, "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": str(person_id), "is_active": True, "token_version": 1, "created_at": now, **access_defaults_for_role(role)})
    print(f"pastor={ACCOUNTS[0][1]} password={PASSWORD}")
    print(f"leader={ACCOUNTS[1][1]} password={PASSWORD}")
    print(f"person={ACCOUNTS[2][1]} password={PASSWORD}")


async def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"setup", "cleanup"}: raise SystemExit("Use setup|cleanup")
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await (setup(db) if sys.argv[1] == "setup" else cleanup(db))


if __name__ == "__main__": asyncio.run(main())