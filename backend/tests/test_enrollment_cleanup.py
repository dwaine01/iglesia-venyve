"""Limpieza de expedientes duplicados: diagnóstico solo lectura, Panorama y
listados por PERSONAS ÚNICAS, archivar por lote (confirmación escrita,
auditoría, reversible), solo la autoridad pastoral, y el índice que impide
dos expedientes activos de la misma persona y proceso."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pymongo.errors import DuplicateKeyError

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


def enrollment(person_id, status, mentor_id, tag, minutes=0, **extra):
    now = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    eid = f"dup-{tag}-{uuid.uuid4().hex[:10]}"
    return {"_id": eid, "enrollment_id": eid, "process_key": "consolidation", "definition_version": 2, "person_id": person_id, "cycle_id": None,
            "status": status, "current_stage_key": "visitor_followup", "progress_pct": 0, "mentor_person_id": mentor_id, "created_at": now, "updated_at": now,
            "source": f"test-{tag}", **extra}


@pytest.mark.asyncio
async def test_duplicate_cleanup_diagnostic_archive_restore_and_unique_counts():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    try:
        pastora = await fx.account(await fx.person(f"Pastora{tag}"), "pastora")
        rosa = await fx.person(f"Rosa{tag}")
        other = await fx.person(f"Otra{tag}")
        mentor = await fx.person(f"Josue{tag}")
        mentor_client = await fx.account(mentor, "persona")
        # Rosa: 1 activo + 98 completados al 0 % sin actividad (restos de pruebas) + 1 completado con avance (se conserva).
        docs = [enrollment(rosa, "active", mentor, tag, consolidation_status="followup_pending")]
        docs += [enrollment(rosa, "completed", mentor, tag, minutes=index + 1) for index in range(98)]
        real = enrollment(rosa, "completed", mentor, tag, minutes=500, progress_pct=40, current_stage_key="mcd")
        with_activity = enrollment(rosa, "completed", mentor, tag, minutes=600)
        docs += [real, with_activity]
        docs.append(enrollment(other, "active", mentor, tag))
        await db.process_enrollments.insert_many(docs)
        await db.consolidation_activities.insert_one({"_id": f"act-{tag}", "enrollment_id": with_activity["enrollment_id"], "status": "done", "completed_at": datetime.now(timezone.utc)})

        # Prevención: no se puede crear un segundo expediente ACTIVO de la misma persona y proceso.
        with pytest.raises(DuplicateKeyError):
            await db.process_enrollments.insert_one(enrollment(rosa, "active", mentor, tag))

        # Diagnóstico (solo lectura): 101 expedientes de Rosa, 98 candidatos con su razón.
        before = await db.process_enrollments.count_documents({"source": f"test-{tag}"})
        diag = (await pastora.get("/api/processes/cleanup/diagnostic", params={"limit": 1000})).json()
        mine = [row for row in diag["candidates"] if row["person_id"] == rosa]
        rosa_row = next(row for row in diag["people"] if row["person_id"] == rosa)
        assert rosa_row["total"] == 101 and rosa_row["open"] == 1 and rosa_row["candidates"] == 98 and rosa_row["by_status"] == {"active": 1, "completed": 100}
        assert len(mine) == 98 and all("0 % de avance, primera etapa" in row["reasons"] for row in mine)
        assert real["enrollment_id"] not in {row["enrollment_id"] for row in mine} and with_activity["enrollment_id"] not in {row["enrollment_id"] for row in mine}
        assert not [row for row in diag["candidates"] if row["person_id"] == other]
        assert diag["unique_active_index"] is True
        assert await db.process_enrollments.count_documents({"source": f"test-{tag}"}) == before  # no cambió nada
        assert (await mentor_client.get("/api/processes/cleanup/diagnostic")).status_code == 403

        # Panorama y listado: personas únicas, no expedientes.
        panorama = (await pastora.get("/api/consolidation/panorama", params={"period": "all", "mentor_person_id": mentor})).json()
        assert panorama["figures"]["total"] == 2 and panorama["figures"]["active"] == 2
        listed = (await pastora.get("/api/processes/enrollments", params={"process_key": "consolidation", "unique_person": "true"})).json()["items"]
        rosa_cards = [item for item in listed if item["person_id"] == rosa]
        assert len(rosa_cards) == 1 and rosa_cards[0]["status"] == "active" and rosa_cards[0]["history_count"] == 100

        # Archivar por lote: exige confirmación escrita exacta; no borra; auditoría; reversible.
        ids = [row["enrollment_id"] for row in mine] + [real["enrollment_id"]]  # el de avance real se rechaza
        assert (await pastora.post("/api/processes/cleanup/archive", json={"enrollment_ids": ids, "confirm_text": "si"})).status_code == 422
        assert (await mentor_client.post("/api/processes/cleanup/archive", json={"enrollment_ids": ids, "confirm_text": f"ARCHIVAR {len(ids)}"})).status_code == 403
        result = (await pastora.post("/api/processes/cleanup/archive", json={"enrollment_ids": ids, "confirm_text": f"archivar {len(ids)}", "note": "Restos de QA"})).json()
        assert result["archived"] == 98 and result["skipped"] == [real["enrollment_id"]]
        assert await db.process_enrollments.count_documents({"source": f"test-{tag}"}) == before  # nada borrado
        assert await db.process_enrollments.count_documents({"source": f"test-{tag}", "status": "archived", "archived_previous_status": "completed"}) == 98
        assert await db.process_timeline.count_documents({"event_type": "archived_duplicate", "detail": {"$regex": result["batch_id"]}}) == 98
        batch = await db.process_cleanup_batches.find_one({"batch_id": result["batch_id"]})
        assert len(batch["items"]) == 98 and batch["note"] == "Restos de QA" and all(item["reasons"] for item in batch["items"])
        # Archivados fuera de los listados y del diagnóstico.
        listed_all = (await pastora.get("/api/processes/enrollments", params={"process_key": "consolidation"})).json()["items"]
        assert sum(1 for item in listed_all if item["person_id"] == rosa) == 3
        assert not [row for row in (await pastora.get("/api/processes/cleanup/diagnostic", params={"limit": 1000})).json()["candidates"] if row["person_id"] == rosa]
        assert (await pastora.get("/api/processes/cleanup/batches")).json()["items"][0]["count"] == 98

        # Reversible.
        assert (await pastora.post("/api/processes/cleanup/restore", json={"batch_id": result["batch_id"], "confirm_text": "no"})).status_code == 422
        restored = (await pastora.post("/api/processes/cleanup/restore", json={"batch_id": result["batch_id"], "confirm_text": "RESTAURAR"})).json()
        assert restored["restored"] == 98 and restored["conflicts"] == []
        assert await db.process_enrollments.count_documents({"source": f"test-{tag}", "status": "archived"}) == 0
        assert await db.process_enrollments.count_documents({"source": f"test-{tag}", "person_id": rosa, "status": "completed"}) == 100
    finally:
        await db.process_enrollments.delete_many({"source": f"test-{tag}"})
        await db.process_timeline.delete_many({"enrollment_id": {"$regex": f"^dup-{tag}"}})
        await db.consolidation_activities.delete_many({"_id": f"act-{tag}"})
        await db.process_cleanup_batches.delete_many({"items.enrollment_id": {"$regex": f"^dup-{tag}"}})
        await fx.cleanup()
