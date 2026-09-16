"""Hace que los módulos backend sean importables al ejecutar pytest desde /app."""
import sys
import time
from pathlib import Path

import requests


BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


_ORIGINAL_REQUEST = requests.sessions.Session.request


def _request_with_connect_retry(self, method, url, **kwargs):
    for attempt in range(3):
        try:
            return _ORIGINAL_REQUEST(self, method, url, **kwargs)
        except requests.exceptions.ConnectTimeout:
            if attempt == 2:
                raise
            time.sleep(0.25 * (attempt + 1))


requests.sessions.Session.request = _request_with_connect_retry