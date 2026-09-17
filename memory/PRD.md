# PRD — Iglesia OS Ven y Ve

## 1. Declaración del producto

Transformar la plataforma actual en el **Sistema Operativo Integral de la Iglesia**: una base institucional única para identidad, procesos de discipulado, sistema celular, respuesta pastoral, operaciones, cuidado, finanzas y automatización.

El trabajo se ejecuta en **PASOS AGIGANTADOS**: auditoría, diseño, implementación backend + frontend, migración, pruebas completas y continuación al siguiente Mega‑Bloque. No se entregan micro‑funciones aisladas ni se usa contenido estático como fuente operativa.

## 2. Regla arquitectónica FROZEN

**UNA PERSONA → UN PERFIL 360 → MUCHOS DOMINIOS → PERMISOS DIFERENTES**

- `persons._id` es el identificador humano canónico.
- La URL oficial de la identidad es `/personas/{person_id}`.
- Cuentas, familias, hogares, ministerios, procesos, células, asistencia, cuidado y finanzas referencian `person_id`.
- Ningún módulo crea una identidad humana alterna.
- `users` representa acceso/autenticación; no sustituye a Persona.
- `people` es una proyección heredada de Consolidación/Ley7; debe conservar `canonical_person_id` hasta su migración al motor de procesos.
- Las vistas editoriales o doctrinales nunca alimentan métricas ni estados.
- Las eliminaciones de cuenta son desactivaciones; el Perfil 360 permanece.
- Los candidatos ambiguos nunca se fusionan automáticamente.

## 3. Personas usuarias

- **Pastor:** gobierno institucional, integridad del núcleo, administración de acceso y visión global.
- **Líder:** gestión de Personas dentro de su scope, procesos, células y equipos autorizados.
- **Persona:** acceso a su propio Perfil 360 y dominios personales autorizados.
- **Roles especializados futuros:** cuidado, finanzas, eventos, recepción, consolidación y supervisión mediante capabilities/scopes explícitos.

## 4. Principios operativos

1. MongoDB y APIs son la fuente de verdad; no los arreglos React.
2. Todo flujo humano comienza resolviendo o creando una Persona canónica.
3. Toda alta busca duplicados y usa idempotencia.
4. Cada dominio mantiene su propio historial y proyecta un resumen al Perfil 360.
5. La autorización se decide en backend mediante capability + scope.
6. Cada cambio de rol, estado o contraseña revoca sesiones anteriores mediante `token_version`.
7. Toda migración registra actor, fecha, conteos y conflictos.
8. Toda interacción y dato crítico nuevo incorpora `data-testid` único.

## 5. Arquitectura técnica

### Backend

- FastAPI modular, MongoDB con Motor y JWT HS256 revocable.
- Transporte de autenticación: JWT Bearer explícito en `Authorization`; la aplicación no emite cookies de sesión. Cookies de Cloudflare/Railway no representan una sesión de Iglesia OS.
- No existe `seed_admin` automático ni endpoint público de siembra; los accesos pastorales se administran mediante flujos autenticados y credenciales de operación controladas.
- Variables obligatorias: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `CORS_ORIGINS`, `CORS_ORIGIN_REGEX`.
- Rutas backend siempre con prefijo `/api`.
- Módulos principales:
  - `server.py`: aplicación, auth, CORS, lockout, rutas legacy y rollout.
  - `access_control.py`: roles base, capabilities y scopes.
  - `canonical_identity.py`: enlace/migración idempotente cuenta ↔ Persona ↔ legacy.
  - `core_governance.py`: integridad, migraciones y gobierno de accesos.
  - `core_person.py`: creación, búsqueda y prevención de duplicados.
  - `core_profile.py`: agregador Perfil 360.
  - `person_profile_domains.py`: contactos, direcciones, llegada, asistencia, notas e historial.
  - `person_core_expansion.py`: demografía, familia, Household, talentos y directorio.
  - `ministries.py`: catálogo, funciones y asignaciones ministeriales.

### Frontend

- React + React Router, Tailwind y componentes Shadcn/Radix.
- Sonner para notificaciones.
- Diseño institucional navy/dorado con Spectral e IBM Plex Sans.
- Navegación responsive por rol.
- Páginas operativas actuales: Dashboard, Gobierno del Núcleo, Personas, Perfil 360, Directorio de Talentos y Ministerios.

## 6. Modelo canónico actual

