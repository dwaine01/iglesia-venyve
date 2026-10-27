"""Finanzas sin la pastora · C: la pastora (y toda cuenta con Acceso Maestro) solo CONSULTA. El servidor
responde «no autorizado» a cualquier cambio suyo; cierres, reaperturas, configuración y cartas los hace el
equipo de Finanzas con su rol."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
WRITES = [
    ("put", "/api/finance/settings", {"accounting_basis": "cash"}),
    ("post", "/api/finance/funds", {"code": "QA", "name": "QA fondo", "restriction_type": "unrestricted", "purpose": "QA"}),
    ("post", "/api/finance/accounts", {"code": "9999", "name": "QA", "account_type": "asset"}),
    ("post", "/api/finance/periods", {"year": 2031, "month": 1, "name": "QA", "start_date": "2031-01-01", "end_date": "2031-01-31"}),
    ("post", "/api/finance/periods/2031-01/close", {}),
    ("post", "/api/finance/periods/2031-01/reopen", {"reason": "QA motivo"}),
    ("post", "/api/finance/journals", {"entry_date": "2031-01-02", "memo": "QA", "lines": []}),
    ("post", "/api/finance/journals/x/approve", {}),
    ("post", "/api/finance/journals/x/reject", {}),
    ("post", "/api/finance/contributions", {}),
    ("post", "/api/finance/contributions/x/correct", {}),
    ("post", "/api/finance/batches", {}),
    ("post", "/api/finance/batches/x/resolve-variance", {"reason": "QA motivo"}),
    ("post", "/api/finance/vendors", {"name": "QA proveedor"}),
    ("post", "/api/finance/expenses", {}),
    ("post", "/api/finance/expenses/x/workflow/approve", {}),
    ("post", "/api/finance/expenses/x/payments", {}),
    ("post", "/api/finance/deposits", {}),
    ("post", "/api/finance/deposits/x/resolve-adjustment", {"reason": "QA motivo"}),
    ("post", "/api/finance/transfers", {}),
    ("post", "/api/finance/budgets", {}),
    ("post", "/api/finance/reconciliations", {}),
    ("post", "/api/finance/contribution-types", {"type_key": "qa_tipo", "name": "QA", "revenue_account_id": "x"}),
    ("put", "/api/finance/settings/annual-statements", {}),
    ("post", "/api/finance/contributors/x/annual-statements/2026", {}),
    ("post", "/api/finance/recurring-obligations/generate", {}),
    ("post", "/api/finance/collections", {"service_date": "2031-01-02", "service_name": "QA", "is_test": True}),
    ("post", "/api/finance/collections/x/validate", {}),
    ("post", "/api/finance/collections/x/receive", {}),
    ("post", "/api/finance/collections/x/deposits", {}),
    ("post", "/api/finance/zelle", {}),
    ("post", "/api/finance/migration/apply", {"confirmation": "CONTABILIZAR PENDIENTES"}),
    ("post", "/api/finance/migration/x/undo", {}),
]


@pytest.mark.asyncio
async def test_pastora_is_read_only_and_team_runs_closings_and_settings():
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    period_id = "2031-02"
    try:
        pastora = await fx.account(await fx.person(f"PastoraC{tag}"), "pastora")
        maestro = await fx.account(await fx.person(f"MaestroC{tag}"), "admin")  # Acceso Maestro: también solo lectura en Finanzas
        fin = await fx.account(await fx.person(f"FinC{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read", "finance.manage"], permissions_mode="manual")
        val = await fx.account(await fx.person(f"ValC{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read", "finance.collection.verify"], permissions_mode="manual")

        for account in (pastora, maestro):
            for method, path, body in WRITES:
                response = await getattr(account, method)(path, json=body)
                assert response.status_code == 403, (path, response.status_code, response.text)
            for path in ("/api/finance/dashboard", "/api/finance/journals", "/api/finance/expenses", "/api/finance/collections", "/api/finance/periods", "/api/finance/migration/preview", "/api/finance/my-roles"):
                assert (await account.get(path)).status_code == 200, path
        roles = (await pastora.get("/api/finance/my-roles")).json()
        assert roles["pastoral_read_only"] and not any(roles[key] for key in ("manage", "record", "verify", "treasury"))

        # Cierre del mes: Finanzas cierra; reabrir con motivo lo hace otra persona con el rol Validar.
        created = await fin.post("/api/finance/periods", json={"year": 2031, "month": 2, "name": f"QA {tag}", "start_date": "2031-02-01", "end_date": "2031-02-28"})
        assert created.status_code == 201, created.text
        closed = await fin.post(f"/api/finance/periods/{period_id}/close")
        assert closed.status_code == 200 and closed.json()["status"] == "closed", closed.text
        assert (await fin.post(f"/api/finance/periods/{period_id}/reopen", json={"reason": "Falta un gasto"})).status_code == 403
        reopened = await val.post(f"/api/finance/periods/{period_id}/reopen", json={"reason": "Falta un gasto"})
        assert reopened.status_code == 200 and reopened.json()["status"] == "open", reopened.text

        # Configuración y carta anual: el equipo de Finanzas (antes solo la pastora).
        assert (await fin.put("/api/finance/settings", json={"accounting_basis": "cash"})).status_code == 200
        assert (await fin.get("/api/finance/settings/annual-statements")).status_code == 200
    finally:
        await db.finance_periods.delete_many({"period_id": period_id})
        await fx.cleanup()
