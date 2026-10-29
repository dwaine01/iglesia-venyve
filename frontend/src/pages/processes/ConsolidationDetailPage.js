import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowLeft, BadgeCheck, BookOpen, Droplets, History, PauseCircle, PlayCircle, UserRoundCheck } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { ConsolidationActionPanel } from '../../components/processes/ConsolidationActionPanel';
import { ConsolidationActivityCalendar } from '../../components/processes/ConsolidationActivityCalendar';
import { ConsolidationStageRail } from '../../components/processes/ConsolidationStageRail';
import { PersonStepByStep } from '../../components/PersonStepByStep';
import { ProcessError, ProcessLoading, ProcessShell } from '../../components/processes/ProcessShell';
import { Button } from '../../components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Textarea } from '../../components/ui/textarea';
import { processStageLabel } from '../../lib/displayLabels';
import { mentorAccessSuffix, mentorAccessDisabled, isPastoralAuthority, isGeneralCoordinator } from '../../lib/accessControl';
import { errorDetailText } from '../../lib/errorText';

const DECISION_STATUS_LABEL = {
  contacted: 'Contactado', pending_decision: 'Pendiente de decisión', accepted: 'Aceptó consolidación',
  start_scheduled: 'Inicio programado', in_progress: 'En proceso', paused: 'Pausado o desistió', completed: 'Completado',
};

const CALL_SCHEDULE_LABEL = { morning: 'Mañana', midday: 'Medio día', night: 'Noche' };
const ATTEMPT_RESULT_LABEL = {
  contacted: 'Contactado', no_answer: 'Sin respuesta', not_home: 'No está en casa', rejected: 'Rechazó',
};

