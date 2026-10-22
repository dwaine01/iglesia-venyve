# Seed QA users for outreach re-test (iteration 32): mentor A (badge, no LBS), mentor B (badge + LBS), leader (outreach.assign)
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from bson import ObjectId

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from access_control import access_defaults_for_role, MENTORSHIP_OUTREACH_ASSIGN  # noqa: E402

PASSWORD = "QaOutreach32!"


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    out = {"password": PASSWORD}
    for label, role, badge, lbs, caps in [
        ("mentora", "persona", True, False, []),
        ("mentorb", "persona", True, True, []),
        ("leader", "lider", False, False, [MENTORSHIP_OUTREACH_ASSIGN]),
    ]:
        email = f"qa.outreach32.{label}@example.com"
        existing = await db.users.find_one({"email": email})
        if existing:
            out[label] = {"email": email, "person_id": existing.get("person_id")}
            continue
        pid = ObjectId()
        await db.persons.insert_one({
            "_id": pid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "QA",
            "apellido": f"Outreach32 {label}", "search_key": f"qa outreach32 {label}",
            "idempotency_key": f"qa:outreach32:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now,
        })
        defaults = access_defaults_for_role(role)
        defaults["capabilities"] = sorted(set(defaults.get("capabilities", []) + caps))
        await db.users.insert_one({
            "nombre": f"QA Outreach32 {label}", "email": email,
            "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "rol": role, "is_active": True, "token_version": 1, "created_at": now, "person_id": str(pid), **defaults,
        })
        if badge:
            await db.mentor_badges.update_one({"person_id": str(pid)}, {"$set": {"person_id": str(pid), "active": True, "since": "2026-01-01", "updated_at": now}}, upsert=True)
        if lbs:
            await db.mentor_qualifications.update_one({"person_id": str(pid), "front_group_id": None}, {"$set": {"person_id": str(pid), "front_group_id": None, "active": True, "can_teach_lbs": True, "archived": False}}, upsert=True)
        out[label] = {"email": email, "person_id": str(pid)}
    # Person 360 with a long name for fuzzy-merge test (FIX 6)
    key = "zelindaqa quorvat gomez"
    p = await db.persons.find_one({"search_key": key})
    if not p:
        r = await db.persons.insert_one({
            "nombre": "Zelindaqa", "apellido": "Quorvat Gomez", "search_key": key,
            "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "idempotency_key": f"qa:outreach32:{uuid.uuid4()}",
            "version": 1, "created_at": now, "updated_at": now,
        })
        out["long_name_person_id"] = str(r.inserted_id)
    else:
        out["long_name_person_id"] = str(p["_id"])
    print(json.dumps(out))


asyncio.run(main())
