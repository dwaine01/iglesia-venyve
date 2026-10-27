"""Equipo y Responsables · E3: asignar, reemplazar y retirar responsables de los cargos que guarda este módulo
(fuente `team`: Dirección-copastor, Finanzas, Librería, Educación, Operación y cargos nuevos). Los cargos que
viven en otro módulo (Consolidación, Mentoría, Grupo Frontal, Ministerios) se conectan en E4; los de cuenta
(pastor principal, coordinador general) se cambian en Gestión de accesos.

Reglas (en el servidor):
- Un guardado trae VARIOS cambios y se valida TODO antes de aplicar; si algo no cumple, no se aplica nada.
- Nadie se asigna a sí mismo. Máximo de personas por cargo (3). La misma persona no se repite en un cargo.
- Cargos de Finanzas/Junta: el pastor, o quien el pastor autorizó («Asignar el equipo de Finanzas/Junta»).
  El coordinador general no escala: solo cargos con permisos que él ya tiene.
- La pastora (o cualquier Acceso Maestro) no ocupa cargos de Finanzas: asignar el equipo no es operar Finanzas.
- Al asignar se aplican los permisos del cargo (libro de permisos E1) y, si hace falta, el grupo de privilegio;
  al retirar se quita SOLO lo que dio ese cargo. Una persona puede tener varios cargos.
- Historial inmutable en `team_events` (quién, cuándo, quién ocupaba el puesto antes). Nada se borra."""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import (
    BOARD_ACCESS, FINANCE_CAPABILITIES, TEAM_ASSIGN_BOARD, TEAM_ASSIGN_FINANCE, has_capability, is_global_pastoral_authority, normalized_capabilities,
)
from capability_grants import grant, revoke
from server import db
from team_catalog import require_team_viewer, serialize

router = APIRouter(prefix="/api/team", tags=["team"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_indexes() -> None:
    await db.team_assignments.create_index("assignment_id", unique=True)
    await db.team_assignments.create_index([("role_id", 1), ("active", 1)])
    await db.team_assignments.create_index([("person_id", 1), ("active", 1)])
    await db.team_events.create_index([("at", -1)])


async def person_card(person_id: Optional[str]) -> Optional[dict]:
    if not person_id or not ObjectId.is_valid(person_id):
        return None
    doc = await db.persons.find_one({"_id": ObjectId(person_id)}, {"nombre": 1, "apellido": 1, "photo_url": 1, "person_number": 1, "is_archived": 1})
    if not doc:
        return None
    return {"person_id": person_id, "name": " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) or "Persona", "photo_url": doc.get("photo_url"),
            "person_number": doc.get("person_number"), "is_archived": bool(doc.get("is_archived"))}


async def user_of(person_id: str) -> Optional[dict]:
    user = await db.users.find_one({"person_id": person_id})
    if user:
        return user
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"auth_user_id": 1}) if ObjectId.is_valid(person_id) else None
    if person and person.get("auth_user_id") and ObjectId.is_valid(str(person["auth_user_id"])):
        return await db.users.find_one({"_id": ObjectId(str(person["auth_user_id"]))})
    return None


def sensitive_group(role: dict) -> Optional[str]:
    caps = set(role.get("capabilities") or [])
    if role.get("privilege_group") == "finance" or caps & set(FINANCE_CAPABILITIES):
        return "finance"
    if role.get("privilege_group") == "board" or BOARD_ACCESS in caps:
        return "board"
    return None


def ensure_actor_may_assign(actor: dict, role: dict) -> None:
    group = sensitive_group(role)
    if is_global_pastoral_authority(actor):
        return
    if group == "finance" and not has_capability(actor, TEAM_ASSIGN_FINANCE):
        raise HTTPException(status_code=403, detail=f"«{role['name']}» es de Finanzas: lo asigna el pastor o quien él autorizó")
    if group == "board" and not has_capability(actor, TEAM_ASSIGN_BOARD):
        raise HTTPException(status_code=403, detail=f"«{role['name']}» es de Junta: lo asigna el pastor o quien él autorizó")
    if group is None:
        beyond = sorted(set(role.get("capabilities") or []) - set(normalized_capabilities(actor)))
        if beyond:
            raise HTTPException(status_code=403, detail=f"No puede asignar «{role['name']}»: da permisos que usted no tiene ({', '.join(beyond)})")


