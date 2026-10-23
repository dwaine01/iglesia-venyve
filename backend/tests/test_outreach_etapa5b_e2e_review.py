# Etapa 5B review (testing agent): end-to-end pool de casas - import/claim/release/assign/aislamiento/dashboard + edge cases
# Requiere: python3 /app/backend/tests/ui_outreach_fixture.py seed
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/mentorship/outreach"
PW = "QaOutreachUI2026!"
PASTOR = ("coreqa.pastor@example.com", "CoreQA2026!Pastor")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def ctx():
    pastor = login(*PASTOR)
    u = {}
    for slug in ("mentora", "mentorb", "leader", "nobadge"):
        email = f"qa.outreachui.{slug}@example.com"
        doc = db.users.find_one({"email": email})
        if not doc:
            pytest.skip("run ui_outreach_fixture.py seed")
        u[slug] = {"pid": doc["person_id"], "h": login(email, PW)}
    today = date.today()
    mk = lambda name, roster: requests.post(f"{API}/campaigns", headers=pastor, json={
        "name": f"QA OutreachUI 5B review {name} {uuid.uuid4().hex[:5]}", "location": "QA Review",
        "start_date": today.isoformat(), "end_date": (today + timedelta(days=5)).isoformat(),
        "assigned_mentors": [{"person_id": u[s]["pid"]} for s in roster]})
    r1 = mk("A", ["mentora", "mentorb"]); assert r1.status_code == 201, r1.text
    r2 = mk("B", ["mentorb"]); assert r2.status_code == 201, r2.text
    cids = [r1.json()["campaign_id"], r2.json()["campaign_id"]]
    yield {"pastor": pastor, "u": u, "cid": cids[0], "cid2": cids[1]}
    hids = db.outreach_households.distinct("household_id", {"campaign_id": {"$in": cids}})
    db.outreach_visit_events.delete_many({"household_id": {"$in": hids}})
    db.outreach_households.delete_many({"campaign_id": {"$in": cids}})
    db.outreach_participations.delete_many({"campaign_id": {"$in": cids}})
    db.outreach_campaigns.delete_many({"campaign_id": {"$in": cids}})


def imp(ctx, h, cid, addrs):
    return requests.post(f"{API}/campaigns/{cid}/households/import", headers=h, json={"entries": [{"address_line1": a, "sector": "QA Rev"} for a in addrs]})


def avail(ctx, cid, h=None):
    return requests.get(f"{API}/campaigns/{cid}/households/available", headers=h or ctx["pastor"])


def find(ctx, cid, addr):
    return next(x for x in avail(ctx, cid).json()["items"] if x["address_line1"] == addr)


# import permissions
def test_leader_capability_can_import(ctx):
    r = imp(ctx, ctx["u"]["leader"]["h"], ctx["cid"], ["REV L1"])
    assert r.status_code == 201 and r.json()["created"] == 1


def test_mentor_cannot_import(ctx):
    assert imp(ctx, ctx["u"]["mentora"]["h"], ctx["cid"], ["REV X"]).status_code == 403


def test_import_unknown_campaign_404(ctx):
    assert imp(ctx, ctx["pastor"], "nope-" + uuid.uuid4().hex, ["X"]).status_code == 404


def test_import_empty_entries_422(ctx):
    r = requests.post(f"{API}/campaigns/{ctx['cid']}/households/import", headers=ctx["pastor"], json={"entries": []})
    assert r.status_code == 422


# pool visibility / roster
def test_roster_mentor_sees_pool_nonroster_403(ctx):
    imp(ctx, ctx["pastor"], ctx["cid2"], ["REV B-only"])
    assert avail(ctx, ctx["cid"], ctx["u"]["mentora"]["h"]).status_code == 200
    assert avail(ctx, ctx["cid2"], ctx["u"]["mentora"]["h"]).status_code == 403
    h = find(ctx, ctx["cid2"], "REV B-only")
    assert requests.post(f"{API}/households/{h['household_id']}/claim", headers=ctx["u"]["mentora"]["h"]).status_code == 403


def test_nobadge_cannot_claim_or_be_assigned(ctx):
    imp(ctx, ctx["pastor"], ctx["cid"], ["REV NB"])
    h = find(ctx, ctx["cid"], "REV NB")
    assert requests.post(f"{API}/households/{h['household_id']}/claim", headers=ctx["u"]["nobadge"]["h"]).status_code in (403, 409)
    r = requests.post(f"{API}/households/{h['household_id']}/assign", headers=ctx["pastor"], json={"mentor_person_id": ctx["u"]["nobadge"]["pid"]})
    assert r.status_code == 409


