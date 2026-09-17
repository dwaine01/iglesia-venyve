import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowLeft, BadgeCheck, BookOpen, History, UserRoundCheck } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { ConsolidationActionPanel } from '../../components/processes/ConsolidationActionPanel';
import { ConsolidationStageRail } from '../../components/processes/ConsolidationStageRail';
import { ProcessError, ProcessLoading, ProcessShell } from '../../components/processes/ProcessShell';
import { Button } from '../../components/ui/button';
import { processStageLabel } from '../../lib/displayLabels';

export default function ConsolidationDetailPage() {
  const { enrollmentId } = useParams();
  const navigate = useNavigate();
  const { API, getAuthHeaders } = useAuth();
  const [journey, setJourney] = useState(null);
  const [assignees, setAssignees] = useState([]);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try {
      const [detail, catalog] = await Promise.all([axios.get(`${API}/api/processes/consolidation/${enrollmentId}`, getAuthHeaders()), axios.get(`${API}/api/processes/catalog`, getAuthHeaders())]);
      setJourney(detail.data); setAssignees(catalog.data.assignees || []); setError('');
    } catch (requestError) { setError(requestError?.response?.data?.detail || 'No se pudo cargar el expediente'); }
  }, [API, enrollmentId, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  return <ProcessShell title={journey?.person?.name || 'Expediente de Consolidación'} eyebrow="Consolidación v2" description="Progreso, membresía, mentoría y transferencias conservados en un solo expediente." actions={<Button variant="outline" onClick={() => navigate('/procesos/consolidacion')} data-testid="back-to-consolidation-button"><ArrowLeft className="h-4 w-4" />Volver</Button>}>
    {!journey && !error ? <ProcessLoading /> : error ? <ProcessError message={error} /> : <>
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="journey-status-summary"><article className="border bg-white p-4"><BookOpen className="h-5 w-5 text-amber-600" /><span className="mt-4 block text-xs text-slate-500">Consolidación</span><b>{journey.consolidation_status === 'completed' ? 'Completada' : 'En progreso'} · {processStageLabel(journey.current_stage_key)}</b></article><article className="border bg-white p-4"><BadgeCheck className="h-5 w-5 text-emerald-700" /><span className="mt-4 block text-xs text-slate-500">Membresía</span><b>{journey.membership?.status === 'active' ? `Miembro · ${journey.membership.member_number}` : 'Sin firma registrada'}</b></article><article className="border bg-white p-4"><UserRoundCheck className="h-5 w-5 text-blue-700" /><span className="mt-4 block text-xs text-slate-500">Mentor LBS</span><b>{journey.mentor_lbs_qualified ? 'Autorizado' : journey.mentor_transfer_required ? 'Transferencia requerida' : 'Pendiente de evaluación'}</b></article><article className="border bg-white p-4"><History className="h-5 w-5 text-slate-600" /><span className="mt-4 block text-xs text-slate-500">Discipulado</span><b>{journey.discipleship ? 'Expediente abierto' : 'Pendiente de Retiro'}</b></article></section>
      <ConsolidationStageRail stages={journey.stages || []} currentStageKey={journey.current_stage_key} />
      <div className="grid gap-6 lg:grid-cols-[1.25fr_.75fr]"><section className="space-y-5"><div className="border bg-white p-5"><div className="flex items-center justify-between"><h2 className="font-['Spectral'] text-2xl font-semibold">Historial permanente</h2><Link className="text-sm font-semibold text-amber-700" to={`/personas/${journey.person.person_id}`} data-testid="open-journey-person-profile">Abrir Perfil 360</Link></div><div className="mt-4 space-y-3">{journey.timeline?.map((event) => <article key={event._id || `${event.event_type}-${event.occurred_at}`} className="border-l-2 border-amber-400 pl-3"><b className="text-sm">{event.title}</b><p className="text-xs text-slate-500">{event.detail}</p><time className="text-[10px] text-slate-400">{new Date(event.occurred_at).toLocaleString('es-US')}</time></article>)}</div></div><div className="border bg-white p-5"><h2 className="font-['Spectral'] text-2xl font-semibold">Historial de mentores</h2><div className="mt-4 space-y-3">{journey.mentor_assignments?.map((item) => <article key={item.assignment_id} className="flex justify-between border-b pb-3 text-sm"><span>{item.mentor_person_id}<small className="block text-slate-500">{item.reason}</small></span><b>{item.active ? 'Actual' : 'Transferido'}</b></article>)}</div></div></section><ConsolidationActionPanel journey={journey} assignees={assignees} onUpdated={load} /></div>
    </>}
  </ProcessShell>;
}