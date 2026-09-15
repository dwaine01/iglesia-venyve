from fastapi import FastAPI, HTTPException, Depends, status, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import os
import jwt
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import json
from dotenv import load_dotenv

load_dotenv(override=False)

app = FastAPI(title="Manual Ley 7 Semanas API")

# CORS
origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "ley7semanas_db")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# JWT Config
SECRET_KEY = os.environ.get("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET environment variable is required but not set.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = 24  # hours
DEFAULT_IS_ACTIVE = True
DEFAULT_TOKEN_VERSION = 1


def utc_now() -> datetime:
    """Return a timezone-aware UTC datetime for BASE-01 code."""
    return datetime.now(timezone.utc)


def utc_iso_z(value: Optional[datetime] = None) -> str:
    """Serialize a datetime as ISO-8601 UTC with a trailing Z."""
    current = value or utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def user_is_active(user: dict) -> bool:
    """Existing users without the physical field remain logically active."""
    return user.get("is_active", DEFAULT_IS_ACTIVE) is True


def user_token_version(user: dict) -> int:
    """Existing users without the physical field use logical version 1."""
    version = user.get("token_version", DEFAULT_TOKEN_VERSION)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise HTTPException(status_code=401, detail="No autorizado")
    return version


def serialize_doc(doc):
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, list):
            result[key] = [serialize_doc(v) if isinstance(v, dict) else str(v) if isinstance(v, ObjectId) else v.isoformat() if isinstance(v, datetime) else v for v in value]
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        else:
            result[key] = value
    return result


