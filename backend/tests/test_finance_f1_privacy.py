"""Finanzas F1 (decisión del dueño): lo que da cada persona lo ve SOLO la pastora; el resto de Finanzas
ve totales sin nombres; cada consulta por persona queda registrada. Permisos en el servidor."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_donor_data_only_for_pastora_and_logged():
    from count_rules import church_today
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    contributions = []
    try:
        pastora = await fx.account(await fx.person(f"PastoraP{tag}"), "pastora")
        finance = await fx.account(await fx.person(f"TesoreraP{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read", "finance.manage"], permissions_mode="manual")
        donor = await fx.person(f"DonanteP{tag}")
        catalog = (await pastora.get("/api/finance/catalog")).json()
        general = next(item["fund_id"] for item in catalog["funds"] if item["code"] == "GENERAL")
        today = (await church_today()).isoformat()
        created = await finance.post("/api/finance/contributions", json={"person_id": donor, "contribution_type": "tithe", "amount_cents": 4200, "received_date": today, "payment_method": "cash",
                                                                         "reference": "Cheque 77", "notes": f"Sobre de DonanteP{tag}", "allocations": [{"fund_id": general, "amount_cents": 4200}]})
        assert created.status_code == 201, created.text  # la tesorera sigue registrando con nombre
        contributions.append(created.json()["contribution_id"])

        # El resto de Finanzas: la lista sin quién dio; los totales siguen.
        listed = (await finance.get("/api/finance/contributions")).json()
        mine = next(item for item in listed["items"] if item["contribution_id"] == contributions[0])
        assert listed["donors_hidden"] is True and mine["amount_cents"] == 4200 and mine["donor_hidden"] is True
        assert not {"person_id", "person_name", "reference", "notes"} & set(mine)
        for path in (f"/api/finance/contributors/{donor}", f"/api/finance/contributors/{donor}/history", f"/api/finance/persons/{donor}/contributions",
                     "/api/finance/reports/contributions-by-family"):
            assert (await finance.get(path)).status_code == 403, path
        assert (await finance.post(f"/api/finance/contributors/{donor}/annual-statements/2026")).status_code == 403
        search = (await finance.get("/api/finance/contributors/search", params={"search": f"DonanteP{tag}"})).json()["items"]
        assert search and "contribution_count" not in search[0]  # busca el nombre para registrar, sin cuántas veces dio
        assert (await finance.get("/api/finance/reports/contributions")).status_code == 200  # totales por concepto y fondo
        audit = (await finance.get("/api/finance/reports/audit")).json()["items"]
        assert all("person_id" not in (event.get("changes") or {}) for event in audit)

        # La pastora sí lo ve, y cada consulta queda registrada.
        before = await db.finance_audit_events.count_documents({"action": "donor_data_viewed"})
        detail = (await pastora.get(f"/api/finance/contributors/{donor}")).json()
        assert detail["total_cents"] == 4200
        full = (await pastora.get("/api/finance/contributions")).json()
        assert full["donors_hidden"] is False and any(item.get("person_id") == donor for item in full["items"])
        assert await db.finance_audit_events.count_documents({"action": "donor_data_viewed"}) == before + 2
        assert await db.finance_audit_events.find_one({"action": "donor_data_viewed", "entity_id": donor})

        # La tesorera corrige sin ver al donante: el reemplazo conserva la misma persona.
        fixed = await finance.post(f"/api/finance/contributions/{contributions[0]}/correct",
                                   json={"reason": "Monto mal escrito", "replacement": {"contribution_type": "tithe", "amount_cents": 4300, "received_date": today, "payment_method": "cash",
                                                                                        "allocations": [{"fund_id": general, "amount_cents": 4300}]}})
        assert fixed.status_code == 201, fixed.text
        contributions.append(fixed.json()["replacement_contribution_id"])
        assert (await db.finance_contributions.find_one({"contribution_id": contributions[-1]}))["person_id"] == donor
    finally:
        await db.finance_journal_entries.delete_many({"source_id": {"$in": contributions}})
        await db.finance_contributions.delete_many({"contribution_id": {"$in": contributions}})
        await db.finance_contribution_corrections.delete_many({"original_contribution_id": {"$in": contributions}})
        await fx.cleanup()
