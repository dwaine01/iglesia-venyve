# Blueprint de Migración — Iglesia OS

## Regla congelada

**UNA PERSONA → UN PERFIL 360 → MUCHOS DOMINIOS → PERMISOS DIFERENTES**

`persons._id` es el identificador humano canónico. Las cuentas, procesos, familias, hogares, ministerios, células, asistencia y finanzas solo lo referencian; nunca crean perfiles humanos alternos.

## Hallazgos de la auditoría

1. `persons` y Perfil 360 ya forman un núcleo canónico sólido.
2. `users` todavía existía como identidad humana paralela sin `person_id`.
3. `people` es una proyección heredada de Consolidación/Ley7 y usaba su propio `_id` como si fuera una Persona.
4. Familia canónica, Household, talentos y Ministerios ya referencian `person_id`.
5. Dashboards y páginas de 7 Semanas siguen leyendo `people`, `person_checklists` y `person_progress`; pertenecen al Mega‑Bloque B.
6. El manual y las diapositivas son contenido editorial, no fuente operativa; sus listas no deben alimentar métricas ni estados.

## Estrategia de migración

### Mega‑Bloque A — CORE

- Enlazar cada `users._id` con un único `persons._id` mediante `users.person_id`.
- Enlazar cada registro heredado `people._id` mediante `people.canonical_person_id`.
- Mantener índices únicos parciales para impedir que dos cuentas reclamen la misma Persona.
- Migrar de forma idempotente nombre, contacto y ocupación hacia dominios canónicos.
- Detectar duplicados y referencias huérfanas sin fusionar automáticamente candidatos ambiguos.
- Administrar roles, estado de cuenta, capabilities y scope desde Gobierno del Núcleo.
- Incrementar `token_version` al cambiar acceso para revocar sesiones previas.

### Mega‑Bloque B — PROCESOS

- Reemplazar `people` como fuente humana por `seven_week_enrollments.person_id`.
- Crear catálogos versionados para semanas, tareas, CAP, Mentoría y Consolidación.
- Migrar `person_checklists` y `person_progress` a inscripciones canónicas.
- Convertir `SemanaPage`, `RegistroPage` y dashboards en vistas del motor de procesos.

**Estado 2026-09-16: COMPLETADO.** Motor común, 7 Semanas, Consolidación, Mentoría, CAP, SLA, alertas, dashboard, automatizaciones y Perfil 360 conectados. Las rutas legacy de escritura retornan 410 y la migración canónica es idempotente.

### Mega‑Bloque C — SISTEMA CELULAR

- Crear Redes, Células, gobierno, membresías de célula, reuniones, asistencia y multiplicación.
- Toda membresía utiliza `person_id`; líderes y supervisores son asignaciones, no perfiles.

**Siguiente bloque autorizado:** implementar Redes, Células, gobierno, reuniones, asistencia, seguimiento y multiplicación conectando `ready_for_cellular` sin duplicar Personas.

### Mega‑Bloques D–H

- D: 9 Puertas operativas conectadas con Personas y Células.
- E: eventos, check‑in y voluntariado.
- F: cuidado pastoral, visitación y Operación 72.
- G: contribuciones, presupuestos y cierres con RBAC financiero.
- H: tableros, automatizaciones y asistencia de IA sobre fuentes reales.

## Contratos de integridad

- Ningún endpoint nuevo puede insertar una Persona sin búsqueda de duplicados e idempotencia.
- Ningún módulo guarda nombre/teléfono como identidad primaria si puede resolverlos por `person_id`.
- Las eliminaciones de cuenta son desactivaciones; el Perfil 360 permanece.
- Toda migración registra ejecución, actor, conteos y conflictos.
- Todo resumen 360 indica fuente, estado real y disponibilidad.