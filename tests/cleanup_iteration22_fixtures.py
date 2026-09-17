import json
from pathlib import Path

from bson import ObjectId

import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import server  # noqa: E402


async def main():
    fixture_file = ROOT / "tests" / "iteration22_fixture.json"
    if not fixture_file.exists():
        print('{"removed": false, "reason": "fixture_missing"}')
        return

    payload = json.loads(fixture_file.read_text(encoding="utf-8"))
    prefix = payload.get("prefix", "t1i22")

    users = await server.db.users.find(
        {
            "$or": [
                {"email": {"$regex": f"^{prefix}"}},
                {"email": {"$regex": "^qa\\.demo\\."}},
            ]
        },
        {"_id": 1, "person_id": 1},
    ).to_list(300)
    person_ids = {item.get("person_id") for item in users if item.get("person_id")}
    person_ids.update(
        [
            payload.get("real_person_id"),
            payload.get("qa_person_id"),
        ]
    )
    person_ids = {item for item in person_ids if item}

    if person_ids:
        await server.db.person_contacts.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.person_memberships.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.person_activity.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.users.delete_many({"person_id": {"$in": list(person_ids)}})
        valid = [ObjectId(item) for item in person_ids if ObjectId.is_valid(item)]
        if valid:
            await server.db.persons.delete_many({"_id": {"$in": valid}})

    if users:
        await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})

    await server.db.finance_settings.update_many(
        {"updated_by_user_id": payload.get("qa_user_id")},
        {"$unset": {"updated_by_user_id": ""}},
    )
    remaining_people = await server.db.persons.count_documents(
        {
            "$or": [
                {"person_number": {"$regex": "^T1I22"}},
                {"nombre": {"$regex": "^T1I22"}},
                {"nombre": {"$regex": "^QA Muestra"}},
            ]
        }
    )
    remaining_users = await server.db.users.count_documents(
        {
            "$or": [
                {"email": {"$regex": "^t1i22\\."}},
                {"email": {"$regex": "^qa\\.demo\\."}},
            ]
        }
    )

    fixture_file.unlink(missing_ok=True)
    print(json.dumps({"removed": True, "remaining_people": remaining_people, "remaining_users": remaining_users}))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
