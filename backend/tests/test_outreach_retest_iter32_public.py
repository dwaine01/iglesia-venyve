# Iteration 32 re-test (public URL): outreach fixes 4-7 (phone last-10 dedup, existing-person dedup, exact-name 7 Semanas, status lock after enrollment)
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PASSWORD = "QaOutreach32!"
MENTOR_A = "qa.outreach32.mentora@example.com"
LEADER = "qa.outreach32.leader@example.com"
API = f"{BASE_URL}/api/mentorship/outreach"


def login(email):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code} {r.text}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def mentor_a():
    return login(MENTOR_A)


@pytest.fixture(scope="module")
def leader():
    return login(LEADER)


def rand10():
    return "3" + str(uuid.uuid4().int)[:9]


# FIX 4: dedup by last 10 digits
def test_phone_dedup_last_10_digits(mentor_a):
    p = rand10()
    r1 = requests.post(f"{API}/visits", json={"contact_type": "new", "contact_name": "QA Phone One", "contact_phone": p}, headers=mentor_a)
    assert r1.status_code == 201, r1.text
    formatted = f"+58 {p[:3]}-{p[3:6]}-{p[6:]}"
    r2 = requests.post(f"{API}/visits", json={"contact_type": "new", "contact_name": "QA Phone Two", "contact_phone": formatted}, headers=mentor_a)
    assert r2.status_code == 409, r2.text
    assert "teléfono" in r2.json()["detail"]
    # reverse direction: prefixed first, then bare
    q = rand10()
    r3 = requests.post(f"{API}/visits", json={"contact_type": "new", "contact_name": "QA Phone Three", "contact_phone": f"0058{q}"}, headers=mentor_a)
    assert r3.status_code == 201, r3.text
    r4 = requests.post(f"{API}/visits", json={"contact_type": "new", "contact_name": "QA Phone Four", "contact_phone": q}, headers=mentor_a)
    assert r4.status_code == 409, r4.text


# FIX 5: duplicate existing person
def test_existing_person_duplicate_rejected(mentor_a, leader):
    s = requests.get(f"{API}/person-search", params={"q": "Outreach32 mentorb"}, headers=mentor_a)
    assert s.status_code == 200
    # use the long-name QA person via search
    s = requests.get(f"{API}/person-search", params={"q": "Quorvat"}, headers=mentor_a)
    items = s.json()["items"]
    assert items, "seed person not found"
    pid = items[0]["person_id"]
    r1 = requests.post(f"{API}/visits", json={"contact_type": "existing", "person_id": pid}, headers=mentor_a)
    assert r1.status_code == 201, r1.text
    r2 = requests.post(f"{API}/visits", json={"contact_type": "existing", "person_id": pid}, headers=mentor_a)
    assert r2.status_code == 409, r2.text
    assert "visita activa" in r2.json()["detail"]
    # leader assigning to another mentor also blocked
    r3 = requests.post(f"{API}/visits", json={"contact_type": "existing", "person_id": pid}, headers=leader)
    assert r3.status_code == 409, r3.text


# FIX 6 + FIX 7: exact-name match on 7 Semanas, then status locked
def test_seven_weeks_exact_name_and_status_lock(mentor_a):
    r = requests.post(f"{API}/visits", json={"contact_type": "new", "contact_name": "Zelindaqa Quorvat"}, headers=mentor_a)
    assert r.status_code == 201, r.text
    vid = r.json()["visit_id"]
    rep = requests.put(f"{API}/visits/{vid}/report", json={"status": "wants_followup"}, headers=mentor_a)
    assert rep.status_code == 200 and rep.json()["status"] == "wants_followup"
    sw = requests.post(f"{API}/visits/{vid}/start-seven-weeks", headers=mentor_a)
    assert sw.status_code == 200, sw.text
    data = sw.json()
    assert data["person_created"] is True, data
    assert data["enrollment_id"]
    # FIX 7: status change blocked
    bad = requests.put(f"{API}/visits/{vid}/report", json={"status": "rejected"}, headers=mentor_a)
    assert bad.status_code == 409, bad.text
    # other fields still editable (same status)
    ok = requests.put(f"{API}/visits/{vid}/report", json={"status": "wants_followup", "note": "QA nota post", "received_mcd": True}, headers=mentor_a)
    assert ok.status_code == 200, ok.text
    g = requests.get(f"{API}/visits/{vid}", headers=mentor_a).json()
    assert g["status"] == "wants_followup" and g["note"] == "QA nota post" and g["received_mcd"] is True
    # second start blocked
    again = requests.post(f"{API}/visits/{vid}/start-seven-weeks", headers=mentor_a)
    assert again.status_code == 409


# FIX 6 positive: exact name still reuses existing person
def test_seven_weeks_exact_name_reuses(mentor_a):
    r = requests.post(f"{API}/visits", json={"contact_type": "new", "contact_name": "Zelindaqa Quorvat Gomez"}, headers=mentor_a)
    assert r.status_code == 201, r.text
    vid = r.json()["visit_id"]
    requests.put(f"{API}/visits/{vid}/report", json={"status": "wants_followup"}, headers=mentor_a)
    sw = requests.post(f"{API}/visits/{vid}/start-seven-weeks", headers=mentor_a)
    assert sw.status_code == 200, sw.text
    assert sw.json()["person_created"] is False


# FIX 8 backend: dashboard has total & wants_followup per mentor
def test_dashboard_by_mentor_fields(leader):
    d = requests.get(f"{API}/dashboard", headers=leader)
    assert d.status_code == 200
    rows = d.json()["by_mentor"]
    assert rows
    for k in ("total", "assigned", "visited", "wants_followup", "seven_weeks_started"):
        assert k in rows[0]
