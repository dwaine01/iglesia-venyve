"""Radio R1 (opción C): canal por invasión sobre WebSocket. Permisos, turno de
habla (uno a la vez), solo el que tiene el turno transmite, registro de quién
habló (sin guardar el audio en vivo), mensajes de voz (GridFS, idempotentes)
y borrado automático a los 30 días. El WebSocket se prueba contra el servidor
vivo de pruebas (misma base) en 127.0.0.1:8001."""
import asyncio
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import websockets

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from radio import purge_expired_voice_messages

db = server.db
WS = "ws://127.0.0.1:8001/api/radio/ws"


def token_of(client) -> str:
    return client.headers["Authorization"].split(" ", 1)[1]


async def recv_until(ws, kind, timeout=3.0):
    while True:
        message = await asyncio.wait_for(ws.recv(), timeout)
        if isinstance(message, bytes):
            if kind == "bytes":
                return message
            continue
        data = json.loads(message)
        if data.get("type") == kind:
            return data


@pytest.mark.asyncio
async def test_radio_channel_floor_audio_log_voice_messages_and_purge():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_ids = []
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, collab_id, outsider_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Colab", "Ajeno")]
        ana = await fx.account(ana_id, "persona")
        collab = await fx.account(collab_id, "persona")
        outsider = await fx.account(outsider_id, "persona")
        await db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": ana_id, "active": True})
        today = date.today()
        for name, start in (("Hoy", today), ("Futura", today + timedelta(days=5))):
            created = await pastora.post("/api/invasions", json={"name": f"{name} {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": start.isoformat(),
                                                                  "mentor_person_ids": [ana_id], "collaborator_person_ids": [collab_id]})
            campaign_ids.append(created.json()["campaign_id"])
        active_id, future_id = campaign_ids

        # Permisos: ajeno 403; participante de una invasión futura 409.
        async with websockets.connect(f"{WS}/{active_id}?token={token_of(outsider)}") as ws:
            assert (await recv_until(ws, "error"))["status"] == 403
        async with websockets.connect(f"{WS}/{future_id}?token={token_of(ana)}") as ws:
            assert (await recv_until(ws, "error"))["status"] == 409
        async with websockets.connect(f"{WS}/{active_id}?token=malo") as ws:
            assert (await recv_until(ws, "error"))["status"] == 401

        async with websockets.connect(f"{WS}/{active_id}?token={token_of(ana)}") as ws_ana, websockets.connect(f"{WS}/{active_id}?token={token_of(collab)}") as ws_col:
            assert (await recv_until(ws_ana, "welcome"))["sample_rate"] == 16000
            await recv_until(ws_col, "welcome")
            presence = await recv_until(ws_ana, "presence")
            while presence["count"] < 2:
                presence = await recv_until(ws_ana, "presence")
            # Turno: Ana habla; Colab recibe "speaking" y no puede tomar el turno.
            await ws_ana.send(json.dumps({"type": "ptt_start"}))
            assert (await recv_until(ws_ana, "talk_granted"))["max_seconds"] == 60
            assert (await recv_until(ws_col, "speaking"))["name"].startswith("Ana")
            await ws_col.send(json.dumps({"type": "ptt_start"}))
            assert (await recv_until(ws_col, "busy"))["speaker"].startswith("Ana")
            # Solo el que tiene el turno transmite.
            chunk = bytes(range(256)) * 5
            await ws_ana.send(chunk)
            assert await recv_until(ws_col, "bytes") == chunk
            await ws_col.send(b"\x00" * 640)
            with pytest.raises(asyncio.TimeoutError):
                await recv_until(ws_ana, "bytes", timeout=0.8)
            # Oyente con audio bloqueado/silenciado: sabe quién habla pero no recibe audio (ahorra datos).
            await ws_col.send(json.dumps({"type": "listen", "on": False}))
            await asyncio.sleep(0.2)
            await ws_ana.send(chunk)
            with pytest.raises(asyncio.TimeoutError):
                await recv_until(ws_col, "bytes", timeout=0.8)
            await ws_col.send(json.dumps({"type": "listen", "on": True}))
            await asyncio.sleep(0.2)
            await ws_ana.send(chunk)
            assert await recv_until(ws_col, "bytes") == chunk
            await ws_ana.send(json.dumps({"type": "ptt_end"}))
            assert (await recv_until(ws_col, "stopped"))["name"].startswith("Ana")
            # Ahora Colab sí puede hablar.
            await ws_col.send(json.dumps({"type": "ptt_start"}))
            await recv_until(ws_col, "talk_granted")
            await ws_col.send(json.dumps({"type": "ptt_end"}))
            await asyncio.sleep(0.3)

        # Misma cuenta en dos pestañas: cuenta como una persona y su voz no vuelve a su otra pestaña (eco).
        async with websockets.connect(f"{WS}/{active_id}?token={token_of(ana)}") as tab1, websockets.connect(f"{WS}/{active_id}?token={token_of(ana)}") as tab2, \
                websockets.connect(f"{WS}/{active_id}?token={token_of(collab)}") as other:
            for ws in (tab1, tab2, other):
                await recv_until(ws, "welcome")
            # Tres conexiones (dos de Ana), pero dos personas: se lee la última presencia enviada.
            presence = await recv_until(other, "presence")
            while True:
                try:
                    presence = await recv_until(other, "presence", timeout=0.5)
                except asyncio.TimeoutError:
                    break
            assert presence["count"] == 2
            await tab1.send(json.dumps({"type": "ptt_start"}))
            await recv_until(tab1, "talk_granted")
            await tab1.send(b"\x01" * 640)
            assert await recv_until(other, "bytes") == b"\x01" * 640
            with pytest.raises(asyncio.TimeoutError):
                await recv_until(tab2, "bytes", timeout=0.8)
            # Turno colgado: si deja de llegar audio 6 s, se libera solo.
            assert (await recv_until(tab1, "talk_timeout", timeout=9))["type"] == "talk_timeout"
            assert (await recv_until(other, "stopped", timeout=2))["name"].startswith("Ana")
            await other.send(json.dumps({"type": "ptt_start"}))
            await recv_until(other, "talk_granted")
            await other.send(json.dumps({"type": "ptt_end"}))
            await asyncio.sleep(0.3)

        # Registro de quién habló (sin audio guardado).
        log = await db.radio_talk_log.find({"campaign_id": active_id}).to_list(10)
        assert len(log) == 4 and all("audio" not in item for item in log) and {item["person_id"] for item in log} == {ana_id, collab_id}
        state = (await pastora.get(f"/api/radio/{active_id}")).json()
        assert len(state["talk_log"]) == 4 and state["retention_days"] == 30
        assert (await outsider.get(f"/api/radio/{active_id}")).status_code == 403

        # Mensaje de voz: se guarda (idempotente), se descarga igual, solo audio.
        audio = b"OggS" + bytes(2000)
        key = f"voice-{uuid.uuid4().hex}"
        sent = await ana.post(f"/api/radio/{active_id}/messages", files={"audio": ("m.ogg", audio, "audio/ogg")}, data={"duration_seconds": "4.2", "client_request_id": key})
        assert sent.status_code == 201, sent.text
        message = sent.json()
        again = (await ana.post(f"/api/radio/{active_id}/messages", files={"audio": ("m.ogg", audio, "audio/ogg")}, data={"duration_seconds": "4.2", "client_request_id": key})).json()
        assert again["duplicate"] is True and again["message_id"] == message["message_id"]
        assert (await ana.post(f"/api/radio/{active_id}/messages", files={"audio": ("x.txt", b"hola", "text/plain")}, data={"client_request_id": f"v-{uuid.uuid4().hex}"})).status_code == 415
        assert (await outsider.post(f"/api/radio/{active_id}/messages", files={"audio": ("m.ogg", audio, "audio/ogg")}, data={"client_request_id": f"v-{uuid.uuid4().hex}"})).status_code == 403
        download = await collab.get(f"/api/radio/{active_id}/messages/{message['message_id']}/audio")
        assert download.status_code == 200 and download.content == audio
        assert (await collab.get(f"/api/radio/{active_id}")).json()["voice_messages"][0]["message_id"] == message["message_id"]

        # Borrado automático a los 30 días (documento y archivo).
        doc = await db.radio_voice_messages.find_one({"message_id": message["message_id"]})
        await db.radio_voice_messages.update_one({"_id": doc["_id"]}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}})
        assert await purge_expired_voice_messages() >= 1
        assert await db.radio_voice_messages.count_documents({"message_id": message["message_id"]}) == 0
        assert await db["radio_messages.files"].count_documents({"_id": doc["gridfs_id"]}) == 0
    finally:
        for collection in ("radio_talk_log", "radio_voice_messages", "outreach_participations", "invasion_participants", "outreach_campaigns"):
            await db[collection].delete_many({"campaign_id": {"$in": campaign_ids}})
        await db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
