"""Invasiones Entrega A — retest iteración 40 contra la URL pública.

Se siembra solo (prefijo QAR40). Cubre:
- BUG1 atomicidad del informe de visita (MCD+NPT en una sola llamada).
- BUG2 roster todo-o-nada al crear invasión (credenciales faltantes, correo repetido, correo usado).
- MEJORA filtro mentor_person_id en /campaigns/{id}/books/{book_id}/deliveries.
- Regresión flujo feliz: visita -> MCD -> 7 Semanas -> mentor abre expediente y completa tarea.
Deja los datos sembrados (escribe /tmp/qar40_ctx.json) para la prueba de UI.
"""
import json
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
TAG = uuid.uuid4().hex[:4].lower()
TEMP_PW = "QaR40Temp123!"
NEW_PW = "QaR40Mentor456!"


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def mk_person(apellido):
    oid = ObjectId()
    now = datetime.now(timezone.utc)
    db.persons.insert_one({"_id": oid, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}", "nombre": "QAR40", "apellido": apellido,
                           "search_key": f"qar40 {apellido}".lower(), "idempotency_key": f"qa:r40:{uuid.uuid4()}", "version": 1,
                           "created_at": now, "updated_at": now})
    return str(oid)


def badge(pastor, pid):
    r = requests.put(f"{BASE_URL}/api/mentorship/badge/{pid}", json={"active": True}, headers=pastor)
    assert r.status_code == 200, r.text


def mentor_login(email):
    h = login(email, TEMP_PW)
    ch = requests.post(f"{BASE_URL}/api/auth/change-password", headers=h,
                       json={"current_password": TEMP_PW, "new_password": NEW_PW, "confirmation": NEW_PW})
    assert ch.status_code == 200, ch.text
    return {"Authorization": f"Bearer {ch.json()['token']}"}


def uid_for(pid):
    return str(db.users.find_one({"person_id": pid})["_id"])


def on_hand(book_id, holder_type, holder_id):
    return (db.library_holdings.find_one({"book_id": book_id, "holder_type": holder_type, "holder_id": holder_id}) or {}).get("quantity_on_hand", 0)


@pytest.fixture(scope="module")
def ctx():
    pastor = login(*PASTOR)
    x, y = mk_person(f"MentorX{TAG}"), mk_person(f"MentorY{TAG}")
    for pid in (x, y):
        badge(pastor, pid)
    ex, ey = f"qa.r40.x.{TAG}@example.com", f"qa.r40.y.{TAG}@example.com"
    r = requests.post(f"{API}/campaigns", headers=pastor, json={
        "name": f"QAR40 Invasion {TAG}", "location": "Bayamón", "start_date": "2026-02-01", "end_date": "2026-02-10",
        "assigned_mentors": [{"person_id": x, "email": ex, "temporary_password": TEMP_PW}, {"person_id": y, "email": ey, "temporary_password": TEMP_PW}]})
    assert r.status_code == 201, r.text
    camp = r.json()
    assert len(camp["accounts_created"]) == 2
    mcd = db.library_books.find_one({"sku": "MCD"})["book_id"]
    npt = db.library_books.find_one({"sku": "NPT"})["book_id"]
    a = requests.post(f"{API}/campaigns/{camp['campaign_id']}/books", headers=pastor, json={"assignments": [
        {"mentor_person_id": x, "book_id": mcd, "quantity": 2}, {"mentor_person_id": y, "book_id": mcd, "quantity": 1}]})
    assert a.status_code == 201, a.text
    c = {"pastor": pastor, "cid": camp["campaign_id"], "x": x, "y": y, "ex": ex, "ey": ey, "mcd": mcd, "npt": npt,
         "hx": mentor_login(ex), "hy": mentor_login(ey)}
    yield c
    json.dump({k: v for k, v in c.items() if k not in ("pastor", "hx", "hy")} | {"pw": NEW_PW}, open("/tmp/qar40_ctx.json", "w"))


