"""Visitantes: el nombre entra a la bienvenida apenas se escribe (borrador). Cuatro
tabletas a la vez, «Terminar registro» actualiza el mismo registro (sin duplicados),
abandono a mitad = «Incompleto» (no se pierde) y el equipo lo completa o descarta."""
import asyncio
import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from tests.test_visitor_registry import cleanup, link, tablet, visitor
from visitor_registry import now_utc

db = server.db


def draft_of(payload):
    return {key: payload[key] for key in ("idempotency_key", "first_name", "last_name", "privacy_version", "privacy_accepted") if key in payload} | {"preferred_name": payload.get("preferred_name")}


@pytest.mark.asyncio
async def test_draft_names_show_immediately_complete_without_duplicates_and_abandon():
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    clients = []
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        await pastora.put("/api/visitors/welcome/state", json={"today": True, "service_kind": "all"})
        tablets = [await tablet(pastora) for _ in range(4)]
        tv = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test", headers={"X-Link-Token": await link(pastora, "screen")})
        clients += tablets + [tv]
        screen = lambda: tv.get("/api/screen/welcome")  # noqa: E731

        # 4 tabletas escriben su nombre a la vez: los 4 aparecen YA en la bienvenida, «registrando…».
        payloads = [visitor(f"{tag}t{t}", phone=f"55503{t}0000", preferred_name=f"Pref{tag}{t}") for t in range(4)]
        drafts = await asyncio.gather(*(tablets[t].post("/api/kiosk/registrations/draft", json=draft_of(payloads[t])) for t in range(4)))
        assert all(item.status_code == 200 and item.json() == {"ok": True} for item in drafts), [item.text for item in drafts]
        names = {item["name"]: item for item in (await screen()).json()["names"] if tag in item["name"]}
        assert set(names) == {f"Pref{tag}{t} Prueba" for t in range(4)} and all(item["registering"] for item in names.values())
        stored = [await db.visitor_registrations.find_one({"idempotency_key": item["idempotency_key"]}, {"_id": 0}) for item in payloads]
        # El borrador solo guarda nombre y servicio.
        assert all(doc["status"] == "draft" and doc["contact"]["phone"] is None and doc["person_id"] is None and doc["visitor_number"] for doc in stored)
        assert len({doc["device_name"] for doc in stored}) == 4

        # El encargado corrige un nombre mientras la persona sigue llenando: se respeta al terminar.
        await pastora.post(f"/api/visitors/welcome/items/{stored[0]['registration_id']}", json={"display_name": f"Corregido{tag} Prueba"})
        # «Terminar registro» (y un doble toque) ACTUALIZA el mismo registro: mismo número, nunca otro.
        finals = await asyncio.gather(*(tablets[t].post("/api/kiosk/registrations", json=payloads[t]) for t in range(4)), tablets[1].post("/api/kiosk/registrations", json=payloads[1]))
        assert all(item.status_code == 201 for item in finals), [item.text for item in finals]
        assert [item.json()["visitor_number"] for item in finals[:4]] == [doc["visitor_number"] for doc in stored] and finals[4].json()["visitor_number"] == stored[1]["visitor_number"]
        for item in payloads:
            assert await db.visitor_registrations.count_documents({"name_key": {"$regex": f"visit{tag}t"}, "first_name": item["first_name"]}) == 1
        done = await db.visitor_registrations.find_one({"registration_id": stored[2]["registration_id"]}, {"_id": 0})
        assert done["status"] == "complete" and done["contact"]["phone"] == payloads[2]["phone"] and done["person_id"] and done["match_status"] == "created"
        names = {item["name"]: item for item in (await screen()).json()["names"] if tag in item["name"]}
        assert f"Corregido{tag} Prueba" in names and not any(item["registering"] for item in names.values())

        # Volvió atrás y corrigió su nombre → mismo borrador. La tableta se reinició y la misma persona
        # vuelve a escribirlo en la misma tableta → se retoma (no se duplica).
        again = visitor(f"{tag}re")
        await tablets[0].post("/api/kiosk/registrations/draft", json=draft_of(again))
        await tablets[0].post("/api/kiosk/registrations/draft", json=draft_of({**again, "last_name": "Prueba"}))
        second = visitor(f"{tag}re")
        await tablets[0].post("/api/kiosk/registrations/draft", json=draft_of(second))
        assert await db.visitor_registrations.count_documents({"name_key": f"visit{tag}re prueba"}) == 1
        completed = await tablets[0].post("/api/kiosk/registrations", json=second)
        assert completed.status_code == 201 and await db.visitor_registrations.count_documents({"name_key": f"visit{tag}re prueba"}) == 1

        # Abandono a mitad: el nombre sigue en la bienvenida y el registro queda «Incompleto».
        left = visitor(f"{tag}ab")
        await tablets[1].post("/api/kiosk/registrations/draft", json=draft_of(left))
        left_doc = await db.visitor_registrations.find_one({"idempotency_key": left["idempotency_key"]}, {"_id": 0})
        await db.visitor_registrations.update_one({"registration_id": left_doc["registration_id"]}, {"$set": {"updated_at": now_utc() - timedelta(minutes=20)}})
        shown = next(item for item in (await screen()).json()["names"] if item["id"] == left_doc["registration_id"])
        assert shown["registering"] is False
        incomplete = (await pastora.get("/api/visitors/followup", params={"state": "incomplete"})).json()
        row = next(item for item in incomplete["items"] if item["registration_id"] == left_doc["registration_id"])
        assert row["registration_state_label"] == "Incompleto" and incomplete["incomplete"] >= 1
        finished = (await pastora.post(f"/api/visitors/registrations/{left_doc['registration_id']}/finish-incomplete")).json()
        assert finished["registration_state"] == "complete" and finished["person_id"]
        # Otro abandonado se descarta: no se borra, se oculta.
        junk = visitor(f"{tag}jk")
        await tablets[2].post("/api/kiosk/registrations/draft", json=draft_of(junk))
        junk_doc = await db.visitor_registrations.find_one({"idempotency_key": junk["idempotency_key"]}, {"_id": 0})
        # Mientras la persona sigue llenando no se puede descartar; ya abandonado, sí.
        assert (await pastora.post(f"/api/visitors/registrations/{junk_doc['registration_id']}/discard")).status_code == 409
        await db.visitor_registrations.update_one({"registration_id": junk_doc["registration_id"]}, {"$set": {"updated_at": now_utc() - timedelta(minutes=20)}})
        assert (await pastora.post(f"/api/visitors/registrations/{junk_doc['registration_id']}/discard")).status_code == 200
        assert junk_doc["registration_id"] not in [item["id"] for item in (await screen()).json()["names"]]
        assert junk_doc["registration_id"] not in [item["registration_id"] for item in (await pastora.get("/api/visitors/followup")).json()["items"]]
        assert await db.visitor_registrations.count_documents({"registration_id": junk_doc["registration_id"], "status": "discarded"}) == 1

        # La misma persona ya quedó completa en otra tableta (mismo teléfono): el borrador se une, no duplica.
        twin = visitor(f"{tag}tw", phone="5550444444")
        assert (await tablets[3].post("/api/kiosk/registrations", json=twin)).status_code == 201
        twin_b = visitor(f"{tag}tw", phone="555-044-4444")
        await tablets[2].post("/api/kiosk/registrations/draft", json=draft_of(twin_b))
        merged = await tablets[2].post("/api/kiosk/registrations", json=twin_b)
        assert merged.json()["duplicate"] is True
        assert await db.visitor_registrations.count_documents({"name_key": f"visit{tag}tw prueba", "status": {"$ne": "merged"}}) == 1
        assert len([item for item in (await screen()).json()["names"] if f"Visit{tag}tw" in item["name"]]) == 1
        # El borrador también exige aceptar el aviso y la tableta no recibe datos.
        assert (await tablets[0].post("/api/kiosk/registrations/draft", json={**draft_of(visitor(f"{tag}np")), "privacy_accepted": False})).status_code == 422
    finally:
        await cleanup(tag)
        await db.app_settings.delete_many({"_id": "visitor_welcome_state"})
        for client in clients:
            await client.aclose()
        await fx.cleanup()