- `users`: cuenta, email, password hash, role, `person_id`, estado, token_version, capabilities y access_scope.
- `persons`: identidad, número VV, demografía mínima, `auth_user_id`, idempotencia y procedencia.
- `person_contacts`, `person_addresses`: datos de contacto modulares.
- `person_talents`, `talent_catalog`: ocupación y habilidades.
- `person_relationships`: parentescos bidireccionales entre Personas.
- `households`, `household_memberships`: hogares separados del parentesco.
- `ministry_catalog`, `ministry_roles`, `ministry_assignments`: Ministerios y funciones.
- `core_migrations`: bitácora de consolidación canónica.
- `login_attempts`: contador temporal y bloqueo de intentos de autenticación.
- `people`: proyección heredada enlazada por `canonical_person_id`; se reemplazará en Mega‑Bloque B.

## 7. Contratos y endpoints actuales

### Identidad y acceso

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/core/governance/integrity`
- `POST /api/core/governance/migrate`
- `GET /api/core/governance/users`
- `PUT /api/core/governance/users/{user_id}/access`

### Persona y Perfil 360

- `GET|POST /api/core/persons`
- `POST /api/core/persons/check-duplicates`
- `GET /api/core/persons/{person_id}`
- `GET /api/core/persons/{person_id}/profile`
- Endpoints de contactos, direcciones, familia, Household, llegada, asistencia, notas, historial y talentos bajo `/api/core/persons/{person_id}`.

### Directorio y Ministerios

- `GET /api/core/persons/directory/search`
- `GET|POST /api/ministries`
- `GET /api/ministries/{ministry_id}`
- `GET|POST /api/ministries/person/{person_id}/assignments`
- `PUT|DELETE /api/ministries/assignments/{assignment_id}`

## 8. Blueprint de migración

Documento operativo: `/app/memory/MIGRATION_BLUEPRINT.md`.

### Hallazgos resueltos en CORE

- Las cuentas existían sin enlace canónico.
- La proyección heredada `people` podía operar como identidad paralela.
- La creación canónica permitía continuar pese a candidatos de duplicado.
- Roles y scopes no tenían una consola institucional única.
- Los dashboards globales contaban proyecciones de procesos, no Personas canónicas.

### Estrategia ejecutada

- Añadir `users.person_id` y `persons.auth_user_id` con unicidad parcial.
- Migrar cuentas existentes al Perfil 360 en startup de forma idempotente.
- Añadir `people.canonical_person_id` y sincronizar nombre, contacto y ocupación.
- Preservar datos legacy hasta migrarlos a inscripciones de proceso.
- Impedir duplicados exactos en altas canónicas.
- Reutilizar el Perfil 360 en altas de Consolidación cuando existe coincidencia segura.
- Exponer score, huérfanos, candidatos de duplicado y versión de acceso.

## 9. Implementado

### BASE-01 — completado

- JWT validado contra el usuario actual en cada solicitud.
- Sesiones revocables mediante `token_version`.
- Usuarios inactivos rechazados inmediatamente.
- Cambios de contraseña incrementan token_version.
- Bloqueo de 15 minutos después de cinco intentos fallidos.
- CORS con orígenes explícitos y credentials habilitado.
- Timestamps UTC aware en los nuevos flujos.

### ACCESS-01 + Perfil 360 — completado

- Capabilities y scopes explícitos.
- Scope `all`, `created_by`, `assigned` y `self`.
- Persona puede consultar su propio Perfil 360 según capabilities de autoservicio.
- Redacción de campos sensibles desde backend.
- Contactos, direcciones, foto, familia, Household, llegada, asistencia, notas, historial, talentos y Ministerios agregados desde sus colecciones reales.

### Person Core Expansion — completado

- Número VV secuencial e idempotencia.
- Búsqueda de duplicados por identidad/contactos.
- Género, estado civil y grupos etarios controlados.
- Catálogo de ocupaciones y habilidades.
- Familia canónica y Household separados.
- Directorio global de Personas y talentos.

### Ministerios Centrales — completado y verificado el 2026-09-16

- Catálogo central con archivo no destructivo.
- Funciones globales/específicas.
- Múltiples asignaciones por Persona y por Ministerio.
- Indicadores de vacante y liderazgo activo.
- Navegación bidireccional al Perfil 360.

### Directorio Global de Talentos — completado y verificado el 2026-09-16

- Ruta `/directorio`.
- Búsqueda por nombre, VV, ocupación, habilidad, Ministerio y función.
- Filtros combinables por ocupación, habilidad, grupo etario, género, Ministerio y función.
- Resultados enriquecidos únicamente con dominios reales.
- Responsive sin overflow.

### MEGA‑BLOQUE A — CORE — completado y verificado el 2026-09-16

- Blueprint de migración creado.
- Todas las cuentas actuales enlazadas a una Persona canónica.
- Migración automática y manual idempotente.
- Integridad actual: 100%, cero cuentas sin Perfil 360, cero huérfanos y cero candidatos duplicados detectados.
- Gobierno del Núcleo en `/nucleo` para pastores.
- Métricas de Personas, cuentas, relaciones, Households y Ministerios.
- Tabla responsive de cuentas con rol, estado y enlace al Perfil 360.
- Cambio de rol/estado con revocación de JWT.
- Protección contra autodegradación/autodesactivación del pastor.
- Registro público no puede otorgar rol pastor.
- Eliminación de pastor convertida en desactivación no destructiva.
- Dashboards pastorales cuentan `persons` como total canónico y separan Personas en proceso.
- Prevención backend de duplicados exactos; la UI ya no ofrece “crear de todas formas”.
- Alta legacy reutiliza identidad/cuenta existente cuando la coincidencia es segura.
- Harness pytest corregido con `backend/tests/conftest.py`.
- Diálogos/sheet corregidos para accesibilidad Radix.

## 10. Verificación del Mega‑Bloque A

- Suite pública CORE: **12/12 PASS**.
- Build frontend `CI=true yarn build`: **PASS**.
- Compilación backend: **PASS**.
- Colección de regresión interna para Perfil 360, Ministerios y expansión Core: **8 pruebas recolectadas correctamente**.
- API health externa: **200**.
- CORS cross-origin permitido: origen exacto + credentials; origen no permitido sin ACAO.
- Cinco intentos fallidos: login válido posterior bloqueado; recuperación verificada tras limpiar el fixture QA.
- Migración ejecutada dos veces: cero Personas nuevas en la segunda ejecución y cero conflictos.
- Cambio de rol: token anterior rechazado con 401; rol restaurado.
- Persona QA abre su Perfil 360 propio: 200.
- Alta duplicada exacta: 409 sin aumentar el total de Personas.
- Líder en Gobierno del Núcleo: 403 y redirección de frontend.
- Screenshot desktop 1920x800: sin overflow.
- Screenshot mobile 390x844, incluyendo menú lateral: sin overflow.
- Consola final sin advertencias Radix; solo cancelaciones esperadas al navegar y Cloudflare RUM.
- Integraciones o APIs MOCKED: **ninguna**.
- Warnings no bloqueantes: source maps de `dompurify`, Browserslist desactualizado y deprecación FastAPI `on_event`.

## 11. Roadmap de Mega‑Bloques

### P0 — completado

- Mega‑Bloque A — CORE: Personas, cuentas, Perfil 360, Familias, Household, RBAC, Directorio y Ministerios unificados.

### P1 — Mega‑Bloque B — PROCESOS — completado el 2026-09-16

- Crear `process_definitions`, `process_stages`, `process_enrollments`, `process_tasks` y `process_events`.
- Implementar Ley de las 7 Semanas como motor versionado, no como página textual.
- Migrar `people`, `person_checklists` y `person_progress` hacia inscripciones por `person_id`.
- Implementar Consolidación, Mentoría y CAP sobre el mismo motor.
- Reemplazar métricas de `SemanaPage`, `RegistroPage` y dashboards por agregaciones reales.
- Añadir responsables, SLA, evidencias, alertas, historial y estados auditables.
- Integrar resúmenes de proceso en Perfil 360.

#### Resultado entregado

- Motor versionado común con cuatro procesos y etapas persistidas.
- 7 Semanas: ciclos, inscripciones, semanas, tareas, asistencia, evidencia, resultado, histórico y próximo paso.
- Consolidación: pipeline, responsable, contactos, timeline, SLA y relación con 7 Semanas.
- Mentoría: mentor/persona canónicos, reuniones, lecciones, compromisos, progreso y próximo encuentro.
- CAP: dones, intereses, disponibilidad, talentos, sugerencias explicables, selección humana, cobertura, activación, evidencia y formación continua.
- 11 reglas configurables de hechos operativos y alertas por scope.
- Dashboard por etapa, SLA, vencimiento, responsables, acciones, promedio, retención y alertas.
- Automatizaciones de llegada, avance semanal, preparación de procesos y handoff celular.
- Migración de `people`, checklists y progreso; escrituras legacy retiradas.
- Perfil 360 y navegación completamente conectados al motor real.
- Datos QA eliminados después de verificar; cero datos demo/MOCK persistidos.

#### Verificación y seguridad

- Testing agent: 22/22 checks backend/E2E PASS; selector 7 Semanas corregido y revalidado por click real.
- Build frontend PASS; backend compile/health PASS.
- Desktop 1920x800 y mobile 390x844 sin overflow.
- Auditoría de seguridad final: PASS, sin CRITICAL/HIGH/MEDIUM confirmados.
- Cierres: registro público solo Persona; scopes Person Core; notas pastorales; asignaciones; índice único; throttle SLA; SSRF proxy; herramientas demo/password/photo retiradas.
- Deuda real documentada en `/app/memory/PROCESS_SCHEMA.md`.

### Mega‑Bloque C — SISTEMA CELULAR — CERRADO 2026‑09‑16

- Redes, células, gobierno, roles y membresías históricas por `person_id`.
- `ready_for_cellular` conectado a CAP sin duplicar Persona.
- Reunión móvil con asistencia idempotente sobre `person_attendance`, visitantes canónicos, conversiones, peticiones, necesidades, tareas y resultados.
- Necesidades, seguimientos, salud, reglas configurables, revisión humana de multiplicación y genealogía.
- Dashboard por scope pastor/red/célula/Persona; contenido sensible separado mediante `cellular.sensitive.read`.
- Manual contextual centralizado y versionado con panel lateral responsive.
- Security Audit final: PASS sin issues materiales. Build, API, E2E y responsive PASS.

### Mega‑Bloque D — 9 PUERTAS + JUNTA DIRECTIVA — CERRADO FUNCIONAL 2026‑09‑16

- Contrato implementado: **CÉLULAS DETECTAN → PUERTAS RESPONDEN → LIDERAZGO SUPERVISA**.
- Cada necesidad celular crea como máximo un `door_case`; estado, Puerta y responsable se sincronizan con la fuente.
- Jerarquía real e histórica: miembro de Junta/supervisor → líder → asistente/sublíder → colaborador/servidor.
- Junta formal con cargos configurables, membresías, voto, permisos, Puertas y Ministerios relacionados.
- Dashboard, reuniones, apertura/cierre, asistencia, quórum, agenda, temporizador, propuestas, votos derivados, acuerdos y tareas.
- Notas de Secretaría con autosave/versiones; minuta manual, borrador IA y libro de minutas. IA nunca puede publicar una minuta oficial.
- Audio visible por chunks, GridFS protegido, SHA‑256, descarga restringida y conservación original.
- Documentos protegidos, MIME/tamaño controlados y descarga con RBAC.
- `MeetingTranscriptionProvider` desacopla Junta del proveedor STT; mappings Speaker→`person_id` y transcript versionado preparados.
- `BoardAIProvider` portable por HTTPS estándar; identidad pseudonimizada, fuentes no confiables delimitadas y consentimiento explícito. No existen imports, ruedas ni índices privados de Emergent en producción.
- Auditoría inmutable de mutaciones críticas, voto secreto en audit feed y RBAC específico para audio/auditoría/minutas.
- Blueprint: `/app/memory/DOORS_BOARD_SCHEMA_BLUEPRINT.md`.
- Validación actual: suite global **71 passed, 8 skipped**; regresión focal **16 passed**; test D, GridFS, documentos y modo IA BLOCKED PASS; frontend build PASS; security audit PASS.

#### Dependencia externa abierta

- **STT diarizado: BLOCKED — external credential required.**
- `OPENAI_STT_API_KEY` permanece vacío y fuera de código/frontend/documentación. Sin esa credencial no se crean speakers ni atribuciones.
- UI muestra: “Identificación de participantes pendiente de procesamiento STT diarizado.”
- No se usa `whisper-1` como sustituto.
- **Board AI: BLOCKED controlado mientras `BOARD_AI_ENDPOINT_URL`, `BOARD_AI_API_KEY` y `BOARD_AI_MODEL` no estén configurados.** Junta manual, minutas, votos, documentos y audio no dependen del proveedor IA.

### P0 — Restauración Railway — RESUELTO Y VALIDADO EN PRODUCCIÓN 2026‑09‑16

- Corregida la precedencia de configuración: Kubernetes/runtime prevalece sobre `.env` mediante `load_dotenv(..., override=False)`.
- La carga local de `.env` ahora usa una ruta relativa explícita a `server.py`, sin depender del directorio de ejecución.
- Railway Production ya recibió `CORS_ORIGINS=https://panel.iglesiavenyve.org` y un `CORS_ORIGIN_REGEX` exacto/anclado; el crash CORS original desapareció.
- Eliminados `emergentintegrations`, `litellm`, ruedas directas e índices privados después de confirmar que impedían resolver el build Railway.
- Límites no secretos de Junta ya no bloquean el boot si faltan variables: audio 24 MiB/4 horas y documentos 10 MiB, con overrides `MAX_AUDIO_BYTES`, `MAX_AUDIO_SECONDS` y `MAX_BOARD_DOCUMENT_BYTES` documentados.
- Instalación limpia pública: PASS; `pip check`: PASS; imports `server.py` y `board_ai_service.py`: PASS sin paquete Emergent.
- Uvicorn supervisado RUNNING y `/api/health` preview 200; login/auth, Junta manual y CORS de regresión PASS.
- Revisión de despliegue: PASS; auditoría de seguridad: PASS sin CRITICAL/HIGH/MEDIUM.
- Railway Production confirmado **Active** por el usuario: boot limpio, índices creados, `/api/health` 200, frontend sin errores, login pastor end‑to‑end PASS, APIs reales 200 y CORS PASS.
- `backend/.env.example` quedó rastreado con `CORS_ORIGIN_REGEX` y los tres límites `MAX_*`; validación de parseo/regex PASS y sin secretos reales.

