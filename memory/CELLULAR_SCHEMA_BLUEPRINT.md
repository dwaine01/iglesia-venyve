# Blueprint técnico — Mega‑Bloque C Sistema Celular

## Regla rectora

**CÉLULAS DETECTAN → PUERTAS RESPONDEN → LIDERAZGO SUPERVISA**

Toda relación humana usa `person_id`; ninguna función, membresía, visita o necesidad almacena nombres libres como identidad.

## Colecciones canónicas

- `cell_networks`: red configurable, campus, director/coordinador y estado.
- `cell_network_assignments`: supervisores/coordinadores históricos por `person_id`.
- `cells`: código, red, campus, dirección, agenda, capacidad, estado, apertura, madre y notas.
- `cell_role_assignments`: líder, asistente, anfitrión e intercesor con vigencia histórica.
- `cell_memberships`: persona, célula, rol, estado, fecha de ingreso/salida y motivo de transferencia.
- `cell_meetings`: fecha/hora, tema, anfitrión, líder, visitantes, conversiones, peticiones, necesidades, tareas y resultados.
- `cell_meeting_attendance`: referencia a reunión y `person_attendance` común; persona/visitante, estado y primera visita.
- `cell_followups`: tipo, persona, necesidad, responsable, prioridad, estado, fecha, próxima acción e histórico.
- `cell_needs`: tipo estructurado, severidad, persona/célula/reunión, puerta sugerida, puerta asignada, responsable y estado.
- `cell_health_snapshots`: métricas por célula y periodo, nunca sobrescritas.
- `cell_multiplication_rules`: criterios configurables.
- `cell_multiplication_reviews`: candidata, hechos, decisión humana, fecha y supervisor.
- `cell_multiplications`: madre, hija, fecha, líder saliente y miembros transferidos.
- `cell_assignment_events`: asignación desde `ready_for_cellular`, actor, fecha, red, célula, líder y primer seguimiento.

## Attendance común

Cada asistencia celular creará/actualizará `person_attendance` con `activity_type=cell_meeting`, `source_id=meeting_id` y `cell_id`. `cell_meeting_attendance` conserva el contexto de reunión sin duplicar la fuente histórica personal.

## Scopes

- Pastor/coordinador celular: visión global según capability.
- Supervisor: redes/células asignadas.
- Líder/asistente: su célula.
- Miembro: solo su membresía y asistencia permitida.

## Contrato con Procesos y Puertas

- Bandeja: `process_enrollments.ready_for_cellular=true` sin membresía activa.
- Asignación crea membresía, evento, primer seguimiento y actualiza próximo paso de Procesos.
- Necesidad sugiere `door_key`; la asignación final siempre es editable y auditada.
- Mapeo inicial: enfermedad→6, petición urgente→1, crisis→3, nuevo creyente→5, evento→9, primera visita→2.
- Ninguna multiplicación ni asignación pastoral ocurre automáticamente.

## Migración

Idempotencia por claves `source + source_id`; se preservan registros históricos. No se detectaron colecciones celulares operativas existentes que requieran migración destructiva.