class Change(BaseModel):
    op: Literal["assign", "remove", "replace"]
    role_id: str
    person_id: Optional[str] = None            # assign / replace: quién entra
    assignment_id: Optional[str] = None        # remove / replace: a quién sustituye
    reason: Optional[str] = Field(default=None, max_length=300)


class ChangeSet(BaseModel):
    changes: list[Change] = Field(min_length=1, max_length=60)
    is_test: bool = False


async def validate(changes: list[Change], actor: dict) -> list[dict]:
    """Revisa todo el guardado sin escribir nada. Devuelve el plan; si algo falla, explica cuál cambio."""
    plan, holders, problems = [], {}, []
    for index, change in enumerate(changes, start=1):
        try:
            role = await db.team_roles.find_one({"role_id": change.role_id}, {"_id": 0})
            if not role or not role.get("active"):
                raise HTTPException(status_code=404, detail="Cargo no encontrado o desactivado")
            if role["source"] == "account_role":
                raise HTTPException(status_code=409, detail=f"«{role['name']}» se cambia en Gestión de accesos")
            if role["source"] != "team":
                raise HTTPException(status_code=409, detail=f"«{role['name']}» se asigna en su módulo (pronto también desde aquí)")
            ensure_actor_may_assign(actor, role)
            if role["role_id"] not in holders:
                holders[role["role_id"]] = {doc["assignment_id"]: doc async for doc in db.team_assignments.find({"role_id": role["role_id"], "active": True}, {"_id": 0})}
            current = holders[role["role_id"]]
            leaving = None
            if change.op in ("remove", "replace"):
                leaving = current.get(change.assignment_id or "")
                if not leaving:
                    raise HTTPException(status_code=404, detail="Esa asignación no está activa en este cargo")
                current.pop(leaving["assignment_id"])
            entering = None
            if change.op in ("assign", "replace"):
                card = await person_card(change.person_id)
                if not card or card["is_archived"]:
                    raise HTTPException(status_code=404, detail="La persona no existe en Persona 360")
                if change.person_id == actor.get("person_id"):
                    raise HTTPException(status_code=403, detail="Nadie puede asignarse a sí mismo un cargo")
                if any(doc["person_id"] == change.person_id for doc in current.values()):
                    raise HTTPException(status_code=409, detail=f"{card['name']} ya ocupa «{role['name']}»")
                if role.get("max_holders") and len(current) >= role["max_holders"]:
                    raise HTTPException(status_code=409, detail=f"«{role['name']}» ya tiene {role['max_holders']} personas (máximo)")
                user = await user_of(change.person_id)
                if sensitive_group(role) == "finance" and user and is_global_pastoral_authority(user):
                    raise HTTPException(status_code=409, detail="La pastora (Acceso Maestro) no ocupa cargos de Finanzas: solo consulta")
                if sensitive_group(role) == "finance" and user:
                    from core_governance import ensure_finance_limit  # mismo tope de cuentas de Finanzas que Gestión de accesos
                    await ensure_finance_limit(["finance"], user)
                entering = {"card": card, "user": user}
                current[f"new-{index}"] = {"assignment_id": f"new-{index}", "person_id": change.person_id}
            plan.append({"change": change, "role": role, "leaving": leaving, "entering": entering})
        except HTTPException as error:
            problems.append({"change": index, "role_id": change.role_id, "detail": error.detail})
    if problems:
        raise HTTPException(status_code=409, detail={"message": "No se guardó nada: hay cambios que no se pueden aplicar", "problems": problems})
    return plan


async def apply_remove(doc: dict, actor: dict, reason: Optional[str], change_set_id: str) -> None:
    if doc.get("user_id"):
        await revoke(doc["user_id"], f"team:{doc['assignment_id']}")
        if doc.get("added_group"):
            others = await db.team_assignments.count_documents({"user_id": doc["user_id"], "active": True, "privilege_group": doc["added_group"], "assignment_id": {"$ne": doc["assignment_id"]}})
            if not others:
                await db.users.update_one({"_id": ObjectId(doc["user_id"])}, {"$pull": {"privilege_groups": doc["added_group"]}, "$inc": {"token_version": 1}})
    await db.team_assignments.update_one({"assignment_id": doc["assignment_id"], "active": True}, {"$set": {
        "active": False, "removed_by_user_id": actor["user_id"], "removed_at": _now(), "removal_reason": reason, "removed_in": change_set_id}})


