# Seed for iteration 38 retest: QA person with active Mentor badge (NO account yet) -> /tmp/iter38_seed.json
import json
import os
import uuid
from datetime import datetime, timezone

import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
now = datetime.now(timezone.utc)

login = requests.post(f"{BASE}/api/auth/login", json={"email": "coreqa.pastor@example.com", "password": "CoreQA2026!Pastor"})
assert login.status_code == 200, login.text
ph = {"Authorization": f"Bearer {login.json()['token']}"}

out = {}
for key in ["Real", "Otro"]:
    pid = ObjectId()
    db.persons.insert_one({"_id": pid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "QA", "apellido": f"Mentor38 {key}",
                           "idempotency_key": f"qa:iter38:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
    r = requests.put(f"{BASE}/api/mentorship/badge/{pid}", headers=ph, json={"active": True, "since": "2026-01-01"})
    assert r.status_code == 200, r.text
    out[key] = str(pid)
json.dump(out, open("/tmp/iter38_seed.json", "w"))
print(out)
