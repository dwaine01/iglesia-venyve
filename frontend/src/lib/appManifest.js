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

/** Enlace del dispositivo: el de la dirección (y se guarda) o, si se abrió el acceso directo, el guardado. */
export function rememberedToken(key, token) {
  try {
    if (token) { localStorage.setItem(key, token); return token; }
    return localStorage.getItem(key) || '';
  } catch { return token || ''; }
}
