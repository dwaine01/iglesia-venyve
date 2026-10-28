"""R2 · Graduación de Consolidación (decisión del dueño): es un ACTO APARTE, después del Retiro.

- Cerrar el Retiro deja el expediente «Retiro hecho, pendiente de graduación» (sigue abierto).
- La iglesia crea un evento de graduación con su fecha; varias personas se gradúan en el mismo evento.
- Solo al registrar la graduación en ese evento se completa la Consolidación y se abre el traspaso a
  Discipulado de Formación. El traspaso se cumple cuando la persona queda inscrita en una cohorte de un
  programa de Formación con propósito «discipulado».
- Nada se borra: una graduación registrada por error se revierte (queda en el historial).
- Los expedientes que cerraron el Retiro ANTES de este cambio no se tocan: solo se cuentan (solo lectura)
  para la propuesta al dueño."""
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import uuid4

from pymongo.errors import DuplicateKeyError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from access_control import CONSOLIDATION_RETREAT_CLOSE, PROCESSES_READ, has_capability, is_global_pastoral_authority
from process_engine import now_utc, record_event, serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/processes/consolidation/graduations", tags=["consolidation-graduation"])
HANDOFF_SLA_HOURS = 72
GRADUATION_STAGE = {"key": "graduation", "order": 11, "name": "Graduación", "tasks": [("graduation_registered", "Registrar graduación en un evento", True)]}


def require_read(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_capability(current_user, PROCESSES_READ):
        raise HTTPException(status_code=403, detail="Sin permiso para consultar Consolidación")
    return current_user


def require_manage(current_user: dict = Depends(get_current_user)) -> dict:
    """Mismo permiso que cerrar el Retiro."""
    if not is_global_pastoral_authority(current_user) and not has_capability(current_user, CONSOLIDATION_RETREAT_CLOSE):
        raise HTTPException(status_code=403, detail="Sin permiso para administrar graduaciones")
    return current_user


async def church_today() -> str:
    from report_period import report_zone
    return datetime.now(await report_zone()).date().isoformat()


# ------------------------------------------------------------------ paso «Graduación» en el expediente
async def ensure_graduation_stage(enrollment: dict) -> None:
    """Los expedientes abiertos antes del cambio no tienen la fila del paso: se agrega al cerrar su Retiro."""
    enrollment_id = enrollment["enrollment_id"]
    if await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": "graduation"}, {"_id": 1}):
        return
    now = now_utc()
    stage_id = str(uuid4())
    await db.process_stage_progress.insert_one({
        "_id": stage_id, "stage_progress_id": stage_id, "enrollment_id": enrollment_id, "person_id": enrollment["person_id"],
        "process_key": "consolidation", "stage_key": "graduation", "stage_order": GRADUATION_STAGE["order"], "stage_name": GRADUATION_STAGE["name"],
        "status": "locked", "opened_at": None, "due_at": None, "attendance": "pending", "attendance_at": None,
        "tasks": [{"task_id": task_id, "label": label, "required": required, "completed": False, "completed_at": None, "evidence_count": 0} for task_id, label, required in GRADUATION_STAGE["tasks"]],
        "result": None, "notes": None, "created_at": now, "updated_at": now, "added_by": "r2_graduation",
    })
    await db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "discipleship_handoff"}, {"$set": {"stage_order": 12, "updated_at": now}})


async def _complete_stage(enrollment_id: str, stage_key: str, now: datetime, **extra) -> None:
    stage = await db.process_stage_progress.find_one({"enrollment_id": enrollment_id, "stage_key": stage_key})
    if not stage:
        return
    tasks = stage.get("tasks", [])
    for task in tasks:
        task.update({"completed": True, "completed_at": task.get("completed_at") or now})
    await db.process_stage_progress.update_one({"_id": stage["_id"]}, {"$set": {"status": "completed", "tasks": tasks, "completed_at": now, "updated_at": now, **extra}})


async def _progress_pct(enrollment_id: str) -> float:
    stages = await db.process_stage_progress.find({"enrollment_id": enrollment_id}, {"_id": 0, "status": 1}).to_list(100)
    done = sum(1 for item in stages if item.get("status") in {"completed", "skipped"})
    return round(done / max(1, len(stages)) * 100, 1)


