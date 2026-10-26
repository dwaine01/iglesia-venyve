"""Auditoría 5/10: eliminar la cuenta de un líder, quitar la insignia de mentor o archivar su Perfil 360
ya no deja trabajo huérfano. La vista previa muestra lo que tiene; si tiene algo hay que elegir a qué
mentor pasarlo; nada se borra (la cuenta queda desactivada)."""
import uuid
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


async def seed_work(tag: str, mentor_id: str, mentor_user_id: str) -> dict:
    now = datetime.now(timezone.utc)
    disciple_id = str(ObjectId())
    await db.persons.insert_one({"_id": ObjectId(disciple_id), "nombre": f"Discipulo{tag}", "apellido": "Handover", "search_key": f"discipulo{tag} handover",
                                 "idempotency_key": f"handover-{disciple_id}", "created_at": now, "updated_at": now})
    enrollment_id, other_enrollment = f"enr-{tag}", f"enr-tr-{tag}"
    await db.process_enrollments.insert_many([
        {"_id": enrollment_id, "enrollment_id": enrollment_id, "process_key": "consolidation", "person_id": disciple_id, "mentor_person_id": mentor_id,
         "status": "active", "current_stage_key": "visitor_followup", "created_at": now},
        {"_id": other_enrollment, "enrollment_id": other_enrollment, "process_key": "consolidation", "person_id": f"otra-{tag}", "mentor_person_id": None,
         "status": "active", "transfer_request": {"status": "pending", "to_person_id": mentor_id, "requested_at": now}, "created_at": now},
    ])
    registration_id = f"reg-{tag}"
    await db.visitor_registrations.insert_one({"registration_id": registration_id, "status": "completed", "first_name": "Visitante", "last_name": tag,
                                               "followup": {"status": "assigned", "assigned_person_id": mentor_id}, "created_at": now})
    book_id = f"book-{tag}"
    await db.library_books.insert_one({"book_id": book_id, "name": f"Libro {tag}", "is_active": True, "created_at": now})
    await db.library_holdings.insert_one({"_id": str(uuid.uuid4()), "book_id": book_id, "holder_type": "user", "holder_id": mentor_user_id, "quantity_on_hand": 3, "reserved_qty": 0})
    return {"disciple_id": disciple_id, "enrollment_id": enrollment_id, "transfer_enrollment": other_enrollment, "registration_id": registration_id, "book_id": book_id}


async def cleanup(tag: str, seeded: list[dict]) -> None:
    for item in seeded:
        await db.persons.delete_one({"_id": ObjectId(item["disciple_id"])})
        await db.process_enrollments.delete_many({"enrollment_id": {"$in": [item["enrollment_id"], item["transfer_enrollment"]]}})
        await db.mentor_assignments.delete_many({"enrollment_id": item["enrollment_id"]})
        await db.visitor_registrations.delete_one({"registration_id": item["registration_id"]})
        await db.library_books.delete_one({"book_id": item["book_id"]})
        await db.library_holdings.delete_many({"book_id": item["book_id"]})
        await db.library_movements.delete_many({"book_id": item["book_id"]})
    await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})


