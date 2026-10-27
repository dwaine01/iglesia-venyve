"""Equipo y Responsables · E4: los cargos que viven en otro módulo se ven y se cambian desde la página, pero el
dato y las reglas siguen siendo del módulo (una sola fuente de verdad): Consolidación, Mentoría, Grupo Frontal y
Ministerios; pastor principal y coordinador general solo se ven."""
import uuid
from datetime import datetime, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_module_roles_read_and_write_through_their_module():
    from team_assignments import ensure_indexes
    from team_catalog import ensure_team_catalog
    await ensure_team_catalog()
    await ensure_indexes()
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    group_id, ministry_id = f"fg-e4-{tag}", f"min-e4-{tag}"
    try:
        pastora_person = await fx.person(f"PastoraE4{tag}")
        pastora = await fx.account(pastora_person, "pastora")
        coord = await fx.account(await fx.person(f"CoordE4{tag}"), "lider", access_level="coordinador_general", capabilities=["operations.view"])
        ana, luis = await fx.person(f"AnaE4{tag}"), await fx.person(f"LuisE4{tag}")
        await fx.account(ana, "lider", capabilities=["library.deliver"], permissions_mode="manual")
        now = datetime.now(timezone.utc)
        await db.front_groups.insert_one({"_id": group_id, "front_group_id": group_id, "name": f"Grupo E4 {tag}", "status": "active", "parent_group_id": None,
                                          "primary_leader_person_id": None, "leader_pending": True, "created_at": now})
        await db.ministry_catalog.insert_one({"_id": ministry_id, "nombre": f"Damas E4 {tag}", "normalized_name": f"damas e4 {tag}", "activo": True, "created_at": now})
        await db.consolidation_lead_designations.update_many({"active": True}, {"$set": {"qa_paused": tag, "active": False}})

        view = (await pastora.get("/api/team/assignments")).json()
        assert any(item.get("unit_id") == group_id for item in view["pending"]) and any(item.get("unit_id") == ministry_id for item in view["pending"])
        assert any(row["person"]["person_id"] == pastora_person for row in view["modules"]["pastor_principal"])  # solo se ve

        # Un guardado con cargos de varios módulos: Consolidación, insignia, grupo y ministerio.
        saved = await pastora.post("/api/team/changes", json={"is_test": True, "changes": [
            {"op": "assign", "role_id": "lider_consolidacion", "person_id": ana},
            {"op": "assign", "role_id": "mentor", "person_id": luis},
            {"op": "assign", "role_id": "responsable_grupo", "unit_id": group_id, "slot": "leader", "person_id": ana},
            {"op": "assign", "role_id": "responsable_ministerio", "unit_id": ministry_id, "person_id": luis}]})
        assert saved.status_code == 200, saved.text
        # El dato vive en cada módulo (no hay copia en team_assignments).
        assert await db.consolidation_lead_designations.find_one({"person_id": ana, "active": True})
        assert (await db.mentor_badges.find_one({"person_id": luis}))["active"] is True
        assert (await db.front_groups.find_one({"front_group_id": group_id}))["primary_leader_person_id"] == ana
        assert await db.ministry_assignments.find_one({"person_id": luis, "ministry_id": ministry_id, "activo": True})
        assert not await db.team_assignments.find_one({"person_id": {"$in": [ana, luis]}})
        view = (await pastora.get("/api/team/assignments")).json()
        group = next(row for row in view["modules"]["responsable_grupo"] if row["unit_id"] == group_id)
        assert group["leader"]["person_id"] == ana and not any(item.get("unit_id") == group_id for item in view["pending"])

        # Mismas reglas del módulo: el coordinador no designa encargados de Consolidación; el líder de grupo necesita cuenta.
        assert (await coord.post("/api/team/changes", json={"changes": [{"op": "assign", "role_id": "lider_consolidacion", "person_id": luis}]})).status_code == 409
        no_account = await pastora.post("/api/team/changes", json={"changes": [{"op": "assign", "role_id": "responsable_grupo", "unit_id": group_id, "slot": "leader", "person_id": luis}]})
        assert no_account.status_code == 409 and "cuenta" in str(no_account.json())

        # Retirar en el módulo: designación y ministerio (el historial de cada módulo se conserva).
        designation = await db.consolidation_lead_designations.find_one({"person_id": ana, "active": True})
        ministry_assignment = await db.ministry_assignments.find_one({"person_id": luis, "ministry_id": ministry_id, "activo": True})
        removed = await pastora.post("/api/team/changes", json={"is_test": True, "changes": [
            {"op": "remove", "role_id": "lider_consolidacion", "assignment_id": designation["designation_id"]},
            {"op": "remove", "role_id": "responsable_ministerio", "assignment_id": ministry_assignment["_id"]}]})
        assert removed.status_code == 200, removed.text
        assert (await db.consolidation_lead_designations.find_one({"designation_id": designation["designation_id"]}))["active"] is False
        assert (await db.ministry_assignments.find_one({"_id": ministry_assignment["_id"]}))["activo"] is False
        events = [item for item in (await pastora.get("/api/team/history")).json()["items"] if item.get("source")]
        assert {"consolidation_leads", "mentorship", "front_groups", "ministries"} <= {item["source"] for item in events}
    finally:
        await db.front_groups.delete_many({"front_group_id": group_id})
        await db.front_group_assignments.delete_many({"front_group_id": group_id})
        await db.ministry_catalog.delete_many({"_id": ministry_id})
        await db.ministry_assignments.delete_many({"ministry_id": ministry_id})
        await db.mentor_badges.delete_many({"person_id": {"$in": fx.person_ids}})
        await db.consolidation_lead_designations.delete_many({"person_id": {"$in": fx.person_ids}})
        await db.consolidation_lead_designations.update_many({"qa_paused": tag}, {"$set": {"active": True}, "$unset": {"qa_paused": ""}})
        await db.team_events.delete_many({"person_id": {"$in": fx.person_ids}})
        await fx.cleanup()
