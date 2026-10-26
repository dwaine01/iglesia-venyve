"""Auditoría 7/10: una definición por número. El mismo mentor ve la misma cifra en el Panel General,
Supervisar Mi Trabajo, Mis estadísticas y Consolidación; «Total Líderes» cuenta las filas de su tabla;
las cuentas de prueba no cuentan; «hoy» es el día de la iglesia (Nueva York)."""
import uuid
from datetime import datetime, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
SETTINGS = "invasion_report_exclusions"


@pytest.mark.asyncio
async def test_same_numbers_everywhere_and_no_global_leak():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    enrollment_ids = []
    try:
        pastora = await fx.account(await fx.person(f"PastoraD{tag}"), "pastora")
        mentor_id, test_mentor_id = await fx.person(f"MentorD{tag}"), await fx.person(f"PruebaD{tag}")
        mentor = await fx.account(mentor_id, "lider")
        await fx.account(test_mentor_id, "lider")
        await db.app_settings.update_one({"_id": SETTINGS}, {"$addToSet": {"person_ids": test_mentor_id}}, upsert=True)
        for pid in (mentor_id, test_mentor_id):
            await db.mentor_badges.insert_one({"_id": f"badge-d-{tag}-{pid}", "person_id": pid, "active": True})
        people = [await fx.person(f"DiscD{tag}{index}") for index in range(4)]

        def enrollment(person, status, mentor_person=mentor_id, cycle=None):
            enrollment_ids.append(f"enr-d-{tag}-{len(enrollment_ids)}")
            return {"_id": enrollment_ids[-1], "enrollment_id": enrollment_ids[-1], "process_key": "consolidation", "definition_version": 2, "person_id": person,
                    "mentor_person_id": mentor_person, "status": status, "current_stage_key": "visitor_followup", "cycle_id": cycle, "created_at": now, "updated_at": now}
        await db.process_enrollments.insert_many([
            enrollment(people[0], "active"), enrollment(people[0], "paused", cycle=f"ciclo-{tag}"),  # la misma persona dos veces → cuenta 1
            enrollment(people[1], "planned"), enrollment(people[2], "completed"), enrollment(people[3], "cancelled"),
            enrollment(await fx.person(f"DePrueba{tag}"), "active", test_mentor_id),
        ])

        # Panel General: la tarjeta cuenta las mismas filas que la tabla y sin la cuenta de prueba.
        dashboard = (await pastora.get("/api/dashboard/role-based")).json()
        assert dashboard["total_lideres"] == len(dashboard["lideres"])
        assert sum(dashboard["total_lideres_desglose"].values()) == dashboard["total_lideres"]
        assert test_mentor_id not in {row.get("person_id") for row in dashboard["lideres"]}
        row = next(row for row in dashboard["lideres"] if row.get("person_id") == mentor_id)
        assert row["trabajo"]["in_consolidation"] == 2  # abiertas, personas únicas

        # Consolidación: misma carga por mentor; el total no incluye retirados.
        panorama = (await pastora.get("/api/consolidation/panorama", params={"mentor_person_id": mentor_id, "period": "all"})).json()
        assert next(item["active"] for item in panorama["mentor_load"]["items"] if item["mentor_person_id"] == mentor_id) == 2
        assert panorama["figures"]["total"] == 3 and panorama["figures"]["open"] == 2
        listed = (await pastora.get("/api/consolidation/panorama/list/total", params={"mentor_person_id": mentor_id, "period": "all"})).json()
        assert len(listed["items"]) == 3

        # Mis estadísticas = Supervisar Mi Trabajo para el mismo mentor.
        mine = (await mentor.get("/api/core/me/stats")).json()["as_mentor"]
        supervise = next(item for item in (await pastora.get("/api/my-work/mentors")).json()["items"] if item["person_id"] == mentor_id)
        assert mine["consolidation"]["in_consolidation"] == supervise["in_consolidation"] == 2
        assert mine["invasion"]["households_visited"] == supervise["houses_visited"]
        assert mine["invasion"]["unique_persons_contacted"] == supervise["people_contacted"]
        assert "global" not in mine["library"]

        # Líder de una rama sin integrantes: ve ceros, nunca las cifras de toda la iglesia.
        group_id = f"fg-d-{tag}"
        await db.front_groups.insert_one({"front_group_id": group_id, "name": f"Vacío {tag}", "status": "active", "primary_leader_person_id": mentor_id})
        await db.front_group_assignments.insert_one({"assignment_id": f"{group_id}-l", "front_group_id": group_id, "person_id": mentor_id, "role": "leader", "active": True})
        await db.front_group_assignments.update_one({"assignment_id": f"{group_id}-l"}, {"$set": {"person_id": mentor_id}})
        await db.app_settings.update_one({"_id": SETTINGS}, {"$addToSet": {"person_ids": mentor_id}})  # la rama queda sin participantes
        leader_block = (await mentor.get("/api/core/me/stats")).json()["as_leader"]
        assert leader_block["invasion"]["visits_total"] == 0 and leader_block["consolidation"]["accepted"] == 0
        assert leader_block["invasion"]["households_visited"] == 0

        from count_rules import church_day_start_utc
        start = await church_day_start_utc()
        assert start.hour in (4, 5)  # medianoche de Nueva York (EDT/EST)
    finally:
        await db.app_settings.update_one({"_id": SETTINGS}, {"$pull": {"person_ids": {"$in": [test_mentor_id, mentor_id]}}})
        await db.process_enrollments.delete_many({"enrollment_id": {"$in": enrollment_ids}})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-d-{tag}"}})
        await db.front_groups.delete_many({"front_group_id": f"fg-d-{tag}"})
        await db.front_group_assignments.delete_many({"front_group_id": f"fg-d-{tag}"})
        await fx.cleanup()
