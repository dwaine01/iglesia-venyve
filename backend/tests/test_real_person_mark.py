"""«Es persona real»: solo el pastor, reversible y con historial; el servidor no deja marcarla «prueba».
La protección contra el borrado del Perfil 360 incluye a las cuentas «pastora» y de nivel Pastor."""
import uuid

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_real_person_mark_blocks_is_test_and_is_reversible():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    try:
        pastora = await fx.account(await fx.person(f"PastoraR{tag}"), "pastora")
        coordinator = await fx.account(await fx.person(f"CoordR{tag}"), "lider", access_level="coordinador_general")
        real = await fx.person(f"Prueba Real {tag}")  # el nombre la vuelve candidata en Datos de prueba
        assert real in {row["person_id"] for row in (await pastora.get("/api/test-data/inventory")).json()["people"]}

        payload = {"person_id": real, "confirmed": True, "reason": "Es la pastora general"}
        assert (await coordinator.post("/api/test-data/real-person", json=payload)).status_code == 403  # solo el pastor
        confirmed = await pastora.post("/api/test-data/real-person", json=payload)
        assert confirmed.status_code == 200, confirmed.text
        body = confirmed.json()
        assert real not in {row["person_id"] for row in body["people"]}
        assert real in {row["person_id"] for row in body["confirmed_real"]}

        # El servidor no deja marcarla «prueba» (todo o nada, aunque vaya junto a otra).
        other = await fx.person(f"Prueba Otra {tag}")
        blocked = await pastora.post("/api/test-data/mark", json={"kind": "person", "ids": [other, real], "is_test": True, "reason": "QA prueba"})
        assert blocked.status_code == 409
        assert not await db.persons.count_documents({"_id": {"$in": [ObjectId(other), ObjectId(real)]}, "is_test": True})
        assert (await coordinator.post("/api/test-data/mark", json={"kind": "person", "ids": [real], "is_test": True, "reason": "QA prueba"})).status_code == 409

        # Reversible y con historial: al quitar la marca vuelve a la lista de candidatas y se puede marcar.
        undone = await pastora.post("/api/test-data/real-person", json={"person_id": real, "confirmed": False, "reason": "Deshacer QA"})
        assert undone.status_code == 200 and real in {row["person_id"] for row in undone.json()["people"]}
        assert (await pastora.post("/api/test-data/mark", json={"kind": "person", "ids": [real], "is_test": True, "reason": "QA prueba"})).status_code == 200
        assert [row["after"] for row in await db.test_data_marks.find({"target_id": real, "field": "confirmed_real"}).sort("at", 1).to_list(10)] == [True, False]
        # Marcada «prueba» no se puede confirmar como real hasta quitar esa marca.
        assert (await pastora.post("/api/test-data/real-person", json=payload)).status_code == 409
    finally:
        await db.test_data_marks.delete_many({"reason": {"$in": ["Es la pastora general", "Deshacer QA", "QA prueba"]}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_pastora_profile_cannot_be_deleted_by_another_pastor():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    try:
        pastor = await fx.account(await fx.person(f"PastorD{tag}"), "pastor")
        pastora_person = await fx.person(f"PastoraD{tag}")
        await fx.account(pastora_person, "pastora")
        level_person = await fx.person(f"NivelD{tag}")
        await fx.account(level_person, "lider", access_level="pastor")
        for person_id in (pastora_person, level_person):
            response = await pastor.delete(f"/api/core/persons/{person_id}")
            assert response.status_code == 409, response.text
            assert "cuenta pastoral" in response.json()["detail"]
    finally:
        await fx.cleanup()