### Sistema global de aprendizaje contextual — COMPLETADO 2026‑09‑16

- Catálogo versionado **2.0** con **32 guías** para módulos actuales A–D y herramientas: dashboards por rol, Núcleo, Personas/Perfil 360, Directorio, Ministerios, Procesos, Células, Puertas, Junta, Bitácora, Códigos, Estadísticas y Manual.
- Cada guía explica propósito, resultado, flujo, paso a paso, entradas, salidas, roles, estados, conexiones entre módulos, errores frecuentes, buenas prácticas, ejemplo y siguiente acción.
- Contenido adaptado a `pastor`, `lider` y `persona`; los pasos del recorrido también respetan rol.
- Botón único `¿Cómo funciona?`: global en AppLayout y embebido donde Células/Puertas/Junta ya tenían shell propio, sin duplicaciones.
- Panel lateral responsive con tabs Visión/Pasos/Impacto/Roles y recorrido visual que resalta controles reales; Escape, anterior, siguiente y terminar.
- Personas usa tarjetas en móvil y tabla en desktop; panel y recorrido verificados en 1920×800 y 390×844 con overflow vacío.
- Sin seguimiento persistente de progreso en esta fase y sin crear datos ficticios.
- Validación: API 32/32 PASS, variantes de rol PASS, contrato backend PASS, build frontend PASS, Mega‑Bloques C/D PASS, Testing Agent iteration 9 confirmó guías/UI; regresión posterior **11 passed** y breadcrumb Personas corregido.
- Autenticación permanece en el contrato aprobado JWT Bearer sin cookie de sesión; no existe `seed_admin` automático ni público.