# --- Models ---
class UserRegister(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    invite_code: Optional[str] = None  # OPCIONAL: si se da, asigna rol y leader segun el codigo
    rol: Optional[str] = "lider"  # usado solo si NO hay invite_code (pastor / lider / persona)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class InviteCodeCreate(BaseModel):
    """Para generar un codigo. El rol_to_assign y leader_id se derivan del creador."""
    destinatario_nombre: Optional[str] = ""  # para acordarse a quien se lo envio
    destinatario_email: Optional[str] = ""  # opcional


class ContactCreate(BaseModel):
    nombre: str
    telefono: Optional[str] = ""
    direccion: Optional[str] = ""
    relacion: Optional[str] = ""  # familiar, amigo, conocido
    estado: Optional[str] = "contactado"  # contactado, visitado, en_proceso, graduado, inactivo
    semana_actual: Optional[int] = 1
    notas: Optional[str] = ""


class ContactUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    relacion: Optional[str] = None
    estado: Optional[str] = None
    semana_actual: Optional[int] = None
    notas: Optional[str] = None


class ChecklistUpdate(BaseModel):
    semana: int
    tarea_id: str
    completada: bool


class ProgressUpdate(BaseModel):
    semana: int
    casas_visitadas: Optional[int] = 0
    personas_contactadas: Optional[int] = 0
    personas_ganadas: Optional[int] = 0
    oraciones_realizadas: Optional[int] = 0


# --- People/Consolidados Models ---
class PersonCreate(BaseModel):
    nombre: str
    telefono: Optional[str] = ""
    direccion: Optional[str] = ""
    relacion: Optional[str] = "conocido"  # familiar, amigo, conocido, vecino
    estado: Optional[str] = "contactado"  # contactado, visitado, en_proceso, graduado, inactivo
    semana_actual: Optional[int] = 1
    notas: Optional[str] = ""
    foto_url: Optional[str] = ""
    edad: Optional[int] = None
    genero: Optional[str] = ""  # masculino, femenino, otro
    ocupacion: Optional[str] = ""
    estado_civil: Optional[str] = ""  # soltero, casado, divorciado, viudo, union_libre
    mejor_horario: Optional[str] = ""  # manana, tarde, noche
    fecha_primer_contacto: Optional[str] = ""
    como_conocio_iglesia: Optional[str] = ""

    @field_validator("edad", mode="before")
    @classmethod
    def _edad_empty_to_none(cls, v):
        # Aceptar "" o espacios como None (formularios web envían strings vacíos).
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        return v

    @field_validator("semana_actual", mode="before")
    @classmethod
    def _semana_empty_to_default(cls, v):
        if v is None or v == "":
            return 1
        return v


class PersonUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    relacion: Optional[str] = None
    estado: Optional[str] = None
    semana_actual: Optional[int] = None
    notas: Optional[str] = None
    foto_url: Optional[str] = None
    edad: Optional[int] = None
    genero: Optional[str] = None
    ocupacion: Optional[str] = None
    estado_civil: Optional[str] = None
    mejor_horario: Optional[str] = None
    fecha_primer_contacto: Optional[str] = None
    como_conocio_iglesia: Optional[str] = None

    @field_validator("edad", "semana_actual", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class PersonProgressUpdate(BaseModel):
    semana: int
    tarea_id: Optional[str] = None
    completada: Optional[bool] = None
    casas_visitadas: Optional[int] = None
    personas_contactadas: Optional[int] = None
    personas_ganadas: Optional[int] = None
    oraciones_realizadas: Optional[int] = None
    notas: Optional[str] = None
    # Validaciones personales
    validacion_leyo_libro: Optional[bool] = None
    validacion_hizo_oraciones: Optional[bool] = None
    validacion_visito_casas: Optional[bool] = None


# --- Bitácora Evangelística del Líder ---
class JournalEntryCreate(BaseModel):
    fecha: str  # ISO date "YYYY-MM-DD"
    casas_visitadas: Optional[int] = 0
    personas_contactadas: Optional[int] = 0
    personas_ganadas: Optional[int] = 0
    oraciones_realizadas: Optional[int] = 0
    notas: Optional[str] = ""

    @field_validator(
        "casas_visitadas", "personas_contactadas", "personas_ganadas", "oraciones_realizadas",
        mode="before",
    )
    @classmethod
    def _empty_to_zero(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return 0
        return v


class JournalEntryUpdate(BaseModel):
    fecha: Optional[str] = None
    casas_visitadas: Optional[int] = None
    personas_contactadas: Optional[int] = None
    personas_ganadas: Optional[int] = None
    oraciones_realizadas: Optional[int] = None
    notas: Optional[str] = None

    @field_validator(
        "casas_visitadas", "personas_contactadas", "personas_ganadas", "oraciones_realizadas",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


# --- Auth Helpers ---
def create_token(
    user_id: str,
    email: str,
    rol: str,
    token_version: int,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None,
):
    if isinstance(token_version, bool) or not isinstance(token_version, int) or token_version < 1:
        raise ValueError("token_version must be a positive integer")

    payload = {
        "user_id": user_id,
        "email": email,
        "rol": rol,
        "token_version": token_version,
        "exp": utc_now() + (
            expires_delta if expires_delta is not None else timedelta(hours=ACCESS_TOKEN_EXPIRE)
        ),
    }
    if extra_claims:
        protected_claims = {"user_id", "email", "rol", "token_version", "exp"}
        payload.update({key: value for key, value in extra_claims.items() if key not in protected_claims})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalido")


async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")

    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="No autorizado")

    payload = verify_token(token)
    token_version = payload.get("token_version")
    user_id = payload.get("user_id")

    # BASE-01 intentionally invalidates legacy JWTs without token_version.
    if (
        isinstance(token_version, bool)
        or not isinstance(token_version, int)
        or token_version < 1
        or not isinstance(user_id, str)
        or not ObjectId.is_valid(user_id)
    ):
        raise HTTPException(status_code=401, detail="No autorizado")

    db_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not db_user or not user_is_active(db_user):
        raise HTTPException(status_code=401, detail="No autorizado")
    if token_version != user_token_version(db_user):
        raise HTTPException(status_code=401, detail="No autorizado")

    return payload


# --- P-001 Core de Personas (aditivo) ---
from core_person import router as core_person_router, ensure_indexes as core_person_ensure_indexes

app.include_router(core_person_router)

# --- P-001 Slice 2A Core Profile 360 (aditivo, read-model) ---
from core_profile import router as core_profile_router

app.include_router(core_profile_router)


# --- Default Checklists ---
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
        {"id": "s2_t1", "texto": "Salir a la invasión: tocar puertas casa por casa", "completada": False},
        {"id": "s2_t2", "texto": "Contactar a las personas de la lista de 30", "completada": False},
        {"id": "s2_t3", "texto": "Invitar a eventos de la iglesia y macrocélulas", "completada": False},
        {"id": "s2_t4", "texto": "Orar por las personas contactadas", "completada": False},
        {"id": "s2_t5", "texto": "Seguimiento diario a los contactados", "completada": False},
        {"id": "s2_t6", "texto": "Registrar respuestas y compromisos", "completada": False},
        {"id": "s2_t7", "texto": "Guerra espiritual contra resistencias", "completada": False},
    ],
    3: [
        {"id": "s3_t1", "texto": "Entregar libro MCD (Mi Conexión con Dios)", "completada": False},
        {"id": "s3_t2", "texto": "Visitar diariamente a personas que respondieron", "completada": False},
        {"id": "s3_t3", "texto": "Asegurar que confiesen las oraciones del libro", "completada": False},
        {"id": "s3_t4", "texto": "Enviar mensajes y notas de voz de seguimiento", "completada": False},
        {"id": "s3_t5", "texto": "Verificar por WhatsApp que lean y confiesen", "completada": False},
        {"id": "s3_t6", "texto": "Apretar ayunos durante la semana", "completada": False},
        {"id": "s3_t7", "texto": "Introducir el libro NPT al finalizar la semana", "completada": False},
    ],
    4: [
        {"id": "s4_t1", "texto": "Entregar libro NPT (Nací Para Triunfar)", "completada": False},
        {"id": "s4_t2", "texto": "Trabajar las oraciones del libro NPT (3 días)", "completada": False},
        {"id": "s4_t3", "texto": "Consolidar en las primeras 72 horas", "completada": False},
        {"id": "s4_t4", "texto": "Intercesión intensa contra los 7 espíritus peores", "completada": False},
        {"id": "s4_t5", "texto": "Preparar ceremonia de graduación NPT", "completada": False},
        {"id": "s4_t6", "texto": "Crear certificados con sello y firma de la iglesia", "completada": False},
        {"id": "s4_t7", "texto": "Realizar graduación e introducir LBS", "completada": False},
    ],
    5: [
        {"id": "s5_t1", "texto": "Iniciar proceso LBS 1 - Liberación", "completada": False},
        {"id": "s5_t2", "texto": "Trabajar liberación en 3 áreas: Persona, Casa, Tierra", "completada": False},
        {"id": "s5_t3", "texto": "Aplicar cuestionarios de áreas de atadura", "completada": False},
        {"id": "s5_t4", "texto": "Romper líneas de iniquidad identificadas", "completada": False},
        {"id": "s5_t5", "texto": "Ministración de renuncias y declaraciones", "completada": False},
        {"id": "s5_t6", "texto": "Liberación por capas (territorio, casa, persona)", "completada": False},
    ],
    6: [
        {"id": "s6_t1", "texto": "Trabajar LBS 2 - Bendición (llenar la casa vacía)", "completada": False},
        {"id": "s6_t2", "texto": "Llenar el corazón con fe y palabra", "completada": False},
        {"id": "s6_t3", "texto": "Reformar el alma con enseñanza continua", "completada": False},
        {"id": "s6_t4", "texto": "Cambiar pensamientos en la mente", "completada": False},
        {"id": "s6_t5", "texto": "Transformar hábitos y costumbres del cuerpo", "completada": False},
        {"id": "s6_t6", "texto": "Llenura del Espíritu Santo", "completada": False},
    ],
    7: [
        {"id": "s7_t1", "texto": "Trabajar LBS 3 - Sanidad (curar el corazón)", "completada": False},
        {"id": "s7_t2", "texto": "Enseñar sobre enfermedades espirituales", "completada": False},
        {"id": "s7_t3", "texto": "Sanar el afán y la ansiedad", "completada": False},
        {"id": "s7_t4", "texto": "Sanar la amargura y falta de perdón", "completada": False},
        {"id": "s7_t5", "texto": "Curar el corazón del dolor", "completada": False},
        {"id": "s7_t6", "texto": "Prevenir regreso de los 7 espíritus peores", "completada": False},
        {"id": "s7_t7", "texto": "Preparar para el Retiro Final", "completada": False},
    ],
}


# --- Startup ---
@app.on_event("startup")
async def startup():
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.contacts.create_index("user_id")
    await db.progress.create_index([("user_id", 1), ("semana", 1)])
    await db.checklists.create_index([("user_id", 1), ("semana", 1)])
    await db.people.create_index("leader_id")
    await db.people.create_index([("leader_id", 1), ("estado", 1)])
    await db.person_progress.create_index([("person_id", 1), ("semana", 1)])
    await db.person_checklists.create_index([("person_id", 1), ("semana", 1)])
    print("Database indexes created")

    # --- P-001 Core de Personas (aditivo) ---
    await core_person_ensure_indexes()
    print("Core Person (P-001) indexes created")


# --- Helpers para Estado Dinámico ---
# Constantes del programa
TOTAL_DAYS = 49  # 7 semanas * 7 días
GRACE_PERIOD_DAYS = 7  # Gracia al iniciar - nunca Meta Baja en los primeros 7 días
BEHIND_THRESHOLD = 10  # % por debajo del esperado para considerar Meta Baja
AHEAD_THRESHOLD = 10  # % por encima del esperado para considerar Excelente


def _as_datetime(value):
    """Convierte string ISO o datetime a datetime naive UTC."""
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", ""))
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except Exception:
            return datetime.utcnow()
    return datetime.utcnow()


async def calculate_person_progress_pct(person_id: str) -> float:
    """Calcula el % de progreso real de una persona basado en tareas completadas."""
    checklists = await db.person_checklists.find({"person_id": person_id}).to_list(100)
    total = 0
    done = 0
    for cl in checklists:
        for t in cl.get("tareas", []):
            total += 1
            if t.get("completada"):
                done += 1
    if total == 0:
        return 0.0
    return (done / total) * 100.0


def calculate_dynamic_status(created_at, actual_pct: float, days_override: Optional[int] = None):
    """
    Retorna el estado dinámico en base a días transcurridos y % real.
    - < 7 días: Recién Iniciado (gracia)
    - 100%: Excelente
    - actual >= esperado + 10%: Excelente
    - actual en ±10% del esperado: Bien
    - actual < esperado - 10%: Meta Baja
    """
    now = datetime.utcnow()
    created = _as_datetime(created_at)
    days_elapsed = days_override if days_override is not None else max(0, (now - created).days)
    expected_pct = min(100.0, (days_elapsed / TOTAL_DAYS) * 100.0)

    actual_pct = max(0.0, min(100.0, float(actual_pct or 0)))

    # Gracia inicial: nunca Meta Baja
    if days_elapsed < GRACE_PERIOD_DAYS:
        if actual_pct >= 100:
            key, label, color, icon = "excelente", "Excelente", "gold", "trophy"
        elif actual_pct >= 20:
            key, label, color, icon = "bien", "Bien", "turquoise", "check"
        else:
            key, label, color, icon = "recien_iniciado", "Recién Iniciado", "blue", "rocket"
    else:
        if actual_pct >= 100:
            key, label, color, icon = "excelente", "Excelente", "gold", "trophy"
        elif actual_pct >= expected_pct + AHEAD_THRESHOLD:
            key, label, color, icon = "excelente", "Excelente", "gold", "trophy"
        elif actual_pct >= expected_pct - BEHIND_THRESHOLD:
            key, label, color, icon = "bien", "Bien", "turquoise", "check"
        else:
            key, label, color, icon = "meta_baja", "Meta Baja", "orange", "alert"

    return {
        "key": key,
        "label": label,
        "color": color,
        "icon": icon,
        "actual_pct": round(actual_pct, 1),
        "expected_pct": round(expected_pct, 1),
        "days_elapsed": days_elapsed,
        "gap": round(actual_pct - expected_pct, 1),
    }


async def compute_person_status(person: dict) -> dict:
    """Calcula el estado dinámico de una persona a partir de su doc."""
    person_id = str(person["_id"])
    actual_pct = await calculate_person_progress_pct(person_id)
    # Usar fecha_primer_contacto si existe, si no created_at
    start = person.get("fecha_primer_contacto") or person.get("created_at")
    return calculate_dynamic_status(start, actual_pct)


async def compute_leader_aggregate_status(personas: list) -> dict:
    """
    Calcula el estado agregado de un líder como PROMEDIO de sus personas.
    - Promedio de % actual y % esperado sobre todas las personas
    - Si no tiene personas: neutro (Recién Iniciado)
    """
    if not personas:
        return {
            "key": "sin_personas",
            "label": "Sin Personas",
            "color": "gray",
            "icon": "users",
            "actual_pct": 0.0,
            "expected_pct": 0.0,
            "days_elapsed": 0,
            "gap": 0.0,
            "total_personas": 0,
        }

    total_actual = 0.0
    total_expected = 0.0
    total_days = 0
    count = 0
    for p in personas:
        pid = str(p["_id"])
        actual = await calculate_person_progress_pct(pid)
        start = p.get("fecha_primer_contacto") or p.get("created_at")
        created = _as_datetime(start)
        days = max(0, (datetime.utcnow() - created).days)
        expected = min(100.0, (days / TOTAL_DAYS) * 100.0)
        total_actual += actual
        total_expected += expected
        total_days += days
        count += 1

    avg_actual = total_actual / count
    avg_days = total_days // count

    # Usar misma lógica que persona individual pero con valores promedio
    status_obj = calculate_dynamic_status(
        created_at=datetime.utcnow() - timedelta(days=avg_days),
        actual_pct=avg_actual,
        days_override=avg_days,
    )
    status_obj["total_personas"] = count
    return status_obj




# --- Auth Routes ---
@app.post("/api/auth/register")
async def register(user: UserRegister):
    """Registro publico.
    - Si se provee invite_code: el codigo determina rol y leader_id
        (pastor master -> pastor; pastor -> lider; lider -> persona).
    - Si NO se provee invite_code: registro libre con el rol indicado en el body
        (default 'lider'). Esto restaura el comportamiento original simple.
    """
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Este correo ya esta registrado")

    code_clean = (user.invite_code or "").strip().upper()

    # ---------- Rama A: registro CON codigo de invitacion ----------
    if code_clean:
        invite = await db.invite_codes.find_one({"code": code_clean})
        if not invite:
            raise HTTPException(status_code=400, detail="Codigo de invitacion invalido")

        if invite.get("used_at"):
            raise HTTPException(status_code=400, detail="Este codigo ya fue utilizado")

        expires_at = invite.get("expires_at")
        if expires_at and datetime.now(timezone.utc) > expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=400, detail="Este codigo ha caducado")

        # Crear usuario con rol y leader_id del codigo
        assigned_rol = invite["role_to_assign"]
        assigned_leader_id = invite.get("leader_id_to_assign")

        hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
        user_doc = {
            "nombre": user.nombre,
            "email": user.email,
            "password": hashed.decode(),
            "rol": assigned_rol,
            "is_active": DEFAULT_IS_ACTIVE,
            "token_version": DEFAULT_TOKEN_VERSION,
            "leader_id": assigned_leader_id,
            "created_at": datetime.utcnow(),
            "registered_via_invite": code_clean,
        }
        result = await db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)

        # Marcar codigo como usado
        await db.invite_codes.update_one(
            {"_id": invite["_id"]},
            {"$set": {"used_at": datetime.now(timezone.utc), "used_by_user_id": user_id}},
        )

        # Si es persona, tambien crearla en la coleccion people (para CRUD del lider)
        if assigned_rol == "persona" and assigned_leader_id:
            await db.people.insert_one({
                "leader_id": assigned_leader_id,
                "user_id": user_id,
                "nombre": user.nombre,
                "email": user.email,
                "telefono": "",
                "edad": None,
                "estado": "contactado",
                "current_semana": 1,
                "created_at": datetime.utcnow(),
                "registered_via_invite": True,
            })
    # ---------- Rama B: registro LIBRE (sin codigo) ----------
    else:
        free_rol = (user.rol or "lider").strip().lower()
        if free_rol not in ("pastor", "lider", "persona"):
            free_rol = "lider"
        assigned_rol = free_rol
        assigned_leader_id = None

        hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
        user_doc = {
            "nombre": user.nombre,
            "email": user.email,
            "password": hashed.decode(),
            "rol": assigned_rol,
            "is_active": DEFAULT_IS_ACTIVE,
            "token_version": DEFAULT_TOKEN_VERSION,
            "leader_id": assigned_leader_id,
            "created_at": datetime.utcnow(),
        }
        result = await db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)

    # ---------- Inicializacion comun (checklists + progress) ----------
    # Initialize checklists for all 7 weeks
    for semana, tareas in DEFAULT_CHECKLISTS.items():
        await db.checklists.insert_one({
            "user_id": user_id,
            "semana": semana,
            "tareas": tareas,
            "updated_at": datetime.utcnow(),
        })

    # Initialize progress for all 7 weeks
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

    token = create_token(
        user_id,
        user.email,
        assigned_rol,
        user_token_version(user_doc),
    )
    return {
        "token": token,
        "user": {"id": user_id, "nombre": user.nombre, "email": user.email, "rol": assigned_rol},
    }


# =============================================================================
# INVITE CODES - Sistema de codigos de invitacion
# =============================================================================
import secrets
import string as _string

INVITE_CODE_TTL_DAYS = 30  # Caducidad de codigos no usados


