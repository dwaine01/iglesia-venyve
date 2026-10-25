import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { Loader2, Mic, MicOff, Pause, Play, Radio as RadioIcon, Send, Square, Trash2, Users, Volume2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { beep, createAudioContext, createPlayer, encodeWav, openMicrophone } from '../lib/radioAudio';

const VOICE_MAX_SECONDS = 60;
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleTimeString('es', { hour: 'numeric', minute: '2-digit' }) : '');
const newId = () => (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);

/** Radio de la invasión (R1): mantener para hablar con la app abierta. */
export default function RadioPage() {
  const { campaignId } = useParams();
  const { API, getAuthHeaders } = useAuth();
  const [state, setState] = useState(null);
  const [error, setError] = useState('');
  const [joined, setJoined] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | connecting | online | offline
  const [presence, setPresence] = useState({ count: 0, names: [], speaker: null });
  const [speaker, setSpeaker] = useState(null);
  const [talk, setTalk] = useState('idle'); // idle | requesting | talking
  const [micReady, setMicReady] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [recording, setRecording] = useState(null); // { started, chunks } | { blob, duration }
  const [busy, setBusy] = useState('');
  const [playing, setPlaying] = useState(null);
  const refs = useRef({ ws: null, ctx: null, mic: null, player: null, mode: 'off', holding: false, chunks: [], leaving: false, retry: 0, wake: null, audio: null });

  const loadState = useCallback(() => {
    axios.get(`${API}/api/radio/${campaignId}`, getAuthHeaders()).then((response) => { setState(response.data); setError(''); })
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo abrir el canal de radio')));
  }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { loadState(); }, [loadState]);

  // Audio (ArrayBuffer) va tal cual en binario; los avisos de turno van como JSON.
  const send = (payload) => {
    const ws = refs.current.ws;
    if (!ws || ws.readyState !== 1) return;
    ws.send(payload instanceof ArrayBuffer || ArrayBuffer.isView(payload) || typeof payload === 'string' ? payload : JSON.stringify(payload));
  };

  const connect = useCallback(() => {
    const r = refs.current;
    const base = API.replace(/^http/, 'ws');
    const token = localStorage.getItem('token') || '';
    setStatus('connecting');
    const ws = new WebSocket(`${base}/api/radio/ws/${campaignId}?token=${encodeURIComponent(token)}`);
    ws.binaryType = 'arraybuffer';
    r.ws = ws;
    ws.onopen = () => { r.retry = 0; };
    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) { r.player?.play(event.data); return; }
      const data = JSON.parse(event.data);
      if (data.type === 'welcome') setStatus('online');
      else if (data.type === 'presence') { setPresence(data); setSpeaker(data.speaker); }
      else if (data.type === 'speaking') { setSpeaker(data.name); if (r.ctx) beep(r.ctx, 660); }
      else if (data.type === 'stopped') { setSpeaker(null); r.player?.reset(); loadState(); }
      else if (data.type === 'busy') { setTalk('idle'); toast.message(`${data.speaker} está hablando; espera a que termine`, { id: 'radio-busy', duration: 2000 }); }
      else if (data.type === 'talk_granted') {
        if (!r.holding) { send({ type: 'ptt_end' }); setTalk('idle'); return; }
        if (r.ctx) beep(r.ctx, 990, 0.08);
        r.mode = 'ptt'; r.mic?.setSending(true); setTalk('talking'); setSeconds(0);
      } else if (data.type === 'talk_limit') { r.mode = 'off'; r.mic?.setSending(false); setTalk('idle'); toast.message('Se alcanzó el máximo de 60 s; vuelve a presionar para seguir', { id: 'radio-limit' }); }
      else if (data.type === 'voice_message') { setState((current) => (current ? { ...current, voice_messages: [data, ...current.voice_messages.filter((item) => item.message_id !== data.message_id)] } : current)); if (r.ctx) beep(r.ctx, 520); }
      else if (data.type === 'error') { r.leaving = true; setError(data.detail || 'Sin acceso al canal'); setStatus('offline'); }
    };
    ws.onclose = () => {
      r.ws = null; setTalk('idle'); setSpeaker(null);
      if (r.mode === 'ptt') { r.mode = 'off'; r.mic?.setSending(false); }
      if (r.leaving) { setStatus('offline'); return; }
      setStatus('connecting');
      const delay = [1000, 2000, 5000, 10000][Math.min(r.retry, 3)];
      r.retry += 1;
      setTimeout(() => { if (!refs.current.leaving) connect(); }, delay);
    };
  }, [API, campaignId, loadState]);

  const join = async () => {
    const r = refs.current;
    r.leaving = false;
    try {
      r.ctx = createAudioContext(); await r.ctx.resume();
      r.player = createPlayer(r.ctx);
    } catch (audioError) { toast.error('Este navegador no permite reproducir audio en vivo'); return; }
    try {
      r.mic = await openMicrophone(r.ctx, (chunk) => {
        if (r.mode === 'ptt') send(chunk);
        else if (r.mode === 'record') r.chunks.push(chunk);
      });
      setMicReady(true);
    } catch (micError) { setMicReady(false); toast.message('Sin permiso de micrófono: podrás escuchar, pero no hablar. Actívalo en los ajustes del navegador.', { duration: 6000 }); }
    try { r.wake = await navigator.wakeLock?.request('screen'); } catch (wakeError) { r.wake = null; }
    setJoined(true);
    connect();
  };
  const leave = useCallback(() => {
    const r = refs.current;
    r.leaving = true; r.mode = 'off';
    try { r.ws?.close(); } catch (closeError) { /* ya cerrado */ }
    r.mic?.close(); r.mic = null;
    r.ctx?.close?.(); r.ctx = null;
    r.wake?.release?.(); r.wake = null;
    r.audio?.pause();
    setJoined(false); setStatus('idle'); setMicReady(false);
  }, []);
  useEffect(() => () => leave(), [leave]);
  // Contador mientras se habla o se graba.
  useEffect(() => {
    if (talk !== 'talking' && !recording?.started) return undefined;
    const timer = setInterval(() => {
      setSeconds((value) => value + 1);
      if (recording?.started && (Date.now() - recording.started) / 1000 >= VOICE_MAX_SECONDS) stopRecording(); // eslint-disable-line no-use-before-define
    }, 1000);
    return () => clearInterval(timer);
  }, [talk, recording]); // eslint-disable-line react-hooks/exhaustive-deps

  const pressStart = (event) => {
    event.preventDefault();
    const r = refs.current;
    if (status !== 'online' || !micReady || recording || (speaker && talk === 'idle')) return;
    r.holding = true; setTalk('requesting'); send({ type: 'ptt_start' });
  };
  const pressEnd = () => {
    const r = refs.current;
    if (!r.holding) return;
    r.holding = false;
    if (r.mode === 'ptt') { r.mode = 'off'; r.mic?.setSending(false); }
    send({ type: 'ptt_end' }); setTalk('idle');
  };

  const startRecording = () => {
    const r = refs.current;
    if (!micReady || talk !== 'idle') return;
    r.chunks = []; r.mode = 'record'; r.mic.setSending(true);
    setSeconds(0); setRecording({ started: Date.now() });
  };
  const stopRecording = () => {
    const r = refs.current;
    if (r.mode !== 'record') return;
    r.mode = 'off'; r.mic?.setSending(false);
    const duration = Math.round((Date.now() - (recording?.started || Date.now())) / 100) / 10;
    setRecording(r.chunks.length ? { blob: encodeWav(r.chunks), duration, key: newId() } : null);
  };
  const sendRecording = async () => {
    if (!recording?.blob) return;
    setBusy('voice');
    try {
      const form = new FormData();
      form.append('audio', recording.blob, 'mensaje.wav'); form.append('duration_seconds', String(recording.duration)); form.append('client_request_id', recording.key);
      await axios.post(`${API}/api/radio/${campaignId}/messages`, form, getAuthHeaders());
      toast.success('Mensaje de voz enviado al canal', { id: 'radio-voice' }); setRecording(null); loadState();
    } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo enviar el mensaje de voz')); } finally { setBusy(''); }
  };
  const playMessage = async (message) => {
    const r = refs.current;
    if (playing === message.message_id) { r.audio?.pause(); setPlaying(null); return; }
    try {
      const response = await axios.get(`${API}/api/radio/${campaignId}/messages/${message.message_id}/audio`, { ...getAuthHeaders(), responseType: 'blob' });
      r.audio?.pause();
      const audio = new Audio(URL.createObjectURL(response.data));
      r.audio = audio; setPlaying(message.message_id);
      audio.onended = () => setPlaying(null);
      await audio.play();
    } catch (playError) { setPlaying(null); toast.error('No se pudo reproducir el mensaje'); }
  };

  if (error) return <div className="mx-auto max-w-xl p-4"><p className="rounded-xl border border-red-200 bg-red-50 p-4 text-base text-red-800" data-testid="radio-error">{error}</p></div>;
  if (!state) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  const othersSpeaking = speaker && talk !== 'talking';
  const pttDisabled = status !== 'online' || !micReady || Boolean(recording) || Boolean(othersSpeaking);
  return (
    <div className="mx-auto w-full max-w-xl space-y-4 p-4 sm:p-6" data-testid="radio-page">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0"><p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.2em] text-[#7A5F22]"><RadioIcon className="h-4 w-4" />Radio de la invasión</p><h1 className="truncate font-['Spectral'] text-2xl font-semibold text-[#101D36]">{state.name}</h1></div>
        {joined && <span className={`shrink-0 rounded-full border px-3 py-1 text-xs font-semibold ${status === 'online' ? 'border-[#bcd8c4] bg-[#eef5f0] text-[#2f6e47]' : 'border-amber-200 bg-amber-50 text-amber-800'}`} data-testid="radio-status">{status === 'online' ? 'Conectado' : status === 'connecting' ? 'Conectando…' : 'Sin conexión'}</span>}
      </header>
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" data-testid="radio-notice">Para escuchar, mantén esta pantalla <b>abierta y encendida</b>. Con la pantalla bloqueada o en otra app el teléfono corta el audio. El audio en vivo no se guarda.</p>

      {!joined
        ? <button type="button" onClick={join} className="inline-flex min-h-16 w-full items-center justify-center gap-2 rounded-2xl bg-[#132443] text-lg font-semibold text-white shadow" data-testid="radio-join"><Volume2 className="h-6 w-6" />Entrar al canal</button>
        : <>
          <div className="flex items-center justify-between gap-2 text-sm text-slate-600"><span className="flex items-center gap-1" data-testid="radio-presence"><Users className="h-4 w-4" />{presence.count} conectado(s)</span><button type="button" onClick={leave} className="min-h-10 font-semibold text-[#8f382f] underline" data-testid="radio-leave">Salir del canal</button></div>
          <div className={`flex min-h-14 items-center justify-center gap-2 rounded-xl border-2 px-3 text-center text-base font-semibold ${talk === 'talking' ? 'border-[#b91c1c] bg-[#fef2f2] text-[#7f1d1d]' : othersSpeaking ? 'border-[#2563eb] bg-[#e8eefb] text-[#1d4ed8]' : 'border-[#E8E5DE] bg-white text-slate-600'}`} data-testid="radio-speaker" aria-live="polite">
            {talk === 'talking' ? <><Mic className="h-5 w-5" />Estás hablando · {Math.max(0, state.max_talk_seconds - seconds)} s</> : othersSpeaking ? <><Volume2 className="h-5 w-5 animate-pulse" />{speaker} está hablando…</> : 'Canal libre'}
          </div>
          <div className="flex justify-center py-2">
            <button type="button" disabled={pttDisabled} onPointerDown={pressStart} onPointerUp={pressEnd} onPointerLeave={pressEnd} onPointerCancel={pressEnd} onContextMenu={(event) => event.preventDefault()}
              className={`flex h-48 w-48 touch-none select-none flex-col items-center justify-center gap-2 rounded-full text-lg font-bold text-white shadow-xl transition ${talk === 'talking' ? 'scale-105 bg-[#b91c1c]' : talk === 'requesting' ? 'bg-[#7f1d1d]' : 'bg-[#132443]'} disabled:bg-slate-400`} data-testid="radio-ptt" aria-label="Mantén presionado para hablar">
              {micReady ? <Mic className="h-12 w-12" /> : <MicOff className="h-12 w-12" />}
              <span className="px-6 text-center text-[15px] leading-5">{!micReady ? 'Sin micrófono' : talk === 'talking' ? 'Suelta para terminar' : othersSpeaking ? 'Espera tu turno' : 'Mantén presionado para hablar'}</span>
            </button>
          </div>

          <section className="space-y-2 rounded-2xl border border-[#E8E5DE] bg-white p-3" data-testid="radio-voice">
            <p className="text-base font-semibold text-[#101D36]">Mensaje de voz</p>
            <p className="text-sm text-slate-600">Queda en el canal {state.retention_days} días para quien no estaba conectado (máx. {VOICE_MAX_SECONDS} s).</p>
            {!recording && <button type="button" onClick={startRecording} disabled={!micReady || talk !== 'idle'} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border-2 border-[#132443] bg-white text-base font-semibold text-[#132443] disabled:opacity-50" data-testid="radio-record"><Mic className="h-5 w-5" />Grabar mensaje de voz</button>}
            {recording?.started && <button type="button" onClick={stopRecording} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#b91c1c] text-base font-semibold text-white" data-testid="radio-record-stop"><Square className="h-5 w-5" />Detener ({seconds} s)</button>}
            {recording?.blob && <div className="grid grid-cols-2 gap-2"><button type="button" onClick={() => setRecording(null)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-[#D9D4C7] text-base font-semibold text-[#101D36]" data-testid="radio-record-discard"><Trash2 className="h-5 w-5" />Descartar</button><button type="button" onClick={sendRecording} disabled={busy === 'voice'} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white" data-testid="radio-record-send">{busy === 'voice' ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}Enviar ({recording.duration} s)</button></div>}
          </section>
        </>}

      <section className="space-y-2" data-testid="radio-messages">
        <p className="text-base font-semibold text-[#101D36]">Mensajes de voz del canal</p>
        {state.voice_messages.length === 0 ? <p className="text-sm text-slate-500">Aún no hay mensajes de voz.</p> : <ul className="space-y-2">{state.voice_messages.map((message) => (
          <li key={message.message_id} className="flex items-center justify-between gap-2 rounded-xl border border-[#E8E5DE] bg-white p-2">
            <span className="min-w-0"><span className="block truncate text-[15px] font-semibold text-[#101D36]">{message.name}</span><span className="block text-xs text-slate-500">{fmtTime(message.created_at)} · {message.duration_seconds} s</span></span>
            <button type="button" onClick={() => playMessage(message)} className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-[#132443] text-white" aria-label={playing === message.message_id ? 'Pausar' : 'Escuchar'} data-testid={`radio-play-${message.message_id}`}>{playing === message.message_id ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}</button>
          </li>))}</ul>}
      </section>
      {state.talk_log.length > 0 && <details className="text-sm text-slate-600"><summary className="min-h-10 cursor-pointer py-2 font-semibold text-[#101D36]">Quién habló ({state.talk_log.length})</summary><ul className="space-y-1">{state.talk_log.map((item, index) => <li key={`${item.started_at}-${index}`}>{fmtTime(item.started_at)} · {item.name} · {item.seconds} s</li>)}</ul></details>}
    </div>
  );
}
