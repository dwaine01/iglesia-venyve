"""Finanzas F2: corregidas fuera de depósitos y conteos, ajuste de depósito, anular en vez de borrar,
presupuesto del año fiscal y «en banco» separado de «por depositar». No cambia la política de aprobación."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_f2_corrected_deposit_adjustment_void_and_fiscal_budget():
    from count_rules import church_today
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    created = {"contributions": [], "deposits": [], "budgets": [], "journals": []}
    try:
        pastora = await fx.account(await fx.person(f"PastoraF{tag}"), "pastora")
        donor = await fx.person(f"DonanteF{tag}")
        funds = {item["code"]: item["fund_id"] for item in (await pastora.get("/api/finance/catalog")).json()["funds"]}
        accounts = {item["code"]: item["account_id"] for item in (await pastora.get("/api/finance/catalog")).json()["accounts"]}
        today = (await church_today()).isoformat()

        def contribution(fund, cents, **extra):
            return {"person_id": donor, "contribution_type": "tithe", "amount_cents": cents, "received_date": today, "payment_method": "cash",
                    "allocations": [{"fund_id": funds[fund], "amount_cents": cents}], **extra}
        original = (await pastora.post("/api/finance/contributions", json=contribution("GENERAL", 10000))).json()
        created["contributions"].append(original["contribution_id"])
        deposit = await pastora.post("/api/finance/deposits", json={"deposit_date": today, "bank_account_id": accounts["1020"], "contribution_ids": [original["contribution_id"]]})
        assert deposit.status_code == 201, deposit.text
        deposit_id = deposit.json()["deposit_id"]
        created["deposits"].append(deposit_id)

        # Se corrige (otro fondo y otro monto) DESPUÉS de depositada.
        fixed = await pastora.post(f"/api/finance/contributions/{original['contribution_id']}/correct",
                                   json={"reason": "Era para Misiones y fueron 120", "replacement": contribution("MISSIONS", 12000)})
        assert fixed.status_code == 201, fixed.text
        replacement_id = fixed.json()["replacement_contribution_id"]
        created["contributions"].append(replacement_id)
        assert (await db.finance_deposits.find_one({"deposit_id": deposit_id}))["status"] == "adjustment_required"

        # La corregida ya no se puede depositar ni contar otra vez.
        again = await pastora.post("/api/finance/deposits", json={"deposit_date": today, "bank_account_id": accounts["1020"], "contribution_ids": [original["contribution_id"]]})
        assert again.status_code == 422
        assert (await pastora.post("/api/finance/batches", json={"batch_date": today, "contribution_ids": [original["contribution_id"]]})).status_code == 422

        # Ajuste: el reemplazo queda en el mismo depósito; asiento por fondo (GENERAL −100, MISIONES +120).
        assert (await pastora.post(f"/api/finance/deposits/{deposit_id}/resolve-adjustment", json={"reason": "x"})).status_code == 422
        adjusted = await pastora.post(f"/api/finance/deposits/{deposit_id}/resolve-adjustment", json={"reason": "Corrección de fondo y monto"})
        assert adjusted.status_code == 200, adjusted.text
        body = adjusted.json()
        assert body["status"] == "pending_reconciliation" and body["total_cents"] == 12000
        assert (await db.finance_contributions.find_one({"contribution_id": replacement_id}))["deposit_id"] == deposit_id
        journal = await db.finance_journal_entries.find_one({"entry_id": body["adjustments"][0]["journal_entry_id"]})
        created["journals"].append(journal["entry_id"])
        assert journal["status"] == "submitted" and journal["total_debit_cents"] == 22000  # sigue el flujo normal de aprobación
        bank = sum(line["debit_cents"] - line["credit_cents"] for line in journal["lines"] if line["account_id"] == accounts["1020"])
        assert bank == 2000
        assert (await pastora.post(f"/api/finance/deposits/{deposit_id}/resolve-adjustment", json={"reason": "Otra vez"})).status_code == 409

        # Un asiento que no debe contar (p. ej. transacción externa duplicada) se ANULA: no se borra y conserva su auditoría.
        from finance_engine import create_journal
        from finance_routes import void_journal
        lines = [{"account_id": accounts["1010"], "fund_id": funds["GENERAL"], "debit_cents": 500, "credit_cents": 0, "description": "x"},
                 {"account_id": accounts["4000"], "fund_id": funds["GENERAL"], "debit_cents": 0, "credit_cents": 500, "description": "x"}]
        draft = await create_journal("qa", today, f"QA anular {tag}", "contribution", f"qa-{tag}", lines, "submitted")
        created["journals"].append(draft["entry_id"])
        await void_journal(draft["entry_id"], "qa", "Transacción externa duplicada")
        voided = await db.finance_journal_entries.find_one({"entry_id": draft["entry_id"]})
        assert voided["status"] == "voided" and voided["void_reason"]
        assert await db.finance_audit_events.count_documents({"entity_id": draft["entry_id"]}) == 2  # creado + anulado
        import inspect
        import finance_expansion_routes
        import finance_routes
        assert "finance_journal_entries.delete_one" not in inspect.getsource(finance_routes) + inspect.getsource(finance_expansion_routes)

        # Tablero: presupuesto solo del año fiscal en curso; banco separado de «por depositar».
        old_budget = await pastora.post("/api/finance/budgets", json={"fiscal_year": 2001, "fund_id": funds["GENERAL"], "account_id": accounts["5000"], "amount_cents": 99999900})
        created["budgets"].append(old_budget.json()["budget_id"])
        dashboard = (await pastora.get("/api/finance/dashboard")).json()
        assert dashboard["fiscal_year_from"] <= today <= dashboard["fiscal_year_to"]
        assert dashboard["budget_total_cents"] < 99999900
        assert dashboard["bank_and_cash_cents"] + dashboard["undeposited_cents"] == dashboard["cash_cents"]
    finally:
        await db.finance_contributions.delete_many({"contribution_id": {"$in": created["contributions"]}})
        await db.finance_deposits.delete_many({"deposit_id": {"$in": created["deposits"]}})
        await db.finance_budgets.delete_many({"budget_id": {"$in": created["budgets"]}})
        await db.finance_journal_entries.delete_many({"$or": [{"source_id": {"$in": created["contributions"] + created["deposits"]}}, {"entry_id": {"$in": created["journals"]}}]})
        await db.finance_contribution_corrections.delete_many({"original_contribution_id": {"$in": created["contributions"]}})
        await fx.cleanup()
