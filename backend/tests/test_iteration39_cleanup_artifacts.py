"""Cleanup verificable para fixtures QA de Junta restringida."""
import re

from bson import ObjectId
from dotenv import dotenv_values
from gridfs import GridFSBucket
from pymongo import MongoClient


ENV = dotenv_values("/app/backend/.env")


def test_cleanup_iteration39_qa_fixtures_and_gridfs():
    db = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
    user_filter = {"email": {"$regex": r"^qa\.(iter39|board\.matrix)", "$options": "i"}}
    users = list(db.users.find(user_filter, {"_id": 1, "person_id": 1}))
    user_ids = [item["_id"] for item in users]
    person_ids = [item.get("person_id") for item in users if item.get("person_id")]
    object_ids = [ObjectId(item) for item in person_ids if re.fullmatch(r"[0-9a-fA-F]{24}", str(item))]

    meeting_ids = db.board_meetings.distinct(
        "meeting_id",
        {"$or": [{"qa_run": {"$in": ["iteration39", "visual39"]}}, {"title": {"$regex": "Iter39|QA Junta restringida", "$options": "i"}}]},
    )
    membership_ids = db.board_memberships.distinct(
        "membership_id",
        {"$or": [{"created_by_user_id": {"$in": [str(item) for item in user_ids]}}, {"person_id": {"$in": person_ids}}, {"qa_run": {"$in": ["iteration39", "visual39"]}}]},
    )

    for bucket_name in ["board_documents", "board_recordings", "board_recording_staging"]:
        bucket = GridFSBucket(db, bucket_name=bucket_name)
        files = db[f"{bucket_name}.files"].find({"$or": [{"metadata.qa_run": {"$in": ["iteration39", "visual39"]}}, {"metadata.meeting_id": {"$in": meeting_ids}}]}, {"_id": 1})
        for file_doc in list(files): bucket.delete(file_doc["_id"])

    for collection in ["board_agenda_items", "board_attendance", "board_proposals", "board_votes", "board_actions", "board_minutes", "board_ai_artifacts", "board_secretary_notes", "board_secretary_note_versions", "board_transcript_versions", "board_transcript_segments", "board_recording_uploads"]:
        db[collection].delete_many({"meeting_id": {"$in": meeting_ids}})
    db.board_meetings.delete_many({"meeting_id": {"$in": meeting_ids}})
    db.door_assignments.delete_many({"source_board_membership_id": {"$in": membership_ids}})
    db.board_memberships.delete_many({"membership_id": {"$in": membership_ids}})
    db.person_activity.delete_many({"person_id": {"$in": person_ids}})
    db.login_attempts.delete_many(user_filter)
    db.users.delete_many({"_id": {"$in": user_ids}})
    db.persons.delete_many({"_id": {"$in": object_ids}})

    assert db.users.count_documents(user_filter) == 0
    assert db.board_meetings.count_documents({"meeting_id": {"$in": meeting_ids}}) == 0
    assert db.board_memberships.count_documents({"membership_id": {"$in": membership_ids}}) == 0