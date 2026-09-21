"""Seed/Cleanup de cuentas efímeras para pruebas UI de Iteración 36."""

import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

BACKEND_DIR = "/app/backend"
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from access_control import CORE_ACCESS_MANAGE, access_defaults_for_role


ARTIFACT_PATH = Path("/app/test_reports/artifacts_iter36/iteration36_accounts.json")
PASSWORD = "Iter36Ui!2026"


def _env():
    backend_env = dotenv_values("/app/backend/.env")
    return (
        str(backend_env.get("MONGO_URL", "")).strip('"'),
        str(backend_env.get("DB_NAME", "")).strip('"'),
    )


def _db():
    mongo_url, db_name = _env()
    return MongoClient(mongo_url)[db_name]


def _attempt_identifier(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _create_user(db, *, prefix: str, role: str, name: str, access_level: str | None = None, extra_caps: list[str] | None = None):
    user_id = ObjectId()
    person_id = ObjectId()
    slug = name.lower().replace(" ", "")
    email = f"{prefix}.{slug}@example.com"
    defaults = access_defaults_for_role(role)
    capabilities = sorted(set((defaults.get("capabilities") or []) + (extra_caps or [])))
    now = datetime.now(timezone.utc)

    db.persons.insert_one(
        {
            "_id": person_id,
            "person_number": f"VV-I36UI{str(person_id)[-5:].upper()}",
            "nombre": name,
            "apellido": "QA",
            "search_key": f"{name} qa".lower(),
            "idempotency_key": f"qa:iter36:ui:acct:{email}",
            "version": 1,
            "auth_user_id": str(user_id),
            "created_at": now,
            "updated_at": now,
        }
    )
    db.users.insert_one(
        {
            "_id": user_id,
            "nombre": name,
            "email": email,
            "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "rol": role,
            "person_id": str(person_id),
            "is_active": True,
            "token_version": 1,
            "created_at": now,
            "capabilities": capabilities,
            "access_scope": defaults.get("access_scope") or {"persons": "none"},
            "access_policy_version": 19,
            **({"access_level": access_level} if access_level else {}),
        }
    )
    return {
        "user_id": str(user_id),
        "person_id": str(person_id),
        "email": email,
        "password": PASSWORD,
        "name": name,
    }


def seed():
    db = _db()
    prefix = f"qa.iter36.ui.{uuid.uuid4().hex[:8]}"
    accounts = {
        "coordinator": _create_user(
            db,
            prefix=prefix,
            role="lider",
            name="Iter36 UI Coordinator",
            access_level="lider",
            extra_caps=[CORE_ACCESS_MANAGE],
        ),
        "leader": _create_user(
            db,
            prefix=prefix,
            role="lider",
            name="Iter36 UI Leader",
            access_level="lider",
        ),
        "director": _create_user(
            db,
            prefix=prefix,
            role="lider",
            name="Iter36 UI Director",
            access_level="director",
            extra_caps=[CORE_ACCESS_MANAGE],
        ),
        "pastor": _create_user(
            db,
            prefix=prefix,
            role="pastor",
            name="Iter36 UI Pastor",
            access_level="pastor",
        ),
    }
    payload = {"prefix": prefix, "accounts": accounts}
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(ARTIFACT_PATH))


def cleanup():
    if not ARTIFACT_PATH.exists():
        return
    data = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    prefix = data["prefix"]
    accounts = data["accounts"]
    db = _db()
    user_ids = [item["user_id"] for item in accounts.values()]
    person_ids = [item["person_id"] for item in accounts.values()]

    created_people = list(
        db.persons.find(
            {
                "$or": [
                    {"created_by": {"$in": user_ids}},
                    {"idempotency_key": {"$regex": "^qa:iter36:"}},
                ]
            },
            {"_id": 1},
        )
    )
    created_person_ids = [str(item["_id"]) for item in created_people]
    all_person_ids = sorted(set([*person_ids, *created_person_ids]))

    memberships = list(
        db.person_memberships.find(
            {"person_id": {"$in": all_person_ids}},
            {"_id": 0, "member_number": 1},
        )
    )
    member_numbers = [item.get("member_number") for item in memberships if item.get("member_number")]

    db.membership_number_registry.delete_many({"member_number": {"$in": member_numbers}})
    db.membership_events.delete_many({"person_id": {"$in": all_person_ids}})
    db.person_memberships.delete_many({"person_id": {"$in": all_person_ids}})
    db.person_activity.delete_many({"person_id": {"$in": all_person_ids}})
    db.person_contacts.delete_many({"person_id": {"$in": all_person_ids}})
    db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in all_person_ids if ObjectId.is_valid(item)]}})
    db.users.delete_many({"email": {"$regex": f"^{prefix}\\."}})
    db.login_attempts.delete_many(
        {
            "identifier": {
                "$in": [_attempt_identifier(item["email"]) for item in accounts.values()]
            }
        }
    )
    ARTIFACT_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    action = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    if action == "seed":
        seed()
    elif action == "cleanup":
        cleanup()
    else:
        raise SystemExit("Usage: python /app/tests/iteration36_membership_ui_accounts.py [seed|cleanup]")