"""Limpieza de expedientes duplicados (Consolidación y demás procesos).

Hallazgo en producción: la misma Persona con ~100 expedientes completados al
0 % (restos de pruebas repetidas) inflaba listados y cifras.

- Diagnóstico SOLO LECTURA (`GET /diagnostic`): cuántos expedientes hay por
  persona y proceso, cuáles son duplicados claros de prueba y por qué.
- Archivar por lote (`POST /archive`): NO borra. Pasa a `status=archived`
  guardando el estado anterior, con confirmación escrita, auditoría en
  `process_cleanup_batches` + la línea de tiempo del expediente, y es
  reversible (`POST /restore`). El borrado definitivo lo decide el dueño.
- Solo la autoridad pastoral (backend).

Un expediente es CANDIDATO solo si cumple TODO:
1. Otra inscripción de la misma persona en el mismo proceso es la principal
   (la activa; si no hay, la de más avance o actividad; si empatan, la más
   reciente) y este no es la principal.
2. No está activo/planificado/en pausa (los activos ya los impide el índice
   único `unique_active_process_enrollment`).
3. 0 % de avance y en la primera etapa.
4. Sin actividades realizadas, sin evidencias, sin retiro ni proceso iniciado.
Que el mentor sea una cuenta de prueba se informa como dato, no se exige."""
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import is_global_pastoral_authority
from server import db, get_current_user

router = APIRouter(prefix="/api/processes/cleanup", tags=["process-cleanup"])

OPEN_STATUSES = {"planned", "active", "paused"}
FIRST_STAGES = {None, "", "visitor_followup", "intake", "new"}
TEST_EMAIL = re.compile(r"(@example\.(com|org)$|e2e|\bqa\b|qa\.|test|fixture|prueba)", re.IGNORECASE)
STATUS_LABELS = {"completed": "Completado", "closed": "Cerrado", "cancelled": "Cancelado", "archived": "Archivado", "active": "Activo", "paused": "En pausa", "planned": "Planificado"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def require_authority(current_user: dict) -> None:
    if not is_global_pastoral_authority(current_user):
        raise HTTPException(status_code=403, detail="Solo la autoridad pastoral usa la limpieza de expedientes")


def _ts(value) -> float:
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).timestamp()
    return 0.0


def _iso(value) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else value


