"""FASE 6F (tramo 1): reporte de invasión — permisos (completo / personal /
sin acceso), pastora excluida, cifras con datos de ejemplo y reporte final
congelado que ya no cambia."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server


@pytest.mark.asyncio
async def test_report_permissions_figures_and_frozen_final():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    today = date.today()
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        lead_id, ana_id, beto_id, collab_id, other_id = [await fx.person(f"{name}{tag}") for name in ("Encargado", "Ana", "Beto", "Colab", "Ajeno")]
        lead = await fx.account(lead_id, "persona")
        ana = await fx.account(ana_id, "persona")
        beto = await fx.account(beto_id, "persona")
        other = await fx.account(other_id, "persona")
        coordinator = await fx.account(await fx.person(f"Coord{tag}"), "lider", access_level="coordinador_general")
        for person_id in (ana_id, beto_id, pastora_id):
            await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        created = await pastora.post("/api/invasions", json={
            "name": f"Invasión {tag}", "location": "Lincoln Park", "purpose": "Alcanzar familias",
            "start_date": (today - timedelta(days=1)).isoformat(), "end_date": today.isoformat(),
            "general_lead_person_id": lead_id, "mentor_person_ids": [ana_id, beto_id, pastora_id], "collaborator_person_ids": [collab_id],
        })
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]
        # Ana: 2 casas (una visitada) y 2 personas alcanzadas; casa disponible sin tomar.
        h1 = (await ana.post("/api/mentorship/outreach/households", json={"campaign_id": campaign_id, "address_line1": "1 Main", "sector": "Norte", "latitude": 39.9, "longitude": -83.0})).json()["household_id"]
        await ana.post("/api/mentorship/outreach/households", json={"campaign_id": campaign_id, "address_line1": "2 Main", "sector": "Norte", "latitude": 39.91, "longitude": -83.0})
        await pastora.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/import", json={"entries": [{"address_line1": "3 Main", "sector": "Sur"}]})
        await ana.post(f"/api/mentorship/outreach/households/{h1}/events", json={"result": "no_answer"})
        now = datetime.now(timezone.utc)
        for index, extra in enumerate(({"status": "wants_followup", "received_mcd": True, "enrollment_id": f"enr-{tag}"}, {"status": "visited", "lbs_decision": "needs_lbs"})):
            await server.db.outreach_visits.insert_one({"_id": f"v-{tag}-{index}", "visit_id": f"v-{tag}-{index}", "campaign_id": campaign_id, "mentor_person_id": ana_id, "household_id": h1, "contact_zone": "Norte", "archived": False, "created_at": now, **extra})
        # Una visita "de la pastora" no cuenta.
        await server.db.outreach_visits.insert_one({"_id": f"v-{tag}-p", "visit_id": f"v-{tag}-p", "campaign_id": campaign_id, "mentor_person_id": pastora_id, "status": "wants_followup", "archived": False, "created_at": now})
        await beto.post(f"/api/invasions/{campaign_id}/respond", json={"response": "declined"})

        # Permisos: completo para pastora, coordinador general y encargado; personal para el mentor; nada para un ajeno.
        for client in (pastora, coordinator, lead):
            assert (await client.get(f"/api/invasions/{campaign_id}/report")).json()["scope"] == "full"
        assert (await other.get(f"/api/invasions/{campaign_id}/report")).status_code == 403
        personal = (await beto.get(f"/api/invasions/{campaign_id}/report")).json()
        assert personal["scope"] == "personal" and "ranking" not in personal and "participation" not in personal

        report = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        assert report["mode"] == "live" and report["summary"]["state"] == "active" and report["can_finalize"] is True
        figures = report["summary"]["key_figures"]
        assert {key: figures[key] for key in ("houses_visited", "houses_total", "people_reached", "wants_followup", "seven_weeks", "participants", "attended", "attendance_pct")} == {
            "houses_visited": 1, "houses_total": 3, "people_reached": 2, "wants_followup": 1, "seven_weeks": 1, "participants": 4, "attended": 1, "attendance_pct": 25}
        # Pastora fuera de participación y ranking.
        roles = {item["role"]: item for item in report["participation"]["by_role"]}
        assert roles["mentor"]["invited"] == 2 and roles["mentor"]["declined"] == 1 and roles["collaborator"]["invited"] == 1
        assert pastora_id not in {item["person_id"] for item in report["ranking"]["mentors"]}
        assert report["ranking"]["mentors"][0]["person_id"] == ana_id and report["ranking"]["mentors"][0]["people"] == 2
        field = report["field"]
        assert field["houses"] == {"available": 1, "assigned": 2, "visited": 1, "located": 2, "total": 3}
        assert field["results"]["received_mcd"] == 1 and field["results"]["lbs_pending"] == 1
        norte = next(item for item in field["by_sector"] if item["sector"] == "Norte")
        assert norte == {"sector": "Norte", "houses": 2, "visited": 1, "people": 2, "coverage_pct": 50}
        ana_personal = (await ana.get(f"/api/invasions/{campaign_id}/report")).json()
        assert ana_personal["mine"]["people"] == 2 and ana_personal["position"] == 1

        # Cerrar → reporte final congelado; lo que pase después no lo cambia.
        assert (await beto.post(f"/api/invasions/{campaign_id}/report/finalize")).status_code == 403
        final = (await lead.post(f"/api/invasions/{campaign_id}/report/finalize")).json()
        assert final["mode"] == "final" and final["summary"]["state"] == "closed" and final["can_finalize"] is False
        await server.db.outreach_visits.insert_one({"_id": f"v-{tag}-late", "visit_id": f"v-{tag}-late", "campaign_id": campaign_id, "mentor_person_id": ana_id, "status": "wants_followup", "archived": False, "created_at": now})
        again = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        assert again["summary"]["key_figures"] == final["summary"]["key_figures"] and again["frozen_at"] == final["frozen_at"]
        assert (await lead.post(f"/api/invasions/{campaign_id}/report/finalize")).json()["frozen_at"] == final["frozen_at"]
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_participations", "invasion_participants", "invasion_reports", "invasion_report_notes", "outreach_campaigns"):
                await server.db[collection].delete_many({"campaign_id": campaign_id})
        await server.db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_report_followup_goals_and_comparison():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_ids = []
    today = date.today()
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        ana_id = await fx.person(f"Ana{tag}")
        await fx.account(ana_id, "persona")
        await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}", "person_id": ana_id, "active": True})
        for name, start in (("Anterior", today - timedelta(days=40)), ("Actual", today - timedelta(days=5))):
            created = await pastora.post("/api/invasions", json={"name": f"{name} {tag}", "location": "Barrio", "start_date": start.isoformat(), "end_date": start.isoformat(), "mentor_person_ids": [ana_id]})
            campaign_ids.append(created.json()["campaign_id"])
        previous_id, campaign_id = campaign_ids
        old = datetime.now(timezone.utc) - timedelta(days=4)
        await server.db.outreach_visits.insert_many([
            {"_id": f"p-{tag}-{i}", "visit_id": f"p-{tag}-{i}", "campaign_id": previous_id, "mentor_person_id": ana_id, "status": "visited", "archived": False, "created_at": old} for i in range(3)])
        # Actual: 3 quieren seguimiento → una con expediente contactada a las 10 h (y en etapa NPT), una transferida
        # sin contacto, y una sin expediente hace 4 días (SIN atender).
        await server.db.process_enrollments.insert_many([
            {"_id": f"e1-{tag}", "enrollment_id": f"e1-{tag}", "process_key": "consolidation", "mentor_person_id": ana_id, "current_stage_key": "npt", "created_at": old},
            {"_id": f"e2-{tag}", "enrollment_id": f"e2-{tag}", "process_key": "consolidation", "mentor_person_id": ana_id, "current_stage_key": "new_visitor", "created_at": datetime.now(timezone.utc)},
        ])
        await server.db.consolidation_activities.insert_one({"_id": f"a-{tag}", "activity_id": f"a-{tag}", "enrollment_id": f"e1-{tag}", "status": "done", "completed_at": old + timedelta(hours=10)})
        await server.db.mentor_assignments.insert_one({"_id": f"m-{tag}", "assignment_id": f"m-{tag}", "enrollment_id": f"e2-{tag}", "transfer": True, "active": True})
        await server.db.outreach_visits.insert_many([
            {"_id": f"c-{tag}-1", "visit_id": f"c-{tag}-1", "campaign_id": campaign_id, "mentor_person_id": ana_id, "status": "wants_followup", "enrollment_id": f"e1-{tag}", "archived": False, "created_at": old},
            {"_id": f"c-{tag}-2", "visit_id": f"c-{tag}-2", "campaign_id": campaign_id, "mentor_person_id": ana_id, "status": "wants_followup", "enrollment_id": f"e2-{tag}", "archived": False, "created_at": datetime.now(timezone.utc)},
            {"_id": f"c-{tag}-3", "visit_id": f"c-{tag}-3", "campaign_id": campaign_id, "mentor_person_id": ana_id, "status": "wants_followup", "archived": False, "created_at": old},
        ])
        report = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        follow = report["followup"]
        assert follow["wants_followup"] == 3 and follow["to_consolidation"] == 2 and follow["transferred"] == 1 and follow["assigned_mentor"] == 2
        assert follow["unattended"] == 1 and follow["pending_recent"] == 1 and follow["attended"] == 1
        assert {row["bucket"]: row["total"] for row in follow["first_contact"]}["< 24 h"] == 1
        assert {row["route"]: row["total"] for row in follow["routes"]} == {"MCD": 1, "NPT": 1, "LBS": 0}
        goals = {item["key"]: item for item in report["goals"]["items"]}
        assert goals["consolidation"]["numerator"] == 2 and goals["consolidation"]["denominator"] == 3 and goals["consolidation"]["semaphore"] in {"verde", "ambar", "rojo"}
        assert goals["coverage"]["semaphore"] == "sin_datos" and report["goals"]["rule"].startswith("Verde desde")
        comparison = report["comparison"]
        assert comparison[0]["current"] and comparison[0]["people"] == 3
        assert any(row["campaign_id"] == previous_id and row["people"] == 3 for row in comparison)
        assert report["summary"]["key_figures"]["to_consolidation"] == 2
    finally:
        for collection in ("outreach_visits", "outreach_participations", "invasion_participants", "invasion_reports", "invasion_report_notes", "outreach_campaigns"):
            await server.db[collection].delete_many({"campaign_id": {"$in": campaign_ids}})
        await server.db.process_enrollments.delete_many({"_id": {"$in": [f"e1-{tag}", f"e2-{tag}"]}})
        await server.db.consolidation_activities.delete_many({"_id": f"a-{tag}"})
        await server.db.mentor_assignments.delete_many({"_id": f"m-{tag}"})
        await server.db.mentor_badges.delete_many({"_id": f"badge-{tag}"})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_report_recommendations_resolved_and_lessons():
    """Tramo 3: recomendaciones por reglas con evidencia, casilla «resuelta»
    persistente (ids con puntos) y lecciones editables aun con el final congelado."""
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    campaign_id = None
    today = date.today()
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        lead_id, ana_id, beto_id, other_id = [await fx.person(f"{name}{tag}") for name in ("Encargado", "Ana", "Beto", "Ajeno")]
        lead = await fx.account(lead_id, "persona")
        ana = await fx.account(ana_id, "persona")
        other = await fx.account(other_id, "persona")
        await fx.account(beto_id, "persona")
        for person_id in (ana_id, beto_id):
            await server.db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        created = await pastora.post("/api/invasions", json={
            "name": f"Invasión {tag}", "location": "Barrio", "start_date": (today - timedelta(days=1)).isoformat(), "end_date": today.isoformat(),
            "general_lead_person_id": lead_id, "mentor_person_ids": [ana_id, beto_id]})
        assert created.status_code == 201, created.text
        campaign_id = created.json()["campaign_id"]
        sector = "Sector 1.A"
        await pastora.post(f"/api/mentorship/outreach/campaigns/{campaign_id}/households/import", json={"entries": [{"address_line1": f"{n} Calle", "sector": sector} for n in range(3)]})
        old = datetime.now(timezone.utc) - timedelta(days=4)
        await server.db.outreach_visits.insert_one({"_id": f"r-{tag}", "visit_id": f"r-{tag}", "campaign_id": campaign_id, "mentor_person_id": ana_id, "status": "wants_followup", "archived": False, "created_at": old})

        report = (await lead.get(f"/api/invasions/{campaign_id}/report")).json()
        recs = {item["id"]: item for item in report["recommendations"]}
        assert recs["followup:unattended"]["priority"] == "alta" and recs["followup:unattended"]["evidence"] == {"label": "Personas sin atender > 48 h", "value": 1, "total": 1, "pct": 100}
        assert recs["houses:available"]["evidence"]["value"] == 3 and recs[f"sector:{sector}"]["evidence"]["pct"] == 0
        assert recs["mentors:idle"]["evidence"]["value"] == 1 and "Beto" in recs["mentors:idle"]["detail"]
        assert recs["houses:unlocated"]["priority"] == "baja" and all(item["rule"].startswith("Regla") and item["responsible"] for item in recs.values())
        assert [item["priority"] for item in report["recommendations"]] == sorted((item["priority"] for item in report["recommendations"]), key={"alta": 0, "media": 1, "baja": 2}.get)
        assert not any(item["resolved"] for item in report["recommendations"])
        assert report["notes"]["worked"] is None

        # Mentor y ajeno no pueden marcar ni editar.
        for client in (ana, other):
            assert (await client.put(f"/api/invasions/{campaign_id}/report/recommendations/houses:available", json={"resolved": True})).status_code == 403
            assert (await client.put(f"/api/invasions/{campaign_id}/report/notes", json={"worked": "x"})).status_code == 403
        assert "recommendations" not in (await ana.get(f"/api/invasions/{campaign_id}/report")).json()

        # Congelar y luego marcar resuelta (id con punto) y escribir lecciones: sigue permitido.
        await lead.post(f"/api/invasions/{campaign_id}/report/finalize")
        marked = await lead.put(f"/api/invasions/{campaign_id}/report/recommendations/sector:{sector}", json={"resolved": True, "note": "Se reforzó"})
        assert marked.status_code == 200, marked.text
        saved = await lead.put(f"/api/invasions/{campaign_id}/report/notes", json={"worked": "  Buena oración  ", "testimonies": "Una familia aceptó a Cristo"})
        assert saved.json()["worked"] == "Buena oración" and saved.json()["updated_by"]
        pastor_saved = (await pastora.put(f"/api/invasions/{campaign_id}/report/notes", json={"pastor_recommendations": "Volver en un mes"})).json()
        assert pastor_saved["worked"] == "Buena oración" and pastor_saved["pastor_recommendations"] == "Volver en un mes"

        final = (await pastora.get(f"/api/invasions/{campaign_id}/report")).json()
        assert final["mode"] == "final"
        resolved = {item["id"]: item for item in final["recommendations"]}[f"sector:{sector}"]
        assert resolved["resolved"] is True and resolved["resolved_note"] == "Se reforzó" and resolved["resolved_by"]
        assert final["notes"]["testimonies"] == "Una familia aceptó a Cristo"
        await lead.put(f"/api/invasions/{campaign_id}/report/recommendations/sector:{sector}", json={"resolved": False})
        again = (await lead.get(f"/api/invasions/{campaign_id}/report")).json()
        assert not {item["id"]: item for item in again["recommendations"]}[f"sector:{sector}"]["resolved"]
    finally:
        if campaign_id:
            for collection in ("outreach_households", "outreach_visit_events", "outreach_visits", "outreach_participations", "invasion_participants", "invasion_reports", "invasion_report_notes", "outreach_campaigns"):
                await server.db[collection].delete_many({"campaign_id": campaign_id})
        await server.db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await server.db.portal_notifications.delete_many({"recipient_user_id": {"$in": [str(item) for item in fx.user_ids]}})
        await fx.cleanup()
