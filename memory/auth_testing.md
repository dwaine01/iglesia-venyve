# Validación de autenticación — fase de estabilización

## Alcance

- Se conserva JWT bearer y el cálculo de permisos desde MongoDB en cada solicitud.
- El cambio de invitaciones únicamente hace segura la comparación cuando `expires_at=None`.
- Si la identidad canónica encuentra múltiples Personas candidatas, el registro se detiene, revierte la cuenta/invitación y crea un conflicto revisable; nunca crea una tercera Persona.
- `seed_user.py` no forma parte del runtime y ahora exige `APP_ENV=development|test`, `ALLOW_DEV_SEED=true` y credenciales explícitas no triviales.

## Pruebas obligatorias

1. Registro con invitación permanente (`expires_at=None`) responde sin error 500.
2. Invitación vencida sigue rechazada.
3. Identidad ambigua no crea Persona ni cuenta huérfana y conserva un conflicto abierto.
4. El seed queda bloqueado en producción incluso si alguien intenta habilitarlo.
5. Login, `/api/auth/me`, cambio de contraseña, revocación y cookies existentes permanecen cubiertos por la regresión completa.

## Seguridad operativa

- No se ejecuta `seed_user.py` durante pruebas o despliegue.
- No se crean credenciales persistentes en este documento.
- Toda cuenta QA se crea en MongoDB local y se elimina al terminar.