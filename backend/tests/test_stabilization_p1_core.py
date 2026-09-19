import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from bson import ObjectId
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from canonical_identity import IdentityConflictError, ensure_user_person_link
from core_governance import AccessUpdate, update_user_access
from finance_engine import create_journal
from seed_user import validate_seed_environment


PREFIX = "stabilization.p1."
PASSWORD = "StabilizationP1!"


async def make_user(role="pastor", email=None):
    user_id = ObjectId(); email = email or f"{PREFIX}{uuid.uuid4().hex[:8]}@example.com"
    doc = {"_id": user_id, "nombre": "QA P1", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(), "rol": role, "is_active": True, "token_version": 1, **access_defaults_for_role(role)}
    await server.db.users.insert_one(doc); return doc


async def login(email):
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client, {"Authorization": f"Bearer {response.json()['token']}"}


async def cleanup():
    users = await server.db.users.find({"email": {"$regex": f"^{PREFIX}"}}, {"_id": 1}).to_list(100)
    user_ids = [str(item["_id"]) for item in users]
    people = await server.db.persons.find({"idempotency_key": {"$regex": "^stabilization:p1:"}}, {"_id": 1}).to_list(2000)
    person_ids = [str(item["_id"]) for item in people]
    await server.db.person_contacts.delete_many({"person_id": {"$in": person_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [item["_id"] for item in people]}})
    await server.db.identity_conflicts.delete_many({"$or": [{"source_id": {"$in": user_ids}}, {"match_value": {"$regex": f"^{PREFIX}"}}]})
    await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})
    entries = await server.db.finance_journal_entries.find({"source_type": "stabilization_concurrency"}, {"_id": 0, "entry_id": 1, "entry_number": 1}).to_list(1000)
    await server.db.finance_entry_number_registry.delete_many({"entry_id": {"$in": [item["entry_id"] for item in entries]}})
    await server.db.finance_audit_events.delete_many({"entity_id": {"$in": [item["entry_id"] for item in entries]}})
    await server.db.finance_journal_entries.delete_many({"source_type": "stabilization_concurrency"})
    await server.db.finance_accounts.delete_many({"name": {"$regex": "^STABILIZATION P1"}}); await server.db.finance_funds.delete_many({"name": {"$regex": "^STABILIZATION P1"}})
    await server.db.invite_codes.delete_many({"code": {"$regex": "^STABP1"}})


@pytest.mark.asyncio
async def test_ambiguous_identity_records_conflict_without_third_person():
    await cleanup(); email = f"{PREFIX}ambiguous@example.com"; user = await make_user("persona", email)
    now = datetime.now(timezone.utc); people = []
    for index in range(2):
        person_id = ObjectId(); people.append(person_id)
        await server.db.persons.insert_one({"_id": person_id, "person_number": f"VV-STABAMB{index}", "nombre": "Persona", "apellido": f"Duplicada {index}", "search_key": f"persona duplicada {index}", "idempotency_key": f"stabilization:p1:ambiguous:{index}", "version": 1, "created_at": now, "updated_at": now})
        await server.db.person_contacts.insert_one({"_id": str(uuid.uuid4()), "person_id": str(person_id), "tipo": "email", "valor": email, "es_principal": True})
    try:
        before = await server.db.persons.count_documents({})
        with pytest.raises(IdentityConflictError) as caught:
            await ensure_user_person_link(server.db, str(user["_id"]), str(user["_id"]))
        assert await server.db.persons.count_documents({}) == before
        conflict = await server.db.identity_conflicts.find_one({"conflict_id": caught.value.conflict_id}, {"_id": 0})
        assert conflict["status"] == "open" and set(conflict["candidate_person_ids"]) == {str(item) for item in people}
    finally: await cleanup()


@pytest.mark.asyncio
async def test_directory_search_finds_person_after_first_500_and_paginates():
    await cleanup(); pastor = await make_user(); now = datetime.now(timezone.utc); docs = []
    for index in range(520):
        person_id = ObjectId(); special = index == 519
        docs.append({"_id": person_id, "person_number": f"VV-STAB{index:04d}", "nombre": "ZetaNeedle" if special else f"Persona{index:04d}", "apellido": "Final" if special else "Carga", "search_key": "zetaneedle final" if special else f"persona{index:04d} carga", "idempotency_key": f"stabilization:p1:directory:{index}", "created_by": str(pastor["_id"]), "version": 1, "created_at": now, "updated_at": now})
    await server.db.persons.insert_many(docs); client, headers = await login(pastor["email"])
    try:
        exact = await client.get("/api/core/persons/directory/search", params={"q": "ZetaNeedle", "limit": 10, "page": 1}, headers=headers)
        assert exact.status_code == 200, exact.text
        assert exact.json()["total"] == 1 and exact.json()["items"][0]["person_number"] == "VV-STAB0519"
        paged = await client.get("/api/core/persons/directory/search", params={"q": "Persona", "limit": 100, "page": 6}, headers=headers)
        assert paged.status_code == 200 and paged.json()["total"] >= 519 and len(paged.json()["items"]) > 0
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_finance_entry_numbers_are_atomic_under_concurrency():
    await cleanup(); account_a, account_b, fund_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.finance_accounts.insert_many([{"_id": account_a, "account_id": account_a, "code": f"STAB-D-{uuid.uuid4().hex[:8]}", "name": "STABILIZATION P1 DEBIT", "active": True}, {"_id": account_b, "account_id": account_b, "code": f"STAB-C-{uuid.uuid4().hex[:8]}", "name": "STABILIZATION P1 CREDIT", "active": True}])
    await server.db.finance_funds.insert_one({"_id": fund_id, "fund_id": fund_id, "code": f"STAB-F-{uuid.uuid4().hex[:8]}", "name": "STABILIZATION P1 FUND", "active": True})
    lines = [{"account_id": account_a, "fund_id": fund_id, "debit_cents": 100, "credit_cents": 0}, {"account_id": account_b, "fund_id": fund_id, "debit_cents": 0, "credit_cents": 100}]
    try:
        entries = await asyncio.gather(*[create_journal("stabilization", "2026-09-19", f"Concurrente {index}", "stabilization_concurrency", str(index), lines) for index in range(25)])
        numbers = [item["entry_number"] for item in entries]
        assert len(numbers) == len(set(numbers)) == 25
        assert await server.db.finance_entry_number_registry.count_documents({"entry_id": {"$in": [item["entry_id"] for item in entries]}}) == 25
    finally: await cleanup()


