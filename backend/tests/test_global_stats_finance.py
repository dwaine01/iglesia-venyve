"""Estadísticas Globales G2: Finanzas con el MISMO permiso del módulo (un
coordinador general o un mentor sin el permiso reciben 403), solo totales
(nunca diezmos por persona), auditoría de quién consultó, proyectos con meta
y recaudado, y actividades de Operaciones."""
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_finance_permissions_totals_audit_projects_and_activities():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        coordinator = await fx.account(await fx.person(f"Coordinador{tag}"), "lider", access_level="coordinador_general")
        mentor = await fx.account(await fx.person(f"Mentor{tag}"), "persona")
        treasurer_id = await fx.person(f"Tesorera{tag}")
        treasurer = await fx.account(treasurer_id, "persona", capabilities=["finance.read"], privilege_groups=["finance"], permissions_mode="manual")
        giver = await fx.person(f"Donante{tag}")
        today = date.today()
        first = today.replace(day=1)
        campaign_id = f"camp-{tag}"
        await db.finance_campaigns.insert_one({"_id": campaign_id, "campaign_id": campaign_id, "name": f"Techo nuevo {tag}", "project_type": "project", "goal_cents": 100000, "budget_cents": 50000, "status": "active", "start_date": first.isoformat()})
        docs = [
            {"amount": 10000, "type": "tithe", "status": "posted"},
            {"amount": 5000, "type": "offering", "status": "posted"},
            {"amount": 25000, "type": "project", "status": "posted", "campaign_id": campaign_id},
            {"amount": 99900, "type": "tithe", "status": "corrected"},  # corregida: no cuenta
        ]
        for index, item in enumerate(docs):
            cid = f"fc-{tag}-{index}"
            await db.finance_contributions.insert_one({"_id": cid, "contribution_id": cid, "person_id": giver, "received_date": "2003-05-10", "status": item["status"], "contribution_type": item["type"],
                                                       "amount_cents": item["amount"], "allocations": [{"fund_id": "f", "amount_cents": item["amount"], "contribution_type": item["type"], "campaign_id": item.get("campaign_id")}]})

        # Permisos: igual que el módulo Finanzas.
        assert (await coordinator.get("/api/global-stats/finance")).status_code == 403
        assert (await mentor.get("/api/global-stats/finance")).status_code == 403
        assert (await coordinator.get("/api/global-stats/access")).json()["sections"]["finance"] is False
        assert "received" not in {item["key"] for item in (await coordinator.get("/api/global-stats/summary")).json()["cards"]}
        may = {"period": "custom", "date_from": "2003-05-01", "date_to": "2003-05-31"}
        response = await treasurer.get("/api/global-stats/finance", params=may)
        assert response.status_code == 200
        data = (await pastora.get("/api/global-stats/finance", params=may)).json()
        cards = {item["key"]: item["value"] for item in data["cards"]}
        assert (cards["tithes"], cards["offerings"], cards["projects"], cards["received"]) == (100.0, 50.0, 250.0, 400.0)
        project = next(item for item in data["projects"] if item["campaign_id"] == campaign_id)
        assert (project["goal"], project["raised"], project["goal_pct"], project["type"]) == (1000.0, 250.0, 25, "Proyecto")
        # Nunca por persona: ni identificador ni nombre del donante.
        text = json.dumps(data)
        assert giver not in text and f"Donante{tag}" not in text and "person_id" not in text
        # Auditoría: quién consultó finanzas.
        assert await db.finance_audit_events.count_documents({"action": "global_stats_finance_viewed", "actor_user_id": {"$in": [doc["_id"] for doc in await db.users.find({"person_id": treasurer_id}, {"_id": 1}).to_list(5)] + [str(doc["_id"]) for doc in await db.users.find({"person_id": treasurer_id}, {"_id": 1}).to_list(5)]}}) >= 1
        # Sin datos: el motivo.
        empty = (await pastora.get("/api/global-stats/finance", params={"period": "custom", "date_from": "2001-01-01", "date_to": "2001-01-31"})).json()
        assert {item["key"]: item for item in empty["cards"]}["offerings"]["empty_reason"] == "Aún no se han registrado ofrendas en este período."

        # Actividades (Operaciones): realizadas en el período y próximas.
        event_id, occurrence_id, upcoming_id = f"ev-{tag}", f"oc-{tag}", f"oc2-{tag}"
        await db.operation_events.insert_one({"_id": event_id, "event_id": event_id, "title": f"Conferencia de jóvenes {tag}", "event_type": "conference", "location": "Templo"})
        starts = datetime.now(timezone.utc) - timedelta(hours=3) if today.day > 1 else datetime.now(timezone.utc) - timedelta(minutes=30)
        await db.operation_event_occurrences.insert_many([{"_id": occurrence_id, "occurrence_id": occurrence_id, "event_id": event_id, "starts_at": starts, "status": "scheduled"},
                                                          {"_id": upcoming_id, "occurrence_id": upcoming_id, "event_id": event_id, "starts_at": datetime.now(timezone.utc) + timedelta(days=5), "status": "scheduled"}])
        for index, person in enumerate([giver, treasurer_id]):
            await db.operation_registrations.insert_one({"_id": f"reg-{tag}-{index}", "registration_id": f"reg-{tag}-{index}", "occurrence_id": occurrence_id, "event_id": event_id, "person_id": person, "status": "registered", "registration_code": f"OP-{tag}-{index}"})
        await db.operation_checkins.insert_one({"_id": f"chk-{tag}", "checkin_id": f"chk-{tag}", "occurrence_id": occurrence_id, "event_id": event_id, "person_id": giver, "status": "active"})
        await db.operation_shifts.insert_one({"_id": f"sh-{tag}", "shift_id": f"sh-{tag}", "occurrence_id": occurrence_id, "event_id": event_id, "required_volunteers": 4})
        await db.operation_volunteer_assignments.insert_one({"_id": f"va-{tag}", "assignment_id": f"va-{tag}", "occurrence_id": occurrence_id, "person_id": treasurer_id, "status": "confirmed"})
        acts = (await pastora.get("/api/global-stats/activities", params={"period": "month"})).json()
        mine = next(item for item in acts["done"] if item["occurrence_id"] == occurrence_id)
        assert (mine["registered"], mine["attended"], mine["volunteers"], mine["volunteers_needed"], mine["type"]) == (2, 1, 1, 4, "Conferencia")
        assert any(item["occurrence_id"] == upcoming_id for item in acts["upcoming"])
        assert (await mentor.get("/api/global-stats/activities")).status_code == 403
    finally:
        await db.finance_contributions.delete_many({"contribution_id": {"$regex": tag}})
        await db.finance_campaigns.delete_many({"campaign_id": {"$regex": tag}})
        for collection in ("operation_events", "operation_event_occurrences", "operation_registrations", "operation_checkins", "operation_shifts", "operation_volunteer_assignments"):
            await db[collection].delete_many({"_id": {"$regex": tag}})
        await fx.cleanup()
