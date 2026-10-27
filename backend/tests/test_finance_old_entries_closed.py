"""Finanzas sin la pastora · B: los donativos de Ven y Come (y los pagos de Librería) entran como aportes de una
colecta; Finanzas la cuadra y envía, y una SEGUNDA persona la valida. Las pantallas antiguas ya no crean aportes."""
import uuid

import pytest
from fastapi import HTTPException

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
BOTH = ["finance.read", "finance.manage", "finance.collection.record", "finance.collection.verify"]


@pytest.mark.asyncio
async def test_venycome_goes_through_collection_and_old_entries_are_closed():
    from finance_collections import ensure_indexes
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    await ensure_indexes()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    donation_id = collection_id = None
    try:
        pastora = await fx.account(await fx.person(f"PastoraB{tag}"), "pastora")
        wanda = await fx.account(await fx.person(f"WandaB{tag}"), "lider", privilege_groups=["finance"], capabilities=BOTH, permissions_mode="manual")
        ana = await fx.account(await fx.person(f"AnaB{tag}"), "lider", privilege_groups=["finance"], capabilities=BOTH, permissions_mode="manual")
        donor = await fx.person(f"DonanteB{tag}")
        encargado = await fx.account(await fx.person(f"EncargadoB{tag}"), "lider", capabilities=["campaign.venycome.manage"], permissions_mode="manual")
        funds = {item["code"]: item["fund_id"] for item in (await wanda.get("/api/finance/catalog")).json()["funds"]}

        # Las pantallas antiguas ya no crean aportes (la pastora: no autorizado).
        body = {"anonymous": True, "contribution_type": "tithe", "amount_cents": 100, "received_date": "2026-10-01", "payment_method": "cash", "allocations": [{"fund_id": funds["GENERAL"], "amount_cents": 100}]}
        assert (await wanda.post("/api/finance/contributions", json=body)).status_code == 410
        assert (await wanda.post("/api/finance/batches", json={"batch_date": "2026-10-01"})).status_code == 410
        assert (await wanda.post("/api/finance/contributions/import-csv")).status_code == 410
        assert (await pastora.post("/api/finance/contributions", json=body)).status_code == 403

        # Ven y Come (modo ensayo = datos de prueba): verificar el donativo lo pone en la colecta del día.
        donation = (await pastora.post("/api/campaigns/venycome/donations", json={"donor_name": f"DonanteB{tag}", "person_id": donor, "amount_cents": 2500,
                                                                                    "donation_type": "received", "idempotency_key": str(uuid.uuid4())})).json()
        donation_id = donation["donation_id"]
        assert (await pastora.post(f"/api/campaigns/venycome/donations/{donation_id}/receive", json={"payment_method": "cash"})).status_code == 403  # la pastora no
        verified = await encargado.post(f"/api/campaigns/venycome/donations/{donation_id}/receive", json={"payment_method": "cash"})
        assert verified.status_code == 200, verified.text
        collection_id = verified.json()["finance_collection_id"]
        assert not await db.finance_contributions.find_one({"origin.source_id": donation_id})  # aún no es contribución
        base = f"/api/finance/collections/{collection_id}"
        collection = (await wanda.get(base)).json()
        assert collection["source"] == "campaign_venycome" and collection["is_test"] is True and collection["summary"]["cash_detail_cents"] >= 2500
        item = await db.finance_collection_items.find_one({"collection_id": collection_id, "origin.source_id": donation_id})
        assert item["campaign_id"] and item["amount_cents"] == 2500 and item["method"] == "cash"
        cash, envelopes = collection["summary"]["cash_detail_cents"], collection["summary"]["envelopes_registered"]  # la colecta del día puede traer otros donativos de prueba

        # Finanzas cuenta y envía; otra persona valida. Nadie espera a la pastora.
        counted = await wanda.post(f"{base}/cash-count", json={"counted_cash_cents": cash, "envelope_count": envelopes})
        assert counted.status_code == 200
        for kind in counted.json()["summary"]["pending_explanations"]:  # p. ej. Zelle de prueba de otros donativos del día
            assert (await wanda.post(f"{base}/explanations", json={"kind": kind, "note": "Datos de prueba del mismo día"})).status_code == 200
        assert (await wanda.post(f"{base}/submit")).status_code == 200
        assert (await wanda.post(f"{base}/validate")).status_code == 403
        assert (await pastora.post(f"{base}/validate")).status_code == 403
        validated = await ana.post(f"{base}/validate")
        assert validated.status_code == 200, validated.text
        contribution = await db.finance_contributions.find_one({"collection_id": collection_id, "origin.source_id": donation_id})
        assert contribution["campaign_id"] and contribution["person_id"] == donor and contribution["is_test"] is True
        assert contribution["origin"] == {"source": "campaign_venycome", "source_id": donation_id}
        journal = await db.finance_journal_entries.find_one({"entry_id": contribution["journal_entry_id"]})
        assert journal["status"] == "posted" and all(line.get("campaign_id") for line in journal["lines"])

        # Ya validada: deshacer desde Ven y Come pide una corrección de la colecta en Finanzas.
        assert (await encargado.post(f"/api/campaigns/venycome/donations/{donation_id}/unverify")).status_code == 409
        assert (await encargado.post(f"/api/campaigns/venycome/donations/{donation_id}/receive", json={"payment_method": "cash"})).status_code == 409  # sin duplicar

        # La regla «transacción externa única» sigue en los registros antiguos (correcciones).
        from finance_routes import ContributionCreate, record_contribution
        legacy = ContributionCreate(**{**body, "source": "csv", "external_transaction_id": f"QA-EXT-{tag}"})
        first = await record_contribution(legacy, {"user_id": str(fx.user_ids[1])})
        with pytest.raises(HTTPException) as duplicate:
            await record_contribution(legacy, {"user_id": str(fx.user_ids[1])})
        assert duplicate.value.status_code == 409
        await db.finance_contributions.delete_many({"contribution_id": first["contribution_id"]})
        await db.finance_journal_entries.delete_many({"entry_id": first["journal_entry_id"]})
    finally:
        if collection_id:
            entries = await db.finance_contributions.distinct("journal_entry_id", {"collection_id": collection_id})
            await db.finance_journal_entries.delete_many({"entry_id": {"$in": entries}})
            await db.finance_contributions.delete_many({"collection_id": collection_id})
            await db.finance_collection_items.delete_many({"collection_id": collection_id})
            await db.finance_collections.delete_many({"collection_id": collection_id})
        if donation_id:
            await db.campaign_donations.delete_many({"donation_id": donation_id})
        await fx.cleanup()
