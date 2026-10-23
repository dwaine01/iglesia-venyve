# PASO0: church timezone setting (GET public-auth, PUT pastoral only, invalid -> 422)
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
URL = f"{BASE_URL}/api/processes/consolidation/settings/timezone"


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def pastor():
    return login("coreqa.pastor@example.com", "CoreQA2026!Pastor")


@pytest.fixture(scope="module")
def member():
    return login("coreqa.member@example.com", "CoreQA2026!Member")


def test_timezone_flow(pastor, member):
    original = requests.get(URL, headers=pastor, timeout=30)
    assert original.status_code == 200
    orig_tz = original.json()["church_timezone"]
    try:
        # member can read
        r = requests.get(URL, headers=member, timeout=30)
        assert r.status_code == 200 and "church_timezone" in r.json()
        # member cannot write
        r = requests.put(URL, headers=member, json={"church_timezone": "America/Santo_Domingo"}, timeout=30)
        assert r.status_code == 403, r.text
        # invalid tz
        r = requests.put(URL, headers=pastor, json={"church_timezone": "Mars/Olympus"}, timeout=30)
        assert r.status_code == 422, r.text
        # valid tz persists
        r = requests.put(URL, headers=pastor, json={"church_timezone": "America/Santo_Domingo"}, timeout=30)
        assert r.status_code == 200 and r.json()["church_timezone"] == "America/Santo_Domingo"
        r = requests.get(URL, headers=member, timeout=30)
        assert r.json()["church_timezone"] == "America/Santo_Domingo"
        # unauthenticated
        r = requests.get(URL, timeout=30)
        assert r.status_code in (401, 403)
    finally:
        requests.put(URL, headers=pastor, json={"church_timezone": orig_tz}, timeout=30)
