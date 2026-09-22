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
        ("front_group_routing_events", {"actor_user_id": {"$in": user_ids}}),
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
        ("front_group_assignments", {"person_id": {"$in": person_ids}}),
        ("mentor_qualifications", {"person_id": {"$in": person_ids}}),
        ("mentor_assignments", {"$or": [{"person_id": {"$in": person_ids}}, {"mentor_person_id": {"$in": person_ids}}]}),
        ("mentor_evaluations", {"mentor_person_id": {"$in": person_ids}}),
        ("leadership_promotions", {"person_id": {"$in": person_ids}}),
        ("person_leadership_status", {"person_id": {"$in": person_ids}}),
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
    qa_groups = await db.front_groups.find(
        {"created_by_user_id": {"$in": user_ids}}, {"_id": 1, "front_group_id": 1}
    ).to_list(10000)
    qa_group_ids = [item["front_group_id"] for item in qa_groups]
    care_cases = await db.pastoral_cases.find({"person_id": {"$in": person_ids}}, {"_id": 1, "case_id": 1}).to_list(100000)
    care_case_ids = [item["case_id"] for item in care_cases]
    op72_items = await db.op72_records.find({"person_id": {"$in": person_ids}}, {"_id": 1, "op72_id": 1}).to_list(100000)
    evangelism_items = await db.evangelism_targets.find({"created_by_user_id": {"$in": user_ids}}, {"_id": 1, "target_id": 1}).to_list(100000)
    evangelism_target_ids = [item["target_id"] for item in evangelism_items]
    note_items = await db.pastoral_case_notes.find({"case_id": {"$in": care_case_ids}}, {"_id": 1, "note_id": 1}).to_list(100000)
    visit_participants = await db.pastoral_visitation_participants.find({"person_id": {"$in": person_ids}}, {"_id": 1, "visit_id": 1}).to_list(100000)
    visit_ids = sorted({item["visit_id"] for item in visit_participants})
    care_entity_ids = care_case_ids + [item["op72_id"] for item in op72_items] + [item["note_id"] for item in note_items] + visit_ids
    care_queries = [
        ("pastoral_case_assignments", {"case_id": {"$in": care_case_ids}}),
        ("pastoral_contact_attempts", {"case_id": {"$in": care_case_ids}}),
        ("pastoral_case_notes", {"case_id": {"$in": care_case_ids}}),
        ("care_alerts", {"case_id": {"$in": care_case_ids}}),
        ("op72_records", {"person_id": {"$in": person_ids}}),
        ("pastoral_visitation_summaries", {"visit_id": {"$in": visit_ids}}),
        ("pastoral_visitation_participants", {"visit_id": {"$in": visit_ids}}),
        ("pastoral_visitations", {"visit_id": {"$in": visit_ids}}),
        ("care_audit_events", {"$or": [{"entity_id": {"$in": care_entity_ids}}, {"actor_user_id": {"$in": user_ids}}]}),
        ("pastoral_cases", {"case_id": {"$in": care_case_ids}}),
        ("evangelism_target_events", {"target_id": {"$in": evangelism_target_ids}}),
        ("evangelism_targets", {"target_id": {"$in": evangelism_target_ids}}),
    ]
    front_group_queries = [
        ("front_group_work_assignments", {"$or": [{"assigned_group_id": {"$in": qa_group_ids}}, {"origin_group_id": {"$in": qa_group_ids}}]}),
        ("front_group_rotation_weeks", {"$or": [{"root_group_id": {"$in": qa_group_ids}}, {"selected_group_id": {"$in": qa_group_ids}}, {"eligible_group_ids_snapshot": {"$in": qa_group_ids}}]}),
        ("front_group_rotation_policies", {"$or": [{"root_group_id": {"$in": qa_group_ids}}, {"ordered_group_ids": {"$in": qa_group_ids}}]}),
        ("cell_front_group_links", {"front_group_id": {"$in": qa_group_ids}}),
        ("front_group_routing_events", {"front_group_id": {"$in": qa_group_ids}}),
        ("front_group_audit_events", {"front_group_id": {"$in": qa_group_ids}}),
        ("front_group_assignments", {"front_group_id": {"$in": qa_group_ids}}),
        ("mentor_qualifications", {"front_group_id": {"$in": qa_group_ids}}),
        ("mentor_assignments", {"front_group_id": {"$in": qa_group_ids}}),
        ("mentor_evaluations", {"front_group_id": {"$in": qa_group_ids}}),
        ("leadership_requirement_evidence", {"front_group_id": {"$in": qa_group_ids}}),
        ("leadership_promotions", {"front_group_id": {"$in": qa_group_ids}}),
        ("person_leadership_status", {"front_group_id": {"$in": qa_group_ids}}),
        ("front_groups", {"front_group_id": {"$in": qa_group_ids}}),
    ]
    qa_programs = await db.formation_programs.find({"created_by_user_id": {"$in": user_ids}}, {"_id": 0, "program_id": 1}).to_list(100000)
    qa_program_ids = [item["program_id"] for item in qa_programs]
    qa_modules = await db.formation_modules.find({"program_id": {"$in": qa_program_ids}}, {"_id": 0, "module_id": 1}).to_list(100000)
    qa_module_ids = [item["module_id"] for item in qa_modules]
    qa_cohorts = await db.formation_cohorts.find({"$or": [{"program_id": {"$in": qa_program_ids}}, {"created_by_user_id": {"$in": user_ids}}]}, {"_id": 0, "cohort_id": 1}).to_list(100000)
    qa_cohort_ids = [item["cohort_id"] for item in qa_cohorts]
    qa_enrollments = await db.formation_enrollments.find({"$or": [{"person_id": {"$in": person_ids}}, {"cohort_id": {"$in": qa_cohort_ids}}]}, {"_id": 0, "enrollment_id": 1}).to_list(100000)
    qa_enrollment_ids = [item["enrollment_id"] for item in qa_enrollments]
    formation_files = await db["formation_documents.files"].find({"metadata.person_id": {"$in": person_ids}}, {"_id": 1}).to_list(100000)
    formation_file_ids = [item["_id"] for item in formation_files]
    formation_queries = [
        ("formation_documents.chunks", {"files_id": {"$in": formation_file_ids}}),
        ("formation_documents.files", {"_id": {"$in": formation_file_ids}}),
        ("formation_attendance", {"$or": [{"person_id": {"$in": person_ids}}, {"enrollment_id": {"$in": qa_enrollment_ids}}]}),
        ("formation_grades", {"$or": [{"person_id": {"$in": person_ids}}, {"enrollment_id": {"$in": qa_enrollment_ids}}]}),
        ("formation_assessments", {"cohort_id": {"$in": qa_cohort_ids}}),
        ("formation_sessions", {"cohort_id": {"$in": qa_cohort_ids}}),
        ("formation_enrollments", {"$or": [{"person_id": {"$in": person_ids}}, {"cohort_id": {"$in": qa_cohort_ids}}]}),
        ("formation_cohort_staff", {"$or": [{"person_id": {"$in": person_ids}}, {"cohort_id": {"$in": qa_cohort_ids}}]}),
        ("formation_cohorts", {"cohort_id": {"$in": qa_cohort_ids}}),
        ("formation_module_prerequisites", {"$or": [{"module_id": {"$in": qa_module_ids}}, {"prerequisite_module_id": {"$in": qa_module_ids}}]}),
        ("formation_achievements", {"$or": [{"person_id": {"$in": person_ids}}, {"program_id": {"$in": qa_program_ids}}]}),
        ("formation_recommendations", {"$or": [{"person_id": {"$in": person_ids}}, {"program_id": {"$in": qa_program_ids}}]}),
        ("formation_certificate_issuances", {"$or": [{"person_id": {"$in": person_ids}}, {"program_id": {"$in": qa_program_ids}}]}),
        ("formation_audit_events", {"$or": [{"person_id": {"$in": person_ids}}, {"actor_user_id": {"$in": user_ids}}, {"entity_id": {"$in": [*qa_program_ids, *qa_module_ids, *qa_cohort_ids, *qa_enrollment_ids]}}]}),
        ("formation_modules", {"program_id": {"$in": qa_program_ids}}),
        ("formation_programs", {"program_id": {"$in": qa_program_ids}}),
    ]
    collection_ids = {}
    upload_ids = []
    for collection_name, query in [*care_queries, *front_group_queries, *formation_queries, *_queries(user_oids, user_ids, person_oids, person_ids)]:
        docs = await db[collection_name].find(query, {"_id": 1}).to_list(100000)
        ids = [item["_id"] for item in docs]
        if collection_name == "person_photo_uploads":
            upload_ids = [str(item) for item in ids]
        if ids:
            collection_ids.setdefault(collection_name, {})
            for item_id in ids:
                collection_ids[collection_name][str(item_id)] = item_id
    collections = [
        {"collection": collection_name, "ids": list(values.values())}
        for collection_name, values in collection_ids.items()
    ]
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