"""Registro de visitantes: enlace único de tabletas (sin código ni sesión) con
permiso ÚNICO de crear; 4 tabletas a la vez sin mezclar ni
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


async def link(pastora, kind) -> str:
    items = {item["kind"]: item for item in (await pastora.get("/api/visitors/links")).json()["items"]}
    return items[kind]["path"].rsplit("/", 1)[1]


async def tablet(pastora, name=None) -> AsyncClient:
    """Una tableta que abre el enlace único: sin código ni sesión; se nombra sola."""
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    client.headers.update({"X-Link-Token": await link(pastora, "tablet"), "X-Tablet-Name": f"Tableta {uuid.uuid4().hex[:4].upper()}",
                           "X-Forwarded-For": f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"})
    return client


@pytest.mark.asyncio
async def test_kiosk_link_numbers_idempotency_dedupe_and_permissions():
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    tablets = []
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        mentor = await fx.account(await fx.person(f"Mentor{tag}"), "persona")
        assert (await mentor.get("/api/visitors/links")).status_code == 403
        assert (await mentor.get("/api/visitors/registrations")).status_code == 403
        links = (await pastora.get("/api/visitors/links")).json()["items"]
        assert [item["kind"] for item in links] == ["tablet", "screen"] and links[0]["path"].startswith("/quiosco/") and links[1]["path"].startswith("/pantalla-bienvenida/")
        assert len(links[0]["path"].rsplit("/", 1)[1]) >= 40
        tablets = [await tablet(pastora) for _ in range(4)]
        # El enlace de tabletas solo lee textos y crea registros: nada del personal ni nombres.
        config = (await tablets[0].get("/api/kiosk/config")).json()
        assert config["texts"]["welcome"].startswith("¡Bienvenido a Casa de Oración!") and "\n" in config["texts"]["welcome"] and config["service"]["label"]
        # La frase principal llega COMPLETA, exacta y en una sola línea.
        main = "Esperamos que hagas de esta iglesia tu casa y de esta familia tu familia."
        assert main in config["texts"]["welcome"].split("\n")
        assert (await tablets[0].get("/api/visitors/registrations")).status_code in (401, 403)
        assert (await tablets[0].get("/api/screen/welcome")).status_code == 401
        stranger = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
        tablets.append(stranger)
        assert (await stranger.post("/api/kiosk/registrations", json=visitor(tag))).status_code == 401
        stranger.headers.update({"X-Link-Token": "x" * 43})
        assert (await stranger.post("/api/kiosk/registrations", json=visitor(tag))).status_code == 401

        # 4 tabletas a la vez, 3 visitantes cada una: 12 registros, números únicos.
        payloads = [[visitor(f"{tag}{t}{n}", phone=f"(555) 01{t}-{n:04d}") for n in range(3)] for t in range(4)]
        results = await asyncio.gather(*(tablets[t].post("/api/kiosk/registrations", json=payloads[t][n]) for t in range(4) for n in range(3)))
        assert all(item.status_code == 201 for item in results), [item.text for item in results]
        numbers = [item.json()["visitor_number"] for item in results]
        assert len(set(numbers)) == 12 and all(number.startswith("V-") for number in numbers)
        # Cada tableta queda anotada con su nombre automático y no se mezclan los datos.
        for t in range(4):
            for n in range(3):
                doc = await db.visitor_registrations.find_one({"idempotency_key": payloads[t][n]["idempotency_key"]}, {"_id": 0})
                assert doc["first_name"] == payloads[t][n]["first_name"] and doc["device_name"] == tablets[t].headers["X-Tablet-Name"]
        # TODO formulario va al módulo: aparece en Seguimiento y en Persona 360 vinculado, con su número.
        followup = {item["visitor_number"]: item for item in (await pastora.get("/api/visitors/followup")).json()["items"]}
        for number in numbers:
            assert number in followup and followup[number]["person_id"], number
            reg = await db.visitor_registrations.find_one({"visitor_number": number}, {"_id": 0})
            assert await db.persons.find_one({"_id": ObjectId(reg["person_id"])})
        sample = await db.visitor_registrations.find_one({"visitor_number": numbers[0]}, {"_id": 0})
        history = (await pastora.get(f"/api/persons/{sample['person_id']}/contact-origin")).json()["history"]
        assert any(row["kind"] == "visitor_registration" and numbers[0] in row["title"] for row in history)

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

        # Persona 360: nueva → creada; mismo teléfono y nombre otro día → vinculada;
        # mismo teléfono con otro nombre → perfil propio + «confirmar» (nunca queda fuera).
        reg = await db.visitor_registrations.find_one({"visitor_number": numbers[0]}, {"_id": 0})
        assert reg["match_status"] == "created" and reg["person_id"]
        await db.visitor_registrations.update_many({"service.date": reg["service"]["date"], "name_key": {"$regex": tag}}, {"$set": {"service.date": "2001-01-01"}})
        await db.visitor_locks.delete_many({"_id": {"$regex": tag}})
        back = await tablets[0].post("/api/kiosk/registrations", json=visitor(f"{tag}00", phone="(555) 010-0000"))
        back_doc = await db.visitor_registrations.find_one({"visitor_number": back.json()["visitor_number"]}, {"_id": 0})
        assert back_doc["match_status"] == "linked" and back_doc["person_id"] == reg["person_id"]
        other = await tablets[0].post("/api/kiosk/registrations", json=visitor(f"Otra{tag}", last_name="Distinta", phone="(555) 010-0000"))
        other_doc = await db.visitor_registrations.find_one({"visitor_number": other.json()["visitor_number"]}, {"_id": 0})
        assert other_doc["match_status"] == "possible" and other_doc["person_id"] and other_doc["person_id"] != reg["person_id"] and reg["person_id"] in other_doc["possible_person_ids"]

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
        # Seguimiento: solo un «No» explícito lo saca; sin responder queda pendiente.
        silent = await tablets[0].post("/api/kiosk/registrations", json=visitor(f"{tag}sil", consent_followup=None))
        refused = await tablets[0].post("/api/kiosk/registrations", json=visitor(f"{tag}ref", consent_followup=False))
        assert (await db.visitor_registrations.find_one({"visitor_number": silent.json()["visitor_number"]}))["followup"]["status"] == "pending"
        assert (await db.visitor_registrations.find_one({"visitor_number": refused.json()["visitor_number"]}))["followup"]["status"] == "not_requested"
        # Sin aceptar el aviso de privacidad no se guarda.
        assert (await tablets[0].post("/api/kiosk/registrations", json=visitor(f"{tag}np", privacy_accepted=False))).status_code == 422
        # Campo trampa: responde igual pero no guarda nada.
        bot = await tablets[0].post("/api/kiosk/registrations", json=visitor(f"{tag}bot", website="http://spam.example"))
        assert bot.status_code == 201 and await db.visitor_registrations.count_documents({"name_key": {"$regex": f"{tag}bot"}}) == 0
        # Límite de frecuencia por tableta.
        burst = await tablet(pastora)
        tablets.append(burst)
        codes = [(await burst.post("/api/kiosk/registrations", json=visitor(f"{tag}r{n}"))).status_code for n in range(13)]
        assert codes[:12] == [201] * 12 and codes[12] == 429

        # Generar enlace nuevo: el anterior deja de funcionar en el acto.
        old = tablets[0].headers["X-Link-Token"]
        rotated = (await pastora.post("/api/visitors/links/tablet/rotate")).json()
        assert rotated["path"].rsplit("/", 1)[1] != old
        assert (await tablets[0].post("/api/kiosk/registrations", json=visitor(f"{tag}rev"))).status_code == 401
        tablets[0].headers.update({"X-Link-Token": rotated["path"].rsplit("/", 1)[1]})
        assert (await tablets[0].get("/api/kiosk/config")).status_code == 200
        # Textos editables con versión del aviso.
        texts = (await pastora.get("/api/visitors/texts")).json()
        updated = (await pastora.put("/api/visitors/texts", json={"welcome": texts["welcome"], "privacy": texts["privacy"] + " Versión de prueba.", "confirmation": texts["confirmation"]})).json()
        assert updated["privacy_version"] == texts["privacy_version"] + 1
        # Aunque alguien la corte en dos líneas al editar, se guarda entera.
        split = texts["welcome"].replace("tu casa y de esta familia", "tu casa\ny de esta familia")
        saved = (await pastora.put("/api/visitors/texts", json={"welcome": split, "privacy": texts["privacy"], "confirmation": texts["confirmation"]})).json()
        assert main in saved["welcome"].split("\n")
        await pastora.put("/api/visitors/texts", json={"welcome": texts["welcome"], "privacy": texts["privacy"], "confirmation": texts["confirmation"]})
    finally:
        await cleanup(tag)
        for client in tablets:
            await client.aclose()
        await fx.cleanup()


async def cleanup(tag):
    ids = [doc["registration_id"] async for doc in db.visitor_registrations.find({"name_key": {"$regex": tag}}, {"registration_id": 1})]
    persons = [doc["person_id"] async for doc in db.visitor_registrations.find({"name_key": {"$regex": tag}, "person_id": {"$ne": None}}, {"person_id": 1})]
    persons += [str(doc["_id"]) async for doc in db.persons.find({"search_key": {"$regex": tag.lower()}}, {"_id": 1})]
    await db.visitor_registrations.delete_many({"registration_id": {"$in": ids}})
    await db.visitor_restricted.delete_many({"registration_id": {"$in": ids}})
    await db.visitor_locks.delete_many({"_id": {"$regex": tag}})
    await db.persons.delete_many({"_id": {"$in": [ObjectId(pid) for pid in set(persons) if ObjectId.is_valid(pid)]}})
    await db.person_contacts.delete_many({"person_id": {"$in": list(set(persons))}})
