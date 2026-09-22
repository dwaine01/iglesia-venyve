import os
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

from access_control import BOARD_ACCESS, FINANCE_CAPABILITIES, access_defaults_for_role


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
DB = MongoClient(BACKEND_ENV["MONGO_URL"])[BACKEND_ENV["DB_NAME"]]
PASSWORD = "QaStrictRbac2026!"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(email):
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": PASSWORD},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    return response.json()["token"], response.json()["user"]


def create_account(label, access_level="lider", groups=None, extra_capabilities=None, role="lider"):
    user_id, person_id = ObjectId(), ObjectId()
    email = f"qa.iter40.{label}.{uuid4().hex[:8]}@example.com"
    now = datetime.now(timezone.utc)
    defaults = access_defaults_for_role("pastora" if role == "pastora" else "lider")
    capabilities = sorted(set([*defaults["capabilities"], *(extra_capabilities or [])]))
    DB.persons.insert_one(
        {
            "_id": person_id,
            "person_number": f"VV-I40-{str(person_id)[-6:].upper()}",
            "nombre": "QA",
            "apellido": label.title(),
            "search_key": f"qa {label}",
            "idempotency_key": f"qa:iter40:{email}",
            "auth_user_id": str(user_id),
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
    )
    DB.users.insert_one(
        {
            "_id": user_id,
            "nombre": f"QA {label.title()}",
            "email": email,
            "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "rol": role,
            "access_level": "pastor" if role == "pastora" else access_level,
            "person_id": str(person_id),
            "capabilities": capabilities,
            "access_scope": defaults["access_scope"] if role == "pastora" else {"persons": "all" if access_level == "coordinador_general" else "created_by"},
            "privilege_groups": groups or [],
            "is_active": True,
            "token_version": 1,
            "access_policy_version": 21,
            "must_change_password": False,
            "onboarding_required": False,
            "created_at": now,
            "updated_at": now,
        }
    )
    return {"user_id": str(user_id), "person_id": str(person_id), "email": email}


@pytest.fixture(scope="module")
def rbac_matrix():
    accounts = {
        "pastora": create_account("pastora", role="pastora"),
        "coordinator": create_account(
            "coordinator",
            access_level="coordinador_general",
            extra_capabilities=[*FINANCE_CAPABILITIES, BOARD_ACCESS],
        ),
        "finance": create_account("finance", groups=["finance"], extra_capabilities=FINANCE_CAPABILITIES),
        "board": create_account("board"),
        "multi": create_account(
            "multi",
            groups=["membership", "finance"],
            extra_capabilities=FINANCE_CAPABILITIES,
        ),
    }
    tokens = {key: login(value["email"])[0] for key, value in accounts.items()}
    created_memberships = []
    created_vendors = []
    note_ids = []
    for key, position in [("board", "secretary"), ("multi", "treasurer")]:
        response = requests.post(
            f"{BASE_URL}/api/board/members",
            headers=auth(tokens["pastora"]),
            json={
                "person_id": accounts[key]["person_id"],
                "position_key": position,
                "voting_rights": True,
                "permissions": [],
                "supervised_door_keys": [],
                "ministry_ids": [],
            },
            timeout=30,
        )
        assert response.status_code == 201, response.text
        created_memberships.append(response.json()["membership_id"])
        tokens[key] = login(accounts[key]["email"])[0]
    now = datetime.now(timezone.utc)
    for category, text in [("general", "nota general QA I40"), ("pastoral", "nota pastoral privada QA I40")]:
        note_id = str(uuid4())
        DB.person_notes.insert_one(
            {
                "_id": note_id,
                "note_id": note_id,
                "person_id": accounts["multi"]["person_id"],
                "categoria": category,
                "contenido": text,
                "created_at": now,
                "updated_at": now,
            }
        )
        note_ids.append(note_id)
    state = {
        "accounts": accounts,
        "tokens": tokens,
        "memberships": created_memberships,
        "vendors": created_vendors,
        "notes": note_ids,
    }
    yield state
    DB.finance_vendors.delete_many({"vendor_id": {"$in": created_vendors}})
    DB.person_notes.delete_many({"_id": {"$in": note_ids}})
    DB.door_assignments.delete_many({"source_board_membership_id": {"$in": created_memberships}})
    DB.board_memberships.delete_many({"membership_id": {"$in": created_memberships}})
    user_ids = [ObjectId(item["user_id"]) for item in accounts.values()]
    person_object_ids = [ObjectId(item["person_id"]) for item in accounts.values()]
    DB.users.delete_many({"_id": {"$in": user_ids}})
    DB.persons.delete_many({"_id": {"$in": person_object_ids}})


def test_pastora_has_global_finance_board_and_private_profile_access(rbac_matrix):
    state = rbac_matrix
    token = state["tokens"]["pastora"]
    target = state["accounts"]["multi"]["person_id"]
    assert requests.get(f"{BASE_URL}/api/finance/dashboard", headers=auth(token), timeout=30).status_code == 200
    assert requests.get(f"{BASE_URL}/api/dashboard/role-based", headers=auth(token), timeout=30).status_code == 200
    assert requests.get(f"{BASE_URL}/api/pastor/pastors", headers=auth(token), timeout=30).status_code == 200
    access = requests.get(f"{BASE_URL}/api/board/access", headers=auth(token), timeout=30)
    assert access.status_code == 200 and access.json()["full_access"] is True
    assert requests.get(f"{BASE_URL}/api/board", headers=auth(token), timeout=30).status_code == 200
    private_finance = requests.get(f"{BASE_URL}/api/finance/persons/{target}/contributions", headers=auth(token), timeout=30)
    assert private_finance.status_code == 200
    profile = requests.get(f"{BASE_URL}/api/core/persons/{target}/profile", headers=auth(token), timeout=30)
    assert profile.status_code == 200 and profile.json()["private_finance_can_read"] is True


def test_coordinator_defaults_deny_even_with_stale_restricted_capabilities(rbac_matrix):
    state = rbac_matrix
    token = state["tokens"]["coordinator"]
    target = state["accounts"]["multi"]["person_id"]
    assert requests.get(f"{BASE_URL}/api/finance/dashboard", headers=auth(token), timeout=30).status_code == 403
    assert requests.get(f"{BASE_URL}/api/finance/persons/{target}/contributions", headers=auth(token), timeout=30).status_code == 403
    access = requests.get(f"{BASE_URL}/api/board/access", headers=auth(token), timeout=30)
    assert access.status_code == 200 and access.json()["allowed"] is False
    assert requests.get(f"{BASE_URL}/api/board", headers=auth(token), timeout=30).status_code == 403
    _, user = login(state["accounts"]["coordinator"]["email"])
    assert "finance.read" not in user["capabilities"]
    assert "finance.manage" not in user["capabilities"]
    assert "board.access" not in user["capabilities"]


def test_finance_role_operates_module_but_cannot_open_board_or_private_profile_finance(rbac_matrix):
    state = rbac_matrix
    token = state["tokens"]["finance"]
    person_id = state["accounts"]["finance"]["person_id"]
    assert requests.get(f"{BASE_URL}/api/finance/dashboard", headers=auth(token), timeout=30).status_code == 200
    vendor = requests.post(
        f"{BASE_URL}/api/finance/vendors",
        headers=auth(token),
        json={"name": f"QA Vendor I40 {uuid4().hex[:6]}", "vendor_type": "organization"},
        timeout=30,
    )
    assert vendor.status_code == 201, vendor.text
    state["vendors"].append(vendor.json()["vendor_id"])
    assert requests.get(f"{BASE_URL}/api/finance/contributors/{person_id}", headers=auth(token), timeout=30).status_code == 200
    assert requests.get(f"{BASE_URL}/api/finance/persons/{person_id}/contributions", headers=auth(token), timeout=30).status_code == 403
    assert requests.get(f"{BASE_URL}/api/board", headers=auth(token), timeout=30).status_code == 403
    profile = requests.get(f"{BASE_URL}/api/core/persons/{person_id}/profile", headers=auth(token), timeout=30)
    assert profile.status_code == 200 and profile.json()["private_finance_can_read"] is False


def test_board_member_has_functional_access_without_finance(rbac_matrix):
    state = rbac_matrix
    token = state["tokens"]["board"]
    access = requests.get(f"{BASE_URL}/api/board/access", headers=auth(token), timeout=30)
    assert access.status_code == 200 and access.json()["allowed"] is True
    assert access.json()["position_key"] == "secretary"
    assert requests.get(f"{BASE_URL}/api/board", headers=auth(token), timeout=30).status_code == 200
    assert requests.get(f"{BASE_URL}/api/finance/dashboard", headers=auth(token), timeout=30).status_code == 403


def test_multirole_is_union_but_never_inherits_pastoral_privacy(rbac_matrix):
    state = rbac_matrix
    token = state["tokens"]["multi"]
    person_id = state["accounts"]["multi"]["person_id"]
    assert requests.get(f"{BASE_URL}/api/finance/dashboard", headers=auth(token), timeout=30).status_code == 200
    assert requests.get(f"{BASE_URL}/api/board", headers=auth(token), timeout=30).status_code == 200
    assert requests.get(f"{BASE_URL}/api/finance/persons/{person_id}/contributions", headers=auth(token), timeout=30).status_code == 403
    profile = requests.get(f"{BASE_URL}/api/core/persons/{person_id}/profile", headers=auth(token), timeout=30)
    assert profile.status_code == 200
    body = profile.json()
    assert body["private_finance_can_read"] is False
    note_text = " ".join(str(item) for item in body.get("notas", []))
    assert "nota general QA I40" in note_text
    assert "nota pastoral privada QA I40" not in note_text


def test_board_requires_both_explicit_grant_and_active_membership(rbac_matrix):
    state = rbac_matrix
    board_user = state["accounts"]["board"]
    token = state["tokens"]["board"]
    DB.users.update_one({"_id": ObjectId(board_user["user_id"])}, {"$pull": {"capabilities": BOARD_ACCESS}})
    denied = requests.get(f"{BASE_URL}/api/board", headers=auth(token), timeout=30)
    assert denied.status_code == 403
    DB.users.update_one({"_id": ObjectId(board_user["user_id"])}, {"$addToSet": {"capabilities": BOARD_ACCESS}})
    assert requests.get(f"{BASE_URL}/api/board", headers=auth(token), timeout=30).status_code == 200