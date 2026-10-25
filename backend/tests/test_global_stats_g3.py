"""Estadísticas Globales G3: invasiones con el MISMO cálculo del Reporte de
invasión, libros desde la bitácora, Grupos Frontales (personas sin duplicar,
líderes sin actividad) y educación/bautismos/niños; permisos por sección."""
import uuid
from datetime import date

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


def door(number, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "opened": True, "contact_level": "conversation", **extra}


@pytest.mark.asyncio
async def test_g3_invasions_books_groups_education():
    await db.front_groups.update_many({"pastoral_main": True}, {"$unset": {"pastoral_main": ""}})
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    book_id = f"bk-{tag}"
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        mentor_id = await fx.person(f"Mentora{tag}")
        mentor = await fx.account(mentor_id, "persona")
        lead = await fx.account(await fx.person(f"Encargada{tag}"), "persona", capabilities=["consolidation.assign"], permissions_mode="manual")
        for section in ("invasions", "books", "groups", "education"):
            assert (await mentor.get(f"/api/global-stats/{section}")).status_code == 403
            assert (await lead.get(f"/api/global-stats/{section}")).status_code == 403
        mentor_user = str((await db.users.find_one({"person_id": mentor_id}, {"_id": 1}))["_id"])
        await db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": mentor_id, "active": True})
        await db.library_books.insert_one({"_id": book_id, "book_id": book_id, "sku": f"T{tag}".upper(), "name": "MCD", "is_active": True, "member_price_cents": 0})
        await pastora.post("/api/library/adjustments", json={"book_id": book_id, "direction": "increase", "quantity": 5, "reason": "Compra"})
        await pastora.post("/api/library/movements", json={"book_id": book_id, "movement_type": "ASSIGNMENT", "quantity": 3, "from_holder": {"type": "warehouse", "id": "central"}, "to_holder": {"type": "user", "id": mentor_user}})
        today = date.today().isoformat()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Invasión {tag}", "location": "Barrio", "start_date": today, "end_date": today, "mentor_person_ids": [mentor_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await mentor.put(f"{base}/my-street", json={"street_name": "Calle Uno"})
        await mentor.post(f"{base}/doors", json=door("1", books=[{"book": book_id, "quantity": 1}], person={"contact_name": f"Luz {tag}"}, followup="yes"))
        await mentor.post(f"{base}/doors", json=door("3", opened=False, contact_level=None))

        inv = (await pastora.get("/api/global-stats/invasions", params={"period": "today"})).json()
        row = next(item for item in inv["items"] if item["campaign_id"] == campaign_id)
        report = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()["summary"]["key_figures"]
        assert (row["houses_visited"], row["people_reached"], row["wants_followup"]) == (report["houses_visited"], report["people_reached"], report["wants_followup"]) == (2, 1, 1)
        assert row["books"] == 1 and row["present"].endswith("/reporte/presentar?dia=1")

        books = (await pastora.get("/api/global-stats/books", params={"period": "today"})).json()
        mine = next(item for item in books["by_mentor"] if item["name"] == f"Mentora{tag} Etapa5C")
        assert (mine["received"], mine["delivered"], mine["available"]) == (3, 1, 2)
        assert {item["key"]: item["value"] for item in books["cards"]}["delivered"] >= 1
        assert any(item["name"] == f"Invasión {tag}" and item["delivered"] == 1 for item in books["by_campaign"])

        # Grupos Frontales: la persona que está en dos grupos cuenta una vez; líder sin actividad.
        group = (await pastora.put("/api/pastoral-front-group", json={"name": f"Casa {tag}"})).json()["group"]
        idle_id, other = await fx.person(f"Quieto{tag}"), await fx.person(f"Otro{tag}")
        await pastora.put(f"/api/front-groups/{group['front_group_id']}/roster", json={"entries": [{"person_ids": [mentor_id, idle_id]}, {"person_ids": [other]}]})
        designated = await pastora.post("/api/front-group-structure/form", json={"parent_group_id": group["front_group_id"], "person_ids": [idle_id, mentor_id]})
        assert designated.status_code == 200
        groups = (await pastora.get("/api/global-stats/groups", params={"period": "today"})).json()
        assert groups["root"]["name"] == f"Casa {tag}" and groups["root"]["people_branch"] == 3
        assert any(item["person_id"] == idle_id for item in groups["idle_leaders"]) and not any(item["person_id"] == mentor_id for item in groups["idle_leaders"])
        assert any(item["status"] == "Por formar" for item in groups["branches"])

        # Educación y procesos: bautismos y presentación de niños con fecha en el período.
        baptized, child = await fx.person(f"Bautizado{tag}"), await fx.person(f"Nino{tag}")
        await db.person_baptisms.insert_one({"_id": f"bap-{tag}", "person_id": baptized, "baptized": True, "baptism_date": "2004-06-12", "status": "completed"})
        await db.person_dedications.insert_one({"_id": f"ded-{tag}", "child_person_id": child, "completed": True, "dedication_date": "2004-06-13"})
        june = {"period": "custom", "date_from": "2004-06-01", "date_to": "2004-06-30"}
        edu = {item["key"]: item for item in (await pastora.get("/api/global-stats/education", params=june)).json()["cards"]}
        assert edu["baptized"]["value"] == 1 and edu["dedications"]["value"] == 1
        assert edu["certificates"]["empty_reason"] == "No se emitieron certificados en este período."
        assert (await pastora.get("/api/global-stats/access")).json()["sections"]["invasions"] is True
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns", "library_movements"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.library_movements.delete_many({"book_id": book_id})
        await db.library_books.delete_many({"_id": book_id})
        await db.library_holdings.delete_many({"book_id": book_id})
        await db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await db.person_baptisms.delete_many({"_id": f"bap-{tag}"})
        await db.person_dedications.delete_many({"_id": f"ded-{tag}"})
        groups_ids = await db.front_groups.distinct("front_group_id", {"$or": [{"name": {"$regex": tag}}, {"primary_leader_person_id": {"$in": fx.person_ids}}]})
        await db.front_groups.delete_many({"front_group_id": {"$in": groups_ids}})
        await db.front_group_assignments.delete_many({"front_group_id": {"$in": groups_ids}})
        await fx.cleanup()
