"""Backend tests for Ven y Come campaign donation Persona 360 linkage."""
import os
import time
import requests

from tests.conftest import campaign_receiver_headers
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

PASTOR_EMAIL = "qa.baptismui53.pastor@example.com"
PASTOR_PASSWORD = "QaBaptismUI53!"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": PASTOR_EMAIL, "password": PASTOR_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    assert token
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def test_person(auth_headers):
    # Create a dedicated test person
    payload = {
        "nombre": "TESTPersonLink",
        "apellido": "CampaignQA",
        "fecha_nacimiento": "1990-01-01",
        "idempotency_key": f"test-person-link-{int(time.time())}",
    }
    r = requests.post(f"{BASE_URL}/api/core/persons", json=payload, headers=auth_headers)
    if r.status_code == 409:  # ya existe de una corrida anterior: se usa la misma (no se duplica)
        data = r.json()["detail"]["candidates"][0]
        return {"person_id": data["person_id"], "nombre_completo": "TESTPersonLink CampaignQA"}
    assert r.status_code in (200, 201), f"Person create failed: {r.status_code} {r.text}"
    data = r.json()
    person_id = data.get("person_id") or data.get("id") or data.get("_id")
    assert person_id, f"No person_id in response: {data}"
    return {"person_id": person_id, "nombre_completo": "TESTPersonLink CampaignQA"}


def _mk_donation(auth_headers, person_id=None, donor_name="TEST Donor", amount=1234):
    body = {
        "donor_name": donor_name,
        "amount_cents": amount,
        "donation_type": "received",
        "anonymous": False,
        "consent_show_name": False,
        "idempotency_key": f"test-don-{time.time_ns()}",
    }
    if person_id:
        body["person_id"] = person_id
    r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations", json=body, headers=auth_headers)
    assert r.status_code in (200, 201), f"Donation create failed: {r.status_code} {r.text}"
    return r.json()


class TestExplicitPersonLink:
    def test_create_donation_with_person_id_stores_it(self, auth_headers, test_person):
        d = _mk_donation(auth_headers, person_id=test_person["person_id"], donor_name=test_person["nombre_completo"])
        assert d.get("person_id") == test_person["person_id"]
        # Fetch donations list and confirm
        r = requests.get(f"{BASE_URL}/api/campaigns/venycome/donations", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        found = next((x for x in items if x.get("donation_id") == d["donation_id"]), None)
        assert found is not None
        assert found.get("person_id") == test_person["person_id"]

    def test_verify_uses_explicit_person_id_exactly(self, auth_headers, test_person):
        d = _mk_donation(auth_headers, person_id=test_person["person_id"], donor_name="SomeOtherName NotMatching")
        donation_id = d["donation_id"]
        r = requests.post(
            f"{BASE_URL}/api/campaigns/venycome/donations/{donation_id}/verify",
            json={"payment_method": "cash"},
            headers=campaign_receiver_headers(),
        )
        assert r.status_code == 200, f"Verify failed: {r.status_code} {r.text}"
        after = r.json()
        assert after.get("finance_person_id") == test_person["person_id"], (
            f"Expected finance_person_id={test_person['person_id']} got {after.get('finance_person_id')}"
        )
        assert after.get("verified") is True

    def test_edit_donation_preserves_person_id(self, auth_headers, test_person):
        d = _mk_donation(auth_headers, person_id=test_person["person_id"], donor_name=test_person["nombre_completo"], amount=5555)
        donation_id = d["donation_id"]
        # Edit amount & donor_name but pass person_id through unchanged
        put_body = {
            "donor_name": "Edited Name TEST",
            "person_id": test_person["person_id"],
            "amount_cents": 7777,
            "donation_type": "received",
            "anonymous": False,
            "consent_show_name": False,
        }
        r = requests.put(f"{BASE_URL}/api/campaigns/venycome/donations/{donation_id}", json=put_body, headers=auth_headers)
        assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text}"
        updated = r.json()
        assert updated.get("person_id") == test_person["person_id"]
        assert updated.get("amount_cents") == 7777
        # Verify afterwards still uses the explicit person_id
        rv = requests.post(
            f"{BASE_URL}/api/campaigns/venycome/donations/{donation_id}/verify",
            json={"payment_method": "cash"},
            headers=campaign_receiver_headers(),
        )
        assert rv.status_code == 200
        assert rv.json().get("finance_person_id") == test_person["person_id"]

    def test_anonymous_overrides_person_id(self, auth_headers, test_person):
        body = {
            "donor_name": None,
            "person_id": test_person["person_id"],
            "amount_cents": 999,
            "donation_type": "received",
            "anonymous": True,
            "consent_show_name": False,
            "idempotency_key": f"test-anon-{time.time_ns()}",
        }
        r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations", json=body, headers=auth_headers)
        assert r.status_code in (200, 201)
        assert r.json().get("person_id") is None, "Anonymous donations must NOT retain person_id"


class TestBackwardCompat:
    def test_donation_without_person_id_stored_as_null(self, auth_headers):
        d = _mk_donation(auth_headers, person_id=None, donor_name="TEST Legacy Free Text Donor Unique XYZ")
        assert d.get("person_id") in (None, "")

    def test_verify_without_person_id_enters_without_person360(self, auth_headers):
        d = _mk_donation(auth_headers, person_id=None, donor_name="TEST Legacy FreeText Unique Donor")
        donation_id = d["donation_id"]
        r = requests.post(
            f"{BASE_URL}/api/campaigns/venycome/donations/{donation_id}/verify",
            json={"payment_method": "cash"},
            headers=campaign_receiver_headers(),
        )
        assert r.status_code == 200, f"Verify failed: {r.status_code} {r.text}"
        after = r.json()
        # Decisión del dueño: ya no se busca ni se crea una persona por el nombre; entra «sin Persona 360»
        # con el nombre tal como lo dieron y se vincula después con «Vincular a Persona 360».
        assert after.get("finance_person_id") is None and after.get("finance_collection_item_id")
        assert after.get("verified") is True
