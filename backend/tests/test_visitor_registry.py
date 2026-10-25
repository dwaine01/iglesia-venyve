"""Registro de visitantes V1: tabletas emparejadas con código de un solo uso y
token con permiso ÚNICO de crear; 4 tabletas a la vez sin mezclar ni
duplicar; doble envío y reintento (idempotencia); misma persona en dos tabletas
al mismo tiempo = un registro; número atómico; Persona 360 (nueva, vinculada,
posible coincidencia a revisión humana); datos restringidos aparte; permisos."""
import asyncio
import uuid

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


def visitor(tag, **extra):
    return {"idempotency_key": f"vk-{uuid.uuid4().hex}", "first_name": f"Visit{tag}", "last_name": "Prueba", "privacy_version": 1, "privacy_accepted": True,
            "consent_followup": True, **extra}


async def tablet(pastora, name) -> AsyncClient:
    created = (await pastora.post("/api/visitors/devices", json={"name": name})).json()
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    paired = await client.post("/api/kiosk/pair", json={"code": created["pairing_code"]})
    assert paired.status_code == 200, paired.text
    client.headers.update({"X-Device-Token": paired.json()["token"]})
    client.device_id = created["device_id"]
    client.code = created["pairing_code"]
    return client


@pytest.mark.asyncio
async def test_kiosk_tablets_numbers_idempotency_dedupe_and_permissions():
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    tablets = []
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        mentor = await fx.account(await fx.person(f"Mentor{tag}"), "persona")
        assert (await mentor.post("/api/visitors/devices", json={"name": "Tableta X"})).status_code == 403
        assert (await mentor.get("/api/visitors/registrations")).status_code == 403
        tablets = [await tablet(pastora, f"Tableta {index} {tag}") for index in range(1, 5)]
        # El código es de un solo uso.
        again = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
        assert (await again.post("/api/kiosk/pair", json={"code": tablets[0].code})).status_code == 404
        # La tableta solo lee su configuración; no puede leer registros ni nada del personal.
        config = (await tablets[0].get("/api/kiosk/config")).json()
        assert config["texts"]["welcome"].startswith("¡Bienvenido a Casa de Oración!") and config["service"]["label"]
        assert (await tablets[0].get("/api/visitors/registrations")).status_code in (401, 403)
        assert (await again.post("/api/kiosk/registrations", json=visitor(tag))).status_code == 401

        # 4 tabletas a la vez, 3 visitantes cada una: 12 registros, números únicos y consecutivos.
        payloads = [[visitor(f"{tag}{t}{n}", phone=f"(555) 01{t}-{n:04d}") for n in range(3)] for t in range(4)]
        results = await asyncio.gather(*(tablets[t].post("/api/kiosk/registrations", json=payloads[t][n]) for t in range(4) for n in range(3)))
        assert all(item.status_code == 201 for item in results), [item.text for item in results]
        numbers = [item.json()["visitor_number"] for item in results]
        assert len(set(numbers)) == 12 and all(number.startswith("V-") for number in numbers)
        # Doble toque (mismo envío dos veces a la vez) y reintento sin internet: un solo registro.
        twice = visitor(f"{tag}dbl", phone="5550109999")
        first, second = await asyncio.gather(tablets[1].post("/api/kiosk/registrations", json=twice), tablets[1].post("/api/kiosk/registrations", json=twice))
        assert first.json()["visitor_number"] == second.json()["visitor_number"]
        retry = await tablets[1].post("/api/kiosk/registrations", json=twice)
        assert retry.json()["visitor_number"] == first.json()["visitor_number"] and retry.json()["duplicate"] is True
        assert await db.visitor_registrations.count_documents({"idempotency_key": twice["idempotency_key"]}) == 1
        # La misma persona en dos tabletas al mismo tiempo (claves distintas): un registro.
        same_a, same_b = visitor(f"{tag}twin", phone="555-777-1212"), visitor(f"{tag}twin", phone="5557771212")
        a, b = await asyncio.gather(tablets[2].post("/api/kiosk/registrations", json=same_a), tablets[3].post("/api/kiosk/registrations", json=same_b))
        assert a.json()["visitor_number"] == b.json()["visitor_number"]
        assert await db.visitor_registrations.count_documents({"name_key": {"$regex": f"visit{tag}twin"}}) == 1

        # Persona 360: nueva → creada; mismo teléfono y nombre otro día → vinculada; mismo teléfono con otro nombre → posible coincidencia.
        reg = await db.visitor_registrations.find_one({"visitor_number": numbers[0]}, {"_id": 0})
        assert reg["match_status"] == "created" and reg["person_id"] and await db.persons.find_one({"_id": ObjectId(reg["person_id"])})
        await db.visitor_registrations.update_many({"service.date": reg["service"]["date"], "name_key": {"$regex": tag}}, {"$set": {"service.date": "2001-01-01"}})
        await db.visitor_locks.delete_many({"_id": {"$regex": tag}})
        back = await tablets[0].post("/api/kiosk/registrations", json=visitor(f"{tag}00", phone="(555) 010-0000"))
        back_doc = await db.visitor_registrations.find_one({"visitor_number": back.json()["visitor_number"]}, {"_id": 0})
        assert back_doc["match_status"] == "linked" and back_doc["person_id"] == reg["person_id"]
        other = await tablets[0].post("/api/kiosk/registrations", json=visitor(f"Otra{tag}", last_name="Distinta", phone="(555) 010-0000"))
        other_doc = await db.visitor_registrations.find_one({"visitor_number": other.json()["visitor_number"]}, {"_id": 0})
        assert other_doc["match_status"] == "possible" and other_doc["person_id"] is None and reg["person_id"] in other_doc["possible_person_ids"]

        # Datos restringidos aparte; la tableta solo recibe número, nombre para saludar y mensaje.
        private = await tablets[0].post("/api/kiosk/registrations", json=visitor(f"{tag}priv", preferred_name="Toñito", prayer_request="Por mi salud", counseling_note="Matrimonial",
                                                                                  requests=["prayer", "counseling_marriage"], family=[{"name": "Hijo", "relation": "hijo", "is_minor": True}]))
        assert set(private.json()) == {"visitor_number", "greeting_name", "confirmation", "duplicate"} and private.json()["greeting_name"] == "Toñito"
        private_doc = await db.visitor_registrations.find_one({"visitor_number": private.json()["visitor_number"]}, {"_id": 0})
        assert "Por mi salud" not in str(private_doc) and private_doc["has_restricted"] is True
        assert (await db.visitor_restricted.find_one({"registration_id": private_doc["registration_id"]}))["prayer_request"] == "Por mi salud"
        staff = (await pastora.get(f"/api/visitors/registrations/{private_doc['registration_id']}")).json()
        assert staff["restricted"]["prayer_request"] == "Por mi salud"
        reader = await fx.account(await fx.person(f"Lector{tag}"), "persona", capabilities=["visitors.read"], permissions_mode="manual")
        limited = (await reader.get(f"/api/visitors/registrations/{private_doc['registration_id']}")).json()
        assert "restricted" not in limited and limited["contact"] is not None
        assert await db.visitor_audit.count_documents({"action": "restricted_viewed", "detail.registration_id": private_doc["registration_id"]}) == 1
        # Sin aceptar el aviso de privacidad no se guarda.
        assert (await tablets[0].post("/api/kiosk/registrations", json=visitor(f"{tag}np", privacy_accepted=False))).status_code == 422

        # Desactivar una tableta la bloquea en el acto.
        assert (await pastora.post(f"/api/visitors/devices/{tablets[3].device_id}/revoke")).status_code == 200
        assert (await tablets[3].post("/api/kiosk/registrations", json=visitor(f"{tag}rev"))).status_code == 401
        # Textos editables con versión del aviso.
        texts = (await pastora.get("/api/visitors/texts")).json()
        updated = (await pastora.put("/api/visitors/texts", json={"welcome": texts["welcome"], "privacy": texts["privacy"] + " Versión de prueba.", "confirmation": texts["confirmation"]})).json()
        assert updated["privacy_version"] == texts["privacy_version"] + 1
        await pastora.put("/api/visitors/texts", json={"welcome": texts["welcome"], "privacy": texts["privacy"], "confirmation": texts["confirmation"]})
    finally:
        ids = [doc["registration_id"] async for doc in db.visitor_registrations.find({"name_key": {"$regex": tag}}, {"registration_id": 1})]
        persons = [doc["person_id"] async for doc in db.visitor_registrations.find({"name_key": {"$regex": tag}, "person_id": {"$ne": None}}, {"person_id": 1})]
        await db.visitor_registrations.delete_many({"registration_id": {"$in": ids}})
        await db.visitor_restricted.delete_many({"registration_id": {"$in": ids}})
        await db.visitor_locks.delete_many({"_id": {"$regex": tag}})
        await db.persons.delete_many({"_id": {"$in": [ObjectId(pid) for pid in set(persons) if ObjectId.is_valid(pid)]}})
        await db.person_contacts.delete_many({"person_id": {"$in": list(set(persons))}})
        await db.visitor_devices.delete_many({"name": {"$regex": tag}})
        for client in tablets:
            await client.aclose()
        await fx.cleanup()
