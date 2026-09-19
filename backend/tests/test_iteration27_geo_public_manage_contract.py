"""Iteration 27: public geo manage/read contracts (audit + sector RBAC)."""

import os
import subprocess
import uuid

import pytest
import requests
from dotenv import dotenv_values


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL_NORM = BASE_URL.rstrip("/") if BASE_URL else None
QA_EMAIL = "qa.geo.ui@example.com"
QA_PASSWORD = "GeoUI2026!"


@pytest.fixture(scope="module")
def auth_headers():
    assert BASE_URL_NORM, "REACT_APP_BACKEND_URL is required"
    subprocess.run(["python", "/app/tests/ui_geo_fixture.py", "setup"], check=True, capture_output=True, text=True)
    try:
        response = requests.post(
            f"{BASE_URL_NORM}/api/auth/login",
            json={"email": QA_EMAIL, "password": QA_PASSWORD},
            timeout=25,
        )
        assert response.status_code == 200, response.text
        token = response.json().get("token")
        assert isinstance(token, str) and token
        yield {"Authorization": f"Bearer {token}"}
    finally:
        subprocess.run(["python", "/app/tests/ui_geo_fixture.py", "cleanup"], check=False, capture_output=True, text=True)


# Geocoding audit endpoint contract
def test_geocoding_audit_contract(auth_headers):
    response = requests.get(f"{BASE_URL_NORM}/api/geo/geocoding-audit", headers=auth_headers, timeout=25)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload.get("total_addresses"), int)
    assert isinstance(payload.get("issues"), list)
    assert "providers" in payload
    assert isinstance(payload.get("audited_at"), str)


# Sector create + locate + soft delete over public endpoint
def test_public_sector_crud_and_locate(auth_headers):
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-83.12, 39.91], [-83.1, 39.91], [-83.1, 39.93], [-83.12, 39.93], [-83.12, 39.91]]],
    }
    name = f"Sector Public QA {uuid.uuid4().hex[:6]}"
    created = requests.post(
        f"{BASE_URL_NORM}/api/geo/sectors",
        json={"zone_id": "south", "name": name, "color": "#2563EB", "geometry": geometry},
        headers=auth_headers,
        timeout=25,
    )
    assert created.status_code == 201, created.text
    sector_id = created.json()["sector_id"]

    located = requests.get(
        f"{BASE_URL_NORM}/api/geo/sectors/locate",
        params={"latitude": 39.92, "longitude": -83.11},
        headers=auth_headers,
        timeout=25,
    )
    assert located.status_code == 200, located.text
    assert located.json().get("sector_id") == sector_id

    removed = requests.delete(f"{BASE_URL_NORM}/api/geo/sectors/{sector_id}", headers=auth_headers, timeout=25)
    assert removed.status_code == 200, removed.text
    assert removed.json().get("status") == "inactive"


# RBAC baseline: unauthenticated mutation must be blocked
def test_sector_mutation_requires_authentication():
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-83.15, 39.9], [-83.14, 39.9], [-83.14, 39.91], [-83.15, 39.91], [-83.15, 39.9]]],
    }
    response = requests.post(
        f"{BASE_URL_NORM}/api/geo/sectors",
        json={"zone_id": "south", "name": "Anon", "geometry": geometry},
        timeout=25,
    )
    assert response.status_code in {401, 403}
