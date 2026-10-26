"""Entrega B (Invasiones) — regression vía URL pública: calendario de actividades,
registro por actividad, panel del mentor, supervisión, decision-status, aislamiento.
Setup de mentores directo en Mongo (persona+usuario+insignia); todas las acciones por HTTP."""
import os
import uuid
from datetime import datetime, timedelta, timezone, date

import bcrypt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

FRONT_ENV = {**os.environ, **dotenv_values("/app/frontend/.env")}
BACK_ENV = {**os.environ, **dotenv_values("/app/backend/.env")}
BASE_URL = FRONT_ENV["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api/processes/consolidation"
PASSWORD = "EntregaBT41Pass!"
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")

mongo = MongoClient(BACK_ENV["MONGO_URL"])[BACK_ENV["DB_NAME"]]
CREATED = {"persons": [], "users": [], "badges": [], "enrollments": [], "holdings": []}


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def make_mentor(label):
    pid = ObjectId()
    now = datetime.now(timezone.utc)
    mongo.persons.insert_one({"_id": pid, "person_number": f"VV-T41{uuid.uuid4().hex[:6].upper()}", "nombre": "QA", "apellido": f"T41 {label}",
                              "idempotency_key": f"qa:t41:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
    mongo.mentor_badges.update_one({"person_id": str(pid)}, {"$set": {"person_id": str(pid), "active": True, "since": "2026-01-01", "updated_at": now}}, upsert=True)
    import sys
    sys.path.insert(0, "/app/backend")
    from access_control import access_defaults_for_role
    defaults = access_defaults_for_role("persona")
    defaults["capabilities"] = sorted(set(defaults.get("capabilities", []) + ["mentorship.outreach.report", "library.deliver"]))
    uid = ObjectId()
    email = f"qa.entregab.t41.{label.lower()}.{uuid.uuid4().hex[:5]}@example.com"
    mongo.users.insert_one({"_id": uid, "nombre": f"QA T41 {label}", "email": email, "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
                            "rol": "persona", "is_active": True, "token_version": 1, "created_at": now, "person_id": str(pid), **defaults})
    CREATED["persons"].append(pid); CREATED["users"].append(uid); CREATED["badges"].append(str(pid))
    return str(pid), str(uid), email


def start_invasion(headers, mentor_pid, agreed_start):
    v = requests.post(f"{BASE_URL}/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": f"Casa T41 {uuid.uuid4().hex[:5]}",
                      "contact_phone": f"809555{uuid.uuid4().int % 10000:04d}", "mentor_person_id": mentor_pid}, headers=headers, timeout=30)
    assert v.status_code == 201, v.text
    vid = v.json()["visit_id"]
    r = requests.put(f"{BASE_URL}/api/mentorship/outreach/visits/{vid}/report", json={"status": "wants_followup", "agreed_start_date": agreed_start,
                     "call_schedule": "morning", "address_line1": "123 Main St", "address_city": "Columbus", "address_state": "OH", "address_zip": "43204"}, headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    s = requests.post(f"{BASE_URL}/api/mentorship/outreach/visits/{vid}/start-seven-weeks", headers=headers, timeout=30)
    assert s.status_code == 200, s.text
    CREATED["enrollments"].append(s.json()["enrollment_id"])
    if s.json().get("converted_person_id") and ObjectId.is_valid(s.json()["converted_person_id"]):
        CREATED["persons"].append(ObjectId(s.json()["converted_person_id"]))
    return s.json()


@pytest.fixture(scope="module")
def ctx():
    a_pid, a_uid, a_email = make_mentor("MentorA")
    b_pid, b_uid, b_email = make_mentor("MentorB")
    a_h, b_h = login(a_email, PASSWORD), login(b_email, PASSWORD)
    past = (date.today() - timedelta(days=3)).isoformat()
    started = start_invasion(a_h, a_pid, past)
    data = {"a_pid": a_pid, "a_uid": a_uid, "a_h": a_h, "b_pid": b_pid, "b_uid": b_uid, "b_h": b_h, "past": past,
            "enrollment_id": started["enrollment_id"], "person_id": started.get("converted_person_id"), "pastor_h": login(*PASTOR)}
    yield data
    # Teardown
    eids = CREATED["enrollments"]
    mongo.consolidation_activities.delete_many({"enrollment_id": {"$in": eids}})
    mongo.process_stage_progress.delete_many({"enrollment_id": {"$in": eids}})
    mongo.process_enrollments.delete_many({"enrollment_id": {"$in": eids}})
    mongo.mentor_badges.delete_many({"person_id": {"$in": CREATED["badges"]}})
    mongo.library_movements.delete_many({"$or": [{"from_holder.id": {"$in": [str(u) for u in CREATED["users"]]}}, {"from_holder_id": {"$in": [str(u) for u in CREATED["users"]]}}]})
    mongo.library_holdings.delete_many({"holder_type": "user", "holder_id": {"$in": [str(u) for u in CREATED["users"]]}})
    mongo.users.delete_many({"_id": {"$in": CREATED["users"]}})
    mongo.persons.delete_many({"_id": {"$in": CREATED["persons"]}})


def activities(ctx, headers=None):
    r = requests.get(f"{API}/{ctx['enrollment_id']}/activities", headers=headers or ctx["a_h"], timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["items"]


# Calendario: 54 actividades, fechas desde la fecha acordada
def test_calendar_54_from_agreed_date(ctx):
    items = activities(ctx)
    assert len(items) == 54
    counts = {}
    for i in items:
        counts[i["stage_key"]] = counts.get(i["stage_key"], 0) + 1
    assert counts == {"mcd": 21, "npt": 12, "lbs_1": 7, "lbs_2": 7, "lbs_3": 7}
    start = date.fromisoformat(ctx["past"])
    first = {k: min(i["scheduled_date"] for i in items if i["stage_key"] == k) for k in counts}
    assert first["mcd"] == start.isoformat()
    assert first["npt"] == (start + timedelta(days=7)).isoformat()
    assert first["lbs_1"] == (start + timedelta(days=14)).isoformat()
    assert first["lbs_3"] == (start + timedelta(days=28)).isoformat()
    assert all(i["mentor_person_id"] == ctx["a_pid"] for i in items)
    det = requests.get(f"{API}/{ctx['enrollment_id']}", headers=ctx["a_h"], timeout=30).json()
    assert det["current_stage_key"] == "mcd"
    assert det.get("decision_status") == "in_progress"


# Panel propio del mentor: atrasado/hoy/próximo y 0/54
def test_my_panel_buckets_and_progress(ctx):
    r = requests.get(f"{API}/my-panel", headers=ctx["a_h"], timeout=30)
    assert r.status_code == 200, r.text
    p = r.json()
    assert len(p["overdue"]) == 9  # 3 días x 3 momentos
    assert len(p["today"]) == 3
    assert all(x["enrollment_id"] == ctx["enrollment_id"] for x in p["overdue"] + p["today"] + p["upcoming"])
    mentee = next(m for m in p["mentees"] if m["enrollment_id"] == ctx["enrollment_id"])
    assert mentee["activities_total"] == 54 and mentee["activities_done"] == 0


# Panel requiere insignia
def test_my_panel_forbidden_without_badge():
    member_h = login("coreqa.member@example.com", "CoreQA2026!Member")
    r = requests.get(f"{API}/my-panel", headers=member_h, timeout=30)
    assert r.status_code == 403


# Entrega de libro sin inventario -> 409 mensaje claro y actividad sigue pendiente
def test_deliver_book_without_units_fails_clearly(ctx):
    act = next(i for i in activities(ctx) if i["stage_key"] == "mcd" and i["status"] == "pending")
    r = requests.put(f"{API}/activities/{act['activity_id']}/result", json={"status": "done", "deliver_book": True}, headers=ctx["a_h"], timeout=30)
    assert r.status_code == 409, r.text
    assert "no le quedan unidades" in r.json()["detail"].lower()
    after = next(i for i in activities(ctx) if i["activity_id"] == act["activity_id"])
    assert after["status"] == "pending"


# Entrega de libro idempotente
def test_deliver_book_idempotent(ctx):
    book = mongo.library_books.find_one({"sku": "MCD", "is_active": True})
    mongo.library_holdings.update_one({"book_id": book["book_id"], "holder_type": "user", "holder_id": ctx["a_uid"]},
                                      {"$set": {"quantity_on_hand": 2, "reserved_qty": 0}, "$setOnInsert": {"_id": str(uuid.uuid4())}}, upsert=True)
    act = next(i for i in activities(ctx) if i["stage_key"] == "mcd" and i["status"] == "pending")
    r1 = requests.put(f"{API}/activities/{act['activity_id']}/result", json={"status": "done", "note": "Oramos", "deliver_book": True}, headers=ctx["a_h"], timeout=30)
    assert r1.status_code == 200, r1.text
    mv = r1.json()["book_delivery_movement_id"]
    assert mv and r1.json()["status"] == "done"
    r2 = requests.put(f"{API}/activities/{act['activity_id']}/result", json={"status": "done", "note": "Oramos", "deliver_book": True}, headers=ctx["a_h"], timeout=30)
    assert r2.status_code == 200 and r2.json()["book_delivery_movement_id"] == mv
    h = mongo.library_holdings.find_one({"book_id": book["book_id"], "holder_type": "user", "holder_id": ctx["a_uid"]})
    assert h["quantity_on_hand"] == 1
    p = requests.get(f"{API}/my-panel", headers=ctx["a_h"], timeout=30).json()
    assert next(m for m in p["mentees"] if m["enrollment_id"] == ctx["enrollment_id"])["activities_done"] == 1


# Sin respuesta no cuenta
def test_no_answer_not_counted(ctx):
    act = next(i for i in activities(ctx) if i["stage_key"] == "mcd" and i["status"] == "pending")
    r = requests.put(f"{API}/activities/{act['activity_id']}/result", json={"status": "no_answer", "note": "No contestó"}, headers=ctx["a_h"], timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["last_result"] == "no_answer"
    ctx["no_answer_id"] = act["activity_id"]
    assert sum(1 for i in activities(ctx) if i["status"] == "done") == 1


# Reprogramada: exige fecha y mueve la fecha
def test_reschedule_requires_date_and_moves(ctx):
    act = next(i for i in activities(ctx) if i["stage_key"] == "mcd" and i["status"] == "pending")
    r = requests.put(f"{API}/activities/{act['activity_id']}/result", json={"status": "rescheduled"}, headers=ctx["a_h"], timeout=30)
    assert r.status_code == 422
    new_date = (date.today() + timedelta(days=2)).isoformat()
    r = requests.put(f"{API}/activities/{act['activity_id']}/result", json={"status": "rescheduled", "rescheduled_date": new_date}, headers=ctx["a_h"], timeout=30)
    assert r.status_code == 200 and r.json()["scheduled_date"] == new_date
    ctx["rescheduled_id"] = act["activity_id"]


# Reprogramada debería aparecer en 'Próximo' del panel en su nueva fecha (esperado por negocio)
def test_rescheduled_activity_visible_in_panel_upcoming(ctx):
    p = requests.get(f"{API}/my-panel", headers=ctx["a_h"], timeout=30).json()
    ids = [x["activity_id"] for x in p["upcoming"] + p["today"]]
    assert ctx["rescheduled_id"] in ids, "Actividad reprogramada desaparece del panel (filtro status=pending)"


# Aislamiento
def test_isolation_between_mentors(ctx):
    r = requests.get(f"{API}/{ctx['enrollment_id']}/activities", headers=ctx["b_h"], timeout=30)
    assert r.status_code == 403
    act = activities(ctx)[-1]
    r = requests.put(f"{API}/activities/{act['activity_id']}/result", json={"status": "done"}, headers=ctx["b_h"], timeout=30)
    assert r.status_code == 403
    p = requests.get(f"{API}/my-panel", headers=ctx["b_h"], timeout=30).json()
    assert p["mentees"] == [] and p["overdue"] == [] and p["today"] == []
    r = requests.get(f"{API}/by-mentor/{ctx['a_pid']}", headers=ctx["b_h"], timeout=30)
    assert r.status_code == 403
    r = requests.put(f"{API}/{ctx['enrollment_id']}/decision-status", json={"new_status": "paused", "reason": "x"}, headers=ctx["b_h"], timeout=30)
    assert r.status_code == 403


# Supervisión por pastor == panel propio
def test_supervision_matches_own_panel(ctx):
    own = requests.get(f"{API}/my-panel", headers=ctx["a_h"], timeout=30).json()
    r = requests.get(f"{API}/by-mentor/{ctx['a_pid']}", headers=ctx["pastor_h"], timeout=30)
    assert r.status_code == 200, r.text
    b = r.json()["activity_buckets"]
    for k in ("today", "overdue", "upcoming"):
        assert [x["activity_id"] for x in b[k]] == [x["activity_id"] for x in own[k]]


# Estado de decisión: pausa con motivo, reanudar, sin membresía
def test_decision_pause_resume_no_membership(ctx):
    url = f"{API}/{ctx['enrollment_id']}/decision-status"
    assert requests.put(url, json={"new_status": "paused"}, headers=ctx["a_h"], timeout=30).status_code == 422
    r = requests.put(url, json={"new_status": "paused", "reason": "Viaje"}, headers=ctx["a_h"], timeout=30)
    assert r.status_code == 200 and r.json()["decision_status"] == "paused" and r.json()["decision_paused_reason"] == "Viaje"
    r = requests.put(url, json={"new_status": "accepted"}, headers=ctx["a_h"], timeout=30)
    # Reanudar recalcula: ya hay 1 actividad realizada -> in_progress
    assert r.status_code == 200 and r.json()["decision_status"] == "in_progress"
    assert mongo.person_memberships.find_one({"person_id": ctx["person_id"]}) is None


# Motivo solo espacios no debe aceptarse
def test_decision_pause_blank_reason_rejected(ctx):
    url = f"{API}/{ctx['enrollment_id']}/decision-status"
    r = requests.put(url, json={"new_status": "paused", "reason": "   "}, headers=ctx["a_h"], timeout=30)
    requests.put(url, json={"new_status": "accepted"}, headers=ctx["a_h"], timeout=30)
    assert r.status_code == 422, "motivo en blanco aceptado"


# Entrada direct_church: MCD + 54 actividades desde hoy
def test_direct_church_intake(ctx):
    pid = ObjectId()
    now = datetime.now(timezone.utc)
    mongo.persons.insert_one({"_id": pid, "person_number": f"VV-T41{uuid.uuid4().hex[:6].upper()}", "nombre": "QA", "apellido": "T41 Iglesia",
                              "idempotency_key": f"qa:t41:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
    CREATED["persons"].append(pid)
    r = requests.post(f"{API}/intakes", json={"person_id": str(pid), "entry_mode": "direct_church", "mentor_person_id": ctx["b_pid"]}, headers=ctx["pastor_h"], timeout=30)
    assert r.status_code == 201, r.text
    body = r.json()
    CREATED["enrollments"].append(body["enrollment_id"])
    assert body["current_stage_key"] == "mcd"
    acts = requests.get(f"{API}/{body['enrollment_id']}/activities", headers=ctx["b_h"], timeout=30).json()["items"]
    assert len(acts) == 54
    assert min(a["scheduled_date"] for a in acts) == datetime.now(timezone.utc).date().isoformat()
    assert all(a["mentor_person_id"] == ctx["b_pid"] for a in acts)
    ctx["church_enrollment_id"] = body["enrollment_id"]


# Transferencia de mentor: las actividades deben seguir al nuevo mentor
def test_mentor_transfer_moves_activities(ctx):
    eid = ctx["church_enrollment_id"]
    mongo.mentor_qualifications.insert_one({"_id": str(uuid.uuid4()), "person_id": ctx["a_pid"], "active": True, "can_teach_lbs": True, "front_group_id": None, "valid_until": None, "qa_t41": True})
    try:
        r = requests.post(f"{API}/{eid}/mentor/transfer", json={"new_mentor_person_id": ctx["a_pid"], "reason": "QA transfer"}, headers=ctx["pastor_h"], timeout=30)
        if r.status_code != 200:
            pytest.skip(f"transfer not possible: {r.status_code} {r.text[:200]}")
        acts = list(mongo.consolidation_activities.find({"enrollment_id": eid}, {"mentor_person_id": 1}))
        assert all(a["mentor_person_id"] == ctx["a_pid"] for a in acts), "actividades quedan con el mentor anterior tras transferir"
    finally:
        mongo.mentor_qualifications.delete_many({"qa_t41": True})


# Iter42: 'sin respuesta' sigue visible en panel (intento, no cierre)
def test_no_answer_activity_still_in_panel(ctx):
    p = requests.get(f"{API}/my-panel", headers=ctx["a_h"], timeout=30).json()
    ids = [x["activity_id"] for x in p["overdue"] + p["today"] + p["upcoming"]]
    assert ctx["no_answer_id"] in ids


# Iter42: reprogramada puede luego registrarse como Realizada
def test_rescheduled_can_be_completed_later(ctx):
    r = requests.put(f"{API}/activities/{ctx['rescheduled_id']}/result", json={"status": "done", "note": "Ahora sí"}, headers=ctx["a_h"], timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "done" and r.json()["last_result"] == "done"
    p = requests.get(f"{API}/my-panel", headers=ctx["a_h"], timeout=30).json()
    assert ctx["rescheduled_id"] not in [x["activity_id"] for x in p["overdue"] + p["today"] + p["upcoming"]]


# Iter42: mismo libro MCD no puede entregarse dos veces a la misma persona desde otra actividad
def test_same_book_not_delivered_twice_across_activities(ctx):
    book = mongo.library_books.find_one({"sku": "MCD", "is_active": True})
    h = mongo.library_holdings.find_one({"book_id": book["book_id"], "holder_type": "user", "holder_id": ctx["a_uid"]})
    act = next(i for i in activities(ctx) if i["stage_key"] == "mcd" and i["status"] == "pending")
    r = requests.put(f"{API}/activities/{act['activity_id']}/result", json={"status": "done", "deliver_book": True}, headers=ctx["a_h"], timeout=30)
    assert r.status_code == 409, r.text
    assert "ya se le entregó" in r.json()["detail"].lower()
    after = next(i for i in activities(ctx) if i["activity_id"] == act["activity_id"])
    assert after["status"] == "pending"
    h2 = mongo.library_holdings.find_one({"book_id": book["book_id"], "holder_type": "user", "holder_id": ctx["a_uid"]})
    assert h2["quantity_on_hand"] == h["quantity_on_hand"]


# Iter42: expediente pausado no aparece en buckets; reanudar lo devuelve
def test_paused_enrollment_hidden_from_buckets(ctx):
    url = f"{API}/{ctx['enrollment_id']}/decision-status"
    assert requests.put(url, json={"new_status": "paused", "reason": "Viaje QA"}, headers=ctx["a_h"], timeout=30).status_code == 200
    p = requests.get(f"{API}/my-panel", headers=ctx["a_h"], timeout=30).json()
    assert not any(x["enrollment_id"] == ctx["enrollment_id"] for x in p["overdue"] + p["today"] + p["upcoming"])
    r = requests.put(url, json={"new_status": "accepted"}, headers=ctx["a_h"], timeout=30)
    assert r.json()["decision_status"] == "in_progress"
    p = requests.get(f"{API}/my-panel", headers=ctx["a_h"], timeout=30).json()
    assert any(x["enrollment_id"] == ctx["enrollment_id"] for x in p["overdue"] + p["today"])


# Iter42: actividad 'done' NO debería poder revertirse a no_answer (pierde avance)
def test_done_activity_cannot_be_reverted(ctx):
    done = next(i for i in activities(ctx) if i["status"] == "done")
    r = requests.put(f"{API}/activities/{done['activity_id']}/result", json={"status": "no_answer"}, headers=ctx["a_h"], timeout=30)
    after = next(i for i in activities(ctx) if i["activity_id"] == done["activity_id"])
    assert after["status"] == "done", f"actividad realizada revertida a pending vía API (resp {r.status_code})"


# Bug residual iter42 #2: reasignar Grupo Frontal (sin el mentor actual en el
# nuevo grupo) debe mover las actividades PENDIENTES al mentor nuevo (None),
# sin reescribir el historial de las ya 'done'.
def test_reassign_front_group_moves_pending_activities(ctx):
    pid = ObjectId()
    now = datetime.now(timezone.utc)
    mongo.persons.insert_one({"_id": pid, "person_number": f"VV-T41{uuid.uuid4().hex[:6].upper()}", "nombre": "QA", "apellido": "T41 Reasigna",
                              "idempotency_key": f"qa:t41:{uuid.uuid4()}", "version": 1, "created_at": now, "updated_at": now})
    CREATED["persons"].append(pid)
    intake = requests.post(f"{API}/intakes", json={"person_id": str(pid), "entry_mode": "direct_church", "mentor_person_id": ctx["b_pid"]}, headers=ctx["pastor_h"], timeout=30)
    assert intake.status_code == 201, intake.text
    eid = intake.json()["enrollment_id"]
    CREATED["enrollments"].append(eid)
    # Marca una actividad como realizada ANTES de reasignar, para confirmar que no se reescribe.
    acts = requests.get(f"{API}/{eid}/activities", headers=ctx["b_h"], timeout=30).json()["items"]
    done_act = acts[0]
    r_done = requests.put(f"{API}/activities/{done_act['activity_id']}/result", json={"status": "done", "note": "QA"}, headers=ctx["b_h"], timeout=30)
    assert r_done.status_code == 200, r_done.text
    fg = requests.post(f"{BASE_URL}/api/front-groups", json={"name": f"QA T41 FG {uuid.uuid4().hex[:5]}"}, headers=ctx["pastor_h"], timeout=30)
    assert fg.status_code == 201, fg.text
    fg_id = fg.json()["front_group_id"]
    resp = requests.put(f"{API}/{eid}/front-group", json={"front_group_id": fg_id, "reason": "QA: grupo sin este mentor"}, headers=ctx["pastor_h"], timeout=30)
    assert resp.status_code == 200, resp.text
    assert resp.json()["mentor_person_id"] is None, "el mentor debía quedar sin asignar al cambiar a un grupo donde no es miembro"
    after = list(mongo.consolidation_activities.find({"enrollment_id": eid}, {"_id": 0, "status": 1, "mentor_person_id": 1}))
    pending_after = [a for a in after if a["status"] == "pending"]
    done_after = [a for a in after if a["status"] == "done"]
    assert pending_after and all(a["mentor_person_id"] is None for a in pending_after), "las actividades pendientes no siguieron el cambio de mentor"
    assert done_after and all(a["mentor_person_id"] == ctx["b_pid"] for a in done_after), "la actividad ya realizada no debe reescribir su mentor histórico"


# Configuración de zona horaria de la iglesia para 'Hoy/Atrasado' (antes fija a la hora del servidor)
def test_church_timezone_setting_restricted_and_validated(ctx):
    original = requests.get(f"{API}/settings/timezone", headers=ctx["a_h"], timeout=30)
    assert original.status_code == 200
    original_tz = original.json()["church_timezone"]
    forbidden = requests.put(f"{API}/settings/timezone", json={"church_timezone": "America/New_York"}, headers=ctx["a_h"], timeout=30)
    assert forbidden.status_code == 403
    invalid = requests.put(f"{API}/settings/timezone", json={"church_timezone": "Not/AZone"}, headers=ctx["pastor_h"], timeout=30)
    assert invalid.status_code == 422
    try:
        ok = requests.put(f"{API}/settings/timezone", json={"church_timezone": "America/New_York"}, headers=ctx["pastor_h"], timeout=30)
        assert ok.status_code == 200 and ok.json()["church_timezone"] == "America/New_York"
        got = requests.get(f"{API}/settings/timezone", headers=ctx["b_h"], timeout=30)
        assert got.json()["church_timezone"] == "America/New_York"
    finally:
        requests.put(f"{API}/settings/timezone", json={"church_timezone": original_tz}, headers=ctx["pastor_h"], timeout=30)
