import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

import { useAuth } from './AuthContext';
import { useInvasionToday } from './InvasionTodayContext';
import { beep, createAudioContext, createOutput, createPlayer, inAppBrowser, isIOS, micErrorCode, micPermission, openMicrophone, radioLog, speakerTest } from '../lib/radioAudio';

/* Radio GLOBAL: una sola conexión para toda la app (no por pantalla).
 * - Se conecta después del primer render si la persona tiene canal hoy y la
 *   mantiene al navegar; reconexión automática, latido cada 20 s y al volver
 *   a primer plano o recuperar la red.
 * - El navegador exige un toque para sonar: «Activar radio» (o cualquier
 *   toque si ya se activó antes) desbloquea el audio; se recuerda.
 * - Salida por un <audio> real + Media Session + Wake Lock (opcional) para
 *   que Android siga sonando en segundo plano cuando el sistema lo permite.
 *   iPhone corta audio y micrófono con la pantalla bloqueada o en otra app.
 * - Micrófono: el permiso se pide en «Activar radio» (toque explícito), NO en
 *   el primer «mantener para hablar»; queda abierto mientras el radio esté
 *   encendido (abrirlo en cada toque perdía los toques cortos) y solo se
 *   ENVÍA mientras se mantiene presionado. Una sola instancia para toda la app. */
const RadioContext = createContext(null);
/** Textos claros por estado del micrófono (qué pasó y qué hacer). */
export const MIC_MESSAGES = {
  unknown: 'Micrófono sin activar: toca «Probar y activar micrófono».',
  requesting: 'Pidiendo permiso del micrófono… acepta en el aviso del navegador.',
  ready: 'Micrófono listo.',
  denied: 'No diste permiso al micrófono. Toca «Reintentar» y elige «Permitir».',
  blocked: 'El micrófono está bloqueado para este sitio: Ajustes del navegador › Permisos del sitio › Micrófono › Permitir. Luego toca «Reintentar».',
  notfound: 'No se encontró ningún micrófono en este dispositivo.',
  busy: 'Otra app está usando el micrófono (llamada, grabadora, otra pestaña). Ciérrala y toca «Reintentar».',
  insecure: 'El micrófono solo funciona con conexión segura (https).',
  unsupported: 'Este navegador no permite usar el micrófono. Abre la plataforma en Chrome (Android) o Safari (iPhone).',
  noframes: 'El micrófono se abrió pero no entrega sonido. Toca «Reintentar»; si sigue, reinicia el navegador.',
  lost: 'El micrófono se desconectó (llamada u otra app). Toca «Reintentar».',
  inapp: 'Estás dentro de otra app (WhatsApp, Facebook o Instagram), que no da micrófono. Abre la plataforma en Chrome o Safari.',
};
const PREFS_KEY = 'venyve.radio.prefs';
const DEFAULT_PREFS = { enabled: true, activated: false, muted: false, volume: 1, wakeLock: true, vibrate: true, sound: true };
const PING_MS = 20 * 1000;
const STALE_MS = 50 * 1000;

function readPrefs() {
  try { return { ...DEFAULT_PREFS, ...(JSON.parse(localStorage.getItem(PREFS_KEY) || '{}')) }; } catch (error) { return DEFAULT_PREFS; }
}

export function useRadioChannel() {
  const { data, current } = useInvasionToday();
  const target = current || data?.active?.[0] || (data?.managed || []).find((item) => item.active_today);
  return target ? { campaign_id: target.campaign_id, name: target.name } : null;
}

