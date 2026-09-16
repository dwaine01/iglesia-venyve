# REGLA FROZEN — UNA PERSONA, UNA FICHA 360

## Principio canónico

**ONE PERSON → ONE CANONICAL PROFILE 360 → MANY MODULES → DIFFERENT PERMISSIONS**

Toda Persona tiene una única ficha oficial: `/personas/{person_id}`. Líderes, mentores, consolidadores, discipuladores, coordinadores, pastores y otros responsables autorizados llegan al mismo Person Profile 360 y al mismo diseño aprobado.

Nunca se crean perfiles alternos por módulo, cargo o ministerio. Lo único que cambia por usuario es:

- capabilities explícitas;
- scope sobre Personas;
- privacidad por campo;
- acciones permitidas.

Cada módulo mantiene su propia colección y fuente de verdad. Membresía, Consolidación, Ley7, Discipulado, Familia, Célula, Ministerio, Asistencia y los demás dominios aportan resúmenes autorizados al agregador 360; no copian sus datos dentro de `persons` y no crean otra ficha.

## Regla de navegación

Cualquier nombre, fotografía o número VV mostrado por un módulo debe enlazar al componente canónico `PersonCanonicalLink` o directamente a `/personas/{person_id}`, sujeto a capability + scope.

## Estado visual

La estructura visual es estable para todos los usuarios autorizados. Los campos restringidos se omiten y los módulos sin permiso muestran `Acceso restringido`. Los módulos aún no construidos muestran `Módulo aún no disponible`. Ninguno inventa datos o estados.
