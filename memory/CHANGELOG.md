# Changelog

## 2026-09-23 — Reconstrucción fiel del master en revisión

- Retirados el CSS y los goldens del concepto rechazado; el adjunto exacto del usuario quedó como único master inmutable.
- Reconstruidos carnet frente/reverso y certificado con coordenadas físicas absolutas y SVGs independientes; QR solo en reverso.
- Aislados los documentos por IDs/data attributes, sin clases globales internas; preview y PDF comparten componentes.
- Comparación MASTER | IMPLEMENTACIÓN iterada y guardada; números/nombres extremos ya no se superponen.
- Iteración 53 validó backend, PDFs, dimensiones y QR; frontend 17/17, contratos 5/5 y build PASS.
- No se crearon goldens de implementación, merge ni deploy: falta aprobación visual explícita del usuario.

## 2026-09-22 — Identidad oficial Concepto A aprobada

- Reemplazada completamente la presentación del carnet y certificado por el sistema Institucional Contemporáneo elegido por el usuario.
- Implementados CR80 frente/reverso, Letter landscape, fotografía `cover`, firma dinámica, QR robusto, zoom y PDFs físicos exactos.
- Aprobación visual explícita recibida; 42 pruebas PASS, QR decodificado en ambas piezas y casos extremos sin solapes.

## 2026-09-22 — Hotfix P0 de carnet con fotografía

- Alineada la validación del carnet con la fuente canónica de fotografías de Persona 360.
- Las cargas nuevas marcan la foto actual y las fotos históricas visibles sin `is_current` también permiten emitir.
- Verificados los casos positivo, negativo sin foto, RBAC, historial, vista previa y responsive; Iteración 47 y auto-regresión PASS sin residuos QA.

## 2026-09-22 — Membresía histórica + Formación configurable

- Añadida regularización de miembros existentes desde Persona 360, sin `acceptance_signed_at` artificial ni procesos iniciales falsos.
- Implementado dominio Formación completo con programas, módulos, prerrequisitos, cohortes, docentes, sesiones, asistencia, notas, progreso, históricos, promoción, reportes y auditoría.
- Integrados Bautismo separado, evidencias privadas GridFS, certificados controlados y Discipulado legado read-only.
- Certificación: backend 280/280, Formación focal 39/39, P0 22/22, frontend 27/27, desktop/móvil y testing independiente 100%.

## 2026-09-22 — RBAC estricto de Junta y Finanzas

- Cerrada la causa raíz: grants históricos aditivos, gates por capability sin grupo, membresía de Junta sin `board.access` y reutilización de `finance.read` para Persona 360.
- Finanzas ahora requiere grupo `finance` + capability; Junta requiere grupo/capability + membresía activa + permiso del cargo. Pastora conserva acceso global y Coordinación General queda denegada por defecto.
- El historial financiero integrado en Persona 360 es exclusivamente pastoral; Finanzas/Tesorería mantiene su operación completa dentro del módulo financiero.
- Certificación: testing agent Iteración 40 (matriz 6/6 + regresión focal 37/37), frontend 26/26, build PASS, API/UI desktop-móvil PASS y cero fixtures RBAC.
- Cierre técnico Iteración 41: ampliada matriz a 16 escenarios y 104 rutas inventariadas; corregida la doble instancia móvil de `useBoardAccess`; regresión 41/41 e independiente 28/28, desktop/móvil 6/6 roles.

## 2026-09-20 — Junta Directiva: grabación estabilizada

- Corregidos temporizadores congelados, pantalla blanca al entrar en Audio/Minuta y pérdida del grabador al cambiar de pestaña.
- Audio ahora se persiste en vivo por bloques, se finaliza con SHA-256 y puede escucharse o descargarse con autenticación.
- Añadidos errores persistentes de micrófono Chrome, estados de guardado, abort seguro y auditoría.
- Validación independiente Iteración 34: backend y frontend PASS; desktop/móvil sin overflow; fixture QA eliminado sin residuos.

## 2026-09-19 — Grupos Frontales recursivos

- Archivados de forma auditable 20 Grupos QA y desactivadas sus relaciones huérfanas, preservando IDs e historial.
- Implementado árbol recursivo ilimitado, prevención de ciclos, rol dual y RBAC por subárbol.
- Añadidos trabajo grupal/delegación, reportes ascendentes, rotación semanal, vínculo Célula ↔ Grupo y autoridad de asignación de Consolidación.
- Integrados Persona 360, continuidad de Consolidación, Op. 72, Invasiones y Mapa 360 sin duplicar procesos ni infraestructura.
- Rediseñado panel de Grupos Frontales y mesa de Consolidación; botón exacto “Crear invasión”.
- Certificación: build frontend; 29 pruebas críticas; navegador desktop/móvil sin overflow; bug independiente `limit=200` corregido y recorrido raíz→hijo→nieto validado.

## 2026-09-18 — Mega‑Bloque F

- Cuidado Pastoral, bóveda AES-256, RBAC y Operación 72 certificados.