def _generate_code(length: int = 8) -> str:
    """Genera un codigo alfanumerico (sin caracteres ambiguos)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin I, O, 0, 1
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _create_unique_code(length: int = 8, max_attempts: int = 10) -> str:
    for _ in range(max_attempts):
        code = _generate_code(length)
        existing = await db.invite_codes.find_one({"code": code})
        if not existing:
            return code
    raise HTTPException(status_code=500, detail="No fue posible generar un codigo unico, intenta de nuevo")


@app.post("/api/invite-codes")
async def create_invite_code(body: InviteCodeCreate, authorization: Optional[str] = Header(None)):
    """Genera un codigo de invitacion.
    - Pastor master / pastor  -> genera codigos para LIDER (nuevo lider no queda vinculado a nadie)
    - Lider                   -> genera codigos para PERSONA (queda vinculada a este lider)
    """
    payload = await get_current_user(authorization)
    rol = payload.get("rol")
    creator_id = payload["user_id"]

    if rol not in ("pastor", "lider"):
        raise HTTPException(status_code=403, detail="Solo pastores y lideres pueden generar codigos")

    # Determinar rol a asignar segun quien crea
    if rol == "pastor":
        role_to_assign = "lider"
        leader_id_to_assign = None  # lider raiz, no queda bajo otro lider
    else:
        role_to_assign = "persona"
        leader_id_to_assign = creator_id  # persona queda bajo este lider

    code = await _create_unique_code()
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_CODE_TTL_DAYS)

    doc = {
        "code": code,
        "created_by_user_id": creator_id,
        "created_by_rol": rol,
        "role_to_assign": role_to_assign,
        "leader_id_to_assign": leader_id_to_assign,
        "destinatario_nombre": (body.destinatario_nombre or "").strip(),
        "destinatario_email": (body.destinatario_email or "").strip().lower(),
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at,
        "used_at": None,
        "used_by_user_id": None,
    }
    result = await db.invite_codes.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    # Normalizar dates a isoformat
    for k in ("created_at", "expires_at"):
        if doc.get(k):
            doc[k] = doc[k].isoformat()
    return doc


@app.get("/api/invite-codes")
async def list_invite_codes(authorization: Optional[str] = Header(None)):
    """Lista los codigos que el usuario actual genero."""
    payload = await get_current_user(authorization)
    rol = payload.get("rol")
    creator_id = payload["user_id"]
    if rol not in ("pastor", "lider"):
        raise HTTPException(status_code=403, detail="Solo pastores y lideres pueden ver codigos")

    cursor = db.invite_codes.find({"created_by_user_id": creator_id}).sort("created_at", -1)
    items = []
    now_utc = datetime.now(timezone.utc)
    async for doc in cursor:
        expires_at = doc.get("expires_at")
        used_at = doc.get("used_at")
        # Estado: used | expired | active
        if used_at:
            estado = "usado"
        elif expires_at and (expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)) < now_utc:
            estado = "vencido"
        else:
            estado = "activo"

        items.append({
            "id": str(doc["_id"]),
            "code": doc["code"],
            "role_to_assign": doc.get("role_to_assign"),
            "destinatario_nombre": doc.get("destinatario_nombre", ""),
            "destinatario_email": doc.get("destinatario_email", ""),
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
            "expires_at": doc["expires_at"].isoformat() if doc.get("expires_at") else None,
            "used_at": doc["used_at"].isoformat() if doc.get("used_at") else None,
            "used_by_user_id": doc.get("used_by_user_id"),
            "estado": estado,
        })
    return items


@app.delete("/api/invite-codes/{code_id}")
async def revoke_invite_code(code_id: str, authorization: Optional[str] = Header(None)):
    """Revoca un codigo no usado (lo marca como vencido inmediatamente)."""
    payload = await get_current_user(authorization)
    creator_id = payload["user_id"]
    try:
        doc = await db.invite_codes.find_one({"_id": ObjectId(code_id), "created_by_user_id": creator_id})
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalido")

    if not doc:
        raise HTTPException(status_code=404, detail="Codigo no encontrado")

    if doc.get("used_at"):
        raise HTTPException(status_code=400, detail="No se puede revocar un codigo ya usado")

    # Marcar como vencido
    await db.invite_codes.update_one(
        {"_id": ObjectId(code_id)},
        {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}},
    )
    return {"ok": True, "message": "Codigo revocado"}





@app.post("/api/auth/login")
async def login(user: UserLogin):
    db_user = await db.users.find_one({"email": user.email})
    if not db_user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not bcrypt.checkpw(user.password.encode(), db_user["password"].encode()):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not user_is_active(db_user):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    user_id = str(db_user["_id"])
    token = create_token(
        user_id,
        db_user["email"],
        db_user["rol"],
        user_token_version(db_user),
    )
    return {"token": token, "user": {"id": user_id, "nombre": db_user["nombre"], "email": db_user["email"], "rol": db_user["rol"]}}


@app.get("/api/auth/me")
async def get_me(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    payload = await get_current_user(authorization)
    user = await db.users.find_one({"_id": ObjectId(payload["user_id"])})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"id": str(user["_id"]), "nombre": user["nombre"], "email": user["email"], "rol": user["rol"]}


# --- Contacts Routes ---
@app.get("/api/contacts")
async def get_contacts(authorization: Optional[str] = Header(None)):
    payload = await get_current_user(authorization)
    contacts = await db.contacts.find({"user_id": payload["user_id"]}).sort("created_at", -1).to_list(1000)
    return [serialize_doc(c) for c in contacts]


@app.post("/api/contacts")
async def create_contact(contact: ContactCreate, authorization: Optional[str] = Header(None)):
    payload = await get_current_user(authorization)
    doc = {
        "user_id": payload["user_id"],
        "nombre": contact.nombre,
        "telefono": contact.telefono,
        "direccion": contact.direccion,
        "relacion": contact.relacion,
        "estado": contact.estado,
        "semana_actual": contact.semana_actual,
        "notas": contact.notas,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.contacts.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@app.put("/api/contacts/{contact_id}")
async def update_contact(contact_id: str, contact: ContactUpdate, authorization: Optional[str] = Header(None)):
    payload = await get_current_user(authorization)
    update_data = {k: v for k, v in contact.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.contacts.update_one(
        {"_id": ObjectId(contact_id), "user_id": payload["user_id"]},
        {"$set": update_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    
    updated = await db.contacts.find_one({"_id": ObjectId(contact_id)})
    return serialize_doc(updated)


@app.delete("/api/contacts/{contact_id}")
async def delete_contact(contact_id: str, authorization: Optional[str] = Header(None)):
    payload = await get_current_user(authorization)
    result = await db.contacts.delete_one({"_id": ObjectId(contact_id), "user_id": payload["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return {"message": "Contacto eliminado"}


# --- Checklist Routes ---
@app.get("/api/checklists")
async def get_checklists(authorization: Optional[str] = Header(None)):
    payload = await get_current_user(authorization)
    checklists = await db.checklists.find({"user_id": payload["user_id"]}).sort("semana", 1).to_list(100)
    return [serialize_doc(c) for c in checklists]


@app.put("/api/checklists")
async def update_checklist(update: ChecklistUpdate, authorization: Optional[str] = Header(None)):
    payload = await get_current_user(authorization)
    checklist = await db.checklists.find_one({"user_id": payload["user_id"], "semana": update.semana})
    
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist no encontrado")
    
    tareas = checklist["tareas"]
    for t in tareas:
        if t["id"] == update.tarea_id:
            t["completada"] = update.completada
            break
    
    await db.checklists.update_one(
        {"_id": checklist["_id"]},
        {"$set": {"tareas": tareas, "updated_at": datetime.utcnow()}}
    )
    
    updated = await db.checklists.find_one({"_id": checklist["_id"]})
    return serialize_doc(updated)


# --- ADMIN: Diagnóstico y bootstrap de checklists/progress ---
@app.get("/api/admin/diagnose-users")
async def admin_diagnose_users(authorization: Optional[str] = Header(None)):
    """Solo pastor: diagnostica qué users tienen checklists/progress y cuáles no."""
    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores")

    users = await db.users.find({}).to_list(1000)
    report = []
    for u in users:
        uid = str(u["_id"])
        cl_count = await db.checklists.count_documents({"user_id": uid})
        pr_count = await db.progress.count_documents({"user_id": uid})
        ppl_count = await db.people.count_documents({"leader_id": uid})
        report.append({
            "user_id": uid,
            "nombre": u.get("nombre"),
            "email": u.get("email"),
            "rol": u.get("rol"),
            "leader_id": u.get("leader_id"),
            "checklists": cl_count,
            "progress": pr_count,
            "personas_asignadas": ppl_count,
            "needs_bootstrap": cl_count < 7 or pr_count < 7,
        })
    return {
        "total_users": len(users),
        "needs_bootstrap": sum(1 for r in report if r["needs_bootstrap"]),
        "users": report,
    }


@app.post("/api/admin/bootstrap-checklists")
async def admin_bootstrap_checklists(authorization: Optional[str] = Header(None)):
    """Solo pastor: para cada usuario que no tenga las 7 semanas de checklists/progress,
    las crea con los valores DEFAULT_CHECKLISTS. Idempotente: salta los que ya existen."""
    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores")

    users = await db.users.find({}).to_list(1000)
    fixed = []
    for u in users:
        uid = str(u["_id"])
        nombre = u.get("nombre", "?")
        cl_added = 0
        pr_added = 0
        # Checklists faltantes
        for semana, tareas in DEFAULT_CHECKLISTS.items():
            existing = await db.checklists.find_one({"user_id": uid, "semana": semana})
            if not existing:
                await db.checklists.insert_one({
                    "user_id": uid,
                    "semana": semana,
                    "tareas": [dict(t) for t in tareas],
                    "updated_at": datetime.utcnow(),
                })
                cl_added += 1
        # Progress faltantes
        for semana in range(1, 8):
            existing = await db.progress.find_one({"user_id": uid, "semana": semana})
            if not existing:
                await db.progress.insert_one({
                    "user_id": uid,
                    "semana": semana,
                    "casas_visitadas": 0,
                    "personas_contactadas": 0,
                    "personas_ganadas": 0,
                    "oraciones_realizadas": 0,
                    "updated_at": datetime.utcnow(),
                })
                pr_added += 1
        if cl_added or pr_added:
            fixed.append({
                "user_id": uid,
                "nombre": nombre,
                "email": u.get("email"),
                "checklists_creadas": cl_added,
                "progress_creados": pr_added,
            })
    return {"total_arreglados": len(fixed), "detalle": fixed}


# ----------------------------------------------------------------------------
# ADMIN: Sembrar datos de DEMO (personas, bitácora, progreso, tareas marcadas)
# ----------------------------------------------------------------------------
DEMO_PEOPLE_NAMES = [
    ("María González", "familiar", "femenino", 42, "casado", "Ama de casa"),
    ("José Ramírez", "amigo", "masculino", 35, "soltero", "Mecánico"),
    ("Carla Rodríguez", "vecino", "femenino", 28, "soltero", "Estudiante"),
    ("Pedro Hernández", "conocido", "masculino", 51, "casado", "Comerciante"),
    ("Ana Sánchez", "familiar", "femenino", 38, "divorciado", "Enfermera"),
    ("Luis Martínez", "amigo", "masculino", 29, "soltero", "Conductor"),
    ("Rosa Díaz", "vecino", "femenino", 47, "casado", "Maestra"),
    ("Carlos Pérez", "conocido", "masculino", 33, "union_libre", "Técnico"),
    ("Laura Torres", "familiar", "femenino", 26, "soltero", "Diseñadora"),
    ("Miguel Castro", "amigo", "masculino", 44, "casado", "Carpintero"),
    ("Patricia Vega", "vecino", "femenino", 31, "casado", "Contadora"),
    ("Roberto Silva", "conocido", "masculino", 39, "viudo", "Albañil"),
]

DEMO_NOTAS_BITACORA = [
    "Día de oración profética y visita a tres familias del sector.",
    "Salimos en equipo a tocar puertas. Dios abrió corazones.",
    "Reunión con personas en proceso. Confesaron las oraciones del libro MCD.",
    "Cierre del día con resultados. Hubo lágrimas de gratitud.",
    "Visita pastoral a familia en crisis. Oramos por sanidad.",
    "Entrega de libros LBS a graduados. Ceremonia simple y poderosa.",
    "Intercesión contra los 7 espíritus peores. Liberación visible.",
    "Día de ayuno y oración. Apretamos para que Dios respalde.",
    "Hicimos seguimiento por WhatsApp y notas de voz.",
    "Decoración del templo con tema GANAR. Todo el equipo activo.",
    "Visita a discípulos avanzados. Empiezan a impactar a otros.",
    "Reunión de obreros para repasar la estrategia 30-60-100.",
]


@app.post("/api/admin/seed-demo")
async def admin_seed_demo(authorization: Optional[str] = Header(None)):
    """Solo pastor: crea data de DEMO para los líderes existentes que no tengan personas.
    - 5-7 personas por líder en distintos estados (contactado, visitado, en_proceso, graduado)
    - Cada persona con sus 7 semanas de checklists/progress (algunas tareas completas)
    - 12-14 entradas de bitácora distribuidas en los últimos 21 días por líder
    - Marca algunas tareas del propio líder como completadas (para ver % de progreso)
    Idempotente: si un líder ya tiene personas creadas (>0) se salta.
    Marca todo con demo=True para poder limpiar después con /api/admin/clear-demo.
    """
    import random as _r
    import unicodedata as _ud
    import re as _re
    import string as _s

    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores")

    leaders = await db.users.find({"rol": "lider"}).to_list(1000)
    summary = []
    estados = ["contactado", "visitado", "en_proceso", "en_proceso", "graduado"]
    horarios = ["manana", "tarde", "noche"]

    name_pool = list(DEMO_PEOPLE_NAMES)
    _r.shuffle(name_pool)
    name_idx = 0

    for leader in leaders:
        leader_id = str(leader["_id"])
        leader_nombre = leader.get("nombre", "Líder")
        # ¿ya tiene personas?
        existing_count = await db.people.count_documents({"leader_id": leader_id})
        if existing_count > 0:
            summary.append({
                "lider": leader_nombre,
                "estado": "skipped",
                "razon": f"ya tiene {existing_count} personas",
            })
            continue

        n_people = _r.randint(5, 7)
        people_created = []
        for _ in range(n_people):
            if name_idx >= len(name_pool):
                _r.shuffle(name_pool)
                name_idx = 0
            nombre, relacion, genero, edad, estado_civil, ocupacion = name_pool[name_idx]
            name_idx += 1

            estado = _r.choice(estados)
            # Semana actual: graduados están en 7, otros distribuidos 1-6
            if estado == "graduado":
                semana_actual = 7
            else:
                semana_actual = _r.randint(1, 6)

            # Crear cuenta de usuario para la persona
            slug = _ud.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
            slug = _re.sub(r"[^a-zA-Z0-9]+", ".", slug).strip(".").lower() or "persona"
            username = f"{slug}{_r.randint(100, 999)}"
            # garantizar único
            for _try in range(5):
                if not await db.users.find_one({"email": f"{username}@consolidados.app"}):
                    break
                username = f"{slug}{_r.randint(100, 999)}"
            temp_password = "".join(_r.choices(_s.ascii_letters + _s.digits, k=8))
            hashed = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt()).decode()
            user_doc = {
                "email": f"{username}@consolidados.app",
                "password": hashed,
                "nombre": nombre,
                "rol": "persona",
                "is_active": DEFAULT_IS_ACTIVE,
                "token_version": DEFAULT_TOKEN_VERSION,
                "created_at": datetime.utcnow(),
                "demo": True,
            }
            user_res = await db.users.insert_one(user_doc)
            person_user_id = str(user_res.inserted_id)

            person_doc = {
                "user_id": person_user_id,
                "leader_id": leader_id,
                "nombre": nombre,
                "telefono": f"+1809{_r.randint(1000000, 9999999)}",
                "direccion": f"Calle {_r.choice(['Duarte','Mella','Sánchez','Independencia','Las Carreras'])} #{_r.randint(1,250)}",
                "relacion": relacion,
                "estado": estado,
                "semana_actual": semana_actual,
                "notas": _r.choice([
                    "Muestra mucho interés. Pide oración por su familia.",
                    "Tiene heridas del pasado, está en proceso de sanidad.",
                    "Asiste regularmente. Se conecta con el grupo.",
                    "Necesita seguimiento más cercano esta semana.",
                    "Avanza bien. Confiesa las oraciones del libro.",
                ]),
                "foto_url": "",
                "edad": edad,
                "genero": genero,
                "ocupacion": ocupacion,
                "estado_civil": estado_civil,
                "mejor_horario": _r.choice(horarios),
                "fecha_primer_contacto": (datetime.utcnow() - timedelta(days=_r.randint(7, 60))).isoformat(),
                "como_conocio_iglesia": _r.choice(["Por un familiar", "Vecino lo invitó", "Visita evangelística", "Redes sociales"]),
                "username": username,
                "temp_password": temp_password,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "demo": True,
            }
            p_res = await db.people.insert_one(person_doc)
            person_id = str(p_res.inserted_id)

            # Checklists para las 7 semanas - completar parcialmente según semana_actual
            for semana, tareas in DEFAULT_CHECKLISTS.items():
                if semana < semana_actual:
                    completion_pct = 1.0  # semanas pasadas: completas
                elif semana == semana_actual:
                    completion_pct = _r.uniform(0.3, 0.8)  # actual: parcial
                else:
                    completion_pct = 0.0  # futuras: vacías
                tareas_doc = []
                for t in tareas:
                    completed = _r.random() < completion_pct
                    tareas_doc.append({"id": t["id"], "texto": t["texto"], "completada": completed})
                await db.person_checklists.insert_one({
                    "person_id": person_id,
                    "leader_id": leader_id,
                    "semana": semana,
                    "tareas": tareas_doc,
                    "updated_at": datetime.utcnow(),
                    "demo": True,
                })

            # Progress para 7 semanas - números realistas
            for semana in range(1, 8):
                if semana <= semana_actual:
                    casas = _r.randint(15, 40)
                    contactadas = _r.randint(8, casas)
                    ganadas = _r.randint(0, max(1, contactadas // 3))
                    oraciones = _r.randint(20, 80)
                else:
                    casas = contactadas = ganadas = oraciones = 0
                await db.person_progress.insert_one({
                    "person_id": person_id,
                    "leader_id": leader_id,
                    "semana": semana,
                    "casas_visitadas": casas,
                    "personas_contactadas": contactadas,
                    "personas_ganadas": ganadas,
                    "oraciones_realizadas": oraciones,
                    "notas": "",
                    "updated_at": datetime.utcnow(),
                    "demo": True,
                })

            people_created.append({"id": person_id, "nombre": nombre, "estado": estado, "semana": semana_actual})

        # Bitácora del líder: 12-14 entradas en últimos 21 días
        n_entries = _r.randint(12, 14)
        used_dates = set()
        entries_created = 0
        for _ in range(n_entries):
            for _try in range(10):
                d = datetime.utcnow().date() - timedelta(days=_r.randint(0, 21))
                if d not in used_dates:
                    used_dates.add(d)
                    break
            casas = _r.randint(5, 25)
            contactadas = _r.randint(3, casas)
            ganadas = _r.randint(0, max(1, contactadas // 3))
            oraciones = _r.randint(10, 60)
            await db.leader_journal.insert_one({
                "leader_id": leader_id,
                "fecha": d.isoformat(),
                "casas_visitadas": casas,
                "personas_contactadas": contactadas,
                "personas_ganadas": ganadas,
                "oraciones_realizadas": oraciones,
                "notas": _r.choice(DEMO_NOTAS_BITACORA),
                "created_at": datetime.combine(d, datetime.min.time()).replace(hour=_r.randint(18, 22)),
                "updated_at": datetime.utcnow(),
                "demo": True,
            })
            entries_created += 1

        # Marcar tareas del líder como completadas (para ver % progreso)
        for cl in await db.checklists.find({"user_id": leader_id}).to_list(20):
            tareas = cl.get("tareas", [])
            n_complete = _r.randint(2, max(2, len(tareas) - 2))
            indices = _r.sample(range(len(tareas)), min(n_complete, len(tareas)))
            for i in indices:
                tareas[i]["completada"] = True
            await db.checklists.update_one({"_id": cl["_id"]}, {"$set": {"tareas": tareas, "updated_at": datetime.utcnow()}})

        # Progress propio del líder: poner números
        for semana in range(1, 8):
            casas = _r.randint(20, 50)
            contactadas = _r.randint(10, casas)
            ganadas = _r.randint(2, max(2, contactadas // 3))
            oraciones = _r.randint(30, 100)
            await db.progress.update_one(
                {"user_id": leader_id, "semana": semana},
                {"$set": {
                    "casas_visitadas": casas,
                    "personas_contactadas": contactadas,
                    "personas_ganadas": ganadas,
                    "oraciones_realizadas": oraciones,
                    "updated_at": datetime.utcnow(),
                }},
                upsert=True,
            )

        summary.append({
            "lider": leader_nombre,
            "estado": "creado",
            "personas_creadas": len(people_created),
            "personas": people_created,
            "bitacora_entradas": entries_created,
        })

    return {"summary": summary}


@app.post("/api/admin/clear-demo")
async def admin_clear_demo(authorization: Optional[str] = Header(None)):
    """Solo pastor: elimina TODOS los documentos marcados con demo=True.
    Útil para limpiar la data de prueba cuando ya no se necesite."""
    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores")

    cols = ["users", "people", "person_checklists", "person_progress", "leader_journal", "invite_codes"]
    deleted = {}
    for col in cols:
        try:
            r = await db[col].delete_many({"demo": True})
            deleted[col] = r.deleted_count
        except Exception as e:
            deleted[col] = f"error: {e}"
    return {"deleted": deleted}


@app.post("/api/admin/reset-leader-passwords")
async def admin_reset_leader_passwords(authorization: Optional[str] = Header(None)):
    """Solo pastor: resetea las contraseñas de TODOS los líderes a una conocida ('Lider2026!')
    para poder hacer login y probar la experiencia del líder. Devuelve email + password de cada uno."""
    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores")

    new_pwd = "Lider2026!"
    hashed = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt()).decode()
    leaders = await db.users.find({"rol": "lider"}).to_list(1000)
    out = []
    for u in leaders:
        await db.users.update_one({"_id": u["_id"]}, {"$set": {"password": hashed}})
        out.append({"nombre": u.get("nombre"), "email": u.get("email"), "password": new_pwd})
    return {"reset": len(out), "credenciales": out}


# --- Progress Routes ---
@app.get("/api/progress")
async def get_progress(authorization: Optional[str] = Header(None)):
    payload = await get_current_user(authorization)
    progress = await db.progress.find({"user_id": payload["user_id"]}).sort("semana", 1).to_list(100)
    return [serialize_doc(p) for p in progress]


@app.put("/api/progress")
async def update_progress(update: ProgressUpdate, authorization: Optional[str] = Header(None)):
    payload = await get_current_user(authorization)
    
    update_data = {
        "casas_visitadas": update.casas_visitadas,
        "personas_contactadas": update.personas_contactadas,
        "personas_ganadas": update.personas_ganadas,
        "oraciones_realizadas": update.oraciones_realizadas,
        "updated_at": datetime.utcnow(),
    }
    
    result = await db.progress.update_one(
        {"user_id": payload["user_id"], "semana": update.semana},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        # Maybe it doesn't exist, create it
        update_data["user_id"] = payload["user_id"]
        update_data["semana"] = update.semana
        await db.progress.insert_one(update_data)
    
    updated = await db.progress.find_one({"user_id": payload["user_id"], "semana": update.semana})
    return serialize_doc(updated)


# --- Dashboard Stats ---
@app.get("/api/dashboard")
async def get_dashboard(authorization: Optional[str] = Header(None)):
    payload = await get_current_user(authorization)
    user_id = payload["user_id"]
    
    # Get all progress
    progress_list = await db.progress.find({"user_id": user_id}).sort("semana", 1).to_list(100)
    
    # Get all checklists
    checklists = await db.checklists.find({"user_id": user_id}).sort("semana", 1).to_list(100)
    
    # Get contacts stats
    total_contacts = await db.contacts.count_documents({"user_id": user_id})
    contacts_by_status = {}
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$estado", "count": {"$sum": 1}}}
    ]
    async for doc in db.contacts.aggregate(pipeline):
        contacts_by_status[doc["_id"]] = doc["count"]
    
    # Calculate overall progress
    total_tasks = 0
    completed_tasks = 0
    checklist_by_week = {}
    for cl in checklists:
        week = cl["semana"]
        week_total = len(cl["tareas"])
        week_completed = sum(1 for t in cl["tareas"] if t["completada"])
        total_tasks += week_total
        completed_tasks += week_completed
        checklist_by_week[week] = {
            "total": week_total,
            "completed": week_completed,
            "percentage": round((week_completed / week_total * 100) if week_total > 0 else 0)
        }
    
    overall_percentage = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0)
    
    # Totals from progress
    total_casas = sum(p.get("casas_visitadas", 0) for p in progress_list)
    total_personas = sum(p.get("personas_contactadas", 0) for p in progress_list)
    total_ganadas = sum(p.get("personas_ganadas", 0) for p in progress_list)
    total_oraciones = sum(p.get("oraciones_realizadas", 0) for p in progress_list)
    
    return {
        "overall_progress": overall_percentage,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "checklist_by_week": checklist_by_week,
        "total_contacts": total_contacts,
        "contacts_by_status": contacts_by_status,
        "totals": {
            "casas_visitadas": total_casas,
            "personas_contactadas": total_personas,
            "personas_ganadas": total_ganadas,
            "oraciones_realizadas": total_oraciones,
        },
        "progress_by_week": [serialize_doc(p) for p in progress_list],
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Manual Ley 7 Semanas"}


# --- Image Proxy (same-origin workaround for PDF generation) ---
# Evita errores CORS cuando html2canvas intenta embeber imágenes externas.
# Solo permite dominios whitelisted para evitar abuso (SSRF mitigation).
_ALLOWED_IMAGE_HOSTS = {
    "customer-assets.emergentagent.com",
    "images.unsplash.com",
    "images.pexels.com",
}

@app.get("/api/proxy/image")
async def proxy_image(url: str):
    """Proxy para imágenes externas: las sirve desde la misma origen del backend
    evitando bloqueos CORS durante la generación del PDF (html2canvas)."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(status_code=400, detail="Esquema no soportado")
        if parsed.hostname not in _ALLOWED_IMAGE_HOSTS:
            raise HTTPException(status_code=403, detail=f"Dominio no permitido: {parsed.hostname}")

        import httpx
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/png")
            from fastapi.responses import Response
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener la imagen: {e}")


