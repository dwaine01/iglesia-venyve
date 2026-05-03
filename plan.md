# Plan: Manual Corporativo (Interactivo) – **La Ley de las 7 Semanas**
## Casa de Oración **Ven y Ve** – Primera Iglesia del Nazareno

### Church Details
- **Nombre**: Casa de Oración Ven y Ve
- **Nombre completo**: Primera Iglesia del Nazareno
- **Pastora**: Carmen Garcia
- **Logo**: Provisto por el usuario (integrado globalmente con mezcla para transparencia)

---

## Phase 1: POC – SKIPPED
No integraciones complejas externas. Es una plataforma CRUD con Auth + contenido + seguimiento.

---

## Phase 2: Full Application Development (Manual + UI Base)
> **Estado real hoy:** La app full-stack existe y corre. Introducción y Mapa están aprobados. Se rediseñaron Dashboard/Semana/Registro/Estadísticas para evitar “plain white”, se aplicó un estilo corporativo (navy/gold/turquoise), y se verificó que **compilan y cargan**.

### Backend (FastAPI + MongoDB)
- [x] Autenticación JWT (login/me)
- [x] Endpoint base de dashboard
- [x] Infraestructura Mongo + modelos/colecciones base
- [x] Sistema de consolidación por persona (People + Person_Checklists + Person_Progress) + RBAC 3 niveles *(ver Phase 6: será reemplazado)*
- [x] Dashboards role-based (pastor / líder / persona) *(ver Phase 6: será reemplazado)*
- [x] **Lógica dinámica de estado** (Excelente / Bien / Recién Iniciado / Meta Baja) basada en **tiempo vs progreso** *(ver Phase 6: será reemplazado por jerarquía)*
- [x] Fix bug: `pwd_context` no definido (hashing con bcrypt unificado)
- [x] Fix: email de persona `@consolidado.local` (rechazado por `EmailStr`) → `@consolidados.app`
- [x] Estructura de métricas/progreso global movida a Bitácora Evangelística (leader_journal) y agregados globales en dashboard *(ver Phase 6: será reemplazado)*

### Frontend (React)
- [x] Login funcional
- [x] Layout con sidebar + navegación por rol *(ver Phase 6: navegación cambiará a jerarquía 5 niveles)*
- [x] **Introducción** (animada, aprobada)
- [x] **Mapa 7 Semanas** (animado, aprobado)
- [x] Dashboard Líder actualizado *(será reemplazado en Phase 6)*
- [x] Dashboard Pastor actualizado *(será reemplazado en Phase 6)*
- [x] Mi Progreso (Persona) actualizado *(será reemplazado en Phase 6 por “Discípulo”)*
- [x] Componente reutilizable `StatusBadge` + `ProgressVsExpected` *(puede reutilizarse luego)*
- [x] Registro de Contactos rediseñado *(será reemplazado en Phase 6)*
- [x] SemanaPage (contenido y checklist UI; persistencia por persona existente) *(será reemplazado en Phase 6/Phase 7)*
- [~] Consistencia visual/animaciones en SemanaPage (mejorable)
- [x] Integración global de logo (Login, Layout, Dashboards, Presentación, Manual imprimible) con técnica tipo `mix-blend-mode: screen`

### Content Structure (7 Weeks)
1. **Semana 1**: Preparación / Oración Profética – Organización
2. **Semana 2**: Invasión – Contactados (NPT)
3. **Semana 3**: MCD – Asistencia
4. **Semana 4**: Liberación – LBS 1
5. **Semana 5**: Bendición – LBS 2
6. **Semana 6**: Sanidad – LBS 3
7. **Semana 7**: Retiro + Cierre (Mi llamado)

### Key Principles to Display
- Visión concreta (no abstracta)
- Procesos continuos
- Ley de la Hormiga
- Ley 30-60-100
- Persona → Discípulo → Obrero → Ministro

### User Stories (Actualizadas)
1. Como **pastor/líder**, puedo iniciar una **presentación sincronizada** con un código de 4 dígitos, controlarla desde un dispositivo (con notas privadas) y mostrar visuales limpios a una audiencia en otra pantalla.
2. Como **pastor/líder**, puedo acceder a un **manual imprimible en tamaño Carta (8.5×11)** con índice, introducción e infografías oficiales integradas.
3. Como **pastor/líder**, puedo **descargar un PDF 100% fiel** al preview en **Carta** (mismas páginas, sin reflow, sin añadir/quitar páginas), con **márgenes uniformes** y **folios no cubiertos**.

> Nota: las user stories de “consolidación por persona” se reemplazarán por el nuevo sistema jerárquico (Phase 6).

---

## Phase 2.5: Implementación Crítica – **Sistema de Gestión de Consolidación (Líder → Personas)**
> **Estado:** Implementado históricamente, pero **deprecado** por decisión del usuario: se reemplazará por el sistema jerárquico de 5 niveles (Phase 6).

---

