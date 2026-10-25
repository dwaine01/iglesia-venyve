"""Formulario ÚNICO de visitantes: preguntas de los 3 papeles, guardado paso a paso en
el borrador, enrutamiento a tareas (con aviso inmediato para «aceptar a Jesús» u
oración), resumen legible, compatibilidad con registros anteriores y «Agregar
nombre» del operador (siguiente / al final / sin duplicados)."""
import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from tests.test_visitor_registry import cleanup, link, tablet, visitor
from visitor_registry import now_utc

db = server.db


@pytest.mark.asyncio
async def test_unified_form_steps_routing_summary_and_manual_names():
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    clients = []
    try:
        pastora_pid = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_pid, "pastora")
        reader = await fx.account(await fx.person(f"Lector{tag}"), "persona", capabilities=["visitors.read", "visitors.followup.manage"], permissions_mode="manual")
        mentor = await fx.account(await fx.person(f"Mentor{tag}"), "persona")
        await pastora.put("/api/visitors/welcome/state", json={"today": True, "service_kind": "all"})
        pad = await tablet(pastora)
        tv = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test", headers={"X-Link-Token": await link(pastora, "screen")})
        clients += [pad, tv]

        # Paso a paso: cada «Siguiente» guarda lo contestado en el MISMO borrador.
        form = visitor(f"{tag}u", last_name="Unico Pérez", preferred_name=f"Uni{tag}")
        assert (await pad.post("/api/kiosk/registrations/draft", json=form)).json() == {"ok": True}
        form |= {"phone": "555-222-3333", "contact_methods": ["text", "whatsapp"], "email": f"uni{tag}@example.com"}
        await pad.post("/api/kiosk/registrations/draft", json=form)
        form |= {"address": "Calle 1 #23", "city": "Orlando", "zip_code": "32801", "visit_mode": "new_in_area", "birth_date": "1985-07-09"}
        await pad.post("/api/kiosk/registrations/draft", json=form)
        draft = await db.visitor_registrations.find_one({"idempotency_key": form["idempotency_key"]}, {"_id": 0})
        assert draft["status"] == "draft" and draft["contact"]["phone"] == "5552223333" and draft["contact"]["zip_code"] == "32801" and draft["visit"]["visit_mode"] == "new_in_area"
        assert draft["person_id"] is None and draft["match_status"] == "pending"  # Persona 360 hasta terminar
        # Tu fe: «aceptar a Jesús hoy» → aviso inmediato, aunque aún no termine.
        form |= {"first_visit": True, "invited_by": "Hermano Juan", "how_heard": "Invitación de alguien", "faith_christian": "on_way", "accept_jesus": "today", "faith_info": True,
                 "other_church": True, "other_church_name": "Iglesia Central", "other_church_pastor": "Pastor Luis"}
        await pad.post("/api/kiosk/registrations/draft", json=form)
        draft = await db.visitor_registrations.find_one({"idempotency_key": form["idempotency_key"]}, {"_id": 0})
        assert draft["followup"]["alert_sent"] is True and any(task["key"] == "call_today" and task["urgent"] for task in draft["followup"]["tasks"])
        pastora_user = await db.users.find_one({"person_id": pastora_pid}, {"_id": 1})
        alert = await db.portal_notifications.find_one({"recipient_user_id": str(pastora_user["_id"]), "type": "visitor_urgent", "ref.registration_id": draft["registration_id"]})
        assert alert and "llamar hoy" in alert["title"].lower() and "aceptar a Jesús" in alert["message"]
        # Familia, servir (varias), apoyo y cierre.
        form |= {"marital_status": "married", "spouse_name": "Ana Pérez", "has_children": True, "children": [{"name": f"Hijo{n}", "age": n + 3} for n in range(6)],
                 "companions": "Mi esposa y mis hijos", "kids_ministry": True,
                 "requests": ["prayer_family", "visit", "membership", "serve", "home_service", "counseling_marriage", "other_help"], "counseling_note": "Confidencial",
                 "needs_note": "Trabajo", "giving_info": True, "consent_followup": True}
        await pad.post("/api/kiosk/registrations/draft", json=form)
        final = await pad.post("/api/kiosk/registrations", json=form)
        assert final.status_code == 201 and final.json()["visitor_number"] == draft["visitor_number"]
        doc = await db.visitor_registrations.find_one({"idempotency_key": form["idempotency_key"]}, {"_id": 0})
        assert doc["status"] == "complete" and doc["person_id"] and len(doc["household"]["children"]) == 6 and doc["giving"]["info"] is True
        assert await db.portal_notifications.count_documents({"type": "visitor_urgent", "ref.registration_id": doc["registration_id"], "recipient_user_id": str(pastora_user["_id"])}) == 1
        keys = {task["key"]: task for task in doc["followup"]["tasks"]}
        assert {"call_today", "faith_info", "visit", "membership", "serve", "kids", "home_service", "giving", "pastoral"} <= set(keys)
        assert keys["giving"]["area"] == "finance" and keys["home_service"]["area"] == "cells" and keys["kids"]["area"] == "children" and keys["pastoral"]["restricted"]

        # Ficha de seguimiento: resumen legible; lo confidencial solo con permiso.
        full = next(item for item in (await pastora.get("/api/visitors/followup")).json()["items"] if item["registration_id"] == doc["registration_id"])
        text = str(full["answers"])
        for expected in ("555-222-3333", "Calle 1 #23, Orlando, 32801", "Es nuevo en el área", "Hermano Juan", "Estoy en camino", "Hoy", "Iglesia Central", "Pastor Luis",
                         "Casado o casada", "Ana Pérez", "Hijo5, 8 años", "Consejería matrimonial", "ofrendar o donar"):
            assert expected in text, expected
        limited = next(item for item in (await reader.get("/api/visitors/followup")).json()["items"] if item["registration_id"] == doc["registration_id"])
        assert "Consejería matrimonial" not in str(limited["answers"]) and "Confidencial" not in str(limited) and "Atención pastoral confidencial" in str(limited["tasks"])
        # Marcar una tarea como hecha; se conserva.
        done = (await pastora.post(f"/api/visitors/registrations/{doc['registration_id']}/tasks/visit", json={"done": True})).json()
        assert next(task for task in done["tasks"] if task["key"] == "visit")["done"] is True
        assert (await mentor.post(f"/api/visitors/registrations/{doc['registration_id']}/tasks/visit", json={"done": False})).status_code == 403

        # La pantalla pública sigue igual: solo nombre, «invitado por» y «registrando».
        screen = (await tv.get("/api/screen/welcome")).json()
        mine = next(item for item in screen["names"] if item["id"] == doc["registration_id"])
        assert set(mine) == {"id", "name", "invited_by", "registering"} and mine["invited_by"] == "Hermano Juan"
        for leaked in ("Orlando", "32801", "Ana Pérez", "Hijo", "Jesús", "Iglesia Central", "ofrendar"):
            assert leaked not in str(screen), leaked

        # La misma persona vuelve a llenar en otra tableta (su borrador ya guardó el teléfono): se une, sin 409 ni duplicado.
        other_pad = await tablet(pastora)
        clients.append(other_pad)
        again = visitor(f"{tag}u", last_name="Unico Pérez", phone="5552223333")
        await other_pad.post("/api/kiosk/registrations/draft", json=again)
        repeat = await other_pad.post("/api/kiosk/registrations", json=again)
        assert repeat.status_code == 201 and repeat.json()["duplicate"] is True and repeat.json()["visitor_number"] == doc["visitor_number"]
        assert await db.visitor_registrations.count_documents({"name_key": f"visit{tag}u unico perez", "status": {"$ne": "merged"}}) == 1
        # Registro de la versión anterior (oración «prayer», acompañantes): se lee bien y genera su tarea.
        old = await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}old", requests=["prayer"], family=[{"name": "Tía Rosa", "relation": "Otro familiar"}]))
        old_doc = await db.visitor_registrations.find_one({"visitor_number": old.json()["visitor_number"]}, {"_id": 0})
        assert any(task["key"] == "call_today" for task in old_doc["followup"]["tasks"])
        old_view = next(item for item in (await pastora.get("/api/visitors/followup")).json()["items"] if item["registration_id"] == old_doc["registration_id"])
        assert "Quiero oración por mí" in str(old_view["answers"]) and "Tía Rosa" in str(old_view["answers"])

        # «Agregar nombre»: entra YA; «Siguiente» lo pone justo después del actual; sin duplicados.
        names_now = [item["id"] for item in (await tv.get("/api/screen/welcome")).json()["names"]]
        current = names_now[0]
        end = await pastora.post("/api/visitors/welcome/manual", json={"name": f"Manual{tag}  Final López", "position": "end"})
        assert end.status_code == 201 and end.json()["manual"] is True and end.json()["name"] == f"Manual{tag} Final López"
        nxt = await pastora.post("/api/visitors/welcome/manual", json={"name": f"Manual{tag} Siguiente", "invited_by": "La pastora", "position": "next", "after_id": current})
        order = [item for item in (await tv.get("/api/screen/welcome")).json()["names"]]
        ids = [item["id"] for item in order]
        assert ids[ids.index(current) + 1] == nxt.json()["registration_id"] and ids[-1] == end.json()["registration_id"]
        assert next(item for item in order if item["id"] == nxt.json()["registration_id"])["invited_by"] == "La pastora"
        dup = await pastora.post("/api/visitors/welcome/manual", json={"name": f"manual{tag} final lopez", "position": "end"})
        assert dup.status_code == 409 and "ya está en la lista" in dup.json()["detail"]
        assert (await mentor.post("/api/visitors/welcome/manual", json={"name": f"Otro{tag}", "position": "end"})).status_code == 403
        # Queda «Agregado a mano · por completar» en Seguimiento; se corrige y se completa como cualquier otro.
        row = next(item for item in (await pastora.get("/api/visitors/followup", params={"state": "incomplete"})).json()["items"] if item["registration_id"] == end.json()["registration_id"])
        assert row["registration_state_label"] == "Agregado a mano · por completar" and row["origin"] == "operator"
        fixed = (await pastora.post(f"/api/visitors/welcome/items/{end.json()['registration_id']}", json={"display_name": f"Manuel{tag} López"})).json()
        assert fixed["name"] == f"Manuel{tag} López"
        assert (await pastora.post(f"/api/visitors/registrations/{end.json()['registration_id']}/finish-incomplete")).json()["registration_state"] == "complete"
        # Un borrador de tableta abandonado también se completa o descarta (no mientras se llena).
        await db.visitor_registrations.update_one({"registration_id": nxt.json()["registration_id"]}, {"$set": {"updated_at": now_utc() - timedelta(minutes=30)}})
        assert (await pastora.post(f"/api/visitors/registrations/{nxt.json()['registration_id']}/discard")).status_code == 200
    finally:
        await cleanup(tag)
        await db.visitor_registrations.delete_many({"name_key": {"$regex": f"manual{tag}"}})
        await db.portal_notifications.delete_many({"type": "visitor_urgent", "message": {"$regex": "V-"}, "created_at": {"$gte": now_utc() - timedelta(hours=1)}})
        await db.app_settings.delete_many({"_id": "visitor_welcome_state"})
        for client in clients:
            await client.aclose()
        await fx.cleanup()
