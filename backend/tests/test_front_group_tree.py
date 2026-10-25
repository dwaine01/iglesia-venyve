"""Grupo Frontal unificado › «Mis ramas»: árbol hacia abajo (pastora → equipos
líder+colíder → el grupo de cada líder → sus integrantes), «Todavía no ha
formado su grupo» + «Formar grupo» con permisos, personas sin contar dos veces,
un líder ve solo su rama (nunca hacia arriba ni ramas ajenas) y el trabajo de
los líderes de su rama."""
import uuid

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_branch_tree_form_and_scopes():
    await db.front_groups.update_many({"pastoral_main": True}, {"$unset": {"pastoral_main": ""}})
    fx = Fixture()
    tag = uuid.uuid4().hex[:6]
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        luis_id, luis_co, ana_id, ana_co, solo = [await fx.person(f"{name}{tag}") for name in ("Luis", "LuisCo", "Ana", "AnaCo", "Solo")]
        luis = await fx.account(luis_id, "persona")
        ana = await fx.account(ana_id, "persona")
        main = (await pastora.put("/api/pastoral-front-group", json={"name": f"Casa de Cornelio {tag}"})).json()["group"]
        gid = main["front_group_id"]
        saved = await pastora.put(f"/api/front-groups/{gid}/roster", json={"entries": [{"person_ids": [luis_id, luis_co]}, {"person_ids": [ana_id, ana_co]}, {"person_ids": [solo]}]})
        assert saved.status_code == 200, saved.text

        tree = (await pastora.get("/api/front-group-structure/tree")).json()
        root = tree["root"]
        assert root["front_group_id"] == gid and root["teams_total"] == 2 and root["groups_formed"] == 0 and root["people_branch"] == 5
        assert [item["name"] for item in root["individuals"]] == [f"Solo{tag} Etapa5C"]
        team = next(item for item in root["teams"] if item["leader"]["person_id"] == luis_id)
        assert team["status"] == "not_designated" and team["can_form"] and team["co_leader"]["person_id"] == luis_co

        # Luis todavía no lidera: ve su equipo pendiente y puede formarlo él mismo.
        mine = (await luis.get("/api/front-group-structure/tree")).json()
        assert mine["root"] is None and mine["my_team"]["parent_group_id"] == gid and mine["my_team"]["direct_leader"] == f"Pastora{tag} Etapa5C"
        assert (await ana.post("/api/front-group-structure/form", json={"parent_group_id": gid, "person_ids": [luis_id, luis_co]})).status_code == 403
        formed = await luis.post("/api/front-group-structure/form", json={"parent_group_id": gid, "person_ids": [luis_id, luis_co]})
        assert formed.status_code == 200, formed.text
        luis_gid = formed.json()["front_group_id"]
        again = (await luis.post("/api/front-group-structure/form", json={"parent_group_id": gid, "person_ids": [luis_id, luis_co]})).json()
        assert again["front_group_id"] == luis_gid  # sin duplicar
        pending = next(item for item in (await pastora.get("/api/front-group-structure/tree")).json()["root"]["teams"] if item["leader"]["person_id"] == luis_id)
        assert pending["status"] == "pending" and pending["pending_group_id"] == luis_gid
        # La pastora (líder superior) también puede conformarlo; aquí lo conforma Luis.
        assert (await luis.put(f"/api/front-groups/{luis_gid}/conform", json={"name": f"Grupo de Luis {tag}"})).status_code == 200
        m1, m2 = await fx.person(f"Marta{tag}"), await fx.person(f"Pedro{tag}")
        assert (await luis.put(f"/api/front-groups/{luis_gid}/roster", json={"entries": [{"person_ids": [m1, m2]}]})).status_code == 200

        root = (await pastora.get("/api/front-group-structure/tree")).json()["root"]
        branch = next(item for item in root["teams"] if item["leader"]["person_id"] == luis_id)
        assert branch["status"] == "formed" and branch["group"]["name"] == f"Grupo de Luis {tag}" and branch["group"]["people_branch"] == 4
        assert branch["group"]["teams"][0]["status"] == "not_designated"
        assert root["people_branch"] == 7 and root["groups_formed"] == 1  # Luis y su colíder cuentan una sola vez

        # Luis ve SU rama hacia abajo y solo el nombre de su líder directo; nunca el grupo de la pastora ni el de Ana.
        mine = (await luis.get("/api/front-group-structure/tree")).json()
        assert mine["root"]["front_group_id"] == luis_gid and mine["direct_leader"]["person_id"] is not None and "Casa de Cornelio" not in str(mine)
        assert (await luis.get("/api/front-group-structure/tree", params={"root": gid})).status_code == 403
        assert (await ana.get("/api/front-group-structure/tree", params={"root": luis_gid})).status_code == 403
        # Trabajo del líder: la pastora ve a Luis; Luis no ve hacia arriba; Ana no ve a Luis.
        assert (await pastora.get("/api/my-work/leader-detail", params={"mentor_person_id": luis_id})).status_code == 200
        assert (await luis.get("/api/my-work/leader-detail", params={"mentor_person_id": pastora_person(fx)})).status_code == 403
        assert (await ana.get("/api/my-work/leader-detail", params={"mentor_person_id": luis_id})).status_code == 403
    finally:
        groups = await db.front_groups.distinct("front_group_id", {"$or": [{"name": {"$regex": tag}}, {"primary_leader_person_id": {"$in": fx.person_ids}}]})
        await db.front_groups.delete_many({"front_group_id": {"$in": groups}})
        await db.front_group_assignments.delete_many({"front_group_id": {"$in": groups}})
        await db.front_group_audit_events.delete_many({"front_group_id": {"$in": groups}})
        await fx.cleanup()


def pastora_person(fx) -> str:
    return fx.person_ids[0]
