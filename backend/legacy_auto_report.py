"""R1 · Expedientes que el servidor creaba solo desde el Manual viejo («Ley 7 Semanas»).

Hasta ahora, en CADA arranque `migrate_legacy_processes` recorría la colección antigua `people` y creaba
expedientes de Consolidación y de 7 semanas (origen `legacy_people` / `legacy_user_weeks`) si la persona no
tenía uno abierto. Si el anterior se cerraba, al reiniciar se creaba otro; y a los «graduados» se les creaba
uno «completado» nuevo en cada arranque. Decisión del dueño: apagarlo. Es reversible (ajuste en
`app_settings`) y no borra nada de lo ya creado.

Este módulo da las cifras en SOLO LECTURA (antes y después del apagado) para el pastor y el coordinador."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from access_control import is_general_coordinator, is_global_pastoral_authority
from server import db, get_current_user

router = APIRouter(prefix="/api/processes/legacy-auto", tags=["processes"])
SETTING_ID = "legacy_process_auto_migration"
LEGACY_SOURCES = ["legacy_people", "legacy_user_weeks"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def auto_migration_enabled() -> bool:
    """Apagado por defecto (decisión del dueño). Al primer arranque se anota cuándo se apagó."""
    doc = await db.app_settings.find_one({"_id": SETTING_ID})
    if not doc:
        await db.app_settings.update_one({"_id": SETTING_ID}, {"$setOnInsert": {"enabled": False, "disabled_at": _now(), "reason": "R1: decisión del dueño"}}, upsert=True)
        return False
    return bool(doc.get("enabled"))


def require_viewer(current_user: dict = Depends(get_current_user)) -> dict:
    if not (is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)):
        raise HTTPException(status_code=403, detail="Solo el pastor y el coordinador general")
    return current_user


async def legacy_report() -> dict:
    setting = await db.app_settings.find_one({"_id": SETTING_ID}, {"_id": 0}) or {}
    disabled_at = setting.get("disabled_at")
    base = {"source": {"$in": LEGACY_SOURCES}}
    by_kind = await db.process_enrollments.aggregate([
        {"$match": base}, {"$group": {"_id": {"process_key": "$process_key", "status": "$status", "source": "$source"}, "count": {"$sum": 1}}}]).to_list(100)
    persons = await db.process_enrollments.aggregate([
        {"$match": base}, {"$group": {"_id": {"person_id": "$person_id", "process_key": "$process_key"}, "count": {"$sum": 1}}},
        {"$group": {"_id": None, "people": {"$sum": 1}, "recreated": {"$sum": {"$cond": [{"$gt": ["$count", 1]}, 1, 0]}}, "extra_copies": {"$sum": {"$subtract": ["$count", 1]}}}}]).to_list(1)
    since = _now() - timedelta(days=30)
    per_day = await db.process_enrollments.aggregate([
        {"$match": {**base, "created_at": {"$gte": since}}}, {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}]).to_list(40)
    created_after = await db.process_enrollments.count_documents({**base, "created_at": {"$gt": disabled_at}}) if disabled_at else None
    # Cuántos de «Personas sin líder» están ahí SOLO por un expediente creado solo desde el Manual viejo.
    from count_rules import people_without_mentor
    rows = await people_without_mentor(limit=100000)
    ids = [row["canonical_person_id"] for row in rows]
    open_q = {"process_key": "consolidation", "status": {"$in": ["planned", "active", "paused"]}, "person_id": {"$in": ids}}
    sources: dict = {}
    async for doc in db.process_enrollments.find(open_q, {"_id": 0, "person_id": 1, "source": 1}):
        sources.setdefault(doc["person_id"], set()).add(doc.get("source") or "")
    only_legacy = sum(1 for pid in ids if sources.get(pid) and sources[pid] <= set(LEGACY_SOURCES))
    first = persons[0] if persons else {"people": 0, "recreated": 0, "extra_copies": 0}
    return {
        "auto_migration_enabled": bool(setting.get("enabled")), "disabled_at": disabled_at.isoformat().replace("+00:00", "Z") if isinstance(disabled_at, datetime) else disabled_at,
        "total_auto_created": sum(row["count"] for row in by_kind),
        "by_kind": [{"process_key": row["_id"]["process_key"], "status": row["_id"]["status"], "source": row["_id"]["source"], "count": row["count"]} for row in by_kind],
        "distinct_people": first["people"], "people_recreated": first["recreated"], "extra_copies": first["extra_copies"],
        "created_last_30_days": per_day and [{"day": row["_id"], "count": row["count"]} for row in per_day] or [],
        "created_after_disabled": created_after,
        "people_without_leader_total": len(rows), "people_without_leader_only_legacy": only_legacy,
        "note": "Solo lectura. Apagar la creación automática no borra lo ya creado.",
    }


@router.get("/report", response_model=dict)
async def report(current_user: dict = Depends(require_viewer)):
    return await legacy_report()


class SettingInput(BaseModel):
    enabled: bool


@router.put("/setting", response_model=dict)
async def update_setting(payload: SettingInput, current_user: dict = Depends(get_current_user)):
    """Reversible: el pastor puede volver a encenderla (no se recomienda)."""
    if not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Solo el pastor")
    now = _now()
    changes = {"enabled": payload.enabled, "updated_at": now, "updated_by_user_id": current_user["user_id"], **({"disabled_at": now} if not payload.enabled else {})}
    await db.app_settings.update_one({"_id": SETTING_ID}, {"$set": changes, "$push": {"history": {"enabled": payload.enabled, "by_user_id": current_user["user_id"], "at": now}}}, upsert=True)
    return await legacy_report()
