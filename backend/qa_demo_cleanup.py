"""Detección y eliminación explícita de artefactos QA/demo autorizados."""
import re
from collections import Counter

from bson import ObjectId


QA_EMAIL_PATTERN = r"^(base01|access01|coreqa|pytest|qa[._-]|test[._-]|demo[._-]|t1qa|t1ui)"
QA_PERSON_PATTERN = r"^(QA|Test|Demo|BASE-01|ACCESS-01|Core QA|T1QA|T1UI)(\b|[-_ ])"
QA_KEY_PATTERN = r"^(qa|test|pytest|demo)[-_:]"
PROTECTED_COLLECTIONS = {"finance_settings", "membership_document_settings"}


async def qa_targets(db) -> tuple[list[dict], list[dict]]:
    users = await db.users.find(
        {"$or": [
            {"email": {"$regex": QA_EMAIL_PATTERN, "$options": "i"}},
            {"nombre": {"$regex": QA_PERSON_PATTERN, "$options": "i"}},
        ]},
        {"_id": 1, "person_id": 1},
    ).to_list(2000)
    linked_oids = [ObjectId(item["person_id"]) for item in users if ObjectId.is_valid(str(item.get("person_id", "")))]
    people = await db.persons.find(
        {"$or": [
            {"_id": {"$in": linked_oids}},
            {"nombre": {"$regex": QA_PERSON_PATTERN, "$options": "i"}},
            {"apellido": {"$regex": QA_PERSON_PATTERN, "$options": "i"}},
            {"idempotency_key": {"$regex": QA_KEY_PATTERN, "$options": "i"}},
        ]},
        {"_id": 1},
    ).to_list(5000)
    return users, people


async def qa_summary(db) -> dict:
    users, people = await qa_targets(db)
    return {"qa_users": len(users), "qa_persons": len(people), "total": len(users) + len(people)}


def _contains_marker(value, string_markers: set[str], object_markers: set[ObjectId]) -> bool:
    if isinstance(value, dict):
        return any(_contains_marker(item, string_markers, object_markers) for item in value.values())
    if isinstance(value, list):
        return any(_contains_marker(item, string_markers, object_markers) for item in value)
    return value in string_markers or value in object_markers


def _explicit_qa(document: dict) -> bool:
    values = [document.get(key) for key in ("name", "nombre", "title", "email", "idempotency_key", "qa_run")]
    return any(
        isinstance(value, str)
        and (re.search(QA_PERSON_PATTERN, value, re.I) or re.search(QA_KEY_PATTERN, value, re.I))
        for value in values
    )


async def delete_qa_artifacts(db) -> dict:
    users, people = await qa_targets(db)
    user_ids = {str(item["_id"]) for item in users}
    person_ids = {str(item["_id"]) for item in people}
    string_markers = user_ids | person_ids
    object_markers = {ObjectId(item) for item in string_markers if ObjectId.is_valid(item)}
    deleted = Counter()
    for collection_name in await db.list_collection_names():
        if collection_name.startswith("system.") or collection_name in PROTECTED_COLLECTIONS:
            continue
        ids = []
        async for document in db[collection_name].find({}):
            if _contains_marker(document, string_markers, object_markers) or _explicit_qa(document):
                ids.append(document["_id"])
        if ids:
            result = await db[collection_name].delete_many({"_id": {"$in": ids}})
            deleted[collection_name] = result.deleted_count
    for collection_name in PROTECTED_COLLECTIONS:
        await db[collection_name].update_many(
            {"updated_by_user_id": {"$in": list(user_ids)}},
            {"$unset": {"updated_by_user_id": ""}},
        )
    return {
        "qa_users": len(users),
        "qa_persons": len(people),
        "deleted_documents": sum(deleted.values()),
        "deleted_by_collection": dict(sorted(deleted.items())),
    }