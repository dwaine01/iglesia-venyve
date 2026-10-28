"""R2b · «Parado» = 7 días sin actividad (regla única) y «Personas sin líder» igual en el panorama y el Panel General."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server
from count_rules import STALLED_DAYS, is_stalled, stalled_by_mentor  # noqa: E402 (después de cargar el servidor)
from process_engine import evaluate_alerts

db = server.db


def test_stalled_rule_edges():
    now = datetime.now(timezone.utc)
    assert STALLED_DAYS == 7
    base = {"status": "active", "current_stage_key": "mcd"}
    assert is_stalled({**base, "created_at": now - timedelta(days=7, minutes=1)}, None, now)
    assert not is_stalled({**base, "created_at": now - timedelta(days=6, hours=23)}, None, now)
    # Una actividad realizada, una tarea o un contacto recientes lo sacan de «parado».
    assert not is_stalled({**base, "created_at": now - timedelta(days=30)}, now - timedelta(days=2), now)
    assert not is_stalled({**base, "created_at": now - timedelta(days=30), "last_activity_at": now - timedelta(days=1)}, None, now)
    # Pausados y los que esperan la fecha de graduación no cuentan.
    assert not is_stalled({**base, "status": "paused", "created_at": now - timedelta(days=30)}, None, now)
    assert not is_stalled({**base, "current_stage_key": "graduation", "created_at": now - timedelta(days=30)}, None, now)


@pytest.mark.asyncio
async def test_stalled_in_panorama_mentor_rows_alert_and_without_leader_matches():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    ids = []
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        mentor_id = await fx.person(f"Mentor{tag}")
        await fx.account(mentor_id, "persona")
        await db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": mentor_id, "active": True})
        people = [await fx.person(f"P{index}{tag}") for index in range(4)]
        specs = [  # (mentor, creado hace, última actividad del expediente)
            (mentor_id, timedelta(days=20), now - timedelta(days=8)),   # parado
            (mentor_id, timedelta(days=20), now - timedelta(days=2)),   # al día
            (mentor_id, timedelta(days=20), None),                      # parado salvo por la actividad realizada de abajo
            (None, timedelta(days=3), None),                            # sin líder
        ]
        for index, (mentor, age, last) in enumerate(specs):
            enrollment_id = f"enr-{tag}-{index}"
            ids.append(enrollment_id)
            await db.process_enrollments.insert_one({"_id": enrollment_id, "enrollment_id": enrollment_id, "process_key": "consolidation", "definition_version": 2, "person_id": people[index],
                                                     "mentor_person_id": mentor, "current_stage_key": "mcd", "status": "active", "created_at": now - age, "last_activity_at": last,
                                                     "next_action_at": now + timedelta(days=1), "front_group_id": None})
        await db.consolidation_activities.insert_one({"_id": f"act-{tag}", "activity_id": f"act-{tag}", "enrollment_id": ids[2], "status": "done", "completed_at": now - timedelta(days=1)})

        assert (await stalled_by_mentor([mentor_id]))[mentor_id] == 1
        panorama = (await pastora.get("/api/consolidation/panorama", params={"mentor_person_id": mentor_id})).json()
        assert panorama["figures"]["stalled"] == 1 and panorama["stalled_days"] == 7
        listed = (await pastora.get("/api/consolidation/panorama/list/stalled", params={"mentor_person_id": mentor_id})).json()
        assert [row["enrollment_id"] for row in listed["items"]] == [ids[0]]

        # «Sin líder»: el panorama de toda la iglesia y el Panel General dan la misma cifra y la misma lista.
        whole = (await pastora.get("/api/consolidation/panorama")).json()
        dashboard = (await pastora.get("/api/dashboard/role-based")).json()
        assert whole["figures"]["without_leader"] == len(dashboard["personas_sin_lider"])
        rows = (await pastora.get("/api/consolidation/panorama/list/without_leader", params={"limit": 200})).json()
        assert rows["total"] == whole["figures"]["without_leader"]
        mine = next(row for row in rows["items"] if row["person_id"] == people[3])
        assert mine["enrollment_id"] == ids[3] and mine["reason"] == "En Consolidación sin mentor"
        assert people[0] not in {row["person_id"] for row in rows["items"]}

        # La alerta «Proceso sin avance» usa la misma regla en Consolidación.
        await evaluate_alerts(db, force=True)
        alerts = {doc["enrollment_id"] async for doc in db.process_alerts.find({"enrollment_id": {"$in": ids}, "rule_key": "stage_stalled", "status": "open"})}
        assert ids[0] in alerts and ids[1] not in alerts and ids[2] not in alerts
    finally:
        await db.process_alerts.delete_many({"enrollment_id": {"$in": ids}})
        await db.process_enrollments.delete_many({"enrollment_id": {"$in": ids}})
        await db.consolidation_activities.delete_many({"_id": f"act-{tag}"})
        await db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await fx.cleanup()
