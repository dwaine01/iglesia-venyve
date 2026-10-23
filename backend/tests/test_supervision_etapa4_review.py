"""Etapa 4 review (testing agent iteration 48): edge cases for supervision scope,
drill-down consistency, thresholds payload, indicator RBAC, delete-preview, C11."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import server
from test_supervision_etapa4 import (
    add_member, auth_client, cleanup, create_person, create_user, make_enrollment, make_front_group,
)


async def _cleanup_groups(ids):
    await server.db.front_groups.delete_many({"front_group_id": {"$in": ids}})
    await server.db.front_group_assignments.delete_many({"front_group_id": {"$in": ids}})


# Scope: leader of a SUB-group (non-root) must still see his own group in drill-down root
@pytest.mark.asyncio
async def test_subgroup_leader_sees_own_group_at_root():
    await cleanup()
    root_leader = await create_person("Root Leader R")
    sub_leader = await create_person("Sub Leader R")
    _, sub_email = await create_user("Sub Leader R", "lider", sub_leader)
    await create_user("Root Leader R", "lider", root_leader)
    client, headers = await auth_client(sub_email)
    groups = []
    try:
        root = await make_front_group("Root R Review", root_leader, root_leader); groups.append(root)
        sub = await make_front_group("Sub R Review", sub_leader, root_leader, parent_id=root); groups.append(sub)
        scope = (await client.get("/api/supervision/scope", headers=headers)).json()
        assert scope["level"] == "branch"
        assert [g["front_group_id"] for g in scope["root_groups"]] == [sub]
        overview = (await client.get("/api/supervision/overview", headers=headers)).json()
        assert overview["scope_level"] == "branch"
        root_list = (await client.get("/api/supervision/groups", headers=headers)).json()["groups"]
        assert sub in [g["front_group_id"] for g in root_list], f"sub-group leader sees empty drill-down root: {root_list}"
    finally:
        await client.aclose(); await _cleanup_groups(groups); await cleanup()


# Scope: leader cannot drill into foreign group via parent_group_id/front_group_id/mentor_person_id
@pytest.mark.asyncio
async def test_branch_leader_forbidden_paths():
    await cleanup()
    la, lb, mb = await create_person("LA Rv"), await create_person("LB Rv"), await create_person("MB Rv")
    _, la_email = await create_user("LA Rv", "lider", la)
    client, headers = await auth_client(la_email)
    groups = []
    try:
        ga = await make_front_group("GA Rv", la, la); groups.append(ga)
        gb = await make_front_group("GB Rv", lb, lb); groups.append(gb)
        await add_member(gb, mb)
        for url in [f"/api/supervision/groups?parent_group_id={gb}", f"/api/supervision/groups?front_group_id={gb}",
                    f"/api/supervision/mentors?front_group_id={gb}", f"/api/supervision/overview?mentor_person_id={mb}",
                    f"/api/supervision/disciples?mentor_person_id={mb}", f"/api/supervision/indicators/paused?front_group_id={gb}"]:
            r = await client.get(url, headers=headers)
            assert r.status_code == 403, f"{url} -> {r.status_code}"
        own = await client.get(f"/api/supervision/mentors?front_group_id={ga}", headers=headers)
        assert own.status_code == 200
    finally:
        await client.aclose(); await _cleanup_groups(groups); await cleanup()


# Scope: self-scope user cannot query another mentor's disciples
@pytest.mark.asyncio
async def test_self_scope_cannot_see_other_mentor():
    await cleanup()
    me, other = await create_person("Self Me Rv"), await create_person("Self Other Rv")
    _, email = await create_user("Self Me Rv", "persona", me)
    client, headers = await auth_client(email)
    try:
        d = await create_person("Disc Other Rv")
        await make_enrollment(d, other, None)
        r = await client.get(f"/api/supervision/disciples?mentor_person_id={other}", headers=headers)
        assert r.status_code == 403
        groups = await client.get("/api/supervision/groups", headers=headers)
        assert groups.status_code == 200 and groups.json()["groups"] == []
        thr = await client.put("/api/supervision/thresholds/stage_stall_days", json={"value": 1}, headers=headers)
        assert thr.status_code == 403
    finally:
        await client.aclose(); await cleanup()


# Thresholds GET payload must only contain threshold entries (UI renders every key)
@pytest.mark.asyncio
async def test_thresholds_payload_only_threshold_keys():
    await cleanup()
    pid = await create_person("Pastor Thr Rv")
    _, email = await create_user("Pastor Thr Rv", "pastor", pid)
    client, headers = await auth_client(email)
    try:
        data = (await client.get("/api/supervision/thresholds", headers=headers)).json()
        non_dict = [k for k, v in data.items() if not isinstance(v, dict) and k not in ("updated_at", "updated_by_user_id")]
        assert non_dict == [], f"thresholds payload leaks non-threshold keys rendered by UI: {non_dict}"
    finally:
        await client.aclose(); await cleanup()


# Thresholds: unknown key -> 404, invalid values accepted?
@pytest.mark.asyncio
async def test_thresholds_validation():
    await cleanup()
    pid = await create_person("Pastor Val Rv")
    _, email = await create_user("Pastor Val Rv", "pastor", pid)
    client, headers = await auth_client(email)
    try:
        r = await client.put("/api/supervision/thresholds/nope", json={"value": 1}, headers=headers)
        assert r.status_code == 404
        bad = await client.put("/api/supervision/thresholds/overdue_activity_ratio_red", json={"value": -5}, headers=headers)
        restore = {"value": 0.30, "label": "% de actividades vencidas sobre el total para marcar el grupo/mentor en rojo", "status": "propuesta"}
        await server.db.supervision_thresholds.update_one({"_id": "default"}, {"$set": {"overdue_activity_ratio_red": restore}})
        assert bad.status_code == 422, f"negative ratio accepted: {bad.status_code}"
    finally:
        await client.aclose(); await cleanup()


# Indicator detail total equals overview count, unknown indicator 404
@pytest.mark.asyncio
async def test_indicator_totals_match_overview():
    await cleanup()
    pid = await create_person("Pastor Ind Rv")
    mentor = await create_person("Mentor Ind Rv")
    _, email = await create_user("Pastor Ind Rv", "pastor", pid)
    client, headers = await auth_client(email)
    try:
        d = await create_person("Disc Ind Rv")
        eid = await make_enrollment(d, mentor, None, decision_status="paused")
        await server.db.process_enrollments.update_one({"enrollment_id": eid}, {"$set": {"decision_paused_reason": "Viaje"}})
        aid = str(uuid.uuid4())
        await server.db.consolidation_activities.insert_one({"_id": aid, "activity_id": aid, "enrollment_id": eid, "status": "pending",
            "scheduled_date": (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat(), "created_at": datetime.now(timezone.utc)})
        ov = (await client.get(f"/api/supervision/overview?mentor_person_id={mentor}", headers=headers)).json()
        assert ov["consolidation"]["paused_total"] == 1
        assert ov["consolidation"]["paused_by_reason"][0]["reason"] == "Viaje"
        assert ov["semaphore"] == "red"
        for key, expected in [("paused", ov["weaknesses"]["paused_total"]), ("activities_overdue", ov["consolidation"]["activities_overdue"])]:
            det = (await client.get(f"/api/supervision/indicators/{key}?mentor_person_id={mentor}", headers=headers)).json()
            assert det["total"] == expected == 1
        assert (await client.get("/api/supervision/indicators/bogus", headers=headers)).status_code == 404
        await server.db.consolidation_activities.delete_one({"_id": aid})
    finally:
        await client.aclose(); await cleanup()


# Group drill-down: overview filtered by front_group_id should match the card's branch totals
@pytest.mark.asyncio
async def test_group_overview_consistent_with_group_card():
    await cleanup()
    pid = await create_person("Pastor Cons Rv")
    leader, sub_leader, sub_mentor = await create_person("L Cons"), await create_person("SL Cons"), await create_person("SM Cons")
    _, email = await create_user("Pastor Cons Rv", "pastor", pid)
    client, headers = await auth_client(email)
    groups = []
    try:
        root = await make_front_group("Root Cons Rv", leader, pid); groups.append(root)
        sub = await make_front_group("Sub Cons Rv", sub_leader, pid, parent_id=root); groups.append(sub)
        await add_member(sub, sub_mentor)
        d = await create_person("Disc Cons")
        eid = await make_enrollment(d, sub_mentor, sub)
        aid = str(uuid.uuid4())
        await server.db.consolidation_activities.insert_one({"_id": aid, "activity_id": aid, "enrollment_id": eid, "status": "pending",
            "scheduled_date": (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat(), "created_at": datetime.now(timezone.utc)})
        card = [g for g in (await client.get("/api/supervision/groups", headers=headers)).json()["groups"] if g["front_group_id"] == root][0]
        assert card["activities_overdue"] == 1 and card["semaphore"] == "red"
        ov = (await client.get(f"/api/supervision/overview?front_group_id={root}", headers=headers)).json()
        await server.db.consolidation_activities.delete_one({"_id": aid})
        assert ov["consolidation"]["activities_overdue"] == card["activities_overdue"], (
            f"card says {card['activities_overdue']} overdue in branch but overview for same group says {ov['consolidation']['activities_overdue']}")
    finally:
        await client.aclose(); await _cleanup_groups(groups); await cleanup()


# Front-group delete-preview: subgroups block; leader RBAC
@pytest.mark.asyncio
async def test_front_group_preview_blocked_by_children():
    await cleanup()
    pid = await create_person("Pastor FG Rv")
    _, email = await create_user("Pastor FG Rv", "pastor", pid)
    client, headers = await auth_client(email)
    groups = []
    try:
        root = await make_front_group("Root FG Rv", pid, pid); groups.append(root)
        sub = await make_front_group("Sub FG Rv", pid, pid, parent_id=root); groups.append(sub)
        r = await client.get(f"/api/front-groups/{root}/delete-preview", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["blocked"] is True, data
        nf = await client.get(f"/api/front-groups/{uuid.uuid4()}/delete-preview", headers=headers)
        assert nf.status_code == 404
    finally:
        await client.aclose(); await _cleanup_groups(groups); await cleanup()


# Cleanup leaves no QA front groups behind (dev's test leaks 'Rama * Scope' groups)
@pytest.mark.asyncio
async def test_qa_cleanup_removes_front_groups():
    await cleanup()
    leftovers = await server.db.front_groups.count_documents({"name": {"$regex": "(Scope|C11|Preview E4)$"}})
    assert leftovers == 0, f"{leftovers} QA front groups leaked by test_supervision_etapa4 cleanup"
