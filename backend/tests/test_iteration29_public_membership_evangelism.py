import io
import os
import subprocess
import uuid

import pytest
import requests
from dotenv import dotenv_values


# Public URL regression for direct membership, import DRY-RUN and minicenso flows.
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")

PASTOR_EMAIL = "qa.features.pastor@example.com"
PERSONA_EMAIL = "qa.features.persona@example.com"


@pytest.fixture(scope="module", autouse=True)
def membership_evangelism_fixture():
    subprocess.run(["python", "/app/tests/ui_membership_evangelism_fixture.py", "setup"], check=True, capture_output=True, text=True)
    yield
    subprocess.run(["python", "/app/tests/ui_membership_evangelism_fixture.py", "cleanup"], check=True, capture_output=True, text=True)
PASSWORD = "FeatureFlow2026!"


def auth_headers(email: str) -> dict:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": PASSWORD},
        timeout=25,
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_public_membership_create_normal_and_direct():
    pastor_headers = auth_headers(PASTOR_EMAIL)

    normal_payload = {
        "nombre": "PublicQA",
        "apellido": "Normal",
        "telefono": "6145556101",
        "idempotency_key": f"ui:features:iter29:normal:{uuid.uuid4()}",
        "preexisting_active_member": False,
    }
    normal = requests.post(f"{BASE_URL}/api/core/persons", json=normal_payload, headers=pastor_headers, timeout=30)
    assert normal.status_code == 201, normal.text
    normal_data = normal.json()
    assert "membership" not in normal_data

    direct_payload = {
        "nombre": "PublicQA",
        "apellido": "Direct",
        "telefono": "6145556102",
        "idempotency_key": f"ui:features:iter29:direct:{uuid.uuid4()}",
        "preexisting_active_member": True,
        "existing_member_number": "PUB-I29-001",
    }
    direct = requests.post(f"{BASE_URL}/api/core/persons", json=direct_payload, headers=pastor_headers, timeout=30)
    assert direct.status_code == 201, direct.text
    direct_data = direct.json()
    assert direct_data["membership"]["direct"] is True


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_public_import_dry_run_and_rbac():
    pastor_headers = auth_headers(PASTOR_EMAIL)
    persona_headers = auth_headers(PERSONA_EMAIL)

    csv_data = (
        "Nombre,Apellido,Correo,Telefono,Direccion,Ciudad,Estado,ZIP\n"
        "Maria,Rios,maria.pubi29@example.com,6145556201,123 Main Street,Columbus,OH,43204\n"
        "Jose,Rios,jose.pubi29@example.com,6145556202,123 Main St.,Columbus,OH,43204\n"
    )
    dry_run = requests.post(
        f"{BASE_URL}/api/membership/import/dry-run",
        files={"file": ("public_iter29.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        headers=pastor_headers,
        timeout=40,
    )
    assert dry_run.status_code == 200, dry_run.text
    data = dry_run.json()
    assert data["dry_run"] is True
    assert data["database_writes"] == 0
    assert data["summary"]["total"] == 2

    denied = requests.post(
        f"{BASE_URL}/api/membership/import/dry-run",
        files={"file": ("public_iter29.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        headers=persona_headers,
        timeout=30,
    )
    assert denied.status_code == 403


@pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not configured")
def test_public_persona_minicenso_create_update_archive():
    persona_headers = auth_headers(PERSONA_EMAIL)

    created = requests.post(
        f"{BASE_URL}/api/geo/evangelism",
        json={
            "house_number": "645",
            "street_name": "Demorest Rd",
            "city": "Columbus",
            "state": "OH",
            "zip": "43204",
            "language": "bilingual",
            "notes": "Public iter29 create",
        },
        headers=persona_headers,
        timeout=40,
    )
    assert created.status_code == 201, created.text
    created_data = created.json()
    target_id = created_data["target_id"]
    assert created_data.get("latitude") is not None and created_data.get("longitude") is not None

    updated = requests.patch(
        f"{BASE_URL}/api/geo/evangelism/{target_id}",
        json={"status": "visited", "notes": "Public iter29 visited"},
        headers=persona_headers,
        timeout=30,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "visited"

    archived = requests.delete(
        f"{BASE_URL}/api/geo/evangelism/{target_id}",
        headers=persona_headers,
        timeout=30,
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived"] is True
