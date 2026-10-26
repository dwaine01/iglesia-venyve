"""Nuevo flujo de Finanzas · P3 con datos de PRUEBA: la segunda persona valida (nunca quien registró),
quedan ambos nombres con fecha y hora, los asientos se contabilizan al validar (sin la pastora) y una
corrección guarda valor anterior, motivo y quién, revierte lo contabilizado y pide validar otra vez."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_second_person_validation_and_corrections():
    from finance_collections import ensure_indexes
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    await ensure_indexes()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    collection_id = None
    try:
        pastora = await fx.account(await fx.person(f"PastoraV{tag}"), "pastora")
        both = ["finance.read", "finance.collection.record", "finance.collection.verify"]
        wanda = await fx.account(await fx.person(f"WandaV{tag}"), "lider", privilege_groups=["finance"], capabilities=both, permissions_mode="manual")
        ana = await fx.account(await fx.person(f"AnaV{tag}"), "lider", privilege_groups=["finance"], capabilities=both, permissions_mode="manual")
        donor = await fx.person(f"DonanteV{tag}")
        general = next(item["fund_id"] for item in (await wanda.get("/api/finance/catalog")).json()["funds"] if item["code"] == "GENERAL")
        dashboard_before = (await pastora.get("/api/finance/dashboard")).json()["income_cents"]

        collection_id = (await wanda.post("/api/finance/collections", json={"service_date": date.today().isoformat(), "service_name": f"Miércoles {tag}", "is_test": True})).json()["collection_id"]
        base = f"/api/finance/collections/{collection_id}"
        item_id = (await wanda.post(f"{base}/items", json={"person_id": donor, "contribution_type": "tithe", "fund_id": general, "amount_cents": 30000, "method": "cash", "reference": "S-1"})).json()["items"][0]["item_id"]
        await wanda.post(f"{base}/cash-count", json={"counted_cash_cents": 30000, "envelope_count": 1})
        assert (await ana.post(f"{base}/validate")).status_code == 409  # aún no está enviada
        await wanda.post(f"{base}/submit")

        # Ni quien registró ni la pastora validan; Ana sí.
        assert (await wanda.post(f"{base}/validate")).status_code == 403
        assert (await pastora.post(f"{base}/validate")).status_code == 403
        validated = await ana.post(f"{base}/validate")
        assert validated.status_code == 200, validated.text
        body = validated.json()
        assert body["status"] == "validated" and body["validated_by_name"] and body["validated_at"]
        assert [stage["stage"] for stage in body["timeline"]] == ["opened", "registered", "validated"]
        journal = await db.finance_journal_entries.find_one({"entry_id": body["posted_journal_id"]})
        assert journal["status"] == "posted" and journal["is_test"] is True and journal["approved_by_user_id"] is None  # sin la pastora
        contributions = await db.finance_contributions.find({"collection_id": collection_id}).to_list(10)
        assert len(contributions) == 1 and contributions[0]["status"] == "recorded" and contributions[0]["is_test"] is True
        assert (await pastora.get("/api/finance/dashboard")).json()["income_cents"] == dashboard_before  # los datos de prueba no cuentan

        # Corrección después de validar: guarda antes/después, motivo y quién; revierte y pide validar otra vez.
        fixed = await wanda.post(f"{base}/corrections", json={"action": "update", "item_id": item_id, "reason": "Eran $320, se leyó mal el sobre",
                                                             "item": {"person_id": donor, "contribution_type": "tithe", "fund_id": general, "amount_cents": 32000, "method": "cash", "reference": "S-1"}})
        assert fixed.status_code == 200, fixed.text
        body = fixed.json()
        assert body["status"] == "registered" and body["corrections"][-1]["before"]["amount_cents"] == 30000 and body["corrections"][-1]["after"]["amount_cents"] == 32000
        assert body["corrections"][-1]["by_name"] and body["corrections"][-1]["reason"]
        assert await db.finance_journal_entries.find_one({"reverses_entry_id": journal["entry_id"], "status": "posted"})
        assert (await db.finance_contributions.find_one({"collection_item_id": item_id, "status": "corrected"}))
        assert body["summary"]["pending_explanations"] == ["cash"]  # el conteo ($300) ya no cuadra con el detalle ($320)
        assert (await ana.post(f"{base}/validate")).status_code == 409
        await wanda.post(f"{base}/explanations", json={"kind": "cash", "note": "Los $20 se entregaron aparte a Tesorería"})
        assert (await wanda.post(f"{base}/validate")).status_code == 403  # quien corrigió no valida
        again = await ana.post(f"{base}/validate")
        assert again.status_code == 200 and again.json()["status"] == "validated"
        active = await db.finance_contributions.find({"collection_id": collection_id, "status": "recorded"}).to_list(10)
        assert len(active) == 1 and active[0]["amount_cents"] == 32000

        # Devolver con observaciones (otra colecta).
        other = (await wanda.post("/api/finance/collections", json={"service_date": date.today().isoformat(), "service_name": f"Vigilia {tag}", "is_test": True})).json()["collection_id"]
        await wanda.post(f"/api/finance/collections/{other}/items", json={"anonymous": True, "contribution_type": "offering", "fund_id": general, "amount_cents": 1000, "method": "zelle"})
        await wanda.post(f"/api/finance/collections/{other}/explanations", json={"kind": "zelle", "note": "El banco aún no lo muestra"})
        await wanda.post(f"/api/finance/collections/{other}/submit")
        returned = await ana.post(f"/api/finance/collections/{other}/return", json={"note": "Verifiquen el Zelle con el banco"})
        assert returned.status_code == 200 and returned.json()["status"] == "registering"
        await db.finance_collection_items.delete_many({"collection_id": other})
        await db.finance_collections.delete_many({"collection_id": other})
    finally:
        if collection_id:
            await db.finance_contributions.delete_many({"collection_id": collection_id})
            await db.finance_journal_entries.delete_many({"source_id": collection_id})
            await db.finance_collection_items.delete_many({"collection_id": collection_id})
            await db.finance_collections.delete_many({"collection_id": collection_id})
        await fx.cleanup()
