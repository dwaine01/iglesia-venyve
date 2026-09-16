# PRD — Iglesia Ven y Ve

## 1. Problema original

Construir y evolucionar una plataforma interna para la iglesia sobre FastAPI, React y MongoDB, con autenticación revocable, control de acceso por capacidades, una identidad canónica por Persona y módulos ministeriales desacoplados.

Bloques solicitados:

1. BASE-01: revocación JWT mediante `token_version`, usuarios activos y timestamps UTC.
2. ACCESS-01 + Profile 360: permisos por capability/scope y una ficha única para cada Persona.
3. Person Core Expansion: demografía controlada, ocupaciones, habilidades, relaciones familiares y Household canónicos.
4. Ministerios Centrales: catálogo, funciones y múltiples asignaciones por Persona.
5. Directorio Global de Talentos: búsqueda combinada por ocupación, habilidad, edad, género, Ministerio y función.

## 2. Regla arquitectónica FROZEN

**ONE PERSON → ONE CANONICAL PROFILE 360 → MANY MODULES → DIFFERENT PERMISSIONS**

- La Persona se crea una sola vez en `persons`.
- La URL oficial es `/personas/{person_id}`.
- Familia, Household, Ministerios, talentos, contactos y demás dominios guardan sus datos en colecciones separadas.
- Ningún módulo crea perfiles alternos o copia su fuente de verdad dentro de `persons`.
- Los nombres, fotos y números VV mostrados en módulos enlazan a la ficha canónica.
- La visibilidad y las acciones dependen de capabilities explícitas y scope sobre Personas.
- Los módulos no construidos muestran estados veraces; nunca inventan datos.

## 3. Personas usuarias

- **Pastor:** acceso maestro y administración institucional.
- **Líder:** gestión de Personas dentro de su scope y uso de directorios/Ministerios.
- **Persona:** acceso a su progreso y módulos personales autorizados.
- **Roles futuros:** pueden acceder a la ficha canónica si reciben capabilities y scope explícitos.

## 4. Arquitectura técnica

### Backend

- FastAPI modular.
- MongoDB mediante Motor y variables `MONGO_URL`/`DB_NAME`.
- JWT validado contra el usuario actual en MongoDB en cada solicitud autenticada.
- Dominios principales:
  - `server.py`: aplicación, auth y módulos legacy.
  - `access_control.py`: capabilities y scopes.
  - `core_person.py`: identidad canónica.
  - `core_profile.py`: agregador Profile 360.
  - `person_core_expansion.py`: talentos, familia, Household y directorio.
  - `ministries.py`: catálogo, funciones y asignaciones ministeriales.

### Frontend

- React + React Router.
- Tailwind CSS y componentes Shadcn/Radix.
- Sonner para notificaciones.
- Layout institucional navy/dorado, tipografías Spectral e IBM Plex Sans.
- Navegación principal a Personas, Directorio de Talentos, Ministerios y Perfil 360.

## 5. Modelos principales

- `users`: email, password, role, is_active, token_version, capabilities, access_scope.
- `persons`: person_id/ObjectId, person_number VV, identidad y demografía base.
- `person_talents`: ocupación principal y habilidades referenciadas al catálogo.
- `talent_catalog`: ocupaciones/habilidades administrables.
- `person_relationships`: relaciones bidireccionales entre dos person_id canónicos.
- `households` y `household_memberships`: hogar separado del parentesco.
- `ministries`: catálogo ministerial.
- `ministry_roles`: funciones globales o específicas de un Ministerio.
- `ministry_assignments`: Persona + Ministerio + función + vigencia.

## 6. Flujos y endpoints clave

- Auth: `/api/auth/login`, `/api/auth/me`.
- Personas: `/api/core/persons`, `/api/core/persons/{person_id}/profile`.
- Talentos: `/api/core/talents/catalog`, `/api/core/persons/{person_id}/talents`.
- Directorio: `/api/core/persons/directory/search`.
- Familia: `/api/core/persons/{person_id}/relationships`, `/family/quick-create`.
- Ministerios: `/api/ministries`, `/api/ministries/{ministry_id}`.
- Asignaciones: `/api/ministries/person/{person_id}/assignments`, `/api/ministries/assignments/{assignment_id}`.

