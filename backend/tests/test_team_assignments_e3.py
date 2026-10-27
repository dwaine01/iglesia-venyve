"""Equipo y Responsables · E3: asignar, reemplazar y retirar en UN guardado (todo o nada), con las reglas del
dueño: nadie se asigna a sí mismo, máximo 3, Finanzas solo el pastor o quien él autorizó, el coordinador no
escala, la pastora no ocupa cargos de Finanzas, se aplican los permisos del cargo y al retirar se quita SOLO lo
que dio ese cargo; historial con quién ocupaba antes. Datos de prueba is_test."""
import uuid

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_team_assignment_rules_permissions_and_history():
    from team_assignments import ensure_indexes
    from team_catalog import ensure_team_catalog
    await ensure_team_catalog()
    await ensure_indexes()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    try:
        pastora_person = await fx.person(f"PastoraE3{tag}")
        pastora = await fx.account(pastora_person, "pastora")
        coord_person = await fx.person(f"CoordE3{tag}")
        coord = await fx.account(coord_person, "lider", access_level="coordinador_general", capabilities=["operations.view", "operations.checkin"])
        ana, luis, rosa, eva = [await fx.person(f"{name}E3{tag}") for name in ("Ana", "Luis", "Rosa", "Eva")]
        for person in (ana, luis, rosa):
            await fx.account(person, "lider", capabilities=["library.deliver"], permissions_mode="manual")
        ana_user = await db.users.find_one({"person_id": ana})

        # Todo o nada: un cambio malo (autoasignación) y no se guarda ninguno.
        bad = await coord.post("/api/team/changes", json={"is_test": True, "changes": [
            {"op": "assign", "role_id": "recepcion", "person_id": ana}, {"op": "assign", "role_id": "recepcion", "person_id": coord_person}]})
        assert bad.status_code == 409 and bad.json()["detail"]["problems"][0]["change"] == 2
        assert not await db.team_assignments.find_one({"person_id": ana, "active": True})

        # El coordinador: Recepción sí (permisos que él tiene); Finanzas y Librería no.
        ok = await coord.post("/api/team/changes", json={"is_test": True, "changes": [{"op": "assign", "role_id": "recepcion", "person_id": ana}]})
        assert ok.status_code == 200, ok.text
        assert (await coord.post("/api/team/changes", json={"is_test": True, "changes": [{"op": "assign", "role_id": "tesorero", "person_id": luis}]})).status_code == 409
        assert (await coord.post("/api/team/changes", json={"is_test": True, "changes": [{"op": "assign", "role_id": "encargado_libreria", "person_id": luis}]})).status_code == 409

        # La pastora arma Finanzas y Librería juntas; ella no puede ocupar Finanzas.
        assert (await pastora.post("/api/team/changes", json={"is_test": True, "changes": [{"op": "assign", "role_id": "tesorero", "person_id": pastora_person}]})).status_code == 409
        saved = await pastora.post("/api/team/changes", json={"is_test": True, "changes": [
            {"op": "assign", "role_id": "finanzas_registra", "person_id": ana}, {"op": "assign", "role_id": "finanzas_verifica", "person_id": luis},
            {"op": "assign", "role_id": "tesorero", "person_id": rosa}, {"op": "assign", "role_id": "encargado_libreria", "person_id": ana}]})
        assert saved.status_code == 200 and saved.json()["applied"] == 4, saved.text
        ana_user = await db.users.find_one({"_id": ana_user["_id"]})
        assert {"finance.collection.record", "operations.checkin", "library.catalog.manage"} <= set(ana_user["capabilities"]) and "finance" in ana_user["privilege_groups"]
        roles = (await (await fx.account(await fx.person(f"Fin{tag}"), "persona")).get("/api/finance/my-roles")).json()  # otro usuario: sin roles
        assert not roles.get("record")

        # Máximo 3 y sin repetir.
        others = [await fx.person(f"Extra{i}{tag}") for i in range(3)]
        assert (await pastora.post("/api/team/changes", json={"is_test": True, "changes": [{"op": "assign", "role_id": "finanzas_registra", "person_id": ana}]})).status_code == 409
        full = await pastora.post("/api/team/changes", json={"is_test": True, "changes": [{"op": "assign", "role_id": "recepcion", "person_id": p} for p in others]})
        assert full.status_code == 409  # Ana + 3 = 4 > 3

        # Reemplazar en Recepción: Ana sale, Eva entra (sin cuenta: queda pendiente). Ana conserva lo de sus otros cargos y lo dado a mano.
        recep = await db.team_assignments.find_one({"role_id": "recepcion", "person_id": ana, "active": True})
        replaced = await coord.post("/api/team/changes", json={"is_test": True, "changes": [{"op": "replace", "role_id": "recepcion", "assignment_id": recep["assignment_id"], "person_id": eva, "reason": "Cambio de turno"}]})
        assert replaced.status_code == 200, replaced.text
        ana_user = await db.users.find_one({"_id": ana_user["_id"]})
        assert "operations.checkin" not in ana_user["capabilities"] and "library.deliver" in ana_user["capabilities"] and "finance.collection.record" in ana_user["capabilities"]
        eva_doc = await db.team_assignments.find_one({"role_id": "recepcion", "person_id": eva, "active": True})
        assert eva_doc["pending_account"] is True and eva_doc["replaced_person_id"] == ana

        # Retirar Finanzas: se quita su permiso y el grupo que dio el cargo.
        reg = await db.team_assignments.find_one({"role_id": "finanzas_registra", "person_id": ana, "active": True})
        assert (await pastora.post("/api/team/changes", json={"is_test": True, "changes": [{"op": "remove", "role_id": "finanzas_registra", "assignment_id": reg["assignment_id"], "reason": "Prueba"}]})).status_code == 200
        ana_user = await db.users.find_one({"_id": ana_user["_id"]})
        assert "finance.collection.record" not in ana_user["capabilities"] and "finance" not in ana_user["privilege_groups"]
        assert await db.team_assignments.count_documents({"assignment_id": reg["assignment_id"]}) == 1  # nada se borra

        # De un vistazo y con historial.
        view = (await pastora.get("/api/team/assignments", params={"include_test": True})).json()
        assert rosa in {row["person"]["person_id"] for row in view["by_role"]["tesorero"]}
        assert view["by_role"]["tesorero"][0]["person"]["name"] and "photo_url" in view["by_role"]["tesorero"][0]["person"]
        if not view["by_role"].get("finanzas_registra"):
            assert any(item["role_id"] == "finanzas_registra" for item in view["pending"])  # puesto pendiente visible
        history = (await pastora.get("/api/team/history")).json()["items"]
        replace_event = next(item for item in history if item["op"] == "replace" and item["person_id"] == eva)
        assert replace_event["previous_person_id"] == ana and replace_event["reason"] == "Cambio de turno"
        assert (await (await fx.account(await fx.person(f"Miembro{tag}"), "persona")).post("/api/team/changes", json={"changes": [{"op": "assign", "role_id": "recepcion", "person_id": ana}]})).status_code == 403
    finally:
        await db.team_assignments.delete_many({"person_id": {"$in": fx.person_ids}})
        await db.team_events.delete_many({"person_id": {"$in": fx.person_ids}})
        await fx.cleanup()
