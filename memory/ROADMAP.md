# Roadmap

## P0 — Operación real

- **Completado:** RBAC deny-by-default de Junta/Finanzas y privacidad pastoral de Persona 360 certificado en Iteración 40.
- **Completado:** Coordinación General sin accesos restringidos por defecto; Finanzas y Junta aisladas con unión multirol explícita.
- Sin bloqueantes P0 pendientes dentro de este alcance; resultado retenido para revisión, sin merge ni despliegue.

## P1 — Seguimiento

- Monitorear métricas de la primera rotación y ajustar ramas elegibles.
- Validar vínculos Célula ↔ Grupo únicamente donde exista política pastoral aprobada.
- Completar revisión visual menor del módulo Finanzas.
- Corregir temporizador simultáneo de Junta (transcurrido + restante/excedido).
- Mapear hablantes de Junta a Persona 360 y completar transcripción, minuta y PDF.

## P2 — Backlog

- Centralizar comprobaciones residuales de autoridad pastoral.
- Migrar eventos FastAPI `on_event` a lifespan para retirar el warning deprecado.
- Activar Pushpay cuando existan credenciales sandbox; actualmente continúa **MOCKED**.
- Mega‑Bloque H: automatización e IA.