### P0 — Renovación integral VEN Y VE 360 — CERRADA Y CERTIFICADA 2026‑09‑16

- Branding **VEN Y VE 360**, carrusel espiritual y lenguaje pastoral aplicados sin cambiar contratos backend, schemas, enums, APIs, RBAC ni datos.
- Capa central `/frontend/src/lib/displayLabels.js` cubre Procesos, Sistema Celular, 9 Puertas, Junta, roles, prioridades, estados, minutas, errores estructurados y claves técnicas.
- Eliminados de la presentación términos como `ready_for_cellular`, `new_visitor`, `seven_weeks`, `in_progress`, `due_soon`, `on_sla`, `follow_up_required`, `ai_draft`, SLA, Household, Dashboard y Pipeline.
- Los formularios conservan los valores internos originales en `value`/payload; únicamente sus etiquetas visibles se traducen.
- Corregido bloqueo de compilación del servidor visual en `BoardMinutesPage`; la vista quedó modularizada sin cambiar endpoints.
- Corregida recuperación de la última minuta manual en `TranscriptMinutesPanel`: guardar → recargar → volver a Audio/Minuta repuebla el editor.
- Corregidos desbordes decorativos, navegación con etiquetas truncadas, textos sin acentos y mensajes de error no humanizados.
- React Build: **PASS**. Solo permanecen warnings no bloqueantes de sourcemaps de `dompurify` y base Browserslist desactualizada.
- Frontend Jest: **17/17 PASS**. Backend pytest: **107/107 PASS**, 2 skips previstos por condiciones opcionales.
- Testing Agent iteration 10: backend público **27/27 PASS**; rutas, auth, sesión, logout, RBAC/scopes, desktop, tablet, móvil y barrido de lenguaje PASS.
- Testing Agent iteration 11: detalles reales de 7 Semanas, Célula y Junta por clic **100% PASS**; persistencia de formularios, asistencia/quórum, agenda, notas, propuesta, tarea y minuta manual PASS.
- Persona/Perfil 360, Procesos, Sistema Celular, 9 Puertas, Junta Directiva y 32 guías contextuales: **PASS**.
- Desktop 1920×800, tablet y móvil 390×844: **PASS**, sin overflow horizontal en vistas verificadas.
- Auth JWT Bearer, navegación protegida y permisos pastor/líder/persona: **PASS**.
- Datos efímeros de certificación eliminados y verificados: **0 residuos QA temporales**.
- Regresiones críticas: **0**. Reportes: `/app/test_reports/iteration_10.json` y `/app/test_reports/iteration_11.json`.

