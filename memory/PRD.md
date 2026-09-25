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

#### Integración STT diarizada — habilitada en desarrollo

- `OPENAI_STT_API_KEY` está configurada exclusivamente en backend y nunca se expone al frontend.
- Modelo exacto `gpt-4o-transcribe-diarize`, respuesta `diarized_json` y segmentación automática verificados contra OpenAI real.
- No se usa `whisper-1` ni `EMERGENT_LLM_KEY` como sustituto de diarización.
- Validación funcional final pendiente únicamente de la grabación manual solicitada al usuario con dos hablantes reales.
- **Board AI: BLOCKED controlado mientras `BOARD_AI_ENDPOINT_URL`, `BOARD_AI_API_KEY` y `BOARD_AI_MODEL` no estén configurados.** Junta manual, minutas, votos, documentos y audio no dependen del proveedor IA.

### P0 — Restauración Railway — RESUELTO; HOTFIX DE DEPENDENCIAS 2026‑09‑21

- Corregida la precedencia de configuración: Kubernetes/runtime prevalece sobre `.env` mediante `load_dotenv(..., override=False)`.
- La carga local de `.env` ahora usa una ruta relativa explícita a `server.py`, sin depender del directorio de ejecución.
- Railway Production ya recibió `CORS_ORIGINS=https://panel.iglesiavenyve.org` y un `CORS_ORIGIN_REGEX` exacto/anclado; el crash CORS original desapareció.
- El PR #11 reintrodujo accidentalmente 130 paquetes de entorno mediante `pip freeze`, incluyendo `emergentintegrations==0.2.0` y un wheel privado de `litellm`; Railway no podía resolverlos.
- `backend/requirements.txt` fue regenerado desde un entorno limpio con 31 dependencias públicas y `reportlab==5.0.1`; no contiene índices privados, wheels directos, `emergentintegrations` ni `litellm`.
- Descarga pública de las 31 ruedas desde PyPI, instalación limpia, `pip check`, ReportLab e imports `server.py`/`board_ai_service.py`: PASS.
- Regresión de portabilidad y STT: 7/7 PASS; el proveedor diarizado continúa usando únicamente `httpx` y `OPENAI_STT_API_KEY`.
- Revisión de despliegue posterior al hotfix: PASS sin bloqueadores estáticos; producción permanece en la versión anterior hasta que el usuario publique el nuevo PR.
- Límites no secretos de Junta permanecen seguros: audio 24 MiB/4 horas y documentos 10 MiB, configurables mediante `MAX_*`.
- `backend/.env.example` conserva CORS, límites y configuración OpenAI STT sin secretos reales.

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

### Estabilización crítica de grabación de Junta — COMPLETADO 2026‑09‑20

- `BoardRecorder` muestra reloj propio y persiste bloques de audio cada 5 segundos mientras continúa grabando.
- Cambiar entre Agenda y Audio/Minuta ya no desmonta el grabador; **Ir a grabación** reposiciona el control sin pantalla blanca.
- El temporizador general se activa inmediatamente con la respuesta de apertura; `start` es idempotente y una reunión cerrada no puede reabrirse.
- Añadidos errores persistentes de Chrome/micrófono, estado de finalización, confirmación de guardado y boundary del workspace.
- Audio guardado se puede escuchar y descargar con autenticación; STT nunca bloquea grabación ni reproducción.
- P0 STT 2026‑09‑21: ventanas móviles FFmpeg, diarización progresiva, conciliación estable Hablante 1/2, versión final íntegra e inmutable y polling UI conectados.
- OpenAI real respondió correctamente con `gpt-4o-transcribe-diarize`; Iteración 35 backend/frontend 100%, build y responsive PASS, sin APIs MOCKED.
- Junta, cuentas, personas, chunks y grabaciones QA eliminados; residuos finales: `0`.

### P0 — Gobierno jerárquico y confidencialidad v2 — COMPLETADO 2026‑09‑16

- Pastor es superadministrador único y decide cuántos coordinadores generales existen.
- Todo coordinador general debe completar información administrativa, cambio de clave, consentimiento electrónico de privacidad/confidencialidad, seguridad de dispositivo y deber de reportar incidentes antes de recibir acceso operativo.
- Pastora conserva autoridad global; Junta Directiva y Finanzas se conceden explícitamente por grupo/capability. Coordinación General no recibe ninguno de esos módulos por jerarquía ni por defaults.
- Jerarquía delegable: Pastor → Coordinador general → Director de área/ministerio/células → secretario, tesorero y equipo.
- Cada nivel solo podrá crear cuentas dentro de su alcance y delegar un subconjunto de sus propios privilegios; nunca podrá elevarse ni conceder Junta/Finanzas sin autorización pastoral.
- Finanzas deberá permitir únicamente las personas designadas explícitamente por el pastor; la cantidad no se codificará de forma rígida hasta confirmar el límite operativo.
- Implementado bloqueo backend/frontend hasta cambiar clave y firmar onboarding; `/auth/me` y onboarding permanecen disponibles durante la activación.
- Formulario administrativo: contacto preferido, contacto de emergencia, dispositivo, compromiso de servicio, cuatro aceptaciones y firma electrónica.
- Cada firma guarda snapshot de política, versión, fecha/hora, IP y agente de navegador en `access_consents`.
- Política editable/versionada por pastor y límite de accesos a Finanzas configurable desde `/nucleo`.
- Jerarquía aplicada con `parent_user_id`: pastor → coordinador → director → secretario/tesorero/equipo. Las cuentas subordinadas se limitan al mismo `organization_scope`.
- Grupos separados: `membership`, `board`, `finance`. La normalización elimina del acceso efectivo capabilities financieras/de Junta que no estén respaldadas por su grupo restringido; no son heredables.
- Junta exige simultáneamente `board.access`, grupo `board`, membresía activa y permiso funcional del cargo; Coordinación o Finanzas sin concesión reciben 403.
- Cierre Iteración 41: matriz granular/inventario 16/16, regresión relacionada 41/41 e independiente 28/28 PASS; 63/63 rutas Finanzas y 41/41 rutas Junta con gate. Desktop/móvil 6/6 roles; estado Junta móvil centralizado; cero fixtures.

## Membresía histórica y Formación configurable — completado 2026-09-22

- Persona 360 permite regularizar miembros existentes sin fabricar firma, Consolidación o formación previa; conserva fecha histórica opcional, fecha/actor de regularización y auditoría before/after.
- Nuevo dominio Formación: programas/módulos configurables, prerrequisitos, cohortes, staff, sesiones, inscripción, asistencia, notas, aprobación, reposición, promoción, reportes e históricos.
- Preparación bautismal y evento real de Bautismo permanecen separados; documentos privados usan GridFS con SHA-256 y RBAC.
- Discipulado legado es read-only; Retiro futuro crea recomendación configurable y no convierte etapas antiguas automáticamente.
- Certificación Iteración 46: backend completo 280/280, focal 39/39, P0 Junta/Finanzas 22/22, frontend 27/27, agente independiente 100%, cero FAIL/SKIP y fixtures en cero.

### P0 — Mega‑Bloque G — CONTABILIDAD Y FINANZAS — IMPLEMENTADO Y CERTIFICADO 2026‑09‑16

