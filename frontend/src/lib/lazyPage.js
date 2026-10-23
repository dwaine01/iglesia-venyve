import { lazy } from 'react';

// Carga diferida por ruta: cada módulo baja su propio archivo JS solo cuando se
// abre (o antes, en segundo plano, con `prefetchPages`). El login ya no tiene
// que descargar el código de todos los módulos.
const loaders = [];
const RELOAD_KEY = 'lazy-page-reloaded';

function withRetry(loader) {
  return () => loader().then((module) => {
    try { sessionStorage.removeItem(RELOAD_KEY); } catch (error) { /* sin almacenamiento */ }
    return module;
  }).catch((error) => {
    // Tras un despliegue nuevo, los archivos con el hash anterior ya no existen:
    // se recarga la página UNA vez para tomar la versión nueva.
    let reloaded = false;
    try { reloaded = sessionStorage.getItem(RELOAD_KEY) === '1'; } catch (storageError) { /* sin almacenamiento */ }
    if (!reloaded && /Loading (CSS )?chunk|ChunkLoadError|Failed to fetch dynamically imported module/i.test(String(error?.message || error?.name))) {
      try { sessionStorage.setItem(RELOAD_KEY, '1'); } catch (storageError) { /* sin almacenamiento */ }
      window.location.reload();
      return new Promise(() => {});
    }
    throw error;
  });
}

export function lazyPage(loader) {
  const load = withRetry(loader);
  loaders.push(loader);
  const Component = lazy(load);
  Component.preload = loader;
  return Component;
}

// Precarga en segundo plano, de a uno y solo cuando el navegador está libre,
// el código de todos los módulos (no sus datos: los permisos los sigue
// validando el backend). Respeta el modo "ahorro de datos".
let started = false;
export function prefetchPages() {
  if (started || typeof window === 'undefined') return;
  const connection = navigator.connection || {};
  if (connection.saveData || /(^|-)2g$/.test(connection.effectiveType || '')) return;
  started = true;
  const queue = [...loaders];
  const idle = window.requestIdleCallback || ((callback) => window.setTimeout(() => callback({ timeRemaining: () => 0 }), 300));
  const next = () => {
    const loader = queue.shift();
    if (!loader) return;
    loader().catch(() => {}).finally(() => idle(next, { timeout: 2000 }));
  };
  // Espera un momento para no competir con la primera pantalla tras el login.
  window.setTimeout(() => idle(next, { timeout: 2000 }), 1500);
}
