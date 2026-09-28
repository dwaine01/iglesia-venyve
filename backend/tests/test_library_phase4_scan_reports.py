"""Librería 360 Fase 4 — Scan flow (resolve material/person, snapshot),
Reports Center (17 reports, PDF/Excel export), auto-release of reservations on
delivery, PO quick-receive scan, RBAC checks.
"""
import os
import io
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
PASTOR = ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!")
LIDER = ("qa.baptismui53.lider@example.com", "QaBaptismUI53!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
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
def sample_book(h_pastor):
    r = requests.get(f"{API}/library/books", headers=h_pastor, timeout=15)
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    if not items:
        pytest.skip("No books in catalog to test scan flow")
    return items[0]


@pytest.fixture(scope="module")
def sample_person(h_pastor):
    # Use library scan search-person to find any person
    for q in ["an", "ma", "jo", "ca", "el"]:
        r = requests.get(f"{API}/library/scan/search-person",
                         params={"q": q}, headers=h_pastor, timeout=15)
        if r.status_code == 200 and r.json().get("items"):
            item = r.json()["items"][0]
            return {"person_id": item["person_id"], "display_name": item["display_name"]}
    pytest.skip("No persons available via search-person")


# ==================== SCAN: resolve-material ====================

def test_resolve_material_by_book_id(h_pastor, sample_book):
    r = requests.get(f"{API}/library/scan/resolve-material",
                     params={"code": sample_book["book_id"]}, headers=h_pastor, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["book_id"] == sample_book["book_id"]
    assert "name" in data
    assert "available_central" in data


def test_resolve_material_by_sku(h_pastor, sample_book):
    if not sample_book.get("sku"):
        pytest.skip("Sample book has no SKU")
    r = requests.get(f"{API}/library/scan/resolve-material",
                     params={"code": sample_book["sku"]}, headers=h_pastor, timeout=15)
    assert r.status_code == 200
    assert r.json()["book_id"] == sample_book["book_id"]


def test_resolve_material_not_found(h_pastor):
    r = requests.get(f"{API}/library/scan/resolve-material",
                     params={"code": "NON_EXISTENT_BOOK_XYZ"}, headers=h_pastor, timeout=15)
    assert r.status_code == 404


# ==================== SCAN: resolve-person ====================

def test_resolve_person_by_raw_id(h_pastor, sample_person):
    pid = sample_person.get("person_id") or sample_person.get("_id")
    r = requests.post(f"{API}/library/scan/resolve-person",
                      json={"code": pid}, headers=h_pastor, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["person_id"] == pid
    assert "display_name" in data


def test_resolve_person_not_found(h_pastor):
    r = requests.post(f"{API}/library/scan/resolve-person",
                      json={"code": "no_such_person_xyz"}, headers=h_pastor, timeout=15)
    assert r.status_code == 404


def test_search_person(h_pastor):
    r = requests.get(f"{API}/library/scan/search-person",
                     params={"q": "a"}, headers=h_pastor, timeout=15)
    # 'a' is >=2? Nope, minimum 2 chars. Try 'an'
    r = requests.get(f"{API}/library/scan/search-person",
                     params={"q": "an"}, headers=h_pastor, timeout=15)
    assert r.status_code == 200
    assert "items" in r.json()


def test_person_library_snapshot(h_pastor, sample_person):
    pid = sample_person.get("person_id") or sample_person.get("_id")
    r = requests.get(f"{API}/library/scan/persons/{pid}/library-snapshot",
                     headers=h_pastor, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["person_id"] == pid
    assert "materials" in data
    assert "pending_payments" in data


# ==================== REPORTS: catalog ====================

def test_reports_catalog_pastor(h_pastor):
    r = requests.get(f"{API}/library/reports/catalog", headers=h_pastor, timeout=15)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 17, f"Expected 17 reports, got {len(items)}"
    keys = {i["key"] for i in items}
    for k in ["inventory_current", "delivered", "reserved", "purchase_orders",
              "overdue_orders", "movement_history", "person_ledger", "library_income"]:
        assert k in keys, f"Missing report key {k}"


def test_reports_catalog_lider_allowed(h_lider):
    # lider has LIBRARY_DELIVER -> should see catalog
    r = requests.get(f"{API}/library/reports/catalog", headers=h_lider, timeout=15)
    assert r.status_code == 200


# ==================== REPORTS: JSON runs (5 different types) ====================

@pytest.mark.parametrize("report_key", [
    "inventory_current", "delivered", "purchase_orders",
    "overdue_orders", "movement_history",
])
def test_report_json_run(h_pastor, report_key):
    r = requests.get(f"{API}/library/reports/{report_key}", headers=h_pastor, timeout=30)
    assert r.status_code == 200, f"{report_key} -> {r.status_code} {r.text}"
    data = r.json()
    assert "columns" in data and "rows" in data
    assert isinstance(data["columns"], list) and len(data["columns"]) > 0


def test_report_inventory_current_filter_by_book(h_pastor, sample_book):
    r = requests.get(f"{API}/library/reports/inventory_current",
                     params={"book_id": sample_book["book_id"]},
                     headers=h_pastor, timeout=15)
    assert r.status_code == 200
    rows = r.json()["rows"]
    # Filter should narrow to just this book (may be 0 or 1)
    assert len(rows) <= 1


def test_report_date_filter_narrows(h_pastor):
    # Future-dated range → no movements
    r = requests.get(f"{API}/library/reports/delivered",
                     params={"date_from": "2099-01-01", "date_to": "2099-12-31"},
                     headers=h_pastor, timeout=15)
    assert r.status_code == 200
    assert r.json()["rows"] == []


# ==================== REPORTS: export PDF / XLSX ====================

def test_export_pdf(h_pastor):
    r = requests.get(f"{API}/library/reports/inventory_current",
                     params={"format": "pdf"}, headers=h_pastor, timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 500
    assert r.content[:4] == b"%PDF"


def test_export_xlsx(h_pastor):
    r = requests.get(f"{API}/library/reports/purchase_orders",
                     params={"format": "xlsx"}, headers=h_pastor, timeout=30)
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers.get("content-type", "")
    assert len(r.content) > 500
    # xlsx = zip → starts with PK
    assert r.content[:2] == b"PK"


# ==================== REPORTS: person_ledger ====================

def test_person_ledger_requires_person(h_pastor):
    r = requests.get(f"{API}/library/reports/person_ledger", headers=h_pastor, timeout=15)
    assert r.status_code == 422


def test_person_ledger_runs(h_pastor, sample_person):
    pid = sample_person.get("person_id") or sample_person.get("_id")
    r = requests.get(f"{API}/library/reports/person_ledger",
                     params={"person_id": pid}, headers=h_pastor, timeout=15)
    assert r.status_code == 200
    data = r.json()
    # Verify RESERVATION types are excluded (per spec)
    for row in data["rows"]:
        # Estado column index 7 by report definition
        assert row[7] not in ("RESERVATION", "RESERVATION_RELEASE")


def test_person_ledger_lider_can_access(h_lider, sample_person):
    pid = sample_person.get("person_id") or sample_person.get("_id")
    r = requests.get(f"{API}/library/reports/person_ledger",
                     params={"person_id": pid}, headers=h_lider, timeout=15)
    assert r.status_code == 200


# ==================== RBAC ====================

def test_lider_blocked_inventory_report(h_lider):
    r = requests.get(f"{API}/library/reports/inventory_current", headers=h_lider, timeout=15)
    assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text}"


def test_lider_can_use_scan_endpoints(h_lider, sample_book, sample_person):
    r = requests.get(f"{API}/library/scan/resolve-material",
                     params={"code": sample_book["book_id"]}, headers=h_lider, timeout=15)
    assert r.status_code == 200
    pid = sample_person.get("person_id") or sample_person.get("_id")
    r = requests.post(f"{API}/library/scan/resolve-person",
                      json={"code": pid}, headers=h_lider, timeout=15)
    assert r.status_code == 200


def test_unauth_blocked_reports():
    r = requests.get(f"{API}/library/reports/catalog", timeout=15)
    assert r.status_code in (401, 403)


def test_unauth_blocked_scan():
    r = requests.get(f"{API}/library/scan/resolve-material",
                     params={"code": "abc"}, timeout=15)
    assert r.status_code in (401, 403)


# ==================== DELIVER creates scan_method + list_price_cents fields ====================

def test_deliver_book_records_scan_method_and_price(h_pastor, sample_book, sample_person):
    pid = sample_person.get("person_id") or sample_person.get("_id")
    payload = {
        "book_id": sample_book["book_id"],
        "quantity": 1,
        "as_loan": False,
        "payment_status": "no_aplica",
        "scan_method": "MANUAL",
        "notes": "TEST_phase4_scan",
    }
    r = requests.post(f"{API}/library/persons/{pid}/deliver",
                      json=payload, headers=h_pastor, timeout=30)
    if r.status_code == 400 and "stock" in r.text.lower():
        pytest.skip(f"No stock for book {sample_book['book_id']}")
    assert r.status_code in (200, 201), r.text
    mv = r.json()
    assert mv.get("scan_method") == "MANUAL"
    assert "list_price_cents" in mv


# ==================== PO lifecycle regression (PUT edit fix) ====================

def test_put_edit_draft_po_available(h_pastor, sample_book):
    # Create a draft PO
    payload = {
        "provider_name": "TEST_Phase4_Provider",
        "expected_date": "2026-06-30",
        "lines": [{"book_id": sample_book["book_id"], "quantity": 2, "unit_cost_cents": 1000}],
        "notes": "TEST_phase4",
    }
    r = requests.post(f"{API}/library/purchase-orders", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code in (200, 201), r.text
    po = r.json()
    po_id = po["po_id"]
    try:
        # PUT edit
        payload["notes"] = "TEST_phase4_edited"
        r2 = requests.put(f"{API}/library/purchase-orders/{po_id}",
                          json=payload, headers=h_pastor, timeout=15)
        assert r2.status_code == 200, f"PUT edit -> {r2.status_code} {r2.text}"
    finally:
        # Cancel to clean up
        requests.post(f"{API}/library/purchase-orders/{po_id}/cancel",
                      headers=h_pastor, timeout=15)
