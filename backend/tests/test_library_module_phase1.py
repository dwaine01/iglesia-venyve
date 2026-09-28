"""Librería 360 (Phase 1) backend tests: catalog CRUD, ledger movements, custody chain,
Persona 360 delivery + finance auto-post, requests approve/partial, damage/loss write-off,
return round-trip, RBAC 403 boundaries, and Encargado de Librería grant/revoke.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pdf-layout-fix-16.preview.emergentagent.com").rstrip("/")
PASTOR_EMAIL = "qa.baptismui53.pastor@example.com"
LIDER_EMAIL = "qa.baptismui53.lider@example.com"
PASSWORD = "QaBaptismUI53!"
TEST_PERSON_ID = "6ab7537721d2e54a3065b2d8"  # BautismoUI CandidatoUno


def _login(email: str) -> dict:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    d = r.json()
    return {"token": d["token"], "user_id": d["user"]["id"], "email": email}


@pytest.fixture(scope="module")
def pastor():
    return _login(PASTOR_EMAIL)


@pytest.fixture(scope="module")
def lider():
    return _login(LIDER_EMAIL)


@pytest.fixture(scope="module")
def persona_user(pastor):
    """Create a temporary persona-role user for RBAC negative tests."""
    email = f"TEST_libpersona_{uuid.uuid4().hex[:8]}@example.com"
    # Register via public register endpoint if available, else fallback via DB not accessible from tests
    # Try /api/auth/register
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "nombre": "TEST Persona Library",
        "email": email,
        "password": PASSWORD,
    }, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"Cannot register persona test user: {r.status_code} {r.text[:200]}")
    login = _login(email)
    yield login
    # No teardown API for user delete; leaving tagged with TEST_ prefix


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ------------ Catalog ------------
class TestCatalog:
    def test_seed_books_present(self, pastor):
        r = requests.get(f"{BASE_URL}/api/library/books", headers=_h(pastor["token"]), timeout=30)
        assert r.status_code == 200
        items = r.json()["items"]
        skus = {b["sku"] for b in items if b.get("sku")}
        expected = {"LBS1", "LBS2", "LBS3", "MCD", "NPT", "DISC1", "DISC2", "DISC3", "DISC4", "RETIRO", "MENTORIA", "CAP"}
        assert expected.issubset(skus), f"missing seed SKUs: {expected - skus}"

    def test_create_edit_toggle_book(self, pastor):
        payload = {
            "sku": f"TESTSKU{uuid.uuid4().hex[:6].upper()}",
            "name": "TEST Book Phase1",
            "item_type": "libro",
            "process_key": "discipleship",
            "cost_price_cents": 500,
            "member_price_cents": 1200,
            "min_stock": 5,
            "ideal_stock": 20,
            "location": "Test Shelf",
        }
        r = requests.post(f"{BASE_URL}/api/library/books", headers=_h(pastor["token"]), json=payload, timeout=30)
        assert r.status_code == 201, r.text
        book = r.json()
        book_id = book["book_id"]
        assert book["member_price_cents"] == 1200

        # Edit
        payload["member_price_cents"] = 2000
        r2 = requests.put(f"{BASE_URL}/api/library/books/{book_id}", headers=_h(pastor["token"]), json=payload, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["member_price_cents"] == 2000

        # Toggle
        r3 = requests.patch(f"{BASE_URL}/api/library/books/{book_id}/toggle-active", headers=_h(pastor["token"]), timeout=30)
        assert r3.status_code == 200
        assert r3.json()["is_active"] is False


# ------------ Ledger + custody ------------
@pytest.fixture(scope="module")
def disc1_book(pastor):
    r = requests.get(f"{BASE_URL}/api/library/books", headers=_h(pastor["token"]), params={"search": "Discipulado 1"}, timeout=30)
    items = r.json()["items"]
    book = next((b for b in items if b.get("sku") == "DISC1"), None)
    assert book, "Discipulado 1 seed not found"
    return book


@pytest.fixture(scope="module")
def lbs1_book(pastor):
    r = requests.get(f"{BASE_URL}/api/library/books", headers=_h(pastor["token"]), params={"search": "LBS 1"}, timeout=30)
    items = r.json()["items"]
    return next(b for b in items if b.get("sku") == "LBS1")


def _dashboard_totals(token):
    r = requests.get(f"{BASE_URL}/api/library/dashboard", headers=_h(token), timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["totals"]


def _inventory_row(pastor, book_id):
    r = requests.get(f"{BASE_URL}/api/library/inventory", headers=_h(pastor["token"]), timeout=30)
    assert r.status_code == 200
    return next(i for i in r.json()["items"] if i["book_id"] == book_id)


class TestInventoryLedger:
    def test_purchase_receipt_and_transfer(self, pastor, lider, disc1_book):
        book_id = disc1_book["book_id"]
        before = _inventory_row(pastor, book_id)
        before_central = before["available_central"]
        before_with_leaders = before["with_leaders"]

        # Receive 50
        r = requests.post(f"{BASE_URL}/api/library/movements", headers=_h(pastor["token"]), json={
            "book_id": book_id, "movement_type": "PURCHASE_RECEIPT", "quantity": 50,
            "to_holder": {"type": "warehouse", "id": "central"},
        }, timeout=30)
        assert r.status_code == 201, r.text

        after_receipt = _inventory_row(pastor, book_id)
        assert after_receipt["available_central"] == before_central + 50

        # Transfer 10 to lider
        r2 = requests.post(f"{BASE_URL}/api/library/movements", headers=_h(pastor["token"]), json={
            "book_id": book_id, "movement_type": "TRANSFER", "quantity": 10,
            "from_holder": {"type": "warehouse", "id": "central"},
            "to_holder": {"type": "user", "id": lider["user_id"]},
        }, timeout=30)
        assert r2.status_code == 201, r2.text

        after_transfer = _inventory_row(pastor, book_id)
        assert after_transfer["available_central"] == before_central + 40
        assert after_transfer["with_leaders"] >= before_with_leaders + 10

        # Lider my-holdings shows book
        my = requests.get(f"{BASE_URL}/api/library/my-holdings", headers=_h(lider["token"]), timeout=30)
        assert my.status_code == 200
        found = next((i for i in my.json()["items"] if i["book"]["book_id"] == book_id), None)
        assert found and found["on_hand"] >= 10


class TestDeliveryAndFinance:
    def test_deliver_paid_and_finance_autopost(self, lider, disc1_book):
        book_id = disc1_book["book_id"]
        before_dash = _dashboard_totals(lider["token"])

        # Lider my-holdings before
        my_before = requests.get(f"{BASE_URL}/api/library/my-holdings", headers=_h(lider["token"]), timeout=30).json()["items"]
        lider_before = next(i for i in my_before if i["book"]["book_id"] == book_id)["on_hand"]

        # Deliver 1 unit at $15.00 paid
        r = requests.post(f"{BASE_URL}/api/library/persons/{TEST_PERSON_ID}/deliver",
                          headers=_h(lider["token"]), json={
                              "book_id": book_id, "quantity": 1,
                              "payment_status": "pagado",
                              "amount_paid_cents": 1500,
                              "payment_method": "efectivo",
                              "notes": "TEST delivery paid $15",
                          }, timeout=30)
        assert r.status_code == 201, r.text
        movement = r.json()
        assert movement["finance_contribution_id"], f"finance_contribution_id missing: {movement}"
        assert not movement.get("finance_sync_error")

        # my-holdings decreased by 1
        my_after = requests.get(f"{BASE_URL}/api/library/my-holdings", headers=_h(lider["token"]), timeout=30).json()["items"]
        lider_after = next(i for i in my_after if i["book"]["book_id"] == book_id)["on_hand"]
        assert lider_after == lider_before - 1

        # Person materials shows delivery
        pm = requests.get(f"{BASE_URL}/api/library/persons/{TEST_PERSON_ID}/materials",
                          headers=_h(lider["token"]), timeout=30)
        assert pm.status_code == 200
        assert any(m["movement_id"] == movement["movement_id"] for m in pm.json()["items"])

        # Verify contribution in finance list (no GET /:id endpoint)
        cid = movement["finance_contribution_id"]
        pastor_state = _login(PASTOR_EMAIL)
        fc = requests.get(f"{BASE_URL}/api/finance/contributions", headers=_h(pastor_state["token"]), timeout=30)
        assert fc.status_code == 200, fc.text
        found = next((c for c in fc.json()["items"] if c.get("contribution_id") == cid), None)
        assert found, f"contribution {cid} not found in finance list"
        assert found["amount_cents"] == 1500
        allocs = found.get("allocations") or []
        assert any(a.get("contribution_type") == "libreria_material_educativo" for a in allocs)

        # Dashboard delivered incremented
        after_dash = _dashboard_totals(lider["token"])
        assert after_dash["delivered"] >= before_dash["delivered"] + 1


class TestRequestsFlow:
    def test_request_and_partial_approve(self, pastor, lider, lbs1_book):
        book_id = lbs1_book["book_id"]

        # Ensure central has enough (receive 20 first)
        requests.post(f"{BASE_URL}/api/library/movements", headers=_h(pastor["token"]), json={
            "book_id": book_id, "movement_type": "PURCHASE_RECEIPT", "quantity": 20,
            "to_holder": {"type": "warehouse", "id": "central"},
        }, timeout=30)

        # Lider on-hand before
        my_before_resp = requests.get(f"{BASE_URL}/api/library/my-holdings", headers=_h(lider["token"]), timeout=30).json()["items"]
        lider_before = next((i["on_hand"] for i in my_before_resp if i["book"]["book_id"] == book_id), 0)

        # Lider creates request for 5
        rq = requests.post(f"{BASE_URL}/api/library/requests", headers=_h(lider["token"]), json={
            "book_id": book_id, "quantity": 5, "notes": "TEST request LBS1",
        }, timeout=30)
        assert rq.status_code == 201, rq.text
        request_id = rq.json()["request_id"]

        # Pastor sees pending
        lst = requests.get(f"{BASE_URL}/api/library/requests", headers=_h(pastor["token"]), timeout=30).json()["items"]
        assert any(r["request_id"] == request_id and r["status"] == "pending" for r in lst)

        # Approve partial 3
        res = requests.post(f"{BASE_URL}/api/library/requests/{request_id}/resolve",
                            headers=_h(pastor["token"]), json={"quantity_approved": 3, "notes": "TEST partial"}, timeout=30)
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "partial"

        # Lider on-hand increased by 3
        my_after = requests.get(f"{BASE_URL}/api/library/my-holdings", headers=_h(lider["token"]), timeout=30).json()["items"]
        lider_after = next(i["on_hand"] for i in my_after if i["book"]["book_id"] == book_id)
        assert lider_after == lider_before + 3


class TestReturnFlow:
    def test_return_from_lider_to_central(self, pastor, lider, lbs1_book):
        book_id = lbs1_book["book_id"]
        before = _inventory_row(pastor, book_id)
        my_before = requests.get(f"{BASE_URL}/api/library/my-holdings", headers=_h(lider["token"]), timeout=30).json()["items"]
        lider_before = next(i["on_hand"] for i in my_before if i["book"]["book_id"] == book_id)
        assert lider_before >= 1, "need stock to return"

        r = requests.post(f"{BASE_URL}/api/library/movements", headers=_h(lider["token"]), json={
            "book_id": book_id, "movement_type": "RETURN", "quantity": 1,
            "from_holder": {"type": "user", "id": lider["user_id"]},
            "to_holder": {"type": "warehouse", "id": "central"},
        }, timeout=30)
        assert r.status_code == 201, r.text

        after = _inventory_row(pastor, book_id)
        assert after["available_central"] == before["available_central"] + 1
        my_after = requests.get(f"{BASE_URL}/api/library/my-holdings", headers=_h(lider["token"]), timeout=30).json()["items"]
        lider_after = next((i["on_hand"] for i in my_after if i["book"]["book_id"] == book_id), 0)
        assert lider_after == lider_before - 1


class TestDamageLoss:
    def test_damage_writeoff(self, pastor, lbs1_book):
        book_id = lbs1_book["book_id"]
        before = _inventory_row(pastor, book_id)

        r = requests.post(f"{BASE_URL}/api/library/movements", headers=_h(pastor["token"]), json={
            "book_id": book_id, "movement_type": "DAMAGE", "quantity": 2,
            "from_holder": {"type": "warehouse", "id": "central"},
            "to_holder": {"type": "writeoff", "id": "damage"},
            "notes": "TEST damage",
        }, timeout=30)
        assert r.status_code == 201, r.text

        after = _inventory_row(pastor, book_id)
        assert after["available_central"] == before["available_central"] - 2

        movs = requests.get(f"{BASE_URL}/api/library/movements", headers=_h(pastor["token"]),
                            params={"book_id": book_id, "limit": 20}, timeout=30).json()["items"]
        assert any(m["movement_type"] == "DAMAGE" and m.get("to_holder", {}).get("type") == "writeoff" for m in movs)


class TestRBAC:
    def test_persona_forbidden_on_movements(self, persona_user, disc1_book):
        r = requests.post(f"{BASE_URL}/api/library/movements", headers=_h(persona_user["token"]), json={
            "book_id": disc1_book["book_id"], "movement_type": "PURCHASE_RECEIPT", "quantity": 1,
            "to_holder": {"type": "warehouse", "id": "central"},
        }, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"

    def test_persona_forbidden_on_dashboard(self, persona_user):
        r = requests.get(f"{BASE_URL}/api/library/dashboard", headers=_h(persona_user["token"]), timeout=30)
        assert r.status_code == 403

    def test_lider_cannot_purchase_receipt(self, lider, disc1_book):
        r = requests.post(f"{BASE_URL}/api/library/movements", headers=_h(lider["token"]), json={
            "book_id": disc1_book["book_id"], "movement_type": "PURCHASE_RECEIPT", "quantity": 5,
            "to_holder": {"type": "warehouse", "id": "central"},
        }, timeout=30)
        assert r.status_code == 403, r.text

    def test_lider_cannot_transfer_from_central(self, lider, disc1_book):
        r = requests.post(f"{BASE_URL}/api/library/movements", headers=_h(lider["token"]), json={
            "book_id": disc1_book["book_id"], "movement_type": "TRANSFER", "quantity": 1,
            "from_holder": {"type": "warehouse", "id": "central"},
            "to_holder": {"type": "user", "id": lider["user_id"]},
        }, timeout=30)
        assert r.status_code == 403, r.text

    def test_lider_cannot_move_from_other_user(self, lider, pastor, disc1_book):
        # from someone else's user_id
        r = requests.post(f"{BASE_URL}/api/library/movements", headers=_h(lider["token"]), json={
            "book_id": disc1_book["book_id"], "movement_type": "DELIVERY", "quantity": 1,
            "from_holder": {"type": "user", "id": pastor["user_id"]},
            "to_holder": {"type": "person", "id": TEST_PERSON_ID},
            "person_id": TEST_PERSON_ID,
        }, timeout=30)
        assert r.status_code == 403, r.text


class TestLibrarianGrant:
    def test_grant_and_revoke_librarian(self, pastor, persona_user):
        # Grant
        r = requests.post(f"{BASE_URL}/api/library/librarians", headers=_h(pastor["token"]),
                          json={"user_id": persona_user["user_id"]}, timeout=30)
        assert r.status_code == 201, r.text

        # Re-login to pick up new capabilities
        newlogin = _login(persona_user["email"])
        # Now inventory should be accessible
        inv = requests.get(f"{BASE_URL}/api/library/inventory", headers=_h(newlogin["token"]), timeout=30)
        assert inv.status_code == 200, f"granted librarian should access inventory: {inv.status_code} {inv.text}"

        # List librarians includes them
        lst = requests.get(f"{BASE_URL}/api/library/librarians", headers=_h(pastor["token"]), timeout=30).json()["items"]
        assert any(u["user_id"] == persona_user["user_id"] for u in lst)

        # Revoke
        rv = requests.delete(f"{BASE_URL}/api/library/librarians/{persona_user['user_id']}",
                             headers=_h(pastor["token"]), timeout=30)
        assert rv.status_code == 200

        # After revoke, re-login and confirm 403
        newlogin2 = _login(persona_user["email"])
        inv2 = requests.get(f"{BASE_URL}/api/library/inventory", headers=_h(newlogin2["token"]), timeout=30)
        assert inv2.status_code == 403, f"revoked user should be 403: {inv2.status_code}"
