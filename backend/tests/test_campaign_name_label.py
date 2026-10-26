"""Backend tests for Ven y Come campaign_name label on finance contributions.

Verifies:
 - verified donation produces finance_contribution with campaign_id, campaign_name, allocations[0].campaign_id, description
 - finance_campaigns 'Ven y Come · Bus de comida' is idempotent (not duplicated)
 - GET /finance/contributions and GET /finance/persons/{id}/contributions include campaign_name
 - Regression: non-campaign contribution returns campaign_name null
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if os.path.exists("/app/frontend/.env"):
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

PASTOR_EMAIL = "qa.baptismui53.pastor@example.com"
PASTOR_PASSWORD = "QaBaptismUI53!"
CAMPAIGN_NAME = "Ven y Come · Bus de comida"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": PASTOR_EMAIL, "password": PASTOR_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def test_person(auth_headers):
    payload = {
        "nombre": f"TESTCampaignLabel{int(time.time())}",
        "apellido": "QAUser",
        "fecha_nacimiento": "1990-01-01",
        "idempotency_key": f"test-camplabel-{time.time_ns()}",
    }
    r = requests.post(f"{BASE_URL}/api/core/persons", json=payload, headers=auth_headers)
    assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
    data = r.json()
    person_id = data.get("person_id") or data.get("id") or data.get("_id")
    return {"person_id": person_id, "full_name": f"{payload['nombre']} QAUser"}


def _create_and_verify_donation(auth_headers, person_id, donor_name, amount=1500, method="cash"):
    body = {
        "donor_name": donor_name,
        "amount_cents": amount,
        "donation_type": "received",
        "anonymous": False,
        "consent_show_name": True,
        "person_id": person_id,
        "idempotency_key": f"camplabel-{time.time_ns()}",
    }
    r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations", json=body, headers=auth_headers)
    assert r.status_code in (200, 201), f"Create failed: {r.text}"
    donation = r.json()
    donation_id = donation["donation_id"]
    rv = requests.post(
        f"{BASE_URL}/api/campaigns/venycome/donations/{donation_id}/verify",
        json={"payment_method": method},
        headers=auth_headers,
    )
    assert rv.status_code == 200, f"Verify failed: {rv.text}"
    return rv.json()


class TestCampaignNameLabel:
    def test_verified_donation_contribution_has_campaign_fields(self, auth_headers, test_person):
        verify_resp = _create_and_verify_donation(auth_headers, test_person["person_id"], test_person["full_name"], amount=1500, method="cash")
        contribution_id = verify_resp.get("finance_contribution_id")
        assert contribution_id, f"verify response missing finance_contribution_id: {verify_resp}"
        # Fetch general contributions and find exact one
        r = requests.get(f"{BASE_URL}/api/finance/contributions", headers=auth_headers, params={"limit": 200})
        assert r.status_code == 200, r.text
        items = r.json().get("items") or r.json()
        latest = next((x for x in items if x.get("contribution_id") == contribution_id or x.get("_id") == contribution_id), None)
        assert latest, f"Contribution {contribution_id} not found. Sample keys: {[list(x.keys()) for x in items[:1]]}"
        assert latest.get("campaign_id"), f"campaign_id missing: {latest}"
        assert latest.get("campaign_name") == CAMPAIGN_NAME, f"campaign_name wrong: {latest.get('campaign_name')!r}"
        allocs = latest.get("allocations") or []
        assert allocs and allocs[0].get("campaign_id") == latest["campaign_id"], f"allocations missing campaign_id: {allocs}"
        desc = latest.get("description") or ""
        assert CAMPAIGN_NAME in desc, f"Description missing campaign name: {desc!r}"
        assert test_person["full_name"] in desc, f"Description missing donor name: {desc!r}"

    def test_finance_campaign_record_is_idempotent(self, auth_headers, test_person):
        # Create & verify a second donation; ensure only ONE finance_campaigns record exists
        _create_and_verify_donation(auth_headers, test_person["person_id"], test_person["full_name"], amount=2500, method="zelle")
        # Query finance campaigns list
        r = requests.get(f"{BASE_URL}/api/finance/campaigns", headers=auth_headers)
        if r.status_code == 404:
            pytest.skip("No finance campaigns listing endpoint available")
        assert r.status_code == 200, r.text
        items = r.json().get("items") or r.json()
        matches = [c for c in items if c.get("name") == CAMPAIGN_NAME]
        assert len(matches) == 1, f"Expected exactly 1 '{CAMPAIGN_NAME}' campaign, found {len(matches)}: {matches}"

    def test_person_contributions_endpoint_has_campaign_name(self, auth_headers, test_person):
        r = requests.get(
            f"{BASE_URL}/api/finance/persons/{test_person['person_id']}/contributions",
            headers=auth_headers,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        items = r.json().get("items") or r.json()
        assert items, "Expected at least one contribution"
        campaign_items = [x for x in items if x.get("campaign_name")]
        assert campaign_items, f"No item with campaign_name. Items: {items[:3]}"
        for it in campaign_items:
            assert it["campaign_name"] == CAMPAIGN_NAME

    def test_general_list_regression_non_campaign_item_has_null(self, auth_headers):
        """Any item without campaign_id should return campaign_name=null (field present)."""
        r = requests.get(f"{BASE_URL}/api/finance/contributions", headers=auth_headers, params={"limit": 100})
        assert r.status_code == 200
        items = r.json().get("items") or r.json()
        non_campaign = [x for x in items if not x.get("campaign_id")]
        if not non_campaign:
            pytest.skip("No non-campaign contributions available for regression check")
        for it in non_campaign[:5]:
            # key must exist and be None
            assert "campaign_name" in it, f"campaign_name key missing on non-campaign item: {it}"
            assert it["campaign_name"] is None, f"Non-campaign item had non-null campaign_name: {it}"
