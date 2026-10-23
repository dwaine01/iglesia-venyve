# Etapa 5B: pool de casas disponibles (import / available / claim / release / assign / aislamiento entre mentores)
# Requiere: python3 /app/backend/tests/ui_outreach_fixture.py seed  (qa.outreachui.* users)
import os
import uuid
from datetime import date, timedelta

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/mentorship/outreach"
PW = "QaOutreachUI2026!"
PASTOR = ("qa.baptismui53.pastor@example.com", "QaBaptismUI53!")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code} {r.text[:120]}")
    data = r.json()
    return {"Authorization": f"Bearer {data['token']}"}, data["user"]


def pid_of(email):
    u = db.users.find_one({"email": email})
    if not u:
        pytest.skip(f"fixture user {email} missing - run ui_outreach_fixture.py seed")
    return u["person_id"]


@pytest.fixture(scope="module")
def ctx():
    pastor_h, _ = login(*PASTOR)
    users = {}
    for slug in ("mentora", "mentorb", "leader", "nobadge"):
        email = f"qa.outreachui.{slug}@example.com"
        users[slug] = {"pid": pid_of(email), "h": login(email, PW)[0]}
    today = date.today()
    r = requests.post(f"{API}/campaigns", headers=pastor_h, json={
        "name": f"QA OutreachUI 5B pytest {uuid.uuid4().hex[:6]}", "location": "QA Sector 5B",
        "start_date": today.isoformat(), "end_date": (today + timedelta(days=7)).isoformat(),
        "assigned_mentors": [{"person_id": users["mentora"]["pid"]}, {"person_id": users["mentorb"]["pid"]}],
    })
    assert r.status_code == 201, r.text
    cid = r.json()["campaign_id"]
    # second campaign without mentors (for 403 roster check)
    r2 = requests.post(f"{API}/campaigns", headers=pastor_h, json={
        "name": f"QA OutreachUI 5B other {uuid.uuid4().hex[:6]}", "location": "QA Other",
        "start_date": today.isoformat(), "end_date": (today + timedelta(days=7)).isoformat(), "assigned_mentors": [],
    })
    assert r2.status_code == 201, r2.text
    yield {"pastor": pastor_h, "u": users, "cid": cid, "other_cid": r2.json()["campaign_id"]}
    db.outreach_visit_events.delete_many({"household_id": {"$in": db.outreach_households.distinct("household_id", {"campaign_id": {"$in": [cid, r2.json()["campaign_id"]]}})}})
    db.outreach_households.delete_many({"campaign_id": {"$in": [cid, r2.json()["campaign_id"]]}})
    db.outreach_participations.delete_many({"campaign_id": {"$in": [cid, r2.json()["campaign_id"]]}})
    db.outreach_campaigns.delete_many({"campaign_id": {"$in": [cid, r2.json()["campaign_id"]]}})


def import_one(ctx, headers, addr):
    r = requests.post(f"{API}/campaigns/{ctx['cid']}/households/import", headers=headers, json={"entries": [{"address_line1": addr, "sector": "QA Sector"}]})
    assert r.status_code == 201, r.text
    items = requests.get(f"{API}/campaigns/{ctx['cid']}/households/available", headers=ctx["pastor"]).json()["items"]
    return next(h for h in items if h["address_line1"] == addr)


