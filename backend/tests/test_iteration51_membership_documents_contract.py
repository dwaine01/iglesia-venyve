"""Iteración 51 - Contrato definitivo de documentos de membresía (fixture vivo)."""

# Módulo: auth fixture vivo + payload membresía + QR/verify público + dimensiones PDF definitivas
import os
import re
from pathlib import Path

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FIXTURE_EMAIL = "qa.iter47.photo.pastora.c83ef2648f@example.com"
FIXTURE_PASSWORD = "QaUiPhoto47!"
FIXTURE_PERSON_ID = "6ab31d0ec5435f2994e8db33"
CARD_BACK_IMG = Path("/app/test_reports/master-card-back.png")
CERT_IMG = Path("/app/test_reports/master-certificate.png")
CARD_PDF = Path("/app/test_reports/master-card.pdf")
CERT_PDF = Path("/app/test_reports/master-certificate.pdf")


@pytest.fixture(scope="module")
def base_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL no definido")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="module")
def auth_headers(base_url: str) -> dict:
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"email": FIXTURE_EMAIL, "password": FIXTURE_PASSWORD},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert isinstance(token, str) and token
    return {"Authorization": f"Bearer {token}"}


def _decode_qr(path: Path) -> str:
    try:
        import cv2
    except Exception:
        pytest.skip("OpenCV no disponible para decodificar QR")

    image = cv2.imread(str(path))
    assert image is not None, f"No se pudo cargar imagen {path}"
    try:
        import zxingcpp

        result = zxingcpp.read_barcode(image)
        if result and getattr(result, "text", None):
            return result.text.strip()
    except Exception:
        pass

    detector = cv2.QRCodeDetector()
    h, w = image.shape[:2]
    candidates = [image]
    # El QR del certificado es pequeño; probar recortes de la zona inferior derecha.
    candidates.extend([
        image[int(h * 0.65):, int(w * 0.72):],
        image[int(h * 0.6):, int(w * 0.68):],
    ])
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    candidates.append(gray)
    candidates.append(cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC))
    candidates.append(cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC))
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates.append(th)
    candidates.append(cv2.resize(th, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_NEAREST))
    candidates.append(cv2.resize(th, None, fx=4.5, fy=4.5, interpolation=cv2.INTER_NEAREST))

    saw_points = False
    for item in candidates:
        decoded, points, _ = detector.detectAndDecode(item)
        if points is not None:
            saw_points = True
        if decoded:
            return decoded.strip()

    assert saw_points, f"No se detectó QR en {path.name}"
    raise AssertionError(f"QR vacío en {path.name}")


def _pdf_page_count_and_mediabox(path: Path) -> tuple[int, tuple[float, float]]:
    raw = path.read_bytes()
    count_matches = [int(item) for item in re.findall(rb"/Count\s+(\d+)", raw)]
    page_count = max(count_matches) if count_matches else 0
    media_matches = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", raw)
    assert media_matches, f"No se encontró MediaBox en {path.name}"
    width_pt = float(media_matches[0][0])
    height_pt = float(media_matches[0][1])
    return page_count, (width_pt, height_pt)


def _pt_to_mm(value: float) -> float:
    return value * 25.4 / 72


def test_fixture_membership_payload_is_available(base_url: str, auth_headers: dict):
    response = requests.get(
        f"{base_url}/api/membership/persons/{FIXTURE_PERSON_ID}",
        headers=auth_headers,
        timeout=30,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("exists") is True
    data = payload.get("data", {})
    membership = data.get("membership", {})
    assert membership.get("member_number") == "VV-0284"
    assert "_id" not in membership
    assert isinstance(data.get("verification_path"), str) and "/verificar/carnet/" in data["verification_path"]


def test_master_images_qr_verify_and_member_number(base_url: str):
    assert CARD_BACK_IMG.exists(), f"Falta evidencia {CARD_BACK_IMG}"
    assert CERT_IMG.exists(), f"Falta evidencia {CERT_IMG}"

    card_qr = _decode_qr(CARD_BACK_IMG)
    cert_qr = _decode_qr(CERT_IMG)
    assert "/verificar/carnet/" in card_qr
    assert "/verificar/carnet/" in cert_qr

    token_card = card_qr.rstrip("/").split("/")[-1]
    token_cert = cert_qr.rstrip("/").split("/")[-1]
    assert token_card == token_cert

    verify = requests.get(f"{base_url}/api/public/membership/verify/{token_card}", timeout=30)
    assert verify.status_code == 200, verify.text
    data = verify.json()
    assert data.get("member_number") == "VV-0284"


def test_master_pdfs_dimensions_and_page_counts_are_exact():
    assert CARD_PDF.exists(), f"No existe {CARD_PDF}"
    assert CERT_PDF.exists(), f"No existe {CERT_PDF}"

    card_pages, (card_w_pt, card_h_pt) = _pdf_page_count_and_mediabox(CARD_PDF)
    assert card_pages == 2
    card_w_mm = _pt_to_mm(card_w_pt)
    card_h_mm = _pt_to_mm(card_h_pt)
    assert abs(card_w_mm - 85.60) < 0.15
    assert abs(card_h_mm - 53.98) < 0.15
    assert abs(card_w_pt - 242.645669) < 0.2
    assert abs(card_h_pt - 153.014173) < 0.2

    cert_pages, (cert_w_pt, cert_h_pt) = _pdf_page_count_and_mediabox(CERT_PDF)
    assert cert_pages == 1
    assert abs(cert_w_pt - 792.0) < 0.2
    assert abs(cert_h_pt - 612.0) < 0.2
