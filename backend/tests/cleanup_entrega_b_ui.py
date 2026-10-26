"""Cleanup of seed_entrega_b_ui.py / test_entrega_b_public_api.py artifacts (qa.entregab.t41.* users)."""
import os
import re
from dotenv import dotenv_values
from pymongo import MongoClient

env = {**os.environ, **dotenv_values("/app/backend/.env")}
db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
users = list(db.users.find({"email": {"$regex": r"^qa\.entregab\.t41\."}}, {"_id": 1, "person_id": 1}))
pids = [u.get("person_id") for u in users if u.get("person_id")]
uids = [str(u["_id"]) for u in users]
enrs = [e["enrollment_id"] for e in db.process_enrollments.find({"mentor_person_id": {"$in": pids}}, {"enrollment_id": 1, "person_id": 1})]
disciples = [e["person_id"] for e in db.process_enrollments.find({"enrollment_id": {"$in": enrs}}, {"person_id": 1})]
db.consolidation_activities.delete_many({"enrollment_id": {"$in": enrs}})
db.process_stage_progress.delete_many({"enrollment_id": {"$in": enrs}})
db.process_enrollments.delete_many({"enrollment_id": {"$in": enrs}})
db.mentor_badges.delete_many({"person_id": {"$in": pids}})
db.library_holdings.delete_many({"holder_type": "user", "holder_id": {"$in": uids}})
db.users.delete_many({"_id": {"$in": [u["_id"] for u in users]}})
from bson import ObjectId
db.persons.delete_many({"_id": {"$in": [ObjectId(p) for p in pids + disciples if ObjectId.is_valid(p)]}})
print(f"cleaned users={len(users)} enrollments={len(enrs)}")
