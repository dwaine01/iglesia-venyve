"""C1 · Encargados de Consolidación: designar/quitar desde la autoridad
pastoral, límite configurable (3 por defecto), capacidades del catálogo 5A
(solo se retiran las que dio la designación), cuenta nueva con la regla del
formulario de invasión, pastora excluida y 403 para quien no corresponde."""
import uuid

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server

db = server.db


@pytest.mark.asyncio
async def test_designate_remove_limit_and_permissions():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        coordinator = await fx.account(await fx.person(f"Coord{tag}"), "lider", access_level="coordinador_general")
        people = [await fx.person(f"Lead{index}{tag}") for index in range(4)]
        clients = [await fx.account(person_id, "persona") for person_id in people[:3]]
        no_account_id = await fx.person(f"SinCuenta{tag}")
        outsider = await fx.account(await fx.person(f"Ajeno{tag}"), "persona")
        await db.consolidation_lead_designations.delete_many({})
        await db.app_settings.delete_many({"_id": "consolidation_leads_limit"})
        # La persona 0 ya tenía processes.read por otra vía: no se le debe retirar.
        await db.users.update_one({"person_id": people[0]}, {"$addToSet": {"capabilities": "processes.read"}})
        before = await db.users.find_one({"person_id": people[0]})

        # Permisos: solo la autoridad pastoral designa; el coordinador ve; el resto 403.
        assert (await coordinator.post("/api/consolidation/leads", json={"person_id": people[0]})).status_code == 403
        assert (await outsider.get("/api/consolidation/leads")).status_code == 403
        assert "consolidation.assign" not in ((await db.users.find_one({"person_id": people[2]})).get("capabilities") or [])  # aún sin capacidades
        assert (await pastora.post("/api/consolidation/leads", json={"person_id": pastora_id})).status_code == 409

        designated = []
        for person_id in people[:3]:
            created = await pastora.post("/api/consolidation/leads", json={"person_id": person_id})
            assert created.status_code == 201, created.text
            designated.append(created.json())
        assert "processes.read" not in designated[0]["granted"] and "consolidation.assign" in designated[0]["granted"]
        assert (await pastora.post("/api/consolidation/leads", json={"person_id": people[0]})).status_code == 409  # ya es encargada
        # Límite de 3 (la persona 3 tiene cuenta, pero no cabe).
        await fx.account(people[3], "persona")
        over = await pastora.post("/api/consolidation/leads", json={"person_id": people[3]})
        assert over.status_code == 409 and "límite" in over.json()["detail"]
        assert (await pastora.put("/api/consolidation/leads/settings", json={"limit": 2})).status_code == 409
        assert (await pastora.put("/api/consolidation/leads/settings", json={"limit": 4})).json()["limit"] == 4

        # Habilitado: ya puede entrar a Consolidación; lo ve el coordinador; aviso en su campana.
        assert (await clients[1].get("/api/processes/consolidation/dashboard")).status_code == 200
        assert set(designated[1]["granted"]) <= set((await db.users.find_one({"person_id": people[1]}))["capabilities"])
        listing = (await coordinator.get("/api/consolidation/leads")).json()
        assert len(listing["items"]) == 3 and listing["limit"] == 4 and listing["can_manage"] is False
        assert any(item["type"] == "consolidation_lead" for item in (await clients[1].get("/api/notifications")).json()["items"])

        # Sin cuenta: avisa; con correo y contraseña la crea (nivel persona) con las capacidades.
        missing = await pastora.post("/api/consolidation/leads", json={"person_id": no_account_id})
        assert missing.status_code == 422 and missing.json()["detail"]["needs_account"] is True
        email = f"lead{tag}@example.com"
        created = await pastora.post("/api/consolidation/leads", json={"person_id": no_account_id, "email": email, "temporary_password": "Temporal12345"})
        assert created.status_code == 201, created.text
        new_user = await db.users.find_one({"person_id": no_account_id})
        fx.user_ids.append(new_user["_id"])
        assert new_user["rol"] == "persona" and "consolidation.assign" in new_user["capabilities"] and created.json()["account_created"] is True

        # Quitar: retira solo lo que dio la designación, cierra sesiones y queda en el historial.
        removed = (await pastora.delete(f"/api/consolidation/leads/{designated[0]['designation_id']}")).json()
        assert removed["active"] is False and removed["removed_by_name"]
        after = await db.users.find_one({"person_id": people[0]})
        assert "processes.read" in after["capabilities"] and "consolidation.assign" not in after["capabilities"]
        assert after.get("token_version", 1) == before.get("token_version", 1) + 1
        history = (await pastora.get("/api/consolidation/leads")).json()["history"]
        assert any(item["designation_id"] == designated[0]["designation_id"] for item in history)
        # Volver a designarla funciona (nueva designación).
        assert (await pastora.post("/api/consolidation/leads", json={"person_id": people[0]})).status_code == 201
    finally:
        await db.consolidation_lead_designations.delete_many({"person_id": {"$in": [str(item) for item in [*locals().get("people", []), locals().get("no_account_id")] if item]}})
        await db.app_settings.delete_many({"_id": "consolidation_leads_limit"})
        await db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
