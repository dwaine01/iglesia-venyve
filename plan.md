# Plan: Manual Corporativo (Interactivo) – **La Ley de las 7 Semanas**
## Casa de Oración **Ven y Ve** – Primera Iglesia del Nazareno

### Church Details
- **Nombre**: Casa de Oración Ven y Ve
- **Nombre completo**: Primera Iglesia del Nazareno
- **Pastora**: Carmen Garcia
- **Logo**: Provisto por el usuario (integrado globalmente con mezcla para transparencia)

---

## Phase 1: POC – SKIPPED
No integraciones complejas externas. Es una plataforma CRUD con Auth + contenido + seguimiento.

---

## Phase 2: Full Application Development (Manual + UI Base)
> **Estado real hoy:** La app full-stack existe y corre. Introducción y Mapa están aprobados. Se rediseñaron Dashboard/Semana/Registro/Estadísticas para evitar “plain white”, se aplicó un estilo corporativo (navy/gold/turquoise), y se verificó que **compilan y cargan**.

### Backend (FastAPI + MongoDB)
- [x] Autenticación JWT (login/me)
- [x] Endpoint base de dashboard
- [x] Infraestructura Mongo + modelos/colecciones base
- [x] Sistema de consolidación por persona (People + Person_Checklists + Person_Progress) + RBAC 3 niveles
- [x] Dashboards role-based (pastor / líder / persona)
- [x] **Lógica dinámica de estado** (Excelente / Bien / Recién Iniciado / Meta Baja) basada en **tiempo vs progreso**
- [x] Fix bug: `pwd_context` no definido (hashing con bcrypt unificado)
- [x] Fix: email de persona `@consolidado.local` (rechazado por `EmailStr`) → `@consolidados.app`
- [x] Estructura de métricas/progreso global movida a Bitácora Evangelística (leader_journal) y agregados globales en dashboard

### Frontend (React)
- [x] Login funcional
- [x] Layout con sidebar + navegación por rol
- [x] **Introducción** (animada, aprobada)
- [x] **Mapa 7 Semanas** (animado, aprobado)
- [x] Dashboard Líder actualizado (estado agregado + lista de personas con estado dinámico)
- [x] Dashboard Pastor actualizado (tabla líderes + estado dinámico agregado)
- [x] Mi Progreso (Persona) actualizado (estado dinámico + motivación + comparación real vs esperado)
- [x] Componente reutilizable `StatusBadge` + `ProgressVsExpected`
- [x] Registro de Contactos rediseñado (tabla + búsqueda + estados; datos reales)
- [x] SemanaPage (contenido y checklist UI; persistencia por persona existente)
- [~] Consistencia visual/animaciones en SemanaPage (mejorable)
- [x] Integración global de logo (Login, Layout, Dashboards, Presentación, Manual imprimible) con técnica tipo `mix-blend-mode: screen`

### Content Structure (7 Weeks)
1. **Semana 1**: Preparación / Oración Profética – Organización
2. **Semana 2**: Invasión – Contactados (NPT)
3. **Semana 3**: MCD – Asistencia
4. **Semana 4**: Liberación – LBS 1
5. **Semana 5**: Bendición – LBS 2
6. **Semana 6**: Sanidad – LBS 3
7. **Semana 7**: Retiro + Cierre (Mi llamado)

### Key Principles to Display
- Visión concreta (no abstracta)
- Procesos continuos
- Ley de la Hormiga
- Ley 30-60-100
- Persona → Discípulo → Obrero → Ministro

