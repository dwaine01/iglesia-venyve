"""Bienvenida sincronizada: una posición por servicio (registration_id + versión) guardada en la base; mover con
la versión vigente (la vieja se ignora: nunca salta dos nombres); sigue a la misma persona aunque lleguen o se quiten
nombres; boleto de un solo uso para el WebSocket (el enlace nunca va en su dirección); respaldo HTTP; el operador
mueve la misma posición. El WebSocket se prueba contra el servidor vivo de pruebas (misma base) en 127.0.0.1:8001."""
import asyncio
import json
import uuid

import pytest
import websockets
from httpx import ASGITransport, AsyncClient

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from tests.test_visitor_registry import link, tablet, visitor

db = server.db
WS = "ws://127.0.0.1:8001/api/visitors/welcome/ws"
LIVE = "http://127.0.0.1:8001"


async def recv_type(ws, kind, timeout=3.0):
    while True:
        data = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if data.get("type") == kind:
            return data


async def setup(fx, tag, count=3):
    pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
    pad = await tablet(pastora)
    code = await link(pastora, "screen")
    # Servicio limpio para la prueba: una fecha propia (no se mezcla con otros registros del día).
    await pastora.put("/api/visitors/welcome/state", json={"today": True, "service_kind": "all"})
    for letter in "abcdefgh"[:count]:
        assert (await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}{letter}", last_name="Sync"))).status_code == 201
    return pastora, pad, code


def mine(view, tag):
    return [item for item in view["names"] if tag in item["name"]]