## Phase 2.6: Refinamiento UI/Animación (Consistencia con Introducción/Mapa)
> **Objetivo:** mantener el estilo elegante corporativo navy/gold, **sin grandes áreas blancas**, con profundidad, gradientes sutiles y micro-interacciones.

- [~] Homologar fondos/gradientes en SemanaPage (sutil + textura) como Dashboard/Mapa
- [x] Estados UI motivadores (badges dinámicos + barras comparativas)
- [x] Responsive móvil aplicado ampliamente (sidebar colapsable, tablas a cards en móvil, stacking)
- [ ] Estados UI premium: loading skeletons, empty states motivadores, toasts consistentes

---

## Phase 2.7: Contenido Exacto del Transcrito (Checklist por Semana)
> **Objetivo:** que el manual refleje la lógica exacta enseñada (libros, prácticas, metas) y que el contenido sea mantenible.

- [~] Revisar Semana 1–7 y asegurar menciones/acciones específicas
- [ ] Extraer datos a config/JSON o endpoint para evitar SemanaPage gigante

---

## Phase 3: Testing & Bug Fixes — **COMPLETADA** ✅
> **Resultado:** QA integral de regresión ejecutado con `testing_agent` en backend y frontend.

---

## Phase 4: Presentación Sincronizada – Testing E2E + “Descargar PDF” — **COMPLETADA** ✅

### 4.x Overhaul Presentación (28 slides + Teleprompter + Pantallas Gigantes) — **COMPLETADA** ✅
> Esta fase se expandió significativamente por requerimientos del producto:

- [x] Expansión de slides **15 → 28** para calcar el manual físico
- [x] Rediseño de slide **“9 Puertas”** y sincronización con el flujo
- [x] Reescritura completa de **notas pastorales** (tono directo y confrontacional)
- [x] Implementación de **Teleprompter TV**: `/presentacion/notas/:CODIGO`
- [x] Toggle **Express/Completo** para notas en:
  - [x] Laptop presentador (`PresentacionPresenterPage`)
  - [x] TV Teleprompter (`PresentacionNotasPage`)
- [x] Auto-scroll al inicio al cambiar de slide (laptop + teleprompter)
- [x] Resúmenes `RESUMENES_NOTAS` (express) para los 28 slides

### 4.y Legibilidad en pantallas grandes — **COMPLETADA** ✅
- [x] Zoom independiente para **Pantalla LED espectador** (17×7 ft) con control flotante (+/−)
  - Default ajustado por feedback del usuario a **125%**
- [x] Zoom independiente para **TV Teleprompter** con control flotante (+/−)
  - Default **125%**
- [x] Título teleprompter sin truncar (`line-clamp-2`)

**Pendiente menor (P2):**
- [ ] Confirmar qué hacer con el bug de numeración duplicada “18” (¿reflejar el typo del manual físico o corregirlo digitalmente?)

---

## Phase 5: Refactorización (Mantenibilidad / Modularidad) — **POSPUESTA**
> Se mantiene pospuesta; Phase 6 implica un cambio estructural mayor de permisos/datos.

---

## Phase 6: Sistema Jerárquico de 5 Niveles (Maestro → Supervisor → Líder → Obrero → Discípulo) — **EN PLANIFICACIÓN / PRÓXIMO**
> **Objetivo:** Reemplazar completamente el modelo actual de consolidación (pastor/líder/persona + people/progress) por un **sistema de trabajo, supervisión, asignación de tareas y seguimiento** con escalafón de privilegios.

### Decisiones del Usuario (Confirmadas)
- **Reset total**: borrar el sistema actual de roles y arrancar de cero con **5 niveles**.
- **Habilitación**: soportar **2 vías**:
  1) **Códigos de invitación**
  2) **Creación directa** por el superior
- **Tope estricto**: cada **Obrero** puede tener **máximo 30 Discípulos** (bloqueo del 31).
- **Tareas/contenido**:
  - Por ahora (fase inicial), usar **Las 7 Semanas existentes** como base.
  - En fase posterior, agregar **tareas/videos/libros** (contenido “módulos”).
  - Aclaración importante: el usuario indicó dos requisitos que se integrarán en Phase 7:
    - **Tareas predeterminadas fijas** (plantillas)
    - **Cada nivel puede crear tareas para sus subordinados** (tareas personalizadas)
- **Fase 1 ahora (Phase 6.0)**: solo **estructura jerárquica + códigos + dashboards por rol** (sin videos/libros todavía).

### 6.1 Modelo de Datos (Backend - MongoDB)

