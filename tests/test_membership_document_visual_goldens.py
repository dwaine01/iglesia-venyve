"""Contrato de arte versionado para documentos de membresía DESIGN LOCKED."""
import hashlib
import json
from pathlib import Path

from PIL import Image


ROOT = Path("/app")
REFERENCE = ROOT / "design-reference/membership-documents-master.png"
GOLDEN_DIR = ROOT / "design-reference/goldens"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_master_reference_is_versioned_and_immutable():
    assert REFERENCE.exists()
    assert Image.open(REFERENCE).size == (1536, 1024)
    assert digest(REFERENCE) == "1f4dd8f83801550a3f3f2496a991b4a4c1fc82a56b253d2c46665c705c2375f2"


def test_three_visual_goldens_and_pdf_render_are_versioned():
    manifest = json.loads((GOLDEN_DIR / "manifest.json").read_text())
    expected = {
        "membership-card-front.png": 85.6 / 53.98,
        "membership-card-back.png": 85.6 / 53.98,
        "membership-certificate.png": 11 / 8.5,
        "membership-certificate-pdf.png": 11 / 8.5,
    }
    for filename, ratio in expected.items():
        path = GOLDEN_DIR / filename
        assert path.exists(), filename
        image = Image.open(path)
        assert abs((image.width / image.height) - ratio) < 0.01
        assert digest(path) == manifest[filename]["sha256"]
        assert [image.width, image.height] == manifest[filename]["pixels"]