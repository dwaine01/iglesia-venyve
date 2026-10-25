/* Dirección del servidor para todas las llamadas /api y WebSocket.
 *
 * En producción el panel reenvía /api al servidor (frontend/deploy/server.js): el navegador
 * habla con UN SOLO dominio, el del panel. Las tabletas Amazon Fire (Silk) no llegaban a
 * *.up.railway.app. Se activa al compilar con REACT_APP_API_SAME_ORIGIN=1 (Dockerfile.frontend).
 * Sin eso (desarrollo local) se usa REACT_APP_BACKEND_URL como siempre. */
const configured = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/+$/, '');
const sameOrigin = process.env.REACT_APP_API_SAME_ORIGIN === '1' && typeof window !== 'undefined' && /^https?:$/.test(window.location.protocol);

export const API_BASE = sameOrigin ? window.location.origin : configured;
/** El servidor directo (sin pasar por el panel): solo para el diagnóstico de la tableta. */
export const DIRECT_BACKEND_URL = configured;
export const API_SAME_ORIGIN = sameOrigin;
