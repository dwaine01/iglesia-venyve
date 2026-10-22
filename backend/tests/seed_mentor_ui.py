import os, uuid, json, sys
from datetime import datetime, timezone
import requests
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv("/app/backend/.env"); load_dotenv("/app/frontend/.env")
B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
d = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
if sys.argv[1:] == ["cleanup"]:
    ids = [str(p["_id"]) for p in d.persons.find({"nombre": "TESTMentorUI"})]
    for col in ("mentor_badges", "mentor_badge_history", "mentor_assignments", "process_enrollments", "process_stage_progress"):
        d[col].delete_many({"person_id": {"$in": ids}})
    d.mentor_assignments.delete_many({"mentor_person_id": {"$in": ids}})
    d.persons.delete_many({"nombre": "TESTMentorUI"}); print("cleaned", len(ids)); sys.exit()
h = {"Authorization": "Bearer " + requests.post(f"{B}/api/auth/login", json={"email": "coreqa.pastor@example.com", "password": "CoreQA2026!Pastor"}).json()["token"]}
def mk(label):
    pid = ObjectId()
    d.persons.insert_one({"_id": pid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "TESTMentorUI", "apellido": label,
        "idempotency_key": f"qa:mentorui:{uuid.uuid4()}", "version": 1, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    return str(pid)
noacc = mk("SinCuenta"); cand = mk("Visitante")
print(requests.put(f"{B}/api/mentorship/badge/{noacc}", json={"active": True}, headers=h).status_code)
member = d.users.find_one({"email": "coreqa.member@example.com"})
print("member badge", requests.put(f"{B}/api/mentorship/badge/{member['person_id']}", json={"active": True}, headers=h).status_code)
r = requests.post(f"{B}/api/processes/consolidation/intakes", json={"person_id": cand, "entry_mode": "visitor_followup"}, headers=h)
print(r.status_code, r.text[:300])
print(json.dumps({"noacc": noacc, "cand": cand, "member_pid": member["person_id"], "enrollment": (r.json().get("enrollment_id") or r.json().get("enrollment", {}).get("enrollment_id")) if r.ok else None}))