### Corrección crítica Junta + Accesos jerárquicos v1 — COMPLETADO 2026‑09‑16

- Corregida pantalla blanca de preview provocada por overlay de `ResizeObserver`; el aviso benigno ya no cubre la aplicación.
- Al abrir una reunión, Junta cambia automáticamente a **Audio/Minuta** y muestra **Ir a grabación** en la cabecera.
- `BoardRecorder` usa el API activo por bloques: `/api/board/recordings/uploads`, `chunks/{seq}` y `complete`; acepta WebM, MP4 y OGG según navegador.
- El control muestra espera de micrófono y errores legibles de permiso, dispositivo o navegador.
- Pastor crea accesos desde un Perfil 360 existente con clave temporal; primer ingreso exige cambio de clave y revoca el JWT anterior.
- Pastor puede crear coordinadores generales; coordinadores generales pueden crear líderes/personas, pero reciben 403 al intentar crear o modificar pastor/coordinador.
- Consola `/nucleo` disponible para pastor y coordinadores autorizados mediante `core.access.manage`.
- Validación: React build PASS, frontend 17/17 PASS, auth/Junta 13/13 iniciales PASS; Mega‑Bloque D volvió a PASS tras limpiar fixtures; datos temporales eliminados.
- Reporte independiente: `/app/test_reports/iteration_12.json`. El hallazgo de rutas antiguas de grabación fue corregido después del reporte y validado contra la suite activa.