- Jurisdicción operativa: Columbus, Ohio, Estados Unidos; base contable de efectivo configurable.
- Contabilidad por fondos con plan de cuentas, fondos restringidos/no restringidos, períodos, asientos balanceados y auditoría inmutable.
- Ingresos con Persona 360 o anónimo, diezmos/ofrendas/donaciones, asignación dividida entre fondos, campañas, promesas, conteos y depósitos.
- Operaciones con proveedores, gastos, pagos, transferencias, presupuestos y conciliación bancaria.
- Reportes de actividad, ingresos/gastos, posición financiera, flujo de efectivo, balances por fondo, presupuesto versus real y auditoría.
- RBAC financiero explícito: Finanzas requiere grupo `finance` + capability y no se hereda. El historial integrado en Persona 360 usa un gate pastoral independiente; `finance.read/manage` nunca lo habilita. Segregación preparador → revisor distinto → aprobación pastoral.
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
- Confirmación posterior en Railway: los commits publicados seguían modificando únicamente PRD/metadatos y `HEAD:frontend/yarn.lock` conservaba el hash anterior sin `qrcode`; no era una nueva falla de build. El lockfile queda marcado explícitamente como archivo versionado para que el próximo Publish incluya sus 90 altas/2 ajustes.
- Cierre confirmado por el usuario el 2026‑09‑17: Publish incluyó finalmente el lockfile, Railway desplegó el frontend sin error y `https://panel.iglesiavenyve.org` respondió HTTP 200; verificación visual de producción mostró la pantalla de acceso completa y sin overflow horizontal.
- `.env` continúa excluido deliberadamente del contexto Docker para no incrustar secretos; Railway inyecta `MONGO_URL`, `DB_NAME`, JWT y CORS como variables runtime según `DEPLOYMENT.md`.
- P0 RBAC resuelto: `CoreGovernancePage` entrega `items`, la tabla usa niveles/grupos válidos y el backend materializa/revoca capacidades delegadas sin convertir títulos operativos en roles administrativos inválidos.

### P0 — Consolidación v2: de visitante a Líder — IMPLEMENTADO 2026‑09‑17

#### Regla oficial
- Un solo motor de Consolidación con cuatro puertas inmutables: `complete_cycle`, `direct_church`, `cell`, `visitor_followup`.
- Tronco común: Nuevo/seguimiento → Oración e Invasión solo cuando aplica → MCD → NPT → Fiesta de Bienvenida → LBS 1 → LBS 2 → LBS 3 → Retiro → Educación/Discipulado.
- Fiesta es obligatoria. Membresía nace exclusivamente con la acción explícita **Firmó Carta de Membresía**, no por asistencia ni por completar Retiro.
- Retiro culmina Consolidación, registra estado de entrega documental y abre un único expediente enlazado de Discipulado.
- Liderazgo ministerial y `users.rol` permanecen separados; promoción nunca concede administración del software.

#### Reutilización y migración
- Reutilizados Persona 360, `person_arrivals`, motor de procesos, stages/tasks/timeline/evidence/alerts, Mentoría, CAP, Ministerios, Sistema Celular, membresías, certificado/carnet/QR y RBAC.
- `consolidation` definición v2 incorpora 11 etapas; `seven_weeks` queda histórico/read-only y no acepta nuevas inscripciones genéricas.
- Migración append-only `consolidation_v2_historical_links`: crea vínculo v2 con `legacy_source_snapshot`, conserva enrollment/stages originales y usa cycle_id de migración para convivir con índices activos.
- El catálogo operativo conserva `consolidation`, `discipleship`, `mentorship` y `cap`; excluye solamente el escritor legado `seven_weeks`.

#### Membresía y documentos
- Número de miembro se asigna en firma mediante contador Mongo atómico y `membership_number_registry` inmutable; es distinto de Person ID y nunca se reutiliza.
- Reintentos de firma son idempotentes y conservan número/fecha originales.
- `person_memberships` separa status, aceptación, beneficios, elegibilidad de certificado/carnet y entrega en Retiro.
- Emisión documental ahora rechaza Personas sin firma formal; membresías históricas se preservan mediante backfill `legacy_membership` y registro de números existentes.

#### Mentoría y Fiesta
- `mentor_assignments` conserva asignación actual e historial append-only con mentor anterior/nuevo, etapa, motivo, fechas y actor.
- `mentor_qualifications` define autorización LBS global o por Grupo Frontal.
- Fiesta evalúa al mentor. Si no está calificado, `mentor_transfer_required=true` y LBS queda bloqueado hasta transferencia formal a mentor autorizado.

#### Grupo Frontal
- Nueva estructura propia `front_groups`, distinta de Redes/Ministerios/Puertas/Células pero enlazable mediante `linked_structures`.
- Estado activo/inactivo, líder principal, equipo, mentores, historial de líderes, procesos organizados, personas alcanzadas y estadísticas.
- `front_group_assignments` define team/mentor/leader y conserva altas/bajas históricas.
- Líder principal puede iniciar Consolidación y promover únicamente dentro de su Grupo cuando RBAC concede la capability correspondiente.

#### Liderazgo configurable
- `leadership_requirement_catalog`: requisitos agregables, editables, activables/desactivables y retirables sin cambiar código.
- Fuentes automáticas: membresía activa, formación/Mentoría/Discipulado, CAP y servicio ministerial; requisitos manuales admiten evidencia triestado.
- Ficha de elegibilidad muestra ✓ `met`, ⚠ `pending`, ✕ `not_met`; la elegibilidad no promueve automáticamente.
- Pastora global O Líder principal del Grupo Frontal con `leadership.promote` puede aprobar; no existe doble aprobación.
- `leadership_promotions` conserva aprobador/rol/fecha/grupo/observaciones/requisitos snapshot/estado anterior→nuevo; segundo intento se bloquea.
- `person_leadership_status` registra el estado ministerial sin modificar `users.rol` ni autoasignar capabilities.

#### RBAC explícito
- Nuevas capabilities pastorales/delegables: `membership.acceptance.manage`, `consolidation.mentor.transfer`, `consolidation.retreat.close`, `front_groups.manage`, `mentor.qualifications.manage`, `leadership.requirements.manage`, `leadership.promote`.
- Backend valida capability y scope en cada acción sensible; secretaria autorizada necesita capability y pertenencia scoped cuando corresponde.
- `CoreAccessTable` permite concesión/revocación explícita con payload contractual válido y conserva grupos restringidos `membership`, `board`, `finance`.

#### Frontend y read models
- Consolidación: tablero, intake de cuatro puertas, métricas, embudo, alertas, expediente, riel de etapas, tareas y acciones formales de Fiesta/Retiro.
- Nuevas rutas: `/procesos/consolidacion/:enrollmentId`, `/procesos/discipulado`, `/grupos-frontales`, `/liderazgo`.
- Perfil 360 muestra simultáneamente Membresía, Consolidación, mentor, Discipulado y Liderazgo.
- Navegación principal retira 7 Semanas como escritor visible; rutas históricas se conservan para compatibilidad.

#### APIs principales
- `POST /api/processes/consolidation/intakes`
- `GET /api/processes/consolidation/dashboard`
- `GET /api/processes/consolidation/{id}`
- `POST /api/processes/consolidation/{id}/start`
- `POST /api/processes/consolidation/{id}/mentor/evaluate`
- `POST /api/processes/consolidation/{id}/mentor/transfer`
- `POST /api/processes/consolidation/{id}/membership-acceptance`
- `POST /api/processes/consolidation/{id}/retreat-close`
- CRUD `/api/front-groups` y calificaciones LBS
- CRUD `/api/leadership/requirements`, eligibility, evidencia y promote

#### Certificación
- Backend completo: **132 passed, 3 skipped**, sin fallas; E2E Consolidación v2 ampliado **5/5 PASS**.
- Regresión post-auditoría iteration 23: catálogo/gates + recorrido **7/7 PASS**.
- Frontend: **19/19 PASS**, build de producción PASS.
- Testing independiente: P0 RBAC, rutas públicas, Grupos Frontales, Liderazgo y móvil validados; observación de catálogo corregida para conservar Mentoría/CAP requeridos por negocio.
- Desktop 1920×800 y móvil 390×844 verificados; riel responsive sin overflow.
- Cleanup final: `persons=0`, `users=0`, `qa_people=0`, `qa_users=0`; fixtures de suite se crean/reponen por prueba y se eliminan al terminar.

### P0 — Eliminación segura de Personas y limpieza QA — IMPLEMENTADO 2026‑09‑17

