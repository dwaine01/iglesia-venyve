import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';

/* Bienvenida sincronizada: una sola posición (registration_id + versión) que comparten todas las pantallas y el
 * panel del operador. Tiempo real por WebSocket con boleto de un solo uso (el enlace nunca va en su dirección).
 * Respaldo: si el WebSocket no conecta (p. ej. el navegador de ProPresenter), se consulta cada 2 s y se mueve
 * por HTTP con la misma regla de versión. Al reconectar, el servidor manda el estado actual. */

const RETRY_MS = [2000, 4000, 8000, 15000];

export function useWelcomeSync({ api, mode, linkToken, authHeaders, onNamesChanged, enabled = true }) {
  const [position, setPosition] = useState(null);
  const [live, setLive] = useState(false);
  const socket = useRef(null);
  const latest = useRef(null);
  const namesChanged = useRef(onNamesChanged);
  namesChanged.current = onNamesChanged;
  // screen = pantalla de la pastora (lee y mueve) · stage = pantalla gigante (solo lee) · operator = panel con sesión.
  const byLink = mode === 'screen' || mode === 'stage';
  const base = mode === 'screen' ? `${api}/api/screen/welcome` : mode === 'stage' ? `${api}/api/stage/welcome` : `${api}/api/visitors/welcome`;
  const headers = useCallback(() => (byLink ? { headers: { 'X-Link-Token': linkToken } } : authHeaders()), [byLink, linkToken, authHeaders]);

  const accept = useCallback((next) => {
    // Nunca se retrocede a una versión vieja (llegan en desorden entre WebSocket y consultas).
    if (!next || next.version === undefined) return;
    if (latest.current && latest.current.service_key === next.service_key && next.version < latest.current.version) return;
    latest.current = next;
    setPosition(next);
  }, []);

  useEffect(() => {
    if (!enabled || (byLink && !linkToken)) return undefined;
    let alive = true;
    let attempt = 0;
    let retryTimer = null;
    let pingTimer = null;
    const connect = async () => {
      if (!alive || typeof window.WebSocket !== 'function') return;
      try {
        const { data } = await axios.post(`${base}/ticket`, null, { ...headers(), timeout: 8000 });
        if (!alive) return;
        const ws = new window.WebSocket(`${api.replace(/^http/, 'ws')}/api/visitors/welcome/ws?ticket=${encodeURIComponent(data.ticket)}`);
        socket.current = ws;
        ws.onopen = () => { attempt = 0; setLive(true); pingTimer = setInterval(() => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'ping' })); }, 25000); };
        ws.onmessage = (event) => {
          let message;
          try { message = JSON.parse(event.data); } catch { return; }
          if (message.type === 'position') { accept(message); if (mode === 'stage') namesChanged.current?.(); }
          if (message.type === 'names_changed') namesChanged.current?.();
        };
        ws.onclose = () => {
          clearInterval(pingTimer);
          if (socket.current === ws) socket.current = null;
          setLive(false);
          if (alive) retryTimer = setTimeout(connect, RETRY_MS[Math.min(attempt++, RETRY_MS.length - 1)]);
        };
      } catch {
        setLive(false);
        if (alive) retryTimer = setTimeout(connect, RETRY_MS[Math.min(attempt++, RETRY_MS.length - 1)]);
      }
    };
    connect();
    return () => { alive = false; clearTimeout(retryTimer); clearInterval(pingTimer); socket.current?.close(); socket.current = null; };
  }, [enabled, mode, byLink, linkToken, base, api, headers, accept]);

  const move = useCallback(async (action) => {
    if (mode === 'stage') return; // la pantalla gigante solo lee
    const version = latest.current?.version ?? 0;
    const ws = socket.current;
    if (ws && ws.readyState === 1) { ws.send(JSON.stringify({ type: 'move', action, version })); return; }
    try { accept((await axios.post(`${base}/position`, { action, version }, { ...headers(), timeout: 8000 })).data); } catch { /* sin conexión: se reintenta al presionar otra vez */ }
  }, [mode, base, headers, accept]);

  return { position, live, move, accept };
}
