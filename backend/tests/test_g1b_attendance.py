"""G1b: asistencia por semana, mes y año (calendario de Nueva York) y, en el Perfil 360, cuántas veces
asistió la persona en el año. Permisos en el servidor."""
import uuid
from datetime import timedelta

import pytest

from tests.test_pastoral_front_group_5c import Fixture, server  # noqa: I001 — server primero

db = server.db


@pytest.mark.asyncio
async def test_series_and_year_summary():
    from count_rules import church_today
    fx, tag = Fixture(), uuid.uuid4().hex[:8]
    inserted = []
    try:
        pastora = await fx.account(await fx.person(f"PastoraG{tag}"), "pastora")
        member_id = await fx.person(f"MiembroG{tag}")
        member = await fx.account(member_id, "persona")
        other = await fx.account(await fx.person(f"OtroG{tag}"), "persona")
        today = await church_today()
        before = {group: (await pastora.get("/api/global-stats/attendance/series", params={"group": group})).json() for group in ("week", "month", "year")}
        assert len(before["week"]["points"]) == 12 and len(before["month"]["points"]) == 12 and len(before["year"]["points"]) == 3
        assert before["year"]["points"][-1]["label"] == str(today.year) and before["week"]["points"][-1]["from"] <= today.isoformat()

        # Tres asistencias este año: hoy (dos registros del mismo servicio = 1) y otra hace unos días si cae en el año.
        days = [today, today] + ([today - timedelta(days=3)] if (today - timedelta(days=3)).year == today.year else [])
        for index, day in enumerate(days):
            doc_id = f"manual-g1b-{tag}-{index}"
            await db.person_attendance.insert_one({"_id": doc_id, "person_id": member_id, "fecha": day.isoformat(), "estado": "presente", "actividad": f"Servicio {tag}"})
            inserted.append(doc_id)
        expected = len({day for day in days})

        summary = (await member.get(f"/api/core/persons/{member_id}/attendance-summary")).json()  # la propia persona
        assert summary["year"] == today.year and summary["total"] == expected and summary["last_day"] == today.isoformat()
        assert sum(row["count"] for row in summary["by_month"]) == expected
        assert (await other.get(f"/api/core/persons/{member_id}/attendance-summary")).status_code == 403
        assert (await pastora.get(f"/api/core/persons/{member_id}/attendance-summary")).json()["total"] == expected

        after = (await pastora.get("/api/global-stats/attendance/series", params={"group": "year"})).json()
        assert after["points"][-1]["total"] - before["year"]["points"][-1]["total"] == expected
        assert (await member.get("/api/global-stats/attendance/series")).status_code == 403
    finally:
        await db.person_attendance.delete_many({"_id": {"$in": inserted}})
        await fx.cleanup()