### P0 — Gobierno jerárquico y confidencialidad v2 — COMPLETADO 2026‑09‑16

- Pastor es superadministrador único y decide cuántos coordinadores generales existen.
- Todo coordinador general debe completar información administrativa, cambio de clave, consentimiento electrónico de privacidad/confidencialidad, seguridad de dispositivo y deber de reportar incidentes antes de recibir acceso operativo.
- Privilegios restringidos se otorgan individualmente por el pastor: Junta Directiva/libro de minutas y Finanzas/Contabilidad. Ser coordinador general no concede estos accesos automáticamente.
- Jerarquía delegable: Pastor → Coordinador general → Director de área/ministerio/células → secretario, tesorero y equipo.
- Cada nivel solo podrá crear cuentas dentro de su alcance y delegar un subconjunto de sus propios privilegios; nunca podrá elevarse ni conceder Junta/Finanzas sin autorización pastoral.
- Finanzas deberá permitir únicamente las personas designadas explícitamente por el pastor; la cantidad no se codificará de forma rígida hasta confirmar el límite operativo.
- Implementado bloqueo backend/frontend hasta cambiar clave y firmar onboarding; `/auth/me` y onboarding permanecen disponibles durante la activación.
- Formulario administrativo: contacto preferido, contacto de emergencia, dispositivo, compromiso de servicio, cuatro aceptaciones y firma electrónica.
- Cada firma guarda snapshot de política, versión, fecha/hora, IP y agente de navegador en `access_consents`.
- Política editable/versionada por pastor y límite de accesos a Finanzas configurable desde `/nucleo`.
- Jerarquía aplicada con `parent_user_id`: pastor → coordinador → director → secretario/tesorero/equipo. Las cuentas subordinadas se limitan al mismo `organization_scope`.
- Grupos separados: `membership`, `board`, `finance`. Junta y Finanzas solo las concede el pastor; no son heredables.
- Junta exige privilegio confidencial y membresía activa simultáneamente. El bypass detectado en iteration 13 fue corregido separando capacidades de Junta de `doors.manage`.
- Validación: frontend build PASS, frontend 17/17 PASS, backend focalizado 18/18 PASS, retest jerarquía/Junta 20/20 PASS, desktop/móvil sin overflow, artefactos QA eliminados.

