"""Librería 360 Phase 2 - Purchase Orders backend tests.

Covers: create draft, submit, approve (with Finance expense linkage),
reject, request_changes → resubmit, mark_ordered, partial + full receive
(with PURCHASE_RECEIPT ledger movements), close, comments, file upload,
and file storage verification (no base64 in mongo).
"""
import io
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PASTOR_EMAIL = "qa.baptismui53.pastor@example.com"
PASSWORD = "QaBaptismUI53!"


def _login(email: str) -> dict:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    d = r.json()
    return {"token": d["token"], "user_id": d["user"]["id"], "email": email}


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def pastor():
    return _login(PASTOR_EMAIL)


@pytest.fixture(scope="module")
def two_books(pastor):
    r = requests.get(f"{BASE_URL}/api/library/books", headers=_h(pastor["token"]), timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 2, "Need at least 2 books to test PO"
    return items[:2]


# ----- Create + Submit + Approve → linked expense -----
class TestPOApproveFlow:
    po_id = None
    po_number = None

    def test_create_draft(self, pastor, two_books):
        payload = {
            "provider_name": "TEST_Provider Phase2",
            "tax_cents": 500,
            "shipping_cents": 1000,
            "lines": [
                {"book_id": two_books[0]["book_id"], "quantity": 3, "unit_cost_cents": 1500},
                {"book_id": two_books[1]["book_id"], "quantity": 2, "unit_cost_cents": 2500},
            ],
        }
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders", headers=_h(pastor["token"]), json=payload, timeout=30)
        assert r.status_code == 201, r.text
        po = r.json()
        assert po["status"] == "draft"
        # subtotal = 3*1500 + 2*2500 = 9500 + tax 500 + ship 1000 = 11000
        assert po["subtotal_cents"] == 9500
        assert po["total_cents"] == 11000
        assert po["po_number"].startswith("PO-")
        assert "_id" not in po
        TestPOApproveFlow.po_id = po["po_id"]
        TestPOApproveFlow.po_number = po["po_number"]

    def test_list_and_filter(self, pastor):
        r = requests.get(f"{BASE_URL}/api/library/purchase-orders", headers=_h(pastor["token"]), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "can_decide" in data
        assert data["can_decide"] is True
        assert any(x["po_id"] == self.po_id for x in data["items"])
        # filter by status
        r2 = requests.get(f"{BASE_URL}/api/library/purchase-orders?status=draft", headers=_h(pastor["token"]), timeout=30)
        assert r2.status_code == 200
        assert all(x["status"] == "draft" for x in r2.json()["items"])

    def test_submit(self, pastor):
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/submit", headers=_h(pastor["token"]), json={}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "submitted"

    def test_approve_creates_expense(self, pastor):
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/decision",
                          headers=_h(pastor["token"]), json={"action": "approve", "note": "OK"}, timeout=30)
        assert r.status_code == 200, r.text
        po = r.json()
        assert po["status"] == "approved"
        # give it a beat for finance sync
        time.sleep(1)
        r2 = requests.get(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}", headers=_h(pastor["token"]), timeout=30)
        po2 = r2.json()
        assert po2.get("linked_expense_id"), f"Expected linked_expense_id after approve, got: {po2}"
        assert not po2.get("finance_sync_error"), f"Finance sync error: {po2.get('finance_sync_error')}"

    def test_mark_ordered(self, pastor):
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/mark-ordered", headers=_h(pastor["token"]), json={}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ordered"

    def test_partial_receive_creates_ledger_movement(self, pastor, two_books):
        book0 = two_books[0]["book_id"]
        # Fetch existing PURCHASE_RECEIPT count before
        # Receive 1 of book0
        payload = {"lines": [
            {"book_id": book0, "quantity_received_now": 1},
            {"book_id": two_books[1]["book_id"], "quantity_received_now": 0},
        ], "notes": "Recepción parcial"}
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/receive", headers=_h(pastor["token"]), json=payload, timeout=30)
        assert r.status_code == 200, r.text
        po = r.json()
        assert po["status"] == "partially_received"
        line0 = next(l for l in po["lines"] if l["book_id"] == book0)
        assert line0["quantity_received"] == 1
        # verify a PURCHASE_RECEIPT movement was created for this book via ledger endpoint
        mv = requests.get(f"{BASE_URL}/api/library/movements?book_id={book0}", headers=_h(pastor["token"]), timeout=30)
        assert mv.status_code == 200, mv.text
        movements = mv.json().get("items", [])
        recent = [m for m in movements if m.get("movement_type") == "PURCHASE_RECEIPT" and self.po_number in (m.get("notes") or "")]
        assert recent, f"No PURCHASE_RECEIPT movement found referencing {self.po_number}. Movements: {movements[:5]}"

    def test_full_receive(self, pastor, two_books):
        payload = {"lines": [
            {"book_id": two_books[0]["book_id"], "quantity_received_now": 2},
            {"book_id": two_books[1]["book_id"], "quantity_received_now": 2},
        ], "notes": "Recepción total"}
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/receive", headers=_h(pastor["token"]), json=payload, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "received"

    def test_close(self, pastor):
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/close", headers=_h(pastor["token"]), json={}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "closed"

    def test_cannot_receive_after_close(self, pastor, two_books):
        payload = {"lines": [{"book_id": two_books[0]["book_id"], "quantity_received_now": 1}]}
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/receive", headers=_h(pastor["token"]), json=payload, timeout=30)
        assert r.status_code == 409

    def test_comment_and_attachment(self, pastor):
        rc = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/comments",
                           headers=_h(pastor["token"]), json={"text": "TEST_ comment"}, timeout=30)
        assert rc.status_code == 201, rc.text
        # upload small PNG (1x1)
        png_bytes = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
                     b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x5c\xcd\xff\x69\x00\x00\x00\x00IEND\xaeB`\x82")
        files = {"file": ("test.png", io.BytesIO(png_bytes), "image/png")}
        h = {"Authorization": f"Bearer {pastor['token']}"}  # NO explicit content-type
        ru = requests.post(f"{BASE_URL}/api/library/files/po-attachment/{self.po_id}", headers=h, files=files, timeout=60)
        assert ru.status_code == 201, ru.text
        file_id = ru.json()["file_id"]
        # list by owner
        rl = requests.get(f"{BASE_URL}/api/library/files/by-owner/purchase_order/{self.po_id}", headers=_h(pastor["token"]), timeout=30)
        assert rl.status_code == 200
        items = rl.json()["items"]
        rec = next((x for x in items if x["file_id"] == file_id), None)
        assert rec is not None
        # storage_path must NOT be base64 blob; should look like a path
        assert "storage_path" in rec and rec["storage_path"] and "/" in rec["storage_path"]
        assert len(rec["storage_path"]) < 500, "storage_path suspiciously long, may be base64"
        # download
        rd = requests.get(f"{BASE_URL}/api/library/files/{file_id}/download", headers=_h(pastor["token"]), timeout=60)
        assert rd.status_code == 200
        assert rd.content[:4] == b"\x89PNG"


# ----- Reject flow: no expense should be created -----
class TestPORejectFlow:
    po_id = None

    def test_create_and_reject(self, pastor, two_books):
        payload = {"provider_name": "TEST_Reject Provider", "lines": [
            {"book_id": two_books[0]["book_id"], "quantity": 1, "unit_cost_cents": 500}
        ]}
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders", headers=_h(pastor["token"]), json=payload, timeout=30)
        assert r.status_code == 201
        TestPORejectFlow.po_id = r.json()["po_id"]
        rs = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/submit", headers=_h(pastor["token"]), json={}, timeout=30)
        assert rs.status_code == 200
        rj = requests.post(f"{BASE_URL}/api/library/purchase-orders/{self.po_id}/decision",
                           headers=_h(pastor["token"]), json={"action": "reject", "note": "no"}, timeout=30)
        assert rj.status_code == 200
        po = rj.json()
        assert po["status"] == "rejected"
        assert not po.get("linked_expense_id")


# ----- Request changes → resubmit flow -----
class TestPORequestChangesFlow:
    po_id = None

    def test_request_changes_and_resubmit(self, pastor, two_books):
        payload = {"provider_name": "TEST_ChangeReq", "lines": [
            {"book_id": two_books[0]["book_id"], "quantity": 1, "unit_cost_cents": 100}
        ]}
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders", headers=_h(pastor["token"]), json=payload, timeout=30)
        assert r.status_code == 201
        pid = r.json()["po_id"]
        TestPORequestChangesFlow.po_id = pid
        requests.post(f"{BASE_URL}/api/library/purchase-orders/{pid}/submit", headers=_h(pastor["token"]), json={}, timeout=30)
        rc = requests.post(f"{BASE_URL}/api/library/purchase-orders/{pid}/decision",
                           headers=_h(pastor["token"]), json={"action": "request_changes", "note": "adjust"}, timeout=30)
        assert rc.status_code == 200
        assert rc.json()["status"] == "changes_requested"
        # Edit is allowed only in draft, changes_requested should allow resubmit
        rs = requests.post(f"{BASE_URL}/api/library/purchase-orders/{pid}/submit", headers=_h(pastor["token"]), json={}, timeout=30)
        assert rs.status_code == 200, rs.text
        assert rs.json()["status"] == "submitted"


# ----- Guards -----
class TestPOGuards:
    def test_unauth(self):
        r = requests.get(f"{BASE_URL}/api/library/purchase-orders", timeout=30)
        assert r.status_code in (401, 403)

    def test_receive_wrong_status(self, pastor, two_books):
        # create fresh draft; try to receive directly
        payload = {"provider_name": "TEST_BadState", "lines": [
            {"book_id": two_books[0]["book_id"], "quantity": 1, "unit_cost_cents": 100}
        ]}
        r = requests.post(f"{BASE_URL}/api/library/purchase-orders", headers=_h(pastor["token"]), json=payload, timeout=30)
        pid = r.json()["po_id"]
        r2 = requests.post(f"{BASE_URL}/api/library/purchase-orders/{pid}/receive",
                           headers=_h(pastor["token"]), json={"lines": [{"book_id": two_books[0]["book_id"], "quantity_received_now": 1}]}, timeout=30)
        assert r2.status_code == 409