- Pastor/Pastora dispone de un botón rojo visible **Eliminar Persona** en el encabezado del Perfil 360 y confirma en un diálogo explícito responsive; ya no está escondido dentro de “Acciones”.
- La operación es un archivo seguro: oculta la Persona del directorio, listados y Perfil 360, conserva historial ministerial/pastoral/financiero y registra auditoría.
- Si existe cuenta no pastoral enlazada, se desactiva y aumenta `token_version`; carnets vigentes pasan a estado inactivo.
- Se bloquea el autoarchivo y cualquier intento de eliminar un Perfil 360 enlazado a una cuenta pastoral.
- Backend `DELETE /api/core/persons/{person_id}` protegido exclusivamente por rol pastor; respuesta Pydantic sin exposición de `_id`.
- Verificación focal inicial: backend **15/15 PASS**, frontend **19/19 PASS**, build PASS y diálogo desktop 1920×800/móvil 390×844 sin overflow.
- Limpieza autorizada ejecutada sobre MongoDB local: **7 Personas QA**, **5 cuentas QA** y **307 artefactos relacionados** eliminados; `finance_settings` se preservó y solo se retiró la referencia al actor QA.
- Resultado posterior: **0 Personas QA/demo**, **0 cuentas QA/demo** y ningún registro objetivo remanente. Las pruebas futuras deben usar fixtures efímeros con cleanup.
- Certificación independiente iteration 21: backend focal **4/4 PASS**, rol pastor/403/409/cascadas/ocultamiento PASS, flujo UI público desktop+móvil PASS y cleanup final confirmó `persons_total=0`, `users_total=0`, `qa_persons=0`, `qa_users=0` en la base local de desarrollo.
- Tras feedback del usuario, se añadió en **Personas** el control pastoral visible **Limpiar muestras (N)** con conteo previo y confirmación; elimina permanentemente solo patrones QA/demo estrictos y referencias relacionadas, preservando Personas reales y configuraciones institucionales.
- Endpoints pastor-only: `GET /api/core/persons/qa-demo/summary` y `DELETE /api/core/persons/qa-demo`; líderes/personas reciben 403.
- Certificación iteration 22: backend QA cleanup y regresión pública PASS, frontend desktop/móvil PASS, diálogo sólido sin overflow, build PASS y cleanup final `remaining_people=0`, `remaining_users=0`.
- Aclaración operativa: la limpieza previa se ejecutó en la base local de desarrollo. Después de publicar esta versión, producción mostrará **Limpiar muestras (N)** para ejecutar la limpieza segura sobre los datos de Railway; muestras no reconocidas por patrón pueden eliminarse individualmente desde su Perfil 360.

### P0 — Acceso RBAC a Liderazgo/Grupos Frontales y respuesta inmediata — RESUELTO 2026‑09‑17

- Corregida la causa real de “No se pudo cargar Liderazgo/Grupo Frontal”: las vistas solicitaban `GET /api/core/persons?limit=500`, pero el contrato backend admite un máximo de 100 y respondía 422.
- Liderazgo, detalle de Grupo Frontal e intake de Consolidación usan ahora `limit=100`; los detalles estructurados de FastAPI se convierten en mensajes legibles y ya no provocan errores de renderizado React.
- Añadidas capabilities explícitas `front_groups.view` y `leadership.view`, disponibles en Gobierno del Núcleo, con guards de ruta y navegación consistentes.
- El rol pastoral legado conserva acceso maestro únicamente en los módulos correspondientes; `core.access.manage` ya no eleva a una cuenta no pastoral a autoridad global ni elude scopes.
- La política de acceso sube a versión 15 para materializar las nuevas capacidades de lectura durante el rollout.
- Las tareas del expediente de Consolidación ahora cambian visualmente de inmediato, muestran guardado individual, persisten la respuesta del servidor y revierten el cambio si la API falla; se eliminó la recarga redundante del catálogo.
- El riel de etapas dejó de depender de ancho mínimo horizontal y se adapta por cuadrícula sin overflow.
- Validación final: backend **137 passed, 3 skipped**; frontend **19/19 PASS**; build de producción PASS; health externo 200; iteration 24 backend/UI PASS; navegación y tareas verificadas en 1920×800 y 390×844 sin overflow.
- Limpieza final confirmada: **0 Personas QA y 0 cuentas QA**.

### Mapa 360 y autocompletado remoto — IMPLEMENTADO 2026‑09‑18

- Nueva ruta privada `/mapas`, accesible desde **Mapa 360** en la navegación cuando el usuario tiene permiso geográfico.
- Dos vistas principales: **Miembros y Personas** y **Células**, sobre MapLibre GL JS con mosaicos OpenStreetMap y centro institucional en 640 Demorest Rd, Columbus, OH 43204.
- Modos interactivos Densidad, Clusters y Pines; hover/click de detalle, filtros por categoría, zona, etapa, Grupo Frontal, célula y período; comparación de 90 días por zona y señal de concentración sin célula cercana.
- Cuatro zonas cardinales mutuamente exclusivas calculadas por bearing desde la iglesia: Norte, Este, Sur y Oeste.
- Geocodificación automática server-side mediante **U.S. Census Geocoding Services API**, sin cuenta ni API key. Solo se consulta al crear o cambiar una dirección; abrir o filtrar el mapa usa las coordenadas persistidas en MongoDB.
- Interfaz `GeocodingProvider` desacoplada para sustituir Census por otro proveedor sin reconstruir Mapa 360.
- Persistencia versionada: GeoJSON 2dsphere, latitude/longitude, provider, timestamp, accuracy/confidence, `address_version`, zona, verificación y estado stale.
- Cambiar una dirección archiva la ubicación anterior y genera un trabajo idempotente. Cambiar solo notas no geocodifica nuevamente. Un job antiguo no puede sobrescribir una versión nueva.
- Cola **Ubicación necesita verificación** para cero/múltiples coincidencias, baja confianza o error. Personal con `geo.manage_locations` puede reintentar Census o mover el pin; una corrección manual tiene prioridad hasta que cambie la dirección.
- Nuevas capabilities explícitas: `geo.view_aggregate`, `geo.view_precise`, `geo.manage_locations`. Los agregados aplican mínimo de privacidad y nunca incluyen nombre, teléfono, dirección o número de Persona; la vista precisa queda auditada y respeta scopes.
- Perfil 360 muestra estado de geocodificación y zona sin exponer coordenadas en sus endpoints ordinarios. Las APIs celulares ordinarias tampoco devuelven lat/lng.
- Consolidación ahora usa búsqueda remota con debounce por nombre, teléfono, correo o número VV, respeta scope y excluye automáticamente Personas archivadas o con Consolidación activa; se eliminó la limitación de las primeras 100 Personas.
- Integración real Census verificada con la dirección institucional: HTTP 200 sin API key, un match, coordenadas persistidas, `address_version=2` y exactamente un job completado.
- Validación final: backend **150 passed, 3 skipped**; contrato público Mapa 360 **10/10 PASS**; frontend **22/22 PASS**; build de producción PASS; health 200; UI desktop 1920×800 y móvil 390×844 sin overflow; iteration 25 UI PASS.
- Compatibilidad de despliegue cerrada: MapLibre 4.7.1 se sirve como asset local versionado y ya no forma parte de `package.json`; el build no depende de que la plataforma incluya cambios de `yarn.lock`.
- Datos QA finales: cuentas, Personas, células, direcciones y revisiones efímeras eliminadas.

### Hotfix de despliegue Mapa 360 — RESUELTO 2026‑09‑18

