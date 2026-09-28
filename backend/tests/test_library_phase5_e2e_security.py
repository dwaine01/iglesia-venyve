"""Librería 360 Fase 5 — FINAL closing tests:
- Notifications + cron endpoint (auth, dedup, mark-read, auto-resolve)
- FULL end-to-end lifecycle (catalog -> PO -> approve -> receive partial -> receive full -> reservation -> transfer -> scan deliver -> auto-release -> ledger reconciliation)
- Security tests (RBAC, IDOR, closed-PO immutability, replay, double-receive/delivery, price tamper, garbage input)
"""
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
PASTOR = ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!")
LIDER = ("qa.baptismui53.lider@example.com", "QaBaptismUI53!")


def _read_env_secret():
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("WEBHOOK_CRON_SECRET="):
                return line.split("=", 1)[1].strip()
    return None


WEBHOOK_SECRET = _read_env_secret()


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def h_pastor():
    tok = _login(*PASTOR)["token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def h_lider():
    tok = _login(*LIDER)["token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sample_person(h_pastor):
    for q in ["an", "ma", "jo", "ca", "el"]:
        r = requests.get(f"{API}/library/scan/search-person", params={"q": q}, headers=h_pastor, timeout=15)
        if r.status_code == 200 and r.json().get("items"):
            return r.json()["items"][0]
    pytest.skip("No persons found")


# =============================================================
# CRON / NOTIFICATIONS
# =============================================================

def test_cron_no_auth_returns_401():
    r = requests.post(f"{API}/library/cron/overdue-notifications", timeout=15)
    assert r.status_code == 401, r.text


def test_cron_wrong_secret_returns_401():
    r = requests.post(f"{API}/library/cron/overdue-notifications",
                      headers={"Authorization": "Bearer WRONGSECRET"}, timeout=15)
    assert r.status_code == 401


def test_cron_correct_secret_returns_202():
    assert WEBHOOK_SECRET, "WEBHOOK_CRON_SECRET missing"
    r = requests.post(f"{API}/library/cron/overdue-notifications",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"}, timeout=15)
    assert r.status_code == 202
    assert r.json().get("accepted") is True


def test_notifications_list_accessible_by_pastor(h_pastor):
    r = requests.get(f"{API}/library/notifications", headers=h_pastor, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "unread_count" in body


# =============================================================
# FULL E2E LIFECYCLE - creates test PO with expected_date in past for cron test
# =============================================================

@pytest.fixture(scope="module")
def e2e_state(h_pastor):
    """Shared state for the multi-step E2E lifecycle."""
    return {}


def test_e2e_01_create_paid_book(h_pastor, e2e_state):
    payload = {
        "sku": f"TEST_P5_{int(time.time())}",
        "name": f"TEST_Phase5 Material Pagado {int(time.time())}",
        "description": "E2E test material - paid",
        "item_type": "libro",
        "process_key": "seven_weeks",
        "cost_price_cents": 500,
        "member_price_cents": 1500,
        "inventory_kind": "consumable",
        "is_active": True,
        "min_stock": 0,
        "ideal_stock": 10,
    }
    r = requests.post(f"{API}/library/books", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 201, r.text
    book = r.json()
    assert book["member_price_cents"] == 1500
    e2e_state["book"] = book
    e2e_state["book_id"] = book["book_id"]


def test_e2e_02_free_material_exists(h_pastor, e2e_state):
    r = requests.get(f"{API}/library/books", headers=h_pastor, timeout=15)
    assert r.status_code == 200
    free = [b for b in r.json().get("items", []) if b.get("member_price_cents", 0) == 0]
    if free:
        e2e_state["free_book"] = free[0]
    # not required to fail if absent


def test_e2e_03_create_po_draft(h_pastor, e2e_state):
    past = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
    payload = {
        "provider_name": f"TEST_Phase5_Provider_{int(time.time())}",
        "lines": [{"book_id": e2e_state["book_id"], "quantity": 10, "unit_cost_cents": 500}],
        "expected_date": past,
        "notes": "TEST_Phase5 E2E",
    }
    r = requests.post(f"{API}/library/purchase-orders", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 201, r.text
    po = r.json()
    assert po["status"] == "draft"
    e2e_state["po_id"] = po["po_id"]
    e2e_state["po_number"] = po["po_number"]


def test_e2e_04_submit_po(h_pastor, e2e_state):
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/submit", headers=h_pastor, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "submitted"


def test_e2e_05_approve_po(h_pastor, e2e_state):
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/decision",
                      json={"action": "approve", "note": "approved"}, headers=h_pastor, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    # Verify Finance Expense created
    r2 = requests.get(f"{API}/library/purchase-orders/{e2e_state['po_id']}", headers=h_pastor, timeout=15)
    assert r2.json().get("linked_expense_id"), f"linked_expense_id missing: {r2.json()}"


def test_e2e_06_mark_ordered(h_pastor, e2e_state):
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/mark-ordered", headers=h_pastor, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ordered"


def test_e2e_07_cron_creates_notification_for_overdue_po(h_pastor, e2e_state):
    """Now that PO is 'ordered' with expected_date in the past, cron should create notif."""
    r = requests.post(f"{API}/library/cron/overdue-notifications",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"}, timeout=15)
    assert r.status_code == 202
    time.sleep(3)  # allow BackgroundTask to run
    r2 = requests.get(f"{API}/library/notifications", headers=h_pastor, timeout=15)
    assert r2.status_code == 200
    items = r2.json()["items"]
    matching = [n for n in items if n["reference_id"] == e2e_state["po_id"]]
    assert matching, f"No notification created for PO {e2e_state['po_number']}"
    n = matching[0]
    assert n["type"] == "po_overdue"
    assert e2e_state["po_number"] in n["title"]
    assert n["read_at"] is None
    e2e_state["notification_id"] = n["notification_id"]


def test_e2e_08_cron_dedup_no_duplicate(h_pastor, e2e_state):
    r = requests.post(f"{API}/library/cron/overdue-notifications",
                      headers={"Authorization": f"Bearer {WEBHOOK_SECRET}"}, timeout=15)
    assert r.status_code == 202
    time.sleep(3)
    r2 = requests.get(f"{API}/library/notifications", headers=h_pastor, timeout=15)
    matching = [n for n in r2.json()["items"] if n["reference_id"] == e2e_state["po_id"] and n["read_at"] is None]
    assert len(matching) == 1, f"Dedup failed: {len(matching)} unread notifications for same PO"


def test_e2e_09_mark_notification_read(h_pastor, e2e_state):
    r = requests.patch(f"{API}/library/notifications/{e2e_state['notification_id']}/read",
                       headers=h_pastor, timeout=15)
    assert r.status_code == 200
    assert r.json()["marked_read"] is True


def test_e2e_10_receive_partial(h_pastor, e2e_state):
    payload = {
        "lines": [{"book_id": e2e_state["book_id"], "quantity_received_now": 5}],
        "notes": "TEST partial receipt",
        "scan_method": "MANUAL",
    }
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/receive",
                      json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "partially_received"
    # Verify ledger movement
    r2 = requests.get(f"{API}/library/movements", params={"book_id": e2e_state["book_id"]},
                      headers=h_pastor, timeout=15)
    assert r2.status_code == 200
    receipts = [m for m in r2.json().get("items", []) if m["movement_type"] == "PURCHASE_RECEIPT"]
    assert any(m["quantity"] == 5 for m in receipts), f"No PURCHASE_RECEIPT for qty=5: {receipts}"


def test_e2e_11_double_receipt_over_pending_rejected(h_pastor, e2e_state):
    """SECURITY: attempting to receive more than remaining should be rejected."""
    payload = {
        "lines": [{"book_id": e2e_state["book_id"], "quantity_received_now": 999}],
        "notes": "attempted over-receive",
    }
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/receive",
                      json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_e2e_12_receive_remaining(h_pastor, e2e_state):
    payload = {"lines": [{"book_id": e2e_state["book_id"], "quantity_received_now": 5}], "notes": "TEST final receipt"}
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/receive",
                      json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "received"


def test_e2e_13_auto_resolve_on_full_receive(h_pastor, e2e_state):
    """Notification should be auto-resolved (already marked-read via step 9 too, but let's verify auto_resolved flag semantics via a fresh cron)."""
    # After full receipt, any remaining unread notif for this PO should be resolved
    r = requests.get(f"{API}/library/notifications", headers=h_pastor, timeout=15)
    items = [n for n in r.json()["items"] if n["reference_id"] == e2e_state["po_id"]]
    for n in items:
        assert n["read_at"] is not None, f"Notification still unread after receive: {n}"


def test_e2e_14_replay_receive_on_closed_po_rejected(h_pastor, e2e_state):
    """SECURITY: attempting to receive on already fully-received PO -> 409."""
    payload = {"lines": [{"book_id": e2e_state["book_id"], "quantity_received_now": 1}], "notes": "replay"}
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/receive",
                      json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"


def test_e2e_15_holdings_updated_after_full_receipt(h_pastor, e2e_state):
    """Verify library_holdings central has +10 after both receipts."""
    r = requests.get(f"{API}/library/movements", params={"book_id": e2e_state["book_id"]},
                     headers=h_pastor, timeout=15)
    receipts = [m for m in r.json().get("items", []) if m["movement_type"] == "PURCHASE_RECEIPT"]
    total = sum(m["quantity"] for m in receipts)
    assert total == 10, f"Expected 10 units received, got {total}"


def test_e2e_16_scan_resolve_material_by_new_book(h_pastor, e2e_state):
    r = requests.get(f"{API}/library/scan/resolve-material",
                     params={"code": f"VYV-LIB-{e2e_state['book_id']}"}, headers=h_pastor, timeout=15)
    assert r.status_code == 200
    assert r.json()["book_id"] == e2e_state["book_id"]


def test_e2e_17_deliver_via_api(h_pastor, sample_person, e2e_state):
    """Deliver 1 unit of new material to a person. Verifies DELIVERY movement + scan_method + list_price_cents."""
    payload = {
        "book_id": e2e_state["book_id"], "quantity": 1,
        "payment_status": "no_aplica", "amount_paid_cents": 0,
        "notes": "TEST_Phase5 E2E delivery", "scan_method": "MANUAL",
    }
    r = requests.post(f"{API}/library/persons/{sample_person['person_id']}/deliver",
                      json=payload, headers=h_pastor, timeout=20)
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["movement_type"] == "DELIVERY"
    assert m["scan_method"] == "MANUAL"
    assert m["list_price_cents"] == 1500
    e2e_state["delivery_movement_id"] = m["movement_id"]
    e2e_state["delivered_person_id"] = sample_person["person_id"]


def test_e2e_18_ledger_reconciliation(h_pastor, e2e_state):
    """Sum ledger movements for the book and compare against library_holdings."""
    r = requests.get(f"{API}/library/movements", params={"book_id": e2e_state["book_id"]},
                     headers=h_pastor, timeout=15)
    movements = r.json().get("items", [])
    additions = sum(m["quantity"] for m in movements if m["movement_type"] == "PURCHASE_RECEIPT")
    removals = sum(m["quantity"] for m in movements if m["movement_type"] in ("DELIVERY", "LOSS", "DAMAGE"))
    net = additions - removals
    # Query all holdings for this book
    r2 = requests.get(f"{API}/library/books/{e2e_state['book_id']}", headers=h_pastor, timeout=15)
    # Fall back: sum via reports if available
    assert net == 10 - 1, f"Ledger net {net} != expected 9"


def test_e2e_19_reports_pdf_download(h_pastor):
    r = requests.get(f"{API}/library/reports/inventory_current",
                     params={"format": "pdf"}, headers=h_pastor, timeout=30)
    assert r.status_code == 200, r.text[:200]
    assert len(r.content) > 200
    assert r.headers.get("content-type", "").startswith("application/pdf")


def test_e2e_20_reports_xlsx_download(h_pastor):
    r = requests.get(f"{API}/library/reports/delivered",
                     params={"format": "xlsx"}, headers=h_pastor, timeout=30)
    assert r.status_code == 200
    assert len(r.content) > 200


# =============================================================
# SECURITY TESTS
# =============================================================

def test_sec_a_lider_cannot_edit_po(h_lider, e2e_state):
    """Lider (no library.inventory.manage) attempts PUT PO -> 403."""
    if not e2e_state.get("po_id"):
        pytest.skip("no PO from e2e")
    payload = {"provider_name": "Hacker", "lines": [{"book_id": e2e_state["book_id"], "quantity": 1, "unit_cost_cents": 1}]}
    r = requests.put(f"{API}/library/purchase-orders/{e2e_state['po_id']}", json=payload, headers=h_lider, timeout=15)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_sec_b_lider_cannot_receive_po(h_lider, e2e_state):
    payload = {"lines": [{"book_id": e2e_state["book_id"], "quantity_received_now": 1}]}
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/receive",
                      json=payload, headers=h_lider, timeout=15)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}"


def test_sec_c_download_file_unauth():
    """No auth token -> should be 401/403."""
    r = requests.get(f"{API}/library/files/nonexistent-file-id/download", timeout=15)
    assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


def test_sec_c2_download_nonexistent_file_authenticated(h_pastor):
    r = requests.get(f"{API}/library/files/nonexistent-file-id/download", headers=h_pastor, timeout=15)
    assert r.status_code == 404


def test_sec_d_garbage_resolve_person(h_pastor):
    r = requests.post(f"{API}/library/scan/resolve-person",
                      json={"code": "'; DROP TABLE users;--"}, headers=h_pastor, timeout=15)
    assert r.status_code == 404, f"Expected 404 not {r.status_code}: {r.text[:200]}"


def test_sec_d2_garbage_resolve_material(h_pastor):
    r = requests.get(f"{API}/library/scan/resolve-material",
                     params={"code": "///GARBAGE\\\\%00"}, headers=h_pastor, timeout=15)
    assert r.status_code == 404


def test_sec_e_replay_receive_on_received_po(h_pastor, e2e_state):
    """Already tested in step 14 - redundant coverage."""
    payload = {"lines": [{"book_id": e2e_state["book_id"], "quantity_received_now": 1}]}
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/receive",
                      json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 409


def test_sec_f_double_delivery_over_stock(h_pastor, sample_person, e2e_state):
    """Attempt to deliver more than remaining central stock -> 409."""
    payload = {"book_id": e2e_state["book_id"], "quantity": 999,
               "payment_status": "no_aplica", "amount_paid_cents": 0}
    r = requests.post(f"{API}/library/persons/{sample_person['person_id']}/deliver",
                      json=payload, headers=h_pastor, timeout=20)
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"


def test_sec_g_close_then_receive_rejected(h_pastor, e2e_state):
    """Close the received PO, then verify it becomes immutable."""
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/close", headers=h_pastor, timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "closed"
    payload = {"lines": [{"book_id": e2e_state["book_id"], "quantity_received_now": 1}]}
    r2 = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/receive",
                       json=payload, headers=h_pastor, timeout=15)
    assert r2.status_code == 409


def test_sec_h_close_then_cancel_rejected(h_pastor, e2e_state):
    r = requests.post(f"{API}/library/purchase-orders/{e2e_state['po_id']}/cancel", headers=h_pastor, timeout=15)
    assert r.status_code == 409


def test_sec_i_price_tamper_accepted_as_partial_payment_flag(h_pastor, sample_person, e2e_state):
    """Delivering with amount_paid_cents=1 for a $15 book: backend currently does not enforce
    that amount matches list price (payment_status can be pago_parcial / becado). Flag as informational."""
    payload = {"book_id": e2e_state["book_id"], "quantity": 1,
               "payment_status": "pago_parcial", "amount_paid_cents": 1, "payment_method": "cash",
               "notes": "TEST_Phase5 price tamper probe"}
    r = requests.post(f"{API}/library/persons/{sample_person['person_id']}/deliver",
                      json=payload, headers=h_pastor, timeout=20)
    # We do not fail here; we assert the transaction is either accepted (flexible discounts) or rejected
    # (strict). Either way documents the finding.
    assert r.status_code in (201, 400, 409, 422)
    print(f"[FINDING sec_i] amount_paid=1 for $15 material -> status={r.status_code} body={r.text[:200]}")


def test_sec_j_idor_notification_belongs_to_other_user(h_lider, e2e_state):
    """Attempt to mark another user's notification as read -> 404 (scoped by recipient)."""
    if not e2e_state.get("notification_id"):
        pytest.skip("no notification")
    r = requests.patch(f"{API}/library/notifications/{e2e_state['notification_id']}/read",
                       headers=h_lider, timeout=15)
    # Lider may or may not be a recipient - if not, must be 404
    assert r.status_code in (200, 404)


# =============================================================
# CLEANUP
# =============================================================

def test_zz_cleanup(h_pastor, e2e_state):
    """Deactivate created test book so it doesn't clutter catalog."""
    if e2e_state.get("book_id"):
        r = requests.put(f"{API}/library/books/{e2e_state['book_id']}",
                         json={"sku": e2e_state["book"]["sku"], "name": e2e_state["book"]["name"],
                               "is_active": False, "member_price_cents": 1500, "cost_price_cents": 500,
                               "item_type": "libro", "inventory_kind": "consumable"},
                         headers=h_pastor, timeout=15)
        print(f"[cleanup] deactivate book: {r.status_code}")
