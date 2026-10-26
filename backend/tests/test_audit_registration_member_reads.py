"""Auditoría 2/10: el registro libre está cerrado y un Miembro (cuenta «persona») ya no lee los
bautismos, presentaciones de niños ni reportes de Formación de toda la iglesia; sí ve lo suyo."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_free_registration_is_closed_and_short_passwords_rejected():
    email = f"qa.libre.{uuid.uuid4().hex}@example.com"
    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as client:
        free = await client.post("/api/auth/register", json={"nombre": "Sin Invitación", "email": email, "password": "UnaClaveLarga2026", "rol": "persona"})
        assert free.status_code == 403 and "invitación" in free.json()["detail"]
        pastor = await client.post("/api/auth/register", json={"nombre": "Falso Pastor", "email": email, "password": "UnaClaveLarga2026", "rol": "pastor"})
        assert pastor.status_code == 403 and "pastor" in pastor.json()["detail"].lower()
        short = await client.post("/api/auth/register", json={"nombre": "Clave Corta", "email": email, "password": "corta", "invite_code": "NOEXISTE"})
        assert short.status_code == 422
    assert await db.users.count_documents({"email": email}) == 0


@pytest.mark.asyncio
async def test_member_sees_only_own_baptism_and_children_not_church_lists():
    fx = Fixture()
    event_ids, child_ids = [], []
    try:
        pastora = await fx.account(await fx.person("PastoraAud2"), "pastora")
        member_id = await fx.person("MiembroAud2")
        member = await fx.account(member_id, "persona")
        other_id = await fx.person("OtraAud2")
        child_id, other_child_id = await fx.person("HijoAud2"), await fx.person("NinoAjenoAud2")
        child_ids += [child_id, other_child_id]
        now = datetime.now(timezone.utc)
        for event_id, collection in ((f"bap-{uuid.uuid4().hex}", db.baptism_events), (f"ded-{uuid.uuid4().hex}", db.dedication_events)):
            await collection.insert_one({"_id": event_id, "event_id": event_id, "name": "Evento QA", "event_date": "2026-11-01", "status": "scheduled", "created_at": now})
            event_ids.append((collection, event_id))
        await db.person_baptisms.insert_many([
            {"baptism_id": f"b-{uuid.uuid4().hex}", "person_id": member_id, "event_id": event_ids[0][1], "status": "scheduled", "created_at": now},
            {"baptism_id": f"b-{uuid.uuid4().hex}", "person_id": other_id, "event_id": event_ids[0][1], "status": "scheduled", "created_at": now},
        ])
        await db.person_dedications.insert_many([
            {"dedication_id": f"d-{uuid.uuid4().hex}", "child_person_id": child_id, "mother_person_id": member_id, "event_id": event_ids[1][1], "status": "scheduled", "created_at": now},
            {"dedication_id": f"d-{uuid.uuid4().hex}", "child_person_id": other_child_id, "event_id": event_ids[1][1], "status": "scheduled", "created_at": now},
        ])

        # La lista de eventos (con los nombres de toda la iglesia) ya no está al alcance de un Miembro.
        for path in ("/api/baptism/events", f"/api/baptism/events/{event_ids[0][1]}", "/api/dedications/events", f"/api/dedications/events/{event_ids[1][1]}"):
            assert (await member.get(path)).status_code == 403, path
            assert (await pastora.get(path)).status_code == 200, path
        # Lo propio sí: su bautismo y la presentación de su hijo.
        assert (await member.get(f"/api/baptism/persons/{member_id}")).json()["exists"] is True
        assert (await member.get(f"/api/dedications/children/{child_id}")).json()["exists"] is True
        # Lo ajeno no: el bautismo de otra persona ni la presentación de otro niño.
        assert (await member.get(f"/api/baptism/persons/{other_id}")).status_code == 403
        assert (await member.get(f"/api/dedications/children/{other_child_id}")).status_code == 403
        assert (await member.get(f"/api/dedications/children/{other_child_id}/issuances")).status_code == 403
        # Reportes de Formación de toda la iglesia: solo la administración educativa.
        assert (await member.get("/api/formation/reports/pending")).status_code == 403
        assert (await pastora.get("/api/formation/reports/pending")).status_code == 200
    finally:
        for collection, event_id in event_ids:
            await collection.delete_one({"event_id": event_id})
        await db.person_baptisms.delete_many({"event_id": {"$in": [item[1] for item in event_ids]}})
        await db.person_dedications.delete_many({"event_id": {"$in": [item[1] for item in event_ids]}})
        await fx.cleanup()
