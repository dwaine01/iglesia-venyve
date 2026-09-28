"""Librería 360 — Iteration 17 security fix test:
GET /api/library/scan/persons/{person_id}/library-snapshot must enforce
ROLE-based (global) OR RELATIONSHIP-based access (mentor / responsible /
consolidation líder / process teacher). Reuses `access_person_ids` from
process_engine — the same relationship graph that already gates Persona 360.

Covers 10 scenarios:
 1. Global access — Pastor
 2. Global access — LIBRARY_CATALOG_MANAGE
 3. Global access — LIBRARY_INVENTORY_MANAGE
 4. Global access — LIBRARY_REPORTS_READ (no library manager, no relationship)
 5. Global access — FINANCE_READ
 6. Global access — FINANCE_MANAGE
 7. Relationship access — mentor_person_id
 8. Relationship access — responsible_person_id (process_key='discipulado_2')
 9. Relationship access — responsible_person_id (process_key='consolidation')
10. NEGATIVE — plain líder with LIBRARY_DELIVER only, no relationship => 403
11. NEGATIVE — persona role (no LIBRARY_DELIVER) => 403 at dependency
12. NEGATIVE — person_id tampering (mentor of A tries B) => 200 for A, 403 for B
13. NEGATIVE — scan flow does not bypass RBAC (resolve-person then snapshot => 403)
14. DATA EXPOSURE — response payload only contains allowed fields.
"""
import os
import time
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

PASTOR = ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

RUN_ID = f"iter17_{int(time.time())}_{uuid.uuid4().hex[:6]}"
PASSWORD = "SnapRBAC17!"

FINANCE_PRIVILEGE_GROUP = "finance"

# --- helpers ---------------------------------------------------------------

def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return r.json()


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def pastor():
    return _login(*PASTOR)


# ----- User factory: insert directly, then bump token_version-free login ---
def _make_user(db, *, email, rol, capabilities, person_display, privilege_groups=None, access_scope=None):
    hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    person_doc = {
        "display_name": person_display,
        "full_name": person_display,
        "nombre": person_display.split()[0],
        "apellido": person_display.split()[-1] if " " in person_display else "",
        "is_archived": False,
        "person_number": f"TEST_{uuid.uuid4().hex[:12]}",
        "idempotency_key": f"TEST_{uuid.uuid4().hex}",
        "created_at": datetime.now(timezone.utc),
    }
    p_res = db.persons.insert_one(person_doc)
    person_id = str(p_res.inserted_id)
    # Also set explicit person_id field so canonical_person queries succeed either way.
    db.persons.update_one({"_id": p_res.inserted_id}, {"$set": {"person_id": person_id}})
    user_doc = {
        "nombre": person_display,
        "email": email,
        "password": hashed,
        "rol": rol,
        "capabilities": capabilities,
        "access_scope": access_scope or ({"persons": "all"} if rol in ("pastor", "pastora") else {"persons": "created_by"} if rol == "lider" else {"persons": "self"}),
        "privilege_groups": privilege_groups or [],
        "is_active": True,
        "token_version": 1,
        "person_id": person_id,
        "created_at": datetime.now(timezone.utc),
    }
    u_res = db.users.insert_one(user_doc)
    user_id = str(u_res.inserted_id)
    return {"user_id": user_id, "person_id": person_id, "email": email, "display_name": person_display}


