# Blueprint — Mega‑Bloque D: 9 Puertas + Junta Directiva

## Contrato rector

**CÉLULAS DETECTAN → PUERTAS RESPONDEN → LIDERAZGO SUPERVISA**

- Una necesidad celular origina como máximo un `door_case`; nunca otra Persona ni un caso paralelo.
- Toda relación humana usa `person_id` canónico.
- Junta Directiva es una entidad formal con membresías históricas y cargos configurables.
- Supervisor de Puerta y líder operativo son asignaciones distintas; una Persona ocupa ambas solo mediante dos asignaciones explícitas.

## Colecciones

- `governance_boards`: Junta, reglas de quórum/votación, estado e histórico.
- `board_position_catalog`: cargos configurables.
- `board_memberships`: Persona, cargo, período, voto, permisos, Puertas y Ministerios.
- `door_assignments`: supervisor, líder, asistente, colaborador o servidor, con vigencia histórica.
- `door_cases`: respuesta única a una necesidad celular u otra fuente.
- `door_case_events`: bitácora inmutable de estado, Puerta, responsable y resolución.
- `board_meetings`: apertura, modalidad, moderador, secretario, agenda, tiempos y cierre.
- `board_meeting_attendance`: asistencia, consentimiento y horas de entrada/salida.
- `board_agenda_items`: puntos configurables, tiempo, discusión, decisión y documentos.
- `board_proposals`, `board_votes`: propuesta, segundo, discusión, estado y voto individual.
- `board_actions`: acuerdos y tareas con responsable, fecha y estado.
- `board_secretary_notes`, `board_secretary_note_versions`: notas humanas con autosave e histórico.
- `board_minutes`: minuta manual, borrador IA y versión oficial; IA nunca publica.
- `board_recording_uploads`, GridFS `board_recordings`/`board_recording_staging`: audio original protegido e inmutable.
- `board_transcript_versions`, `board_transcript_segments`, `board_speaker_mappings`: transcript original/final y Speaker → person_id corregible.
- `board_ai_artifacts`: resumen, minuta, acuerdos y tareas derivados con versiones fuente.

## Reglas congeladas

1. `board_memberships.person_id`, `door_assignments.person_id`, asistencia, votos, acciones y speaker mappings siempre apuntan a `persons._id`.
2. `door_cases(source_type, source_id)` es único.
3. El audio y transcript original nunca se sobrescriben.
4. Una corrección Speaker → Persona crea nueva versión derivada e invalida artefactos IA previos.
5. Notas de Secretaría son fuente humana independiente.
6. Minuta IA inicia como `ai_draft`; solo una Persona autorizada puede revisarla y publicarla como oficial.
7. Quórum se calcula con membresías activas y derecho a voto según regla de la Junta.
8. Todos los cambios relevantes producen evento de auditoría con actor y timestamp UTC.

## Jerarquía operativa

Junta Directiva → Supervisor/Encargado de Puerta → Líder de Puerta → Asistente/Sublíder → Colaboradores/Servidores.

## Audio e IA

- Grabación visible con consentimiento registrado.
- Chunks secuenciales; archivo final GridFS con SHA‑256.
- STT: `gpt-4o-transcribe-diarize` con labels Speaker 1..N.
- Identidad sugerida/corregida aparte mediante `board_speaker_mappings`.
- Minuta/análisis: `gpt-5.4-mini` sobre agenda, asistencia, transcript final, notas humanas, votos, acuerdos y tareas.