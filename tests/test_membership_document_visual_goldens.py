"""Bloquea el master del usuario; los goldens se crearán solo tras su aprobación final."""
import hashlib
from pathlib import Path

from PIL import Image


ROOT = Path('/app')
MASTER = ROOT / 'design-reference/membership-documents-master.png'


def test_user_supplied_master_is_immutable():
    assert hashlib.sha256(MASTER.read_bytes()).hexdigest() == '43e86ca8eacbdff662bdfbe0d305afe57e8be9baac1eca94d1d0317a39cf8124'
    with Image.open(MASTER) as image:
        assert image.size == (1536, 1024)


def test_implementation_goldens_wait_for_explicit_user_approval():
    assert not (ROOT / 'design-reference/goldens').exists()