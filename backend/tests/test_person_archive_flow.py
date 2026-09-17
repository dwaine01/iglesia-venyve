"""Archive flow regression for Persona 360: permissions, cascading state, and visibility."""

import os
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role


QA_EMAIL_PREFIX = "t1qaarchive"
QA_NAME_PREFIX = "T1QAARCH"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _qa_email(tag: str) -> str:
    return f"{QA_EMAIL_PREFIX}.{tag}.{uuid.uuid4().hex[:8]}@example.com"


async def _cleanup_qa_artifacts() -> None:
    users = await server.db.users.find(
        {"email": {"$regex": f"^{QA_EMAIL_PREFIX}\\."}},
        {"_id": 1, "person_id": 1},
    ).to_list(500)
    user_person_ids = [item.get("person_id") for item in users if item.get("person_id")]

    named_people = await server.db.persons.find(
        {
            "$or": [
                {"nombre": {"$regex": f"^{QA_NAME_PREFIX}"}},
                {"apellido": {"$regex": f"^{QA_NAME_PREFIX}"}},
            ]
        },
        {"_id": 1},
    ).to_list(1000)

    person_ids = {str(item["_id"]) for item in named_people}
    person_ids.update(pid for pid in user_person_ids if isinstance(pid, str))

    if person_ids:
        await server.db.person_contacts.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.person_addresses.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.person_activity.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.process_enrollments.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.cell_memberships.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.cell_followups.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.cell_needs.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.household_memberships.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.person_relationships.delete_many({
            "$or": [
                {"person_a_id": {"$in": list(person_ids)}},
                {"person_b_id": {"$in": list(person_ids)}},
            ]
        })
        await server.db.person_talents.delete_many({"_id": {"$in": list(person_ids)}})
        await server.db.ministry_assignments.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.person_memberships.delete_many({"person_id": {"$in": list(person_ids)}})
        await server.db.persons.delete_many({"_id": {"$in": [ObjectId(pid) for pid in person_ids if ObjectId.is_valid(pid)]}})

    if users:
        await server.db.users.delete_many({"_id": {"$in": [item["_id"] for item in users]}})


async def _create_user_with_person(role: str, tag: str, password: str = "TestPass123!") -> dict:
    user_id = ObjectId()
    person_oid = ObjectId()
    email = _qa_email(tag)
    now = _now_utc()

    await server.db.persons.insert_one(
        {
            "_id": person_oid,
            "person_number": f"VV-9{str(uuid.uuid4().int)[:5]}",
            "nombre": f"{QA_NAME_PREFIX} {tag}",
            "apellido": "ACTOR",
            "search_key": f"{QA_NAME_PREFIX.lower()} {tag.lower()} actor",
            "idempotency_key": str(uuid.uuid4()),
            "version": 1,
            "created_by": str(user_id),
            "auth_user_id": str(user_id),
            "created_at": now,
            "updated_at": now,
        }
    )

    await server.db.users.insert_one(
        {
            "_id": user_id,
            "nombre": f"{QA_NAME_PREFIX} {tag}",
            "email": email,
            "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            "rol": role,
            "person_id": str(person_oid),
            "is_active": True,
            "token_version": 1,
            **access_defaults_for_role(role),
        }
    )
    return {
        "user_id": str(user_id),
        "person_id": str(person_oid),
        "email": email,
        "password": password,
    }


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return token


@pytest_asyncio.fixture
async def api_client():
    await _cleanup_qa_artifacts()
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await _cleanup_qa_artifacts()