@pytest.mark.asyncio
async def test_leader_delete_requires_handover_and_keeps_the_account():
    fx, tag, seeded = Fixture(), uuid.uuid4().hex[:8], []
    try:
        pastora = await fx.account(await fx.person(f"PastoraH{tag}"), "pastora")
        leader_id, heir_id = await fx.person(f"LiderH{tag}"), await fx.person(f"HerederaH{tag}")
        await fx.account(leader_id, "lider")
        await fx.account(heir_id, "persona")
        for pid in (leader_id, heir_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{pid}", "person_id": pid, "active": True})
        leader_user = await db.users.find_one({"person_id": leader_id})
        heir_user = await db.users.find_one({"person_id": heir_id})
        work = await seed_work(tag, leader_id, str(leader_user["_id"]))
        seeded.append(work)
        user_id = str(leader_user["_id"])

        preview = (await pastora.get(f"/api/pastor/leaders/{user_id}/delete-preview")).json()["pending_work"]
        assert preview["blocking"] is True
        assert preview["counts"]["disciples"] == 1 and preview["counts"]["visitor_followups"] == 1
        assert preview["counts"]["transfers_pending"] == 1 and preview["counts"]["books"] == 3
        assert "_items" not in preview  # solo el resumen público

        name = leader_user["nombre"]
        blocked = await pastora.request("DELETE", f"/api/pastor/leaders/{user_id}", json={"confirm_name": name})
        assert blocked.status_code == 409 and blocked.json()["detail"]["pending_work"]["total"] >= 6
        assert await db.users.count_documents({"_id": leader_user["_id"], "is_active": {"$ne": False}}) == 1  # nada cambió

        bad_target = await pastora.request("DELETE", f"/api/pastor/leaders/{user_id}", json={"confirm_name": name, "reassign_to_person_id": leader_id})
        assert bad_target.status_code == 422

        done = await pastora.request("DELETE", f"/api/pastor/leaders/{user_id}", json={"confirm_name": name, "reassign_to_person_id": heir_id})
        assert done.status_code == 200, done.text
        assert done.json()["handover"]["books_moved"] == 3
        assert (await db.process_enrollments.find_one({"enrollment_id": work["enrollment_id"]}))["mentor_person_id"] == heir_id
        assert (await db.process_enrollments.find_one({"enrollment_id": work["transfer_enrollment"]}))["transfer_request"]["to_person_id"] == heir_id
        assert (await db.visitor_registrations.find_one({"registration_id": work["registration_id"]}))["followup"]["assigned_person_id"] == heir_id
        assert (await db.library_holdings.find_one({"book_id": work["book_id"], "holder_id": str(heir_user["_id"])}))["quantity_on_hand"] == 3
        # La cuenta no se borra: queda desactivada, sin acceso y fuera de la lista de líderes.
        kept = await db.users.find_one({"_id": leader_user["_id"]})
        assert kept and kept["is_active"] is False and kept.get("account_deleted_at")
        board = (await pastora.get("/api/dashboard/role-based")).json()
        assert all(row.get("_id") != user_id for row in board.get("lideres", []))
        assert (await pastora.get(f"/api/pastor/leaders/{user_id}/delete-preview")).status_code == 404
    finally:
        await cleanup(tag, seeded)
        await fx.cleanup()


@pytest.mark.asyncio
async def test_badge_removal_and_archive_require_handover():
    fx, tag, seeded = Fixture(), uuid.uuid4().hex[:8], []
    try:
        pastora = await fx.account(await fx.person(f"PastoraB{tag}"), "pastora")
        mentor_id, heir_id = await fx.person(f"MentorB{tag}"), await fx.person(f"HerederoB{tag}")
        await fx.account(mentor_id, "persona")
        await fx.account(heir_id, "persona")
        for pid in (mentor_id, heir_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{pid}", "person_id": pid, "active": True})
        mentor_user = await db.users.find_one({"person_id": mentor_id})
        work = await seed_work(tag, mentor_id, str(mentor_user["_id"]))
        seeded.append(work)

        archive = await pastora.delete(f"/api/core/persons/{mentor_id}")
        assert archive.status_code == 409 and archive.json()["detail"]["pending_work"]["counts"]["disciples"] == 1
        blocked = await pastora.put(f"/api/mentorship/badge/{mentor_id}", json={"active": False})
        assert blocked.status_code == 409
        assert (await db.mentor_badges.find_one({"person_id": mentor_id}))["active"] is True  # la insignia sigue

        done = await pastora.put(f"/api/mentorship/badge/{mentor_id}", json={"active": False, "reassign_to_person_id": heir_id})
        assert done.status_code == 200, done.text
        assert done.json()["handover"]["visitor_followups"] == 1
        assert (await db.mentor_badges.find_one({"person_id": mentor_id}))["active"] is False
        assert (await db.process_enrollments.find_one({"enrollment_id": work["enrollment_id"]}))["mentor_person_id"] == heir_id
        # Sin pendientes ya se puede archivar sin elegir a nadie.
        assert (await pastora.delete(f"/api/core/persons/{mentor_id}")).status_code == 200
    finally:
        await cleanup(tag, seeded)
        await fx.cleanup()
