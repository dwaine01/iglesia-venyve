import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role


def now_utc():
    return datetime.now(timezone.utc)


async def cleanup_spec_artifacts():
    users = await server.db.users.find(
        {"email": {"$regex": "^(cleanup\\.(actor|leader)|qa\\.demo)\\."}},
        {"_id": 1, "person_id": 1},
    ).to_list(100)
    people = await server.db.persons.find(
        {"person_number": {"$regex": "^VV-(REAL|QA)"}},
        {"_id": 1},
    ).to_list(100)
    person_ids = {str(item["_id"]) for item in people}
    person_ids.update(item.get("person_id") for item in users if item.get("person_id"))
    if person_ids:
        await server.db.person_contacts.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in person_ids if ObjectId.is_valid(item)]}})
    if users:
        await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})


@pytest.mark.asyncio
async def test_pastor_cleans_qa_demo_and_preserves_real_records():
    await cleanup_spec_artifacts()
    suffix = uuid.uuid4().hex[:8]
    actor_id = ObjectId()
    actor_email = f"cleanup.actor.{suffix}@iglesiavenyve.org"
    real_person_id = ObjectId()
    qa_person_id = ObjectId()
    qa_user_id = ObjectId()
    now = now_utc()
    await server.db.users.insert_one({
        "_id": actor_id,
        "nombre": "Pastor Limpieza",
        "email": actor_email,
        "password": bcrypt.hashpw(b"CleanupPass123!", bcrypt.gensalt()).decode(),
        "rol": "pastor",
        "is_active": True,
        "token_version": 1,
        **access_defaults_for_role("pastor"),
    })
    await server.db.persons.insert_many([
        {"_id": real_person_id, "person_number": f"VV-REAL{suffix[:6]}", "nombre": "Persona", "apellido": "Conservada", "version": 1, "created_at": now, "updated_at": now},
        {"_id": qa_person_id, "person_number": f"VV-QA{suffix[:6]}", "nombre": "QA Muestra", "apellido": suffix, "idempotency_key": f"qa:{suffix}", "version": 1, "created_by": str(qa_user_id), "created_at": now, "updated_at": now},
    ])
    await server.db.users.insert_one({
        "_id": qa_user_id,
        "nombre": "QA Cuenta",
        "email": f"qa.demo.{suffix}@example.com",
        "password": "not-used",
        "rol": "persona",
        "person_id": str(qa_person_id),
        "is_active": True,
        "token_version": 1,
    })
    await server.db.person_contacts.insert_one({"_id": str(uuid.uuid4()), "person_id": str(qa_person_id), "tipo": "email", "valor": f"qa.{suffix}@example.com"})
    await server.db.finance_settings.update_one({"_id": "primary"}, {"$set": {"updated_by_user_id": str(qa_user_id)}}, upsert=True)
    try:
        async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as client:
            login = await client.post("/api/auth/login", json={"email": actor_email, "password": "CleanupPass123!"})
            assert login.status_code == 200, login.text
            headers = {"Authorization": f"Bearer {login.json()['token']}"}
            summary = await client.get("/api/core/persons/qa-demo/summary", headers=headers)
            assert summary.status_code == 200
            assert summary.json()["qa_persons"] >= 1
            cleaned = await client.delete("/api/core/persons/qa-demo", headers=headers)
            assert cleaned.status_code == 200, cleaned.text
            assert cleaned.json()["deleted_documents"] >= 3
        assert await server.db.persons.find_one({"_id": qa_person_id}) is None
        assert await server.db.users.find_one({"_id": qa_user_id}) is None
        assert await server.db.person_contacts.find_one({"person_id": str(qa_person_id)}) is None
        assert await server.db.persons.find_one({"_id": real_person_id}) is not None
        settings = await server.db.finance_settings.find_one({"_id": "primary"})
        assert "updated_by_user_id" not in settings
    finally:
        await cleanup_spec_artifacts()


@pytest.mark.asyncio
async def test_non_pastor_cannot_preview_or_clean_qa_demo():
    await cleanup_spec_artifacts()
    user_id = ObjectId()
    email = f"cleanup.leader.{uuid.uuid4().hex[:8]}@iglesiavenyve.org"
    await server.db.users.insert_one({
        "_id": user_id,
        "nombre": "Lider Limpieza",
        "email": email,
        "password": bcrypt.hashpw(b"CleanupPass123!", bcrypt.gensalt()).decode(),
        "rol": "lider",
        "is_active": True,
        "token_version": 1,
        **access_defaults_for_role("lider"),
    })
    try:
        async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as client:
            login = await client.post("/api/auth/login", json={"email": email, "password": "CleanupPass123!"})
            assert login.status_code == 200, login.text
            headers = {"Authorization": f"Bearer {login.json()['token']}"}
            assert (await client.get("/api/core/persons/qa-demo/summary", headers=headers)).status_code == 403
            assert (await client.delete("/api/core/persons/qa-demo", headers=headers)).status_code == 403
    finally:
        await cleanup_spec_artifacts()