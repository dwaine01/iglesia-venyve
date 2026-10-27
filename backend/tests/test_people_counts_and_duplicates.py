"""Revisión de producción · puntos 6 y 7: una sola regla para «cuántas personas» (Panel General,
Estadísticas Globales y Gobierno del Núcleo dicen lo mismo y qué excluyen); Datos de prueba detecta más
candidatas; el mismo teléfono con nombres distintos no sugiere fusionar y se puede marcar «No es duplicado»."""
import uuid
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


async def phone(person_id: str, number: str) -> None:
    await db.person_contacts.insert_one({"_id": str(uuid.uuid4()), "person_id": person_id, "tipo": "telefono", "valor": number, "valor_normalizado": number, "es_principal": True})


@pytest.mark.asyncio
async def test_same_count_everywhere_more_test_candidates_and_not_duplicate():
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    number = "614" + str(uuid.uuid4().int)[:7]
    try:
        pastora = await fx.account(await fx.person(f"PastoraC6{tag}"), "pastora")
        admin = await fx.person(f"Pastor Admin{tag}")
        await fx.account(admin, "admin")
        gerson, eddy = await fx.person(f"Gerson{tag} Marte"), await fx.person(f"Eddy{tag} Herrera")
        await phone(gerson, number); await phone(eddy, number)
        same_a, same_b = await fx.person(f"Luisa{tag} Peña"), await fx.person(f"Luisa{tag} Peña")
        await phone(same_a, number + "9"); await phone(same_b, number + "9")
        loose = await fx.person(f"Suelto{tag}")
        real = await fx.person(f"Real{tag}")
        await phone(real, number + "8")

        # 6) La misma cifra en las tres pantallas, con lo que excluye.
        panel = (await pastora.get("/api/dashboard/role-based")).json()
        core = (await pastora.get("/api/core/governance/integrity")).json()["counts"]
        stats = (await pastora.get("/api/global-stats/summary")).json()
        card = next(item for item in stats["cards"] if item["key"] == "persons_total")
        assert panel["total_personas_global"] == core["persons"] == card["value"] == panel["total_personas_desglose"]["counted"]
        assert "archivadas" in panel["total_personas_desglose"]["rule"] and "archivadas" in card["definition"]

        # Datos de prueba: nuevas candidatas (solo para revisar a mano).
        rows = {row["person_id"]: row["reasons"] for row in (await pastora.get("/api/test-data/inventory")).json()["people"]}
        assert any("Cuenta del sistema" in reason for reason in rows.get(admin, []))
        assert any("Mismo teléfono" in reason for reason in rows.get(gerson, [])) and any("Mismo teléfono" in reason for reason in rows.get(eddy, []))
        assert any("Registro suelto" in reason for reason in rows.get(loose, []))
        assert real not in rows

        # 7) Mismo teléfono con nombres distintos: no sugiere fusionar; «No es duplicado» se guarda y se deshace.
        groups = (await pastora.get("/api/person-merge/candidates")).json()["groups"]
        family = next(group for group in groups if {p["person_id"] for p in group["people"]} == {gerson, eddy})
        twins = next(group for group in groups if {p["person_id"] for p in group["people"]} == {same_a, same_b})
        assert family["suggest_merge"] is False and "nombres distintos" in family["reason"]
        assert twins["suggest_merge"] is True
        assert (await pastora.post("/api/person-merge/not-duplicate", json={"person_ids": [gerson, eddy], "reason": "Prueba del dueño, son dos personas"})).status_code == 200
        after = (await pastora.get("/api/person-merge/candidates")).json()
        assert not any({p["person_id"] for p in group["people"]} == {gerson, eddy} for group in after["groups"])
        assert any(row["signature"] == family["signature"] for row in after["dismissed"])
        assert (await pastora.post("/api/person-merge/not-duplicate/undo", json={"signature": family["signature"]})).status_code == 200
        again = (await pastora.get("/api/person-merge/candidates")).json()["groups"]
        assert any({p["person_id"] for p in group["people"]} == {gerson, eddy} for group in again)
        assert await db.persons.count_documents({"_id": {"$in": [ObjectId(gerson), ObjectId(eddy)]}}) == 2  # nada se borra
    finally:
        await db.person_contacts.delete_many({"person_id": {"$in": fx.person_ids}})
        await db.person_duplicate_dismissals.delete_many({"person_ids": {"$in": fx.person_ids}})
        await fx.cleanup()


@pytest.mark.asyncio
async def test_existing_person_proof_message_does_not_push_new_contact():
    from mentorship_outreach import require_existing_person_proof
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        await require_existing_person_proof({"_id": ObjectId(), "created_by": "otro"}, None, {"user_id": "x", "rol": "lider", "access_scope": {"persons": "created_by"}})
    assert "líder" in error.value.detail and "duplicaría" in error.value.detail
