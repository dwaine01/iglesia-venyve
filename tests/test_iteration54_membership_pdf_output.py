"""Iteración 54: validación de geometría/raster/QR en PDFs descargados desde flujo UI real."""

# Módulo: contrato PDF (CR80/Letter), determinismo de doble descarga, QR público
import hashlib
import json
import re
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest
import requests


STATE_PATH = Path("/app/test_reports/iteration52_fixture.json")
CARD_1_PDF = Path("/app/test_reports/artifacts_iter54/iter54_card_1.pdf")
CARD_2_PDF = Path("/app/test_reports/artifacts_iter54/iter54_card_2.pdf")
CERT_PDF = Path("/app/test_reports/artifacts_iter54/iter54_certificate.pdf")
PROD_PDF = Path("/app/test_reports/production-damaris-card.pdf")
ARTIFACTS_DIR = Path("/app/test_reports/artifacts_iter54")


def _pdf_page_count_and_mediabox(path: Path) -> tuple[int, tuple[float, float]]:
    raw = path.read_bytes()
    page_counts = [int(value) for value in re.findall(rb"/Count\s+(\d+)", raw)]
    media = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", raw)
    assert media, f"MediaBox no encontrado en {path.name}"
    width_pt = float(media[0][0])
    height_pt = float(media[0][1])
    return (max(page_counts) if page_counts else 0), (width_pt, height_pt)


def _render_page(pdf_path: Path, page_index: int, scale: float):
    document = pdfium.PdfDocument(str(pdf_path))
    page = document.get_page(page_index)
    image = page.render(scale=scale).to_pil()
    page.close()
    document.close()
    return np.array(image.convert("RGB"))


def _save_png(rgb_array: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR))


def _decode_qr_from_rgb(rgb_image: np.ndarray) -> str:
    detector = cv2.QRCodeDetector()
    bgr = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]

    candidates = [
        bgr,
        bgr[int(h * 0.56):, int(w * 0.56):],
        bgr[int(h * 0.62):, int(w * 0.64):],
    ]

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    candidates.extend([
        gray,
        cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC),
        cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC),
    ])

    for candidate in candidates:
        decoded, points, _ = detector.detectAndDecode(candidate)
        if points is not None and decoded:
            return decoded.strip()
    return ""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_image_dimensions(path: Path) -> list[tuple[int, int]]:
    raw = path.read_bytes()
    pairs = re.findall(rb"/Width\s+(\d+)\s*/Height\s+(\d+)", raw)
    return [(int(w), int(h)) for w, h in pairs]


def test_card_and_certificate_pdf_geometry_and_reference_delta():
    assert CARD_1_PDF.exists(), f"Falta {CARD_1_PDF}"
    assert CARD_2_PDF.exists(), f"Falta {CARD_2_PDF}"
    assert CERT_PDF.exists(), f"Falta {CERT_PDF}"
    assert PROD_PDF.exists(), f"Falta {PROD_PDF}"

    card_pages, (card_w_pt, card_h_pt) = _pdf_page_count_and_mediabox(CARD_1_PDF)
    assert card_pages == 2
    assert abs(card_w_pt - 242.645669) < 0.4
    assert abs(card_h_pt - 153.014173) < 0.4

    cert_pages, (cert_w_pt, cert_h_pt) = _pdf_page_count_and_mediabox(CERT_PDF)
    assert cert_pages == 1
    assert abs(cert_w_pt - 792.0) < 0.4
    assert abs(cert_h_pt - 612.0) < 0.4

    prod_pages, _ = _pdf_page_count_and_mediabox(PROD_PDF)
    assert prod_pages == 2


def test_card_raster_resolution_and_double_download_determinism():
    image_dims = _extract_image_dimensions(CARD_1_PDF)
    assert (2764, 1743) in image_dims

    _, (card_w_pt, _) = _pdf_page_count_and_mediabox(CARD_1_PDF)
    card_scale = 2764 / card_w_pt

    card1_front = _render_page(CARD_1_PDF, 0, card_scale)
    card1_back = _render_page(CARD_1_PDF, 1, card_scale)
    card2_front = _render_page(CARD_2_PDF, 0, card_scale)
    card2_back = _render_page(CARD_2_PDF, 1, card_scale)

    _save_png(card1_front, ARTIFACTS_DIR / "iter54_card1_front_render.png")
    _save_png(card1_back, ARTIFACTS_DIR / "iter54_card1_back_render.png")
    _save_png(card2_front, ARTIFACTS_DIR / "iter54_card2_front_render.png")
    _save_png(card2_back, ARTIFACTS_DIR / "iter54_card2_back_render.png")

    assert abs(card1_front.shape[1] - 2764) <= 1 and abs(card1_front.shape[0] - 1743) <= 1
    assert abs(card1_back.shape[1] - 2764) <= 1 and abs(card1_back.shape[0] - 1743) <= 1

    # Determinismo raster por página entre dos descargas consecutivas
    assert _sha256_bytes(card1_front.tobytes()) == _sha256_bytes(card2_front.tobytes())
    assert _sha256_bytes(card1_back.tobytes()) == _sha256_bytes(card2_back.tobytes())

    # Presencia de arte vectorial en borde derecho del frente (evita desaparición de capas)
    right_band = card1_front[:, int(card1_front.shape[1] * 0.78):, :]
    non_white = np.sum(np.any(right_band < 245, axis=2))
    assert non_white > 100000


def test_certificate_raster_resolution_and_qr_public_verification_member_number():
    if not STATE_PATH.exists():
        pytest.skip("No existe estado de fixture")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    base_url = state["base_url"].rstrip("/")
    expected_member_number = state["member_number"]

    _, (cert_w_pt, _) = _pdf_page_count_and_mediabox(CERT_PDF)
    cert_scale = 2112 / cert_w_pt
    cert_rgb = _render_page(CERT_PDF, 0, cert_scale)
    _save_png(cert_rgb, ARTIFACTS_DIR / "iter54_certificate_render.png")
    assert cert_rgb.shape[1] == 2112 and cert_rgb.shape[0] == 1632

    _, (card_w_pt, _) = _pdf_page_count_and_mediabox(CARD_1_PDF)
    card_scale = 2764 / card_w_pt
    card_front = _render_page(CARD_1_PDF, 0, card_scale)
    card_back = _render_page(CARD_1_PDF, 1, card_scale)

    card_back_qr = _decode_qr_from_rgb(card_back)
    cert_qr = _decode_qr_from_rgb(cert_rgb)
    card_front_qr = _decode_qr_from_rgb(card_front)

    assert "/verificar/carnet/" in card_back_qr
    assert "/verificar/carnet/" in cert_qr
    assert card_front_qr == ""  # QR solo reverso en carnet

    token_card = card_back_qr.rstrip("/").split("/")[-1]
    token_cert = cert_qr.rstrip("/").split("/")[-1]
    assert token_card == token_cert

    verify = requests.get(f"{base_url}/api/public/membership/verify/{token_card}", timeout=30)
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    assert payload.get("valid") is True
    assert payload.get("member_number") == expected_member_number
