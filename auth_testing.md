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

## Mega‑Bloque B — Procesos

- Registro público con rol líder/pastor debe retornar 403; sin invitación solo crea Persona.
- Líder no puede leer Personas fuera de scope ni asignar otro responsable/mentor/cobertura.
- Persona solo consulta/actualiza sus propias tareas y evidencias.
- Solo pastor administra reglas SLA y ejecuta migración.
- Duplicar una inscripción activa equivalente debe retornar 409.
- Proxy de imágenes requiere JWT, rechaza hosts no permitidos y no sigue redirecciones.