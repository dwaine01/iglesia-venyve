"""Seed QA para pruebas UI de Etapa 3. Usa helpers de test_etapa3_invasion_consolidation_library.
Crea líder de rama + mentor (con MCD/NPT asignados), campaña, hogar con intentos,
visitas en 'wants_followup' (única / coincidencia fuerte / posible) y una visita
con MCD entregado e iniciada (para probar 'Ya se había entregado').
Escribe /tmp/etapa3_seed.json. Limpieza: qa_demo_cleanup (prefijo qa.outreach.etapa3.*)."""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import server  # noqa: E402
from test_etapa3_invasion_consolidation_library import (  # noqa: E402
    PASSWORD, MENTOR_CAPS, activate_badge, add_member, assign_to_mentor, auth_client, book_id_for, create_person,
    create_user, make_front_group, tag, uniq_phone, central_qty, set_central,
)


async def main():
    t = tag()
    mcd, npt = await book_id_for("MCD"), await book_id_for("NPT")
    saved = {mcd: await central_qty(mcd), npt: await central_qty(npt)}
    await set_central(mcd, saved[mcd] + 10); await set_central(npt, saved[npt] + 10)
    leader_pid = await create_person(f"UILider{t}")
    mentor_pid = await create_person(f"UIMentor{t}")
    for p in (leader_pid, mentor_pid):
        await activate_badge(p)
    leader_uid, leader_email = await create_user("UILider", "persona", leader_pid, MENTOR_CAPS)
    _, mentor_email = await create_user("UIMentor", "persona", mentor_pid, MENTOR_CAPS)
    gid = await make_front_group(f"QA Rama E3 UI {t}", leader_pid, leader_uid)
    await add_member(gid, mentor_pid)
    await assign_to_mentor(mcd, mentor_pid, 4)
    await assign_to_mentor(npt, mentor_pid, 2)
    strong_phone = uniq_phone()
    strong_pid = await create_person(f"Fuerte{t}", nombre="Xilofon", fecha="1988-03-03", phone=strong_phone)
    possible_pid = await create_person(f"Posible{t}", nombre="Yerbal")
    c, h = await auth_client(mentor_email)
    # campaña creada vía un pastor QA temporal
    _, pastor_email = await create_user("UIPastor", "pastor", await create_person(f"UIPastor{t}"))
    pc, ph = await auth_client(pastor_email)
    camp = (await pc.post("/api/mentorship/outreach/campaigns", json={"name": f"QA Invasión E3 UI {t}", "location": "Sector UI", "start_date": "2026-01-01", "end_date": "2026-01-02", "assigned_mentors": [{"person_id": mentor_pid}]}, headers=ph)).json()
    cid = camp["campaign_id"]
    today = datetime.now(timezone.utc).date().isoformat()

    async def visit(name, phone, extra=None):
        r = await c.post("/api/mentorship/outreach/visits", json={"contact_type": "new", "contact_name": name, "contact_phone": phone, "campaign_id": cid}, headers=h)
        vid = r.json()["visit_id"]
        rr = await c.put(f"/api/mentorship/outreach/visits/{vid}/report", json={"status": "wants_followup", "agreed_start_date": today, "call_schedule": "morning", **(extra or {})}, headers=h)
        assert rr.status_code == 200, rr.text
        return vid

    v_happy = await visit(f"Happy Unico{t}", uniq_phone())
    v_strong = await visit(f"Xilofon Fuerte{t}", strong_phone, {"contact_birth_date": "1988-03-03"})
    v_possible = await visit(f"Yerbal Posible{t}", uniq_phone())
    hh = (await c.post("/api/mentorship/outreach/households", json={"campaign_id": cid, "address_line1": "Calle UI 45", "sector": "Sector UI"}, headers=h)).json()
    await c.post(f"/api/mentorship/outreach/households/{hh['household_id']}/events", json={"result": "no_answer", "note": "Nadie abrió"}, headers=h)
    ev = (await c.post(f"/api/mentorship/outreach/households/{hh['household_id']}/events", json={"result": "contacted", "persons": [{"contact_type": "new", "contact_name": f"Origen Hogar{t}", "contact_phone": uniq_phone()}]}, headers=h)).json()
    v_ack = ev["visits"][0]["visit_id"]
    rr = await c.put(f"/api/mentorship/outreach/visits/{v_ack}/report", json={"status": "wants_followup", "agreed_start_date": today, "call_schedule": "morning", "received_mcd": True}, headers=h)
    assert rr.status_code == 200, rr.text
    st = (await c.post(f"/api/mentorship/outreach/visits/{v_ack}/start-seven-weeks", headers=h)).json()
    out = {"password": PASSWORD, "leader_email": leader_email, "mentor_email": mentor_email, "pastor_email": pastor_email,
           "mentor_pid": mentor_pid, "strong_pid": strong_pid, "possible_pid": possible_pid, "campaign_id": cid,
           "v_happy": v_happy, "v_strong": v_strong, "v_possible": v_possible, "v_ack": v_ack, "ack_enrollment": st["enrollment_id"],
           "ack_person": st["converted_person_id"], "gid": gid, "mcd": mcd, "npt": npt, "saved_central": saved}
    await c.aclose(); await pc.aclose()
    with open("/tmp/etapa3_seed.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))


asyncio.run(main())