# Import
class TestImport:
    def test_pastor_import_creates_available(self, ctx):
        r = requests.post(f"{API}/campaigns/{ctx['cid']}/households/import", headers=ctx["pastor"], json={"entries": [
            {"address_line1": "QA Calle 1 #5", "sector": "Villa Mella"}, {"address_line1": "QA Calle 2"}, {"address_line1": "  ", "sector": ""}]})
        assert r.status_code == 201
        assert r.json() == {"created": 2, "skipped": 1}
        docs = list(db.outreach_households.find({"campaign_id": ctx["cid"], "address_line1": {"$in": ["QA Calle 1 #5", "QA Calle 2"]}}))
        assert len(docs) == 2 and all(d["mentor_person_id"] is None and d["status"] == "available" for d in docs)

    def test_leader_capability_can_import(self, ctx):
        r = requests.post(f"{API}/campaigns/{ctx['cid']}/households/import", headers=ctx["u"]["leader"]["h"], json={"entries": [{"address_line1": "QA Leader Casa"}]})
        assert r.status_code == 201 and r.json()["created"] == 1

    def test_mentor_cannot_import(self, ctx):
        r = requests.post(f"{API}/campaigns/{ctx['cid']}/households/import", headers=ctx["u"]["mentora"]["h"], json={"entries": [{"address_line1": "QA X"}]})
        assert r.status_code == 403

    def test_import_unknown_campaign_404(self, ctx):
        r = requests.post(f"{API}/campaigns/nope-{uuid.uuid4()}/households/import", headers=ctx["pastor"], json={"entries": [{"address_line1": "QA X"}]})
        assert r.status_code == 404

    def test_import_empty_entries_422(self, ctx):
        r = requests.post(f"{API}/campaigns/{ctx['cid']}/households/import", headers=ctx["pastor"], json={"entries": []})
        assert r.status_code == 422


# Available pool listing
class TestAvailable:
    def test_roster_mentor_sees_only_available(self, ctx):
        r = requests.get(f"{API}/campaigns/{ctx['cid']}/households/available", headers=ctx["u"]["mentora"]["h"])
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1 and all(h["mentor_person_id"] is None for h in items)
        assert all(h["campaign_id"] == ctx["cid"] for h in items)

    def test_non_roster_403(self, ctx):
        r = requests.get(f"{API}/campaigns/{ctx['other_cid']}/households/available", headers=ctx["u"]["mentora"]["h"])
        assert r.status_code == 403

    def test_nobadge_403(self, ctx):
        r = requests.get(f"{API}/campaigns/{ctx['cid']}/households/available", headers=ctx["u"]["nobadge"]["h"])
        assert r.status_code == 403

    def test_leader_can_list(self, ctx):
        r = requests.get(f"{API}/campaigns/{ctx['other_cid']}/households/available", headers=ctx["u"]["leader"]["h"])
        assert r.status_code == 200


