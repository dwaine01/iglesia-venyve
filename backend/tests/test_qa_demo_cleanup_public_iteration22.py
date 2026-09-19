"""QA/demo cleanup endpoints regression via public backend URL."""
import json
import os
from pathlib import Path

import pytest
import requests
from bson import ObjectId

import server


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if BASE_URL:
    BASE_URL = BASE_URL.rstrip("/")

FIXTURE_FILE = Path("/app/tests/iteration22_fixture.json")


def _load_fixture() -> dict:
    if not FIXTURE_FILE.exists():
        pytest.skip("iteration22 fixture file missing")
    return json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))


def _login(email: str, password: str) -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("token")
    assert data.get("user", {}).get("email") == email
    return data["token"]


@pytest.mark.asyncio
async def test_qa_demo_summary_and_cleanup_roles_and_preservation():
    """Core Personas QA/demo summary+cleanup with RBAC and data preservation checks."""
    payload = _load_fixture()

    pastor_token = _login(payload["pastor_email"], payload["password"])
    leader_token = _login(payload["leader_email"], payload["password"])

    leader_headers = {"Authorization": f"Bearer {leader_token}"}
    leader_preview = requests.get(f"{BASE_URL}/api/core/persons/qa-demo/summary", headers=leader_headers, timeout=20)
    assert leader_preview.status_code == 403
    leader_cleanup = requests.delete(f"{BASE_URL}/api/core/persons/qa-demo", headers=leader_headers, json={"preview_token": "x" * 30, "confirmation_phrase": "ELIMINAR QA 1"}, timeout=20)
    assert leader_cleanup.status_code == 403

    pastor_headers = {"Authorization": f"Bearer {pastor_token}"}
    preview = requests.get(f"{BASE_URL}/api/core/persons/qa-demo/summary", headers=pastor_headers, timeout=20)
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()
    assert isinstance(preview_data.get("qa_users"), int)
    assert isinstance(preview_data.get("qa_persons"), int)
    assert preview_data["total"] == preview_data["qa_users"] + preview_data["qa_persons"]
    assert preview_data["total"] >= 1

    cleanup = requests.delete(f"{BASE_URL}/api/core/persons/qa-demo", headers=pastor_headers, json={"preview_token": preview_data["preview_token"], "confirmation_phrase": preview_data["confirmation_phrase"]}, timeout=30)
    assert cleanup.status_code == 200, cleanup.text
    cleanup_data = cleanup.json()
    assert isinstance(cleanup_data.get("deleted_documents"), int)
    assert cleanup_data["deleted_documents"] >= 1

    post = requests.get(f"{BASE_URL}/api/core/persons/qa-demo/summary", headers=pastor_headers, timeout=20)
    assert post.status_code == 200
    post_data = post.json()
    assert post_data["qa_users"] == 0
    assert post_data["qa_persons"] == 0
    assert post_data["total"] == 0

    qa_person_exists = await server.db.persons.find_one({"_id": ObjectId(payload["qa_person_id"])})
    assert qa_person_exists is None
    qa_user_exists = await server.db.users.find_one({"_id": ObjectId(payload["qa_user_id"])})
    assert qa_user_exists is None
    real_person_exists = await server.db.persons.find_one({"_id": ObjectId(payload["real_person_id"])})
    assert real_person_exists is not None

    settings = await server.db.finance_settings.find_one({"_id": "primary"})
    assert settings is not None
    assert settings.get("updated_by_user_id") == payload["qa_user_id"]
