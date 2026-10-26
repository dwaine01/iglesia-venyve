"""Nuevo flujo de Finanzas · P5 con datos de PRUEBA: Tesorería deposita (monto, fecha, cuenta y comprobante),
el sistema compara con el efectivo recibido y muestra el saldo pendiente. Recorrido completo:
Registrada › Validada › Efectivo recibido por Tesorería › Depositada, cada etapa con quién y cuándo."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.mark.asyncio
async def test_deposit_and_full_journey():
    from finance_collections import ensure_indexes
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    await ensure_indexes()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    collection_id, deposits = None, []
    try:
        caps = lambda *extra: ["finance.read", *extra]  # noqa: E731
        pastora = await fx.account(await fx.person(f"PastoraD{tag}"), "pastora")
        wanda = await fx.account(await fx.person(f"WandaD{tag}"), "lider", privilege_groups=["finance"], capabilities=caps("finance.collection.record"), permissions_mode="manual")
        ana = await fx.account(await fx.person(f"AnaD{tag}"), "lider", privilege_groups=["finance"], capabilities=caps("finance.collection.verify"), permissions_mode="manual")
        tesorera = await fx.account(await fx.person(f"TesoreraD{tag}"), "lider", privilege_groups=["finance"], capabilities=caps("finance.treasury"), permissions_mode="manual")
        catalog = (await wanda.get("/api/finance/catalog")).json()
        funds = {item["code"]: item["fund_id"] for item in catalog["funds"]}
        accounts = {item["code"]: item["account_id"] for item in catalog["accounts"]}
        dashboard_before = (await pastora.get("/api/finance/dashboard")).json()

        collection_id = (await wanda.post("/api/finance/collections", json={"service_date": date.today().isoformat(), "service_name": f"Domingo {tag}", "is_test": True})).json()["collection_id"]
        base = f"/api/finance/collections/{collection_id}"
        await wanda.post(f"{base}/items", json={"anonymous": True, "contribution_type": "tithe", "fund_id": funds["GENERAL"], "amount_cents": 250000, "method": "cash", "reference": "S-1"})
        await wanda.post(f"{base}/items", json={"anonymous": True, "contribution_type": "building", "fund_id": funds["BUILDING"], "amount_cents": 50000, "method": "cash", "reference": "S-2"})
        await wanda.post(f"{base}/items", json={"anonymous": True, "contribution_type": "offering", "fund_id": funds["GENERAL"], "amount_cents": 20000, "method": "other"})
        await wanda.post(f"{base}/cash-count", json={"counted_cash_cents": 300000, "envelope_count": 2})
        await wanda.post(f"{base}/submit")
        await ana.post(f"{base}/validate")
        await wanda.post(f"{base}/handover", json={"delivered_cents": 300000})
        assert (await tesorera.post(f"{base}/deposits", json={"deposit_date": date.today().isoformat(), "bank_account_id": accounts["1020"], "amount_cents": 1000})).status_code == 409
        body = (await tesorera.post(f"{base}/receive", json={"received_cents": 300000})).json()
        assert body["deposit_pending_cents"] == 300000  # otros medios ($200) no son efectivo

        today = date.today().isoformat()
        # Pro-Templo tiene banco designado (Chase): no se mezcla con el depósito al banco principal.
        assert (await tesorera.post(f"{base}/deposits", json={"deposit_date": today, "bank_account_id": accounts["1020"], "amount_cents": 300000})).status_code == 409
        assert (await pastora.post(f"{base}/deposits", json={"deposit_date": today, "bank_account_id": accounts["1020"], "amount_cents": 250000})).status_code == 403
        assert (await tesorera.post(f"{base}/deposits", json={"deposit_date": today, "bank_account_id": accounts["1020"], "amount_cents": 400000})).status_code == 422
        first = await tesorera.post(f"{base}/deposits", json={"deposit_date": today, "bank_account_id": accounts["1020"], "amount_cents": 250000, "reference": "Boleta 101"})
        assert first.status_code == 201, first.text
        body = first.json()
        assert body["status"] == "cash_received" and body["deposit_pending_cents"] == 50000
        deposit_id = body["deposits"][0]["deposit_id"]
        deposits.append(deposit_id)
        voucher = await tesorera.post("/api/finance/documents", data={"entity_type": "deposit", "entity_id": deposit_id}, files={"file": ("boleta.pdf", PDF, "application/pdf")})
        assert voucher.status_code == 201, voucher.text  # Tesorería sube el comprobante
        second = (await tesorera.post(f"{base}/deposits", json={"deposit_date": today, "bank_account_id": accounts["1030"], "amount_cents": 50000, "reference": "Chase 7"})).json()
        deposits.append(second["deposits"][-1]["deposit_id"])
        assert second["status"] == "deposited" and second["deposit_pending_cents"] == 0
        assert [stage["stage"] for stage in second["timeline"]] == ["opened", "registered", "validated", "cash_received", "deposited"]
        assert all(stage.get("by_name") and stage.get("at") for stage in second["timeline"])
        journal = await db.finance_journal_entries.find_one({"source_id": deposit_id})
        assert journal["status"] == "posted" and journal["is_test"] is True
        cash = await db.finance_contributions.find({"collection_id": collection_id, "payment_method": "cash"}).to_list(10)
        assert cash and all(item["deposit_id"] for item in cash)
        dashboard_after = (await pastora.get("/api/finance/dashboard")).json()
        assert dashboard_after["income_cents"] == dashboard_before["income_cents"]  # todo era de prueba
        assert (await pastora.get(base)).status_code == 200  # la pastora consulta todo
    finally:
        if collection_id:
            await db.finance_contributions.delete_many({"collection_id": collection_id})
            await db.finance_journal_entries.delete_many({"source_id": {"$in": [collection_id, *deposits]}})
            await db.finance_deposits.delete_many({"deposit_id": {"$in": deposits}})
            await db["finance_documents.files"].delete_many({"metadata.entity_id": {"$in": deposits}})
            await db.finance_collection_items.delete_many({"collection_id": collection_id})
            await db.finance_collections.delete_many({"collection_id": collection_id})
        await fx.cleanup()
