"""Seed script to create a test user for development/testing"""
import asyncio
import os
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
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

async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Check if test user exists
    existing = await db.users.find_one({"email": "admin@venyve.com"})
    if existing:
        print("Test user already exists")
        return
    
    # Create test user
    hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt())
    user_doc = {
        "nombre": "Pastora Carmen",
        "email": "admin@venyve.com",
        "password": hashed.decode(),
        "rol": "lider",
        **access_defaults_for_role("lider"),
        "is_active": True,
        "token_version": 1,
        "created_at": datetime.utcnow(),
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Initialize checklists
    for semana, tareas in DEFAULT_CHECKLISTS.items():
        await db.checklists.insert_one({
            "user_id": user_id,
            "semana": semana,
            "tareas": tareas,
            "updated_at": datetime.utcnow(),
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
            "updated_at": datetime.utcnow(),
        })
    
    print(f"Test user created: admin@venyve.com / admin123")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed())
