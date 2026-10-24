import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Check, HandHeart, Loader2, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';

const todayIso = () => { const now = new Date(); return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
const addDays = (iso, days) => { const value = new Date(`${iso}T12:00:00`); value.setDate(value.getDate() + days); return value.toISOString().slice(0, 10); };
const shortDate = (iso) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('es', { weekday: 'short', day: 'numeric', month: 'short' }) : '');
const periodDays = (period) => { const list = []; if (!period) return list; let cursor = period.prayer_start; while (cursor <= period.prep_end && list.length < 60) { list.push(cursor); cursor = addDays(cursor, 1); } return list; };

function DayDots({ period, prayed }) {
  const days = periodDays(period); const today = todayIso(); const set = new Set(prayed);
  return (
    <ol className="flex flex-wrap gap-1.5" aria-label="Días de oración">
      {days.map((day) => <li key={day} title={shortDate(day)} className={`grid h-8 w-8 place-items-center rounded-full border text-[11px] font-semibold ${set.has(day) ? 'border-[#2f6e47] bg-[#2f6e47] text-white' : day > today ? 'border-dashed border-slate-300 text-slate-300' : 'border-slate-300 text-slate-500'}`}>{new Date(`${day}T12:00:00`).getDate()}</li>)}
    </ol>
  );
}

// Portal del participante: "Hoy oré en casa" + sus reuniones.
export function MyPrayerCard({ campaignId }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { axios.get(`${API}/api/invasions/${campaignId}/prayer`, getAuthHeaders()).then((response) => setData(response.data)).catch(() => setData(null)); }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { load(); }, [load]);
  if (!data || data.declined || !data.mine) return null;
  const today = todayIso();
  const prayedToday = data.mine.prayer_days.includes(today);
  const canMark = today >= data.period.prayer_start && today <= data.period.end;
  const toggle = async () => {
    setBusy(true);
    try { setData((await axios.post(`${API}/api/invasions/${campaignId}/prayer/home`, { prayed: !prayedToday }, getAuthHeaders())).data); toast.success(prayedToday ? 'Se quitó el registro de hoy' : '¡Gracias! Registraste tu oración de hoy'); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); } finally { setBusy(false); }
  };
  const upcoming = data.meetings.filter((meeting) => meeting.day >= today);
  return (
    <div className="mt-3 space-y-2 rounded-xl border border-[#E8E5DE] bg-[#FBFAF7] p-3" data-testid={`my-prayer-${campaignId}`}>
      <p className="flex items-center gap-2 text-sm font-semibold text-[#101D36]"><HandHeart className="h-4 w-4 text-[#7A5F22]" />Preparación en oración · {data.mine.prayer_count} de {data.period.total_days} días</p>
      <DayDots period={data.period} prayed={data.mine.prayer_days} />
      {data.period.status === 'upcoming' && <p className="text-xs text-slate-500">Empieza el {shortDate(data.period.prayer_start)}.</p>}
      {canMark && <button type="button" onClick={toggle} disabled={busy} className={`inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg px-4 text-base font-semibold ${prayedToday ? 'border border-[#bcd8c4] bg-white text-[#2f6e47]' : 'bg-[#7A5F22] text-white'}`} data-testid={`my-prayer-today-${campaignId}`}>{busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Check className="h-5 w-5" />}{prayedToday ? 'Hoy ya oraste (tocar para deshacer)' : 'Hoy oré en casa'}</button>}
      {data.meetings.length > 0 && <ul className="space-y-1 text-sm">{data.meetings.map((meeting) => <li key={meeting.meeting_id} className="flex flex-wrap justify-between gap-2"><span>Reunión de oración · {shortDate(meeting.day)}{meeting.time ? ` ${meeting.time}` : ''} · {meeting.place}</span>{meeting.i_attended ? <span className="text-xs font-semibold text-[#2f6e47]">Asististe</span> : meeting.day >= today ? <span className="text-xs text-slate-500">Próxima</span> : null}</li>)}</ul>}
      {!upcoming.length && !data.meetings.length && <p className="text-xs text-slate-500">Aún no hay reuniones de oración programadas.</p>}
    </div>
  );
}

