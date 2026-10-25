"""C2 · Panorama de Consolidación: cifras, embudo, sin atender (48 h), sin
próxima acción, carga por mentor, avance por invasión, tendencia, listados y
permisos (completo / solo mis personas / 403)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server

db = server.db


@pytest.mark.asyncio
async def test_panorama_figures_lists_and_scope():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    ids = []
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        coordinator = await fx.account(await fx.person(f"Coord{tag}"), "lider", access_level="coordinador_general")
        lead_id, ana_id, beto_id, collab_id = [await fx.person(f"{name}{tag}") for name in ("Encargado", "Ana", "Beto", "Colab")]
        lead = await fx.account(lead_id, "persona")
        ana = await fx.account(ana_id, "persona")
        collab = await fx.account(collab_id, "persona")
        await db.users.update_one({"person_id": lead_id}, {"$addToSet": {"capabilities": "consolidation.assign"}})
        for person_id in (ana_id, beto_id):
            await db.mentor_badges.insert_one({"_id": f"badge-{tag}-{person_id}", "person_id": person_id, "active": True})
        camp = f"camp-{tag}"
        await db.outreach_campaigns.insert_one({"_id": camp, "campaign_id": camp, "name": f"Invasión {tag}", "start_date": (now - timedelta(days=3)).date().isoformat(), "end_date": (now - timedelta(days=3)).date().isoformat(), "status": "active"})
        people = [await fx.person(f"P{index}{tag}") for index in range(5)]
        specs = [  # (mentor, etapa, creado hace, próxima acción, invasión, transferencia)
            (ana_id, "visitor_followup", timedelta(days=4), None, camp, False),     # sin atender (sin actividad > 48 h), sin próxima acción
            (ana_id, "mcd", timedelta(days=10), now + timedelta(days=2), camp, False),
            (ana_id, "lbs_1", timedelta(days=40), now + timedelta(days=1), None, True),
            (beto_id, "visitor_followup", timedelta(hours=5), None, None, False),  # reciente: no cuenta como sin atender
            (beto_id, "retreat", timedelta(days=60), now, None, False),
        ]
        for index, (mentor, stage, age, next_at, campaign, transfer) in enumerate(specs):
            enrollment_id = f"enr-{tag}-{index}"
            ids.append(enrollment_id)
            await db.process_enrollments.insert_one({"_id": enrollment_id, "enrollment_id": enrollment_id, "process_key": "consolidation", "definition_version": 2, "person_id": people[index],
                                                     "mentor_person_id": mentor, "current_stage_key": stage, "status": "active", "created_at": now - age, "next_action_at": next_at,
                                                     "campaign_id": campaign, "mentor_transfer_required": transfer, "front_group_id": None})
        # Actividades realizadas: primer contacto a las 6 h y a las 18 h.
        await db.consolidation_activities.insert_many([
            {"_id": f"act-{tag}-1", "activity_id": f"act-{tag}-1", "enrollment_id": ids[1], "status": "done", "completed_at": now - timedelta(days=10) + timedelta(hours=6)},
            {"_id": f"act-{tag}-2", "activity_id": f"act-{tag}-2", "enrollment_id": ids[2], "status": "done", "completed_at": now - timedelta(days=40) + timedelta(hours=18)},
            {"_id": f"act-{tag}-3", "activity_id": f"act-{tag}-3", "enrollment_id": ids[4], "status": "done", "completed_at": now - timedelta(days=1)},
        ])
        await db.person_memberships.insert_one({"_id": f"mem-{tag}", "person_id": people[4], "status": "active"})

        # Permisos: completo (pastora, coordinador, encargado); mentor = sus personas; colaborador 403.
        assert (await collab.get("/api/consolidation/panorama")).status_code == 403
        assert (await collab.get("/api/consolidation/panorama/list/total")).status_code == 403
        mine = (await ana.get("/api/consolidation/panorama", params={"mentor_person_id": beto_id})).json()
        assert mine["scope"] == "mine" and mine["figures"]["total"] >= 3 and mine["filters"]["mentor_person_id"] == ana_id
        assert all(row["mentor_person_id"] == ana_id for row in (await ana.get("/api/consolidation/panorama/list/total")).json()["items"])
        for client in (pastora, coordinator, lead):
            assert (await client.get("/api/consolidation/panorama")).json()["scope"] == "all"

        # Cifras con el filtro de la invasión (solo nuestros datos).
        data = (await lead.get("/api/consolidation/panorama", params={"campaign_id": camp, "period": "all"})).json()
        assert data["figures"]["total"] == 2 and data["figures"]["unattended"] == 1 and data["figures"]["no_next_action"] == 1
        assert data["by_campaign"][0]["campaign_id"] == camp and data["by_campaign"][0]["in_route"] == 1 and data["by_campaign"][0]["unattended"] == 1
        # Por mentor (Ana): embudo, primer contacto, transferencias, nuevas en el mes y comparación.
        ana_view = (await pastora.get("/api/consolidation/panorama", params={"mentor_person_id": ana_id, "period": "month"})).json()
        funnel = {row["key"]: row["value"] for row in ana_view["funnel"]}
        assert funnel["contacted"] == 3 and funnel["mcd"] == 2 and funnel["lbs"] == 1 and funnel["retreat"] == 0
        assert ana_view["figures"]["first_contact_avg_hours"] == 12.0 and ana_view["figures"]["transfers"] == 1
        assert ana_view["figures"]["new"] == 2 and ana_view["figures"]["new_previous"] == 1 and ana_view["figures"]["new_delta"] == 1
        beto_view = (await pastora.get("/api/consolidation/panorama", params={"mentor_person_id": beto_id, "period": "all"})).json()
        assert {row["key"]: row["value"] for row in beto_view["funnel"]}["membership"] == 1 and beto_view["figures"]["unattended"] == 0
        assert len(ana_view["trend"]) == 8 and sum(row["new"] for row in ana_view["trend"]) >= 1
        # Carga por mentor con nombre.
        loads = {row["mentor_person_id"]: row for row in (await pastora.get("/api/consolidation/panorama", params={"period": "all"})).json()["mentor_load"]["items"]}
        assert loads[ana_id]["active"] >= 3 and loads[ana_id]["name"]

        # Listados detrás de cada cifra.
        unattended = (await lead.get("/api/consolidation/panorama/list/unattended", params={"campaign_id": camp})).json()
        assert unattended["total"] == 1 and unattended["items"][0]["enrollment_id"] == ids[0] and unattended["items"][0]["mentor_name"]
        assert (await lead.get("/api/consolidation/panorama/list/funnel:mcd", params={"mentor_person_id": ana_id})).json()["total"] == 2
        assert (await lead.get("/api/consolidation/panorama/list/stage:retreat", params={"mentor_person_id": beto_id})).json()["total"] == 1
        assert (await lead.get("/api/consolidation/panorama/list/nada")).status_code == 404
    finally:
        await db.process_enrollments.delete_many({"enrollment_id": {"$in": ids}})
        await db.consolidation_activities.delete_many({"_id": {"$regex": f"^act-{tag}"}})
        await db.person_memberships.delete_many({"_id": f"mem-{tag}"})
        await db.outreach_campaigns.delete_many({"_id": f"camp-{tag}"})
        await db.mentor_badges.delete_many({"_id": {"$regex": f"^badge-{tag}"}})
        await fx.cleanup()
