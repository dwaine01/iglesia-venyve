# Seed QA data for UI testing of Invasiones + Mis Discípulos (iteration 37). Writes /tmp/outreach_ui_seed.json
import json
import os
import uuid
from datetime import datetime, timezone

import sys
sys.path.insert(0, "/app/backend")
import bcrypt
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
PW = "QaOutreachUI37!"
now = datetime.now(timezone.utc)


def person(label):
    pid = ObjectId()
    db.persons.insert_one({"_id": pid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "QA", "apellido": label,
                           "idempotency_key": f"qa:outreachui37:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
    return str(pid)


def badge(pid):
    db.mentor_badges.update_one({"person_id": pid}, {"$set": {"person_id": pid, "active": True, "since": "2026-01-01", "updated_at": now}}, upsert=True)


login = requests.post(f"{BASE}/api/auth/login", json={"email": "coreqa.pastor@example.com", "password": "CoreQA2026!Pastor"})
assert login.status_code == 200, login.text
ph = {"Authorization": f"Bearer {login.json()['token']}"}

out = {}
for key in ["A", "B"]:
    email = f"qa.outreachui37.mentor{key.lower()}@example.com"
    existing = db.users.find_one({"email": email})
    if existing:
        out[f"mentor_{key}"] = {"person_id": existing["person_id"], "email": email}
        continue
    pid = person(f"MentorUI37 {key}")
    badge(pid)
    email = f"qa.outreachui37.mentor{key.lower()}@example.com"
    r = requests.post(f"{BASE}/api/core/governance/users", headers=ph, json={"person_id": pid, "email": email, "temporary_password": "TempPass37!x", "access_level": "persona", "mentor_access": True})
    assert r.status_code == 201, r.text
    lg = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": "TempPass37!x"}).json()
    ch = requests.post(f"{BASE}/api/auth/change-password", headers={"Authorization": f"Bearer {lg['token']}"}, json={"current_password": "TempPass37!x", "new_password": PW})
    assert ch.status_code == 200, ch.text
    out[f"mentor_{key}"] = {"person_id": pid, "email": email}

# Mentor with badge but no account (should appear as "(sin acceso)")
nopid = person("MentorUI37 SinCuenta")
badge(nopid)
out["mentor_noaccess_pid"] = nopid

# Leader with outreach.assign (not pastor/coord general)
from access_control import access_defaults_for_role  # noqa: E402
lpid = person("LiderUI37")
badge(lpid)
d = access_defaults_for_role("lider")
d["capabilities"] = sorted(set(d.get("capabilities", []) + ["mentorship.outreach.assign"]))
lemail = "qa.outreachui37.lider@example.com"
db.users.insert_one({"_id": ObjectId(), "nombre": "QA LiderUI37", "email": lemail, "person_id": lpid,
                     "password": bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode(), "rol": "lider", "is_active": True,
                     "token_version": 1, "created_at": now, **d})
out["leader"] = {"person_id": lpid, "email": lemail}
out["password"] = PW
json.dump(out, open("/tmp/outreach_ui_seed.json", "w"), indent=1)
print(json.dumps(out, indent=1))
