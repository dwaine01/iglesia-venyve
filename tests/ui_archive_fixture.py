"""Create and cleanup ephemeral fixture data for Persona archive UI testing."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from bson import ObjectId
from pymongo import MongoClient


PREFIX_EMAIL = "t1uiarchive"
PREFIX_NAME = "T1UIARCH"


def _read_env_file(path: Path) -> dict:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _settings() -> tuple[str, str]:
    env = _read_env_file(Path("/app/backend/.env"))
    mongo_url = os.environ.get("MONGO_URL") or env.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME") or env.get("DB_NAME")
    if not mongo_url or not db_name:
        raise RuntimeError("MONGO_URL and DB_NAME are required")
    return mongo_url, db_name


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cleanup(db) -> dict:
    users = list(
        db.users.find(
            {"email": {"$regex": f"^{PREFIX_EMAIL}\\."}},
            {"_id": 1, "person_id": 1},
        )
    )
    named_people = list(
        db.persons.find(
            {
                "$or": [
                    {"nombre": {"$regex": f"^{PREFIX_NAME}"}},
                    {"apellido": {"$regex": f"^{PREFIX_NAME}"}},
                ]
            },
            {"_id": 1},
        )
    )

    person_ids = {str(item["_id"]) for item in named_people}
    for user in users:
        pid = user.get("person_id")
        if isinstance(pid, str) and pid:
            person_ids.add(pid)

    if person_ids:
        db.person_contacts.delete_many({"person_id": {"$in": list(person_ids)}})
        db.person_addresses.delete_many({"person_id": {"$in": list(person_ids)}})
        db.person_activity.delete_many({"person_id": {"$in": list(person_ids)}})
        db.process_enrollments.delete_many({"person_id": {"$in": list(person_ids)}})
        db.cell_memberships.delete_many({"person_id": {"$in": list(person_ids)}})
        db.cell_followups.delete_many({"person_id": {"$in": list(person_ids)}})
        db.cell_needs.delete_many({"person_id": {"$in": list(person_ids)}})
        db.household_memberships.delete_many({"person_id": {"$in": list(person_ids)}})
        db.person_relationships.delete_many(
            {
                "$or": [
                    {"person_a_id": {"$in": list(person_ids)}},
                    {"person_b_id": {"$in": list(person_ids)}},
                ]
            }
        )
        db.person_talents.delete_many({"_id": {"$in": list(person_ids)}})
        db.ministry_assignments.delete_many({"person_id": {"$in": list(person_ids)}})
        db.person_memberships.delete_many({"person_id": {"$in": list(person_ids)}})
        db.persons.delete_many(
            {"_id": {"$in": [ObjectId(pid) for pid in person_ids if ObjectId.is_valid(pid)]}}
        )

    if users:
        db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})

    remaining_people = db.persons.count_documents(
        {
            "$or": [
                {"nombre": {"$regex": f"^{PREFIX_NAME}"}},
                {"apellido": {"$regex": f"^{PREFIX_NAME}"}},
            ]
        }
    )
    remaining_users = db.users.count_documents({"email": {"$regex": f"^{PREFIX_EMAIL}\\."}})
    return {
        "remaining_people": remaining_people,
        "remaining_users": remaining_users,
    }


def _setup(db) -> dict:
    _cleanup(db)
    now = _now()
    suffix = uuid.uuid4().hex[:8]

    pastor_user_id = ObjectId()
    pastor_person_id = ObjectId()
    target_person_id = ObjectId()

    pastor_email = f"{PREFIX_EMAIL}.pastor.{suffix}@example.com"
    pastor_password = "TestPass123!"
    target_name = f"{PREFIX_NAME} TARGET {suffix}"

    db.persons.insert_one(
        {
            "_id": pastor_person_id,
            "person_number": f"VV-9{str(uuid.uuid4().int)[:5]}",
            "nombre": f"{PREFIX_NAME} PASTOR",
            "apellido": suffix.upper(),
            "search_key": f"{PREFIX_NAME.lower()} pastor {suffix}",
            "idempotency_key": str(uuid.uuid4()),
            "created_by": str(pastor_user_id),
            "auth_user_id": str(pastor_user_id),
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )

    db.persons.insert_one(
        {
            "_id": target_person_id,
            "person_number": f"VV-8{str(uuid.uuid4().int)[:5]}",
            "nombre": target_name,
            "apellido": "ARCHIVE",
            "search_key": f"{target_name.lower()} archive",
            "idempotency_key": str(uuid.uuid4()),
            "created_by": str(pastor_user_id),
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )

    db.users.insert_one(
        {
            "_id": pastor_user_id,
            "nombre": f"{PREFIX_NAME} Pastor",
            "email": pastor_email,
            "password": bcrypt.hashpw(pastor_password.encode(), bcrypt.gensalt()).decode(),
            "rol": "pastor",
            "person_id": str(pastor_person_id),
            "is_active": True,
            "token_version": 1,
            "capabilities": [
                "person.profile.sensitive.read",
                "person.profile.write",
                "person.household.read",
                "person.household.write",
                "person.family.read",
                "person.family.write",
                "person.arrival.read",
                "person.arrival.write",
                "person.attendance.read",
                "person.attendance.write",
                "person.notes.read",
                "person.notes.write",
                "person.history.read",
                "person.directory.search",
                "person.talents.read",
                "person.talents.write",
                "person.ministries.read",
                "person.ministries.write",
                "person.contacts.read",
                "person.contacts.write",
                "person.addresses.read",
                "person.addresses.write",
            ],
            "access_scope": {"persons": "all"},
            "access_policy_version": 13,
            "created_at": now,
        }
    )

    linked_user_id = ObjectId()
    db.users.insert_one(
        {
            "_id": linked_user_id,
            "nombre": f"{PREFIX_NAME} Linked",
            "email": f"{PREFIX_EMAIL}.linked.{suffix}@example.com",
            "password": bcrypt.hashpw(b"NotUsed123!", bcrypt.gensalt()).decode(),
            "rol": "persona",
            "person_id": str(target_person_id),
            "is_active": True,
            "token_version": 2,
            "capabilities": ["person.profile.sensitive.read"],
            "access_scope": {"persons": "self"},
            "access_policy_version": 13,
            "created_at": now,
        }
    )

    db.person_memberships.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "membership_id": str(uuid.uuid4()),
            "person_id": str(target_person_id),
            "member_number": str(uuid.uuid4().int)[:5],
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    )

    return {
        "pastor_email": pastor_email,
        "pastor_password": pastor_password,
        "target_person_id": str(target_person_id),
        "target_person_name": target_name,
        "created_users": 2,
        "created_persons": 2,
    }


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "setup"
    mongo_url, db_name = _settings()
    client = MongoClient(mongo_url)
    db = client[db_name]
    try:
        if mode == "setup":
            print(json.dumps({"mode": "setup", **_setup(db)}))
        elif mode == "cleanup":
            print(json.dumps({"mode": "cleanup", **_cleanup(db)}))
        else:
            raise RuntimeError("mode must be setup or cleanup")
    finally:
        client.close()


if __name__ == "__main__":
    main()
