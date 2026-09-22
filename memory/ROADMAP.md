# Roadmap

## P0 — Operación real

- **Completado:** RBAC deny-by-default de Junta/Finanzas y privacidad pastoral de Persona 360 certificado en Iteración 40.
- **Completado:** Coordinación General sin accesos restringidos por defecto; Finanzas y Junta aisladas con unión multirol explícita.
- **P0 RBAC listo para revisión manual:** cierre Iteración 41 sin FAIL/SKIP dentro de la matriz; resultado retenido, sin merge ni despliegue.
- **Completado:** membresía histórica y Formación/Educación configurable integradas con Persona 360, Bautismo y certificados preparados; Iteración 46 sin FAIL/SKIP.
- **Completado:** hotfix de emisión de carnet con fotografía visible; Iteración 47 backend/frontend y responsive PASS.

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