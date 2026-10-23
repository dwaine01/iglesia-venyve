# Seed / clean campaign for Etapa 5B UI testing. Run: python3 seed_etapa5b_ui.py [seed|clean]
import os
import sys
from datetime import date, timedelta

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
NAME = "QA OutreachUI 5B UI"


def clean():
    cids = db.outreach_campaigns.distinct("campaign_id", {"name": {"$regex": "^QA OutreachUI"}})
    hids = db.outreach_households.distinct("household_id", {"campaign_id": {"$in": cids}})
    db.outreach_visit_events.delete_many({"household_id": {"$in": hids}})
    db.outreach_households.delete_many({"campaign_id": {"$in": cids}})
    db.outreach_participations.delete_many({"campaign_id": {"$in": cids}})
    db.outreach_campaigns.delete_many({"campaign_id": {"$in": cids}})
    print("cleaned campaigns", len(cids), "households", len(hids))


def seed():
    clean()
    tok = requests.post(f"{BASE}/api/auth/login", json={"email": "qa.baptismui53.pastor@example.com", "password": "QaBaptismUI53!"}).json()["token"]
    pa = db.users.find_one({"email": "qa.outreachui.mentora@example.com"})["person_id"]
    pb = db.users.find_one({"email": "qa.outreachui.mentorb@example.com"})["person_id"]
    t = date.today()
    r = requests.post(f"{BASE}/api/mentorship/outreach/campaigns", headers={"Authorization": f"Bearer {tok}"}, json={
        "name": NAME, "location": "Villa Mella QA", "start_date": t.isoformat(), "end_date": (t + timedelta(days=10)).isoformat(),
        "assigned_mentors": [{"person_id": pa}, {"person_id": pb}]})
    print(r.status_code, r.json().get("campaign_id"), "mentora", pa, "mentorb", pb)


if __name__ == "__main__":
    {"seed": seed, "clean": clean}[sys.argv[1] if len(sys.argv) > 1 else "seed"]()
