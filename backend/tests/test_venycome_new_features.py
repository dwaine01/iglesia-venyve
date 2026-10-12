"""Backend tests for Ven y Come new features: delete donation, verify donation,
finance integration (Pro-Templo), 409 guards on verified donations."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

PASTOR_EMAIL = "qa.baptismui53.pastor@example.com"
PASTOR_PASS = "QaBaptismUI53!"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": PASTOR_EMAIL, "password": PASTOR_PASS}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def building_fund_id(auth_headers):
    r = requests.get(f"{BASE_URL}/api/finance/catalog", headers=auth_headers, timeout=15)
    assert r.status_code == 200, f"Could not fetch funds: {r.status_code} {r.text}"
    data = r.json()
    funds = data.get("funds") or []
    for f in funds:
        if f.get("code") == "BUILDING":
            return f.get("fund_id")
    pytest.skip("BUILDING fund not configured")


def _create_donation(auth_headers, donor_name="TEST_VerifyUser One", amount_cents=12345, donation_type="received"):
    r = requests.post(
        f"{BASE_URL}/api/campaigns/venycome/donations",
        headers=auth_headers,
        json={
            "donor_name": donor_name,
            "amount_cents": amount_cents,
            "donation_type": donation_type,
            "anonymous": False,
            "consent_show_name": True,
        },
        timeout=15,
    )
    assert r.status_code == 201, f"create donation failed: {r.status_code} {r.text}"
    return r.json()


# ---------- Delete donation ----------
class TestDeleteDonation:
    def test_delete_unverified_donation(self, auth_headers):
        d = _create_donation(auth_headers, donor_name="TEST_DeleteMe Alpha")
        did = d["donation_id"]
        r = requests.delete(f"{BASE_URL}/api/campaigns/venycome/donations/{did}", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # verify no longer listed
        r2 = requests.get(f"{BASE_URL}/api/campaigns/venycome/donations", headers=auth_headers, timeout=15)
        ids = [it["donation_id"] for it in r2.json()["items"]]
        assert did not in ids


# ---------- Verify donation + finance integration ----------
class TestVerifyDonation:
    def test_verify_received_and_creates_finance_contribution(self, auth_headers, building_fund_id):
        d = _create_donation(auth_headers, donor_name="TEST_VerifyFlow Beta", amount_cents=55500)
        did = d["donation_id"]
        r = requests.post(
            f"{BASE_URL}/api/campaigns/venycome/donations/{did}/verify",
            headers=auth_headers,
            json={"payment_method": "zelle"},
            timeout=20,
        )
        assert r.status_code == 200, f"verify failed: {r.status_code} {r.text}"
        after = r.json()
        assert after["verified"] is True
        assert after["verified_payment_method"] == "zelle"
        assert after.get("finance_contribution_id")
        contribution_id = after["finance_contribution_id"]

        # Finance contribution exists
        r2 = requests.get(f"{BASE_URL}/api/finance/contributions", headers=auth_headers, timeout=15)
        assert r2.status_code == 200, r2.text
        items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
        match = next((c for c in items if c.get("contribution_id") == contribution_id), None)
        assert match is not None, f"Finance contribution {contribution_id} not found"
        assert match["contribution_type"] == "building"
        assert match["amount_cents"] == 55500
        assert match["payment_method"] == "zelle"
        allocations = match.get("allocations", [])
        assert allocations and allocations[0]["fund_id"] == building_fund_id

    def test_re_verify_returns_409(self, auth_headers):
        d = _create_donation(auth_headers, donor_name="TEST_ReVerify Gamma", amount_cents=10000)
        did = d["donation_id"]
        r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/verify", headers=auth_headers, json={"payment_method": "cash"}, timeout=20)
        assert r.status_code == 200
        r2 = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/verify", headers=auth_headers, json={"payment_method": "cash"}, timeout=15)
        assert r2.status_code == 409
        assert "verificado" in r2.json().get("detail", "").lower()

    def test_cannot_edit_verified(self, auth_headers):
        d = _create_donation(auth_headers, donor_name="TEST_LockedEdit Delta", amount_cents=10000)
        did = d["donation_id"]
        requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/verify", headers=auth_headers, json={"payment_method": "zelle"}, timeout=20)
        r = requests.put(
            f"{BASE_URL}/api/campaigns/venycome/donations/{did}",
            headers=auth_headers,
            json={"donor_name": "Changed", "amount_cents": 20000, "donation_type": "received", "anonymous": False, "consent_show_name": True},
            timeout=15,
        )
        assert r.status_code == 409

    def test_cannot_void_verified(self, auth_headers):
        d = _create_donation(auth_headers, donor_name="TEST_LockedVoid Eps", amount_cents=10000)
        did = d["donation_id"]
        requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/verify", headers=auth_headers, json={"payment_method": "zelle"}, timeout=20)
        r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/void", headers=auth_headers, timeout=15)
        assert r.status_code == 409

    def test_cannot_delete_verified(self, auth_headers):
        d = _create_donation(auth_headers, donor_name="TEST_LockedDelete Zeta", amount_cents=10000)
        did = d["donation_id"]
        requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/verify", headers=auth_headers, json={"payment_method": "zelle"}, timeout=20)
        r = requests.delete(f"{BASE_URL}/api/campaigns/venycome/donations/{did}", headers=auth_headers, timeout=15)
        assert r.status_code == 409

    def test_cannot_verify_promise(self, auth_headers):
        d = _create_donation(auth_headers, donor_name="TEST_Promise Eta", amount_cents=10000, donation_type="promise")
        did = d["donation_id"]
        r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/verify", headers=auth_headers, json={"payment_method": "zelle"}, timeout=15)
        assert r.status_code == 409
        assert "recibidos" in r.json().get("detail", "").lower()


# ---------- Summary includes donor_totals ----------
class TestSummaryDonorTotals:
    def test_summary_contains_donor_totals(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/campaigns/venycome/summary", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "donor_totals" in data
        assert isinstance(data["donor_totals"], dict)
