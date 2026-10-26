"""Verify person_name & campaign_name enrichment on finance contributions endpoints."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
PASTOR = {"email": "qa.baptismui53.pastor@example.com", "password": "QaBaptismUI53!"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=PASTOR, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_contributions_list_has_person_name(headers):
    r = requests.get(f"{BASE_URL}/api/finance/contributions", headers=headers, timeout=30)
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert isinstance(items, list)
    # must have person_name key on every item
    for it in items:
        assert "person_name" in it, f"missing person_name on {it.get('contribution_id')}"
        assert "campaign_name" in it, f"missing campaign_name on {it.get('contribution_id')}"

    # at least one non-anonymous w/ real person_id should resolve to a real name
    named = [it for it in items if it.get("person_id") and not it.get("anonymous") and it.get("person_name")]
    assert len(named) > 0, "expected at least one contribution with resolved person_name"
    # person_name should not be a raw ObjectId / snake-case
    for it in named[:5]:
        assert len(it["person_name"]) > 1
        assert it["person_name"] != it["person_id"]
    print(f"Found {len(items)} items, {len(named)} with resolved person_name")
    print("Sample names:", [n["person_name"] for n in named[:5]])


def test_person_contributions_endpoint_has_enrichment(headers):
    # First find a person_id from the contributions list
    r = requests.get(f"{BASE_URL}/api/finance/contributions", headers=headers, timeout=30)
    items = r.json().get("items", [])
    person_id = next((it["person_id"] for it in items if it.get("person_id") and not it.get("anonymous")), None)
    if not person_id:
        pytest.skip("No non-anonymous contributions to test person-scoped endpoint")

    r2 = requests.get(f"{BASE_URL}/api/finance/persons/{person_id}/contributions", headers=headers, timeout=30)
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert "items" in data
    for it in data["items"]:
        assert "person_name" in it
        assert "campaign_name" in it
    print(f"Person-scoped endpoint returned {len(data['items'])} items with enrichment OK")


def test_anonymous_contributions_have_null_person_name(headers):
    r = requests.get(f"{BASE_URL}/api/finance/contributions", headers=headers, timeout=30)
    items = r.json().get("items", [])
    anon = [it for it in items if it.get("anonymous")]
    for it in anon:
        # should not leak a real name; either null or n/a
        assert not it.get("person_id") or it.get("person_name") is None or it.get("person_name") == ""
    print(f"Checked {len(anon)} anonymous contributions - no leaked names")
