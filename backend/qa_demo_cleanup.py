"""Limpieza QA explícita, acotada y precedida por un plan firmado."""
import hashlib
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import jwt
from bson import ObjectId


QA_EMAIL_PATTERN = r"^(base01|access01|coreqa|pytest|qa[._-]|test[._-]|demo[._-]|t1qa|t1ui)"
QA_PERSON_PATTERN = r"^(QA|Test|Demo|BASE-01|ACCESS-01|Core QA|T1QA|T1UI)(\b|[-_ ])"
QA_KEY_PATTERN = r"^(qa|test|pytest|demo)[-_:]"
PREVIEW_TTL_MINUTES = 5


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


def _queries(user_oids: list[ObjectId], user_ids: list[str], person_oids: list[ObjectId], person_ids: list[str]) -> list[tuple[str, dict]]:
    """Allowlist de campos que representan propiedad directa, nunca una mención incidental."""
    return [
        ("person_contacts", {"person_id": {"$in": person_ids}}),
        ("person_addresses", {"person_id": {"$in": person_ids}}),
        ("person_activity", {"person_id": {"$in": person_ids}}),
        ("person_memberships", {"person_id": {"$in": person_ids}}),
        ("membership_events", {"person_id": {"$in": person_ids}}),
        ("membership_number_registry", {"person_id": {"$in": person_ids}}),
        ("person_photos", {"person_id": {"$in": person_ids}}),
        ("person_photo_uploads", {"person_id": {"$in": person_ids}}),
        ("person_talents", {"$or": [{"_id": {"$in": person_ids}}, {"person_id": {"$in": person_ids}}]}),
        ("person_households", {"person_id": {"$in": person_ids}}),
        ("person_family", {"person_id": {"$in": person_ids}}),
        ("person_relationships", {"$or": [{"person_a_id": {"$in": person_ids}}, {"person_b_id": {"$in": person_ids}}]}),
        ("household_memberships", {"person_id": {"$in": person_ids}}),
        ("ministry_assignments", {"person_id": {"$in": person_ids}}),
        ("cap_assessments", {"person_id": {"$in": person_ids}}),
        ("front_group_memberships", {"person_id": {"$in": person_ids}}),
        ("front_group_mentor_qualifications", {"person_id": {"$in": person_ids}}),
        ("leadership_promotions", {"person_id": {"$in": person_ids}}),
        ("process_enrollments", {"person_id": {"$in": person_ids}}),
        ("process_stage_progress", {"person_id": {"$in": person_ids}}),
        ("process_timeline", {"person_id": {"$in": person_ids}}),
        ("process_alerts", {"person_id": {"$in": person_ids}}),
        ("cell_memberships", {"person_id": {"$in": person_ids}}),
        ("cell_followups", {"person_id": {"$in": person_ids}}),
        ("cell_role_assignments", {"person_id": {"$in": person_ids}}),
        ("progress", {"user_id": {"$in": user_ids}}),
        ("checklists", {"user_id": {"$in": user_ids}}),
        ("persons", {"_id": {"$in": person_oids}}),
        ("users", {"_id": {"$in": user_oids}}),
    ]


async def qa_cleanup_plan(db) -> dict:
    users, people = await qa_targets(db)
    user_oids = [item["_id"] for item in users]
    user_ids = [str(item) for item in user_oids]
    person_oids = [item["_id"] for item in people]
    person_ids = [str(item) for item in person_oids]
    collections = []
    upload_ids = []
    for collection_name, query in _queries(user_oids, user_ids, person_oids, person_ids):
        docs = await db[collection_name].find(query, {"_id": 1}).to_list(100000)
        ids = [item["_id"] for item in docs]
        if collection_name == "person_photo_uploads":
            upload_ids = [str(item) for item in ids]
        if ids:
            collections.append({"collection": collection_name, "ids": ids})
    if upload_ids:
        chunks = await db.person_photo_chunks.find({"upload_id": {"$in": upload_ids}}, {"_id": 1}).to_list(100000)
        if chunks:
            principal_index = next((index for index, item in enumerate(collections) if item["collection"] == "person_photo_uploads"), len(collections))
            collections.insert(principal_index, {"collection": "person_photo_chunks", "ids": [item["_id"] for item in chunks]})
    fingerprint = [f"{item['collection']}:{str(doc_id)}" for item in collections for doc_id in item["ids"]]
    digest = hashlib.sha256("\n".join(sorted(fingerprint)).encode("utf-8")).hexdigest()
    return {"qa_users": len(users), "qa_persons": len(people), "collections": collections, "digest": digest}


def _preview_token(plan: dict) -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is required")
    now = datetime.now(timezone.utc)
    return jwt.encode({"type": "qa_cleanup_preview", "digest": plan["digest"], "exp": now + timedelta(minutes=PREVIEW_TTL_MINUTES), "iat": now}, secret, algorithm="HS256")


def _decode_preview_token(token: str) -> dict:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is required")
    return jwt.decode(token, secret, algorithms=["HS256"])


async def qa_preview(db) -> dict:
    plan = await qa_cleanup_plan(db)
    counts = {item["collection"]: len(item["ids"]) for item in plan["collections"]}
    samples = {item["collection"]: [str(value) for value in item["ids"][:5]] for item in plan["collections"]}
    total_documents = sum(counts.values())
    return {
        "qa_users": plan["qa_users"], "qa_persons": plan["qa_persons"],
        "total": plan["qa_users"] + plan["qa_persons"], "affected_documents": total_documents,
        "affected_by_collection": counts, "samples_by_collection": samples,
        "confirmation_phrase": f"ELIMINAR QA {total_documents}", "preview_token": _preview_token(plan),
        "expires_in_seconds": PREVIEW_TTL_MINUTES * 60,
    }


async def delete_qa_artifacts(db, preview_token: str, confirmation_phrase: str) -> dict:
    payload = _decode_preview_token(preview_token)
    if payload.get("type") != "qa_cleanup_preview":
        raise ValueError("Vista previa inválida")
    plan = await qa_cleanup_plan(db)
    total_documents = sum(len(item["ids"]) for item in plan["collections"])
    if not isinstance(confirmation_phrase, str) or confirmation_phrase.strip() != f"ELIMINAR QA {total_documents}":
        raise ValueError("La frase de confirmación no coincide")
    if payload.get("digest") != plan["digest"]:
        raise RuntimeError("Los artefactos QA cambiaron; genere una nueva vista previa")
    deleted = Counter()
    for item in plan["collections"]:
        result = await db[item["collection"]].delete_many({"_id": {"$in": item["ids"]}})
        deleted[item["collection"]] = result.deleted_count
    return {
        "qa_users": plan["qa_users"], "qa_persons": plan["qa_persons"],
        "deleted_documents": sum(deleted.values()), "deleted_by_collection": dict(sorted(deleted.items())),
    }