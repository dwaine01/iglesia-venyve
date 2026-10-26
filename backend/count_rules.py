"""Una definición por número (auditoría 7/10).

Antes cada pantalla contaba a su manera: «Personas en Consolidación» incluía a los retirados,
el Panel General contaba expedientes repetidos de la misma persona, «Mis estadísticas» y
«Supervisar Mi Trabajo» daban cifras distintas para el mismo mentor y algunas fechas se
tomaban en UTC. Aquí vive la regla única; las pantallas la importan.

- En Consolidación (por mentor, «ahora»): personas únicas con expediente abierto
  (planificado, activo o en pausa). Las cuentas de prueba y la autoridad principal no cuentan.
- Personas en Consolidación (total): personas únicas con expediente abierto o terminado;
  los retirados/cancelados se muestran aparte y los archivados (historial) no cuentan.
- «Hoy», «esta semana», «vencida»: siempre en la zona de la iglesia (Nueva York si no hay otra).
"""
from datetime import date, datetime, time, timezone

from server import db

CONSOLIDATION_OPEN = ["planned", "active", "paused"]
CONSOLIDATION_COUNTED = CONSOLIDATION_OPEN + ["completed"]


async def church_today() -> date:
    from report_period import report_zone
    return datetime.now(await report_zone()).date()


async def church_day_start_utc(day: date | None = None) -> datetime:
    """Medianoche local de `day` (hoy si falta), en UTC, para filtrar fechas guardadas en UTC."""
    from report_period import report_zone
    zone = await report_zone()
    day = day or datetime.now(zone).date()
    return datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc)


async def open_consolidation_by_mentor(mentor_ids: list[str]) -> dict[str, int]:
    """{mentor: personas únicas en Consolidación ahora}. Una persona con dos expedientes
    abiertos cuenta una vez, para el mentor de su expediente principal."""
    from enrollment_cleanup import representatives
    from report_period import excluded_person_ids
    if not mentor_ids:
        return {}
    excluded = await excluded_person_ids()
    items = await db.process_enrollments.find(
        {"mentor_person_id": {"$in": mentor_ids}, "process_key": "consolidation", "status": {"$in": CONSOLIDATION_OPEN}, "person_id": {"$nin": list(excluded)}},
        {"_id": 0, "enrollment_id": 1, "person_id": 1, "process_key": 1, "mentor_person_id": 1, "status": 1, "progress_pct": 1, "updated_at": 1, "created_at": 1},
    ).to_list(50000)
    counts = {pid: 0 for pid in mentor_ids}
    for item in representatives(items)[0]:
        counts[item["mentor_person_id"]] = counts.get(item["mentor_person_id"], 0) + 1
    return counts
