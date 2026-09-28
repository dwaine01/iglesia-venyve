"""Librería 360 — Security remediation tests (iter16).

Covers 5 fixes:
  FIX 1 (SEC-001, BFLA on reservations): non-manager líder cannot RESERVATION/RESERVATION_RELEASE against central.
  FIX 2a (SEC-004, BOLA on person_ledger report): líder without reports.read only sees own actor rows.
  FIX 2b (BOLA on person materials tab): líder only sees own actor_user_id movements.
  FIX 3 (regex sanitization): re.escape() applied to $regex search inputs.
  FIX 4 (Excel formula injection): sanitize_cell() prefixes '=' '+' '-' '@' with a single quote in xlsx exports.

Also spot-checks:
  - regression: líder RESERVATION into own inventory still 201.
  - regression: líder DELIVERY from own user inventory still 201.
  - regression: reservations/sync endpoint (internal apply_movement) still creates RESERVATION movements against central.
  - regression: manager/reports.read user still sees FULL person_ledger and full person_materials list.
"""
import io
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests
from openpyxl import load_workbook

# Direct load of the sanitize_cell function for FIX 4 unit test — avoid importing the
# module (which triggers server.py circular import). Load just the function via AST.
import ast, textwrap
_lib_reports_src = open("/app/backend/library_reports.py").read()
_module_ast = ast.parse(_lib_reports_src)
_ns = {}
for _node in _module_ast.body:
    if isinstance(_node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "FORMULA_PREFIXES" for t in _node.targets):
        exec(compile(ast.Module(body=[_node], type_ignores=[]), "<ast>", "exec"), _ns)
    if isinstance(_node, ast.FunctionDef) and _node.name == "sanitize_cell":
        exec(compile(ast.Module(body=[_node], type_ignores=[]), "<ast>", "exec"), _ns)
sanitize_cell = _ns["sanitize_cell"]
FORMULA_PREFIXES = _ns["FORMULA_PREFIXES"]

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
PASTOR = ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!")
LIDER = ("qa.baptismui53.lider@example.com", "QaBaptismUI53!")

CENTRAL_HOLDER = {"type": "warehouse", "id": "central"}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def pastor_data():
    return _login(*PASTOR)


@pytest.fixture(scope="module")
def lider_data():
    return _login(*LIDER)


