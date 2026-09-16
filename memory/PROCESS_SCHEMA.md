# Mega‑Bloque B — Schema y contratos de Procesos

## Regla canónica

Toda relación humana utiliza `person_id` de `persons`. Responsable, mentor y cobertura son `responsible_person_id`, `mentor_person_id` y `coverage_person_id`; nunca nombres libres.

## Colecciones

### `process_definitions`

- `process_key`: `seven_weeks | consolidation | mentorship | cap`
- `version`, `name`, `description`, `active`, `source`
- `stages[]`: `key`, `order`, `name`, `short_name`, `sla_hours`, `artifact`, `tasks[]`

### `process_cycles`

- `cycle_id`, `process_key`, `name`
- `start_date`, `end_date`, `capacity`, `status`
- `coordinator_person_id`, `created_by_user_id`, timestamps

### `process_enrollments`

- `enrollment_id`, `process_key`, `definition_version`
- `person_id`, `cycle_id`
- `responsible_person_id`, `mentor_person_id`
- `status`, `current_stage_key`, `progress_pct`
- `last_activity_at`, `last_contact_at`, `next_contact_at`
- `next_action`, `next_action_at`, `result`, `ready_for_cellular`
- `source`, `source_id`, audit timestamps
- Índice único parcial por `process_key + person_id + cycle_id` para estados activos.

### `process_stage_progress`

- `stage_progress_id`, `enrollment_id`, `person_id`, `process_key`
- `stage_key`, `stage_order`, `stage_name`, `status`
- `opened_at`, `due_at`, `completed_at`
- `attendance`, `attendance_at`
- `tasks[]`: `task_id`, `label`, `required`, `completed`, `completed_at`, `evidence_count`
- `result`, `notes`, `legacy_metrics`, timestamps

### `process_evidence`

- `evidence_id`, `enrollment_id`, `person_id`, `stage_key`, `task_id`
- `kind: note | link | reference`, `title`, `note`, `url`
- `created_by_user_id`, `created_at`

### `process_timeline`

- `enrollment_id`, `person_id`, `process_key`
- `event_type`, `title`, `detail`, `actor_user_id`, `occurred_at`

### `process_alert_rules`

- `rule_key`, `name`, `process_key`, `condition`
- `threshold`, `severity`, `enabled`, `visible_to`

### `process_alerts`

- `alert_id`, `rule_key`, `rule_name`, `process_key`
- `enrollment_id`, `person_id`, `responsible_person_id`
- `severity`, `fact`, `status`, detección/resolución y actor

### Mentoría

- `mentorships`: `mentorship_id`, `enrollment_id`, `person_id`, `mentor_person_id`, metas, estado, progreso, encuentros y próxima fecha.
- `mentorship_meetings`: reunión, asistencia, lección, notas, compromisos, próxima fecha y auditoría.

### CAP

- `cap_assessments`: `cap_id`, `enrollment_id`, `person_id`, responsable, dones, intereses, disponibilidad, sugerencias explicables, puerta seleccionada, cobertura, evidencia, formación continua y estado.
- `door_catalog`: las 9 Puertas institucionales con keywords operativos.

## Endpoints

### Comunes

- `GET /api/processes/catalog`
- `GET /api/processes/dashboard`
- `GET|POST /api/processes/enrollments`
- `GET|PUT /api/processes/enrollments/{enrollment_id}`
- `PUT /api/processes/enrollments/{id}/stages/{stage_key}`
- `PUT /api/processes/enrollments/{id}/stages/{stage_key}/tasks/{task_id}`
- `POST /api/processes/enrollments/{id}/evidence`
- `GET|PUT /api/processes/alerts[/{alert_id}]`
- `GET|PUT /api/processes/alert-rules[/{rule_key}]`
- `POST /api/processes/migrate`

### 7 Semanas

- `GET|POST /api/processes/cycles`
- `PUT /api/processes/cycles/{cycle_id}`
- Inscripción, progreso, asistencia, tareas, evidencia y resultados utilizan endpoints comunes.

### Consolidación

- `POST /api/processes/enrollments/{id}/contacts`
- El detalle común devuelve timeline completo.

### Mentoría

- `GET|POST /api/processes/mentorships`
- `GET /api/processes/mentorships/{mentorship_id}`
- `POST /api/processes/mentorships/{mentorship_id}/meetings`

### CAP

- `GET|POST /api/processes/cap`
- `PUT /api/processes/cap/{cap_id}`

## Automatizaciones

- Llegada/origen actualizado → crear Consolidación y primer contacto dentro de 24h.
- Semana completada → abrir siguiente etapa.
- Proceso actualizado → evaluar hechos y alertas SLA.
- 7 Semanas completadas → preparar Consolidación y CAP como `planned` si no existen.
- CAP completado → `ready_for_cellular=true` y próximo paso hacia Sistema Celular/9 Puertas.
- Ninguna regla etiqueta estado pastoral ni asigna una Puerta automáticamente.

## RBAC

- `pastor`: lectura/escritura global, reglas SLA y migración.
- `lider`: Personas creadas, propias o asignadas; solo puede asignarse a sí mismo como responsable/mentor/cobertura.
- `persona`: solo sus procesos; puede participar en tareas/evidencias, no crear ciclos, inscripciones ni reglas.
- Cambiar una asignación requiere una cuenta pastor/líder activa asociada al `person_id`.

## Migración

- `people.canonical_person_id` → inscripciones de Consolidación y 7 Semanas.
- `person_checklists` y `checklists` → tareas de etapa.
- `person_progress` y `progress` → `legacy_metrics` por semana.
- `people` queda solo lectura con marca de versión/fecha; escrituras legacy retornan 410.
- La migración es idempotente y nunca elimina la fuente legacy automáticamente.

## Deuda técnica real

1. Evidencias soportan nota/enlace/referencia; carga binaria requiere almacenamiento de objetos externo.
2. El evaluador SLA corre en escritura/consulta con throttle de 30s; alto volumen requerirá worker programado.
3. Dashboard y enriquecimiento realizan consultas por inscripción; migrar a aggregation pipelines y paginación antes de decenas de miles de casos.
4. La conexión real con Células queda intencionalmente para Mega‑Bloque C; B entrega `ready_for_cellular`.
5. Endpoints legacy de lectura permanecen temporalmente para trazabilidad de migración.