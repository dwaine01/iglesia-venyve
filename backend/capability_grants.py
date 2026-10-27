"""De dónde viene cada permiso (Equipo y Responsables · E1).

`users.capabilities` sigue siendo la lista efectiva que lee todo el sistema. Al lado, cada cuenta lleva un
libro `capability_grants`: pares {capability, source} SOLO para los permisos que AGREGÓ un cargo o una
designación (p. ej. `consolidation_lead:<id>`, más adelante `team:<asignación>`). Todo lo demás es «dado a
mano» (Gestión de accesos, roles por defecto, otros módulos) y nunca lo toca un cargo.

Reglas:
- Dar (grant): si la cuenta YA tenía el permiso por otra vía y no está en el libro, se respeta como propio y
  no se anota (al retirar el cargo no se quita). Si no lo tenía, o ya lo daba otro cargo, se anota esta fuente.
- Retirar (revoke): se borran las anotaciones de esa fuente; un permiso sale de la cuenta SOLO si ya no lo da
  ningún otro cargo. Lo dado a mano y lo de otros cargos se conserva.
- Gestión de accesos edita lo dado a mano: lo que da un cargo se mantiene mientras el cargo siga activo.
Retirar cierra las sesiones abiertas (token_version) para que rija enseguida; dar no hace falta. Nada se borra del historial:
el historial vive en cada designación/asignación."""
from datetime import datetime, timezone

from bson import ObjectId

from server import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


def grant_entries(user: dict) -> list[dict]:
    value = user.get("capability_grants") or []
    return [item for item in value if isinstance(item, dict) and item.get("capability") and item.get("source")]


def held_by_grants(user: dict) -> set:
    """Permisos que hoy existen porque los da algún cargo/designación."""
    return {item["capability"] for item in grant_entries(user)}


def sources_by_capability(user: dict) -> dict:
    out: dict = {}
    for item in grant_entries(user):
        out.setdefault(item["capability"], []).append(item["source"])
    return out


async def grant(user_id, capabilities, source: str, owned: bool = False) -> list[str]:
    """Da los permisos de una fuente. Devuelve los que se anotaron a esa fuente.
    `owned=True`: la cuenta se acaba de crear PARA esta fuente; todo lo pedido es de ella."""
    oid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    user = await db.users.find_one({"_id": oid}, {"capabilities": 1, "capability_grants": 1})
    if not user:
        return []
    current = set(user.get("capabilities") or [])
    ledger = held_by_grants(user)
    already = {item["capability"] for item in grant_entries(user) if item["source"] == source}
    noted = sorted(cap for cap in set(capabilities) if cap not in already and (owned or cap not in current or cap in ledger))
    if not noted:
        return []
    await db.users.update_one({"_id": oid}, {"$addToSet": {"capabilities": {"$each": noted}},
                                             "$push": {"capability_grants": {"$each": [{"capability": cap, "source": source, "at": _now()} for cap in noted]}},
                                             "$set": {"updated_at": _now()}})  # dar no cierra sesiones (el permiso se lee en cada petición)
    return noted


async def revoke(user_id, source: str) -> list[str]:
    """Retira SOLO lo que dio esta fuente. Devuelve los permisos que salieron de la cuenta."""
    oid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    user = await db.users.find_one({"_id": oid}, {"capabilities": 1, "capability_grants": 1})
    if not user:
        return []
    entries = grant_entries(user)
    mine = {item["capability"] for item in entries if item["source"] == source}
    if not mine:
        return []
    still = {item["capability"] for item in entries if item["source"] != source}
    removed = sorted(mine - still)
    update = {"$pull": {"capability_grants": {"source": source}}, "$inc": {"token_version": 1}, "$set": {"updated_at": _now()}}
    await db.users.update_one({"_id": oid}, update)
    if removed:
        await db.users.update_one({"_id": oid}, {"$pull": {"capabilities": {"$in": removed}}})
    return removed


def keep_granted(user: dict, capabilities: list[str]) -> list[str]:
    """Gestión de accesos guarda la lista completa: lo que da un cargo activo no se pierde al guardar."""
    return sorted(set(capabilities) | held_by_grants(user))


async def migrate_consolidation_leads() -> dict:
    """Anota en el libro lo que ya dieron las designaciones activas de Encargados de Consolidación.
    Con respaldo y reversible (`undo_consolidation_leads_migration`). Idempotente."""
    migration_id = "capability_grants_consolidation_leads_v1"
    if await db.core_migrations.find_one({"_id": migration_id}, {"_id": 1}):
        return {"migration_id": migration_id, "skipped": True}
    backup, noted = [], 0
    async for doc in db.consolidation_lead_designations.find({"active": True, "granted": {"$exists": True, "$ne": []}}, {"_id": 0}):
        if not (doc.get("user_id") and ObjectId.is_valid(doc["user_id"])):
            continue
        user = await db.users.find_one({"_id": ObjectId(doc["user_id"])}, {"capabilities": 1, "capability_grants": 1})
        if not user:
            continue
        backup.append({"user_id": doc["user_id"], "capability_grants": user.get("capability_grants")})
        source = f"consolidation_lead:{doc['designation_id']}"
        have = set(user.get("capabilities") or [])
        entries = [{"capability": cap, "source": source, "at": _now(), "migrated": True} for cap in doc["granted"] if cap in have
                   and not any(item["source"] == source and item["capability"] == cap for item in grant_entries(user))]
        if entries:
            await db.users.update_one({"_id": user["_id"]}, {"$push": {"capability_grants": {"$each": entries}}})
            noted += len(entries)
    await db.core_migrations.insert_one({"_id": migration_id, "migration_id": migration_id, "backup": backup, "noted": noted, "completed_at": _now()})
    return {"migration_id": migration_id, "noted": noted, "users": len(backup)}


async def undo_consolidation_leads_migration() -> dict:
    """Deshace la migración: devuelve el libro de cada cuenta a como estaba (los permisos no cambian)."""
    migration_id = "capability_grants_consolidation_leads_v1"
    doc = await db.core_migrations.find_one({"_id": migration_id})
    if not doc:
        return {"migration_id": migration_id, "restored": 0}
    for item in doc.get("backup") or []:
        if item.get("capability_grants") is None:
            await db.users.update_one({"_id": ObjectId(item["user_id"])}, {"$pull": {"capability_grants": {"migrated": True}}})
        else:
            await db.users.update_one({"_id": ObjectId(item["user_id"])}, {"$set": {"capability_grants": item["capability_grants"]}})
    # Queda marcada como deshecha (no se vuelve a aplicar sola al reiniciar).
    await db.core_migrations.update_one({"_id": migration_id}, {"$set": {"undone_at": _now()}})
    return {"migration_id": migration_id, "restored": len(doc.get("backup") or [])}
