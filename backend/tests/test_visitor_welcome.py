"""Visitantes: pantalla de bienvenida por ENLACE único. LISTA BLANCA (falla si se
filtra cualquier otro dato), todo registrado entra a la lista, sin familiares ni
menores, quitar sin borrar, corregir nombre y enlaces separados."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from tests.test_visitor_registry import cleanup, link, tablet, visitor

db = server.db
SCREEN_KEYS = {"names", "total", "service_label"}
ITEM_KEYS = {"registration_id", "visitor_number", "name", "default_name", "corrected", "hidden", "service_label"}


@pytest.mark.asyncio
async def test_welcome_link_whitelist_everyone_listed_hide_and_correct():
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    clients = []
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        mentor = await fx.account(await fx.person(f"Mentor{tag}"), "persona")
        pad = await tablet(pastora)
        tv = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test", headers={"X-Link-Token": await link(pastora, "screen")})
        clients += [pad, tv]
        await pastora.put("/api/visitors/welcome/state", json={"today": True, "service_kind": "all"})
        secret = dict(phone="5550409999", city="Ciudad Secreta", address="Calle Secreta 1", birth_date="1990-01-02", prayer_request="OracionSecreta", counseling_note="ConsejeriaSecreta",
                      requests=["prayer", "counseling_marriage"], email=f"secreto{tag}@example.com", family=[{"name": f"Hija{tag}", "relation": "Hijo o hija", "is_minor": True}])
        first = visitor(f"{tag}a", last_name="Uno Ramos", preferred_name=f"Toño{tag}", **secret)
        second = visitor(f"{tag}b", last_name="Dos", phone="5550408888", consent_followup=False)
        for payload in (first, second):
            assert (await pad.post("/api/kiosk/registrations", json=payload)).status_code == 201

        # Lista blanca: la pantalla recibe exactamente estas claves; cada nombre solo {id, name}.
        view = (await tv.get("/api/screen/welcome")).json()
        assert set(view) == SCREEN_KEYS and all(set(item) == {"id", "name"} for item in view["names"])
        for leaked in ("5550409999", "Secreta", "1990", "OracionSecreta", "ConsejeriaSecreta", "secreto", "Consejería", "V-20", f"Hija{tag}"):
            assert leaked not in str(view), leaked
        mine = [item for item in view["names"] if tag in item["name"]]
        # Todo registrado entra (sin preguntar), en orden de llegada; nunca los familiares ni menores.
        assert [item["name"] for item in mine] == [f"Toño{tag} Uno", f"Visit{tag}b Dos"]

        # Panel del operador: también lista blanca; el mentor no tiene acceso.
        assert (await mentor.get("/api/visitors/welcome")).status_code == 403
        panel = (await pastora.get("/api/visitors/welcome")).json()
        items = [item for item in panel["items"] if tag in item["name"]]
        assert items and all(set(item) == ITEM_KEYS for item in items) and "5550409999" not in str(panel) and "Secreta" not in str(panel)
        target = next(item for item in items if item["name"] == f"Visit{tag}b Dos")

        # Corregir el nombre y quitarlo de la bienvenida SIN borrar el registro.
        fixed = (await pastora.post(f"/api/visitors/welcome/items/{target['registration_id']}", json={"display_name": f"Bety{tag}  Dos"})).json()
        assert fixed["name"] == f"Bety{tag} Dos" and fixed["corrected"] is True
        assert f"Bety{tag} Dos" in [item["name"] for item in (await tv.get("/api/screen/welcome")).json()["names"]]
        await pastora.post(f"/api/visitors/welcome/items/{target['registration_id']}", json={"hidden": True})
        assert not any(f"Bety{tag}" in item["name"] for item in (await tv.get("/api/screen/welcome")).json()["names"])
        assert await db.visitor_registrations.count_documents({"registration_id": target["registration_id"]}) == 1
        assert await db.visitor_audit.count_documents({"action": "welcome_item_changed", "detail.registration_id": target["registration_id"]}) == 2
        back = (await pastora.post(f"/api/visitors/welcome/items/{target['registration_id']}", json={"hidden": False, "reset_name": True})).json()
        assert back["name"] == f"Visit{tag}b Dos" and back["hidden"] is False

        # Enlaces separados: el de tabletas no lee nombres y el de pantalla no registra.
        assert (await pad.get("/api/screen/welcome")).status_code == 401
        assert (await tv.post("/api/kiosk/registrations", json=visitor(f"{tag}x"))).status_code == 401
        assert (await tv.get("/api/kiosk/config")).status_code == 401
        assert (await tv.get("/api/visitors/welcome")).status_code in (401, 403)
        # Enlace nuevo de pantalla: el anterior deja de funcionar.
        await pastora.post("/api/visitors/links/screen/rotate")
        assert (await tv.get("/api/screen/welcome")).status_code == 401
    finally:
        await cleanup(tag)
        await db.app_settings.delete_many({"_id": "visitor_welcome_state"})
        for client in clients:
            await client.aclose()
        await fx.cleanup()