export function RadioProvider({ children }) {
  const { API, user } = useAuth();
  const channel = useRadioChannel();
  const channelId = channel?.campaign_id || null;
  const [prefs, setPrefsState] = useState(readPrefs);
  const [status, setStatus] = useState('off'); // off | connecting | online | offline | error
  const [error, setError] = useState('');
  const [presence, setPresence] = useState({ count: 0, names: [], speaker: null });
  const [speaker, setSpeaker] = useState(null);
  const [talk, setTalk] = useState('idle'); // idle | requesting | talking
  const [seconds, setSeconds] = useState(0);
  const [audioReady, setAudioReady] = useState(false);
  // unknown | requesting | ready | denied | blocked | notfound | busy | insecure | unsupported | noframes | lost | inapp
  const [micState, setMicState] = useState(() => (inAppBrowser() ? 'inapp' : 'unknown'));
  const [eventsVersion, setEventsVersion] = useState(0); // cambia con mensajes de voz / turnos (la pantalla de Radio recarga)
  const [lastVoice, setLastVoice] = useState(null);
  const [ready, setReady] = useState(false);
  const r = useRef({ ws: null, ctx: null, out: null, player: null, mic: null, micOpening: null, micPermission: null, mode: 'off', holding: false, retry: 0, retryTimer: null,
                     pingTimer: null, lastSeen: 0, wake: null, chunks: [], channelId: null, fatal: false, prefs }).current;
  r.prefs = prefs;
  r.micStateNow = micState;

  const setPrefs = useCallback((patch) => {
    setPrefsState((current) => {
      const next = { ...current, ...(typeof patch === 'function' ? patch(current) : patch) };
      try { localStorage.setItem(PREFS_KEY, JSON.stringify(next)); } catch (error) { /* modo privado */ }
      return next;
    });
  }, []);

  // La conexión arranca después del primer render (no frena ninguna pantalla).
  useEffect(() => {
    const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 1200));
    const handle = idle(() => setReady(true), { timeout: 2500 });
    return () => (window.cancelIdleCallback ? window.cancelIdleCallback(handle) : clearTimeout(handle));
  }, []);

  const send = useCallback((payload) => {
    const ws = r.ws;
    if (!ws || ws.readyState !== 1) return false;
    ws.send(payload instanceof ArrayBuffer || ArrayBuffer.isView(payload) ? payload : JSON.stringify(payload));
    return true;
  }, [r]);
  const listening = audioReady && !prefs.muted && prefs.enabled;
  useEffect(() => { send({ type: 'listen', on: listening }); }, [listening, send, status]);

  // ------------------------------------------------------------ audio
  const ensureWake = useCallback(async () => {
    if (!r.prefs.wakeLock || !r.prefs.enabled || document.visibilityState !== 'visible' || r.wake || !navigator.wakeLock) return;
    try { r.wake = await navigator.wakeLock.request('screen'); r.wake.addEventListener?.('release', () => { r.wake = null; }); } catch (error) { r.wake = null; }
  }, [r]);
  const releaseWake = useCallback(() => { try { r.wake?.release?.(); } catch (error) { /* nada */ } r.wake = null; }, [r]);

  const mediaSession = useCallback((name) => {
    const session = navigator.mediaSession;
    if (!session) return;
    try {
      if (window.MediaMetadata) session.metadata = new window.MediaMetadata({ title: `Radio · ${name || 'Invasión'}`, artist: 'Ven y Ve 360', album: 'Radio de la invasión' });
      session.playbackState = 'playing';
      session.setActionHandler?.('pause', () => setPrefs({ muted: true }));
      session.setActionHandler?.('play', () => setPrefs({ muted: false }));
    } catch (error) { /* navegador sin Media Session completo */ }
  }, [setPrefs]);

  // iPhone (Safari 16.4+): tipo de sesión de audio. «playback»/«play-and-record» suenan aunque
  // el interruptor de silencio esté activado; con micrófono abierto debe ser «play-and-record».
  const audioSession = (type) => { try { if (navigator.audioSession && navigator.audioSession.type !== type) navigator.audioSession.type = type; } catch (error) { radioLog('AUDIO_SESSION_FAIL', error?.message); } };

  // ------------------------------------------------------------ micrófono (una sola instancia)
  const closeMic = useCallback(() => { r.mic?.close(); r.mic = null; audioSession('playback'); }, [r]);
  const prepareMic = useCallback(async () => {
    if (r.mic) return true;
    if (r.micOpening) return r.micOpening;
    if (inAppBrowser()) { r.micStateNow = 'inapp'; setMicState('inapp'); radioLog('MIC_INAPP', inAppBrowser()); return false; }
    if (!r.ctx) return false;
    setMicState('requesting');
    r.micOpening = (async () => {
      try {
        audioSession('play-and-record');
        r.mic = await openMicrophone(r.ctx, (chunk) => {
          if (r.mode === 'ptt') send(chunk);
          else if (r.mode === 'record') r.chunks.push(chunk);
        });
        r.mic.track?.addEventListener?.('ended', () => { radioLog('MIC_TRACK_ENDED'); r.mic = null; setMicState('lost'); });
        setMicState('ready');
        return true;
      } catch (error) {
        let code = micErrorCode(error);
        if (code === 'denied' && (await micPermission()) === 'denied') code = 'blocked';
        radioLog(`MIC_${code.toUpperCase()}`, `${error?.name}: ${error?.message}`);
        r.micStateNow = code; setMicState(code);
        return false;
      } finally { r.micOpening = null; }
    })();
    return r.micOpening;
  }, [r]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Desbloquea el audio (y, si `withMic`, pide/abre el micrófono). Debe
   * llamarse dentro de un toque del usuario. */
  const activate = useCallback(async ({ withMic = false } = {}) => {
    try {
      if (!r.ctx || r.ctx.state === 'closed') {
        r.ctx = createAudioContext();
        r.out = createOutput(r.ctx);
        r.player = createPlayer(r.ctx, r.out.node);
        r.ctx.onstatechange = () => setAudioReady(r.ctx?.state === 'running');
      }
      if (!r.mic) audioSession('playback');
      await r.ctx.resume();
      await r.out.start();
      r.out.setVolume(r.prefs.muted ? 0 : r.prefs.volume);
      setAudioReady(r.ctx.state === 'running');
      if (r.ctx.state === 'running') {
        setPrefs({ activated: true, enabled: true });
        mediaSession(channel?.name);
        ensureWake();
        // Micrófono: en el toque explícito, o en silencio si ya había permiso.
        if (withMic || r.micPermission === 'granted') prepareMic();
        return true;
      }
      radioLog('CTX_NOT_RUNNING', r.ctx.state);
    } catch (error) { radioLog('AUDIO_UNLOCK_FAIL', error?.message); setAudioReady(false); }
    return false;
  }, [r, setPrefs, mediaSession, ensureWake, channel?.name, prepareMic]);

  // Estado del permiso (si el navegador lo informa) y sus cambios.
  useEffect(() => {
    let status;
    const apply = (state) => {
      r.micPermission = state;
      if (state === 'denied') setMicState((current) => (current === 'inapp' ? current : 'blocked'));
      else if (state === 'granted') setMicState((current) => (current === 'blocked' || current === 'denied' ? 'unknown' : current));
    };
    (async () => {
      try { status = await navigator.permissions?.query({ name: 'microphone' }); } catch (error) { status = null; }
      if (!status) return;
      apply(status.state);
      status.onchange = () => apply(status.state);
    })();
    return () => { if (status) status.onchange = null; };
  }, [r]);

  useEffect(() => { r.out?.setVolume(prefs.muted ? 0 : prefs.volume); if (navigator.mediaSession) { try { navigator.mediaSession.playbackState = prefs.muted ? 'paused' : 'playing'; } catch (error) { /* nada */ } } }, [prefs.muted, prefs.volume, r]);
  useEffect(() => { if (prefs.wakeLock && prefs.enabled && audioReady) ensureWake(); else releaseWake(); }, [prefs.wakeLock, prefs.enabled, audioReady, ensureWake, releaseWake]);

  // Si ya se activó antes, el primer toque en cualquier parte de la app vuelve a desbloquear el audio.
  useEffect(() => {
    if (!channelId || !prefs.enabled || !prefs.activated || audioReady) return undefined;
    const unlock = () => { activate(); };  // con micrófono solo si ya había permiso
    document.addEventListener('pointerdown', unlock, { capture: true, once: true });
    return () => document.removeEventListener('pointerdown', unlock, { capture: true });
  }, [channelId, prefs.enabled, prefs.activated, audioReady, activate]);

  // ------------------------------------------------------------ conexión
  const disconnect = useCallback((reason = 'off') => {
    clearTimeout(r.retryTimer); clearInterval(r.pingTimer);
    const ws = r.ws; r.ws = null;
    if (ws) { ws.onclose = null; try { ws.close(); } catch (error) { /* ya cerrado */ } }
    if (r.mode === 'ptt') { r.mode = 'off'; r.mic?.setSending(false); }
    setTalk('idle'); setSpeaker(null); setStatus(reason);
  }, [r]);

  const connect = useCallback(() => {
    if (!r.channelId || r.fatal) return;
    if (r.ws && r.ws.readyState <= 1) return;
    clearTimeout(r.retryTimer);
    const token = localStorage.getItem('token') || '';
    if (!token) return;
    if (r.ticketPending) return;
    setStatus((current) => (current === 'online' ? current : 'connecting'));
    const channelId = r.channelId;
    const retryLater = () => {
      setStatus(navigator.onLine === false ? 'offline' : 'connecting');
      const delay = [800, 2000, 4000, 8000, 15000][Math.min(r.retry, 4)];
      r.retry += 1;
      r.retryTimer = setTimeout(connect, delay);
    };
    // Boleto de UN SOLO USO (60 s) para abrir el canal: la sesión nunca va en la dirección del WebSocket.
    r.ticketPending = true;
    fetch(`${API}/api/radio/ticket/${channelId}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.json().catch(() => ({})).then((data) => {
        if (!response.ok) { const failure = new Error(typeof data.detail === 'string' ? data.detail : 'Sin acceso al canal'); failure.status = response.status; throw failure; }
        return data.ticket;
      }))
      .then((ticket) => { r.ticketPending = false; if (r.channelId === channelId && !r.fatal) openSocket(ticket); })
      .catch((failure) => {
        r.ticketPending = false;
        if (r.channelId !== channelId) return;
        // Sin acceso (no participa, cerrado, fuera de fecha, sesión vencida): no se reintenta. Sin red: se reintenta.
        if (failure.status && failure.status < 500 && failure.status !== 429) { r.fatal = true; setError(failure.message); setStatus('error'); return; }
        retryLater();
      });
  }, [API, r]); // eslint-disable-line react-hooks/exhaustive-deps

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const openSocket = (ticket) => {
    const ws = new WebSocket(`${API.replace(/^http/, 'ws')}/api/radio/ws/${r.channelId}?ticket=${encodeURIComponent(ticket)}`);
    ws.binaryType = 'arraybuffer';
    r.ws = ws;
    ws.onopen = () => { r.retry = 0; r.lastSeen = Date.now(); };
    ws.onmessage = (event) => {
      r.lastSeen = Date.now();
      if (event.data instanceof ArrayBuffer) { if (!r.prefs.muted) r.player?.play(event.data); return; }
      let data;
      try { data = JSON.parse(event.data); } catch (error) { return; }
      const ping = (frequency, duration) => { if (r.ctx && r.prefs.sound && !r.prefs.muted) beep(r.ctx, frequency, duration, r.out?.node); };
      if (data.type === 'welcome') { setStatus('online'); setError(''); ws.send(JSON.stringify({ type: 'listen', on: Boolean(r.ctx?.state === 'running' && !r.prefs.muted && r.prefs.enabled) })); }
      else if (data.type === 'presence') { setPresence(data); setSpeaker(data.speaker); }
      else if (data.type === 'speaking') {
        setSpeaker(data.name); ping(660);
        if (r.prefs.vibrate && navigator.vibrate) { try { navigator.vibrate(60); } catch (error) { /* nada */ } }
      } else if (data.type === 'stopped') { setSpeaker(null); r.player?.reset(); setEventsVersion((value) => value + 1); }
      else if (data.type === 'busy') { setTalk('idle'); toast.message(`${data.speaker} está hablando; espera a que termine`, { id: 'radio-busy', duration: 2000 }); }
      else if (data.type === 'talk_granted') {
        if (!r.holding) { ws.send(JSON.stringify({ type: 'ptt_end' })); setTalk('idle'); return; }
        ping(990, 0.08);
        if (!r.mic) { radioLog('PTT_NO_MIC'); ws.send(JSON.stringify({ type: 'ptt_end' })); setTalk('idle'); return; }
        r.mode = 'ptt'; r.mic.setSending(true); setTalk('talking'); setSeconds(0);
      } else if (data.type === 'talk_timeout') { radioLog('PTT_TIMEOUT'); r.mode = 'off'; r.holding = false; r.mic?.setSending(false); setTalk('idle'); toast.message('Se cortó tu transmisión: no llegaba audio de tu micrófono', { id: 'radio-limit' }); }
      else if (data.type === 'talk_limit') { r.mode = 'off'; r.mic?.setSending(false); setTalk('idle'); toast.message('Se alcanzó el máximo de 60 s; vuelve a presionar para seguir', { id: 'radio-limit' }); }
      else if (data.type === 'voice_message') { setLastVoice(data); setEventsVersion((value) => value + 1); ping(520); }
      else if (data.type === 'error') {
        // Sin acceso a este canal (no participa, cerrado, fuera de fecha): no se reintenta.
        r.fatal = true; setError(data.detail || 'Sin acceso al canal'); setStatus('error');
      }
    };
    ws.onclose = () => {
      if (r.ws === ws) r.ws = null;
      clearInterval(r.pingTimer);
      if (r.mode === 'ptt') { r.mode = 'off'; r.mic?.setSending(false); }
      setTalk('idle'); setSpeaker(null);
      if (r.fatal || !r.channelId) return;
      setStatus(navigator.onLine === false ? 'offline' : 'connecting');
      const delay = [800, 2000, 4000, 8000, 15000][Math.min(r.retry, 4)];
      r.retry += 1;
      r.retryTimer = setTimeout(connect, delay);
    };
    // Latido: si no llega nada en ~50 s la conexión está muerta (red inestable) → se reabre.
    clearInterval(r.pingTimer);
    r.pingTimer = setInterval(() => {
      if (ws.readyState !== 1) return;
      if (Date.now() - r.lastSeen > STALE_MS) { try { ws.close(); } catch (error) { /* nada */ } return; }
      try { ws.send(JSON.stringify({ type: 'ping' })); } catch (error) { /* nada */ }
    }, PING_MS);
  };

  useEffect(() => {
    r.fatal = false; r.retry = 0;
    r.channelId = ready && user && prefs.enabled ? channelId : null;
    if (!r.channelId) { disconnect('off'); return undefined; }
    disconnect('connecting');
    connect();
    return () => disconnect('off');
  }, [ready, user, channelId, prefs.enabled, connect, disconnect, r]);

  // Volver a primer plano o recuperar la red: reconectar ya y reanudar el audio.
  useEffect(() => {
    const wake = () => {
      if (document.visibilityState !== 'visible') return;
      if (r.channelId && !r.fatal && (!r.ws || r.ws.readyState > 1)) { clearTimeout(r.retryTimer); r.retry = 0; connect(); }
      if (r.ctx && r.ctx.state !== 'running') r.ctx.resume().then(() => setAudioReady(r.ctx?.state === 'running')).catch(() => setAudioReady(false));
      if (r.prefs.wakeLock && r.prefs.enabled && r.ctx?.state === 'running') ensureWake();
    };
    const offline = () => setStatus((current) => (current === 'off' || current === 'error' ? current : 'offline'));
    document.addEventListener('visibilitychange', wake);
    window.addEventListener('online', wake);
    window.addEventListener('focus', wake);
    window.addEventListener('offline', offline);
    return () => { document.removeEventListener('visibilitychange', wake); window.removeEventListener('online', wake); window.removeEventListener('focus', wake); window.removeEventListener('offline', offline); };
  }, [r, connect, ensureWake]);

  // Al salir de la cuenta o desactivar: todo cerrado.
  useEffect(() => () => { disconnect('off'); closeMic(); releaseWake(); r.out?.close(); try { r.ctx?.close?.(); } catch (error) { /* nada */ } }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Contador mientras se habla.
  useEffect(() => {
    if (talk !== 'talking') return undefined;
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [talk]);

  // ------------------------------------------------------------ hablar (mantener)
  const pressStart = useCallback(() => {
    // Dentro del gesto: reanudar audio (iPhone lo suspende/interrumpe).
    try { if (r.ctx && r.ctx.state !== 'running') r.ctx.resume(); r.out?.resume(); } catch (error) { /* nada */ }
    if (status !== 'online' || r.mode === 'record') return;
    if (!r.mic) {
      // Sin micrófono listo NO se intenta transmitir (se perdía el toque): se prepara y se avisa.
      (async () => {
        if (!r.ctx || r.ctx.state !== 'running') await activate();
        if (await prepareMic()) toast.success('Micrófono listo: mantén presionado para hablar', { id: 'radio-mic' });
        else toast.error(MIC_MESSAGES[r.micStateNow] || MIC_MESSAGES.unsupported, { id: 'radio-mic', duration: 8000 });
      })();
      return;
    }
    if (speaker && talk === 'idle') { toast.message(`${speaker} está hablando; espera a que termine`, { id: 'radio-busy', duration: 2000 }); return; }
    r.holding = true; setTalk('requesting');
    send({ type: 'ptt_start' });
  }, [status, speaker, talk, activate, prepareMic, send, r]);
  const pressEnd = useCallback(() => {
    if (!r.holding) return;
    r.holding = false;
    if (r.mode === 'ptt') { r.mode = 'off'; r.mic?.setSending(false); }
    send({ type: 'ptt_end' }); setTalk('idle');
  }, [r, send]);
  // Soltar siempre: si la app pierde el foco o pasa a segundo plano mientras se mantiene.
  useEffect(() => {
    const release = () => { if (document.visibilityState === 'hidden' || !document.hasFocus()) pressEnd(); };
    window.addEventListener('blur', pressEnd);
    document.addEventListener('visibilitychange', release);
    return () => { window.removeEventListener('blur', pressEnd); document.removeEventListener('visibilitychange', release); };
  }, [pressEnd]);
  // Radio apagado o sin canal: se cierra el micrófono.
  useEffect(() => { if (!prefs.enabled || !channelId) { closeMic(); setMicState((current) => (current === 'ready' ? 'unknown' : current)); } }, [prefs.enabled, channelId, closeMic]);

  // Mensaje de voz (grabación para quien no estaba conectado).
  const recordStart = useCallback(async () => {
    if (talk !== 'idle') return false;
    if (!r.mic && !(await prepareMic())) return false;
    r.chunks = []; r.mode = 'record'; r.mic.setSending(true);
    return true;
  }, [talk, prepareMic, r]);
  const recordStop = useCallback(() => {
    if (r.mode !== 'record') return [];
    r.mode = 'off'; r.mic?.setSending(false);
    const chunks = r.chunks; r.chunks = [];
    return chunks;
  }, [r]);
  const micLevel = useCallback(() => r.mic?.level() || 0, [r]);
  const outputLevel = useCallback(() => r.out?.level() || 0, [r]);
  const testSpeaker = useCallback(async () => {
    if (!r.ctx || r.ctx.state !== 'running') await activate();
    if (r.ctx && r.out) speakerTest(r.ctx, r.out.node);
  }, [r, activate]);

  const value = useMemo(() => ({
    channel, status, error, presence, speaker, talk, seconds, audioReady, micState, prefs, setPrefs, activate, pressStart, pressEnd, prepareMic,
    micLevel, outputLevel, testSpeaker, inApp: inAppBrowser(), outputMode: r.out?.mode || null,
    recordStart, recordStop, eventsVersion, lastVoice, ios: isIOS(), connected: status === 'online',
    needsUnlock: Boolean(channelId && prefs.enabled && status !== 'error' && !audioReady),
  }), [channel, channelId, status, error, presence, speaker, talk, seconds, audioReady, micState, prefs, setPrefs, activate, pressStart, pressEnd, prepareMic, micLevel, outputLevel, testSpeaker, recordStart, recordStop, eventsVersion, lastVoice, r]);
  return <RadioContext.Provider value={value}>{children}</RadioContext.Provider>;
}

export function useRadio() {
  return useContext(RadioContext);
}
