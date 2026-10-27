"""Nuevo flujo de Finanzas · P7: migración con respaldo y reversible. Los asientos de contribuciones que
esperaban la aprobación de la pastora se contabilizan; gastos y asientos manuales no se tocan; se puede
deshacer. La ejecuta Finanzas o Tesorería; la pastora solo consulta."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_migration_backup_apply_undo_and_pastoral_read_only():
    from finance_engine import create_journal, ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    created, migration_id = [], None
    try:
        pastora = await fx.account(await fx.person(f"PastoraM{tag}"), "pastora")
        fin = await fx.account(await fx.person(f"FinM{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read", "finance.manage"], permissions_mode="manual")
        tes = await fx.account(await fx.person(f"TesM{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read", "finance.treasury"], permissions_mode="manual")
        lector = await fx.account(await fx.person(f"LecM{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read"], permissions_mode="manual")
        catalog = (await pastora.get("/api/finance/catalog")).json()
        fund = next(item["fund_id"] for item in catalog["funds"] if item["code"] == "GENERAL")
        accounts = {item["code"]: item["account_id"] for item in catalog["accounts"]}
        lines = [{"account_id": accounts["1010"], "fund_id": fund, "debit_cents": 700, "credit_cents": 0}, {"account_id": accounts["4000"], "fund_id": fund, "debit_cents": 0, "credit_cents": 700}]
        contribution = await create_journal("qa", "2026-10-01", f"QA migración {tag}", "contribution", f"qa-{tag}", lines, "submitted")
        expense_lines = [{"account_id": accounts["5000"], "fund_id": fund, "debit_cents": 300, "credit_cents": 0}, {"account_id": accounts["1020"], "fund_id": fund, "debit_cents": 0, "credit_cents": 300}]
        payment = await create_journal("qa", "2026-10-01", f"QA pago {tag}", "expense_payment", f"qa-exp-{tag}", expense_lines, "submitted")
        created += [contribution["entry_id"], payment["entry_id"]]

        # La vista previa es solo lectura (también la pastora); aplicar y deshacer: Finanzas o Tesorería, nunca la pastora.
        preview = (await pastora.get("/api/finance/migration/preview")).json()
        assert preview["total"] >= 1 and preview["untouched_other_pending"] >= 1
        assert (await pastora.post("/api/finance/migration/apply", json={"confirmation": "contabilizar pendientes"})).status_code == 403
        assert (await lector.post("/api/finance/migration/apply", json={"confirmation": "contabilizar pendientes"})).status_code == 403
        assert (await tes.post("/api/finance/migration/apply", json={"confirmation": "si"})).status_code == 422
        applied = (await tes.post("/api/finance/migration/apply", json={"confirmation": "contabilizar pendientes"})).json()
        migration_id = applied["migration_id"]
        assert (await db.finance_journal_entries.find_one({"entry_id": contribution["entry_id"]}))["status"] == "posted"
        assert (await db.finance_journal_entries.find_one({"entry_id": payment["entry_id"]}))["status"] == "submitted"  # gastos sin cambios
        backup = await db.finance_migrations.find_one({"migration_id": migration_id})
        assert any(entry["entry_id"] == contribution["entry_id"] and entry["status"] == "submitted" for entry in backup["backup"])

        assert (await pastora.post(f"/api/finance/migration/{migration_id}/undo")).status_code == 403
        undone = (await fin.post(f"/api/finance/migration/{migration_id}/undo")).json()
        assert undone["restored"] >= 1
        assert (await db.finance_journal_entries.find_one({"entry_id": contribution["entry_id"]}))["status"] == "submitted"

        # La pastora ya no registra por las pantallas antiguas (solo consulta).
        body = {"anonymous": True, "contribution_type": "tithe", "amount_cents": 100, "received_date": "2026-10-01", "payment_method": "cash", "allocations": [{"fund_id": fund, "amount_cents": 100}]}
        assert (await pastora.post("/api/finance/contributions", json=body)).status_code == 403
        assert (await pastora.post("/api/finance/batches", json={"batch_date": "2026-10-01"})).status_code == 403
        assert (await pastora.get("/api/finance/dashboard")).status_code == 200
    finally:
        await db.finance_journal_entries.delete_many({"entry_id": {"$in": created}})
        if migration_id:
            await db.finance_migrations.delete_many({"migration_id": migration_id})
        await fx.cleanup()
