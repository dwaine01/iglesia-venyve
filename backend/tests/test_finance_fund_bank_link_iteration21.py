"""Finance fund-to-bank-account linking + deposit routing hard block (Iteration 21)."""
import os
import uuid
from datetime import date

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PASTOR_EMAIL = "qa.baptismui53.pastor@example.com"
PASTOR_PASSWORD = "QaBaptismUI53!"


@pytest.fixture(scope="module")
def pastor_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Nuevo flujo: la pastora solo consulta; registra y deposita el equipo de Finanzas.
    from tests.conftest import finance_team_token
    token = finance_team_token(BASE_URL)
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def catalog(pastor_client):
    r = pastor_client.get(f"{BASE_URL}/api/finance/catalog", timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


# Catalog seed: BUILDING fund linked to 1030 Banco Chase - Pro-Templo
def test_building_fund_has_chase_default_bank_account(catalog):
    funds = {f["code"]: f for f in catalog["funds"]}
    accounts_by_id = {a["account_id"]: a for a in catalog["accounts"]}
    assert "BUILDING" in funds, "BUILDING fund missing"
    chase_id = funds["BUILDING"].get("default_bank_account_id")
    assert chase_id, "BUILDING must have default_bank_account_id auto-seeded"
    chase = accounts_by_id.get(chase_id)
    assert chase is not None
    assert chase["code"] == "1030"
    assert chase["name"] == "Banco Chase - Pro-Templo"
    assert chase["account_type"] == "asset"


def test_other_funds_have_no_default_bank_account(catalog):
    funds = {f["code"]: f for f in catalog["funds"]}
    for code in ("GENERAL", "MISSIONS"):
        assert code in funds
        assert not funds[code].get("default_bank_account_id"), f"{code} should NOT have default bank account"


# PUT /funds/{id}/bank-account
def test_put_fund_bank_account_unlink_and_relink(pastor_client, catalog):
    funds = {f["code"]: f for f in catalog["funds"]}
    accounts = {a["code"]: a for a in catalog["accounts"]}
    building = funds["BUILDING"]
    chase_id = accounts["1030"]["account_id"]
    bank_principal_id = accounts["1020"]["account_id"]

    # unlink
    r = pastor_client.put(
        f"{BASE_URL}/api/finance/funds/{building['fund_id']}/bank-account",
        json={"bank_account_id": None},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("default_bank_account_id") in (None, "")

    # relink to 1020 Banco principal (valid asset)
    r = pastor_client.put(
        f"{BASE_URL}/api/finance/funds/{building['fund_id']}/bank-account",
        json={"bank_account_id": bank_principal_id},
        timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["default_bank_account_id"] == bank_principal_id

    # restore to chase 1030
    r = pastor_client.put(
        f"{BASE_URL}/api/finance/funds/{building['fund_id']}/bank-account",
        json={"bank_account_id": chase_id},
        timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["default_bank_account_id"] == chase_id


def test_put_fund_bank_account_rejects_non_asset(pastor_client, catalog):
    funds = {f["code"]: f for f in catalog["funds"]}
    accounts = {a["code"]: a for a in catalog["accounts"]}
    revenue_id = accounts["4000"]["account_id"]  # revenue, not asset
    r = pastor_client.put(
        f"{BASE_URL}/api/finance/funds/{funds['GENERAL']['fund_id']}/bank-account",
        json={"bank_account_id": revenue_id},
        timeout=20,
    )
    assert r.status_code == 422, r.text


def test_put_fund_bank_account_rejects_invalid_id(pastor_client, catalog):
    funds = {f["code"]: f for f in catalog["funds"]}
    r = pastor_client.put(
        f"{BASE_URL}/api/finance/funds/{funds['GENERAL']['fund_id']}/bank-account",
        json={"bank_account_id": "nonexistent-id-" + uuid.uuid4().hex},
        timeout=20,
    )
    assert r.status_code == 422


# Deposit hard block
@pytest.fixture(scope="module")
def contrib_ids(pastor_client, catalog):
    """Create one BUILDING contribution and one GENERAL/tithe contribution (anonymous)."""
    funds = {f["code"]: f for f in catalog["funds"]}
    today = date.today().isoformat()
    created = {}
    for code, c_type, amount in (("BUILDING", "building", 1500), ("GENERAL", "tithe", 2000)):
        payload = {
            "anonymous": True,
            "contribution_type": c_type,
            "amount_cents": amount,
            "received_date": today,
            "payment_method": "cash",
            "allocations": [{"fund_id": funds[code]["fund_id"], "amount_cents": amount, "contribution_type": c_type}],
            "reference": f"TEST_iter21_{code}_{uuid.uuid4().hex[:6]}",
        }
        r = pastor_client.post(f"{BASE_URL}/api/finance/contributions", json=payload, timeout=20)
        assert r.status_code == 201, f"{code}: {r.status_code} {r.text}"
        created[code] = r.json()["contribution_id"]
    return created


def test_deposit_mixed_funds_blocked_409(pastor_client, catalog, contrib_ids):
    """Trying to deposit BUILDING+GENERAL contributions into Banco principal must 409."""
    accounts = {a["code"]: a for a in catalog["accounts"]}
    bank_principal_id = accounts["1020"]["account_id"]
    payload = {
        "deposit_date": date.today().isoformat(),
        "bank_account_id": bank_principal_id,
        "contribution_ids": [contrib_ids["BUILDING"], contrib_ids["GENERAL"]],
        "reference": "TEST_iter21_blocked",
    }
    r = pastor_client.post(f"{BASE_URL}/api/finance/deposits", json=payload, timeout=20)
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"
    detail = r.json().get("detail", "")
    assert "Pro-Templo" in detail
    assert "1030" in detail
    assert "Banco Chase" in detail


def test_deposit_building_only_into_chase_succeeds(pastor_client, catalog, contrib_ids):
    accounts = {a["code"]: a for a in catalog["accounts"]}
    chase_id = accounts["1030"]["account_id"]
    r = pastor_client.post(
        f"{BASE_URL}/api/finance/deposits",
        json={
            "deposit_date": date.today().isoformat(),
            "bank_account_id": chase_id,
            "contribution_ids": [contrib_ids["BUILDING"]],
            "reference": "TEST_iter21_building_ok",
        },
        timeout=20,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["bank_account_id"] == chase_id
    assert data["total_cents"] == 1500


def test_deposit_tithe_only_into_any_account_succeeds(pastor_client, catalog, contrib_ids):
    """GENERAL fund has no designated account → any asset account is OK."""
    accounts = {a["code"]: a for a in catalog["accounts"]}
    bank_principal_id = accounts["1020"]["account_id"]
    r = pastor_client.post(
        f"{BASE_URL}/api/finance/deposits",
        json={
            "deposit_date": date.today().isoformat(),
            "bank_account_id": bank_principal_id,
            "contribution_ids": [contrib_ids["GENERAL"]],
            "reference": "TEST_iter21_tithe_ok",
        },
        timeout=20,
    )
    assert r.status_code == 201, r.text


# Regression: person contributions endpoint still works
def test_person_contributions_endpoint_regression(pastor_client):
    # Find any contribution with a person_id
    r = pastor_client.get(f"{BASE_URL}/api/finance/contributions", timeout=20)
    assert r.status_code == 200
    items = r.json().get("items", [])
    person_id = next((it.get("person_id") for it in items if it.get("person_id")), None)
    if not person_id:
        pytest.skip("No linked person contributions available for regression check")
    r = pastor_client.get(f"{BASE_URL}/api/finance/persons/{person_id}/contributions", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data
    assert "total_cents" in data
    assert isinstance(data["items"], list)
