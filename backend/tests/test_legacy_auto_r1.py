"""R1: el servidor ya no crea expedientes solos desde el Manual viejo en cada arranque (reversible), y el
pastor/coordinador ven en solo lectura cuántos se crearon, cuántos se recrearon y cuántos de «Personas sin
líder» están ahí solo por eso."""
import uuid
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_legacy_auto_creation_report_and_switch_off():
    from legacy_auto_report import SETTING_ID, auto_migration_enabled, legacy_report
    from process_engine import migrate_legacy_processes
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    legacy_ids = []
    saved_setting = await db.app_settings.find_one({"_id": SETTING_ID})
    try:
        pastora = await fx.account(await fx.person(f"PastoraR1{tag}"), "pastora")
        coord = await fx.account(await fx.person(f"CoordR1{tag}"), "lider", access_level="coordinador_general")
        member = await fx.account(await fx.person(f"MiembroR1{tag}"), "persona")
        maria, juan = await fx.person(f"MariaR1{tag}"), await fx.person(f"JuanR1{tag}")
        for person_id, estado in ((maria, "en_proceso"), (juan, "graduado")):
            oid = ObjectId()
            legacy_ids.append(oid)
            await db.people.insert_one({"_id": oid, "canonical_person_id": person_id, "nombre": "QA", "estado": estado, "semana_actual": 2, "leader_id": None, "created_at": datetime.now(timezone.utc)})
        before = await legacy_report()

        # Cómo era: dos «arranques» seguidos. El graduado recibe un expediente completado NUEVO cada vez; si el
        # abierto de María se cierra, el siguiente arranque le crea otro (sin mentor → «Personas sin líder»).
        await migrate_legacy_processes(db, "system:startup")
        await db.process_enrollments.update_many({"person_id": maria, "process_key": "consolidation"}, {"$set": {"status": "archived"}})
        await migrate_legacy_processes(db, "system:startup")
        assert await db.process_enrollments.count_documents({"person_id": juan, "process_key": "consolidation", "source": "legacy_people"}) == 2
        assert await db.process_enrollments.count_documents({"person_id": maria, "process_key": "consolidation", "source": "legacy_people"}) == 2

        report = (await coord.get("/api/processes/legacy-auto/report")).json()
        assert report["total_auto_created"] >= before["total_auto_created"] + 6
        assert report["people_recreated"] >= before["people_recreated"] + 2
        assert report["people_without_leader_only_legacy"] >= before["people_without_leader_only_legacy"] + 1
        assert (await member.get("/api/processes/legacy-auto/report")).status_code == 403

        # Apagado por defecto (decisión del dueño) y reversible solo por el pastor.
        await db.app_settings.delete_one({"_id": SETTING_ID})
        assert await auto_migration_enabled() is False
        assert (await coord.put("/api/processes/legacy-auto/setting", json={"enabled": True})).status_code == 403
        on = (await pastora.put("/api/processes/legacy-auto/setting", json={"enabled": True})).json()
        assert on["auto_migration_enabled"] is True
        off = (await pastora.put("/api/processes/legacy-auto/setting", json={"enabled": False})).json()
        assert off["auto_migration_enabled"] is False and off["created_after_disabled"] == 0
        assert len((await db.app_settings.find_one({"_id": SETTING_ID}))["history"]) == 2
    finally:
        await db.process_enrollments.delete_many({"person_id": {"$in": fx.person_ids}})
        await db.people.delete_many({"_id": {"$in": legacy_ids}})
        await db.app_settings.delete_one({"_id": SETTING_ID})
        if saved_setting:
            await db.app_settings.insert_one(saved_setting)
        await fx.cleanup()
