# Probe for atomicity bugs: (a) partial MCD delivery when NPT fails in same PUT, (b) partial account creation on 422
import os, uuid
from datetime import datetime, timezone
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv("/app/frontend/.env"); load_dotenv("/app/backend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/"); API = f"{BASE}/api/mentorship/outreach"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
def login(e, p): return {"Authorization": "Bearer " + requests.post(f"{BASE}/api/auth/login", json={"email": e, "password": p}).json()["token"]}
pastor = login("coreqa.pastor@example.com", "CoreQA2026!Pastor")
con = login("qa.e2e.con.b042@example.com", "QaE2EMentorCon456!")
camp = db.outreach_campaigns.find_one({"name": "QAE2E Invasion B042"})
cid = camp["campaign_id"]; con_pid = "6adadbb88349a486ef28f515"
con_uid = str(db.users.find_one({"person_id": con_pid})["_id"])
mcd = db.library_books.find_one({"sku": "MCD"})["book_id"]
r = requests.post(f"{API}/campaigns/{cid}/books", headers=pastor, json={"assignments": [{"mentor_person_id": con_pid, "book_id": mcd, "quantity": 2}]})
print("assign MCD to con:", r.status_code)
def on_hand(): return (db.library_holdings.find_one({"book_id": mcd, "holder_type": "user", "holder_id": con_uid}) or {}).get("quantity_on_hand")
print("con MCD on_hand before:", on_hand())
v = requests.post(f"{API}/visits", headers=con, json={"contact_type": "new", "contact_name": "QAE2E Casa Atomic", "contact_phone": "7875559911", "campaign_id": cid}).json()
vid = v["visit_id"]
r1 = requests.put(f"{API}/visits/{vid}/report", headers=con, json={"status": "visited", "received_mcd": True, "received_npt": True})
print("PUT mcd+npt:", r1.status_code, r1.text[:160])
print("con MCD on_hand after failed PUT:", on_hand(), "visit mcd_movement:", db.outreach_visits.find_one({"visit_id": vid}).get("mcd_delivery_movement_id"))
r2 = requests.put(f"{API}/visits/{vid}/report", headers=con, json={"status": "visited", "received_mcd": True})
print("PUT mcd only:", r2.status_code, "on_hand:", on_hand())
print("DELIVERY movements for con in campaign:", db.library_movements.count_documents({"campaign_id": cid, "movement_type": "DELIVERY", "from_holder.id": con_uid}))

# (b) partial account creation
now = datetime.now(timezone.utc); pids = []
for n in ("AtomA", "AtomB"):
    oid = ObjectId(); db.persons.insert_one({"_id": oid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "QAE2E", "apellido": n, "idempotency_key": str(uuid.uuid4()), "version": 1, "created_at": now, "updated_at": now})
    pids.append(str(oid)); requests.put(f"{BASE}/api/mentorship/badge/{oid}", json={"active": True}, headers=pastor)
r = requests.post(f"{API}/campaigns", headers=pastor, json={"name": "QAE2E Atom", "location": "X", "start_date": "2026-02-01", "end_date": "2026-02-02",
    "assigned_mentors": [{"person_id": pids[0], "email": f"qa.e2e.atoma.{uuid.uuid4().hex[:4]}@example.com", "temporary_password": "QaAtomTemp123!"}, {"person_id": pids[1]}]})
print("create campaign A(creds)+B(no creds):", r.status_code, r.text[:140])
print("account created for A despite 422?:", bool(db.users.find_one({"person_id": pids[0]})))
