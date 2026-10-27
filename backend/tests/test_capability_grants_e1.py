"""Equipo y Responsables · E1: el libro de permisos. Un cargo quita al retirarse SOLO lo que él dio y que ningún
otro cargo da; lo dado a mano se conserva; Gestión de accesos no borra lo que da un cargo activo. La migración
de Encargados de Consolidación tiene respaldo y se puede deshacer."""
import uuid
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_grant_revoke_only_what_each_source_gave_and_manual_survives():
    from capability_grants import grant, revoke
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    try:
        pastora = await fx.account(await fx.person(f"PastoraE1{tag}"), "pastora")
        person = await fx.person(f"PersonaE1{tag}")
        await fx.account(person, "lider", capabilities=["library.deliver"], permissions_mode="manual")
        user = await db.users.find_one({"person_id": person})
        caps = lambda u: set(u.get("capabilities") or [])  # noqa: E731

        # Dos cargos dan el mismo permiso; uno de ellos además uno que la persona ya tenía a mano.
        assert await grant(user["_id"], ["processes.read", "library.deliver"], "team:A") == ["processes.read"]
        assert await grant(user["_id"], ["processes.read", "processes.write"], "team:B") == ["processes.read", "processes.write"]
        assert await revoke(user["_id"], "team:A") == []          # processes.read lo sigue dando B
        user = await db.users.find_one({"_id": user["_id"]})
        assert {"processes.read", "processes.write", "library.deliver"} <= caps(user)

        # Gestión de accesos guarda una lista sin los permisos del cargo B: no se pierden.
        body = {"access_level": "lider", "is_active": True, "privilege_groups": [], "capabilities": ["library.deliver"]}
        saved = await pastora.put(f"/api/core/governance/users/{user['_id']}/access", json=body)
        assert saved.status_code == 200, saved.text
        assert {"processes.read", "processes.write"} <= set(saved.json()["capabilities"])
        assert saved.json()["capabilities_by_role"]["processes.read"] == ["team:B"]

        assert sorted(await revoke(user["_id"], "team:B")) == ["processes.read", "processes.write"]
        user = await db.users.find_one({"_id": user["_id"]})
        assert "library.deliver" in caps(user) and not ({"processes.read", "processes.write"} & caps(user))  # lo dado a mano se queda
        assert user["token_version"] >= 2  # retirar cierra las sesiones abiertas
    finally:
        await fx.cleanup()


@pytest.mark.asyncio
async def test_consolidation_leads_use_ledger_and_migration_is_reversible():
    from capability_grants import migrate_consolidation_leads, undo_consolidation_leads_migration
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    designation_ids = []
    try:
        pastora = await fx.account(await fx.person(f"PastoraL{tag}"), "pastora")
        person = await fx.person(f"EncargadaL{tag}")
        await fx.account(person, "lider", capabilities=["processes.read"], permissions_mode="manual")
        user = await db.users.find_one({"person_id": person})
        await db.consolidation_lead_designations.update_many({"active": True, "person_id": {"$nin": [person]}}, {"$set": {"qa_paused": tag, "active": False}})

        created = await pastora.post("/api/consolidation/leads", json={"person_id": person})
        assert created.status_code == 201, created.text
        designation_ids.append(created.json()["designation_id"])
        user = await db.users.find_one({"_id": user["_id"]})
        sources = {item["capability"] for item in user["capability_grants"]}
        assert "processes.read" not in sources and "processes.write" in sources  # lo que tenía a mano no se anota
        assert (await pastora.delete(f"/api/consolidation/leads/{designation_ids[0]}")).status_code == 200
        user = await db.users.find_one({"_id": user["_id"]})
        assert "processes.read" in user["capabilities"] and "processes.write" not in user["capabilities"]

        # Migración: una designación antigua (sin libro) queda anotada; deshacer la devuelve como estaba.
        legacy_id = f"qa-legacy-{tag}"
        designation_ids.append(legacy_id)
        await db.users.update_one({"_id": user["_id"]}, {"$addToSet": {"capabilities": "processes.write"}})
        await db.consolidation_lead_designations.insert_one({"_id": legacy_id, "designation_id": legacy_id, "person_id": person, "user_id": str(user["_id"]), "active": True,
                                                             "granted": ["processes.write"], "designated_at": datetime.now(timezone.utc)})
        saved_migration = await db.core_migrations.find_one({"_id": "capability_grants_consolidation_leads_v1"})
        await db.core_migrations.delete_one({"_id": "capability_grants_consolidation_leads_v1"})
        result = await migrate_consolidation_leads()
        assert result["noted"] >= 1
        user = await db.users.find_one({"_id": user["_id"]})
        assert any(item["source"] == f"consolidation_lead:{legacy_id}" for item in user["capability_grants"])
        await undo_consolidation_leads_migration()
        user = await db.users.find_one({"_id": user["_id"]})
        assert not any(item["source"] == f"consolidation_lead:{legacy_id}" for item in user.get("capability_grants") or [])
        assert "processes.write" in user["capabilities"]  # deshacer no toca los permisos
        await db.core_migrations.delete_one({"_id": "capability_grants_consolidation_leads_v1"})
        if saved_migration:
            await db.core_migrations.insert_one(saved_migration)
    finally:
        await db.consolidation_lead_designations.delete_many({"designation_id": {"$in": designation_ids}})
        await db.consolidation_lead_designations.update_many({"qa_paused": tag}, {"$set": {"active": True}, "$unset": {"qa_paused": ""}})
        await fx.cleanup()
