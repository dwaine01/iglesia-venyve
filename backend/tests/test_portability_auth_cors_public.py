"""Public regression for portability/startup, auth, CORS, and lockout hardening."""
import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Module: public endpoint configuration and helper routines
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL") or "").rstrip("/")
BACKEND_ENV = dotenv_values("/app/backend/.env")
PASTOR_EMAIL = "coreqa.pastor@example.com"
PASTOR_PASSWORD = "CoreQA2026!Pastor"


def require_base_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is required for public testing")
    return BASE_URL


def login(email: str, password: str) -> requests.Response:
    return requests.post(
        f"{require_base_url()}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )


# Feature: dependency portability and startup-safe imports
def test_requirements_excludes_private_or_blocked_dependencies():
    requirements = Path("/app/backend/requirements.txt").read_text(encoding="utf-8").lower()

    assert "emergentintegrations" not in requirements
    assert "litellm" not in requirements
    assert "--extra-index-url" not in requirements
    assert "--index-url" not in requirements
    assert ".whl" not in requirements


def test_dockerfile_backend_uses_port_and_no_private_index():
    dockerfile = Path("/app/Dockerfile.backend").read_text(encoding="utf-8")
    dockerfile_lower = dockerfile.lower()

    assert "--extra-index-url" not in dockerfile_lower
    assert "--index-url" not in dockerfile_lower
    assert "${PORT}" in dockerfile


def test_portable_modules_import_without_emergent_package_dependency():
    import builtins
    import importlib
    import sys
    from unittest.mock import patch

    original_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "emergentintegrations" or name.startswith("emergentintegrations."):
            raise ImportError("emergentintegrations blocked in portability test")
        return original_import(name, globals, locals, fromlist, level)

    for module_name in ["board_ai_service", "server"]:
        sys.modules.pop(module_name, None)

    with patch("builtins.__import__", side_effect=blocked_import):
        importlib.import_module("board_ai_service")
        importlib.import_module("server")


def test_board_upload_limits_have_safe_defaults_and_validate_overrides(monkeypatch):
    from board_recording_routes import positive_int_setting

    for name in ["MAX_AUDIO_BYTES", "MAX_AUDIO_SECONDS", "MAX_BOARD_DOCUMENT_BYTES"]:
        monkeypatch.delenv(name, raising=False)
    assert positive_int_setting("MAX_AUDIO_BYTES", 24 * 1024 * 1024) == 25165824
    assert positive_int_setting("MAX_AUDIO_SECONDS", 4 * 60 * 60) == 14400
    assert positive_int_setting("MAX_BOARD_DOCUMENT_BYTES", 10 * 1024 * 1024) == 10485760

    monkeypatch.setenv("MAX_AUDIO_BYTES", "0")
    with pytest.raises(RuntimeError, match="positive integer"):
        positive_int_setting("MAX_AUDIO_BYTES", 25165824)


# Feature: health/auth/cors/public security behavior
def test_health_returns_200_and_expected_payload():
    response = requests.get(f"{require_base_url()}/api/health", timeout=20)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload.get("service"), str)


def test_login_and_auth_me_with_qa_credentials():
    response = login(PASTOR_EMAIL, PASTOR_PASSWORD)
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data.get("token"), str) and len(data["token"]) > 20
    me = requests.get(
        f"{require_base_url()}/api/auth/me",
        headers={"Authorization": f"Bearer {data['token']}"},
        timeout=30,
    )
    assert me.status_code == 200, me.text
    me_data = me.json()
    assert me_data["email"] == PASTOR_EMAIL
    assert me_data["rol"] == "pastor"


def test_login_uses_documented_bearer_contract_without_app_cookie():
    response = login(PASTOR_EMAIL, PASTOR_PASSWORD)
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert isinstance(token, str) and len(token) > 20
    set_cookie = response.headers.get("set-cookie", "")
    lowered = set_cookie.lower()
    assert not any(name in lowered for name in ["access_token=", "auth=", "session=", "token="])


def test_bcrypt_hash_starts_with_2b_for_pastor_qa_user():
    mongo_url = BACKEND_ENV.get("MONGO_URL")
    db_name = BACKEND_ENV.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("Missing MONGO_URL/DB_NAME in backend env")

    client = MongoClient(mongo_url)
    try:
        user = client[db_name].users.find_one({"email": PASTOR_EMAIL})
        assert user is not None
        password_hash = user.get("password", "")
        assert isinstance(password_hash, str)
        assert password_hash.startswith("$2b$")
    finally:
        client.close()


