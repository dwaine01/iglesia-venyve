"""Revisión de producción · «Personas sin líder»: no aparecen las cuentas del sistema/pastorales, ni
líderes o mentores cuyo único expediente es el migrado del Manual antiguo; sí quien tiene un expediente
de Consolidación abierto de verdad. Cada fila dice su origen."""
import uuid
from datetime import datetime, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_people_without_mentor_excludes_staff_and_migrated_team():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    enrollments = []

    async def enroll(person_id, source=None):
        enrollment_id = f"enr-r5-{uuid.uuid4().hex[:8]}"
        enrollments.append(enrollment_id)
        await db.process_enrollments.insert_one({"_id": enrollment_id, "enrollment_id": enrollment_id, "process_key": "consolidation", "definition_version": 2, "source": source,
                                                 "person_id": person_id, "mentor_person_id": None, "status": "active", "created_at": now, "updated_at": now})
    try:
        pastora = await fx.account(await fx.person(f"PastoraR5{tag}"), "pastora")
        admin_person = await fx.person(f"PastorAdmin{tag}")
        await fx.account(admin_person, "admin")
        leader_legacy = await fx.person(f"LiderViejo{tag}")
        await fx.account(leader_legacy, "lider")
        leader_real = await fx.person(f"LiderReal{tag}")
        await fx.account(leader_real, "lider")
        mentor_legacy = await fx.person(f"MentoraVieja{tag}")
        await db.mentor_badges.insert_one({"_id": f"badge-r5-{tag}", "person_id": mentor_legacy, "active": True})
        member_legacy, member = await fx.person(f"MiembroViejo{tag}"), await fx.person(f"Visitante{tag}")
        await enroll(admin_person)
        await enroll(leader_legacy, "legacy_seven_weeks")
        await enroll(leader_real)
        await enroll(mentor_legacy, "legacy_seven_weeks")
        await enroll(member_legacy, "legacy_seven_weeks")
        await enroll(member, "visitor_kiosk")

        rows = {row["canonical_person_id"]: row for row in (await pastora.get("/api/dashboard/role-based")).json()["personas_sin_lider"]}
        assert admin_person not in rows          # cuenta del sistema / pastoral
        assert leader_legacy not in rows and mentor_legacy not in rows  # solo el expediente migrado
        assert rows[leader_real]["origen"] == "Expediente de Consolidación"
        assert rows[member_legacy]["origen"] == "Expediente migrado del Manual antiguo"
        assert rows[member]["motivo"] == "En Consolidación sin mentor"
    finally:
        await db.process_enrollments.delete_many({"enrollment_id": {"$in": enrollments}})
        await db.mentor_badges.delete_many({"_id": f"badge-r5-{tag}"})
        await fx.cleanup()
