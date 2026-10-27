"""Decisiones del dueño (revisión de producción): (a) el Acceso Maestro queda en solo lectura en Finanzas pero
SÍ sigue asignando los roles en Gestión de accesos; (c) quien aprobó un gasto no lo paga; quien lo registró sí."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
BASE = ["finance.read", "finance.manage"]


@pytest.mark.asyncio
async def test_master_access_assigns_roles_and_approver_cannot_pay():
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    expense_ids, journal_ids = [], []
    try:
        maestro = await fx.account(await fx.person(f"MaestroO{tag}"), "admin")
        wanda_person = await fx.person(f"WandaO{tag}")
        await fx.account(wanda_person, "lider", privilege_groups=["finance"], capabilities=["finance.read"], permissions_mode="manual")
        wanda_user = await db.users.find_one({"person_id": wanda_person})
        # (a) Gestión de accesos no es Finanzas: el Acceso Maestro asigna roles; en Finanzas solo consulta.
        body = {"access_level": "lider", "privilege_groups": ["finance"], "capabilities": ["finance.read", "finance.manage", "finance.treasury"], "is_active": True}
        granted = await maestro.put(f"/api/core/governance/users/{wanda_user['_id']}/access", json=body)
        assert granted.status_code == 200, granted.text
        assert "finance.treasury" in (await db.users.find_one({"_id": wanda_user["_id"]}))["capabilities"]
        assert (await maestro.post("/api/finance/vendors", json={"name": f"QA {tag}"})).status_code == 403

        # (c) Registra Finanzas+Tesorería; aprueba Validar+Tesorería; quien aprobó no paga; quien registró sí.
        fin_tes = await fx.account(await fx.person(f"FinTesO{tag}"), "lider", privilege_groups=["finance"], capabilities=[*BASE, "finance.treasury"], permissions_mode="manual")
        val_tes = await fx.account(await fx.person(f"ValTesO{tag}"), "lider", privilege_groups=["finance"], capabilities=[*BASE, "finance.collection.verify", "finance.treasury"], permissions_mode="manual")
        catalog = (await fin_tes.get("/api/finance/catalog")).json()
        fund = next(item["fund_id"] for item in catalog["funds"] if item["code"] == "GENERAL")
        accounts = {item["code"]: item["account_id"] for item in catalog["accounts"]}
        expense = (await fin_tes.post("/api/finance/expenses", json={"expense_date": "2026-10-20", "description": f"QA gasto {tag}", "total_cents": 1500,
                                                                   "allocations": [{"account_id": accounts["5030"], "fund_id": fund, "debit_cents": 1500, "credit_cents": 0}]})).json()
        expense_ids.append(expense["expense_id"])
        assert (await val_tes.post(f"/api/finance/expenses/{expense['expense_id']}/workflow/approve")).status_code == 200
        pay = {"payment_date": "2026-10-21", "bank_account_id": accounts["1020"], "payment_method": "check", "reference": f"QA-{tag}"}
        blocked = await val_tes.post(f"/api/finance/expenses/{expense['expense_id']}/payments", json=pay)
        assert blocked.status_code == 403 and "aprobó" in blocked.json()["detail"]
        paid = await fin_tes.post(f"/api/finance/expenses/{expense['expense_id']}/payments", json=pay)
        assert paid.status_code == 201, paid.text
        journal_ids.append(paid.json()["journal_entry_id"])
    finally:
        await db.finance_expenses.delete_many({"expense_id": {"$in": expense_ids}})
        await db.finance_payments.delete_many({"expense_id": {"$in": expense_ids}})
        await db.finance_journal_entries.delete_many({"entry_id": {"$in": journal_ids}})
        await db.finance_vendors.delete_many({"name": f"QA {tag}"})
        await fx.cleanup()