- Corregido el crash de producción al importar `geo_provider.py` sin `CENSUS_GEOCODER_URL` o `CENSUS_GEOCODER_BENCHMARK`: la API completa ahora inicia y únicamente el proveedor Census queda marcado como no configurado.
- El centro institucional aprobado tiene configuración segura de aplicación y ya no provoca un segundo crash cuando faltan `GEO_CHURCH_*` en un contenedor nuevo.
- `/api/geo/config` informa `geocoding_configured`; Mapa 360 muestra una alerta clara y desactiva el backfill mientras el endpoint Census no esté configurado.
- Corregido definitivamente el segundo bloqueo Railway: se retiraron `maplibre-gl` y `@mapbox/jsonlint-lines-primitives` de npm y MapLibre 4.7.1 quedó vendorizado en `frontend/public/vendor/`; por tanto, incluso si la automatización omite `yarn.lock`, `package.json` continúa siendo compatible con el lockfile publicado.
- Simulación exacta de producción PASS: import de `server` con todas las variables geo vacías, **349 rutas cargadas**, sin RuntimeError.
- Instalación de imagen PASS: `yarn install --frozen-lockfile` con el lockfile actual **y también con el lockfile antiguo exacto de GitHub**; Jest **22/22** y build de producción PASS.
- Runtime vendorizado PASS: `/vendor/maplibre-gl.js` HTTP 200 (803,086 bytes), `window.maplibregl.Map` disponible, canvas real en `/mapas`, escritorio 1920×800 y móvil 390×844 sin overflow.
- `.env` permanece intencionalmente excluido de la imagen; producción debe inyectar variables desde su administrador de entorno. No se modificó `.dockerignore`.
- Variables públicas para habilitar toda la función, sin API key: backend `CENSUS_GEOCODER_URL=https://geocoding.geo.census.gov/geocoder`, `CENSUS_GEOCODER_BENCHMARK=Public_AR_Current`; frontend `REACT_APP_MAP_TILE_URL=https://tile.openstreetmap.org/{z}/{x}/{y}.png`.
- RCA producción confirmado en el bundle de `panel.iglesiavenyve.org`: Railway tenía la variable frontend, pero `Dockerfile.frontend` no la declaraba como build argument y CRA compilaba `REACT_APP_MAP_TILE_URL=undefined`.
- `Dockerfile.frontend` ahora declara `ARG REACT_APP_MAP_TILE_URL` y `ENV REACT_APP_MAP_TILE_URL=$REACT_APP_MAP_TILE_URL` antes de `RUN yarn build`.
- Verificación exacta PASS: contrato/orden del Dockerfile validado, build CRA ejecutado con ambos build args y URL OSM encontrada dentro del chunk generado; auditoría de despliegue sin bloqueos.

### Mapa 360 — experiencia geográfica v2 — IMPLEMENTADO 2026‑09‑18

- Preservada la base de layout solicitada: `AppLayout` usa `main` flex-column/overflow-hidden, breadcrumb `shrink-0` y un wrapper del `Outlet` que mantiene scroll normal fuera de `/mapas`.
- En `/mapas`, el sidebar desktop se oculta automáticamente y puede restaurarse/ocultarse con `toggle-map-sidebar-button`; el mapa usa todo el ancho disponible.
- `GeoMapsPage` es una pantalla full-height: toolbar compacta de 72.5px en desktop, canvas 1920×644 y mapa móvil de más de 540px, sin overflow horizontal.
- Toolbar única con tabs Personas/Células, modos Densidad/Clusters/Pines, métricas, filtros en popover, comparación, backfill, revisión y búsqueda por nombre/número VV.
- Búsqueda remota protegida por `geo.view_precise`: debounce, respeto de scope, centrado `flyTo`, halo de resaltado y panel de detalle. Corregida la carrera que reabría resultados después de seleccionar.
- Iglesia Ven y Ve es una fuente/capa fija independiente de filtros en 640 Demorest Rd, con pin carmesí grande y símbolo propio.
- Pines estilo gota generados localmente y diferenciados: Persona ámbar, Célula verde, Grupo Frontal azul e Iglesia carmesí.
- Grupos Frontales se representan por centroide de miembros autorizados, sin dirección física; si el grupo está convertido/vinculado a una Célula, el centroide desaparece y prevalece el pin real celular.
- Zonas reforzadas visualmente: relleno 16%, límites 3.5px, cuatro colores y etiquetas Zona 1 Norte, Zona 2 Este, Zona 3 Sur y Zona 4 Oeste.
- Añadidas 12 subzonas por distancia desde la iglesia: A=0–3 millas, B=3–6 millas, C=>6 millas. Dos anillos visibles y etiquetas 1-A…4-C; `zone_number`, `subzone_key` y distancia se persisten y migran para ubicaciones existentes.
- Geocodificación automática encadenada mediante `GeocodingProvider`: Census primero y Geocodio como respaldo permanente; la cola manual queda solo si ambos fallan o la confianza es insuficiente.
- Backfill reintenta estados históricos `not_found`, `ambiguous`, `needs_verification` y `provider_error`, y resuelve automáticamente revisiones cuando Geocodio encuentra coincidencia.
- Integración real verificada con 6553 Bellmouth Rd: Census `not_found` → Geocodio `matched`, precisión `rooftop`, estado `verified`, proveedores intentados `[census, geocodio]`, subzona `4-B`.
- La `GEOCODIO_API_KEY` permanece únicamente en backend; escaneo final del código/bundle frontend: **0 filtraciones**.
- Pruebas finales: backend **157 passed, 3 skipped**, frontend **22/22**, build PASS, iteration 26 backend 19/19 y UI desktop/mobile PASS; dos selecciones móviles consecutivas confirmaron búsqueda→halo→detalle.
- Variables backend necesarias en producción: `GEOCODIO_API_URL`, `GEOCODIO_API_KEY`, `GEOCODIO_TIMEOUT_SECONDS`; nunca exponerlas como `REACT_APP_*`.

### MAPA TERRITORIAL 360 — COMPLETADO TÉCNICAMENTE — 2026‑09‑19

- Añadida normalización conservadora de direcciones físicas en `geo_address.py`: sufijos equivalentes (`Street`/`St`), mayúsculas y puntuación convergen; apartamento, suite, piso y unidad permanecen como hogares distintos.
- La vista precisa ya no emite un pin por Persona: agrupa por `normalized_address_key`, integra `household_memberships` cuando existe un único domicilio inequívoco y devuelve únicamente residentes permitidos por el scope actual.
- Geocodio mantiene el orden aprobado Census → Geocodio y exige dirección completa, ciudad/estado/ZIP coincidentes, score mínimo 0.8 y `accuracy_type` no amplio. Los resultados dudosos quedan en revisión con razones explícitas.
- Nuevo endpoint administrativo `GET /api/geo/geocoding-audit` para inventariar completitud, coordenadas, proveedor, confidence/accuracy, revisiones y asignación territorial sin exponer la API key.
- Nuevo Core `geo_sectors`: `sector_id`, `zone_id`, `zone_number`, `order`, nombre, notas, color, Polygon GeoJSON, estado, timestamps, autores y campos de archivo lógico.
- CRUD sectorial: `GET|POST /api/geo/sectors`, `GET|PUT|DELETE /api/geo/sectors/{sector_id}` y `GET /api/geo/sectors/locate`. DELETE desactiva y conserva auditoría.
- Validaciones: anillo cerrado, tres vértices distintos, rango geográfico, área no cero, sin autocruces y conflicto 409 ante superposición activa en la misma Zona; una excepción requiere confirmación explícita y queda auditada.
- Índices MongoDB activos: `sector_id_1` unique, `zone_id_1_order_1` unique, `geometry_2dsphere`, `status_1_zone_id_1_order_1`; además, índices de `normalized_address_key` y `sector_id` en ubicaciones.
- Point-in-polygon asigna `sector_id`, nombre y orden al geocodificar o corregir manualmente; crear, editar o desactivar sectores recalcula ubicaciones existentes. Las estadísticas de Personas, hogares, líderes y células se calculan dinámicamente, no se copian al Sector.
- Editor administrativo no modal: crear → dibujar sobre calles → arrastrar vértices → revisar → nombrar → guardar; permite editar, borrar puntos, desactivar y confirmar solapamientos. Snap-to-roads permanece opcional y no bloqueante.
- Presentación independiente con superficie desktop exacta 2:1, navegación Zona → Sector → Calles → Hogares, historial atrás/adelante, pantalla completa, métricas dinámicas, calles OSM y pines DOM de hogar con badge numérico.
- Corregida búsqueda desktop/móvil mediante resultados portaleados sobre MapLibre; selección abre halo y panel de hogar/persona de forma determinista. El editor dejó de usar el overlay modal que impedía clicar calles.
- Alta/edición de dirección genera `normalized_address_key` y `address_complete` inmediatamente, antes de geocodificar; una edición invalida coordenadas, Zona y Sector antiguos, incrementa `address_version` y activa el job Census → Geocodio. No se ejecuta migración/backfill histórico desde startup.
- Nuevo estado administrativo **⚠ Sin ubicación**: `GET /api/geo/unlocated-persons`, badge en toolbar y drawer scoped. Clasifica sin inventar datos: sin dirección/Hogar, Hogar sin ubicación, conflicto familiar, dirección incompleta, geocodificación fallida/pendiente o revisión requerida. Una Persona desaparece automáticamente al obtener ubicación propia o familiar inequívoca.
- Crear, editar o desactivar un Sector ejecuta point-in-polygon sobre ubicaciones vigentes y actualiza `sector_id`; las estadísticas continúan calculándose desde Personas, Households, liderazgo y células reales.
- Verificación read-only de producción confirmó que Personas creadas manualmente residen en `persons`, las direcciones en `person_addresses` y los hogares en `households/household_memberships`; Mapa 360 consume exactamente ese Core. La ausencia operativa actual es `geo_sectors`, no una desconexión de membresía.
- Certificación final aislada: backend geo **29/29 PASS**, frontend Jest **22/22 PASS**, build producción PASS; iteration 28 sin bugs deterministas; recorridos UI desktop 1920×800 y móvil 390×844 PASS, sin overflow; cadena Sin ubicación → búsqueda → editor → guardar → Presentación PASS y stage 2:1 verificado.
- Limpieza final: 0 usuarios/personas/sectores QA residuales en la base local. No se modificó producción, no se ejecutó backfill histórico y no se inventaron direcciones o sectores.
- Archivos principales: backend `geo_address.py`, `geo_sector_service.py`, `geo_provider.py`, `geo_service.py`, `geo_queries.py`, `geo_routes.py`; frontend `GeoMapCanvas.js`, `GeoSectorEditorDrawer.js`, `GeoPersonSearch.js`, `Presentation2To1Shell.js`, `GeoMapsPage.js`, `GeoMapToolbar.js`, `GeoDetailPanel.js`, `geoGeometry.js`, `App.css`; pruebas `test_geo_maps.py`, `test_iteration27_geo_public_manage_contract.py`, `ui_geo_fixture.py`.
- **Única operación pendiente del administrador:** entrar a `/mapas` y crear/dibujar los sectores territoriales reales desde el editor.

