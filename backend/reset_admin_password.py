"""Restablece la contraseña de una cuenta existente en PRODUCCIÓN (Railway).

Este entorno de vista previa usa una base de datos distinta a la de tu app
desplegada en Railway, por eso el agente no puede resetear tu cuenta real
desde aquí. Corre este script TU MISMO, conectado a la base de datos de
PRODUCCIÓN (el MONGO_URL que configuraste en Railway), no al MONGO_URL de
este preview.

Uso:
    MONGO_URL="<tu-mongo-url-de-produccion>" DB_NAME="<tu-db-name>" \
    python3 reset_admin_password.py admin@venyve.com "NuevaContrasena123!"
"""
import asyncio
import sys
from datetime import datetime, timezone

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient


async def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python3 reset_admin_password.py <email> <nueva_contrasena>")
        sys.exit(1)
    import os
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("ERROR: define MONGO_URL y DB_NAME de tu base de datos de PRODUCCIÓN antes de correr este script.")
        sys.exit(1)

    email, new_password = sys.argv[1], sys.argv[2]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    user = await db.users.find_one({"email": email})
    if not user:
        print(f"No existe ningún usuario con el correo '{email}' en esta base de datos.")
        sys.exit(1)

    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    new_token_version = user.get("token_version", 1) + 1
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password": new_hash,
            "token_version": new_token_version,
            "is_active": True,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    print(f"Contraseña actualizada para {email}. Ya puedes iniciar sesión con la nueva contraseña.")


if __name__ == "__main__":
    asyncio.run(main())
