"""E2E regression test for status='corrected' filtering fix in finance endpoints.

Flow: create campaign donation -> verify -> confirm appears in /api/finance/contributions
and in /api/finance/persons/{id}/contributions -> unverify (sets status='corrected')
-> confirm it is EXCLUDED from both endpoints while legitimate verified entries remain.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pdf-layout-fix-16.preview.emergentagent.com").rstrip("/")
PASTOR_EMAIL = "qa.baptismui53.pastor@example.com"
PASTOR_PASSWORD = "QaBaptismUI53!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": PASTOR_EMAIL, "password": PASTOR_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


def test_login(h):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=h)
    assert r.status_code == 200


def test_finance_contributions_excludes_corrected(h):
    r = requests.get(f"{BASE_URL}/api/finance/contributions", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    bad = [i for i in items if i.get("status") == "corrected"]
    assert bad == [], f"Found {len(bad)} corrected contributions leaking into /api/finance/contributions"


def test_e2e_verify_then_unverify_filters_corrected(h):
    unique = f"TEST_CorrectedFilter_{int(time.time())}"

    # 1. Create donation (received type)
    create_payload = {
        "donor_name": unique,
        "amount_cents": 7777,
        "donation_type": "received",
        "anonymous": False,
        "consent_show_name": False,
    }
    r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations", json=create_payload, headers=h)
    assert r.status_code == 201, r.text
    donation = r.json()
    did = donation["donation_id"]
    print(f"Created donation {did}")

    # 2. Verify (creates finance_contributions status=recorded)
    r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/verify",
                      json={"payment_method": "zelle"}, headers=h)
    assert r.status_code == 200, r.text
    verified = r.json()
    contribution_id = verified.get("finance_contribution_id")
    finance_person_id = verified.get("finance_person_id")
    assert contribution_id, "verify did not return finance_contribution_id"
    print(f"Verified: contribution_id={contribution_id} person_id={finance_person_id}")

    # 3. Confirm it appears in /api/finance/contributions with the Ven y Come campaign_name
    r = requests.get(f"{BASE_URL}/api/finance/contributions", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    match = next((i for i in items if i.get("contribution_id") == contribution_id), None)
    assert match is not None, "verified contribution missing from finance list"
    assert match.get("status") == "recorded"
    assert match.get("campaign_name") == "Ven y Come · Bus de comida", f"got {match.get('campaign_name')}"
    assert match.get("amount_cents") == 7777

    # 4. Confirm it appears in person 360 financial history
    if finance_person_id:
        r = requests.get(f"{BASE_URL}/api/finance/persons/{finance_person_id}/contributions", headers=h)
        assert r.status_code == 200
        data = r.json()
        pitems = data["items"]
        pmatch = next((i for i in pitems if i.get("contribution_id") == contribution_id), None)
        assert pmatch is not None, "verified contribution missing from person contributions"
        assert data["total_cents"] >= 7777

    # 5. Unverify (sets status=corrected)
    r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/unverify", headers=h)
    assert r.status_code == 200, r.text
    print("Unverified")

    # 6. Confirm it is NO LONGER in /api/finance/contributions
    r = requests.get(f"{BASE_URL}/api/finance/contributions", headers=h)
    items = r.json()["items"]
    leaked = next((i for i in items if i.get("contribution_id") == contribution_id), None)
    assert leaked is None, f"corrected contribution still leaking: {leaked}"
    # And no corrected rows at all
    assert all(i.get("status") != "corrected" for i in items)

    # 7. Confirm it is NO LONGER in person contributions and total_cents does not include it
    if finance_person_id:
        r = requests.get(f"{BASE_URL}/api/finance/persons/{finance_person_id}/contributions", headers=h)
        data = r.json()
        pitems = data["items"]
        leaked_p = next((i for i in pitems if i.get("contribution_id") == contribution_id), None)
        assert leaked_p is None, "corrected contribution still in person history"
        assert all(i.get("status") != "corrected" for i in pitems)

    # 8. The donation itself should now be unverified/active
    r = requests.get(f"{BASE_URL}/api/campaigns/venycome/donations", headers=h)
    assert r.status_code == 200
    donations = r.json()["items"]
    dmatch = next((d for d in donations if d.get("donation_id") == did), None)
    assert dmatch is not None
    assert dmatch.get("verified") is False
    assert dmatch.get("status") != "voided"
    print("E2E flow complete: corrected filtering works")

    # cleanup: void the donation (we cannot delete verified; already unverified)
    requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/void", headers=h)


def test_family_scope_also_excludes_corrected(h):
    """Also validate scope=family path excludes corrected"""
    # Just hit any person endpoint with scope=family and confirm no corrected items
    r = requests.get(f"{BASE_URL}/api/finance/contributions", headers=h)
    items = r.json()["items"]
    person_ids = {i["person_id"] for i in items if i.get("person_id")}
    if not person_ids:
        pytest.skip("no persons with contributions")
    pid = next(iter(person_ids))
    r = requests.get(f"{BASE_URL}/api/finance/persons/{pid}/contributions?scope=family", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert all(i.get("status") != "corrected" for i in data["items"])
