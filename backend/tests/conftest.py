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


# Las pruebas crean y borran datos: NUNCA contra la base de producción.
# Solo se permiten bases cuyo nombre diga "test" y nunca dentro de Railway.
_db_name = os.environ.get("DB_NAME") or ""
if "test" not in _db_name.lower() or os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"):
    raise SystemExit(f"Pruebas bloqueadas: DB_NAME={_db_name!r} no es una base de pruebas (debe contener 'test') o se está en Railway. "
                     "Las pruebas nunca deben escribir en producción.")


# Muchas pruebas hablan por HTTP con REACT_APP_BACKEND_URL: solo se permite un servidor local
# (auditoría, datos 1.2). Un candado de base «test» no sirve si las peticiones van a producción.
_backend_url = (os.environ.get("REACT_APP_BACKEND_URL") or "").lower()
if _backend_url and not any(host in _backend_url for host in ("://localhost", "://127.0.0.1", "://0.0.0.0")):
    raise SystemExit(f"Pruebas bloqueadas: REACT_APP_BACKEND_URL={_backend_url!r} no es un servidor local. "
                     "Las pruebas nunca deben escribir en producción.")


def create_persona_account(email: str, password: str, nombre: str = "QA Persona") -> None:
    """Cuenta Persona de prueba directo en la base de PRUEBAS (el registro libre está cerrado)."""
    client = MongoClient(os.environ["MONGO_URL"])
    try:
        client[os.environ["DB_NAME"]].users.insert_one({
            "nombre": nombre, "email": email.lower(), "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            "rol": "persona", "is_active": True, "token_version": 1, "created_at": datetime.now(timezone.utc),
        })
    finally:
        client.close()


FINANCE_TEAM = ("qa.finance.team@example.com", "QaFinanceTeam2026!")


def finance_team_token(base_url: str) -> str:
    """Nuevo flujo de Finanzas: la pastora solo consulta, así que las pruebas que REGISTRAN contribuciones o
    depósitos usan una cuenta del equipo de Finanzas (grupo Finanzas + Consultar/Administrar + roles de la
    colecta), creada en la base de PRUEBAS."""
    client = MongoClient(os.environ["MONGO_URL"])
    try:
        client[os.environ["DB_NAME"]].users.update_one({"email": FINANCE_TEAM[0]}, {"$set": {
            "nombre": "QA Equipo Finanzas", "password": bcrypt.hashpw(FINANCE_TEAM[1].encode(), bcrypt.gensalt()).decode(), "rol": "lider", "access_level": "lider",
            "is_active": True, "token_version": 1, "must_change_password": False, "onboarding_required": False, "permissions_mode": "manual",
            "privilege_groups": ["finance"], "capabilities": ["finance.read", "finance.manage", "finance.collection.record", "finance.treasury"],
            "access_scope": {"persons": "created_by"}}, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}}, upsert=True)
        client[os.environ["DB_NAME"]].login_attempts.delete_many({})
    finally:
        client.close()
    response = requests.post(f"{base_url.rstrip('/')}/api/auth/login", json={"email": FINANCE_TEAM[0], "password": FINANCE_TEAM[1]}, timeout=30)
    assert response.status_code == 200, response.text
    return response.json()["token"]


def seed_legacy_contribution(fields: dict) -> str:
    """Un registro ANTIGUO de contribución (de antes de la Colecta) en la base de PRUEBAS, para probar lo que
    se sigue haciendo con el historial (depósitos, correcciones, listados). Los aportes nuevos van por la Colecta."""
    from uuid import uuid4
    contribution_id = str(uuid4())
    now = datetime.now(timezone.utc)
    doc = {"_id": contribution_id, "contribution_id": contribution_id, "person_id": None, "anonymous": True, "household_id": None, "source": "manual",
           "batch_id": None, "deposit_id": None, "journal_entry_id": None, "status": "recorded", "created_by_user_id": "qa-legacy", "created_at": now, "updated_at": now, **fields}
    doc.setdefault("accounting_date", doc.get("received_date"))
    client = MongoClient(os.environ["MONGO_URL"])
    try:
        client[os.environ["DB_NAME"]].finance_contributions.insert_one(doc)
    finally:
        client.close()
    return contribution_id


CAMPAIGN_RECEIVER = ("qa.campaign.receiver@example.com", "QaCampaignRecv2026!")
_receiver_token = {}


def campaign_receiver_headers(base_url: str | None = None) -> dict:
    """Decisión del dueño: «Recibido»/verificar en Ven y Come lo hace SOLO el encargado de la campaña (permiso
    Operador Ven y Come), no la pastora. Cuenta QA con ese permiso, en la base de PRUEBAS."""
    base_url = (base_url or os.environ["REACT_APP_BACKEND_URL"]).rstrip("/")
    if base_url not in _receiver_token:
        client = MongoClient(os.environ["MONGO_URL"])
        try:
            client[os.environ["DB_NAME"]].users.update_one({"email": CAMPAIGN_RECEIVER[0]}, {"$set": {
                "nombre": "QA Encargado Ven y Come", "password": bcrypt.hashpw(CAMPAIGN_RECEIVER[1].encode(), bcrypt.gensalt()).decode(), "rol": "lider", "access_level": "lider",
                "is_active": True, "token_version": 1, "must_change_password": False, "onboarding_required": False, "permissions_mode": "manual",
                "privilege_groups": [], "capabilities": ["campaign.venycome.manage"], "access_scope": {"persons": "created_by"}},
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)}}, upsert=True)
            client[os.environ["DB_NAME"]].login_attempts.delete_many({})
        finally:
            client.close()
        response = requests.post(f"{base_url}/api/auth/login", json={"email": CAMPAIGN_RECEIVER[0], "password": CAMPAIGN_RECEIVER[1]}, timeout=30)
        assert response.status_code == 200, response.text
        _receiver_token[base_url] = response.json()["token"]
    return {"Authorization": f"Bearer {_receiver_token[base_url]}", "Content-Type": "application/json"}


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
    ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!", "QA Baptism Pastor", "pastor"),
    ("qa.baptismui53.lider@example.com", "QaBaptismUI53!", "QA Baptism Lider", "lider"),
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
        fixture_key = f"qa:session:{email}"
        existing_person = database.persons.find_one({"idempotency_key": fixture_key}, {"_id": 1})
        person_id = existing_person["_id"] if existing_person else ObjectId(); user_id = ObjectId()
        if not existing_person:
            database.persons.insert_one({"_id": person_id, "person_number": f"VV-QA{str(person_id)[-7:].upper()}", "nombre": name, "apellido": "Fixture", "search_key": f"{name} fixture".lower(), "idempotency_key": fixture_key, "version": 1, "created_at": now, "updated_at": now})
        defaults = access_defaults_for_role(role)
        database.users.insert_one({"_id": user_id, "nombre": name, "email": email, "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(), "rol": role, "person_id": str(person_id), "is_active": True, "token_version": 1, "created_at": now, **defaults})
        database.persons.update_one({"_id": person_id}, {"$set": {"auth_user_id": str(user_id), "updated_at": now}})


def pytest_sessionstart(session):
    ensure_qa_accounts()


def pytest_runtest_setup(item):
    ensure_qa_accounts()


def pytest_sessionfinish(session, exitstatus):
    subprocess.run([sys.executable, "/app/tests/ui_journey_v2_fixture.py", "cleanup"], check=False, capture_output=True, text=True)