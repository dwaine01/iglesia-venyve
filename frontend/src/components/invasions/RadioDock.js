import React, { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { GripHorizontal, Mic, MicOff, Volume2, VolumeX } from 'lucide-react';

import { useRadio } from '../../context/RadioContext';

const POSITION_KEY = 'venyve.radio.ptt.bottom';

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
      <button type="button" onClick={radio.activate} className="flex min-h-11 w-full shrink-0 items-center justify-center gap-2 border-b border-amber-200 bg-amber-50 px-3 text-[15px] font-semibold text-amber-900" data-testid="radio-unlock" data-print-hide>
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
  const disabled = radio.status !== 'online' || radio.micState === 'denied';
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
        aria-label={talking ? 'Suelta para terminar' : othersSpeaking ? `${radio.speaker} está hablando` : 'Mantén presionado para hablar por radio'} data-testid="radio-ptt-floating-button">
        {radio.micState === 'denied' ? <MicOff className="h-7 w-7" /> : othersSpeaking ? <Volume2 className="h-7 w-7 animate-pulse" /> : <Mic className="h-7 w-7" />}
        {radio.status !== 'online' && <span className="absolute -right-0.5 -top-0.5 h-4 w-4 rounded-full border-2 border-white bg-amber-500" aria-hidden />}
      </button>
    </div>
  );
}
