"""Cleanup verification for finance QA prefixes and related GridFS artifacts."""

import os
import re

import pytest
from pymongo import MongoClient


PREFIX_PATTERN = re.compile(r"QA-(G28|I15|P0)", re.IGNORECASE)


def _db():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME no definidos")
    return MongoClient(mongo_url)[db_name]


# módulo: verificación de cleanup de datos QA en colecciones finance_*
def test_no_finance_qa_prefix_leftovers():
    db = _db()
    checks = {
        "finance_contributions": {"$or": [{"reference": {"$regex": PREFIX_PATTERN.pattern}}, {"notes": {"$regex": PREFIX_PATTERN.pattern}}]},
        "finance_batches": {"$or": [{"service_name": {"$regex": PREFIX_PATTERN.pattern}}, {"notes": {"$regex": PREFIX_PATTERN.pattern}}]},
        "finance_deposits": {"reference": {"$regex": PREFIX_PATTERN.pattern}},
        "finance_vendors": {"name": {"$regex": PREFIX_PATTERN.pattern}},
        "finance_expenses": {"$or": [{"description": {"$regex": PREFIX_PATTERN.pattern}}, {"invoice_number": {"$regex": PREFIX_PATTERN.pattern}}, {"category": {"$regex": PREFIX_PATTERN.pattern}}]},
        "finance_payments": {"reference": {"$regex": PREFIX_PATTERN.pattern}},
        "finance_campaigns": {"name": {"$regex": PREFIX_PATTERN.pattern}},
        "finance_budgets": {"category": {"$regex": PREFIX_PATTERN.pattern}},
        "finance_periods": {"name": {"$regex": PREFIX_PATTERN.pattern}},
        "finance_reconciliations": {"notes": {"$regex": PREFIX_PATTERN.pattern}},
        "finance_recurring_obligations": {"$or": [{"name": {"$regex": PREFIX_PATTERN.pattern}}, {"description": {"$regex": PREFIX_PATTERN.pattern}}]},
    }

    try:
        for collection_name, query in checks.items():
            count = db[collection_name].count_documents(query)
            assert count == 0, f"Leftover QA artifacts in {collection_name}: {count}"

        grid_files_left = db["finance_documents.files"].count_documents(
            {
                "$or": [
                    {"filename": {"$regex": PREFIX_PATTERN.pattern}},
                    {"metadata.entity_id": {"$regex": PREFIX_PATTERN.pattern}},
                ]
            }
        )
        assert grid_files_left == 0, f"Leftover GridFS files: {grid_files_left}"
    finally:
        db.client.close()
