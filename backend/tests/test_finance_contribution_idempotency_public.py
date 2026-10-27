"""Regresión pública para contribuciones manuales, splits e idempotencia externa."""
import os
from datetime import date
from uuid import uuid4

import pytest
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")


def api(path: str) -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is required")
    return f"{BASE_URL}{path}"


def auth_headers() -> dict:
    # Nuevo flujo: la pastora solo consulta; registra el equipo de Finanzas.
    from tests.conftest import finance_team_token
    return {"Authorization": f"Bearer {finance_team_token(api(''))}"}


def cleanup_finance_regression(reference_prefix: str) -> None:
    client = MongoClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    contributions = list(
        database.finance_contributions.find(
            {"reference": {"$regex": f"^{reference_prefix}"}},
            {"_id": 0, "contribution_id": 1, "journal_entry_id": 1},
        )
    )
    contribution_ids = [item["contribution_id"] for item in contributions]
    journal_ids = [item["journal_entry_id"] for item in contributions]
    if contribution_ids:
        database.finance_contributions.delete_many({"contribution_id": {"$in": contribution_ids}})
        database.finance_journal_entries.delete_many({"entry_id": {"$in": journal_ids}})
        database.finance_audit_events.delete_many(
            {"entity_id": {"$in": contribution_ids + journal_ids}}
        )
    client.close()


def test_manual_split_and_external_idempotency():
    headers = auth_headers()
    catalog = requests.get(api("/api/finance/catalog"), headers=headers, timeout=30)
    assert catalog.status_code == 200, catalog.text
    funds = catalog.json()["funds"]
    assert len(funds) >= 2

    run_id = uuid4().hex
    reference_prefix = f"QA-P0-FINANCE-{run_id}"
    common = {
        "anonymous": True,
        "contribution_type": "offering",
        "received_date": date.today().isoformat(),
        "payment_method": "cash",
    }

    try:
        # Los aportes nuevos ya no entran por aquí: van por Finanzas › Colecta (registro y validación por una
        # segunda persona). La regla de transacción externa única sigue probada en test_finance_old_entries_closed.
        payload = {**common, "reference": f"{reference_prefix}-MANUAL-1", "amount_cents": 100,
                   "allocations": [{"fund_id": funds[0]["fund_id"], "amount_cents": 100}], "source": "csv", "external_transaction_id": f"{reference_prefix}-EXTERNAL"}
        for _ in range(2):
            closed = requests.post(api("/api/finance/contributions"), headers=headers, json=payload, timeout=30)
            assert closed.status_code == 410, closed.text
            assert "Colecta" in closed.json()["detail"]
        listed = requests.get(api("/api/finance/contributions"), headers=headers, timeout=30).json()["items"]
        assert not [item for item in listed if str(item.get("reference") or "").startswith(reference_prefix)]
    finally:
        cleanup_finance_regression(reference_prefix)