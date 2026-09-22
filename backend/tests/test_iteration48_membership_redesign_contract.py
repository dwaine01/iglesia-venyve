"""Iteración 48 - Contratos backend/PDF para rediseño de carnet y certificado."""

# Módulo: Membresía documentos oficiales + verificación pública + geometría PDF
import os
from pathlib import Path
import re

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
QA_EMAIL = "qa.iter47.photo.pastora.bd0bbe62f3@example.com"
QA_PASSWORD = "QaUiPhoto47!"
QA_PERSON_ID = "6ab2e796067c039e4c8c2fc2"
CARD_PDF = Path("/app/test_reports/redesign-card-cr80.pdf")
CERT_PDF = Path("/app/test_reports/redesign-certificate-letter.pdf")
CARD_PREVIEW_CAPTURE = Path("/app/test_reports/artifacts_iter48/iteration48_card_preview_desktop.jpeg")


def _assert_env():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL no está definido")


def _auth_headers():
    _assert_env()
    response = requests.post(
        f"{BASE_URL.rstrip('/')}/api/auth/login",
        json={"email": QA_EMAIL, "password": QA_PASSWORD},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _pdf_page_count_and_mediabox(path: Path) -> tuple[int, tuple[float, float]]:
    raw = path.read_bytes()
    count_matches = [int(item) for item in re.findall(rb"/Count\s+(\d+)", raw)]
    page_count = max(count_matches) if count_matches else 0
    media_matches = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", raw)
    assert media_matches, "No se encontró MediaBox en PDF"
    width_pt = float(media_matches[0][0])
    height_pt = float(media_matches[0][1])
    return page_count, (width_pt, height_pt)


def _pt_to_mm(value: float) -> float:
    return value * 25.4 / 72


def test_card_pdf_geometry_is_cr80_two_pages():
    assert CARD_PDF.exists(), f"No existe {CARD_PDF}"
    pages, (width_pt, height_pt) = _pdf_page_count_and_mediabox(CARD_PDF)
    assert pages == 2
    width_mm = _pt_to_mm(width_pt)
    height_mm = _pt_to_mm(height_pt)
    ratio = width_mm / height_mm
    assert abs(width_mm - 85.60) < 0.15
    assert abs(height_mm - 53.98) < 0.15
    assert abs(ratio - (85.60 / 53.98)) < 0.01


def test_certificate_pdf_geometry_is_letter_landscape():
    assert CERT_PDF.exists(), f"No existe {CERT_PDF}"
    pages, (width_pt, height_pt) = _pdf_page_count_and_mediabox(CERT_PDF)
    assert pages == 1
    assert abs(width_pt - 792.0) < 0.2
    assert abs(height_pt - 612.0) < 0.2
    assert abs((width_pt / height_pt) - (11 / 8.5)) < 0.01


def test_membership_document_payload_and_public_verification():
    headers = _auth_headers()
    person_resp = requests.get(
        f"{BASE_URL.rstrip('/')}/api/membership/persons/{QA_PERSON_ID}",
        headers=headers,
        timeout=30,
    )
    assert person_resp.status_code == 200, person_resp.text
    payload = person_resp.json()
    assert payload.get("exists") is True
    data = payload.get("data", {})
    member_number = data.get("membership", {}).get("member_number")
    verification_path = data.get("verification_path")

    assert isinstance(member_number, str) and len(member_number.strip()) > 0
    assert member_number != data.get("membership", {}).get("membership_id")
    assert verification_path and verification_path.startswith("/verificar/carnet/")

    token = verification_path.rsplit("/", 1)[-1]
    public_resp = requests.get(
        f"{BASE_URL.rstrip('/')}/api/public/membership/verify/{token}",
        timeout=30,
    )
    assert public_resp.status_code == 200, public_resp.text
    public_data = public_resp.json()
    assert public_data.get("status") in {"active", "expired", "inactive", "invalid"}
    assert public_data.get("member_number") == member_number


def test_reprint_and_issuance_history_still_work_for_card():
    headers = _auth_headers()
    issue_resp = requests.post(
        f"{BASE_URL.rstrip('/')}/api/membership/persons/{QA_PERSON_ID}/documents/card/issue",
        headers=headers,
        json={"issue_date": "2026-02-10"},
        timeout=30,
    )
    assert issue_resp.status_code == 201, issue_resp.text
    action = issue_resp.json().get("action")
    assert action in {"issued", "reprinted"}

    history_resp = requests.get(
        f"{BASE_URL.rstrip('/')}/api/membership/persons/{QA_PERSON_ID}/issuances",
        headers=headers,
        timeout=30,
    )
    assert history_resp.status_code == 200, history_resp.text
    items = history_resp.json().get("items", [])
    assert any(item.get("document_type") == "card" for item in items)


def test_qr_decoding_from_real_card_capture_points_to_verification_route():
    if not CARD_PREVIEW_CAPTURE.exists():
        pytest.skip("No existe captura UI de carnet para decodificar QR")
    try:
        import cv2
    except Exception:
        pytest.skip("OpenCV no disponible para decodificar QR")

    image = cv2.imread(str(CARD_PREVIEW_CAPTURE))
    detector = cv2.QRCodeDetector()
    decoded, points, _ = detector.detectAndDecode(image)
    assert points is not None, "No se detectó QR en la captura"
    assert decoded and "/verificar/carnet/" in decoded

    token = decoded.rstrip("/").split("/")[-1]
    verify = requests.get(f"{BASE_URL.rstrip('/')}/api/public/membership/verify/{token}", timeout=30)
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    assert payload.get("status") in {"active", "expired", "inactive", "invalid"}
