"""Iteración 52 - Decodificación QR desde capturas de preview UI."""

import json
from pathlib import Path

import cv2
import pytest
import requests


STATE_PATH = Path("/app/test_reports/iteration52_fixture.json")
CARD_PREVIEW = Path("/app/test_reports/artifacts_iter52/iteration52_card_front_preview.jpeg")
CERT_PREVIEW = Path("/app/test_reports/artifacts_iter52/iteration52_certificate_preview.jpeg")


def _decode_qr(path: Path) -> str:
    image = cv2.imread(str(path))
    assert image is not None, f"No se pudo cargar {path}"

    detector = cv2.QRCodeDetector()
    h, w = image.shape[:2]
    crops = [
        image,
        image[int(h * 0.25):int(h * 0.85), int(w * 0.45):int(w * 0.95)],
        image[int(h * 0.35):int(h * 0.92), int(w * 0.55):int(w * 0.98)],
    ]

    for item in crops:
        decoded, points, _ = detector.detectAndDecode(item)
        if points is not None and decoded:
            return decoded.strip()

        gray = cv2.cvtColor(item, cv2.COLOR_BGR2GRAY)
        decoded_gray, points_gray, _ = detector.detectAndDecode(cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC))
        if points_gray is not None and decoded_gray:
            return decoded_gray.strip()

    raise AssertionError(f"No se pudo decodificar QR en {path.name}")


def test_preview_qr_card_and_certificate_resolve_same_public_token():
    if not STATE_PATH.exists():
        pytest.skip("No existe fixture iteración 52")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    base_url = state["base_url"].rstrip("/")

    assert CARD_PREVIEW.exists(), f"Falta captura {CARD_PREVIEW}"
    assert CERT_PREVIEW.exists(), f"Falta captura {CERT_PREVIEW}"

    card_qr = _decode_qr(CARD_PREVIEW)
    cert_qr = _decode_qr(CERT_PREVIEW)
    assert "/verificar/carnet/" in card_qr
    assert "/verificar/carnet/" in cert_qr

    token_card = card_qr.rstrip("/").split("/")[-1]
    token_cert = cert_qr.rstrip("/").split("/")[-1]
    assert token_card == token_cert

    verify = requests.get(f"{base_url}/api/public/membership/verify/{token_card}", timeout=30)
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    assert payload.get("valid") is True
    assert isinstance(payload.get("member_number"), str) and payload.get("member_number", "").startswith("VV-I52-")
