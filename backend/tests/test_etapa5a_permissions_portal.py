# ETAPA 5A: portal por permisos asignados (capability catalog, manual mode, recorte, self-portal)
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
LEADER = ("coreqa.leader@example.com", "CoreQA2026!Leader")
MEMBER = ("coreqa.member@example.com", "CoreQA2026!Member")
CREATED_USERS = []


def login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token
    return {"Authorization": f"Bearer {token}"}


NEW_PW = "Test5aFinal!2026"


def activated_login(email):
    """Login with temp password, then change it (must_change_password gate)."""
    h = login(email, "Test5aTemp!2026")
    r = requests.post(f"{API}/auth/change-password", headers=h, json={"current_password": "Test5aTemp!2026", "new_password": NEW_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def pastor_h():
    return login(*PASTOR)


def make_person(h, tag):
    r = requests.post(f"{API}/core/persons", headers=h, json={"nombre": f"TEST5A {tag}", "apellido": "Etapa5a", "idempotency_key": f"test5a-{tag}-{uuid.uuid4().hex}"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    return d.get("person_id") or d.get("id") or d.get("person", {}).get("person_id")


def make_user(h, level, extra=None, tag=None):
    tag = tag or uuid.uuid4().hex[:6]
    pid = make_person(h, tag)
    email = f"test5a.{tag}@example.com"
    payload = {"person_id": pid, "email": email, "temporary_password": "Test5aTemp!2026", "access_level": level, **(extra or {})}
    r = requests.post(f"{API}/core/governance/users", headers=h, json=payload, timeout=30)
    if r.status_code == 201:
        CREATED_USERS.append(r.json()["user_id"])
    return r, email, pid


def get_user(h, user_id):
    r = requests.get(f"{API}/core/governance/users", headers=h, timeout=30)
    assert r.status_code == 200
    return next(u for u in r.json()["items"] if u["user_id"] == user_id)


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    h = login(*PASTOR)
    for uid in CREATED_USERS:
        u = get_user(h, uid)
        requests.put(f"{API}/core/governance/users/{uid}/access", headers=h, json={"access_level": u.get("access_level") or u["rol"], "is_active": False}, timeout=30)


# Self portal: /api/core/me/profile & /api/core/me/stats always available
@pytest.mark.parametrize("creds", [PASTOR, LEADER, MEMBER])
def test_me_profile_and_stats(creds):
    h = login(*creds)
    p = requests.get(f"{API}/core/me/profile", headers=h, timeout=30)
    assert p.status_code == 200, p.text
    body = p.json()
    for k in ("person", "contacts", "addresses", "ministries", "front_groups", "account"):
        assert k in body
    s = requests.get(f"{API}/core/me/stats", headers=h, timeout=60)
    assert s.status_code == 200, s.text
    assert "has_any_activity" in s.json()


def test_me_requires_auth():
    assert requests.get(f"{API}/core/me/profile", timeout=30).status_code in (401, 403)


# Capability catalog
def test_catalog_pastor(pastor_h):
    r = requests.get(f"{API}/core/governance/capability-catalog", headers=pastor_h, timeout=30)
    assert r.status_code == 200
    mods = r.json()["modules"]
    total = sum(len(m["items"]) for m in mods)
    print("modules", len(mods), "caps", total)
    assert len(mods) >= 10 and total >= 80
    keys = {i["capability"] for m in mods for i in m["items"]}
    assert "core.access.manage" not in keys and "core.governance.manage" not in keys


def test_catalog_member_forbidden():
    r = requests.get(f"{API}/core/governance/capability-catalog", headers=login(*MEMBER), timeout=30)
    assert r.status_code == 403


# Creation: manual mode with empty capabilities
def test_create_persona_minimal(pastor_h):
    r, email, _ = make_user(pastor_h, "persona")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["capabilities"] == []
    assert d.get("permissions_mode") == "manual"
    h = activated_login(email)
    assert requests.get(f"{API}/core/me/profile", headers=h, timeout=30).status_code == 200


def test_create_lider_minimal(pastor_h):
    r, _, _ = make_user(pastor_h, "lider")
    assert r.status_code == 201, r.text
    assert r.json()["capabilities"] == []


def test_create_persona_with_caps(pastor_h):
    r, _, _ = make_user(pastor_h, "persona", {"capabilities": ["front_groups.view"]})
    assert r.status_code == 201, r.text
    assert r.json()["capabilities"] == ["front_groups.view"]


def test_create_invalid_cap_rejected(pastor_h):
    r, _, _ = make_user(pastor_h, "persona", {"capabilities": ["core.access.manage"]})
    assert r.status_code == 400, r.text


def test_create_mentor_access_bundle(pastor_h):
    r, _, _ = make_user(pastor_h, "persona", {"mentor_access": True})
    assert r.status_code == 201, r.text
    caps = r.json()["capabilities"]
    assert "mentorship.outreach.report" in caps and "library.deliver" in caps


def test_coordinator_cannot_send_caps(pastor_h):
    r, email, _ = make_user(pastor_h, "coordinador_general")
    assert r.status_code == 201, r.text
    ch = activated_login(email)
    ob = requests.get(f"{API}/access/onboarding", headers=ch, timeout=30).json()
    sub = requests.post(f"{API}/access/onboarding", headers=ch, json={"preferred_contact_method": "correo", "emergency_contact_name": "Test Contacto", "emergency_contact_phone": "5551234567", "device_ownership": "personal", "service_commitment": "Compromiso de servicio para pruebas QA", "privacy_acknowledged": True, "confidentiality_acknowledged": True, "secure_device_acknowledged": True, "incident_reporting_acknowledged": True, "signature": "Test QA", "policy_version": ob["policy"]["version"]}, timeout=30)
    assert sub.status_code == 200, sub.text
    if sub.json().get("token"):
        ch = {"Authorization": f"Bearer {sub.json()['token']}"}
    pid = make_person(pastor_h, "coordchild" + uuid.uuid4().hex[:4])
    r2 = requests.post(f"{API}/core/governance/users", headers=ch, json={"person_id": pid, "email": f"test5a.cc{uuid.uuid4().hex[:5]}@example.com", "temporary_password": "Test5aTemp!2026", "access_level": "persona", "capabilities": ["front_groups.view"]}, timeout=30)
    print("coord w/ caps:", r2.status_code, r2.text[:200])
    assert r2.status_code == 403
    assert "Solo el pastor puede personalizar capacidades" in r2.text
    r3 = requests.post(f"{API}/core/governance/users", headers=ch, json={"person_id": pid, "email": f"test5a.cc{uuid.uuid4().hex[:5]}@example.com", "temporary_password": "Test5aTemp!2026", "access_level": "persona"}, timeout=30)
    print("coord w/o caps:", r3.status_code, r3.text[:200])
    assert r3.status_code == 201
    CREATED_USERS.append(r3.json()["user_id"])
    assert r3.json()["capabilities"] == []


# Update: recorte (trim) authoritative for lider/persona
def test_update_trim_capabilities(pastor_h):
    r, _, _ = make_user(pastor_h, "persona", {"capabilities": ["front_groups.view", "library.deliver"]})
    assert r.status_code == 201
    uid = r.json()["user_id"]
    u = requests.put(f"{API}/core/governance/users/{uid}/access", headers=pastor_h, json={"access_level": "persona", "is_active": True, "capabilities": ["library.deliver"]}, timeout=30)
    assert u.status_code == 200, u.text
    print("after trim:", u.json()["capabilities"])
    assert u.json()["capabilities"] == ["library.deliver"]
    assert get_user(pastor_h, uid)["capabilities"] == ["library.deliver"]


def test_update_trim_to_empty(pastor_h):
    r, _, _ = make_user(pastor_h, "lider", {"capabilities": ["front_groups.view"]})
    uid = r.json()["user_id"]
    u = requests.put(f"{API}/core/governance/users/{uid}/access", headers=pastor_h, json={"access_level": "lider", "is_active": True, "capabilities": []}, timeout=30)
    assert u.status_code == 200, u.text
    assert u.json()["capabilities"] == []


def test_update_structural_caps_rejected(pastor_h):
    r, _, _ = make_user(pastor_h, "persona")
    uid = r.json()["user_id"]
    for cap in ("core.access.manage", "core.governance.manage"):
        u = requests.put(f"{API}/core/governance/users/{uid}/access", headers=pastor_h, json={"access_level": "persona", "is_active": True, "capabilities": [cap]}, timeout=30)
        assert u.status_code == 400, u.text
        assert cap not in get_user(pastor_h, uid)["capabilities"]


def test_update_without_caps_keeps_manual_list(pastor_h):
    """Editing a manual account without sending capabilities must not re-grant role defaults."""
    r, _, _ = make_user(pastor_h, "persona", {"capabilities": ["front_groups.view"]})
    uid = r.json()["user_id"]
    u = requests.put(f"{API}/core/governance/users/{uid}/access", headers=pastor_h, json={"access_level": "persona", "is_active": True}, timeout=30)
    assert u.status_code == 200, u.text
    print("after no-caps edit:", u.json()["capabilities"])
    assert u.json()["capabilities"] == ["front_groups.view"]


# Existing accounts keep their caps
def test_existing_accounts_keep_caps(pastor_h):
    r = requests.get(f"{API}/core/governance/users", headers=pastor_h, timeout=30)
    items = {u["email"]: u for u in r.json()["items"]}
    assert len(items["coreqa.leader@example.com"]["capabilities"]) > 10
    assert len(items["coreqa.member@example.com"]["capabilities"]) > 5