@pytest.mark.asyncio
async def test_rbac_rejects_valid_but_non_customizable_capability():
    await cleanup(); pastor = await make_user(); target = await make_user("lider")
    current = {**pastor, "user_id": str(pastor["_id"]), "access_level": "pastor"}
    try:
        with pytest.raises(HTTPException) as caught:
            await update_user_access(str(target["_id"]), AccessUpdate(access_level="lider", is_active=True, capabilities=["finance.read"], privilege_groups=[]), current)
        assert caught.value.status_code == 400 and "no personalizables" in str(caught.value.detail)
        unchanged = await server.db.users.find_one({"_id": target["_id"]}, {"_id": 0, "capabilities": 1})
        assert "finance.read" not in unchanged.get("capabilities", [])
    finally: await cleanup()


@pytest.mark.asyncio
async def test_invitation_without_expiry_registers_without_500():
    await cleanup(); code = f"STABP1{uuid.uuid4().hex[:10].upper()}"; email = f"{PREFIX}invite@example.com"
    await server.db.invite_codes.insert_one({"code": code, "created_by_user_id": "stabilization", "created_by_rol": "lider", "role_to_assign": "persona", "leader_id_to_assign": None, "created_at": datetime.now(timezone.utc), "expires_at": None, "used_at": None, "used_by_user_id": None})
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    try:
        response = await client.post("/api/auth/register", json={"nombre": "Invitado Permanente", "email": email, "password": PASSWORD, "invite_code": code})
        assert response.status_code == 200, response.text
        user = await server.db.users.find_one({"email": email}, {"_id": 0, "person_id": 1})
        assert user and user.get("person_id")
        person_id = user["person_id"]
        await server.db.person_contacts.delete_many({"person_id": person_id}); await server.db.persons.delete_one({"_id": ObjectId(person_id)})
    finally:
        await client.aclose(); await cleanup()


@pytest.mark.asyncio
async def test_ambiguous_registration_rolls_back_user_and_invite_and_expired_stays_rejected():
    await cleanup(); email = f"{PREFIX}register.ambiguous@example.com"; now = datetime.now(timezone.utc)
    for index in range(2):
        person_id = ObjectId()
        await server.db.persons.insert_one({"_id": person_id, "person_number": f"VV-STABREG{index}", "nombre": "Registro", "apellido": f"Ambiguo {index}", "search_key": f"registro ambiguo {index}", "idempotency_key": f"stabilization:p1:register:{index}", "version": 1, "created_at": now, "updated_at": now})
        await server.db.person_contacts.insert_one({"_id": str(uuid.uuid4()), "person_id": str(person_id), "tipo": "email", "valor": email, "es_principal": True})
    code = f"STABP1{uuid.uuid4().hex[:10].upper()}"; expired_code = f"STABP1{uuid.uuid4().hex[:10].upper()}"
    await server.db.invite_codes.insert_many([
        {"code": code, "created_by_user_id": "stabilization", "role_to_assign": "persona", "created_at": now, "expires_at": None, "used_at": None},
        {"code": expired_code, "created_by_user_id": "stabilization", "role_to_assign": "persona", "created_at": now, "expires_at": now - timedelta(minutes=1), "used_at": None},
    ])
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    try:
        conflict = await client.post("/api/auth/register", json={"nombre": "Registro Ambiguo", "email": email, "password": PASSWORD, "invite_code": code})
        assert conflict.status_code == 409, conflict.text
        assert await server.db.users.count_documents({"email": email}) == 0
        invite = await server.db.invite_codes.find_one({"code": code}, {"_id": 0})
        assert invite.get("used_at") is None and invite.get("used_by_user_id") is None
        assert await server.db.persons.count_documents({"idempotency_key": {"$regex": "^stabilization:p1:register:"}}) == 2
        assert await server.db.identity_conflicts.count_documents({"match_value": email, "status": "open"}) == 1
        expired = await client.post("/api/auth/register", json={"nombre": "Registro Vencido", "email": f"{PREFIX}expired@example.com", "password": PASSWORD, "invite_code": expired_code})
        assert expired.status_code == 400 and "caducado" in expired.text.lower()
    finally:
        await client.aclose(); await cleanup()


def test_seed_user_is_blocked_in_production_and_has_no_fixed_credentials(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production"); monkeypatch.setenv("ALLOW_DEV_SEED", "true")
    monkeypatch.setenv("DEV_SEED_EMAIL", "admin@venyve.com"); monkeypatch.setenv("DEV_SEED_PASSWORD", "admin123")
    monkeypatch.setenv("DEV_SEED_NAME", "Unsafe"); monkeypatch.setenv("DEV_SEED_ROLE", "lider")
    with pytest.raises(RuntimeError, match="bloqueado"):
        validate_seed_environment()