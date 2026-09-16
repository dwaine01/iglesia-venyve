"""Public endpoint regression: directory filters and enriched ministries response."""

import os

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
TEST_EMAIL = os.environ.get("TEST_UI_EMAIL", "access01.ui@example.com")
TEST_PASSWORD = os.environ.get("TEST_UI_PASSWORD", "Access01UiTest!")


@pytest.fixture(scope="module")
def api_client():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is required")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    login = session.post(
        f"{BASE_URL.rstrip('/')}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip("Auth failed for public endpoint regression")
    token = login.json().get("token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# Directory API: membership lock + ministry/role + occupation/skill/age combined filters
def test_directory_membership_filter_blocked(api_client):
    response = api_client.get(
        f"{BASE_URL.rstrip('/')}/api/core/persons/directory/search",
        params={"membership_status": "activo"},
        timeout=30,
    )
    assert response.status_code == 409
    detail = response.json().get("detail")
    assert "Membresía" in detail


def test_directory_ministry_text_and_combined_ministry_role_filters(api_client):
    search = api_client.get(
        f"{BASE_URL.rstrip('/')}/api/core/persons/directory/search",
        params={"q": "Ministerio QA", "limit": 100},
        timeout=30,
    )
    assert search.status_code == 200
    payload = search.json()
    assert isinstance(payload.get("items"), list)
    assert payload.get("membership_filter_available") is False

    if not payload["items"]:
        pytest.skip("No ministry-text results available for this scoped account")

    first = payload["items"][0]
    assert "ministries" in first
    assert isinstance(first["ministries"], list)
    assert first["canonical_profile_path"].startswith("/personas/")
    assert first["ministries"], "Expected enriched ministries in directory response"
    assignment = first["ministries"][0]

    filtered = api_client.get(
        f"{BASE_URL.rstrip('/')}/api/core/persons/directory/search",
        params={
            "ministry_id": assignment["ministry_id"],
            "ministry_role_id": assignment["role_id"],
            "limit": 100,
        },
        timeout=30,
    )
    assert filtered.status_code == 200
    data = filtered.json()
    assert isinstance(data.get("items"), list)
    assert any(
        any(
            m["ministry_id"] == assignment["ministry_id"] and m["role_id"] == assignment["role_id"]
            for m in item.get("ministries", [])
        )
        for item in data["items"]
    )


def test_directory_occupation_skill_age_group_combined_filter(api_client):
    baseline = api_client.get(
        f"{BASE_URL.rstrip('/')}/api/core/persons/directory/search",
        params={"limit": 100},
        timeout=30,
    )
    assert baseline.status_code == 200
    items = baseline.json().get("items", [])

    candidate = next(
        (
            item
            for item in items
            if item.get("talents", {}).get("ocupacion_principal")
            and item.get("talents", {}).get("habilidades")
            and item.get("age_group")
        ),
        None,
    )
    if not candidate:
        candidate = next((item for item in items if item.get("age_group")), None)
        if not candidate:
            pytest.skip("No age-group candidate visible in current scope")
        catalog_response = api_client.get(
            f"{BASE_URL.rstrip('/')}/api/core/talents/catalog",
            timeout=30,
        )
        assert catalog_response.status_code == 200
        catalog = catalog_response.json().get("items", [])
        occupation = next(item for item in catalog if item["tipo"] in {"ocupacion", "ambos"})
        skill = next(item for item in catalog if item["tipo"] in {"habilidad", "ambos"} and item["talent_id"] != occupation["talent_id"])
        update = api_client.put(
            f"{BASE_URL.rstrip('/')}/api/core/persons/{candidate['person_id']}/talents",
            json={
                "ocupacion_principal_id": occupation["talent_id"],
                "habilidad_ids": [skill["talent_id"]],
            },
            timeout=30,
        )
        assert update.status_code == 200
        candidate["talents"] = update.json()

    occupation_id = candidate["talents"]["ocupacion_principal"]["talent_id"]
    skill_id = candidate["talents"]["habilidades"][0]["talent_id"]
    age_group = candidate["age_group"]

    combined = api_client.get(
        f"{BASE_URL.rstrip('/')}/api/core/persons/directory/search",
        params={
            "occupation_id": occupation_id,
            "skill_id": skill_id,
            "age_group": age_group,
            "limit": 100,
        },
        timeout=30,
    )
    assert combined.status_code == 200
    combined_items = combined.json().get("items", [])
    assert any(item["person_id"] == candidate["person_id"] for item in combined_items)
