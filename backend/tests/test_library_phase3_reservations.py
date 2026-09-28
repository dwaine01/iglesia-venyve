"""Librería 360 Fase 3 — Reserva Automática, PO desde déficit, alertas overdue, RBAC."""
import os
import time
import pytest
import requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PASTOR = ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!")
LIDER = ("qa.baptismui53.lider@example.com", "QaBaptismUI53!")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
mongo = MongoClient(MONGO_URL)[DB_NAME]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def pastor():
    return _login(*PASTOR)


@pytest.fixture(scope="module")
def lider():
    return _login(*LIDER)


@pytest.fixture(scope="module")
def h_pastor(pastor):
    return {"Authorization": f"Bearer {pastor['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def h_lider(lider):
    return {"Authorization": f"Bearer {lider['token']}", "Content-Type": "application/json"}


# ==================== 1. Basic deficit endpoint & sync (manager) ====================

def test_deficit_report_pastor_ok(h_pastor):
    r = requests.get(f"{API}/library/reservations/deficit-report", headers=h_pastor, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_sync_pastor_ok(h_pastor):
    r = requests.post(f"{API}/library/reservations/sync", headers=h_pastor, timeout=30)
    assert r.status_code == 200, r.text
    assert "created" in r.json() and "released" in r.json()


# ==================== 2. RBAC negative — lider ====================

def test_lider_rbac_deficit_report_403(h_lider):
    r = requests.get(f"{API}/library/reservations/deficit-report", headers=h_lider, timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"


def test_lider_rbac_sync_403(h_lider):
    r = requests.post(f"{API}/library/reservations/sync", headers=h_lider, timeout=15)
    assert r.status_code == 403, r.text


# ==================== 3. Core flow: enrollment -> reservation -> deficit -> PO -> cancel-> release ==

TEST_CYCLE_NAME = "TEST_Fase3_Ciclo"


@pytest.fixture(scope="module")
def seven_weeks_books():
    books = list(mongo.library_books.find({"is_active": True, "process_key": "seven_weeks"}, {"_id": 0}))
    assert books, "No hay libros activos con process_key='seven_weeks' — no se puede probar"
    return books


@pytest.fixture(scope="module")
def test_person_id():
    # Use BautismoUI person as enrollee
    p = mongo.persons.find_one({"nombre": "BautismoUI"})
    assert p, "BautismoUI person missing"
    return str(p["_id"])


@pytest.fixture(scope="module")
def responsible_person_id():
    # Need a person with an active user (rol pastor/lider) — the query in backend is strict about 'pastor'/'lider'
    u = mongo.users.find_one({"rol": {"$in": ["pastor", "lider"]}, "is_active": {"$ne": False}, "person_id": {"$exists": True}})
    assert u, "No pastor/lider user available"
    return u["person_id"]


@pytest.fixture(scope="module")
def cycle(h_pastor):
    # Create a test cycle for seven_weeks
    start = datetime.utcnow().date().isoformat()
    end = (datetime.utcnow() + timedelta(days=60)).date().isoformat()
    payload = {"name": TEST_CYCLE_NAME, "start_date": start, "end_date": end,
               "capacity": 30, "status": "active"}
    r = requests.post(f"{API}/processes/cycles", headers=h_pastor, json=payload, timeout=15)
    assert r.status_code == 201, r.text
    c = r.json()
    yield c
    # Cleanup
    mongo.process_cycles.delete_one({"cycle_id": c["cycle_id"]})


enrollment_holder = {}


def test_baseline_deficit_snapshot(h_pastor, seven_weeks_books):
    r = requests.get(f"{API}/library/reservations/deficit-report", headers=h_pastor, timeout=30)
    assert r.status_code == 200
    baseline = {row["book_id"]: row for row in r.json()["items"]}
    enrollment_holder["baseline"] = baseline
    # Should have entries for every seven_weeks book
    for b in seven_weeks_books:
        assert b["book_id"] in baseline, f"Missing baseline for {b['name']}"


def test_create_enrollment_triggers_reservations(h_pastor, cycle, test_person_id, seven_weeks_books):
    # Insert enrollment directly via mongo (review request explicitly allows this).
    # Rationale: pastora rol has scope restrictions preventing API path in this seed;
    # the reservation engine reads process_enrollments directly regardless of provenance.
    from uuid import uuid4 as _uuid4
    eid = str(_uuid4())
    doc = {
        "_id": eid, "enrollment_id": eid, "process_key": "seven_weeks",
        "person_id": test_person_id, "cycle_id": cycle["cycle_id"],
        "status": "active", "current_stage_key": "start",
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        "created_by_user_id": "test-suite", "source": "test",
    }
    mongo.process_enrollments.insert_one(doc)
    enrollment_holder["enrollment_id"] = eid
    enrollment_holder["created_here"] = True

    # Trigger sync via deficit-report
    time.sleep(0.5)
    r2 = requests.get(f"{API}/library/reservations/deficit-report", headers=h_pastor, timeout=30)
    assert r2.status_code == 200
    after = {row["book_id"]: row for row in r2.json()["items"]}
    enrollment_holder["after"] = after

    baseline = enrollment_holder["baseline"]
    increments = 0
    for b in seven_weeks_books:
        bid = b["book_id"]
        if after[bid]["enrolled_count"] > baseline[bid]["enrolled_count"]:
            increments += 1
    assert increments == len(seven_weeks_books), f"enrolled_count did not increase for all books; {increments}/{len(seven_weeks_books)}"


def test_reservations_created_in_db(seven_weeks_books):
    eid = enrollment_holder["enrollment_id"]
    reservations = list(mongo.library_reservations.find({"enrollment_id": eid, "status": "active"}, {"_id": 0}))
    assert len(reservations) == len(seven_weeks_books), \
        f"Expected {len(seven_weeks_books)} active reservations, got {len(reservations)}"


def test_reservation_movements_and_holdings(seven_weeks_books):
    eid = enrollment_holder["enrollment_id"]
    reservations = list(mongo.library_reservations.find({"enrollment_id": eid, "status": "active"}, {"_id": 0}))
    for r in reservations:
        # Movement should exist
        mov = mongo.library_movements.find_one({"movement_id": r["movement_id"]})
        assert mov, f"Missing RESERVATION movement for {r['book_id']}"
        assert mov["movement_type"] == "RESERVATION"
        assert mov["quantity"] == 1
    # Holdings reserved_qty should be > 0 for those books
    for r in reservations:
        h = mongo.library_holdings.find_one({"book_id": r["book_id"], "holder_type": "warehouse", "holder_id": "central"})
        assert h and h.get("reserved_qty", 0) >= 1, f"reserved_qty not incremented for {r['book_id']}"


# ==================== 4. Create PO from deficit ====================

po_holder = {}


def test_create_po_from_deficit_when_deficit_exists(h_pastor):
    after = enrollment_holder["after"]
    deficit_rows = [r for r in after.values() if r["deficit"] > 0]
    if not deficit_rows:
        # Force a deficit by picking a book & artificially setting central stock to 0 momentarily is risky.
        # Instead, verify the endpoint rejects when no deficit exists (422).
        first_book = next(iter(after.values()))
        r = requests.post(f"{API}/library/purchase-orders/from-deficit",
                          headers=h_pastor,
                          json={"book_id": first_book["book_id"]}, timeout=15)
        # No deficit -> 422 (see backend logic)
        assert r.status_code == 422, f"expected 422 no deficit, got {r.status_code} {r.text}"
        pytest.skip("No deficit rows > 0 in this environment — PO-from-deficit creation path can't be positively asserted.")

    target = max(deficit_rows, key=lambda x: x["deficit"])
    r = requests.post(f"{API}/library/purchase-orders/from-deficit",
                      headers=h_pastor,
                      json={"book_id": target["book_id"]}, timeout=20)
    assert r.status_code == 201, r.text
    po = r.json()
    assert po["status"] == "draft", f"PO status must be draft, got {po['status']}"
    assert len(po["lines"]) == 1
    assert po["lines"][0]["book_id"] == target["book_id"]
    assert po["lines"][0]["quantity_ordered"] == target["deficit"]
    assert "Reserva Automática" in po["notes"]
    po_holder["po_id"] = po["po_id"]


# ==================== 5. Cancel enrollment -> release reservations ====================

def test_cancel_enrollment_releases_reservations(h_pastor, seven_weeks_books):
    if not enrollment_holder.get("created_here"):
        pytest.skip("Enrollment pre-existed, skipping cancellation to avoid mutating real data")
    eid = enrollment_holder["enrollment_id"]
    # Cancel directly via mongo (created directly earlier)
    mongo.process_enrollments.update_one({"enrollment_id": eid}, {"$set": {"status": "cancelled"}})

    # Trigger sync
    r2 = requests.post(f"{API}/library/reservations/sync", headers=h_pastor, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["released"] >= len(seven_weeks_books)

    # Verify all reservations for this enrollment are released
    active_left = mongo.library_reservations.count_documents({"enrollment_id": eid, "status": "active"})
    assert active_left == 0, f"Expected 0 active reservations after cancel, got {active_left}"

    released = list(mongo.library_reservations.find({"enrollment_id": eid, "status": "released"}, {"_id": 0}))
    for rr in released:
        assert rr.get("release_movement_id"), "Missing release_movement_id on released reservation"
        mov = mongo.library_movements.find_one({"movement_id": rr["release_movement_id"]})
        assert mov and mov["movement_type"] == "RESERVATION_RELEASE"


# ==================== 6. Overdue PO alerts ====================

overdue_holder = {}


def test_create_and_mark_po_overdue(h_pastor):
    # Create a PO
    book = mongo.library_books.find_one({"is_active": True}, {"_id": 0})
    assert book
    payload = {"provider_name": "TEST_Fase3_Provider",
               "lines": [{"book_id": book["book_id"], "quantity": 2, "unit_cost_cents": 1000}],
               "notes": "TEST_Fase3_Overdue"}
    r = requests.post(f"{API}/library/purchase-orders", headers=h_pastor, json=payload, timeout=15)
    assert r.status_code == 201, r.text
    po = r.json()
    po_id = po["po_id"]
    overdue_holder["po_id"] = po_id
    overdue_holder["book_id"] = book["book_id"]

    # submit -> approve -> mark ordered
    assert requests.post(f"{API}/library/purchase-orders/{po_id}/submit", headers=h_pastor, timeout=15).status_code == 200
    assert requests.post(f"{API}/library/purchase-orders/{po_id}/decision",
                        headers=h_pastor, json={"action": "approve", "note": "ok"}, timeout=15).status_code == 200
    assert requests.post(f"{API}/library/purchase-orders/{po_id}/mark-ordered", headers=h_pastor, timeout=15).status_code == 200

    # Force expected_date to 5 days ago via mongo
    past = datetime.now(timezone.utc) - timedelta(days=5)
    mongo.library_purchase_orders.update_one({"po_id": po_id}, {"$set": {"expected_date": past}})

    # Verify list shows overdue
    r2 = requests.get(f"{API}/library/purchase-orders", headers=h_pastor, timeout=15)
    assert r2.status_code == 200
    the_po = next((p for p in r2.json()["items"] if p["po_id"] == po_id), None)
    assert the_po, "PO not returned"
    assert the_po["is_overdue"] is True, the_po
    assert the_po["days_overdue"] >= 5
    assert the_po["pending_quantity"] == 2


def test_overdue_persists_after_partial_receive(h_pastor):
    po_id = overdue_holder["po_id"]
    book_id = overdue_holder["book_id"]
    r = requests.post(f"{API}/library/purchase-orders/{po_id}/receive",
                      headers=h_pastor,
                      json={"lines": [{"book_id": book_id, "quantity_received_now": 1}], "notes": "parcial test"},
                      timeout=20)
    assert r.status_code == 200, r.text
    r2 = requests.get(f"{API}/library/purchase-orders", headers=h_pastor, timeout=15)
    the_po = next((p for p in r2.json()["items"] if p["po_id"] == po_id), None)
    assert the_po["status"] == "partially_received"
    assert the_po["is_overdue"] is True, "Overdue must persist while pending>0"
    assert the_po["pending_quantity"] == 1


def test_dashboard_overdue_alert(h_pastor):
    r = requests.get(f"{API}/library/dashboard", headers=h_pastor, timeout=15)
    assert r.status_code == 200
    d = r.json()
    # According to review request, dashboard should include alerts.overdue_purchase_orders
    alerts = d.get("alerts", {})
    assert "overdue_purchase_orders" in alerts, f"alerts.overdue_purchase_orders missing: {alerts}"
    assert alerts["overdue_purchase_orders"] >= 1


# ==================== 7. Regression: PUT edit draft PO (route missing decorator?) ====================

def test_put_edit_draft_po_endpoint_available(h_pastor):
    """CRITICAL REGRESSION: verify PUT /api/library/purchase-orders/{po_id} still works.
    In library_purchase_orders.py the update_purchase_order function appears to be missing
    its @router.put decorator (line 271)."""
    book = mongo.library_books.find_one({"is_active": True}, {"_id": 0})
    payload = {"provider_name": "TEST_Fase3_Edit",
               "lines": [{"book_id": book["book_id"], "quantity": 1, "unit_cost_cents": 500}],
               "notes": "TEST_Fase3_EditOriginal"}
    c = requests.post(f"{API}/library/purchase-orders", headers=h_pastor, json=payload, timeout=15)
    assert c.status_code == 201
    po_id = c.json()["po_id"]

    # Try to PUT edit
    edit_payload = {"provider_name": "TEST_Fase3_EditUpdated",
                    "lines": [{"book_id": book["book_id"], "quantity": 3, "unit_cost_cents": 500}],
                    "notes": "edited"}
    r = requests.put(f"{API}/library/purchase-orders/{po_id}", headers=h_pastor, json=edit_payload, timeout=15)
    # Cleanup best-effort
    requests.post(f"{API}/library/purchase-orders/{po_id}/cancel", headers=h_pastor, timeout=15)
    assert r.status_code == 200, f"PUT edit draft PO broken (missing @router.put on update_purchase_order): {r.status_code} {r.text}"


# ==================== 8. Cleanup ====================

def test_cleanup(h_pastor):
    # Cancel test PO if still exists
    po_id = overdue_holder.get("po_id")
    if po_id:
        po = mongo.library_purchase_orders.find_one({"po_id": po_id})
        if po and po["status"] in {"draft", "submitted", "approved", "changes_requested"}:
            requests.post(f"{API}/library/purchase-orders/{po_id}/cancel", headers=h_pastor, timeout=10)
    # Delete test-created enrollment if we created it (and it's cancelled already)
    eid = enrollment_holder.get("enrollment_id")
    if eid and enrollment_holder.get("created_here"):
        # Release any lingering reservations (should be released already)
        mongo.process_enrollments.delete_one({"enrollment_id": eid})
    # Test provider vendor cleanup
    mongo.finance_vendors.delete_many({"name": {"$regex": "^TEST_Fase3_"}})
