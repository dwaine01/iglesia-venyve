"""One-off seed: Discipulado/Formación curriculum requested by the user (2026-09-29)."""
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

DEFAULT_POLICY = {
    "method": "attendance_only", "minimum_attendance_pct": 80, "minimum_grade_pct": 70,
    "late_weight": 0.5, "excused_policy": "exclude", "manual_confirmation_required": False,
    "custom_requirements": [],
}

PROGRAMS = [
    {
        "name": "Discipulado de Evangelismo y Consolidación",
        "description": "Primera etapa formativa tras la conversión: MCD, NPT y LBS, cerrando con un Retiro.",
        "modules": [
            ("Mi Conexión con Dios (MCD)", "Primer encuentro personal con Dios. Duración: 7 días.", 7),
            ("Nací Para Triunfar (NPT)", "Fundamentos de identidad y propósito en Cristo. Duración: 3 días.", 3),
            ("LBS (Liberación, Bendición, Sanidad)", "Proceso de liberación, bendición y sanidad interior. Duración: 21 días.", 21),
            ("Retiro", "Retiro de cierre del Discipulado de Evangelismo y Consolidación.", None),
        ],
    },
    {
        "name": "Discipulado",
        "description": "Discipulado central de un año: libros de 3 meses cada uno, dos retiros y graduación. Se entrega certificado por cada discipulado completado.",
        "modules": [
            ("Mi llamado sobrenatural", "Primer libro del Discipulado. Duración: 3 meses.", 90),
            ("El privilegio de servir", "Segundo libro del Discipulado. Duración: 3 meses.", 90),
            ("La estrategia es ganar", "Tercer libro del Discipulado. Duración: 3 meses (9 meses acumulados).", 90),
            ("Retiro 1", "Retiro al terminar los tres primeros libros del Discipulado.", None),
            ("Conociendo al Padre", "Cuarto libro del Discipulado.", None),
            ("Conociendo al Hijo", "Quinto libro del Discipulado.", None),
            ("Conociendo al Espíritu Santo", "Sexto libro del Discipulado.", None),
            ("El proceso de convertirse en discípulo", "Séptimo libro del Discipulado. Duración: 3 meses.", 90),
            ("Retiro 2", "Retiro al terminar el último libro del Discipulado.", None),
            ("Graduación", "Graduación anual del Discipulado.", None),
        ],
    },
    {
        "name": "Academia de Obreros",
        "description": "Formación de obreros de un año: cuatro módulos de 3 meses, retiro y graduación con diploma.",
        "modules": [
            ("Academia de Obrero 1", "Primer módulo de Academia de Obreros. Duración: 3 meses.", 90),
            ("Academia de Obrero 2", "Segundo módulo de Academia de Obreros. Duración: 3 meses.", 90),
            ("Academia de Obrero 3", "Tercer módulo de Academia de Obreros. Duración: 3 meses.", 90),
            ("Academia de Obrero 4", "Cuarto módulo de Academia de Obreros. Duración: 3 meses.", 90),
            ("Retiro", "Retiro de cierre de Academia de Obreros.", None),
            ("Graduación", "Graduación de Academia de Obreros. Se entrega un diploma.", None),
        ],
    },
]


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    for program_def in PROGRAMS:
        existing = await db.formation_programs.find_one({"name": program_def["name"]})
        if existing:
            print("SKIP (ya existe):", program_def["name"])
            continue
        program_id = str(uuid4())
        program_doc = {
            "_id": program_id, "program_id": program_id, "name": program_def["name"],
            "description": program_def["description"], "purpose": "discipleship", "active": True,
            "certificate_enabled": True, "certificate_scope": "program", "version": 1,
            "created_by_user_id": "system_seed", "created_at": now, "updated_at": now,
        }
        await db.formation_programs.insert_one(program_doc)
        prev_module_id = None
        for order, (name, description, duration_days) in enumerate(program_def["modules"], start=1):
            module_id = str(uuid4())
            module_doc = {
                "_id": module_id, "module_id": module_id, "program_id": program_id,
                "program_name_snapshot": program_def["name"], "name": name, "description": description,
                "order": order, "active": True, "approval_policy": DEFAULT_POLICY,
                "certificate_enabled": True, "duration_days": duration_days, "version": 1,
                "created_by_user_id": "system_seed", "created_at": now, "updated_at": now,
            }
            await db.formation_modules.insert_one(module_doc)
            if prev_module_id:
                prereq_id = str(uuid4())
                await db.formation_module_prerequisites.insert_one({
                    "_id": prereq_id, "module_id": module_id, "prerequisite_module_id": prev_module_id,
                    "active": True, "mode": "all", "created_at": now, "updated_at": now,
                })
            prev_module_id = module_id
        print("CREATED:", program_def["name"], "with", len(program_def["modules"]), "modules")


asyncio.run(main())
