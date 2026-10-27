"""Revisión de producción · punto 3 (paso 3): el Perfil 360 › Finanzas y el Resumen dicen lo mismo. Solo
suma lo contabilizado; lo registrado sin validar es «Pendiente de contabilizar» y lo prometido en Ven y Come
es «Promesa pendiente» (nunca ingreso). Caso real: $100 de Ven y Come del 2026-10-18 con el asiento sin validar."""
import uuid
from datetime import datetime, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_venycome_100_is_pending_until_validated_and_pledge_apart():
    from finance_engine import create_journal, ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    contribution_id, entry_id, donation_id = f"qa-vyc-{tag}", None, f"qa-don-{tag}"
    try:
        pastora = await fx.account(await fx.person(f"PastoraP3{tag}"), "pastora")
        val = await fx.account(await fx.person(f"ValP3{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read", "finance.collection.verify"], permissions_mode="manual")
        member = await fx.person(f"Miembro{tag}")
        catalog = (await pastora.get("/api/finance/catalog")).json()
        building = next(item["fund_id"] for item in catalog["funds"] if item["code"] == "BUILDING")
        accounts = {item["code"]: item["account_id"] for item in catalog["accounts"]}
        # Como lo dejó la versión anterior: contribución registrada con el asiento «enviado» (sin contabilizar).
        lines = [{"account_id": accounts["1010"], "fund_id": building, "debit_cents": 10000, "credit_cents": 0}, {"account_id": accounts["4040"], "fund_id": building, "debit_cents": 0, "credit_cents": 10000}]
        entry_id = (await create_journal("qa-operador", "2026-10-18", "Ven y Come · Bus de comida", "contribution", contribution_id, lines, "submitted"))["entry_id"]
        now = datetime.now(timezone.utc)
        await db.finance_contributions.insert_one({"_id": contribution_id, "contribution_id": contribution_id, "person_id": member, "anonymous": False, "contribution_type": "building",
                                                   "amount_cents": 10000, "received_date": "2026-10-18", "allocations": [{"fund_id": building, "amount_cents": 10000, "contribution_type": "building"}],
                                                   "journal_entry_id": entry_id, "status": "recorded", "created_at": now, "updated_at": now})
        await db.campaign_donations.insert_one({"_id": donation_id, "donation_id": donation_id, "person_id": member, "donor_name": "Miembro", "amount_cents": 5000, "donation_type": "promise",
                                                "status": "active", "is_rehearsal": False, "created_at": now})
        params = {"start": "2026-01-01", "end": "2026-12-31"}
        before_dash = (await pastora.get("/api/finance/dashboard")).json()

        profile = (await pastora.get(f"/api/finance/persons/{member}/contributions", params=params)).json()
        assert profile["total_cents"] == 0 and profile["items"] == []          # no suma como ingreso
        assert profile["pending"]["cents"] == 10000 and profile["pending"]["items"][0]["received_date"] == "2026-10-18"
        assert profile["pledges"][0]["amount_cents"] == 5000                   # promesa aparte
        assert before_dash["pending_to_post"]["cents"] >= 10000

        # Una segunda persona lo valida en Asientos: recién ahí suma, en el perfil y en el Resumen.
        assert (await val.post(f"/api/finance/journals/{entry_id}/approve")).status_code == 200
        profile = (await pastora.get(f"/api/finance/persons/{member}/contributions", params=params)).json()
        assert profile["total_cents"] == 10000 and profile["pending"]["cents"] == 0
        after_dash = (await pastora.get("/api/finance/dashboard")).json()
        assert after_dash["income_cents"] - before_dash["income_cents"] == 10000
        assert before_dash["pending_to_post"]["cents"] - after_dash["pending_to_post"]["cents"] == 10000
    finally:
        await db.finance_contributions.delete_many({"contribution_id": contribution_id})
        if entry_id:
            await db.finance_journal_entries.delete_many({"entry_id": entry_id})
        await db.campaign_donations.delete_many({"donation_id": donation_id})
        await fx.cleanup()
