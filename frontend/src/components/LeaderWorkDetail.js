import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { BookOpen, CalendarCheck, Clock, DoorOpen, Loader2, Sprout, UserCheck } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';

const ICON = { visit: DoorOpen, person: UserCheck, book: BookOpen };
const ROLE_LABELS = { mentor: 'Mentor', collaborator: 'Colaborador', general_lead: 'Encargado general', logistics: 'Logística' };

/** Panel General › Entrar al Líder: resumen (hoy / semana / total), trabajo de hoy
 * hora por hora, expedientes de Consolidación y asistencia a invasiones. Las mismas
 * cifras de «Supervisar Mi Trabajo» (una sola fuente en el backend). */
export function LeaderWorkDetail({ mentorPersonId }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    setData(null); setError('');
    axios.get(`${API}/api/my-work/leader-detail`, { ...getAuthHeaders(), params: { mentor_person_id: mentorPersonId } })
      .then((response) => setData(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar el detalle del líder')));
  }, [API, getAuthHeaders, mentorPersonId]);
  if (error) return <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800" data-testid="leader-detail-error">{error}</p>;
  if (!data) return <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />;
  const { today, week, total } = data.summary;
  const block = (title, rows) => (
    <div className="rounded-xl border border-[#E8E5DE] bg-white p-3">
      <p className="text-sm font-bold uppercase tracking-wide text-[#7A5F22]">{title}</p>
      <ul className="mt-1 space-y-0.5 text-[15px] text-[#101D36]">{rows.map(([label, value]) => <li key={label} className="flex justify-between gap-2"><span>{label}</span><b>{value ?? 0}</b></li>)}</ul>
    </div>
  );
  return (
    <section className="space-y-4" data-testid="leader-detail">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">{data.name}</h2>
        <span className="rounded-full border px-2.5 py-1 text-sm font-semibold" data-testid="leader-detail-status">{data.row.work_status_label}</span>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3" data-testid="leader-detail-summary">
        {block('Hoy', [['Viviendas visitadas', today.houses], ['Personas registradas', today.people], ['Libros entregados', today.books]])}
        {block('Esta semana', [['Viviendas visitadas', week.houses], ['Abrieron', week.opened], ['Comenzaron Consolidación', week.started_consolidation]])}
        {block('Total', [['Viviendas visitadas', total.houses], ['Personas contactadas', total.people], ['Libros entregados', total.books], ['Personas en Consolidación', total.in_consolidation], ['Pendientes', total.pending]])}
      </div>
      <div className="rounded-xl border border-[#E8E5DE] bg-white p-3" data-testid="leader-detail-timeline">
        <p className="flex items-center gap-1.5 text-base font-semibold text-[#101D36]"><Clock className="h-4 w-4 text-[#9A7A2F]" />Su trabajo de hoy, hora por hora</p>
        {data.timeline.length === 0 ? <p className="mt-1 text-[15px] text-slate-600">Hoy todavía no registró visitas, personas ni libros.</p> : (
          <ol className="mt-2 divide-y divide-[#F1EFEA]">{data.timeline.map((item, index) => {
            const Icon = ICON[item.kind] || DoorOpen;
            return (
              <li key={index} className="flex items-start gap-3 py-2" data-testid={`leader-timeline-${item.kind}`}>
                <span className="w-14 shrink-0 text-[15px] font-bold text-[#132443]">{item.time || '—'}</span>
                <Icon className="mt-1 h-4 w-4 shrink-0 text-[#9A7A2F]" />
                <span className="min-w-0"><span className="block text-[15px] font-semibold text-[#101D36]">{item.title}</span>{item.detail && <span className="block text-sm text-slate-600">{item.detail}</span>}
                  {item.person_id && <Link to={`/personas/${item.person_id}`} className="text-sm font-semibold text-[#0879BE] underline">Perfil 360</Link>}</span>
              </li>
            );
          })}</ol>
        )}
      </div>
      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        <div className="rounded-xl border border-[#E8E5DE] bg-white p-3" data-testid="leader-detail-enrollments">
          <p className="flex items-center gap-1.5 text-base font-semibold text-[#101D36]"><Sprout className="h-4 w-4 text-[#9A7A2F]" />Expedientes de Consolidación ({data.enrollments.length})</p>
          {data.enrollments.length === 0 ? <p className="mt-1 text-[15px] text-slate-600">No acompaña expedientes de Consolidación activos.</p> : (
            <ul className="mt-1 divide-y divide-[#F1EFEA]">{data.enrollments.map((item) => (
              <li key={item.enrollment_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="text-[15px] text-[#101D36]"><b>{item.name}</b> · Etapa: {item.stage || '—'}{item.next_action ? ` · Próximo: ${item.next_action}` : ' · Sin próxima acción'}</span>
                <span className="flex gap-2"><Link to={`/procesos/consolidacion/${item.enrollment_id}`} className="text-sm font-semibold text-[#0879BE] underline">Expediente</Link><Link to={`/personas/${item.person_id}`} className="text-sm font-semibold text-[#0879BE] underline">Perfil 360</Link></span>
              </li>))}</ul>
          )}
        </div>
        <div className="rounded-xl border border-[#E8E5DE] bg-white p-3" data-testid="leader-detail-attendance">
          <p className="flex items-center gap-1.5 text-base font-semibold text-[#101D36]"><CalendarCheck className="h-4 w-4 text-[#9A7A2F]" />Asistencia a invasiones</p>
          {data.attendance.length === 0 ? <p className="mt-1 text-[15px] text-slate-600">No figura como participante en ninguna invasión.</p> : (
            <ul className="mt-1 divide-y divide-[#F1EFEA]">{data.attendance.map((item) => (
              <li key={item.campaign_id} className="py-2 text-[15px] text-[#101D36]"><b>{item.name}</b> · {item.roles.map((role) => ROLE_LABELS[role] || role).join(', ') || 'Participante'} · {item.attended ? `Asistió${item.days ? ` (${item.days} día(s))` : ''}` : 'No asistió'}</li>
            ))}</ul>
          )}
        </div>
      </div>
      <p className="text-sm text-slate-600">Inventario de libros: <b>{data.inventory.received}</b> recibidos · <b>{data.inventory.delivered}</b> entregados · <b>{data.inventory.available}</b> disponibles. Debajo: sus pendientes, sus personas y sus viviendas.</p>
    </section>
  );
}
