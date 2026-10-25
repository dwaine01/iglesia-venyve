// Acceso directo tipo app para los enlaces de visitantes: cada página usa su
// propio manifest (nombre corto «Registro» o «Bienvenida», su dirección y
// pantalla completa) y su título para iPhone/iPad. El enlace secreto se guarda en
// el equipo para que el acceso directo abra directo, sin página principal ni login.
import { useEffect } from 'react';

export function useAppManifest(manifest, title) {
  useEffect(() => {
    const link = document.getElementById('app-manifest');
    const meta = document.getElementById('apple-app-title');
    const previous = [link?.getAttribute('href'), meta?.getAttribute('content')];
    link?.setAttribute('href', manifest);
    meta?.setAttribute('content', title);
    return () => {
      if (link && previous[0]) link.setAttribute('href', previous[0]);
      if (meta && previous[1]) meta.setAttribute('content', previous[1]);
    };
  }, [manifest, title]);
}

/** Tras conectar BIEN: guarda el código corto en el equipo (para el acceso directo) y, si se abrió
 * con el enlace largo anterior, pasa a la dirección corta sin recargar. */
export function adoptShortPath(key, shortPath) {
  if (!shortPath) return;
  try { localStorage.setItem(key, shortPath.split('/').pop()); } catch { /* sin almacenamiento */ }
  if (window.location.pathname !== shortPath) window.history.replaceState(window.history.state, '', `${shortPath}${window.location.search}`);
}

/** Enlace del dispositivo: el de la dirección o, si se abrió el acceso directo, el guardado en el equipo. */
export function rememberedToken(key, token) {
  // Solo se lee: se guarda al conectar bien (así un código mal escrito no borra el bueno).
  if (token) return token;
  try { return localStorage.getItem(key) || ''; } catch { return ''; }
}