### User Stories (Actualizadas)
1. Como **pastor**, puedo iniciar sesión y ver **dashboard general** de líderes.
2. Como pastor, puedo entrar al dashboard de un líder y dejar **notas**.
3. Como **líder**, puedo iniciar sesión y ver mi **panel**.
4. Como líder, puedo leer la Introducción y navegar el Mapa.
5. Como líder, puedo administrar un **grupo de personas**.
6. Como líder, puedo crear/editar personas a mi cargo (incluye credenciales).
7. Como líder, puedo ver el **progreso por semana** de cada persona.
8. Como líder, puedo marcar tareas/checklists **por persona**, y que quede guardado.
9. Como líder, puedo ver **estado dinámico** por persona y un **estado agregado** de mi grupo (promedio).
10. Como **persona**, puedo ver mi progreso, completar tareas y ver un estado motivacional (Excelente/Bien/Recién Iniciado/Meta Baja).
11. Como **pastor/líder**, puedo iniciar una **presentación sincronizada** con un código de 4 dígitos, controlarla desde un dispositivo (con notas privadas) y mostrar visuales limpios a una audiencia en otra pantalla.
12. Como **pastor/líder**, puedo acceder a un **manual imprimible en tamaño Carta (8.5×11)** con índice, introducción e infografías oficiales integradas.
13. Como **pastor/líder**, puedo **descargar un PDF 100% fiel** al preview en **Carta** (mismas páginas, sin reflow, sin añadir/quitar páginas), con **márgenes uniformes** y **folios no cubiertos**.
14. Como **líder**, puedo registrar mi trabajo evangelístico global en una **Bitácora Evangelística** y ver métricas agregadas.

---

## Phase 2.5: Implementación Crítica – **Sistema de Gestión de Consolidación (Líder → Personas)**
> **Objetivo:** La plataforma deja de ser “manual personal” y pasa a ser un **CRM de consolidación**: cada líder gestiona múltiples personas y su progreso individual en las 7 semanas.

### 2.5.1 Modelo de Datos (MongoDB)
- [x] **people** (consolidados)
  - Implementado (incluye `leader_id`, `estado`, `semana_actual`, `fecha_primer_contacto`, `created_at`, `updated_at`, + campos extendidos)
- [x] **person_checklists** (tareas por persona/semana)
- [x] **person_progress** (progreso numérico por persona/semana)
- [ ] **house_visits** (opcional; si se requiere detalle por visita)

### 2.5.2 Reglas de Negocio (Consolidación)
- [x] Un líder **solo ve** y administra personas donde `leader_id == user._id`.
- [x] Cada persona tiene progreso **independiente** por semana (checklist + contadores).
- [x] Dashboard agrega métricas **de todas las personas** del líder.
- [x] **Estado dinámico automático** por persona:
  - Ritmo esperado: **49 días** (7×7)
  - Gracia: **7 días** iniciales (nunca Meta Baja)
  - Umbrales: ±10% (Excelente si va adelantado; Meta Baja si va retrasado)
- [x] **Estado agregado del líder** basado en el **promedio** del grupo.

### 2.5.3 API Endpoints (FastAPI)
- [x] `POST /api/people` crear persona (genera user tipo persona + credenciales)
- [x] `GET /api/people` listar personas del líder (+ filtros)
- [x] `GET /api/people/{id}` detalle
- [x] `PUT /api/people/{id}` editar
- [x] `DELETE /api/people/{id}` eliminar/archivar (si aplica)
- [x] `GET /api/people/{id}/progress` obtener progreso (person_progress + checklists)
- [x] `PUT/POST /api/people/{id}/progress` actualizar progreso
- [~] `POST /api/people/{id}/visits` (si aplica)
- [x] `GET /api/stats` estadísticas agregadas reales (usa Bitácora como fuente de verdad para métricas globales)
- [x] `GET /api/dashboard/role-based` dashboards por rol (pastor/líder/persona)
- [x] Endpoints de **presentación sincronizada** (estado en memoria para MVP):
  - `POST /api/presentation/session` (crear código 4 dígitos)
  - `GET /api/presentation/session/{code}` (leer estado actual)
  - `PUT /api/presentation/session/{code}` (actualizar estado desde presentador)

### 2.5.4 Frontend UX (Flujos)
- [x] **Registro de Contactos / Personas**:
  - Crear persona (form)
  - Mostrar credenciales
  - Tabla + acciones
