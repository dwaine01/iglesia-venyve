# Contrato congelado — Grupos Frontales

**Estado:** aprobado por el usuario.  
**Implementación:** aditiva, sin inferir jerarquías ni destruir IDs existentes.

## Naturaleza

- Estructura humana recursiva de liderazgo y ejecución, distinta de Ministerios, procesos, Puertas, Redes y Células.
- Árbol sin límite codificado de niveles: Pastora → líderes → ramas → subramas.
- Toda relación humana utiliza exclusivamente `persons._id` como `person_id`.
- Una Persona puede pertenecer al grupo superior y liderar simultáneamente su propia rama mediante asignaciones independientes.

## Célula de origen y Grupo responsable

- `source_cell_id` siempre se conserva para identificar la Célula de origen.
- Célula de origen y Grupo Frontal responsable son datos independientes.
- Solo una política/vinculación configurable puede enrutar desde una Célula a un Grupo.
- Sin vínculo aplicable, se utiliza rotación semanal, selección manual autorizada u otra regla configurada.

## Autoridad de Consolidación

- Consolidación ve Grupos disponibles, rotación semanal y propuesta de asignación.
- La rotación facilita; nunca elimina revisión, confirmación o modificación autorizada.
- Toda modificación manual exige motivo y auditoría.
- Después de confirmar, el líder frontal distribuye Grupo → rama → subrama → mentor/responsable.

## Integraciones congeladas

- Persona 360 permanece como única identidad.
- Consolidación, Operación 72 y Ley de las 7 Semanas permanecen como procesos existentes.
- Mapa 360 y `evangelism_targets` se reutilizan para Invasiones; no se crea otra infraestructura geográfica.
- El botón del panel se denomina exactamente **Crear invasión**.
- Una Persona que regresa continúa desde su último avance válido; no reinicia ni duplica expediente.

## Privacidad

- La pertenencia o liderazgo frontal nunca concede acceso a Cuidado Pastoral.
- Notas, bóveda y expedientes pastorales conservan capabilities y asignaciones propias.
- Los reportes frontales solo reciben hechos operativos mínimos, nunca contenido confidencial.

## Migración

- Los 20 Grupos QA aprobados se archivan, nunca se eliminan.
- Sus IDs e historial permanecen trazables.
- No se convierten en raíces, no participan en rotaciones, selectores, métricas ni reportes activos.
- Toda jerarquía real futura se crea seleccionando Personas reales desde Persona 360.

## Estado de implementación — 2026-09-19

- Fases 0–9 implementadas de forma aditiva.
- Los 20 residuos QA permanecen archivados; no existen Grupos Frontales reales activos todavía.
- Backend disponible para árbol, scope, trabajo, rotación, vínculos celulares, reportes e integraciones.
- Frontend disponible para crear raíz/subramas desde Persona 360, administrar el panel y confirmar asignaciones desde Consolidación.
- El primer paso operativo es que la Pastora cree el Grupo raíz real y seleccione su líder desde Persona 360.