# ------------------------------------------------------------------ traspaso a Discipulado de Formación
async def discipleship_program_ids() -> list[str]:
    return [doc["program_id"] async for doc in db.formation_programs.find({"purpose": "discipleship"}, {"_id": 0, "program_id": 1})]


async def discipleship_formation_enrollment(person_id: str) -> Optional[dict]:
    program_ids = await discipleship_program_ids()
    if not program_ids:
        return None
    return await db.formation_enrollments.find_one(
        {"person_id": person_id, "program_id": {"$in": program_ids}, "status": {"$nin": ["withdrawn", "cancelled"]}}, {"_id": 0}, sort=[("enrolled_at", 1)])


async def link_handoff(enrollment: dict, formation: dict, actor_user_id: str) -> None:
    """Cumple el paso «Educación / Discipulado» de un expediente GRADUADO (los de antes del cambio no se tocan)."""
    if not enrollment.get("graduated_at") or enrollment.get("discipleship_enrollment_id"):
        return
    now = now_utc()
    await _complete_stage(enrollment["enrollment_id"], "discipleship_handoff", now, result=f"Inscrito en {formation.get('module_name_snapshot') or 'Formación'}")
    await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": {
        "discipleship_enrollment_id": formation["enrollment_id"], "discipleship_program_id": formation.get("program_id"), "discipleship_linked_at": now,
        "progress_pct": await _progress_pct(enrollment["enrollment_id"]), "next_action": None, "next_action_at": None, "updated_at": now}})
    async for rec in db.formation_recommendations.find({"source_enrollment_id": enrollment["enrollment_id"], "status": "recommended"}, {"_id": 1}):
        try:
            await db.formation_recommendations.update_one({"_id": rec["_id"]}, {"$set": {"status": "fulfilled", "fulfilled_by_enrollment_id": formation["enrollment_id"], "fulfilled_at": now}})
        except DuplicateKeyError:  # índice único (persona, módulo, estado): ya hay una cumplida igual
            pass
    await record_event(db, enrollment, actor_user_id, "discipleship_linked", "Traspaso a Discipulado cumplido",
                       f"Inscrito en {formation.get('program_name_snapshot') or ''} · {formation.get('module_name_snapshot') or ''}".strip(" ·"))


async def on_formation_enrollment(formation: dict, actor_user_id: str) -> None:
    """Formación llama aquí al inscribir: si es Discipulado, cumple el traspaso del expediente graduado."""
    if formation.get("program_id") not in await discipleship_program_ids():
        return
    async for enrollment in db.process_enrollments.find({"process_key": "consolidation", "person_id": formation["person_id"], "graduated_at": {"$ne": None},
                                                         "discipleship_enrollment_id": None}, {"_id": 0}):
        await link_handoff(enrollment, formation, actor_user_id)


# ------------------------------------------------------------------ cerrar Retiro (llamado desde consolidation_v2)
async def mark_retreat_done(enrollment: dict, retreat_date: datetime, actor_user_id: str) -> None:
    enrollment_id = enrollment["enrollment_id"]
    claimed = await db.process_enrollments.update_one({"enrollment_id": enrollment_id, "retreat_completed_at": None, "current_stage_key": "retreat"},
                                                      {"$set": {"retreat_completed_at": retreat_date}})
    if not claimed.modified_count:  # otro cierre llegó primero
        return
    await ensure_graduation_stage(enrollment)
    now = now_utc()
    await _complete_stage(enrollment_id, "retreat", now)
    await db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "graduation"},
                                               {"$set": {"status": "open", "opened_at": now, "due_at": None, "updated_at": now}})
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {
        "consolidation_status": "graduation_pending", "current_stage_key": "graduation", "retreat_completed_at": retreat_date,
        "progress_pct": await _progress_pct(enrollment_id), "last_activity_at": now,
        "next_action": "Registrar la graduación en un evento de graduación", "next_action_at": None, "updated_at": now}})
    await record_event(db, enrollment, actor_user_id, "retreat_closed", "Retiro hecho · pendiente de graduación", "La Consolidación se completa al registrar la graduación")