# --- Server-side PDF Generation via Playwright (Chromium headless) ---
# Fidelidad 100% porque usa el motor real del navegador (Chrome) ejecutado
# server-side. El cliente solo descarga el binario resultante.
#
# Requiere: PLAYWRIGHT_BROWSERS_PATH + chromium headless_shell instalado.
# El botón del frontend hace GET con Authorization Bearer y descarga el blob.

_PLAYWRIGHT_CHROMIUM_PATH = os.environ.get(
    "PLAYWRIGHT_CHROMIUM_PATH",
    "/pw-browsers/chromium_headless_shell-1208/chrome-linux/headless_shell",
)
# URL pública del frontend (para que el headless browser cargue la página
# exactamente como la ve el usuario). En producción ingress maneja todo.
_FRONTEND_PUBLIC_URL = os.environ.get("FRONTEND_PUBLIC_URL", "http://localhost:3000")


def _pick_frontend_url_from_request(request_url: Optional[str]) -> str:
    """URL del frontend para el headless browser.
    Preferimos localhost:3000 (dentro del contenedor) para evitar
    edge proxies (Cloudflare/ingress) que puedan rechazar requests sin cookies."""
    # Prioridad 1: variable de entorno explícita (producción puede apuntar a otro host)
    if os.environ.get("FRONTEND_PUBLIC_URL"):
        return os.environ["FRONTEND_PUBLIC_URL"]
    # Prioridad 2: siempre localhost en el contenedor
    return "http://localhost:3000"


