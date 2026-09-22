"""Fixture efímero UI para P0 de emisión de carnet con foto en Persona 360."""
import base64
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from access_control import ACCESS_POLICY_VERSION, access_defaults_for_role  # noqa: E402


load_dotenv("/app/backend/.env", override=False)
load_dotenv("/app/frontend/.env", override=False)

DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PREFIX = "qa.iter47.photo"
PASSWORD = "QaUiPhoto47!"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _person(nombre: str, apellido: str, key: str) -> ObjectId:
    pid = ObjectId()
    now = datetime.now(timezone.utc)
    DB.persons.insert_one(
        {
            "_id": pid,
            "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
            "nombre": nombre,
            "apellido": apellido,
            "search_key": f"{nombre} {apellido}".lower(),
            "idempotency_key": key,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )
    return pid


def _user(email: str, role: str, person_id: str, name: str) -> ObjectId:
    now = datetime.now(timezone.utc)
    uid = ObjectId()
    defaults = access_defaults_for_role(role)
    DB.users.insert_one(
        {
            "_id": uid,
            "nombre": name,
            "email": email,
            "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "rol": role,
            "access_level": "pastor" if role in {"pastor", "pastora"} else role,
            "person_id": person_id,
            "capabilities": defaults["capabilities"],
            "access_scope": defaults["access_scope"],
            "privilege_groups": defaults.get("privilege_groups", []),
            "is_active": True,
            "token_version": 1,
            "access_policy_version": ACCESS_POLICY_VERSION,
            "must_change_password": False,
            "onboarding_required": False,
            "created_at": now,
            "updated_at": now,
        }
    )
    return uid


def _auth_token(email: str) -> str:
    login = requests.post(
        f"{API}/api/auth/login",
        json={"email": email, "password": PASSWORD},
        timeout=30,
    )
    login.raise_for_status()
    return login.json()["token"]


def setup_fixture():
    suffix = uuid.uuid4().hex[:10]
    pastor_key = f"{PREFIX}:pastor:{suffix}"
    member_key = f"{PREFIX}:member:{suffix}"
    now = datetime.now(timezone.utc)

    pastor_pid = _person("QA", "Pastora Foto", pastor_key)
    member_pid = _person("QA", "Miembro Foto", member_key)

    pastor_email = f"{PREFIX}.pastora.{suffix}@example.com"
    pastor_uid = _user(pastor_email, "pastora", str(pastor_pid), "QA Pastora Foto")
    DB.persons.update_one({"_id": pastor_pid}, {"$set": {"auth_user_id": str(pastor_uid), "updated_at": now}})

    membership_id = str(uuid.uuid4())
    member_number = f"UI47-{suffix.upper()}"
    DB.person_memberships.insert_one(
        {
            "_id": membership_id,
            "membership_id": membership_id,
            "person_id": str(member_pid),
            "member_number": member_number,
            "status": "active",
            "legacy_membership": True,
            "created_at": now,
            "updated_at": now,
        }
    )
    DB.membership_number_registry.insert_one(
        {
            "_id": member_number,
            "member_number": member_number,
            "person_id": str(member_pid),
            "reserved_at": now,
            "source": "ui_iter47",
        }
    )

    token = _auth_token(pastor_email)
    headers = {"Authorization": f"Bearer {token}"}
    init = requests.post(
        f"{API}/api/core/persons/{member_pid}/photo/uploads",
        headers=headers,
        json={"content_type": "image/png", "total_size": len(PNG_1X1), "total_chunks": 1},
        timeout=30,
    )
    init.raise_for_status()
    upload_id = init.json()["upload_id"]
    chunk = requests.put(
        f"{API}/api/core/persons/{member_pid}/photo/uploads/{upload_id}/chunks/0",
        headers={**headers, "Content-Type": "application/octet-stream"},
        data=PNG_1X1,
        timeout=30,
    )
    chunk.raise_for_status()
    done = requests.post(
        f"{API}/api/core/persons/{member_pid}/photo/uploads/{upload_id}/complete",
        headers=headers,
        json={},
        timeout=30,
    )
    done.raise_for_status()

    print(
        json.dumps(
            {
                "email": pastor_email,
                "password": PASSWORD,
                "person_id": str(member_pid),
                "suffix": suffix,
                "membership_id": membership_id,
                "upload_id": upload_id,
            }
        )
    )


def cleanup_fixture():
    regex = f"^{PREFIX}"
    users = list(DB.users.find({"email": {"$regex": regex}}, {"_id": 1, "person_id": 1, "email": 1}))
    user_person_ids = [item.get("person_id") for item in users if item.get("person_id")]
    people = list(DB.persons.find({"idempotency_key": {"$regex": f"^{PREFIX}:"}}, {"_id": 1}))
    person_ids = [str(item["_id"]) for item in people]
    all_person_ids = list({*person_ids, *user_person_ids})

    upload_ids = DB.person_photo_uploads.distinct("_id", {"person_id": {"$in": all_person_ids}})
    if upload_ids:
        DB.person_photo_chunks.delete_many({"upload_id": {"$in": [str(item) for item in upload_ids]}})
    DB.person_photo_uploads.delete_many({"person_id": {"$in": all_person_ids}})
    DB.person_photos.delete_many({"person_id": {"$in": all_person_ids}})
    DB.membership_document_issuances.delete_many({"person_id": {"$in": all_person_ids}})
    DB.membership_events.delete_many({"person_id": {"$in": all_person_ids}})
    DB.person_activity.delete_many({"person_id": {"$in": all_person_ids}})
    DB.person_memberships.delete_many({"person_id": {"$in": all_person_ids}})
    DB.membership_number_registry.delete_many({"person_id": {"$in": all_person_ids}})
    DB.users.delete_many({"email": {"$regex": regex}})
    DB.persons.delete_many({"idempotency_key": {"$regex": f"^{PREFIX}:"}})

    print(
        json.dumps(
            {
                "remaining_users": DB.users.count_documents({"email": {"$regex": regex}}),
                "remaining_persons": DB.persons.count_documents({"idempotency_key": {"$regex": f"^{PREFIX}:"}}),
                "remaining_memberships": DB.person_memberships.count_documents({"person_id": {"$in": all_person_ids}}),
            }
        )
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_fixture()
    else:
        cleanup_fixture()
