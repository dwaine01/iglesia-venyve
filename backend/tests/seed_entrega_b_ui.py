"""Seed for Entrega B UI testing: two mentors (A with 1 MCD unit) + invasion started 3 days ago for A.
Run from /app/backend: python3 tests/seed_entrega_b_ui.py"""
import sys
from datetime import date, timedelta
sys.path.insert(0, "/app/backend/tests")
import test_entrega_b_public_api as t

a_pid, a_uid, a_email = t.make_mentor("UIA")
b_pid, b_uid, b_email = t.make_mentor("UIB")
a_h = t.login(a_email, t.PASSWORD)
started = t.start_invasion(a_h, a_pid, (date.today() - timedelta(days=3)).isoformat())
book = t.mongo.library_books.find_one({"sku": "MCD", "is_active": True})
t.mongo.library_holdings.update_one({"book_id": book["book_id"], "holder_type": "user", "holder_id": a_uid},
                                    {"$set": {"quantity_on_hand": 1, "reserved_qty": 0}, "$setOnInsert": {"_id": str(t.uuid.uuid4())}}, upsert=True)
print(f"A_EMAIL={a_email}\nA_PID={a_pid}\nA_UID={a_uid}\nB_EMAIL={b_email}\nB_PID={b_pid}\nPASSWORD={t.PASSWORD}\nENROLLMENT={started['enrollment_id']}\nPERSON={started.get('converted_person_id')}")
