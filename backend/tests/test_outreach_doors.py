"""Puerta a puerta (tramo 1): calle activa, vivienda por número/apartamento,
intento con pocos toques, idempotencia del doble toque, libros sin bloquear,
permisos y migración segura de visitas anteriores."""
import uuid
from datetime import date, datetime, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero (orden de importación)
from outreach_doors import door_key, migrate_legacy_visits

db = server.db


def door(number, unit=None, **extra):
    return {"client_request_id": f"req-{uuid.uuid4().hex}", "house_number": number, "unit": unit, "opened": False, **extra}


@pytest.mark.asyncio
async def test_street_doors_attempts_books_and_permissions():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    book_id = f"bk-{tag}"
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, beto_id, outsider_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto", "Ajeno")]
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        outsider = await fx.account(outsider_id, "persona")
        for person_id in (ana_id, beto_id, outsider_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        today = date.today().isoformat()
        created = await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today, "end_date": today, "mentor_person_ids": [ana_id, beto_id]})
        campaign_id = created.json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"

        # Sin calle activa no se puede; el ajeno (fuera del roster) tampoco.
        assert (await ana.post(f"{base}/doors", json=door("12"))).status_code == 422
        assert (await outsider.put(f"{base}/my-street", json={"street_name": "Calle 18"})).status_code == 403
        street = (await ana.put(f"{base}/my-street", json={"street_name": "Calle 18", "latitude": 41.85, "longitude": -87.66, "location_source": "gps"})).json()
        assert street["active_street"]["street_name"] == "Calle 18"
        assert (await ana.get(f"{base}/my-street")).json()["active_street"]["street_key"] == "calle 18"

        # No abrieron: se guarda sin preguntas → pendiente de nueva visita.
        first = door("12", "Apt 3", contact_level="conversation", followup="yes")
        saved = await ana.post(f"{base}/doors", json=first)
        assert saved.status_code == 201, saved.text
        body = saved.json()
        house = body["household"]
        assert house["address_line1"] == "12 Calle 18" and house["address_line2"] == "Apt 3" and house["unit"] == "Apt 3"
        assert house["door_status"] == "pending_revisit" and house["attempts_count"] == 1 and house["location_approx"] is True and house["latitude"] == 41.85
        assert body["event"]["contact_level"] is None and body["event"]["followup"] == "not_asked" and body["duplicate"] is False
        # Doble toque: la misma clave devuelve lo mismo, sin duplicar.
        again = (await ana.post(f"{base}/doors", json=first)).json()
        assert again["duplicate"] is True and again["event"]["visit_event_id"] == body["event"]["visit_event_id"]
        assert await db.outreach_visit_events.count_documents({"household_id": house["household_id"]}) == 1

        # La misma puerta escrita distinto suma un intento a la MISMA vivienda; si abren deja de estar pendiente.
        second = await ana.post(f"{base}/doors", json=door("12", "3", street_name="calle  18", opened=True, contact_level="invited_in", actions=["prayer", "invitation"],
                                                             followup="yes", followup_date=today, language="en", language_basis="impression",
                                                             person={"contact_name": f"Rosa {tag}", "contact_phone": f"555{tag[:6]}"}))
        assert second.status_code == 201, second.text
        result = second.json()
        assert result["household"]["household_id"] == house["household_id"] and result["household"]["attempts_count"] == 2
        assert result["household"]["door_status"] == "followup_scheduled" and result["household"]["followup_date"] == today
        assert result["event"]["language"] == "en" and result["event"]["language_basis"] == "impression" and result["event"]["actions"] == ["invitation", "prayer"]
        visit = result["visits"][0]
        assert visit["status"] == "wants_followup" and visit["household_id"] == house["household_id"]
        assert door_key("Calle 18", "12", "Apt 3") == door_key("calle  18", "12", "3")
        # Otro apartamento = otra vivienda.
        other_unit = (await ana.post(f"{base}/doors", json=door("12", "4"))).json()
        assert other_unit["household"]["household_id"] != house["household_id"]

        # Teléfono repetido: el intento se guarda igual y se avisa (nunca bloquear la calle).
        repeated = (await ana.post(f"{base}/doors", json=door("14", opened=True, person={"contact_name": "Otra", "contact_phone": f"555{tag[:6]}"}))).json()
        assert repeated["person_warning"] and repeated["visits"] == [] and repeated["household"]["door_status"] == "opened"

        # Religión u origen solo si la persona lo compartió.
        assert (await ana.post(f"{base}/doors", json=door("16", opened=True, religion="Católica"))).status_code == 422
        shared = (await ana.post(f"{base}/doors", json=door("16", opened=True, religion="Católica", origin="México", shared_by_person=True))).json()
        assert shared["event"]["religion"] == "Católica" and shared["event"]["origin"] == "México" and shared["event"]["shared_by_person"] is True

        # Libros: con existencias descuenta; sin existencias o sin cargar NO bloquea y queda para conciliar.
        ana_user = await db.users.find_one({"person_id": ana_id}, {"_id": 1})
        await db.library_books.insert_one({"_id": book_id, "book_id": book_id, "sku": f"T{tag}".upper(), "name": f"Libro {tag}", "is_active": True})
        await db.library_holdings.insert_one({"_id": f"h-{tag}", "book_id": book_id, "holder_type": "user", "holder_id": str(ana_user["_id"]), "quantity_on_hand": 3, "reserved_qty": 0})
        books = (await ana.post(f"{base}/doors", json=door("20", opened=True, books=[{"book": book_id, "quantity": 2}, {"book": "LBS-NO-CARGADO", "quantity": 1}], other_material_count=2))).json()
        rows = {row["book"]: row for row in books["event"]["books"]}
        assert rows[book_id]["inventory_status"] == "discounted" and rows["LBS-NO-CARGADO"]["inventory_status"] == "not_discounted"
        assert books["event"]["books_total"] == 3 and books["event"]["other_material_count"] == 2 and books["event"]["books_inventory_pending"] is True
        assert (await db.library_holdings.find_one({"_id": f"h-{tag}"}))["quantity_on_hand"] == 1
        no_stock = (await ana.post(f"{base}/doors", json=door("22", books=[{"book": book_id, "quantity": 5}]))).json()
        assert no_stock["event"]["books"][0]["inventory_status"] == "not_discounted" and "existencias" in no_stock["event"]["books"][0]["reason"]
        assert (await db.library_holdings.find_one({"_id": f"h-{tag}"}))["quantity_on_hand"] == 1

        # Permisos: otro mentor no registra en la vivienda de Ana (ni registrándola de nuevo); el ajeno tampoco.
        attempt = {"client_request_id": f"req-{uuid.uuid4().hex}", "opened": False}
        assert (await beto.post(f"/api/mentorship/outreach/households/{house['household_id']}/attempts", json=attempt)).status_code == 403
        await beto.put(f"{base}/my-street", json={"street_name": "Calle 18"})
        assert (await beto.post(f"{base}/doors", json=door("12", "3"))).status_code == 409
        assert (await outsider.post(f"{base}/doors", json=door("1", street_name="Calle 1"))).status_code == 403
        # Nueva visita del propio mentor: al historial de la misma vivienda.
        revisit = (await ana.post(f"/api/mentorship/outreach/households/{house['household_id']}/attempts", json=attempt)).json()
        assert revisit["household"]["attempts_count"] == 3 and revisit["household"]["door_status"] == "pending_revisit"
        # El mentor solo ve sus viviendas.
        listed = {item["household_id"] for item in (await beto.get("/api/mentorship/outreach/households", params={"campaign_id": campaign_id})).json()["items"]}
        assert house["household_id"] not in listed
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_visit_history", "outreach_participations", "invasion_participants", "outreach_campaigns", "library_movements"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.library_books.delete_many({"_id": book_id})
        await db.library_holdings.delete_many({"book_id": book_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_migration_of_legacy_visits_is_safe_and_idempotent():
    tag = uuid.uuid4().hex[:8]
    campaign_id = f"camp-{tag}"
    now = datetime.now(timezone.utc)
    base = {"archived": False, "household_id": None, "visit_event_id": None, "created_at": now, "mentor_person_id": f"m-{tag}", "created_by_user_id": "u1"}
    visits = [
        {**base, "_id": f"a-{tag}", "visit_id": f"a-{tag}", "campaign_id": campaign_id, "status": "wants_followup", "contact_name": "Ana", "address_line1": "5 Main St",
         "enrollment_id": f"enr-{tag}", "converted_person_id": f"p-{tag}", "received_mcd": True, "mcd_delivery_movement_id": f"mv-{tag}"},
        {**base, "_id": f"b-{tag}", "visit_id": f"b-{tag}", "campaign_id": campaign_id, "status": "not_found", "contact_zone": "Sector Norte"},
        {**base, "_id": f"c-{tag}", "visit_id": f"c-{tag}", "campaign_id": campaign_id, "status": "assigned"},
        {**base, "_id": f"d-{tag}", "visit_id": f"d-{tag}", "campaign_id": None, "status": "visited"},
    ]
    try:
        await db.outreach_visits.insert_many([dict(item) for item in visits])
        before = {item["visit_id"]: item for item in await db.outreach_visits.find({"visit_id": {"$regex": tag}}, {"_id": 0}).to_list(10)}
        await migrate_legacy_visits()
        await migrate_legacy_visits()  # idempotente: la segunda vez no crea nada
        after = {item["visit_id"]: item for item in await db.outreach_visits.find({"visit_id": {"$regex": tag}}, {"_id": 0}).to_list(10)}
        # Nada se pierde: todos los campos anteriores siguen iguales.
        for visit_id, old in before.items():
            assert all(after[visit_id].get(key) == value for key, value in old.items() if key not in {"household_id", "visit_event_id"})
        assert after[f"a-{tag}"]["household_id"] == f"mig-a-{tag}" and after[f"a-{tag}"]["visit_event_id"] == f"mig-a-{tag}"
        assert after[f"a-{tag}"]["enrollment_id"] == f"enr-{tag}" and after[f"a-{tag}"]["mcd_delivery_movement_id"] == f"mv-{tag}"
        assert after[f"c-{tag}"]["household_id"] == f"mig-c-{tag}" and after[f"c-{tag}"]["visit_event_id"] is None
        assert after[f"d-{tag}"]["household_id"] is None  # sin invasión: «Persona sin vivienda»
        assert await db.outreach_households.count_documents({"campaign_id": campaign_id}) == 3
        assert await db.outreach_visit_events.count_documents({"campaign_id": campaign_id}) == 2
        house_a = await db.outreach_households.find_one({"household_id": f"mig-a-{tag}"})
        house_b = await db.outreach_households.find_one({"household_id": f"mig-b-{tag}"})
        assert house_a["address_line1"] == "5 Main St" and house_a["door_status"] == "opened" and house_a["attempts_count"] == 1 and not house_a["address_incomplete"]
        assert house_b["door_status"] == "pending_revisit" and house_b["address_incomplete"] is True and house_b["address_line1"] == "Sector Norte"
        event_a = await db.outreach_visit_events.find_one({"visit_event_id": f"mig-a-{tag}"})
        assert event_a["opened"] is True and event_a["followup"] == "yes" and event_a["books_total"] == 1 and event_a["migrated"] is True
    finally:
        await db.outreach_visits.delete_many({"visit_id": {"$regex": tag}})
        await db.outreach_households.delete_many({"campaign_id": campaign_id})
        await db.outreach_visit_events.delete_many({"campaign_id": campaign_id})


@pytest.mark.asyncio
async def test_door_summary_lists_and_books_scope():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, beto_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto")]
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        for person_id in (ana_id, beto_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        today = date.today().isoformat()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today, "end_date": today, "mentor_person_ids": [ana_id, beto_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await ana.put(f"{base}/my-street", json={"street_name": "Calle Sol"})
        await ana.post(f"{base}/doors", json=door("1"))                                      # no abrieron
        await ana.post(f"{base}/doors", json=door("1"))                                      # 2.º intento, misma vivienda
        await ana.post(f"{base}/doors", json=door("2", opened=True, contact_level="brief", books=[{"book": "NO-CARGADO", "quantity": 2}]))
        await ana.post(f"{base}/doors", json=door("3", opened=True, contact_level="conversation"))
        summary = (await ana.get(f"{base}/door-summary")).json()
        assert {key: summary[key] for key in ("visited", "opened", "no_answer", "conversed", "books", "attempts", "pending_revisit", "consolidation")} == {
            "visited": 3, "opened": 2, "no_answer": 1, "conversed": 1, "books": 2, "attempts": 4, "pending_revisit": 1, "consolidation": 0}
        no_answer = (await ana.get(f"{base}/door-summary/no_answer")).json()
        assert no_answer["total"] == 1 and no_answer["items"][0]["address_line1"] == "1 Calle Sol" and no_answer["items"][0]["attempts_count"] == 2
        assert (await ana.get(f"{base}/door-summary/books")).json()["items"][0]["books_total"] == 2
        assert (await ana.get(f"{base}/door-summary/nada")).status_code == 404
        # Beto solo ve su trabajo (vacío) y no el de Ana.
        assert (await beto.get(f"{base}/door-summary")).json()["visited"] == 0
        assert (await beto.get(f"{base}/door-summary", params={"mentor_person_id": ana_id})).status_code == 403
        books = (await ana.get("/api/mentorship/outreach/door-books")).json()["items"]
        assert [item["sku"] for item in books[:2]] == ["MCD", "NPT"]
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_participations", "invasion_participants", "outreach_campaigns"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_pending_doors_schedule_resolution_map_and_location():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id, beto_id = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto")]
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        for person_id in (ana_id, beto_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        today = date.today()
        campaign_id = (await pastora.post("/api/invasions", json={"name": f"Inv {tag}", "location": "Barrio", "start_date": today.isoformat(), "end_date": today.isoformat(), "mentor_person_ids": [ana_id, beto_id]})).json()["campaign_id"]
        base = f"/api/mentorship/outreach/campaigns/{campaign_id}"
        await ana.put(f"{base}/my-street", json={"street_name": "Calle Luna", "latitude": 41.0, "longitude": -87.0, "location_source": "gps"})
        closed = (await ana.post(f"{base}/doors", json=door("1"))).json()["household"]                     # sin respuesta
        opened = (await ana.post(f"{base}/doors", json=door("2", opened=True, followup="yes", followup_date="2020-01-01"))).json()["household"]  # seguimiento atrasado
        (await ana.post(f"{base}/doors", json=door("3", opened=True))).json()                              # abrieron, sin pendiente
        await beto.put(f"{base}/my-street", json={"street_name": "Calle Mar"})
        await beto.post(f"{base}/doors", json=door("9"))

        pending = (await ana.get(f"{base}/pending-doors")).json()
        assert pending["scope"] == "mine" and pending["total"] == 2
        assert [item["household_id"] for item in pending["items"]] == [opened["household_id"], closed["household_id"]]  # programados (atrasados) primero
        assert pending["items"][0]["overdue"] is True and pending["items"][0]["door_status"] == "followup_scheduled"
        assert (await ana.get(f"{base}/pending-doors", params={"status": "pending_revisit"})).json()["total"] == 1
        everyone = (await pastora.get(f"{base}/pending-doors")).json()
        assert everyone["scope"] == "all" and everyone["total"] == 3 and all(item["mentor_name"] for item in everyone["items"])

        # Programar una vivienda sin respuesta → seguimiento programado; otro mentor no puede.
        next_day = (today.replace(day=28) if today.day < 28 else today).isoformat()
        assert (await beto.put(f"/api/mentorship/outreach/households/{closed['household_id']}/next-visit", json={"next_visit_date": next_day})).status_code == 403
        scheduled = (await ana.put(f"/api/mentorship/outreach/households/{closed['household_id']}/next-visit", json={"next_visit_date": next_day, "note": "Volver en la tarde"})).json()
        assert scheduled["door_status"] == "followup_scheduled" and scheduled["followup_date"] == next_day
        # Registrar la visita resuelve lo programado; si vuelven a no abrir, queda pendiente otra vez.
        again = (await ana.post(f"/api/mentorship/outreach/households/{closed['household_id']}/attempts", json={"client_request_id": f"req-{uuid.uuid4().hex}", "opened": False})).json()
        assert again["household"]["door_status"] == "pending_revisit" and again["household"]["followup_date"] is None and again["household"]["attempts_count"] == 2
        # Si después abren sin seguimiento, ya no es pendiente; el seguimiento antiguo no "revive".
        resolved = (await ana.post(f"/api/mentorship/outreach/households/{opened['household_id']}/attempts", json={"client_request_id": f"req-{uuid.uuid4().hex}", "opened": True})).json()
        assert resolved["household"]["door_status"] == "opened" and resolved["household"]["followup_date"] is None
        # Quitar la programación.
        await ana.put(f"/api/mentorship/outreach/households/{closed['household_id']}/next-visit", json={"next_visit_date": next_day})
        cleared = (await ana.put(f"/api/mentorship/outreach/households/{closed['household_id']}/next-visit", json={"next_visit_date": None})).json()
        assert cleared["door_status"] == "pending_revisit"

        # Mapa con el estado de cada puerta; confirmar ubicación quita "aproximada".
        points = {item["household_id"]: item for item in (await ana.get(f"{base}/households/map")).json()["points"]}
        assert points[closed["household_id"]]["door_status"] == "pending_revisit" and points[closed["household_id"]]["location_approx"] is True
        confirm = await ana.put(f"/api/mentorship/outreach/households/{closed['household_id']}/location", json={"latitude": 41.0001, "longitude": -87.0001, "accuracy_m": 8, "source": "gps"})
        assert confirm.status_code == 200, confirm.text
        assert confirm.json()["household"]["location_approx"] is False and confirm.json()["household"]["location_reference"] is None
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_participations", "invasion_participants", "outreach_campaigns"):
                await db[collection].delete_many({"campaign_id": campaign_id})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
