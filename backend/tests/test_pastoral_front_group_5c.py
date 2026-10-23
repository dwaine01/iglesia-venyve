"""ETAPA 5C: grupo frontal principal de la pastora, privacidad de integrantes
y 'Crear mi grupo frontal' por designación. Pertenecer a un grupo NO da
permisos: todo se valida en el backend."""
import os
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ley7semanas_test_db")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

import server  # noqa: E402
from access_control import access_defaults_for_role  # noqa: E402

PASSWORD = "Etapa5cPass123!"


class Fixture:
    def __init__(self):
        self.user_ids, self.person_ids, self.clients = [], [], []

    async def person(self, nombre: str) -> str:
        oid = ObjectId()
        now = datetime.now(timezone.utc)
        await server.db.persons.insert_one({
            "_id": oid, "person_number": f"VV-5C{uuid.uuid4().int % 99999:05d}", "nombre": nombre, "apellido": "Etapa5C",
            "search_key": f"{nombre} etapa5c".lower(), "idempotency_key": f"etapa5c-{oid}", "created_at": now, "updated_at": now,
        })
        self.person_ids.append(str(oid))
        return str(oid)

    async def account(self, person_id: str, role: str, **extra) -> AsyncClient:
        email = f"etapa5c.{uuid.uuid4().hex}@example.com"
        doc = {
            "nombre": "Cuenta 5C", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "rol": role, "person_id": person_id, "is_active": True, "token_version": 1,
            "must_change_password": False, "onboarding_required": False, **access_defaults_for_role(role), **extra,
        }
        result = await server.db.users.insert_one(doc)
        self.user_ids.append(result.inserted_id)
        await server.db.persons.update_one({"_id": ObjectId(person_id)}, {"$set": {"auth_user_id": str(result.inserted_id)}})
        client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
        login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 200, login.text
        client.headers.update({"Authorization": f"Bearer {login.json()['token']}"})
        self.clients.append(client)
        return client

    async def cleanup(self):
        for client in self.clients:
            await client.aclose()
        groups = await server.db.front_groups.distinct("front_group_id", {"$or": [
            {"primary_leader_person_id": {"$in": self.person_ids}}, {"pastoral_main": True},
        ]})
        groups += await server.db.front_groups.distinct("front_group_id", {"parent_group_id": {"$in": groups}})
        await server.db.front_groups.delete_many({"front_group_id": {"$in": groups}})
        await server.db.front_group_assignments.delete_many({"$or": [{"front_group_id": {"$in": groups}}, {"person_id": {"$in": self.person_ids}}]})
        await server.db.front_group_audit_events.delete_many({"front_group_id": {"$in": groups}})
        await server.db.users.delete_many({"_id": {"$in": self.user_ids}})
        await server.db.persons.delete_many({"_id": {"$in": [ObjectId(item) for item in self.person_ids]}})