### HOTFIX — Exportación PDF de carnet/certificado: nombres largos y clipping de glifos — RESUELTO 2026‑09‑22

- Eliminado el hack `revealExportText` en `membershipPdf.js` que desactivaba `overflow`/`maxHeight` durante la captura html2canvas: ahora `overflow:hidden` permanece siempre activo, garantizando que un nombre nunca invada foto, QR, firma o fecha en el carnet/certificado exportado.
- Nombre del certificado (`MembershipCertificateTemplate.js`): añadido `textOverflow:ellipsis` como red de seguridad dura; en nombres largos (>48 car.) usa `WebkitLineClamp:3` para truncar con elipsis en vez de desbordar.
- Corregido clipping vertical de glifos en el PDF descargado (regresión detectada tras el fix anterior, invisible en la vista previa): altura/posición del nombre ajustadas (`top:3.30in/height:1.0in/lineHeight:1.15` para una línea; `top:3.34in/height:1.06in/lineHeight:.92` para nombre largo) y el párrafo de la declaración (`statement`) perdió `overflow:hidden`/`max-height` fijo (es texto de plantilla fijo, sin riesgo de invasión) y ganó `padding-bottom:.1in` + `lineHeight:1.3`.
- SVGs decorativos siguen 100% inline (nunca archivos externos) y se rasterizan a canvas antes de la captura (`prepareSvgLayers`), confirmando arte presente en el PDF final.
- `@page` con unidades físicas ya existente: mm para carnet (85.6×53.98mm) y pulgadas para certificado (11×8.5in); sin cambios necesarios.
- Snapshots Jest de "DESIGN LOCKED" regeneradas para los 3 archivos modificados; **17/17 PASS**, build de producción PASS.
- Verificación con PDF real descargado (no solo vista previa) en 3 rondas de testing agent: ronda 1 detectó regresión de clipping vertical de glifos; ronda 2 corrigió el caso de nombre largo pero dejó nombre corto y párrafo de declaración clippeados; ronda 3 confirmó **100% PASS** — nombre corto, nombre largo `'María Fernanda de los Ángeles Santos Francisco Gómez'` y declaración completos, sin invasión de áreas, dimensiones PDF exactas (Letter 792×612pt 1 página; CR80 242.65×153.01pt 2 páginas), arte SVG presente, sin errores de consola.

### MEMBRESÍA HISTÓRICA + MINICENSO EVANGELÍSTICO — IMPLEMENTADO 2026‑09‑19

- **Alta Directa:** `POST /api/core/persons` acepta `preexisting_active_member` y número histórico opcional. Solo Pastor/Pastora o Coordinación General pueden usar el bypass; un payload forzado por Líder ordinario recibe 403.
- La activación es idempotente y auditable: asigna o conserva `member_number`, marca membresía `active`, registra origen directo, habilita inmediatamente carnet/certificado y añade el privilegio de membresía a cuentas vinculadas.
- Los números existentes admiten dígitos, letras y guiones. El Core valida conflictos antes de crear la Persona; además aplica compensación sobre Persona, contactos, registro, membresía y eventos si falla una activación, evitando altas parciales.
- `PersonaNuevaPage` muestra el control **Miembro activo preexistente** exclusivamente a las dos autoridades autorizadas, permite conservar número previo y confirma el resultado en la ficha Persona 360.
- **Importador DRY-RUN:** nueva ruta protegida `/personas/importar` y endpoint `POST /api/membership/import/dry-run`; acepta CSV y XLSX hasta 5 MiB/2,000 filas mediante `openpyxl`, sin SDK frontend adicional.
- El análisis sugiere y permite corregir mapeo de 14 campos; normaliza nombres, teléfonos, correo y direcciones; detecta posibles duplicados por número VV, número de miembro, correo, teléfono y nombre+fecha; clasifica cada fila como Listo/Revisar/Error.
- Hogares con dirección exacta común se devuelven como sugerencia `HH-*`; conflictos de nombre familiar y dirección quedan en revisión. No se crea ni fusiona ningún hogar durante el análisis.
- Contrato no destructivo explícito: `dry_run=true`, `database_writes=0`; pruebas comparan conteos antes/después en Personas, membresías, hogares y membresías de hogar para CSV/XLSX.
- **Minicenso:** colección `evangelism_targets` y eventos auditables con CRUD lógico bajo `/api/geo/evangelism`; todos los usuarios autenticados pueden registrar, asignar, actualizar y archivar casas sin obtener acceso a datos territoriales de Personas/Células.
- Cada casa conserva dirección normalizada, Point GeoJSON cuando hay match, verificación, Zona/Subzona/Sector, idioma aparente, notas, responsable y ciclo `Detectada → Asignada → Visitada → Seguimiento → Conectada / No visitar`.
- La pestaña **Casas por visitar** usa pines por estado, filtro, captura móvil y panel editable. Una lista accesible con `data-testid` por `target_id` abre también casas sin coordenadas y permite edición/archivo E2E sin depender de clics aproximados sobre WebGL.
- Usuarios sin capacidades geo ven solamente Minicenso; Pastor/Liderazgo autorizado conserva Personas, Células, sectores y Presentación sin cambio de contratos privados.
- Índices activos: `target_id` unique, dirección normalizada unique para activos, `location_2dsphere`, estado/fecha, responsable/estado y eventos por objetivo/fecha.
- Certificación: backend focalizado e independiente **27/27 PASS** más regresión de rollback **3/3 PASS**; frontend **23/23 PASS** y build producción PASS; instalación backend limpia desde `requirements.txt` y `pip check` PASS; API pública health/config/import PASS.
- UI verificada en 1920×800 y 390×844 sin overflow: CSV → mapeo → dashboard; Persona → registrar casa → lista determinista → panel → Visitada → guardar → reabrir → archivar. Hallazgo iteration 29 sobre testabilidad del pin quedó resuelto con la lista accesible.
- Limpieza final local: `feature_users=0`, `feature_people=0`, `feature_targets=0`, `orphan_pub_numbers=0`. Producción no fue usada ni modificada.

### HOTFIX — ALTA DIRECTA PARA COORDINACIÓN GENERAL — COMPLETADO 2026‑09‑21

