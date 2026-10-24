import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { CalendarClock, Crosshair, Loader2, MapPin, Navigation, Plus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { accuracyLabel, directionsUrl, getCurrentLocation } from '../../lib/geolocation';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { DOOR_STATUS } from './DoorStats';
import { DoorForm } from './DoorForm';

const FILTERS = [['all', 'Todos'], ['pending_revisit', 'Sin respuesta'], ['followup_scheduled', 'Programados']];
const fmtDay = (iso) => (iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString('es', { weekday: 'short', day: 'numeric', month: 'short' }) : '');
const addressOf = (item) => [item.address_line1, item.address_line2].filter(Boolean).join(' · ') || 'Vivienda sin dirección';

/** Nueva visita a una vivienda: mismo formulario de puerta (se agrega a su historial). */
export function RevisitSheet({ household, books, onClose, onSaved }) {
  return (
    <Dialog open={Boolean(household)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="bg-white p-3 sm:max-w-xl sm:p-4" data-testid="door-revisit-sheet">
        <DialogHeader><DialogTitle>Registrar nueva visita</DialogTitle><DialogDescription>Se agrega al historial de esta vivienda.</DialogDescription></DialogHeader>
        {household && <DoorForm household={household} books={books} onSaved={(data) => { onSaved?.(data); onClose(); }} />}
      </DialogContent>
    </Dialog>
  );
}

function ScheduleDialog({ household, onClose, onSaved }) {
  const { API, getAuthHeaders } = useAuth();
  const [day, setDay] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { setDay(household?.followup_date || ''); setNote(household?.next_visit_note || ''); }, [household]);
  const save = async (value) => {
    setBusy(true);
    try {
      await axios.put(`${API}/api/mentorship/outreach/households/${household.household_id}/next-visit`, { next_visit_date: value || null, note: note.trim() || null }, getAuthHeaders());
      toast.success(value ? `Próxima visita: ${fmtDay(value)}` : 'Se quitó la fecha programada', { id: 'door-saved', duration: 2500 }); onSaved(); onClose();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo programar')); } finally { setBusy(false); }
  };
  return (
    <Dialog open={Boolean(household)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="door-schedule-dialog">
        <DialogHeader><DialogTitle>{household?.followup_date ? 'Reprogramar visita' : 'Programar visita'}</DialogTitle><DialogDescription>{household && addressOf(household)}</DialogDescription></DialogHeader>
        <input type="date" value={day} onChange={(event) => setDay(event.target.value)} className="h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="door-schedule-date" />
        <input value={note} onChange={(event) => setNote(event.target.value)} maxLength={300} placeholder="Nota (opcional): ej. volver en la tarde" className="h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" />
        <button type="button" onClick={() => save(day)} disabled={!day || busy} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-50" data-testid="door-schedule-save">{busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <CalendarClock className="h-5 w-5" />}Guardar fecha</button>
        {household?.followup_date && <button type="button" onClick={() => save(null)} disabled={busy} className="min-h-11 text-[15px] font-semibold text-[#8f382f] underline">Quitar fecha programada</button>}
      </DialogContent>
    </Dialog>
  );
}

/** Pendientes de nueva visita y seguimientos programados (los atrasados primero). */
export function PendingDoors({ campaignId, books, refreshKey, onChanged }) {
  const { API, getAuthHeaders } = useAuth();
  const [filter, setFilter] = useState('all');
  const [data, setData] = useState(null);
  const [revisit, setRevisit] = useState(null);
  const [schedule, setSchedule] = useState(null);
  const [busy, setBusy] = useState('');
  const load = useCallback(() => {
    axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/pending-doors`, { ...getAuthHeaders(), params: { status: filter, limit: 100 } })
      .then((response) => setData(response.data)).catch(() => setData({ items: [], total: 0 }));
  }, [API, getAuthHeaders, campaignId, filter]);
  useEffect(() => { load(); }, [load, refreshKey]);
  const changed = () => { load(); onChanged?.(); };
  const placeHere = async (item) => {
    setBusy(item.household_id);
    try {
      const position = await getCurrentLocation();
      await axios.put(`${API}/api/mentorship/outreach/households/${item.household_id}/location`, { latitude: position.latitude, longitude: position.longitude, accuracy_m: position.accuracy_m, source: 'gps' }, getAuthHeaders());
      toast.success(`Ubicación guardada (${accuracyLabel(position.accuracy_m)})`, { id: 'door-saved', duration: 2500 }); changed();
    } catch (error) { toast.error(error.response ? apiErrorMessage(error, 'No se pudo guardar la ubicación') : error.message); } finally { setBusy(''); }
  };
  return (
    <section className="space-y-3" data-testid="door-pending">
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        {FILTERS.map(([key, label]) => <button key={key} type="button" onClick={() => setFilter(key)} className={`min-h-11 shrink-0 rounded-full border px-4 text-[15px] font-semibold ${filter === key ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-[#101D36]'}`} data-testid={`door-pending-filter-${key}`}>{label}</button>)}
      </div>
      {!data ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : data.items.length === 0
        ? <p className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-base text-slate-500">No hay viviendas pendientes en esta vista.</p>
        : <>
          <p className="text-sm text-slate-600">{data.total} vivienda(s){data.scope === 'all' ? ' de toda la invasión' : ''}</p>
          <ul className="space-y-2">
            {data.items.map((item) => {
              const status = DOOR_STATUS[item.door_status];
              return (
                <li key={item.household_id} className={`rounded-xl border bg-white p-3 ${item.overdue ? 'border-amber-300' : 'border-[#E8E5DE]'}`} data-testid={`door-pending-${item.household_id}`}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="min-w-0 text-base font-semibold text-[#101D36]">{addressOf(item)}</p>
                    {status && <span className={`shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${status.className}`}>{status.label}</span>}
                  </div>
                  <p className="mt-1 text-sm text-slate-600">Último resultado: {item.last_result === 'opened' ? 'abrieron' : item.last_result === 'no_answer' ? 'no abrieron' : 'sin visitas'}{item.last_attempt_at ? ` · ${fmtDay(item.last_attempt_at)}` : ''} · {item.attempts_count || 0} intento(s)</p>
                  {item.followup_date && <p className={`text-sm font-semibold ${item.overdue ? 'text-amber-800' : 'text-[#1d4ed8]'}`}>{item.overdue ? 'Atrasada · ' : 'Próxima visita · '}{fmtDay(item.followup_date)}{item.next_visit_note ? ` · ${item.next_visit_note}` : ''}</p>}
                  {data.scope === 'all' && <p className="text-xs text-slate-500">{[item.mentor_name || 'Sin mentor', item.team_name].filter(Boolean).join(' · ')}</p>}
                  {item.location_approx && <p className="flex items-center gap-1 text-xs text-slate-500"><MapPin className="h-3.5 w-3.5" />Ubicación aproximada (de la calle)</p>}
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {item.mine && <button type="button" onClick={() => setRevisit(item)} className="col-span-2 inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#132443] px-3 text-[15px] font-semibold text-white" data-testid={`door-pending-revisit-${item.household_id}`}><Plus className="h-5 w-5" />Registrar nueva visita</button>}
                    <a href={directionsUrl(item.latitude, item.longitude, addressOf(item))} target="_blank" rel="noreferrer" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-[#D9D4C7] px-3 text-[15px] font-semibold text-[#101D36]" data-testid={`door-pending-directions-${item.household_id}`}><Navigation className="h-5 w-5" />Cómo llegar</a>
                    <button type="button" onClick={() => setSchedule(item)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-[#D9D4C7] px-3 text-[15px] font-semibold text-[#101D36]" data-testid={`door-pending-schedule-${item.household_id}`}><CalendarClock className="h-5 w-5" />{item.followup_date ? 'Reprogramar' : 'Programar'}</button>
                    <button type="button" onClick={() => placeHere(item)} disabled={busy === item.household_id} className="col-span-2 inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-dashed border-[#D9D4C7] px-3 text-sm font-semibold text-[#101D36]" data-testid={`door-pending-place-${item.household_id}`}>{busy === item.household_id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Crosshair className="h-4 w-4" />}{item.latitude == null ? 'Ubicar con mi ubicación' : 'Corregir ubicación con mi ubicación'}</button>
                  </div>
                </li>
              );
            })}
          </ul>
        </>}
      <RevisitSheet household={revisit} books={books} onClose={() => setRevisit(null)} onSaved={changed} />
      <ScheduleDialog household={schedule} onClose={() => setSchedule(null)} onSaved={changed} />
    </section>
  );
}
