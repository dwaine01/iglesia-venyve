# Seed for E2E testing of Invasiones Entrega A: two badge mentors (one with account, one without)
import asyncio, os, json, uuid
from datetime import datetime, timezone
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')
load_dotenv('/app/frontend/.env')
BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]


async def mk_person(nombre, apellido):
    oid = ObjectId()
    now = datetime.now(timezone.utc)
    await db.persons.insert_one({"_id": oid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": nombre, "apellido": apellido,
                                 "search_key": f"{nombre} {apellido}".lower(), "idempotency_key": f"qa:e2e:{uuid.uuid4()}", "version": 1,
                                 "created_at": now, "updated_at": now})
    return str(oid)


async def main():
    tag = uuid.uuid4().hex[:4].upper()
    with_pid = await mk_person("QAE2E", f"MentorConCuenta{tag}")
    without_pid = await mk_person("QAE2E", f"MentorSinCuenta{tag}")
    s = requests.Session()
    tok = s.post(f"{BASE}/api/auth/login", json={"email": "coreqa.pastor@example.com", "password": "CoreQA2026!Pastor"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    for pid in (with_pid, without_pid):
        r = s.put(f"{BASE}/api/mentorship/badge/{pid}", json={"active": True}, headers=h)
        print("badge", r.status_code, r.text[:150])
    email_with = f"qa.e2e.con.{tag.lower()}@example.com"
    r = s.post(f"{BASE}/api/core/governance/users", json={"person_id": with_pid, "email": email_with, "temporary_password": "QaE2EMentor123!",
                                                         "access_level": "persona", "mentor_access": True}, headers=h)
    print("create user", r.status_code, r.text[:200])
    print(json.dumps({"tag": tag, "with_pid": with_pid, "without_pid": without_pid, "email_with": email_with}))

asyncio.run(main())
