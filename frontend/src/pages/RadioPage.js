import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { Loader2, Mic, MicOff, Pause, Speaker, Play, Radio as RadioIcon, Send, Square, Trash2, Users, Volume2, VolumeX } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { useRadio } from '../context/RadioContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { encodeWav } from '../lib/radioAudio';
import { LevelBar, MicStatus, useLiveLevel } from '../components/invasions/RadioDock';

const VOICE_MAX_SECONDS = 60;
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleTimeString('es', { hour: 'numeric', minute: '2-digit' }) : '');
const newId = () => (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);

function Toggle({ label, hint, checked, onChange, testId }) {
  return (
    <label className="flex min-h-12 items-center justify-between gap-3 py-1">
      <span className="min-w-0"><span className="block text-[15px] font-semibold text-[#101D36]">{label}</span>{hint && <span className="block text-xs text-slate-500">{hint}</span>}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="h-6 w-6 shrink-0 accent-[#132443]" data-testid={testId} />
    </label>
  );
}

/** Radio de la invasión. La conexión en vivo es GLOBAL (RadioContext): se
 * escucha en cualquier pantalla; aquí están el botón grande, los ajustes,
 * los mensajes de voz (30 días) y el registro de quién habló. */
export default function RadioPage() {
  const { campaignId } = useParams();
  const { API, getAuthHeaders } = useAuth();
  const radio = useRadio();
  const [state, setState] = useState(null);
  const [error, setError] = useState('');
  const [recording, setRecording] = useState(null); // { started } | { blob, duration, key }
  const [recSeconds, setRecSeconds] = useState(0);
  const [busy, setBusy] = useState('');
  const [playing, setPlaying] = useState(null);
  const [audio, setAudio] = useState(null);

  const loadState = useCallback(() => {
    axios.get(`${API}/api/radio/${campaignId}`, getAuthHeaders()).then((response) => { setState(response.data); setError(''); })
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo abrir el canal de radio')));
  }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { loadState(); }, [loadState, radio?.eventsVersion]);
  useEffect(() => () => audio?.pause(), [audio]);

  const stopRecording = useCallback(() => {
    const chunks = radio.recordStop();
    setRecording((current) => (chunks.length && current?.started ? { blob: encodeWav(chunks), duration: Math.round((Date.now() - current.started) / 100) / 10, key: newId() } : null));
  }, [radio]);
  useEffect(() => {
    if (!recording?.started) return undefined;
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - recording.started) / 1000);
      setRecSeconds(elapsed);
      if (elapsed >= VOICE_MAX_SECONDS) stopRecording();
    }, 500);
    return () => clearInterval(timer);
  }, [recording, stopRecording]);

  if (error) return <div className="mx-auto max-w-xl p-4"><p className="rounded-xl border border-red-200 bg-red-50 p-4 text-base text-red-800" data-testid="radio-error">{error}</p></div>;
  if (!state || !radio) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;

  const sameChannel = radio.channel?.campaign_id === campaignId;
  const live = sameChannel && radio.prefs.enabled;
  const talking = radio.talk === 'talking';
  const othersSpeaking = radio.speaker && !talking;
  const pttDisabled = !live || radio.status !== 'online' || Boolean(recording) || Boolean(othersSpeaking);
  const micReady = radio.micState === 'ready';
  const startPress = (event) => { event.preventDefault(); event.currentTarget.setPointerCapture?.(event.pointerId); radio.pressStart(); };
  const startRecording = async () => { if (await radio.recordStart()) { setRecSeconds(0); setRecording({ started: Date.now() }); } };
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
    if (playing === message.message_id) { audio?.pause(); setPlaying(null); return; }
    try {
      const response = await axios.get(`${API}/api/radio/${campaignId}/messages/${message.message_id}/audio`, { ...getAuthHeaders(), responseType: 'blob' });
      audio?.pause();
      const element = new Audio(URL.createObjectURL(response.data));
      setAudio(element); setPlaying(message.message_id);
      element.onended = () => setPlaying(null);
      await element.play();
    } catch (playError) { setPlaying(null); toast.error('No se pudo reproducir el mensaje'); }
  };
  const statusLabel = !radio.prefs.enabled ? 'Radio apagado' : radio.status === 'online' ? (radio.audioReady ? 'Escuchando' : 'Conectado · sin audio') : radio.status === 'offline' ? 'Sin red · reintentando' : 'Conectando…';

  return (
    <div className="mx-auto w-full max-w-xl space-y-4 p-4 sm:p-6" data-testid="radio-page">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0"><p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.2em] text-[#7A5F22]"><RadioIcon className="h-4 w-4" />Radio de la invasión</p><h1 className="truncate font-['Spectral'] text-2xl font-semibold text-[#101D36]">{state.name}</h1></div>
        {sameChannel && <span className={`shrink-0 rounded-full border px-3 py-1 text-xs font-semibold ${radio.status === 'online' && radio.audioReady && radio.prefs.enabled ? 'border-[#bcd8c4] bg-[#eef5f0] text-[#2f6e47]' : 'border-amber-200 bg-amber-50 text-amber-800'}`} data-testid="radio-status">{statusLabel}</span>}
      </header>
      <div className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" data-testid="radio-notice">
        <p>Escuchas el radio en <b>cualquier pantalla</b> de la plataforma mientras esté abierta; para responder, mantén presionado el micrófono.</p>
        {radio.ios
          ? <p><b>iPhone:</b> para escuchar, mantén la app abierta y la pantalla encendida. Con la pantalla bloqueada o en otra app, el iPhone corta el audio y el micrófono.</p>
          : <p><b>Android:</b> con «Mantener pantalla encendida» sigue sonando; si cambias de app o se apaga la pantalla, puede seguir sonando mientras el sistema lo permita (ahorro de batería puede cortarlo).</p>}
        <p>El audio en vivo no se guarda; solo quién habló y cuándo.</p>
      </div>

      {!sameChannel && <p className="rounded-xl border border-slate-200 bg-white p-3 text-sm text-slate-600">El radio en vivo está conectado a la invasión de hoy{radio.channel ? ` («${radio.channel.name}»)` : ''}. Aquí puedes escuchar los mensajes de voz de este canal.</p>}

      {sameChannel && !radio.prefs.enabled && <button type="button" onClick={() => { radio.setPrefs({ enabled: true }); radio.activate({ withMic: true }); }} className="inline-flex min-h-16 w-full items-center justify-center gap-2 rounded-2xl bg-[#132443] text-lg font-semibold text-white shadow" data-testid="radio-enable"><Volume2 className="h-6 w-6" />Encender radio</button>}
      {live && radio.needsUnlock && <button type="button" onClick={() => radio.activate({ withMic: true })} className="inline-flex min-h-16 w-full items-center justify-center gap-2 rounded-2xl bg-[#132443] text-lg font-semibold text-white shadow" data-testid="radio-join"><Volume2 className="h-6 w-6" />Activar radio</button>}

      {live && <>
        <div className="flex items-center justify-between gap-2 text-sm text-slate-600"><span className="flex items-center gap-1" data-testid="radio-presence"><Users className="h-4 w-4" />{radio.presence.count} conectado(s)</span>
          <button type="button" onClick={() => radio.setPrefs({ muted: !radio.prefs.muted })} className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-[#D9D4C7] bg-white px-3 font-semibold text-[#101D36]" data-testid="radio-mute">{radio.prefs.muted ? <><VolumeX className="h-4 w-4" />Silenciado</> : <><Volume2 className="h-4 w-4" />Silenciar</>}</button>
        </div>
        <div className={`flex min-h-14 items-center justify-center gap-2 rounded-xl border-2 px-3 text-center text-base font-semibold ${talking ? 'border-[#b91c1c] bg-[#fef2f2] text-[#7f1d1d]' : othersSpeaking ? 'border-[#2563eb] bg-[#e8eefb] text-[#1d4ed8]' : 'border-[#E8E5DE] bg-white text-slate-600'}`} data-testid="radio-speaker" aria-live="polite">
          {talking ? <><Mic className="h-5 w-5" />Estás hablando · {Math.max(0, state.max_talk_seconds - radio.seconds)} s</> : othersSpeaking ? <><Volume2 className="h-5 w-5 animate-pulse" />{radio.speaker} está hablando…</> : 'Canal libre'}
        </div>
        <div className="flex justify-center py-2">
          <button type="button" disabled={pttDisabled} onPointerDown={startPress} onPointerUp={radio.pressEnd} onPointerCancel={radio.pressEnd} onLostPointerCapture={radio.pressEnd} onContextMenu={(event) => event.preventDefault()}
            className={`flex h-48 w-48 touch-none select-none flex-col items-center justify-center gap-2 rounded-full text-lg font-bold text-white shadow-xl transition ${talking ? 'scale-105 bg-[#b91c1c]' : radio.talk === 'requesting' ? 'bg-[#7f1d1d]' : 'bg-[#132443]'} disabled:bg-slate-400`} data-testid="radio-ptt" aria-label="Mantén presionado para hablar">
            {!micReady ? <MicOff className="h-12 w-12" /> : <Mic className="h-12 w-12" />}
            <span className="px-6 text-center text-[15px] leading-5">{!micReady && !talking ? 'Toca para activar el micrófono' : talking ? 'Suelta para terminar' : othersSpeaking ? 'Espera tu turno' : 'Mantén presionado para hablar'}</span>
          </button>
        </div>
        <MicStatus />
        <OutputStatus radio={radio} />

        <section className="space-y-1 rounded-2xl border border-[#E8E5DE] bg-white p-3" data-testid="radio-settings">
          <p className="text-base font-semibold text-[#101D36]">Ajustes</p>
          <label className="flex min-h-12 items-center gap-3"><span className="w-20 shrink-0 text-[15px] font-semibold text-[#101D36]">Volumen</span><input type="range" min="0" max="2" step="0.05" value={radio.prefs.volume} onChange={(event) => radio.setPrefs({ volume: Number(event.target.value), muted: false })} className="h-10 min-w-0 flex-1 accent-[#132443]" data-testid="radio-volume" /><span className="w-12 shrink-0 text-right text-sm tabular-nums text-slate-600">{Math.round(radio.prefs.volume * 100)}%</span></label>
          <Toggle label="Mantener pantalla encendida" hint="Mientras el radio esté activo (usa más batería)." checked={radio.prefs.wakeLock} onChange={(value) => radio.setPrefs({ wakeLock: value })} testId="radio-wakelock" />
          <Toggle label="Vibrar cuando alguien habla" checked={radio.prefs.vibrate} onChange={(value) => radio.setPrefs({ vibrate: value })} testId="radio-vibrate" />
          <Toggle label="Sonido corto de aviso" checked={radio.prefs.sound} onChange={(value) => radio.setPrefs({ sound: value })} testId="radio-sound" />
          <button type="button" onClick={() => radio.setPrefs({ enabled: false })} className="min-h-11 text-[15px] font-semibold text-[#8f382f] underline" data-testid="radio-leave">Apagar radio en este dispositivo</button>
        </section>

        <section className="space-y-2 rounded-2xl border border-[#E8E5DE] bg-white p-3" data-testid="radio-voice">
          <p className="text-base font-semibold text-[#101D36]">Mensaje de voz</p>
          <p className="text-sm text-slate-600">Queda en el canal {state.retention_days} días para quien no estaba conectado (máx. {VOICE_MAX_SECONDS} s).</p>
          {!recording && <button type="button" onClick={startRecording} disabled={radio.talk !== 'idle'} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border-2 border-[#132443] bg-white text-base font-semibold text-[#132443] disabled:opacity-50" data-testid="radio-record"><Mic className="h-5 w-5" />Grabar mensaje de voz</button>}
          {recording?.started && <button type="button" onClick={stopRecording} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#b91c1c] text-base font-semibold text-white" data-testid="radio-record-stop"><Square className="h-5 w-5" />Detener ({recSeconds} s)</button>}
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

/** Salida (bocina): nivel de lo que suena, «Probar bocina» y el aviso de volumen. */
function OutputStatus({ radio }) {
  const [testing, setTesting] = useState(false);
  const receiving = Boolean(radio.speaker) && radio.talk !== 'talking';
  const level = useLiveLevel(radio.outputLevel, radio.audioReady && (receiving || testing));
  const test = async () => { setTesting(true); await radio.testSpeaker(); setTimeout(() => setTesting(false), 1200); };
  return (
    <div className="space-y-2 rounded-xl border border-[#E8E5DE] bg-white p-3" data-testid="radio-output-status">
      <p className="flex items-center gap-2 text-[15px] font-semibold text-[#101D36]"><Speaker className="h-5 w-5 shrink-0" />{!radio.audioReady ? 'Bocina sin activar' : radio.prefs.muted ? 'Radio silenciado' : receiving ? `Sonando: ${radio.speaker}` : 'Bocina lista'}</p>
      <LevelBar level={level} color="bg-[#1d4ed8]" testId="radio-output-level" />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={test} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-[#D9D4C7] bg-white px-3 text-[15px] font-semibold text-[#101D36]" data-testid="radio-test-speaker"><Speaker className="h-4 w-4" />Probar bocina</button>
        <span className="text-xs text-slate-500">Sube el volumen de medios del teléfono si suena bajo.{radio.ios ? ' En iPhone (iOS 16.4 o más reciente) suena aunque el interruptor de silencio esté activado.' : ''}</span>
      </div>
    </div>
  );
}