### P0 — Mega‑Bloque G — CONTABILIDAD Y FINANZAS — IMPLEMENTADO Y CERTIFICADO 2026‑09‑16

- Jurisdicción operativa: Columbus, Ohio, Estados Unidos; base contable de efectivo configurable.
- Contabilidad por fondos con plan de cuentas, fondos restringidos/no restringidos, períodos, asientos balanceados y auditoría inmutable.
- Ingresos con Persona 360 o anónimo, diezmos/ofrendas/donaciones, asignación dividida entre fondos, campañas, promesas, conteos y depósitos.
- Operaciones con proveedores, gastos, pagos, transferencias, presupuestos y conciliación bancaria.
- Reportes de actividad, ingresos/gastos, posición financiera, flujo de efectivo, balances por fondo, presupuesto versus real y auditoría.
- RBAC financiero explícito: Finanzas no se hereda; solo el pastor concede el grupo restringido. Segregación preparador → revisor distinto → aprobación pastoral.
- Corregida la idempotencia: múltiples contribuciones manuales sin identificador externo son válidas; duplicados reales CSV/Pushpay continúan protegidos con 409 y los orígenes externos exigen identificador.
- Corregida la navegación móvil: la notificación de bienvenida se presenta abajo, no cubre el botón de menú y el acceso a Finanzas abre correctamente en 390×844 sin overflow.
- Verificación independiente iteration 15: backend 100%, frontend 100%, health 200, build PASS, RBAC/seguridad focal PASS y respuestas MongoDB sin `_id` expuesto.
- Regresión local posterior: contribuciones manuales/split/idempotencia **2/2 PASS**, frontend **19/19 PASS**, build PASS y cero fixtures financieros QA remanentes.
- Pushpay seleccionado para donaciones/pagos. El adapter existe, pero la integración permanece explícitamente **MOCKED/BLOCKED** hasta recibir credenciales sandbox reales.
- Auditoría operativa ampliada completada contra 28 requisitos: **27 PASS, 0 PARTIAL, 0 MISSING y 1 BLOCKED (Pushpay)**. Matriz trazable en `/app/memory/FINANCE_GAP_AUDIT.md`.
- Captura diaria: permite abrir primero una sesión de conteo, registrar sobres ligados por `batch_id`, buscar Persona 360, capturar múltiples conceptos/fondos/proyectos y métodos efectivo, cheque, Zelle, ACH, transferencia, Pushpay u otro.
- Contribuyentes: ficha financiera confidencial con filtros, totales por concepto/fondo/método, elegibilidad anual configurable, carta PDF en borrador o con plantilla aprobada y auditoría de emisión.
- Correcciones: conserva original y snapshots before/after; anula asiento no contabilizado o crea reversión si está contabilizado; bloquea fechas cerradas y marca depósitos que requieren ajuste.
- Conteos/depósitos: doble conteo independiente, desglose, diferencias autorizadas, comprobante y traza contribución → conteo → depósito → banco → conciliación → contabilidad.
- Cuentas por pagar: proveedor/beneficiario, factura, vencimiento, categorías, fondo/proyecto, naturaleza fija/variable, clasificación empleado/pastor configurable, comprobante GridFS, revisión, aprobación, programación, pago y conciliación.
- Obligaciones recurrentes generan AP idempotente; no se implementó payroll ficticio.
- Fondos/proyectos/presupuesto: Pro‑Templo y Misiones, entradas/gastos/disponible/presupuesto con drill‑down; presupuestos por cuenta/fondo/ministerio/proyecto/categoría.
- Cierre mensual: checklist integral, bloqueo de movimientos en período cerrado y reapertura pastoral con motivo/auditoría.
- Certificación iteration 16 + self-test final: E2E real PASS, backend **4/4**, frontend **19/19**, build PASS, health 200, desktop/móvil sin overflow, GridFS/RBAC/auditoría PASS y **0 artefactos QA**.

### P0 — Documentos oficiales de membresía — IMPLEMENTADO; arranque corregido 2026‑09‑17

