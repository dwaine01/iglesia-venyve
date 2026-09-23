"""Limpia el fixture visual definitivo y restaura settings institucionales."""
import json
import os
import pickle
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv("/app/backend/.env", override=False)
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
FIXTURE_PATH = Path("/app/test_reports/definitive_documents_fixture.json")
SETTINGS_PKL = Path("/app/test_reports/definitive_settings.pkl")
PREFIX = "qa.iter47.photo"


def main() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text()) if FIXTURE_PATH.exists() else {}
    restored = False
    if SETTINGS_PKL.exists():
        previous = pickle.loads(SETTINGS_PKL.read_bytes())
        if isinstance(previous, dict):
            previous.pop("_id", None)
            DB.membership_document_settings.update_one({"settings_id": "primary"}, {"$set": previous}, upsert=True)
            restored = True

    signature_file_id = fixture.get("signature_file_id")
    if signature_file_id and ObjectId.is_valid(signature_file_id):
        oid = ObjectId(signature_file_id)
        DB["membership_signatures.files"].delete_one({"_id": oid})
        DB["membership_signatures.chunks"].delete_many({"files_id": oid})

    users = list(DB.users.find({"email": {"$regex": f"^{PREFIX}"}}, {"person_id": 1}))
    people = list(DB.persons.find({"idempotency_key": {"$regex": f"^{PREFIX}:"}}, {"_id": 1}))
    person_ids = list({*[item.get("person_id") for item in users if item.get("person_id")], *[str(item["_id"]) for item in people]})
    upload_ids = DB.person_photo_uploads.distinct("_id", {"person_id": {"$in": person_ids}})
    DB.person_photo_chunks.delete_many({"upload_id": {"$in": [str(item) for item in upload_ids]}})
    for collection in ("person_photo_uploads", "person_photos", "membership_document_issuances", "membership_events", "person_activity", "person_memberships"):
        DB[collection].delete_many({"person_id": {"$in": person_ids}})
    DB.membership_number_registry.delete_many({"person_id": {"$in": person_ids}})
    DB.users.delete_many({"email": {"$regex": f"^{PREFIX}"}})
    DB.persons.delete_many({"idempotency_key": {"$regex": f"^{PREFIX}:"}})

    if restored and not (DB.membership_document_settings.find_one({"settings_id": "primary"}) or {}).get("signature_file_id"):
        DB.membership_document_settings.update_one({"settings_id": "primary"}, {"$set": {"signature_file_id": None}})

    print(json.dumps({
        "restored_settings": restored,
        "remaining_users": DB.users.count_documents({"email": {"$regex": f"^{PREFIX}"}}),
        "remaining_persons": DB.persons.count_documents({"idempotency_key": {"$regex": f"^{PREFIX}:"}}),
        "remaining_memberships": DB.person_memberships.count_documents({"person_id": {"$in": person_ids}}) if person_ids else 0,
        "signature_files_remaining": DB["membership_signatures.files"].count_documents({"_id": ObjectId(signature_file_id)}) if signature_file_id and ObjectId.is_valid(signature_file_id) else 0,
    }))


if __name__ == "__main__":
    main()