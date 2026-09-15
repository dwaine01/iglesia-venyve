"""BASE-01 regression tests for revocable, versioned JWT authentication."""
import os
from datetime import timedelta
import uuid

import bcrypt
import jwt
import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ley7semanas_test_db")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

import server  # noqa: E402


@pytest_asyncio.fixture
async def auth_case():
    unique = uuid.uuid4().hex
    email = f"base01.{unique}@example.com"
    password = "Base01TestPass!"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    result = await server.db.users.insert_one({
        "nombre": "BASE-01 Existing User",
        "email": email,
        "password": hashed,
        "rol": "lider",
        # Intentionally omit is_active/token_version to prove logical defaults.
    })
    user_id = str(result.inserted_id)

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "email": email,
            "password": password,
            "user_id": user_id,
        }

    await server.db.contacts.delete_many({"user_id": user_id})
    await server.db.checklists.delete_many({"user_id": user_id})
    await server.db.progress.delete_many({"user_id": user_id})
    await server.db.users.delete_many({"email": email})


async def login(auth_case):
    response = await auth_case["client"].post(
        "/api/auth/login",
        json={"email": auth_case["email"], "password": auth_case["password"]},
    )
    return response


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_existing_active_user_login_emits_valid_versioned_token(auth_case):
    response = await login(auth_case)
    assert response.status_code == 200, response.text

    token = response.json()["token"]
    payload = server.verify_token(token)
    assert payload["user_id"] == auth_case["user_id"]
    assert payload["token_version"] == server.DEFAULT_TOKEN_VERSION

    me = await auth_case["client"].get("/api/auth/me", headers=bearer(token))
    assert me.status_code == 200, me.text
    assert me.json()["id"] == auth_case["user_id"]


@pytest.mark.asyncio
async def test_expired_and_invalid_tokens_are_rejected(auth_case):
    expired = server.create_token(
        auth_case["user_id"],
        auth_case["email"],
        "lider",
        server.DEFAULT_TOKEN_VERSION,
        expires_delta=timedelta(seconds=-1),
    )
    expired_response = await auth_case["client"].get(
        "/api/auth/me", headers=bearer(expired)
    )
    invalid_response = await auth_case["client"].get(
        "/api/auth/me", headers=bearer("not-a-jwt")
    )

    assert expired_response.status_code == 401
    assert invalid_response.status_code == 401


@pytest.mark.asyncio
async def test_legacy_token_without_version_is_rejected(auth_case):
    legacy_token = jwt.encode(
        {
            "user_id": auth_case["user_id"],
            "email": auth_case["email"],
            "rol": "lider",
            "exp": server.utc_now() + timedelta(minutes=5),
        },
        server.SECRET_KEY,
        algorithm=server.ALGORITHM,
    )

    response = await auth_case["client"].get(
        "/api/auth/me", headers=bearer(legacy_token)
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_nonexistent_and_malformed_user_ids_are_rejected(auth_case):
    nonexistent = server.create_token(
        str(ObjectId()),
        auth_case["email"],
        "lider",
        server.DEFAULT_TOKEN_VERSION,
    )
    malformed = server.create_token(
        "not-an-object-id",
        auth_case["email"],
        "lider",
        server.DEFAULT_TOKEN_VERSION,
    )

    nonexistent_response = await auth_case["client"].get(
        "/api/auth/me", headers=bearer(nonexistent)
    )
    malformed_response = await auth_case["client"].get(
        "/api/auth/me", headers=bearer(malformed)
    )

    assert nonexistent_response.status_code == 401
    assert malformed_response.status_code == 401


@pytest.mark.asyncio
async def test_is_active_false_revokes_access_and_blocks_login(auth_case):
    login_response = await login(auth_case)
    token = login_response.json()["token"]

    await server.db.users.update_one(
        {"_id": ObjectId(auth_case["user_id"])},
        {"$set": {"is_active": False}},
    )

    revoked = await auth_case["client"].get(
        "/api/auth/me", headers=bearer(token)
    )
    blocked_login = await login(auth_case)

    assert revoked.status_code == 401
    assert blocked_login.status_code == 401


@pytest.mark.asyncio
async def test_incremented_version_revokes_old_token_and_new_login_uses_current(auth_case):
    first_login = await login(auth_case)
    old_token = first_login.json()["token"]

    await server.db.users.update_one(
        {"_id": ObjectId(auth_case["user_id"])},
        {"$set": {"token_version": 2}},
    )

    revoked = await auth_case["client"].get(
        "/api/auth/me", headers=bearer(old_token)
    )
    second_login = await login(auth_case)
    new_token = second_login.json()["token"]
    new_payload = server.verify_token(new_token)
    accepted = await auth_case["client"].get(
        "/api/auth/me", headers=bearer(new_token)
    )

    assert revoked.status_code == 401
    assert second_login.status_code == 200
    assert new_payload["token_version"] == 2
    assert accepted.status_code == 200


@pytest.mark.asyncio
async def test_authenticated_legacy_endpoint_regression(auth_case):
    login_response = await login(auth_case)
    token = login_response.json()["token"]

    response = await auth_case["client"].get(
        "/api/contacts", headers=bearer(token)
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.asyncio
async def test_new_registration_persists_auth_defaults():
    unique = uuid.uuid4().hex
    email = f"base01.new.{unique}@example.com"
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "nombre": "BASE-01 New User",
                "email": email,
                "password": "Base01TestPass!",
                "rol": "lider",
            },
        )
        assert response.status_code == 200, response.text
        user = await server.db.users.find_one({"email": email})
        assert user["is_active"] is True
        assert user["token_version"] == 1
        payload = server.verify_token(response.json()["token"])
        assert payload["token_version"] == 1

        user_id = str(user["_id"])
        await server.db.checklists.delete_many({"user_id": user_id})
        await server.db.progress.delete_many({"user_id": user_id})
        await server.db.users.delete_one({"_id": user["_id"]})


def test_base01_utc_helpers_are_timezone_aware_and_emit_z():
    current = server.utc_now()
    serialized = server.utc_iso_z(current)

    assert current.tzinfo is not None
    assert current.utcoffset() == timedelta(0)
    assert serialized.endswith("Z")
    assert "+00:00" not in serialized
