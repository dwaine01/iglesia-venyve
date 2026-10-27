"""Ven y Come · paso 4: una promesa con solo el nombre llega a «Recibido» sin Persona 360 y el dinero NO se
bloquea: entra a la colecta con el nombre tal como lo dieron y la etiqueta «sin Persona 360». Ya no se crea una
persona por el nombre. Después se vincula («Vincular a Persona 360») a una existente o nueva, sin duplicar, y
el aporte de Finanzas queda con esa persona."""
import uuid

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_promise_without_person_received_then_linked():
    from finance_collections import ensure_indexes
    from finance_engine import ensure_indexes_and_seed
    await ensure_indexes_and_seed()
    await ensure_indexes()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    donations, collections = [], set()
    try:
        pastora = await fx.account(await fx.person(f"PastoraV4{tag}"), "pastora")
        encargado = await fx.account(await fx.person(f"EncargadoV4{tag}"), "lider", capabilities=["campaign.venycome.manage"], permissions_mode="manual")
        existing = await fx.person(f"Rosa{tag} Lima")
        from person_matching import normalize_text
        await db.persons.update_one({"_id": ObjectId(existing)}, {"$set": {"nombre": f"Rosa{tag}", "apellido": "Lima", "search_key": normalize_text(f"Rosa{tag} Lima")}})
        persons_before = await db.persons.count_documents({})

        async def promise(name):
            doc = (await encargado.post("/api/campaigns/venycome/donations", json={"donor_name": name, "amount_cents": 3000, "donation_type": "promise", "idempotency_key": str(uuid.uuid4())})).json()
            donations.append(doc["donation_id"])
            return doc["donation_id"]

        first = await promise(f"Rosa{tag} Lima")
        received = await encargado.post(f"/api/campaigns/venycome/donations/{first}/receive", json={"payment_method": "zelle"})
        assert received.status_code == 200, received.text
        body = received.json()
        collections.add(body["finance_collection_id"])
        assert body["finance_person_id"] is None and await db.persons.count_documents({}) == persons_before  # no se crea ni se adivina
        item = await db.finance_collection_items.find_one({"item_id": body["finance_collection_item_id"]})
        assert item["person_id"] is None and item["without_person"] is True and item["donor_name"] == f"Rosa{tag} Lima" and item["anonymous"] is False
        view = (await pastora.get(f"/api/finance/collections/{body['finance_collection_id']}")).json()
        assert next(row for row in view["items"] if row["item_id"] == item["item_id"])["person_name"] == f"Rosa{tag} Lima (sin Persona 360)"

        # Vincular: crear con el mismo nombre que ya existe → pide elegir la existente (no duplica).
        conflict = await encargado.post(f"/api/campaigns/venycome/donations/{first}/link-person", json={"create": True})
        assert conflict.status_code == 409 and existing in {c["person_id"] for c in conflict.json()["detail"]["candidates"]}
        assert (await pastora.post(f"/api/campaigns/venycome/donations/{first}/link-person", json={"person_id": existing})).status_code == 403  # la pastora no
        linked = await encargado.post(f"/api/campaigns/venycome/donations/{first}/link-person", json={"person_id": existing})
        assert linked.status_code == 200 and linked.json()["person_id"] == existing
        item = await db.finance_collection_items.find_one({"item_id": item["item_id"]})
        assert item["person_id"] == existing and item["without_person"] is False and item["history"][-1]["action"] == "person_linked"
        assert await db.persons.count_documents({}) == persons_before

        # Alguien que no existe: «crear» hace una sola Persona 360 (idempotente).
        second = await promise(f"Nuevo{tag} Donante")
        await encargado.post(f"/api/campaigns/venycome/donations/{second}/receive", json={"payment_method": "cash"})
        created = await encargado.post(f"/api/campaigns/venycome/donations/{second}/link-person", json={"create": True})
        assert created.status_code == 200, created.text
        new_person = created.json()["person_id"]
        fx.person_ids.append(new_person)
        assert await db.persons.count_documents({"_id": ObjectId(new_person)}) == 1 and await db.persons.count_documents({}) == persons_before + 1
    finally:
        await db.finance_collection_items.delete_many({"origin.source_id": {"$in": donations}})
        await db.finance_collections.delete_many({"collection_id": {"$in": list(collections)}, "status": "registering", "is_test": True})
        await db.campaign_donations.delete_many({"donation_id": {"$in": donations}})
        await fx.cleanup()