def test_cors_allows_explicit_origin_and_blocks_untrusted_without_wildcard():
    parsed = urlsplit(require_base_url())
    trusted_origin = f"{parsed.scheme}://{parsed.netloc}"

    trusted = requests.options(
        f"{require_base_url()}/api/auth/login",
        headers={
            "Origin": trusted_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=20,
    )
    assert trusted.status_code in (200, 204)
    assert trusted.headers.get("access-control-allow-origin") == trusted_origin
    assert trusted.headers.get("access-control-allow-credentials") == "true"
    assert trusted.headers.get("access-control-allow-origin") != "*"

    untrusted = requests.options(
        f"{require_base_url()}/api/auth/login",
        headers={
            "Origin": "https://malicious.example.net",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=20,
    )
    assert untrusted.status_code in (400, 403)
    assert untrusted.headers.get("access-control-allow-origin") is None


# Feature: brute-force lockout after repeated failures
def test_bruteforce_lockout_applies_after_five_failed_attempts_and_sets_locked_until():
    mongo_url = BACKEND_ENV.get("MONGO_URL")
    db_name = BACKEND_ENV.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("Missing MONGO_URL/DB_NAME in backend env")

    test_email = f"lockout.{uuid.uuid4().hex[:10]}@example.com"
    identifier = hashlib.sha256(test_email.encode("utf-8")).hexdigest()

    for _ in range(6):
        response = login(test_email, "WrongPassword!123")
        assert response.status_code == 401

    client = MongoClient(mongo_url)
    try:
        attempt = client[db_name].login_attempts.find_one({"identifier": identifier})
        assert attempt is not None
        assert int(attempt.get("failed_attempts", 0)) >= 5
        locked_until = attempt.get("locked_until")
        assert locked_until is not None
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        assert locked_until > datetime.now(timezone.utc)
    finally:
        client[db_name].login_attempts.delete_many({"identifier": identifier})
        client.close()


# Feature: board AI blocked/degraded contract when provider is not configured
def test_board_ai_status_reports_blocked_when_provider_env_missing():
    if any(
        (os.environ.get(name) or BACKEND_ENV.get(name) or "").strip()
        for name in ["BOARD_AI_ENDPOINT_URL", "BOARD_AI_API_KEY", "BOARD_AI_MODEL"]
    ):
        pytest.skip("Board AI provider is configured in this environment; BLOCKED contract not applicable")

    auth_response = login(PASTOR_EMAIL, PASTOR_PASSWORD)
    assert auth_response.status_code == 200, auth_response.text
    token = auth_response.json()["token"]

    status_response = requests.get(
        f"{require_base_url()}/api/board/ai/status",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert status_response.status_code == 200, status_response.text
    payload = status_response.json()
    assert payload["status"] == "BLOCKED"
    assert payload["error_code"] == "not_configured"


def test_ai_draft_returns_409_without_consent_and_503_blocked_with_consent():
    if any(
        (os.environ.get(name) or BACKEND_ENV.get(name) or "").strip()
        for name in ["BOARD_AI_ENDPOINT_URL", "BOARD_AI_API_KEY", "BOARD_AI_MODEL"]
    ):
        pytest.skip("Board AI provider is configured in this environment; BLOCKED contract not applicable")

    auth_response = login(PASTOR_EMAIL, PASTOR_PASSWORD)
    assert auth_response.status_code == 200, auth_response.text
    token = auth_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    meeting_id = f"qa-missing-provider-{uuid.uuid4().hex[:8]}"
    no_consent = requests.post(
        f"{require_base_url()}/api/board/meetings/{meeting_id}/ai-draft",
        headers=headers,
        json={"external_processing_acknowledged": False},
        timeout=30,
    )
    assert no_consent.status_code == 409, no_consent.text

    with_consent = requests.post(
        f"{require_base_url()}/api/board/meetings/{meeting_id}/ai-draft",
        headers=headers,
        json={"external_processing_acknowledged": True},
        timeout=30,
    )
    assert with_consent.status_code == 503, with_consent.text
    detail = with_consent.json()["detail"]
    assert detail["status"] == "BLOCKED"
    assert detail["error_code"] == "board_ai_not_configured"