"""ENTREGA B de Invasiones: calendario individual de actividades por discípulo
(MCD/NPT/LBS) y panel del mentor.

Cuando el expediente de Consolidación entra a MCD (viniendo de Invasión, de
célula/iglesia, o de 'Pendiente de decisión' manual) se genera, UNA sola vez,
el calendario completo de actividades hasta el final de LBS, con fecha
calculada desde la fecha de inicio acordada de ESE discípulo (cada uno tiene la
suya, aunque compartan invasión). El mentor registra el resultado actividad por
actividad; el avance de etapa (para estadísticas) solo cuenta las 'realizada'.

No duplica el motor de Consolidación v2 (`consolidation_service.py`,
`process_engine.py`): las etapas (mcd/npt/lbs_1/lbs_2/lbs_3) y sus tareas
siguen siendo la fuente de verdad para abrir/cerrar/bloquear; esto es un nivel
de detalle operativo DENTRO de esas etapas.
"""
from datetime import date, datetime, timedelta
from typing import Literal, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from access_control import CONSOLIDATION_ASSIGN, has_capability, is_general_coordinator, is_global_pastoral_authority
from consolidation_service import assert_consolidation_scope, load_consolidation
from library_module import deliver_from_mentor_to_person
from process_engine import now_utc, record_event, serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/processes/consolidation", tags=["consolidation-activities"])

ACTIVITY_STAGES = ("mcd", "npt", "lbs_1", "lbs_2", "lbs_3")
# Semana (S3..S7 de la Ley de las 7 Semanas) de cada etapa relativa al inicio de MCD.
STAGE_WEEK_OFFSET = {"mcd": 0, "npt": 1, "lbs_1": 2, "lbs_2": 3, "lbs_3": 4}
STAGE_WEEK_LABEL = {"mcd": "S3", "npt": "S4", "lbs_1": "S5", "lbs_2": "S6", "lbs_3": "S7"}
STAGE_TITLE = {"mcd": "Mi Conexión con Dios", "npt": "Nací Para Triunfar", "lbs_1": "LBS · Liberación", "lbs_2": "LBS · Bendición", "lbs_3": "LBS · Sanidad"}
BOOK_SKU_BY_STAGE = {"mcd": "MCD", "npt": "NPT"}  # solo estas dos etapas entregan un libro físico
RESULT_STATUSES = ("pending", "done", "no_answer", "rescheduled")

MCD_MOMENTS = [("morning", "Mañana"), ("midday", "Medio día"), ("night", "Noche")]
NPT_MOMENTS = [("9am", "9:00 a.m."), ("12m", "12:00 m."), ("3pm", "3:00 p.m."), ("6pm", "6:00 p.m.")]
LBS_TOPICS = {
    "lbs_1": [
        "Quebrantando la Maldición de la Tierra",
        "Liberándonos de las Maldiciones de nuestros propios Territorios",
        "Quebrantando la Maldición de la Parentela",
        "La Maldición de los Padres",
        "Quebrantando las Auto-Maldiciones",
        "Rompiendo las Maldiciones sin Confesar",
        "Liberándome de los Siete espíritus Peores",
    ],
    "lbs_2": [
        "Conociendo la Plenitud de la Bendición",
        "La Bendición de ser Redimido por Jesucristo",
        "Conociendo al Espíritu Santo",
        "El Poder Creativo de la Palabra de Dios",
        "El Poder del Pensamiento Positivo",
        "Poder y Autoridad Espiritual",
        "La Bendición de Dar",
    ],
    "lbs_3": [
        "El Poder de la Sanidad Profunda",
        "Sanando mi Vida del Rechazo",
        "Sanando mi Vida del Temor",
        "Sanando mi Vida de la Ansiedad",
        "Conociendo el Poder del Perdón",
        "La Renovación de la Mente",
        "El Poder de los Sueños y las Visiones",
    ],
}


