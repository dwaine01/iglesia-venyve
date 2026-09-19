import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowRight, Bell, CalendarClock, Loader2, Plus } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../../components/ui/button';
import { OperationsMetrics } from '../../components/operations/OperationsMetrics';
import { OperationsShell } from '../../components/operations/OperationsShell';

const dateTime = (value) => new Intl.DateTimeFormat('es-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

export default function OperationsDashboardPage() {
  const { API, getAuthHeaders } = useAuth(); const navigate = useNavigate(); const [data, setData] = useState(null); const [error, setError] = useState('');
  useEffect(() => { axios.get(`${API}/api/operations/dashboard`, getAuthHeaders()).then((response) => setData(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar Operaciones'))); }, [API, getAuthHeaders]);
  const actions = data?.permissions?.manage ? <Button onClick={() => navigate('/operaciones/eventos')} className="bg-[#E5B94B] text-slate-950 hover:bg-[#F1CB68]" data-testid="operations-dashboard-create-event-button"><Plus className="h-4 w-4" />Crear evento</Button> : null;
  return <OperationsShell title="Centro de operaciones" description="Próximas ocurrencias, cobertura de equipos y movimiento de asistencia en un solo lugar." actions={actions}>
    {error && <div className="border border-red-300 bg-red-50 p-4 text-sm text-red-800" data-testid="operations-dashboard-error">{error}</div>}
    {!data && !error && <div className="flex justify-center py-20" data-testid="operations-dashboard-loading"><Loader2 className="h-7 w-7 animate-spin text-emerald-700" /></div>}
    {data && <div className="space-y-7"><OperationsMetrics metrics={data.metrics} /><div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
      <section className="border bg-white" data-testid="operations-upcoming-section"><header className="flex items-center justify-between border-b p-4"><div><p className="text-xs font-bold uppercase text-blue-700">Agenda</p><h2 className="font-['Spectral'] text-2xl font-semibold">Próximas ocurrencias</h2></div><Link to="/operaciones/eventos" className="text-sm font-semibold text-emerald-700" data-testid="operations-view-all-events-link">Ver eventos</Link></header><div className="divide-y">{data.upcoming.length === 0 ? <p className="p-6 text-sm text-slate-500" data-testid="operations-upcoming-empty">No hay ocurrencias durante los próximos siete días.</p> : data.upcoming.map((item) => <Link key={item.occurrence_id} to={`/operaciones/ocurrencias/${item.occurrence_id}`} className="flex items-center gap-4 p-4 transition-colors hover:bg-emerald-50" data-testid={`operations-upcoming-${item.occurrence_id}`}><span className="flex h-11 w-11 shrink-0 items-center justify-center bg-blue-50 text-blue-700"><CalendarClock className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-slate-950">{item.event?.title || 'Evento'}</b><small className="block text-slate-500">{dateTime(item.starts_at)} · {item.event?.location}</small></span><ArrowRight className="h-4 w-4 text-slate-400" /></Link>)}</div></section>
      <section className="border bg-white" data-testid="operations-notifications-section"><header className="border-b p-4"><p className="text-xs font-bold uppercase text-amber-700">Actividad</p><h2 className="flex items-center gap-2 font-['Spectral'] text-2xl font-semibold"><Bell className="h-5 w-5" />Notificaciones</h2></header><div className="divide-y">{data.notifications.length === 0 ? <p className="p-6 text-sm text-slate-500" data-testid="operations-notifications-empty">No tiene notificaciones pendientes.</p> : data.notifications.map((item) => <div key={item.notification_id} className="p-4" data-testid={`operation-notification-${item.notification_id}`}><b className="block text-sm">{item.title}</b><p className="mt-1 text-xs leading-5 text-slate-600">{item.message}</p></div>)}</div></section>
    </div></div>}
  </OperationsShell>;
}