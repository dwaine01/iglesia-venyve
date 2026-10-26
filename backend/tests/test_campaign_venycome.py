"""Backend tests for Campaña Ven y Come (iteration 19).
Covers RBAC, CRUD, idempotency, void, mark-received, settings, reset-rehearsal,
presentation links, public summary (token + JWT), and WebSocket access.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://invasiones-mentor.preview.emergentagent.com").rstrip("/")
PASTOR = ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!")
LIDER = ("qa.baptismui53.lider@example.com", "QaBaptismUI53!")

API = f"{BASE_URL}/api/campaigns/venycome"


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def pastor_headers():
    return {"Authorization": f"Bearer {_login(*PASTOR)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def lider_headers():
    return {"Authorization": f"Bearer {_login(*LIDER)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def pastor_jwt():
    return _login(*PASTOR)


@pytest.fixture(scope="module", autouse=True)
def ensure_rehearsal_mode(pastor_headers):
    """Make sure test runs in rehearsal mode and clear rehearsal donations before + after."""
    r = requests.put(f"{API}/settings", headers=pastor_headers,
                     json={"goal_cents": 1_200_000, "counting_rule": "committed", "mode": "rehearsal"})
    assert r.status_code == 200
    requests.post(f"{API}/settings/reset-rehearsal", headers=pastor_headers)
    yield
    requests.post(f"{API}/settings/reset-rehearsal", headers=pastor_headers)


# ---------------- RBAC ----------------

class TestRBAC:
    def test_no_auth_rejected(self):
        for method, url in [("get", "/settings"), ("get", "/summary"), ("get", "/donations"),
                             ("post", "/donations"), ("get", "/presentation-links")]:
            r = getattr(requests, method)(f"{API}{url}", json={} if method == "post" else None)
            assert r.status_code in (401, 403), f"{url} returned {r.status_code}"

    def test_lider_without_capability_forbidden(self, lider_headers):
        for method, url, body in [("get", "/settings", None), ("get", "/summary", None),
                                   ("get", "/donations", None),
                                   ("post", "/donations", {"amount_cents": 1000}),
                                   ("get", "/presentation-links", None),
                                   ("post", "/settings/reset-rehearsal", {})]:
            if method == "get":
                r = requests.get(f"{API}{url}", headers=lider_headers)
            else:
                r = requests.post(f"{API}{url}", headers=lider_headers, json=body)
            assert r.status_code == 403, f"{url} should be 403, got {r.status_code}"

    def test_pastor_can_read_settings(self, pastor_headers):
        r = requests.get(f"{API}/settings", headers=pastor_headers)
        assert r.status_code == 200
        d = r.json()
        assert "goal_cents" in d and "counting_rule" in d and "mode" in d


# ---------------- Settings ----------------

class TestSettings:
    def test_update_settings_received_only(self, pastor_headers):
        r = requests.put(f"{API}/settings", headers=pastor_headers,
                         json={"goal_cents": 1_200_000, "counting_rule": "received_only", "mode": "rehearsal"})
        assert r.status_code == 200
        assert r.json()["counting_rule"] == "received_only"
        g = requests.get(f"{API}/settings", headers=pastor_headers).json()
        assert g["counting_rule"] == "received_only"

        # Restore committed
        r = requests.put(f"{API}/settings", headers=pastor_headers,
                         json={"goal_cents": 1_200_000, "counting_rule": "committed", "mode": "rehearsal"})
        assert r.status_code == 200

    def test_settings_validation_rejects_negative_goal(self, pastor_headers):
        r = requests.put(f"{API}/settings", headers=pastor_headers,
                         json={"goal_cents": -1, "counting_rule": "committed", "mode": "rehearsal"})
        assert r.status_code == 422


# ---------------- Donations CRUD ----------------

class TestDonationsCRUD:
    def test_create_donation_odd_amount(self, pastor_headers):
        payload = {"donor_name": "TEST_Odd", "amount_cents": 3333, "donation_type": "received",
                   "anonymous": False, "consent_show_name": True}
        r = requests.post(f"{API}/donations", headers=pastor_headers, json=payload)
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["amount_cents"] == 3333
        assert d["donor_name"] == "TEST_Odd"
        assert d["status"] == "active"
        assert d["is_rehearsal"] is True
        assert "donation_id" in d
        # Verify list
        lst = requests.get(f"{API}/donations", headers=pastor_headers).json()
        ids = [i["donation_id"] for i in lst["items"]]
        assert d["donation_id"] in ids

    def test_idempotency_double_post(self, pastor_headers):
        key = f"TEST_idemp_{uuid.uuid4()}"
        payload = {"donor_name": "TEST_Idem", "amount_cents": 5000, "donation_type": "received",
                   "consent_show_name": True, "idempotency_key": key}
        r1 = requests.post(f"{API}/donations", headers=pastor_headers, json=payload)
        r2 = requests.post(f"{API}/donations", headers=pastor_headers, json=payload)
        assert r1.status_code == 201
        assert r2.status_code in (200, 201)
        assert r1.json()["donation_id"] == r2.json()["donation_id"], "Idempotency broken"

    def test_update_donation(self, pastor_headers):
        c = requests.post(f"{API}/donations", headers=pastor_headers, json={
            "donor_name": "TEST_Edit", "amount_cents": 2500, "donation_type": "received",
            "consent_show_name": True}).json()
        did = c["donation_id"]
        u = requests.put(f"{API}/donations/{did}", headers=pastor_headers, json={
            "donor_name": "TEST_Edited", "amount_cents": 7777, "donation_type": "received",
            "anonymous": False, "consent_show_name": True})
        assert u.status_code == 200
        assert u.json()["amount_cents"] == 7777
        assert u.json()["donor_name"] == "TEST_Edited"

    def test_mark_received_moves_from_pending(self, pastor_headers):
        # Reset for clean totals
        requests.post(f"{API}/settings/reset-rehearsal", headers=pastor_headers)
        p = requests.post(f"{API}/donations", headers=pastor_headers, json={
            "donor_name": "TEST_Promise", "amount_cents": 10000, "donation_type": "promise",
            "consent_show_name": True}).json()
        s1 = requests.get(f"{API}/summary", headers=pastor_headers).json()
        assert s1["pending_cents"] == 10000
        assert s1["received_cents"] == 0

        r = requests.post(f"{API}/donations/{p['donation_id']}/mark-received", headers=pastor_headers)
        assert r.status_code == 200
        assert r.json()["donation_type"] == "received"

        s2 = requests.get(f"{API}/summary", headers=pastor_headers).json()
        assert s2["pending_cents"] == 0
        assert s2["received_cents"] == 10000
        assert s2["committed_cents"] == 10000  # no double count

    def test_mark_received_twice_conflict(self, pastor_headers):
        c = requests.post(f"{API}/donations", headers=pastor_headers, json={
            "donor_name": "TEST_AlreadyR", "amount_cents": 500, "donation_type": "received",
            "consent_show_name": True}).json()
        r = requests.post(f"{API}/donations/{c['donation_id']}/mark-received", headers=pastor_headers)
        assert r.status_code == 409

    def test_void_donation(self, pastor_headers):
        c = requests.post(f"{API}/donations", headers=pastor_headers, json={
            "donor_name": "TEST_Void", "amount_cents": 4000, "donation_type": "received",
            "consent_show_name": True}).json()
        did = c["donation_id"]
        r = requests.post(f"{API}/donations/{did}/void", headers=pastor_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "voided"

        # Cannot edit voided
        u = requests.put(f"{API}/donations/{did}", headers=pastor_headers, json={
            "donor_name": "x", "amount_cents": 100, "donation_type": "received",
            "anonymous": False, "consent_show_name": False})
        assert u.status_code == 409

        # Cannot void again
        v2 = requests.post(f"{API}/donations/{did}/void", headers=pastor_headers)
        assert v2.status_code == 409

        # Cannot show voided
        s = requests.post(f"{API}/donations/{did}/show", headers=pastor_headers)
        assert s.status_code == 409

    def test_show_existing_donation(self, pastor_headers):
        c = requests.post(f"{API}/donations", headers=pastor_headers, json={
            "donor_name": "TEST_Show", "amount_cents": 100, "donation_type": "received",
            "consent_show_name": True}).json()
        r = requests.post(f"{API}/donations/{c['donation_id']}/show", headers=pastor_headers)
        assert r.status_code == 200
        # No duplicate donation created
        lst = requests.get(f"{API}/donations", headers=pastor_headers).json()
        matches = [i for i in lst["items"] if i["donation_id"] == c["donation_id"]]
        assert len(matches) == 1

    def test_max_amount_rejected(self, pastor_headers):
        r = requests.post(f"{API}/donations", headers=pastor_headers, json={
            "amount_cents": 10_000_001, "donation_type": "received"})
        assert r.status_code == 422

    def test_zero_amount_rejected(self, pastor_headers):
        r = requests.post(f"{API}/donations", headers=pastor_headers, json={
            "amount_cents": 0, "donation_type": "received"})
        assert r.status_code == 422


# ---------------- Counting rule ----------------

class TestCountingRule:
    def test_received_only_excludes_promises(self, pastor_headers):
        requests.post(f"{API}/settings/reset-rehearsal", headers=pastor_headers)
        requests.post(f"{API}/donations", headers=pastor_headers, json={
            "donor_name": "TEST_P", "amount_cents": 5000, "donation_type": "promise"})
        requests.post(f"{API}/donations", headers=pastor_headers, json={
            "donor_name": "TEST_R", "amount_cents": 3000, "donation_type": "received"})
        # Committed
        requests.put(f"{API}/settings", headers=pastor_headers,
                     json={"goal_cents": 1_200_000, "counting_rule": "committed", "mode": "rehearsal"})
        s = requests.get(f"{API}/summary", headers=pastor_headers).json()
        assert s["counted_cents"] == 8000
        # received_only
        requests.put(f"{API}/settings", headers=pastor_headers,
                     json={"goal_cents": 1_200_000, "counting_rule": "received_only", "mode": "rehearsal"})
        s2 = requests.get(f"{API}/summary", headers=pastor_headers).json()
        assert s2["counted_cents"] == 3000
        assert s2["received_cents"] == 3000
        assert s2["pending_cents"] == 5000  # Raw totals unchanged
        # Restore
        requests.put(f"{API}/settings", headers=pastor_headers,
                     json={"goal_cents": 1_200_000, "counting_rule": "committed", "mode": "rehearsal"})


# ---------------- Reset rehearsal ----------------

class TestReset:
    def test_reset_rehearsal_only_deletes_rehearsal(self, pastor_headers):
        # In rehearsal mode, create donation → should be is_rehearsal=True
        d = requests.post(f"{API}/donations", headers=pastor_headers, json={
            "amount_cents": 100, "donation_type": "received"}).json()
        assert d["is_rehearsal"] is True
        r = requests.post(f"{API}/settings/reset-rehearsal", headers=pastor_headers)
        assert r.status_code == 200
        assert r.json()["deleted_count"] >= 1
        # Confirm empty
        lst = requests.get(f"{API}/donations", headers=pastor_headers).json()
        assert len(lst["items"]) == 0


# ---------------- Presentation links + public access ----------------

class TestPublic:
    def test_create_revoke_link_and_public_summary(self, pastor_headers):
        c = requests.post(f"{API}/presentation-links", headers=pastor_headers,
                          json={"label": "TEST_pres"})
        assert c.status_code == 201
        link = c.json()
        token = link["token"]
        token_id = link["token_id"]

        # Public summary with valid token (NO auth header)
        r = requests.get(f"{API}/public/summary", params={"token": token})
        assert r.status_code == 200
        assert "percent" in r.json()

        # No token
        r0 = requests.get(f"{API}/public/summary")
        assert r0.status_code in (403, 422)

        # Invalid token
        rbad = requests.get(f"{API}/public/summary", params={"token": "invalid123"})
        assert rbad.status_code == 403

        # Revoke
        rv = requests.post(f"{API}/presentation-links/{token_id}/revoke", headers=pastor_headers)
        assert rv.status_code == 200

        # After revocation, token no longer works
        r2 = requests.get(f"{API}/public/summary", params={"token": token})
        assert r2.status_code == 403

    def test_public_summary_rejects_user_jwt(self, pastor_jwt):
        # La sesión de un usuario ya no sirve como enlace público (quedaba en historial, proyector y registros).
        r = requests.get(f"{API}/public/summary", params={"token": pastor_jwt})
        assert r.status_code == 403

    def test_screen_link_is_temporary_and_hidden(self, pastor_headers):
        created = requests.post(f"{API}/screen-link", headers=pastor_headers)
        assert created.status_code == 201, created.text
        token = created.json()["token"]
        assert requests.get(f"{API}/public/summary", params={"token": token}).status_code == 200
        listed = requests.get(f"{API}/presentation-links", headers=pastor_headers).json()["items"]
        assert all(item.get("token") != token for item in listed)

    def test_list_presentation_links(self, pastor_headers):
        r = requests.get(f"{API}/presentation-links", headers=pastor_headers)
        assert r.status_code == 200
        assert "items" in r.json()

    def test_revoke_nonexistent(self, pastor_headers):
        r = requests.post(f"{API}/presentation-links/nonexistent-id/revoke", headers=pastor_headers)
        assert r.status_code == 404


# ---------------- Anonymous display ----------------

class TestAnonymousLabel:
    """Verify donor_label logic indirectly via donation record state."""
    def test_anonymous_flag_persisted(self, pastor_headers):
        d = requests.post(f"{API}/donations", headers=pastor_headers, json={
            "donor_name": "TEST_ShouldHide", "amount_cents": 100, "donation_type": "received",
            "anonymous": True, "consent_show_name": False}).json()
        assert d["anonymous"] is True
        assert d["consent_show_name"] is False
