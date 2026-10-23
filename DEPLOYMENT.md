# 🚀 Guía de Deployment — Iglesia Ven y Ve (Railway + HostGator DNS)

Despliegue en Railway: **2 servicios** (backend FastAPI y frontend React) desde el mismo repo, con dominios personalizados gestionados vía HostGator DNS.

## Mapeo de dominios

| Dominio | Servicio | Tipo |
|---|---|---|
| `panel.iglesiavenyve.org` | Frontend React | Público |
| (URL pública asignada por Railway) | Backend FastAPI | API |

> **Nota (actualizada):** Esta tabla refleja la arquitectura REAL verificada en Railway. El backend se accede actualmente mediante la URL pública que Railway asigna al servicio backend (no tiene dominio personalizado propio). Los dominios `iglesiavenyve.org` y `www.iglesiavenyve.org` NO están enlazados actualmente a ningún servicio activo. El resto de esta guía documenta el procedimiento histórico de configuración DNS en HostGator y puede no reflejar el estado actual del despliegue.

---

## 0. Pre-requisitos

- Cuenta en [Railway](https://railway.app) conectada a GitHub (repo `dwaine01/iglesia-venyve`).
- MongoDB Atlas configurado:
    - `MONGO_URL`: configúralo en Railway → Variables del servicio backend (no se documenta el valor real aquí por seguridad).
  - `DB_NAME`: `iglesia_venyve`
  - En **Atlas → Network Access** añade `0.0.0.0/0` (o los rangos IP de Railway).
- Dominio `iglesiavenyve.org` con DNS gestionado en HostGator (cPanel → Zone Editor).

---

## 1. Crear servicio **BACKEND** en Railway

1. Railway → **New Project** → **Deploy from GitHub repo** → elige `dwaine01/iglesia-venyve` (rama `main`).
2. Railway detecta automáticamente `railway.toml` en la raíz → usa `Dockerfile.backend`.
3. **Settings → Service Name**: `venyve-backend`.
4. **Variables** (Settings → Variables → Raw Editor):

```
MONGO_URL=<configúralo directamente en Railway → Variables; usa el valor real de MongoDB Atlas, no lo escribas aquí>
DB_NAME=iglesia_venyve
CORS_ORIGINS=https://panel.iglesiavenyve.org
CORS_ORIGIN_REGEX=^https://panel\.iglesiavenyve\.org$
JWT_SECRET=cambia-esto-por-uno-seguro-openssl-rand-hex-32
MAX_AUDIO_BYTES=25165824
MAX_AUDIO_SECONDS=14400
MAX_BOARD_DOCUMENT_BYTES=10485760
```

5. **Deploy** → espera el build (~3–5 min).
6. **Settings → Networking → Generate Domain** → obtienes una URL pública (ej. `venyve-backend-production-xxxx.up.railway.app`).
7. Verifica abriendo `https://<tu-backend>.up.railway.app/docs` → debes ver Swagger UI.

---

## 2. Crear servicio **FRONTEND** en Railway

1. En el mismo proyecto Railway → **+ New** → **GitHub Repo** → selecciona el mismo repo `dwaine01/iglesia-venyve`.
2. Entra al nuevo servicio → **Settings → Config-as-code → Config Path** = `railway-frontend.toml`.
   > ⚠️ Esto es **lo más importante** — evita que ambos servicios construyan con `Dockerfile.backend`.
3. **Settings → Service Name**: `venyve-frontend`.
4. **Variables**:

```
REACT_APP_BACKEND_URL=https://iglesia-venyve-production.up.railway.app
WDS_SOCKET_PORT=443
NODE_ENV=production
CI=false
GENERATE_SOURCEMAP=false
```

> 🔴 **`REACT_APP_BACKEND_URL` se inyecta en build-time**. Si lo cambias después, debes hacer **Redeploy** (no basta con restart) para que el bundle de React lo tome.

5. **Deploy** → espera el build (~5–8 min, el primer build descarga deps).
6. **Settings → Networking → Generate Domain** → obtienes URL pública del frontend.
7. Abre esa URL → debe cargar el sitio.

> 💡 **Tip primer test**: temporalmente puedes poner `REACT_APP_BACKEND_URL` igual a la URL pública de Railway del backend (`https://iglesia-venyve-production.up.railway.app`). *(Nota: `panel.iglesiavenyve.org` es hoy el dominio del FRONTEND, no del backend — ver disclaimer al inicio de este documento.)*

---

## 3. Conectar dominios personalizados en Railway

### 3.1 Backend → `panel.iglesiavenyve.org`
1. Servicio `venyve-backend` → **Settings → Networking → Custom Domain** → **+ Custom Domain**.
2. Ingresa: `panel.iglesiavenyve.org`.
3. Railway te muestra un **CNAME target**, algo como `xxxxxxxx.up.railway.app`. **Cópialo** — lo necesitas para HostGator.

### 3.2 Frontend → `iglesiavenyve.org` y `www.iglesiavenyve.org`
1. Servicio `venyve-frontend` → **Settings → Networking → Custom Domain** → **+ Custom Domain**.
2. Ingresa: `www.iglesiavenyve.org` → te dará un **CNAME target**. **Cópialo.**
3. **+ Custom Domain** otra vez → `iglesiavenyve.org` (apex/root).
   - Railway te indicará si usar CNAME (HostGator soporta flattening de apex) o un registro `A` con IP.

---

## 4. Configurar DNS en **HostGator** (cPanel)

> Ruta: cPanel → **Domains → Zone Editor** → selecciona `iglesiavenyve.org` → **Manage**.

Reemplaza los `xxxxxxxx`/`yyyyyyyy` por los CNAME targets que te dió Railway.

| Tipo  | Nombre / Host | Valor                                                | TTL  |
|-------|---------------|------------------------------------------------------|------|
| CNAME | `panel`       | `xxxxxxxx.up.railway.app` (target del backend)       | 300  |
| CNAME | `www`         | `yyyyyyyy.up.railway.app` (target del frontend)      | 300  |
| CNAME | `@`           | `yyyyyyyy.up.railway.app` (target del frontend) *    | 300  |

\* **Apex (`@`)**: Si HostGator no acepta CNAME en `@`, usa un registro **A** con la IP que indique Railway, **o** crea un **redirect** en cPanel → Domains → Redirects de `iglesiavenyve.org` → `www.iglesiavenyve.org`.

### Limpieza importante
- **Borra** cualquier `A` previo en `@`, `www`, `panel` que apunte a HostGator (ej. `162.241.x.x`) o sobreescribirá el routing.
- **NO toques** registros **MX** (correo) ni **TXT** (SPF/DKIM/verificaciones).

---

## 5. Esperar propagación + HTTPS

- Propagación DNS: **5–30 min** (a veces hasta 1 hora).
- Railway emite **certificado SSL Let’s Encrypt** automáticamente cuando detecta el DNS bien.
- Verifica en https://dnschecker.org/ que `panel.iglesiavenyve.org`, `iglesiavenyve.org` y `www.iglesiavenyve.org` resuelvan al CNAME de Railway.
- En Railway, el dominio pasará de `DNS not configured` → **`Active`** (con candado verde).

---

## 6. Checklist final

- [ ] `https://panel.iglesiavenyve.org/docs` muestra Swagger UI del backend.
- [ ] `https://iglesiavenyve.org` carga el frontend.
- [ ] `https://www.iglesiavenyve.org` carga el frontend.
- [ ] Login/Registro funciona (DevTools → Network: las requests van a `https://panel.iglesiavenyve.org/api/...`).
- [ ] Sin errores CORS en consola.
- [ ] MongoDB conecta correctamente (revisa logs del backend en Railway).
- [ ] Login devuelve JWT y las llamadas autenticadas usan `Authorization: Bearer`; no se espera una cookie de sesión de la aplicación.

---

## 7. Troubleshooting rápido

| Síntoma | Causa | Solución |
|---|---|---|
| `502 Application failed to respond` | Backend no escucha en `$PORT` | Ya resuelto: `Dockerfile.backend` usa `${PORT}`. Re-deploy. |
| Frontend carga pero login falla | `REACT_APP_BACKEND_URL` mal configurado | Cambia variable en Railway (frontend) y **Redeploy** completo (build-time). |
| `Access-Control-Allow-Origin` error | `CORS_ORIGINS` no incluye el dominio | Backend → actualiza `CORS_ORIGINS` y redeploy. |
| `CORS_ORIGINS and CORS_ORIGIN_REGEX environment variables are required` | Falta configuración runtime porque `.env` no viaja en Git | Backend Production → define ambas variables en Railway; no uses `*`. |
| `ModuleNotFoundError: emergentintegrations` | Acoplamiento histórico de IA al runtime | La IA de Junta usa ahora `BoardAIProvider` HTTP opcional; no agregues ruedas ni índices privados. |
| `KeyError: MAX_AUDIO_BYTES` | Variables de límites no presentes en un environment antiguo | El backend usa políticas seguras de 24 MiB/4 horas/10 MiB y permite override con las tres variables documentadas. |
| `MongoServerSelectionError` | Atlas no permite la IP | Atlas → Network Access → `0.0.0.0/0`. |
| Build frontend falla por memoria | CRA usa mucha RAM | Añade `NODE_OPTIONS=--max_old_space_size=4096` en variables del frontend. |
| Build frontend falla por warnings | CRA trata warnings como errores | Ya resuelto: `Dockerfile.frontend` setea `CI=false`. |
| `DNS not configured` por más de 30 min | CNAME mal o caché | Valida en dnschecker.org, revisa que no haya `A` viejo conflictivo. |
| Backend OK pero `/api/...` da 404 | Frontend usa URL mal | Revisa que `REACT_APP_BACKEND_URL` **no** termine en `/`. |

---

## 8. Seed inicial de usuario pastor (opcional)

Si necesitas crear el primer usuario `pastor`:

**Local** (con env vars del backend):
```bash
cd backend
python seed_user.py
```

**O en Railway**: Settings → **Run a one-off command** en el servicio backend:
```
python seed_user.py
```

---

## 9. Rescate de acceso del pastor general (emergencia, sin scripts manuales)

Si la cuenta del pastor general queda bloqueada en producción y no hay otro
pastor disponible para usar el botón "Restablecer contraseña" del Panel
General, el backend trae un mecanismo de rescate que se aplica solo con
variables de entorno (sin shell, sin scripts, sin tocar Mongo a mano).

**Reglas del mecanismo** (`backend/admin_recovery.py`, se ejecuta en cada
arranque del backend):
- Solo actúa si **ambas** variables `ADMIN_RECOVERY_EMAIL` y
  `ADMIN_RECOVERY_PASSWORD` están presentes.
- La contraseña debe tener **mínimo 12 caracteres**; si es más corta, se
  ignora (deja un warning en los logs, nunca imprime la contraseña).
- Solo actúa sobre una cuenta **que ya existe** con rol `pastor`, `pastora`,
  `admin` o `superadmin`. Nunca crea cuentas nuevas ni cambia el rol de
  nadie.
- Es **idempotente**: guarda una huella (hash, nunca la contraseña) en la
  colección `system_recovery`. Mientras esa huella no cambie, los reinicios
  del backend no vuelven a tocar la cuenta — así, una vez que cambias la
  contraseña manualmente, Railway puede reiniciarse sin pisarla de nuevo.
- Fuerza el cambio de contraseña en el próximo ingreso
  (`must_change_password`) e invalida cualquier sesión vieja
  (`token_version`).
- También borra el bloqueo por intentos fallidos de login
  (`login_attempts`) de esa cuenta — así el rescate funciona incluso si la
  cuenta quedó bloqueada por 5 intentos fallidos, que es el caso típico de
  "cuenta bloqueada".

### Procedimiento paso a paso

1. Railway → servicio **backend** (`venyve-backend`) → **Variables**.
2. Agrega:
   ```
   ADMIN_RECOVERY_EMAIL=admin@venyve.com
   ADMIN_RECOVERY_PASSWORD=<una-contraseña-nueva-de-al-menos-12-caracteres>
   ```
3. Guarda — Railway hace **redeploy automático** del servicio backend.
   Espera a que el deploy termine (revisa los logs: deben decir
   `[admin_recovery] Contraseña de rescate aplicada para admin@venyve.com...`).
4. Entra al panel con ese correo y la contraseña nueva. El sistema te pedirá
   cambiarla de inmediato (pantalla "Crea tu clave personal").
5. Cambia la contraseña desde ahí.
6. **Borra ambas variables** (`ADMIN_RECOVERY_EMAIL` y
   `ADMIN_RECOVERY_PASSWORD`) de Railway y guarda de nuevo para que el
   redeploy las quite del entorno. Esto evita dejarlas expuestas de forma
   permanente.

> Si el correo no corresponde a una cuenta pastoral existente, o la
> contraseña no cumple el mínimo, el backend no hace nada (ni crea, ni
> cambia roles) — solo deja un warning en los logs de Railway.

> **Nota**: si la cuenta vuelve a bloquearse por fuerza bruta DESPUÉS de un
> rescate ya aplicado, reiniciar con las mismas dos variables no la vuelve a
> desbloquear (la huella de esa contraseña ya quedó registrada). En ese caso,
> usa una contraseña de rescate distinta a la anterior para forzar un nuevo
> rescate.

---

## 11. Migración de datos C11 (diagnóstico/aplicación)

La migración C11 (`backend/migration_c11.py`, endpoints `GET /api/admin/migrations/c11?mode=diagnose|apply`) es **idempotente y no destructiva**. Solo la pastora/pastor general o un coordinador general pueden ejecutarla (desde `/admin/migracion-c11` en el panel).

### Qué hace
- **Modo `diagnose`** (solo lectura, seguro en cualquier ambiente): reporta Personas con más de una cuenta, cuentas sin Persona asociada, Grupos Frontales con líder sin cuenta o con más de un líder activo, y expedientes de invasión (`process_enrollments` con `source="mentorship_outreach"`) sin `front_group_id`. Para estos últimos, propone un `front_group_id` **solo** cuando el mentor tiene una única rama de supervisión activa (sin ambigüedad).
- **Modo `apply`**: corrige **únicamente** los expedientes con propuesta clara (mentor con una sola rama). El resto de hallazgos (cuentas duplicadas, cuentas huérfanas, líderes duplicados) se reportan pero **nunca se tocan automáticamente** — requieren revisión pastoral manual caso por caso. Cada corrida de `apply` queda registrada en `migration_runs` (quién, cuándo, cuántos expedientes).

### Procedimiento recomendado
1. **Nunca ejecutes `apply` directamente en producción sin antes correr `diagnose` ahí mismo y revisar el reporte con la pastora/coordinador.**
2. Corre primero `diagnose` en producción (es de solo lectura, no cambia nada) y exporta/lee el resumen.
3. Si el número de "expedientes auto-corregibles" es razonable y se entiende el criterio (mentor con una única rama), corre `apply` desde el panel (`/admin/migracion-c11` → botón "Aplicar corrección segura").
4. Vuelve a correr `diagnose`: debe mostrar `enrollments_auto_fixable: 0` para los casos ya corregidos (comportamiento idempotente — correrlo de nuevo no cambia nada más).
5. Los hallazgos que **no** se auto-corrigen (duplicados, huérfanos, líderes múltiples) deben resolverse manualmente desde los paneles correspondientes (Persona 360, Grupos Frontales) — la migración solo los señala.

---

## 12. Historial de borrados administrativos

`/admin/historial-borrados` (solo pastoral/coordinador general) lista cada borrado **total y permanente** de una Invasión o un Grupo Frontal (colección `admin_deletions`): quién lo hizo, cuándo y el motivo escrito. No hay forma de deshacer un borrado total — por eso los diálogos de borrado en el panel siempre muestran primero un conteo ("se borrarán X hogares, Y visitas…") antes de confirmar.

---

## 13. Estructura de archivos de deploy

```
iglesia-venyve/
├── Dockerfile.backend          # FastAPI + uvicorn (puerto $PORT)
├── Dockerfile.frontend         # React build + serve (puerto $PORT)
├── railway.toml                # Backend (default config)
├── railway-frontend.toml       # Frontend (usar como Config Path)
├── .dockerignore               # Excluye node_modules, docs, etc.
├── backend/
│   ├── server.py
│   ├── seed_user.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── package.json
    ├── craco.config.js
    ├── src/
    └── .env.example
```

✅ Mismo proceso que `martinez-autoparts.com` y `ohioairbagreset.com`.
