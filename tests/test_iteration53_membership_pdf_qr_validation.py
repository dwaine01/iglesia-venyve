"""Iteración 53 - Validación de PDFs emitidos y QR desde render del reverso/certificado."""

import json
import re
from pathlib import Path

import cv2
import pypdfium2 as pdfium
import pytest
import requests


STATE_PATH = Path("/app/test_reports/iteration52_fixture.json")
CARD_PDF = Path("/app/test_reports/artifacts_iter53/iter53_card.pdf")
CERT_PDF = Path("/app/test_reports/artifacts_iter53/iter53_certificate.pdf")
ARTIFACTS_DIR = Path("/app/test_reports/artifacts_iter53")


def _pdf_page_count_and_mediabox(path: Path) -> tuple[int, tuple[float, float]]:
    raw = path.read_bytes()
    page_counts = [int(value) for value in re.findall(rb"/Count\s+(\d+)", raw)]
    media = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", raw)
    assert media, f"MediaBox no encontrado en {path.name}"
    width_pt = float(media[0][0])
    height_pt = float(media[0][1])
    return (max(page_counts) if page_counts else 0), (width_pt, height_pt)


def _render_pdf_page_to_png(pdf_path: Path, page_index: int, out_path: Path, scale: float = 4.0) -> Path:
    document = pdfium.PdfDocument(str(pdf_path))
    page = document.get_page(page_index)
    image = page.render(scale=scale).to_pil()
    image.save(out_path)
    page.close()
    document.close()
    return out_path


def _decode_qr(path: Path) -> str:
    image = cv2.imread(str(path))
    assert image is not None, f"No se pudo cargar {path}"
    detector = cv2.QRCodeDetector()

    h, w = image.shape[:2]
    candidates = [
        image,
        image[int(h * 0.58):, int(w * 0.60):],
        image[int(h * 0.62):, int(w * 0.68):],
    ]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    candidates.extend(
        [
            gray,
            cv2.resize(gray, None, fx=2.8, fy=2.8, interpolation=cv2.INTER_CUBIC),
            cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC),
        ]
    )

    for candidate in candidates:
        decoded, points, _ = detector.detectAndDecode(candidate)
        if points is not None and decoded:
            return decoded.strip()

    raise AssertionError(f"No se pudo decodificar QR en {path.name}")


def test_pdf_dimensions_contract():
    assert CARD_PDF.exists(), f"Falta {CARD_PDF}"
    assert CERT_PDF.exists(), f"Falta {CERT_PDF}"

    card_pages, (card_w, card_h) = _pdf_page_count_and_mediabox(CARD_PDF)
    assert card_pages == 2
    assert abs(card_w - 242.645669) < 0.4
    assert abs(card_h - 153.014173) < 0.4

    cert_pages, (cert_w, cert_h) = _pdf_page_count_and_mediabox(CERT_PDF)
    assert cert_pages == 1
    assert abs(cert_w - 792.0) < 0.4
    assert abs(cert_h - 612.0) < 0.4


def test_qr_from_card_back_pdf_and_certificate_pdf_validate_member_number():
    if not STATE_PATH.exists():
        pytest.skip("No existe fixture de estado iteración 52")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    base_url = state["base_url"].rstrip("/")
    expected_member_number = state["member_number"]

    card_back_png = _render_pdf_page_to_png(CARD_PDF, page_index=1, out_path=ARTIFACTS_DIR / "iter53_card_back_pdf_render.png")
    cert_png = _render_pdf_page_to_png(CERT_PDF, page_index=0, out_path=ARTIFACTS_DIR / "iter53_certificate_pdf_render.png")

    card_qr = _decode_qr(card_back_png)
    cert_qr = _decode_qr(cert_png)
    assert "/verificar/carnet/" in card_qr
    assert "/verificar/carnet/" in cert_qr

    token_card = card_qr.rstrip("/").split("/")[-1]
    token_cert = cert_qr.rstrip("/").split("/")[-1]
    assert token_card == token_cert

    verify = requests.get(f"{base_url}/api/public/membership/verify/{token_card}", timeout=30)
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    assert payload.get("valid") is True
    assert payload.get("member_number") == expected_member_number
