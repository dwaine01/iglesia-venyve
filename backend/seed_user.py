"""Seed script to create a test user for development/testing"""
import asyncio
import os
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from access_control import access_defaults_for_role

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
if not MONGO_URL or not DB_NAME:
    raise RuntimeError("MONGO_URL and DB_NAME environment variables are required.")

DEFAULT_CHECKLISTS = {
    1: [
        {"id": "s1_t1", "texto": "Elaborar lista de 30 personas (familiares, amigos, conocidos)", "completada": False},
        {"id": "s1_t2", "texto": "Organizar equipo de obreros para la campaña", "completada": False},
        {"id": "s1_t3", "texto": "Preparar material promocional y eslóganes", "completada": False},
        {"id": "s1_t4", "texto": "Campaña de oración profética (6am - 9am)", "completada": False},
        {"id": "s1_t5", "texto": "Salir a tocar puertas y visitar hogares", "completada": False},
        {"id": "s1_t6", "texto": "Registrar casas visitadas y personas contactadas", "completada": False},
        {"id": "s1_t7", "texto": "Reunión de cierre diario para reportar resultados", "completada": False},
        {"id": "s1_t8", "texto": "Decorar la iglesia con tema de GANAR", "completada": False},
    ],
    2: [
        {"id": "s2_t1", "texto": "Entregar libro MCD (Mi Conexión con Dios) a nuevos contactos", "completada": False},
        {"id": "s2_t2", "texto": "Visitar diariamente a personas que respondieron", "completada": False},
        {"id": "s2_t3", "texto": "Asegurar que confiesen las oraciones del libro", "completada": False},
        {"id": "s2_t4", "texto": "Enviar mensajes, textos y notas de voz de seguimiento", "completada": False},
        {"id": "s2_t5", "texto": "Verificar por WhatsApp que lean y confiesen", "completada": False},
        {"id": "s2_t6", "texto": "Intercesión intensa contra los 7 espíritus peores", "completada": False},
        {"id": "s2_t7", "texto": "Consolidar en las primeras 72 horas", "completada": False},
    ],
    3: [
        {"id": "s3_t1", "texto": "Apretar ayunos duros durante la semana", "completada": False},
        {"id": "s3_t2", "texto": "Visitar todos los días a las personas que respondieron", "completada": False},
        {"id": "s3_t3", "texto": "Preparar ceremonia de graduación NPT", "completada": False},
        {"id": "s3_t4", "texto": "Crear certificados con sello y firma de la iglesia", "completada": False},
        {"id": "s3_t5", "texto": "Comprar marcos para los diplomas", "completada": False},
        {"id": "s3_t6", "texto": "Realizar ceremonia de graduación", "completada": False},
        {"id": "s3_t7", "texto": "Introducir el libro LBS en la noche de graduación", "completada": False},
    ],
    4: [
        {"id": "s4_t1", "texto": "Iniciar proceso de liberación con libro LBS", "completada": False},
        {"id": "s4_t2", "texto": "Aplicar cuestionarios de áreas de atadura", "completada": False},
        {"id": "s4_t3", "texto": "Trabajar liberación por capas: Persona", "completada": False},
        {"id": "s4_t4", "texto": "Trabajar liberación por capas: Casa", "completada": False},
        {"id": "s4_t5", "texto": "Trabajar liberación por capas: Tierra/Territorio", "completada": False},
        {"id": "s4_t6", "texto": "Romper líneas de iniquidad identificadas", "completada": False},
        {"id": "s4_t7", "texto": "Ministración de renuncias y declaraciones", "completada": False},
    ],
    5: [
        {"id": "s5_t1", "texto": "Llenar el corazón con fe y palabra", "completada": False},
        {"id": "s5_t2", "texto": "Reformar el alma con enseñanza continua", "completada": False},
        {"id": "s5_t3", "texto": "Cambiar pensamientos en la mente", "completada": False},
        {"id": "s5_t4", "texto": "Transformar hábitos y costumbres del cuerpo", "completada": False},
        {"id": "s5_t5", "texto": "Llenura del Espíritu Santo", "completada": False},
        {"id": "s5_t6", "texto": "Asegurar la consolidación del nuevo creyente", "completada": False},
    ],
    6: [
        {"id": "s6_t1", "texto": "Enseñar sobre enfermedades espirituales", "completada": False},
        {"id": "s6_t2", "texto": "Trabajar sanidad del afán y la ansiedad", "completada": False},
        {"id": "s6_t3", "texto": "Trabajar sanidad de la amargura", "completada": False},
        {"id": "s6_t4", "texto": "Trabajar sanidad de la falta de perdón", "completada": False},
        {"id": "s6_t5", "texto": "Curar el corazón del dolor", "completada": False},
        {"id": "s6_t6", "texto": "Prevenir regreso de los 7 espíritus peores", "completada": False},
    ],
    7: [
        {"id": "s7_t1", "texto": "Organizar retiro (viernes noche + sábado todo el día)", "completada": False},
        {"id": "s7_t2", "texto": "Buscar llenura del Espíritu Santo para cada persona", "completada": False},
        {"id": "s7_t3", "texto": "Entregar libro Mi Llamado", "completada": False},
        {"id": "s7_t4", "texto": "Entregar libro Visión Familiar", "completada": False},
        {"id": "s7_t5", "texto": "Graduar con ambos libros en el retiro", "completada": False},
        {"id": "s7_t6", "texto": "Establecer plan de seguimiento post-retiro", "completada": False},
        {"id": "s7_t7", "texto": "Celebrar y dar gracias por los resultados", "completada": False},
    ],
}

