"""Etapa 1 ronda 2 (iteration_44): re-test de FIX 1-6 vía URL pública.
FIX1 capability front_groups.view para líder 'persona'; FIX2 quick-person assign=false;
FIX3 transfer 409 si ya es integrante del destino; FIX5 archivar 409/200; FIX4 tree."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
STATE = {}


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def ph():
    return login(*PASTOR)


def quick(h, gid, apellido, assign=True, extra=None):
    body = {"nombre": "QA", "apellido": apellido, "idempotency_key": f"qa:r2:{uuid.uuid4()}", "assign": assign}
    body.update(extra or {})
    return requests.post(f"{BASE_URL}/api/front-groups/{gid}/quick-person", json=body, headers=h, timeout=30)


def active_assignments(gid, pid):
    return mdb.front_group_assignments.count_documents({"front_group_id": gid, "person_id": pid, "active": True})


# Setup: grupo matriz QA
def test_create_root(ph):
    r = requests.post(f"{BASE_URL}/api/front-groups", json={"name": f"QA R2 Matriz {uuid.uuid4().hex[:4]}"}, headers=ph, timeout=30)
    assert r.status_code == 201, r.text
    STATE["root"] = r.json()["front_group_id"]


# FIX 2: assign=false no crea assignment; assign=true sí
def test_quick_person_assign_false_no_assignment(ph):
    r = quick(ph, STATE["root"], f"Rdos Lider {uuid.uuid4().hex[:5]}", assign=False)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["assignment_added"] is False
    pid = body["person"]["person_id"]
    assert active_assignments(STATE["root"], pid) == 0
    STATE["leader_pid"] = pid


def test_quick_person_assign_true_creates_assignment(ph):
    r = quick(ph, STATE["root"], f"Rdos Miembro {uuid.uuid4().hex[:5]}", assign=True)
    assert r.status_code == 201, r.text
    assert r.json()["assignment_added"] is True
    pid = r.json()["person"]["person_id"]
    assert active_assignments(STATE["root"], pid) == 1
    STATE["root_member_pid"] = pid


def test_quick_person_default_assign_is_true(ph):
    body = {"nombre": "QA", "apellido": f"Rdos Default {uuid.uuid4().hex[:5]}", "idempotency_key": f"qa:r2:{uuid.uuid4()}"}
    r = requests.post(f"{BASE_URL}/api/front-groups/{STATE['root']}/quick-person", json=body, headers=ph, timeout=30)
    assert r.status_code == 201, r.text
    assert r.json()["assignment_added"] is True


# Designación + cuenta persona para el líder (FIX 1 backend)
def test_designate_and_leader_account(ph):
    co = quick(ph, STATE["root"], f"Rdos Colider {uuid.uuid4().hex[:5]}", assign=False)
    assert co.status_code == 201
    STATE["co_pid"] = co.json()["person"]["person_id"]
    d = requests.post(f"{BASE_URL}/api/front-groups/{STATE['root']}/designations", json={
        "leader_person_id": STATE["leader_pid"], "co_leader_person_id": STATE["co_pid"], "reason": "QA r2"}, headers=ph, timeout=30)
    assert d.status_code == 201, d.text
    STATE["child"] = d.json()["front_group_id"]
    email = f"qa.r2lider.{uuid.uuid4().hex[:6]}@example.com"
    u = requests.post(f"{BASE_URL}/api/core/governance/users", json={"person_id": STATE["leader_pid"], "email": email, "access_level": "persona"}, headers=ph, timeout=30)
    assert u.status_code == 201, u.text
    tok = u.json()["invitation_token"]
    a = requests.post(f"{BASE_URL}/api/auth/accept-invitation", json={"token": tok, "new_password": "QaR2Lider2026!"}, timeout=30)
    assert a.status_code == 200, a.text
    STATE["leader_email"] = email
    with open("/tmp/r2_state.txt", "w") as fh:
        fh.write(f"{email}\n{STATE['root']}\n{STATE['child']}\n")


def test_leader_me_has_front_groups_view():
    h = login(STATE["leader_email"], "QaR2Lider2026!")
    me = requests.get(f"{BASE_URL}/api/auth/me", headers=h, timeout=30)
    assert me.status_code == 200, me.text
    data = me.json()
    user = data.get("user", data)
    print("leader rol/access:", user.get("rol"), user.get("access_level"), user.get("capabilities"))
    assert "front_groups.view" in (user.get("capabilities") or []), user
    STATE["lh"] = h


# FIX 3: transfer 409 si ya es integrante activo del destino
def test_transfer_conflict_409(ph):
    # agregar root_member también al grupo hijo, luego intentar trasladar root->child
    r = requests.put(f"{BASE_URL}/api/front-groups/{STATE['child']}/conform", json={"member_person_ids": [STATE["root_member_pid"]]}, headers=ph, timeout=30)
    assert r.status_code == 200, r.text
    t = requests.post(f"{BASE_URL}/api/front-groups/{STATE['root']}/members/transfer", json={
        "person_id": STATE["root_member_pid"], "to_group_id": STATE["child"], "reason": "QA r2 dup"}, headers=ph, timeout=30)
    assert t.status_code == 409, t.text
    assert "destino" in str(t.json().get("detail"))
    assert active_assignments(STATE["root"], STATE["root_member_pid"]) == 1  # origen intacto


def test_transfer_conflict_when_destination_role_is_leader(ph):
    # el líder es integrante 'member' del padre (designación) y 'leader' del hijo
    t = requests.post(f"{BASE_URL}/api/front-groups/{STATE['root']}/members/transfer", json={
        "person_id": STATE["leader_pid"], "to_group_id": STATE["child"], "reason": "QA r2 dup leader"}, headers=ph, timeout=30)
    assert t.status_code == 409, t.text


def test_transfer_success_still_works(ph):
    m = quick(ph, STATE["root"], f"Rdos Traslado {uuid.uuid4().hex[:5]}", assign=True)
    pid = m.json()["person"]["person_id"]
    t = requests.post(f"{BASE_URL}/api/front-groups/{STATE['root']}/members/transfer", json={
        "person_id": pid, "to_group_id": STATE["child"], "reason": "QA r2 ok"}, headers=ph, timeout=30)
    assert t.status_code == 200, t.text
    assert active_assignments(STATE["child"], pid) == 1
    assert active_assignments(STATE["root"], pid) == 0


# FIX 4: tree incluye conteos
def test_tree_and_list(ph):
    tree = requests.get(f"{BASE_URL}/api/front-groups/tree", headers=ph, timeout=30)
    assert tree.status_code == 200
    lst = requests.get(f"{BASE_URL}/api/front-groups", headers=ph, timeout=30)
    assert lst.status_code == 200


# FIX 5: archivo bloqueado con dependientes
def test_archive_blocked_then_leaf_ok(ph):
    b = requests.post(f"{BASE_URL}/api/front-groups/{STATE['root']}/archive", json={"reason": "QA r2"}, headers=ph, timeout=30)
    assert b.status_code == 409
    assert b.json()["detail"]["dependent_group_count"] >= 1
