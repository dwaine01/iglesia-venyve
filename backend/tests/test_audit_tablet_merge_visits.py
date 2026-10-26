"""Auditoría 10/10: tableta → Consolidación (cierra el seguimiento), fusión guiada y reversible de
personas duplicadas (nada se borra) y visitas de la misma persona en invasiones distintas."""
import uuid
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_tablet_to_consolidation_merge_undo_and_visits_per_invasion():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    registration_id, campaigns = f"reg-m-{tag}", [f"camp-m1-{tag}", f"camp-m2-{tag}"]
    try:
        pastora = await fx.account(await fx.person(f"PastoraM{tag}"), "pastora")
        mentor_id, visitor_id = await fx.person(f"MentorM{tag}"), await fx.person(f"VisitanteM{tag}")
        mentor = await fx.account(mentor_id, "persona")
        outsider = await fx.account(await fx.person(f"AjenoM{tag}"), "persona")
        await db.mentor_badges.insert_one({"_id": f"badge-m-{tag}", "person_id": mentor_id, "active": True})
        await db.visitor_registrations.insert_one({"registration_id": registration_id, "visitor_number": f"V-{tag}", "person_id": visitor_id, "status": "completed",
                                                   "first_name": "Visitante", "last_name": tag, "welcome": {"preferred_name": None}, "service": {"date": "2026-10-25", "label": "Domingo"},
                                                   "match_status": "linked", "contact": {"phone": None, "methods": []}, "visit": {}, "consents": {"followup": True},
                                                   "followup": {"status": "assigned", "assigned_person_id": mentor_id, "results": []}, "created_at": now})

        # Tableta → Consolidación: solo el asignado o quien administra; abre el expediente y cierra el seguimiento.
        assert (await outsider.post(f"/api/visitors/registrations/{registration_id}/to-consolidation")).status_code == 403
        moved = await mentor.post(f"/api/visitors/registrations/{registration_id}/to-consolidation")
        assert moved.status_code == 200, moved.text
        enrollment = await db.process_enrollments.find_one({"enrollment_id": moved.json()["enrollment_id"]}, {"_id": 0})
        assert enrollment["person_id"] == visitor_id and enrollment["mentor_person_id"] == mentor_id and enrollment["status"] == "active"
        registration = await db.visitor_registrations.find_one({"registration_id": registration_id})
        assert registration["followup"]["status"] == "done" and registration["followup"]["enrollment_id"] == enrollment["enrollment_id"]
        again = await mentor.post(f"/api/visitors/registrations/{registration_id}/to-consolidation")
        assert again.json()["reused_enrollment"] is True  # no se duplica

        # Visitas: la misma persona en dos invasiones distintas sí; dos veces en la misma, no.
        for campaign_id in campaigns:
            await db.outreach_campaigns.insert_one({"campaign_id": campaign_id, "name": f"Inv {campaign_id}", "start_date": "2026-10-01", "end_date": "2026-12-31", "assigned_mentor_ids": [mentor_id], "created_at": now})
        for campaign_id in campaigns:
            visit = await mentor.post("/api/mentorship/outreach/visits", json={"contact_type": "existing", "person_id": visitor_id, "campaign_id": campaign_id})
            assert visit.status_code == 201, visit.text
        repeat = await mentor.post("/api/mentorship/outreach/visits", json={"contact_type": "existing", "person_id": visitor_id, "campaign_id": campaigns[0]})
        assert repeat.status_code == 409

        # Fusión: la duplicada pasa todo a la que se conserva, queda archivada (no borrada) y se puede deshacer.
        duplicate_id = await fx.person(f"VisitanteM{tag}")
        await db.person_contacts.insert_one({"person_id": duplicate_id, "tipo": "telefono", "valor": "3055551234", "valor_normalizado": "3055551234", "merge_tag": tag})
        await db.person_contacts.insert_one({"person_id": visitor_id, "tipo": "telefono", "valor": "3055551234", "valor_normalizado": "3055551234", "merge_tag": tag})
        await db.person_attendance.insert_one({"attendance_id": f"att-{tag}", "person_id": duplicate_id, "fecha": "2026-10-25", "estado": "presente"})
        assert (await mentor.get("/api/person-merge/candidates")).status_code == 403
        groups = (await pastora.get("/api/person-merge/candidates")).json()["groups"]
        assert any({visitor_id, duplicate_id} <= {person["person_id"] for person in group["people"]} for group in groups)
        plan = (await pastora.post("/api/person-merge/preview", json={"keep_person_id": visitor_id, "merged_person_id": duplicate_id})).json()
        assert plan["references"].get("person_attendance.person_id") == 1
        assert (await pastora.post("/api/person-merge", json={"keep_person_id": visitor_id, "merged_person_id": duplicate_id})).status_code == 422  # sin motivo
        merged = await pastora.post("/api/person-merge", json={"keep_person_id": visitor_id, "merged_person_id": duplicate_id, "reason": "Mismo teléfono"})
        assert merged.status_code == 200, merged.text
        assert (await db.person_attendance.find_one({"attendance_id": f"att-{tag}"}))["person_id"] == visitor_id
        archived = await db.persons.find_one({"_id": ObjectId(duplicate_id)})
        assert archived["is_archived"] is True and archived["merged_into_person_id"] == visitor_id
        assert await db.person_merges.find_one({"merge_id": merged.json()["merge_id"]}, {"merged_snapshot": 1})  # respaldo completo

        undone = await pastora.post(f"/api/person-merge/{merged.json()['merge_id']}/undo")
        assert undone.status_code == 200 and undone.json()["restored"] >= 2
        assert (await db.person_attendance.find_one({"attendance_id": f"att-{tag}"}))["person_id"] == duplicate_id
        restored = await db.persons.find_one({"_id": ObjectId(duplicate_id)})
        assert not restored.get("is_archived") and not restored.get("merged_into_person_id")
    finally:
        enrollments = await db.process_enrollments.distinct("enrollment_id", {"person_id": {"$in": fx.person_ids}})
        for name in ("process_enrollments", "process_stage_progress", "consolidation_activities", "mentor_assignments", "process_timeline"):
            await db[name].delete_many({"enrollment_id": {"$in": enrollments}})
        await db.outreach_visits.delete_many({"campaign_id": {"$in": campaigns}})
        await db.outreach_campaigns.delete_many({"campaign_id": {"$in": campaigns}})
        await db.visitor_registrations.delete_many({"registration_id": registration_id})
        await db.person_contacts.delete_many({"merge_tag": tag})
        await db.person_attendance.delete_many({"attendance_id": f"att-{tag}"})
        await db.mentor_badges.delete_many({"_id": f"badge-m-{tag}"})
        merges = await db.person_merges.distinct("merge_id", {"keep_person_id": {"$in": fx.person_ids}})
        await db.person_merges.delete_many({"merge_id": {"$in": merges}})
        await db.person_merge_changes.delete_many({"merge_id": {"$in": merges}})
        await fx.cleanup()
