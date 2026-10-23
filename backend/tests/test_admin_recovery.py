"""Rescate de acceso de emergencia para el pastor general (admin_recovery.py).

Cubre `apply_admin_recovery(db)`, invocado en el startup de `server.py` cuando
existen ADMIN_RECOVERY_EMAIL y ADMIN_RECOVERY_PASSWORD en el entorno:

- Se aplica SOLO sobre una cuenta existente con rol pastor/pastora/admin/superadmin.
- NO se aplica sobre lider/coordinador_general/persona (no crea cuentas, no cambia roles).
- NO se aplica si la contraseña tiene menos de 12 caracteres.
- Es idempotente: la misma huella (email+password) no vuelve a tocar la cuenta.
- Nunca imprime la contraseña ni su hash en los logs (stdout).
"""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId

import server
from access_control import access_defaults_for_role
from admin_recovery import apply_admin_recovery
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "AdminRecoveryPass123!"
RECOVERY_PASSWORD = "RescueValidPass1234!"


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA",
        "apellido": label,
        "idempotency_key": f"qa:adminrecovery:{uuid.uuid4()}",
        "version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, password: str = PASSWORD) -> tuple[str, str]:
    user_id = ObjectId()
    slug = label.lower().replace(" ", ".")
    email = f"qa.adminrecovery.{slug}.{uuid.uuid4().hex[:6]}@example.com"
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


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


@pytest.fixture(autouse=True)
def clear_recovery_env(monkeypatch):
    monkeypatch.delenv("ADMIN_RECOVERY_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_RECOVERY_PASSWORD", raising=False)
    yield


