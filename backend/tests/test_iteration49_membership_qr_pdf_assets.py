"""Iteración 49 - Validación de QR y geometría PDF desde artefactos UI reales."""

# Módulo: decodificación QR de reverso/certificado + tamaño de páginas PDF CR80/Letter
import os
import re
from pathlib import Path

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
CARD_IMG = Path("/app/test_reports/qr-card-back.png")
CERT_IMG = Path("/app/test_reports/qr-certificate.png")
CARD_PDF = Path("/app/test_reports/concept-a-card-cr80.pdf")
CERT_PDF = Path("/app/test_reports/concept-a-certificate-letter.pdf")


def _decode_qr(path: Path) -> str:
    try:
        import cv2
    except Exception:
        pytest.skip("OpenCV no disponible para decodificar QR")
    image = cv2.imread(str(path))
    assert image is not None, f"No se pudo cargar imagen {path}"

    # Intento 1: zxing-cpp (más robusto para capturas con compresión)
    try:
        import zxingcpp
        result = zxingcpp.read_barcode(image)
        if result and getattr(result, "text", None):
            return result.text.strip()
    except Exception:
        pass

    # Intento 2: OpenCV con preprocesamiento
    detector = cv2.QRCodeDetector()

    candidates = [image]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    candidates.append(gray)
    candidates.append(cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC))
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates.append(th)
    candidates.append(cv2.resize(th, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_NEAREST))

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


def test_qr_from_card_and_certificate_resolve_to_public_verification():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL no definido")
    assert CARD_IMG.exists(), f"Falta evidencia {CARD_IMG}"
    assert CERT_IMG.exists(), f"Falta evidencia {CERT_IMG}"

    card_qr = _decode_qr(CARD_IMG)
    cert_qr = _decode_qr(CERT_IMG)

    assert "/verificar/carnet/" in card_qr
    assert "/verificar/carnet/" in cert_qr

    token_card = card_qr.rstrip("/").split("/")[-1]
    token_cert = cert_qr.rstrip("/").split("/")[-1]
    assert token_card == token_cert

    verify = requests.get(f"{BASE_URL}/api/public/membership/verify/{token_card}", timeout=30)
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    assert payload.get("status") in {"active", "expired", "inactive", "invalid"}
    assert isinstance(payload.get("member_number"), str) and payload.get("member_number")


def test_card_pdf_is_exact_cr80_two_pages_and_certificate_is_letter_landscape():
    assert CARD_PDF.exists(), f"No existe {CARD_PDF}"
    assert CERT_PDF.exists(), f"No existe {CERT_PDF}"

    card_pages, (card_w_pt, card_h_pt) = _pdf_page_count_and_mediabox(CARD_PDF)
    assert card_pages == 2
    card_w_mm = _pt_to_mm(card_w_pt)
    card_h_mm = _pt_to_mm(card_h_pt)
    assert abs(card_w_mm - 85.60) < 0.15
    assert abs(card_h_mm - 53.98) < 0.15
    assert abs((card_w_mm / card_h_mm) - (85.6 / 53.98)) < 0.01

    cert_pages, (cert_w_pt, cert_h_pt) = _pdf_page_count_and_mediabox(CERT_PDF)
    assert cert_pages == 1
    assert abs(cert_w_pt - 792.0) < 0.2
    assert abs(cert_h_pt - 612.0) < 0.2
    assert abs((cert_w_pt / cert_h_pt) - (11 / 8.5)) < 0.01