async def apply_assign(role: dict, entering: dict, actor: dict, replaced: Optional[dict], change_set_id: str, is_test: bool) -> dict:
    assignment_id = str(uuid4())
    user = entering["user"]
    granted, added_group = [], None
    group = sensitive_group(role) if role.get("privilege_group") else None
    if user:
        if group and group not in (user.get("privilege_groups") or []):
            await db.users.update_one({"_id": user["_id"]}, {"$addToSet": {"privilege_groups": group}})
            added_group = group
        granted = await grant(user["_id"], role.get("capabilities") or [], f"team:{assignment_id}")
    doc = {"_id": assignment_id, "assignment_id": assignment_id, "role_id": role["role_id"], "area_id": role["area_id"], "kind": role.get("kind"),
           "person_id": entering["card"]["person_id"], "user_id": str(user["_id"]) if user else None, "granted": granted, "added_group": added_group,
           "privilege_group": role.get("privilege_group"), "pending_account": user is None, "active": True, "is_test": is_test,
           "replaced_assignment_id": (replaced or {}).get("assignment_id"), "replaced_person_id": (replaced or {}).get("person_id"),
           "assigned_by_user_id": actor["user_id"], "assigned_at": _now(), "assigned_in": change_set_id}
    await db.team_assignments.insert_one(doc)
    return doc


@router.post("/changes", response_model=dict)
async def save_changes(payload: ChangeSet, current_user: dict = Depends(require_team_viewer)):
    """Guarda TODO el equipo de una vez (todo o nada)."""
    plan = await validate(payload.changes, current_user)
    change_set_id = str(uuid4())
    events = []
    for step in plan:
        change, role, leaving, entering = step["change"], step["role"], step["leaving"], step["entering"]
        if leaving:
            await apply_remove(leaving, current_user, change.reason, change_set_id)
        new = await apply_assign(role, entering, current_user, leaving, change_set_id, payload.is_test) if entering else None
        events.append({"_id": str(uuid4()), "change_set_id": change_set_id, "op": change.op, "role_id": role["role_id"], "role_name": role["name"], "area_id": role["area_id"],
                       "person_id": change.person_id, "assignment_id": (new or {}).get("assignment_id"), "previous_assignment_id": (leaving or {}).get("assignment_id"),
                       "previous_person_id": (leaving or {}).get("person_id"), "granted": (new or {}).get("granted", []), "reason": change.reason,
                       "by_user_id": current_user["user_id"], "at": _now(), "is_test": payload.is_test})
    if events:
        await db.team_events.insert_many(events)
    return {"change_set_id": change_set_id, "applied": len(events)}


@router.get("/assignments", response_model=dict)
async def assignments(include_test: bool = False, current_user: dict = Depends(require_team_viewer)):
    """De un vistazo: quién está a cargo de cada cosa y qué puestos faltan (cargos de este módulo)."""
    query = {"active": True} if include_test else {"active": True, "is_test": {"$ne": True}}
    docs = await db.team_assignments.find(query, {"_id": 0}).to_list(5000)
    by_role: dict = {}
    for doc in docs:
        by_role.setdefault(doc["role_id"], []).append({**serialize(doc), "person": await person_card(doc["person_id"])})
    roles = await db.team_roles.find({"active": True, "source": "team"}, {"_id": 0, "role_id": 1, "name": 1, "area_id": 1, "max_holders": 1}).to_list(1000)
    pending = [{"role_id": role["role_id"], "name": role["name"], "area_id": role["area_id"]} for role in roles if not by_role.get(role["role_id"])]
    return {"by_role": by_role, "pending": pending}


@router.get("/history", response_model=dict)
async def history(current_user: dict = Depends(require_team_viewer)):
    items = await db.team_events.find({}, {"_id": 0}).sort("at", -1).limit(300).to_list(300)
    return {"items": [serialize(item) for item in items]}
