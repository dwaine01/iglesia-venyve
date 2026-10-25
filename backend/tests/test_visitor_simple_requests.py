"""Tabletas Amazon Fire (Silk): la tableta y la pantalla usan pedidos «simples»: el código va
en la dirección (?link=…&tablet=…) y los datos como texto plano. Siguen valiendo los
encabezados de antes. Diagnóstico /api/kiosk/ping sin datos."""
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from tests.test_visitor_registry import cleanup, link, visitor

db = server.db


@pytest.mark.asyncio
async def test_kiosk_and_screen_accept_simple_requests():
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test", headers={"X-Forwarded-For": f"10.55.{uuid.uuid4().int % 250}.1"})
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        code, screen_code = await link(pastora, "tablet"), await link(pastora, "screen")
        assert (await client.get("/api/kiosk/ping")).json() == {"ok": True, "kiosk_api": 4}
        params = {"link": code.lower(), "tablet": "Tableta 5A5A"}
        config = await client.get("/api/kiosk/config", params=params)
        assert config.status_code == 200 and config.json()["device_name"] == "Tableta 5A5A" and config.json()["short_path"] == f"/r/{code}"
        # Datos como texto plano (sin la consulta previa del navegador): borrador y registro final.
        form = visitor(f"{tag}s", phone="5550601234")
        text = {"Content-Type": "text/plain;charset=UTF-8"}
        assert (await client.post("/api/kiosk/registrations/draft", params=params, content=json.dumps(form), headers=text)).json() == {"ok": True}
        final = await client.post("/api/kiosk/registrations", params=params, content=json.dumps(form), headers=text)
        assert final.status_code == 201, final.text
        doc = await db.visitor_registrations.find_one({"visitor_number": final.json()["visitor_number"]}, {"_id": 0})
        assert doc["device_name"] == "Tableta 5A5A" and doc["contact"]["phone"] == "5550601234" and doc["status"] == "complete"
        # Código equivocado en la dirección: 401, como antes.
        assert (await client.get("/api/kiosk/config", params={"link": "ZZZZZZZZ"})).status_code == 401
        # Pantalla de bienvenida con el código en la dirección.
        screen = await client.get("/api/screen/welcome", params={"link": screen_code})
        assert screen.status_code == 200 and any(item["id"] == doc["registration_id"] for item in screen.json()["names"])
        # Los encabezados de antes siguen funcionando.
        assert (await client.get("/api/kiosk/config", headers={"X-Link-Token": code, "X-Tablet-Name": "Tableta 6B6B"})).json()["device_name"] == "Tableta 6B6B"
    finally:
        await cleanup(tag)
        await client.aclose()
        await fx.cleanup()
