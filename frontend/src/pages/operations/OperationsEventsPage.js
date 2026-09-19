import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { CalendarDays, ChevronRight, Loader2, Plus, Repeat2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../../components/ui/button';
import { EventCreateDialog } from '../../components/operations/EventCreateDialog';
import { OperationsShell } from '../../components/operations/OperationsShell';

const dateTime = (value) => value ? new Intl.DateTimeFormat('es-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Sin próxima fecha';

export default function OperationsEventsPage() {
  const { API, getAuthHeaders } = useAuth(); const [data, setData] = useState(null); const [open, setOpen] = useState(false); const [saving, setSaving] = useState(false); const [error, setError] = useState('');
  const load = useCallback(() => axios.get(`${API}/api/operations/events`, getAuthHeaders()).then((response) => setData(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudieron cargar los eventos'))), [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  const create = async (payload) => { setSaving(true); setError(''); try { await axios.post(`${API}/api/operations/events`, payload, getAuthHeaders()); toast.success('Evento y ocurrencias creados'); setOpen(false); await load(); } catch (requestError) { setError(apiErrorMessage(requestError, 'No se pudo crear el evento')); } finally { setSaving(false); } };
  const actions = data?.permissions?.manage ? <Button onClick={() => setOpen(true)} className="bg-[#E5B94B] text-slate-950 hover:bg-[#F1CB68]" data-testid="operations-new-event-button"><Plus className="h-4 w-4" />Nuevo evento</Button> : null;
  return <OperationsShell title="Eventos" description="Series únicas o recurrentes listas para voluntariado, registro y control de asistencia." actions={actions}>
    {!data && !error && <div className="flex justify-center py-20"><Loader2 className="h-7 w-7 animate-spin" /></div>}
    {error && !open && <div className="border border-red-300 bg-red-50 p-3 text-sm text-red-800" data-testid="operations-events-error">{error}</div>}
    {data && <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="operations-events-list">{data.items.length === 0 ? <div className="col-span-full border border-dashed bg-white p-10 text-center" data-testid="operations-events-empty"><CalendarDays className="mx-auto h-8 w-8 text-slate-400" /><b className="mt-3 block">Aún no hay eventos</b></div> : data.items.map((event) => <Link key={event.event_id} to={`/operaciones/eventos/${event.event_id}`} className="group border bg-white p-5 shadow-sm transition-transform hover:-translate-y-1" data-testid={`operation-event-card-${event.event_id}`}><div className="flex items-start justify-between gap-3"><span className="bg-slate-950 px-2 py-1 text-xs font-bold uppercase text-white">{event.event_type}</span>{event.recurrence?.frequency !== 'none' && <span className="flex items-center gap-1 text-xs font-semibold text-blue-700"><Repeat2 className="h-3.5 w-3.5" />Recurrente</span>}</div><h2 className="mt-5 font-['Spectral'] text-2xl font-semibold text-slate-950">{event.title}</h2><p className="mt-2 text-sm text-slate-500">{event.location}</p><div className="mt-6 flex items-end justify-between border-t pt-4"><div><small className="block uppercase text-slate-400">Próxima</small><b className="text-sm">{dateTime(event.next_occurrence?.starts_at)}</b></div><ChevronRight className="h-5 w-5 text-slate-400 transition-transform group-hover:translate-x-1" /></div></Link>)}</section>}
    <EventCreateDialog open={open} onOpenChange={(value) => { setOpen(value); if (!value) setError(''); }} onCreate={create} saving={saving} error={open ? error : ''} />
  </OperationsShell>;
}