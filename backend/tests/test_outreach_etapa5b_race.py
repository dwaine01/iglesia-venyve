# Etapa 5B: claim concurrente real (2 mentores en paralelo x 10 casas) - nunca dos dueños
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests

from test_outreach_etapa5b_households_pool import API, ctx, db  # noqa: F401


def test_parallel_claims_single_winner(ctx):  # noqa: F811
    a, b = ctx["u"]["mentora"], ctx["u"]["mentorb"]
    addrs = [f"QA Race {uuid.uuid4().hex[:6]}" for _ in range(10)]
    r = requests.post(f"{API}/campaigns/{ctx['cid']}/households/import", headers=ctx["pastor"], json={"entries": [{"address_line1": x} for x in addrs]})
    assert r.status_code == 201
    hids = [d["household_id"] for d in db.outreach_households.find({"address_line1": {"$in": addrs}})]
    for hid in hids:
        with ThreadPoolExecutor(max_workers=2) as ex:
            fa = ex.submit(requests.post, f"{API}/households/{hid}/claim", headers=a["h"])
            fb = ex.submit(requests.post, f"{API}/households/{hid}/claim", headers=b["h"])
            codes = sorted([fa.result().status_code, fb.result().status_code])
        assert codes == [200, 409], codes
        owner = db.outreach_households.find_one({"household_id": hid})["mentor_person_id"]
        assert owner in (a["pid"], b["pid"])
