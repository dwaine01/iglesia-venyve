"""Toda cuenta abre su PROPIA ficha 360 completa (sin permiso de directorio),
pero una cuenta nueva no abre la ficha de otra Persona."""
import os
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ley7semanas_test_db")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

import server  # noqa: E402
from access_control import PERSON_SELF_CAPABILITIES  # noqa: E402


async def _person(nombre: str) -> str:
    oid = ObjectId()
    await server.db.persons.insert_one({
        "_id": oid,
        "person_number": f"VV-{uuid.uuid4().int % 999999:06d}",
        "nombre": nombre,
        "apellido": "Prueba",
        "fecha_nacimiento": "1990-01-01",
        "created_at": datetime.now(timezone.utc),
    })
    return str(oid)


async def _account(person_id: str, capabilities: list[str], scope: str):
    unique = uuid.uuid4().hex
    email = f"self.profile.{unique}@example.com"
    result = await server.db.users.insert_one({
        "nombre": "Cuenta Nueva",
        "email": email,
        "password": bcrypt.hashpw(b"SelfProfile123!", bcrypt.gensalt()).decode(),
        "rol": "lider",
        "access_level": "lider",
        "permissions_mode": "manual",
        "person_id": person_id,
        "is_active": True,
        "token_version": 1,
        "capabilities": capabilities,
        "access_scope": {"persons": scope},
        "access_policy_version": 3,
    })
    await server.db.persons.update_one({"_id": ObjectId(person_id)}, {"$set": {"auth_user_id": str(result.inserted_id)}})
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": "SelfProfile123!"})
    assert login.status_code == 200, login.text
    client.headers.update({"Authorization": f"Bearer {login.json()['token']}"})
    return client, result.inserted_id


async def _cleanup(user_ids, person_ids):
    await server.db.users.delete_many({"_id": {"$in": user_ids}})
    await server.db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in person_ids]}})
    await server.db.person_contacts.delete_many({"person_id": {"$in": person_ids}})


@pytest.mark.asyncio
async def test_new_account_without_modules_opens_own_full_profile_read_only():
    own_id = await _person("Propia")
    other_id = await _person("Ajena")
    await server.db.person_contacts.insert_one({"contact_id": str(uuid.uuid4()), "person_id": own_id, "tipo": "telefono", "valor": "8095550000", "es_principal": True, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
    client, user_id = await _account(own_id, [], "none")
    try:
        own = await client.get(f"/api/core/persons/{own_id}/profile")
        assert own.status_code == 200, own.text
        body = own.json()
        assert body["header"]["nombre_completo"] == "Propia Prueba"
        assert body["header"]["fecha_nacimiento"] == "1990-01-01"
        assert body["header"]["primary_phone"] == "8095550000"
        assert "contacto" in body["sections_available"]
        assert "historial" in body["sections_available"]
        # Solo lectura: no hereda escrituras que la cuenta no tiene.
        assert body["profile_can_write"] is False
        assert body["contacto"]["can_write"] is False
        assert (await client.get(f"/api/core/persons/{own_id}/photo")).status_code == 404

        assert (await client.get(f"/api/core/persons/{other_id}/profile")).status_code == 403
        assert (await client.get(f"/api/core/persons/{other_id}/photo")).status_code == 403
        write = await client.post(f"/api/core/persons/{own_id}/contacts", json={"tipo": "email", "valor": "x@example.com"})
        assert write.status_code == 403
    finally:
        await client.aclose()
        await _cleanup([user_id], [own_id, other_id])


@pytest.mark.asyncio
async def test_mentor_bundle_account_cannot_open_person_outside_scope():
    own_id = await _person("Mentor")
    other_id = await _person("Otra")
    client, user_id = await _account(own_id, list(PERSON_SELF_CAPABILITIES), "created_by")
    try:
        own = await client.get(f"/api/core/persons/{own_id}/profile")
        assert own.status_code == 200, own.text
        assert own.json()["profile_can_write"] is True
        other = await client.get(f"/api/core/persons/{other_id}/profile")
        assert other.status_code == 403
        assert "header" not in other.json()
    finally:
        await client.aclose()
        await _cleanup([user_id], [own_id, other_id])
