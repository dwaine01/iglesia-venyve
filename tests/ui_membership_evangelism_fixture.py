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


EMAILS = ["qa.features.pastor@example.com", "qa.features.persona@example.com"]
PASSWORD = "FeatureFlow2026!"


async def cleanup(db):
    users = await db.users.find({"email": {"$in": EMAILS}}, {"_id": 1, "person_id": 1}).to_list(10)
    user_ids = [str(item["_id"]) for item in users]; person_ids = [item.get("person_id") for item in users if item.get("person_id")]
    target_ids = [item["target_id"] for item in await db.evangelism_targets.find({"created_by_user_id": {"$in": user_ids}}, {"_id": 0, "target_id": 1}).to_list(100)]
    await db.evangelism_target_events.delete_many({"target_id": {"$in": target_ids}}); await db.evangelism_targets.delete_many({"created_by_user_id": {"$in": user_ids}})
    created_people = await db.persons.find({"$or": [{"created_by": {"$in": user_ids}}, {"idempotency_key": {"$regex": "^ui:features:"}}, {"_id": {"$in": [ObjectId(item) for item in person_ids if ObjectId.is_valid(item)]}}]}, {"_id": 1}).to_list(100)
    all_person_ids = [str(item["_id"]) for item in created_people]
    memberships = await db.person_memberships.find({"person_id": {"$in": all_person_ids}}, {"_id": 0, "member_number": 1}).to_list(100)
    await db.membership_number_registry.delete_many({"member_number": {"$in": [item["member_number"] for item in memberships]}})
    await db.membership_number_registry.delete_many({"$or": [{"person_id": {"$in": all_person_ids}}, {"member_number": {"$regex": "^PUB-I29-"}}]})
    for collection in ["person_memberships", "membership_events", "person_activity", "person_contacts", "person_addresses"]:
        await db[collection].delete_many({"person_id": {"$in": all_person_ids}})
    await db.persons.delete_many({"_id": {"$in": [item["_id"] for item in created_people]}}); await db.users.delete_many({"email": {"$in": EMAILS}})


async def setup(db):
    await cleanup(db); now = datetime.now(timezone.utc)
    for role, email, name in [("pastor", EMAILS[0], "QA Pastora Funciones"), ("persona", EMAILS[1], "QA Persona Evangelismo")]:
        person_id, user_id = ObjectId(), ObjectId(); defaults = access_defaults_for_role(role)
        await db.persons.insert_one({"_id": person_id, "person_number": f"VV-UF{str(person_id)[-6:].upper()}", "nombre": name, "apellido": "Temporal", "search_key": f"{name} temporal".lower(), "idempotency_key": f"ui:features:account:{email}", "version": 1, "auth_user_id": str(user_id), "created_at": now, "updated_at": now})
        await db.users.insert_one({"_id": user_id, "nombre": name, "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": str(person_id), "is_active": True, "token_version": 1, "created_at": now, **defaults})
    print(f"pastor={EMAILS[0]} password={PASSWORD}")
    print(f"persona={EMAILS[1]} password={PASSWORD}")


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    if len(sys.argv) != 2 or sys.argv[1] not in {"setup", "cleanup"}: raise SystemExit("Use setup|cleanup")
    await (setup(db) if sys.argv[1] == "setup" else cleanup(db))


if __name__ == "__main__": asyncio.run(main())