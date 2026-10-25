import React, { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Copy, GripHorizontal, Mic, MicOff, RotateCcw, Volume2, VolumeX } from 'lucide-react';
import { toast } from 'sonner';

import { MIC_MESSAGES, useRadio } from '../../context/RadioContext';

const POSITION_KEY = 'venyve.radio.ptt.bottom';
const MIC_PROBLEM = new Set(['denied', 'blocked', 'notfound', 'busy', 'insecure', 'unsupported', 'noframes', 'lost', 'inapp']);

/** Nivel en vivo (0–1) leído con requestAnimationFrame mientras `active`. */
export function useLiveLevel(read, active) {
  const [level, setLevel] = useState(0);
  useEffect(() => {
    if (!active) { setLevel(0); return undefined; }
    let frame;
    let last = 0;
    const tick = (time) => {
      if (time - last > 60) { last = time; setLevel(Math.min(1, (read() || 0) * 4)); }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [read, active]);
  return level;
}

export function LevelBar({ level, color = 'bg-emerald-500', testId }) {
  return <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(level * 100)} data-testid={testId} data-level={Math.round(level * 100)}><div className={`h-full rounded-full transition-[width] duration-75 ${color}`} style={{ width: `${Math.round(level * 100)}%` }} /></div>;
}

/** Estado del micrófono, claro y accionable (con «Reintentar»). */
export function MicStatus({ compact = false }) {
  const radio = useRadio();
  const state = radio.micState;
  const talking = radio.talk === 'talking';
  const level = useLiveLevel(radio.micLevel, state === 'ready');
  const copy = async () => { try { await navigator.clipboard.writeText(window.location.href); toast.success('Enlace copiado: pégalo en Chrome o Safari'); } catch (error) { toast.message(window.location.href); } };
  const tone = talking ? 'border-red-300 bg-red-50 text-red-800' : state === 'ready' ? 'border-[#bcd8c4] bg-[#eef5f0] text-[#2f6e47]' : MIC_PROBLEM.has(state) ? 'border-red-200 bg-red-50 text-red-800' : 'border-amber-200 bg-amber-50 text-amber-900';
  return (
    <div className={`space-y-2 rounded-xl border p-3 ${tone}`} data-testid="radio-mic-status" data-state={state}>
      <p className="flex items-center gap-2 text-[15px] font-semibold">{state === 'ready' || talking ? <Mic className="h-5 w-5 shrink-0" /> : <MicOff className="h-5 w-5 shrink-0" />}
        {talking ? 'Transmitiendo…' : state === 'ready' ? 'Micrófono listo' : state === 'requesting' ? 'Pidiendo permiso…' : MIC_PROBLEM.has(state) ? 'Micrófono con problema' : 'Micrófono sin activar'}</p>
      {(state === 'ready' || talking) && <LevelBar level={level} color={talking ? 'bg-red-500' : 'bg-emerald-500'} testId="radio-mic-level" />}
      {!compact && state === 'ready' && !talking && <p className="text-xs">Prueba del micrófono: habla y mira la barra (no se transmite hasta que mantengas presionado).</p>}
      {!compact && state !== 'ready' && <p className="text-sm" data-testid="radio-mic-message">{MIC_MESSAGES[state] || MIC_MESSAGES.unknown}</p>}
      {state !== 'ready' && state !== 'requesting' && state !== 'inapp' && state !== 'notfound' && state !== 'insecure' && (
        <button type="button" onClick={() => (radio.audioReady ? radio.prepareMic() : radio.activate({ withMic: true }))} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-current bg-white px-3 text-[15px] font-semibold" data-testid="radio-mic-retry">
          {state === 'unknown' ? <><Mic className="h-4 w-4" />Probar y activar micrófono</> : <><RotateCcw className="h-4 w-4" />Reintentar</>}
        </button>)}
      {state === 'inapp' && <button type="button" onClick={copy} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-current bg-white px-3 text-[15px] font-semibold" data-testid="radio-open-browser"><Copy className="h-4 w-4" />Copiar enlace para abrir en Chrome/Safari</button>}
    </div>
  );
}

/** Franja bajo la barra superior, en CUALQUIER pantalla: quién habla y el
 * aviso «Toca para activar el radio» cuando el navegador bloquea el audio.
 * Ocupa su propio espacio (no tapa contenido). */
export function RadioBanner() {
  const radio = useRadio();
  const location = useLocation();
  if (!radio?.channel || !radio.prefs.enabled || radio.status === 'error' || radio.status === 'off') return null;
  const onRadioPage = location.pathname.endsWith('/radio');
  if (radio.needsUnlock && !onRadioPage) {
    return (
      <button type="button" onClick={() => radio.activate({ withMic: true })} className="flex min-h-11 w-full shrink-0 items-center justify-center gap-2 border-b border-amber-200 bg-amber-50 px-3 text-[15px] font-semibold text-amber-900" data-testid="radio-unlock" data-print-hide>
        <Volume2 className="h-5 w-5 shrink-0" /><span className="truncate">{radio.speaker ? `${radio.speaker} está hablando · ` : ''}Toca para activar el radio</span>
      </button>
    );
  }
  if (radio.speaker && radio.talk !== 'talking') {
    return (
      <div className="flex min-h-11 w-full shrink-0 items-center justify-between gap-2 border-b border-[#c3d3f5] bg-[#e8eefb] px-3 text-[15px] font-semibold text-[#1d4ed8]" role="status" aria-live="polite" data-testid="radio-speaking-banner" data-print-hide>
        <span className="flex min-w-0 items-center gap-2"><Volume2 className="h-5 w-5 shrink-0 animate-pulse" /><span className="truncate">{radio.speaker} está hablando{radio.prefs.muted ? ' (silenciado)' : ''}</span></span>
        <button type="button" onClick={() => radio.setPrefs({ muted: !radio.prefs.muted })} className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white/70" aria-label={radio.prefs.muted ? 'Activar sonido del radio' : 'Silenciar radio'} data-testid="radio-banner-mute">{radio.prefs.muted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}</button>
      </div>
    );
  }
  if (radio.talk === 'talking') {
    return <div className="flex min-h-11 w-full shrink-0 items-center justify-center gap-2 border-b border-red-200 bg-[#fef2f2] px-3 text-[15px] font-semibold text-[#7f1d1d]" role="status" data-testid="radio-talking-banner" data-print-hide><Mic className="h-5 w-5" />Estás hablando · {Math.max(0, 60 - radio.seconds)} s</div>;
  }
  return null;
}

function useKeyboardOpen() {
  const [open, setOpen] = useState(() => document.documentElement.dataset.keyboard === 'open');
  useEffect(() => {
    const observer = new MutationObserver(() => setOpen(document.documentElement.dataset.keyboard === 'open'));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-keyboard'] });
    return () => observer.disconnect();
  }, []);
  return open;
}

/** Micrófono flotante (mantener para hablar) en cualquier pantalla mientras
 * hay canal. Se oculta con el teclado abierto y en la pantalla de Radio (que
 * tiene su botón grande). Se puede subir/bajar con la manija (se recuerda). */
export function RadioPTT() {
  const radio = useRadio();
  const location = useLocation();
  const keyboard = useKeyboardOpen();
  const [bottom, setBottom] = useState(() => { try { return Number(localStorage.getItem(POSITION_KEY)) || 0; } catch (error) { return 0; } });
  const drag = useRef(null);
  const visible = Boolean(radio?.channel && radio.prefs.enabled && radio.status !== 'error' && radio.status !== 'off' && !location.pathname.endsWith('/radio'));
  // Espacio extra al final de la página para que ningún botón quede atrapado bajo el micrófono.
  useEffect(() => {
    if (visible) document.documentElement.dataset.radioPtt = 'on'; else delete document.documentElement.dataset.radioPtt;
    return () => { delete document.documentElement.dataset.radioPtt; };
  }, [visible]);
  if (!radio?.channel || !radio.prefs.enabled || radio.status === 'error' || radio.status === 'off' || keyboard || location.pathname.endsWith('/radio')) return null;
  const talking = radio.talk === 'talking';
  const othersSpeaking = radio.speaker && !talking;
  const disabled = radio.status !== 'online';
  const micProblem = radio.micState !== 'ready';
  const onDragStart = (event) => { event.preventDefault(); event.currentTarget.setPointerCapture?.(event.pointerId); drag.current = { y: event.clientY, start: bottom }; };
  const onDragMove = (event) => {
    if (!drag.current) return;
    const next = Math.max(0, Math.min(window.innerHeight - 260, drag.current.start + (drag.current.y - event.clientY)));
    setBottom(next);
  };
  const onDragEnd = () => { if (!drag.current) return; drag.current = null; try { localStorage.setItem(POSITION_KEY, String(Math.round(bottom))); } catch (error) { /* nada */ } };
  const start = (event) => { event.preventDefault(); event.currentTarget.setPointerCapture?.(event.pointerId); radio.pressStart(); };
  // Por encima de la barra inferior y de la franja de «Guardar» de los formularios (móvil); abajo a la derecha en escritorio.
  const style = { bottom: `calc(${bottom}px + var(--radio-ptt-base))` };
  return (
    <div className="fixed right-3 z-40 flex flex-col items-center gap-1 [--radio-ptt-base:24px] max-lg:[--radio-ptt-base:calc(9.5rem+env(safe-area-inset-bottom))]" style={style} data-testid="radio-ptt-floating" data-print-hide>
      <button type="button" onPointerDown={onDragStart} onPointerMove={onDragMove} onPointerUp={onDragEnd} onPointerCancel={onDragEnd} className="flex h-6 w-11 touch-none items-center justify-center rounded-full bg-white/90 text-slate-500 shadow" aria-label="Mover el micrófono" data-testid="radio-ptt-handle"><GripHorizontal className="h-4 w-4" /></button>
      <button type="button" disabled={disabled} onPointerDown={start} onPointerUp={radio.pressEnd} onPointerCancel={radio.pressEnd} onLostPointerCapture={radio.pressEnd} onContextMenu={(event) => event.preventDefault()}
        className={`relative grid h-16 w-16 touch-none select-none place-items-center rounded-full border-4 text-white shadow-xl transition ${talking ? 'scale-110 border-red-200 bg-[#b91c1c]' : radio.talk === 'requesting' ? 'border-red-100 bg-[#7f1d1d]' : othersSpeaking ? 'border-[#c3d3f5] bg-[#1d4ed8]' : 'border-white bg-[#132443]'} disabled:bg-slate-400`}
        aria-label={micProblem && !talking ? 'Activar micrófono del radio' : talking ? 'Suelta para terminar' : othersSpeaking ? `${radio.speaker} está hablando` : 'Mantén presionado para hablar por radio'} data-testid="radio-ptt-floating-button">
        {talking && <PttLevelRing read={radio.micLevel} />}
        {micProblem && !talking ? <MicOff className="h-7 w-7" /> : othersSpeaking ? <Volume2 className="h-7 w-7 animate-pulse" /> : <Mic className="h-7 w-7" />}
        {(radio.status !== 'online' || micProblem) && <span className={`absolute -right-0.5 -top-0.5 h-4 w-4 rounded-full border-2 border-white ${MIC_PROBLEM.has(radio.micState) ? 'bg-red-500' : 'bg-amber-500'}`} data-testid="radio-ptt-floating-warning" aria-hidden />}
      </button>
    </div>
  );
}

// Anillo que crece con la voz mientras transmites.
function PttLevelRing({ read }) {
  const level = useLiveLevel(read, true);
  return <span className="pointer-events-none absolute inset-0 rounded-full border-4 border-red-300" style={{ transform: `scale(${1 + level * 0.45})`, opacity: 0.4 + level * 0.6 }} aria-hidden data-testid="radio-ptt-level" />;
}
