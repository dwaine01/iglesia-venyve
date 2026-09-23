"""Iteración 52 - Validación de PDF descargados, MediaBox y QR desde render PDF."""

import json
import re
from pathlib import Path

import cv2
import pypdfium2 as pdfium
import pytest
import requests


STATE_PATH = Path("/app/test_reports/iteration52_fixture.json")
CARD_PDF = Path("/app/test_reports/artifacts_iter52/iteration52_card.pdf")
CERT_PDF = Path("/app/test_reports/artifacts_iter52/iteration52_certificate.pdf")
RENDER_DIR = Path("/app/test_reports/artifacts_iter52")


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


def _render_pdf_page_to_png(pdf_path: Path, page_index: int, out_path: Path, scale: float = 4.0) -> Path:
    document = pdfium.PdfDocument(str(pdf_path))
    page = document.get_page(page_index)
    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()
    pil_image.save(out_path)
    page.close()
    document.close()
    return out_path


def _decode_qr_from_image(path: Path) -> str:
    image = cv2.imread(str(path))
    assert image is not None, f"No se pudo cargar {path}"

    detector = cv2.QRCodeDetector()
    candidates = [image]
    h, w = image.shape[:2]
    candidates.extend([
        image[int(h * 0.60):, int(w * 0.62):],
        image[int(h * 0.65):, int(w * 0.70):],
    ])

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    candidates.extend([
        gray,
        cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC),
        cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC),
    ])

    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates.extend([
        th,
        cv2.resize(th, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_NEAREST),
        cv2.resize(th, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_NEAREST),
    ])

    for candidate in candidates:
        decoded, points, _ = detector.detectAndDecode(candidate)
        if points is not None and decoded:
            return decoded.strip()

    raise AssertionError(f"No se pudo decodificar QR en {path.name}")


def test_downloaded_pdfs_have_expected_page_count_and_mediabox():
    assert CARD_PDF.exists(), f"No existe {CARD_PDF}"
    assert CERT_PDF.exists(), f"No existe {CERT_PDF}"

    card_pages, (card_w_pt, card_h_pt) = _pdf_page_count_and_mediabox(CARD_PDF)
    assert card_pages == 2
    assert abs(_pt_to_mm(card_w_pt) - 85.60) < 0.2
    assert abs(_pt_to_mm(card_h_pt) - 53.98) < 0.2

    cert_pages, (cert_w_pt, cert_h_pt) = _pdf_page_count_and_mediabox(CERT_PDF)
    assert cert_pages == 1
    assert abs(cert_w_pt - 792.0) < 0.3
    assert abs(cert_h_pt - 612.0) < 0.3


def test_qr_from_pdf_renders_points_to_same_public_token_and_member_number():
    if not STATE_PATH.exists():
        pytest.skip("No existe fixture iteración 52")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    base_url = state["base_url"].rstrip("/")
    expected_prefix = "VV-I52-"

    card_render = _render_pdf_page_to_png(CARD_PDF, page_index=0, out_path=RENDER_DIR / "iteration52_card_pdf_render.png")
    cert_render = _render_pdf_page_to_png(CERT_PDF, page_index=0, out_path=RENDER_DIR / "iteration52_certificate_pdf_render.png")

    card_qr = _decode_qr_from_image(card_render)
    cert_qr = _decode_qr_from_image(cert_render)

    assert "/verificar/carnet/" in card_qr
    assert "/verificar/carnet/" in cert_qr

    token_card = card_qr.rstrip("/").split("/")[-1]
    token_cert = cert_qr.rstrip("/").split("/")[-1]
    assert token_card == token_cert

    verify = requests.get(f"{base_url}/api/public/membership/verify/{token_card}", timeout=30)
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    assert isinstance(payload.get("member_number"), str) and payload.get("member_number", "").startswith(expected_prefix)
    assert payload.get("valid") is True