export default function ConsolidationDetailPage() {
  const { enrollmentId } = useParams();
  const navigate = useNavigate();
  const { API, getAuthHeaders, user } = useAuth();
  const [journey, setJourney] = useState(null);
  const [assignees, setAssignees] = useState([]);
  const [error, setError] = useState('');
  const [pauseOpen, setPauseOpen] = useState(false);
  const [pauseReason, setPauseReason] = useState('');
  const [pauseSaving, setPauseSaving] = useState(false);
  const loadJourney = useCallback(async () => {
    try {
      const detail = await axios.get(`${API}/api/processes/consolidation/${enrollmentId}`, getAuthHeaders());
      setJourney(detail.data); setError('');
    } catch (requestError) { setError(requestError?.response?.data?.detail || 'No se pudo cargar el expediente'); }
  }, [API, enrollmentId, getAuthHeaders]);
  useEffect(() => {
    loadJourney();
    Promise.all([
      axios.get(`${API}/api/processes/catalog`, getAuthHeaders()),
      axios.get(`${API}/api/mentorship/mentors`, getAuthHeaders()).catch((mentorError) => { toast.error(mentorError?.response?.data?.detail || 'No se pudo cargar la lista de mentores'); return { data: { items: [] } }; }),
    ]).then(([catalog, mentors]) => {
      const mentorOptions = new Map((catalog.data.assignees || []).map((item) => [item.person_id, item]));
      (mentors.data.items || []).forEach((item) => mentorOptions.set(item.person_id, { person_id: item.person_id, name: `${item.lbs_qualified ? `${item.name} (LBS)` : item.name}${mentorAccessSuffix(item)}`, role: 'mentor', lbs_qualified: item.lbs_qualified, has_account: item.has_account, account_active: item.account_active, disabled: mentorAccessDisabled(item) }));
      setAssignees(Array.from(mentorOptions.values()));
    }).catch((catalogError) => { toast.error(catalogError?.response?.data?.detail || 'No se pudo cargar la lista de mentores'); setAssignees([]); });
  }, [API, getAuthHeaders, loadJourney]);
  const updateCurrentTasks = useCallback((tasks) => {
    setJourney((current) => current ? {
      ...current,
      stages: (current.stages || []).map((stage) => stage.stage_key === current.current_stage_key ? { ...stage, tasks } : stage),
    } : current);
  }, []);
  const togglePause = async () => {
    if (journey.decision_status === 'paused') {
      try {
        const response = await axios.put(`${API}/api/processes/consolidation/${enrollmentId}/decision-status`, { new_status: 'accepted' }, getAuthHeaders());
        setJourney(response.data);
        toast.success('Proceso reanudado');
      } catch (requestError) { toast.error(errorDetailText(requestError, 'No se pudo reanudar')); }
      return;
    }
    setPauseOpen(true);
  };
  const confirmPause = async () => {
    if (!pauseReason.trim()) { toast.error('Indique el motivo de la pausa o el desistimiento'); return; }
    setPauseSaving(true);
    try {
      const response = await axios.put(`${API}/api/processes/consolidation/${enrollmentId}/decision-status`, { new_status: 'paused', reason: pauseReason }, getAuthHeaders());
      setJourney(response.data);
      toast.success('Proceso pausado');
      setPauseOpen(false); setPauseReason('');
    } catch (requestError) { toast.error(errorDetailText(requestError, 'No se pudo pausar')); } finally { setPauseSaving(false); }
  };
  const canRegisterActivities = journey && (user?.person_id === journey.mentor_person_id || isPastoralAuthority(user) || isGeneralCoordinator(user));
  return <ProcessShell title={journey?.person?.name || 'Expediente de Consolidación'} eyebrow="Consolidación v2" description="Progreso, membresía, mentoría y transferencias conservados en un solo expediente." actions={<Button variant="outline" onClick={() => navigate('/procesos/consolidacion')} data-testid="back-to-consolidation-button"><ArrowLeft className="h-4 w-4" />Volver</Button>}>
    {!journey && !error ? <ProcessLoading /> : error ? <ProcessError message={error} /> : <>
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6" data-testid="journey-status-summary"><article className="border bg-white p-4"><BookOpen className="h-5 w-5 text-amber-600" /><span className="mt-4 block text-xs text-slate-500">Consolidación</span><b>{journey.consolidation_status === 'completed' ? 'Completada' : journey.consolidation_status === 'graduation_pending' ? 'Pendiente de graduación' : 'En progreso'} · {processStageLabel(journey.current_stage_key)}</b></article><article className="border bg-white p-4"><BadgeCheck className="h-5 w-5 text-emerald-700" /><span className="mt-4 block text-xs text-slate-500">Membresía</span><b>{journey.membership?.status === 'active' ? `Miembro · ${journey.membership.member_number}` : 'Sin firma registrada'}</b></article><article className="border bg-white p-4" data-testid="journey-baptism-summary"><Droplets className="h-5 w-5 text-sky-700" /><span className="mt-4 block text-xs text-slate-500">Bautismo · recomendado antes de Retiro</span><b>{journey.baptism?.status === 'completed' ? `Completado · ${journey.baptism.baptism_date || ''}` : journey.baptism?.status === 'scheduled' ? 'Programado' : 'Pendiente'}</b></article><article className="border bg-white p-4"><UserRoundCheck className="h-5 w-5 text-blue-700" /><span className="mt-4 block text-xs text-slate-500">Mentor LBS</span><b>{journey.mentor_lbs_qualified ? 'Autorizado' : journey.mentor_transfer_required ? 'Transferencia requerida' : 'Pendiente de evaluación'}</b></article><article className="border bg-white p-4"><History className="h-5 w-5 text-slate-600" /><span className="mt-4 block text-xs text-slate-500">Graduación y Discipulado</span><b data-testid="journey-discipleship-summary">{journey.discipleship ? `Inscrito · ${journey.discipleship.module_name_snapshot || 'Discipulado'}` : journey.graduated_at ? `Graduado ${String(journey.graduated_at).slice(0, 10)} · falta inscribir` : journey.retreat_completed_at ? (journey.status === 'completed' ? 'Retiro cerrado (regla anterior)' : 'Pendiente de graduación') : 'Pendiente de Retiro'}</b></article><article className="border bg-white p-4" data-testid="journey-decision-status-summary">{journey.decision_status === 'paused' ? <PauseCircle className="h-5 w-5 text-rose-600" /> : <PlayCircle className="h-5 w-5 text-emerald-700" />}<span className="mt-4 block text-xs text-slate-500">Estado de decisión</span><b>{DECISION_STATUS_LABEL[journey.decision_status] || '—'}</b>{journey.decision_status === 'paused' && journey.decision_paused_reason && <small className="mt-1 block text-slate-500">{journey.decision_paused_reason}</small>}{canRegisterActivities && <Button size="sm" variant="outline" className="mt-2" onClick={togglePause} data-testid="decision-status-toggle-button">{journey.decision_status === 'paused' ? 'Reanudar' : 'Pausar / Desistir'}</Button>}</article></section>
      <ConsolidationStageRail stages={journey.stages || []} currentStageKey={journey.current_stage_key} />
      <details className="border bg-white p-5" data-testid="journey-step-by-step">
        <summary className="min-h-11 cursor-pointer font-['Spectral'] text-2xl font-semibold">Proceso paso a paso</summary>
        <div className="mt-4"><PersonStepByStep personId={journey.person_id} showEnrollmentLink={false} /></div>
      </details>
      {journey.outreach_origin && (
        <section className="border bg-white p-5" data-testid="journey-outreach-origin">
          <h2 className="font-['Spectral'] text-2xl font-semibold">Procedencia · Invasión</h2>
          <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <p><span className="text-slate-500">Invasión:</span> {journey.outreach_origin.campaign_name || 'Sin invasión'}{journey.outreach_origin.campaign_location ? ` · ${journey.outreach_origin.campaign_location}` : ''}</p>
            <p><span className="text-slate-500">Hogar:</span> {journey.outreach_origin.household_address || 'Sin hogar registrado'}</p>
            <p><span className="text-slate-500">Materiales entregados en el primer contacto:</span> {[journey.outreach_origin.materials_delivered?.mcd && 'MCD', journey.outreach_origin.materials_delivered?.npt && 'NPT'].filter(Boolean).join(', ') || 'Ninguno'}</p>
            <p><span className="text-slate-500">Horario de llamadas acordado:</span> {CALL_SCHEDULE_LABEL[journey.outreach_origin.agreed_call_schedule] || '—'}</p>
          </div>
          {journey.outreach_origin.attempts?.length > 0 && (
            <div className="mt-3" data-testid="journey-outreach-attempts">
              <h3 className="text-sm font-semibold text-slate-700">Historial de intentos del hogar</h3>
              <div className="mt-1 space-y-1">
                {journey.outreach_origin.attempts.map((attempt, index) => (
                  <p key={index} className="text-xs text-slate-500" data-testid={`journey-outreach-attempt-${index}`}>{attempt.occurred_at ? new Date(attempt.occurred_at).toLocaleString('es-US') : '—'} · {ATTEMPT_RESULT_LABEL[attempt.result] || attempt.result || attempt.event_type}{attempt.note ? ` · ${attempt.note}` : ''}</p>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
      <ConsolidationActivityCalendar enrollmentId={enrollmentId} currentStageKey={journey.current_stage_key} canRegister={canRegisterActivities} />
      <div className="grid gap-6 lg:grid-cols-[1.25fr_.75fr]"><section className="space-y-5"><div className="border bg-white p-5"><div className="flex items-center justify-between"><h2 className="font-['Spectral'] text-2xl font-semibold">Historial permanente</h2><Link className="text-sm font-semibold text-amber-700" to={`/personas/${journey.person.person_id}`} data-testid="open-journey-person-profile">Abrir Perfil 360</Link></div><div className="mt-4 space-y-3">{journey.timeline?.map((event) => <article key={event._id || `${event.event_type}-${event.occurred_at}`} className="border-l-2 border-amber-400 pl-3"><b className="text-sm">{event.title}</b><p className="text-xs text-slate-500">{event.detail}</p><time className="text-[10px] text-slate-400">{new Date(event.occurred_at).toLocaleString('es-US')}</time></article>)}</div></div><div className="border bg-white p-5"><h2 className="font-['Spectral'] text-2xl font-semibold">Historial de mentores</h2><div className="mt-4 space-y-3">{journey.mentor_assignments?.map((item) => <article key={item.assignment_id} className="flex justify-between border-b pb-3 text-sm"><span>{item.mentor_person_id}<small className="block text-slate-500">{item.reason}</small></span><b>{item.active ? 'Actual' : 'Transferido'}</b></article>)}</div></div></section><ConsolidationActionPanel journey={journey} assignees={assignees} onUpdated={loadJourney} onTasksChanged={updateCurrentTasks} /></div>
    </>}
    <Dialog open={pauseOpen} onOpenChange={setPauseOpen}>
      <DialogContent data-testid="pause-decision-dialog">
        <DialogHeader><DialogTitle>Pausar o desistir del proceso</DialogTitle></DialogHeader>
        <Textarea value={pauseReason} onChange={(event) => setPauseReason(event.target.value)} placeholder="Motivo (obligatorio)" data-testid="pause-reason-textarea" />
        <DialogFooter>
          <Button variant="outline" onClick={() => setPauseOpen(false)}>Cancelar</Button>
          <Button onClick={confirmPause} disabled={pauseSaving} data-testid="pause-confirm-button">Confirmar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </ProcessShell>;
}