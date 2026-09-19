"""Fases 0-1: archivado QA, árbol recursivo, rol dual y RBAC de rama."""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from front_group_phase0 import APPROVED_QA_GROUP_IDS
from qa_demo_cleanup import delete_qa_artifacts, qa_preview


PASSWORD = "FrontTreePass2026!"


async def cleanup_qa():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


async def create_person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id,
        "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA",
        "apellido": label,
        "search_key": f"qa {label}".lower(),
        "idempotency_key": f"qa:front-tree:{uuid.uuid4()}",
        "version": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None, capabilities=None) -> str:
    user_id = ObjectId(); email = f"qa.fronttree.{uuid.uuid4().hex[:8]}@example.com"
    defaults = access_defaults_for_role(role)
    if capabilities is not None:
        defaults["capabilities"] = capabilities
    await server.db.users.insert_one({
        "_id": user_id, "nombre": f"QA {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "is_active": True, "token_version": 1,
        "created_at": datetime.now(timezone.utc), **defaults,
        **({"person_id": person_id} if person_id else {}),
    })
    return email


async def auth(email: str) -> tuple[AsyncClient, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client, {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.mark.asyncio
async def test_phase0_archived_ids_are_preserved_and_excluded_from_active_views():
    assert await server.db.front_groups.count_documents({
        "front_group_id": {"$in": APPROVED_QA_GROUP_IDS}, "status": "archived"
    }) == 20
    assert await server.db.front_groups.count_documents({
        "front_group_id": {"$in": APPROVED_QA_GROUP_IDS}
    }) == 20
    assert await server.db.front_group_assignments.count_documents({
        "front_group_id": {"$in": APPROVED_QA_GROUP_IDS}, "active": True
    }) == 0
    assert await server.db.front_group_audit_events.count_documents({
        "front_group_id": {"$in": APPROVED_QA_GROUP_IDS}, "action": "qa_group_archived"
    }) == 20


@pytest.mark.asyncio
async def test_recursive_tree_dual_role_branch_rbac_and_care_separation():
    await cleanup_qa()
    pastor_email = await create_user("Pastor Árbol", "pastor")
    leader_person_id = await create_person("Líder Rama")
    leader_email = await create_user(
        "Líder Rama", "lider", leader_person_id,
        ["front_groups.view", "front_groups.manage"],
    )
    pastor, pastor_headers = await auth(pastor_email)
    leader, leader_headers = await auth(leader_email)
    try:
        root = await pastor.post("/api/front-groups", json={"name": "QA Raíz Realista"}, headers=pastor_headers)
        assert root.status_code == 201, root.text
        root_id = root.json()["front_group_id"]
        branch = await pastor.post("/api/front-groups", json={"name": "QA Rama", "parent_group_id": root_id}, headers=pastor_headers)
        assert branch.status_code == 201, branch.text
        branch_id = branch.json()["front_group_id"]
        subbranch = await pastor.post("/api/front-groups", json={"name": "QA Subrama", "parent_group_id": branch_id}, headers=pastor_headers)
        assert subbranch.status_code == 201, subbranch.text
        subbranch_id = subbranch.json()["front_group_id"]
        sibling = await pastor.post("/api/front-groups", json={"name": "QA Rama Hermana", "parent_group_id": root_id}, headers=pastor_headers)
        sibling_id = sibling.json()["front_group_id"]

        member = await pastor.post(f"/api/front-groups/{root_id}/members", json={"person_id": leader_person_id, "role": "member"}, headers=pastor_headers)
        assert member.status_code == 201, member.text
        led = await pastor.post(f"/api/front-groups/{branch_id}/leader", json={"person_id": leader_person_id, "reason": "Lidera su propia rama"}, headers=pastor_headers)
        assert led.status_code == 200, led.text

        listing = await leader.get("/api/front-groups", headers=leader_headers)
        assert listing.status_code == 200, listing.text
        groups = {item["front_group_id"]: item for item in listing.json()["items"]}
        assert {root_id, branch_id, subbranch_id}.issubset(groups)
        assert sibling_id not in groups
        assert groups[root_id]["permissions"]["manage"] is False
        assert groups[branch_id]["permissions"]["manage"] is True
        assert groups[subbranch_id]["permissions"]["manage"] is True

        assert (await leader.put(f"/api/front-groups/{root_id}", json={"description": "No permitido"}, headers=leader_headers)).status_code == 403
        assert (await leader.put(f"/api/front-groups/{sibling_id}", json={"description": "No permitido"}, headers=leader_headers)).status_code == 403
        assert (await leader.put(f"/api/front-groups/{subbranch_id}", json={"description": "Dentro de su rama"}, headers=leader_headers)).status_code == 200
        created_child = await leader.post("/api/front-groups", json={"name": "QA Nivel adicional", "parent_group_id": subbranch_id}, headers=leader_headers)
        assert created_child.status_code == 201, created_child.text
        assert created_child.json()["depth"] == 3
        assert (await leader.post("/api/front-groups", json={"name": "QA Raíz no permitida"}, headers=leader_headers)).status_code == 403

        cycle = await leader.post(f"/api/front-groups/{branch_id}/move", json={"parent_group_id": subbranch_id, "reason": "Debe bloquear ciclo"}, headers=leader_headers)
        assert cycle.status_code == 409, cycle.text
        tree = await leader.get("/api/front-groups/tree", headers=leader_headers)
        assert tree.status_code == 200, tree.text
        assert tree.json()["total"] >= 4
        assert (await leader.get("/api/care/dashboard", headers=leader_headers)).status_code == 403

        active = await pastor.get("/api/front-groups", headers=pastor_headers)
        assert all(item["front_group_id"] not in APPROVED_QA_GROUP_IDS for item in active.json()["items"])
        archived = await pastor.get("/api/front-groups?include_archived=true", headers=pastor_headers)
        assert any(item["front_group_id"] in APPROVED_QA_GROUP_IDS for item in archived.json()["items"])
    finally:
        await pastor.aclose(); await leader.aclose(); await cleanup_qa()