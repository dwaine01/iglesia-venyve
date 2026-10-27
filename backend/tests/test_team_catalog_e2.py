"""Equipo y Responsables · E2: catálogo de áreas y cargos. Cargos iniciales del dueño, máximo 3 por cargo,
principal/asistente, permisos solo del catálogo, dónde vive cada dato (sin dos fuentes de verdad), crear áreas y
cargos, el coordinador no escala privilegios ni toca Finanzas/Junta, historial inmutable y nada se borra."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_catalog_seed_rules_and_no_escalation():
    from team_catalog import ensure_team_catalog
    await ensure_team_catalog()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    created_areas, created_roles = [], []
    try:
        pastora = await fx.account(await fx.person(f"PastoraE2{tag}"), "pastora")
        coord = await fx.account(await fx.person(f"CoordE2{tag}"), "lider", access_level="coordinador_general", capabilities=["operations.view", "operations.checkin"])
        member = await fx.account(await fx.person(f"MiembroE2{tag}"), "persona")
        assert (await member.get("/api/team/catalog")).status_code == 403

        data = (await coord.get("/api/team/catalog")).json()
        areas = {area["key"]: area for area in data["areas"]}
        assert {"direccion", "finanzas", "consolidacion", "grupos_frontales", "libreria", "educacion", "ministerios", "operacion"} <= set(areas)
        roles = {role["key"]: role for area in data["areas"] for role in area["roles"]}
        # Finanzas: las tres funciones = los roles que ya existen.
        assert "finance.collection.record" in roles["finanzas_registra"]["capabilities"]
        assert "finance.collection.verify" in roles["finanzas_verifica"]["capabilities"]
        assert "finance.treasury" in roles["tesorero"]["capabilities"]
        # Una sola fuente de verdad: lo que ya vive en otro módulo se marca así.
        assert roles["pastor_principal"]["source"] == "account_role" and roles["coordinador_general"]["source"] == "account_role"
        assert roles["lider_consolidacion"]["source"] == "consolidation_leads" and roles["mentor"]["source"] == "mentorship"
        assert roles["responsable_grupo"]["source"] == "front_groups" and roles["responsable_ministerio"]["source"] == "ministries"
        assert all(role["max_holders"] in (None, 1, 2, 3) for role in roles.values()) and data["max_holders"] == 3

        # Ampliable: área y cargo nuevos (máximo 3; más de 3 no).
        area = (await coord.post("/api/team/areas", json={"name": f"Alabanza {tag}"})).json()
        created_areas.append(area["area_id"])
        assert (await coord.post("/api/team/roles", json={"area_id": area["area_id"], "name": "Director", "max_holders": 4})).status_code == 422
        role = await coord.post("/api/team/roles", json={"area_id": area["area_id"], "name": "Director de alabanza", "kind": "principal", "max_holders": 2, "capabilities": ["operations.view"]})
        assert role.status_code == 201, role.text
        created_roles.append(role.json()["role_id"])

        # El coordinador no escala: ni permisos que no tiene, ni Finanzas/Junta, ni editar un cargo de Finanzas.
        assert (await coord.post("/api/team/roles", json={"area_id": area["area_id"], "name": "Cargo QA", "capabilities": ["library.catalog.manage"]})).status_code == 403
        assert (await coord.post("/api/team/roles", json={"area_id": area["area_id"], "name": "Cargo QA", "capabilities": ["finance.read"], "privilege_group": "finance"})).status_code == 403
        tes = roles["tesorero"]
        assert (await coord.put("/api/team/roles/tesorero", json={"area_id": tes["area_id"], "name": "Tesorera", "kind": "principal", "max_holders": 3, "capabilities": tes["capabilities"], "privilege_group": "finance"})).status_code == 403
        assert (await pastora.post("/api/team/roles", json={"area_id": area["area_id"], "name": "Cargo QA", "capabilities": ["no.existe"]})).status_code == 422
        fin = await pastora.post("/api/team/roles", json={"area_id": area["area_id"], "name": f"Caja chica {tag}", "capabilities": ["finance.read"], "privilege_group": "finance", "max_holders": 1})
        assert fin.status_code == 201
        created_roles.append(fin.json()["role_id"])

        # Nada se borra: se desactiva; queda en el historial.
        off = await coord.put(f"/api/team/roles/{created_roles[0]}", json={"area_id": area["area_id"], "name": "Director de alabanza", "kind": "principal", "max_holders": 2, "capabilities": ["operations.view"], "active": False})
        assert off.status_code == 200 and off.json()["active"] is False
        assert await db.team_roles.count_documents({"role_id": created_roles[0]}) == 1
        events = [item for item in (await pastora.get("/api/team/catalog/history")).json()["items"] if item["entity_id"] in created_roles + created_areas]
        assert {"area_created", "role_created", "role_updated"} <= {item["action"] for item in events}
        assert next(item for item in events if item["action"] == "role_updated")["before"]["active"] is True
    finally:
        await db.team_roles.delete_many({"role_id": {"$in": created_roles}})
        await db.team_areas.delete_many({"area_id": {"$in": created_areas}})
        await db.team_catalog_events.delete_many({"entity_id": {"$in": created_roles + created_areas}})
        await fx.cleanup()
