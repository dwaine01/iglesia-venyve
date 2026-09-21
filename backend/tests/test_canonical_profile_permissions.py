"""FROZEN rule: ONE PERSON -> ONE canonical Profile 360 -> permissions."""
import os
import uuid

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ley7semanas_test_db")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

import server  # noqa: E402
from access_control import (  # noqa: E402
    PERSON_ATTENDANCE_READ,
    PERSON_HISTORY_READ,
    PERSON_NOTES_READ,
    PERSON_PROFILE_SENSITIVE_READ,
    access_defaults_for_role,
)


async def authenticated_client(user_doc: dict, password: str):
    user_doc = dict(user_doc)
    user_doc["password"] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    result = await server.db.users.insert_one(user_doc)
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post(
        "/api/auth/login", json={"email": user_doc["email"], "password": password}
    )
    assert login.status_code == 200, login.text
    client.headers.update({"Authorization": f"Bearer {login.json()['token']}"})
    return client, result.inserted_id


@pytest.mark.asyncio
async def test_mentor_and_pastor_use_same_canonical_profile_with_different_permissions():
    unique = uuid.uuid4().hex
    person_id = str(ObjectId())
    person_oid = ObjectId(person_id)
    pastor_doc = {
        "nombre": "Pastor Canonical",
        "email": f"pastor.canonical.{unique}@example.com",
        "rol": "pastor",
        "is_active": True,
        "token_version": 1,
        **access_defaults_for_role("pastor"),
    }
    pastor, pastor_user_id = await authenticated_client(pastor_doc, "CanonicalPastorPass!")
    await server.db.persons.insert_one({
        "_id": person_oid,
        "person_number": f"VV-{uuid.uuid4().int % 999999:06d}",
        "nombre": "Juan",
        "apellido": "Pérez",
        "fecha_nacimiento": "1991-05-20",
        "age_category": "adulto",
        "created_by": str(pastor_user_id),
    })
    pastoral_note = await pastor.post(
        f"/api/core/persons/{person_id}/notes",
        json={"contenido": "Nota pastoral restringida", "categoria": "pastoral"},
    )
    assert pastoral_note.status_code == 201

    mentor_doc = {
        "nombre": "Mentor Canonical",
        "email": f"mentor.canonical.{unique}@example.com",
        "rol": "mentor",
        "is_active": True,
        "token_version": 1,
        "capabilities": [
            PERSON_PROFILE_SENSITIVE_READ,
            PERSON_ATTENDANCE_READ,
            PERSON_NOTES_READ,
            PERSON_HISTORY_READ,
        ],
        "access_scope": {"persons": "assigned", "person_ids": [person_id]},
        "access_policy_version": 3,
    }
    mentor, mentor_user_id = await authenticated_client(mentor_doc, "CanonicalMentorPass!")

    try:
        pastor_profile = await pastor.get(f"/api/core/persons/{person_id}/profile")
        mentor_profile = await mentor.get(f"/api/core/persons/{person_id}/profile")
        assert pastor_profile.status_code == 200
        assert mentor_profile.status_code == 200
        assert pastor_profile.json()["canonical_profile_path"] == f"/personas/{person_id}"
        assert mentor_profile.json()["canonical_profile_path"] == f"/personas/{person_id}"
        assert pastor_profile.json()["header"]["nombre_completo"] == "Juan Pérez"
        assert mentor_profile.json()["header"]["nombre_completo"] == "Juan Pérez"
        assert len(pastor_profile.json()["sections"]) == len(mentor_profile.json()["sections"]) == 18

        mentor_body = mentor_profile.json()
        assert "asistencia" in mentor_body["sections_available"]
        assert "historial" in mentor_body["sections_available"]
        assert "contacto" in mentor_body["sections_planned"]
        assert mentor_body["notas"] == []
        statuses = {
            section["section_key"]: section["status_code"]
            for section in mentor_body["sections"]
        }
        assert statuses["contacto"] == "access_restricted"
        assert statuses["household"] == "access_restricted"
        assert statuses["asistencia"] == "no_record"
        assert statuses["discipulado"] == "access_restricted"

        forbidden_write = await mentor.post(
            f"/api/core/persons/{person_id}/attendance",
            json={"fecha": "2025-07-01", "actividad": "Servicio", "estado": "presente"},
        )
        forbidden_pastoral = await mentor.post(
            f"/api/core/persons/{person_id}/notes",
            json={"contenido": "No permitido", "categoria": "pastoral"},
        )
        assert forbidden_write.status_code == 403
        assert forbidden_pastoral.status_code == 403
    finally:
        await pastor.aclose()
        await mentor.aclose()
        await server.db.person_notes.delete_many({"person_id": person_id})
        await server.db.person_activity.delete_many({"person_id": person_id})
        await server.db.persons.delete_one({"_id": person_oid})
        await server.db.users.delete_many({"_id": {"$in": [pastor_user_id, mentor_user_id]}})
