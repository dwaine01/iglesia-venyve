import { useEffect, useState, useCallback } from 'react';

/**
 * Hook para gestionar el "Modo Pantalla Gigante" del panel.
 *
 * Aplica un `zoom` CSS al <html> escalando TODO de forma proporcional
 * (texto, imagenes, espaciados, sidebar, modales, etc.) sin romper la
 * disposicion. La preferencia se persiste por dispositivo en localStorage,
 * de modo que la laptop conectada al TV LED del auditorio mantiene el
 * tamano configurado aunque se recargue la pagina.
 *
 * Niveles:
 *   - 1.00  Normal       -> Uso diario en laptop / tablet
 *   - 1.35  Grande       -> Pantallas medianas / Smart TV cercano
 *   - 1.70  Gigante      -> Pantalla LED del auditorio (17 x 7 ft)
 */

const STORAGE_KEY = 'venyve_display_scale';

export const SCALE_LEVELS = [
  { value: 1.0, label: 'Normal', description: 'Laptop / Tablet', shortLabel: '100%' },
  { value: 1.35, label: 'Grande', description: 'Pantalla mediana', shortLabel: '135%' },
  { value: 1.7, label: 'Gigante', description: 'Pantalla LED auditorio', shortLabel: '170%' },
];

const DEFAULT_SCALE = 1.0;
const ALLOWED_VALUES = SCALE_LEVELS.map((l) => l.value);

function readScaleFromStorage() {
  if (typeof window === 'undefined') return DEFAULT_SCALE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SCALE;
    const num = parseFloat(raw);
    if (!Number.isFinite(num)) return DEFAULT_SCALE;
    // Solo aceptar valores conocidos para evitar zooms raros
    return ALLOWED_VALUES.includes(num) ? num : DEFAULT_SCALE;
  } catch {
    return DEFAULT_SCALE;
  }
}

function applyScaleToDOM(scale) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (scale === 1) {
    root.style.removeProperty('zoom');
  } else {
    // `zoom` escala el documento entero conservando posiciones relativas y
    // proporciones. Soportado en Chrome, Edge, Safari y Firefox 126+.
    root.style.zoom = String(scale);
  }
  // Marca para CSS condicional si en el futuro hace falta
  root.dataset.displayScale = String(scale);
}

export function useDisplayScale() {
  const [scale, setScaleState] = useState(() => readScaleFromStorage());

  // Aplicar al cargar y cada vez que cambie
  useEffect(() => {
    applyScaleToDOM(scale);
  }, [scale]);

  const setScale = useCallback((nextValue) => {
    const safe = ALLOWED_VALUES.includes(nextValue) ? nextValue : DEFAULT_SCALE;
    setScaleState(safe);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(safe));
    } catch {
      /* noop */
    }
  }, []);

  return { scale, setScale, levels: SCALE_LEVELS };
}

export default useDisplayScale;
