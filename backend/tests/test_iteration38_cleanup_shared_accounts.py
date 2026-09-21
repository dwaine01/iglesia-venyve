"""Iteración 38: limpieza de estado en cuentas QA compartidas."""

import os

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PASTOR_EMAIL = "coreqa.pastor@example.com"
PASTOR_PASSWORD = "CoreQA2026!Pastor"
LEADER_EMAIL = "coreqa.leader@example.com"
MEMBERSHIP_DIRECT_IMPORT = "membership.direct_import"


def _login(email: str, password: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    token = body.get("token")
    assert isinstance(token, str) and len(token) > 20
    return {"token": token, "body": body}


# Módulo: restauración de capability delegada temporal para no dejar residuos QA.
@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_revoke_direct_import_from_shared_coreqa_leader_if_present():
    pastor = _login(PASTOR_EMAIL, PASTOR_PASSWORD)
    users = requests.get(
        f"{BASE_URL}/api/core/governance/users",
        headers={"Authorization": f"Bearer {pastor['token']}"},
        timeout=30,
    )
    assert users.status_code == 200, users.text
    leader = next((item for item in users.json().get("items", []) if item.get("email") == LEADER_EMAIL), None)
    if not leader:
        pytest.skip("Shared QA leader account not present")

    capabilities = [item for item in (leader.get("capabilities") or []) if item != MEMBERSHIP_DIRECT_IMPORT]
    payload = {
        "access_level": leader.get("access_level") or leader.get("rol") or "lider",
        "is_active": bool(leader.get("is_active", True)),
        "privilege_groups": leader.get("privilege_groups") or [],
        "capabilities": capabilities,
    }
    update = requests.put(
        f"{BASE_URL}/api/core/governance/users/{leader['user_id']}/access",
        json=payload,
        headers={"Authorization": f"Bearer {pastor['token']}"},
        timeout=30,
    )
    assert update.status_code == 200, update.text
    assert MEMBERSHIP_DIRECT_IMPORT not in (update.json().get("capabilities") or [])
