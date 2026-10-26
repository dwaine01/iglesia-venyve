"""Nuevo flujo de Finanzas · P2: registro y cuadre de la colecta con datos de PRUEBA (is_test).
Efectivo / Zelle / total separados, sobres, Zelle a mano y por CSV (cada transacción con un solo aporte),
diferencias documentadas, nada se borra y la pastora solo consulta."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
RECORD = ["finance.read", "finance.manage", "finance.collection.record"]


@pytest.mark.asyncio
async def test_collection_registration_balance_and_zelle():
    from finance_collections import ensure_indexes
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    await ensure_indexes()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    collection_id = None
    try:
        pastora = await fx.account(await fx.person(f"PastoraC{tag}"), "pastora")
        wanda = await fx.account(await fx.person(f"WandaC{tag}"), "lider", privilege_groups=["finance"], capabilities=RECORD, permissions_mode="manual")
        tesorera = await fx.account(await fx.person(f"TesoreraC{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read", "finance.treasury"], permissions_mode="manual")
        lectora = await fx.account(await fx.person(f"LectoraC{tag}"), "lider", privilege_groups=["finance"], capabilities=["finance.read"], permissions_mode="manual")
        donor = await fx.person(f"DonanteC{tag}")
        catalog = (await wanda.get("/api/finance/catalog")).json()
        general = next(item["fund_id"] for item in catalog["funds"] if item["code"] == "GENERAL")
        assert any(item["type_key"] == "special_offering" for item in catalog["contribution_types"])
        today = date.today().isoformat()

        # La pastora no abre colectas (solo consulta).
        assert (await pastora.post("/api/finance/collections", json={"service_date": today, "service_name": "Domingo", "is_test": True})).status_code == 403
        opened = await wanda.post("/api/finance/collections", json={"service_date": today, "service_name": f"Domingo prueba {tag}", "is_test": True})
        assert opened.status_code == 201, opened.text
        collection_id = opened.json()["collection_id"]
        base = f"/api/finance/collections/{collection_id}"

        def item(**extra):
            return {"contribution_type": "tithe", "fund_id": general, "amount_cents": 5000, "method": "cash", **extra}
        await wanda.post(f"{base}/items", json=item(person_id=donor, reference="Sobre 1"))
        await wanda.post(f"{base}/items", json=item(anonymous=True, contribution_type="offering", amount_cents=2000, reference="Sobre 2"))
        zelle_item = (await wanda.post(f"{base}/items", json=item(person_id=donor, method="zelle", amount_cents=10000, reference="ZL-1"))).json()["items"][-1]["item_id"]
        other = (await wanda.post(f"{base}/items", json=item(anonymous=True, contribution_type="special_offering", method="other", amount_cents=1000))).json()["items"][-1]["item_id"]
        assert (await wanda.post(f"{base}/items", json=item())).status_code == 422  # sin persona ni ANÓNIMO

        data = (await wanda.get(base)).json()["summary"]
        assert (data["cash_detail_cents"], data["zelle_cents"], data["other_cents"], data["total_cents"]) == (7000, 10000, 1000, 18000)
        assert (await wanda.post(f"{base}/submit")).status_code == 409  # falta el conteo del efectivo

        # Conteo: faltan $5 en efectivo → diferencia que hay que explicar.
        data = (await wanda.post(f"{base}/cash-count", json={"counted_cash_cents": 6500, "envelope_count": 2})).json()["summary"]
        assert [item["kind"] for item in data["differences"]] == ["cash", "zelle"] and data["differences"][0]["difference_cents"] == -500
        assert (await wanda.post(f"{base}/submit")).status_code == 409
        await wanda.post(f"{base}/explanations", json={"kind": "cash", "note": "Un billete de $5 quedó en la caja de la ofrenda; se agrega el domingo"})

        # Zelle recibidos: a mano (Tesorería) y por CSV (sin repetir); cada transacción con UN solo aporte.
        tx = await tesorera.post("/api/finance/zelle", json={"received_date": today, "amount_cents": 10000, "sender_name": f"Donante C {tag}", "confirmation": f"CONF{tag}", "is_test": True})
        assert tx.status_code == 201, tx.text
        tx_id = tx.json()["tx_id"]
        assert (await tesorera.post("/api/finance/zelle", json={"received_date": today, "amount_cents": 10000, "sender_name": "Otro", "confirmation": f"CONF{tag}", "is_test": True})).status_code == 409
        csv_body = f"Date,Description,Amount,Confirmation\n{today[5:7]}/{today[8:10]}/{today[:4]},Donante C {tag},100.00,CONF{tag}\n{today},Otra Persona {tag},25.50,CONF2{tag}\n{today},Pago de luz,-80.00,X\n"
        imported = (await wanda.post("/api/finance/zelle/import-csv?is_test=true", files={"file": ("zelle.csv", csv_body, "text/csv")})).json()
        assert (imported["loaded"], imported["repeated"]) == (1, 1)
        assert (await pastora.post("/api/finance/zelle", json={"received_date": today, "amount_cents": 100, "sender_name": "X", "is_test": True})).status_code == 403
        matched = await wanda.post(f"{base}/items/{zelle_item}/match-zelle", json={"tx_id": tx_id})
        assert matched.status_code == 200, matched.text
        second = (await wanda.post(f"{base}/items", json=item(anonymous=True, method="zelle", amount_cents=10000))).json()["items"][-1]["item_id"]
        assert (await wanda.post(f"{base}/items/{second}/match-zelle", json={"tx_id": tx_id})).status_code == 409  # ya coincide con otro aporte
        voided = await wanda.post(f"{base}/items/{second}/void", json={"reason": "Registrado dos veces"})
        assert voided.status_code == 200 and any(row["item_id"] == second and row["status"] == "voided" for row in voided.json()["items"])  # anulado, no borrado
        await wanda.post(f"{base}/items/{other}/void", json={"reason": "Prueba de anulación"})

        # Quien solo consulta ve montos, no quién dio.
        seen = (await lectora.get(base)).json()["items"]
        assert all(row["person_name"] in ("Anónimo", "Donante reservado") and "person_id" not in row for row in seen)

        sent = await wanda.post(f"{base}/submit")
        assert sent.status_code == 200, sent.text
        body = sent.json()
        assert body["status"] == "registered" and [stage["stage"] for stage in body["timeline"]] == ["opened", "registered"]
        assert body["summary"]["total_cents"] == 17000 and not body["summary"]["pending_explanations"]
        assert (await wanda.post(f"{base}/items", json=item(anonymous=True))).status_code == 409  # ya no se edita en silencio
        assert all(item.get("is_test") for item in await db.finance_collection_items.find({"collection_id": collection_id}).to_list(50))
        listed = (await lectora.get("/api/finance/collections")).json()["items"]
        assert collection_id not in {row["collection_id"] for row in listed}  # las de prueba no salen por defecto
    finally:
        if collection_id:
            await db.finance_collection_items.delete_many({"collection_id": collection_id})
            await db.finance_collections.delete_many({"collection_id": collection_id})
        await db.finance_zelle_received.delete_many({"sender_name": {"$regex": tag}})
        await db.finance_zelle_received.delete_many({"confirmation": {"$regex": tag}})
        await fx.cleanup()
