"""Backend tests for the new POST /api/campaigns/venycome/donations/{id}/unverify
endpoint (iteration: revert donation verification).

Covers:
- Verify -> unverify happy path (donation state + the Colecta item voided; nothing deleted).
- 409 when unverifying a non-verified donation.
- Post-unverify: PUT (edit), /void, DELETE, re-verify (new Colecta item) all work.
"""
import os
import uuid

import pytest
import requests


from tests.conftest import campaign_receiver_headers
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PASTOR = ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!")
API = f"{BASE_URL}/api/campaigns/venycome"


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers():
    return {"Authorization": f"Bearer {_login(*PASTOR)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def ensure_rehearsal_mode(headers):
    # Keep in rehearsal mode so we don't pollute real finance; endpoint still creates finance docs.
    r = requests.put(f"{API}/settings", headers=headers,
                     json={"goal_cents": 1_200_000, "counting_rule": "committed", "mode": "rehearsal"})
    assert r.status_code == 200
    requests.post(f"{API}/settings/reset-rehearsal", headers=headers)
    yield
    requests.post(f"{API}/settings/reset-rehearsal", headers=headers)


def _create_received_donation(headers, amount=5000):
    payload = {
        "donor_name": f"TEST_Unverify_{uuid.uuid4().hex[:6]}",
        "amount_cents": amount,
        "donation_type": "received",
        "note": "unverify-test",
        "idempotency_key": str(uuid.uuid4()),
    }
    r = requests.post(f"{API}/donations", headers=headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create failed {r.status_code} {r.text}"
    return r.json()


def _verify(headers, donation_id, method="zelle"):
    r = requests.post(f"{API}/donations/{donation_id}/verify", headers=campaign_receiver_headers(),
                      json={"payment_method": method}, timeout=30)
    assert r.status_code == 200, f"verify failed {r.status_code} {r.text}"
    return r.json()


class TestUnverifyHappyPath:
    def test_unverify_resets_flags_and_voids_collection_item(self, headers):
        donation = _create_received_donation(headers)
        did = donation["donation_id"]
        verified = _verify(headers, did, "zelle")
        # Nuevo flujo: el donativo entra como aporte de la colecta «Ven y Come» (aún no es contribución).
        item_id, collection_id = verified.get("finance_collection_item_id"), verified.get("finance_collection_id")
        assert item_id and collection_id, f"verify did not register a collection item: {verified}"
        assert verified.get("finance_contribution_id") in (None, "")
        assert verified.get("verified") is True
        assert verified.get("finance_person_id")
        collection = requests.get(f"{BASE_URL}/api/finance/collections/{collection_id}", headers=headers, timeout=30).json()
        item = next(x for x in collection["items"] if x["item_id"] == item_id)
        assert collection["source"] == "campaign_venycome" and collection["is_test"] is True  # ensayo: datos de prueba
        assert item["status"] == "active" and item["amount_cents"] == 5000 and item["method"] == "zelle"

        r = requests.post(f"{API}/donations/{did}/unverify", headers=campaign_receiver_headers(), timeout=30)
        assert r.status_code == 200, f"unverify failed {r.status_code} {r.text}"
        after = r.json()
        assert after.get("verified") is False
        assert after.get("verified_at") in (None, "")
        assert after.get("finance_collection_item_id") in (None, "")
        assert after.get("finance_person_id") in (None, "")
        assert after.get("verified_payment_method") in (None, "")
        g = requests.get(f"{API}/donations", headers=headers, timeout=30)
        gitems = g.json() if isinstance(g.json(), list) else g.json().get("items", [])
        assert next(x for x in gitems if x.get("donation_id") == did).get("verified") is False
        # El aporte queda anulado en la colecta (nunca se borra).
        collection = requests.get(f"{BASE_URL}/api/finance/collections/{collection_id}", headers=headers, timeout=30).json()
        assert next(x for x in collection["items"] if x["item_id"] == item_id)["status"] == "voided"

    def test_unverify_on_not_verified_returns_409(self, headers):
        donation = _create_received_donation(headers)
        did = donation["donation_id"]
        r = requests.post(f"{API}/donations/{did}/unverify", headers=campaign_receiver_headers(), timeout=30)
        assert r.status_code == 409, f"expected 409 got {r.status_code} {r.text}"
        body = r.json()
        detail = (body.get("detail") or "").lower()
        assert "verific" in detail or "no está" in detail or "no esta" in detail

    def test_after_unverify_edit_void_delete_and_reverify_new_contribution(self, headers):
        donation = _create_received_donation(headers, amount=7000)
        did = donation["donation_id"]
        v1 = _verify(headers, did, "zelle")
        original_cid = v1["finance_collection_item_id"]

        # While verified: edit should 409
        edit_while_verified = requests.put(f"{API}/donations/{did}", headers=headers,
                                           json={"donor_name": "TEST_EditBlocked", "amount_cents": 7000, "donation_type": "received"}, timeout=30)
        assert edit_while_verified.status_code == 409

        # Unverify
        u = requests.post(f"{API}/donations/{did}/unverify", headers=campaign_receiver_headers(), timeout=30)
        assert u.status_code == 200

        # Edit should now succeed
        e = requests.put(f"{API}/donations/{did}", headers=headers,
                         json={"donor_name": "TEST_EditedAfterUnverify", "amount_cents": 7500,
                               "donation_type": "received"}, timeout=30)
        assert e.status_code == 200, f"edit after unverify failed {e.status_code} {e.text}"
        assert e.json().get("amount_cents") == 7500

        # Re-verify -> new contribution id
        v2 = _verify(headers, did, "cash")
        new_cid = v2["finance_collection_item_id"]
        assert new_cid and new_cid != original_cid, f"expected new cid, orig={original_cid} new={new_cid}"

        # Unverify again, then try /void and DELETE
        requests.post(f"{API}/donations/{did}/unverify", headers=campaign_receiver_headers(), timeout=30)

        # Try void
        donation2 = _create_received_donation(headers, amount=3000)
        did2 = donation2["donation_id"]
        _verify(headers, did2, "zelle")
        requests.post(f"{API}/donations/{did2}/unverify", headers=campaign_receiver_headers(), timeout=30)
        void_r = requests.post(f"{API}/donations/{did2}/void", headers=headers, timeout=30)
        assert void_r.status_code == 200, f"void after unverify failed {void_r.status_code} {void_r.text}"

        # Try delete on first after re-unverify
        del_r = requests.delete(f"{API}/donations/{did}", headers=headers, timeout=30)
        assert del_r.status_code in (200, 204), f"delete after unverify failed {del_r.status_code} {del_r.text}"


class TestUnverifyRBAC:
    def test_no_auth_rejected(self):
        r = requests.post(f"{API}/donations/does-not-exist/unverify")
        assert r.status_code in (401, 403)