# ------------------------------------------------------------------ eventos de graduación
class EventInput(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    event_date: date
    location: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1200)


class EventUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=160)
    event_date: Optional[date] = None
    location: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1200)
    status: Optional[Literal["planned", "cancelled"]] = None


class GraduatesInput(BaseModel):
    enrollment_ids: list[str] = Field(min_length=1, max_length=300)


class RevertInput(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


async def _event(event_id: str) -> dict:
    event = await db.graduation_events.find_one({"event_id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Evento de graduación no encontrado")
    return event


async def _person_names(person_ids: list[str]) -> dict:
    from bson import ObjectId
    oids = [ObjectId(pid) for pid in set(person_ids) if ObjectId.is_valid(pid)]
    return {str(doc["_id"]): " ".join(part for part in [doc.get("nombre"), doc.get("apellido")] if part)
            async for doc in db.persons.find({"_id": {"$in": oids}}, {"nombre": 1, "apellido": 1})}


async def pending_graduation() -> list[dict]:
    return await db.process_enrollments.find({"process_key": "consolidation", "status": "active", "current_stage_key": "graduation",
                                              "retreat_completed_at": {"$ne": None}, "graduated_at": None}, {"_id": 0}).to_list(5000)


async def legacy_retreat_closed_count() -> int:
    """Cerraron el Retiro con la regla anterior (quedaron «completados» sin graduación). Solo se cuentan."""
    return await db.process_enrollments.count_documents({"process_key": "consolidation", "definition_version": {"$gte": 2},
                                                         "retreat_completed_at": {"$ne": None}, "graduated_at": None, "status": "completed"})


@router.get("", response_model=dict)
async def list_events(current_user: dict = Depends(require_read)):
    events = await db.graduation_events.find({}, {"_id": 0}).sort("event_date", -1).to_list(500)
    counts = {row["_id"]: row["n"] async for row in db.graduation_records.aggregate([{"$match": {"status": "active"}}, {"$group": {"_id": "$event_id", "n": {"$sum": 1}}}])}
    for event in events:
        event["graduates_count"] = counts.get(event["event_id"], 0)
    pending = await pending_graduation()
    return {"items": serialize(events), "pending_count": len(pending), "legacy_retreat_closed_count": await legacy_retreat_closed_count(),
            "can_manage": is_global_pastoral_authority(current_user) or has_capability(current_user, CONSOLIDATION_RETREAT_CLOSE)}


@router.post("", response_model=dict, status_code=201)
async def create_event(payload: EventInput, current_user: dict = Depends(require_manage)):
    now = now_utc()
    event_id = str(uuid4())
    doc = {"_id": event_id, "event_id": event_id, "name": payload.name.strip(), "event_date": payload.event_date.isoformat(), "location": payload.location,
           "notes": payload.notes, "status": "planned", "created_by_user_id": current_user["user_id"], "created_at": now, "updated_at": now, "history": []}
    await db.graduation_events.insert_one(doc)
    return serialize(doc)


@router.put("/{event_id}", response_model=dict)
async def update_event(event_id: str, payload: EventUpdate, current_user: dict = Depends(require_manage)):
    event = await _event(event_id)
    changes = payload.model_dump(exclude_none=True)
    if "event_date" in changes:
        changes["event_date"] = changes["event_date"].isoformat()
    graduates = await db.graduation_records.count_documents({"event_id": event_id, "status": "active"})
    if graduates and (changes.get("status") == "cancelled" or ("event_date" in changes and changes["event_date"] != event["event_date"])):
        raise HTTPException(status_code=409, detail="El evento ya tiene graduados: revierta esas graduaciones antes de cambiar la fecha o cancelarlo")
    now = now_utc()
    await db.graduation_events.update_one({"event_id": event_id}, {"$set": {**changes, "updated_at": now},
                                                                    "$push": {"history": {"changes": changes, "by_user_id": current_user["user_id"], "at": now}}})
    return serialize(await _event(event_id))


@router.get("/{event_id}", response_model=dict)
async def event_detail(event_id: str, current_user: dict = Depends(require_read)):
    event = await _event(event_id)
    records = await db.graduation_records.find({"event_id": event_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    pending = await pending_graduation()
    names = await _person_names([row["person_id"] for row in records] + [row["person_id"] for row in pending])
    mentor_names = await _person_names([row["mentor_person_id"] for row in pending if row.get("mentor_person_id")])
    return {
        "event": serialize(event),
        "graduates": [{**serialize(row), "person_name": names.get(row["person_id"]) or "Persona"} for row in records],
        "candidates": [{"enrollment_id": row["enrollment_id"], "person_id": row["person_id"], "person_name": names.get(row["person_id"]) or "Persona",
                        "mentor_name": mentor_names.get(row.get("mentor_person_id")), "retreat_completed_at": serialize(row.get("retreat_completed_at"))} for row in pending],
    }


@router.post("/{event_id}/graduates", response_model=dict)
async def register_graduates(event_id: str, payload: GraduatesInput, current_user: dict = Depends(require_manage)):
    event = await _event(event_id)
    if event.get("status") == "cancelled":
        raise HTTPException(status_code=409, detail="El evento está cancelado")
    if event["event_date"] > await church_today():
        raise HTTPException(status_code=409, detail="La graduación se registra el día del evento o después")
    ids = list(dict.fromkeys(payload.enrollment_ids))
    rows = {row["enrollment_id"]: row for row in await db.process_enrollments.find({"enrollment_id": {"$in": ids}, "process_key": "consolidation"}, {"_id": 0}).to_list(len(ids))}
    # Todo o nada: se valida a todos antes de escribir.
    problems = []
    for enrollment_id in ids:
        row = rows.get(enrollment_id)
        if not row:
            problems.append(f"{enrollment_id}: expediente no encontrado")
        elif row.get("graduated_at"):
            problems.append(f"{enrollment_id}: ya está graduado")
        elif row.get("status") != "active" or row.get("current_stage_key") != "graduation" or not row.get("retreat_completed_at"):
            problems.append(f"{enrollment_id}: no está «Retiro hecho, pendiente de graduación»")
    if problems:
        raise HTTPException(status_code=409, detail={"message": "No se registró ninguna graduación", "problems": problems})
    graduated_at = datetime.fromisoformat(event["event_date"]).replace(hour=12, tzinfo=timezone.utc)
    program = await db.formation_programs.find_one({"purpose": "discipleship", "active": True}, {"_id": 0}, sort=[("created_at", 1)])
    module = await db.formation_modules.find_one({"program_id": program["program_id"], "active": True}, {"_id": 0}, sort=[("order", 1)]) if program else None
    done = []
    for enrollment_id in ids:
        enrollment = rows[enrollment_id]
        now = now_utc()
        claimed = await db.process_enrollments.update_one(
            {"enrollment_id": enrollment_id, "graduated_at": None, "current_stage_key": "graduation", "status": "active"},
            {"$set": {"graduated_at": graduated_at, "graduation_event_id": event_id, "pre_graduation_decision_status": enrollment.get("decision_status")}})
        if not claimed.modified_count:
            continue
        record_id = str(uuid4())
        await db.graduation_records.insert_one({"_id": record_id, "record_id": record_id, "event_id": event_id, "enrollment_id": enrollment_id,
                                                "person_id": enrollment["person_id"], "graduated_at": graduated_at, "status": "active",
                                                "registered_by_user_id": current_user["user_id"], "created_at": now})
        await _complete_stage(enrollment_id, "graduation", now, result=event["name"])
        await db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "discipleship_handoff"},
                                                   {"$set": {"status": "open", "opened_at": now, "due_at": now + timedelta(hours=HANDOFF_SLA_HOURS), "updated_at": now}})
        recommendation_id = None
        if program and module:
            await db.formation_recommendations.update_one(
                {"person_id": enrollment["person_id"], "module_id": module["module_id"], "status": "recommended"},
                {"$setOnInsert": {"_id": (new_id := str(uuid4())), "recommendation_id": new_id, "person_id": enrollment["person_id"], "program_id": program["program_id"],
                                  "module_id": module["module_id"], "program_name_snapshot": program["name"], "module_name_snapshot": module["name"],
                                  "source": "consolidation_graduation", "source_enrollment_id": enrollment_id, "status": "recommended",
                                  "created_by_user_id": current_user["user_id"], "created_at": now}}, upsert=True)
            rec = await db.formation_recommendations.find_one({"person_id": enrollment["person_id"], "module_id": module["module_id"], "status": "recommended"}, {"recommendation_id": 1})
            recommendation_id = (rec or {}).get("recommendation_id")
        await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {
            "status": "completed", "consolidation_status": "completed", "decision_status": "completed", "completed_at": now,
            "current_stage_key": "discipleship_handoff", "formation_recommendation_id": recommendation_id, "discipleship_enrollment_id": None,
            "progress_pct": await _progress_pct(enrollment_id), "last_activity_at": now,
            "next_action": f"Inscribir en {module['name']}" if module else "Configurar programa de Formación / Discipulado", "next_action_at": None, "updated_at": now}})
        await record_event(db, enrollment, current_user["user_id"], "graduated", "Graduación registrada", f"{event['name']} · {event['event_date']}")
        refreshed = await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
        formation = await discipleship_formation_enrollment(enrollment["person_id"])
        if formation:
            await link_handoff(refreshed, formation, current_user["user_id"])
        done.append(enrollment_id)
    await db.graduation_events.update_one({"event_id": event_id}, {"$set": {"status": "held", "updated_at": now_utc()}})
    return {"graduated": done, **(await event_detail(event_id, current_user))}


