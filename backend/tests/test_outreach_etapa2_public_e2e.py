"""Etapa 2 Invasiones — E2E vía URL pública (requiere seed_etapa2_ui.py -> /tmp/etapa2_seed.json).

Cubre: campos nuevos de campaña + roster por grupo, participación, hogares/intentos
(no inventar datos), supervisión de rama de solo lectura (rama y sub-rama), aislamiento
de mentor fuera de la rama, /api/front-groups plano para el selector.
"""
import json
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api/mentorship/outreach"
SEED_PATH = "/tmp/etapa2_seed.json"

if not os.path.exists(SEED_PATH):
    pytest.skip("Seed no encontrado; correr tests/seed_etapa2_ui.py", allow_module_level=True)
SEED = json.load(open(SEED_PATH))


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def h():
    return {
        "pastor": login("coreqa.pastor@example.com", "CoreQA2026!Pastor"),
        **{k: login(SEED[k]["email"], SEED["password"]) for k in ("leader", "sub_leader", "mentor_root", "mentor_sub", "mentor_out")},
    }


@pytest.fixture(scope="module")
def state():
    return {}


# Selector de grupos del CreateCampaignDialog
def test_front_groups_flat_has_id_and_name(h):
    r = requests.get(f"{BASE_URL}/api/front-groups", headers=h["pastor"], timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    root = next(i for i in items if i["front_group_id"] == SEED["root_group"])
    assert root.get("display_name") or root.get("name")


# Roster por grupo incluye sub-ramas
def test_mentors_by_group_includes_descendants(h):
    r = requests.get(f"{API}/mentors-by-group/{SEED['root_group']}", headers=h["pastor"], timeout=30)
    assert r.status_code == 200
    ids = {i["person_id"] for i in r.json()["items"]}
    assert SEED["mentor_root"]["person_id"] in ids and SEED["mentor_sub"]["person_id"] in ids
    assert SEED["mentor_out"]["person_id"] not in ids


def test_mentor_cannot_create_campaign(h):
    r = requests.post(f"{API}/campaigns", json={"name": "X", "location": "Y", "start_date": "2026-09-01", "end_date": "2026-09-02"}, headers=h["mentor_root"], timeout=30)
    assert r.status_code == 403


def test_pastor_creates_campaign_with_new_fields(h, state):
    payload = {
        "name": f"QA Invasión E2E {uuid.uuid4().hex[:4]}", "location": "Sector QA", "start_date": "2026-09-01", "end_date": "2026-09-02",
        "meeting_time": "07:30", "meeting_place": "Iglesia", "sectors": ["A", " B "], "instructions": "Llevar agua",
        "assigned_mentors": [{"person_id": SEED["mentor_root"]["person_id"]}, {"person_id": SEED["mentor_sub"]["person_id"]}],
    }
    r = requests.post(f"{API}/campaigns", json=payload, headers=h["pastor"], timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sectors"] == ["A", "B"] and body["meeting_time"] == "07:30" and body["instructions"] == "Llevar agua"
    state["campaign_id"] = body["campaign_id"]


def test_participation_flow(h, state):
    cid = state["campaign_id"]
    items = requests.get(f"{API}/campaigns", headers=h["mentor_root"], timeout=30).json()["items"]
    assert next(i for i in items if i["campaign_id"] == cid)["my_participation_status"] == "assigned"
    r = requests.post(f"{API}/campaigns/{cid}/participate", headers=h["mentor_root"], timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    out = requests.post(f"{API}/campaigns/{cid}/participate", headers=h["mentor_out"], timeout=30)
    assert out.status_code == 403


def test_household_rules_and_activity(h, state):
    cid = state["campaign_id"]
    r = requests.post(f"{API}/households", json={"sector": "Sector Sub", "campaign_id": cid}, headers=h["mentor_sub"], timeout=30)
    assert r.status_code == 201, r.text
    hid = r.json()["household_id"]
    state["household_sub"] = hid
    assert r.json()["front_group_id"] == SEED["sub_group"]
    for result in ("no_answer", "not_home", "refused"):
        bad = requests.post(f"{API}/households/{hid}/events", json={"result": result, "persons": [{"contact_type": "new", "contact_name": "Inventado"}]}, headers=h["mentor_sub"], timeout=30)
        assert bad.status_code == 422, f"{result} con personas debe ser 422"
    assert requests.post(f"{API}/households/{hid}/events", json={"result": "contacted"}, headers=h["mentor_sub"], timeout=30).status_code == 422
    assert requests.post(f"{API}/households/{hid}/events", json={"result": "bogus"}, headers=h["mentor_sub"], timeout=30).status_code == 422
    ok = requests.post(f"{API}/households/{hid}/events", json={"result": "contacted", "persons": [{"contact_type": "new", "contact_name": "QA Persona Sub", "contact_phone": f"809777{uuid.uuid4().int % 10000:04d}"}]}, headers=h["mentor_sub"], timeout=30)
    assert ok.status_code == 201, ok.text
    state["visit_sub"] = ok.json()["visits"][0]["visit_id"]
    assert ok.json()["visits"][0]["household_id"] == hid
    report = requests.get(f"{API}/campaigns/{cid}/report", headers=h["pastor"], timeout=30).json()
    status = {m["mentor_person_id"]: m["participation_status"] for m in report["mentors"]}
    assert status[SEED["mentor_sub"]["person_id"]] == "active"  # sin confirmar antes
    assert status[SEED["mentor_root"]["person_id"]] == "confirmed"


# Supervisión: líder raíz ve sub-rama; líder sub-rama ve la suya; nadie edita
def test_root_leader_sees_subbranch_read_only(h, state):
    ov = requests.get(f"{API}/my-branch-overview", headers=h["leader"], timeout=30).json()
    assert ov["is_supervisor"] is True
    assert any(x["household_id"] == state["household_sub"] for x in ov["households"])
    v = next(x for x in ov["visits"] if x["visit_id"] == state["visit_sub"])
    assert v["read_only"] is True
    hid, vid = state["household_sub"], state["visit_sub"]
    assert requests.put(f"{API}/visits/{vid}/report", json={"status": "visited"}, headers=h["leader"], timeout=30).status_code == 403
    assert requests.post(f"{API}/households/{hid}/events", json={"result": "no_answer"}, headers=h["leader"], timeout=30).status_code == 403
    assert requests.put(f"{API}/households/{hid}", json={"note": "x"}, headers=h["leader"], timeout=30).status_code == 403
    assert requests.post(f"{API}/visits/{vid}/start-seven-weeks", headers=h["leader"], timeout=30).status_code == 403
    assert requests.get(f"{API}/visits/{vid}", headers=h["leader"], timeout=30).status_code == 200


def test_sub_leader_sees_own_branch(h, state):
    ov = requests.get(f"{API}/my-branch-overview", headers=h["sub_leader"], timeout=30).json()
    assert ov["is_supervisor"] is True
    assert any(x["household_id"] == state["household_sub"] for x in ov["households"])


def test_outside_mentor_isolated(h, state):
    assert requests.get(f"{API}/households/{state['household_sub']}", headers=h["mentor_out"], timeout=30).status_code == 403
    assert requests.get(f"{API}/visits/{state['visit_sub']}", headers=h["mentor_out"], timeout=30).status_code == 403
    lst = requests.get(f"{API}/households", headers=h["mentor_out"], timeout=30).json()["items"]
    assert all(x["household_id"] != state["household_sub"] for x in lst)
    lst2 = requests.get(f"{API}/visits?mentor_person_id={SEED['mentor_sub']['person_id']}", headers=h["mentor_out"], timeout=30).json()["items"]
    assert all(x["visit_id"] != state["visit_sub"] for x in lst2)


def test_peer_mentor_in_same_root_branch_cannot_see_sub_mentor(h, state):
    # mentor_root es miembro (no líder) de la rama raíz: no debe supervisar a mentor_sub
    r = requests.get(f"{API}/households/{state['household_sub']}", headers=h["mentor_root"], timeout=30)
    assert r.status_code == 403, f"un mentor par no debe ver hogares de otro mentor: {r.status_code}"