## 7. Implementado

### BASE-01 — completado

- JWT revocable con `token_version`.
- Bloqueo inmediato de usuarios con `is_active=false`.
- Validación del usuario desde MongoDB por solicitud.
- Helpers UTC aware e ISO-Z.

### ACCESS-01 + Profile 360 — completado

- Capabilities y scopes explícitos.
- Redacción de datos sensibles en backend.
- Ficha 360 canónica con dominios reales y módulos pendientes veraces.
- Contactos y direcciones modulares.
- Edición básica, foto persistente, Household, familia, llegada, asistencia, notas e historial.

### Person Core Expansion — completado

- Género y estado civil controlados.
- Catálogo estructurado de ocupaciones/habilidades.
- Relaciones familiares entre Personas canónicas.
- Búsqueda antes de crear y creación rápida con VV/person_id propio.
- Household separado de familia.
- Grupos etarios derivados.

### Ministerios Centrales — completado y verificado el 2026-09-16

- Catálogo central y archivo no destructivo.
- Catálogo extensible de funciones.
- Una Persona puede tener múltiples asignaciones.
- Un Ministerio puede tener múltiples Personas/funciones.
- Indicadores de vacante/actividad de liderazgo.
- Detalle, búsqueda de Personas, asignación y finalización desde frontend.
- Navegación bidireccional al Perfil 360.
- Creación familiar rápida con asignación ministerial opcional.

### Directorio Global de Talentos — completado y verificado el 2026-09-16

- Ruta `/directorio` y acceso desde el menú principal.
- Búsqueda por nombre, VV, ocupación, habilidad, Ministerio o función.
- Filtros combinables separados para ocupación y habilidad.
- Filtros por grupo etario, género, Ministerio y función.
- Resultados enriquecidos con talentos y asignaciones ministeriales reales.
- Navegación al único Perfil 360 canónico.
- Estados de carga, error, vacío, limpieza y reintento.
- Membresía se muestra como pendiente hasta que exista su módulo fuente de verdad.
- Responsive sin overflow en 1920x800 y 390x844.

### Configuración — reforzada el 2026-09-16

- Backend y frontend usan variables de entorno sin valores por defecto para URL y base de datos.
- Configuración ausente falla de forma explícita.

## 8. Verificación más reciente

- Backend dirigido de Person Core + Ministerios: 2/2 PASS.
- Suite backend completa: 33/33 PASS; 3 pruebas públicas se omiten dentro de la suite local cuando no se inyecta URL externa.
- Regresión pública del Directorio: 3/3 PASS con URL externa.
- Build frontend `CI=true yarn build`: PASS.
- Agente de pruebas: flujos frontend de Directorio, Ministerios, asignaciones, Perfil 360 y familia rápida aprobados.
- Verificación visual propia:
  - Directorio desktop 1920x800: sin overflow.
  - Directorio mobile 390x844: sin overflow.
  - Ministerios y detalle mobile 390x844: sin overflow.
- Integraciones simuladas: ninguna.
- Advertencias conocidas sin regresión: source maps de `dompurify`, Browserslist antiguo y deprecación FastAPI `on_event`.

## 9. Roadmap priorizado

### P0 — completo

- Verificación frontend integral de Ministerios y familia rápida.
- Directorio Global de Talentos funcional de extremo a extremo.

### P1 — siguiente

- Construir Membresía como dominio real y habilitar su filtro en el Directorio.
- Definir catálogo/estados oficiales de Membresía antes de exponer filtros.

### P2 — futuro

- Bautismo.
- Bienvenida.
- Consolidación.
- Ley7 como dominio conectado a Persona.
- Discipulado.
- Cada módulo debe conservar fuente de verdad propia y resumirse en Profile 360.

## 10. Restricciones vigentes

- No rediseñar ni debatir la regla FROZEN.
- No crear perfiles alternos de niño, familiar, Ministerio o proceso.
- No inventar estados para módulos aún no construidos.
- No usar datos de producción en pruebas destructivas.
- Toda nueva interacción o dato crítico debe incluir `data-testid` único.
- APIs frontend siempre mediante `REACT_APP_BACKEND_URL` y rutas backend con prefijo `/api`.