- [x] **SemanaPage** con `personId`:
  - Checklist y progreso guardados por persona
- [x] **Dashboard (Líder)**:
  - Resumen total de personas + distribución por estado
  - Lista de personas con estado dinámico
  - Estado agregado del líder (promedio)
- [x] **Dashboard General (Pastor)**:
  - Tabla de líderes con estado dinámico agregado
  - [x] Panel “Gestión de Pastores” (Master Pastor puede crear nuevos pastores)
- [x] **Mi Progreso (Persona)**:
  - Estado dinámico + barra real vs esperado + motivación
- [x] **Presentación (Home/Join/Presenter/Audience)**:
  - Presenter: control de slides + notas privadas
  - Audience: visual limpio sincronizado por código
- [x] **Manual imprimible (Carta 8.5×11)**:
  - Introducción en 2 páginas + promesa
  - Índice (1 página)
  - Infografías integradas + logo global

---

## Phase 2.6: Refinamiento UI/Animación (Consistencia con Introducción/Mapa)
> **Objetivo:** mantener el estilo elegante corporativo navy/gold, **sin grandes áreas blancas**, con profundidad, gradientes sutiles y micro-interacciones.

- [~] Homologar fondos/gradientes en SemanaPage (sutil + textura) como Dashboard/Mapa
- [x] Estados UI motivadores (badges dinámicos + barras comparativas)
- [x] Responsive móvil aplicado ampliamente (sidebar colapsable, tablas a cards en móvil, stacking)
- [ ] Estados UI premium: loading skeletons, empty states motivadores, toasts consistentes

---

## Phase 2.7: Contenido Exacto del Transcrito (Checklist por Semana)
> **Objetivo:** que el manual refleje la lógica exacta enseñada (libros, prácticas, metas) y que el contenido sea mantenible (evitar componentes gigantes).

- [~] Revisar Semana 1–7 y asegurar menciones/acciones específicas:
  - Semana 1: lista de 30, oración 6–9am, tocar puertas, etc.
  - Semana 2: libro NPT + graduación/seguimiento
  - Semana 3–4: MCD + Liberación (LBS)
  - Semana 5: Bendición
  - Semana 6: Sanidad
  - Semana 7: Retiro + “Mi llamado”
- [ ] Extraer datos a config/JSON o endpoint para evitar SemanaPage gigante

---

## Phase 3: Testing & Bug Fixes — **COMPLETADA** ✅
> **Resultado:** QA integral de regresión ejecutado con `testing_agent` en backend y frontend. Backend 91.4% (32/35) sin bugs críticos. Frontend 95% (19/20) con un hallazgo MEDIUM que resultó ser falso positivo (botones en vista móvil `md:hidden` correctamente ocultos en desktop). Hardening RBAC aplicado.

### 3.1 Smoke test por rol (P0) — **COMPLETADA** ✅
- [x] **Pastor**: login → dashboard general con tabla líderes ✅
- [x] **Líder**: login → dashboard → Registro → CRUD persona → SemanaPage ✅
- [x] **Persona**: login → Mi Progreso con barra y estado dinámico ✅

### 3.2 RBAC / Permisos (P0) — **COMPLETADA** ✅
- [x] Líder no puede ver personas ajenas (cross-leader isolation validado)
- [x] Persona no puede acceder a endpoints de líder/pastor (hardening 403 aplicado en `/api/people` GET/POST/DELETE)
- [x] PDF: Pastor/Líder → 200, Persona → 403, sin auth → 401
- [x] Pastor accede a vistas globales

### 3.3 E2E Consolidación (P0) — **COMPLETADA** ✅
- [x] CRUD persona + sanitización `edad` (`'' → null`) + emails `@consolidados.app`
- [x] Cálculo estado dinámico (Excelente/Bien/Recién Iniciado/Meta Baja)
- [x] Dashboard líder con distribución por estado y agregado promedio