@app.get("/api/manual/pdf")
async def generate_manual_pdf(request: Request, authorization: Optional[str] = Header(None)):
    """Genera el PDF del manual usando Chromium headless server-side.
    Fidelidad 100% — mismo motor del navegador que renderiza en pantalla."""
    payload = await get_current_user(authorization)
    if payload.get("rol") not in ("pastor", "lider"):
        raise HTTPException(status_code=403, detail="Solo líderes y pastores pueden descargar el manual")

    # Derivar URL del frontend desde el request actual (same-origin en prod)
    base_url = _pick_frontend_url_from_request(str(request.url) if request else None)
    target_url = f"{base_url}/presentacion/imprimir?pdf=1"

    # Emitimos un token efímero que el frontend usa para auto-login en la
    # sesión headless (localStorage) antes de cargar la ruta protegida.
    ephemeral_token = create_token(
        payload["user_id"],
        payload.get("email", ""),
        payload.get("rol", ""),
        payload["token_version"],
        expires_delta=timedelta(minutes=3),
        extra_claims={
            "nombre": payload.get("nombre", ""),
            "purpose": "pdf-render",
        },
    )

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(status_code=500, detail="Playwright no disponible")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                executable_path=_PLAYWRIGHT_CHROMIUM_PATH if os.path.exists(_PLAYWRIGHT_CHROMIUM_PATH) else None,
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            context = await browser.new_context(
                viewport={"width": 1200, "height": 900},
                device_scale_factor=2,
            )
            page = await context.new_page()

            # Inyectamos el token efímero en localStorage ANTES de cargar la ruta
            # protegida para simular una sesión autenticada.
            await context.add_init_script(
                f"""
                try {{
                    const token = {repr(ephemeral_token)};
                    const user = {{
                        id: {repr(payload['user_id'])},
                        rol: {repr(payload.get('rol', ''))},
                        nombre: {repr(payload.get('nombre', ''))},
                        email: {repr(payload.get('email', ''))},
                    }};
                    localStorage.setItem('token', token);
                    localStorage.setItem('user', JSON.stringify(user));
                }} catch(e) {{}}
                """
            )

            await page.goto(target_url, wait_until="networkidle", timeout=60000)

            # Esperar que TODAS las imágenes terminen de cargar (incluidas las
            # externas como infografías oficiales). Si alguna falla, seguimos
            # después del timeout de seguridad (8s por imagen).
            await page.evaluate(
                """
                () => Promise.all(
                    Array.from(document.images).map(img => {
                        if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                        return new Promise((resolve) => {
                            const done = () => { img.onload = null; img.onerror = null; resolve(); };
                            img.onload = done;
                            img.onerror = done;
                            setTimeout(done, 8000);
                        });
                    })
                )
                """
            )

            # Ocultar el badge de Emergent que el entorno preview inyecta
            await page.evaluate(
                """
                () => {
                    document.querySelectorAll('#emergent-badge, a[href*="emergent.sh"]').forEach(el => el.remove());
                }
                """
            )

            # Fuentes listas antes de rasterizar vectorialmente
            try:
                await page.evaluate("document.fonts && document.fonts.ready")
            except Exception:
                pass
            await page.wait_for_timeout(1500)

            pdf_bytes = await page.pdf(
                format="Letter",
                print_background=True,
                prefer_css_page_size=True,
                # Los márgenes reales se definen en el CSS @page (15/14/20/14mm)
                # — aquí los dejamos en 0 para NO duplicar.
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
                display_header_footer=False,
            )

            await browser.close()

        from fastapi.responses import Response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="Manual-La-Ley-de-las-7-Semanas.pdf"',
                "Cache-Control": "no-store",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {e}")


# --- Photo Upload ---
@app.post("/api/upload/photo")
async def upload_photo(photo_data: dict, authorization: Optional[str] = Header(None)):
    """Upload photo as base64 and return URL"""
    await get_current_user(authorization)  # Verify authenticated
    
    # In a real app, you'd upload to S3, Cloudinary, etc.
    # For now, we'll store base64 directly (not recommended for production)
    base64_data = photo_data.get("base64")
    if not base64_data:
        raise HTTPException(status_code=400, detail="No photo data provided")
    
    # Return the base64 data URL
    return {"url": base64_data}


# --- Pastor Notes ---
@app.post("/api/pastor/notes")
async def add_pastor_note(note_data: dict, authorization: Optional[str] = Header(None)):
    """Pastor deja nota a un líder"""
    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores pueden dejar notas")
    
    leader_id = note_data.get("leader_id")
    texto = note_data.get("texto")
    
    if not leader_id or not texto:
        raise HTTPException(status_code=400, detail="leader_id y texto son requeridos")
    
    doc = {
        "pastor_id": payload["user_id"],
        "pastor_nombre": payload.get("nombre", "Pastor"),
        "leader_id": leader_id,
        "texto": texto,
        "created_at": datetime.utcnow(),
    }
    result = await db.pastor_notes.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@app.get("/api/pastor/notes/{leader_id}")
async def get_pastor_notes(leader_id: str, authorization: Optional[str] = Header(None)):
    """Obtener notas del pastor para un líder"""
    await get_current_user(authorization)
    notes = await db.pastor_notes.find({"leader_id": leader_id}).sort("created_at", -1).to_list(100)
    return [serialize_doc(n) for n in notes]




# --- Notas de Presentación (editables por slide) ---

@app.post("/api/presentation/notes")
async def save_presentation_note(data: dict, authorization: Optional[str] = Header(None)):
    """Guardar nota personalizada del presentador por slide"""
    payload = await get_current_user(authorization)
    slide_id = data.get("slide_id")
    note_text = data.get("note_text", "")
    
    if not slide_id:
        raise HTTPException(status_code=400, detail="slide_id requerido")
    
    await db.presentation_notes.update_one(
        {"user_id": payload["user_id"], "slide_id": slide_id},
        {"$set": {"user_id": payload["user_id"], "slide_id": slide_id, "note_text": note_text, "updated_at": datetime.utcnow()}},
        upsert=True
    )
    return {"message": "Nota guardada"}

@app.get("/api/presentation/notes")
async def get_presentation_notes(authorization: Optional[str] = Header(None)):
    """Obtener todas las notas del presentador"""
    payload = await get_current_user(authorization)
    notes = await db.presentation_notes.find({"user_id": payload["user_id"]}).to_list(100)
    return {n["slide_id"]: n.get("note_text", "") for n in notes}

