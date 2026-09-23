"""Public endpoint regression for Mapa 360 + Consolidación intake autocomplete."""

import os
import subprocess

import pytest
import requests
from dotenv import dotenv_values


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL_NORM = BASE_URL.rstrip("/") if BASE_URL else None
QA_EMAIL = "qa.geo.ui@example.com"
QA_PASSWORD = "GeoUI2026!"


@pytest.fixture(scope="session")
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


# Consolidation candidate autocomplete contract
@pytest.mark.parametrize("term", ["Josué Rivera", "6145553600", "VV-QM9999"])
def test_intake_candidates_search_variants(term, auth_headers):
    response = requests.get(
        f"{BASE_URL_NORM}/api/processes/consolidation/intake-candidates",
        params={"search": term, "limit": 20},
        headers=auth_headers,
        timeout=25,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data.get("items"), list)
    assert any((item.get("name") or "").lower().find("jos") >= 0 for item in data["items"])
    assert all(item.get("person_id") for item in data["items"])


# Geo configuration and privacy contract
def test_geo_config_exposes_maplibre_osm_contract(auth_headers):
    response = requests.get(f"{BASE_URL_NORM}/api/geo/config", headers=auth_headers, timeout=25)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["map_policy"]["renderer"] == "maplibre"
    assert data["map_policy"]["tiles"] == "openstreetmap"
    assert data["center"]["address"].lower().find("demorest") >= 0


# Aggregate should remain privacy-safe (no identity/address)
def test_geo_aggregate_people_hides_identity_fields(auth_headers):
    response = requests.get(
        f"{BASE_URL_NORM}/api/geo/aggregate",
        params={"entity_kind": "people"},
        headers=auth_headers,
        timeout=25,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("meta", {}).get("privacy") == "k-anonymous"
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        assert "name" not in props
        assert "address" not in props
        assert "person_number" not in props
        assert "phone" not in props
        assert "coverage_gap" in props
        assert "nearest_cell_miles" in props


# Precise mode returns feature collections for people and cells
@pytest.mark.parametrize("kind", ["people", "cells"])
def test_geo_precise_entity_kinds(kind, auth_headers):
    response = requests.get(
        f"{BASE_URL_NORM}/api/geo/precise",
        params={"entity_kind": kind},
        headers=auth_headers,
        timeout=25,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("type") == "FeatureCollection"
    assert payload.get("meta", {}).get("privacy") == "precise"
    assert isinstance(payload.get("features"), list)


# Cells map detail contract
def test_geo_precise_cells_expose_operational_fields(auth_headers):
    response = requests.get(
        f"{BASE_URL_NORM}/api/geo/precise",
        params={"entity_kind": "cells"},
        headers=auth_headers,
        timeout=25,
    )
    assert response.status_code == 200, response.text
    features = response.json().get("features", [])
    if not features:
        pytest.skip("No hay celdas geocodificadas en este entorno")
    props = features[0].get("properties", {})
    assert "leader" in props
    assert "meeting_day" in props
    assert "meeting_time" in props
    assert "capacity" in props
    assert "members" in props


# Comparison analytics response shape (90 days)
def test_geo_comparison_90_days_shape(auth_headers):
    response = requests.get(
        f"{BASE_URL_NORM}/api/geo/comparison",
        params={"days": 90},
        headers=auth_headers,
        timeout=25,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("days") == 90
    assert set(data.get("zones", {}).keys()) == {"north", "east", "south", "west"}


# Manual verification queue visibility for manage role
def test_geo_review_queue_visible_for_manage_role(auth_headers):
    response = requests.get(f"{BASE_URL_NORM}/api/geo/review-queue", headers=auth_headers, timeout=25)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload.get("items"), list)
    assert isinstance(payload.get("total"), int)


def test_geo_manager_can_confirm_selected_person_location(auth_headers):
    search = requests.get(
        f"{BASE_URL_NORM}/api/geo/search",
        params={"q": "Ana Norte", "limit": 10},
        headers=auth_headers,
        timeout=25,
    )
    assert search.status_code == 200, search.text
    person = next(item for item in search.json()["items"] if "ana" in item["name"].lower())
    response = requests.post(
        f"{BASE_URL_NORM}/api/geo/persons/{person['person_id']}/confirm-location",
        json={"latitude": person["latitude"], "longitude": person["longitude"]},
        headers=auth_headers,
        timeout=25,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["person_id"] == person["person_id"]
    assert payload["verification_status"] == "manual_verified"
    assert payload["address_id"]
