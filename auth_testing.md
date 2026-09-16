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