"""Catálogo institucional versionado para el Mega-Bloque B."""
from datetime import datetime, timezone


SEVEN_WEEK_STAGES = [
    {
        "key": "week_1", "order": 1, "name": "Preparación y oración", "short_name": "S1",
        "sla_hours": 168, "artifact": "Lista y responsable",
        "tasks": [
            ("list_30", "Registrar lista de personas a contactar", True),
            ("responsible_confirmed", "Confirmar responsable de seguimiento", True),
            ("first_action", "Registrar primera acción y próximo paso", True),
        ],
    },
    {
        "key": "week_2", "order": 2, "name": "Invasión y contacto", "short_name": "S2",
        "sla_hours": 168, "artifact": "Contacto verificable",
        "tasks": [
            ("contact_attempt", "Registrar contacto o visita", True),
            ("response_logged", "Documentar respuesta y necesidad", True),
            ("next_contact", "Definir próximo contacto", True),
        ],
    },
    {
        "key": "week_3", "order": 3, "name": "MCD", "short_name": "MCD",
        "sla_hours": 168, "artifact": "MCD completado",
        "tasks": [
            ("mcd_delivered", "Registrar entrega de MCD", True),
            ("mcd_followup", "Registrar seguimiento de MCD", True),
            ("mcd_completed", "Confirmar MCD completado", True),
        ],
    },
    {
        "key": "week_4", "order": 4, "name": "Nací Para Triunfar", "short_name": "NPT",
        "sla_hours": 168, "artifact": "NPT completado",
        "tasks": [
            ("npt_day_1", "Registrar día 1 de NPT", True),
            ("npt_day_2", "Registrar día 2 de NPT", True),
            ("npt_day_3", "Registrar día 3 de NPT", True),
            ("npt_result", "Documentar resultado de NPT", True),
        ],
    },
    {
        "key": "week_5", "order": 5, "name": "LBS · Liberación", "short_name": "LBS 1",
        "sla_hours": 168, "artifact": "LBS 1 completado",
        "tasks": [("lbs_1_session", "Registrar sesión LBS 1", True), ("lbs_1_result", "Documentar resultado", True)],
    },
    {
        "key": "week_6", "order": 6, "name": "LBS · Bendición", "short_name": "LBS 2",
        "sla_hours": 168, "artifact": "LBS 2 completado",
        "tasks": [("lbs_2_session", "Registrar sesión LBS 2", True), ("lbs_2_result", "Documentar resultado", True)],
    },
    {
        "key": "week_7", "order": 7, "name": "LBS · Sanidad", "short_name": "LBS 3",
        "sla_hours": 168, "artifact": "Resultado y próximo paso",
        "tasks": [
            ("lbs_3_session", "Registrar sesión LBS 3", True),
            ("lbs_3_result", "Documentar resultado", True),
            ("next_step_defined", "Definir próximo paso", True),
        ],
    },
]


PROCESS_DEFINITIONS = [
    {
        "process_key": "seven_weeks", "name": "Ley de las 7 Semanas", "version": 1,
        "description": "Formación y seguimiento semanal con asistencia, tareas y evidencia.",
        "stages": SEVEN_WEEK_STAGES,
    },
    {
        "process_key": "consolidation", "name": "Consolidación", "version": 1,
        "description": "Pipeline de contacto, seguimiento y conexión con próximos pasos.",
        "stages": [
            {"key": "new_visitor", "order": 1, "name": "Nuevo visitante", "short_name": "Nuevo", "sla_hours": 24, "tasks": [("first_contact", "Registrar primer contacto", True)]},
            {"key": "contacted", "order": 2, "name": "Contactado", "short_name": "Contacto", "sla_hours": 72, "tasks": [("need_identified", "Registrar necesidad y contexto", True)]},
            {"key": "first_visit", "order": 3, "name": "Primera visita", "short_name": "Visita", "sla_hours": 168, "tasks": [("visit_logged", "Registrar visita o encuentro", True)]},
            {"key": "follow_up", "order": 4, "name": "Seguimiento", "short_name": "Seguimiento", "sla_hours": 168, "tasks": [("next_action", "Definir próxima acción", True)]},
            {"key": "formation", "order": 5, "name": "Formación", "short_name": "Formación", "sla_hours": 336, "tasks": [("formation_path", "Confirmar ruta de formación", True)]},
            {"key": "ready_for_activation", "order": 6, "name": "Listo para activación", "short_name": "Activación", "sla_hours": 168, "tasks": [("cap_prepared", "Preparar evaluación CAP", True)]},
            {"key": "completed", "order": 7, "name": "Consolidación completada", "short_name": "Completado", "sla_hours": 0, "tasks": [("next_step_confirmed", "Confirmar próximo paso", True)]},
        ],
    },
    {
        "process_key": "mentorship", "name": "Mentoría", "version": 1,
        "description": "Acompañamiento individual mediante reuniones y lecciones trazables.",
        "stages": [
            {"key": "assigned", "order": 1, "name": "Mentor asignado", "short_name": "Asignación", "sla_hours": 72, "tasks": [("first_meeting_planned", "Programar primer encuentro", True)]},
            {"key": "active", "order": 2, "name": "Acompañamiento activo", "short_name": "Activo", "sla_hours": 168, "tasks": [("meeting_logged", "Registrar encuentro", True)]},
            {"key": "formation", "order": 3, "name": "Lecciones en progreso", "short_name": "Lecciones", "sla_hours": 336, "tasks": [("lesson_progress", "Actualizar progreso de lecciones", True)]},
            {"key": "completed", "order": 4, "name": "Mentoría completada", "short_name": "Completado", "sla_hours": 0, "tasks": [("outcome_logged", "Registrar resultado final", True)]},
        ],
    },
    {
        "process_key": "cap", "name": "CAP", "version": 1,
        "description": "Consolidación y Activación por Puertas: don, ubicación y evidencia de servicio.",
        "stages": [
            {"key": "assessment", "order": 1, "name": "Evaluación", "short_name": "Evaluación", "sla_hours": 168, "tasks": [("gifts_recorded", "Registrar dones e intereses", True)]},
            {"key": "door_suggested", "order": 2, "name": "Puertas sugeridas", "short_name": "Sugerencias", "sla_hours": 168, "tasks": [("suggestions_reviewed", "Revisar puertas sugeridas", True)]},
            {"key": "door_selected", "order": 3, "name": "Puerta seleccionada", "short_name": "Selección", "sla_hours": 168, "tasks": [("door_confirmed", "Confirmar puerta seleccionada", True)]},
            {"key": "activated", "order": 4, "name": "Activación", "short_name": "Activación", "sla_hours": 336, "tasks": [("service_evidence", "Registrar evidencia de servicio", True)]},
            {"key": "continuous_training", "order": 5, "name": "Formación continua", "short_name": "Formación", "sla_hours": 720, "tasks": [("training_plan", "Definir plan de formación continua", True)]},
            {"key": "completed", "order": 6, "name": "CAP completado", "short_name": "Completado", "sla_hours": 0, "tasks": [("cellular_handoff", "Preparar conexión con Sistema Celular", True)]},
        ],
    },
]