@pytest.mark.asyncio
async def test_position_versions_follow_person_and_operator_share():
    fx, tag = Fixture(), uuid.uuid4().hex[:6]
    clients = []
    try:
        pastora, pad, code = await setup(fx, tag)
        screen_a = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test", headers={"X-Link-Token": code})
        screen_b = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test", headers={"X-Link-Token": code})
        clients += [pad, screen_a, screen_b]
        view = (await screen_a.get("/api/screen/welcome")).json()
        names = view["names"]
        start = view["position"]
        # Se arranca en el primero de los míos (la lista del día puede traer otros de pruebas anteriores).
        first_mine = next(index for index, item in enumerate(names) if tag in item["name"])
        version = start["version"]
        while (await screen_a.get("/api/screen/welcome/position")).json()["index"] != first_mine:
            current = (await screen_a.get("/api/screen/welcome/position")).json()
            action = "next" if current["index"] < first_mine else "prev"
            version = (await screen_a.post("/api/screen/welcome/position", json={"action": action, "version": current["version"]})).json()["version"]

        # Dos pantallas presionan «Siguiente» con la MISMA versión: solo una cuenta (no salta dos nombres).
        current = (await screen_a.get("/api/screen/welcome/position")).json()
        one = (await screen_a.post("/api/screen/welcome/position", json={"action": "next", "version": current["version"]})).json()
        two = (await screen_b.post("/api/screen/welcome/position", json={"action": "next", "version": current["version"]})).json()
        assert one["moved"] is True and two["moved"] is False and two["stale"] is True
        assert one["index"] == two["index"] == current["index"] + 1 and one["version"] == current["version"] + 1
        assert one["registration_id"] == names[first_mine + 1]["id"]

        # Guardada en la base (sobrevive un reinicio): registration_id + versión, no solo un índice.
        stored = await db.visitor_welcome_positions.find_one({"registration_id": one["registration_id"]})
        assert stored and stored["version"] == one["version"]

        # Llega un visitante nuevo: todas siguen en la MISMA persona.
        assert (await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}z", last_name="Sync"))).status_code == 201
        after_new = (await screen_b.get("/api/screen/welcome")).json()["position"]
        assert after_new["registration_id"] == one["registration_id"] and after_new["version"] == one["version"]

        # El operador quita a la persona mostrada: todas pasan a la siguiente (la misma regla en todas).
        await pastora.post(f"/api/visitors/welcome/items/{one['registration_id']}", json={"hidden": True})
        after_hide = (await screen_a.get("/api/screen/welcome/position")).json()
        assert after_hide["registration_id"] == names[first_mine + 2]["id"]
        # Corregir un nombre no mueve la posición.
        await pastora.post(f"/api/visitors/welcome/items/{after_hide['registration_id']}", json={"display_name": f"Corregido{tag}"})
        assert (await screen_b.get("/api/screen/welcome/position")).json()["registration_id"] == after_hide["registration_id"]

        # El panel del operador muestra y mueve la MISMA posición.
        panel = (await pastora.get("/api/visitors/welcome")).json()
        assert panel["position"]["registration_id"] == after_hide["registration_id"]
        back = (await pastora.post("/api/visitors/welcome/position", json={"action": "prev", "version": panel["position"]["version"]})).json()
        assert back["moved"] is True and (await screen_a.get("/api/screen/welcome/position")).json()["registration_id"] == back["registration_id"]
        assert back["registration_id"] == names[first_mine]["id"]  # el escondido se salta

        # Permisos: sin enlace o con uno equivocado, nada; un mentor sin permiso de bienvenida, 403.
        anonymous = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
        clients.append(anonymous)
        assert (await anonymous.post("/api/screen/welcome/position", json={"action": "next", "version": back["version"]})).status_code == 401
        assert (await anonymous.post("/api/screen/welcome/ticket")).status_code == 401
        mentor = await fx.account(await fx.person(f"Mentor{tag}"), "persona")
        assert (await mentor.post("/api/visitors/welcome/position", json={"action": "next", "version": back["version"]})).status_code == 403
        assert (await mentor.post("/api/visitors/welcome/ticket")).status_code == 403
    finally:
        for client in clients:
            await client.aclose()
        await db.visitor_registrations.delete_many({"first_name": {"$regex": tag}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_websocket_two_screens_and_operator_in_real_time():
    fx, tag = Fixture(), uuid.uuid4().hex[:6]
    clients = []
    try:
        pastora, pad, code = await setup(fx, tag, count=2)
        live = AsyncClient(base_url=LIVE, headers={"X-Link-Token": code}, timeout=10)
        clients += [pad, live]

        async def screen_ticket():
            response = await live.post("/api/screen/welcome/ticket")
            assert response.status_code == 200, response.text
            return response.json()["ticket"]

        ticket = await screen_ticket()
        assert code not in f"{WS}?ticket={ticket}"  # el enlace nunca va en la dirección del WebSocket
        async with websockets.connect(f"{WS}?ticket={ticket}") as ws_a, websockets.connect(f"{WS}?ticket={await screen_ticket()}") as ws_b:
            start_a, start_b = await recv_type(ws_a, "position"), await recv_type(ws_b, "position")  # al conectar: el estado actual
            assert start_a == start_b
            # A presiona «Siguiente»: B lo recibe al instante.
            await ws_a.send(json.dumps({"type": "move", "action": "next", "version": start_a["version"]}))
            moved_b = await recv_type(ws_b, "position")
            moved_a = await recv_type(ws_a, "position")
            assert moved_a == moved_b and moved_b["version"] == start_a["version"] + 1
            # Dos a la vez con la misma versión: solo una avanza; nadie salta dos.
            await ws_a.send(json.dumps({"type": "move", "action": "next", "version": moved_b["version"]}))
            await ws_b.send(json.dumps({"type": "move", "action": "next", "version": moved_b["version"]}))
            seen = []
            for ws in (ws_a, ws_b):
                while True:
                    try:
                        seen.append(await recv_type(ws, "position", timeout=1.0))
                    except asyncio.TimeoutError:
                        break
            assert seen and {item["version"] for item in seen} <= {moved_b["version"], moved_b["version"] + 1}  # nunca +2
            assert {item["index"] for item in seen} <= {moved_b["index"], min(moved_b["index"] + 1, moved_b["total"] - 1)}
            final = (await live.get("/api/screen/welcome/position")).json()
            assert final["version"] == moved_b["version"] + 1 and final["index"] == min(moved_b["index"] + 1, final["total"] - 1)
            # Respaldo HTTP (otra pantalla sin WebSocket): las conectadas también lo reciben.
            await live.post("/api/screen/welcome/position", json={"action": "prev", "version": final["version"]})
            assert (await recv_type(ws_a, "position"))["version"] == final["version"] + 1
            # «sync» al reconectar o cuando la pantalla lo pida.
            await ws_b.send(json.dumps({"type": "sync"}))
            assert (await recv_type(ws_b, "position"))["version"] == final["version"] + 1
            # El operador entra con su propio boleto y mueve la misma posición.
            operator_ticket = (await pastora.post("/api/visitors/welcome/ticket")).json()["ticket"]
            async with websockets.connect(f"{WS}?ticket={operator_ticket}") as ws_op:
                state = await recv_type(ws_op, "position")
                await ws_op.send(json.dumps({"type": "move", "action": "first", "version": state["version"]}))
                assert (await recv_type(ws_a, "position"))["index"] == 0
        # Boleto de un solo uso: el mismo boleto no abre otra vez; uno inventado tampoco.
        async with websockets.connect(f"{WS}?ticket={ticket}") as ws:
            assert (await recv_type(ws, "error"))["status"] == 401
        async with websockets.connect(f"{WS}?ticket=inventado") as ws:
            assert (await recv_type(ws, "error"))["status"] == 401
        # Enlace nuevo: un boleto sacado con el enlace anterior ya no sirve.
        stale_ticket = await screen_ticket()
        rotated = await pastora.post("/api/visitors/links/screen/rotate")
        assert rotated.status_code == 200, rotated.text
        async with websockets.connect(f"{WS}?ticket={stale_ticket}") as ws:
            assert (await recv_type(ws, "error"))["status"] == 401
    finally:
        for client in clients:
            await client.aclose()
        await db.visitor_registrations.delete_many({"first_name": {"$regex": tag}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_stage_screen_reads_only_the_shown_name_and_cannot_move():
    fx, tag = Fixture(), uuid.uuid4().hex[:6]
    clients = []
    try:
        pastora, pad, code = await setup(fx, tag, count=0)
        stage_code = await link(pastora, "stage")
        assert stage_code != code  # enlace aparte del de la pastora
        # Un visitante invitado por alguien (el «invitado por» nunca sale en la gigante).
        assert (await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}a", last_name="Gomez", invited=True, invited_by="Hermana Rosa"))).status_code == 201
        assert (await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}b", last_name="Perez"))).status_code == 201
        stage = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test", headers={"X-Link-Token": stage_code})
        screen = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test", headers={"X-Link-Token": code})
        clients += [pad, stage, screen]
        # Llevar la posición a mi primer visitante.
        names = (await screen.get("/api/screen/welcome")).json()["names"]
        target = next(index for index, item in enumerate(names) if tag in item["name"])
        while True:
            position = (await screen.get("/api/screen/welcome/position")).json()
            if position["index"] == target:
                break
            await screen.post("/api/screen/welcome/position", json={"action": "next" if position["index"] < target else "prev", "version": position["version"]})

        view = (await stage.get("/api/stage/welcome")).json()
        assert set(view) == {"shown", "version"} and set(view["shown"]) == {"id", "name"}  # lista blanca: solo el nombre
        assert view["shown"]["name"] == f"Visit{tag}a Gomez" and "Rosa" not in str(view)
        # Solo LEE: no puede mover (ni por la ruta de la pastora ni pedir su boleto); la de la pastora no lee la gigante.
        assert (await stage.post("/api/screen/welcome/position", json={"action": "next", "version": position["version"]})).status_code == 401
        assert (await stage.post("/api/screen/welcome/ticket")).status_code == 401
        assert (await screen.get("/api/stage/welcome")).status_code == 401
        assert (await stage.post("/api/stage/welcome/ticket")).status_code == 200
        # Si el operador quita a quien se muestra, en la gigante no sale (pasa al siguiente).
        shown_id = view["shown"]["id"]
        await pastora.post(f"/api/visitors/welcome/items/{shown_id}", json={"hidden": True})
        after = (await stage.get("/api/stage/welcome")).json()
        assert after["shown"] is None or after["shown"]["id"] != shown_id
        # Mientras alguien aún se registra (borrador), en público no sale.
        draft = await db.visitor_registrations.find_one({"first_name": f"Visit{tag}b"})
        await db.visitor_registrations.update_one({"registration_id": draft["registration_id"]}, {"$set": {"status": "draft", "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)}})
        from visitor_welcome_sync import visible_docs
        key, _ = await visible_docs()
        await db.visitor_welcome_positions.update_one({"_id": key}, {"$set": {"registration_id": draft["registration_id"]}})
        assert (await screen.get("/api/screen/welcome/position")).json()["registration_id"] == draft["registration_id"]
        assert (await stage.get("/api/stage/welcome")).json()["shown"] is None
        # Termina de registrarse: ya sale.
        await db.visitor_registrations.update_one({"registration_id": draft["registration_id"]}, {"$set": {"status": "complete"}})
        assert (await stage.get("/api/stage/welcome")).json()["shown"]["name"] == f"Visit{tag}b Perez"
    finally:
        for client in clients:
            await client.aclose()
        await db.visitor_registrations.delete_many({"first_name": {"$regex": tag}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_stage_websocket_ignores_moves_and_new_visitor_notifies_at_once():
    fx, tag = Fixture(), uuid.uuid4().hex[:6]
    clients = []
    try:
        pastora, pad, code = await setup(fx, tag, count=2)
        stage_code = await link(pastora, "stage")
        live_stage = AsyncClient(base_url=LIVE, headers={"X-Link-Token": stage_code}, timeout=10)
        live_tablet = AsyncClient(base_url=LIVE, headers=dict(pad.headers), timeout=10)
        clients += [pad, live_stage, live_tablet]
        ticket = (await live_stage.post("/api/stage/welcome/ticket")).json()["ticket"]
        async with websockets.connect(f"{WS}?ticket={ticket}") as ws:
            start = await recv_type(ws, "position")
            await ws.send(json.dumps({"type": "move", "action": "next", "version": start["version"]}))
            await asyncio.sleep(0.5)
            assert (await live_stage.get("/api/stage/welcome")).json()["version"] == start["version"]  # la gigante no movió nada
            # Llega un visitante nuevo por la tableta: aviso al instante (sin recargar).
            assert (await live_tablet.post("/api/kiosk/registrations", json=visitor(f"{tag}z", last_name="Nuevo"))).status_code == 201
            assert (await recv_type(ws, "names_changed"))["type"] == "names_changed"
    finally:
        for client in clients:
            await client.aclose()
        await db.visitor_registrations.delete_many({"first_name": {"$regex": tag}})
        await fx.cleanup()
