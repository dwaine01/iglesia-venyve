"""Restablecer contraseña de pastor desde Panel General (DashboardGeneralPage.js).

Cubre el endpoint ya existente `POST /api/pastor/pastors/{pastor_id}/reset-password`
(server.py), ahora expuesto en la UI con un diálogo (nueva contraseña + confirmación,
mínimo 10 caracteres en el FRONTEND; el backend sigue exigiendo 6, documentado abajo).

- Un pastor puede resetear la contraseña de OTRO pastor: invalida su token_version
  (sesión vieja deja de servir), la contraseña vieja deja de funcionar y la nueva sí.
- Un usuario que no es pastor (lider/persona) recibe 403.
- Un `pastor_id` inexistente recibe 404.
- Documentado (NO es un bug, está pendiente de confirmación del usuario antes de
  cambiarlo): hoy el backend SÍ permite que un pastor se resetee a sí mismo vía este
  endpoint (el endpoint hermano de desactivar pastor sí bloquea `pastor_id==self`,
  este todavía no). Este test fija el comportamiento ACTUAL para que un cambio futuro
  sea deliberado, no accidental.
"""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "PastorResetPass123!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA",
        "apellido": label,
        "idempotency_key": f"qa:pastorreset:{uuid.uuid4()}",
        "version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, password: str = PASSWORD) -> tuple[str, str]:
    user_id = ObjectId()
    slug = label.lower().replace(" ", ".")
    email = f"qa.pastorreset.{slug}.{uuid.uuid4().hex[:6]}@example.com"
    defaults = access_defaults_for_role(role)
    document = {
        "_id": user_id,
        "nombre": f"QA {label}",
        "email": email,
        "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "rol": role,
        "is_active": True,
        "token_version": 1,
        "created_at": datetime.now(timezone.utc),
        **defaults,
    }
    if person_id:
        document["person_id"] = person_id
    await server.db.users.insert_one(document)
    return str(user_id), email


async def auth_client(email: str, password: str = PASSWORD) -> tuple[AsyncClient, dict, str]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    return client, {"Authorization": f"Bearer {token}"}, token


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


@pytest.mark.asyncio
async def test_pastor_resets_other_pastor_password_and_invalidates_old_session():
    await cleanup()
    actor_person_id = await create_person("Reset Actor")
    target_person_id = await create_person("Reset Target")
    _, actor_email = await create_user("Reset Actor", "pastor", actor_person_id)
    _, target_email = await create_user("Reset Target", "pastor", target_person_id, password="OldPassword123!")
    actor_client, actor_headers, _ = await auth_client(actor_email)
    target_client, target_headers, _ = await auth_client(target_email, password="OldPassword123!")
    try:
        pastors = await actor_client.get("/api/pastor/pastors", headers=actor_headers)
        target_id = next(p["_id"] for p in pastors.json() if p["email"] == target_email)

        response = await actor_client.post(
            f"/api/pastor/pastors/{target_id}/reset-password", json={"password": "BrandNewPassword456!"}, headers=actor_headers,
        )
        assert response.status_code == 200, response.text

        stale = await target_client.get("/api/auth/me", headers=target_headers)
        assert stale.status_code == 401, "el token emitido antes del reset debe quedar invalidado"

        old_login = await actor_client.post("/api/auth/login", json={"email": target_email, "password": "OldPassword123!"})
        assert old_login.status_code == 401

        new_login = await actor_client.post("/api/auth/login", json={"email": target_email, "password": "BrandNewPassword456!"})
        assert new_login.status_code == 200
    finally:
        await actor_client.aclose()
        await target_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_non_pastor_cannot_reset_pastor_password():
    await cleanup()
    target_person_id = await create_person("Reset Target Denied")
    leader_person_id = await create_person("Reset Denied Leader")
    _, target_email = await create_user("Reset Target Denied", "pastor", target_person_id)
    _, leader_email = await create_user("Reset Denied Leader", "lider", leader_person_id)
    leader_client, leader_headers, _ = await auth_client(leader_email)
    try:
        pastors = await leader_client.get("/api/pastor/pastors", headers=leader_headers)
        assert pastors.status_code == 403, "un lider tampoco puede listar pastores"

        target_user = await server.db.users.find_one({"email": target_email}, {"_id": 1})
        response = await leader_client.post(
            f"/api/pastor/pastors/{target_user['_id']}/reset-password", json={"password": "DoesNotMatter123!"}, headers=leader_headers,
        )
        assert response.status_code == 403
    finally:
        await leader_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_reset_requires_backend_minimum_and_rejects_unknown_target():
    await cleanup()
    actor_person_id = await create_person("Reset Actor Min")
    _, actor_email = await create_user("Reset Actor Min", "pastor", actor_person_id)
    actor_client, actor_headers, _ = await auth_client(actor_email)
    try:
        pastors = await actor_client.get("/api/pastor/pastors", headers=actor_headers)
        self_id = next(p["_id"] for p in pastors.json() if p["email"] == actor_email)

        too_short = await actor_client.post(
            f"/api/pastor/pastors/{self_id}/reset-password", json={"password": "short"}, headers=actor_headers,
        )
        assert too_short.status_code == 400, "backend exige minimo 6 caracteres hoy (la UI exige 10, es mas estricta)"

        missing = await actor_client.post(
            f"/api/pastor/pastors/{ObjectId()}/reset-password", json={"password": "ValidEnough123!"}, headers=actor_headers,
        )
        assert missing.status_code == 404
    finally:
        await actor_client.aclose()
        await cleanup()


@pytest.mark.asyncio
async def test_self_reset_via_api_is_currently_allowed_pending_user_decision():
    """Comportamiento ACTUAL (no cambiado sin confirmacion del usuario): el backend no
    bloquea pastor_id==self en este endpoint, a diferencia de desactivar-pastor que si
    lo hace. La UI oculta la accion sobre la propia fila, pero una llamada directa a la
    API hoy todavia tiene exito. Si el usuario confirma el endurecimiento, este test se
    debe actualizar para esperar 400."""
    await cleanup()
    actor_person_id = await create_person("Reset Self")
    _, actor_email = await create_user("Reset Self", "pastor", actor_person_id, password="OriginalSelf123!")
    actor_client, actor_headers, _ = await auth_client(actor_email, password="OriginalSelf123!")
    try:
        pastors = await actor_client.get("/api/pastor/pastors", headers=actor_headers)
        self_entry = next(p for p in pastors.json() if p["email"] == actor_email)
        assert self_entry["is_current"] is True, "is_current es lo que la UI usa para ocultar la accion"

        response = await actor_client.post(
            f"/api/pastor/pastors/{self_entry['_id']}/reset-password", json={"password": "NewSelfPassword456!"}, headers=actor_headers,
        )
        assert response.status_code == 200
    finally:
        await actor_client.aclose()
        await cleanup()
