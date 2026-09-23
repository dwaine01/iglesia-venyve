"""Iteración 52 - Contrato backend para emisión oficial de documentos de membresía."""

# Módulo: auth efímero + settings/firma + emisión card/certificate + verify público
import json
import os
from pathlib import Path

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
STATE_PATH = Path("/app/test_reports/iteration52_fixture.json")


@pytest.fixture(scope="module")
def fixture_state() -> dict:
    if not STATE_PATH.exists():
        pytest.skip("No existe fixture iteración 52")
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def base_url(fixture_state: dict) -> str:
    url = (BASE_URL or fixture_state.get("base_url") or "").rstrip("/")
    if not url:
        pytest.skip("REACT_APP_BACKEND_URL no definido")
    return url


@pytest.fixture(scope="module")
def auth_headers(base_url: str, fixture_state: dict) -> dict:
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"email": fixture_state["pastor_email"], "password": fixture_state["pastor_password"]},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert isinstance(token, str) and token
    return {"Authorization": f"Bearer {token}"}


def test_membership_status_payload_and_photo_available(base_url: str, auth_headers: dict, fixture_state: dict):
    person_id = fixture_state["member_person_id"]
    response = requests.get(f"{base_url}/api/membership/persons/{person_id}", headers=auth_headers, timeout=30)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("exists") is True
    data = payload.get("data", {})
    assert data.get("person", {}).get("has_profile_photo") is True
    assert data.get("membership", {}).get("member_number") == fixture_state["member_number"]
    assert "_id" not in data.get("membership", {})


def test_issue_card_and_certificate_then_validate_public_verify(base_url: str, auth_headers: dict, fixture_state: dict):
    person_id = fixture_state["member_person_id"]
    card_resp = requests.post(
        f"{base_url}/api/membership/persons/{person_id}/documents/card/issue",
        headers=auth_headers,
        json={"issue_date": "2026-02-10"},
        timeout=30,
    )
    assert card_resp.status_code == 201, card_resp.text
    card_data = card_resp.json().get("data", {})
    assert card_data.get("person", {}).get("full_name")
    verification_path = card_data.get("verification_path")
    assert isinstance(verification_path, str) and verification_path.startswith("/verificar/carnet/")

    cert_resp = requests.post(
        f"{base_url}/api/membership/persons/{person_id}/documents/certificate/issue",
        headers=auth_headers,
        json={"issue_date": "2026-02-10"},
        timeout=30,
    )
    assert cert_resp.status_code == 201, cert_resp.text
    cert_data = cert_resp.json().get("data", {})
    assert cert_data.get("verification_path") == verification_path
    assert cert_data.get("certificate", {}).get("has_signature") is True

    token = verification_path.rsplit("/", 1)[-1]
    verify = requests.get(f"{base_url}/api/public/membership/verify/{token}", timeout=30)
    assert verify.status_code == 200, verify.text
    verify_data = verify.json()
    assert verify_data.get("valid") is True
    assert verify_data.get("member_number") == fixture_state["member_number"]


def test_issuance_history_has_both_document_types(base_url: str, auth_headers: dict, fixture_state: dict):
    person_id = fixture_state["member_person_id"]
    response = requests.get(f"{base_url}/api/membership/persons/{person_id}/issuances", headers=auth_headers, timeout=30)
    assert response.status_code == 200, response.text
    items = response.json().get("items", [])
    kinds = {item.get("document_type") for item in items}
    assert "card" in kinds
    assert "certificate" in kinds
