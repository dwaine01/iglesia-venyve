import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { GraduationCap, Loader2, Undo2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Checkbox } from '../../components/ui/checkbox';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { ProcessError, ProcessLoading, ProcessShell } from '../../components/processes/ProcessShell';
import { churchToday } from '../../lib/churchDate';

// R2 · Graduación: acto aparte después del Retiro. La iglesia crea el evento con su fecha y registra a
// varias personas a la vez; solo entonces se completa la Consolidación y se abre el traspaso a Discipulado.
const errorText = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.problems?.length) return `${detail.message}: ${detail.problems.join(' · ')}`;
  return detail?.message || fallback;
};

export default function GraduationsPage() {
  const { API, getAuthHeaders } = useAuth();
  const [list, setList] = useState(null);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState(null);
  const [picked, setPicked] = useState([]);
  const [busy, setBusy] = useState('');
  const [form, setForm] = useState({ name: '', event_date: churchToday(), location: '' });

  const loadList = useCallback(async () => {
    try { setList((await axios.get(`${API}/api/processes/consolidation/graduations`, getAuthHeaders())).data); setError(''); }
    catch (requestError) { setError(errorText(requestError, 'No se pudieron cargar las graduaciones')); }
  }, [API, getAuthHeaders]);
  const loadDetail = useCallback(async (eventId) => {
    if (!eventId) { setDetail(null); return; }
    try { setDetail((await axios.get(`${API}/api/processes/consolidation/graduations/${eventId}`, getAuthHeaders())).data); setPicked([]); }
    catch (requestError) { toast.error(errorText(requestError, 'No se pudo abrir el evento')); }
  }, [API, getAuthHeaders]);
  useEffect(() => { loadList(); }, [loadList]);
  useEffect(() => { loadDetail(selectedId); }, [loadDetail, selectedId]);

  const run = async (key, request, message) => {
    setBusy(key);
    try { await request(); toast.success(message); await loadList(); await loadDetail(selectedId); return true; }
    catch (requestError) { toast.error(errorText(requestError, 'No se pudo completar la acción')); return false; }
    finally { setBusy(''); }
  };
  const createEvent = async () => {
    setBusy('create');
    try {
      const response = await axios.post(`${API}/api/processes/consolidation/graduations`, { name: form.name, event_date: form.event_date, location: form.location || null }, getAuthHeaders());
      toast.success('Evento de graduación creado'); setForm({ name: '', event_date: churchToday(), location: '' }); await loadList(); setSelectedId(response.data.event_id);
    } catch (requestError) { toast.error(errorText(requestError, 'No se pudo crear el evento')); } finally { setBusy(''); }
  };
  const graduate = () => run('graduate', () => axios.post(`${API}/api/processes/consolidation/graduations/${selectedId}/graduates`, { enrollment_ids: picked }, getAuthHeaders()), 'Graduación registrada');
  const revert = (row) => {
    const reason = window.prompt(`Motivo para revertir la graduación de ${row.person_name}`);
    if (!reason) return;
    run(`revert-${row.enrollment_id}`, () => axios.post(`${API}/api/processes/consolidation/graduations/${selectedId}/graduates/${row.enrollment_id}/revert`, { reason }, getAuthHeaders()), 'Graduación revertida');
  };

  const canManage = Boolean(list?.can_manage);
  const event = detail?.event;
  const futureEvent = event && event.event_date > churchToday();
  return <ProcessShell title="Graduaciones" eyebrow="Consolidación" description="La graduación es un acto aparte, después del Retiro. La iglesia fija la fecha; al registrar a la persona en el evento se completa su Consolidación y se abre el paso a Discipulado de Formación.">
    {error ? <ProcessError message={error} /> : !list ? <ProcessLoading /> : <>
      <section className="grid gap-3 sm:grid-cols-2" data-testid="graduation-summary">
        <article className="border bg-white p-4"><span className="text-xs text-slate-500">Retiro hecho · pendientes de graduación</span><b className="mt-2 block font-['Spectral'] text-3xl" data-testid="graduation-pending-count">{list.pending_count}</b></article>
        <article className="border bg-white p-4"><span className="text-xs text-slate-500">Cerraron el Retiro con la regla anterior (sin graduación registrada)</span><b className="mt-2 block font-['Spectral'] text-3xl" data-testid="graduation-legacy-count">{list.legacy_retreat_closed_count}</b><small className="mt-1 block text-slate-500">No se modifican: su tratamiento espera la decisión del dueño.</small></article>
      </section>
      {canManage && <section className="space-y-3 border bg-white p-5" data-testid="graduation-create-form"><h2 className="font-['Spectral'] text-xl font-semibold">Nuevo evento de graduación</h2>
        <div className="grid gap-3 sm:grid-cols-3"><div className="space-y-1"><Label>Nombre</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Graduación de Consolidación" data-testid="graduation-name-input" /></div>
          <div className="space-y-1"><Label>Fecha</Label><Input type="date" value={form.event_date} onChange={(e) => setForm({ ...form, event_date: e.target.value })} data-testid="graduation-date-input" /></div>
          <div className="space-y-1"><Label>Lugar (opcional)</Label><Input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} data-testid="graduation-location-input" /></div></div>
        <Button disabled={busy === 'create' || form.name.trim().length < 3 || !form.event_date} onClick={createEvent} data-testid="graduation-create-button">{busy === 'create' ? <Loader2 className="h-4 w-4 animate-spin" /> : <GraduationCap className="h-4 w-4" />}Crear evento</Button></section>}
      <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <div className="space-y-2" data-testid="graduation-events-list"><h2 className="font-['Spectral'] text-xl font-semibold">Eventos</h2>
          {list.items.length ? list.items.map((item) => <button key={item.event_id} type="button" onClick={() => setSelectedId(item.event_id)} className={`block w-full border p-3 text-left text-sm ${selectedId === item.event_id ? 'border-amber-500 bg-amber-50' : 'bg-white'}`} data-testid={`graduation-event-${item.event_id}`}><b className="block">{item.name}</b><span className="text-slate-500">{item.event_date}{item.location ? ` · ${item.location}` : ''} · {item.graduates_count} graduado(s){item.status === 'cancelled' ? ' · cancelado' : ''}</span></button>) : <p className="border border-dashed bg-white p-6 text-center text-sm text-slate-500">Todavía no hay eventos de graduación.</p>}</div>
        <div className="space-y-4">{!event ? <p className="border border-dashed bg-white p-6 text-center text-sm text-slate-500">Elija un evento para ver sus graduados y registrar a otros.</p> : <>
          <article className="border bg-white p-4"><h2 className="font-['Spectral'] text-2xl font-semibold">{event.name}</h2><p className="text-sm text-slate-500">{event.event_date}{event.location ? ` · ${event.location}` : ''}</p></article>
          <article className="space-y-2 border bg-white p-4" data-testid="graduation-graduates"><h3 className="font-semibold">Graduados en este evento</h3>
            {detail.graduates.length ? detail.graduates.map((row) => <div key={row.record_id} className="flex flex-wrap items-center justify-between gap-2 border-t pt-2 text-sm"><Link className="font-medium text-blue-800 hover:underline" to={`/procesos/consolidacion/${row.enrollment_id}`}>{row.person_name}</Link>{row.status === 'reverted' ? <span className="text-xs text-slate-500">Revertida: {row.revert_reason}</span> : canManage && <Button size="sm" variant="outline" disabled={Boolean(busy)} onClick={() => revert(row)} data-testid={`graduation-revert-${row.enrollment_id}`}><Undo2 className="h-4 w-4" />Revertir</Button>}</div>) : <p className="text-sm text-slate-500">Nadie todavía.</p>}</article>
          {canManage && event.status !== 'cancelled' && <article className="space-y-2 border bg-white p-4" data-testid="graduation-candidates"><h3 className="font-semibold">Retiro hecho · pendientes de graduación</h3>
            {futureEvent && <p className="text-sm text-amber-800">La graduación se registra el día del evento o después.</p>}
            {detail.candidates.length ? detail.candidates.map((row) => <label key={row.enrollment_id} className="flex items-center gap-3 border-t pt-2 text-sm"><Checkbox checked={picked.includes(row.enrollment_id)} onCheckedChange={(checked) => setPicked((prev) => checked === true ? [...prev, row.enrollment_id] : prev.filter((id) => id !== row.enrollment_id))} data-testid={`graduation-pick-${row.enrollment_id}`} /><span><b>{row.person_name}</b>{row.mentor_name ? <span className="text-slate-500"> · mentor {row.mentor_name}</span> : null}{row.retreat_completed_at ? <span className="text-slate-500"> · Retiro {String(row.retreat_completed_at).slice(0, 10)}</span> : null}</span></label>) : <p className="text-sm text-slate-500">No hay personas pendientes de graduación.</p>}
            <Button disabled={!picked.length || Boolean(busy) || futureEvent} onClick={graduate} data-testid="graduation-register-button">{busy === 'graduate' ? <Loader2 className="h-4 w-4 animate-spin" /> : <GraduationCap className="h-4 w-4" />}Registrar graduación ({picked.length})</Button></article>}
        </>}</div>
      </section>
    </>}
  </ProcessShell>;
}
