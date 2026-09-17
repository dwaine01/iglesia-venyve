"""Servicios de dominio para procesos, SLA, alertas, automatización y migración."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from bson import ObjectId
from pymongo.errors import DuplicateKeyError


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value


def serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return iso_z(value)
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items() if key != "_id"}
    return value


async def get_definition(db, process_key: str, version: int | None = None) -> dict:
    query = {"process_key": process_key, "active": True} if version is None else {"process_key": process_key, "version": version}
    definition = await db.process_definitions.find_one(query, {"_id": 0}, sort=[("version", -1)])
    if not definition:
        raise ValueError(f"Proceso no configurado: {process_key}")
    return definition


async def record_event(db, enrollment: dict, actor_user_id: str, event_type: str, title: str, detail: str = "") -> None:
    await db.process_timeline.insert_one({
        "_id": str(uuid4()),
        "enrollment_id": enrollment["enrollment_id"],
        "person_id": enrollment["person_id"],
        "process_key": enrollment["process_key"],
        "event_type": event_type,
        "title": title,
        "detail": detail,
        "actor_user_id": actor_user_id,
        "occurred_at": now_utc(),
    })


async def create_enrollment(
    db,
    process_key: str,
    person_id: str,
    responsible_person_id: str | None,
    actor_user_id: str,
    cycle_id: str | None = None,
    status: str = "active",
    next_action: str | None = None,
    next_action_at: datetime | None = None,
    source: str = "manual",
    source_id: str | None = None,
    allow_parallel_versions: bool = False,
) -> tuple[dict, bool]:
    definition = await get_definition(db, process_key)
    query = {"process_key": process_key, "person_id": person_id, "status": {"$in": ["planned", "active", "paused"]}}
    if allow_parallel_versions:
        query["definition_version"] = definition["version"]
    if cycle_id:
        query["cycle_id"] = cycle_id
    existing = await db.process_enrollments.find_one(query, {"_id": 0})
    if existing:
        return existing, False
    now = now_utc()
    first = definition["stages"][0]
    enrollment = {
        "_id": str(uuid4()),
        "enrollment_id": None,
        "process_key": process_key,
        "definition_version": definition["version"],
        "person_id": person_id,
        "cycle_id": cycle_id,
        "responsible_person_id": responsible_person_id,
        "mentor_person_id": None,
        "status": status,
        "current_stage_key": first["key"],
        "progress_pct": 0,
        "started_at": now if status == "active" else None,
        "last_activity_at": now,
        "next_action": next_action,
        "next_action_at": next_action_at,
        "result": None,
        "ready_for_cellular": False,
        "source": source,
        "source_id": source_id,
        "created_by_user_id": actor_user_id,
        "created_at": now,
        "updated_at": now,
    }
    enrollment["enrollment_id"] = enrollment["_id"]
    try:
        await db.process_enrollments.insert_one(enrollment)
    except DuplicateKeyError:
        existing = await db.process_enrollments.find_one(query, {"_id": 0})
        if existing:
            return existing, False
        raise
    stage_docs = []
    for index, stage in enumerate(definition["stages"]):
        stage_docs.append({
            "_id": str(uuid4()),
            "stage_progress_id": None,
            "enrollment_id": enrollment["enrollment_id"],
            "person_id": person_id,
            "process_key": process_key,
            "stage_key": stage["key"],
            "stage_order": stage["order"],
            "stage_name": stage["name"],
            "status": "open" if index == 0 and status == "active" else "locked",
            "opened_at": now if index == 0 and status == "active" else None,
            "due_at": now + timedelta(hours=stage.get("sla_hours", 0)) if index == 0 and stage.get("sla_hours") else None,
            "attendance": "pending",
            "attendance_at": None,
            "tasks": [
                {"task_id": task_id, "label": label, "required": required, "completed": False, "completed_at": None, "evidence_count": 0}
                for task_id, label, required in stage.get("tasks", [])
            ],
            "result": None,
            "notes": None,
            "created_at": now,
            "updated_at": now,
        })
    for item in stage_docs:
        item["stage_progress_id"] = item["_id"]
    if stage_docs:
        await db.process_stage_progress.insert_many(stage_docs)
    await record_event(db, enrollment, actor_user_id, "enrolled", "Inscripción creada", definition["name"])
    return {key: value for key, value in enrollment.items() if key != "_id"}, True


async def recalculate_enrollment(db, enrollment_id: str, actor_user_id: str, allow_automation: bool = True) -> dict:
    enrollment = await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    if not enrollment:
        raise ValueError("Inscripción no encontrada")
    definition = await get_definition(db, enrollment["process_key"], enrollment.get("definition_version"))
    stages = await db.process_stage_progress.find({"enrollment_id": enrollment_id}, {"_id": 0}).sort("stage_order", 1).to_list(100)
    completed = [item for item in stages if item.get("status") in {"completed", "skipped"}]
    next_stage = next((item for item in stages if item.get("status") not in {"completed", "skipped"}), None)
    progress = round((len(completed) / max(1, len(stages))) * 100, 1)
    now = now_utc()
    update = {"progress_pct": progress, "last_activity_at": now, "updated_at": now}
    if next_stage:
        update["current_stage_key"] = next_stage["stage_key"]
        if next_stage.get("status") == "locked" and enrollment.get("status") == "active":
            template = next((item for item in definition["stages"] if item["key"] == next_stage["stage_key"]), {})
            due_at = now + timedelta(hours=template.get("sla_hours", 0)) if template.get("sla_hours") else None
            await db.process_stage_progress.update_one(
                {"stage_progress_id": next_stage["stage_progress_id"]},
                {"$set": {"status": "open", "opened_at": now, "due_at": due_at, "updated_at": now}},
            )
    else:
        update.update({"status": "completed", "progress_pct": 100, "completed_at": now, "current_stage_key": definition["stages"][-1]["key"]})
    await db.process_enrollments.update_one({"enrollment_id": enrollment_id}, {"$set": update})
    updated = await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0})
    if allow_automation and updated.get("status") == "completed" and enrollment.get("status") != "completed":
        await record_event(db, updated, actor_user_id, "completed", "Proceso completado", "Se preparó el próximo paso operativo")
        if updated["process_key"] == "seven_weeks":
            for next_process in ("consolidation", "cap"):
                prepared, created = await create_enrollment(
                    db, next_process, updated["person_id"], updated.get("responsible_person_id"), actor_user_id,
                    status="planned", next_action="Revisar y activar próximo proceso", source="automation", source_id=enrollment_id,
                )
                if created:
                    await record_event(db, prepared, actor_user_id, "prepared", "Próximo proceso preparado", "Generado al completar 7 Semanas")
        if updated["process_key"] == "cap":
            await db.process_enrollments.update_one(
                {"enrollment_id": enrollment_id},
                {"$set": {"ready_for_cellular": True, "next_action": "Conectar con Sistema Celular y 9 Puertas", "next_action_at": None, "updated_at": now}},
            )
    return serialize(await db.process_enrollments.find_one({"enrollment_id": enrollment_id}, {"_id": 0}))


async def access_person_ids(db, current_user: dict) -> set[str] | None:
    if current_user.get("rol") == "pastor" or current_user.get("access_scope", {}).get("persons") == "all":
        return None
    if current_user.get("rol") == "persona":
        return {current_user.get("person_id")} if current_user.get("person_id") else set()
    ids = {str(item["_id"]) async for item in db.persons.find({"created_by": current_user.get("user_id")}, {"_id": 1})}
    if current_user.get("person_id"):
        ids.add(current_user["person_id"])
        assigned = await db.process_enrollments.distinct("person_id", {"$or": [
            {"responsible_person_id": current_user["person_id"]}, {"mentor_person_id": current_user["person_id"]}
        ]})
        ids.update(assigned)
    return ids


async def enrollment_in_scope(db, enrollment: dict, current_user: dict) -> bool:
    allowed = await access_person_ids(db, current_user)
    if allowed is None:
        return True
    return enrollment.get("person_id") in allowed or current_user.get("person_id") in {
        enrollment.get("responsible_person_id"), enrollment.get("mentor_person_id")
    }


def _as_utc(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def evaluate_alerts(db, force: bool = False) -> dict:
    now = now_utc()
    if not force:
        last_run = await db.process_alert_runs.find_one({"_id": "global"}, {"_id": 0, "started_at": 1})
        started_at = _as_utc(last_run.get("started_at")) if last_run else None
        if started_at and now - started_at < timedelta(seconds=30):
            return {"created": 0, "resolved": 0, "throttled": True}
    await db.process_alert_runs.update_one({"_id": "global"}, {"$set": {"started_at": now}}, upsert=True)
    rules = await db.process_alert_rules.find({"enabled": True}, {"_id": 0}).to_list(100)
    enrollments = await db.process_enrollments.find({"status": {"$in": ["active", "planned", "completed"]}}, {"_id": 0}).to_list(10000)
    created = resolved = 0
    for enrollment in enrollments:
        stages = await db.process_stage_progress.find({"enrollment_id": enrollment["enrollment_id"]}, {"_id": 0}).sort("stage_order", 1).to_list(100)
        current = next((item for item in stages if item["stage_key"] == enrollment.get("current_stage_key")), stages[0] if stages else {})
        for rule in rules:
            if rule.get("process_key") and rule["process_key"] != enrollment["process_key"]:
                continue
            condition = rule["condition"]
            threshold = rule.get("threshold", 0)
            fact = None
            if condition == "no_responsible" and not enrollment.get("responsible_person_id") and enrollment.get("status") != "completed":
                fact = "La inscripción no tiene responsable asignado."
            elif condition == "no_next_action" and not enrollment.get("next_action") and enrollment.get("status") != "completed":
                fact = "No existe una próxima acción registrada."
            elif condition == "stage_stalled" and enrollment.get("status") == "active":
                last = _as_utc(enrollment.get("last_activity_at") or enrollment.get("created_at"))
                if last and now - last >= timedelta(hours=threshold):
                    fact = f"Sin actividad registrada durante {threshold} horas."
            elif condition == "new_visitor_uncontacted" and current.get("stage_key") in {"new_visitor", "visitor_followup"} and not enrollment.get("last_contact_at"):
                started = _as_utc(enrollment.get("started_at") or enrollment.get("created_at"))
                if started and now - started >= timedelta(hours=threshold):
                    fact = "Nuevo visitante sin contacto dentro del SLA."
            elif condition == "consecutive_absences":
                attended = [item.get("attendance") for item in stages if item.get("attendance") in {"present", "absent", "excused"}]
                consecutive = 0
                for value in reversed(attended):
                    if value == "absent": consecutive += 1
                    else: break
                if consecutive >= threshold:
                    fact = f"Registra {consecutive} ausencias consecutivas."
            elif condition == "artifact_incomplete" and enrollment["process_key"] == "seven_weeks":
                mapping = {"mcd_incomplete": "week_3", "npt_incomplete": "week_4", "lbs_pending": "week_5"}
                stage_key = mapping.get(rule["rule_key"])
                stage = next((item for item in stages if item["stage_key"] == stage_key), None)
                if stage and stage.get("status") in {"open", "in_progress"}:
                    opened = _as_utc(stage.get("opened_at"))
                    if opened and now - opened >= timedelta(hours=threshold):
                        fact = f"{stage.get('stage_name')} continúa incompleto fuera del SLA."
            elif condition == "mentor_inactive" and enrollment.get("status") == "active":
                last = _as_utc(enrollment.get("last_contact_at") or enrollment.get("last_activity_at"))
                if last and now - last >= timedelta(hours=threshold):
                    fact = "No hay encuentro o contacto reciente del mentor."
            elif condition == "completed_no_cell" and enrollment.get("status") == "completed":
                if not await db.cell_memberships.find_one({"person_id": enrollment["person_id"], "active": True}):
                    fact = "Proceso completado sin conexión celular registrada."
            elif condition == "formation_no_door" and enrollment.get("status") == "completed" and enrollment["process_key"] in {"seven_weeks", "consolidation"}:
                if not await db.cap_assessments.find_one({"person_id": enrollment["person_id"], "selected_door_key": {"$nin": [None, ""]}}):
                    fact = "Formación completada sin puerta seleccionada."
            elif condition == "welcome_membership_pending" and enrollment.get("current_stage_key") == "welcome_party":
                opened = _as_utc(current.get("opened_at"))
                membership = await db.person_memberships.find_one({"person_id": enrollment["person_id"], "acceptance_signed_at": {"$exists": True}}, {"_id": 1})
                if not membership and opened and now - opened >= timedelta(hours=threshold):
                    fact = "Fiesta de Bienvenida sin Carta de Membresía registrada."
            elif condition == "mentor_lbs_unqualified" and enrollment.get("mentor_transfer_required") is True:
                fact = "El mentor actual no está autorizado para impartir LBS."
            elif condition == "retreat_delivery_pending" and enrollment.get("current_stage_key") == "retreat":
                membership = await db.person_memberships.find_one({"person_id": enrollment["person_id"]}, {"_id": 0, "certificate_delivery_status": 1})
                if membership and membership.get("certificate_delivery_status") != "delivered":
                    fact = "La entrega del certificado continúa pendiente en Retiro."
            elif condition == "discipleship_handoff_missing" and enrollment.get("retreat_completed_at") and not enrollment.get("discipleship_enrollment_id"):
                fact = "Retiro completado sin expediente de Educación / Discipulado."
            alert_query = {"rule_key": rule["rule_key"], "enrollment_id": enrollment["enrollment_id"], "status": {"$in": ["open", "acknowledged"]}}
            open_alert = await db.process_alerts.find_one(alert_query)
            if fact and not open_alert:
                alert = {
                    "_id": str(uuid4()), "alert_id": None, "rule_key": rule["rule_key"], "rule_name": rule["name"],
                    "process_key": enrollment["process_key"], "enrollment_id": enrollment["enrollment_id"],
                    "person_id": enrollment["person_id"], "responsible_person_id": enrollment.get("responsible_person_id"),
                    "severity": rule["severity"], "fact": fact, "status": "open", "detected_at": now, "updated_at": now,
                }
                alert["alert_id"] = alert["_id"]
                await db.process_alerts.insert_one(alert); created += 1
            elif not fact and open_alert:
                await db.process_alerts.update_one({"_id": open_alert["_id"]}, {"$set": {"status": "resolved", "resolved_at": now, "resolution": "Hecho operativo ya no presente", "updated_at": now}}); resolved += 1
    return {"created": created, "resolved": resolved}


async def migrate_legacy_processes(db, actor_user_id: str) -> dict:
    result = {"people_migrated": 0, "leader_records_migrated": 0, "stage_records_migrated": 0, "conflicts": []}
    legacy_people = await db.people.find({"canonical_person_id": {"$exists": True}}).to_list(10000)
    for legacy in legacy_people:
        try:
            legacy_id = str(legacy["_id"])
            responsible = None
            if legacy.get("leader_id") and ObjectId.is_valid(legacy["leader_id"]):
                leader = await db.users.find_one({"_id": ObjectId(legacy["leader_id"])}, {"_id": 0, "person_id": 1})
                responsible = leader.get("person_id") if leader else None
            consolidation, created_a = await create_enrollment(
                db, "consolidation", legacy["canonical_person_id"], responsible, actor_user_id,
                status="completed" if legacy.get("estado") == "graduado" else "active",
                next_action="Revisar próximo contacto", source="legacy_people", source_id=legacy_id,
            )
            seven, created_b = await create_enrollment(
                db, "seven_weeks", legacy["canonical_person_id"], responsible, actor_user_id,
                status="active", next_action=f"Continuar semana {legacy.get('semana_actual', 1)}", source="legacy_people", source_id=legacy_id,
            )
            week = max(1, min(7, int(legacy.get("semana_actual") or 1)))
            legacy_checklists = await db.person_checklists.find({"person_id": legacy_id}).to_list(100)
            for checklist in legacy_checklists:
                tasks = [{"task_id": item.get("id", str(uuid4())), "label": item.get("texto", "Tarea migrada"), "required": True, "completed": bool(item.get("completada")), "completed_at": checklist.get("updated_at") if item.get("completada") else None, "evidence_count": 0} for item in checklist.get("tareas", [])]
                await db.process_stage_progress.update_one(
                    {"enrollment_id": seven["enrollment_id"], "stage_key": f"week_{checklist.get('semana')}"},
                    {"$set": {"tasks": tasks, "status": "completed" if tasks and all(item["completed"] for item in tasks) else ("open" if checklist.get("semana") == week else "locked"), "updated_at": now_utc()}},
                ); result["stage_records_migrated"] += 1
            for progress in await db.person_progress.find({"person_id": legacy_id}).to_list(100):
                week_number = max(1, min(7, int(progress.get("semana") or 1)))
                metrics = {key: progress.get(key, 0) for key in ["casas_visitadas", "personas_contactadas", "personas_ganadas", "oraciones_realizadas"]}
                metrics.update({key: progress.get(key) for key in ["validacion_leyo_libro", "validacion_hizo_oraciones", "validacion_visito_casas"] if key in progress})
                await db.process_stage_progress.update_one(
                    {"enrollment_id": seven["enrollment_id"], "stage_key": f"week_{week_number}"},
                    {"$set": {"legacy_metrics": metrics, "legacy_notes": progress.get("notas"), "updated_at": now_utc()}},
                )
                result["stage_records_migrated"] += 1
            await recalculate_enrollment(db, seven["enrollment_id"], actor_user_id)
            await db.people.update_one({"_id": legacy["_id"]}, {"$set": {"process_migration_version": 1, "process_migrated_at": now_utc()}})
            if created_a or created_b: result["people_migrated"] += 1
        except Exception as exc:
            result["conflicts"].append({"source": "people", "source_id": str(legacy["_id"]), "detail": str(exc)})
    users = await db.users.find({"person_id": {"$exists": True}}).to_list(10000)
    for user in users:
        uid = str(user["_id"])
        if not await db.checklists.find_one({"user_id": uid}) and not await db.progress.find_one({"user_id": uid}):
            continue
        try:
            responsible = user.get("person_id")
            enrollment, created = await create_enrollment(db, "seven_weeks", user["person_id"], responsible, actor_user_id, status="active", source="legacy_user_weeks", source_id=uid)
            for checklist in await db.checklists.find({"user_id": uid}).to_list(100):
                tasks = [{"task_id": item.get("id", str(uuid4())), "label": item.get("texto", "Tarea migrada"), "required": True, "completed": bool(item.get("completada")), "completed_at": checklist.get("updated_at") if item.get("completada") else None, "evidence_count": 0} for item in checklist.get("tareas", [])]
                await db.process_stage_progress.update_one({"enrollment_id": enrollment["enrollment_id"], "stage_key": f"week_{checklist.get('semana')}"}, {"$set": {"tasks": tasks, "updated_at": now_utc()}})
            for progress in await db.progress.find({"user_id": uid}).to_list(100):
                week_number = max(1, min(7, int(progress.get("semana") or 1)))
                metrics = {key: progress.get(key, 0) for key in ["casas_visitadas", "personas_contactadas", "personas_ganadas", "oraciones_realizadas"]}
                await db.process_stage_progress.update_one(
                    {"enrollment_id": enrollment["enrollment_id"], "stage_key": f"week_{week_number}"},
                    {"$set": {"legacy_metrics": metrics, "updated_at": now_utc()}},
                )
                result["stage_records_migrated"] += 1
            await recalculate_enrollment(db, enrollment["enrollment_id"], actor_user_id)
            if created: result["leader_records_migrated"] += 1
        except Exception as exc:
            result["conflicts"].append({"source": "users", "source_id": uid, "detail": str(exc)})
    result["conflict_count"] = len(result["conflicts"])
    return result


async def ensure_process_indexes(db) -> None:
    await db.process_definitions.create_index([("process_key", 1), ("version", -1)], unique=True)
    await db.process_cycles.create_index("cycle_id", unique=True)
    await db.process_enrollments.create_index("enrollment_id", unique=True)
    await db.process_enrollments.create_index([("process_key", 1), ("person_id", 1), ("status", 1)])
    await db.process_enrollments.create_index(
        [("process_key", 1), ("person_id", 1), ("cycle_id", 1)],
        unique=True,
        partialFilterExpression={"status": {"$in": ["planned", "active", "paused"]}},
        name="unique_active_process_enrollment",
    )
    await db.process_stage_progress.create_index([("enrollment_id", 1), ("stage_key", 1)], unique=True)
    await db.process_evidence.create_index("evidence_id", unique=True)
    await db.process_timeline.create_index([("person_id", 1), ("occurred_at", -1)])
    await db.process_alert_rules.create_index("rule_key", unique=True)
    await db.process_alerts.create_index([("status", 1), ("severity", 1), ("responsible_person_id", 1)])
    await db.mentorships.create_index("mentorship_id", unique=True)
    await db.mentorship_meetings.create_index([("mentorship_id", 1), ("occurred_at", -1)])
    await db.cap_assessments.create_index("cap_id", unique=True)
    await db.door_catalog.create_index("door_key", unique=True)