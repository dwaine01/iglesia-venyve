"""Cleanup guard: remove QA artifacts created during Mega-Bloque C validation."""
import os

from dotenv import dotenv_values
from bson import ObjectId
from pymongo import MongoClient


BACKEND_ENV = dotenv_values("/app/backend/.env")
MONGO_URL = (BACKEND_ENV.get("MONGO_URL") or os.environ.get("MONGO_URL") or "").strip('"')
DB_NAME = (BACKEND_ENV.get("DB_NAME") or os.environ.get("DB_NAME") or "").strip('"')


def test_cleanup_qa_artifacts_created_by_t1_run():
    if not MONGO_URL or not DB_NAME:
        return

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    try:
        qa_users = list(db.users.find({"email": {"$regex": r"^qa\.lockout\.", "$options": "i"}}, {"_id": 1, "person_id": 1}))
        qa_person_ids_from_users = [item.get("person_id") for item in qa_users if item.get("person_id")]

        network_ids = db.cell_networks.distinct("network_id", {"name": {"$regex": r"^QA (UI Red T1|MegaC )", "$options": "i"}})
        cell_ids = db.cells.distinct("cell_id", {
            "$or": [
                {"network_id": {"$in": network_ids}},
                {"name": {"$regex": r"^QA (UI C[ée]lula|MegaC )", "$options": "i"}},
                {"code": {"$regex": r"^(QAT1U|QAC)", "$options": "i"}},
            ]
        })
        meeting_ids = db.cell_meetings.distinct("meeting_id", {"cell_id": {"$in": cell_ids}})
        need_ids = db.cell_needs.distinct("need_id", {"cell_id": {"$in": cell_ids}})
        case_ids = db.door_cases.distinct("case_id", {"source_type": "cell_need", "source_id": {"$in": need_ids}})
        qa_person_ids = db.persons.distinct("_id", {"$or": [{"nombre": "QA Lockout"}, {"apellido": {"$regex": r"MegaC", "$options": "i"}}]})
        qa_person_ids = [str(item) for item in qa_person_ids] + qa_person_ids_from_users

        if network_ids:
            db.cell_network_assignments.delete_many({"network_id": {"$in": network_ids}})
            db.cell_networks.delete_many({"network_id": {"$in": network_ids}})

        if cell_ids:
            db.cell_role_assignments.delete_many({"cell_id": {"$in": cell_ids}})
            db.cell_memberships.delete_many({"cell_id": {"$in": cell_ids}})
            db.cell_followups.delete_many({"cell_id": {"$in": cell_ids}})
            db.cell_needs.delete_many({"cell_id": {"$in": cell_ids}})
            db.cell_health_snapshots.delete_many({"cell_id": {"$in": cell_ids}})
            db.cell_multiplication_reviews.delete_many({"cell_id": {"$in": cell_ids}})
            db.cell_timeline.delete_many({"cell_id": {"$in": cell_ids}})
            db.cells.delete_many({"cell_id": {"$in": cell_ids}})

        if meeting_ids:
            db.cell_meeting_attendance.delete_many({"meeting_id": {"$in": meeting_ids}})
            db.person_attendance.delete_many({"activity_type": "cell_meeting", "source_id": {"$in": meeting_ids}})
            db.cell_meetings.delete_many({"meeting_id": {"$in": meeting_ids}})

        if case_ids:
            db.door_case_events.delete_many({"case_id": {"$in": case_ids}})
            db.board_audit_events.delete_many({"entity_id": {"$in": case_ids}})
            db.door_cases.delete_many({"case_id": {"$in": case_ids}})

        if qa_person_ids:
            db.cell_assignment_events.delete_many({"person_id": {"$in": qa_person_ids}})
            db.person_contacts.delete_many({"person_id": {"$in": qa_person_ids}})
            db.person_activity.delete_many({"person_id": {"$in": qa_person_ids}})
            db.process_enrollments.delete_many({"person_id": {"$in": qa_person_ids}})
            db.process_stage_progress.delete_many({"person_id": {"$in": qa_person_ids}})
            db.process_timeline.delete_many({"person_id": {"$in": qa_person_ids}})
            db.process_alerts.delete_many({"person_id": {"$in": qa_person_ids}})
            db.persons.delete_many({"_id": {"$in": [ObjectId(pid) for pid in qa_person_ids if len(pid) == 24]}})

        if qa_users:
            db.users.delete_many({"_id": {"$in": [item["_id"] for item in qa_users]}})

        remaining_networks = db.cell_networks.count_documents({"name": {"$regex": r"^QA (UI Red T1|MegaC )", "$options": "i"}})
        remaining_cells = db.cells.count_documents({"$or": [{"name": {"$regex": r"^QA (UI C[ée]lula|MegaC )", "$options": "i"}}, {"code": {"$regex": r"^(QAT1U|QAC)", "$options": "i"}}]})
        remaining_users = db.users.count_documents({"email": {"$regex": r"^qa\.lockout\.", "$options": "i"}})

        assert remaining_networks == 0
        assert remaining_cells == 0
        assert remaining_users == 0
    finally:
        client.close()
