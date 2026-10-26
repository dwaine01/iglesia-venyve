"""Auditoría 6/10: el mentor, el líder de grupo frontal y el coordinador general abren el Perfil 360
o el expediente de SU gente (antes: 403), y un mentor ya no puede volverse «mentor de contacto» de
cualquier persona buscándola por nombre."""
import uuid
from datetime import datetime, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_mentor_leader_and_coordinator_reach_their_people():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    enrollment_id, registration_id, group_id = f"enr-rel-{tag}", f"reg-rel-{tag}", f"fg-rel-{tag}"
    try:
        mentor_id, leader_id, coord_id = await fx.person(f"Mentor{tag}"), await fx.person(f"Lider{tag}"), await fx.person(f"Coord{tag}")
        mentor = await fx.account(mentor_id, "persona")
        leader = await fx.account(leader_id, "persona")
        coord = await fx.account(coord_id, "lider", access_level="coordinador_general")
        outsider = await fx.account(await fx.person(f"Ajeno{tag}"), "persona")
        visitor, disciple, member, stranger = [await fx.person(f"{name}{tag}") for name in ("Visitante", "Discipulo", "Integrante", "Desconocido")]
        await db.person_contacts.insert_many([
            {"person_id": visitor, "tipo": "telefono", "valor": "305 555 0101", "valor_normalizado": "3055550101", "es_principal": True, "test_tag": tag},
            {"person_id": stranger, "tipo": "telefono", "valor": "305 555 0199", "valor_normalizado": "3055550199", "es_principal": True, "test_tag": tag},
        ])
        await db.mentor_badges.insert_one({"_id": f"badge-rel-{tag}", "person_id": mentor_id, "active": True})
        # (a) Seguimiento asignado desde la tableta → ve su ficha y su teléfono.
        await db.visitor_registrations.insert_one({"registration_id": registration_id, "visitor_number": f"V-{tag}", "person_id": visitor, "status": "completed",
                                                   "followup": {"status": "assigned", "assigned_person_id": mentor_id}, "created_at": now})
        # (b) Responsable de un expediente terminado → ve su ficha, sin teléfono.
        await db.process_enrollments.insert_one({"_id": enrollment_id, "enrollment_id": enrollment_id, "process_key": "consolidation", "definition_version": 2,
                                                 "person_id": disciple, "responsible_person_id": mentor_id, "status": "completed", "created_at": now})
        # (c) Integrante de la rama que lidera.
        await db.front_groups.insert_one({"front_group_id": group_id, "name": f"Grupo {tag}", "status": "active", "primary_leader_person_id": leader_id})
        await db.front_group_assignments.insert_many([
            {"assignment_id": f"{group_id}-l", "front_group_id": group_id, "person_id": leader_id, "role": "leader", "active": True},
            {"assignment_id": f"{group_id}-m", "front_group_id": group_id, "person_id": member, "role": "member", "active": True},
        ])

        profile = (await mentor.get(f"/api/core/persons/{visitor}/profile")).json()
        assert profile["contact_mentor_view"] is True and profile["header"]["primary_phone"] == "305 555 0101"
        profile = await mentor.get(f"/api/core/persons/{disciple}/profile")
        assert profile.status_code == 200 and "primary_phone" not in profile.json()["header"]
        assert (await mentor.get(f"/api/persons/{visitor}/contact-origin")).status_code == 200
        assert (await leader.get(f"/api/core/persons/{member}/profile")).status_code == 200
        for client, person in ((outsider, visitor), (mentor, member), (leader, visitor), (mentor, stranger)):
            assert (await client.get(f"/api/core/persons/{person}/profile")).status_code == 403

        # El coordinador general abre un expediente fuera de sus grupos (lo ve en el panorama).
        assert (await coord.get(f"/api/processes/consolidation/{enrollment_id}")).status_code == 200
        assert (await outsider.get(f"/api/processes/consolidation/{enrollment_id}")).status_code == 403

        # Escalada cerrada: sin relación, vincular a alguien existente exige su teléfono.
        visit = {"contact_type": "existing", "person_id": stranger}
        assert (await mentor.post("/api/mentorship/outreach/visits", json=visit)).status_code == 422
        assert (await mentor.post("/api/mentorship/outreach/visits", json={**visit, "contact_phone": "3050000000"})).status_code == 422
        assert (await mentor.get(f"/api/persons/{stranger}/contact-origin")).status_code == 403
        created = await mentor.post("/api/mentorship/outreach/visits", json={**visit, "contact_phone": "(305) 555-0199"})
        assert created.status_code == 201, created.text
        # La persona que ya acompaña no necesita el teléfono.
        assert (await mentor.post("/api/mentorship/outreach/visits", json={"contact_type": "existing", "person_id": visitor})).status_code == 201
    finally:
        await db.outreach_visits.delete_many({"person_id": {"$in": fx.person_ids}})
        await db.person_contacts.delete_many({"test_tag": tag})
        await db.mentor_badges.delete_many({"_id": f"badge-rel-{tag}"})
        await db.visitor_registrations.delete_many({"registration_id": registration_id})
        await db.process_enrollments.delete_many({"enrollment_id": enrollment_id})
        await db.front_groups.delete_many({"front_group_id": group_id})
        await db.front_group_assignments.delete_many({"front_group_id": group_id})
        await fx.cleanup()
