"""
Backend tests for iteration 28:
- BUG FIX: PUT /api/core/governance/users/{user_id}/access accepts 'campaign.venycome.manage'
- NEW FEATURE: zelle_info in Campaign Settings
- NEW FEATURE: GET /donations/{id}/contact and POST /donations/{id}/notes
- REGRESSION: low-privilege operator can access campaign endpoints but not person directory
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pdf-layout-fix-16.preview.emergentagent.com").rstrip("/")

PASTOR_EMAIL = "qa.baptismui53.pastor@example.com"
PASTOR_PASS = "QaBaptismUI53!"
MEMBER_EMAIL = "coreqa.member@example.com"
MEMBER_PASS = "MemberQA2026!"
MEMBER_USER_ID = "6ab4897333f15d6b82918f62"

ORIGINAL_MEMBER_CAPS = [
    "baptism.read", "cellular.read", "dedication.read", "formation.read",
    "operations.view", "operations.volunteer", "person.addresses.read", "person.addresses.write",
    "person.arrival.read", "person.attendance.read", "person.contacts.read", "person.contacts.write",
    "person.family.read", "person.history.read", "person.household.read", "person.ministries.read",
    "person.notes.read", "person.profile.sensitive.read", "person.profile.write",
    "person.talents.read", "person.talents.write", "processes.participate", "processes.read",
]


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def pastor_headers():
    token = _login(PASTOR_EMAIL, PASTOR_PASS)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def member_headers():
    token = _login(MEMBER_EMAIL, MEMBER_PASS)
    return {"Authorization": f"Bearer {token}"}


# ============ BUG FIX: capabilities validation ============
class TestCapabilityAssignment:
    def test_grant_campaign_venycome_manage(self, pastor_headers):
        """Pastor should be able to grant campaign.venycome.manage to a persona-level user."""
        new_caps = sorted(set(ORIGINAL_MEMBER_CAPS + ["campaign.venycome.manage"]))
        payload = {
            "access_level": "persona",
            "privilege_groups": [],
            "capabilities": new_caps,
            "is_active": True,
        }
        r = requests.put(
            f"{BASE_URL}/api/core/governance/users/{MEMBER_USER_ID}/access",
            json=payload, headers=pastor_headers, timeout=15,
        )
        assert r.status_code == 200, f"grant failed: {r.status_code} {r.text}"
        data = r.json()
        caps = data.get("capabilities") or data.get("user", {}).get("capabilities", [])
        assert "campaign.venycome.manage" in caps, f"capability not persisted: {caps}"


# ============ FEATURE: zelle_info in settings ============
class TestCampaignSettingsZelle:
    def test_settings_persists_zelle_info(self, pastor_headers):
        zelle_text = f"TEST_zelle_{int(time.time())}@iglesia.org"
        # Get current settings to preserve values
        get_r = requests.get(f"{BASE_URL}/api/campaigns/venycome/settings", headers=pastor_headers, timeout=15)
        assert get_r.status_code == 200
        current = get_r.json()
        payload = {
            "goal_cents": current.get("goal_cents") or 1_200_000,
            "counting_rule": current.get("counting_rule") or "committed",
            "mode": current.get("mode") or "rehearsal",
            "zelle_info": zelle_text,
        }
        put_r = requests.put(f"{BASE_URL}/api/campaigns/venycome/settings", json=payload, headers=pastor_headers, timeout=15)
        assert put_r.status_code == 200, put_r.text
        assert put_r.json().get("zelle_info") == zelle_text

        # Verify by GET
        get2 = requests.get(f"{BASE_URL}/api/campaigns/venycome/settings", headers=pastor_headers, timeout=15)
        assert get2.json().get("zelle_info") == zelle_text


# ============ FEATURE: contact endpoint + notes ============
@pytest.fixture(scope="module")
def test_donation(pastor_headers):
    """Create a donation linked to pastor's own person for contact testing."""
    # Fetch pastor's person_id by their account info
    me = requests.get(f"{BASE_URL}/api/auth/me", headers=pastor_headers, timeout=15)
    person_id = None
    if me.status_code == 200:
        person_id = me.json().get("user", {}).get("person_id") or me.json().get("person_id")

    payload = {
        "donor_name": f"TEST_ContactDonor_{int(time.time())}",
        "person_id": person_id,
        "amount_cents": 5000,
        "donation_type": "received",
        "anonymous": False,
        "consent_show_name": True,
    }
    r = requests.post(f"{BASE_URL}/api/campaigns/venycome/donations", json=payload, headers=pastor_headers, timeout=15)
    assert r.status_code in (200, 201), r.text
    donation = r.json()
    yield donation
    # Cleanup
    try:
        requests.delete(f"{BASE_URL}/api/campaigns/venycome/donations/{donation['donation_id']}", headers=pastor_headers, timeout=10)
    except Exception:
        pass