### 3.4 E2E Presentación sincronizada (P1) — **COMPLETADA** ✅
- [x] Códigos 4 dígitos + RBAC correcto + propagación de estado
- [x] Página de audiencia con input de código funcional

### 3.5 Bitácora Evangelística (P1) — **COMPLETADA** ✅
- [x] Endpoints `/api/journal/*` funcionales + widgets dashboard

### 3.6 Exportación PDF Playwright (P0) — **COMPLETADA** ✅
- [x] Validación estructural: 29 páginas, Letter 8.5×11 (MediaBox 612×792)
- [x] Validación visual: sin truncamientos, folios siempre visibles y sin solaparse
- [x] Permisos validados (200/403/401)

### 3.7 Responsive de flujos críticos (P2) — **COMPLETADA** ✅
- [x] Sidebar colapsa en móvil; vista dual cards/tabla (md:hidden / hidden md:block) funciona

### 3.8 Reporte final QA — **COMPLETADA** ✅
- Reportes: `/app/test_reports/iteration_3.json` (backend) y `/app/test_reports/iteration_4.json` (frontend)
- Hardening aplicado: `GET/POST/DELETE /api/people` rechaza rol `persona` con 403

### 3.9 Hallazgos y acciones
- [x] **BACKEND DESIGN LOW**: Personas podían llamar a `/api/people` (lista/crear/borrar). **RESUELTO** con role check → 403 confirmado por curl.
- [x] **FRONTEND MEDIUM (FALSO POSITIVO)**: "Continuar" buttons "no visibles" → son buttons de la vista móvil (`md:hidden`). En desktop se muestran los 4 correctos; click navega correctamente a `/persona/{id}/semana/1`.

---

## Phase 4: Presentación Sincronizada – Testing E2E + “Descargar PDF” (Pedido del usuario: **C + D**) — **COMPLETADA**
> **Objetivo:** asegurar confiabilidad del motor Presentador↔Audiencia (sin race conditions) y habilitar exportación real a PDF desde el manual imprimible.

### 4.1 E2E Testing – Sincronización Presentador/Audiencia (P1) — **COMPLETADA**
- [x] Escenarios multi-cliente diseñados y ejecutados por `testing_agent` (reporte en `/app/test_reports/iteration_2.json`).
- [x] Backend API: **40/40 tests pasados (100%)**
- [x] Frontend E2E: **95%** (solo overlay cosmético del badge Emergent)
- [x] Bug latente detectado y corregido: `LOGO_IGLESIA` no estaba importado en `PresentacionImprimirPage.js`.

### 4.2 Botón “Descargar PDF” en Manual imprimible (P2) — **COMPLETADA / ESTABILIZADA**
- [x] Método definitivo: **Playwright server-side** (`GET /api/manual/pdf`) para fidelidad total.
- [x] Botón PRIMARIO: descarga directa (blob) + toasts.
- [x] Botón SECUNDARIO “Imprimir”: diálogo nativo como alternativa.
- [~] Método anterior `html2canvas/jsPDF` queda como fallback interno (sin botón visible) para escenarios offline.

### 4.3 Micro-fixes de UX solicitados — **COMPLETADA**
- [x] Slide de Introducción rediseñado horizontal
- [x] Numeración de páginas en manual imprimible

### 4.4 Bug Fix crítico — Registro de Persona (422) — **COMPLETADA**
- [x] Sanitización `edad` (`'' → null`) + normalización de username (ASCII)

### 4.5 Bitácora Evangelística del Líder — **COMPLETADA**
- [x] Back: `leader_journal` + endpoints `/api/journal/*` + stats
- [x] Front: `BitacoraPage.js` + widgets dashboard

### 4.8 PDF server-side vía Playwright — **COMPLETADA**
- [x] Endpoint `/api/manual/pdf` con Chromium headless
- [x] Inyección de token efímero en `localStorage`
- [x] Espera de imágenes + `document.fonts.ready`