def require_pastoral_or_coordinator(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_global_pastoral_authority(current_user) and not is_general_coordinator(current_user):
        raise HTTPException(status_code=403, detail="Solo la pastora/pastor o un coordinador general puede configurar el catálogo de actividades")
    return current_user


DEFAULT_CHURCH_TIMEZONE = "UTC"  # sin configurar aún; la pastora la fija en Configuración (PUT /settings/timezone)


async def get_church_timezone() -> str:
    """Zona horaria de la congregación para 'Hoy/Atrasado' (configurable por
    pastora/coordinador, en vez de la hora del servidor). Singleton en Mongo."""
    settings = await db.mentorship_settings.find_one({"_id": "global"}, {"_id": 0, "church_timezone": 1})
    return (settings or {}).get("church_timezone") or DEFAULT_CHURCH_TIMEZONE


def local_today(tz_name: str) -> date:
    try:
        return datetime.now(ZoneInfo(tz_name)).date()
    except (ZoneInfoNotFoundError, ValueError):
        return now_utc().date()


class ChurchTimezoneUpdate(BaseModel):
    church_timezone: str = Field(min_length=2, max_length=64)


@router.get("/settings/timezone", response_model=dict)
async def get_church_timezone_setting(current_user: dict = Depends(get_current_user)):
    return {"church_timezone": await get_church_timezone()}


@router.put("/settings/timezone", response_model=dict)
async def update_church_timezone_setting(payload: ChurchTimezoneUpdate, current_user: dict = Depends(require_pastoral_or_coordinator)):
    try:
        ZoneInfo(payload.church_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=422, detail="Zona horaria inválida (use un identificador IANA, p. ej. America/New_York)")
    now = now_utc()
    await db.mentorship_settings.update_one(
        {"_id": "global"},
        {"$set": {"church_timezone": payload.church_timezone, "updated_at": now, "updated_by_user_id": current_user["user_id"]}},
        upsert=True,
    )
    return {"church_timezone": payload.church_timezone}


async def seed_activity_catalog() -> None:
    """Catálogo configurable por la pastora (`consolidation_activity_templates`):
    MCD 7 días x3 momentos = 21, NPT 3 días x4 momentos = 12, LBS 7 días x1
    tema diario x3 libros = 21. Semilla idempotente (upsert por template_id);
    la pastora puede luego editar título/contenido/activo sin tocar código."""
    await db.consolidation_activity_templates.create_index("template_id", unique=True)
    await db.consolidation_activities.create_index("activity_id", unique=True)
    await db.consolidation_activities.create_index([("enrollment_id", 1), ("order", 1)])
    await db.consolidation_activities.create_index([("mentor_person_id", 1), ("status", 1), ("scheduled_date", 1)])
    now = now_utc()
    templates = []
    order = 0
    for day in range(1, 8):
        for moment_key, moment_label in MCD_MOMENTS:
            order += 1
            templates.append({"stage_key": "mcd", "day_number": day, "moment_key": moment_key, "moment_label": moment_label, "title": f"MCD · Día {day} · {moment_label}", "content": None, "order": order})
    for day in range(1, 4):
        for moment_key, moment_label in NPT_MOMENTS:
            order += 1
            templates.append({"stage_key": "npt", "day_number": day, "moment_key": moment_key, "moment_label": moment_label, "title": f"NPT · Día {day} · {moment_label}", "content": None, "order": order})
    for stage_key, topics in LBS_TOPICS.items():
        for day, topic in enumerate(topics, start=1):
            order += 1
            templates.append({"stage_key": stage_key, "day_number": day, "moment_key": "day", "moment_label": "Sesión del día", "title": f"{STAGE_TITLE[stage_key]} · Día {day}: {topic}", "content": topic, "order": order})
    for template in templates:
        template_id = f"{template['stage_key']}_{template['day_number']}_{template['moment_key']}"
        await db.consolidation_activity_templates.update_one(
            {"template_id": template_id},
            {"$set": {**template, "template_id": template_id, "active": True, "updated_at": now}, "$setOnInsert": {"_id": template_id, "created_at": now}},
            upsert=True,
        )


async def ensure_consolidation_calendar(enrollment: dict, actor_user_id: str) -> bool:
    """Genera, UNA sola vez por expediente (idempotente), las actividades de
    MCD→NPT→LBS1→LBS2→LBS3 a partir de la fecha de inicio de ESTE discípulo.
    Se llama exactamente al momento en que la etapa MCD se abre, sin importar
    el camino (Invasión, célula/iglesia, o 'Pendiente de decisión' manual)."""
    if await db.consolidation_activities.find_one({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 1}):
        return False
    templates = await db.consolidation_activity_templates.find({"stage_key": {"$in": ACTIVITY_STAGES}, "active": True}, {"_id": 0}).sort("order", 1).to_list(200)
    if not templates:
        return False
    raw_start = enrollment.get("outreach_agreed_start_date")
    try:
        start_date = date.fromisoformat(raw_start) if raw_start else now_utc().date()
    except ValueError:
        start_date = now_utc().date()
    now = now_utc()
    docs = []
    for template in templates:
        stage_key = template["stage_key"]
        week_start = start_date + timedelta(days=7 * STAGE_WEEK_OFFSET[stage_key])
        scheduled_date = week_start + timedelta(days=template["day_number"] - 1)
        activity_id = str(uuid4())
        docs.append({
            "_id": activity_id, "activity_id": activity_id, "enrollment_id": enrollment["enrollment_id"],
            "person_id": enrollment["person_id"], "mentor_person_id": enrollment.get("mentor_person_id"),
            "stage_key": stage_key, "stage_week_label": STAGE_WEEK_LABEL[stage_key], "day_number": template["day_number"],
            "moment_key": template["moment_key"], "moment_label": template["moment_label"],
            "title": template["title"], "content": template.get("content"), "order": template["order"],
            "scheduled_date": scheduled_date.isoformat(), "status": "pending", "last_result": None, "result_at": None,
            "note": None, "next_step": None, "rescheduled_date": None, "book_delivery_movement_id": None,
            "created_at": now, "updated_at": now,
        })
    await db.consolidation_activities.insert_many(docs)
    decision_status = "start_scheduled" if start_date > now.date() else "in_progress"
    await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": {"decision_status": decision_status, "updated_at": now}})
    await record_event(db, enrollment, actor_user_id, "calendar_generated", "Calendario individual generado", f"{len(docs)} actividades desde {start_date.isoformat()}")
    return True


async def sync_activities_mentor(enrollment_id: str, mentor_person_id: str | None) -> None:
    """Al transferir el mentor responsable (o cambiar de grupo frontal), las
    actividades PENDIENTES deben pasar a su panel; las 'realizada' quedan
    atribuidas a quien realmente las hizo (no se reescribe el historial)."""
    await db.consolidation_activities.update_many(
        {"enrollment_id": enrollment_id, "status": "pending"},
        {"$set": {"mentor_person_id": mentor_person_id, "updated_at": now_utc()}},
    )


async def build_mentor_activity_buckets(mentor_person_id: str, upcoming_days: int = 7) -> dict:
    """'Hoy', 'Atrasado' y 'Próximo' de UN mentor — usado tanto por su propio
    panel como por la vista de supervisión (pastora/coordinador) de ese mentor.
    Incluye actividades 'pendientes' aunque su último intento haya sido 'sin
    respuesta' o 'reprogramada' (son intentos, no cierran la actividad); excluye
    expedientes pausados/desistidos o ya completados."""
    today = local_today(await get_church_timezone())
    upcoming_limit = (today + timedelta(days=upcoming_days)).isoformat()
    paused_or_done = await db.process_enrollments.distinct(
        "enrollment_id", {"process_key": "consolidation", "mentor_person_id": mentor_person_id, "$or": [{"decision_status": "paused"}, {"status": "completed"}]},
    )
    base = {"mentor_person_id": mentor_person_id, "status": "pending", "enrollment_id": {"$nin": paused_or_done}}
    today_items = await db.consolidation_activities.find({**base, "scheduled_date": today.isoformat()}, {"_id": 0}).sort("order", 1).to_list(300)
    overdue_items = await db.consolidation_activities.find({**base, "scheduled_date": {"$lt": today.isoformat()}}, {"_id": 0}).sort("scheduled_date", 1).to_list(300)
    upcoming_items = await db.consolidation_activities.find({**base, "scheduled_date": {"$gt": today.isoformat(), "$lte": upcoming_limit}}, {"_id": 0}).sort("scheduled_date", 1).to_list(300)
    person_ids = {item["person_id"] for item in today_items + overdue_items + upcoming_items}
    valid_oids = [ObjectId(pid) for pid in person_ids if ObjectId.is_valid(pid)]
    people = await db.persons.find({"_id": {"$in": valid_oids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(valid_oids)) if valid_oids else []
    names = {str(p["_id"]): f"{p.get('nombre', '')} {p.get('apellido', '')}".strip() for p in people}

    def enrich(items: list) -> list:
        return [{**serialize(item), "person_name": names.get(item["person_id"], "—")} for item in items]

    return {"today": enrich(today_items), "overdue": enrich(overdue_items), "upcoming": enrich(upcoming_items)}


@router.get("/activity-catalog", response_model=dict)
async def get_activity_catalog(current_user: dict = Depends(get_current_user)):
    items = await db.consolidation_activity_templates.find({}, {"_id": 0}).sort([("stage_key", 1), ("order", 1)]).to_list(200)
    return {"items": serialize(items), "total": len(items)}


class ActivityTemplateUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    content: Optional[str] = Field(default=None, max_length=2000)
    active: Optional[bool] = None


@router.put("/activity-catalog/{template_id}", response_model=dict)
async def update_activity_template(template_id: str, payload: ActivityTemplateUpdate, current_user: dict = Depends(require_pastoral_or_coordinator)):
    update = {key: value for key, value in payload.model_dump(exclude_unset=True).items()}
    if not update:
        raise HTTPException(status_code=422, detail="Indique al menos un campo para actualizar")
    update["updated_at"] = now_utc()
    result = await db.consolidation_activity_templates.update_one({"template_id": template_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Plantilla de actividad no encontrada")
    return serialize(await db.consolidation_activity_templates.find_one({"template_id": template_id}, {"_id": 0}))


@router.get("/my-panel", response_model=dict)
async def my_mentor_panel(current_user: dict = Depends(get_current_user)):
    """Panel del mentor: SOLO sus propios discípulos, nunca los de otro mentor."""
    mentor_person_id = current_user.get("person_id")
    if not mentor_person_id:
        raise HTTPException(status_code=403, detail="Esta cuenta no está vinculada a un Perfil 360")
    if not await db.mentor_badges.find_one({"person_id": mentor_person_id, "active": True}, {"_id": 1}):
        raise HTTPException(status_code=403, detail="Requiere insignia de Mentor activa")
    buckets = await build_mentor_activity_buckets(mentor_person_id)
    enrollments = await db.process_enrollments.find(
        {"process_key": "consolidation", "definition_version": 2, "mentor_person_id": mentor_person_id}, {"_id": 0},
    ).sort("updated_at", -1).to_list(500)
    person_ids = [ObjectId(item["person_id"]) for item in enrollments if ObjectId.is_valid(item["person_id"])]
    people = await db.persons.find({"_id": {"$in": person_ids}}, {"_id": 1, "nombre": 1, "apellido": 1}).to_list(len(person_ids)) if person_ids else []
    names = {str(p["_id"]): f"{p.get('nombre', '')} {p.get('apellido', '')}".strip() for p in people}
    mentees = []
    for item in enrollments:
        total = await db.consolidation_activities.count_documents({"enrollment_id": item["enrollment_id"]})
        done = await db.consolidation_activities.count_documents({"enrollment_id": item["enrollment_id"], "status": "done"})
        mentees.append({
            "enrollment_id": item["enrollment_id"], "person_id": item["person_id"], "person_name": names.get(item["person_id"], "—"),
            "current_stage_key": item.get("current_stage_key"), "decision_status": item.get("decision_status"),
            "activities_done": done, "activities_total": total,
        })
    return {"mentor_person_id": mentor_person_id, **buckets, "mentees": mentees}


@router.get("/{enrollment_id}/activities", response_model=dict)
async def list_enrollment_activities(enrollment_id: str, current_user: dict = Depends(get_current_user)):
    enrollment = await load_consolidation(db, enrollment_id)
    await assert_consolidation_scope(db, enrollment, current_user)
    items = await db.consolidation_activities.find({"enrollment_id": enrollment_id}, {"_id": 0}).sort("order", 1).to_list(200)
    return {"items": serialize(items), "total": len(items)}


class ActivityResultUpdate(BaseModel):
    status: Literal["done", "no_answer", "rescheduled"]
    note: Optional[str] = Field(default=None, max_length=1000)
    next_step: Optional[str] = Field(default=None, max_length=500)
    rescheduled_date: Optional[date] = None
    deliver_book: bool = False


@router.put("/activities/{activity_id}/result", response_model=dict)
async def update_activity_result(activity_id: str, payload: ActivityResultUpdate, current_user: dict = Depends(get_current_user)):
    activity = await db.consolidation_activities.find_one({"activity_id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    enrollment = await load_consolidation(db, activity["enrollment_id"])
    await assert_consolidation_scope(db, enrollment, current_user)
    if current_user.get("rol") == "persona" and current_user.get("person_id") != enrollment.get("mentor_person_id"):
        raise HTTPException(status_code=403, detail="Solo el mentor responsable puede registrar esta actividad")
    if payload.status == "rescheduled" and not payload.rescheduled_date:
        raise HTTPException(status_code=422, detail="Indique la nueva fecha para reprogramar")
    if activity["status"] == "done" and payload.status != "done":
        raise HTTPException(status_code=409, detail="La actividad ya fue realizada; no se puede revertir")
    now = now_utc()
    # 'sin respuesta' y 'reprogramada' son INTENTOS, no cierran la actividad: sigue
    # 'pending' (aparece en Hoy/Atrasado/Próximo y se puede volver a registrar más
    # tarde); solo 'done' es terminal y cuenta para el avance de la etapa.
    update = {
        "status": "done" if payload.status == "done" else "pending", "last_result": payload.status,
        "result_at": now, "note": payload.note, "next_step": payload.next_step, "updated_at": now,
    }
    if payload.status == "rescheduled":
        update["rescheduled_date"] = payload.rescheduled_date.isoformat()
        update["scheduled_date"] = payload.rescheduled_date.isoformat()
    if payload.deliver_book and payload.status == "done" and activity["stage_key"] in BOOK_SKU_BY_STAGE and not activity.get("book_delivery_movement_id"):
        sku = BOOK_SKU_BY_STAGE[activity["stage_key"]]
        book = await db.library_books.find_one({"sku": sku}, {"_id": 0, "book_id": 1, "name": 1})
        already_delivered = book and await db.library_movements.find_one({"book_id": book["book_id"], "movement_type": "DELIVERY", "person_id": enrollment["person_id"]}, {"_id": 1})
        if already_delivered:
            raise HTTPException(status_code=409, detail=f"Ya se le entregó {book['name']} a esta persona antes; no se puede entregar de nuevo")
        movement_id = await deliver_from_mentor_to_person(
            sku, enrollment["mentor_person_id"], enrollment["person_id"], current_user["user_id"],
            campaign_id=enrollment.get("campaign_id"), process_key="consolidation", notes=f"Entrega durante actividad: {activity['title']}",
        )
        update["book_delivery_movement_id"] = movement_id
    await db.consolidation_activities.update_one({"activity_id": activity_id}, {"$set": update})
    if payload.status == "done" and enrollment.get("decision_status") == "start_scheduled":
        await db.process_enrollments.update_one({"enrollment_id": enrollment["enrollment_id"]}, {"$set": {"decision_status": "in_progress", "updated_at": now}})
    await record_event(db, enrollment, current_user["user_id"], "activity_result", f"{activity['title']}: {payload.status}", payload.note or "")
    return serialize(await db.consolidation_activities.find_one({"activity_id": activity_id}, {"_id": 0}))
