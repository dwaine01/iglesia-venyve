"""Fases 6-7: Persona 360, Mapa, Invasión y Operación 72 enlazados al árbol."""
import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

import server
import evangelism_routes
from access_control import access_defaults_for_role
from geo_queries import person_features
from qa_demo_cleanup import delete_qa_artifacts, qa_preview


PASSWORD = "Integrations2026!"


async def cleanup():
    preview = await qa_preview(server.db)
    await delete_qa_artifacts(server.db, preview["preview_token"], preview["confirmation_phrase"])


async def person(label: str) -> str:
    person_id = ObjectId()
    await server.db.persons.insert_one({
        "_id": person_id, "person_number": f"VV-QA{uuid.uuid4().hex[:7].upper()}",
        "nombre": "QA", "apellido": label, "search_key": f"qa {label}".lower(),
        "idempotency_key": f"qa:fg-integrations:{uuid.uuid4()}", "version": 1,
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return str(person_id)


async def user(label: str, role: str, person_id: str | None = None, capabilities=None) -> str:
    user_id = ObjectId(); email = f"qa.fgintegrations.{uuid.uuid4().hex[:8]}@example.com"
    defaults = access_defaults_for_role(role)
    if capabilities is not None: defaults["capabilities"] = capabilities
    await server.db.users.insert_one({
        "_id": user_id, "nombre": f"QA {label}", "email": email,
        "password": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "rol": role, "is_active": True, "token_version": 1,
        "created_at": datetime.now(timezone.utc), **defaults,
        **({"person_id": person_id} if person_id else {}),
    })
    return email


async def auth(email: str) -> tuple[AsyncClient, dict, dict]:
    client = AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return client, headers, me.json()


@pytest.mark.asyncio
async def test_person_map_invasion_op72_and_rollup_without_pastoral_leak(monkeypatch):
    await cleanup()
    pastor_email = await user("Pastora Integraciones", "pastor")
    leader_person = await person("Líder Dual")
    leader_email = await user("Líder Dual", "lider", leader_person)
    converted_person = await person("Persona Invasión")

    async def fake_geocode(values):
        return {
            "location": {"type": "Point", "coordinates": [-82.99, 39.96]},
            "latitude": 39.96, "longitude": -82.99,
            "geocoding_status": "matched", "verification_status": "verified",
            "geocoding_provider": "qa", "geocoding_accuracy": "rooftop",
            "geocoding_confidence_score": 1.0, "geocoding_matched_address": "100 QA St",
            "geocoded_at": datetime.now(timezone.utc), "zone_key": "south", "zone_number": 3,
            "subzone_key": "south-near", "sector_id": None, "sector_name": None, "sector_order": None,
        }
    monkeypatch.setattr(evangelism_routes, "_geocode", fake_geocode)

    pastor, ph, pastor_user = await auth(pastor_email)
    leader, lh, leader_user = await auth(leader_email)
    try:
        root = (await pastor.post("/api/front-groups", json={"name": "QA Raíz Pastoral"}, headers=ph)).json()
        branch = (await pastor.post("/api/front-groups", json={"name": "QA Rama Invasión", "parent_group_id": root["front_group_id"]}, headers=ph)).json()
        assert (await pastor.post(f"/api/front-groups/{root['front_group_id']}/members", json={"person_id": leader_person, "role": "member"}, headers=ph)).status_code == 201
        assert (await pastor.post(f"/api/front-groups/{branch['front_group_id']}/leader", json={"person_id": leader_person, "reason": "Lidera rama"}, headers=ph)).status_code == 200

        await server.db.person_addresses.insert_one({
            "_id": str(uuid.uuid4()), "address_id": str(uuid.uuid4()), "person_id": leader_person,
            "tipo": "casa", "linea1": "100 QA St", "ciudad": "Columbus", "provincia": "OH", "pais": "Estados Unidos", "es_principal": True,
            "location": {"type": "Point", "coordinates": [-82.99, 39.96]},
            "geocoding_status": "matched", "verification_status": "verified", "coordinates_stale": False,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        })
        features = await person_features(server.db, pastor_user, {})
        leader_feature = next(item for item in features if item["properties"]["entity_id"] == leader_person)
        assert set(leader_feature["properties"]["front_group_ids"]) == {root["front_group_id"], branch["front_group_id"]}
        assert leader_feature["properties"]["member_front_group_ids"] == [root["front_group_id"]]
        assert leader_feature["properties"]["led_front_group_ids"] == [branch["front_group_id"]]

        profile = await pastor.get(f"/api/core/persons/{leader_person}/profile", headers=ph)
        assert profile.status_code == 200, profile.text
        assert len(profile.json()["grupos_frontales"]["items"]) == 2

        invasion = await leader.post("/api/geo/evangelism", json={
            "house_number": "100", "street_name": "QA Invasion St", "city": "Columbus", "state": "OH",
            "front_group_id": branch["front_group_id"], "invasion_reference": "QA-INV-001",
        }, headers=lh)
        assert invasion.status_code == 201, invasion.text
        target_id = invasion.json()["target_id"]
        assert invasion.json()["front_group_id"] == branch["front_group_id"]
        assert await server.db.front_group_work_assignments.find_one({"source_type": "evangelism_target", "source_id": target_id, "assigned_group_id": branch["front_group_id"]})

        op72 = await pastor.post("/api/care/op72", json={
            "person_id": converted_person, "decision_at": datetime.now(timezone.utc).isoformat(),
            "source_type": "evangelism_target", "source_id": target_id,
        }, headers=ph)
        assert op72.status_code == 201, op72.text
        op72_record = op72.json()["record"]
        assert op72_record["front_group_id"] == branch["front_group_id"]
        assert await server.db.front_group_work_assignments.find_one({"source_type": "op72", "source_id": op72_record["op72_id"], "assigned_group_id": branch["front_group_id"]})

        report = await leader.get(f"/api/front-group-reports/{branch['front_group_id']}", headers=lh)
        assert report.status_code == 200, report.text
        assert report.json()["metrics"]["invasions"]["targets"] == 1
        assert report.json()["metrics"]["op72"]["total"] == 1
        assert report.json()["metrics"]["work"]["total"] >= 2

        private = await leader.get(f"/api/care/op72/{op72_record['op72_id']}", headers=lh)
        assert private.status_code == 404
        report_text = str(report.json()).lower()
        assert "note_content" not in report_text and "case_summary" not in report_text and "pastoral_case_notes" not in report_text
    finally:
        await pastor.aclose(); await leader.aclose(); await cleanup()