# Blueprint congelado 1.1 — Mega-Bloque F: Cuidado Pastoral

**Estado:** aprobado y congelado por el usuario.  
**Regla de rollout:** implementación y pruebas locales; publicación aditiva para revisión visual en producción; sin migraciones históricas automáticas.

## Contrato funcional

- Cuidado Pastoral administra casos, asignaciones, contactos, visitas, alertas y notas confidenciales.
- Persona 360 es la única identidad. Toda relación humana usa `person_id`; Cuidado no crea Personas.
- Estados: Detectado, Asignado, Contactado, En seguimiento, Resuelto, Cerrado y Escalado.
- Escalado permanece activo hasta resolución o cierre y conserva el responsable normal.
- Un caso urgente puede escalarse inmediatamente a Pastor/Pastora o Coordinación General autorizada; actor, momento, destino y motivo quedan auditados.

## Operación 72

- Existe una sola Operación 72 histórica por `person_id`.
- `first_conversion_at` es inmutable y nunca se reemplaza por reconciliación, restauración o regreso.
- Reconciliación, restauración y regreso pueden abrir nuevos casos pastorales, pero nunca otra Operación 72.
- Pausar no borra contactos, responsables, etapas ni avances.
- Reactivar reutiliza el expediente y las inscripciones existentes de Consolidación/7 Semanas, conservando `current_stage_key`, tareas y porcentaje.
- La auditoría registra pausa, retorno, actor y etapa desde la cual continúa.

## Separación de dominios

- Operación 72: respuesta inmediata y SLA de 24/72 horas.
- Consolidación: proceso formativo.
- Cuidado Pastoral: expediente y acompañamiento.
- Solo se comparten IDs y hechos operativos mínimos; nunca notas confidenciales.

## Visitas

- Visita individual: una Persona canónica.
- Visita de hogar: `household_id` real y participantes que pertenecen al hogar al programarla.
- Cada participante conserva resultado, caso relacionado y próximo paso individual.

## Privacidad congelada

- Bóveda AES-GCM con clave versionada de entorno.
- Notas append-only; correcciones mediante adendas.
- Visibilidad `pastoral_core` y `assigned_team`.
- Cada lectura de una nota se audita.
- Nunca se proyecta contenido confidencial a Perfil 360, búsquedas, logs, alertas, notificaciones u otros módulos.
- Perfil 360 omite totalmente Cuidado para usuarios no autorizados: sin tarjetas, contadores, badges, timeline ni metadata inferible.

## RBAC

- Pastor/Pastora: autoridad global.
- Coordinación General autorizada: scope global y capacidades explícitas de Cuidado.
- Equipo asignado: solo expedientes con asignación activa y notas `assigned_team`.
- Persona sin permiso: ningún acceso, incluida su propia información pastoral.

## Alertas

- 24 horas sin responsable primario.
- 72 horas sin contacto exitoso.
- Próximo paso vencido.
- Caso urgente.
- Las alertas son idempotentes y nunca contienen notas o detalles confidenciales.

## Migración

- No hay backfill automático de notas, conversiones, casos de Puertas ni seguimientos celulares.
- Primero se entrega un dry-run de conteos sin escrituras.
- Cualquier migración ejecutable se habilitará únicamente después de la revisión en producción y una nueva aprobación explícita.