def representatives(items: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Un expediente por (persona, proceso): el abierto; si no hay, el de más
    avance y más reciente. Devuelve también cuántos más tiene cada uno
    (historial) para mostrarlo sin inflar las cifras."""
    groups: dict[tuple, list] = defaultdict(list)
    for item in items:
        groups[(item.get("person_id"), item.get("process_key"))].append(item)
    chosen, extra = [], {}
    for rows in groups.values():
        best = max(rows, key=lambda row: (row.get("status") in OPEN_STATUSES, row.get("progress_pct") or 0, _ts(row.get("updated_at") or row.get("created_at"))))
        chosen.append(best)
        extra[best["enrollment_id"]] = len(rows) - 1
    return chosen, extra


async def _test_people(person_ids: set) -> dict[str, str]:
    """Mentores que parecen cuentas de prueba (dato informativo)."""
    if not person_ids:
        return {}
    flagged = {}
    async for user in db.users.find({"person_id": {"$in": list(person_ids)}}, {"_id": 0, "person_id": 1, "email": 1, "nombre": 1}):
        if TEST_EMAIL.search(user.get("email") or "") or TEST_EMAIL.search(user.get("nombre") or ""):
            flagged[user["person_id"]] = user.get("nombre") or user.get("email")
    return flagged


async def analyze(process_key: Optional[str] = None) -> dict:
    """Agrupa por (persona, proceso) y marca candidatos con su razón."""
    query: dict = {"status": {"$ne": "archived"}}
    if process_key:
        query["process_key"] = process_key
    keys = {"_id": 0, "enrollment_id": 1, "process_key": 1, "person_id": 1, "status": 1, "progress_pct": 1, "current_stage_key": 1, "mentor_person_id": 1,
            "created_at": 1, "updated_at": 1, "retreat_completed_at": 1, "process_started_at": 1, "entry_mode": 1, "definition_version": 1, "source": 1, "cycle_id": 1}
    items = await db.process_enrollments.find(query, keys).to_list(200000)
    groups: dict[tuple, list] = defaultdict(list)
    for item in items:
        groups[(item.get("person_id"), item.get("process_key"))].append(item)
    multi = {key: rows for key, rows in groups.items() if len(rows) > 1}
    ids = [row["enrollment_id"] for rows in multi.values() for row in rows]
    done = {}
    evidence = set()
    if ids:
        async for row in db.consolidation_activities.aggregate([{"$match": {"enrollment_id": {"$in": ids}, "status": "done"}}, {"$group": {"_id": "$enrollment_id", "n": {"$sum": 1}}}]):
            done[row["_id"]] = row["n"]
        evidence = set(await db.process_evidence.distinct("enrollment_id", {"enrollment_id": {"$in": ids}}))
    mentors = await _test_people({row.get("mentor_person_id") for rows in multi.values() for row in rows if row.get("mentor_person_id")})

    def weight(row: dict) -> tuple:
        return (row.get("status") in OPEN_STATUSES, done.get(row["enrollment_id"], 0) > 0 or row["enrollment_id"] in evidence, row.get("progress_pct") or 0, _ts(row.get("updated_at") or row.get("created_at")))

    candidates, open_duplicates, people = [], [], []
    for (person_id, key), rows in multi.items():
        primary = max(rows, key=weight)
        open_rows = [row for row in rows if row.get("status") in OPEN_STATUSES]
        if len(open_rows) > 1:
            open_duplicates.append({"person_id": person_id, "process_key": key, "enrollment_ids": [row["enrollment_id"] for row in open_rows]})
        found = 0
        for row in rows:
            if row is primary:
                continue
            blockers = []
            if row.get("status") in OPEN_STATUSES:
                blockers.append("está abierto")
            if row.get("progress_pct"):
                blockers.append(f"{row['progress_pct']} % de avance")
            if row.get("current_stage_key") not in FIRST_STAGES:
                blockers.append("pasó de la primera etapa")
            if done.get(row["enrollment_id"]):
                blockers.append("tiene actividades realizadas")
            if row["enrollment_id"] in evidence:
                blockers.append("tiene evidencias")
            if row.get("retreat_completed_at") or row.get("process_started_at"):
                blockers.append("tiene hitos (retiro o proceso iniciado)")
            if blockers:
                continue
            reasons = [f"Misma persona y proceso que el expediente principal ({STATUS_LABELS.get(primary.get('status'), primary.get('status'))})",
                       f"Estado {STATUS_LABELS.get(row.get('status'), row.get('status'))}", "0 % de avance, primera etapa", "Sin actividades ni evidencias"]
            if row.get("mentor_person_id") in mentors:
                reasons.append(f"Mentor de prueba: {mentors[row['mentor_person_id']]}")
            candidates.append({"enrollment_id": row["enrollment_id"], "person_id": person_id, "process_key": key, "status": row.get("status"),
                               "stage_key": row.get("current_stage_key"), "mentor_person_id": row.get("mentor_person_id"), "test_mentor": row.get("mentor_person_id") in mentors,
                               "created_at": _iso(row.get("created_at")), "primary_enrollment_id": primary["enrollment_id"], "reasons": reasons})
            found += 1
        people.append({"person_id": person_id, "process_key": key, "total": len(rows), "open": len(open_rows), "candidates": found, "primary_enrollment_id": primary["enrollment_id"],
                       "by_status": dict(sorted(((status, sum(1 for row in rows if row.get("status") == status)) for status in {row.get("status") for row in rows}), key=lambda pair: str(pair[0])))})
    people.sort(key=lambda row: -row["total"])
    by_process: dict[str, dict] = defaultdict(lambda: {"enrollments": 0, "people": 0})
    for (person_id, key), rows in groups.items():
        by_process[key]["enrollments"] += len(rows)
        by_process[key]["people"] += 1
    return {"enrollments": len(items), "people_processes": len(groups), "with_duplicates": len(multi), "by_process": dict(by_process),
            "people": people, "candidates": candidates, "open_duplicates": open_duplicates}


async def _names(person_ids: set) -> dict:
    from mentorship_outreach import person_display_name
    return {pid: await person_display_name(pid) for pid in person_ids if pid}


@router.get("/diagnostic", response_model=dict)
async def diagnostic(process_key: Optional[str] = "consolidation", limit: int = 200, current_user: dict = Depends(get_current_user)):
    """Solo lectura: no cambia nada."""
    require_authority(current_user)
    data = await analyze(process_key or None)
    limit = max(1, min(limit, 1000))
    shown_people = data["people"][:50]
    shown = data["candidates"][:limit]
    names = await _names({row["person_id"] for row in shown_people} | {row["person_id"] for row in shown} | {row["mentor_person_id"] for row in shown if row.get("mentor_person_id")})
    for row in shown_people:
        row["name"] = names.get(row["person_id"]) or "Persona"
    for row in shown:
        row["name"] = names.get(row["person_id"]) or "Persona"
        row["mentor_name"] = names.get(row.get("mentor_person_id"))
    indexes = await db.process_enrollments.index_information()
    return {"process_key": process_key, "enrollments": data["enrollments"], "people_processes": data["people_processes"], "with_duplicates": data["with_duplicates"],
            "by_process": data["by_process"], "candidates_total": len(data["candidates"]), "candidates": shown, "people": shown_people,
            "open_duplicates": data["open_duplicates"], "unique_active_index": "unique_active_process_enrollment" in indexes}


class ArchiveInput(BaseModel):
    enrollment_ids: list[str] = Field(min_length=1, max_length=2000)
    confirm_text: str = Field(min_length=1, max_length=40)
    note: Optional[str] = Field(default=None, max_length=500)


class RestoreInput(BaseModel):
    batch_id: str = Field(min_length=1, max_length=80)
    confirm_text: str = Field(min_length=1, max_length=40)


@router.post("/archive", response_model=dict)
async def archive(payload: ArchiveInput, current_user: dict = Depends(get_current_user)):
    """Archiva (no borra) los candidatos elegidos. Confirmación escrita:
    «ARCHIVAR <cantidad>». Se vuelve a verificar que sigan siendo candidatos."""
    require_authority(current_user)
    requested = list(dict.fromkeys(payload.enrollment_ids))
    if payload.confirm_text.strip().upper() != f"ARCHIVAR {len(requested)}":
        raise HTTPException(status_code=422, detail=f"Escriba «ARCHIVAR {len(requested)}» para confirmar")
    candidates = {row["enrollment_id"]: row for row in (await analyze())["candidates"]}
    valid = [item for item in requested if item in candidates]
    skipped = [item for item in requested if item not in candidates]
    batch_id = str(uuid4())
    now = now_utc()
    archived = []
    for enrollment_id in valid:
        current = await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0, "status": 1, "person_id": 1, "process_key": 1})
        result = await db.process_enrollments.update_one({"enrollment_id": enrollment_id, "status": current["status"]}, {"$set": {
            "status": "archived", "archived_previous_status": current["status"], "archived_at": now, "archived_by_user_id": current_user["user_id"],
            "archive_batch_id": batch_id, "archive_reason": "duplicate_cleanup", "updated_at": now}})
        if result.modified_count:
            archived.append({"enrollment_id": enrollment_id, "previous_status": current["status"], "person_id": current.get("person_id"), "process_key": current.get("process_key"),
                             "reasons": candidates[enrollment_id]["reasons"]})
            await db.process_timeline.insert_one({"_id": str(uuid4()), "enrollment_id": enrollment_id, "person_id": current.get("person_id"), "process_key": current.get("process_key"),
                                                  "event_type": "archived_duplicate", "title": "Expediente archivado (duplicado)", "detail": f"Lote {batch_id}. Reversible.",
                                                  "actor_user_id": current_user["user_id"], "occurred_at": now})
    await db.process_cleanup_batches.insert_one({"_id": batch_id, "batch_id": batch_id, "action": "archive", "items": archived, "skipped": skipped, "note": (payload.note or "").strip() or None,
                                                 "actor_user_id": current_user["user_id"], "actor_name": current_user.get("nombre"), "created_at": now, "restored_at": None})
    return {"batch_id": batch_id, "archived": len(archived), "skipped": skipped}


@router.post("/restore", response_model=dict)
async def restore(payload: RestoreInput, current_user: dict = Depends(get_current_user)):
    """Deshace un lote: cada expediente vuelve a su estado anterior."""
    require_authority(current_user)
    if payload.confirm_text.strip().upper() != "RESTAURAR":
        raise HTTPException(status_code=422, detail="Escriba «RESTAURAR» para confirmar")
    batch = await db.process_cleanup_batches.find_one({"batch_id": payload.batch_id, "action": "archive"})
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    now = now_utc()
    restored, conflicts = 0, []
    for item in batch.get("items") or []:
        try:
            result = await db.process_enrollments.update_one({"enrollment_id": item["enrollment_id"], "status": "archived", "archive_batch_id": payload.batch_id},
                                                             {"$set": {"status": item["previous_status"], "restored_at": now, "updated_at": now},
                                                              "$unset": {"archived_previous_status": "", "archived_at": "", "archived_by_user_id": "", "archive_batch_id": "", "archive_reason": ""}})
            restored += result.modified_count
        except Exception:  # noqa: BLE001 — p. ej. ya hay otro expediente activo (índice único)
            conflicts.append(item["enrollment_id"])
            continue
        if result.modified_count:
            await db.process_timeline.insert_one({"_id": str(uuid4()), "enrollment_id": item["enrollment_id"], "person_id": item.get("person_id"), "process_key": item.get("process_key"),
                                                  "event_type": "restored_from_archive", "title": "Expediente restaurado", "detail": f"Lote {payload.batch_id}.",
                                                  "actor_user_id": current_user["user_id"], "occurred_at": now})
    await db.process_cleanup_batches.update_one({"batch_id": payload.batch_id}, {"$set": {"restored_at": now, "restored_by_user_id": current_user["user_id"], "restore_conflicts": conflicts}})
    return {"batch_id": payload.batch_id, "restored": restored, "conflicts": conflicts}


@router.get("/batches", response_model=dict)
async def batches(current_user: dict = Depends(get_current_user)):
    require_authority(current_user)
    rows = await db.process_cleanup_batches.find({}, {"_id": 0, "items": 0}).sort("created_at", -1).limit(50).to_list(50)
    counts = {doc["_id"]: doc["n"] async for doc in db.process_cleanup_batches.aggregate([{"$project": {"n": {"$size": {"$ifNull": ["$items", []]}}}}])}
    return {"items": [{**{key: _iso(value) for key, value in row.items()}, "count": counts.get(row["batch_id"], 0)} for row in rows]}


async def ensure_indexes() -> None:
    await db.process_cleanup_batches.create_index([("created_at", -1)])
    await db.process_enrollments.create_index("archive_batch_id", sparse=True)
