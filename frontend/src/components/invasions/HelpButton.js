import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Loader2, Phone, Siren } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { useInvasionToday } from '../../context/InvasionTodayContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { getCurrentLocation } from '../../lib/geolocation';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';

const REASONS = [['support', 'Necesito apoyo'], ['risk', 'Situación de riesgo'], ['prayer', 'Persona necesita oración'], ['urgent_info', 'Información urgente']];
const HOLD_MS = 1000;
const newId = () => (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);
// La ubicación no debe demorar el aviso: si tarda más de 4 s, se envía sin ella.
const quickLocation = () => Promise.race([getCurrentLocation().catch(() => null), new Promise((resolve) => setTimeout(() => resolve(null), 4000))]);

// Mantener presionado 1 s para enviar (evita falsas alarmas).
function HoldToSend({ disabled, onComplete, busy }) {
  const [progress, setProgress] = useState(0);
  const frame = useRef(null);
  const started = useRef(0);
  const stop = () => { cancelAnimationFrame(frame.current); frame.current = null; setProgress(0); };
  const tick = () => {
    const value = Math.min(1, (Date.now() - started.current) / HOLD_MS);
    setProgress(value);
    if (value >= 1) { frame.current = null; setProgress(0); onComplete(); return; }
    frame.current = requestAnimationFrame(tick);
  };
  const start = (event) => { if (disabled || busy) return; event.preventDefault(); started.current = Date.now(); frame.current = requestAnimationFrame(tick); };
  useEffect(() => () => cancelAnimationFrame(frame.current), []);
  return (
    <button type="button" disabled={disabled || busy} onPointerDown={start} onPointerUp={stop} onPointerLeave={stop} onPointerCancel={stop} onContextMenu={(event) => event.preventDefault()}
      onKeyDown={(event) => { if ((event.key === 'Enter' || event.key === ' ') && !frame.current) start(event); }} onKeyUp={stop}
      className="relative min-h-16 w-full touch-none select-none overflow-hidden rounded-2xl bg-[#b91c1c] px-4 text-lg font-bold text-white shadow-lg disabled:opacity-50" data-testid="help-hold">
      <span className="absolute inset-y-0 left-0 bg-[#7f1d1d]" style={{ width: `${progress * 100}%` }} aria-hidden />
      <span className="relative inline-flex items-center gap-2">{busy ? <Loader2 className="h-6 w-6 animate-spin" /> : <Siren className="h-6 w-6" />}{busy ? 'Enviando…' : progress > 0 ? 'Sigue presionando…' : 'Mantén presionado para enviar'}</span>
    </button>
  );
}

/** Botón rojo «Ayuda» (participantes de una invasión activa hoy). No sustituye al 911. */
export function HelpButton() {
  const { API, getAuthHeaders } = useAuth();
  const { data, current } = useInvasionToday();
  const active = data?.active || [];
  const [open, setOpen] = useState(false);
  const [campaignId, setCampaignId] = useState('');
  const [reason, setReason] = useState(null);
  const [note, setNote] = useState('');
  const [shareLocation, setShareLocation] = useState(true);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(null);
  const requestId = useRef(newId());
  if (!active.length) return null;

  const openSheet = () => { setCampaignId((current || active[0]).campaign_id); setReason(null); setNote(''); setSent(null); requestId.current = newId(); setOpen(true); };
  const send = async () => {
    if (!reason) { toast.error('Elige qué está pasando'); return; }
    setBusy(true);
    try {
      const location = shareLocation ? await quickLocation() : null;
      const response = await axios.post(`${API}/api/invasions/${campaignId}/help`, {
        client_request_id: requestId.current, reason, note: note.trim() || null,
        latitude: location?.latitude ?? null, longitude: location?.longitude ?? null, accuracy_m: location?.accuracy_m ?? null,
      }, getAuthHeaders());
      setSent(response.data); requestId.current = newId();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo enviar el aviso. Si es urgente, llama por teléfono.')); } finally { setBusy(false); }
  };
  return (
    <>
      <button type="button" onClick={openSheet} className="inline-flex h-11 shrink-0 items-center gap-1.5 rounded-full bg-[#b91c1c] px-3 text-[15px] font-bold text-white shadow" data-testid="help-button" aria-label="Necesito ayuda"><Siren className="h-5 w-5" /><span>Ayuda</span></button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-white sm:max-w-md" data-testid="help-sheet">
          <DialogHeader><DialogTitle className="text-[#b91c1c]">Necesito ayuda</DialogTitle><DialogDescription>Avisa al organizador, al encargado general, a los coordinadores y al pastor.</DialogDescription></DialogHeader>
          <a href="tel:911" className="flex min-h-12 items-center gap-2 rounded-xl border-2 border-[#b91c1c] bg-[#fef2f2] px-3 text-[15px] font-semibold text-[#7f1d1d]" data-testid="help-911"><Phone className="h-5 w-5 shrink-0" />Emergencia médica o de seguridad: llama al 911. Este botón no sustituye al 911.</a>
          {sent
            ? <div className="space-y-3 text-center" data-testid="help-sent">
                <CheckCircle2 className="mx-auto h-12 w-12 text-[#2f6e47]" />
                <p className="text-lg font-semibold text-[#101D36]">{sent.duplicate ? 'Tu aviso ya estaba enviado' : 'Aviso enviado'}</p>
                <p className="text-[15px] text-slate-700">{sent.reason_label} · {new Date(sent.created_at).toLocaleTimeString('es', { hour: 'numeric', minute: '2-digit' })}{sent.notified ? ` · recibido por ${sent.notified} responsable(s)` : ''}{sent.latitude != null ? ' · con tu ubicación' : ''}</p>
                <p className="text-sm text-slate-500">Te avisaremos cuando alguien lo atienda.</p>
                <button type="button" onClick={() => setOpen(false)} className="min-h-12 w-full rounded-xl border border-[#D9D4C7] text-base font-semibold text-[#101D36]">Cerrar</button>
              </div>
            : <>
              {active.length > 1 && <select value={campaignId} onChange={(event) => setCampaignId(event.target.value)} className="h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" data-testid="help-campaign">{active.map((item) => <option key={item.campaign_id} value={item.campaign_id}>{item.name}</option>)}</select>}
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {REASONS.map(([key, label]) => <button key={key} type="button" onClick={() => setReason(key)} aria-pressed={reason === key} className={`min-h-12 rounded-xl border-2 px-3 text-[15px] font-semibold ${reason === key ? 'border-[#b91c1c] bg-[#b91c1c] text-white' : 'border-[#D9D4C7] bg-white text-[#101D36]'}`} data-testid={`help-reason-${key}`}>{label}</button>)}
              </div>
              <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} maxLength={500} placeholder="Nota (opcional)" className="w-full rounded-lg border border-[#D9D4C7] p-3 text-base" data-testid="help-note" />
              <label className="flex min-h-11 items-center gap-2 text-[15px] text-[#101D36]"><input type="checkbox" checked={shareLocation} onChange={(event) => setShareLocation(event.target.checked)} className="h-5 w-5" data-testid="help-location" />Enviar mi ubicación actual</label>
              <div className="sticky-actions"><HoldToSend disabled={!reason} busy={busy} onComplete={send} />{!reason && <p className="mt-1 text-center text-sm text-slate-500">Primero elige qué está pasando.</p>}</div>
            </>}
        </DialogContent>
      </Dialog>
    </>
  );
}
