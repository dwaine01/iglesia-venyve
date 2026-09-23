"""Startup must reconcile stale membership-number ownership without taking down the API."""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import server
from membership_documents import ensure_membership_documents


db = server.db


def test_startup_reconciles_stale_registry_owner():
    suffix = uuid4().hex[:10].upper()
    person_id = f"qa-registry-{suffix}"
    membership_id = str(uuid4())
    old_number = f"OLD-{suffix}"
    current_number = f"NEW-{suffix}"
    now = datetime.now(timezone.utc)

    async def scenario():
        try:
            await db.person_memberships.insert_one({
                "_id": membership_id,
                "membership_id": membership_id,
                "person_id": person_id,
                "member_number": current_number,
                "status": "active",
                "legacy_membership": True,
                "created_at": now,
                "updated_at": now,
            })
            await db.membership_number_registry.insert_one({
                "_id": old_number,
                "member_number": old_number,
                "person_id": person_id,
                "reserved_at": now,
                "source": "qa_stale_registry",
            })

            await ensure_membership_documents()

            reconciled = await db.membership_number_registry.find_one({"person_id": person_id}, {"_id": 0})
            assert reconciled["member_number"] == current_number
            assert await db.membership_number_registry.count_documents({"person_id": person_id}) == 1

            await ensure_membership_documents()
            assert await db.membership_number_registry.count_documents({"person_id": person_id}) == 1
        finally:
            await db.membership_number_registry.delete_many({"person_id": person_id})
            await db.person_memberships.delete_many({"person_id": person_id})

    asyncio.run(scenario())