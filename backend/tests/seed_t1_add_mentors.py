# Seed for T1 testing of add/remove mentors on an existing invasion (public URL tests + UI).
# Persons/users use the "qa.addmentors" / "QA" pattern so qa_demo_cleanup removes them.
import json
import os
import uuid
from datetime import datetime, timezone

import bcrypt
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
PASSWORD = "T1AddMentors2026!"
now = datetime.now(timezone.utc)
tag = uuid.uuid4().hex[:5].upper()


def person(label):
    pid = ObjectId()
    db.persons.insert_one({"_id": pid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "QA", "apellido": f"{label} {tag}",
                           "idempotency_key": f"qa:add-mentors:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
    return str(pid)


def user(label, pid, role="persona"):
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from access_control import access_defaults_for_role
    email = f"qa.addmentors.t1{label.lower()}.{tag.lower()}@example.com"
    db.users.insert_one({"_id": ObjectId(), "nombre": f"QA {label}", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
                         "rol": role, "person_id": pid, "is_active": True, "token_version": 1, "created_at": now, **access_defaults_for_role(role)})
    return email


def badge(pid):
    db.mentor_badges.update_one({"person_id": pid}, {"$set": {"person_id": pid, "active": True, "created_at": now}}, upsert=True)


out = {"password": PASSWORD, "tag": tag}
out["mentor_a"] = person("T1MentorA"); out["mentor_a_email"] = user("MentorA", out["mentor_a"]); badge(out["mentor_a"])
out["mentor_b_noaccount"] = person("T1MentorB"); badge(out["mentor_b_noaccount"])
out["mentor_c_group"] = person("T1MentorC"); out["mentor_c_email"] = user("MentorC", out["mentor_c_group"]); badge(out["mentor_c_group"])
out["mentor_d_busy"] = person("T1MentorD"); out["mentor_d_email"] = user("MentorD", out["mentor_d_busy"]); badge(out["mentor_d_busy"])
out["no_badge"] = person("T1SinInsignia")
parent, child = str(uuid.uuid4()), str(uuid.uuid4())
for gid, name, anc in ((parent, f"QA T1 Rama {tag}", []), (child, f"QA T1 SubRama {tag}", [parent])):
    db.front_groups.insert_one({"_id": gid, "front_group_id": gid, "name": name, "display_name": name, "status": "active", "ancestor_group_ids": anc,
                                "parent_group_id": anc[0] if anc else None, "created_at": now, "updated_at": now})
_aid = str(uuid.uuid4()); db.front_group_assignments.insert_one({"_id": _aid, "assignment_id": _aid, "front_group_id": child, "person_id": out["mentor_c_group"], "active": True, "role": "member", "created_at": now})
out["group_parent"], out["group_child"] = parent, child
json.dump(out, open("/tmp/t1_add_mentors_seed.json", "w"), indent=1)
print(json.dumps(out, indent=1))