class TestContactEndpoint:
    def test_contact_returns_structure(self, pastor_headers, test_donation):
        did = test_donation["donation_id"]
        r = requests.get(f"{BASE_URL}/api/campaigns/venycome/donations/{did}/contact", headers=pastor_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("donor_name", "amount_cents", "phone", "email", "zelle_info"):
            assert k in data, f"missing key {k}: {data}"
        assert data["amount_cents"] == test_donation["amount_cents"]

    def test_add_note_and_persists(self, pastor_headers, test_donation):
        did = test_donation["donation_id"]
        note_text = f"TEST_note persistence {int(time.time())}"
        r = requests.post(
            f"{BASE_URL}/api/campaigns/venycome/donations/{did}/notes",
            json={"text": note_text}, headers=pastor_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        updated = r.json()
        notes = updated.get("contact_notes") or []
        assert any(n["text"] == note_text for n in notes), f"note not appended: {notes}"
        # Verify present in donations list
        lst = requests.get(f"{BASE_URL}/api/campaigns/venycome/donations", headers=pastor_headers, timeout=15).json()
        item = next((it for it in lst.get("items", []) if it["donation_id"] == did), None)
        assert item is not None
        assert any(n["text"] == note_text for n in item.get("contact_notes") or [])

    def test_empty_note_rejected(self, pastor_headers, test_donation):
        did = test_donation["donation_id"]
        r = requests.post(
            f"{BASE_URL}/api/campaigns/venycome/donations/{did}/notes",
            json={"text": "   "}, headers=pastor_headers, timeout=15,
        )
        assert r.status_code in (400, 422), r.text


# ============ REGRESSION: low-privilege operator permissions ============
class TestLowPrivilegeAccess:
    def test_member_can_access_campaign_summary(self, member_headers):
        r = requests.get(f"{BASE_URL}/api/campaigns/venycome/summary", headers=member_headers, timeout=15)
        # After pastor grant above, member should have campaign operator access
        assert r.status_code == 200, f"operator access denied: {r.status_code} {r.text}"

    def test_member_cannot_list_persons(self, member_headers):
        r = requests.get(f"{BASE_URL}/api/core/persons", headers=member_headers, timeout=15)
        assert r.status_code in (401, 403), f"expected forbidden, got {r.status_code}: {r.text[:200]}"


# ============ CLEANUP: restore member capabilities ============
class TestCleanupRestore:
    def test_restore_original_member_capabilities(self, pastor_headers):
        """Restore coreqa.member to its original capability set WITHOUT campaign.venycome.manage."""
        payload = {
            "access_level": "persona",
            "privilege_groups": [],
            "capabilities": sorted(ORIGINAL_MEMBER_CAPS),
            "is_active": True,
        }
        r = requests.put(
            f"{BASE_URL}/api/core/governance/users/{MEMBER_USER_ID}/access",
            json=payload, headers=pastor_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
