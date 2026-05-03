"""
Sistema de Jerarquía de 5 Niveles — Casa de Oracion Ven y Ve
============================================================

Implementa el escalafón de privilegios:
  1. Maestro    -> ve todo, puede crear cualquier rol inferior
  2. Supervisor -> habilitado por Maestro, supervisa Líderes asignados
  3. Líder      -> habilita Obreros, supervisa todo el árbol descendente
  4. Obrero     -> habilita Discípulos (máx. 30), supervisa sus Discípulos
  5. Discípulo  -> ve solo sus propias tareas y módulos

Este módulo expone un APIRouter que se monta en server.py
"""

from fastapi import APIRouter, HTTPException, Header, Body
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from datetime import datetime, timedelta, timezone
import os
import secrets
import string
import bcrypt
import jwt
import uuid

from motor.motor_asyncio import AsyncIOMotorClient

# ==============================================================================
# Setup
# ==============================================================================

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "ley7semanas_db")
_client = AsyncIOMotorClient(MONGO_URL)
db = _client[DB_NAME]

SECRET_KEY = os.environ.get("JWT_SECRET", "ley7semanas_secret_key_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_HOURS = 24

# Secreto para el endpoint one-time de seed (configurable por env)
SEED_SECRET = os.environ.get("SEED_SECRET", "venyve-master-seed-2026")

router = APIRouter()

# ==============================================================================
# Configuración de roles
# ==============================================================================

ROLES = ("maestro", "supervisor", "lider", "obrero", "discipulo")
RoleLiteral = Literal["maestro", "supervisor", "lider", "obrero", "discipulo"]

# Quién puede CREAR qué rol
CAN_CREATE = {
    "maestro": {"supervisor", "lider", "obrero", "discipulo"},
    "supervisor": {"lider"},
    "lider": {"obrero"},
    "obrero": {"discipulo"},
    "discipulo": set(),
}

# Etiquetas legibles
ROLE_LABEL = {
    "maestro": "Maestro",
    "supervisor": "Supervisor",
    "lider": "Líder de Grupo",
    "obrero": "Obrero",
    "discipulo": "Discípulo",
}

# Nivel jerárquico (1 = más alto)
ROLE_LEVEL = {"maestro": 1, "supervisor": 2, "lider": 3, "obrero": 4, "discipulo": 5}

# Tope estricto de discípulos por obrero
MAX_DISCIPULOS_POR_OBRERO = 30

INVITATION_DEFAULT_TTL_DAYS = 7
INVITATION_CODE_LENGTH = 8

# ==============================================================================
# Helpers de seguridad / token
# ==============================================================================

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _create_token(user_id: str, email: str, rol: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "rol": rol,
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada. Vuelve a iniciar sesión.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


async def _current_user(authorization: Optional[str]) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    token = authorization.replace("Bearer ", "").strip()
    payload = _decode_token(token)
    user = await db.users.find_one({"_id": payload["user_id"], "active": True})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    return user


def _gen_invitation_code() -> str:
    """Códigos como 'A8K3X7QP' - alfanuméricos sin caracteres ambiguos."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin O/0/I/1
    return "".join(secrets.choice(alphabet) for _ in range(INVITATION_CODE_LENGTH))


def _serialize_user(u: dict) -> dict:
    if not u:
        return None
    return {
        "id": u["_id"],
        "email": u["email"],
        "nombre": u.get("nombre", ""),
        "apellido": u.get("apellido"),
        "telefono": u.get("telefono"),
        "rol": u["rol"],
        "rol_label": ROLE_LABEL.get(u["rol"], u["rol"]),
        "superior_id": u.get("superior_id"),
        "created_by": u.get("created_by"),
        "active": u.get("active", True),
        "created_at": u["created_at"].isoformat() if isinstance(u.get("created_at"), datetime) else u.get("created_at"),
    }


def _serialize_invitation(inv: dict) -> dict:
    return {
        "id": inv["_id"],
        "code": inv["code"],
        "target_role": inv["target_role"],
        "target_role_label": ROLE_LABEL.get(inv["target_role"], inv["target_role"]),
        "generated_by": inv["generated_by"],
        "superior_id": inv["superior_id"],
        "expires_at": inv["expires_at"].isoformat() if isinstance(inv.get("expires_at"), datetime) else inv.get("expires_at"),
        "used_by": inv.get("used_by"),
        "used_at": inv["used_at"].isoformat() if isinstance(inv.get("used_at"), datetime) else inv.get("used_at"),
        "status": inv.get("status", "active"),
        "created_at": inv["created_at"].isoformat() if isinstance(inv.get("created_at"), datetime) else inv.get("created_at"),
    }


# ==============================================================================
# Permisos jerárquicos
# ==============================================================================

async def _is_descendant(user_id: str, ancestor_id: str) -> bool:
    """¿user_id es descendiente directo o indirecto de ancestor_id?"""
    if user_id == ancestor_id:
        return False
    cursor_id = user_id
    # Subir por la cadena hasta encontrar al ancestro o llegar al tope
    for _ in range(20):  # cap defensivo
        u = await db.users.find_one({"_id": cursor_id})
        if not u:
            return False
        sup = u.get("superior_id")
        if not sup:
            return False
        if sup == ancestor_id:
            return True
        cursor_id = sup
    return False


async def _can_view(viewer: dict, target_id: str) -> bool:
    """¿`viewer` puede ver al usuario `target_id`?"""
    if viewer["_id"] == target_id:
        return True
    if viewer["rol"] == "maestro":
        return True
    return await _is_descendant(target_id, viewer["_id"])


async def _get_team_recursive(user_id: str) -> List[dict]:
    """Devuelve todos los descendientes directos e indirectos de user_id."""
    result = []
    queue = [user_id]
    visited = {user_id}
    while queue:
        current = queue.pop(0)
        async for child in db.users.find({"superior_id": current, "active": True}):
            if child["_id"] in visited:
                continue
            visited.add(child["_id"])
            result.append(child)
            queue.append(child["_id"])
    return result


# ==============================================================================
# Pydantic Models (request/response)
# ==============================================================================

class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterWithCodeIn(BaseModel):
    code: str
    nombre: str
    apellido: Optional[str] = None
    email: EmailStr
    password: str = Field(min_length=6)
    telefono: Optional[str] = None


class CreateInvitationIn(BaseModel):
    target_role: RoleLiteral
    expires_in_days: int = Field(default=INVITATION_DEFAULT_TTL_DAYS, ge=1, le=30)
    note: Optional[str] = None


class CreateUserDirectIn(BaseModel):
    nombre: str
    apellido: Optional[str] = None
    email: EmailStr
    password: str = Field(min_length=6)
    rol: RoleLiteral
    telefono: Optional[str] = None


class UpdateUserIn(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    active: Optional[bool] = None


class SeedMaestroIn(BaseModel):
    seed_secret: str
    nombre: str = "Carmen Garcia"
    email: EmailStr = "admin@venyve.com"
    password: str = "admin123"
    wipe_legacy: bool = True


# ==============================================================================
# Endpoints — Auth
# ==============================================================================

@router.post("/api/auth/login")
async def login(body: LoginIn):
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = _create_token(user["_id"], user["email"], user["rol"])
    return {"token": token, "user": _serialize_user(user)}


@router.get("/api/auth/me")
async def me(authorization: Optional[str] = Header(None)):
    user = await _current_user(authorization)
    return {"user": _serialize_user(user)}


@router.post("/api/auth/register-with-code")
async def register_with_code(body: RegisterWithCodeIn):
    code = body.code.strip().upper()
    inv = await db.invitations.find_one({"code": code})
    if not inv:
        raise HTTPException(status_code=404, detail="Código de invitación no válido")
    if inv["status"] != "active":
        raise HTTPException(status_code=400, detail=f"Este código ya fue {inv['status']}")
    expires_at = inv["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        await db.invitations.update_one({"_id": inv["_id"]}, {"$set": {"status": "expired"}})
        raise HTTPException(status_code=400, detail="Este código ya expiró. Pide uno nuevo.")

    # Validar email único
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=409, detail="Este email ya está registrado")

    # Si el target_role es discipulo, validar tope de 30 del obrero superior
    if inv["target_role"] == "discipulo":
        count = await db.users.count_documents({
            "superior_id": inv["superior_id"],
            "rol": "discipulo",
            "active": True,
        })
        if count >= MAX_DISCIPULOS_POR_OBRERO:
            raise HTTPException(
                status_code=400,
                detail=f"El obrero ya alcanzó el máximo de {MAX_DISCIPULOS_POR_OBRERO} discípulos.",
            )

    # Crear usuario
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    user_doc = {
        "_id": new_id,
        "email": body.email.lower(),
        "password_hash": _hash_password(body.password),
        "nombre": body.nombre.strip(),
        "apellido": (body.apellido or "").strip() or None,
        "telefono": (body.telefono or "").strip() or None,
        "rol": inv["target_role"],
        "superior_id": inv["superior_id"],
        "created_by": inv["generated_by"],
        "active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(user_doc)

    # Marcar invitación como usada
    await db.invitations.update_one(
        {"_id": inv["_id"]},
        {"$set": {"status": "used", "used_by": new_id, "used_at": now}},
    )

    token = _create_token(new_id, user_doc["email"], user_doc["rol"])
    return {"token": token, "user": _serialize_user(user_doc)}


@router.get("/api/auth/invitations/{code}/preview")
async def preview_invitation(code: str):
    """Permite a la página de registro mostrar info del código antes de registrarse."""
    code = code.strip().upper()
    inv = await db.invitations.find_one({"code": code})
    if not inv:
        raise HTTPException(status_code=404, detail="Código no encontrado")
    superior = await db.users.find_one({"_id": inv["superior_id"]})
    expires_at = inv["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    is_expired = expires_at < datetime.now(timezone.utc).replace(tzinfo=None)
    return {
        "valid": inv["status"] == "active" and not is_expired,
        "status": inv["status"] if not is_expired else "expired",
        "target_role": inv["target_role"],
        "target_role_label": ROLE_LABEL.get(inv["target_role"], inv["target_role"]),
        "superior_nombre": (superior or {}).get("nombre", "—"),
        "superior_rol": (superior or {}).get("rol"),
        "expires_at": expires_at.isoformat(),
    }


# ==============================================================================
# Endpoints — Invitaciones
# ==============================================================================

@router.post("/api/users/invitations")
async def create_invitation(
    body: CreateInvitationIn,
    authorization: Optional[str] = Header(None),
):
    user = await _current_user(authorization)
    allowed = CAN_CREATE.get(user["rol"], set())
    if body.target_role not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Tu rol ({ROLE_LABEL[user['rol']]}) no puede crear {ROLE_LABEL[body.target_role]}",
        )

    # Si target = discipulo y emisor = obrero, validar tope 30
    if body.target_role == "discipulo" and user["rol"] == "obrero":
        count = await db.users.count_documents({
            "superior_id": user["_id"],
            "rol": "discipulo",
            "active": True,
        })
        # contar también invitaciones activas que aún no se usan
        pending = await db.invitations.count_documents({
            "superior_id": user["_id"],
            "target_role": "discipulo",
            "status": "active",
        })
        if count + pending >= MAX_DISCIPULOS_POR_OBRERO:
            raise HTTPException(
                status_code=400,
                detail=f"Has alcanzado el máximo de {MAX_DISCIPULOS_POR_OBRERO} discípulos (incluyendo invitaciones pendientes).",
            )

    # Generar código único
    for _ in range(10):
        code = _gen_invitation_code()
        if not await db.invitations.find_one({"code": code}):
            break
    else:
        raise HTTPException(status_code=500, detail="No se pudo generar un código único")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    inv = {
        "_id": str(uuid.uuid4()),
        "code": code,
        "generated_by": user["_id"],
        "target_role": body.target_role,
        "superior_id": user["_id"],
        "expires_at": now + timedelta(days=body.expires_in_days),
        "used_by": None,
        "used_at": None,
        "status": "active",
        "note": body.note,
        "created_at": now,
    }
    await db.invitations.insert_one(inv)
    return _serialize_invitation(inv)


@router.get("/api/users/invitations")
async def list_invitations(authorization: Optional[str] = Header(None)):
    user = await _current_user(authorization)
    cursor = db.invitations.find({"generated_by": user["_id"]}).sort("created_at", -1)
    items = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async for inv in cursor:
        # auto-marcar expiradas
        exp = inv.get("expires_at")
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp)
        if inv["status"] == "active" and exp and exp < now:
            await db.invitations.update_one({"_id": inv["_id"]}, {"$set": {"status": "expired"}})
            inv["status"] = "expired"
        items.append(_serialize_invitation(inv))
    return {"items": items}


@router.delete("/api/users/invitations/{invitation_id}")
async def revoke_invitation(invitation_id: str, authorization: Optional[str] = Header(None)):
    user = await _current_user(authorization)
    inv = await db.invitations.find_one({"_id": invitation_id})
    if not inv:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    if inv["generated_by"] != user["_id"] and user["rol"] != "maestro":
        raise HTTPException(status_code=403, detail="No puedes revocar invitaciones de otros")
    if inv["status"] != "active":
        raise HTTPException(status_code=400, detail=f"Invitación ya está {inv['status']}")
    await db.invitations.update_one({"_id": invitation_id}, {"$set": {"status": "revoked"}})
    return {"success": True}


# ==============================================================================
# Endpoints — Users (gestión de equipo)
# ==============================================================================

@router.post("/api/users/create-direct")
async def create_user_direct(
    body: CreateUserDirectIn,
    authorization: Optional[str] = Header(None),
):
    user = await _current_user(authorization)
    allowed = CAN_CREATE.get(user["rol"], set())
    if body.rol not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Tu rol ({ROLE_LABEL[user['rol']]}) no puede crear {ROLE_LABEL[body.rol]}",
        )

    # Validar email único
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(status_code=409, detail="Este email ya está registrado")

    # Validar tope de 30 si es obrero creando discípulo
    if body.rol == "discipulo" and user["rol"] == "obrero":
        count = await db.users.count_documents({
            "superior_id": user["_id"],
            "rol": "discipulo",
            "active": True,
        })
        if count >= MAX_DISCIPULOS_POR_OBRERO:
            raise HTTPException(
                status_code=400,
                detail=f"Has alcanzado el máximo de {MAX_DISCIPULOS_POR_OBRERO} discípulos.",
            )

    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc = {
        "_id": new_id,
        "email": body.email.lower(),
        "password_hash": _hash_password(body.password),
        "nombre": body.nombre.strip(),
        "apellido": (body.apellido or "").strip() or None,
        "telefono": (body.telefono or "").strip() or None,
        "rol": body.rol,
        "superior_id": user["_id"],
        "created_by": user["_id"],
        "active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(doc)
    return _serialize_user(doc)


@router.get("/api/users/my-team")
async def my_team(authorization: Optional[str] = Header(None), recursive: bool = True):
    """
    Devuelve el equipo del usuario actual.
    - Maestro: todos los usuarios
    - Otros: descendientes directos (recursive=False) o indirectos (recursive=True)
    """
    user = await _current_user(authorization)
    if user["rol"] == "maestro":
        cursor = db.users.find({"_id": {"$ne": user["_id"]}}).sort([("rol", 1), ("nombre", 1)])
        items = [_serialize_user(u) async for u in cursor]
    elif recursive:
        team = await _get_team_recursive(user["_id"])
        items = [_serialize_user(u) for u in team]
    else:
        cursor = db.users.find({"superior_id": user["_id"], "active": True}).sort("nombre", 1)
        items = [_serialize_user(u) async for u in cursor]

    # Stats por rol
    by_role = {r: 0 for r in ROLES}
    for it in items:
        by_role[it["rol"]] = by_role.get(it["rol"], 0) + 1

    return {"items": items, "stats": by_role, "total": len(items)}


@router.get("/api/users/{user_id}")
async def get_user(user_id: str, authorization: Optional[str] = Header(None)):
    viewer = await _current_user(authorization)
    target = await db.users.find_one({"_id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not await _can_view(viewer, user_id):
        raise HTTPException(status_code=403, detail="Sin permiso para ver este usuario")

    # Datos extra: superior, conteo subordinados directos
    superior = await db.users.find_one({"_id": target.get("superior_id")}) if target.get("superior_id") else None
    direct_subs = await db.users.count_documents({"superior_id": user_id, "active": True})
    return {
        "user": _serialize_user(target),
        "superior": _serialize_user(superior) if superior else None,
        "direct_subordinates": direct_subs,
    }


@router.put("/api/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserIn,
    authorization: Optional[str] = Header(None),
):
    viewer = await _current_user(authorization)
    target = await db.users.find_one({"_id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if viewer["_id"] != user_id and not await _can_view(viewer, user_id):
        raise HTTPException(status_code=403, detail="Sin permiso")
    update = {k: v for k, v in body.dict(exclude_unset=True).items() if v is not None}
    if not update:
        return {"user": _serialize_user(target)}
    update["updated_at"] = datetime.now(timezone.utc)
    await db.users.update_one({"_id": user_id}, {"$set": update})
    refreshed = await db.users.find_one({"_id": user_id})
    return {"user": _serialize_user(refreshed)}


@router.delete("/api/users/{user_id}")
async def deactivate_user(user_id: str, authorization: Optional[str] = Header(None)):
    viewer = await _current_user(authorization)
    if viewer["_id"] == user_id:
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo")
    if not await _can_view(viewer, user_id):
        raise HTTPException(status_code=403, detail="Sin permiso")
    target = await db.users.find_one({"_id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"active": False, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"success": True}


# ==============================================================================
# Endpoints — Dashboard jerárquico
# ==============================================================================

@router.get("/api/dashboard/hierarchy")
async def hierarchy_dashboard(authorization: Optional[str] = Header(None)):
    user = await _current_user(authorization)

    # Stats por rol del subárbol del usuario (o globales si maestro)
    if user["rol"] == "maestro":
        team = []
        async for u in db.users.find({"_id": {"$ne": user["_id"]}, "active": True}):
            team.append(u)
    else:
        team = await _get_team_recursive(user["_id"])

    by_role = {r: 0 for r in ROLES}
    for t in team:
        by_role[t["rol"]] = by_role.get(t["rol"], 0) + 1

    # Subordinados directos
    direct = []
    async for u in db.users.find({"superior_id": user["_id"], "active": True}).sort("rol", 1):
        direct.append(_serialize_user(u))

    # Invitaciones activas mías
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    active_invitations = await db.invitations.count_documents({
        "generated_by": user["_id"],
        "status": "active",
        "expires_at": {"$gt": now},
    })

    # Si el usuario es obrero, devolver su contador hacia los 30
    discipulos_count = None
    if user["rol"] == "obrero":
        discipulos_count = await db.users.count_documents({
            "superior_id": user["_id"],
            "rol": "discipulo",
            "active": True,
        })

    return {
        "me": _serialize_user(user),
        "stats_by_role": by_role,
        "team_total": len(team),
        "direct_subordinates": direct,
        "active_invitations": active_invitations,
        "discipulos_count": discipulos_count,
        "max_discipulos": MAX_DISCIPULOS_POR_OBRERO if user["rol"] == "obrero" else None,
        "can_create_roles": sorted(list(CAN_CREATE.get(user["rol"], set()))),
    }


# ==============================================================================
# Endpoints — Admin / Seed
# ==============================================================================

@router.post("/api/admin/seed-maestro")
async def seed_maestro(body: SeedMaestroIn):
    """
    One-time setup: borra el sistema viejo y crea al primer Maestro.
    Requiere SEED_SECRET para evitar ejecuciones accidentales.
    """
    if body.seed_secret != SEED_SECRET:
        raise HTTPException(status_code=403, detail="Secreto inválido")

    legacy_drops = []
    if body.wipe_legacy:
        # Borrar collections del sistema antiguo
        for coll in [
            "users", "contacts", "checklists", "progress",
            "people", "person_progress", "person_checklists",
            "leader_journal", "pastor_notes", "invite_codes",
            "invitations",  # también limpiar invitaciones nuevas si las hay
        ]:
            try:
                res = await db[coll].delete_many({})
                legacy_drops.append({coll: res.deleted_count})
            except Exception as e:  # noqa: BLE001
                legacy_drops.append({coll: f"error: {e}"})

    # Crear índices nuevos
    await db.users.create_index("email", unique=True)
    await db.users.create_index("superior_id")
    await db.users.create_index([("superior_id", 1), ("rol", 1)])
    await db.invitations.create_index("code", unique=True)
    await db.invitations.create_index("generated_by")
    await db.invitations.create_index("status")

    # Crear Maestro
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    maestro = {
        "_id": new_id,
        "email": body.email.lower(),
        "password_hash": _hash_password(body.password),
        "nombre": body.nombre,
        "apellido": None,
        "telefono": None,
        "rol": "maestro",
        "superior_id": None,
        "created_by": None,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(maestro)

    return {
        "success": True,
        "legacy_drops": legacy_drops,
        "maestro": _serialize_user(maestro),
        "message": f"Sistema reiniciado. Inicia sesión con {body.email} / {body.password}",
    }


@router.get("/api/admin/health")
async def admin_health():
    """Diagnóstico rápido para confirmar que el módulo de jerarquía está montado."""
    user_count = await db.users.count_documents({})
    by_role = {}
    for r in ROLES:
        by_role[r] = await db.users.count_documents({"rol": r, "active": True})
    return {
        "module": "hierarchy",
        "users_total": user_count,
        "by_role": by_role,
    }
