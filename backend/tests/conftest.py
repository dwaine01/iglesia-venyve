"""Hace que los módulos backend sean importables al ejecutar pytest desde /app."""
import os
import sys
import time
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
from bson import ObjectId
from pymongo import MongoClient
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


QA_ACCOUNTS = [
    ("coreqa.pastor@example.com", "CoreQA2026!Pastor", "Core QA Pastor", "pastor"),
    ("coreqa.leader@example.com", "CoreQA2026!Leader", "Core QA Leader", "lider"),
    ("coreqa.member@example.com", "CoreQA2026!Member", "Core QA Member", "persona"),
    ("access01.ui@example.com", "Access01UiTest!", "ACCESS-01 UI Leader", "lider"),
]


def ensure_qa_accounts():
    from access_control import access_defaults_for_role
    database = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    for email, password, name, role in QA_ACCOUNTS:
        database.login_attempts.delete_one({"identifier": hashlib.sha256(email.encode("utf-8")).hexdigest()})
        existing = database.users.find_one({"email": email})
        if existing and existing.get("person_id") and ObjectId.is_valid(existing["person_id"]) and database.persons.find_one({"_id": ObjectId(existing["person_id"])}, {"_id": 1}):
            continue
        if existing:
            database.users.delete_one({"_id": existing["_id"]})
        person_id = ObjectId(); user_id = ObjectId()
        database.persons.insert_one({"_id": person_id, "person_number": f"VV-QA{str(person_id)[-7:].upper()}", "nombre": name, "apellido": "Fixture", "search_key": f"{name} fixture".lower(), "idempotency_key": f"qa:session:{email}", "version": 1, "created_at": now, "updated_at": now})
        defaults = access_defaults_for_role(role)
        database.users.insert_one({"_id": user_id, "nombre": name, "email": email, "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": str(person_id), "is_active": True, "token_version": 1, "created_at": now, **defaults})


def pytest_sessionstart(session):
    ensure_qa_accounts()


def pytest_runtest_setup(item):
    ensure_qa_accounts()


def pytest_sessionfinish(session, exitstatus):
    subprocess.run([sys.executable, "/app/tests/ui_journey_v2_fixture.py", "cleanup"], check=False, capture_output=True, text=True)