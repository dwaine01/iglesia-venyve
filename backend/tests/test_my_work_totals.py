"""Supervisar Mi Trabajo: totales reales (no solo pendientes), «Mis personas»
con TODAS las personas contactadas o con libro, «Mis viviendas» con filtro,
inventario por mentor y migración idempotente de visitas antiguas (caso
Luis: 9 visitas «asignadas», 8 con MCD entregado desde el perfil)."""
import uuid
from datetime import date, datetime, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db
NAMES = ("Ernesto", "Karla", "Elvido", "Selena", "Yadira", "Filibetto", "Manuel", "Paulo", "Alvin")


@pytest.mark.asyncio
async def test_legacy_visits_totals_people_households_and_inventory():
    from outreach_doors import migrate_legacy_visits
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = f"camp-{tag}"
    book_id = f"bk-{tag}"
    people = {}
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        luis_id = await fx.person(f"Luis{tag}")
        luis = await fx.account(luis_id, "persona")
        luis_user = str((await db.users.find_one({"person_id": luis_id}, {"_id": 1}))["_id"])
        await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{luis_id}", "person_id": luis_id, "active": True})
        await db.outreach_campaigns.insert_one({"_id": campaign_id, "campaign_id": campaign_id, "name": f"Invasión {tag}", "status": "active", "assigned_mentor_ids": [luis_id],
                                                "start_date": date.today().isoformat(), "end_date": date.today().isoformat()})
        await db.library_books.insert_one({"_id": book_id, "book_id": book_id, "sku": f"T{tag}".upper(), "name": "MCD", "is_active": True, "member_price_cents": 0})
        await pastora.post("/api/library/adjustments", json={"book_id": book_id, "direction": "increase", "quantity": 10, "reason": "Compra"})
        await pastora.post("/api/library/movements", json={"book_id": book_id, "movement_type": "ASSIGNMENT", "quantity": 10, "from_holder": {"type": "warehouse", "id": "central"}, "to_holder": {"type": "user", "id": luis_user}})
        now = datetime.now(timezone.utc)
        # Visitas antiguas (formulario Hogar): 8 quedaron «asignadas» aunque entregó el MCD; Alvin, «visitada».
        for index, name in enumerate(NAMES):
            people[name] = await fx.person(f"{name}{tag}")
            visit_id = f"v-{tag}-{index}"
            await db.outreach_visits.insert_one({"_id": visit_id, "visit_id": visit_id, "campaign_id": campaign_id, "mentor_person_id": luis_id, "contact_type": "existing",
                                                 "person_id": people[name], "contact_name": name, "status": "visited" if name == "Alvin" else "assigned",
                                                 "address_line1": f"{4240 + index} Lincoln Park", "visit_date": "2026-10-24", "household_id": None, "visit_event_id": None,
                                                 "enrollment_id": None, "archived": False, "created_at": now, "updated_at": now})
            if name != "Alvin":
                delivered = await luis.post(f"/api/library/persons/{people[name]}/deliver", json={"book_id": book_id, "quantity": 1, "process_key": "outreach_invasion", "payment_status": "no_aplica"})
                assert delivered.status_code == 201, delivered.text
        # Antes: el selector decía 0 viviendas · 0 personas.
        mentors = {row["person_id"]: row for row in (await pastora.get("/api/my-work/mentors")).json()["items"]}
        assert mentors[luis_id]["people_contacted"] == 9 and mentors[luis_id]["books_delivered"] == 8

        first = await migrate_legacy_visits()
        again = await migrate_legacy_visits()
        assert first["households"] >= 9 and first["events"] >= 9 and again["households"] == 0 and again["events"] == 0  # idempotente
        assert await db.outreach_households.count_documents({"campaign_id": campaign_id}) == 9
        assert await db.outreach_visit_events.count_documents({"campaign_id": campaign_id}) == 9
        assert await db.outreach_visits.count_documents({"campaign_id": campaign_id}) == 9  # nada se borra ni se duplica
        # Estado real en producción: la migración anterior creó la vivienda pero no el intento (visita «asignada»).
        legacy = await db.outreach_visits.find_one({"person_id": people["Elvido"]}, {"_id": 0})
        await db.outreach_visit_events.delete_one({"visit_event_id": legacy["visit_event_id"]})
        await db.outreach_visits.update_one({"visit_id": legacy["visit_id"]}, {"$set": {"visit_event_id": None}})
        assert (await migrate_legacy_visits())["events"] == 1 and (await migrate_legacy_visits())["events"] == 0
        house = await db.outreach_households.find_one({"household_id": legacy["household_id"]}, {"_id": 0})
        assert house["attempts_count"] == 1 and house["books_total"] == 1 and house["door_status"] == "opened"

        row = {item["person_id"]: item for item in (await pastora.get("/api/my-work/mentors")).json()["items"]}[luis_id]
        assert (row["houses_visited"], row["people_contacted"], row["books_delivered"]) == (9, 9, 8)
        assert row["inventory"] == {"received": 10, "delivered": 8, "available": 2}
        assert (row["households"], row["people"]) == (9, 9)

        summary = (await luis.get("/api/my-work/summary", params={"period": "all"})).json()
        assert summary["totals"]["houses_visited"] == 9 and summary["figures"]["visited"] == 9
        assert any(notice["key"] == "no_next_action" and "9 persona(s)" in notice["text"] for notice in summary["notices"])

        people_view = (await luis.get("/api/my-work/people")).json()
        assert people_view["total"] == 9 and people_view["counts"]["no_next"] == 9
        elvido = next(item for item in people_view["items"] if item["person_id"] == people["Elvido"])
        assert elvido["status_label"] == "Contactada · sin próxima atención" and elvido["books"] == 1 and elvido["can_schedule"] and "Lincoln Park" in elvido["address"]
        assert elvido["campaign_name"] == f"Invasión {tag}"

        houses = (await luis.get("/api/my-work/households", params={"state": "visited"})).json()
        assert houses["total"] == 9 and all(item["attempts_count"] == 1 for item in houses["items"])
        assert (await luis.get("/api/my-work/households", params={"state": "pending"})).json()["total"] == 0
        assert (await luis.get("/api/my-work/households", params={"state": "all"})).json()["total"] == 9

        # Panel General › Líderes y su Desempeño y su detalle: MISMAS cifras que Supervisar.
        dashboard = (await pastora.get("/api/dashboard/role-based")).json()
        luis_row = next(item for item in dashboard["lideres"] if item.get("person_id") == luis_id)
        assert (luis_row["trabajo"]["houses_visited"], luis_row["trabajo"]["people_contacted"], luis_row["trabajo"]["books_delivered"]) == (9, 9, 8)
        assert luis_row["trabajo"]["today"]["books"] == 8 and luis_row["trabajo"]["work_status_label"] == "Trabajó hoy"
        detail = (await pastora.get("/api/my-work/leader-detail", params={"mentor_person_id": luis_id})).json()
        assert detail["summary"]["total"] == {"houses": 9, "people": 9, "books": 8, "in_consolidation": 0, "stalled": 0, "pending": 0}
        assert detail["summary"]["today"]["books"] == 8 and sum(1 for item in detail["timeline"] if item["kind"] == "book") == 8
        assert all(item["time"] for item in detail["timeline"]) and any("Elvido" in (item.get("detail") or "") for item in detail["timeline"])
        assert detail["inventory"] == row["inventory"]
        assert (await luis.get("/api/my-work/leader-detail", params={"mentor_person_id": luis_id})).status_code == 200  # el propio mentor

        # Programar el seguimiento → «Seguimiento aceptado»; un expediente → «En Consolidación».
        visit_id = elvido["visit_id"]
        assert (await luis.put(f"/api/mentorship/outreach/visits/{visit_id}/followup", json={"accepted": True, "next_action": "Llamar por teléfono", "next_action_date": date.today().isoformat()})).status_code == 200
        eid = f"mwt-{tag}"
        await db.process_enrollments.insert_one({"_id": eid, "enrollment_id": eid, "process_key": "consolidation", "person_id": people["Karla"], "status": "active", "mentor_person_id": luis_id,
                                                 "current_stage_key": "mcd", "created_at": now, "updated_at": now, "source": f"test-{tag}"})
        status = {item["person_id"]: item["status_label"] for item in (await luis.get("/api/my-work/people")).json()["items"]}
        assert status[people["Elvido"]] == "Seguimiento aceptado" and status[people["Karla"]] == "En Consolidación"
        # Permisos: el mentor ve solo lo suyo.
        other = await fx.account(await fx.person(f"Otro{tag}"), "persona")
        assert (await other.get("/api/my-work/people", params={"mentor_person_id": luis_id})).status_code == 403
        assert (await other.get("/api/my-work/households", params={"mentor_person_id": luis_id})).status_code == 403
        assert (await other.get("/api/my-work/leader-detail", params={"mentor_person_id": luis_id})).status_code == 403
        assert (await other.get("/api/dashboard/role-based")).json().get("rol") != "pastor"
    finally:
        for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_campaigns", "library_movements"):
            await db[collection].delete_many({"campaign_id": campaign_id})
        await db.outreach_visits.delete_many({"visit_id": {"$regex": f"^v-{tag}"}})
        await db.process_enrollments.delete_many({"source": f"test-{tag}"})
        await db.library_movements.delete_many({"book_id": book_id})
        await db.library_books.delete_many({"_id": book_id})
        await db.library_holdings.delete_many({"book_id": book_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
