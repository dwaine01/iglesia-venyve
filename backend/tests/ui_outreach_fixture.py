# Seed QA fixture for Phase 2 Outreach UI testing (qa.outreachui.* users). Run: python ui_outreach_fixture.py [seed|clean]
import os
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
from access_control import access_defaults_for_role  # noqa: E402

PASSWORD = "QaOutreachUI2026!"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
now = datetime.now(timezone.utc)

USERS = [
    # slug, role, badge, lbs, extra caps
    ("mentora", "persona", True, False, []),
    ("mentorb", "persona", True, True, []),
    ("nobadge", "persona", False, False, []),
    ("leader", "lider", True, False, ["mentorship.outreach.assign"]),
]


def clean():
    users = list(db.users.find({"email": {"$regex": r"^qa\.outreachui\."}}))
    pids = [u.get("person_id") for u in users if u.get("person_id")]
    pids += [str(p["_id"]) for p in db.persons.find({"apellido": {"$regex": "^OutreachUI"}}, {"_id": 1})]
    visits = list(db.outreach_visits.find({"$or": [{"mentor_person_id": {"$in": pids}}, {"contact_name": {"$regex": "^QA OutreachUI"}}]}))
    vids = [v["visit_id"] for v in visits]
    conv = [v.get("converted_person_id") for v in visits if v.get("converted_person_id")]
    enr = [v.get("enrollment_id") for v in visits if v.get("enrollment_id")]
    db.outreach_visit_history.delete_many({"visit_id": {"$in": vids}})
    db.outreach_visits.delete_many({"visit_id": {"$in": vids}})
    db.outreach_campaigns.delete_many({"name": {"$regex": "^QA OutreachUI"}})
    if enr:
        for col in ("process_enrollments", "mentor_assignments", "process_stage_progress", "enrollment_stages"):
            db[col].delete_many({"enrollment_id": {"$in": enr}})
    allp = pids + conv
    db.mentor_badges.delete_many({"person_id": {"$in": allp}})
    db.mentor_qualifications.delete_many({"person_id": {"$in": allp}})
    db.mentor_badge_history.delete_many({"person_id": {"$in": allp}})
    db.person_contacts.delete_many({"person_id": {"$in": allp}})
    db.persons.delete_many({"_id": {"$in": [ObjectId(p) for p in allp if ObjectId.is_valid(p)]}})
    db.users.delete_many({"email": {"$regex": r"^qa\.outreachui\."}})
    print(f"cleaned users={len(users)} visits={len(vids)} persons={len(allp)}")


def seed():
    clean()
    out = {}
    for slug, role, badge, lbs, caps in USERS:
        pid = ObjectId()
        db.persons.insert_one({"_id": pid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "QA", "apellido": f"OutreachUI {slug.capitalize()}",
                               "search_key": f"qa outreachui {slug}", "idempotency_key": f"qa:outreachui:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
        d = access_defaults_for_role(role)
        d["capabilities"] = sorted(set(d.get("capabilities", []) + caps))
        email = f"qa.outreachui.{slug}@example.com"
        db.users.insert_one({"_id": ObjectId(), "nombre": f"QA OutreachUI {slug}", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
                             "rol": role, "is_active": True, "token_version": 1, "created_at": now, "person_id": str(pid), **d})
        if badge:
            db.mentor_badges.insert_one({"person_id": str(pid), "active": True, "since": now.date().isoformat(), "badge_id": str(uuid.uuid4()), "created_at": now, "updated_at": now})
        if lbs:
            db.mentor_qualifications.insert_one({"qualification_id": str(uuid.uuid4()), "person_id": str(pid), "front_group_id": None, "can_teach_lbs": True, "valid_until": None,
                                                 "active": True, "archived": False, "created_at": now, "updated_at": now})
        out[slug] = (email, str(pid))
    ex = ObjectId()
    db.persons.insert_one({"_id": ex, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "Zebedeo", "apellido": "OutreachUI Existente",
                           "search_key": "zebedeo outreachui existente", "idempotency_key": f"qa:outreachui:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
    db.person_contacts.insert_one({"_id": str(uuid.uuid4()), "person_id": str(ex), "tipo": "telefono", "valor": "555-SECRET", "es_principal": True, "created_at": now})
    out["existing"] = ("-", str(ex))
    for k, v in out.items():
        print(k, v[0], v[1])


if __name__ == "__main__":
    seed() if (sys.argv[1:] or ["seed"])[0] == "seed" else clean()
