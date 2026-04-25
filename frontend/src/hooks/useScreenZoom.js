import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Hook para zoom independiente en una vista de pantalla externa
 * (LED gigante de la audiencia, TV teleprompter detrás del escenario,
 * etc.) — separado del zoom global del panel/laptop.
 *
 * Diferencia clave con `useDisplayScale`:
 *   - Aquí el zoom se aplica a un contenedor específico (no al <html>).
 *   - Se persiste por dispositivo con una clave propia, así la laptop de
 *     la pastora puede tener zoom 100% mientras el LED de la sala usa
 *     200% sin pisarse.
 *
 * Uso:
 *   const { zoom, setZoom, levels, containerRef } = useScreenZoom('led_audiencia', 1.5);
 *   return <div ref={containerRef}>...</div>;
 */

export const ZOOM_LEVELS = [
  { value: 1.0, label: '100%' },
  { value: 1.25, label: '125%' },
  { value: 1.5, label: '150%' },
  { value: 1.75, label: '175%' },
  { value: 2.0, label: '200%' },
  { value: 2.5, label: '250%' },
  { value: 3.0, label: '300%' },
];

const ALLOWED = ZOOM_LEVELS.map((l) => l.value);

function readZoom(key, fallback) {
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    const num = parseFloat(raw);
    if (!Number.isFinite(num)) return fallback;
    return ALLOWED.includes(num) ? num : fallback;
  } catch {
    return fallback;
  }
}

export function useScreenZoom(storageKey, defaultZoom = 1.0) {
  const containerRef = useRef(null);
  const [zoom, setZoomState] = useState(() => readZoom(storageKey, defaultZoom));

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    if (zoom === 1) {
      el.style.removeProperty('zoom');
    } else {
      // `zoom` es soportado en Chrome/Edge/Safari y Firefox 126+,
      // y escala TODO el subárbol incluido el texto, sin romper layout.
      el.style.zoom = String(zoom);
    }
  }, [zoom]);

  const setZoom = useCallback((value) => {
    const safe = ALLOWED.includes(value) ? value : defaultZoom;
    setZoomState(safe);
    try {
      window.localStorage.setItem(storageKey, String(safe));
    } catch {
      /* noop */
    }
  }, [storageKey, defaultZoom]);

  const increment = useCallback(() => {
    setZoomState((current) => {
      const idx = ALLOWED.indexOf(current);
      const next = idx < 0 || idx === ALLOWED.length - 1 ? ALLOWED[ALLOWED.length - 1] : ALLOWED[idx + 1];
      try { window.localStorage.setItem(storageKey, String(next)); } catch { /* noop */ }
      return next;
    });
  }, [storageKey]);

  const decrement = useCallback(() => {
    setZoomState((current) => {
      const idx = ALLOWED.indexOf(current);
      const next = idx <= 0 ? ALLOWED[0] : ALLOWED[idx - 1];
      try { window.localStorage.setItem(storageKey, String(next)); } catch { /* noop */ }
      return next;
    });
  }, [storageKey]);

  return { zoom, setZoom, increment, decrement, levels: ZOOM_LEVELS, containerRef };
}

export default useScreenZoom;
