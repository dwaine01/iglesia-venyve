"""Regresión P0 Finanzas: contribuciones, idempotencia, RBAC, workflow y seguridad básica."""
import os
from datetime import date
from uuid import uuid4

import pytest
import requests
from pymongo import MongoClient


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
LEADER = ("coreqa.leader@example.com", "CoreQA2026!Leader")
MEMBER = ("coreqa.member@example.com", "CoreQA2026!Member")


def api(path: str) -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is required")
    return f"{BASE_URL}{path}"


def login(credentials: tuple[str, str]) -> tuple[str, dict]:
    response = requests.post(
        api("/api/auth/login"),
        json={"email": credentials[0], "password": credentials[1]},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["token"], body["user"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def list_governance_users(token: str) -> list[dict]:
    response = requests.get(api("/api/core/governance/users"), headers=headers(token), timeout=30)
    assert response.status_code == 200, response.text
    return response.json().get("items", [])


def find_user(users: list[dict], email: str) -> dict:
    for item in users:
        if item.get("email", "").lower() == email.lower():
            return item
    raise AssertionError(f"User not found in governance list: {email}")


def update_access(token: str, user_id: str, payload: dict) -> requests.Response:
    return requests.put(
        api(f"/api/core/governance/users/{user_id}/access"),
        headers=headers(token),
        json=payload,
        timeout=30,
    )


@pytest.fixture
def finance_state():
    # Módulo: setup QA temporal y cleanup estricto de fixtures QA creados por esta regresión
    pastor_token, _ = login(PASTOR)
    users = list_governance_users(pastor_token)
    leader = find_user(users, LEADER[0])
    member = find_user(users, MEMBER[0])

    original_leader = {
        "user_id": leader["user_id"],
        "access_level": leader.get("access_level") or leader.get("rol"),
        "is_active": leader.get("is_active", True),
        "privilege_groups": leader.get("privilege_groups") or ["membership"],
        "capabilities": leader.get("capabilities") or [],
    }
    original_member = {
        "user_id": member["user_id"],
        "access_level": member.get("access_level") or member.get("rol"),
        "is_active": member.get("is_active", True),
        "privilege_groups": member.get("privilege_groups") or ["membership"],
        "capabilities": member.get("capabilities") or [],
    }

    reference_prefix = f"QA-I15-FIN-{uuid4().hex[:8]}"
    fund_code = f"QA15{uuid4().hex[:6]}".upper()

    try:
        yield {
            "pastor_token": pastor_token,
            "leader": leader,
            "member": member,
            "original_leader": original_leader,
            "original_member": original_member,
            "reference_prefix": reference_prefix,
            "fund_code": fund_code,
        }
    finally:
        # Restore leader access
        restore_leader = update_access(
            pastor_token,
            original_leader["user_id"],
            {
                "access_level": original_leader["access_level"],
                "is_active": original_leader["is_active"],
                "privilege_groups": original_leader["privilege_groups"],
                "capabilities": original_leader["capabilities"],
            },
        )
        assert restore_leader.status_code == 200, restore_leader.text

        # Restore member access
        restore_member = update_access(
            pastor_token,
            original_member["user_id"],
            {
                "access_level": original_member["access_level"],
                "is_active": original_member["is_active"],
                "privilege_groups": original_member["privilege_groups"],
                "capabilities": original_member["capabilities"],
            },
        )
        assert restore_member.status_code == 200, restore_member.text

        # DB cleanup only for this run QA fixtures
        client = MongoClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        contributions = list(
            db.finance_contributions.find(
                {"reference": {"$regex": f"^{reference_prefix}"}},
                {"_id": 0, "contribution_id": 1, "journal_entry_id": 1},
            )
        )
        contribution_ids = [item["contribution_id"] for item in contributions]
        contribution_journal_ids = [
            item["journal_entry_id"] for item in contributions if item.get("journal_entry_id")
        ]
        standalone_journals = list(
            db.finance_journal_entries.find(
                {"memo": {"$regex": f"^{reference_prefix}"}},
                {"_id": 0, "entry_id": 1},
            )
        )
        journal_ids = contribution_journal_ids + [
            item["entry_id"] for item in standalone_journals
        ]
        qa_funds = list(
            db.finance_funds.find({"code": fund_code}, {"_id": 0, "fund_id": 1})
        )
        fund_ids = [item["fund_id"] for item in qa_funds]

        if contribution_ids:
            db.finance_contributions.delete_many({"contribution_id": {"$in": contribution_ids}})
        if journal_ids:
            db.finance_journal_entries.delete_many({"entry_id": {"$in": journal_ids}})
        audit_entity_ids = contribution_ids + journal_ids + fund_ids
        if audit_entity_ids:
            db.finance_audit_events.delete_many({"entity_id": {"$in": audit_entity_ids}})

        db.finance_funds.delete_many({"code": fund_code})
        client.close()


def _catalog(token: str) -> dict:
    response = requests.get(api("/api/finance/catalog"), headers=headers(token), timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "funds" in data and "accounts" in data
    assert all("_id" not in item for item in data["funds"])
    assert all("_id" not in item for item in data["accounts"])
    return data


def test_finance_p0_regression_suite(finance_state):
    # Módulo: flujo principal P0 (contribuciones, idempotencia, fondos, workflow, RBAC y seguridad)
    pastor_token = finance_state["pastor_token"]
    reference_prefix = finance_state["reference_prefix"]
    fund_code = finance_state["fund_code"]
    users = list_governance_users(pastor_token)
    leader_user = find_user(users, LEADER[0])
    member_user = find_user(users, MEMBER[0])

    # RBAC baseline: member without finance capability gets 403
    member_token, _ = login(MEMBER)
    forbidden_catalog = requests.get(api("/api/finance/catalog"), headers=headers(member_token), timeout=30)
    assert forbidden_catalog.status_code == 403, forbidden_catalog.text

    # Public security: JWT required
    no_auth_catalog = requests.get(api("/api/finance/catalog"), timeout=30)
    assert no_auth_catalog.status_code == 401, no_auth_catalog.text

    # Grant finance to leader+member for workflow checks; pastor can grant restricted groups
    leader_grant = update_access(
        pastor_token,
        leader_user["user_id"],
        {
            "access_level": leader_user.get("access_level") or leader_user.get("rol"),
            "is_active": True,
            "privilege_groups": ["membership", "finance"],
        },
    )
    assert leader_grant.status_code == 200, leader_grant.text
    leader_capabilities = leader_grant.json().get("capabilities", [])
    assert "finance.read" in leader_capabilities and "finance.manage" in leader_capabilities

    member_grant = update_access(
        pastor_token,
        member_user["user_id"],
        {
            "access_level": member_user.get("access_level") or member_user.get("rol"),
            "is_active": True,
            "privilege_groups": ["membership", "finance"],
        },
    )
    assert member_grant.status_code == 200, member_grant.text
    member_capabilities = member_grant.json().get("capabilities", [])
    assert "finance.read" in member_capabilities and "finance.manage" in member_capabilities

    # Non-pastor cannot grant restricted groups
    leader_token, _ = login(LEADER)
    blocked_grant = update_access(
        leader_token,
        member_user["user_id"],
        {
            "access_level": member_user.get("access_level") or member_user.get("rol"),
            "is_active": True,
            "privilege_groups": ["membership", "finance"],
        },
    )
    assert blocked_grant.status_code == 403, blocked_grant.text

    catalog = _catalog(pastor_token)
    assert len(catalog["funds"]) >= 2
    fund_a = catalog["funds"][0]["fund_id"]
    fund_b = catalog["funds"][1]["fund_id"]

    # Manual contribution idempotency fix: two consecutive manual inserts without external_transaction_id
    common = {
        "anonymous": True,
        "contribution_type": "offering",
        "received_date": date.today().isoformat(),
        "payment_method": "cash",
        "source": "manual",
    }
    manual_one = requests.post(
        api("/api/finance/contributions"),
        headers=headers(pastor_token),
        json={
            **common,
            "reference": f"{reference_prefix}-MANUAL-1",
            "amount_cents": 100,
            "allocations": [{"fund_id": fund_a, "amount_cents": 100}],
        },
        timeout=30,
    )
    assert manual_one.status_code == 201, manual_one.text

    manual_two_split = requests.post(
        api("/api/finance/contributions"),
        headers=headers(pastor_token),
        json={
            **common,
            "reference": f"{reference_prefix}-MANUAL-2",
            "amount_cents": 300,
            "allocations": [
                {"fund_id": fund_a, "amount_cents": 100},
                {"fund_id": fund_b, "amount_cents": 200},
            ],
        },
        timeout=30,
    )
    assert manual_two_split.status_code == 201, manual_two_split.text
    manual_two_body = manual_two_split.json()
    assert manual_two_body["amount_cents"] == 300
    assert len(manual_two_body["allocations"]) == 2

    # Verify split created balanced journal
    journal_id = manual_two_body["journal_entry_id"]
    journals = requests.get(api("/api/finance/journals"), headers=headers(pastor_token), timeout=30)
    assert journals.status_code == 200, journals.text
    target = next(item for item in journals.json().get("items", []) if item["entry_id"] == journal_id)
    assert target["total_debit_cents"] == target["total_credit_cents"] == 300
    assert all("_id" not in line for line in [target])

    # External idempotency true duplicate: first 201, second 409
    external_id = f"{reference_prefix}-EXT-1"
    external_payload = {
        "anonymous": True,
        "contribution_type": "offering",
        "received_date": date.today().isoformat(),
        "payment_method": "cash",
        "reference": f"{reference_prefix}-CSV-1",
        "amount_cents": 250,
        "allocations": [{"fund_id": fund_a, "amount_cents": 250}],
        "source": "csv",
        "external_transaction_id": external_id,
    }
    ext_first = requests.post(api("/api/finance/contributions"), headers=headers(pastor_token), json=external_payload, timeout=30)
    ext_dup = requests.post(api("/api/finance/contributions"), headers=headers(pastor_token), json=external_payload, timeout=30)
    assert ext_first.status_code == 201, ext_first.text
    assert ext_dup.status_code == 409, ext_dup.text

    # csv/pushpay without external id must fail 422
    csv_missing = requests.post(
        api("/api/finance/contributions"),
        headers=headers(pastor_token),
        json={
            **external_payload,
            "reference": f"{reference_prefix}-CSV-MISS",
            "external_transaction_id": "",
        },
        timeout=30,
    )
    pushpay_missing = requests.post(
        api("/api/finance/contributions"),
        headers=headers(pastor_token),
        json={
            **external_payload,
            "source": "pushpay",
            "reference": f"{reference_prefix}-PUSHPAY-MISS",
            "external_transaction_id": None,
        },
        timeout=30,
    )
    assert csv_missing.status_code == 422, csv_missing.text
    assert pushpay_missing.status_code == 422, pushpay_missing.text

    # Funds create unique then duplicate
    unique_fund = requests.post(
        api("/api/finance/funds"),
        headers=headers(pastor_token),
        json={
            "code": fund_code,
            "name": f"{reference_prefix} Fondo QA",
            "restriction_type": "unrestricted",
            "purpose": "QA only",
        },
        timeout=30,
    )
    duplicate_fund = requests.post(
        api("/api/finance/funds"),
        headers=headers(pastor_token),
        json={
            "code": fund_code,
            "name": f"{reference_prefix} Fondo QA DUP",
            "restriction_type": "unrestricted",
            "purpose": "QA duplicate",
        },
        timeout=30,
    )
    assert unique_fund.status_code == 201, unique_fund.text
    assert duplicate_fund.status_code == 409, duplicate_fund.text

    # Workflow segregation: preparer(leader) -> reviewer(member) -> approve(pastor)
    leader_token, _ = login(LEADER)
    member_token, _ = login(MEMBER)
    journal_create = requests.post(
        api("/api/finance/journals"),
        headers=headers(leader_token),
        json={
            "entry_date": date.today().isoformat(),
            "memo": f"{reference_prefix} workflow",
            "lines": [
                {
                    "account_id": catalog["accounts"][0]["account_id"],
                    "fund_id": fund_a,
                    "debit_cents": 500,
                    "credit_cents": 0,
                    "description": "QA debit",
                },
                {
                    "account_id": catalog["accounts"][0]["account_id"],
                    "fund_id": fund_a,
                    "debit_cents": 0,
                    "credit_cents": 500,
                    "description": "QA credit",
                },
            ],
        },
        timeout=30,
    )
    assert journal_create.status_code == 201, journal_create.text
    entry_id = journal_create.json()["entry_id"]

    submit = requests.post(api(f"/api/finance/journals/{entry_id}/submit"), headers=headers(leader_token), timeout=30)
    self_review = requests.post(api(f"/api/finance/journals/{entry_id}/review"), headers=headers(leader_token), timeout=30)
    review = requests.post(api(f"/api/finance/journals/{entry_id}/review"), headers=headers(member_token), timeout=30)
    member_approve = requests.post(api(f"/api/finance/journals/{entry_id}/approve"), headers=headers(member_token), timeout=30)
    pastor_approve = requests.post(api(f"/api/finance/journals/{entry_id}/approve"), headers=headers(pastor_token), timeout=30)
    assert submit.status_code == 200, submit.text
    assert self_review.status_code == 403, self_review.text
    assert review.status_code == 200, review.text
    assert member_approve.status_code == 403, member_approve.text
    assert pastor_approve.status_code == 200, pastor_approve.text
    assert pastor_approve.json()["status"] == "posted"

    # Pushpay must remain BLOCKED/MOCKED until real credentials
    pushpay_status = requests.get(api("/api/finance/integrations/pushpay"), headers=headers(pastor_token), timeout=30)
    pushpay_sync = requests.post(api("/api/finance/integrations/pushpay/sync"), headers=headers(pastor_token), timeout=30)
    assert pushpay_status.status_code == 200, pushpay_status.text
    status_data = pushpay_status.json()
    assert status_data["status"] == "blocked_credentials_required"
    assert status_data["configured"] is False
    # verify no actual secret values exposed
    as_text = str(status_data)
    for secret_key in [
        "PUSHPAY_CLIENT_ID",
        "PUSHPAY_CLIENT_SECRET",
        "PUSHPAY_ORGANIZATION_KEY",
        "PUSHPAY_MERCHANT_KEY",
    ]:
        secret_val = os.environ.get(secret_key)
        if secret_val:
            assert secret_val not in as_text

    assert pushpay_sync.status_code == 503, pushpay_sync.text
    assert "bloqueado" in pushpay_sync.text.lower() or "sandbox" in pushpay_sync.text.lower()