def validate_seed_environment() -> dict:
    environment = os.environ.get("APP_ENV")
    if environment not in {"development", "test"} or os.environ.get("ALLOW_DEV_SEED") != "true":
        raise RuntimeError("seed_user.py está bloqueado fuera de development/test con ALLOW_DEV_SEED=true")
    required = {name: os.environ.get(name) for name in ["DEV_SEED_EMAIL", "DEV_SEED_PASSWORD", "DEV_SEED_NAME", "DEV_SEED_ROLE"]}
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Faltan variables de seed: {', '.join(missing)}")
    if required["DEV_SEED_ROLE"] not in {"persona", "lider"}:
        raise RuntimeError("DEV_SEED_ROLE solo permite persona o lider")
    if len(required["DEV_SEED_PASSWORD"]) < 12 or required["DEV_SEED_PASSWORD"].lower() in {"admin123", "password123", "changeme123"}:
        raise RuntimeError("DEV_SEED_PASSWORD debe ser única y tener al menos 12 caracteres")
    return required


async def seed():
    settings = validate_seed_environment()
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Check if test user exists
    email = settings["DEV_SEED_EMAIL"].strip().lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        print("Test user already exists")
        return
    
    # Create test user
    hashed = bcrypt.hashpw(settings["DEV_SEED_PASSWORD"].encode(), bcrypt.gensalt())
    user_doc = {
        "nombre": settings["DEV_SEED_NAME"].strip(),
        "email": email,
        "password": hashed.decode(),
        "rol": settings["DEV_SEED_ROLE"],
        **access_defaults_for_role(settings["DEV_SEED_ROLE"]),
        "is_active": True,
        "token_version": 1,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Initialize checklists
    for semana, tareas in DEFAULT_CHECKLISTS.items():
        await db.checklists.insert_one({
            "user_id": user_id,
            "semana": semana,
            "tareas": tareas,
            "updated_at": datetime.now(timezone.utc),
        })
    
    # Initialize progress
    for semana in range(1, 8):
        await db.progress.insert_one({
            "user_id": user_id,
            "semana": semana,
            "casas_visitadas": 0,
            "personas_contactadas": 0,
            "personas_ganadas": 0,
            "oraciones_realizadas": 0,
            "updated_at": datetime.now(timezone.utc),
        })
    
    print(f"Test user created: {email} (password not displayed)")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed())
