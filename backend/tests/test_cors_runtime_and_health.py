import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


def _require_base_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is required for public endpoint testing")
    return BASE_URL.rstrip("/")


# CORS runtime/environment and public health checks
class TestCorsRuntimeAndHealth:
    def test_server_import_prefers_runtime_cors_over_dotenv(self):
        backend_dir = "/app/backend"
        env = os.environ.copy()
        env["CORS_ORIGINS"] = "https://runtime-check.example.com"
        env["CORS_ORIGIN_REGEX"] = r"^https://runtime-check\\.example\\.com$"
        env.setdefault("MONGO_URL", "mongodb://localhost:27017")
        env.setdefault("DB_NAME", "test_database")
        env.setdefault("JWT_SECRET", "test_secret")
        env["PYTHONPATH"] = f"{backend_dir}:{env.get('PYTHONPATH', '')}".rstrip(":")

        probe_script = Path(backend_dir) / "tests" / "_cors_runtime_probe.py"
        probe_script.write_text(
            "import json\n"
            "import server\n"
            "print(json.dumps({'origins': server.origins, 'regex': server.cors_origin_regex}))\n",
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                ["python", str(probe_script)],
                cwd=backend_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert proc.returncode == 0, proc.stderr
            data = json.loads(proc.stdout.strip())
        finally:
            probe_script.unlink(missing_ok=True)

        assert data["origins"] == ["https://runtime-check.example.com"]
        assert data["regex"] == r"^https://runtime-check\\.example\\.com$"

    def test_public_health_returns_200(self):
        base_url = _require_base_url()
        response = requests.get(f"{base_url}/api/health", timeout=20)
        assert response.status_code == 200

        payload = response.json()
        assert payload["status"] == "ok"
        assert isinstance(payload.get("service"), str)

    @pytest.mark.parametrize(
        "origin",
        [
            "https://qa-subdomain.emergent.host",
        ],
    )
    def test_preflight_allows_expected_origin_patterns_with_credentials(self, origin):
        base_url = _require_base_url()
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        }
        response = requests.options(f"{base_url}/api/auth/login", headers=headers, timeout=20)

        assert response.status_code in (200, 204)
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_preflight_allows_configured_preview_origin_with_credentials(self):
        base_url = _require_base_url()
        parsed = urlsplit(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        }
        response = requests.options(f"{base_url}/api/auth/login", headers=headers, timeout=20)

        assert response.status_code in (200, 204)
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_arbitrary_preview_subdomain_is_not_credentialed(self):
        base_url = _require_base_url()
        origin = "https://qa-subdomain.preview.emergentagent.com"
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        }
        response = requests.options(f"{base_url}/api/auth/login", headers=headers, timeout=20)

        assert response.headers.get("access-control-allow-origin") != origin

    def test_preflight_blocks_untrusted_origin(self):
        base_url = _require_base_url()
        bad_origin = "https://malicious.example.net"
        headers = {
            "Origin": bad_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        }
        response = requests.options(f"{base_url}/api/auth/login", headers=headers, timeout=20)

        assert response.status_code in (400, 403)
        assert response.headers.get("access-control-allow-origin") is None