# Claim / conflict / isolation / release
class TestClaimRelease:
    def test_claim_conflict_isolation_release(self, ctx):
        a, b = ctx["u"]["mentora"], ctx["u"]["mentorb"]
        h = import_one(ctx, ctx["pastor"], f"QA Conflict {uuid.uuid4().hex[:5]}")
        hid = h["household_id"]
        r = requests.post(f"{API}/households/{hid}/claim", headers=a["h"])
        assert r.status_code == 200 and r.json()["mentor_person_id"] == a["pid"] and r.json()["status"] == "assigned"
        # idempotent
        assert requests.post(f"{API}/households/{hid}/claim", headers=a["h"]).status_code == 200
        r = requests.post(f"{API}/households/{hid}/claim", headers=b["h"])
        assert r.status_code == 409 and "ya fue tomada" in r.json()["detail"]
        assert db.outreach_households.find_one({"household_id": hid})["mentor_person_id"] == a["pid"]
        # isolation
        assert requests.get(f"{API}/households/{hid}", headers=b["h"]).status_code == 403
        lst = requests.get(f"{API}/households?mentor_person_id={b['pid']}", headers=b["h"]).json()["items"]
        assert hid not in [x["household_id"] for x in lst]
        lst_a = requests.get(f"{API}/households?mentor_person_id={a['pid']}", headers=b["h"]).json()["items"]
        assert hid not in [x["household_id"] for x in lst_a], "Mentor B can list Mentor A's household by passing A's pid"
        r = requests.post(f"{API}/households/{hid}/release", headers=b["h"])
        assert r.status_code == 403 and "Solo el mentor responsable" in r.json()["detail"]
        # not in pool anymore
        pool = requests.get(f"{API}/campaigns/{ctx['cid']}/households/available", headers=b["h"]).json()["items"]
        assert hid not in [x["household_id"] for x in pool]
        # A sees it in own list
        mine = requests.get(f"{API}/households?mentor_person_id={a['pid']}", headers=a["h"]).json()["items"]
        assert hid in [x["household_id"] for x in mine]
        # insert an event to check history preserved
        db.outreach_visit_events.insert_one({"_id": str(uuid.uuid4()), "visit_event_id": str(uuid.uuid4()), "household_id": hid, "result": "no_answer", "occurred_at": "2026-01-01T00:00:00Z", "mentor_person_id": a["pid"]})
        r = requests.post(f"{API}/households/{hid}/release", headers=a["h"])
        assert r.status_code == 200 and r.json()["mentor_person_id"] is None and r.json()["status"] == "available"
        assert db.outreach_visit_events.count_documents({"household_id": hid}) == 1
        assert requests.post(f"{API}/households/{hid}/release", headers=a["h"]).status_code == 409
        # B can now claim
        assert requests.post(f"{API}/households/{hid}/claim", headers=b["h"]).status_code == 200

    def test_nobadge_cannot_claim(self, ctx):
        h = import_one(ctx, ctx["pastor"], f"QA NoBadge {uuid.uuid4().hex[:5]}")
        assert requests.post(f"{API}/households/{h['household_id']}/claim", headers=ctx["u"]["nobadge"]["h"]).status_code == 409

    def test_non_roster_cannot_claim(self, ctx):
        # leader has badge but is not in the roster
        h = import_one(ctx, ctx["pastor"], f"QA NonRoster {uuid.uuid4().hex[:5]}")
        assert requests.post(f"{API}/households/{h['household_id']}/claim", headers=ctx["u"]["leader"]["h"]).status_code == 403


# Direct assign by leader
class TestAssign:
    def test_assign_flow(self, ctx):
        a, b = ctx["u"]["mentora"], ctx["u"]["mentorb"]
        h = import_one(ctx, ctx["pastor"], f"QA Assign {uuid.uuid4().hex[:5]}")
        hid = h["household_id"]
        assert requests.post(f"{API}/households/{hid}/assign", headers=a["h"], json={"mentor_person_id": a["pid"]}).status_code == 403
        r = requests.post(f"{API}/households/{hid}/assign", headers=ctx["pastor"], json={"mentor_person_id": ctx["u"]["nobadge"]["pid"]})
        assert r.status_code == 409
        r = requests.post(f"{API}/households/{hid}/assign", headers=ctx["u"]["leader"]["h"], json={"mentor_person_id": a["pid"]})
        assert r.status_code == 200 and r.json()["mentor_person_id"] == a["pid"]
        r = requests.post(f"{API}/households/{hid}/assign", headers=ctx["pastor"], json={"mentor_person_id": b["pid"]})
        assert r.status_code == 409 and "devuélvala primero" in r.json()["detail"]
        # leader release
        assert requests.post(f"{API}/households/{hid}/release", headers=ctx["u"]["leader"]["h"]).status_code == 200

    def test_assign_missing_body_422(self, ctx):
        h = import_one(ctx, ctx["pastor"], f"QA Assign422 {uuid.uuid4().hex[:5]}")
        assert requests.post(f"{API}/households/{h['household_id']}/assign", headers=ctx["pastor"], json={}).status_code == 422


# Participation does not grant leader access
class TestNoLeaderLeak:
    def test_mentor_dashboard_403(self, ctx):
        r = requests.post(f"{API}/campaigns/{ctx['cid']}/participate", headers=ctx["u"]["mentora"]["h"])
        assert r.status_code == 200
        assert requests.get(f"{API}/dashboard", headers=ctx["u"]["mentora"]["h"]).status_code == 403
