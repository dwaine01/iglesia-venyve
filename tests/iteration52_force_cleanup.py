"""Cleanup reforzado de artefactos QA de iteración 52."""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient


BACKEND_ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]

# Baseline observado al inicio de iteración 52
BASE_SIGNATURE_ID = "6ab3211d7fcd97fc1d2b3911"
BASE_SIGNATURE_SHA = "cd6244612585281598eb906d4e644e855c814f0636445cf579515efbc65226ef"
BASE_SIGNER_NAME = "Pastora Principal"
BASE_SIGNER_TITLE = "Pastora Principal"
BASE_ORG_NAME = "Primera Iglesia del Nazareno Ven y Ve"
BASE_EXPIRATION_MONTHS = 12


def main() -> None:
    qa_users = list(DB.users.find({"email": {"$regex": r"^qa\.iter52\.pastora\..+@example\.com$"}}, {"_id": 1, "email": 1, "person_id": 1}))
    qa_user_ids = [str(item["_id"]) for item in qa_users]
    qa_person_ids = [item.get("person_id") for item in qa_users if item.get("person_id")]

    qa_person_docs = list(DB.persons.find({"idempotency_key": {"$regex": r"^qa:iter52:"}}, {"_id": 1}))
    qa_person_ids.extend([str(item["_id"]) for item in qa_person_docs])
    qa_person_ids = sorted({item for item in qa_person_ids if item})

    qa_memberships = list(DB.person_memberships.find({"$or": [{"person_id": {"$in": qa_person_ids}}, {"member_number": {"$regex": r"^VV-I52-"}}]}, {"membership_id": 1, "person_id": 1, "member_number": 1}))
    qa_membership_ids = [item.get("membership_id") for item in qa_memberships if item.get("membership_id")]

    DB.person_photo_uploads.delete_many({"person_id": {"$in": qa_person_ids}})
    DB.person_photo_chunks.delete_many({"person_id": {"$in": qa_person_ids}})
    DB.person_photos.delete_many({"person_id": {"$in": qa_person_ids}})

    DB.membership_document_issuances.delete_many({"person_id": {"$in": qa_person_ids}})
    DB.membership_events.delete_many({"person_id": {"$in": qa_person_ids}})
    DB.person_activity.delete_many({"person_id": {"$in": qa_person_ids}})

    DB.membership_number_registry.delete_many({"$or": [{"person_id": {"$in": qa_person_ids}}, {"member_number": {"$regex": r"^VV-I52-"}}]})
    DB.person_memberships.delete_many({"$or": [{"person_id": {"$in": qa_person_ids}}, {"membership_id": {"$in": qa_membership_ids}}, {"member_number": {"$regex": r"^VV-I52-"}}]})

    temp_signatures = list(DB.membership_signatures.files.find({"$or": [{"filename": {"$regex": r"iter52-signature"}}, {"metadata.uploaded_by_user_id": {"$in": qa_user_ids}}]}, {"_id": 1}))
    for item in temp_signatures:
        DB.membership_signatures.chunks.delete_many({"files_id": item["_id"]})
        DB.membership_signatures.files.delete_one({"_id": item["_id"]})

    DB.users.delete_many({"email": {"$regex": r"^qa\.iter52\.pastora\..+@example\.com$"}})
    DB.persons.delete_many({"idempotency_key": {"$regex": r"^qa:iter52:"}})

    restored_signature_id = BASE_SIGNATURE_ID if ObjectId.is_valid(BASE_SIGNATURE_ID) and DB.membership_signatures.files.count_documents({"_id": ObjectId(BASE_SIGNATURE_ID)}) else None

    DB.membership_document_settings.update_one(
        {"settings_id": "primary"},
        {
            "$set": {
                "signature_file_id": restored_signature_id,
                "signature_sha256": BASE_SIGNATURE_SHA if restored_signature_id else None,
                "authorized_signer_name": BASE_SIGNER_NAME,
                "authorized_signer_title": BASE_SIGNER_TITLE,
                "organization_name": BASE_ORG_NAME,
                "expiration_months": BASE_EXPIRATION_MONTHS,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    print({
        "qa_users_removed": len(qa_users),
        "qa_persons_removed": len(qa_person_docs),
        "qa_memberships_removed": len(qa_memberships),
        "qa_temp_signatures_removed": len(temp_signatures),
        "restored_signature_file_id": restored_signature_id,
    })


if __name__ == "__main__":
    main()
