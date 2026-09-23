"""Iteración 52: prepara y limpia fixture efímero para pruebas UI/API de membresía."""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import bcrypt
import requests
from bson import ObjectId
from dotenv import dotenv_values
from PIL import Image, ImageDraw
from pymongo import MongoClient

from access_control import ACCESS_POLICY_VERSION, access_defaults_for_role


ROOT = Path("/app")
FRONTEND_ENV = dotenv_values(str(ROOT / "frontend/.env"))
BACKEND_ENV = dotenv_values(str(ROOT / "backend/.env"))
BASE_URL = FRONTEND_ENV["REACT_APP_BACKEND_URL"].rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
STATE_PATH = ROOT / "test_reports/iteration52_fixture.json"
SIGNATURE_PATH = ROOT / "test_reports/iteration52_signature.png"

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _mk_user(email: str, password: str, name: str, role: str, person_id: str) -> dict:
    defaults = access_defaults_for_role(role)
    now = datetime.now(timezone.utc)
    user_id = ObjectId()
    return {
        "_id": user_id,
        "nombre": name,
        "email": email,
        "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
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


def _auth_headers(email: str, password: str) -> dict:
    login = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    login.raise_for_status()
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _make_signature_png() -> bytes:
    image = Image.new("RGBA", (600, 220), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.line((20, 140, 230, 70), fill=(1, 161, 200, 255), width=7)
    draw.line((220, 70, 420, 160), fill=(110, 206, 60, 255), width=7)
    draw.line((420, 160, 570, 80), fill=(1, 161, 200, 255), width=7)
    draw.arc((90, 95, 290, 195), start=185, end=345, fill=(110, 206, 60, 255), width=5)
    buff = io.BytesIO()
    image.save(buff, format="PNG")
    return buff.getvalue()


def setup_fixture() -> None:
    suffix = uuid4().hex[:10]
    now = datetime.now(timezone.utc)

    pastor_person_id = ObjectId()
    member_person_id = ObjectId()
    pastor_person_str = str(pastor_person_id)
    member_person_str = str(member_person_id)

    pastor_email = f"qa.iter52.pastora.{suffix}@example.com"
    pastor_password = f"QaIter52!{suffix[:4]}"

    DB.persons.insert_many(
        [
            {
                "_id": pastor_person_id,
                "person_number": f"VV-I52-P-{suffix[:5].upper()}",
                "nombre": "Pastora",
                "apellido": "Iteracion 52",
                "search_key": "pastora iteracion 52",
                "idempotency_key": f"qa:iter52:pastora:{suffix}",
                "version": 1,
                "created_at": now,
                "updated_at": now,
            },
            {
                "_id": member_person_id,
                "person_number": f"VV-I52-M-{suffix[:5].upper()}",
                "nombre": "María Fernanda de los Ángeles",
                "apellido": "Santos Francisco Gómez Calderón del Valle",
                "full_name": "MARÍA FERNANDA DE LOS ÁNGELES SANTOS FRANCISCO GÓMEZ CALDERÓN DEL VALLE",
                "search_key": "maria fernanda angeles santos francisco gomez",
                "idempotency_key": f"qa:iter52:member:{suffix}",
                "version": 1,
                "created_at": now,
                "updated_at": now,
            },
        ]
    )

    pastor_user = _mk_user(pastor_email, pastor_password, "Pastora Iteración 52", "pastora", pastor_person_str)
    DB.users.insert_one(pastor_user)
    DB.persons.update_one(
        {"_id": pastor_person_id},
        {"$set": {"auth_user_id": str(pastor_user["_id"]), "updated_at": now}},
    )

    membership_id = str(uuid4())
    member_number = f"VV-I52-{suffix.upper()}-EXT"
    DB.person_memberships.insert_one(
        {
            "_id": membership_id,
            "membership_id": membership_id,
            "person_id": member_person_str,
            "member_number": member_number,
            "status": "active",
            "legacy_membership": True,
            "historical_membership_date": "2011-03-06",
            "historical_date_precision": "exact",
            "created_at": now,
            "updated_at": now,
        }
    )
    DB.membership_number_registry.insert_one(
        {
            "_id": member_number,
            "member_number": member_number,
            "person_id": member_person_str,
            "reserved_at": now,
            "source": "iter52",
        }
    )

    previous_settings = DB.membership_document_settings.find_one({"settings_id": "primary"}) or {}

    headers = _auth_headers(pastor_email, pastor_password)
    init_resp = requests.post(
        f"{BASE_URL}/api/core/persons/{member_person_str}/photo/uploads",
        headers=headers,
        json={"content_type": "image/png", "total_size": len(PNG_1X1), "total_chunks": 1},
        timeout=30,
    )
    init_resp.raise_for_status()
    upload_id = init_resp.json()["upload_id"]
    requests.put(
        f"{BASE_URL}/api/core/persons/{member_person_str}/photo/uploads/{upload_id}/chunks/0",
        headers={**headers, "Content-Type": "application/octet-stream"},
        data=PNG_1X1,
        timeout=30,
    ).raise_for_status()
    requests.post(
        f"{BASE_URL}/api/core/persons/{member_person_str}/photo/uploads/{upload_id}/complete",
        headers=headers,
        json={},
        timeout=30,
    ).raise_for_status()

    signature_bytes = _make_signature_png()
    SIGNATURE_PATH.write_bytes(signature_bytes)
    requests.post(
        f"{BASE_URL}/api/membership/settings/signature",
        headers=headers,
        files={"file": ("iter52-signature.png", signature_bytes, "image/png")},
        timeout=30,
    ).raise_for_status()

    state = {
        "suffix": suffix,
        "base_url": BASE_URL,
        "pastor_email": pastor_email,
        "pastor_password": pastor_password,
        "pastor_user_id": str(pastor_user["_id"]),
        "pastor_person_id": pastor_person_str,
        "member_person_id": member_person_str,
        "membership_id": membership_id,
        "member_number": member_number,
        "upload_id": upload_id,
        "signature_path": str(SIGNATURE_PATH),
        "previous_settings": {
            "signature_file_id": previous_settings.get("signature_file_id"),
            "signature_sha256": previous_settings.get("signature_sha256"),
            "authorized_signer_name": previous_settings.get("authorized_signer_name"),
            "authorized_signer_title": previous_settings.get("authorized_signer_title"),
            "organization_name": previous_settings.get("organization_name"),
            "expiration_months": previous_settings.get("expiration_months"),
        },
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fixture created: {STATE_PATH}")


def cleanup_fixture() -> None:
    if not STATE_PATH.exists():
        print("No fixture state found; nothing to clean")
        return

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    member_person_id = state["member_person_id"]
    pastor_person_id = state["pastor_person_id"]
    membership_id = state["membership_id"]
    member_number = state["member_number"]
    pastor_email = state["pastor_email"]
    suffix = state["suffix"]
    previous = state.get("previous_settings", {})

    current_settings = DB.membership_document_settings.find_one({"settings_id": "primary"}) or {}
    current_signature_id = current_settings.get("signature_file_id")
    previous_signature_id = previous.get("signature_file_id")

    if current_signature_id and current_signature_id != previous_signature_id and ObjectId.is_valid(current_signature_id):
        file_oid = ObjectId(current_signature_id)
        DB.membership_signatures.files.delete_one({"_id": file_oid})
        DB.membership_signatures.chunks.delete_many({"files_id": file_oid})

    DB.membership_document_settings.update_one(
        {"settings_id": "primary"},
        {
            "$set": {
                "signature_file_id": previous_signature_id,
                "signature_sha256": previous.get("signature_sha256"),
                "authorized_signer_name": previous.get("authorized_signer_name") or "",
                "authorized_signer_title": previous.get("authorized_signer_title") or "",
                "organization_name": previous.get("organization_name") or "Casa de Oración Ven y Ve",
                "expiration_months": int(previous.get("expiration_months") or 12),
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    DB.person_photo_chunks.delete_many({"upload_id": state.get("upload_id")})
    DB.person_photo_uploads.delete_many({"person_id": member_person_id})
    DB.person_photos.delete_many({"person_id": member_person_id})
    DB.membership_document_issuances.delete_many({"person_id": member_person_id})
    DB.membership_events.delete_many({"person_id": member_person_id})
    DB.person_activity.delete_many({"person_id": member_person_id})
    DB.membership_number_registry.delete_many({"member_number": member_number})
    DB.person_memberships.delete_one({"membership_id": membership_id})
    DB.users.delete_many({"email": pastor_email})
    DB.persons.delete_many({"idempotency_key": {"$regex": f"^qa:iter52:.*:{suffix}$"}})
    DB.persons.delete_one({"_id": ObjectId(pastor_person_id)})

    if SIGNATURE_PATH.exists():
        SIGNATURE_PATH.unlink()
    STATE_PATH.unlink(missing_ok=True)
    print("Fixture cleanup done")


if __name__ == "__main__":
    import sys

    action = (sys.argv[1] if len(sys.argv) > 1 else "setup").strip().lower()
    if action == "setup":
        setup_fixture()
    elif action == "cleanup":
        cleanup_fixture()
    else:
        raise SystemExit(f"Unknown action: {action}")
