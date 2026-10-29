"""R3 · «Proceso paso a paso» de una persona (SOLO LECTURA; nada se copia ni se escribe).

Une en una línea lo que ya guardan los módulos:
- antes del proceso: primer contacto (visita de invasión, tableta de visitantes o alta), visitas y libros;
- el momento en que pasa de «conocida» a «En proceso con mentor X», y desde qué origen (iglesia, célula, invasión);
- los 12 pasos de Consolidación con su estado (hecho, a tiempo o tarde, en curso, atrasado, pendiente, no aplica),
  fecha, quién lo hizo, sus puntos (tareas) y evidencia;
- después: Fiesta/Membresía, bautismo, Retiro, Graduación (evento), Discipulado de Formación, Grupo Frontal.
Mismo acceso que «Contactado por» (person_contact.can_read): la autoridad pastoral, quien tiene alcance sobre la
persona, quien asigna en Consolidación, la propia persona y el mentor que la contactó o la acompaña."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from process_engine import serialize
from server import db, get_current_user

router = APIRouter(prefix="/api/persons", tags=["person-steps"])
OPEN = ["planned", "active", "paused"]
ENTRY_ORIGIN = {
    "invasion": ("invasion", "Invasión"), "complete_cycle": ("iglesia", "Iglesia (ciclo completo)"), "direct_church": ("iglesia", "Iglesia"),
    "cell": ("celula", "Célula"), "visitor_followup": ("iglesia", "Iglesia · seguimiento de visitante"),
}


def _aware(value) -> Optional[datetime]:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


async def _person_names(person_ids) -> dict:
    oids = [ObjectId(pid) for pid in {pid for pid in person_ids if pid} if ObjectId.is_valid(pid)]
    return {str(doc["_id"]): " ".join(filter(None, [doc.get("nombre"), doc.get("apellido")])) or "Persona"
            async for doc in db.persons.find({"_id": {"$in": oids}}, {"nombre": 1, "apellido": 1})} if oids else {}


async def _user_names(user_ids) -> dict:
    """Nombre de quien hizo algo (por su cuenta): la persona enlazada o el nombre de la cuenta."""
    ids = [uid for uid in {uid for uid in user_ids if uid}]
    keys = ids + [ObjectId(uid) for uid in ids if ObjectId.is_valid(uid)]
    users = {str(doc["_id"]): doc async for doc in db.users.find({"_id": {"$in": keys}}, {"nombre": 1, "person_id": 1})} if keys else {}
    people = await _person_names([doc.get("person_id") for doc in users.values()])
    return {uid: people.get(doc.get("person_id")) or doc.get("nombre") or "Usuario" for uid, doc in users.items()}


def stage_state(stage: dict, now: datetime) -> dict:
    status = stage.get("status")
    due = _aware(stage.get("due_at"))
    done_at = _aware(stage.get("completed_at"))
    if status == "completed":
        on_time = None if not due or not done_at else done_at <= due
        return {"state": "done", "label": "Hecho" if on_time is not False else "Hecho tarde", "on_time": on_time}
    if status == "skipped":
        return {"state": "not_applicable", "label": "No aplica", "on_time": None}
    if status in {"open", "in_progress"}:
        if due and due < now:
            return {"state": "overdue", "label": "Atrasado", "on_time": False}
        return {"state": "current", "label": "En curso", "on_time": None}
    return {"state": "pending", "label": "Pendiente", "on_time": None}


def _who_completed(stage: dict, timeline: list) -> Optional[str]:
    """Quién lo cerró: el dato guardado o, para lo anterior a R3, el movimiento del historial más cercano."""
    if stage.get("completed_by_user_id"):
        return stage["completed_by_user_id"]
    done_at = _aware(stage.get("completed_at"))
    if not done_at:
        return None
    near = [item for item in timeline if item.get("actor_user_id") and _aware(item.get("occurred_at"))
            and abs((_aware(item["occurred_at"]) - done_at).total_seconds()) <= 10]
    return near[0]["actor_user_id"] if near else None


def origin_of(enrollment: Optional[dict], first_contact: Optional[dict], visitor_regs: list) -> dict:
    if enrollment:
        if enrollment.get("source") == "mentorship_outreach" or enrollment.get("entry_mode") == "invasion":
            name = (first_contact or {}).get("campaign_name")
            return {"kind": "invasion", "label": f"Invasión «{name}»" if name else "Invasión"}
        if str(enrollment.get("source") or "").startswith("legacy_"):
            return {"kind": "manual_antiguo", "label": "Manual antiguo (Ley de las 7 Semanas)"}
        if enrollment.get("source") == "visitor_registry":
            return {"kind": "iglesia", "label": "Iglesia · registro de visitante"}
        kind, label = ENTRY_ORIGIN.get(enrollment.get("entry_mode"), (None, None))
        if kind:
            return {"kind": kind, "label": label}
    if first_contact and first_contact.get("campaign_name"):
        return {"kind": "invasion", "label": f"Invasión «{first_contact['campaign_name']}»"}
    if visitor_regs:
        return {"kind": "iglesia", "label": "Iglesia · registro de visitante"}
    return {"kind": "registro", "label": "Registrada en Persona 360"}


async def step_by_step(person_id: str) -> dict:
    from person_contact import build, gather
    now = datetime.now(timezone.utc)
    person = await db.persons.find_one({"_id": ObjectId(person_id)}, {"nombre": 1, "apellido": 1, "person_number": 1, "created_at": 1})
    data = await gather(person_id)
    from person_contact import contact_mentor_ids
    names = await _person_names(contact_mentor_ids(data))
    contact = build(data, names)
    first_contact = contact.get("first_contact")

    enrollments = await db.process_enrollments.find({"person_id": person_id, "process_key": "consolidation"}, {"_id": 0}).sort("created_at", -1).to_list(50)
    main = next((item for item in enrollments if item.get("status") in OPEN), None) or next(iter(enrollments), None)
    stages, timeline, assignments = [], [], []
    if main:
        stages = await db.process_stage_progress.find({"enrollment_id": main["enrollment_id"]}, {"_id": 0}).sort("stage_order", 1).to_list(100)
        timeline = await db.process_timeline.find({"enrollment_id": main["enrollment_id"]}, {"_id": 0}).sort("occurred_at", 1).to_list(500)
        assignments = await db.mentor_assignments.find({"enrollment_id": main["enrollment_id"]}, {"_id": 0}).sort("started_at", 1).to_list(100)
    membership = await db.person_memberships.find_one({"person_id": person_id}, {"_id": 0})
    baptism = await db.person_baptisms.find_one({"person_id": person_id, "status": "completed"}, {"_id": 0})
    graduation = await db.graduation_records.find_one({"person_id": person_id, "status": "active"}, {"_id": 0}, sort=[("created_at", -1)])
    graduation_event = await db.graduation_events.find_one({"event_id": graduation["event_id"]}, {"_id": 0, "name": 1, "event_date": 1}) if graduation else None
    discipleship_programs = [doc["program_id"] async for doc in db.formation_programs.find({"purpose": "discipleship"}, {"_id": 0, "program_id": 1})]
    discipleship = await db.formation_enrollments.find_one({"person_id": person_id, "program_id": {"$in": discipleship_programs}}, {"_id": 0}, sort=[("enrolled_at", 1)]) if discipleship_programs else None
    group_rows = await db.front_group_assignments.find({"person_id": person_id, "active": True}, {"_id": 0, "front_group_id": 1, "role": 1, "created_at": 1, "started_at": 1}).to_list(20)
    groups = {doc["front_group_id"]: doc.get("name") async for doc in db.front_groups.find({"front_group_id": {"$in": [row["front_group_id"] for row in group_rows]}}, {"_id": 0, "front_group_id": 1, "name": 1})} if group_rows else {}

    mentor_ids = [row.get("mentor_person_id") for row in assignments] + [(main or {}).get("mentor_person_id")]
    people_names = await _person_names(mentor_ids)
    actor_ids = [item.get("actor_user_id") for item in timeline] + [stage.get("completed_by_user_id") for stage in stages] + [(graduation or {}).get("registered_by_user_id")]
    actor_names = await _user_names(actor_ids)
    origin = origin_of(main, first_contact, data.get("visitor_regs") or [])

    # ---- hitos (orden por fecha)
    milestones = []
    def add(key, label, at, by=None, detail=None):
        if at:
            milestones.append({"key": key, "label": label, "at": serialize(_aware(at) or at), "by": by, "detail": detail})
    if first_contact:
        add("first_contact", "Primer contacto", first_contact.get("at"), first_contact.get("mentor_name"),
            " · ".join(filter(None, [first_contact.get("campaign_name"), first_contact.get("address")])) or None)
    for reg in data.get("visitor_regs") or []:
        add("visitor_registered", "Registrada como visitante en la iglesia", reg.get("created_at"), None, f"Visitante #{reg.get('visitor_number')}" if reg.get("visitor_number") else None)
    for book in contact.get("books") or []:
        add("book", f"Libro entregado · {book.get('quantity') or 1} × {book.get('book_name')}", book.get("at"), book.get("delivered_by"), book.get("campaign_name"))
    if main:
        first_assignment = assignments[0] if assignments else None
        mentor_name = people_names.get((first_assignment or {}).get("mentor_person_id") or main.get("mentor_person_id"))
        add("in_process", f"En proceso con mentor {mentor_name}" if mentor_name else "Inició Consolidación (sin mentor todavía)",
            (first_assignment or {}).get("started_at") or main.get("created_at"), None, f"Desde {origin['label']}")
        for row in assignments[1:]:
            add("mentor_changed", f"Cambio de mentor: {people_names.get(row.get('mentor_person_id')) or 'Mentor'}", row.get("started_at"), None, row.get("reason"))
        if main.get("retreat_completed_at"):
            add("retreat", "Retiro hecho", main.get("retreat_completed_at"))
    if membership and membership.get("acceptance_signed_at"):
        add("membership", "Carta de Membresía firmada", membership.get("acceptance_signed_at"), None, f"Miembro {membership.get('member_number')}" if membership.get("member_number") else None)
    if baptism:
        add("baptism", "Bautismo", baptism.get("baptism_date") or baptism.get("updated_at"))
    if graduation:
        add("graduation", "Graduación", graduation.get("graduated_at"), actor_names.get(graduation.get("registered_by_user_id")), (graduation_event or {}).get("name"))
    if discipleship:
        add("discipleship", f"Inscrita en Discipulado · {discipleship.get('module_name_snapshot') or 'Formación'}", discipleship.get("enrolled_at"), None, discipleship.get("cohort_name_snapshot"))
    for row in group_rows:
        add("front_group", f"Grupo Frontal · {groups.get(row['front_group_id']) or 'Grupo'}", row.get("started_at") or row.get("created_at"), None,
            {"leader": "Líder", "co_leader": "Colíder"}.get(row.get("role"), "Integrante"))
    milestones.sort(key=lambda row: str(row["at"]))

    # ---- pasos de Consolidación
    steps = []
    for stage in stages:
        state = stage_state(stage, now)
        who = _who_completed(stage, timeline) if stage.get("status") == "completed" else None
        tasks = [{"task_id": task.get("task_id"), "label": task.get("label"), "completed": bool(task.get("completed")), "completed_at": serialize(task.get("completed_at")),
                  "evidence_count": task.get("evidence_count") or 0} for task in stage.get("tasks") or []]
        steps.append({"stage_key": stage.get("stage_key"), "order": stage.get("stage_order"), "name": stage.get("stage_name"), **state,
                      "opened_at": serialize(stage.get("opened_at")), "due_at": serialize(stage.get("due_at")), "completed_at": serialize(stage.get("completed_at")),
                      "completed_by": actor_names.get(who) if who else None, "note": stage.get("skip_reason") or stage.get("completion_note") or stage.get("result"),
                      "tasks": tasks, "tasks_done": sum(1 for task in tasks if task["completed"]), "evidence_count": sum(task["evidence_count"] for task in tasks)})
    done = [step for step in steps if step["state"] == "done"]
    by_the_book = {"steps_done": len(done), "on_time": sum(1 for step in done if step["on_time"] is not False), "late": sum(1 for step in done if step["on_time"] is False),
                   "overdue_now": sum(1 for step in steps if step["state"] == "overdue"),
                   "missing_tasks": sum(1 for step in done for task in step["tasks"] if not task["completed"])}

    # ---- dónde está hoy
    if not main:
        now_state = {"key": "known", "label": "Conocida · todavía no está en Consolidación" if (first_contact or data.get("visitor_regs")) else "Registrada · sin proceso"}
    else:
        mentor_now = people_names.get(main.get("mentor_person_id"))
        status = main.get("status")
        if status in OPEN and main.get("current_stage_key") == "graduation":
            now_state = {"key": "graduation_pending", "label": "Retiro hecho · pendiente de graduación"}
        elif status == "paused":
            now_state = {"key": "paused", "label": f"En pausa{f' · mentor {mentor_now}' if mentor_now else ''}"}
        elif status in OPEN:
            now_state = {"key": "in_process", "label": f"En proceso con mentor {mentor_now}" if mentor_now else "En Consolidación sin mentor"}
        elif main.get("graduated_at"):
            now_state = {"key": "discipleship" if main.get("discipleship_enrollment_id") or discipleship else "graduated",
                         "label": "En Discipulado (Formación)" if main.get("discipleship_enrollment_id") or discipleship else "Graduada · falta inscribir en Discipulado"}
        elif status == "completed":
            now_state = {"key": "closed", "label": "Consolidación cerrada"}
        else:
            now_state = {"key": "withdrawn", "label": "Retirada del proceso"}
        current = next((step for step in steps if step["state"] in {"current", "overdue"}), None)
        if current and status in OPEN:
            now_state["step"] = current["name"]
        now_state["origin"] = origin["label"]
        now_state["since"] = serialize((assignments[-1] if assignments else {}).get("started_at") or main.get("created_at"))

    return {
        "person": {"person_id": person_id, "name": " ".join(filter(None, [(person or {}).get("nombre"), (person or {}).get("apellido")])) or "Persona",
                   "person_number": (person or {}).get("person_number")},
        "now": now_state, "origin": origin, "milestones": milestones,
        "consolidation": {"enrollment_id": main["enrollment_id"], "status": main.get("status"), "steps": steps, "by_the_book": by_the_book,
                          "timeline": [{"title": item.get("title"), "detail": item.get("detail"), "at": serialize(item.get("occurred_at")), "by": actor_names.get(item.get("actor_user_id"))}
                                       for item in timeline[-60:]][::-1]} if main else None,
        "history": [{"enrollment_id": item["enrollment_id"], "status": item.get("status"), "created_at": serialize(item.get("created_at")), "source": item.get("source")}
                    for item in enrollments if not main or item["enrollment_id"] != main["enrollment_id"]],
        "note": "Solo lectura: se arma con lo que ya guarda cada módulo.",
    }


@router.get("/{person_id}/step-by-step", response_model=dict)
async def get_step_by_step(person_id: str, current_user: dict = Depends(get_current_user)):
    from person_contact import can_read, gather, load_person
    person = await load_person(person_id)
    if not await can_read(person, current_user, await gather(person_id)):
        raise HTTPException(status_code=403, detail="Sin acceso a esta persona")
    return await step_by_step(person_id)
