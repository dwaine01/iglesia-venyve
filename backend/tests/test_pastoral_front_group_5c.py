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
