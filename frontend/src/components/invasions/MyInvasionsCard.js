import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { CalendarDays, Check, Clock, Loader2, MapPin, X } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';

const STATUS_STYLE = {
  invited: 'bg-amber-50 text-amber-800 border-amber-200',
  confirmed: 'bg-[#eef5f0] text-[#2f6e47] border-[#bcd8c4]',
  declined: 'bg-[#f8ecea] text-[#8f382f] border-[#e3c2bd]',
  attended: 'bg-[#e8eefb] text-[#1d4ed8] border-[#c3d3f5]',
};
const formatDate = (iso, options = { weekday: 'short', day: 'numeric', month: 'short' }) => (iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('es', options) : '');
const hours = (minutes) => `${Math.floor(minutes / 60)} h${minutes % 60 ? ` ${minutes % 60} min` : ''}`;

// FASE 6B: el invitado (mentor, colaborador o encargado) ve sus invasiones en
// su portal y responde "Voy a participar" / "No podré participar".
export function MyInvasionsCard({ onChanged }) {
  const { API, getAuthHeaders } = useAuth();
  const [searchParams] = useSearchParams();
  const highlighted = searchParams.get('invasion');
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState('');
  const [declining, setDeclining] = useState(null);
  const [note, setNote] = useState('');

  const load = useCallback(() => {
    axios.get(`${API}/api/invasions/mine/invitations`, getAuthHeaders()).then((response) => setItems(response.data.items || [])).catch(() => setItems([]));
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!highlighted || !items?.length) return;
    document.getElementById(`invasion-invite-${highlighted}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [highlighted, items]);

  const respond = async (item, response) => {
    setBusy(`${item.campaign_id}-${response}`);
    try {
      await axios.post(`${API}/api/invasions/${item.campaign_id}/respond`, { response, note: response === 'declined' ? note.trim() || null : null }, getAuthHeaders());
      toast.success(response === 'confirmed' ? '¡Gracias! Quedaste confirmado' : 'Se avisó que no podrás participar');
      setDeclining(null); setNote(''); load(); onChanged?.();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar tu respuesta')); } finally { setBusy(''); }
  };

  if (!items?.length) return null;
  return (
    <section className="space-y-3" data-testid="my-invasions">
      <h2 className="font-['Spectral'] text-xl font-semibold text-[#101D36]">Mis invasiones</h2>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {items.map((item) => {
          const statusKey = item.attended ? 'attended' : item.status;
          return (
            <article key={item.campaign_id} id={`invasion-invite-${item.campaign_id}`} className={`min-w-0 rounded-2xl border bg-white p-4 shadow-sm ${highlighted === item.campaign_id ? 'border-[#101D36] ring-2 ring-[#101D36]/15' : 'border-[#E8E5DE]'}`} data-testid={`my-invasion-${item.campaign_id}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="text-lg font-semibold text-[#101D36]">{item.name}</h3>
                  <p className="text-sm text-slate-500">{item.role_labels.join(' · ')}</p>
                </div>
                <span className={`shrink-0 rounded-full border px-3 py-1 text-xs font-semibold ${STATUS_STYLE[statusKey] || STATUS_STYLE.invited}`} data-testid={`my-invasion-status-${item.campaign_id}`}>{item.status_label}</span>
              </div>
              {item.purpose && <p className="mt-2 text-sm text-slate-700">{item.purpose}</p>}
              <ul className="mt-3 space-y-1.5 text-sm text-slate-700">
                <li className="flex gap-2"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />{item.location}{item.site_meeting_point?.reference ? ` · ${item.site_meeting_point.reference}` : ''}</li>
                <li className="flex gap-2"><CalendarDays className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />{formatDate(item.start_date)}{item.end_date && item.end_date !== item.start_date ? ` → ${formatDate(item.end_date)}` : ''}</li>
                {item.schedule_days.length > 0 && <li className="flex gap-2"><Clock className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" /><span>{item.schedule_days.map((day) => `${formatDate(day.day)} ${day.start_time} (${hours(day.duration_minutes)})`).join(' · ')}</span></li>}
                {item.departure_point && <li className="pl-6 text-slate-500">Salida: {item.departure_point}</li>}
                {item.prayer_start_date && <li className="pl-6 text-slate-500">Preparación en oración desde el {formatDate(item.prayer_start_date, { day: 'numeric', month: 'long' })}</li>}
              </ul>
              {item.can_respond && !item.attended && (
                declining === item.campaign_id
                  ? <div className="mt-3 space-y-2" data-testid={`my-invasion-decline-${item.campaign_id}`}>
                      <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} maxLength={500} placeholder="Motivo (opcional)" className="w-full rounded-lg border border-[#D9D4C7] p-3 text-base" />
                      <div className="grid grid-cols-2 gap-2">
                        <button type="button" onClick={() => { setDeclining(null); setNote(''); }} className="min-h-12 rounded-lg border border-[#D9D4C7] bg-white text-base font-semibold text-[#101D36]">Volver</button>
                        <button type="button" onClick={() => respond(item, 'declined')} disabled={Boolean(busy)} className="min-h-12 rounded-lg bg-[#8f382f] text-base font-semibold text-white" data-testid={`my-invasion-decline-confirm-${item.campaign_id}`}>{busy === `${item.campaign_id}-declined` ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : 'Confirmar'}</button>
                      </div>
                    </div>
                  : <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <button type="button" onClick={() => respond(item, 'confirmed')} disabled={Boolean(busy) || item.status === 'confirmed'} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#2f6e47] px-4 text-base font-semibold text-white disabled:opacity-60" data-testid={`my-invasion-yes-${item.campaign_id}`}>{busy === `${item.campaign_id}-confirmed` ? <Loader2 className="h-5 w-5 animate-spin" /> : <Check className="h-5 w-5" />}{item.status === 'confirmed' ? 'Ya confirmaste' : 'Voy a participar'}</button>
                      <button type="button" onClick={() => setDeclining(item.campaign_id)} disabled={Boolean(busy) || item.status === 'declined'} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-[#e3c2bd] bg-white px-4 text-base font-semibold text-[#8f382f] disabled:opacity-60" data-testid={`my-invasion-no-${item.campaign_id}`}><X className="h-5 w-5" />{item.status === 'declined' ? 'Respondiste que no' : 'No podré participar'}</button>
                    </div>
              )}
              {item.finished && <p className="mt-3 text-xs text-slate-500">Esta invasión ya terminó.</p>}
            </article>
          );
        })}
      </div>
    </section>
  );
}
