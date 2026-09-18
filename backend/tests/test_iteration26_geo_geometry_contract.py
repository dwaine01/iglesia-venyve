"""Iteration 26: Geo config geometry + search contract via public base URL."""

import os
import subprocess

import pytest
import requests
from dotenv import dotenv_values

backend_env = dotenv_values("/app/backend/.env")
for key in (
    "CENSUS_GEOCODER_URL",
    "CENSUS_GEOCODER_BENCHMARK",
    "GEOCODIO_API_URL",
    "GEOCODIO_API_KEY",
    "GEOCODIO_TIMEOUT_SECONDS",
):
    if backend_env.get(key):
        os.environ.setdefault(key, str(backend_env[key]))

from geo_provider import FallbackGeocodingProvider, geocoding_providers_status


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL_NORM = BASE_URL.rstrip("/") if BASE_URL else None
QA_EMAIL = "qa.geo.ui@example.com"
QA_PASSWORD = "GeoUI2026!"


@pytest.fixture(scope="module")
def auth_headers():
    """Auth fixture using ephemeral QA map account fixture."""
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


# Config geometry contract: 4 zones + 4 labels + 2 rings + 12 subzone labels
def test_geo_config_geometry_contract(auth_headers):
    response = requests.get(f"{BASE_URL_NORM}/api/geo/config", headers=auth_headers, timeout=25)
    assert response.status_code == 200, response.text
    payload = response.json()

    zone_features = payload["zones"]["features"]
    zone_polygons = [item for item in zone_features if item.get("properties", {}).get("feature_type") == "zone"]
    zone_labels = [item for item in zone_features if item.get("properties", {}).get("feature_type") == "zone_label"]
    assert len(zone_polygons) == 4
    assert len(zone_labels) == 4

    subzone_features = payload["subzones"]["features"]
    rings = [item for item in subzone_features if item.get("properties", {}).get("feature_type") == "subzone_ring"]
    subzone_labels = [item for item in subzone_features if item.get("properties", {}).get("feature_type") == "subzone_label"]
    assert len(rings) == 2
    assert len(subzone_labels) == 12


# Search contract: requires precise permission and returns coordinates + zone/subzone
def test_geo_search_contract(auth_headers):
    response = requests.get(
        f"{BASE_URL_NORM}/api/geo/search",
        params={"q": "Ana Norte", "limit": 10},
        headers=auth_headers,
        timeout=25,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("total", 0) >= 1
    first = payload["items"][0]
    assert isinstance(first.get("latitude"), float)
    assert isinstance(first.get("longitude"), float)
    assert first.get("zone") in {"north", "east", "south", "west"}
    assert first.get("subzone") in {f"{number}-{letter}" for number in range(1, 5) for letter in "ABC"}


# API contract: provider key must stay backend-only and never leak in payloads
def test_geocodio_key_not_exposed_in_geo_api(auth_headers):
    configured_key = str(backend_env.get("GEOCODIO_API_KEY") or "").strip().strip('"')
    response = requests.get(f"{BASE_URL_NORM}/api/geo/config", headers=auth_headers, timeout=25)
    assert response.status_code == 200, response.text
    body = response.text.lower()
    assert "geocodio_api_key" not in body
    if configured_key:
        assert configured_key not in response.text


# Real fallback integration: Census miss should auto-resolve with Geocodio
@pytest.mark.asyncio
async def test_real_fallback_census_to_geocodio_bellmouth():
    providers = geocoding_providers_status()
    if not (providers.get("census") and providers.get("geocodio")):
        pytest.skip("Census/Geocodio providers are not fully configured")

    provider = FallbackGeocodingProvider()
    result = await provider.geocode(
        {
            "street": "6553 Bellmouth Rd",
            "city": "Galloway",
            "state": "OH",
            "zip": "43119",
        }
    )

    assert result.status in {"matched", "needs_verification"}
    assert result.provider == "geocodio"
    assert result.accuracy in {"rooftop", "point", "range_interpolated", "unknown"}
    attempted = (result.provider_metadata or {}).get("attempted_providers", [])
    assert attempted == ["census", "geocodio"]
