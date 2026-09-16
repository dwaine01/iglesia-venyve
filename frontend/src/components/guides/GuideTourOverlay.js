import React, { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { Button } from '../ui/button';

export const GuideTourOverlay = ({ open, steps, title, onClose }) => {
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const step = steps[index];

  useEffect(() => { if (open) setIndex(0); }, [open]);
  useEffect(() => {
    if (!open || !step) return undefined;
    const update = () => {
      const target = document.querySelector(`[data-testid="${step.target}"]`);
      if (!target) { setRect(null); return; }
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      window.setTimeout(() => {
        const box = target.getBoundingClientRect();
        setRect({ top: box.top - 6, left: box.left - 6, width: box.width + 12, height: box.height + 12 });
      }, 220);
    };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => { window.removeEventListener('resize', update); window.removeEventListener('scroll', update, true); };
  }, [index, open, step]);
  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = (event) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [onClose, open]);

  if (!open || !step) return null;
  const last = index === steps.length - 1;
  return createPortal(<div className="fixed inset-0 pointer-events-none" style={{ zIndex: 90 }} data-testid="guide-tour-overlay">
    {rect ? <div className="fixed rounded-md border-2 border-[#F3D870] transition-[top,left,width,height] duration-300" style={{ ...rect, boxShadow: '0 0 0 9999px rgba(7, 15, 28, .72)' }} data-testid="guide-tour-highlight" /> : <div className="fixed inset-0 bg-[#07101C]/75" />}
    <section className="pointer-events-auto fixed inset-x-3 bottom-3 max-h-[48vh] overflow-y-auto border border-[#D4AF37]/50 bg-white p-5 shadow-2xl sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-[420px]" data-testid="guide-tour-card">
      <div className="flex items-start justify-between gap-4"><div><p className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#996515]">{title} · Paso {index + 1} de {steps.length}</p><h2 className="mt-1 font-['Spectral'] text-2xl font-semibold text-[#0B192C]" data-testid="guide-tour-step-title">{step.title}</h2></div><Button size="icon" variant="ghost" onClick={onClose} aria-label="Salir del recorrido" data-testid="guide-tour-close"><X className="h-4 w-4" /></Button></div>
      <p className="mt-3 text-sm leading-6 text-slate-700" data-testid="guide-tour-step-body">{step.body}</p>
      {!rect && <p className="mt-2 text-xs text-amber-800" data-testid="guide-tour-target-unavailable">Este control aparece cuando existen datos o permisos para este paso.</p>}
      <div className="mt-5 flex items-center justify-between gap-3"><Button variant="outline" onClick={() => setIndex((value) => Math.max(0, value - 1))} disabled={index === 0} data-testid="guide-tour-previous"><ArrowLeft className="mr-2 h-4 w-4" />Anterior</Button><Button onClick={() => last ? onClose() : setIndex((value) => value + 1)} className="bg-[#0B192C] text-white hover:bg-[#1E3E62]" data-testid="guide-tour-next">{last ? <><Check className="mr-2 h-4 w-4" />Terminar</> : <>Siguiente<ArrowRight className="ml-2 h-4 w-4" /></>}</Button></div>
    </section>
  </div>, document.body);
};