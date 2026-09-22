"""Regresión del contrato foto canónica → emisión de carnet."""
import base64
import os
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

from access_control import ACCESS_POLICY_VERSION, access_defaults_for_role


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV["REACT_APP_BACKEND_URL"]).rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
PASSWORD = "QaMembershipPhoto47!"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@pytest.fixture
def membership_photo_state():
    suffix = uuid4().hex[:10]
    user_id, actor_person_id, member_person_id = ObjectId(), ObjectId(), ObjectId()
    member_id = str(member_person_id)
    membership_id = str(uuid4())
    member_number = f"PHOTO-{suffix.upper()}"
    email = f"qa.membership.photo.{suffix}@example.com"
    now = datetime.now(timezone.utc)
    defaults = access_defaults_for_role("pastor")
    DB.persons.insert_many([
        {"_id": actor_person_id, "person_number": f"VV-P47-{suffix[:6]}", "nombre": "Pastora", "apellido": "Foto QA", "search_key": "pastora foto qa", "idempotency_key": f"qa:p47:actor:{suffix}", "version": 1, "created_at": now, "updated_at": now},
        {"_id": member_person_id, "person_number": f"VV-M47-{suffix[:6]}", "nombre": "Miembro", "apellido": "Con Foto", "search_key": "miembro con foto", "idempotency_key": f"qa:p47:member:{suffix}", "version": 1, "created_at": now, "updated_at": now},
    ])
    DB.users.insert_one({
        "_id": user_id,
        "nombre": "Pastora Foto QA",
        "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": "pastora",
        "access_level": "pastor",
        "person_id": str(actor_person_id),
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
    })
    DB.persons.update_one({"_id": actor_person_id}, {"$set": {"auth_user_id": str(user_id)}})
    DB.person_memberships.insert_one({
        "_id": membership_id,
        "membership_id": membership_id,
        "person_id": member_id,
        "member_number": member_number,
        "status": "active",
        "legacy_membership": True,
        "created_at": now,
        "updated_at": now,
    })
    DB.membership_number_registry.insert_one({"_id": member_number, "member_number": member_number, "person_id": member_id, "reserved_at": now, "source": "photo_regression"})
    state = {"email": email, "member_id": member_id, "membership_id": membership_id, "user_id": user_id, "actor_person_id": actor_person_id, "member_person_id": member_person_id, "upload_ids": []}
    yield state
    DB.membership_document_issuances.delete_many({"membership_id": membership_id})
    DB.membership_events.delete_many({"membership_id": membership_id})
    DB.membership_number_registry.delete_many({"person_id": member_id})
    DB.person_memberships.delete_many({"person_id": member_id})
    DB.person_activity.delete_many({"person_id": {"$in": [member_id, str(actor_person_id)]}})
    DB.person_photo_chunks.delete_many({"upload_id": {"$in": state["upload_ids"]}})
    DB.person_photo_uploads.delete_many({"person_id": member_id})
    DB.person_photos.delete_many({"person_id": member_id})
    DB.users.delete_one({"_id": user_id})
    DB.persons.delete_many({"_id": {"$in": [actor_person_id, member_person_id]}})


def test_uploaded_and_legacy_visible_photo_both_enable_card(membership_photo_state):
    state = membership_photo_state
    login = requests.post(f"{BASE_URL}/api/auth/login", json={"email": state["email"], "password": PASSWORD}, timeout=30)
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    initialized = requests.post(
        f"{BASE_URL}/api/core/persons/{state['member_id']}/photo/uploads",
        headers=headers,
        json={"content_type": "image/png", "total_size": len(PNG_1X1), "total_chunks": 1},
        timeout=30,
    )
    assert initialized.status_code == 201, initialized.text
    upload_id = initialized.json()["upload_id"]
    state["upload_ids"].append(upload_id)
    chunk = requests.put(
        f"{BASE_URL}/api/core/persons/{state['member_id']}/photo/uploads/{upload_id}/chunks/0",
        headers={**headers, "Content-Type": "application/octet-stream"},
        data=PNG_1X1,
        timeout=30,
    )
    assert chunk.status_code == 200, chunk.text
    completed = requests.post(
        f"{BASE_URL}/api/core/persons/{state['member_id']}/photo/uploads/{upload_id}/complete",
        headers=headers,
        json={},
        timeout=30,
    )
    assert completed.status_code == 200, completed.text
    assert DB.person_photos.find_one({"person_id": state["member_id"]})["is_current"] is True

    DB.person_photos.update_one({"person_id": state["member_id"]}, {"$unset": {"is_current": ""}})
    profile = requests.get(f"{BASE_URL}/api/core/persons/{state['member_id']}/profile", headers=headers, timeout=30)
    photo = requests.get(f"{BASE_URL}/api/core/persons/{state['member_id']}/photo", headers=headers, timeout=30)
    assert profile.status_code == 200 and profile.json()["header"]["photo_available"] is True
    assert photo.status_code == 200 and photo.content == PNG_1X1

    issued = requests.post(
        f"{BASE_URL}/api/membership/persons/{state['member_id']}/documents/card/issue",
        headers=headers,
        json={"issue_date": "2026-09-22"},
        timeout=30,
    )
    assert issued.status_code == 201, issued.text
    assert issued.json()["data"]["person"]["has_profile_photo"] is True