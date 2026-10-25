"""Estadísticas Globales G1: permisos por sección (backend), Consolidación con
las MISMAS cifras del panorama, asistencia por tipo de servicio desde Persona
360 (domingo / miércoles / especial / células), la pastora no cuenta, nuevos
vs recurrentes, ausentes frecuentes y motivos cuando no hay datos."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_global_stats_permissions_consolidation_and_attendance():
    fx = Fixture()
    tag = uuid.uuid4().hex[:8]
    inserted = []
    try:
        pastora_id = await fx.person(f"Pastora{tag}")
        pastora = await fx.account(pastora_id, "pastora")
        mentor = await fx.account(await fx.person(f"Mentor{tag}"), "persona")
        lead = await fx.account(await fx.person(f"Encargada{tag}"), "persona", capabilities=["consolidation.assign"], permissions_mode="manual")
        ana, beto, caro = [await fx.person(f"{name}{tag}") for name in ("Ana", "Beto", "Caro")]
        # Permisos (backend): un mentor no ve nada; la encargada de Consolidación solo Consolidación.
        assert (await mentor.get("/api/global-stats/access")).status_code == 403
        for path in ("summary", "consolidation", "attendance"):
            assert (await mentor.get(f"/api/global-stats/{path}")).status_code == 403
        assert (await lead.get("/api/global-stats/consolidation")).status_code == 200
        assert (await lead.get("/api/global-stats/summary")).status_code == 403
        assert (await pastora.get("/api/global-stats/access")).json()["sections"] == {"summary": True, "consolidation": True, "attendance": True, "finance": True, "activities": True}

        # Consolidación: mismas cifras que el panorama del módulo.
        stats = (await pastora.get("/api/global-stats/consolidation", params={"period": "year"})).json()
        panorama = (await pastora.get("/api/consolidation/panorama", params={"period": "all"})).json()
        figures = {item["key"]: item["value"] for item in stats["cards"]}
        assert figures["total"] == panorama["figures"]["total"] and figures["active"] == panorama["figures"]["active"] and figures["unattended"] == panorama["figures"]["unattended"]
        assert stats["funnel"] == panorama["funnel"]

        # Asistencia en un rango propio: un domingo y un miércoles de servicio, una actividad especial y una célula.
        today = date.today()
        sunday = today - timedelta(days=(today.weekday() + 1) % 7 or 7) - timedelta(weeks=1)
        wednesday = sunday + timedelta(days=3)
        saturday = sunday + timedelta(days=6)
        event_service, event_special = f"ev-{tag}", f"ev2-{tag}"
        await db.operation_events.insert_many([{"_id": event_service, "event_id": event_service, "title": f"Servicio {tag}", "event_type": "service"},
                                               {"_id": event_special, "event_id": event_special, "title": f"Conferencia {tag}", "event_type": "conference"}])
        occurrences = {"sun": (event_service, sunday), "wed": (event_service, wednesday), "sat": (event_special, saturday), "sun2": (event_service, sunday - timedelta(weeks=1))}
        for key, (event_id, day) in occurrences.items():
            starts = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=16)  # mediodía en Nueva York
            await db.operation_event_occurrences.insert_one({"_id": f"oc-{key}-{tag}", "occurrence_id": f"oc-{key}-{tag}", "event_id": event_id, "starts_at": starts})

        async def present(person_id, key, day, kind="operation"):
            doc_id = f"operation:{tag}-{key}-{person_id}" if kind == "operation" else f"cell:{tag}-{key}:{person_id}"
            doc = {"_id": doc_id, "person_id": person_id, "fecha": f"{day.isoformat()}T17:00:00+00:00" if kind == "operation" else day.isoformat(), "estado": "presente", "actividad": "x"}
            doc.update({"notas": f"Operaciones · oc-{key}-{tag}"} if kind == "operation" else {"activity_type": "cell_meeting", "source_id": f"meet-{tag}"})
            await db.person_attendance.insert_one(doc)
            inserted.append(doc_id)
        for person in (ana, beto, pastora_id):  # la pastora no cuenta
            await present(person, "sun", sunday)
        await present(ana, "wed", wednesday)
        await present(caro, "sat", saturday)
        await present(beto, "cell", wednesday, kind="cell")
        params = {"period": "custom", "date_from": sunday.isoformat(), "date_to": saturday.isoformat()}
        data = (await pastora.get("/api/global-stats/attendance", params=params)).json()
        by = {item["kind"]: item for item in data["by_service"]}
        assert (by["sunday"]["sessions"], by["sunday"]["attendance"], by["sunday"]["average"]) == (1, 2, 2.0)
        assert (by["wednesday"]["attendance"], by["special"]["attendance"], by["cell"]["attendance"]) == (1, 1, 1)
        cards = {item["key"]: item for item in data["cards"]}
        assert cards["unique_people"]["value"] == 3 and cards["service_average"]["value"] == 1.5  # (2 + 1) ÷ 2 servicios
        assert cards["newcomers"]["value"] == 3 and cards["returning"]["value"] == 0
        assert all(item["definition"] and item["source"] for item in data["cards"])
        # Ausentes frecuentes: Ana vino 3 veces antes y nada en las últimas 3 semanas del período siguiente.
        later = saturday + timedelta(weeks=4)
        late = (await pastora.get("/api/global-stats/attendance", params={"period": "custom", "date_from": (later - timedelta(days=6)).isoformat(), "date_to": later.isoformat()})).json()
        assert any(item["person_id"] == ana for item in late["frequent_absent"]) is False  # solo 2 asistencias (domingo + miércoles)
        await present(ana, "sun2", sunday - timedelta(weeks=1))
        late = (await pastora.get("/api/global-stats/attendance", params={"period": "custom", "date_from": (later - timedelta(days=6)).isoformat(), "date_to": later.isoformat()})).json()
        assert any(item["person_id"] == ana and item["previous_attendance"] == 3 for item in late["frequent_absent"])
        # Sin datos: el motivo, no un cero engañoso.
        empty = (await pastora.get("/api/global-stats/attendance", params={"period": "custom", "date_from": "2001-01-01", "date_to": "2001-01-07"})).json()
        assert {item["key"]: item for item in empty["cards"]}["service_average"]["empty_reason"]

        summary = (await pastora.get("/api/global-stats/summary", params=params)).json()
        keys = {item["key"]: item for item in summary["cards"]}
        assert keys["active_people"]["value"] == 3 and keys["service_average"]["value"] == 1.5 and summary["finance_available"] is True and "received" in keys
        assert (await pastora.get("/api/global-stats/summary", params={"period": "custom", "date_from": "2026-02-01", "date_to": "2026-01-01"})).status_code == 422
    finally:
        await db.person_attendance.delete_many({"_id": {"$in": inserted}})
        await db.operation_events.delete_many({"event_id": {"$regex": tag}})
        await db.operation_event_occurrences.delete_many({"occurrence_id": {"$regex": tag}})
        await fx.cleanup()