- Carnet CR80 y certificado oficial construidos con plantillas DOM/CSS/SVG, campos dinámicos, fotografía, vigencia, cargo y código QR de verificación pública.
- Emisión vinculada exclusivamente a Persona 360, descarga PDF en frontend y endpoint público `/verificar/carnet/{token}` sin exponer contacto, dirección ni información financiera.
- Acceso restringido mediante la capability explícita `membership.documents.manage`; Pastor/Pastora conserva la configuración institucional.
- Corregido el bloqueo de producción `ModuleNotFoundError: No module named 'PIL'`: `backend/requirements.txt` ahora fija `pillow==12.3.0`, dependencia requerida por `membership_documents.py`.
- Validación iteration 18: instalación virtual limpia, `pip check`, import de Pillow, import completo de `server`, regresión/E2E de membresía **5/5 PASS**, health público 200 y vista pública de token inválido PASS.
- Corregido el segundo bloqueo de build frontend: `package.json` incluía `qrcode` pero el commit no contenía su resolución en `yarn.lock`, por lo que Railway abortaba con `--frozen-lockfile`.
- Validación iteration 19: instalación Yarn desde carpeta vacía con `--frozen-lockfile` PASS, `qrcode@^1.5.4` resuelto a 1.5.4, build de producción PASS y ruta pública de verificación PASS.
- Recurrencia investigada: la primera sincronización se generó correctamente en el working tree, pero `frontend/yarn.lock` quedó fuera del commit publicado; Railway volvió a construir el lockfile antiguo y reprodujo el mismo error.
- Corrección versionada definitiva: `frontend/yarn.lock` contiene el bloque de `qrcode@^1.5.4` y sus dependencias transitivas; iteration 20 confirmó diff acotado `+89/-2`, instalación frozen limpia, build y ruta pública PASS.
- `.env` continúa excluido deliberadamente del contexto Docker para no incrustar secretos; Railway inyecta `MONGO_URL`, `DB_NAME`, JWT y CORS como variables runtime según `DEPLOYMENT.md`.
- Pendiente P0: corregir el desacople `CoreGovernancePage` → `CoreAccessTable` (`users` frente a `items`) y alinear niveles/grupos del payload con `AccessUpdate` antes de certificar la delegación del permiso.

### P1/P2 — siguientes pasos y backlog

- **P0 — Gobierno de accesos:** restaurar filas de `CoreAccessTable`, persistir concesión/revocación de `membership.documents.manage` y ejecutar regresión backend + frontend.
- **P1 — Aceptación funcional del usuario:** revisar Mega‑Bloque G ya certificado con casos reales de la oficina de la iglesia y recopilar ajustes de política/terminología.
- **P1 — Pushpay:** activar OAuth/sandbox, sincronización idempotente y mapeo contable únicamente después de recibir credenciales reales.
- **P2 — Finanzas:** pulido visual y desminificación de páginas financieras según feedback, sin alterar contratos verificados.
- **P3 — Mega‑Bloque E — Operaciones:** eventos, check‑in, asistencia y voluntariado.
- **P4 — Mega‑Bloque F — Cuidado:** casos pastorales, visitación y Operación 72.
- **P5 — Mega‑Bloque H — Automatización + IA:** workflows, alertas, dashboards y asistente sobre datos autorizados.

## 12. Próximas tareas ejecutables

1. Corregir y certificar `CoreGovernancePage/CoreAccessTable`, incluyendo persistencia real de `membership.documents.manage`.
2. Entregar Documentos Oficiales de Membresía y Mega‑Bloque G al usuario para aceptación funcional con datos reales autorizados.
3. Mantener Pushpay **MOCKED/BLOCKED** hasta recibir las credenciales sandbox.
4. Al recibir credenciales, integrar Pushpay mediante playbook verificado, probar OAuth/webhooks y generar asientos balanceados idempotentes.
5. Aplicar el pulido P2 de Finanzas y continuar con Mega‑Bloque E — Operaciones después de la aprobación funcional.

## 13. Restricciones vigentes

- No rediseñar ni debatir la regla FROZEN.
- No crear perfiles alternos para niño, familiar, cuenta, Ministerio, proceso o célula.
- No inventar estados para módulos aún no construidos.
- No usar datos de producción en pruebas destructivas.
- No usar datos estáticos del manual como fuente operativa.
- Toda nueva interacción o dato crítico debe incluir `data-testid` único.
- Frontend usa `REACT_APP_BACKEND_URL`; backend usa prefijo `/api` y variables de entorno obligatorias.