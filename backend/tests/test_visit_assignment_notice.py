"""«Asignar visita» (Visitas e Invasiones › Totales por mentor): el mentor la ve YA en
Mi Trabajo › Pendientes (con dirección, persona y quién la asignó), en Mis Visitas, en
la tarjeta «Tienes N visitas asignadas» y recibe el aviso «Te asignaron una visita»
con enlace directo. Sin cuenta 360 no hay a quién avisar (y el líder lo sabe)."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_assigned_visit_reaches_the_mentor():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    visit_ids = []
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        ana_id = await fx.person(f"Ana{tag}")
        ana = await fx.account(ana_id, "persona")
        danya_id = await fx.person(f"Danya{tag}")  # mentora sin cuenta 360
        for pid in (ana_id, danya_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{pid}", "person_id": pid, "active": True})
        ana_user = await db.users.find_one({"person_id": ana_id})
        # Una cuenta «persona» que es mentor sabe que lo es (así ve «Mi Trabajo» y «Mis Visitas»),
        # aunque no tenga permiso para leer perfiles (/badge/{id} le da 403).
        assert (await ana.get("/api/mentorship/my-badge")).json() == {"person_id": ana_id, "active": True}
        assert (await pastora.get("/api/mentorship/my-badge")).json()["active"] is False

        created = await pastora.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": f"Luz Visita {tag}", "contact_phone": f"555-{int(tag[:6], 16) % 10000000:07d}",
                                                                               "contact_zone": "Calle 18 #45", "mentor_person_id": ana_id})
        assert created.status_code == 201, created.text
        visit = created.json()
        visit_ids.append(visit["visit_id"])
        assert visit["mentor_notified"] is True and visit["assigned_by_name"].startswith(f"Pastora{tag}")

        # Aviso en la campana (y al celular si está activado) con enlace directo a la visita.
        notice = await db.portal_notifications.find_one({"recipient_user_id": str(ana_user["_id"]), "type": "visit_assigned"})
        assert notice["title"] == f"Te asignaron una visita: Luz Visita {tag}"
        assert "Calle 18 #45" in notice["message"] and f"Asignada por Pastora{tag}" in notice["message"]
        assert notice["link"] == f"/mentoria/visitas?visita={visit['visit_id']}"
        assert any(item["type"] == "visit_assigned" for item in (await ana.get("/api/notifications")).json()["items"])

        # Mi Trabajo › Pendientes: aparece de inmediato, para hoy, con dirección y quién la asignó.
        pending = (await ana.get("/api/my-work/pending")).json()
        item = next(row for row in pending["items"] if row["kind"] == "assigned_visit")
        assert item["title"] == f"Luz Visita {tag}" and item["subtitle"] == "Calle 18 #45" and item["bucket"] == "today"
        assert item["last_result"].startswith(f"Asignada por Pastora{tag}") and item["visit_id"] == visit["visit_id"]
        assert (await ana.get("/api/my-work/pending", params={"kind": "people"})).json()["total"] >= 1
        assert (await ana.get("/api/my-work/summary")).json()["assigned_visits"] == 1
        # Mis Visitas: la misma visita, con «Asignada por».
        mine = (await ana.get("/api/mentorship/outreach/visits", params={"mentor_person_id": ana_id})).json()["items"]
        assert [row["visit_id"] for row in mine] == [visit["visit_id"]] and mine[0]["assigned_by_name"].startswith(f"Pastora{tag}")

        # Al hacerla, sale de pendientes.
        assert (await ana.put(f"/api/mentorship/outreach/visits/{visit['visit_id']}/report", json={"status": "visited"})).status_code == 200
        assert not any(row["kind"] == "assigned_visit" for row in (await ana.get("/api/my-work/pending")).json()["items"])
        assert (await ana.get("/api/my-work/summary")).json()["assigned_visits"] == 0

        # Mentora sin cuenta 360: la visita se asigna, pero no hay a quién avisar (el líder lo ve).
        other = (await pastora.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": f"Mar Visita {tag}", "mentor_person_id": danya_id})).json()
        visit_ids.append(other["visit_id"])
        assert other["mentor_notified"] is False
        assert await db.portal_notifications.count_documents({"ref.visit_id": other["visit_id"]}) == 0
        mentors = {row["person_id"]: row for row in (await pastora.get("/api/mentorship/mentors")).json()["items"]}
        assert mentors[danya_id]["has_account"] is False and mentors[ana_id]["has_account"] is True

        # Lo que el mentor anota para sí mismo no genera aviso.
        own = (await ana.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": f"Sol Visita {tag}"})).json()
        visit_ids.append(own["visit_id"])
        assert own["mentor_notified"] is False and own["assigned_by_name"] is None
        assert await db.portal_notifications.count_documents({"ref.visit_id": own["visit_id"]}) == 0
    finally:
        await db.outreach_visits.delete_many({"visit_id": {"$in": visit_ids}})
        await db.outreach_visit_history.delete_many({"visit_id": {"$in": visit_ids}})
        await db.portal_notifications.delete_many({"ref.visit_id": {"$in": visit_ids}})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
