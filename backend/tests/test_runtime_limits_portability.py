"""Runtime portability and safe-limit defaults for Railway-like env sets."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values


# Module: public backend URL health validation
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL") or "")


def _railway_min_env() -> dict:
    env = os.environ.copy()
    env["MONGO_URL"] = env.get("MONGO_URL", "mongodb://localhost:27017")
    env["DB_NAME"] = env.get("DB_NAME", "test_database")
    env["JWT_SECRET"] = env.get("JWT_SECRET", "test-jwt-secret")
    env["CORS_ORIGINS"] = "https://panel.iglesiavenyve.org"
    env["CORS_ORIGIN_REGEX"] = r"^https://panel\.iglesiavenyve\.org$"
    return env


def _copy_backend_without_env(tmp_path: Path) -> Path:
    source_backend = Path("/app/backend")
    runtime_backend = tmp_path / "backend_runtime"
    shutil.copytree(source_backend, runtime_backend)
    env_file = runtime_backend / ".env"
    if env_file.exists():
        env_file.unlink()
    return runtime_backend


def _import_server_with_env(runtime_backend: Path, overrides: dict | None = None) -> subprocess.CompletedProcess:
    script_path = runtime_backend / "runtime_import_smoke.py"
    script_path.write_text(
        "\n".join(
            [
                "import json",
                "import server",
                "import board_recording_routes as brr",
                "print(json.dumps({",
                "  'app_loaded': bool(server.app),",
                "  'MAX_AUDIO_BYTES': brr.MAX_AUDIO_BYTES,",
                "  'MAX_AUDIO_SECONDS': brr.MAX_AUDIO_SECONDS,",
                "  'MAX_BOARD_DOCUMENT_BYTES': brr.MAX_DOCUMENT_BYTES",
                "}))",
            ]
        ),
        encoding="utf-8",
    )

    env = _railway_min_env()
    for key in ["MAX_AUDIO_BYTES", "MAX_AUDIO_SECONDS", "MAX_BOARD_DOCUMENT_BYTES"]:
        env.pop(key, None)
    if overrides:
        for key, value in overrides.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = str(value)

    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(runtime_backend),
        env=env,
        capture_output=True,
        text=True,
        timeout=40,
    )


# Module: import/startup fallback behavior for limit env vars
def test_import_server_without_env_file_and_without_limits_does_not_crash(tmp_path):
    runtime_backend = _copy_backend_without_env(tmp_path)
    result = _import_server_with_env(runtime_backend)
    assert result.returncode == 0, result.stderr


def test_missing_limits_resolve_to_exact_safe_defaults(tmp_path):
    runtime_backend = _copy_backend_without_env(tmp_path)
    result = _import_server_with_env(runtime_backend)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["MAX_AUDIO_BYTES"] == 25165824
    assert payload["MAX_AUDIO_SECONDS"] == 14400
    assert payload["MAX_BOARD_DOCUMENT_BYTES"] == 10485760


def test_positive_integer_overrides_are_applied(tmp_path):
    runtime_backend = _copy_backend_without_env(tmp_path)
    result = _import_server_with_env(
        runtime_backend,
        {
            "MAX_AUDIO_BYTES": 26000000,
            "MAX_AUDIO_SECONDS": 7200,
            "MAX_BOARD_DOCUMENT_BYTES": 2097152,
        },
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["MAX_AUDIO_BYTES"] == 26000000
    assert payload["MAX_AUDIO_SECONDS"] == 7200
    assert payload["MAX_BOARD_DOCUMENT_BYTES"] == 2097152


@pytest.mark.parametrize("bad_value", ["0", "-1", "abc"])
def test_non_positive_or_non_numeric_overrides_fail_clearly(tmp_path, bad_value):
    runtime_backend = _copy_backend_without_env(tmp_path)
    result = _import_server_with_env(runtime_backend, {"MAX_AUDIO_BYTES": bad_value})
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "MAX_AUDIO_BYTES must be a positive integer" in combined


# Module: running service behavior check on public URL
def test_public_health_endpoint_returns_200():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is required")
    response = requests.get(f"{BASE_URL.rstrip('/')}/api/health", timeout=20)
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"