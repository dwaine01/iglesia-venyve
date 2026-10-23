# Helper E2E para rescate de acceso (admin_recovery) contra backend real bajo supervisor.
# Uso: python3 e2e_admin_recovery_helper.py seed|state|cleanup
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import bcrypt
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from access_control import access_defaults_for_role  # noqa: E402

cfg = dotenv_values("/app/backend/.env")
db = MongoClient(cfg["MONGO_URL"])[cfg["DB_NAME"]]
STATE = "/tmp/e2e_recovery_state.json"
ORIG = "OrigPastorPass2026!"


def mk(label, role, extra=None):
    email = f"qa.e2erecovery.{label}.{uuid.uuid4().hex[:6]}@example.com"
    doc = {"_id": ObjectId(), "nombre": f"QA E2E {label}", "email": email,
           "password": bcrypt.hashpw(ORIG.encode(), bcrypt.gensalt()).decode(),
           "rol": role, "is_active": True, "token_version": 1,
           "created_at": datetime.now(timezone.utc), **access_defaults_for_role(role)}
    if extra:
        doc.update(extra)
    db.users.insert_one(doc)
    return email


cmd = sys.argv[1]
if cmd == "seed":
    st = {"pastor": mk("pastor", "pastor"),
          "lider": mk("lider", "lider"),
          "coord": mk("coord", "lider", {"access_level": "coordinador_general"}),
          "persona": mk("persona", "persona")}
    json.dump(st, open(STATE, "w"))
    print(json.dumps(st))
elif cmd == "state":
    st = json.load(open(STATE))
    out = {}
    for k, e in st.items():
        u = db.users.find_one({"email": e})
        out[k] = {"orig_ok": bcrypt.checkpw(ORIG.encode(), u["password"].encode()),
                  "hash": u["password"], "tv": u.get("token_version"), "active": u.get("is_active"),
                  "mcp": u.get("must_change_password"), "rol": u.get("rol"),
                  "rec": db.system_recovery.count_documents({"email": e})}
        if len(sys.argv) > 2:
            out[k]["check_" + sys.argv[2][:4]] = bcrypt.checkpw(sys.argv[2].encode(), u["password"].encode())
    out["total_recovery"] = db.system_recovery.count_documents({})
    out["ghost_users"] = db.users.count_documents({"email": {"$regex": "^qa.e2erecovery.ghost"}})
    out["recovery_docs"] = [{k: str(v) for k, v in d.items() if k != "_id"} for d in db.system_recovery.find()]
    print(json.dumps(out, indent=1, default=str))
elif cmd == "deactivate":
    st = json.load(open(STATE))
    print(db.users.update_one({"email": st["pastor"]}, {"$set": {"is_active": False}}).modified_count)
elif cmd == "cleanup":
    st = json.load(open(STATE))
    emails = list(st.values())
    print("users del:", db.users.delete_many({"email": {"$in": emails}}).deleted_count)
    print("recovery del:", db.system_recovery.delete_many({"email": {"$regex": "^qa.e2erecovery"}}).deleted_count)
    print("attempts del:", db.login_attempts.delete_many({}).deleted_count if len(sys.argv) > 2 else 0)
