"""Nuevo flujo de Finanzas · P7: migración de lo existente, con respaldo y reversible.

Con la decisión del dueño la pastora ya no aprueba los asientos de contribuciones. Los asientos de
contribuciones y depósitos que quedaron «enviados/revisados» esperando esa aprobación se quedarían
trabados para siempre. Esta migración:

- `preview` (solo lectura): cuántos hay y de qué tipo; nada cambia.
- `apply`: guarda un RESPALDO completo de cada asiento y lo marca «contabilizado» con la política
  `migracion_nuevo_flujo` (quién y cuándo). Gastos, pagos, asientos manuales y transferencias NO se tocan.
- `undo`: devuelve cada asiento a su estado anterior desde el respaldo (si no fue conciliado después).

La ejecuta el equipo de Finanzas o Tesorería (nunca la pastora), escribiendo la frase de confirmación. Nada se borra.
"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import FINANCE_TREASURY
from finance_engine import audit, has_finance_manage, has_finance_role, require_finance_manage, require_finance_read, serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/finance/migration", tags=["finance-migration"])
SOURCE_TYPES = ["contribution", "contribution_reversal", "deposit", "deposit_adjustment"]
PENDING = ["submitted", "reviewed"]
PHRASE = "CONTABILIZAR PENDIENTES"


def require_owner(current_user: dict = Depends(get_current_user)) -> dict:
    """La migración la ejecuta el equipo de Finanzas o Tesorería (decisión del dueño), nunca la pastora."""
    if not (has_finance_role(current_user, FINANCE_TREASURY) or has_finance_manage(current_user)):
        require_finance_manage(current_user)
    return current_user


def viewer(current_user: dict = Depends(get_current_user)) -> dict:
    require_finance_read(current_user)  # la vista previa es solo lectura: también la pastora
    return current_user


def pending_query() -> dict:
    return {"source_type": {"$in": SOURCE_TYPES}, "status": {"$in": PENDING}}


@router.get("/preview", response_model=dict)
async def preview(current_user: dict = Depends(viewer)):
    rows = await db.finance_journal_entries.aggregate([{"$match": pending_query()}, {"$group": {"_id": {"source_type": "$source_type", "status": "$status"}, "count": {"$sum": 1}, "cents": {"$sum": "$total_debit_cents"}}}]).to_list(50)
    untouched = await db.finance_journal_entries.count_documents({"source_type": {"$nin": SOURCE_TYPES}, "status": {"$in": PENDING}})
    return {"pending": [{"source_type": row["_id"]["source_type"], "status": row["_id"]["status"], "count": row["count"], "total_cents": row["cents"]} for row in rows],
            "total": sum(row["count"] for row in rows), "untouched_other_pending": untouched, "confirmation_phrase": PHRASE,
            "history": serialize(await db.finance_migrations.find({}, {"_id": 0, "backup": 0}).sort("at", -1).limit(20).to_list(20)),
            "note": "Solo lectura. Al aplicar se guarda un respaldo de cada asiento y se puede deshacer."}


class ApplyInput(BaseModel):
    confirmation: str = Field(min_length=3, max_length=60)


@router.post("/apply", response_model=dict)
async def apply(payload: ApplyInput, current_user: dict = Depends(require_owner)):
    if payload.confirmation.strip().upper() != PHRASE:
        raise HTTPException(status_code=422, detail=f"Escriba exactamente: {PHRASE}")
    entries = await db.finance_journal_entries.find(pending_query(), {"_id": 0}).to_list(20000)
    migration_id = str(uuid4())
    now = datetime.now(timezone.utc)
    # Respaldo completo ANTES de cambiar nada.
    await db.finance_migrations.insert_one({"_id": migration_id, "migration_id": migration_id, "kind": "post_pending_contribution_journals", "status": "applied",
                                            "count": len(entries), "backup": entries, "by_user_id": current_user["user_id"], "at": now})
    ids = [entry["entry_id"] for entry in entries]
    if ids:
        await db.finance_journal_entries.update_many({"entry_id": {"$in": ids}, "status": {"$in": PENDING}}, {"$set": {
            "status": "posted", "posted_at": now, "posting_policy": "migracion_nuevo_flujo", "migration_id": migration_id, "migrated_by_user_id": current_user["user_id"], "updated_at": now}})
    await audit(current_user["user_id"], "finance_migration_applied", "migration", migration_id, {"count": len(ids)})
    return {"migration_id": migration_id, "posted": len(ids)}


@router.post("/{migration_id}/undo", response_model=dict)
async def undo(migration_id: str, current_user: dict = Depends(require_owner)):
    record = await db.finance_migrations.find_one({"migration_id": migration_id})
    if not record:
        raise HTTPException(status_code=404, detail="Migración no encontrada")
    if record.get("status") == "undone":
        return {"migration_id": migration_id, "restored": 0, "already": True}
    restored, skipped = 0, []
    for entry in record.get("backup") or []:
        current = await db.finance_journal_entries.find_one({"entry_id": entry["entry_id"]}, {"_id": 0, "reconciliation_id": 1, "migration_id": 1})
        if not current or current.get("migration_id") != migration_id or current.get("reconciliation_id"):
            skipped.append(entry["entry_id"])  # cambió después (p. ej. conciliado): no se toca
            continue
        result = await db.finance_journal_entries.update_one({"entry_id": entry["entry_id"]}, {"$set": {"status": entry["status"], "posted_at": entry.get("posted_at"), "updated_at": datetime.now(timezone.utc)},
                                                                                              "$unset": {"posting_policy": "", "migration_id": "", "migrated_by_user_id": ""}})
        restored += result.modified_count
    await db.finance_migrations.update_one({"migration_id": migration_id}, {"$set": {"status": "undone", "undone_at": datetime.now(timezone.utc), "undone_by_user_id": current_user["user_id"],
                                                                                    "restored": restored, "skipped": skipped}})
    await audit(current_user["user_id"], "finance_migration_undone", "migration", migration_id, {"restored": restored, "skipped": len(skipped)})
    return {"migration_id": migration_id, "restored": restored, "skipped": skipped}