### 4.10 Bug Fix crítico — PDF en blanco por backticks en CSS — **COMPLETADA**
- [x] Eliminados backticks de comentarios CSS que rompían el template literal JSX
- [x] Restaurado render de `PresentacionImprimirPage` en headless

### 4.11–4.15 Manual imprimible Carta (8.5×11) + Restauración de contenido — **COMPLETADA / CERRADA** ✅
> **Estado actualizado:** Manual final en **29 páginas**, **US Letter exacto**, sin truncamientos, sin solapes de folio, y con todas las secciones requeridas.

- [x] `.manual-page` estricta Letter en pantalla y PDF (`8.5in×11in`) + Playwright `format="Letter"`
- [x] Índice completo en 1 sola página
- [x] Eliminado `mt-auto` en bloques finales que invadían el folio
- [x] Zona segura inferior: `padding-bottom` **25mm** + cinta protectora `::before` + folio `::after`
- [x] Restauradas secciones faltantes: Operación 72, Puertas (intro), Estructura General, Estrategia de Ganar
- [x] **Validación técnica:** 29 páginas, 8.5×11, archivo ~4.6MB
- [x] **Validación visual:** folios siempre visibles, sin truncamientos, sin contenido tapado
- [x] PDF final guardado: `/app/Manual-Letter-FINAL.pdf`

---

## Phase 5: Refactorización (Mantenibilidad / Modularidad) — **POSPUESTA ESTRATÉGICAMENTE**
> **Decisión actual:** Antes de refactorizar, se ejecuta **Phase 3 (QA de regresión)**. Refactorizar sin QA introduce riesgo de regresión y no agrega valor inmediato visible.

### 5.1 Backend – Modularizar `server.py` (P2)
- [ ] Separar en routers: `auth.py`, `dashboard.py`, `people.py`, `pastors.py`, `presentation.py`, `manual_pdf.py`, `journal.py`
- [ ] Extraer utilidades: `security.py`, `schemas.py`, `db.py`
- [ ] (Opcional) Persistencia de sesiones de presentación en Mongo (vs dict en memoria)

### 5.2 Frontend – Dividir páginas grandes en componentes (P2)
- [ ] `SemanaPage.js` → extraer config + componentes
- [ ] `RegistroPage.js` → componentes tabla/filtros/modales
- [ ] `PresentacionImprimirPage.js` → `PrintCover`, `PrintTOC`, `PrintIntroPart1`, `PrintIntroPart2`, `PrintOperacion72`, `PrintPuertasIntro`, `PrintPuertaPage`, `PrintEstructura`, `PrintEstrategiaGanar`, etc. + centralizar estilos de impresión

### 5.3 QA Post-Refactor (P2)
- [ ] Smoke test por rol (Pastor/Líder/Persona)
- [ ] Validar Presentación sincronizada
- [ ] Verificar manual Carta + PDF Playwright (**29 páginas**) + folios/márgenes

---

## Status
- **Fase 2:** COMPLETADA (Manual/UI base en funcionamiento; Introducción/Mapa aprobados)
- **Fase 2.5:** COMPLETADA (Personas + progreso + dashboards RBAC + estado dinámico + gestión de pastores)
- **Fase 2.6 / 2.7:** EN PROGRESO (pulido visual y exactitud de contenido por semana)
- **Fase 3:** **COMPLETADA** ✅ (Backend 91.4% + Frontend 95%; hardening RBAC aplicado en `/api/people`; hallazgo MEDIUM frontend fue falso positivo)
- **Fase 4:** **COMPLETADA** ✅ (Presentación sincronizada validada + PDF server-side Playwright)
- **Fase 4.11–4.15:** **COMPLETADAS / CERRADAS** ✅ (Manual Carta 8.5×11 estabilizado; 29 páginas; contenido restaurado; folios y márgenes verificados técnica y visualmente)
- **Fase 5:** POSPUESTA (hasta terminar QA de regresión)
- **Bloqueadores:** ninguno técnico; nota MVP: sesiones de presentación en memoria se pierden al reiniciar backend
