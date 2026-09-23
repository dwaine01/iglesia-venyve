"""Iteration 55: public geo confirmation RBAC/mismatch contracts."""

import os
import subprocess
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

from access_control import access_defaults_for_role


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL_NORM = BASE_URL.rstrip("/") if BASE_URL else None
QA_EMAIL = "qa.geo.ui@example.com"
QA_PASSWORD = "GeoUI2026!"
VIEWER_PASSWORD = "GeoViewOnly2026!"


MONGO_URL = os.environ.get("MONGO_URL") or dotenv_values("/app/backend/.env").get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or dotenv_values("/app/backend/.env").get("DB_NAME")


# Geo fixture and viewer-user lifecycle helpers
def _create_viewer_user(email: str):
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    defaults = access_defaults_for_role("lider")
    defaults["capabilities"] = ["geo.view_aggregate", "geo.view_precise"]
    db.users.insert_one(
        {
            "_id": ObjectId(),
            "nombre": "QA Geo Viewer",
            "email": email,
            "password": bcrypt.hashpw(VIEWER_PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "rol": "lider",
            "is_active": True,
            "token_version": 1,
            "created_at": datetime.now(timezone.utc),
            **defaults,
        }
    )
    client.close()


def _cleanup_viewer_user(email: str):
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.users.delete_many({"email": email})
    client.close()


@pytest.fixture(scope="module")
def fixture_context():
    assert BASE_URL_NORM, "REACT_APP_BACKEND_URL is required"
    assert MONGO_URL and DB_NAME, "MONGO_URL and DB_NAME are required"
    subprocess.run(["python", "/app/tests/ui_geo_fixture.py", "setup"], check=True, capture_output=True, text=True)
    viewer_email = f"qa.geo.viewer.{uuid.uuid4().hex[:8]}@example.com"
    _create_viewer_user(viewer_email)
    try:
        manager_login = requests.post(
            f"{BASE_URL_NORM}/api/auth/login",
            json={"email": QA_EMAIL, "password": QA_PASSWORD},
            timeout=25,
        )
        assert manager_login.status_code == 200, manager_login.text
        manager_token = manager_login.json().get("token")
        assert isinstance(manager_token, str) and manager_token

        viewer_login = requests.post(
            f"{BASE_URL_NORM}/api/auth/login",
            json={"email": viewer_email, "password": VIEWER_PASSWORD},
            timeout=25,
        )
        assert viewer_login.status_code == 200, viewer_login.text
        viewer_token = viewer_login.json().get("token")
        assert isinstance(viewer_token, str) and viewer_token

        search = requests.get(
            f"{BASE_URL_NORM}/api/geo/search",
            params={"q": "Ana Norte", "limit": 10},
            headers={"Authorization": f"Bearer {manager_token}"},
            timeout=25,
        )
        assert search.status_code == 200, search.text
        person = next(item for item in search.json()["items"] if "ana" in item["name"].lower())

        yield {
            "manager": {"Authorization": f"Bearer {manager_token}"},
            "viewer": {"Authorization": f"Bearer {viewer_token}"},
            "person": person,
        }
    finally:
        _cleanup_viewer_user(viewer_email)
        subprocess.run(["python", "/app/tests/ui_geo_fixture.py", "cleanup"], check=False, capture_output=True, text=True)


# Confirmation flow contracts: mismatch(409) and no-manage role(403)
def test_confirm_location_mismatch_returns_409(fixture_context):
    person = fixture_context["person"]

    mismatch = requests.post(
        f"{BASE_URL_NORM}/api/geo/persons/{person['person_id']}/confirm-location",
        json={"latitude": person["latitude"] + 0.01, "longitude": person["longitude"] + 0.01},
        headers=fixture_context["manager"],
        timeout=25,
    )
    assert mismatch.status_code == 409, mismatch.text
    assert "no coincide" in (mismatch.text or "").lower()


def test_confirm_location_forbidden_without_geo_manage(fixture_context):
    config = requests.get(f"{BASE_URL_NORM}/api/geo/config", headers=fixture_context["viewer"], timeout=25)
    assert config.status_code == 200, config.text
    permissions = config.json().get("permissions", {})
    assert permissions.get("view_precise") is True
    assert permissions.get("manage_locations") is False

    person = fixture_context["person"]

    forbidden = requests.post(
        f"{BASE_URL_NORM}/api/geo/persons/{person['person_id']}/confirm-location",
        json={"latitude": person["latitude"], "longitude": person["longitude"]},
        headers=fixture_context["viewer"],
        timeout=25,
    )
    assert forbidden.status_code == 403, forbidden.text
