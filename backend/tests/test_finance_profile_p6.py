"""Nuevo flujo de Finanzas · P6: pestaña Finanzas del Perfil 360 con datos de PRUEBA reales (no is_test,
porque los de prueba nunca se muestran): historial, último diezmo, totales del período y meses sin
registros. Solo lectura, sin etiquetas automáticas; solo la pastora y quien ella autorice; cada consulta registrada."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_profile_finance_tab():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    ids = [f"qa-p6-{tag}-{index}" for index in range(4)]
    try:
        pastora = await fx.account(await fx.person(f"PastoraF{tag}"), "pastora")
        lectora = await fx.account(await fx.person(f"LectoraF{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read"], permissions_mode="manual")
        member = await fx.person(f"MiembroF{tag}")
        rows = [("2025-01-05", "tithe", 10000), ("2025-01-19", "offering", 2000), ("2025-03-02", "tithe", 12000), ("2025-03-09", "donation", 5000)]
        for contribution_id, (day, kind, cents) in zip(ids, rows):
            await db.finance_contributions.insert_one({"_id": contribution_id, "contribution_id": contribution_id, "person_id": member, "contribution_type": kind, "amount_cents": cents,
                                                       "received_date": day, "allocations": [{"contribution_type": kind, "amount_cents": cents, "fund_id": "x"}], "status": "recorded", "test_tag": tag})
        await db.finance_contributions.insert_one({"_id": f"{ids[0]}-t", "contribution_id": f"{ids[0]}-t", "person_id": member, "contribution_type": "tithe", "amount_cents": 99900,
                                                   "received_date": "2025-02-02", "allocations": [{"contribution_type": "tithe", "amount_cents": 99900}], "status": "recorded", "is_test": True})
        ids.append(f"{ids[0]}-t")

        assert (await lectora.get(f"/api/finance/persons/{member}/contributions")).status_code == 403
        before = await db.finance_audit_events.count_documents({"action": "donor_data_viewed", "entity_id": member})
        data = (await pastora.get(f"/api/finance/persons/{member}/contributions", params={"start": "2025-01-01", "end": "2025-04-30"})).json()
        assert data["total_cents"] == 29000 and data["totals_by_type"] == {"tithe": 22000, "offering": 2000, "donation": 5000}  # sin el de prueba
        assert data["last_tithe"] == {"received_date": "2025-03-02", "amount_cents": 12000}
        assert data["months_without_records"] == ["2025-02", "2025-04"] and data["months_in_period"] == 4
        assert [item["received_date"] for item in data["items"]] == ["2025-03-09", "2025-03-02", "2025-01-19", "2025-01-05"]
        assert not any(key in data for key in ("label", "status_label", "obedient", "category"))  # sin etiquetas automáticas
        assert await db.finance_audit_events.count_documents({"action": "donor_data_viewed", "entity_id": member}) == before + 1
        assert (await pastora.get(f"/api/finance/persons/{member}/contributions", params={"start": "2025-05-01", "end": "2025-01-01"})).status_code == 422
    finally:
        await db.finance_contributions.delete_many({"contribution_id": {"$in": ids}})
        await db.finance_audit_events.delete_many({"action": "donor_data_viewed", "entity_id": {"$in": fx.person_ids}})
        await fx.cleanup()
