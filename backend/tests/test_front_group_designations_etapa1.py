"""Etapa 1 (Fundación de Grupos Frontales): pareja de liderazgo, designación,
'Conformar mi grupo frontal' (sin duplicar), alta rápida con coincidencias
(C4), baja/traslado de integrantes con historial, archivado bloqueado por
dependientes/procesos, invitaciones de acceso (C5) y aislamiento por rama
(RBAC real: líder/colíder por designación, no por capability manual)."""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "Etapa1Pass2026!"


async def cleanup_qa():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


async def create_person(label: str) -> str:
    person_id = ObjectId()
    now = datetime.now(timezone.utc)
    await server.db.persons.insert_one({
        "_id": person_id, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA", "apellido": label, "search_key": f"qa {label}".lower(),
        "idempotency_key": f"qa:etapa1:{uuid.uuid4()}", "version": 1,
        "created_at": now, "updated_at": now,
    })
    return str(person_id)


async def create_user(label: str, role: str, person_id: str | None = None) -> str:
    user_id = ObjectId(); email = f"qa.etapa1.{uuid.uuid4().hex[:8]}@example.com"
    defaults = access_defaults_for_role(role)
    await server.db.users.insert_one({
        "_id": user_id, "nombre": f"QA {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "is_active": True, "token_version": 1,
        "created_at": datetime.now(timezone.utc), **defaults,
        **({"person_id": person_id} if person_id else {}),
    })
    return email


