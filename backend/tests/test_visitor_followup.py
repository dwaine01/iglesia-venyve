"""Visitantes V2: seguimiento por servicio y fecha (asignar, llamada/visita con
resultado), consejería y necesidades restringidas, la persona asignada solo ve
lo suyo, y revisión humana de «posible coincidencia»."""
import uuid

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero
from tests.test_visitor_registry import cleanup, tablet, visitor

db = server.db


@pytest.mark.asyncio
async def test_followup_assign_attempts_restricted_and_match_review():
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    tablets = []
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        server_pid = await fx.person(f"Servidor{tag}")
        servant = await fx.account(server_pid, "persona")
        other = await fx.account(await fx.person(f"Otro{tag}"), "persona")
        manager = await fx.account(await fx.person(f"Gestor{tag}"), "persona", capabilities=["visitors.followup.manage"], permissions_mode="manual")
        tablets = [await tablet(pastora)]
        pad = tablets[0]
        counsel = (await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}c", phone="5550201111", requests=["counseling_marriage", "prayer"], counseling_note="Privado"))).json()
        plain = (await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}p", phone="5550202222", requests=["visit"]))).json()
        regs = {doc["visitor_number"]: doc async for doc in db.visitor_registrations.find({"name_key": {"$regex": tag}}, {"_id": 0})}
        counsel_id, plain_id = regs[counsel["visitor_number"]]["registration_id"], regs[plain["visitor_number"]]["registration_id"]
        service = regs[counsel["visitor_number"]]["service"]

        # Por servicio y fecha; el gestor no ve el tipo de consejería, la pastora sí.
        listing = (await manager.get("/api/visitors/followup", params={"service_date": service["date"], "service_kind": service["kind"]})).json()
        mine = {item["registration_id"]: item for item in listing["items"]}
        assert {counsel_id, plain_id} <= set(mine) and listing["can_manage"] is True
        assert "Consejería matrimonial" not in mine[counsel_id]["requests"] and any("confidencial" in item for item in mine[counsel_id]["requests"])
        assert "Privado" not in str(listing)
        full = {item["registration_id"]: item for item in (await pastora.get("/api/visitors/followup", params={"service_date": service["date"]})).json()["items"]}
        assert "Consejería matrimonial" in full[counsel_id]["requests"]
        # La vista de registros también oculta el tipo para quien solo consulta.
        reader = await fx.account(await fx.person(f"Lector{tag}"), "persona", capabilities=["visitors.read"], permissions_mode="manual")
        assert "Consejería matrimonial" not in (await reader.get(f"/api/visitors/registrations/{counsel_id}")).json()["requests"]

        # Asignar: solo el gestor; la persona asignada ve SOLO lo suyo y registra resultados.
        assert (await servant.post(f"/api/visitors/registrations/{plain_id}/assign", json={"person_id": server_pid})).status_code == 403
        assignees = (await manager.get("/api/visitors/followup/assignees", params={"q": f"Servidor{tag}"})).json()["items"]
        assert assignees and assignees[0]["person_id"] == server_pid
        assigned = (await manager.post(f"/api/visitors/registrations/{plain_id}/assign", json={"person_id": server_pid})).json()
        assert assigned["status"] == "assigned" and assigned["assigned_name"]
        assert (await servant.get("/api/visitors/followup/mine-count")).json()["count"] == 1 and (await other.get("/api/visitors/followup/mine-count")).json()["count"] == 0
        own = (await servant.get("/api/visitors/followup")).json()
        assert [item["registration_id"] for item in own["items"]] == [plain_id] and own["can_manage"] is False
        assert (await other.get("/api/visitors/followup")).json()["items"] == []
        assert (await other.post(f"/api/visitors/registrations/{plain_id}/attempts", json={"kind": "call", "outcome": "no_answer", "idempotency_key": f"a-{tag}-x"})).status_code == 403
        attempt = {"kind": "call", "outcome": "no_answer", "note": "Volver a llamar el martes", "idempotency_key": f"a-{tag}-1"}
        first = (await servant.post(f"/api/visitors/registrations/{plain_id}/attempts", json=attempt)).json()
        again = (await servant.post(f"/api/visitors/registrations/{plain_id}/attempts", json=attempt)).json()
        assert first["status"] == "in_progress" and len(again["attempts"]) == 1 and again["attempts"][0]["outcome_label"] == "No contestó"
        done = (await servant.post(f"/api/visitors/registrations/{plain_id}/attempts", json={"kind": "visit", "outcome": "visit_done", "complete": True, "idempotency_key": f"a-{tag}-2"})).json()
        assert done["status"] == "done" and done["status_label"] == "Completado" and len(done["attempts"]) == 2
        assert await db.visitor_audit.count_documents({"action": "followup_attempt", "detail.registration_id": plain_id}) == 2

        # Posible coincidencia: el mismo teléfono con otro nombre → revisión humana.
        twin = (await pad.post("/api/kiosk/registrations", json=visitor(f"Otra{tag}", last_name="Distinta", phone="5550202222"))).json()
        twin_doc = await db.visitor_registrations.find_one({"visitor_number": twin["visitor_number"]}, {"_id": 0})
        assert twin_doc["match_status"] == "possible"
        view = next(item for item in (await manager.get("/api/visitors/followup", params={"service_date": service["date"]})).json()["items"] if item["registration_id"] == twin_doc["registration_id"])
        assert view["possible_people"] and view["possible_people"][0]["name"]
        assert (await manager.post(f"/api/visitors/registrations/{twin_doc['registration_id']}/resolve-match", json={"person_id": str(ObjectId())})).status_code == 422
        created = (await manager.post(f"/api/visitors/registrations/{twin_doc['registration_id']}/resolve-match", json={"create_new": True})).json()
        assert created["match_status"] == "created" and created["person_id"] not in twin_doc["possible_person_ids"]
        assert created["person_id"] == twin_doc["person_id"]  # ya tenía su perfil en Persona 360
        assert (await manager.post(f"/api/visitors/registrations/{twin_doc['registration_id']}/resolve-match", json={"create_new": True})).status_code == 409
        # «Sí, es esta persona»: se vincula a la existente y se retira el perfil provisional.
        same = (await pad.post("/api/kiosk/registrations", json=visitor(f"{tag}p", last_name="Prueba Segunda", phone="5550202222"))).json()
        same_doc = await db.visitor_registrations.find_one({"visitor_number": same["visitor_number"]}, {"_id": 0})
        assert same_doc["match_status"] == "possible" and same_doc["person_id"]
        target = next(pid for pid in same_doc["possible_person_ids"] if pid == regs[plain["visitor_number"]]["person_id"])
        linked = (await manager.post(f"/api/visitors/registrations/{same_doc['registration_id']}/resolve-match", json={"person_id": target})).json()
        assert linked["match_status"] == "linked" and linked["person_id"] == target
        assert await db.persons.find_one({"_id": ObjectId(same_doc["person_id"])}) is None
    finally:
        await cleanup(tag)
        for client in tablets:
            await client.aclose()
        await fx.cleanup()
