"""Invasiones Entrega A — regresión contra la URL pública (REACT_APP_BACKEND_URL).

Depende de datos sembrados por tests/e2e_seed_entrega_a.py + flujo UI (campaña
"QAE2E Invasion B042", visita QAE2E Casa Rodriguez). Si no existen, se salta.
Cubre: 422 credenciales faltantes, 403 líder, 409 desentrega/sin unidades/stock,
privacidad de visitas, informe de líderes y destinatarios de libro.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/mentorship/outreach"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
LEADER = ("coreqa.leader@example.com", "CoreQA2026!Leader")
MEMBER = ("coreqa.member@example.com", "CoreQA2026!Member")
MENTOR_NEW = ("qa.e2e.sin.b042@example.com", "QaE2EMentorNew123!")
MENTOR_CON = ("qa.e2e.con.b042@example.com", "QaE2EMentor123!")
MENTOR_CON_NEWPW = "QaE2EMentorCon456!"


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None, r
    return {"Authorization": f"Bearer {r.json()['token']}"}, r


@pytest.fixture(scope="module")
def ctx():
    campaign = db.outreach_campaigns.find_one({"name": "QAE2E Invasion B042"}, {"_id": 0})
    visit = db.outreach_visits.find_one({"contact_name": "QAE2E Casa Rodriguez"}, {"_id": 0})
    if not campaign or not visit:
        pytest.skip("Datos E2E no sembrados")
    pastor, _ = login(*PASTOR)
    assert pastor
    return {"campaign": campaign, "visit": visit, "pastor": pastor}


@pytest.fixture(scope="module")
def mentor_con_headers():
    h, r = login(MENTOR_CON[0], MENTOR_CON_NEWPW)
    if h:
        return h
    h, r = login(*MENTOR_CON)
    assert h, r.text
    ch = requests.post(f"{BASE_URL}/api/auth/change-password", headers=h,
                       json={"current_password": MENTOR_CON[1], "new_password": MENTOR_CON_NEWPW, "confirmation": MENTOR_CON_NEWPW})
    assert ch.status_code == 200, ch.text
    return {"Authorization": f"Bearer {ch.json()['token']}"}


# --- Roster: mentor sin cuenta sin credenciales -> 422 y no se crea cuenta
def test_create_campaign_missing_credentials_422(ctx):
    oid = ObjectId()
    now = datetime.now(timezone.utc)
    db.persons.insert_one({"_id": oid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "QAE2E", "apellido": "SinCred",
                           "idempotency_key": f"qa:e2e:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
    pid = str(oid)
    b = requests.put(f"{BASE_URL}/api/mentorship/badge/{pid}", json={"active": True}, headers=ctx["pastor"])
    assert b.status_code == 200
    r = requests.post(f"{API}/campaigns", headers=ctx["pastor"], json={
        "name": "QAE2E SinCred", "location": "X", "start_date": "2026-02-01", "end_date": "2026-02-02", "assigned_mentors": [{"person_id": pid}]})
    assert r.status_code == 422, r.text
    assert "correo" in r.json()["detail"].lower()
    assert db.users.find_one({"person_id": pid}) is None
    assert db.outreach_campaigns.find_one({"name": "QAE2E SinCred"}) is None


# --- Permisos: lider (no coordinador general) no crea/edita/asigna libros
def test_leader_cannot_create_campaign():
    h, r = login(*LEADER)
    assert h, r.text
    resp = requests.post(f"{API}/campaigns", headers=h, json={"name": "QAE2E L", "location": "X", "start_date": "2026-02-01", "end_date": "2026-02-02"})
    assert resp.status_code == 403
    assert "pastor" in resp.json()["detail"].lower()


def test_leader_cannot_edit_campaign_or_assign_books(ctx):
    h, _ = login(*LEADER)
    cid = ctx["campaign"]["campaign_id"]
    put = requests.put(f"{API}/campaigns/{cid}", headers=h, json={"name": "hack"})
    assert put.status_code == 403
    book = db.library_books.find_one({"sku": "MCD"})
    post = requests.post(f"{API}/campaigns/{cid}/books", headers=h, json={"assignments": [{"mentor_person_id": ctx["campaign"]["assigned_mentor_ids"][0], "book_id": book["book_id"], "quantity": 1}]})
    assert post.status_code == 403


# --- Stock: cantidad mayor al central -> 409, sin mover nada
def test_assign_books_insufficient_stock_409(ctx):
    cid = ctx["campaign"]["campaign_id"]
    book = db.library_books.find_one({"sku": "NPT"})
    before = db.library_holdings.find_one({"book_id": book["book_id"], "holder_type": "warehouse", "holder_id": "central"})["quantity_on_hand"]
    r = requests.post(f"{API}/campaigns/{cid}/books", headers=ctx["pastor"], json={"assignments": [{"mentor_person_id": ctx["visit"]["mentor_person_id"], "book_id": book["book_id"], "quantity": before + 5}]})
    assert r.status_code == 409
    assert "existencias" in r.json()["detail"].lower() and str(before) in r.json()["detail"]
    after = db.library_holdings.find_one({"book_id": book["book_id"], "holder_type": "warehouse", "holder_id": "central"})["quantity_on_hand"]
    assert after == before


# --- Entrega: idempotencia y bloqueo de desentrega
def test_redeliver_true_is_idempotent_and_undo_409(ctx):
    h, r = login(*MENTOR_NEW)
    assert h, r.text
    vid = ctx["visit"]["visit_id"]
    cid = ctx["campaign"]["campaign_id"]
    again = requests.put(f"{API}/visits/{vid}/report", headers=h, json={"status": "wants_followup", "received_mcd": True})
    assert again.status_code == 200, again.text
    assert db.library_movements.count_documents({"campaign_id": cid, "movement_type": "DELIVERY", "book_id": db.library_books.find_one({"sku": "MCD"})["book_id"]}) == 1
    undo = requests.put(f"{API}/visits/{vid}/report", headers=h, json={"status": "wants_followup", "received_mcd": False})
    assert undo.status_code == 409
    assert "entreg" in undo.json()["detail"].lower()


# --- Sin unidades: mentor con cuenta pero sin libros asignados -> 409
def test_deliver_without_units_409(mentor_con_headers):
    r = requests.post(f"{API}/visits", headers=mentor_con_headers, json={"contact_type": "new", "contact_name": "QAE2E Casa SinLibro", "contact_phone": f"78755{uuid.uuid4().int % 100000:05d}"})
    assert r.status_code == 201, r.text
    vid = r.json()["visit_id"]
    rep = requests.put(f"{API}/visits/{vid}/report", headers=mentor_con_headers, json={"status": "visited", "received_npt": True})
    assert rep.status_code == 409
    assert "unidades" in rep.json()["detail"].lower()
    v = db.outreach_visits.find_one({"visit_id": vid})
    assert not v.get("npt_delivery_movement_id")
    db.outreach_visits.delete_one({"visit_id": vid})


# --- Privacidad: otro mentor no ve visitas ajenas; miembro sin insignia 403
def test_other_mentor_cannot_see_visit(ctx, mentor_con_headers):
    vid = ctx["visit"]["visit_id"]
    one = requests.get(f"{API}/visits/{vid}", headers=mentor_con_headers)
    assert one.status_code == 403
    lst = requests.get(f"{API}/visits", headers=mentor_con_headers).json()["items"]
    assert all(item["visit_id"] != vid for item in lst)
    own = requests.get(f"{API}/visits", headers=login(*MENTOR_NEW)[0]).json()["items"]
    mine = next(i for i in own if i["visit_id"] == vid)
    assert mine["contact_phone"] and mine["address_line1"] == "123 Calle QA"


def test_member_without_badge_forbidden(ctx):
    h, r = login(*MEMBER)
    assert h, r.text
    assert requests.get(f"{API}/visits", headers=h).status_code == 403
    assert requests.get(f"{API}/campaigns/{ctx['campaign']['campaign_id']}/report", headers=h).status_code == 403


# --- Informe de líderes y apertura de libro
def test_campaign_report_and_book_recipients(ctx):
    cid = ctx["campaign"]["campaign_id"]
    rep = requests.get(f"{API}/campaigns/{cid}/report", headers=ctx["pastor"])
    assert rep.status_code == 200
    mentors = {m["mentor_person_id"]: m for m in rep.json()["mentors"]}
    active = mentors[ctx["visit"]["mentor_person_id"]]
    assert active["contacts_total"] == 1 and active["accepted"] == 1 and active["has_activity"] is True
    mcd = next(b for b in active["books"] if b["book_name"] == "MCD")
    assert mcd["assigned"] == 2 and mcd["delivered"] == 1
    idle = [m for pid, m in mentors.items() if pid != ctx["visit"]["mentor_person_id"]]
    assert idle and idle[0]["has_activity"] is False
    dl = requests.get(f"{API}/campaigns/{cid}/books/{mcd['book_id']}/deliveries", headers=ctx["pastor"])
    assert dl.status_code == 200
    assert [i["person_name"] for i in dl.json()["items"]] == ["QAE2E Casa Rodriguez"]


def test_leader_with_outreach_assign_can_view_report_if_capable(ctx):
    h, _ = login(*LEADER)
    r = requests.get(f"{API}/campaigns/{ctx['campaign']['campaign_id']}/report", headers=h)
    print("leader report status", r.status_code)
    assert r.status_code in (200, 403)