# --- Presentación: Sincronización Presenter ↔ Audience ---
import secrets

@app.post("/api/presentation/session")
async def create_presentation_session(authorization: Optional[str] = Header(None)):
    """Crea una sesión de presentación. Devuelve un código de 4 dígitos."""
    payload = await get_current_user(authorization)
    if payload.get("rol") not in ["pastor", "lider"]:
        raise HTTPException(status_code=403, detail="Solo pastores y líderes pueden presentar")

    # Generar código único de 4 dígitos
    for _ in range(10):
        code = ''.join(secrets.choice('0123456789') for _ in range(4))
        existing = await db.presentation_sessions.find_one({"code": code, "active": True})
        if not existing:
            break

    doc = {
        "code": code,
        "owner_id": payload["user_id"],
        "owner_name": payload.get("nombre", ""),
        "current_slide": 0,
        "active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await db.presentation_sessions.insert_one(doc)
    return {"code": code, "current_slide": 0}


@app.put("/api/presentation/session/{code}")
async def update_presentation_session(code: str, data: dict, authorization: Optional[str] = Header(None)):
    """Actualiza el slide actual de la sesión. Solo el dueño puede."""
    payload = await get_current_user(authorization)
    session = await db.presentation_sessions.find_one({"code": code, "active": True})
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    if session["owner_id"] != payload["user_id"]:
        raise HTTPException(status_code=403, detail="Solo el presentador puede controlar")

    current_slide = int(data.get("current_slide", 0))
    await db.presentation_sessions.update_one(
        {"code": code},
        {"$set": {"current_slide": current_slide, "updated_at": datetime.utcnow()}}
    )
    return {"code": code, "current_slide": current_slide}


@app.get("/api/presentation/session/{code}")
async def get_presentation_session(code: str):
    """Obtiene el estado actual de la sesión. Público (para audiencia)."""
    session = await db.presentation_sessions.find_one({"code": code, "active": True})
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return {
        "code": session["code"],
        "current_slide": session.get("current_slide", 0),
        "owner_name": session.get("owner_name", ""),
        "updated_at": session.get("updated_at").isoformat() if session.get("updated_at") else None,
    }


@app.delete("/api/presentation/session/{code}")
async def close_presentation_session(code: str, authorization: Optional[str] = Header(None)):
    """Cierra la sesión."""
    payload = await get_current_user(authorization)
    session = await db.presentation_sessions.find_one({"code": code})
    if not session:
        return {"success": True}
    if session["owner_id"] != payload["user_id"]:
        raise HTTPException(status_code=403, detail="Solo el presentador puede cerrar")
    await db.presentation_sessions.update_one({"code": code}, {"$set": {"active": False}})
    return {"success": True}


# --- Gestión de Pastores (solo pastores) ---
@app.get("/api/pastor/pastors")
async def list_pastors(authorization: Optional[str] = Header(None)):
    """Listar todos los pastores. Solo accesible por pastores."""
    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores pueden ver la lista de pastores")
    pastors = await db.users.find({"rol": "pastor"}).sort("created_at", 1).to_list(1000)
    return [
        {
            "_id": str(p["_id"]),
            "nombre": p.get("nombre", ""),
            "email": p.get("email", ""),
            "created_at": p.get("created_at").isoformat() if p.get("created_at") else None,
            "is_current": str(p["_id"]) == payload["user_id"],
        }
        for p in pastors
    ]


@app.post("/api/pastor/pastors")
async def create_pastor(data: dict, authorization: Optional[str] = Header(None)):
    """Crear nueva cuenta de pastor con acceso maestro. Solo pastores existentes."""
    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores pueden crear otros pastores")

    nombre = (data.get("nombre") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not nombre or not email or not password:
        raise HTTPException(status_code=400, detail="Nombre, email y contraseña son requeridos")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    # Validar email no exista
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    doc = {
        "nombre": nombre,
        "email": email,
        "password": hashed,
        "rol": "pastor",
        "is_active": DEFAULT_IS_ACTIVE,
        "token_version": DEFAULT_TOKEN_VERSION,
        "created_at": datetime.utcnow(),
        "created_by": payload["user_id"],
    }
    result = await db.users.insert_one(doc)
    return {
        "_id": str(result.inserted_id),
        "nombre": nombre,
        "email": email,
        "rol": "pastor",
        "created_at": doc["created_at"].isoformat(),
    }


@app.delete("/api/pastor/pastors/{pastor_id}")
async def delete_pastor(pastor_id: str, authorization: Optional[str] = Header(None)):
    """Eliminar una cuenta de pastor. No se puede auto-eliminar."""
    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores pueden eliminar pastores")

    if pastor_id == payload["user_id"]:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")

    # Evitar eliminar si queda 1 solo pastor
    total = await db.users.count_documents({"rol": "pastor"})
    if total <= 1:
        raise HTTPException(status_code=400, detail="Debe existir al menos un pastor en el sistema")

    target = await db.users.find_one({"_id": ObjectId(pastor_id), "rol": "pastor"})
    if not target:
        raise HTTPException(status_code=404, detail="Pastor no encontrado")

    await db.users.delete_one({"_id": ObjectId(pastor_id)})
    return {"success": True, "message": f"Pastor {target.get('nombre')} eliminado"}


@app.post("/api/pastor/pastors/{pastor_id}/reset-password")
async def reset_pastor_password(pastor_id: str, data: dict, authorization: Optional[str] = Header(None)):
    """Resetear la contraseña de un pastor. Solo otros pastores."""
    payload = await get_current_user(authorization)
    if payload.get("rol") != "pastor":
        raise HTTPException(status_code=403, detail="Solo pastores pueden resetear contraseñas de pastores")

    new_password = data.get("password") or ""
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    target = await db.users.find_one({"_id": ObjectId(pastor_id), "rol": "pastor"})
    if not target:
        raise HTTPException(status_code=404, detail="Pastor no encontrado")

    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    await db.users.update_one({"_id": ObjectId(pastor_id)}, {"$set": {"password": hashed}})
    return {"success": True, "message": "Contraseña actualizada correctamente"}




# --- Password Reset for Persons ---
@app.post("/api/people/{person_id}/reset-password")
async def reset_person_password(person_id: str, authorization: Optional[str] = Header(None)):
    """Resetear contraseña de una persona (solo líder de esa persona)"""
    payload = await get_current_user(authorization)
    leader_id = payload["user_id"]
    
    # Verificar que la persona pertenece a este líder
    person = await db.people.find_one({"_id": ObjectId(person_id), "leader_id": leader_id})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    
    # Generar nueva contraseña
    import random
    import string
    new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    
    # Actualizar en users
    user_id = person.get("user_id")
    if user_id:
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password": hashed_password}}
        )
    
    # Actualizar temp_password en people
    await db.people.update_one(
        {"_id": ObjectId(person_id)},
        {"$set": {"temp_password": new_password, "updated_at": datetime.utcnow()}}
    )
    
    return {
        "username": person.get("username"),
        "new_password": new_password
    }


# --- Dashboard según Rol ---
@app.get("/api/dashboard/role-based")
async def get_dashboard_by_role(authorization: Optional[str] = Header(None), leader_id: Optional[str] = None):
    """Retorna dashboard según el rol del usuario"""
    payload = await get_current_user(authorization)
    user_id = payload["user_id"]
    rol = payload.get("rol", "lider")
    
    # Si es pastor y especifica leader_id, muestra dashboard de ese líder
    if rol == "pastor" and leader_id:
        # Pastor viendo dashboard de un líder específico
        lider = await db.users.find_one({"_id": ObjectId(leader_id)})
        if not lider:
            raise HTTPException(status_code=404, detail="Líder no encontrado")
        
        # Dashboard del líder visto por el pastor
        total_personas = await db.people.count_documents({"leader_id": leader_id})
        by_status = {}
        for estado in ["contactado", "visitado", "en_proceso", "graduado", "inactivo"]:
            count = await db.people.count_documents({"leader_id": leader_id, "estado": estado})
            by_status[estado] = count
        
        personas = await db.people.find({"leader_id": leader_id}).to_list(1000)
        personas_con_estado = []
        personas_meta_baja = []
        for p in personas:
            estado_din = await compute_person_status(p)
            p_ser = serialize_doc(p)
            p_ser["estado_dinamico"] = estado_din
            personas_con_estado.append(p_ser)
            if estado_din["key"] == "meta_baja":
                personas_meta_baja.append(p_ser)
        
        estado_agregado = await compute_leader_aggregate_status(personas)
        
        # Obtener notas del pastor para este líder
        notes = await db.pastor_notes.find({"leader_id": leader_id}).sort("created_at", -1).to_list(10)
        
        return {
            "rol": "pastor_viewing_lider",
            "lider": serialize_doc(lider),
            "total_personas": total_personas,
            "por_estado": by_status,
            "personas": personas_con_estado,
            "personas_meta_baja": personas_meta_baja[:10],
            "estado_agregado": estado_agregado,
            "pastor_notes": [serialize_doc(n) for n in notes],
        }
    
    if rol == "pastor":
        # Dashboard General del Pastor - ve todos los líderes
        lideres = await db.users.find({"rol": "lider"}).to_list(1000)
        lideres_data = []
        
        for lider in lideres:
            lider_id = str(lider["_id"])
            # Contar personas por líder
            total_personas = await db.people.count_documents({"leader_id": lider_id})
            activas = await db.people.count_documents({"leader_id": lider_id, "estado": "en_proceso"})
            graduadas = await db.people.count_documents({"leader_id": lider_id, "estado": "graduado"})
            
            # Obtener todas las personas para calcular estado dinámico
            personas_docs = await db.people.find({"leader_id": lider_id}).to_list(1000)
            # Promedio de semana actual
            pipeline = [
                {"$match": {"leader_id": lider_id}},
                {"$group": {"_id": None, "avg_semana": {"$avg": "$semana_actual"}}}
            ]
            avg_result = await db.people.aggregate(pipeline).to_list(1)
            promedio_semana = round(avg_result[0]["avg_semana"], 1) if avg_result else 0
            
            # Estado dinámico agregado (promedio de sus personas)
            estado_dinamico = await compute_leader_aggregate_status(personas_docs)
            
            lideres_data.append({
                "_id": lider_id,
                "nombre": lider.get("nombre", ""),
                "email": lider.get("email", ""),
                "total_personas": total_personas,
                "activas": activas,
                "graduadas": graduadas,
                "promedio_semana": promedio_semana,
                "estado": estado_dinamico,
                # Compat: flag legacy
                "meta_baja": estado_dinamico["key"] == "meta_baja",
            })
        
        return {
            "rol": "pastor",
            "lideres": lideres_data,
            "total_lideres": len(lideres_data),
            "total_personas_global": sum(l["total_personas"] for l in lideres_data),
        }
    
    elif rol == "lider":
        # Dashboard del Líder - ve sus personas
        total_personas = await db.people.count_documents({"leader_id": user_id})
        by_status = {}
        for estado in ["contactado", "visitado", "en_proceso", "graduado", "inactivo"]:
            count = await db.people.count_documents({"leader_id": user_id, "estado": estado})
            by_status[estado] = count
        
        # Calcular estado dinámico para cada persona
        personas = await db.people.find({"leader_id": user_id}).to_list(1000)
        personas_con_estado = []
        personas_meta_baja = []
        for p in personas:
            estado_din = await compute_person_status(p)
            p_ser = serialize_doc(p)
            p_ser["estado_dinamico"] = estado_din
            personas_con_estado.append(p_ser)
            if estado_din["key"] == "meta_baja":
                personas_meta_baja.append(p_ser)
        
        # Estado agregado del líder
        estado_agregado = await compute_leader_aggregate_status(personas)
        
        # Obtener notas del pastor
        notes = await db.pastor_notes.find({"leader_id": user_id}).sort("created_at", -1).to_list(10)
        
        return {
            "rol": "lider",
            "total_personas": total_personas,
            "por_estado": by_status,
            "personas": personas_con_estado,
            "personas_meta_baja": personas_meta_baja[:10],
            "estado_agregado": estado_agregado,
            "pastor_notes": [serialize_doc(n) for n in notes],
        }
    
    elif rol == "persona":
        # Dashboard Personal - ve solo su progreso
        person = await db.people.find_one({"user_id": user_id})
        if not person:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        
        person_id = str(person["_id"])
        semana_actual = person.get("semana_actual", 1)
        
        # Obtener progreso de todas las semanas
        progress_all = await db.person_progress.find({"person_id": person_id}).sort("semana", 1).to_list(100)
        checklists_all = await db.person_checklists.find({"person_id": person_id}).sort("semana", 1).to_list(100)
        
        # Calcular estrellas ganadas
        estrellas = 0
        for cl in checklists_all:
            tareas = cl.get("tareas", [])
            if tareas:
                completadas = sum(1 for t in tareas if t.get("completada", False))
                if completadas == len(tareas):
                    estrellas += 1
        
        # Calcular progreso general
        total_tasks = sum(len(cl.get("tareas", [])) for cl in checklists_all)
        completed_tasks = sum(sum(1 for t in cl.get("tareas", []) if t.get("completada", False)) for cl in checklists_all)
        progreso_general = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
        
        # Estado dinámico de la persona
        start_date = person.get("fecha_primer_contacto") or person.get("created_at")
        estado_dinamico = calculate_dynamic_status(start_date, progreso_general)
        
        return {
            "rol": "persona",
            "person": serialize_doc(person),
            "semana_actual": semana_actual,
            "estrellas": estrellas,
            "progreso_general": progreso_general,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "estado_dinamico": estado_dinamico,
            "progress": [serialize_doc(p) for p in progress_all],
            "checklists": [serialize_doc(c) for c in checklists_all],
        }
    
    else:
        raise HTTPException(status_code=403, detail="Rol no reconocido")


# --- People/Consolidados Routes ---
@app.get("/api/people")
async def get_people(authorization: Optional[str] = Header(None), estado: Optional[str] = None):
    """Obtener todas las personas bajo el líder actual"""
    payload = await get_current_user(authorization)
    if payload.get("rol") not in ("lider", "pastor"):
        raise HTTPException(status_code=403, detail="Solo líderes y pastores pueden listar personas")
    leader_id = payload["user_id"]
    
    query = {"leader_id": leader_id}
    if estado:
        query["estado"] = estado
    
    people = await db.people.find(query).sort("created_at", -1).to_list(1000)
    return [serialize_doc(p) for p in people]


@app.post("/api/people")
async def create_person(person: PersonCreate, authorization: Optional[str] = Header(None)):
    """Crear una nueva persona para consolidar"""
    payload = await get_current_user(authorization)
    if payload.get("rol") not in ("lider", "pastor"):
        raise HTTPException(status_code=403, detail="Solo líderes y pastores pueden crear personas")
    leader_id = payload["user_id"]
    
    # Generate unique username and password for the person.
    # Normalizamos acentos y caracteres no-ASCII para que el email resultante
    # pase la validación de EmailStr en login y sea compatible con cualquier SMTP.
    import random
    import string
    import re
    import unicodedata
    nombre_norm = unicodedata.normalize('NFKD', person.nombre).encode('ascii', 'ignore').decode('ascii')
    nombre_norm = re.sub(r'[^a-zA-Z0-9\s]', '', nombre_norm).strip().lower()
    nombre_norm = re.sub(r'\s+', '.', nombre_norm) or 'persona'
    # Garantizar unicidad: intentar varios sufijos hasta encontrar uno libre
    username = None
    for _ in range(10):
        candidate = f"{nombre_norm}{random.randint(100, 999)}"
        existing = await db.users.find_one({"email": f"{candidate}@consolidados.app"})
        if not existing:
            username = candidate
            break
    if not username:
        # Fallback: sufijo largo aleatorio prácticamente único
        username = f"{nombre_norm}{''.join(random.choices(string.digits, k=6))}"
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    hashed_password = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt()).decode()
    
    # Create user account for the person
    user_doc = {
        "email": f"{username}@consolidados.app",
        "password": hashed_password,
        "nombre": person.nombre,
        "rol": "persona",
        "is_active": DEFAULT_IS_ACTIVE,
        "token_version": DEFAULT_TOKEN_VERSION,
        "created_at": datetime.utcnow(),
    }
    user_result = await db.users.insert_one(user_doc)
    person_user_id = str(user_result.inserted_id)
    
    doc = {
        "user_id": person_user_id,  # Link to user account
        "leader_id": leader_id,
        "nombre": person.nombre,
        "telefono": person.telefono,
        "direccion": person.direccion,
        "relacion": person.relacion,
        "estado": person.estado,
        "semana_actual": person.semana_actual,
        "notas": person.notas,
        "foto_url": person.foto_url,
        "edad": person.edad,
        "genero": person.genero,
        "ocupacion": person.ocupacion,
        "estado_civil": person.estado_civil,
        "mejor_horario": person.mejor_horario,
        "fecha_primer_contacto": person.fecha_primer_contacto or datetime.utcnow().isoformat(),
        "como_conocio_iglesia": person.como_conocio_iglesia,
        "username": username,
        "temp_password": temp_password,  # Store temporarily to show to leader
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.people.insert_one(doc)
    person_id = str(result.inserted_id)
    
    # Initialize checklists for all 7 weeks for this person
    for semana, tareas in DEFAULT_CHECKLISTS.items():
        await db.person_checklists.insert_one({
            "person_id": person_id,
            "leader_id": leader_id,
            "semana": semana,
            "tareas": [{"id": t["id"], "texto": t["texto"], "completada": False} for t in tareas],
            "updated_at": datetime.utcnow(),
        })
    
    # Initialize progress for all 7 weeks for this person
    for semana in range(1, 8):
        await db.person_progress.insert_one({
            "person_id": person_id,
            "leader_id": leader_id,
            "semana": semana,
            "casas_visitadas": 0,
            "personas_contactadas": 0,
            "personas_ganadas": 0,
            "oraciones_realizadas": 0,
            "notas": "",
            "updated_at": datetime.utcnow(),
        })
    
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


@app.get("/api/people/{person_id}")
async def get_person(person_id: str, authorization: Optional[str] = Header(None)):
    """Obtener detalle de una persona específica"""
    payload = await get_current_user(authorization)
    leader_id = payload["user_id"]
    
    person = await db.people.find_one({"_id": ObjectId(person_id), "leader_id": leader_id})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    
    return serialize_doc(person)


@app.put("/api/people/{person_id}")
async def update_person(person_id: str, person: PersonUpdate, authorization: Optional[str] = Header(None)):
    """Actualizar información de una persona"""
    payload = await get_current_user(authorization)
    leader_id = payload["user_id"]
    
    update_data = {k: v for k, v in person.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.people.update_one(
        {"_id": ObjectId(person_id), "leader_id": leader_id},
        {"$set": update_data}
    )
    if result.modified_count == 0 and result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    
    updated = await db.people.find_one({"_id": ObjectId(person_id)})
    return serialize_doc(updated)


@app.delete("/api/people/{person_id}")
async def delete_person(person_id: str, authorization: Optional[str] = Header(None)):
    """Eliminar una persona (y todo su progreso asociado)"""
    payload = await get_current_user(authorization)
    if payload.get("rol") not in ("lider", "pastor"):
        raise HTTPException(status_code=403, detail="Solo líderes y pastores pueden eliminar personas")
    leader_id = payload["user_id"]
    
    # Delete person
    result = await db.people.delete_one({"_id": ObjectId(person_id), "leader_id": leader_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    
    # Delete associated progress and checklists
    await db.person_progress.delete_many({"person_id": person_id})
    await db.person_checklists.delete_many({"person_id": person_id})
    
    return {"message": "Persona eliminada"}


@app.get("/api/people/{person_id}/progress")
async def get_person_progress(person_id: str, authorization: Optional[str] = Header(None), semana: Optional[int] = None):
    """Obtener progreso de una persona (todas las semanas o una específica)"""
    payload = await get_current_user(authorization)
    leader_id = payload["user_id"]
    
    # Verify person belongs to leader
    person = await db.people.find_one({"_id": ObjectId(person_id), "leader_id": leader_id})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    
    query = {"person_id": person_id}
    if semana:
        query["semana"] = semana
    
    progress = await db.person_progress.find(query).sort("semana", 1).to_list(100)
    return [serialize_doc(p) for p in progress]


@app.put("/api/people/{person_id}/progress")
async def update_person_progress(person_id: str, update: PersonProgressUpdate, authorization: Optional[str] = Header(None)):
    """Actualizar progreso de una persona en una semana específica"""
    payload = await get_current_user(authorization)
    leader_id = payload["user_id"]
    
    # Verify person belongs to leader
    person = await db.people.find_one({"_id": ObjectId(person_id), "leader_id": leader_id})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    
    # If updating a checklist task
    if update.tarea_id is not None and update.completada is not None:
        checklist = await db.person_checklists.find_one({
            "person_id": person_id,
            "semana": update.semana
        })
        
        if checklist:
            tareas = checklist["tareas"]
            for t in tareas:
                if t["id"] == update.tarea_id:
                    t["completada"] = update.completada
                    break
            
            await db.person_checklists.update_one(
                {"_id": checklist["_id"]},
                {"$set": {"tareas": tareas, "updated_at": datetime.utcnow()}}
            )
    
    # Update progress counters
    update_data = {}
    if update.casas_visitadas is not None:
        update_data["casas_visitadas"] = update.casas_visitadas
    if update.personas_contactadas is not None:
        update_data["personas_contactadas"] = update.personas_contactadas
    if update.personas_ganadas is not None:
        update_data["personas_ganadas"] = update.personas_ganadas
    if update.oraciones_realizadas is not None:
        update_data["oraciones_realizadas"] = update.oraciones_realizadas
    if update.notas is not None:
        update_data["notas"] = update.notas
    # Validaciones personales
    if update.validacion_leyo_libro is not None:
        update_data["validacion_leyo_libro"] = update.validacion_leyo_libro
    if update.validacion_hizo_oraciones is not None:
        update_data["validacion_hizo_oraciones"] = update.validacion_hizo_oraciones
    if update.validacion_visito_casas is not None:
        update_data["validacion_visito_casas"] = update.validacion_visito_casas
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.person_progress.update_one(
            {"person_id": person_id, "semana": update.semana},
            {"$set": update_data}
        )
    
    # Return updated progress
    progress = await db.person_progress.find_one({"person_id": person_id, "semana": update.semana})
    return serialize_doc(progress)


@app.get("/api/people/{person_id}/checklists")
async def get_person_checklists(person_id: str, authorization: Optional[str] = Header(None), semana: Optional[int] = None):
    """Obtener checklists de una persona (todas las semanas o una específica)"""
    payload = await get_current_user(authorization)
    leader_id = payload["user_id"]
    
    # Verify person belongs to leader
    person = await db.people.find_one({"_id": ObjectId(person_id), "leader_id": leader_id})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    
    query = {"person_id": person_id}
    if semana:
        query["semana"] = semana
    
    checklists = await db.person_checklists.find(query).sort("semana", 1).to_list(100)
    return [serialize_doc(c) for c in checklists]


@app.get("/api/stats")
async def get_stats(authorization: Optional[str] = Header(None)):
    """Obtener estadísticas reales agregadas de todas las personas del líder"""
    payload = await get_current_user(authorization)
    leader_id = payload["user_id"]
    
    # Total people
    total_people = await db.people.count_documents({"leader_id": leader_id})
    
    # People by status
    people_by_status = {}
    pipeline = [
        {"$match": {"leader_id": leader_id}},
        {"$group": {"_id": "$estado", "count": {"$sum": 1}}}
    ]
    async for doc in db.people.aggregate(pipeline):
        people_by_status[doc["_id"]] = doc["count"]
    
    # People by week
    people_by_week = {}
    pipeline = [
        {"$match": {"leader_id": leader_id}},
        {"$group": {"_id": "$semana_actual", "count": {"$sum": 1}}}
    ]
    async for doc in db.people.aggregate(pipeline):
        people_by_week[f"S{doc['_id']}"] = doc["count"]
    
    # Aggregate totals from the leader's JOURNAL (new source of truth).
    # Nota: antes estos totales se sumaban desde person_progress (cada persona).
    # Eso era conceptualmente incorrecto. Ahora el líder registra su jornada
    # evangelística en /api/journal y esa es la fuente oficial de los contadores.
    pipeline_journal = [
        {"$match": {"leader_id": leader_id}},
        {"$group": {
            "_id": None,
            "casas_visitadas": {"$sum": "$casas_visitadas"},
            "personas_contactadas": {"$sum": "$personas_contactadas"},
            "personas_ganadas": {"$sum": "$personas_ganadas"},
            "oraciones_realizadas": {"$sum": "$oraciones_realizadas"},
        }},
    ]
    journal_agg = await db.leader_journal.aggregate(pipeline_journal).to_list(1)
    if journal_agg:
        total_casas = int(journal_agg[0].get("casas_visitadas", 0) or 0)
        total_contactadas = int(journal_agg[0].get("personas_contactadas", 0) or 0)
        total_ganadas = int(journal_agg[0].get("personas_ganadas", 0) or 0)
        total_oraciones = int(journal_agg[0].get("oraciones_realizadas", 0) or 0)
    else:
        total_casas = total_contactadas = total_ganadas = total_oraciones = 0
    
    # Activity by week (aggregate progress data by week)
    activity_by_week = {}
    for semana in range(1, 8):
        week_progress = await db.person_progress.find({"leader_id": leader_id, "semana": semana}).to_list(1000)
        activity_count = sum(
            p.get("casas_visitadas", 0) + p.get("personas_contactadas", 0) + p.get("personas_ganadas", 0)
            for p in week_progress
        )
        activity_by_week[f"S{semana}"] = activity_count
    
    # Calculate overall task completion percentage
    all_checklists = await db.person_checklists.find({"leader_id": leader_id}).to_list(10000)
    total_tasks = 0
    completed_tasks = 0
    for cl in all_checklists:
        for t in cl.get("tareas", []):
            total_tasks += 1
            if t.get("completada", False):
                completed_tasks += 1
    
    overall_completion = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
    
    return {
        "total_people": total_people,
        "people_by_status": people_by_status,
        "people_by_week": people_by_week,
        "totals": {
            "casas_visitadas": total_casas,
            "personas_contactadas": total_contactadas,
            "personas_ganadas": total_ganadas,
            "oraciones_realizadas": total_oraciones,
        },
        "activity_by_week": activity_by_week,
        "overall_completion": overall_completion,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
    }



# ============================================================
# BITÁCORA EVANGELÍSTICA DEL LÍDER (jornadas de trabajo en el campo)
# ============================================================
# Modelo: cada entrada es un registro diario del esfuerzo evangelístico del líder.
# Separado del progreso individual de cada consolidado (que ahora usa solo checklist).

def _today_iso():
    return datetime.utcnow().date().isoformat()


def _week_start_iso():
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def _month_start_iso():
    today = datetime.utcnow().date()
    return today.replace(day=1).isoformat()


def _serialize_journal(doc: dict) -> dict:
    out = {
        "id": str(doc["_id"]),
        "leader_id": doc.get("leader_id", ""),
        "leader_name": doc.get("leader_name", ""),
        "fecha": doc.get("fecha", ""),
        "casas_visitadas": doc.get("casas_visitadas", 0),
        "personas_contactadas": doc.get("personas_contactadas", 0),
        "personas_ganadas": doc.get("personas_ganadas", 0),
        "oraciones_realizadas": doc.get("oraciones_realizadas", 0),
        "notas": doc.get("notas", ""),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }
    return out


@app.post("/api/journal")
async def create_journal_entry(entry: JournalEntryCreate, authorization: Optional[str] = Header(None)):
    """Crear una entrada de bitácora del líder. Solo líderes y pastores."""
    payload = await get_current_user(authorization)
    if payload.get("rol") not in ("lider", "pastor"):
        raise HTTPException(status_code=403, detail="Solo líderes y pastores pueden registrar bitácora")

    doc = {
        "leader_id": payload["user_id"],
        "leader_name": payload.get("nombre", ""),
        "fecha": entry.fecha or _today_iso(),
        "casas_visitadas": int(entry.casas_visitadas or 0),
        "personas_contactadas": int(entry.personas_contactadas or 0),
        "personas_ganadas": int(entry.personas_ganadas or 0),
        "oraciones_realizadas": int(entry.oraciones_realizadas or 0),
        "notas": (entry.notas or "").strip(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.leader_journal.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize_journal(doc)


@app.get("/api/journal")
async def list_journal_entries(
    authorization: Optional[str] = Header(None),
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    limit: int = 100,
):
    """Listar entradas de bitácora del líder autenticado (o de todos si es pastor)."""
    payload = await get_current_user(authorization)
    query: dict = {}
    if payload.get("rol") == "lider":
        query["leader_id"] = payload["user_id"]
    # Pastor ve todas por defecto; puede filtrar después en frontend por leader_id si lo necesita.

    if desde:
        query.setdefault("fecha", {})["$gte"] = desde
    if hasta:
        query.setdefault("fecha", {})["$lte"] = hasta

    cursor = db.leader_journal.find(query).sort("fecha", -1).limit(max(1, min(int(limit or 100), 500)))
    items = [_serialize_journal(d) async for d in cursor]
    return items


@app.get("/api/journal/stats")
async def journal_stats(authorization: Optional[str] = Header(None)):
    """Totales agregados (hoy, semana, mes, total) para el líder autenticado o todos (pastor)."""
    payload = await get_current_user(authorization)
    base_query: dict = {}
    if payload.get("rol") == "lider":
        base_query["leader_id"] = payload["user_id"]

    today = _today_iso()
    week_start = _week_start_iso()
    month_start = _month_start_iso()

    async def _sum(filter_q: dict) -> dict:
        pipeline = [
            {"$match": filter_q},
            {"$group": {
                "_id": None,
                "casas_visitadas": {"$sum": "$casas_visitadas"},
                "personas_contactadas": {"$sum": "$personas_contactadas"},
                "personas_ganadas": {"$sum": "$personas_ganadas"},
                "oraciones_realizadas": {"$sum": "$oraciones_realizadas"},
                "entradas": {"$sum": 1},
            }},
        ]
        res = await db.leader_journal.aggregate(pipeline).to_list(length=1)
        if not res:
            return {
                "casas_visitadas": 0, "personas_contactadas": 0,
                "personas_ganadas": 0, "oraciones_realizadas": 0, "entradas": 0,
            }
        d = res[0]
        d.pop("_id", None)
        return d

    def q(date_filter):
        return {**base_query, **date_filter}

    hoy = await _sum(q({"fecha": today}))
    semana = await _sum(q({"fecha": {"$gte": week_start}}))
    mes = await _sum(q({"fecha": {"$gte": month_start}}))
    total = await _sum(base_query)

    # Actividad por día de los últimos 14 días (para gráfico)
    pipeline_daily = [
        {"$match": base_query},
        {"$group": {
            "_id": "$fecha",
            "casas": {"$sum": "$casas_visitadas"},
            "contactadas": {"$sum": "$personas_contactadas"},
            "ganadas": {"$sum": "$personas_ganadas"},
            "oraciones": {"$sum": "$oraciones_realizadas"},
        }},
        {"$sort": {"_id": -1}},
        {"$limit": 14},
    ]
    daily_raw = await db.leader_journal.aggregate(pipeline_daily).to_list(length=14)
    # Ordenar ascendente por fecha para el gráfico
    daily = sorted(
        [
            {
                "fecha": d["_id"],
                "casas": d.get("casas", 0),
                "contactadas": d.get("contactadas", 0),
                "ganadas": d.get("ganadas", 0),
                "oraciones": d.get("oraciones", 0),
            }
            for d in daily_raw
        ],
        key=lambda x: x["fecha"],
    )

    return {
        "hoy": hoy,
        "semana": semana,
        "mes": mes,
        "total": total,
        "daily_last_14": daily,
        "date_context": {
            "hoy": today,
            "semana_desde": week_start,
            "mes_desde": month_start,
        },
    }


@app.put("/api/journal/{entry_id}")
async def update_journal_entry(entry_id: str, entry: JournalEntryUpdate, authorization: Optional[str] = Header(None)):
    """Editar una entrada. Solo el dueño (o pastor) puede."""
    payload = await get_current_user(authorization)
    try:
        oid = ObjectId(entry_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    existing = await db.leader_journal.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    if payload.get("rol") != "pastor" and existing.get("leader_id") != payload["user_id"]:
        raise HTTPException(status_code=403, detail="No autorizado")

    update_doc = {k: v for k, v in entry.dict(exclude_unset=True).items() if v is not None}
    if not update_doc:
        return _serialize_journal(existing)
    update_doc["updated_at"] = datetime.utcnow()
    await db.leader_journal.update_one({"_id": oid}, {"$set": update_doc})
    updated = await db.leader_journal.find_one({"_id": oid})
    return _serialize_journal(updated)


@app.delete("/api/journal/{entry_id}")
async def delete_journal_entry(entry_id: str, authorization: Optional[str] = Header(None)):
    """Eliminar una entrada. Solo el dueño (o pastor) puede."""
    payload = await get_current_user(authorization)
    try:
        oid = ObjectId(entry_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    existing = await db.leader_journal.find_one({"_id": oid})
    if not existing:
        return {"success": True}
    if payload.get("rol") != "pastor" and existing.get("leader_id") != payload["user_id"]:
        raise HTTPException(status_code=403, detail="No autorizado")

    await db.leader_journal.delete_one({"_id": oid})
    return {"success": True}
