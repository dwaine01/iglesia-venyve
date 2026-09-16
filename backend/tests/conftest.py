"""Hace que los módulos backend sean importables al ejecutar pytest desde /app."""
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values


APP_DIR = Path(__file__).resolve().parents[2]
BACKEND_ENV = dotenv_values(APP_DIR / "backend" / ".env")
FRONTEND_ENV = dotenv_values(APP_DIR / "frontend" / ".env")

for key in ("MONGO_URL", "DB_NAME", "JWT_SECRET", "CORS_ORIGINS", "CORS_ORIGIN_REGEX"):
    value = BACKEND_ENV.get(key)
    if value:
        os.environ[key] = str(value).strip('"')

if FRONTEND_ENV.get("REACT_APP_BACKEND_URL"):
    os.environ["REACT_APP_BACKEND_URL"] = str(FRONTEND_ENV["REACT_APP_BACKEND_URL"]).strip('"')


BACKEND_DIR = str(APP_DIR / "backend")
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