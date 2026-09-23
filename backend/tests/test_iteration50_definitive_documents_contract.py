"""Contrato estático del master DESIGN LOCKED sin credenciales efímeras."""
import hashlib
from pathlib import Path


ROOT = Path("/app")


def test_master_reference_and_local_assets_are_versioned():
    master = ROOT / "design-reference/membership-documents-master.png"
    assert master.exists()
    assert hashlib.sha256(master.read_bytes()).hexdigest() == "43e86ca8eacbdff662bdfbe0d305afe57e8be9baac1eca94d1d0317a39cf8124"
    for path in (
        "frontend/public/assets/membership/church-logo.png",
        "frontend/src/assets/fonts/PlusJakartaSans-Variable.ttf",
        "frontend/src/assets/fonts/CormorantGaramond-Variable.ttf",
        "frontend/src/assets/fonts/CormorantGaramond-Italic-Variable.ttf",
    ):
        assert (ROOT / path).stat().st_size > 10_000


def test_physical_geometry_and_institution_are_locked_in_source():
    geometry = (ROOT / "frontend/src/components/membership/membershipDocumentGeometry.js").read_text()
    assert "width: 85.6, height: 53.98" in geometry
    assert "width: 279.4, height: 215.9" in geometry
    assert "PRIMERA IGLESIA DEL NAZARENO" in geometry
    assert "UNA FAMILIA PARA LA ETERNIDAD" in geometry
    assert "CONOCIENDO A DIOS · HACIENDO FAMILIA · TRANSFORMANDO VIDAS" in geometry


def test_qr_and_pdf_contract_are_configured_for_print():
    dialog = (ROOT / "frontend/src/components/membership/MembershipDocumentDialog.js").read_text()
    pdf = (ROOT / "frontend/src/components/membership/membershipPdf.js").read_text()
    css = (ROOT / "frontend/src/components/membership/membership-documents.css").read_text()
    assert "errorCorrectionLevel: 'Q'" in dialog
    assert "margin: 4" in dialog and "width: 900" in dialog
    assert "format: [85.6, 53.98]" in pdf
    assert "format: [11, 8.5]" in pdf
    assert "scale: 4" in pdf
    assert "toDataURL('image/png')" in pdf
    assert "image-rendering: pixelated" in css