@router.post("/{event_id}/graduates/{enrollment_id}/revert", response_model=dict)
async def revert_graduate(event_id: str, enrollment_id: str, payload: RevertInput, current_user: dict = Depends(require_manage)):
    """Corrige una graduación registrada por error: el expediente vuelve a «pendiente de graduación». No borra nada."""
    record = await db.graduation_records.find_one({"event_id": event_id, "enrollment_id": enrollment_id, "status": "active"}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Esa graduación no está registrada en este evento")
    enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    if enrollment.get("discipleship_enrollment_id"):
        raise HTTPException(status_code=409, detail="La persona ya está inscrita en Discipulado de Formación; corrija primero esa inscripción")
    now = now_utc()
    await db.graduation_records.update_one({"record_id": record["record_id"]}, {"$set": {"status": "reverted", "reverted_at": now, "reverted_by_user_id": current_user["user_id"], "revert_reason": payload.reason}})
    await db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "graduation"}, {"$set": {"status": "open", "completed_at": None, "updated_at": now,
                                                                                                                     "tasks.$[].completed": False, "tasks.$[].completed_at": None}})
    await db.process_stage_progress.update_one({"enrollment_id": enrollment_id, "stage_key": "discipleship_handoff"}, {"$set": {"status": "locked", "opened_at": None, "due_at": None, "updated_at": now}})
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": {
        "status": "active", "consolidation_status": "graduation_pending", "decision_status": enrollment.get("pre_graduation_decision_status") or "accepted", "completed_at": None, "current_stage_key": "graduation",
        "graduated_at": None, "graduation_event_id": None, "formation_recommendation_id": None, "progress_pct": await _progress_pct(enrollment_id),
        "next_action": "Registrar la graduación en un evento de graduación", "next_action_at": None, "updated_at": now}})
    await record_event(db, enrollment, current_user["user_id"], "graduation_reverted", "Graduación revertida", payload.reason)
    return await event_detail(event_id, current_user)


async def ensure_indexes() -> None:
    await db.graduation_events.create_index("event_id", unique=True)
    await db.graduation_events.create_index([("event_date", -1)])
    await db.graduation_records.create_index("record_id", unique=True)
    await db.graduation_records.create_index([("event_id", 1), ("status", 1)])
    await db.graduation_records.create_index("enrollment_id", unique=True, partialFilterExpression={"status": "active"}, name="one_active_graduation_per_enrollment")
