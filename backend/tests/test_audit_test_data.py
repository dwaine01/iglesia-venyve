"""Auditoría 8/10: marca `is_test` reversible, inventario de solo lectura, invasión archivada (sin
borrar) y «Personas sin líder» calculada desde Persona 360 (baja sola al asignar mentor)."""
import uuid
from datetime import datetime, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_mark_archive_inventory_and_people_without_mentor():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    campaign_id, enrollment_id = f"camp-t-{tag}", f"enr-t-{tag}"
    try:
        pastora = await fx.account(await fx.person(f"PastoraT{tag}"), "pastora")
        member = await fx.account(await fx.person(f"MiembroT{tag}"), "persona")
        fake = await fx.person(f"Prueba {tag}")
        orphan, mentor_id = await fx.person(f"Huerfana{tag}"), await fx.person(f"MentorT{tag}")
        await db.outreach_campaigns.insert_one({"campaign_id": campaign_id, "name": f"Prueba de invasion {tag}", "start_date": "2026-10-24", "end_date": "2026-10-24", "created_at": now})
        await db.process_enrollments.insert_one({"_id": enrollment_id, "enrollment_id": enrollment_id, "process_key": "consolidation", "definition_version": 2,
                                                 "person_id": orphan, "mentor_person_id": None, "status": "active", "created_at": now, "updated_at": now})

        assert (await member.get("/api/test-data/inventory")).status_code == 403
        before = {name: await db[name].count_documents({}) for name in ("persons", "outreach_campaigns", "users")}
        inventory = (await pastora.get("/api/test-data/inventory")).json()
        assert {name: await db[name].count_documents({}) for name in before} == before  # solo lectura
        assert fake in {row["person_id"] for row in inventory["people"]}
        assert campaign_id in {row["campaign_id"] for row in inventory["campaigns"]}

        # Marcar saca de las cifras; quitar la marca la devuelve. Nada se borra.
        from report_period import excluded_person_ids
        marked = await pastora.post("/api/test-data/mark", json={"kind": "person", "ids": [fake], "is_test": True, "reason": "Prueba QA"})
        assert marked.status_code == 200 and marked.json()["changed"] == 1, marked.text
        assert fake in await excluded_person_ids()
        await pastora.post("/api/test-data/mark", json={"kind": "person", "ids": [fake], "is_test": False, "reason": "Prueba QA"})
        assert fake not in await excluded_person_ids() and await db.persons.count_documents({"nombre": f"Prueba {tag}"}) == 1
        assert await db.test_data_marks.count_documents({"target_id": fake}) == 2

        # Archivar la invasión de prueba (reversible): sale de «Reporte para la pastora».
        await pastora.post("/api/test-data/mark", json={"kind": "campaign", "ids": [campaign_id], "is_test": True, "reason": "Prueba QA"})
        assert (await pastora.post(f"/api/test-data/campaigns/{campaign_id}/archive", json={"archived": True, "reason": "Invasión de prueba"})).status_code == 200
        campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id})
        assert campaign["archived"] is True and campaign["is_test"] is True
        presentable = (await pastora.get("/api/invasions/report-settings/presentable")).json()
        assert campaign_id not in {item["campaign_id"] for item in presentable.get("items", [])}
        await pastora.post(f"/api/test-data/campaigns/{campaign_id}/archive", json={"archived": False, "reason": "Deshacer"})
        assert (await db.outreach_campaigns.find_one({"campaign_id": campaign_id}))["archived"] is False

        # «Personas sin líder»: aparece sin mentor y baja sola en cuanto tiene un mentor activo.
        sin_lider = (await pastora.get("/api/dashboard/role-based")).json()["personas_sin_lider"]
        assert orphan in {row["canonical_person_id"] for row in sin_lider}
        await db.mentor_badges.insert_one({"_id": f"badge-t-{tag}", "person_id": mentor_id, "active": True})
        await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {"mentor_person_id": mentor_id}})
        sin_lider = (await pastora.get("/api/dashboard/role-based")).json()["personas_sin_lider"]
        assert orphan not in {row["canonical_person_id"] for row in sin_lider}
    finally:
        await db.outreach_campaigns.delete_many({"campaign_id": campaign_id})
        await db.process_enrollments.delete_many({"enrollment_id": enrollment_id})
        await db.mentor_badges.delete_many({"_id": f"badge-t-{tag}"})
        await db.test_data_marks.delete_many({"target_id": {"$in": [campaign_id] + fx.person_ids}})
        await fx.cleanup()