@pytest.mark.asyncio
async def test_applies_recovery_for_pastor_role_and_forces_password_change(monkeypatch, capsys):
    await cleanup()
    person_id = await create_person("Pastor Recovery Target")
    user_id, email = await create_user("Pastor Recovery Target", "pastor", person_id)
    try:
        monkeypatch.setenv("ADMIN_RECOVERY_EMAIL", email.upper())  # insensible a mayúsculas
        monkeypatch.setenv("ADMIN_RECOVERY_PASSWORD", RECOVERY_PASSWORD)

        before = await server.db.users.find_one({"_id": ObjectId(user_id)})
        assert before["token_version"] == 1

        await apply_admin_recovery(server.db)

        after = await server.db.users.find_one({"_id": ObjectId(user_id)})
        assert bcrypt.checkpw(RECOVERY_PASSWORD.encode(), after["password"].encode())
        assert after["must_change_password"] is True
        assert after["is_active"] is True
        assert after["token_version"] == 2, "debe invalidar sesiones viejas"

        record = await server.db.system_recovery.find_one({"email": email.lower()})
        assert record is not None
        assert "fingerprint" in record and len(record["fingerprint"]) == 64
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_does_not_apply_for_lider_or_coordinador_general(monkeypatch):
    """No crea cuentas ni cambia roles: lider y coordinador_general (rol base
    lider) quedan fuera, aunque el correo exista."""
    await cleanup()
    lider_person_id = await create_person("Lider No Recovery")
    lider_user_id, lider_email = await create_user("Lider No Recovery", "lider", lider_person_id)

    coord_person_id = await create_person("Coordinador No Recovery")
    coord_user_id, coord_email = await create_user("Coordinador No Recovery", "lider", coord_person_id)
    await server.db.users.update_one({"_id": ObjectId(coord_user_id)}, {"$set": {"access_level": "coordinador_general"}})
    try:
        for email in (lider_email, coord_email):
            monkeypatch.setenv("ADMIN_RECOVERY_EMAIL", email)
            monkeypatch.setenv("ADMIN_RECOVERY_PASSWORD", RECOVERY_PASSWORD)
            await apply_admin_recovery(server.db)

        lider_after = await server.db.users.find_one({"_id": ObjectId(lider_user_id)})
        coord_after = await server.db.users.find_one({"_id": ObjectId(coord_user_id)})
        assert bcrypt.checkpw(PASSWORD.encode(), lider_after["password"].encode()), "la contraseña original no debe cambiar"
        assert bcrypt.checkpw(PASSWORD.encode(), coord_after["password"].encode()), "la contraseña original no debe cambiar"
        assert lider_after["token_version"] == 1
        assert coord_after["token_version"] == 1
        assert await server.db.system_recovery.count_documents({}) == 0
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_does_not_apply_for_nonexistent_email_and_never_creates_account(monkeypatch):
    await cleanup()
    ghost_email = f"qa.adminrecovery.ghost.{uuid.uuid4().hex[:6]}@example.com"
    monkeypatch.setenv("ADMIN_RECOVERY_EMAIL", ghost_email)
    monkeypatch.setenv("ADMIN_RECOVERY_PASSWORD", RECOVERY_PASSWORD)
    try:
        await apply_admin_recovery(server.db)
        assert await server.db.users.find_one({"email": ghost_email}) is None, "nunca debe crear una cuenta"
        assert await server.db.system_recovery.count_documents({}) == 0
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_rejects_short_password_without_touching_account(monkeypatch):
    await cleanup()
    person_id = await create_person("Pastor Short Password")
    user_id, email = await create_user("Pastor Short Password", "pastor", person_id)
    try:
        monkeypatch.setenv("ADMIN_RECOVERY_EMAIL", email)
        monkeypatch.setenv("ADMIN_RECOVERY_PASSWORD", "Short1!")  # 7 caracteres, < 12

        await apply_admin_recovery(server.db)

        after = await server.db.users.find_one({"_id": ObjectId(user_id)})
        assert bcrypt.checkpw(PASSWORD.encode(), after["password"].encode()), "la contraseña original no debe cambiar"
        assert after["token_version"] == 1
        assert await server.db.system_recovery.count_documents({}) == 0
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_idempotent_same_fingerprint_does_not_reapply(monkeypatch):
    """Tras aplicarse una vez, reinicios posteriores con las mismas variables no
    deben pisar la contraseña que el pastor ya cambió manualmente."""
    await cleanup()
    person_id = await create_person("Pastor Idempotent")
    user_id, email = await create_user("Pastor Idempotent", "pastor", person_id)
    try:
        monkeypatch.setenv("ADMIN_RECOVERY_EMAIL", email)
        monkeypatch.setenv("ADMIN_RECOVERY_PASSWORD", RECOVERY_PASSWORD)

        await apply_admin_recovery(server.db)
        first = await server.db.users.find_one({"_id": ObjectId(user_id)})
        assert first["token_version"] == 2

        # El pastor cambia su propia contraseña manualmente tras el rescate.
        manual_password = "ManualChangeAfterRescue1!"
        await server.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password": bcrypt.hashpw(manual_password.encode(), bcrypt.gensalt()).decode(), "must_change_password": False}, "$inc": {"token_version": 1}},
        )

        # El backend se reinicia (mismas variables todavía en Railway) -> no debe reaplicar.
        await apply_admin_recovery(server.db)

        after = await server.db.users.find_one({"_id": ObjectId(user_id)})
        assert bcrypt.checkpw(manual_password.encode(), after["password"].encode()), "no debe pisar la contraseña que el pastor ya cambió"
        assert after["token_version"] == 3
        assert await server.db.system_recovery.count_documents({"email": email.lower()}) == 1, "no debe duplicar el registro de auditoría"
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_never_logs_the_password_or_its_hash(monkeypatch, capsys):
    await cleanup()
    person_id = await create_person("Pastor No Log Password")
    user_id, email = await create_user("Pastor No Log Password", "pastor", person_id)
    try:
        monkeypatch.setenv("ADMIN_RECOVERY_EMAIL", email)
        monkeypatch.setenv("ADMIN_RECOVERY_PASSWORD", RECOVERY_PASSWORD)

        await apply_admin_recovery(server.db)

        captured = capsys.readouterr()
        combined_output = captured.out + captured.err
        assert RECOVERY_PASSWORD not in combined_output, "la contraseña en texto plano nunca debe aparecer en logs"

        stored = await server.db.users.find_one({"_id": ObjectId(user_id)})
        assert stored["password"] not in combined_output, "el hash bcrypt tampoco debe imprimirse"
    finally:
        await cleanup()


@pytest.mark.asyncio
async def test_missing_env_vars_is_a_noop():
    await cleanup()
    try:
        # Sin ADMIN_RECOVERY_EMAIL/ADMIN_RECOVERY_PASSWORD (limpiados por el fixture autouse).
        await apply_admin_recovery(server.db)
        assert await server.db.system_recovery.count_documents({}) == 0
    finally:
        await cleanup()
