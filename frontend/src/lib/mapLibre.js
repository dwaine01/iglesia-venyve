import { useEffect, useState } from 'react';

// MapLibre (≈800 kB) se descarga solo cuando una pantalla muestra un mapa,
// no en cada página. Mismos archivos locales de /vendor (sin dependencias nuevas).
let loading = null;

export function loadMapLibre() {
  if (typeof window === 'undefined') return Promise.reject(new Error('Sin navegador'));
  if (window.maplibregl) return Promise.resolve(window.maplibregl);
  if (loading) return loading;
  const base = process.env.PUBLIC_URL || '';
  loading = new Promise((resolve, reject) => {
    if (!document.querySelector('link[data-maplibre]')) {
      const css = document.createElement('link');
      css.rel = 'stylesheet'; css.href = `${base}/vendor/maplibre-gl.css`; css.dataset.maplibre = '1';
      document.head.appendChild(css);
    }
    const script = document.createElement('script');
    script.src = `${base}/vendor/maplibre-gl.js`; script.async = true;
    script.onload = () => (window.maplibregl ? resolve(window.maplibregl) : reject(new Error('MapLibre no disponible')));
    script.onerror = () => { loading = null; script.remove(); reject(new Error('No se pudo cargar el mapa')); };
    document.head.appendChild(script);
  });
  return loading;
}

// { maplibregl, failed }: maplibregl es null mientras carga.
export function useMapLibre() {
  const [state, setState] = useState(() => ({ maplibregl: typeof window !== 'undefined' ? window.maplibregl || null : null, failed: false }));
  useEffect(() => {
    if (state.maplibregl) return undefined;
    let active = true;
    loadMapLibre().then((lib) => { if (active) setState({ maplibregl: lib, failed: false }); }).catch(() => { if (active) setState({ maplibregl: null, failed: true }); });
    return () => { active = false; };
  }, [state.maplibregl]);
  return state;
}