# Core archive cascade and visibility assertions
@pytest.mark.asyncio
async def test_archive_person_cascades_and_hides_from_core_views(api_client):
    pastor = await _create_user_with_person("pastor", "pastor")
    pastor_token = await _login(api_client, pastor["email"], pastor["password"])
    api_client.headers.update({"Authorization": f"Bearer {pastor_token}"})

    created = await api_client.post(
        "/api/core/persons",
        json={
            "nombre": f"{QA_NAME_PREFIX} TARGET",
            "apellido": "ARCHIVE",
            "telefono": "8091112233",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert created.status_code == 201, created.text
    person_id = created.json()["person_id"]

    linked_user_id = ObjectId()
    await server.db.users.insert_one(
        {
            "_id": linked_user_id,
            "nombre": f"{QA_NAME_PREFIX} LINKED",
            "email": _qa_email("linked"),
            "password": bcrypt.hashpw(b"NotUsed123!", bcrypt.gensalt()).decode(),
            "rol": "persona",
            "person_id": person_id,
            "is_active": True,
            "token_version": 7,
            **access_defaults_for_role("persona"),
        }
    )
    await server.db.person_memberships.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "membership_id": str(uuid.uuid4()),
            "person_id": person_id,
            "member_number": str(uuid.uuid4().int)[:5],
            "status": "active",
            "created_at": _now_utc(),
            "updated_at": _now_utc(),
        }
    )

    archived = await api_client.delete(f"/api/core/persons/{person_id}")
    assert archived.status_code == 200, archived.text
    archived_data = archived.json()
    assert archived_data["archived"] is True
    assert archived_data["linked_account_deactivated"] is True

    person_doc = await server.db.persons.find_one({"_id": ObjectId(person_id)})
    assert person_doc["is_archived"] is True

    linked_user = await server.db.users.find_one({"_id": linked_user_id})
    assert linked_user["is_active"] is False
    assert linked_user["token_version"] == 8

    membership = await server.db.person_memberships.find_one({"person_id": person_id})
    assert membership["status"] == "inactive"

    archived_activity = await server.db.person_activity.find_one(
        {"person_id": person_id, "action": "archived"}
    )
    assert archived_activity is not None

    person_get = await api_client.get(f"/api/core/persons/{person_id}")
    assert person_get.status_code == 404

    profile_get = await api_client.get(f"/api/core/persons/{person_id}/profile")
    assert profile_get.status_code == 404

    list_search = await api_client.get("/api/core/persons", params={"search": f"{QA_NAME_PREFIX} TARGET"})
    assert list_search.status_code == 200
    assert all(item["person_id"] != person_id for item in list_search.json()["items"])

    directory_search = await api_client.get(
        "/api/core/persons/directory/search",
        params={"q": f"{QA_NAME_PREFIX} TARGET"},
    )
    assert directory_search.status_code == 200
    assert all(item["person_id"] != person_id for item in directory_search.json()["items"])


# Authorization: non-pastoral roles cannot archive
@pytest.mark.asyncio
async def test_leader_and_persona_receive_403_when_archiving(api_client):
    pastor = await _create_user_with_person("pastor", "issuer")
    pastor_token = await _login(api_client, pastor["email"], pastor["password"])
    api_client.headers.update({"Authorization": f"Bearer {pastor_token}"})
    created = await api_client.post(
        "/api/core/persons",
        json={
            "nombre": f"{QA_NAME_PREFIX} TOBLOCK",
            "apellido": "ROLES",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert created.status_code == 201, created.text
    person_id = created.json()["person_id"]

    leader = await _create_user_with_person("lider", "leader")
    persona = await _create_user_with_person("persona", "persona")

    leader_token = await _login(api_client, leader["email"], leader["password"])
    leader_attempt = await api_client.delete(
        f"/api/core/persons/{person_id}",
        headers={"Authorization": f"Bearer {leader_token}"},
    )
    assert leader_attempt.status_code == 403

    persona_token = await _login(api_client, persona["email"], persona["password"])
    persona_attempt = await api_client.delete(
        f"/api/core/persons/{person_id}",
        headers={"Authorization": f"Bearer {persona_token}"},
    )
    assert persona_attempt.status_code == 403


# Guard rails: self archive and pastoral-linked target must return 409
@pytest.mark.asyncio
async def test_self_archive_and_pastoral_linked_archive_return_409(api_client):
    actor = await _create_user_with_person("pastor", "actor")
    actor_token = await _login(api_client, actor["email"], actor["password"])
    api_client.headers.update({"Authorization": f"Bearer {actor_token}"})

    self_attempt = await api_client.delete(f"/api/core/persons/{actor['person_id']}")
    assert self_attempt.status_code == 409

    created = await api_client.post(
        "/api/core/persons",
        json={
            "nombre": f"{QA_NAME_PREFIX} BLOCKED",
            "apellido": "PASTOR",
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert created.status_code == 201, created.text
    protected_person_id = created.json()["person_id"]

    linked_pastor_id = ObjectId()
    await server.db.users.insert_one(
        {
            "_id": linked_pastor_id,
            "nombre": f"{QA_NAME_PREFIX} OTHER PASTOR",
            "email": _qa_email("otherpastor"),
            "password": bcrypt.hashpw(b"NotUsed123!", bcrypt.gensalt()).decode(),
            "rol": "pastor",
            "person_id": protected_person_id,
            "is_active": True,
            "token_version": 2,
            **access_defaults_for_role("pastor"),
        }
    )

    pastoral_attempt = await api_client.delete(f"/api/core/persons/{protected_person_id}")
    assert pastoral_attempt.status_code == 409


@pytest.mark.asyncio
async def test_no_qa_demo_residue_after_cleanup():
    await _cleanup_qa_artifacts()
    remaining_persons = await server.db.persons.count_documents(
        {
            "$or": [
                {"nombre": {"$regex": f"^{QA_NAME_PREFIX}"}},
                {"apellido": {"$regex": f"^{QA_NAME_PREFIX}"}},
            ]
        }
    )
    remaining_users = await server.db.users.count_documents(
        {"email": {"$regex": f"^{QA_EMAIL_PREFIX}\\."}}
    )
    assert remaining_persons == 0
    assert remaining_users == 0