# claim / isolation / release
def test_claim_isolation_release(ctx):
    imp(ctx, ctx["pastor"], ctx["cid"], ["REV C1"])
    h = find(ctx, ctx["cid"], "REV C1"); hid = h["household_id"]
    a, b = ctx["u"]["mentora"], ctx["u"]["mentorb"]
    r = requests.post(f"{API}/households/{hid}/claim", headers=a["h"])
    assert r.status_code == 200 and r.json()["mentor_person_id"] == a["pid"] and r.json()["status"] == "assigned"
    # idempotent
    assert requests.post(f"{API}/households/{hid}/claim", headers=a["h"]).status_code == 200
    rb = requests.post(f"{API}/households/{hid}/claim", headers=b["h"])
    assert rb.status_code == 409 and "tomada" in rb.json()["detail"]
    assert requests.get(f"{API}/households/{hid}", headers=b["h"]).status_code == 403
    rr = requests.post(f"{API}/households/{hid}/release", headers=b["h"])
    assert rr.status_code == 403 and "Solo el mentor responsable" in rr.json()["detail"]
    # B's lists never include A's house
    lb = requests.get(f"{API}/households?mentor_person_id={b['pid']}", headers=b["h"]).json()["items"]
    assert hid not in [x["household_id"] for x in lb]
    lb2 = requests.get(f"{API}/households?mentor_person_id={a['pid']}", headers=b["h"]).json()["items"]
    assert hid not in [x["household_id"] for x in lb2]
    assert hid not in [x["household_id"] for x in avail(ctx, ctx["cid"], b["h"]).json()["items"]]
    la = requests.get(f"{API}/households?mentor_person_id={a['pid']}", headers=a["h"]).json()["items"]
    assert hid in [x["household_id"] for x in la]
    # release by owner -> back to pool, B can take it
    r = requests.post(f"{API}/households/{hid}/release", headers=a["h"])
    assert r.status_code == 200 and r.json()["status"] == "available" and r.json()["mentor_person_id"] is None
    assert requests.post(f"{API}/households/{hid}/release", headers=a["h"]).status_code == 409
    assert requests.post(f"{API}/households/{hid}/claim", headers=b["h"]).status_code == 200


def test_concurrent_claim_vs_assign_single_owner(ctx):
    imp(ctx, ctx["pastor"], ctx["cid"], [f"REV R{i}" for i in range(5)])
    a, b = ctx["u"]["mentora"], ctx["u"]["mentorb"]
    for i in range(5):
        hid = find(ctx, ctx["cid"], f"REV R{i}")["household_id"]
        with ThreadPoolExecutor(3) as ex:
            f1 = ex.submit(requests.post, f"{API}/households/{hid}/claim", headers=a["h"])
            f2 = ex.submit(requests.post, f"{API}/households/{hid}/claim", headers=b["h"])
            f3 = ex.submit(requests.post, f"{API}/households/{hid}/assign", headers=ctx["pastor"], json={"mentor_person_id": b["pid"]})
            codes = [f.result().status_code for f in (f1, f2, f3)]
        doc = db.outreach_households.find_one({"household_id": hid})
        assert doc["mentor_person_id"] in (a["pid"], b["pid"])
        assert codes.count(409) >= 1, codes


# assign
def test_assign_by_leader_and_mentor_forbidden(ctx):
    imp(ctx, ctx["pastor"], ctx["cid"], ["REV AS1"])
    hid = find(ctx, ctx["cid"], "REV AS1")["household_id"]
    a = ctx["u"]["mentora"]
    assert requests.post(f"{API}/households/{hid}/assign", headers=ctx["u"]["mentorb"]["h"], json={"mentor_person_id": a["pid"]}).status_code == 403
    r = requests.post(f"{API}/households/{hid}/assign", headers=ctx["u"]["leader"]["h"], json={"mentor_person_id": a["pid"]})
    assert r.status_code == 200 and r.json()["mentor_person_id"] == a["pid"]
    r2 = requests.post(f"{API}/households/{hid}/assign", headers=ctx["pastor"], json={"mentor_person_id": ctx["u"]["mentorb"]["pid"]})
    assert r2.status_code == 409


def test_assign_to_mentor_outside_roster(ctx):
    """Reports whether backend allows assigning a campaign house to a mentor NOT in that campaign roster."""
    imp(ctx, ctx["pastor"], ctx["cid2"], ["REV OUT"])
    hid = find(ctx, ctx["cid2"], "REV OUT")["household_id"]
    r = requests.post(f"{API}/households/{hid}/assign", headers=ctx["pastor"], json={"mentor_person_id": ctx["u"]["mentora"]["pid"]})
    print("assign outside roster ->", r.status_code, r.text[:150])
    assert r.status_code in (403, 409, 422), "backend allowed assigning to a mentor outside the invasion roster"


# participation does not grant leader dashboard
def test_participate_no_dashboard(ctx):
    a = ctx["u"]["mentora"]
    camp = next(c for c in requests.get(f"{API}/campaigns", headers=a["h"]).json()["items"] if c["campaign_id"] == ctx["cid"])
    assert camp["my_participation_status"] is not None
    assert requests.get(f"{API}/dashboard", headers=a["h"]).status_code == 403