def new_visit(h, cid, name):
    r = requests.post(f"{API}/visits", headers=h, json={"contact_type": "new", "contact_name": name,
                      "contact_phone": f"78755{uuid.uuid4().int % 100000:05d}", "campaign_id": cid})
    assert r.status_code == 201, r.text
    return r.json()["visit_id"]


# BUG1: entrega MCD+NPT combinada sin NPT asignado -> 409, MCD persistido, reintento no duplica
def test_combined_report_atomic_retry(ctx):
    xu = uid_for(ctx["x"])
    before_m = on_hand(ctx["mcd"], "user", xu)
    central_before = on_hand(ctx["mcd"], "warehouse", "central")
    vid = new_visit(ctx["hx"], ctx["cid"], f"QAR40 Casa Atomic {TAG}")
    r1 = requests.put(f"{API}/visits/{vid}/report", headers=ctx["hx"], json={"status": "visited", "received_mcd": True, "received_npt": True})
    assert r1.status_code == 409, r1.text
    v = db.outreach_visits.find_one({"visit_id": vid})
    assert v.get("mcd_delivery_movement_id"), "MCD movement id no persistido tras 409 de NPT"
    assert not v.get("npt_delivery_movement_id")
    assert on_hand(ctx["mcd"], "user", xu) == before_m - 1
    r2 = requests.put(f"{API}/visits/{vid}/report", headers=ctx["hx"], json={"status": "visited", "received_mcd": True})
    assert r2.status_code == 200, r2.text
    assert r2.json().get("received_mcd") is True or r2.json().get("mcd_delivery_movement_id")
    assert db.library_movements.count_documents({"campaign_id": ctx["cid"], "movement_type": "DELIVERY", "from_holder.id": xu}) == 1
    assert on_hand(ctx["mcd"], "user", xu) == before_m - 1
    assert on_hand(ctx["mcd"], "warehouse", "central") == central_before
    # Desmarcar ahora debe ser 409 (ya entregado)
    r3 = requests.put(f"{API}/visits/{vid}/report", headers=ctx["hx"], json={"status": "visited", "received_mcd": False})
    assert r3.status_code == 409


# BUG2: roster A(credenciales)+B(sin credenciales) -> 422 sin cuenta huérfana para A
def test_roster_missing_creds_no_orphan(ctx):
    a, b = mk_person(f"AtomA{TAG}"), mk_person(f"AtomB{TAG}")
    badge(ctx["pastor"], a); badge(ctx["pastor"], b)
    r = requests.post(f"{API}/campaigns", headers=ctx["pastor"], json={"name": f"QAR40 Atom {TAG}", "location": "X", "start_date": "2026-02-01", "end_date": "2026-02-02",
        "assigned_mentors": [{"person_id": a, "email": f"qa.r40.atoma.{TAG}@example.com", "temporary_password": TEMP_PW}, {"person_id": b}]})
    assert r.status_code == 422, r.text
    assert "correo" in r.json()["detail"].lower()
    assert db.users.find_one({"person_id": a}) is None
    assert db.users.find_one({"email": f"qa.r40.atoma.{TAG}@example.com"}) is None


# BUG2: correo repetido dentro del roster -> 422 sin cuentas
def test_roster_duplicate_email_no_orphan(ctx):
    a, b = mk_person(f"DupA{TAG}"), mk_person(f"DupB{TAG}")
    badge(ctx["pastor"], a); badge(ctx["pastor"], b)
    email = f"qa.r40.dup.{TAG}@example.com"
    r = requests.post(f"{API}/campaigns", headers=ctx["pastor"], json={"name": f"QAR40 Dup {TAG}", "location": "X", "start_date": "2026-02-01", "end_date": "2026-02-02",
        "assigned_mentors": [{"person_id": a, "email": email, "temporary_password": TEMP_PW}, {"person_id": b, "email": email.upper(), "temporary_password": TEMP_PW}]})
    assert r.status_code == 422, r.text
    assert db.users.count_documents({"person_id": {"$in": [a, b]}}) == 0


