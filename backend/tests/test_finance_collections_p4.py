"""Nuevo flujo de Finanzas · P4 con datos de PRUEBA: Wanda entrega $3,000 en efectivo, Tesorería confirma
desde su usuario. Si recibe otra cantidad, registra el monto real y la diferencia queda por aclarar. El Zelle
es parte de la colecta pero no del efectivo. Quien entrega nunca recibe la misma colecta."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_cash_handover_to_treasury():
    from finance_collections import ensure_indexes
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    await ensure_indexes()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    ids = []
    try:
        caps = lambda *extra: ["finance.read", *extra]  # noqa: E731
        pastora = await fx.account(await fx.person(f"PastoraE{tag}"), "pastora")
        wanda = await fx.account(await fx.person(f"WandaE{tag}"), "lider", privilege_groups=["finance"], capabilities=caps("finance.collection.record", "finance.treasury"), permissions_mode="manual")
        ana = await fx.account(await fx.person(f"AnaE{tag}"), "lider", privilege_groups=["finance"], capabilities=caps("finance.collection.verify"), permissions_mode="manual")
        tesorera = await fx.account(await fx.person(f"TesoreraE{tag}"), "lider", privilege_groups=["finance"], capabilities=caps("finance.treasury"), permissions_mode="manual")
        general = next(item["fund_id"] for item in (await wanda.get("/api/finance/catalog")).json()["funds"] if item["code"] == "GENERAL")

        async def validated_collection(name, cash_cents, zelle_cents=0):
            collection_id = (await wanda.post("/api/finance/collections", json={"service_date": date.today().isoformat(), "service_name": f"{name} {tag}", "is_test": True})).json()["collection_id"]
            ids.append(collection_id)
            base = f"/api/finance/collections/{collection_id}"
            await wanda.post(f"{base}/items", json={"anonymous": True, "contribution_type": "offering", "fund_id": general, "amount_cents": cash_cents, "method": "cash", "reference": "Bolsa"})
            if zelle_cents:
                await wanda.post(f"{base}/items", json={"anonymous": True, "contribution_type": "tithe", "fund_id": general, "amount_cents": zelle_cents, "method": "zelle"})
                await wanda.post(f"{base}/explanations", json={"kind": "zelle", "note": "Se verifica con el banco el lunes"})
            await wanda.post(f"{base}/cash-count", json={"counted_cash_cents": cash_cents, "envelope_count": 1})
            assert (await wanda.post(f"{base}/submit")).status_code == 200
            assert (await ana.post(f"{base}/validate")).status_code == 200
            return base

        # Recibe exactamente lo entregado: el Zelle ($500) no entra en el efectivo.
        base = await validated_collection("Domingo", 300000, zelle_cents=50000)
        assert (await tesorera.post(f"{base}/receive", json={"received_cents": 300000})).status_code == 409  # aún no hay entrega
        handed = (await wanda.post(f"{base}/handover", json={"delivered_cents": 300000})).json()
        assert handed["handover"]["expected_cash_cents"] == 300000 and handed["handover"]["delivered_by_name"]
        assert (await wanda.post(f"{base}/receive", json={"received_cents": 300000})).status_code == 403  # quien entrega no recibe
        assert (await pastora.post(f"{base}/receive", json={"received_cents": 300000})).status_code == 403
        received = await tesorera.post(f"{base}/receive", json={"received_cents": 300000})
        assert received.status_code == 200, received.text
        body = received.json()
        assert body["status"] == "cash_received" and body["reception"]["difference_status"] == "none" and body["reception"]["received_by_name"]
        assert [stage["stage"] for stage in body["timeline"]][-1] == "cash_received"
        assert (await wanda.post(f"{base}/corrections", json={"action": "void", "item_id": body["items"][0]["item_id"], "reason": "Ya no se puede corregir aquí"})).status_code == 409

        # Recibe $10 menos: queda la diferencia por aclarar y un asiento a «Diferencias por aclarar».
        base = await validated_collection("Miércoles", 300000)
        await wanda.post(f"{base}/handover", json={"delivered_cents": 300000})
        short = (await tesorera.post(f"{base}/receive", json={"received_cents": 299000, "note": "Contado dos veces"})).json()
        assert short["reception"]["difference_cents"] == -1000 and short["reception"]["difference_status"] == "pending"
        journal = await db.finance_journal_entries.find_one({"entry_id": short["reception"]["journal_entry_id"]})
        assert journal["status"] == "posted" and journal["is_test"] is True and journal["total_debit_cents"] == 1000
        clarified = await tesorera.post(f"{base}/clarify-cash", json={"note": "Faltó un billete de $10; se repone el domingo"})
        assert clarified.status_code == 200 and clarified.json()["reception"]["difference_status"] == "clarified"
    finally:
        for collection_id in ids:
            await db.finance_contributions.delete_many({"collection_id": collection_id})
            await db.finance_journal_entries.delete_many({"source_id": collection_id})
            await db.finance_collection_items.delete_many({"collection_id": collection_id})
            await db.finance_collections.delete_many({"collection_id": collection_id})
        await fx.cleanup()