- El control **Miembro activo preexistente** de `/personas/nueva` queda habilitado para Pastor/Pastora y Coordinación General, incluyendo cuentas históricas `rol=lider` + `access_level=lider` + `core.access.manage`.
- La normalización del nivel de acceso es única y coherente en login, `/api/auth/me`, autorización backend, gobierno del Core y frontend; siempre devuelve `coordinador_general` para la forma histórica válida.
- Líder ordinario y Director permanecen bloqueados aunque intenten forzar `preexisting_active_member=true`; el backend responde 403 y no depende de la visibilidad del control.
- Coordinador puede activar la casilla, conservar un número histórico opcional y crear la Persona con membresía directa activa; Pastor conserva el flujo sin regresión.
- Certificación Iteración 36: backend 5/5 PASS, frontend desktop/móvil PASS, control seleccionable, input histórico visible y overflow `[]`; sin APIs MOCKED.
- Limpieza verificada: `iteration36_users=0`, `iteration36_people=0`, `iteration36_members=0`.

### PRIVILEGIO DE MEMBRESÍA DIRECTA DELEGABLE — COMPLETADO 2026‑09‑21

- Nueva capacidad granular `membership.direct_import`, mostrada como **Registrar miembro activo preexistente** en Gestión de Accesos.
- Pastor/Pastora y Coordinación General reciben el privilegio automáticamente; un Líder ordinario no lo recibe por defecto.
- Solo Pastor/Pastora puede asignar o retirar esta capacidad a múltiples cuentas mediante la tabla existente de Gestión de Accesos.
- El delegado puede activar **Miembro activo preexistente** al crear una Persona, preservar un número histórico y omitir los procesos propios de un nuevo creyente.
- Aislamiento estricto: `membership.direct_import` no concede `membership.documents.manage`; sin esta segunda capacidad el delegado recibe 403 al intentar emitir carnet/certificado.
- La asignación y revocación incrementan `token_version`; las sesiones anteriores quedan invalidadas y el usuario debe iniciar una sesión nueva para aplicar el cambio.
- Política de acceso centralizada en `ACCESS_POLICY_VERSION = 20`; Integridad confirma `access_policy_outdated=0`.
- Verificación Iteración 38: delegación/revocación, JWT, backend, UI escritorio/móvil y separación de documentos PASS; suites 9/9, frontend 25/25 y build PASS, sin APIs MOCKED.
- Protocolo reproducible documentado en `/app/auth_testing.md`; limpieza final `iter38_users=0`, `iter38_people=0` y cuenta compartida sin capacidad residual.

### PERFIL 360 — ACTIVACIÓN TOTAL DE MÓDULOS — COMPLETADO 2026‑09‑21

- Las 17 tarjetas del Perfil 360 ya proyectan fuentes reales y autorizadas; no queda ningún estado `module_unavailable`/“No disponible” para los dominios implementados.
- Estados visibles y honestos: **Registrado**, **En proceso**, **Sin registros** o **Acceso restringido** según datos y permisos.
- **Membresía** lee `person_memberships`, abre pestaña propia y conserva el panel completo de carnet/certificado únicamente para usuarios autorizados; los demás ven resumen de solo lectura.
- **Bautismo** es un dominio persistente en `person_baptisms`, con estado pendiente/programado/completado, fecha, lugar, ministro, testimonio, notas, validación y actividad auditable.
- **Bienvenida** refleja la etapa `welcome_party` de Consolidación y abre el expediente exacto cuando existe.
- **Consolidación, Ley de las 7 Semanas, Discipulado, Mentoría, CAP, Célula y Ministerio** abren páginas o expedientes reales incluso cuando aún no existen registros.
- Ley de las 7 Semanas recuperó la inscripción funcional mediante ciclo; Consolidación mantiene su intake oficial y rechaza creación genérica.
- Discipulado acepta `?person=` y enfoca automáticamente el expediente de la Persona seleccionada desde Perfil 360.
- Permisos preservados: sin `processes.read`, los módulos de procesos muestran Acceso restringido; Célula conserva su permiso independiente `cellular.read`; sin `processes.write`, Bautismo responde 403.
- Verificación: regresión principal **24/24 PASS**, Iteración 37 **6/6 PASS**, frontend **24/24 PASS**, build PASS, health 200 y servidor con 430 rutas.
- Browser real: 17 tarjetas, 0 deshabilitadas para Pastor, 0 “No disponible”, Membresía/Bautismo/Bienvenida/Ley7/Discipulado navegados y Bautismo guardado; desktop 1920×800 y móvil 390×844 sin overflow.
- APIs MOCKED: ninguna. Limpieza final: `iter37_users=0`, `iter37_people=0`, `iter37_baptisms=0`, `iter37_memberships=0`.

### JUNTA DIRECTIVA — RECINTO RESTRINGIDO Y PRIVACIDAD PASTORAL — COMPLETADO 2026‑09‑22

- Junta dejó de depender de jerarquía general, `doors.manage`, `core.access.manage` o acceso de Coordinación General.
- Fuente de verdad: **Pastor/Pastora = FULL**; cualquier otra cuenta requiere `board_memberships` activa por `person_id` en cada request.
- `GET /api/board/access` entrega únicamente `allowed`, cargo, permisos efectivos y clasificación institucional; frontend usa esta respuesta para navegación y protección de rutas.
- Coordinador General, Director, Líder, Supervisor, Mentor o Líder frontal sin membresía formal no ven `nav-board`, son redirigidos al intentar URL directa y reciben 403 en backend.
- Matriz máxima por cargo aplicada también en servidor:
  - Presidencia/Vicepresidencia: reuniones, agenda, votaciones, acuerdos y tareas.
  - Secretaría: reuniones, agenda, notas, minutas, grabaciones, documentos y seguimiento.
  - Tesorería: lectura institucional, documentos compartidos y votación si corresponde.
  - Vocal/Miembro: lectura institucional, votación y solo tareas/documentos propios o compartidos.
- Un payload que intenta conceder permisos superiores al cargo recibe 422; permisos almacenados históricos también se intersectan con el máximo del cargo.
- Agregar membresía sincroniza `board.access`; finalizarla incrementa `token_version`, invalida sesiones anteriores y retira acceso inmediatamente.
- La membresía de Junta nunca agrega `care.confidential.read`, `person.pastoral_notes.read` ni el legado `board.confidential.access`.
- Separación documental fuerte: Junta solo acepta/lista/descarga `classification=board_institutional`; cualquier `pastoral_confidential` queda fuera del módulo incluso para evitar mezcla accidental.
- Respuestas no pastorales usan resúmenes institucionales mínimos y eliminan `profile_path`; notas privadas de Secretaría requieren su permiso específico.
- Vocal solo ve tareas propias/compartidas, actualiza las propias, ve minutas oficiales y no ve grabaciones, notas o borradores; Secretaría/Pastora administran esos artefactos.
- Se corrigió un crash de startup detectado en Iteración 39: Mongo no permite `$addToSet` y `$pull` sobre `capabilities` en una sola operación; la migración quedó dividida en dos escrituras seguras.
- Verificación post-fix: Junta/Auth/regresiones **25/25 PASS**, matriz+cleanup **5/5 PASS**, frontend **25/25 PASS**, build PASS, health 200 y servidor con 431 rutas.
- Browser: Coordinador sin botón/redirección segura; Pastora con gestión completa; Secretaría con notas/audio/documentos; Vocal móvil sin controles elevados y sin overflow.
- APIs MOCKED: ninguna. Limpieza final: `iter39_users=0`, `iter39_meetings=0`, `iter39_memberships=0`.

### FASE DE ESTABILIZACIÓN — COMPLETADA 2026‑09‑19

