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
- Variables obligatorias: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `CORS_ORIGINS`.
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
- GPT‑5.4‑mini PASS real para análisis, borrador y resumen aun sin transcript; identidad pseudonimizada, fuentes no confiables delimitadas y consentimiento explícito.
- Auditoría inmutable de mutaciones críticas, voto secreto en audit feed y RBAC específico para audio/auditoría/minutas.
- Blueprint: `/app/memory/DOORS_BOARD_SCHEMA_BLUEPRINT.md`.
- Validación: suite global **66 passed, 3 skipped**; test D, GridFS, documentos y GPT PASS; frontend build PASS; E2E agente PASS; security audit PASS.

#### Dependencia externa abierta

- **STT diarizado: BLOCKED — external credential required.**
- `OPENAI_STT_API_KEY` permanece vacío y fuera de código/frontend/documentación. Sin esa credencial no se crean speakers ni atribuciones.
- UI muestra: “Identificación de participantes pendiente de procesamiento STT diarizado.”
- No se usa `whisper-1` como sustituto.

### P0 — Arranque y CORS de despliegue — RESUELTO 2026‑09‑16

- Corregida la precedencia de configuración: Kubernetes/runtime prevalece sobre `.env` mediante `load_dotenv(..., override=False)`.
- La carga local de `.env` ahora usa una ruta relativa explícita a `server.py`, sin depender del directorio de ejecución.
- CORS permite el origen preview configurado explícitamente y el patrón productivo `*.emergent.host`; subdominios preview arbitrarios no forman parte del contrato con credenciales.
- Backend reiniciado y verificado RUNNING; `/api/health` externo devuelve 200.
- Regresión dedicada de arranque, precedencia runtime, health y CORS: **6/6 PASS**.
- Revisión final de preparación de despliegue: **PASS**, sin bloqueadores.

### P0 — siguiente: Mega‑Bloque G — CONTABILIDAD Y FINANZAS

- Jurisdicción: Columbus, Ohio, Estados Unidos.
- Contabilidad por fondos, plan de cuentas, fondos restringidos/no restringidos, donaciones, diezmos, ofrendas, promesas, gastos, proveedores, presupuestos, bancos, conciliación, caja, activos, cierres y auditoría inmutable.
- Pushpay seleccionado para donaciones/pagos. Cuenta aún no creada; solicitar sandbox/OAuth al iniciar la integración.
- RBAC financiero, segregación de funciones, aprobaciones multinivel y reportes para liderazgo/Junta.

### P1/P2 — backlog

- **Mega‑Bloque E — Operaciones:** eventos, check‑in, asistencia y voluntariado.
- **Mega‑Bloque F — Cuidado:** casos pastorales, visitación y Operación 72.
- **Mega‑Bloque H — Automatización + IA:** workflows, alertas, dashboards y asistente sobre datos autorizados.

## 12. Próximas tareas ejecutables

1. Diseñar y aprobar el schema contable por fondos para Ohio.
2. Implementar plan de cuentas, períodos, asientos balanceados y cierres.
3. Construir ingresos/donantes/recibos, gastos/proveedores/aprobaciones y conciliación bancaria.
4. Preparar adapter Pushpay OAuth/webhooks idempotentes sin activarlo hasta obtener sandbox.
5. Conectar dashboard financiero con Junta Directiva y permisos segregados.

## 13. Restricciones vigentes

- No rediseñar ni debatir la regla FROZEN.
- No crear perfiles alternos para niño, familiar, cuenta, Ministerio, proceso o célula.
- No inventar estados para módulos aún no construidos.
- No usar datos de producción en pruebas destructivas.
- No usar datos estáticos del manual como fuente operativa.
- Toda nueva interacción o dato crítico debe incluir `data-testid` único.
- Frontend usa `REACT_APP_BACKEND_URL`; backend usa prefijo `/api` y variables de entorno obligatorias.