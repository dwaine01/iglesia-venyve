"""Visitantes V3: pantallas de bienvenida. LISTA BLANCA (falla si se filtra
cualquier otro dato), solo nombres autorizados por pantalla, quitar sin borrar,
corregir nombre, controles (pausa, adelante, atrás) y separación de dispositivos."""
import uuid

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from tests.test_visitor_registry import tablet, visitor

db = server.db
SCREEN_KEYS = {"device_name", "audience", "mode", "paused", "seconds", "page", "pages", "names", "total", "service_label"}
ITEM_KEYS = {"registration_id", "visitor_number", "name", "default_name", "corrected", "hidden", "service_label", "authorized"}


async def screen(pastora, name, kind) -> AsyncClient:
    created = (await pastora.post("/api/visitors/devices", json={"name": name, "kind": kind})).json()
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    paired = (await client.post("/api/kiosk/pair", json={"code": created["pairing_code"]})).json()
    assert paired["kind"] == kind
    client.headers.update({"X-Device-Token": paired["token"]})
    return client


@pytest.mark.asyncio
async def test_welcome_screens_whitelist_consents_controls_and_separation():
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    clients = []
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        mentor = await fx.account(await fx.person(f"Mentor{tag}"), "persona")
        pad = await tablet(pastora, f"Tableta {tag}")
        tv = await screen(pastora, f"TV {tag}", "screen_tv")
        pulpit = await screen(pastora, f"Pastora {tag}", "screen_pastora")
        clients += [pad, tv, pulpit]
        secret = dict(phone="5550409999", city="Ciudad Secreta", address="Calle Secreta 1", birth_date="1990-01-02", prayer_request="OracionSecreta", counseling_note="ConsejeriaSecreta",
                      requests=["prayer", "counseling_marriage"], email=f"secreto{tag}@example.com")
        both = visitor(f"{tag}a", last_name="Uno", preferred_name=f"Toño{tag}", consent_screens=True, consent_announce=True, consent_family_announce=True,
                       family=[{"name": f"Hija{tag}", "relation": "Hijo o hija", "is_minor": True}], **secret)
        tv_only = visitor(f"{tag}b", last_name="Dos", consent_screens=True, phone="5550408888")
        announce_only = visitor(f"{tag}c", last_name="Tres", consent_announce=True, phone="5550407777")
        nobody = visitor(f"{tag}d", last_name="Cuatro", phone="5550406666")
        for payload in (both, tv_only, announce_only, nobody):
            assert (await pad.post("/api/kiosk/registrations", json=payload)).status_code == 201
        await pastora.put("/api/visitors/welcome/state", json={"audience": "tv", "mode": "list", "today": True, "service_kind": "all"})
        await pastora.put("/api/visitors/welcome/state", json={"audience": "pastora", "mode": "list", "today": True, "service_kind": "all"})

        # Lista blanca: la pantalla recibe exactamente estas claves y los nombres son texto.
        tv_view = (await tv.get("/api/screen/welcome")).json()
        assert set(tv_view) == SCREEN_KEYS and all(isinstance(name, str) for name in tv_view["names"])
        dump = str(tv_view) + str((await pulpit.get("/api/screen/welcome")).json())
        for leaked in ("5550409999", "Secreta", "1990", "OracionSecreta", "ConsejeriaSecreta", "secreto", "Consejería", "V-20"):
            assert leaked not in dump, leaked
        tv_names = [name for name in tv_view["names"] if tag in name]
        # Salón: solo quien autorizó pantallas; nunca la familia.
        assert any(f"Toño{tag} Uno" == name for name in tv_names) and any(f"Visit{tag}b Dos" == name for name in tv_names)
        assert not any(f"{tag}c" in name or f"{tag}d" in name or f"Hija{tag}" in name for name in tv_names)
        # Pastora: solo quien autorizó anunciar; la familia solo con su autorización.
        pulpit_names = [name for name in (await pulpit.get("/api/screen/welcome")).json()["names"] if tag in name]
        assert f"Toño{tag} Uno y su familia: Hija{tag}" in pulpit_names and any(f"Visit{tag}c Tres" == name for name in pulpit_names)
        assert not any(f"{tag}b" in name or f"{tag}d" in name for name in pulpit_names)

        # Panel del operador: también lista blanca; el mentor no tiene acceso.
        assert (await mentor.get("/api/visitors/welcome")).status_code == 403
        panel = (await pastora.get("/api/visitors/welcome", params={"audience": "tv"})).json()
        mine = [item for item in panel["items"] if tag in item["name"]]
        assert mine and all(set(item) == ITEM_KEYS for item in mine) and "5550409999" not in str(panel) and "Secreta" not in str(panel)
        target = next(item for item in mine if item["name"] == f"Visit{tag}b Dos")

        # Corregir el nombre y quitarlo de la pantalla SIN borrar el registro.
        fixed = (await pastora.post(f"/api/visitors/welcome/items/{target['registration_id']}", json={"display_name": f"Bety{tag}  Dos"})).json()
        assert fixed["tv"]["name"] == f"Bety{tag} Dos" and fixed["tv"]["corrected"] is True
        assert f"Bety{tag} Dos" in (await tv.get("/api/screen/welcome")).json()["names"]
        await pastora.post(f"/api/visitors/welcome/items/{target['registration_id']}", json={"hidden": True})
        assert not any(f"Bety{tag}" in name for name in (await tv.get("/api/screen/welcome")).json()["names"])
        assert await db.visitor_registrations.count_documents({"registration_id": target["registration_id"]}) == 1
        assert await db.visitor_audit.count_documents({"action": "welcome_item_changed", "detail.registration_id": target["registration_id"]}) == 2
        await pastora.post(f"/api/visitors/welcome/items/{target['registration_id']}", json={"hidden": False, "reset_name": True})

        # Uno por uno: pausa, adelante y atrás; la pantalla muestra lo mismo que el operador.
        one = (await pastora.put("/api/visitors/welcome/state", json={"audience": "tv", "mode": "one"})).json()
        assert len(one["names"]) == 1 and one["pages"] == one["total"]
        paused = (await pastora.post("/api/visitors/welcome/control", json={"audience": "tv", "action": "pause"})).json()
        forward = (await pastora.post("/api/visitors/welcome/control", json={"audience": "tv", "action": "next"})).json()
        assert forward["paused"] is True and forward["page"] == (paused["page"] + 1) % paused["pages"]
        back = (await pastora.post("/api/visitors/welcome/control", json={"audience": "tv", "action": "prev"})).json()
        assert back["page"] == paused["page"] and (await tv.get("/api/screen/welcome")).json()["names"] == back["names"]
        await pastora.post("/api/visitors/welcome/control", json={"audience": "tv", "action": "play"})

        # Un código de pantalla abierto en el quiosco no se gasta.
        spare = (await pastora.post("/api/visitors/devices", json={"name": f"TV2 {tag}", "kind": "screen_tv"})).json()
        anon = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
        clients.append(anon)
        assert (await anon.post("/api/kiosk/pair", json={"code": spare["pairing_code"], "expected_kinds": ["tablet"]})).status_code == 409
        assert (await anon.post("/api/kiosk/pair", json={"code": spare["pairing_code"], "expected_kinds": ["screen_tv", "screen_pastora"]})).status_code == 200
        # Separación: la tableta no lee nombres; la pantalla no registra ni lee configuración.
        assert (await pad.get("/api/screen/welcome")).status_code == 403
        assert (await tv.post("/api/kiosk/registrations", json=visitor(f"{tag}x"))).status_code == 403
        assert (await tv.get("/api/kiosk/config")).status_code == 403
        assert (await tv.get("/api/visitors/welcome")).status_code in (401, 403)
    finally:
        ids = [doc["registration_id"] async for doc in db.visitor_registrations.find({"name_key": {"$regex": tag}}, {"registration_id": 1})]
        persons = [doc["person_id"] async for doc in db.visitor_registrations.find({"name_key": {"$regex": tag}, "person_id": {"$ne": None}}, {"person_id": 1})]
        await db.visitor_registrations.delete_many({"registration_id": {"$in": ids}})
        await db.visitor_restricted.delete_many({"registration_id": {"$in": ids}})
        await db.visitor_locks.delete_many({"_id": {"$regex": tag}})
        await db.persons.delete_many({"_id": {"$in": [ObjectId(pid) for pid in set(persons) if ObjectId.is_valid(pid)]}})
        await db.person_contacts.delete_many({"person_id": {"$in": list(set(persons))}})
        await db.visitor_devices.delete_many({"name": {"$regex": tag}})
        await db.app_settings.delete_many({"_id": {"$in": ["visitor_welcome_state_tv", "visitor_welcome_state_pastora"]}})
        for client in clients:
            await client.aclose()
        await fx.cleanup()
