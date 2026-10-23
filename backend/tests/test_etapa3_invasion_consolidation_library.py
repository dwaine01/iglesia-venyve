"""Etapa 3 — Invasión -> Consolidación (mismo expediente vía person_matching),
C7 (attempts/completed_at/registered_by/reschedule_history), C8 Librería
(reconocimiento de entrega en primer contacto, devolución/ajuste con motivo,
my-branch-library) y procedencia de Invasión en el expediente.

Corre in-process (ASGI) como test_mentorship_outreach_etapa2.py; crea y limpia
sus propias cuentas QA (qa.outreach.etapa3.*) y restaura existencias de Central.
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
from access_control import access_defaults_for_role
from person_matching import normalize_text, normalize_phone
from qa_demo_cleanup import delete_qa_artifacts, qa_preview

PASSWORD = "OutreachEtapa3Pass123!"
MENTOR_CAPS = ["mentorship.outreach.report", "library.deliver"]


def tag() -> str:
    return uuid.uuid4().hex[:6]


def uniq_phone() -> str:
    return f"305{uuid.uuid4().int % 10**7:07d}"


async def create_person(label: str, nombre: str = "QA", fecha=None, phone=None) -> str:
    pid = ObjectId()
    await server.db.persons.insert_one({
        "_id": pid, "person_number": f"VV-QE3{uuid.uuid4().hex[:6].upper()}",
        "nombre": nombre, "apellido": label, "search_key": normalize_text(f"{nombre} {label}"),
        "fecha_nacimiento": fecha, "idempotency_key": f"qa:outreach:etapa3:{uuid.uuid4()}",
        "version": 1, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    if phone:
        await server.db.person_contacts.insert_one({
            "person_id": str(pid), "tipo": "telefono", "valor": phone, "valor_normalizado": normalize_phone(phone),
            "es_principal": True, "created_at": datetime.now(timezone.utc),
        })
    return str(pid)


async def create_user(label: str, role: str, person_id=None, capabilities=None):
    user_id = ObjectId()
    email = f"qa.outreach.etapa3.{label.lower().replace(' ', '.')}.{tag()}@example.com"
    defaults = access_defaults_for_role(role)
    defaults["capabilities"] = sorted(set(defaults.get("capabilities", []) + (capabilities or [])))
    doc = {"_id": user_id, "nombre": f"QA {label}", "email": email,
           "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
           "rol": role, "is_active": True, "token_version": 1, "created_at": datetime.now(timezone.utc), **defaults}
    if person_id:
        doc["person_id"] = person_id
    await server.db.users.insert_one(doc)
    return str(user_id), email


async def auth_client(email: str):
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return client, {"Authorization": f"Bearer {login.json()['token']}"}


async def activate_badge(pid: str):
    await server.db.mentor_badges.update_one({"person_id": pid}, {"$set": {"person_id": pid, "active": True, "since": "2026-01-01"}}, upsert=True)


async def make_front_group(name, leader_pid, leader_uid):
    gid = str(uuid.uuid4())
    await server.db.front_groups.insert_one({
        "_id": gid, "front_group_id": gid, "name": name, "parent_group_id": None, "ancestor_group_ids": [], "depth": 0,
        "status": "active", "primary_leader_person_id": leader_pid, "created_by_user_id": leader_uid,
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    await add_member(gid, leader_pid, "leader")
    return gid


async def add_member(gid, pid, role="mentor"):
    aid = str(uuid.uuid4())
    await server.db.front_group_assignments.insert_one({"_id": aid, "assignment_id": aid, "front_group_id": gid, "person_id": pid, "role": role, "active": True, "created_at": datetime.now(timezone.utc)})


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


async def book_id_for(sku):
    return (await server.db.library_books.find_one({"sku": sku, "is_active": True}, {"_id": 0, "book_id": 1}))["book_id"]


async def central_qty(book_id):
    h = await server.db.library_holdings.find_one({"book_id": book_id, "holder_type": "warehouse", "holder_id": "central"}, {"_id": 0})
    return (h or {}).get("quantity_on_hand", 0)


async def set_central(book_id, qty):
    await server.db.library_holdings.update_one(
        {"book_id": book_id, "holder_type": "warehouse", "holder_id": "central"},
        {"$set": {"quantity_on_hand": qty, "reserved_qty": 0}, "$setOnInsert": {"_id": str(uuid.uuid4())}}, upsert=True)


async def assign_to_mentor(book_id, mentor_pid, qty):
    from library_module import HolderInput, MovementInput, apply_movement, CENTRAL_HOLDER
    user = await server.db.users.find_one({"person_id": mentor_pid}, {"_id": 1})
    await apply_movement(MovementInput(book_id=book_id, movement_type="ASSIGNMENT", quantity=qty, from_holder=HolderInput(**CENTRAL_HOLDER),
                                       to_holder=HolderInput(type="user", id=str(user["_id"]))), "system:test")
    return str(user["_id"])


@pytest_asyncio.fixture
async def env():
    """Pastor + líder de grupo frontal + mentor (miembro del grupo) + mentor fuera de rama."""
    await cleanup()
    mcd, npt = await book_id_for("MCD"), await book_id_for("NPT")
    saved = {mcd: await central_qty(mcd), npt: await central_qty(npt)}
    await set_central(mcd, 50); await set_central(npt, 50)
    t = tag()
    pastor_pid = await create_person(f"Pastor E3 {t}")
    leader_pid = await create_person(f"Lider E3 {t}")
    mentor_pid = await create_person(f"Mentor E3 {t}")
    outsider_pid = await create_person(f"Fuera E3 {t}")
    for p in (mentor_pid, outsider_pid, leader_pid):
        await activate_badge(p)
    _, pastor_email = await create_user("Pastor", "pastor", pastor_pid)
    leader_uid, leader_email = await create_user("Lider", "persona", leader_pid, MENTOR_CAPS)
    _, mentor_email = await create_user("Mentor", "persona", mentor_pid, MENTOR_CAPS)
    _, outsider_email = await create_user("Fuera", "persona", outsider_pid, MENTOR_CAPS)
    gid = await make_front_group(f"QA Grupo E3 {t}", leader_pid, leader_uid)
    await add_member(gid, mentor_pid)
    clients = {}
    for k, e in (("pastor", pastor_email), ("leader", leader_email), ("mentor", mentor_email), ("outsider", outsider_email)):
        clients[k] = await auth_client(e)
    data = {"clients": clients, "mentor_pid": mentor_pid, "leader_pid": leader_pid, "outsider_pid": outsider_pid, "gid": gid, "mcd": mcd, "npt": npt}
    try:
        yield data
    finally:
        for c, _ in clients.values():
            await c.aclose()
        await server.db.front_groups.delete_one({"front_group_id": gid})
        await server.db.front_group_assignments.delete_many({"front_group_id": gid})
        await cleanup()
        for b, q in saved.items():
            await set_central(b, q)


async def new_visit(env, name, phone, campaign_id=None):
    c, h = env["clients"]["mentor"]
    r = await c.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": name, "contact_phone": phone, "campaign_id": campaign_id}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["visit_id"]


async def followup(env, visit_id, extra=None):
    c, h = env["clients"]["mentor"]
    today = datetime.now(timezone.utc).date().isoformat()
    r = await c.put(f"/api/mentorship/outreach/visits/{visit_id}/report", json={"status": "wants_followup", "agreed_start_date": today, "call_schedule": "morning", **(extra or {})}, headers=h)
    return r


# --- Invasión -> Consolidación: caso feliz + front_group heredado ---
@pytest.mark.asyncio
async def test_happy_path_start_creates_person_and_enrollment_with_front_group(env):
    c, h = env["clients"]["mentor"]
    vid = await new_visit(env, f"Zorbax Unico{tag()}", uniq_phone())
    assert (await followup(env, vid)).status_code == 200
    r = await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["person_created"] is True and body["enrollment_created"] is True
    enr = await server.db.process_enrollments.find_one({"enrollment_id": body["enrollment_id"]}, {"_id": 0})
    assert enr["front_group_id"] == env["gid"]
    assert enr["person_id"] == body["converted_person_id"]
    detail = await c.get(f"/api/processes/consolidation/{body['enrollment_id']}", headers=h)
    assert detail.status_code == 200, detail.text
    assert detail.json()["outreach_origin"]["visit_id"] == vid


# --- C8: received_mcd en visita nueva crea Persona + DELIVERY ---
@pytest.mark.asyncio
async def test_received_mcd_on_new_visit_creates_person_and_delivery(env):
    c, h = env["clients"]["mentor"]
    await assign_to_mentor(env["mcd"], env["mentor_pid"], 2)
    vid = await new_visit(env, f"Quetzal Nuevo{tag()}", uniq_phone())
    r = await c.put(f"/api/mentorship/outreach/visits/{vid}/report", json={"status": "visited", "received_mcd": True}, headers=h)
    assert r.status_code == 200, r.text
    visit = await server.db.outreach_visits.find_one({"visit_id": vid}, {"_id": 0})
    assert visit["converted_person_id"] and visit["mcd_delivery_movement_id"]
    n = await server.db.library_movements.count_documents({"movement_type": "DELIVERY", "book_id": env["mcd"], "person_id": visit["converted_person_id"], "process_key": "outreach_invasion"})
    assert n == 1


# --- Coincidencia FUERTE (nombre+teléfono+fecha) en start y en MCD ---
@pytest.mark.asyncio
async def test_strong_match_blocks_and_use_existing_person(env):
    c, h = env["clients"]["mentor"]
    t, phone = tag(), uniq_phone()
    existing = await create_person(f"Fuerte{t}", nombre="Kalimba", fecha="1990-05-05", phone=phone)
    vid = await new_visit(env, f"Kalimba Fuerte{t}", phone)
    assert (await followup(env, vid, {"contact_birth_date": "1990-05-05"})).status_code == 200
    r = await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", headers=h)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert any(cand["person_id"] == existing for cand in detail["candidates"])
    assert not detail.get("requires_confirmation")
    # MCD también bloquea
    await assign_to_mentor(env["mcd"], env["mentor_pid"], 1)
    r_mcd = await c.put(f"/api/mentorship/outreach/visits/{vid}/report", json={"status": "wants_followup", "received_mcd": True}, headers=h)
    assert r_mcd.status_code == 409
    # Confirm distinct NO debe saltarse una coincidencia fuerte
    r_force = await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", json={"confirm_distinct_person": True, "distinct_reason": "otra"}, headers=h)
    assert r_force.status_code == 409
    ok = await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", json={"person_id": existing}, headers=h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["converted_person_id"] == existing and ok.json()["person_created"] is False
    assert await server.db.persons.count_documents({"search_key": normalize_text(f"Kalimba Fuerte{t}")}) == 1


# --- Coincidencia POSIBLE (solo nombre) exige motivo ---
@pytest.mark.asyncio
async def test_possible_match_requires_reason_and_creates_distinct_person(env):
    c, h = env["clients"]["mentor"]
    t = tag()
    existing = await create_person(f"Posible{t}", nombre="Wombat")
    vid = await new_visit(env, f"Wombat Posible{t}", uniq_phone())
    assert (await followup(env, vid)).status_code == 200
    r = await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["requires_confirmation"] is True
    no_reason = await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", json={"confirm_distinct_person": True, "distinct_reason": "  "}, headers=h)
    assert no_reason.status_code == 409
    ok = await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", json={"confirm_distinct_person": True, "distinct_reason": "Otra persona, distinto hogar"}, headers=h)
    assert ok.status_code == 200, ok.text
    new_pid = ok.json()["converted_person_id"]
    assert new_pid != existing and ok.json()["person_created"] is True
    doc = await server.db.persons.find_one({"_id": ObjectId(new_pid)})
    assert doc["distinct_person_confirmed"]["reason"] == "Otra persona, distinto hogar"


# --- Procedencia hogar/invasión + intentos + reconocimiento entrega MCD ---
@pytest.mark.asyncio
async def test_origin_attempts_and_book_acknowledgement_no_duplicate(env):
    pc, ph = env["clients"]["pastor"]
    c, h = env["clients"]["mentor"]
    camp = await pc.post("/api/mentorship/outreach/campaigns", json={"name": f"QA Inv E3 {tag()}", "location": "Sector E3", "start_date": "2026-01-01", "end_date": "2026-01-02", "assigned_mentors": [{"person_id": env["mentor_pid"]}]}, headers=ph)
    assert camp.status_code == 201, camp.text
    cid = camp.json()["campaign_id"]
    hh = await c.post("/api/mentorship/outreach/households", json={"campaign_id": cid, "address_line1": "Calle QA 123", "sector": "Sector E3"}, headers=h)
    assert hh.status_code == 201, hh.text
    hid = hh.json()["household_id"]
    assert (await c.post(f"/api/mentorship/outreach/households/{hid}/events", json={"result": "no_answer"}, headers=h)).status_code == 201
    ev = await c.post(f"/api/mentorship/outreach/households/{hid}/events", json={"result": "contacted", "persons": [{"contact_type": "new", "contact_name": f"Origen Hogar{tag()}", "contact_phone": uniq_phone()}]}, headers=h)
    assert ev.status_code == 201, ev.text
    vid = ev.json()["visits"][0]["visit_id"]
    await assign_to_mentor(env["mcd"], env["mentor_pid"], 2)
    assert (await followup(env, vid, {"received_mcd": True})).status_code == 200
    st = await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", headers=h)
    assert st.status_code == 200, st.text
    eid, person_id = st.json()["enrollment_id"], st.json()["converted_person_id"]
    det = (await c.get(f"/api/processes/consolidation/{eid}", headers=h)).json()
    origin = det["outreach_origin"]
    assert origin["campaign_id"] == cid and origin["household_id"] == hid
    assert origin["materials_delivered"]["mcd"] is True and origin["materials_delivered"]["npt"] is False
    assert len(origin["attempts"]) == 2 and "Calle QA 123" in origin["household_address"]
    assert det.get("campaign_id") == cid
    acts = (await c.get(f"/api/processes/consolidation/{eid}/activities", headers=h)).json()["items"]
    mcd_acts = sorted([a for a in acts if a["stage_key"] == "mcd"], key=lambda a: (a["day_number"], a.get("moment_key") or ""))
    done = await c.put(f"/api/processes/consolidation/activities/{mcd_acts[0]['activity_id']}/result", json={"status": "done", "deliver_book": True}, headers=h)
    assert done.status_code == 200, done.text
    assert done.json()["book_delivery_acknowledged"] is True
    assert await server.db.library_movements.count_documents({"movement_type": "DELIVERY", "book_id": env["mcd"], "person_id": person_id}) == 1


# --- Regresión: dos actividades de Consolidación, mismo libro -> 409 ---
@pytest.mark.asyncio
async def test_second_consolidation_delivery_still_409(env):
    c, h = env["clients"]["mentor"]
    await assign_to_mentor(env["mcd"], env["mentor_pid"], 2)
    vid = await new_visit(env, f"Dos Entregas{tag()}", uniq_phone())
    assert (await followup(env, vid)).status_code == 200
    st = (await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", headers=h)).json()
    acts = (await c.get(f"/api/processes/consolidation/{st['enrollment_id']}/activities", headers=h)).json()["items"]
    mcd_acts = sorted([a for a in acts if a["stage_key"] == "mcd"], key=lambda a: (a["day_number"], a.get("moment_key") or ""))
    first = await c.put(f"/api/processes/consolidation/activities/{mcd_acts[0]['activity_id']}/result", json={"status": "done", "deliver_book": True}, headers=h)
    assert first.status_code == 200 and not first.json().get("book_delivery_acknowledged")
    second = await c.put(f"/api/processes/consolidation/activities/{mcd_acts[1]['activity_id']}/result", json={"status": "done", "deliver_book": True}, headers=h)
    assert second.status_code == 409


# --- C7: attempts[], completed_at, registered_by_user_id, reschedule_history ---
@pytest.mark.asyncio
async def test_c7_attempts_completed_at_and_reschedule_history(env):
    c, h = env["clients"]["mentor"]
    me = (await c.get("/api/auth/me", headers=h)).json()
    vid = await new_visit(env, f"Intentos Ce{tag()}", uniq_phone())
    assert (await followup(env, vid)).status_code == 200
    st = (await c.post(f"/api/mentorship/outreach/visits/{vid}/start-seven-weeks", headers=h)).json()
    acts = (await c.get(f"/api/processes/consolidation/{st['enrollment_id']}/activities", headers=h)).json()["items"]
    a1, a2 = acts[0]["activity_id"], acts[1]["activity_id"]
    for note in ("primer intento", "segundo intento"):
        r = await c.put(f"/api/processes/consolidation/activities/{a1}/result", json={"status": "no_answer", "note": note}, headers=h)
        assert r.status_code == 200, r.text
    assert [x["note"] for x in r.json()["attempts"]] == ["primer intento", "segundo intento"]
    done = await c.put(f"/api/processes/consolidation/activities/{a1}/result", json={"status": "done"}, headers=h)
    assert done.status_code == 200
    body = done.json()
    assert body["completed_at"] and body["registered_by_user_id"] == (me.get("user_id") or me.get("id") or me.get("user", {}).get("user_id"))
    assert len(body["attempts"]) == 2, "completar no debe borrar intentos"
    d1 = (datetime.now(timezone.utc).date() + timedelta(days=3)).isoformat()
    d2 = (datetime.now(timezone.utc).date() + timedelta(days=5)).isoformat()
    await c.put(f"/api/processes/consolidation/activities/{a2}/result", json={"status": "rescheduled", "rescheduled_date": d1}, headers=h)
    r2 = await c.put(f"/api/processes/consolidation/activities/{a2}/result", json={"status": "rescheduled", "rescheduled_date": d2}, headers=h)
    hist = r2.json()["reschedule_history"]
    assert len(hist) == 2 and hist[0]["to_date"] == d1 and hist[1]["from_date"] == d1 and hist[1]["to_date"] == d2


# --- C8: my-branch-library (mentor propio, líder de rama, fuera de rama) ---
@pytest.mark.asyncio
async def test_my_branch_library_visibility(env):
    await assign_to_mentor(env["npt"], env["mentor_pid"], 3)
    await assign_to_mentor(env["npt"], env["outsider_pid"], 1)
    for who, expect_mentor, expect_outsider in (("mentor", True, False), ("leader", True, False), ("outsider", False, True)):
        c, h = env["clients"][who]
        r = await c.get("/api/mentorship/outreach/my-branch-library", headers=h)
        assert r.status_code == 200, r.text
        mentors = {i["mentor_person_id"] for i in r.json()["items"]}
        assert (env["mentor_pid"] in mentors) is expect_mentor, f"{who}: {mentors}"
        assert (env["outsider_pid"] in mentors) is expect_outsider, f"{who}: {mentors}"
    c, h = env["clients"]["mentor"]
    item = next(i for i in (await c.get("/api/mentorship/outreach/my-branch-library", headers=h)).json()["items"] if i["book_id"] == env["npt"])
    assert item["assigned"] == 3 and item["in_custody"] == 3 and item["returned"] == 0


# --- C8: devolución con motivo obligatorio + my-holdings returned_quantity ---
@pytest.mark.asyncio
async def test_return_requires_reason_and_reflects_in_holdings(env):
    c, h = env["clients"]["mentor"]
    uid = await assign_to_mentor(env["npt"], env["mentor_pid"], 2)
    payload = {"book_id": env["npt"], "movement_type": "RETURN", "quantity": 1, "from_holder": {"type": "user", "id": uid}, "to_holder": {"type": "warehouse", "id": "central"}}
    assert (await c.post("/api/library/movements", json=payload, headers=h)).status_code == 422
    assert (await c.post("/api/library/movements", json={**payload, "notes": "   "}, headers=h)).status_code == 422
    ok = await c.post("/api/library/movements", json={**payload, "notes": "Sobró tras la invasión"}, headers=h)
    assert ok.status_code == 201, ok.text
    hold = await c.get("/api/library/my-holdings", headers=h)
    assert hold.status_code == 200, hold.text
    item = next(i for i in hold.json()["items"] if i["book"]["book_id"] == env["npt"])
    assert item["returned_quantity"] == 1 and item["on_hand"] == 1 and "deliveries" in item
    br = next(i for i in (await c.get("/api/mentorship/outreach/my-branch-library", headers=h)).json()["items"] if i["book_id"] == env["npt"])
    assert br["returned"] == 1 and br["in_custody"] == 1


# --- C8: ajustes de inventario (manager) ---
@pytest.mark.asyncio
async def test_adjustments_permissions_reason_and_never_negative(env):
    pc, ph = env["clients"]["pastor"]
    mc, mh = env["clients"]["mentor"]
    b = env["npt"]
    before = await central_qty(b)
    inc = await pc.post("/api/library/adjustments", json={"book_id": b, "direction": "increase", "quantity": 4, "reason": "Recuento físico"}, headers=ph)
    assert inc.status_code == 201, inc.text
    assert await central_qty(b) == before + 4
    mv = await server.db.library_movements.find_one({"movement_id": inc.json()["movement_id"]}, {"_id": 0})
    assert mv["movement_type"] == "ADJUSTMENT" and mv["notes"] == "Recuento físico"
    dec = await pc.post("/api/library/adjustments", json={"book_id": b, "direction": "decrease", "quantity": 2, "reason": "Dañados"}, headers=ph)
    assert dec.status_code == 201 and await central_qty(b) == before + 2
    assert (await pc.post("/api/library/adjustments", json={"book_id": b, "direction": "increase", "quantity": 1}, headers=ph)).status_code == 422
    assert (await pc.post("/api/library/adjustments", json={"book_id": b, "direction": "increase", "quantity": 1, "reason": ""}, headers=ph)).status_code == 422
    neg = await pc.post("/api/library/adjustments", json={"book_id": b, "direction": "decrease", "quantity": 99999, "reason": "Error"}, headers=ph)
    assert neg.status_code == 409, neg.text
    assert await central_qty(b) == before + 2
    assert (await mc.post("/api/library/adjustments", json={"book_id": b, "direction": "increase", "quantity": 1, "reason": "Intento"}, headers=mh)).status_code == 403
    # BUG conocido: motivo solo espacios -> 500 (ValidationError sin manejar en create_adjustment)
    ws = await pc.post("/api/library/adjustments", json={"book_id": b, "direction": "increase", "quantity": 1, "reason": "     "}, headers=ph)
    assert ws.status_code in (400, 422), f"motivo en blanco debe ser 4xx, fue {ws.status_code}"