async def auth_with_password(email: str, password: str) -> tuple[AsyncClient, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client, {"Authorization": f"Bearer {response.json()['token']}"}


async def auth(email: str) -> tuple[AsyncClient, dict]:
    return await auth_with_password(email, PASSWORD)


async def create_account_with_invitation(client, headers, person_id, slug) -> dict:
    """C5: cuenta creada SIN contraseña temporal -> se emite invitación."""
    email = f"qa.etapa1.{slug}.{uuid.uuid4().hex[:6]}@example.com"
    resp = await client.post("/api/core/governance/users", json={
        "person_id": person_id, "email": email, "access_level": "persona",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body.get("invitation_token"), "se esperaba un token de invitación al no dar contraseña temporal"
    return {"email": email, "invitation_token": body["invitation_token"]}


def find_node(nodes, group_id):
    for node in nodes:
        if node["front_group_id"] == group_id:
            return node
        found = find_node(node.get("children", []), group_id)
        if found:
            return found
    return None


@pytest.mark.asyncio
async def test_designation_leader_pair_conform_quick_person_and_rbac():
    await cleanup_qa()
    pastor_email = await create_user("Pastora Matriz", "pastor")
    pastor, pastor_h = await auth(pastor_email)
    leader_pid = await create_person("Lider Designado")
    coleader_pid = await create_person("Colider Designado")
    outsider_pid = await create_person("Lider Rama B")
    leader = coleader = outsider = None
    try:
        root = await pastor.post("/api/front-groups", json={"name": f"QA Matriz Etapa1 {uuid.uuid4().hex[:5]}"}, headers=pastor_h)
        assert root.status_code == 201, root.text
        root_id = root.json()["front_group_id"]

        # A3: la pastora designa la pareja; el grupo dependiente se crea en el acto
        designation = await pastor.post(f"/api/front-groups/{root_id}/designations", json={
            "leader_person_id": leader_pid, "co_leader_person_id": coleader_pid, "reason": "QA designación inicial",
        }, headers=pastor_h)
        assert designation.status_code == 201, designation.text
        group_id = designation.json()["front_group_id"]
        assert designation.json()["status"] == "pending_formation"
        assert designation.json()["display_name"] == "Equipo de QA Lider Designado"

        # Idempotencia: repetir la designación con el mismo líder/padre NO crea otro grupo
        repeat = await pastor.post(f"/api/front-groups/{root_id}/designations", json={
            "leader_person_id": leader_pid, "co_leader_person_id": coleader_pid,
        }, headers=pastor_h)
        assert repeat.status_code == 201
        assert repeat.json()["front_group_id"] == group_id
        assert await server.db.front_groups.count_documents({"parent_group_id": root_id, "primary_leader_person_id": leader_pid}) == 1

        # Cuentas para el líder y colíder designados (invitación, sin contraseña escrita por la pastora)
        leader_acc = await create_account_with_invitation(pastor, pastor_h, leader_pid, "lider")
        coleader_acc = await create_account_with_invitation(pastor, pastor_h, coleader_pid, "colider")

        accept_leader = await pastor.post("/api/auth/accept-invitation", json={"token": leader_acc["invitation_token"], "new_password": "LiderNueva2026!"})
        assert accept_leader.status_code == 200, accept_leader.text
        reuse_token = await pastor.post("/api/auth/accept-invitation", json={"token": leader_acc["invitation_token"], "new_password": "Otra2026!!"})
        assert reuse_token.status_code == 400

        accept_coleader = await pastor.post("/api/auth/accept-invitation", json={"token": coleader_acc["invitation_token"], "new_password": "ColiderNueva2026!"})
        assert accept_coleader.status_code == 200, accept_coleader.text

        leader, leader_h = await auth_with_password(leader_acc["email"], "LiderNueva2026!")
        coleader, coleader_h = await auth_with_password(coleader_acc["email"], "ColiderNueva2026!")

        # A4: el líder, SIN capability manual alguna, ve su designación en el árbol
        tree = await leader.get("/api/front-groups/tree", headers=leader_h)
        assert tree.status_code == 200, tree.text
        node = find_node(tree.json()["items"], group_id)
        assert node is not None, "el líder designado no ve su grupo pendiente de conformación"
        assert node["status"] == "pending_formation"
        assert node["permissions"]["manage"] is True

        # El colíder lo ve (alcance de soporte) pero no puede gestionarlo
        co_detail = await coleader.get(f"/api/front-groups/{group_id}", headers=coleader_h)
        assert co_detail.status_code == 200, co_detail.text
        assert co_detail.json()["permissions"]["support"] is True
        assert co_detail.json()["permissions"]["manage"] is False

        # A4: conformar el grupo (agrega un integrante existente); repetir es seguro (no duplica)
        member_pid = await create_person("Integrante Uno")
        conform = await leader.put(f"/api/front-groups/{group_id}/conform", json={
            "name": "Equipo QA Visión 2026", "member_person_ids": [member_pid],
        }, headers=leader_h)
        assert conform.status_code == 200, conform.text
        assert conform.json()["status"] == "active"
        conform_again = await leader.put(f"/api/front-groups/{group_id}/conform", json={"member_person_ids": [member_pid]}, headers=leader_h)
        assert conform_again.status_code == 200
        assert await server.db.front_group_assignments.count_documents({"front_group_id": group_id, "person_id": member_pid, "active": True}) == 1

        # C4: alta rápida — coincidencia POSIBLE bloquea sin confirmación, pasa con ella
        key1 = f"qa:etapa1:quick:{uuid.uuid4()}"
        quick1 = await leader.post(f"/api/front-groups/{group_id}/quick-person", json={
            "nombre": "QA", "apellido": "Integrante Uno", "idempotency_key": key1,
        }, headers=leader_h)
        assert quick1.status_code == 409
        assert quick1.json()["detail"]["requires_confirmation"] is True

        quick2 = await leader.post(f"/api/front-groups/{group_id}/quick-person", json={
            "nombre": "QA", "apellido": "Integrante Uno", "idempotency_key": key1,
            "confirm_distinct_person": True, "distinct_reason": "Es otra persona con nombre parecido",
        }, headers=leader_h)
        assert quick2.status_code == 201, quick2.text
        new_person_id = quick2.json()["person"]["person_id"]
        assert new_person_id != member_pid

        # El colíder SÍ puede dar de alta (soporte) pero NO designar pareja, mover ni dar de baja
        key2 = f"qa:etapa1:quick:{uuid.uuid4()}"
        co_quick = await coleader.post(f"/api/front-groups/{group_id}/quick-person", json={
            "nombre": "QA", "apellido": f"Alta Colider {uuid.uuid4().hex[:4]}", "idempotency_key": key2,
        }, headers=coleader_h)
        assert co_quick.status_code == 201, co_quick.text

        co_designate = await coleader.post(f"/api/front-groups/{group_id}/designations", json={"leader_person_id": member_pid}, headers=coleader_h)
        assert co_designate.status_code == 403
        co_move = await coleader.post(f"/api/front-groups/{group_id}/move", json={"reason": "QA intento"}, headers=coleader_h)
        assert co_move.status_code == 403
        co_end = await coleader.request("DELETE", f"/api/front-groups/{group_id}/members/{member_pid}", json={"reason": "QA intento"}, headers=coleader_h)
        assert co_end.status_code == 403

        # A4: el líder designa el siguiente nivel (tercer nivel en total)
        sub_leader_pid = await create_person("Lider Nivel 3")
        sub_designation = await leader.post(f"/api/front-groups/{group_id}/designations", json={"leader_person_id": sub_leader_pid}, headers=leader_h)
        assert sub_designation.status_code == 201, sub_designation.text
        sub_group_id = sub_designation.json()["front_group_id"]
        assert sub_designation.json()["display_name"] == "Equipo de QA Lider Nivel 3"

        # La pastora ve toda la estructura, incluido el tercer nivel
        pastor_tree = await pastor.get("/api/front-groups/tree", headers=pastor_h)
        assert find_node(pastor_tree.json()["items"], sub_group_id) is not None

        # E3: un líder de OTRA rama no lee ni escribe en este grupo
        outsider_root = await pastor.post("/api/front-groups", json={"name": f"QA Rama B {uuid.uuid4().hex[:5]}"}, headers=pastor_h)
        assert outsider_root.status_code == 201
        outsider_designation = await pastor.post(f"/api/front-groups/{outsider_root.json()['front_group_id']}/designations", json={"leader_person_id": outsider_pid}, headers=pastor_h)
        assert outsider_designation.status_code == 201
        outsider_acc = await create_account_with_invitation(pastor, pastor_h, outsider_pid, "outsider")
        outsider_accept = await pastor.post("/api/auth/accept-invitation", json={"token": outsider_acc["invitation_token"], "new_password": "OutsiderNueva2026!"})
        assert outsider_accept.status_code == 200
        outsider, outsider_h = await auth_with_password(outsider_acc["email"], "OutsiderNueva2026!")
        outsider_read = await outsider.get(f"/api/front-groups/{group_id}", headers=outsider_h)
        assert outsider_read.status_code == 403
        outsider_tree = await outsider.get("/api/front-groups/tree", headers=outsider_h)
        assert find_node(outsider_tree.json()["items"], group_id) is None

        # Baja de integrante con historial (motivo registrado) + traslado a otro grupo
        end = await leader.request("DELETE", f"/api/front-groups/{group_id}/members/{member_pid}", json={"reason": "QA: se trasladó de ciudad"}, headers=leader_h)
        assert end.status_code == 200, end.text
        assert await server.db.front_group_assignments.count_documents({"front_group_id": group_id, "person_id": member_pid, "active": False, "end_reason": "QA: se trasladó de ciudad"}) == 1

        transfer = await leader.post(f"/api/front-groups/{group_id}/members/transfer", json={
            "person_id": new_person_id, "to_group_id": sub_group_id, "reason": "QA: pasa a apoyar el nuevo grupo",
        }, headers=leader_h)
        assert transfer.status_code == 200, transfer.text
        assert await server.db.front_group_assignments.count_documents({"front_group_id": sub_group_id, "person_id": new_person_id, "active": True}) == 1
        assert await server.db.front_group_assignments.count_documents({"front_group_id": group_id, "person_id": new_person_id, "active": True}) == 0

        # Archivar bloqueado mientras tenga un grupo dependiente activo
        blocked_archive = await leader.post(f"/api/front-groups/{group_id}/archive", json={"reason": "QA intento"}, headers=leader_h)
        assert blocked_archive.status_code == 409
        leaf_archive = await leader.post(f"/api/front-groups/{sub_group_id}/archive", json={"reason": "QA: cierre de prueba"}, headers=leader_h)
        assert leaf_archive.status_code == 200, leaf_archive.text
        assert leaf_archive.json()["status"] == "archived"

        # Historial de auditoría disponible
        history = await leader.get(f"/api/front-groups/{group_id}/history", headers=leader_h)
        assert history.status_code == 200
        actions = {item["action"] for item in history.json()["items"]}
        assert {"group_conformed", "member_quick_created", "member_ended", "member_transferred_out"}.issubset(actions)
    finally:
        for client in (pastor, leader, coleader, outsider):
            if client is not None:
                await client.aclose()
        await cleanup_qa()