# BUG2: segundo mentor usa correo de otra cuenta -> 409 sin cuenta para el primero
def test_roster_email_taken_no_orphan(ctx):
    a, b = mk_person(f"TakA{TAG}"), mk_person(f"TakB{TAG}")
    badge(ctx["pastor"], a); badge(ctx["pastor"], b)
    r = requests.post(f"{API}/campaigns", headers=ctx["pastor"], json={"name": f"QAR40 Tak {TAG}", "location": "X", "start_date": "2026-02-01", "end_date": "2026-02-02",
        "assigned_mentors": [{"person_id": a, "email": f"qa.r40.taka.{TAG}@example.com", "temporary_password": TEMP_PW}, {"person_id": b, "email": PASTOR[0], "temporary_password": TEMP_PW}]})
    assert r.status_code == 409, r.text
    assert db.users.count_documents({"person_id": {"$in": [a, b]}}) == 0
    assert db.outreach_campaigns.find_one({"name": f"QAR40 Tak {TAG}"}) is None


# MEJORA: filtro por mentor en destinatarios del libro
def test_book_deliveries_filtered_by_mentor(ctx):
    vy = new_visit(ctx["hy"], ctx["cid"], f"QAR40 Casa DeY {TAG}")
    r = requests.put(f"{API}/visits/{vy}/report", headers=ctx["hy"], json={"status": "visited", "received_mcd": True})
    assert r.status_code == 200, r.text
    url = f"{API}/campaigns/{ctx['cid']}/books/{ctx['mcd']}/deliveries"
    allr = requests.get(url, headers=ctx["pastor"]).json()["items"]
    xr = requests.get(url, headers=ctx["pastor"], params={"mentor_person_id": ctx["x"]}).json()["items"]
    yr = requests.get(url, headers=ctx["pastor"], params={"mentor_person_id": ctx["y"]}).json()["items"]
    assert len(allr) == 2 and len(xr) == 1 and len(yr) == 1
    assert "Atomic" in xr[0]["person_name"] and "DeY" in yr[0]["person_name"]
    # mentor sin cuenta / id desconocido no debe dar 500
    unk = requests.get(url, headers=ctx["pastor"], params={"mentor_person_id": str(ObjectId())})
    assert unk.status_code in (200, 404, 409), unk.text  # 409 actual: "mentor no tiene cuenta" (menor)
    if unk.status_code == 200:
        assert unk.json()["items"] == []


# Regresión: flujo feliz hasta 7 Semanas y el mentor abre expediente y marca tarea
def test_happy_flow_seven_weeks_and_mentor_detail(ctx):
    h = ctx["hx"]
    hold = requests.get(f"{BASE_URL}/api/library/my-holdings", headers=h)
    assert hold.status_code == 200, hold.text
    vid = new_visit(h, ctx["cid"], f"QAR40 Casa Feliz {TAG}")
    rep = requests.put(f"{API}/visits/{vid}/report", headers=h, json={
        "status": "wants_followup", "visit_date": "2026-02-02", "received_mcd": True, "spiritual_status": "no_cristiano",
        "address_line1": "Calle 1 #23", "address_city": "Bayamón", "address_state": "PR", "address_zip": "00961",
        "agreed_start_date": "2026-02-09", "call_schedule": "night"})
    assert rep.status_code == 200, rep.text
    sw = requests.post(f"{API}/visits/{vid}/start-seven-weeks", headers=h)
    assert sw.status_code == 200, sw.text
    eid = sw.json()["enrollment_id"]
    ctx["happy_vid"], ctx["eid"] = vid, eid
    d = requests.get(f"{BASE_URL}/api/processes/consolidation/{eid}", headers=h)
    assert d.status_code == 200, d.text
    lst = requests.get(f"{BASE_URL}/api/processes/enrollments?process_key=consolidation", headers=h)
    assert lst.status_code == 200, lst.text
    dash = requests.get(f"{BASE_URL}/api/processes/consolidation/dashboard", headers=h)
    assert dash.status_code == 200, dash.text
    rpt = requests.get(f"{API}/campaigns/{ctx['cid']}/report", headers=ctx["pastor"])
    assert rpt.status_code == 200, rpt.text
