"""Finanzas sin la pastora · gastos y asientos: Finanzas registra, una segunda persona con el rol Validar
aprueba (nunca quien registró) y Tesorería paga. La pastora solo consulta."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
BASE = ["finance.read", "finance.manage"]


@pytest.mark.asyncio
async def test_expense_and_journal_two_person_flow_without_pastora():
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    expense_id, journal_ids = None, []
    try:
        pastora = await fx.account(await fx.person(f"PastoraG{tag}"), "pastora")
        fin = await fx.account(await fx.person(f"FinG{tag}"), "lider", privilege_groups=["finance"], capabilities=[*BASE, "finance.collection.record", "finance.collection.verify"], permissions_mode="manual")
        val = await fx.account(await fx.person(f"ValG{tag}"), "lider", privilege_groups=["finance"], capabilities=[*BASE, "finance.collection.verify"], permissions_mode="manual")
        tes = await fx.account(await fx.person(f"TesG{tag}"), "lider", privilege_groups=["finance"], capabilities=[*BASE, "finance.treasury"], permissions_mode="manual")
        catalog = (await fin.get("/api/finance/catalog")).json()
        fund = next(item["fund_id"] for item in catalog["funds"] if item["code"] == "GENERAL")
        accounts = {item["code"]: item["account_id"] for item in catalog["accounts"]}
        body = {"expense_date": "2026-10-20", "description": f"QA gasto {tag}", "total_cents": 4500, "allocations": [{"account_id": accounts["5030"], "fund_id": fund, "debit_cents": 4500, "credit_cents": 0}]}

        assert (await pastora.post("/api/finance/expenses", json=body)).status_code == 403
        created = await fin.post("/api/finance/expenses", json=body)
        assert created.status_code == 201, created.text
        expense_id = created.json()["expense_id"]

        assert (await fin.post(f"/api/finance/expenses/{expense_id}/workflow/approve")).status_code == 403   # quien registró
        assert (await pastora.post(f"/api/finance/expenses/{expense_id}/workflow/approve")).status_code == 403
        assert (await tes.post(f"/api/finance/expenses/{expense_id}/workflow/approve")).status_code == 403   # sin rol Validar
        pay = {"payment_date": "2026-10-21", "bank_account_id": accounts["1020"], "payment_method": "ach", "reference": f"QA-{tag}"}
        assert (await tes.post(f"/api/finance/expenses/{expense_id}/payments", json=pay)).status_code == 409  # aún sin validar
        approved = await val.post(f"/api/finance/expenses/{expense_id}/workflow/approve")
        assert approved.status_code == 200 and approved.json()["status"] == "approved", approved.text

        assert (await val.post(f"/api/finance/expenses/{expense_id}/payments", json=pay)).status_code == 403  # sin Tesorería
        assert (await pastora.post(f"/api/finance/expenses/{expense_id}/payments", json=pay)).status_code == 403
        paid = await tes.post(f"/api/finance/expenses/{expense_id}/payments", json=pay)
        assert paid.status_code == 201, paid.text
        journal = await db.finance_journal_entries.find_one({"entry_id": paid.json()["journal_entry_id"]})
        journal_ids.append(journal["entry_id"])
        assert journal["status"] == "posted" and journal["posting_policy"] == "gasto_dos_personas"
        assert (await db.finance_expenses.find_one({"expense_id": expense_id}))["status"] == "paid"

        # Asientos manuales: Finanzas prepara, otra persona con Validar contabiliza; la pastora no.
        lines = [{"account_id": accounts["1020"], "fund_id": fund, "debit_cents": 100, "credit_cents": 0}, {"account_id": accounts["4090"], "fund_id": fund, "debit_cents": 0, "credit_cents": 100}]
        entry = (await fin.post("/api/finance/journals", json={"entry_date": "2026-10-20", "memo": f"QA manual {tag}", "lines": lines})).json()
        journal_ids.append(entry["entry_id"])
        assert (await fin.post(f"/api/finance/journals/{entry['entry_id']}/submit")).status_code == 200
        assert (await fin.post(f"/api/finance/journals/{entry['entry_id']}/approve")).status_code == 403
        assert (await pastora.post(f"/api/finance/journals/{entry['entry_id']}/approve")).status_code == 403
        posted = await val.post(f"/api/finance/journals/{entry['entry_id']}/approve")
        assert posted.status_code == 200 and posted.json()["status"] == "posted", posted.text

        roles = (await pastora.get("/api/finance/my-roles")).json()
        assert roles["pastoral_read_only"] and not roles["verify"] and not roles["treasury"]
        assert (await pastora.get("/api/finance/expenses")).status_code == 200
    finally:
        if expense_id:
            await db.finance_expenses.delete_many({"expense_id": expense_id})
            await db.finance_payments.delete_many({"expense_id": expense_id})
        await db.finance_journal_entries.delete_many({"entry_id": {"$in": journal_ids}})
        await fx.cleanup()