@pytest.mark.asyncio
async def test_pastoral_group_roster_privacy_and_leader_privilege():
    await server.db.front_groups.update_many({"pastoral_main": True}, {"$unset": {"pastoral_main": ""}})
    fx = Fixture()
    try:
        pastora_id = await fx.person("Pastora")
        pastora = await fx.account(pastora_id, "pastora")
        coordinator = await fx.account(await fx.person("Coordinador"), "lider", access_level="coordinador_general")
        leader1_id, co1_id = await fx.person("LiderUno"), await fx.person("ColiderUno")
        leader2_id, solo_id, pastor_co_id = await fx.person("LiderDos"), await fx.person("Solita"), await fx.person("PastorColider")
        leader1 = await fx.account(leader1_id, "lider", capabilities=[], permissions_mode="manual")
        co1 = await fx.account(co1_id, "persona")
        leader2 = await fx.account(leader2_id, "lider", capabilities=[], permissions_mode="manual")

        created = await pastora.put("/api/pastoral-front-group", json={"name": "Grupo de la Pastora", "co_leader_person_id": pastor_co_id})
        assert created.status_code == 200, created.text
        main_id = created.json()["group"]["front_group_id"]
        assert created.json()["group"]["leader"]["person_id"] == pastora_id
        assert created.json()["group"]["co_leader"]["person_id"] == pastor_co_id
        assert (await pastora.put("/api/pastoral-front-group", json={"name": "Grupo de la Pastora"})).status_code == 200
        assert await server.db.front_groups.count_documents({"pastoral_main": True}) == 1

        # Lista confirmada: parejas e individuos (pueden estar incompletas: un individuo es válido).
        roster_payload = {"entries": [{"person_ids": [leader1_id, co1_id]}, {"person_ids": [leader2_id]}, {"person_ids": [solo_id]}]}
        saved = await pastora.put(f"/api/front-groups/{main_id}/roster", json=roster_payload)
        assert saved.status_code == 200, saved.text
        assert saved.json()["totals"] == {"people": 4, "pairs": 1, "individuals": 2}
        again = await pastora.put(f"/api/front-groups/{main_id}/roster", json=roster_payload)
        assert again.json()["totals"] == {"people": 4, "pairs": 1, "individuals": 2}
        assert await server.db.front_group_assignments.count_documents({"front_group_id": main_id, "person_id": leader1_id, "active": True}) == 1
        assert (await pastora.put(f"/api/front-groups/{main_id}/roster", json={"entries": [{"person_ids": [leader1_id]}, {"person_ids": [leader1_id, co1_id]}]})).status_code == 422
        assert (await pastora.put(f"/api/front-groups/{main_id}/roster", json={"entries": [{"person_ids": [pastor_co_id]}]})).status_code == 422
        assert (await pastora.put(f"/api/front-groups/{main_id}/roster", json={"entries": [{"person_ids": [co1_id, co1_id]}]})).status_code == 422

        # Solo pastora/pastor y coordinador general ven el conjunto; solo la autoridad pastoral lo edita.
        coordinator_view = await coordinator.get("/api/pastoral-front-group")
        assert coordinator_view.status_code == 200 and coordinator_view.json()["roster"]["totals"]["people"] == 4
        assert coordinator_view.json()["can_edit"] is False
        assert (await coordinator.put("/api/pastoral-front-group", json={"name": "No"})).status_code == 403
        assert (await coordinator.put(f"/api/front-groups/{main_id}/roster", json={"entries": []})).status_code == 403
        assert (await leader1.get("/api/pastoral-front-group")).status_code == 403
        activity = await coordinator.get(f"/api/pastoral-front-group/members/{leader1_id}/activity")
        assert activity.status_code == 200, activity.text
        assert {"as_person", "as_mentor", "as_leader"} <= set(activity.json())

        # Un integrante solo ve nombre, líder y colíder: nunca a los demás integrantes.
        mine = (await co1.get("/api/core/me/front-groups")).json()["items"]
        assert mine == [{
            "front_group_id": main_id, "name": "Grupo de la Pastora", "status": "active", "pastoral_main": True, "my_role": "member",
            "leader_name": "Pastora Etapa5C", "co_leader_name": "PastorColider Etapa5C", "can_create": False, "can_manage": False,
        }]
        detail = await co1.get(f"/api/front-groups/{main_id}")
        assert detail.status_code == 200 and detail.json()["member_view"] is True
        assert "assignments" not in detail.json() and "team_count" not in detail.json()
        assert (await co1.get(f"/api/front-groups/{main_id}/roster")).status_code == 403
        assert (await co1.get(f"/api/front-groups/{main_id}/history")).status_code == 403
        assert (await co1.get(f"/api/front-groups/{main_id}/qualified-mentors")).status_code == 403
        listing = (await co1.get("/api/front-groups")).json()["items"]
        assert [item.get("member_view") for item in listing] == [True] and "team_count" not in listing[0]

        # Sin privilegio de líder no puede crear ni asignar.
        assert (await leader1.post("/api/front-groups", json={"name": "Mi grupo", "parent_group_id": main_id})).status_code == 403
        assert (await leader1.put(f"/api/front-groups/{main_id}/conform", json={"name": "Robado"})).status_code == 403
        assert (await leader1.post(f"/api/front-groups/{main_id}/leader-privilege", json={"person_id": leader1_id})).status_code == 403
        assert all(not item["can_create"] for item in (await leader1.get("/api/core/me/front-groups")).json()["items"])
        # Solo a integrantes del grupo, y con cuenta activa.
        assert (await pastora.post(f"/api/front-groups/{main_id}/leader-privilege", json={"person_id": pastor_co_id})).status_code == 422
        assert (await pastora.post(f"/api/front-groups/{main_id}/leader-privilege", json={"person_id": solo_id})).status_code == 409

        # Pareja: la pastora asigna a ambos (uno líder, el otro colíder del nuevo grupo).
        granted = await pastora.post(f"/api/front-groups/{main_id}/leader-privilege", json={"person_id": leader1_id, "co_leader_person_id": co1_id})
        assert granted.status_code == 201, granted.text
        child_id = granted.json()["front_group_id"]
        assert granted.json()["status"] == "pending_formation"
        assert (await pastora.post(f"/api/front-groups/{main_id}/leader-privilege", json={"person_id": leader1_id})).json()["front_group_id"] == child_id
        roster = (await pastora.get(f"/api/front-groups/{main_id}/roster")).json()
        pair = next(entry for entry in roster["entries"] if entry["type"] == "pair")
        privileges = {card["person_id"]: card["leader_privilege"] for card in pair["people"]}
        assert privileges[leader1_id]["as"] == "leader" and privileges[co1_id]["as"] == "co_leader"
        assert privileges[leader1_id]["front_group_id"] == child_id
        pending = [item for item in (await leader1.get("/api/core/me/front-groups")).json()["items"] if item["front_group_id"] == child_id][0]
        assert pending["can_create"] is True and pending["my_role"] == "leader"
        assert pending["from_group_name"] == "Grupo de la Pastora" and pending["from_pastoral_main"] is True
        assert pending["assigned_by_name"] == "Cuenta 5C"

        # Crea su grupo: elige colíder, organiza miembros en individuos y parejas.
        new_co_id, member_a, member_b, member_c = (await fx.person("NuevoColider"), await fx.person("MiembroA"), await fx.person("MiembroB"), await fx.person("MiembroC"))
        member_a_client = await fx.account(member_a, "persona")
        conformed = await leader1.put(f"/api/front-groups/{child_id}/conform", json={"name": "Grupo de LiderUno", "co_leader_person_id": new_co_id})
        assert conformed.status_code == 200, conformed.text
        assert conformed.json()["status"] == "active"
        child_roster = await leader1.put(f"/api/front-groups/{child_id}/roster", json={"entries": [{"person_ids": [member_a, member_b]}, {"person_ids": [member_c]}]})
        assert child_roster.status_code == 200, child_roster.text
        assert child_roster.json()["totals"] == {"people": 3, "pairs": 1, "individuals": 1}
        assert await server.db.front_group_assignments.count_documents({"front_group_id": child_id, "role": "co_leader", "active": True}) == 1
        assert await server.db.front_group_assignments.count_documents({"front_group_id": child_id, "role": "leader", "active": True}) == 1
        # El líder de una rama no ve el conjunto del grupo de la pastora.
        assert (await leader1.get(f"/api/front-groups/{main_id}")).json().get("member_view") is True
        assert (await leader1.get(f"/api/front-groups/{main_id}/roster")).status_code == 403
        # El miembro ve a qué grupo pertenece, con su líder y colíder, y nada más.
        member_groups = (await member_a_client.get("/api/core/me/front-groups")).json()["items"]
        assert [(item["name"], item["leader_name"], item["co_leader_name"]) for item in member_groups] == [("Grupo de LiderUno", "LiderUno Etapa5C", "NuevoColider Etapa5C")]
        assert "assignments" not in (await member_a_client.get(f"/api/front-groups/{child_id}")).json()

        # Una sola persona líder activa y un solo colíder por grupo.
        assert (await pastora.post(f"/api/front-groups/{child_id}/leader", json={"person_id": leader2_id, "reason": "Relevo"})).status_code == 200
        assert (await pastora.post(f"/api/front-groups/{child_id}/co-leader", json={"person_id": co1_id, "reason": "Relevo"})).status_code == 200
        assert await server.db.front_group_assignments.count_documents({"front_group_id": child_id, "role": "leader", "active": True}) == 1
        assert await server.db.front_group_assignments.count_documents({"front_group_id": child_id, "role": "co_leader", "active": True}) == 1
        assert (await leader2.post(f"/api/front-groups/{child_id}/co-leader", json={"person_id": leader2_id, "reason": "Mismo"})).status_code == 422
    finally:
        await fx.cleanup()


