# Pruebas de autenticación y gobierno de acceso

## Verificación MongoDB

- Confirmar índice único en `users.email`.
- Confirmar índices únicos parciales en `users.person_id` y `persons.auth_user_id`.
- Confirmar que cada usuario activo tenga `person_id`, `token_version`, `capabilities` y `access_scope`.
- Confirmar que el hash de contraseña comience con `$2` y nunca sea devuelto por API.

## Pruebas API

1. Iniciar sesión con una cuenta activa en `POST /api/auth/login`.
2. Consultar `GET /api/auth/me` y verificar `person_id` y `canonical_profile_path`.
3. Consultar `GET /api/core/governance/integrity` como pastor.
4. Ejecutar `POST /api/core/governance/migrate` y verificar idempotencia ejecutándolo dos veces.
5. Actualizar rol/estado con `PUT /api/core/governance/users/{user_id}/access`.
6. Confirmar que un cambio de acceso incremente `token_version` y revoque el JWT previo.
7. Confirmar que un líder reciba 403 en rutas de gobierno del núcleo.

## Pruebas frontend

- Abrir `/nucleo` como pastor y verificar indicadores, migración y tabla de accesos.
- Cambiar el rol de una cuenta de prueba, guardar y comprobar la actualización.
- Verificar que la pantalla no tenga overflow en 1920x800 ni 390x844.

## Gestión jerárquica de accesos

- El contrato continúa siendo JWT Bearer; no se introducen cookies de sesión.
- Pastor: crea y administra coordinadores generales, líderes y personas.
- Coordinador general: crea y administra líderes y personas; nunca pastores ni otros coordinadores generales.
- Cada acceso nuevo se vincula con un Perfil 360 existente y usa contraseña temporal bcrypt.
- El primer ingreso exige cambio de contraseña; el cambio incrementa `token_version` y revoca el JWT anterior.
- Verificar 403 para líder/persona en administración de accesos y 403 para coordinador intentando elevar privilegios.
- Ninguna respuesta API puede incluir hash o contraseña.
- Toda cuenta privilegiada queda bloqueada en backend hasta completar cambio de clave y onboarding.
- Verificar cadena Pastor → Coordinador general → Director → secretario/tesorero/equipo y `parent_user_id` directo.
- Director solo puede crear cuentas con el mismo `organization_scope`.
- Junta exige simultáneamente `board.confidential.access` y membresía activa; Finanzas nunca es delegable fuera del pastor.
- Las firmas deben conservar snapshot y versión de política, cuatro aceptaciones, fecha/hora, IP y agente de navegador.

## Mega‑Bloque B — Procesos

- Registro público con rol líder/pastor debe retornar 403; sin invitación solo crea Persona.
- Líder no puede leer Personas fuera de scope ni asignar otro responsable/mentor/cobertura.
- Persona solo consulta/actualiza sus propias tareas y evidencias.
- Solo pastor administra reglas SLA y ejecuta migración.
- Duplicar una inscripción activa equivalente debe retornar 409.
- Proxy de imágenes requiere JWT, rechaza hosts no permitidos y no sigue redirecciones.

## Consolidación v2 — autorización focal

- Crear cuentas QA efímeras para autoridad pastoral, líder con capability y usuario sin permiso.
- Confirmar JWT vigente mediante `GET /api/auth/me` usando `Authorization: Bearer <token>`.
- Verificar acceso pastoral y delegado a `GET /api/front-groups`, `GET /api/leadership/requirements`, `GET /api/leadership/dashboard` y `GET /api/core/persons?limit=500`.
- Verificar 403 para la cuenta sin `processes.read` ni permisos administrativos equivalentes.
- Confirmar que Liderazgo y Grupos Frontales solo aparezcan en navegación cuando puedan consultarse.
- Eliminar cuentas, Personas y registros QA al terminar; no persistir credenciales efímeras.

## Membresía directa delegada

- Pastor asigna `membership.direct_import` desde Gestión de Accesos y el cambio incrementa `token_version`.
- El token anterior queda revocado; con sesión nueva el delegado ve la capacidad en `/api/auth/me`.
- Delegado puede crear Persona con `preexisting_active_member=true`, pero no emitir carnet/certificado sin `membership.documents.manage`.
- Líder ordinario recibe 403 al forzar el bypass.
- Al revocar la capacidad, el token previo queda inválido y una sesión nueva vuelve a recibir 403.
- Pastor y Coordinación General conservan alta directa automática.
- Limpiar cuentas, Personas, membresías, eventos y números de miembro QA al terminar.

## Junta Directiva restringida

- Pastor/Pastora obtiene `full_access=true` sin depender de capacidades generales.
- Coordinador General, Director y Líder sin membresía formal activa reciben `allowed=false`, no ven navegación y obtienen 403 en rutas de Junta.
- Membresía activa se valida por `person_id` en cada request; los permisos efectivos se intersectan con el máximo del cargo.
- Presidencia: reuniones/agenda/votos/acuerdos/tareas. Secretaría: reuniones/notas/minutas/grabaciones/documentos/tareas. Tesorería y Vocal: lectura institucional, votos y elementos compartidos/asignados.
- Finalizar membresía incrementa `token_version`, invalida JWT previo y elimina `board.access`.
- Miembro de Junta nunca recibe `care.confidential.read`, `person.pastoral_notes.read` ni el legado `board.confidential.access`.
- Documentos aceptados en Junta llevan `classification=board_institutional`; cualquier archivo `pastoral_confidential` queda fuera de listados y descargas, incluso para evitar mezclas accidentales.
- Vocal solo ve tareas propias/compartidas, documentos propios/compartidos y minutas oficiales; Secretaría/Pastora gestionan borradores y grabaciones.
- Probar desktop/móvil, acceso directo por URL, IDOR de documentos, revocación y limpieza completa de fixtures.