- **Limpieza QA/demo P0:** el escaneo transversal fue reemplazado por una allowlist explícita de colecciones y campos de propiedad directa. Nunca se elimina un documento real por una mención incidental a una cuenta QA.
- `GET /api/core/persons/qa-demo/summary` produce DRY-RUN por colección, ejemplos, frase exacta y token JWT por cinco minutos. `DELETE` exige token + frase y rechaza preview vencido, alterado o desactualizado.
- **Multiplicación celular P0:** `create_cell_record` quedó desacoplado de FastAPI; la aprobación valida líder/transferidos, crea hija, genealogía, rol y membresías, y solo entonces programa geo. Una excepción compensa hija y reactiva membresías previas.
- **Membresía directa P0:** rollback usa el `inserted_id` ObjectId y compensa registro, eventos, membresía, contactos y Persona; una falla forzada confirma cero Personas fantasma.
- **Identidad canónica:** múltiples coincidencias crean `identity_conflicts` y detienen el vínculo. El registro público revierte cuenta e invitación; nunca crea una tercera Persona.
- **Directorio:** búsqueda/filtros se ejecutan en MongoDB con `page/limit`, orden estable y total; conserva talentos/ministerios y encuentra Personas posteriores a los primeros 500 registros.
- **Finanzas:** `entry_number` usa contador atómico y reserva única en `finance_entry_number_registry`; el índice único se instala si el historial no tiene duplicados. No se migraron asientos existentes y partida doble permanece verde.
- **Gobierno/RBAC:** rechaza capabilities nuevas no personalizables, conserva capabilities legadas solicitadas y permite retirar las derivadas de grupos; ya no responde éxito si descartaría un valor.
- **Invitaciones:** `expires_at=None` funciona sin 500 y las vencidas siguen rechazadas. `seed_user.py` queda bloqueado fuera de development/test y exige credenciales fuertes explícitas por entorno; nunca fue ejecutado contra producción.
- **Grabaciones y fotos:** finalize de Junta adquiere estado atómico y deja un solo archivo; los uploads/chunks de fotos comparten TTL y la limpieza elimina vencidos/huérfanos conservando activos.
- **Minicenso:** todos los autenticados mantienen registrar/asignar/estado. Roster devuelve solo `user_id + name`; ubicación precisa se limita a creador/responsable/GEO_VIEW_PRECISE; `pastoral_notes` queda separado y reservado a autoridad pastoral.
- **Frontend:** diálogo QA exige preview/frase; Minicenso explica ubicaciones protegidas. MapLibre genera etiquetas/contadores locales en canvas, sin `text-field` ni dependencia glyph; diálogo de captura incluye descripción accesible.
- **Pruebas específicas:** P0 4 PASS; P1 Core/Auth/Finanzas 7 PASS; uploads/privacidad 3 PASS; certificación independiente Iteración 30 **18/18 PASS**.
- **Regresión final:** backend 186 PASS + pública aislada 8 PASS = **194 PASS**, 3 omitidas intencionalmente; frontend **23/23 PASS** y build PASS. UI 1920×800/390×844 sin overflow; consola sin errores glyph ni warnings de descripción.
- **Limpieza final local:** `qa_remaining=0`, `evangelism_targets=0`; 89 reservas contables huérfanas exclusivamente QA eliminadas. Producción no fue consultada ni modificada.
- **P2 sin cambios:** la autoridad pastoral se revisará por intención de módulo; no se hizo sustitución masiva, especialmente en Finanzas.

### MEGA‑BLOQUE E — OPERACIONES — COMPLETADO 2026‑09‑19

- **Flujo cerrado:** crear evento → materializar ocurrencias → crear equipos/turnos → convocar voluntarios → registrar Personas/invitados → check-in → cerrar asistencia → consultar métricas.
- **Recurrencia preparada para crecimiento:** eventos soportan `none/daily/weekly/monthly`, intervalo, días semanales, día mensual y final por cantidad/fecha/sin fecha. Ocurrencias usan IDs deterministas e idempotentes y pueden extenderse hasta 730 días sin rediseñar el modelo.
- **Turnos únicos o recurrentes:** `single_occurrence` aplica a una fecha; `all_occurrences` materializa el turno en toda la serie y en ocurrencias futuras. Incluye rol, offsets, duración, cupos, instrucciones y relación opcional a Ministerio/Célula.
- **Voluntariado:** asignación única por Persona/turno, estados invitado/confirmado/declinado/check-in/no-show, respuesta de la Persona y notificación interna auditable.
- **Inscripciones:** Persona canónica o invitado, autoinscripción limitada al propio `person_id`, capacidad/waitlist y código `OP-*`; staff de check-in puede registrar invitados sin crear Personas duplicadas.
- **Check-in móvil:** búsqueda por nombre/número VV, código de inscripción, número de miembro o QR HMAC del carnet; cámara mediante `BarcodeDetector` con fallback manual. `duplicate_key` e `idempotency_key` únicos evitan doble entrada por doble toque.
- Cada check-in canónico actualiza inscripción, turno voluntario y `person_attendance` de Persona 360. Cierre congela métricas, completa turnos, marca no-show y bloquea nuevas entradas; un segundo cierre es idempotente.
- **RBAC:** Pastor/`operations.manage` administra y cierra; Líder/`operations.checkin` registra entradas sin crear eventos; Persona/`operations.view|volunteer` consulta, se autoinscribe y responde solo sus convocatorias. Listados privados ocultan otros asistentes/contactos a cuentas básicas.
- **Dashboard:** ocurrencias próximas, check-ins del día, voluntarios confirmados, cupos por cubrir y notificaciones internas.
- **Archivos:** PDF/PNG/JPEG hasta 5 MiB en GridFS, magic bytes verificados, descarga autenticada, metadata vinculada al evento y limpieza ante fallo.
- **Auditoría:** todos los writes relevantes generan `operation_audit_events`; índices únicos cubren ocurrencias, turno/Persona, inscripción/Persona, códigos y check-ins.
- **Frontend:** rutas independientes `/operaciones`, `/operaciones/eventos`, detalle de evento, detalle de ocurrencia y check-in móvil; guía contextual agregada como módulo 33.
- **Pruebas:** E2E backend específico 2/2 PASS; certificación independiente Iteración 31 9/9 PASS; recorrido UI público evento semanal→turno→invitado→check-in PASS.
- **Regresión final:** backend **201 PASS**, 3 omitidas intencionalmente; frontend **24/24 PASS** y build PASS. Desktop 1920×800 y móvil 390×844 sin overflow ni errores de consola.
- **Limpieza final local:** eventos, ocurrencias, turnos, asignaciones, inscripciones, check-ins, notificaciones y credenciales QA en cero. Producción no fue consultada ni modificada.
- **Fuera de alcance preservado:** Pushpay continúa **MOCKED/BLOCKED**; no se añadió IA.

### MEGA‑BLOQUE F — CUIDADO PASTORAL — IMPLEMENTADO Y CERTIFICADO 2026‑09‑19

