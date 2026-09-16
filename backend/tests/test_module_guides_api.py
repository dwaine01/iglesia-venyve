"""Pruebas API de guías contextuales (catálogo, contrato de campos y adaptación por rol)."""

import json
import os
from pathlib import Path

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
GUIDES_DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "module_guides.json"
REQUIRED_LIST_FIELDS = [
    "purpose",
    "result",
    "flow",
    "roles",
    "states",
    "steps",
    "inputs",
    "outputs",
    "connections",
    "common_errors",
    "good_practices",
    "example",
    "next",
    "role_focus",
    "tour_steps",
]


def _require_base_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL no definido")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def _login_and_token(api_client: requests.Session, email: str, password: str) -> str:
    base = _require_base_url()
    response = api_client.post(
        f"{base}/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload.get("token"), str) and payload["token"]
    return payload["token"]


@pytest.fixture(scope="session")
def pastor_token(api_client):
    return _login_and_token(api_client, "coreqa.pastor@example.com", "CoreQA2026!Pastor")


@pytest.fixture(scope="session")
def leader_token(api_client):
    return _login_and_token(api_client, "coreqa.leader@example.com", "CoreQA2026!Leader")


@pytest.fixture(scope="session")
def member_token(api_client):
    return _login_and_token(api_client, "coreqa.member@example.com", "CoreQA2026!Member")


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _load_expected_module_keys() -> list[str]:
    payload = json.loads(GUIDES_DOC_PATH.read_text(encoding="utf-8"))
    assert payload.get("schema_version") == "2.0"
    return sorted(payload.get("modules", {}).keys())


# módulo: catálogo de guías
def test_guides_catalog_lists_all_32_modules(api_client, pastor_token):
    base = _require_base_url()
    expected_keys = _load_expected_module_keys()
    assert len(expected_keys) == 32

    response = api_client.get(f"{base}/api/guides", headers=_auth_headers(pastor_token))
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data.get("items"), list)
    assert len(data["items"]) == 32

    got_keys = sorted(item.get("module_key") for item in data["items"])
    assert got_keys == expected_keys
    assert all(item.get("title") for item in data["items"])
    assert all(item.get("version") for item in data["items"])


# módulo: contrato completo de cada guía
def test_each_guide_contains_required_non_empty_fields(api_client, pastor_token):
    base = _require_base_url()
    expected_keys = _load_expected_module_keys()

    for module_key in expected_keys:
        response = api_client.get(
            f"{base}/api/guides/{module_key}",
            headers=_auth_headers(pastor_token),
        )
        assert response.status_code == 200, f"{module_key}: {response.text}"
        data = response.json()
        for field in REQUIRED_LIST_FIELDS:
            assert field in data, f"{module_key}: missing {field}"
            value = data[field]
            if isinstance(value, list):
                assert len(value) > 0, f"{module_key}: empty list {field}"
            elif isinstance(value, dict):
                assert len(value.keys()) > 0, f"{module_key}: empty object {field}"
            else:
                assert value not in (None, ""), f"{module_key}: empty scalar {field}"


# módulo: rol activo y enfoque contextual por perfil
def test_role_focus_changes_for_pastor_lider_persona(api_client, pastor_token, leader_token, member_token):
    base = _require_base_url()
    module_key = "processes_dashboard"

    pastor = api_client.get(f"{base}/api/guides/{module_key}", headers=_auth_headers(pastor_token))
    leader = api_client.get(f"{base}/api/guides/{module_key}", headers=_auth_headers(leader_token))
    member = api_client.get(f"{base}/api/guides/{module_key}", headers=_auth_headers(member_token))

    assert pastor.status_code == 200
    assert leader.status_code == 200
    assert member.status_code == 200

    p_data = pastor.json()
    l_data = leader.json()
    m_data = member.json()

    assert p_data["active_role_label"] == "Pastor"
    assert l_data["active_role_label"] == "Líder"
    assert m_data["active_role_label"] == "Persona"
    assert p_data["role_focus"]
    assert l_data["role_focus"]
    assert m_data["role_focus"]
    assert len({p_data["role_focus"], l_data["role_focus"], m_data["role_focus"]}) == 3


# módulo: pasos del tour restringidos por rol (no filtrar incorrectamente)
def test_role_restricted_tour_step_visible_for_allowed_roles(api_client, pastor_token, leader_token, member_token):
    base = _require_base_url()
    module_key = "ministries"
    restricted_target = "create-ministry-button"

    pastor = api_client.get(f"{base}/api/guides/{module_key}", headers=_auth_headers(pastor_token)).json()
    leader = api_client.get(f"{base}/api/guides/{module_key}", headers=_auth_headers(leader_token)).json()
    member = api_client.get(f"{base}/api/guides/{module_key}", headers=_auth_headers(member_token)).json()

    pastor_targets = {step.get("target") for step in pastor.get("tour_steps", [])}
    leader_targets = {step.get("target") for step in leader.get("tour_steps", [])}
    member_targets = {step.get("target") for step in member.get("tour_steps", [])}

    assert restricted_target in pastor_targets
    assert restricted_target in leader_targets
    assert restricted_target not in member_targets
