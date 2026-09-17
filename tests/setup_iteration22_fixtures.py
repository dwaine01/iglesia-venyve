import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from bson import ObjectId

import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import server  # noqa: E402
from access_control import access_defaults_for_role  # noqa: E402


async def cleanup(prefix: str):
    await server.db.login_attempts.delete_many({"identifier": {"$regex": prefix}})
    users = await server.db.users.find(
        {"email": {"$regex": f"^{prefix}"}},
        {"_id": 1, "person_id": 1},
    ).to_list(200)
    people = await server.db.persons.find(
        {
            "$or": [
                {"person_number": {"$regex": f"^{prefix.upper()}"}},
                {"nombre": {"$regex": f"^{prefix.upper()}"}},
            ]
        },
        {"_id": 1},
    ).to_list(200)
    person_ids = {str(item["_id"]) for item in people}
    person_ids.update(item.get("person_id") for item in users if item.get("person_id"))
    valid_person_oids = [ObjectId(pid) for pid in person_ids if ObjectId.is_valid(pid)]
    if person_ids:
        await server.db.person_contacts.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.person_memberships.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.person_activity.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.users.delete_many({"person_id": {"$in": list(person_ids)}})
    if valid_person_oids:
        await server.db.persons.delete_many({"_id": {"$in": valid_person_oids}})
    if users:
        await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})


async def main():
    suffix = uuid.uuid4().hex[:8]
    prefix = f"t1i22.{suffix}"
    await cleanup("t1i22")

    now = datetime.now(timezone.utc)
    password = "T1I22Pass!123"

    pastor_id = ObjectId()
    leader_id = ObjectId()
    real_person_id = ObjectId()
    qa_person_id = ObjectId()
    qa_user_id = ObjectId()

    pastor_email = f"{prefix}.pastor@example.com"
    leader_email = f"{prefix}.leader@example.com"
    qa_email = f"qa.demo.{suffix}@example.com"

    await server.db.users.insert_many([
        {
            "_id": pastor_id,
            "nombre": f"T1I22 Pastor {suffix}",
            "email": pastor_email,
            "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            "rol": "pastor",
            "is_active": True,
            "token_version": 1,
            **access_defaults_for_role("pastor"),
        },
        {
            "_id": leader_id,
            "nombre": f"T1I22 Lider {suffix}",
            "email": leader_email,
            "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            "rol": "lider",
            "is_active": True,
            "token_version": 1,
            **access_defaults_for_role("lider"),
        },
        {
            "_id": qa_user_id,
            "nombre": f"QA Demo {suffix}",
            "email": qa_email,
            "password": "not-used",
            "rol": "persona",
            "person_id": str(qa_person_id),
            "is_active": True,
            "token_version": 1,
        },
    ])

    await server.db.persons.insert_many([
        {
            "_id": real_person_id,
            "person_number": f"T1I22REAL{suffix[:4]}",
            "nombre": f"T1I22REAL-{suffix}",
            "apellido": "Conservada",
            "search_key": f"t1i22real {suffix}",
            "version": 1,
            "created_at": now,
            "updated_at": now,
        },
        {
            "_id": qa_person_id,
            "person_number": f"T1I22QA{suffix[:4]}",
            "nombre": f"QA Muestra {suffix}",
            "apellido": "Temporal",
            "search_key": f"qa muestra {suffix}",
            "idempotency_key": f"qa:{suffix}",
            "version": 1,
            "created_by": str(qa_user_id),
            "created_at": now,
            "updated_at": now,
        },
    ])

    await server.db.person_contacts.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "person_id": str(qa_person_id),
            "tipo": "email",
            "valor": f"qa.{suffix}@example.com",
            "created_at": now,
            "updated_at": now,
        }
    )

    await server.db.finance_settings.update_one(
        {"_id": "primary"},
        {"$set": {"updated_by_user_id": str(qa_user_id), "currency": "DOP"}},
        upsert=True,
    )

    payload = {
        "prefix": prefix,
        "password": password,
        "pastor_email": pastor_email,
        "leader_email": leader_email,
        "real_person_id": str(real_person_id),
        "qa_person_id": str(qa_person_id),
        "qa_user_id": str(qa_user_id),
    }
    out_file = ROOT / "tests" / "iteration22_fixture.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
