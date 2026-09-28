"""Librería 360 — P2 validation: payment_status='pagado' requires
amount_paid_cents >= book.member_price_cents. Other payment_status values
(pendiente, exonerado, beca, descuento, pago_parcial, no_aplica) must NOT
be blocked by this check.

Covers both entry points that call apply_movement():
- POST /api/library/persons/{person_id}/deliver  (deliver_book)
- POST /api/library/movements                    (create_movement)
"""
import os
import time
from uuid import uuid4

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
PASTOR = ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!")

BOOK_PRICE = 1500  # cents


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def h_pastor():
    tok = _login(*PASTOR)["token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sample_person(h_pastor):
    for q in ["an", "ma", "jo", "ca", "el", "a"]:
        r = requests.get(f"{API}/library/scan/search-person", params={"q": q}, headers=h_pastor, timeout=15)
        if r.status_code == 200 and r.json().get("items"):
            return r.json()["items"][0]
    pytest.skip("No persons available")


@pytest.fixture(scope="module")
def test_book(h_pastor):
    """Create a paid book with 20 units of central stock via PURCHASE_RECEIPT."""
    suffix = f"{int(time.time())}_{uuid4().hex[:6]}"
    payload = {
        "sku": f"TEST_P2VAL_{suffix}",
        "name": f"TEST_P2Validation Book {suffix}",
        "description": "P2 payment validation test material",
        "item_type": "libro",
        "cost_price_cents": 500,
        "member_price_cents": BOOK_PRICE,
        "inventory_kind": "consumable",
        "is_active": True,
        "min_stock": 0,
        "ideal_stock": 50,
    }
    r = requests.post(f"{API}/library/books", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 201, r.text
    book = r.json()
    # Seed central stock via PURCHASE_RECEIPT movement
    mv = {
        "book_id": book["book_id"],
        "movement_type": "PURCHASE_RECEIPT",
        "quantity": 20,
        "to_holder": {"type": "warehouse", "id": "central"},
        "notes": "TEST_P2Validation seed stock",
    }
    r2 = requests.post(f"{API}/library/movements", json=mv, headers=h_pastor, timeout=15)
    assert r2.status_code == 201, r2.text
    yield book
    # Cleanup: deactivate
    requests.put(f"{API}/library/books/{book['book_id']}",
                 json={**payload, "is_active": False}, headers=h_pastor, timeout=15)


def _holding_central(h_pastor, book_id):
    r2 = requests.get(f"{API}/library/movements", params={"book_id": book_id}, headers=h_pastor, timeout=15)
    assert r2.status_code == 200, r2.text
    items = r2.json().get("items", [])
    add = sum(m["quantity"] for m in items if m["movement_type"] == "PURCHASE_RECEIPT")
    rem = sum(m["quantity"] for m in items if m["movement_type"] in ("DELIVERY", "LOSS", "DAMAGE"))
    return add - rem, len(items)


def _deliver(h_pastor, person_id, book_id, payment_status, amount_paid_cents, quantity=1):
    payload = {
        "book_id": book_id,
        "quantity": quantity,
        "payment_status": payment_status,
        "amount_paid_cents": amount_paid_cents,
        "payment_method": "efectivo" if amount_paid_cents else None,
        "scan_method": "MANUAL",
        "notes": f"TEST_P2Validation deliver {payment_status}/{amount_paid_cents}",
    }
    # cleanup Nones
    payload = {k: v for k, v in payload.items() if v is not None}
    return requests.post(f"{API}/library/persons/{person_id}/deliver",
                         json=payload, headers=h_pastor, timeout=20)


# ---------------- deliver_book endpoint ----------------

def test_deliver_pagado_underpaid_rejected_422(h_pastor, sample_person, test_book):
    before_stock, before_count = _holding_central(h_pastor, test_book["book_id"])
    r = _deliver(h_pastor, sample_person["person_id"], test_book["book_id"], "pagado", BOOK_PRICE - 1)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"
    detail = (r.json().get("detail") or "").lower()
    assert "pagado" in detail or "precio" in detail or str(BOOK_PRICE) in r.text, r.text
    # Verify no movement was created, no stock change
    after_stock, after_count = _holding_central(h_pastor, test_book["book_id"])
    assert after_stock == before_stock, f"Stock changed: {before_stock} -> {after_stock}"
    assert after_count == before_count, f"Movement leaked: {before_count} -> {after_count}"


def test_deliver_pagado_zero_amount_rejected_422(h_pastor, sample_person, test_book):
    r = _deliver(h_pastor, sample_person["person_id"], test_book["book_id"], "pagado", 0)
    assert r.status_code == 422, r.text


def test_deliver_pagado_exact_price_success(h_pastor, sample_person, test_book):
    before_stock, _ = _holding_central(h_pastor, test_book["book_id"])
    r = _deliver(h_pastor, sample_person["person_id"], test_book["book_id"], "pagado", BOOK_PRICE)
    assert r.status_code == 201, r.text
    mv = r.json()
    assert mv["movement_type"] == "DELIVERY"
    assert mv["amount_paid_cents"] == BOOK_PRICE
    assert mv["payment_status"] == "pagado"
    after_stock, _ = _holding_central(h_pastor, test_book["book_id"])
    assert after_stock == before_stock - 1
    # Verify finance sync happened
    assert mv.get("finance_contribution_id"), "expected finance income posted"


def test_deliver_pagado_overpayment_success(h_pastor, sample_person, test_book):
    r = _deliver(h_pastor, sample_person["person_id"], test_book["book_id"], "pagado", BOOK_PRICE + 500)
    assert r.status_code == 201, r.text
    assert r.json()["amount_paid_cents"] == BOOK_PRICE + 500


def test_deliver_pago_parcial_below_price_success(h_pastor, sample_person, test_book):
    r = _deliver(h_pastor, sample_person["person_id"], test_book["book_id"], "pago_parcial", 1)
    assert r.status_code == 201, r.text
    assert r.json()["payment_status"] == "pago_parcial"


def test_deliver_exonerado_zero_success(h_pastor, sample_person, test_book):
    r = _deliver(h_pastor, sample_person["person_id"], test_book["book_id"], "exonerado", 0)
    assert r.status_code == 201, r.text
    assert r.json()["payment_status"] == "exonerado"


def test_deliver_beca_zero_success(h_pastor, sample_person, test_book):
    r = _deliver(h_pastor, sample_person["person_id"], test_book["book_id"], "beca", 0)
    assert r.status_code == 201, r.text
    assert r.json()["payment_status"] == "beca"


def test_deliver_pendiente_zero_success(h_pastor, sample_person, test_book):
    r = _deliver(h_pastor, sample_person["person_id"], test_book["book_id"], "pendiente", 0)
    assert r.status_code == 201, r.text
    assert r.json()["payment_status"] == "pendiente"


def test_deliver_descuento_below_price_success(h_pastor, sample_person, test_book):
    r = _deliver(h_pastor, sample_person["person_id"], test_book["book_id"], "descuento", 100)
    assert r.status_code == 201, r.text


# ---------------- generic /movements DELIVERY entry ----------------

def test_movements_delivery_pagado_underpaid_rejected_422(h_pastor, sample_person, test_book):
    payload = {
        "book_id": test_book["book_id"],
        "movement_type": "DELIVERY",
        "quantity": 1,
        "from_holder": {"type": "warehouse", "id": "central"},
        "to_holder": {"type": "person", "id": sample_person["person_id"]},
        "person_id": sample_person["person_id"],
        "payment_status": "pagado",
        "amount_paid_cents": BOOK_PRICE - 100,
        "payment_method": "efectivo",
        "notes": "TEST_P2Validation generic movement underpaid",
    }
    r = requests.post(f"{API}/library/movements", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 422, r.text


def test_movements_delivery_pagado_exact_price_success(h_pastor, sample_person, test_book):
    payload = {
        "book_id": test_book["book_id"],
        "movement_type": "DELIVERY",
        "quantity": 1,
        "from_holder": {"type": "warehouse", "id": "central"},
        "to_holder": {"type": "person", "id": sample_person["person_id"]},
        "person_id": sample_person["person_id"],
        "payment_status": "pagado",
        "amount_paid_cents": BOOK_PRICE,
        "payment_method": "efectivo",
        "notes": "TEST_P2Validation generic movement paid",
    }
    r = requests.post(f"{API}/library/movements", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 201, r.text


def test_movements_delivery_pago_parcial_below_price_success(h_pastor, sample_person, test_book):
    payload = {
        "book_id": test_book["book_id"],
        "movement_type": "DELIVERY",
        "quantity": 1,
        "from_holder": {"type": "warehouse", "id": "central"},
        "to_holder": {"type": "person", "id": sample_person["person_id"]},
        "person_id": sample_person["person_id"],
        "payment_status": "pago_parcial",
        "amount_paid_cents": 50,
        "notes": "TEST_P2Validation generic movement partial",
    }
    r = requests.post(f"{API}/library/movements", json=payload, headers=h_pastor, timeout=15)
    assert r.status_code == 201, r.text
