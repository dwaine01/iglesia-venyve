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
    response = requests.post(
        api("/api/auth/login"),
        json={"email": PASTOR[0], "password": PASTOR[1]},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


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
        first_manual = requests.post(
            api("/api/finance/contributions"),
            headers=headers,
            json={
                **common,
                "reference": f"{reference_prefix}-MANUAL-1",
                "amount_cents": 100,
                "allocations": [{"fund_id": funds[0]["fund_id"], "amount_cents": 100}],
                "source": "manual",
            },
            timeout=30,
        )
        second_manual_split = requests.post(
            api("/api/finance/contributions"),
            headers=headers,
            json={
                **common,
                "reference": f"{reference_prefix}-MANUAL-2",
                "amount_cents": 300,
                "allocations": [
                    {"fund_id": funds[0]["fund_id"], "amount_cents": 100},
                    {"fund_id": funds[1]["fund_id"], "amount_cents": 200},
                ],
                "source": "manual",
            },
            timeout=30,
        )
        assert first_manual.status_code == 201, first_manual.text
        assert second_manual_split.status_code == 201, second_manual_split.text

        external_id = f"{reference_prefix}-EXTERNAL"
        external_payload = {
            **common,
            "reference": f"{reference_prefix}-CSV",
            "amount_cents": 250,
            "allocations": [{"fund_id": funds[0]["fund_id"], "amount_cents": 250}],
            "source": "csv",
            "external_transaction_id": external_id,
        }
        imported = requests.post(
            api("/api/finance/contributions"), headers=headers, json=external_payload, timeout=30
        )
        duplicate = requests.post(
            api("/api/finance/contributions"), headers=headers, json=external_payload, timeout=30
        )
        missing_external_id = requests.post(
            api("/api/finance/contributions"),
            headers=headers,
            json={**external_payload, "external_transaction_id": ""},
            timeout=30,
        )

        assert imported.status_code == 201, imported.text
        assert duplicate.status_code == 409, duplicate.text
        assert missing_external_id.status_code == 422, missing_external_id.text
    finally:
        cleanup_finance_regression(reference_prefix)