@pytest.fixture(scope="module")
def seed(db, pastor):
    pastor_uid = pastor["user"]["id"]

    # TARGET person (unrelated to any test líder unless a process_enrollment is created)
    target = db.persons.insert_one({
        "display_name": f"TARGET_{RUN_ID}",
        "full_name": f"TARGET {RUN_ID}",
        "nombre": "TARGET",
        "apellido": RUN_ID,
        "is_archived": False,
        "created_by": pastor_uid,
        "person_number": f"TEST_{uuid.uuid4().hex[:12]}",
        "idempotency_key": f"TEST_{uuid.uuid4().hex}",
        "created_at": datetime.now(timezone.utc),
    })
    target_pid = str(target.inserted_id)
    db.persons.update_one({"_id": target.inserted_id}, {"$set": {"person_id": target_pid}})

    # A SECOND person with NO relationship to any test user (for tampering test)
    target_b = db.persons.insert_one({
        "display_name": f"TARGETB_{RUN_ID}",
        "full_name": f"TARGETB {RUN_ID}",
        "nombre": "TARGETB",
        "apellido": RUN_ID,
        "is_archived": False,
        "created_by": pastor_uid,
        "person_number": f"TEST_{uuid.uuid4().hex[:12]}",
        "idempotency_key": f"TEST_{uuid.uuid4().hex}",
        "created_at": datetime.now(timezone.utc),
    })
    target_b_pid = str(target_b.inserted_id)
    db.persons.update_one({"_id": target_b.inserted_id}, {"$set": {"person_id": target_b_pid}})

    # Global-access via capability / library manager
    u_reports = _make_user(db, email=f"test_snap_reports_{RUN_ID}@example.com", rol="lider",
                            capabilities=["library.deliver", "library.reports.read"],
                            person_display=f"Reports {RUN_ID}")
    u_finance_r = _make_user(db, email=f"test_snap_finr_{RUN_ID}@example.com", rol="lider",
                              capabilities=["library.deliver", "finance.read"],
                              privilege_groups=[FINANCE_PRIVILEGE_GROUP],
                              person_display=f"FinanceR {RUN_ID}")
    u_finance_m = _make_user(db, email=f"test_snap_finm_{RUN_ID}@example.com", rol="lider",
                              capabilities=["library.deliver", "finance.manage"],
                              privilege_groups=[FINANCE_PRIVILEGE_GROUP],
                              person_display=f"FinanceM {RUN_ID}")
    u_cat = _make_user(db, email=f"test_snap_cat_{RUN_ID}@example.com", rol="lider",
                        capabilities=["library.catalog.manage"],
                        person_display=f"Catalog {RUN_ID}")
    u_inv = _make_user(db, email=f"test_snap_inv_{RUN_ID}@example.com", rol="lider",
                        capabilities=["library.inventory.manage"],
                        person_display=f"Inventory {RUN_ID}")

    # Relationship-based access users (plain líder LIBRARY_DELIVER only)
    u_mentor = _make_user(db, email=f"test_snap_mentor_{RUN_ID}@example.com", rol="lider",
                          capabilities=["library.deliver"],
                          person_display=f"Mentor {RUN_ID}")
    u_teacher = _make_user(db, email=f"test_snap_teacher_{RUN_ID}@example.com", rol="lider",
                           capabilities=["library.deliver"],
                           person_display=f"Teacher {RUN_ID}")
    u_consol = _make_user(db, email=f"test_snap_consol_{RUN_ID}@example.com", rol="lider",
                          capabilities=["library.deliver"],
                          person_display=f"Consol {RUN_ID}")

    # Plain líder with NO relationship (negative)
    u_plain = _make_user(db, email=f"test_snap_plain_{RUN_ID}@example.com", rol="lider",
                         capabilities=["library.deliver"],
                         person_display=f"Plain {RUN_ID}")

    # Persona (no library capability at all)
    u_persona = _make_user(db, email=f"test_snap_persona_{RUN_ID}@example.com", rol="persona",
                           capabilities=[],
                           person_display=f"Persona {RUN_ID}")

    # process_enrollments giving relationships to TARGET only (NOT to TARGET_B)
    now = datetime.now(timezone.utc)
    db.process_enrollments.insert_many([
        {"enrollment_id": f"enr_mentor_{RUN_ID}", "person_id": target_pid,
         "mentor_person_id": u_mentor["person_id"], "process_key": "discipulado_1",
         "status": "active", "created_at": now},
        {"enrollment_id": f"enr_teacher_{RUN_ID}", "person_id": target_pid,
         "responsible_person_id": u_teacher["person_id"], "process_key": "discipulado_2",
         "status": "active", "created_at": now},
        {"enrollment_id": f"enr_consol_{RUN_ID}", "person_id": target_pid,
         "responsible_person_id": u_consol["person_id"], "process_key": "consolidation",
         "status": "active", "created_at": now},
    ])

    ctx = {
        "target_pid": target_pid,
        "target_b_pid": target_b_pid,
        "u_reports": u_reports, "u_finance_r": u_finance_r, "u_finance_m": u_finance_m,
        "u_cat": u_cat, "u_inv": u_inv,
        "u_mentor": u_mentor, "u_teacher": u_teacher, "u_consol": u_consol,
        "u_plain": u_plain, "u_persona": u_persona,
    }
    yield ctx

    # ---- cleanup ----
    emails = [u["email"] for u in [u_reports, u_finance_r, u_finance_m, u_cat, u_inv,
                                   u_mentor, u_teacher, u_consol, u_plain, u_persona]]
    db.users.delete_many({"email": {"$in": emails}})
    person_ids = [ctx["target_pid"], ctx["target_b_pid"]] + [u["person_id"] for u in
        [u_reports, u_finance_r, u_finance_m, u_cat, u_inv, u_mentor, u_teacher, u_consol, u_plain, u_persona]]
    for pid in person_ids:
        try:
            db.persons.delete_one({"_id": ObjectId(pid)})
        except Exception:
            db.persons.delete_one({"person_id": pid})
    db.process_enrollments.delete_many({"enrollment_id": {"$regex": f"_{RUN_ID}$"}})


