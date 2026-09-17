"""Verify archive side-effects for a specific person_id in MongoDB."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient


def _read_env(path: Path) -> dict:
    values = {}
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
    env = _read_env(Path("/app/backend/.env"))
    mongo_url = os.environ.get("MONGO_URL") or env.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME") or env.get("DB_NAME")
    if not mongo_url or not db_name:
        raise RuntimeError("MONGO_URL and DB_NAME are required")
    return mongo_url, db_name


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("usage: python verify_ui_archive_state.py <person_id>")
    person_id = sys.argv[1]
    if not ObjectId.is_valid(person_id):
        raise RuntimeError("person_id must be a valid ObjectId")

    mongo_url, db_name = _settings()
    client = MongoClient(mongo_url)
    db = client[db_name]
    try:
        person = db.persons.find_one({"_id": ObjectId(person_id)})
        memberships = list(db.person_memberships.find({"person_id": person_id}, {"status": 1, "_id": 0}))
        linked_users = list(
            db.users.find(
                {"person_id": person_id, "rol": {"$ne": "pastor"}},
                {"email": 1, "is_active": 1, "token_version": 1, "_id": 0},
            )
        )
        activity = db.person_activity.find_one({"person_id": person_id, "action": "archived"}, {"_id": 0, "created_at": 1})

        print(
            json.dumps(
                {
                    "person_found": bool(person),
                    "is_archived": bool(person and person.get("is_archived") is True),
                    "linked_users": linked_users,
                    "memberships": memberships,
                    "activity_archived_exists": bool(activity),
                }
            )
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