DOOR_CATALOG = [
    (1, "Intercesión Profética", "Cobertura espiritual", ["oración", "intercesión", "ayuno", "profecía"]),
    (2, "Bienvenida / Consolidación", "Recepción y seguimiento", ["bienvenida", "servicio", "acompañamiento", "hospitalidad"]),
    (3, "Cuidado Pastoral Inmediato", "Atención y consejería", ["escucha", "consejería", "cuidado", "acompañamiento"]),
    (4, "Retiros y Encuentros (LBS)", "Encuentros y restauración", ["retiros", "logística", "restauración", "oración"]),
    (5, "Mentores de Discipulado", "Formación y enseñanza", ["enseñanza", "discipulado", "mentor", "biblia"]),
    (6, "Visitación Pastoral", "Cuidado fuera del templo", ["visita", "enfermos", "familias", "acompañamiento"]),
    (7, "Multimedia y Comunicación", "Comunicación y tecnología", ["fotografía", "video", "redes", "tecnología", "diseño"]),
    (8, "Administración y Recursos", "Administración y materiales", ["administración", "finanzas", "organización", "recursos"]),
    (9, "Congresos y Eventos Especiales", "Eventos y entrenamiento", ["eventos", "congresos", "logística", "capacitación"]),
]


ALERT_RULES = [
    ("no_responsible", "Caso sin responsable", None, "no_responsible", 0, "critical"),
    ("no_next_action", "Persona sin próximo paso", None, "no_next_action", 0, "warning"),
    ("stage_stalled", "Proceso sin avance", None, "stage_stalled", 168, "warning"),
    ("new_visitor_uncontacted", "Nuevo visitante sin contacto", "consolidation", "new_visitor_uncontacted", 24, "critical"),
    ("consecutive_absences", "Ausencias consecutivas", "seven_weeks", "consecutive_absences", 2, "warning"),
    ("mcd_incomplete", "MCD incompleto", "seven_weeks", "artifact_incomplete", 168, "warning"),
    ("npt_incomplete", "NPT incompleto", "seven_weeks", "artifact_incomplete", 168, "warning"),
    ("lbs_pending", "LBS pendiente", "seven_weeks", "artifact_incomplete", 168, "warning"),
    ("mentor_inactive", "Mentor sin contacto reciente", "mentorship", "mentor_inactive", 168, "warning"),
    ("completed_no_cell", "Proceso terminado sin célula", "seven_weeks", "completed_no_cell", 0, "warning"),
    ("formation_no_door", "Formación terminada sin puerta", None, "formation_no_door", 0, "warning"),
]


async def seed_process_catalog(db) -> None:
    now = datetime.now(timezone.utc)
    for definition in PROCESS_DEFINITIONS:
        await db.process_definitions.update_one(
            {"process_key": definition["process_key"], "version": definition["version"]},
            {"$set": {**definition, "active": True, "source": "institutional_catalog", "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    for number, name, summary, keywords in DOOR_CATALOG:
        await db.door_catalog.update_one(
            {"door_key": f"door_{number}"},
            {"$set": {"number": number, "name": name, "summary": summary, "keywords": keywords, "active": True, "source": "institutional_catalog", "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    for key, name, process_key, condition, threshold, severity in ALERT_RULES:
        await db.process_alert_rules.update_one(
            {"rule_key": key},
            {"$setOnInsert": {
                "_id": key, "rule_key": key, "name": name, "process_key": process_key,
                "condition": condition, "threshold": threshold, "severity": severity,
                "enabled": True, "visible_to": ["pastor", "responsible"], "created_at": now,
            }},
            upsert=True,
        )