- Blueprint 1.1 aprobado y congelado en `memory/CARE_BLUEPRINT.md`: Cuidado administra expedientes, asignaciones, contactos, visitas y bóveda; Operación 72 responde inmediatamente; Consolidación conserva el proceso formativo. Solo comparten IDs y nunca notas.
- Nueva API `/api/care/*` y colecciones separadas para casos, asignaciones, contactos, notas cifradas, Operación 72, visitas, participantes, alertas y auditoría. Índices únicos protegen `case_id`, `visit_id`, asignación primaria y `op72_records.person_id`.
- Operación 72 conserva una sola primera conversión histórica por `person_id`; `first_conversion_at` es inmutable. Pausa y reactivación preservan inscripción, `current_stage_key`, tareas y progreso de Consolidación/7 Semanas, sin duplicar Persona, expediente ni proceso.
- Reconciliación, restauración y regreso abren casos pastorales independientes, pero nunca otra Operación 72. El disparador celular `conversion_person_ids` crea/enlaza Op72 idempotentemente.
- Estados controlados: Detectado, Asignado, Contactado, En seguimiento, Resuelto, Cerrado y Escalado. Urgencias escalan inmediatamente a autoridad pastoral sin retirar al responsable normal y auditan actor, fecha, destino y motivo.
- Alertas idempotentes: 24h sin asignar, 72h sin contacto exitoso, próximo paso vencido y urgente. Dashboard, alertas y Perfil 360 nunca contienen notas o ciphertext.
- Bóveda AES‑GCM con clave `PASTORAL_NOTES_ENCRYPTION_KEY`, notas append-only, adendas, visibilidad `pastoral_core/assigned_team` y auditoría por lectura. Sin clave, la bóveda falla cerrada y no guarda texto plano.
- RBAC central de Cuidado: Pastor/Pastora y Coordinación General autorizada tienen scope global; equipo asignado solo accede a casos activos asignados y notas `assigned_team`; Persona recibe 403. IDs ajenos responden 404 para evitar inferencias.
- Perfil 360 agrega la sección Cuidado únicamente si existe actividad y el usuario tiene permiso global o asignación sobre esa Persona. Usuarios no autorizados no reciben tarjeta, contador, timeline ni metadata.
- Visitas individuales o por `household_id` canónico; una visita familiar conserva participante, resultado, próximo paso y caso individual. El resumen de hogar se cifra y no se copia a otros módulos.
- Rollout conservador: producción inicia sin backfill. `/api/care/migrations/legacy/dry-run` solo cuenta y garantiza `writes_performed=false`; migrar notas/conversiones históricas requiere una aprobación posterior a la revisión real.
- Frontend operativo en `/cuidado-pastoral`, casos, expediente, Operación 72 y visitas; desktop 1920×800 y móvil 390×844 certificados con overflow `[]`.
- Certificación independiente Iteración 32: backend/frontend 100%, flujos Pastor/Líder, privacidad, Op72, visitas y build PASS. Regresión final completa: **210 PASS**, 3 omitidas intencionalmente; build PASS con warnings preexistentes de sourcemaps/bundle.
- Limpieza final local: `care_ui_users=0`, `coreqa_users=0`, `care_cases=0`, `op72_records=0`, `finance_qa=0`. La cascada QA ahora incluye todas las colecciones de Cuidado.
- Versión candidata lista para producción: `PASTORAL_NOTES_ENCRYPTION_KEY` fue rotada a una clave AES‑256 base64-url válida, la bóveda responde `vault-ready` y el chequeo de publicación quedó **PASS sin bloqueadores**. Falta únicamente que el usuario pulse **Publish**; después se realizará la revisión visual en producción sin ejecutar migración histórica.

### P1/P2 — siguientes pasos y backlog

- **P1 — Aceptación operativa:** validar Consolidación v2 con responsables reales, asignar `front_groups.view`/`leadership.view` y capacidades de gestión, y crear el primer Grupo Frontal de producción.
- **Operación administrativa — Mapa 360:** dibujar los sectores territoriales reales; snap-to-roads permanece P2/opcional y no bloqueante.
- **P1 — Aceptación funcional del usuario:** revisar Mega‑Bloque F en producción con casos reales autorizados y recopilar ajustes de política/terminología, sin ejecutar backfill histórico.
- **P1 — Pushpay:** activar OAuth/sandbox, sincronización idempotente y mapeo contable únicamente después de recibir credenciales reales.
- **P2 — Finanzas:** pulido visual y desminificación de páginas financieras según feedback, sin alterar contratos verificados.
- **COMPLETADO — Mega‑Bloque E — Operaciones:** eventos, check‑in, asistencia y voluntariado.
- **COMPLETADO — Mega‑Bloque F — Cuidado:** casos pastorales, visitación, privacidad extrema y Operación 72 histórica única.
- **P4 — Mega‑Bloque H — Automatización + IA:** workflows, alertas, dashboards y asistente sobre datos autorizados.

## 12. Próximas tareas ejecutables

1. El administrador dibuja y aprueba los sectores territoriales reales de cada Zona en `/mapas`; el sistema recalcula asignaciones y estadísticas automáticamente.
2. Ejecutar aceptación física del Modo Presentación en la pantalla 14×7 y ajustar tamaños únicamente con feedback de distancia real.
3. Entregar el padrón histórico real como CSV/XLSX para ejecutar primero el DRY-RUN, revisar duplicados/hogares y definir en una fase posterior el commit supervisado; el flujo actual nunca escribe.
4. Mantener Pushpay **MOCKED/BLOCKED** hasta recibir las credenciales sandbox.
5. Configurar `PASTORAL_NOTES_ENCRYPTION_KEY`, publicar la versión candidata de Mega‑Bloque F y realizar aceptación visual/operativa en producción sin migrar históricos.

## 13. Restricciones vigentes

- No rediseñar ni debatir la regla FROZEN.
- No crear perfiles alternos para niño, familiar, cuenta, Ministerio, proceso o célula.
- No inventar estados para módulos aún no construidos.
- No usar datos de producción en pruebas destructivas.
- No usar datos estáticos del manual como fuente operativa.
- Toda nueva interacción o dato crítico debe incluir `data-testid` único.
- Frontend usa `REACT_APP_BACKEND_URL`; backend usa prefijo `/api` y variables de entorno obligatorias.

### MEGA‑BLOQUE G — Grupos Frontales recursivos (implementado 2026-09-19)
- Contrato congelado en `memory/FRONT_GROUPS_BLUEPRINT.md`: árbol ilimitado, rol dual canónico, trabajo descendente y reportes ascendentes.
- Fase 0: 20 Grupos QA archivados sin hard delete; IDs, historial y auditoría preservados. No quedan Grupos reales activos ni credenciales QA.
- Núcleo: padre/raíz/ancestros, prevención de ciclos, scope de subárbol y RBAC por rama.
- Operación: trabajo delegable, rotación semanal auditable, autoridad de Consolidación, vínculo configurable Célula ↔ Grupo y continuidad del expediente.
- Integraciones: Persona 360, Op. 72 única, Ley de 7 Semanas como proceso y Mapa 360/Invasiones reutilizados con botón “Crear invasión”.
- UI y certificación: panel recursivo y mesa semanal; build exitoso, 29 pruebas críticas y desktop/móvil sin overflow. Iteración 33 corregida y revalidada.

### HOTFIX P0 — Carnet con fotografía visible — RESUELTO 2026-09-22

- Corregido el desacople entre Persona 360, que reconocía cualquier fotografía canónica por `person_id`, y la emisión del carnet, que exigía incorrectamente `is_current=true`.
- Las nuevas cargas de fotografía guardan `is_current=true`; las fotografías históricas ya visibles continúan siendo válidas aunque no tengan esa bandera.
- Se conserva el rechazo 422 cuando realmente no existe fotografía y el 403 para usuarios sin autoridad ni `membership.documents.manage`; no se modificó RBAC de Junta o Finanzas.
- Certificación Iteración 47: backend 3/3, frontend desktop/móvil, botón habilitado, emisión 201, vista previa e historial PASS; auto-regresión 4/4 PASS y cero datos QA residuales.

### REPRODUCCIÓN DEL MASTER — PENDIENTE DE APROBACIÓN VISUAL 2026-09-23

- El usuario rechazó el concepto minimalista anterior. Sus estilos y goldens fueron retirados; no deben reutilizarse.
- El adjunto exacto 1536 × 1024 quedó guardado como fuente única en `design-reference/membership-documents-master.png` (SHA-256 `43e86ca8…`).
- Reconstrucción actual: coordenadas absolutas en mm/in, IDs `vv-membership-*`, sin clases globales internas, logo `contain`, foto `cover` y SVGs independientes para bandas, marcos, curvas y cruz de agua.
- Carnet CR80 exacto: frente sin QR; foto/identidad/estado/número/fecha según master. Reverso ~90% blanco con mensaje exacto, teléfono, firma, divisor, QR y geometría inferior.
- Certificado Letter landscape exacto: marca, título, nombre, texto, datos, firma, QR y geometrías institucionales. Preview y PDF comparten los mismos componentes.
- Casos extremos: números de 22 caracteres y nombres de 78 caracteres usan escalado/líneas controladas; medición browser confirmó cero invasión y cero overflow de página en 1920×800 y 390×844.
- Comparaciones visuales: `test_reports/master-compare-card-front-final.png`, `master-compare-card-back-final.png`, `master-compare-certificate-final.png`.
- Certificación Iteración 53: backend/PDF/QR PASS; issue de número largo corregido y auto-verificado. Frontend 17/17, contratos visuales 5/5 y build PASS.
- **Pendiente:** aprobación visual explícita del usuario. Hasta entonces no crear goldens de implementación, no merge y no deploy.