@pytest.fixture(scope="module")
def h_pastor(pastor_data):
    return {"Authorization": f"Bearer {pastor_data['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def h_lider(lider_data):
    return {"Authorization": f"Bearer {lider_data['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def lider_user_id(lider_data):
    return lider_data["user"]["id"]


@pytest.fixture(scope="module")
def pastor_user_id(pastor_data):
    return pastor_data["user"]["id"]


@pytest.fixture(scope="module")
def seed_book(h_pastor):
    """Create a paid TEST book seeded with 20 units at central via a PO."""
    ts = int(time.time())
    sku = f"TEST_SEC16_{ts}"
    payload = {
        "sku": sku, "name": f"TEST Security Fix Book {ts}",
        "kind": "paid", "member_price_cents": 1500, "list_price_cents": 1500,
        "notes": "iter16 security fix seed",
    }
    r = requests.post(f"{API}/library/books", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code in (200, 201), r.text
    book = r.json()

    # Seed stock at central via a PO (draft -> submit -> approve -> mark-ordered -> receive)
    po_payload = {
        "provider_name": f"TEST_SEC16_Provider_{ts}",
        "expected_date": datetime.now(timezone.utc).date().isoformat(),
        "lines": [{"book_id": book["book_id"], "quantity": 20, "unit_cost_cents": 1000}],
    }
    po_r = requests.post(f"{API}/library/purchase-orders", json=po_payload, headers=h_pastor, timeout=15)
    assert po_r.status_code in (200, 201), po_r.text
    po_id = po_r.json()["po_id"]
    for step in ["submit", "mark-ordered"]:
        pass  # handled below
    requests.post(f"{API}/library/purchase-orders/{po_id}/submit", headers=h_pastor, timeout=15)
    requests.post(f"{API}/library/purchase-orders/{po_id}/decision",
                  json={"action": "approve", "note": "ok"}, headers=h_pastor, timeout=15)
    requests.post(f"{API}/library/purchase-orders/{po_id}/mark-ordered", headers=h_pastor, timeout=15)
    receive_r = requests.post(
        f"{API}/library/purchase-orders/{po_id}/receive",
        json={"lines": [{"book_id": book["book_id"], "quantity_received_now": 20}]},
        headers=h_pastor, timeout=15,
    )
    assert receive_r.status_code in (200, 201), receive_r.text
    return book


@pytest.fixture(scope="module")
def sample_person(h_pastor):
    for q in ["an", "ma", "jo", "ca", "el"]:
        r = requests.get(f"{API}/library/scan/search-person", params={"q": q}, headers=h_pastor, timeout=15)
        if r.status_code == 200 and r.json().get("items"):
            return r.json()["items"][0]
    pytest.skip("No persons found")


@pytest.fixture(scope="module")
def stocked_lider(h_pastor, seed_book, lider_user_id):
    """Transfer 5 units from central to líder so RESERVATION/DELIVERY-from-own tests work."""
    payload = {
        "book_id": seed_book["book_id"],
        "movement_type": "TRANSFER",
        "quantity": 5,
        "from_holder": CENTRAL_HOLDER,
        "to_holder": {"type": "user", "id": lider_user_id},
        "notes": "TEST_SEC16 seed transfer",
    }
    r = requests.post(f"{API}/library/movements", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 201, r.text
    return True


# ==================== FIX 1: SEC-001 BFLA on reservations ====================

def test_fix1_lider_cannot_reserve_against_central(h_lider, seed_book):
    payload = {
        "book_id": seed_book["book_id"],
        "movement_type": "RESERVATION",
        "quantity": 1,
        "to_holder": CENTRAL_HOLDER,
        "notes": "TEST_SEC16 bfla attempt",
    }
    r = requests.post(f"{API}/library/movements", json=payload, headers=h_lider, timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


def test_fix1_lider_can_reserve_into_own_inventory(h_lider, seed_book, lider_user_id, stocked_lider):
    payload = {
        "book_id": seed_book["book_id"],
        "movement_type": "RESERVATION",
        "quantity": 1,
        "to_holder": {"type": "user", "id": lider_user_id},
        "notes": "TEST_SEC16 self-reservation",
    }
    r = requests.post(f"{API}/library/movements", json=payload, headers=h_lider, timeout=15)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"


def test_fix1_lider_cannot_release_reservation_from_central(h_lider, seed_book):
    payload = {
        "book_id": seed_book["book_id"],
        "movement_type": "RESERVATION_RELEASE",
        "quantity": 1,
        "from_holder": CENTRAL_HOLDER,
        "notes": "TEST_SEC16 bfla release",
    }
    r = requests.post(f"{API}/library/movements", json=payload, headers=h_lider, timeout=15)
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


def test_fix1_lider_can_release_reservation_from_own_inventory(h_lider, seed_book, lider_user_id, stocked_lider):
    # First create a self-reservation to release
    reserve = requests.post(f"{API}/library/movements", json={
        "book_id": seed_book["book_id"], "movement_type": "RESERVATION", "quantity": 1,
        "to_holder": {"type": "user", "id": lider_user_id}, "notes": "TEST_SEC16 to-release",
    }, headers=h_lider, timeout=15)
    assert reserve.status_code == 201, reserve.text
    r = requests.post(f"{API}/library/movements", json={
        "book_id": seed_book["book_id"], "movement_type": "RESERVATION_RELEASE", "quantity": 1,
        "from_holder": {"type": "user", "id": lider_user_id}, "notes": "TEST_SEC16 self-release",
    }, headers=h_lider, timeout=15)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"


def test_fix1_lider_delivery_from_own_still_works(h_lider, seed_book, lider_user_id, stocked_lider, sample_person):
    payload = {
        "book_id": seed_book["book_id"],
        "movement_type": "DELIVERY",
        "quantity": 1,
        "from_holder": {"type": "user", "id": lider_user_id},
        "to_holder": {"type": "person", "id": sample_person["person_id"]},
        "person_id": sample_person["person_id"],
        "payment_status": "exonerado",
        "amount_paid_cents": 0,
        "notes": "TEST_SEC16 regression delivery",
    }
    r = requests.post(f"{API}/library/movements", json=payload, headers=h_lider, timeout=15)
    assert r.status_code == 201, f"expected 201, got {r.status_code}: {r.text}"


def test_fix1_reservations_sync_internal_path_unaffected(h_pastor):
    """The automated reservations/sync endpoint calls apply_movement() directly, bypassing
    the router BFLA check. That must still succeed for managers."""
    r = requests.post(f"{API}/library/reservations/sync", headers=h_pastor, timeout=30)
    assert r.status_code in (200, 202), r.text


# ==================== FIX 2a: BOLA on person_ledger report ====================

def test_fix2a_manager_sees_full_person_ledger(h_pastor, sample_person):
    r = requests.get(f"{API}/library/reports/person_ledger",
                     params={"person_id": sample_person["person_id"]},
                     headers=h_pastor, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "rows" in data
    # Cannot assert non-empty for arbitrary person, but must not error.


def test_fix2a_lider_person_ledger_filtered_to_own_actor(h_pastor, h_lider, seed_book, lider_user_id,
                                                          stocked_lider, sample_person):
    """Person delivered to by pastor: líder must NOT see rows where actor is pastor.
    But if líder personally delivered something to same person, that row MUST appear."""
    # Pastor delivers 1 unit from central to sample_person
    pastor_deliver = requests.post(f"{API}/library/movements", json={
        "book_id": seed_book["book_id"], "movement_type": "DELIVERY", "quantity": 1,
        "from_holder": CENTRAL_HOLDER,
        "to_holder": {"type": "person", "id": sample_person["person_id"]},
        "person_id": sample_person["person_id"],
        "payment_status": "exonerado", "amount_paid_cents": 0,
        "notes": "TEST_SEC16 pastor delivery",
    }, headers=h_pastor, timeout=15)
    assert pastor_deliver.status_code == 201, pastor_deliver.text

    # Líder delivers 1 unit from own inventory to same person
    lider_deliver = requests.post(f"{API}/library/movements", json={
        "book_id": seed_book["book_id"], "movement_type": "DELIVERY", "quantity": 1,
        "from_holder": {"type": "user", "id": lider_user_id},
        "to_holder": {"type": "person", "id": sample_person["person_id"]},
        "person_id": sample_person["person_id"],
        "payment_status": "exonerado", "amount_paid_cents": 0,
        "notes": "TEST_SEC16 lider delivery",
    }, headers=h_lider, timeout=15)
    assert lider_deliver.status_code == 201, lider_deliver.text
    lider_movement_id = lider_deliver.json()["movement_id"]

    # Manager view: must see BOTH rows
    r_pastor = requests.get(f"{API}/library/reports/person_ledger",
                            params={"person_id": sample_person["person_id"]},
                            headers=h_pastor, timeout=15)
    assert r_pastor.status_code == 200, r_pastor.text
    pastor_rows = r_pastor.json().get("rows", [])
    assert len(pastor_rows) >= 2, f"Manager should see at least 2 rows, got {len(pastor_rows)}"

    # Lider view: must only see rows where actor is the líder
    r_lider = requests.get(f"{API}/library/reports/person_ledger",
                           params={"person_id": sample_person["person_id"]},
                           headers=h_lider, timeout=15)
    assert r_lider.status_code == 200, r_lider.text
    lider_rows = r_lider.json().get("rows", [])
    # The last column is "Entregado por" (actor name). We can't easily map names,
    # so instead verify via person_materials that lider only sees own movement (done in FIX 2b).
    # But the LEN of rows for líder MUST be strictly less than for pastor when pastor has more actor rows.
    assert len(lider_rows) <= len(pastor_rows), "Líder should not see MORE rows than manager"
    # And should be >= 1 since líder did deliver personally
    assert len(lider_rows) >= 1, f"Líder should see at least their own delivery row, got {len(lider_rows)}"


# ==================== FIX 2b: BOLA on person materials tab ====================

def test_fix2b_person_materials_filtered_for_lider(h_pastor, h_lider, seed_book, lider_user_id, sample_person):
    """After the two deliveries above, líder should only see own movements on this tab."""
    r_pastor = requests.get(f"{API}/library/persons/{sample_person['person_id']}/materials",
                            headers=h_pastor, timeout=15)
    assert r_pastor.status_code == 200, r_pastor.text
    pastor_items = r_pastor.json().get("items", [])

    r_lider = requests.get(f"{API}/library/persons/{sample_person['person_id']}/materials",
                           headers=h_lider, timeout=15)
    assert r_lider.status_code == 200, r_lider.text
    lider_items = r_lider.json().get("items", [])

    # Every líder-visible movement must have actor_user_id == lider_user_id
    for item in lider_items:
        assert item.get("actor_user_id") == lider_user_id, \
            f"Líder saw a movement with actor {item.get('actor_user_id')} != own id {lider_user_id}"

    # Manager should see AT LEAST as many as líder (and typically more, since pastor also acted)
    assert len(pastor_items) >= len(lider_items)
    # Manager must see at least one non-lider-actor movement (the pastor DELIVERY)
    non_lider_for_pastor = [i for i in pastor_items if i.get("actor_user_id") != lider_user_id]
    assert len(non_lider_for_pastor) >= 1, "Manager should see movements not authored by the líder"


# ==================== FIX 3: regex sanitization ====================

REGEX_PAYLOADS = ["(a+)+b", ".*.*.*.*.*!", "$^*(", "[[[", "\\", ".*" * 20]


@pytest.mark.parametrize("payload", REGEX_PAYLOADS)
def test_fix3_books_search_regex_safe(h_pastor, payload):
    t0 = time.time()
    r = requests.get(f"{API}/library/books", params={"search": payload}, headers=h_pastor, timeout=10)
    elapsed = time.time() - t0
    assert r.status_code == 200, f"payload={payload!r} status={r.status_code} body={r.text[:200]}"
    assert elapsed < 5, f"query took {elapsed}s for payload {payload!r} (regex hang?)"


@pytest.mark.parametrize("payload", REGEX_PAYLOADS)
def test_fix3_scan_search_person_regex_safe(h_pastor, payload):
    t0 = time.time()
    r = requests.get(f"{API}/library/scan/search-person", params={"q": payload}, headers=h_pastor, timeout=10)
    elapsed = time.time() - t0
    assert r.status_code in (200, 404), f"payload={payload!r} status={r.status_code}"
    assert elapsed < 5, f"query took {elapsed}s for payload {payload!r}"


@pytest.mark.parametrize("payload", REGEX_PAYLOADS)
def test_fix3_resolve_material_regex_safe(h_pastor, payload):
    t0 = time.time()
    r = requests.get(f"{API}/library/scan/resolve-material", params={"code": payload}, headers=h_pastor, timeout=10)
    elapsed = time.time() - t0
    # Should be 404 (not found) or 200, never 500
    assert r.status_code in (200, 404), f"payload={payload!r} status={r.status_code} body={r.text[:200]}"
    assert elapsed < 5, f"query took {elapsed}s for payload {payload!r}"


# ==================== FIX 4: Excel formula injection ====================

def test_fix4_sanitize_cell_unit_test():
    """Unit test the sanitize_cell function directly."""
    assert sanitize_cell("=cmd") == "'=cmd"
    assert sanitize_cell("+1+1") == "'+1+1"
    assert sanitize_cell("-2") == "'-2"
    assert sanitize_cell("@SUM(A1)") == "'@SUM(A1)"
    assert sanitize_cell("normal text") == "normal text"
    assert sanitize_cell("") == ""
    assert sanitize_cell(None) is None
    assert sanitize_cell(123) == 123
    # Ensure FORMULA_PREFIXES contains exactly the 4 chars
    assert set(FORMULA_PREFIXES) == {"=", "+", "-", "@"}


def test_fix4_xlsx_export_sanitized(h_pastor, seed_book, sample_person, lider_user_id, h_lider):
    """Create a movement with a formula-looking notes field, export xlsx, verify sanitization.

    Since notes field is used but not part of the exported columns of most reports, we rely on
    the fact that at least one row is exported and confirm the sheet loads AND that if any cell
    starts with a formula character, it has been prefixed. We also confirm the export produces
    a valid xlsx file with rows."""
    # Ensure at least one delivery exists (from previous test); export movement_history
    r = requests.get(f"{API}/library/reports/movement_history",
                     params={"format": "xlsx"}, headers=h_pastor, timeout=30)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), r.headers
    wb = load_workbook(io.BytesIO(r.content))
    sheet = wb.active
    # Confirm header row present and at least 1 data row
    rows = list(sheet.iter_rows(values_only=True))
    assert len(rows) >= 2, f"expected header + >=1 data row, got {len(rows)}"
    # Any string cell in data rows starting with formula chars must be prefixed (impossible
    # to be present raw because sanitize_cell runs on every cell). Verify no raw offender:
    for row in rows[1:]:
        for cell in row:
            if isinstance(cell, str) and cell.startswith(("=", "+", "-", "@")):
                pytest.fail(f"Unsanitized formula-looking cell found in xlsx export: {cell!r}")


def test_fix4_xlsx_export_book_name_with_formula_prefix(h_pastor):
    """Create a TEST book with a name starting with '=' and confirm its export cell is quoted."""
    ts = int(time.time())
    book_name = f"=DANGER_TEST_SEC16_{ts}"
    payload = {
        "sku": f"TEST_SEC16_XL_{ts}",
        "name": book_name,
        "kind": "free",
    }
    r = requests.post(f"{API}/library/books", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code in (200, 201), r.text
    book = r.json()

    # Add a stock movement so it shows in inventory_current report
    mv = requests.post(f"{API}/library/movements", json={
        "book_id": book["book_id"], "movement_type": "PURCHASE_RECEIPT", "quantity": 3,
        "to_holder": CENTRAL_HOLDER, "notes": "TEST_SEC16 seed",
    }, headers=h_pastor, timeout=15)
    assert mv.status_code == 201, mv.text

    r = requests.get(f"{API}/library/reports/inventory_current",
                     params={"format": "xlsx"}, headers=h_pastor, timeout=30)
    assert r.status_code == 200, r.text
    wb = load_workbook(io.BytesIO(r.content))
    sheet = wb.active
    found_sanitized = False
    for row in sheet.iter_rows(values_only=True):
        for cell in row:
            if isinstance(cell, str) and book_name in cell:
                # Must be prefixed with single quote
                assert cell.startswith("'="), f"unsanitized cell {cell!r} found in export"
                found_sanitized = True
    assert found_sanitized, "Test book name not found in inventory_current export - cannot verify sanitization"

    # Cleanup: deactivate
    requests.patch(f"{API}/library/books/{book['book_id']}/toggle-active", headers=h_pastor, timeout=15)


# ==================== Cleanup ====================

def test_zz_cleanup(h_pastor, seed_book):
    """Deactivate seed book to keep DB clean."""
    r = requests.patch(f"{API}/library/books/{seed_book['book_id']}/toggle-active",
                        headers=h_pastor, timeout=15)
    assert r.status_code in (200, 204), r.text