@pytest.mark.asyncio
async def test_structure_levels_permissions_and_distinct_totals():
    """5C-2: pastora → líder → grupo del líder → otro líder → su grupo."""
    await server.db.front_groups.update_many({"pastoral_main": True}, {"$unset": {"pastoral_main": ""}})
    fx = Fixture()
    try:
        pastora = await fx.account(await fx.person("PastoraE"), "pastora")
        coordinator = await fx.account(await fx.person("CoordE"), "lider", access_level="coordinador_general")
        luis_id, marta_id, pedro_id = await fx.person("LuisE"), await fx.person("MartaE"), await fx.person("PedroE")
        rosa_id, juan_id, nina_id = await fx.person("RosaE"), await fx.person("JuanE"), await fx.person("NinaE")
        luis = await fx.account(luis_id, "lider", capabilities=[], permissions_mode="manual")
        rosa = await fx.account(rosa_id, "persona")
        nina = await fx.account(nina_id, "persona")

        main_id = (await pastora.put("/api/pastoral-front-group", json={"name": "Grupo PastoraE"})).json()["group"]["front_group_id"]
        await pastora.put(f"/api/front-groups/{main_id}/roster", json={"entries": [{"person_ids": [luis_id, marta_id]}, {"person_ids": [pedro_id]}]})
        child_id = (await pastora.post(f"/api/front-groups/{main_id}/leader-privilege", json={"person_id": luis_id, "co_leader_person_id": marta_id})).json()["front_group_id"]
        await luis.put(f"/api/front-groups/{child_id}/conform", json={"name": "Grupo LuisE"})
        await luis.put(f"/api/front-groups/{child_id}/roster", json={"entries": [{"person_ids": [rosa_id, juan_id]}, {"person_ids": [pedro_id]}]})
        grandchild = await luis.post(f"/api/front-groups/{child_id}/leader-privilege", json={"person_id": rosa_id})
        assert grandchild.status_code == 201, grandchild.text
        grandchild_id = grandchild.json()["front_group_id"]
        await rosa.put(f"/api/front-groups/{grandchild_id}/conform", json={"name": "Grupo RosaE"})
        await rosa.put(f"/api/front-groups/{grandchild_id}/roster", json={"entries": [{"person_ids": [nina_id]}]})

        start = (await pastora.get("/api/front-group-structure/start")).json()
        assert start["scope"] == "global" and [item["front_group_id"] for item in start["groups"]] == [main_id]
        node = (await pastora.get(f"/api/front-group-structure/groups/{main_id}")).json()
        assert node["group"]["direct"] == {"people": 3, "pairs": 1, "individuals": 1}
        # Rama: Luis, Marta, Pedro, Rosa, Juan, Nina = 6 personas distintas (Luis/Marta/Rosa son
        # integrantes de un grupo y líderes de otro; Pedro está en dos grupos). La pastora supervisa:
        # no cuenta como integrante ni como líder operativo.
        assert node["group"]["branch"] == {"groups": 3, "people": 6, "pairs": 2, "leaders": 3}
        assert [child["front_group_id"] for child in node["children"]] == [child_id]
        assert node["children"][0]["leader"]["person_id"] == luis_id
        assert (await coordinator.get(f"/api/front-group-structure/groups/{grandchild_id}")).status_code == 200

        # El líder explora solo su rama y vuelve por niveles hasta su grupo.
        luis_start = (await luis.get("/api/front-group-structure/start")).json()
        assert luis_start["scope"] == "branch" and [item["front_group_id"] for item in luis_start["groups"]] == [child_id]
        assert (await luis.get(f"/api/front-group-structure/groups/{main_id}")).status_code == 403
        luis_child = (await luis.get(f"/api/front-group-structure/groups/{child_id}")).json()
        assert luis_child["parent"]["name"] == "Grupo PastoraE" and luis_child["parent"]["explorable"] is False
        deep = (await luis.get(f"/api/front-group-structure/groups/{grandchild_id}")).json()
        assert [item["front_group_id"] for item in deep["breadcrumbs"]] == [child_id]
        assert deep["roster"]["totals"]["people"] == 1
        # Rosa (líder del nivel más bajo) no sube a la rama de Luis.
        assert (await rosa.get(f"/api/front-group-structure/groups/{child_id}")).status_code == 403
        # Un integrante final no explora estructura.
        assert (await nina.get("/api/front-group-structure/start")).json()["groups"] == []
        assert (await nina.get(f"/api/front-group-structure/groups/{grandchild_id}")).status_code == 403
    finally:
        await fx.cleanup()