def _token_for(user):
    return _login(user["email"], PASSWORD)["token"]


SNAP_URL = lambda pid: f"{API}/library/scan/persons/{pid}/library-snapshot"

# ------------- Tests -------------------------------------------------------

class TestGlobalAccessRoles:
    def test_pastor_global(self, pastor, seed):
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(pastor["token"]), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["person_id"] == seed["target_pid"]
        assert "materials" in body and "pending_payments" in body

    def test_library_catalog_manager_global(self, seed):
        t = _token_for(seed["u_cat"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 200, r.text

    def test_library_inventory_manager_global(self, seed):
        t = _token_for(seed["u_inv"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 200, r.text

    def test_library_reports_read_global(self, seed):
        t = _token_for(seed["u_reports"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 200, r.text

    def test_finance_read_global(self, seed):
        t = _token_for(seed["u_finance_r"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 200, r.text

    def test_finance_manage_global(self, seed):
        t = _token_for(seed["u_finance_m"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 200, r.text


class TestRelationshipAccess:
    def test_mentor_relationship_grants_access(self, seed):
        t = _token_for(seed["u_mentor"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 200, r.text

    def test_responsible_teacher_relationship_grants_access(self, seed):
        t = _token_for(seed["u_teacher"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 200, r.text

    def test_consolidation_responsible_grants_access(self, seed):
        t = _token_for(seed["u_consol"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 200, r.text


class TestNegativeAccess:
    def test_plain_lider_no_relationship_403(self, seed):
        t = _token_for(seed["u_plain"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 403, r.text

    def test_persona_no_library_deliver_blocked_at_dependency(self, seed):
        t = _token_for(seed["u_persona"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 403, r.text

    def test_person_id_tampering_403_on_unrelated_target(self, seed):
        """Mentor of TARGET tampers URL to TARGETB — must 403 while TARGET still 200."""
        t = _token_for(seed["u_mentor"])
        r_a = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r_a.status_code == 200, r_a.text
        r_b = requests.get(SNAP_URL(seed["target_b_pid"]), headers=_h(t), timeout=15)
        assert r_b.status_code == 403, r_b.text

    def test_scan_resolve_person_does_not_bypass_snapshot_rbac(self, seed):
        """Plain líder can resolve-person (that endpoint is neutral) but snapshot still 403."""
        t = _token_for(seed["u_plain"])
        # resolve using the target person_id itself as code (canonical_person path)
        r_resolve = requests.post(f"{API}/library/scan/resolve-person",
                                   headers=_h(t), json={"code": seed["target_pid"]}, timeout=15)
        assert r_resolve.status_code == 200, r_resolve.text
        resolved_pid = r_resolve.json()["person_id"]
        assert resolved_pid == seed["target_pid"]
        r_snap = requests.get(SNAP_URL(resolved_pid), headers=_h(t), timeout=15)
        assert r_snap.status_code == 403, r_snap.text


class TestDataExposure:
    def test_only_allowed_fields_in_snapshot_payload(self, seed):
        """Verify the snapshot response never leaks unrelated Finanzas fields."""
        t = _token_for(seed["u_mentor"])
        r = requests.get(SNAP_URL(seed["target_pid"]), headers=_h(t), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"person_id", "display_name", "materials", "pending_payments"}, body.keys()
        for m in body["materials"]:
            assert set(m.keys()).issubset({"book_id", "book_name", "cover_file_id", "process_key", "status"}), m
        forbidden = {"diezmo", "diezmos", "ofrenda", "ofrendas", "contribution", "contributions",
                     "account_balance", "tithe", "tithes", "donations"}
        # Recursive scan for forbidden keys
        def _scan(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    assert k.lower() not in forbidden, f"forbidden field leaked: {k}"
                    _scan(v)
            elif isinstance(obj, list):
                for v in obj:
                    _scan(v)
        _scan(body)
        # pending_payments allowed keys
        for p in body["pending_payments"]:
            assert set(p.keys()).issubset({"movement_id", "book_name", "occurred_at",
                                             "list_price_cents", "amount_paid_cents",
                                             "balance_cents", "payment_status"}), p
