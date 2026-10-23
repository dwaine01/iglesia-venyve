"""Etapa 2 — verificación de fixes de iteration_45 (vía URL pública).

Requiere tests/seed_etapa2_ui.py -> /tmp/etapa2_seed.json. Deja datos QA para la UI
(campaña + hogares); los limpia qa_demo_cleanup. Escribe /tmp/etapa2_round2_state.json.
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
STATE_PATH = "/tmp/etapa2_round2_state.json"

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
        **{k: login(SEED[k]["email"], SEED["password"]) for k in ("leader", "mentor_root", "mentor_sub")},
    }


@pytest.fixture(scope="module")
def state():
    data = {}
    yield data
    with open(STATE_PATH, "w") as fh:
        json.dump(data, fh, indent=2)


# Setup: campaña con mentor_root + mentor_sub
def test_setup_campaign(h, state):
    payload = {
        "name": f"QA Invasión Round2 {uuid.uuid4().hex[:4]}", "location": "Sector QA", "start_date": "2026-09-01", "end_date": "2026-09-30",
        "assigned_mentors": [{"person_id": SEED["mentor_root"]["person_id"]}, {"person_id": SEED["mentor_sub"]["person_id"]}],
    }
    r = requests.post(f"{API}/campaigns", json=payload, headers=h["pastor"], timeout=30)
    assert r.status_code == 201, r.text
    state["campaign_id"] = r.json()["campaign_id"]
    state["campaign_name"] = payload["name"]
    for k in ("mentor_root", "mentor_sub"):
        p = requests.post(f"{API}/campaigns/{state['campaign_id']}/participate", headers=h[k], timeout=30)
        assert p.status_code == 200 and p.json()["status"] == "confirmed"


# FIX 3: hogar sin contactos -> has_activity consistente con participation 'active'
def test_fix3_household_without_contacts_is_consistent(h, state):
    cid = state["campaign_id"]
    r = requests.post(f"{API}/households", json={"sector": "Sector Sub R2", "address_line1": "Calle QA 1", "campaign_id": cid}, headers=h["mentor_sub"], timeout=30)
    assert r.status_code == 201, r.text
    state["household_sub"] = r.json()["household_id"]
    report = requests.get(f"{API}/campaigns/{cid}/report", headers=h["pastor"], timeout=30).json()
    by = {m["mentor_person_id"]: m for m in report["mentors"]}
    sub = by[SEED["mentor_sub"]["person_id"]]
    assert sub["participation_status"] == "active"
    assert sub["contacts_total"] == 0
    assert sub["has_activity"] is True
    root = by[SEED["mentor_root"]["person_id"]]
    assert root["participation_status"] == "confirmed" and root["has_activity"] is False
    for m in report["mentors"]:
        assert m["has_activity"] == (m["contacts_total"] > 0 or m["participation_status"] == "active")


# FIX 2: /households devuelve campaign_name
def test_fix2_households_include_campaign_name(h, state):
    items = requests.get(f"{API}/households", headers=h["mentor_sub"], timeout=30).json()["items"]
    hh = next(i for i in items if i["household_id"] == state["household_sub"])
    assert hh["campaign_name"] == state["campaign_name"]
    assert hh["attempts"] == 0 and hh["last_occurred_at"] is None


# FIX 1: my-branch-overview incluye attempts/last_occurred_at/campaign_name
def test_fix1_branch_overview_has_attempts(h, state):
    hid = state["household_sub"]
    for result in ("no_answer", "not_home"):
        r = requests.post(f"{API}/households/{hid}/events", json={"result": result}, headers=h["mentor_sub"], timeout=30)
        assert r.status_code == 201, r.text
    ok = requests.post(f"{API}/households/{hid}/events", json={"result": "contacted", "persons": [{"contact_type": "new", "contact_name": "QA Persona R2", "contact_phone": f"809555{uuid.uuid4().int % 10000:04d}"}]}, headers=h["mentor_sub"], timeout=30)
    assert ok.status_code == 201, ok.text
    state["visit_sub"] = ok.json()["visits"][0]["visit_id"]
    ov = requests.get(f"{API}/my-branch-overview", headers=h["leader"], timeout=30).json()
    assert ov["is_supervisor"] is True
    hh = next(x for x in ov["households"] if x["household_id"] == hid)
    assert hh["attempts"] == 3
    assert hh["last_occurred_at"]
    assert hh["campaign_name"] == state["campaign_name"]
    listed = next(i for i in requests.get(f"{API}/households", headers=h["mentor_sub"], timeout=30).json()["items"] if i["household_id"] == hid)
    assert listed["attempts"] == hh["attempts"] and listed["last_occurred_at"] == hh["last_occurred_at"]
    v = next(x for x in ov["visits"] if x["visit_id"] == state["visit_sub"])
    assert v["read_only"] is True


# FIX 3 (bis): tras contactos, report sigue consistente
def test_fix3_report_after_contact(h, state):
    report = requests.get(f"{API}/campaigns/{state['campaign_id']}/report", headers=h["pastor"], timeout=30).json()
    sub = next(m for m in report["mentors"] if m["mentor_person_id"] == SEED["mentor_sub"]["person_id"])
    assert sub["contacts_total"] == 1 and sub["has_activity"] is True and sub["participation_status"] == "active"


# Detalle de hogar visto por el líder: visitas read_only (para VisitCard)
def test_household_detail_for_leader_read_only(h, state):
    r = requests.get(f"{API}/households/{state['household_sub']}", headers=h["leader"], timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert len(body["events"]) == 3
    assert all(v.get("read_only") is True for v in body["visits"])


# Hogar sin intentos para mentor_root (prueba UI FIX 4)
def test_setup_root_household_no_campaign(h, state):
    r = requests.post(f"{API}/households", json={"sector": "Sector Raiz R2", "address_line1": "Calle Raiz 9"}, headers=h["mentor_root"], timeout=30)
    assert r.status_code == 201, r.text
    state["household_root"] = r.json()["household_id"]
    items = requests.get(f"{API}/households", headers=h["mentor_root"], timeout=30).json()["items"]
    hh = next(i for i in items if i["household_id"] == state["household_root"])
    assert hh["campaign_name"] is None and hh["attempts"] == 0
    # mentor_root sigue 'confirmed' (crear hogar sin campaña no lo activa)
    camp = next(i for i in requests.get(f"{API}/campaigns", headers=h["mentor_root"], timeout=30).json()["items"] if i["campaign_id"] == state["campaign_id"])
    assert camp["my_participation_status"] == "confirmed"
