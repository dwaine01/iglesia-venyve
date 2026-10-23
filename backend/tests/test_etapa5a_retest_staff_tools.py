# ETAPA 5A retest: trim/preserve capabilities, staff_tools catalog + backfill, invite-codes/journal capability gating
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
LEADER = ("coreqa.leader@example.com", "CoreQA2026!Leader")
STAFF = {"invitations.codes.manage", "evangelism.log.write", "presentation.manual.view"}
TEMP_PW = "Test5aTemp!2026"
NEW_PW = "Test5aFinal!2026"
CREATED = []


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"Authorization": f"Bearer {d.get('access_token') or d.get('token')}"}


def activated(email):
    h = login(email, TEMP_PW)
    r = requests.post(f"{API}/auth/change-password", headers=h, json={"current_password": TEMP_PW, "new_password": NEW_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def ph():
    return login(*PASTOR)


def users(h):
    r = requests.get(f"{API}/core/governance/users", headers=h, timeout=30)
    assert r.status_code == 200
    return r.json()["items"]


def get_user(h, uid):
    return next(u for u in users(h) if u["user_id"] == uid)


def make_user(h, level, extra=None):
    tag = uuid.uuid4().hex[:6]
    r = requests.post(f"{API}/core/persons", headers=h, json={"nombre": f"TEST5AR {tag}", "apellido": "Retest", "idempotency_key": f"t5ar-{tag}"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    pid = d.get("person_id") or d.get("id") or d.get("person", {}).get("person_id")
    email = f"test5ar.{tag}@example.com"
    r = requests.post(f"{API}/core/governance/users", headers=h, json={"person_id": pid, "email": email, "temporary_password": TEMP_PW, "access_level": level, **(extra or {})}, timeout=30)
    assert r.status_code == 201, r.text
    CREATED.append(r.json()["user_id"])
    return r.json(), email


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    h = login(*PASTOR)
    for uid in CREATED:
        u = get_user(h, uid)
        requests.put(f"{API}/core/governance/users/{uid}/access", headers=h, json={"access_level": u.get("access_level") or u["rol"], "is_active": False}, timeout=30)


# Catalog: staff_tools module present, totals recomputed
def test_catalog_staff_tools(ph):
    r = requests.get(f"{API}/core/governance/capability-catalog", headers=ph, timeout=30)
    assert r.status_code == 200
    body = r.json()
    mods = body.get("modules") or body.get("items") or body
    caps = [c["capability"] for m in mods for c in m["items"]]
    keys = [m["module_key"] for m in mods]
    print(f"modules={len(mods)} caps={len(caps)} unique={len(set(caps))} keys={keys}")
    staff = next(m for m in mods if (m["module_key"]) == "staff_tools")
    assert {c["capability"] for c in staff["items"]} == STAFF


# Trim + preserve on manual lider/persona
@pytest.mark.parametrize("level", ["lider", "persona"])
def test_trim_then_preserve(ph, level):
    u, _ = make_user(ph, level)
    uid = u["user_id"]
    r = requests.put(f"{API}/core/governance/users/{uid}/access", headers=ph, json={"access_level": level, "is_active": True, "capabilities": ["front_groups.view", "library.deliver"]}, timeout=30)
    assert r.status_code == 200, r.text
    assert sorted(get_user(ph, uid)["capabilities"]) == ["front_groups.view", "library.deliver"]
    r = requests.put(f"{API}/core/governance/users/{uid}/access", headers=ph, json={"access_level": level, "is_active": True, "capabilities": ["library.deliver"]}, timeout=30)
    assert r.status_code == 200, r.text
    assert get_user(ph, uid)["capabilities"] == ["library.deliver"]
    r = requests.put(f"{API}/core/governance/users/{uid}/access", headers=ph, json={"access_level": level, "is_active": True}, timeout=30)
    assert r.status_code == 200, r.text
    assert get_user(ph, uid)["capabilities"] == ["library.deliver"]


# Legacy leader backfilled with staff tools
def test_legacy_leader_has_staff_tools(ph):
    u = next(x for x in users(ph) if x.get("email") == LEADER[0])
    caps = set(u["capabilities"])
    print("leader caps count", len(caps), "mode", u.get("permissions_mode"))
    assert STAFF <= caps
    for c in ["processes.read", "cellular.read", "doors.read", "library.deliver", "front_groups.view"]:
        assert c in caps, c


# Invite codes / journal gating
def test_minimal_lider_blocked(ph):
    _, email = make_user(ph, "lider")
    h = activated(email)
    assert requests.post(f"{API}/invite-codes", headers=h, json={}, timeout=30).status_code == 403
    assert requests.get(f"{API}/invite-codes", headers=h, timeout=30).status_code == 403
    assert requests.post(f"{API}/journal", headers=h, json={"fecha": "2026-01-10", "casas_visitadas": 1}, timeout=30).status_code == 403
    assert requests.get(f"{API}/journal", headers=h, timeout=30).status_code == 403
    assert requests.get(f"{API}/journal/stats", headers=h, timeout=30).status_code == 403


def test_minimal_persona_blocked(ph):
    _, email = make_user(ph, "persona")
    h = activated(email)
    assert requests.get(f"{API}/invite-codes", headers=h, timeout=30).status_code == 403
    assert requests.get(f"{API}/journal", headers=h, timeout=30).status_code == 403
    assert requests.get(f"{API}/journal/stats", headers=h, timeout=30).status_code == 403


def test_legacy_leader_allowed():
    h = login(*LEADER)
    r = requests.post(f"{API}/invite-codes", headers=h, json={"destinatario_nombre": "TEST5AR"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    code_id = r.json()["_id"]
    assert requests.get(f"{API}/invite-codes", headers=h, timeout=30).status_code == 200
    requests.delete(f"{API}/invite-codes/{code_id}", headers=h, timeout=30)
    r = requests.post(f"{API}/journal", headers=h, json={"fecha": "2026-01-10", "casas_visitadas": 1, "notas": "TEST5AR"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    eid = r.json().get("id") or r.json().get("_id")
    assert requests.get(f"{API}/journal", headers=h, timeout=30).status_code == 200
    assert requests.get(f"{API}/journal/stats", headers=h, timeout=30).status_code == 200
    requests.delete(f"{API}/journal/{eid}", headers=h, timeout=30)


# Persona granted evangelism.log.write: should not see other leaders' journal entries
def test_persona_with_log_cap_scope(ph):
    lh = login(*LEADER)
    r = requests.post(f"{API}/journal", headers=lh, json={"fecha": "2026-01-10", "casas_visitadas": 1, "notas": "TEST5AR scope"}, timeout=30)
    eid = r.json().get("id") or r.json().get("_id")
    try:
        u, email = make_user(ph, "persona", {"capabilities": ["evangelism.log.write"]})
        h = activated(email)
        r = requests.get(f"{API}/journal", headers=h, timeout=30)
        print("persona journal status", r.status_code, "count", len(r.json()) if r.status_code == 200 else r.text)
        if r.status_code == 200:
            ids = [e.get("id") or e.get("_id") for e in r.json()]
            assert eid not in ids, "persona with evangelism.log.write sees other leaders' journal entries (unscoped query)"
    finally:
        requests.delete(f"{API}/journal/{eid}", headers=lh, timeout=30)
