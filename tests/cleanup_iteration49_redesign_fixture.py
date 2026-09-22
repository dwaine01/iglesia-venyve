"""Limpieza final de fixture rediseño A y restauración de settings institucionales."""

import json
import os
import pickle
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv("/app/backend/.env", override=False)

DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
FIXTURE_PATH = Path("/app/test_reports/redesign_a_fixture.json")
SETTINGS_PKL = Path("/app/test_reports/redesign_a_settings.pkl")
PREFIX = "qa.iter47.photo"


def main() -> None:
    fixture = {}
    if FIXTURE_PATH.exists():
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    # 1) Restaurar settings institucionales desde snapshot .pkl
    restored = False
    if SETTINGS_PKL.exists():
        previous = pickle.loads(SETTINGS_PKL.read_bytes())
        if isinstance(previous, dict):
            previous.pop("_id", None)
            DB.membership_document_settings.update_one(
                {"settings_id": "primary"},
                {"$set": previous},
                upsert=True,
            )
            restored = True

    # 2) Eliminar firma temporal en GridFS si la referencia del fixture existe
    deleted_signature_blob = False
    signature_files_remaining = 0
    signature_chunks_remaining = 0
    signature_file_id = fixture.get("signature_file_id")
    if signature_file_id and ObjectId.is_valid(signature_file_id):
        oid = ObjectId(signature_file_id)
        files = DB[f"membership_signatures.files"]
        chunks = DB[f"membership_signatures.chunks"]
        files.delete_one({"_id": oid})
        chunks.delete_many({"files_id": oid})
        signature_files_remaining = files.count_documents({"_id": oid})
        signature_chunks_remaining = chunks.count_documents({"files_id": oid})
        deleted_signature_blob = True

    # 3) Limpiar datos QA del prefijo iter47.photo (usuarios/personas/membresías/fotos/eventos)
    users = list(DB.users.find({"email": {"$regex": f"^{PREFIX}"}}, {"_id": 1, "person_id": 1, "email": 1}))
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
    DB.users.delete_many({"email": {"$regex": f"^{PREFIX}"}})
    DB.persons.delete_many({"idempotency_key": {"$regex": f"^{PREFIX}:"}})

    # 4) Si settings restaurados no usan firma, limpiar referencia
    if restored:
        settings = DB.membership_document_settings.find_one({"settings_id": "primary"}, {"_id": 0}) or {}
        if not settings.get("signature_file_id"):
            DB.membership_document_settings.update_one(
                {"settings_id": "primary"},
                {"$set": {"signature_file_id": None}},
            )

    summary = {
        "restored_settings": restored,
        "deleted_signature_blob": deleted_signature_blob,
        "remaining_users": DB.users.count_documents({"email": {"$regex": f"^{PREFIX}"}}),
        "remaining_persons": DB.persons.count_documents({"idempotency_key": {"$regex": f"^{PREFIX}:"}}),
        "remaining_memberships": DB.person_memberships.count_documents({"person_id": {"$in": all_person_ids}}) if all_person_ids else 0,
        "signature_files_remaining": signature_files_remaining,
        "signature_chunks_remaining": signature_chunks_remaining,
    }
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