#### Collection `users` (nueva, reemplaza la antigua)
```json
{
  "_id": "uuid",
  "email": "str (unique)",
  "password_hash": "str",
  "nombre": "str",
  "apellido": "str (opt)",
  "telefono": "str (opt)",
  "rol": "maestro|supervisor|lider|obrero|discipulo",
  "superior_id": "uuid|null",
  "created_by": "uuid|null",
  "active": true,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### Collection `invitations` (nueva)
```json
{
  "_id": "uuid",
  "code": "str (8 chars uppercase)",
  "generated_by": "uuid",
  "target_role": "str",
  "superior_id": "uuid",
  "expires_at": "datetime",
  "used_by": "uuid|null",
  "used_at": "datetime|null",
  "status": "active|used|expired|revoked",
  "created_at": "datetime"
}
```

### 6.2 Reglas de Permisos

#### Quién puede CREAR/HABILITAR a quién
- Maestro → cualquier rol
- Supervisor → Líder
- Líder → Obrero
- Obrero → Discípulo (**max 30**)
- Discípulo → nadie

#### Quién puede VER (jerarquía descendente recursiva)
- Maestro: TODOS
- Supervisor: sus Líderes + descendencia (Obreros/Discípulos)
- Líder: sus Obreros + Discípulos descendientes
- Obrero: sus Discípulos
- Discípulo: solo a sí mismo

### 6.3 Endpoints Backend Nuevos
- `POST /api/auth/seed-maestro` (one-time, primer maestro)
- `POST /api/auth/register-with-code` (registro público con invitación)
- `POST /api/users/create-direct` (crear usuario directo)
- `POST /api/users/invitations` (generar código)
- `GET /api/users/invitations` (mis códigos)
- `DELETE /api/users/invitations/{id}` (revocar)
- `GET /api/users/my-team` (árbol descendente)
- `GET /api/users/{id}` (con permiso jerárquico)
- `PUT /api/users/{id}` (editar)
- `DELETE /api/users/{id}` (desactivar)
- `GET /api/dashboard/hierarchy` (estadísticas por rol)

### 6.4 Endpoints/Collections a Eliminar (al ejecutar Phase 6)
- `/api/people/*` y colección `people`
- `/api/journal/*` y colección `leader_journal`
- endpoints de “pastores” y colecciones relacionadas (si existen)
- `person_checklists`, `person_progress`
- Páginas frontend dependientes: DashboardLider, DashboardPastor, MiProgreso, RegistroPage, BitacoraPage, EstadisticasPage, PastoresPage, SemanaPage

### 6.5 Endpoints/Funcionalidades a MANTENER (no tocar)
- Sistema de presentación sincronizada (slides, teleprompter, audiencia)
- Manual imprimible PDF (Playwright)
- Logo, design tokens, base visual

### 6.6 Frontend - Páginas Nuevas
- `/registro?code=ABCD1234` (público)
- `/dashboard` (por rol)
- `/equipo` (Mi Equipo: subordinados + generar invitación + crear directo)
- `/equipo/codigos` (códigos activos/usados/revocados)
- `/cuenta` (perfil)

### 6.7 Frontend - Componentes Nuevos
- `<RoleBadge />`
- `<HierarchyTree />`
- `<InvitationCodeCard />` (copiar + QR + expiración)
- `<TeamMemberRow />`
- `<CreateUserDialog />` (tabs: código vs directo)

### 6.8 Plan de Implementación (Orden)
1. [ ] Congelar y documentar el corte: **este deploy borrará usuarios/datos** (backup opcional)
2. [ ] Backend: nuevo modelo `users` + `invitations`
3. [ ] Backend: reescribir auth (seed maestro + register-with-code)
4. [ ] Backend: permisos jerárquicos (helpers: `can_create_role`, `can_view_user`)
5. [ ] Backend: endpoints `my-team` + dashboard jerárquico
6. [ ] Backend: **eliminar** endpoints/colecciones viejas (people/journal/progress)
7. [ ] Frontend: actualizar rutas y navegación (sidebar) para 5 roles
8. [ ] Frontend: página `/registro` con validación de código
9. [ ] Frontend: `/equipo` + `/equipo/codigos` + `/dashboard`
10. [ ] E2E: Maestro → Supervisor → Líder → Obrero → Discípulo + validación del límite 30
11. [ ] Deploy

### 6.9 Bloqueos y Decisiones Pendientes
- Email del Maestro inicial: **usar `admin@venyve.com`** (confirmado como default)
- Presentación: mantener funcionalidad; si hay referencias antiguas a user_id, se asume que la presentación es independiente del modelo de people.

---

## Phase 7 (Futura): Sistema de Tareas + Módulos (Videos/Libros) — **PENDIENTE**
> Se inicia luego de estabilizar Phase 6.

- Tareas **predeterminadas fijas** (plantillas) basadas en “Las 7 Semanas”
- Tareas **personalizadas** por nivel para subordinados
- Tracking de completitud por usuario (Discípulo) y visibilidad jerárquica
- Biblioteca de módulos: videos/libros por semana

---

## Status (Actualizado)
- **Fase 2–4:** COMPLETADAS ✅ (Manual + Presentación + PDF + Teleprompter + escalado para LED/TV)
- **Fase 5:** POSPUESTA
- **Fase 6:** PRÓXIMA (cambio estructural mayor; requiere reset de datos)
- **Bloqueadores:** definir ventana de corte / backup antes de borrar usuarios/datos
