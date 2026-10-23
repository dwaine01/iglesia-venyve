"""Seed for Etapa 4 UI review (iteration 48). Root group led by coreqa.leader, sub-group, coreqa.member as mentor
with 2 disciples (one paused, one with overdue activity). Run with `python3 tests/seed_etapa4_ui_review.py [cleanup]`."""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = "qa-etapa4-ui-review"
now = datetime.now(timezone.utc)


def cleanup():
    gids = db.front_groups.distinct("front_group_id", {"qa_tag": TAG})
    db.front_groups.delete_many({"qa_tag": TAG})
    db.front_group_assignments.delete_many({"front_group_id": {"$in": gids}})
    eids = db.process_enrollments.distinct("enrollment_id", {"qa_tag": TAG})
    db.process_enrollments.delete_many({"qa_tag": TAG})
    db.consolidation_activities.delete_many({"enrollment_id": {"$in": eids}})
    db.persons.delete_many({"qa_tag": TAG})


def group(name, leader_pid, parent=None):
    gid = str(uuid.uuid4())
    anc = [parent] if parent else []
    db.front_groups.insert_one({"_id": gid, "front_group_id": gid, "name": name, "parent_group_id": parent, "ancestor_group_ids": anc,
                                "depth": len(anc), "status": "active", "primary_leader_person_id": leader_pid, "qa_tag": TAG, "created_at": now, "updated_at": now})
    assign(gid, leader_pid, "leader")
    return gid


def assign(gid, pid, role):
    aid = str(uuid.uuid4())
    db.front_group_assignments.insert_one({"_id": aid, "assignment_id": aid, "front_group_id": gid, "person_id": pid, "role": role, "active": True, "started_at": now, "created_at": now})


def person(label):
    oid = ObjectId()
    db.persons.insert_one({"_id": oid, "nombre": "QAUI", "apellido": label, "qa_tag": TAG, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
                       "idempotency_key": f"qa:etapa4ui:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
    return str(oid)


if __name__ == "__main__":
    cleanup()
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        print("cleaned"); sys.exit(0)
    leader = db.users.find_one({"email": "coreqa.leader@example.com"})["person_id"]
    member = db.users.find_one({"email": "coreqa.member@example.com"})["person_id"]
    other_leader = person("LiderAjeno")
    root = group("QAUI Rama Lider", leader)
    sub = group("QAUI Subrama", leader, parent=root)
    foreign = group("QAUI Rama Ajena", other_leader)
    assign(root, member, "mentor")
    for label, status in [("DiscipuloPausado", "paused"), ("DiscipuloVencido", "in_progress")]:
        pid = person(label); eid = str(uuid.uuid4())
        db.process_enrollments.insert_one({"_id": eid, "enrollment_id": eid, "process_key": "consolidation", "person_id": pid, "mentor_person_id": member,
                                           "front_group_id": root, "decision_status": status, "decision_paused_reason": "Viaje de trabajo" if status == "paused" else None,
                                           "current_stage_key": "mcd", "status": "active", "qa_tag": TAG, "created_at": now - timedelta(days=20), "updated_at": now})
        if status != "paused":
            aid = str(uuid.uuid4())
            db.consolidation_activities.insert_one({"_id": aid, "activity_id": aid, "enrollment_id": eid, "status": "pending", "stage_key": "mcd",
                                                    "scheduled_date": (now - timedelta(days=4)).date().isoformat(), "created_at": now})
    print({"root": root, "sub": sub, "foreign": foreign, "leader": leader, "member": member})