@pytest.mark.asyncio
async def test_group_stats_semaphore_ranking_and_no_double_count():
    """5C-3: métricas desde los mismos registros de invasión, semáforo
    configurable, comparación entre grupos y ranking de integrantes."""
    await server.db.front_groups.update_many({"pastoral_main": True}, {"$unset": {"pastoral_main": ""}})
    fx = Fixture()
    campaign_id = f"camp-5c3-{uuid.uuid4().hex}"
    try:
        pastora_id_s = await fx.person("PastoraS")
        pastora = await fx.account(pastora_id_s, "pastora")
        luis_id, marta_id, pedro_id, rosa_id, juan_id = [await fx.person(name) for name in ("LuisS", "MartaS", "PedroS", "RosaS", "JuanS")]
        luis = await fx.account(luis_id, "lider", capabilities=[], permissions_mode="manual")
        rosa = await fx.account(rosa_id, "persona")
        main_id = (await pastora.put("/api/pastoral-front-group", json={"name": "Grupo PastoraS"})).json()["group"]["front_group_id"]
        await pastora.put(f"/api/front-groups/{main_id}/roster", json={"entries": [{"person_ids": [luis_id, marta_id]}, {"person_ids": [pedro_id]}]})
        child_id = (await pastora.post(f"/api/front-groups/{main_id}/leader-privilege", json={"person_id": luis_id, "co_leader_person_id": marta_id})).json()["front_group_id"]
        await luis.put(f"/api/front-groups/{child_id}/conform", json={"name": "Grupo LuisS"})
        await luis.put(f"/api/front-groups/{child_id}/roster", json={"entries": [{"person_ids": [rosa_id, juan_id]}, {"person_ids": [pedro_id]}]})

        now = datetime.now(timezone.utc)
        await server.db.outreach_campaigns.insert_one({"_id": campaign_id, "campaign_id": campaign_id, "name": "Invasión 5C3", "start_date": now.date().isoformat(), "end_date": now.date().isoformat(), "created_at": now})
        events = [(luis_id, "contacted"), (luis_id, "no_answer"), (rosa_id, "no_answer"), (rosa_id, "no_answer"), (rosa_id, "not_home")]
        await server.db.outreach_visit_events.insert_many([{"_id": f"{campaign_id}-e{index}", "visit_event_id": f"{campaign_id}-e{index}", "household_id": f"{campaign_id}-h", "campaign_id": campaign_id, "mentor_person_id": mentor, "result": result, "occurred_at": now, "created_at": now} for index, (mentor, result) in enumerate(events)])
        await server.db.outreach_visits.insert_one({"_id": f"{campaign_id}-v", "visit_id": f"{campaign_id}-v", "campaign_id": campaign_id, "mentor_person_id": luis_id, "status": "wants_followup", "archived": False, "created_at": now})
        await server.db.outreach_households.insert_one({"_id": f"{campaign_id}-h", "household_id": f"{campaign_id}-h", "campaign_id": campaign_id, "mentor_person_id": rosa_id, "archived": False, "created_at": now})

        stats = await pastora.get(f"/api/front-group-structure/groups/{main_id}/stats", params={"period": "invasion", "campaign_id": campaign_id})
        assert stats.status_code == 200, stats.text
        body = stats.json()
        branch = body["branch"]
        # 5 personas distintas (Pedro está en dos grupos; Luis/Marta son integrantes y líderes);
        # la pastora no cuenta como participante.
        assert branch["people"] == 5 and branch["leaders"] == 2
        assert branch["attempts"] == 5 and branch["attempts_by_result"]["no_answer"] == 3
        assert branch["persons_reached"] == 1 and branch["followups"] == 1 and branch["households"] == 1
        assert branch["participants"] == 2 and branch["semaphore_reasons"]["participation"] == "yellow"
        child = body["children"][0]
        assert child["front_group_id"] == child_id and child["people"] == 5 and child["attempts"] == 5
        # Ranking dentro del grupo de la pastora: Luis avanza más; quienes no tienen actividad necesitan apoyo.
        group_rank = {row["person_id"]: row for row in body["ranking_group"]}
        assert body["ranking_group"][0]["person_id"] == luis_id and group_rank[luis_id]["highlight"] == "top"
        assert group_rank[luis_id]["score"] == 3 * 1 + 2
        assert group_rank[pedro_id]["highlight"] == "needs_support"
        assert len(body["ranking_branch"]) == 5
        assert pastora_id_s not in {row["person_id"] for row in body["ranking_branch"] + body["ranking_group"]}
        assert {row["person_id"] for row in body["ranking_branch"] if row["highlight"] == "top"} == {luis_id, rosa_id}
        assert sum(point["attempts"] for point in body["timeline"]) == 5
        assert "personas alcanzadas×3" in body["criteria"]["score"]

        week = (await pastora.get(f"/api/front-group-structure/groups/{main_id}/stats", params={"period": "week"})).json()
        assert week["branch"]["attempts"] == 5
        # Umbral configurable: subirlo cambia el semáforo (y se restaura).
        assert (await pastora.put("/api/supervision/thresholds/participation_ratio_yellow", json={"value": 0.5})).status_code == 200
        stricter = (await pastora.get(f"/api/front-group-structure/groups/{main_id}/stats", params={"period": "invasion", "campaign_id": campaign_id})).json()
        assert stricter["branch"]["semaphore_reasons"]["participation"] == "red" and stricter["branch"]["semaphore"] == "red"
        assert (await pastora.put("/api/supervision/thresholds/participation_ratio_yellow", json={"value": 0.3})).status_code == 200

        # Permisos: el líder ve su rama pero no la de la pastora; un integrante no ve estadísticas.
        assert (await luis.get(f"/api/front-group-structure/groups/{main_id}/stats")).status_code == 403
        assert (await luis.get(f"/api/front-group-structure/groups/{child_id}/stats", params={"period": "all"})).json()["branch"]["people"] == 5
        assert (await rosa.get(f"/api/front-group-structure/groups/{child_id}/stats")).status_code == 403
        assert (await rosa.get("/api/front-group-structure/campaigns")).status_code == 403
    finally:
        for collection in ("outreach_visit_events", "outreach_visits", "outreach_households", "outreach_campaigns"):
            await server.db[collection].delete_many({"campaign_id": campaign_id})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_activity_panel_teams_classes_and_member_activity():
    """Panel dinámico: un recuadro por equipo (pareja/individuo + liderazgo),
    clase A/B/C = semáforo configurable, % de avance relativo, asistencia y
    apoyo desde Persona 360/Operaciones, datos inexistentes declarados."""
    await server.db.front_groups.update_many({"pastoral_main": True}, {"$unset": {"pastoral_main": ""}})
    fx = Fixture()
    tag = uuid.uuid4().hex
    try:
        pastora_id = await fx.person("PastoraP")
        pastora = await fx.account(pastora_id, "pastora")
        luis_id, marta_id, pedro_id, rosa_id = [await fx.person(name) for name in ("LuisP", "MartaP", "PedroP", "RosaP")]
        luis = await fx.account(luis_id, "lider", capabilities=[], permissions_mode="manual")
        rosa = await fx.account(rosa_id, "persona")
        main_id = (await pastora.put("/api/pastoral-front-group", json={"name": "Grupo PastoraP"})).json()["group"]["front_group_id"]
        await pastora.put(f"/api/front-groups/{main_id}/roster", json={"entries": [{"person_ids": [luis_id, marta_id]}, {"person_ids": [pedro_id]}]})
        child_id = (await pastora.post(f"/api/front-groups/{main_id}/leader-privilege", json={"person_id": luis_id})).json()["front_group_id"]
        await luis.put(f"/api/front-groups/{child_id}/conform", json={"name": "Grupo LuisP"})
        await luis.put(f"/api/front-groups/{child_id}/roster", json={"entries": [{"person_ids": [rosa_id]}]})
        now = datetime.now(timezone.utc)
        await server.db.outreach_visit_events.insert_many([{"_id": f"{tag}-e{i}", "visit_event_id": f"{tag}-e{i}", "household_id": f"{tag}-h", "mentor_person_id": luis_id, "result": "no_answer", "occurred_at": now, "created_at": now} for i in range(3)])
        await server.db.outreach_visits.insert_one({"_id": f"{tag}-v", "visit_id": f"{tag}-v", "mentor_person_id": luis_id, "status": "assigned", "archived": False, "created_at": now})
        await server.db.person_attendance.insert_many([
            {"_id": f"{tag}-a1", "person_id": marta_id, "fecha": now.date().isoformat(), "actividad": "Culto", "estado": "presente"},
            {"_id": f"{tag}-a2", "person_id": marta_id, "fecha": now.isoformat(), "actividad": "Evento", "estado": "presente"},
            {"_id": f"{tag}-a3", "person_id": pedro_id, "fecha": now.date().isoformat(), "actividad": "Culto", "estado": "ausente"},
        ])
        await server.db.operation_volunteer_assignments.insert_one({"_id": f"{tag}-s", "assignment_id": f"{tag}-s", "person_id": pedro_id, "shift_id": f"{tag}-shift", "status": "confirmed", "assigned_at": now})
        await server.db.mentor_badges.insert_one({"_id": f"{tag}-b", "person_id": marta_id, "active": True})

        panel = await pastora.get(f"/api/front-group-structure/groups/{main_id}/panel", params={"period": "week"})
        assert panel.status_code == 200, panel.text
        body = panel.json()
        # La pastora (único integrante del liderazgo de su grupo) no aparece: no hay recuadro de liderazgo.
        assert [team["type"] for team in body["teams"]] == ["pair", "individual"]
        assert pastora_id not in {member["person_id"] for team in body["teams"] for member in team["members"]}
        pair = body["teams"][0]
        members = {member["person_id"]: member for member in pair["members"]}
        assert "Líder de su grupo" in members[luis_id]["functions"] and members[luis_id]["led_group"]["front_group_id"] == child_id
        assert "Mentor" in members[marta_id]["functions"]
        assert members[marta_id]["metrics"]["attendance"] == 2 and members[luis_id]["metrics"]["attempts"] == 3
        assert pair["summary"]["participants"] == 1 and pair["summary"]["participation_ratio"] == 0.5
        # Metas (valores iniciales 'propuesta'): asistencia 80%, actividades 50%, invasiones 60%, 1 persona/integrante/semana.
        goals = {item["key"]: item for item in pair["goals"]}
        assert goals["attendance"]["value"] == 0.5 and goals["attendance"]["goal"] == 0.8 and goals["attendance"]["progress"] == 0.625
        assert goals["activities"]["has_data"] is False and goals["activities"]["progress"] is None  # sin turnos ni actividades: sin datos, no 0%
        assert goals["outreach"]["progress"] == 0.833 and goals["persons_reached"]["goal"] == 1.0 and goals["persons_reached"]["progress"] == 0.5
        assert goals["attendance"]["goal_status"] == "propuesta"
        assert pair["summary"]["overall_progress"] == 0.653 and pair["summary"]["class"] == "B" and pair["summary"]["rank"] == 1
        assert pair["summary"]["relative_pct"] == 100
        solo = body["teams"][1]
        assert solo["summary"]["support_shifts"] == 1 and solo["summary"]["attendance"] == 0
        solo_goals = {item["key"]: item for item in solo["goals"]}
        assert solo_goals["attendance"]["has_data"] is True and solo_goals["attendance"]["progress"] == 0  # registro 'ausente': 0% real
        assert solo_goals["outreach"]["has_data"] is False and solo["summary"]["overall_progress"] == 0.5 and solo["summary"]["class"] == "B"
        assert solo["summary"]["rank"] == 2
        assert body["group"]["people"] == 3 and body["group"]["teams"] == 2
        assert body["group"]["class"] == "C" and body["group"]["overall_progress"] == 0.492
        assert body["can_edit_goals"] is True and "goal_progress_green" in body["criteria"]["goals"]
        member_goals = {item["key"]: item for item in members[marta_id]["goals"]["indicators"]}
        assert member_goals["attendance"]["value"] == 1
        assert {item["key"] for item in body["unavailable"]} == {"group_meetings", "brought_to_church"}

        # Actividad individual: la pastora ve a todos; el líder solo a su rama; un integrante a nadie.
        activity = await pastora.get(f"/api/front-group-structure/people/{luis_id}/activity", params={"period": "week"})
        assert activity.status_code == 200 and activity.json()["in_period"]["attempts"] == 3
        assert {"as_person", "as_mentor", "as_leader"} <= set(activity.json())
        assert (await luis.get(f"/api/front-group-structure/people/{rosa_id}/activity")).status_code == 200
        assert (await luis.get(f"/api/front-group-structure/people/{pastora_id}/activity")).status_code == 403
        assert (await luis.get(f"/api/front-group-structure/groups/{main_id}/panel")).status_code == 403
        assert (await luis.get(f"/api/front-group-structure/groups/{child_id}/panel")).json()["can_edit_goals"] is False
        assert (await rosa.get(f"/api/front-group-structure/people/{luis_id}/activity")).status_code == 403
    finally:
        await server.db.outreach_visit_events.delete_many({"_id": {"$regex": f"^{tag}"}})
        await server.db.outreach_visits.delete_many({"_id": f"{tag}-v"})
        await server.db.person_attendance.delete_many({"_id": {"$regex": f"^{tag}"}})
        await server.db.operation_volunteer_assignments.delete_many({"_id": f"{tag}-s"})
        await server.db.mentor_badges.delete_many({"_id": f"{tag}-b"})
        await fx.cleanup()