// Panel del encargado / organizador / autoridad: avance, reuniones y seguimiento.
export function PrayerPanel({ campaignId }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ day: todayIso(), time: '19:00', place: 'La iglesia' });
  const [openMeeting, setOpenMeeting] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { axios.get(`${API}/api/invasions/${campaignId}/prayer`, getAuthHeaders()).then((response) => setData(response.data)).catch(() => setData(null)); }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { load(); }, [load]);
  const call = async (request, success) => {
    setBusy(true);
    try { setData((await request()).data); if (success) toast.success(success); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); } finally { setBusy(false); }
  };
  const today = todayIso();
  const people = useMemo(() => data?.items || [], [data]);
  if (!data?.can_edit) return null;
  const totals = data.totals;
  const pct = (value) => (value == null ? 'Sin datos' : `${value}%`);
  return (
    <section className="space-y-3 border-t border-[#EEECE6] pt-3" data-testid="prayer-panel">
      <h4 className="flex items-center gap-2 text-base font-semibold text-[#101D36]"><HandHeart className="h-5 w-5 text-[#7A5F22]" />Preparación en oración</h4>
      <p className="text-xs text-slate-500">Del {shortDate(data.period.prayer_start)} al {shortDate(data.period.prep_end)} · {data.period.expected_days} de {data.period.total_days} días transcurridos</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="prayer-totals">
        {[['Oraron al menos un día', pct(totals.prayed_any_pct), `${totals.prayed_any} de ${totals.participants}`], ['Promedio de días', totals.avg_days ?? 'Sin datos', 'por participante'], ['Asistencia a reuniones', pct(totals.meeting_attendance_pct), `${totals.meetings_held} realizada(s)`], ['Necesitan seguimiento', totals.needs_followup, 'participantes']].map(([label, value, hint]) => <div key={label} className="rounded-lg border border-[#EEECE6] bg-[#FBFAF7] p-2 text-center"><p className="text-xl font-semibold text-[#101D36]">{value}</p><p className="text-[11px] text-slate-600">{label}</p><p className="text-[10px] text-slate-400">{hint}</p></div>)}
      </div>
      <p className="text-[11px] text-slate-500">{data.rule}</p>

      <div className="space-y-2 rounded-lg border border-[#EEECE6] p-3">
        <p className="text-sm font-semibold text-[#101D36]">Reuniones de oración en la iglesia</p>
        {data.meetings.map((meeting) => (
          <div key={meeting.meeting_id} className="rounded-lg border border-[#EEECE6] p-2" data-testid={`prayer-meeting-${meeting.meeting_id}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <button type="button" onClick={() => setOpenMeeting(openMeeting === meeting.meeting_id ? null : meeting.meeting_id)} className="min-h-10 text-left text-sm"><b>{shortDate(meeting.day)}{meeting.time ? ` · ${meeting.time}` : ''}</b> · {meeting.place} · {meeting.attendee_count} asistente(s)</button>
              {!meeting.attendee_count && <button type="button" onClick={() => call(() => axios.delete(`${API}/api/invasions/${campaignId}/prayer/meetings/${meeting.meeting_id}`, getAuthHeaders()))} className="grid h-10 w-10 place-items-center rounded-md text-[#8f382f] hover:bg-red-50" aria-label="Eliminar reunión"><Trash2 className="h-4 w-4" /></button>}
            </div>
            {openMeeting === meeting.meeting_id && (meeting.day > today
              ? <p className="text-xs text-slate-500">La asistencia se registra el día de la reunión.</p>
              : <ul className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">{people.map((person) => { const checked = (meeting.attendee_ids || []).includes(person.person_id); return <li key={person.person_id}><label className="flex min-h-11 items-center gap-2 rounded-md border border-[#EEECE6] px-2 text-sm"><input type="checkbox" className="h-5 w-5" checked={checked} disabled={busy} onChange={() => call(() => axios.put(`${API}/api/invasions/${campaignId}/prayer/meetings/${meeting.meeting_id}/attendance`, { person_id: person.person_id, attended: !checked }, getAuthHeaders()))} data-testid={`prayer-attendance-${meeting.meeting_id}-${person.person_id}`} />{person.name}</label></li>; })}</ul>)}
          </div>
        ))}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-[1fr_8rem_1fr_auto]">
          <input type="date" value={form.day} min={data.period.prayer_start} max={data.period.end} onChange={(event) => setForm({ ...form, day: event.target.value })} className="h-11 rounded-lg border border-[#D9D4C7] px-2 text-sm" aria-label="Fecha" />
          <input type="time" value={form.time} onChange={(event) => setForm({ ...form, time: event.target.value })} className="h-11 rounded-lg border border-[#D9D4C7] px-2 text-sm" aria-label="Hora" />
          <input value={form.place} onChange={(event) => setForm({ ...form, place: event.target.value })} className="col-span-2 h-11 rounded-lg border border-[#D9D4C7] px-2 text-sm sm:col-span-1" aria-label="Lugar" />
          <button type="button" disabled={busy} onClick={() => call(() => axios.post(`${API}/api/invasions/${campaignId}/prayer/meetings`, { day: form.day, time: form.time || null, place: form.place }, getAuthHeaders()), 'Reunión agregada')} className="col-span-2 inline-flex min-h-11 items-center justify-center gap-1 rounded-lg bg-[#101D36] px-4 text-sm font-semibold text-white sm:col-span-1" data-testid="prayer-meeting-add"><Plus className="h-4 w-4" />Agregar</button>
        </div>
      </div>

      <ul className="space-y-2" data-testid="prayer-people">
        {people.map((person) => {
          const prayedToday = person.prayer_days.includes(today);
          return (
            <li key={person.person_id} className="rounded-lg border border-[#EEECE6] p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0"><p className="text-sm font-semibold text-[#101D36]">{person.name}</p><p className="text-xs text-slate-500">{person.prayer_count} día(s) de oración · {person.meetings_attended_count} reunión(es)</p></div>
                {person.followup_reason ? <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800" title={person.followup_reason}>Seguimiento</span> : <span className="rounded-full border border-[#bcd8c4] bg-[#eef5f0] px-2 py-0.5 text-xs font-semibold text-[#2f6e47]">Al día</span>}
              </div>
              {person.followup_reason && <p className="mt-1 text-xs text-amber-800">{person.followup_reason}</p>}
              <div className="mt-2"><DayDots period={data.period} prayed={person.prayer_days} /></div>
              {today >= data.period.prayer_start && today <= data.period.end && <button type="button" disabled={busy} onClick={() => call(() => axios.put(`${API}/api/invasions/${campaignId}/prayer/home/${person.person_id}`, { prayed: !prayedToday }, getAuthHeaders()))} className="mt-2 min-h-10 rounded-md border border-[#D9D4C7] px-3 text-xs font-semibold text-[#101D36]" data-testid={`prayer-mark-${person.person_id}`}>{prayedToday ? 'Quitar oración de hoy' : 'Marcar que oró hoy'}</button>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
