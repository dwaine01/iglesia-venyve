"""Rescate de acceso de emergencia para el pastor general — sin scripts manuales.

Si las variables de entorno ADMIN_RECOVERY_EMAIL y ADMIN_RECOVERY_PASSWORD
existen al arrancar el backend, se restablece la contraseña de una cuenta
pastoral YA EXISTENTE (rol pastor, pastora, admin o superadmin). Esta rutina
NUNCA crea cuentas ni cambia roles: solo actúa sobre una cuenta que ya tiene
autoridad pastoral.

Es idempotente: guarda una huella sha256(email+password) en la colección
`system_recovery`. Si esa huella ya fue aplicada, el arranque no vuelve a
tocar la cuenta — así, una vez que el pastor cambia la contraseña, reinicios
posteriores del backend no la pisan de nuevo mientras las variables sigan
puestas en Railway.

También borra el bloqueo por fuerza bruta (`login_attempts`) de esa cuenta,
por si quedó bloqueada por intentos fallidos de login — ese es justo el
escenario de "cuenta bloqueada" que motiva este rescate.

Procedimiento completo para producción: ver DEPLOYMENT.md.
"""
import hashlib
import os
from datetime import datetime, timezone

import bcrypt

RECOVERABLE_ROLES = {"pastor", "pastora", "admin", "superadmin"}
MIN_PASSWORD_LENGTH = 12


def _fingerprint(email: str, password: str) -> str:
    return hashlib.sha256(f"{email}:{password}".encode("utf-8")).hexdigest()


async def apply_admin_recovery(db) -> None:
    raw_email = os.environ.get("ADMIN_RECOVERY_EMAIL")
    password = os.environ.get("ADMIN_RECOVERY_PASSWORD")
    if not raw_email or not password:
        return

    email = raw_email.strip().lower()

    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"[admin_recovery] WARNING: ADMIN_RECOVERY_PASSWORD debe tener al menos {MIN_PASSWORD_LENGTH} caracteres. Rescate ignorado para {email}.")
        return

    target = await db.users.find_one({"email": email})
    if not target or target.get("rol") not in RECOVERABLE_ROLES:
        print(f"[admin_recovery] WARNING: no existe una cuenta pastoral (pastor/pastora/admin/superadmin) con el correo {email}. No se creó ni modificó ninguna cuenta.")
        return

    fingerprint = _fingerprint(email, password)
    already_applied = await db.system_recovery.find_one({"email": email, "fingerprint": fingerprint})
    if already_applied:
        return

    current_version = target.get("token_version")
    if not isinstance(current_version, int) or isinstance(current_version, bool) or current_version < 1:
        current_version = 1

    now = datetime.now(timezone.utc)
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    await db.users.update_one(
        {"_id": target["_id"]},
        {"$set": {
            "password": hashed,
            "is_active": True,
            "must_change_password": True,
            "token_version": current_version + 1,
            "updated_at": now,
        }},
    )
    # Limpia el bloqueo por fuerza bruta (login_attempts) de esta cuenta: si
    # quedó bloqueada por intentos fallidos, el rescate también debe desbloquearla.
    login_attempt_identifier = hashlib.sha256(email.encode("utf-8")).hexdigest()
    await db.login_attempts.delete_one({"identifier": login_attempt_identifier})
    await db.system_recovery.insert_one({
        "email": email,
        "fingerprint": fingerprint,
        "event": "admin_recovery_password_reset",
        "applied_at": now,
    })
    print(f"[admin_recovery] Contraseña de rescate aplicada para {email}. Debe iniciar sesión, cambiar su contraseña, y luego borrar ADMIN_RECOVERY_EMAIL / ADMIN_RECOVERY_PASSWORD de las variables de entorno.")


async def ensure_system_recovery_indexes(db) -> None:
    await db.system_recovery.create_index([("email", 1), ("fingerprint", 1)])
