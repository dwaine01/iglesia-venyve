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
JWT_SECRET=cambia-esto-por-uno-seguro-openssl-rand-hex-32
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

---

## 7. Troubleshooting rápido

| Síntoma | Causa | Solución |
|---|---|---|
| `502 Application failed to respond` | Backend no escucha en `$PORT` | Ya resuelto: `Dockerfile.backend` usa `${PORT}`. Re-deploy. |
| Frontend carga pero login falla | `REACT_APP_BACKEND_URL` mal configurado | Cambia variable en Railway (frontend) y **Redeploy** completo (build-time). |
| `Access-Control-Allow-Origin` error | `CORS_ORIGINS` no incluye el dominio | Backend → actualiza `CORS_ORIGINS` y redeploy. |
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

## 9. Estructura de archivos de deploy

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
