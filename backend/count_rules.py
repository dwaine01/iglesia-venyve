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


async def staff_and_team_person_ids() -> tuple[set, set]:
    """(cuentas del sistema/pastorales, líderes y mentores) por person_id, enlazados por la cuenta
    (users.person_id) o por la persona (persons.auth_user_id)."""
    from access_control import is_global_pastoral_authority
    users = await db.users.find({}, {"_id": 1, "person_id": 1, "rol": 1, "role": 1, "access_level": 1, "is_active": 1}).to_list(20000)
    by_user = {str(user["_id"]): user for user in users}
    staff, team = set(), set(await db.mentor_badges.distinct("person_id", {"active": True}))
    def classify(person_id, user):
        if is_global_pastoral_authority(user):
            staff.add(person_id)
        elif str(user.get("rol") or "").lower() == "lider" and user.get("is_active") is not False:
            team.add(person_id)
    for user in users:
        if user.get("person_id"):
            classify(user["person_id"], user)
    async for person in db.persons.find({"auth_user_id": {"$nin": [None, ""]}}, {"_id": 1, "auth_user_id": 1}):
        user = by_user.get(str(person["auth_user_id"]))
        if user:
            classify(str(person["_id"]), user)
    return staff, team


async def people_without_mentor(limit: int = 500) -> list[dict]:
    """«Personas sin líder» desde Persona 360 (auditoría 8/10): personas con un expediente de
    Consolidación abierto cuyo mentor falta o ya no tiene insignia activa, más las que quedaron sin
    líder en el Manual antiguo y todavía nadie acompaña. Baja sola en cuanto alguien recibe un mentor.
    No cuentan las archivadas, las de prueba ni la demostración antigua.
    Revisión de producción: tampoco las cuentas del sistema/pastorales (Pastor Admin…), ni los líderes y
    mentores cuyo único expediente es el migrado del Manual antiguo («Ley 7 Semanas»): solo cuentan si
    tienen un expediente de Consolidación propio, abierto de verdad."""
    from bson import ObjectId
    from enrollment_cleanup import representatives
    from report_period import excluded_person_ids
    excluded = await excluded_person_ids()
    staff, team = await staff_and_team_person_ids()
    active_mentors = set(await db.mentor_badges.distinct("person_id", {"active": True}))
    open_items, _ = representatives(await db.process_enrollments.find(
        {"process_key": "consolidation", "status": {"$in": CONSOLIDATION_OPEN}},
        {"_id": 0, "enrollment_id": 1, "person_id": 1, "process_key": 1, "mentor_person_id": 1, "status": 1, "progress_pct": 1, "updated_at": 1, "created_at": 1, "source": 1}).to_list(50000))
    accompanied = {item["person_id"] for item in open_items if item.get("mentor_person_id") in active_mentors}
    accompanied |= set(await db.mentor_assignments.distinct("person_id", {"active": True, "mentor_person_id": {"$in": list(active_mentors)}}))
    reasons: dict[str, str] = {}
    origins: dict[str, str] = {}
    for item in open_items:
        person_id = item["person_id"]
        if person_id in accompanied or person_id in staff:
            continue
        migrated = str(item.get("source") or "").startswith("legacy_")
        if migrated and person_id in team:
            continue  # líder o mentor con el expediente migrado del Manual antiguo: no está «sin líder»
        reasons[person_id] = "Su mentor ya no está activo" if item.get("mentor_person_id") else "En Consolidación sin mentor"
        origins[person_id] = "Expediente migrado del Manual antiguo" if migrated else "Expediente de Consolidación"
    async for doc in db.people.find({"leader_id": None, "previous_leader_id": {"$exists": True}, "demo": {"$ne": True}, "canonical_person_id": {"$nin": [None, ""]}},
                                    {"_id": 0, "canonical_person_id": 1}):
        person_id = doc["canonical_person_id"]
        if person_id not in accompanied and person_id not in staff and person_id not in team:
            reasons.setdefault(person_id, "Su líder fue eliminado")
            origins.setdefault(person_id, "Manual antiguo")
    candidates = [ObjectId(pid) for pid in reasons if pid not in excluded and ObjectId.is_valid(pid)]
    rows = [{"_id": str(doc["_id"]), "canonical_person_id": str(doc["_id"]), "nombre": " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) or "Persona",
             "motivo": reasons[str(doc["_id"])], "origen": origins.get(str(doc["_id"]))}
            async for doc in db.persons.find({"_id": {"$in": candidates}, "is_archived": {"$ne": True}, "is_test": {"$ne": True}}, {"nombre": 1, "apellido": 1})]
    rows.sort(key=lambda row: row["nombre"].lower())
    return rows[:limit]



# ------------------------------------------------------------------ una sola regla para «cuántas personas»
PERSON_COUNT_RULE = ("Personas activas de Persona 360: no cuenta las archivadas (incluidas las fusionadas como duplicado) "
                     "ni las marcadas de prueba o excluidas en «Datos de prueba».")


async def person_count_breakdown() -> dict:
    """La MISMA cifra para Panel General, Estadísticas Globales y Gobierno del Núcleo, con lo que excluye."""
    from report_period import SETTINGS_ID
    settings = await db.app_settings.find_one({"_id": SETTINGS_ID}, {"_id": 0, "person_ids": 1}) or {}
    from bson import ObjectId
    excluded_oids = [ObjectId(pid) for pid in settings.get("person_ids") or [] if ObjectId.is_valid(str(pid))]
    total = await db.persons.count_documents({})
    archived = await db.persons.count_documents({"is_archived": True})
    test = await db.persons.count_documents({"is_archived": {"$ne": True}, "is_test": True})
    excluded = await db.persons.count_documents({"_id": {"$in": excluded_oids}, "is_archived": {"$ne": True}, "is_test": {"$ne": True}}) if excluded_oids else 0
    return {"counted": total - archived - test - excluded, "registered": total, "archived": archived, "test": test, "excluded": excluded, "rule": PERSON_COUNT_RULE}
