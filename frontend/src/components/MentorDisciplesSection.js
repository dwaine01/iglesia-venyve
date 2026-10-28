import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, ChevronDown, ChevronUp, Loader2, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import AddDiscipleDialog from './AddDiscipleDialog';
import { errorDetailText } from '../lib/errorText';

const STAGE_SHORT_LABELS = {
  visitor_followup: 'Seguimiento', prayer: 'Oración', invasion: 'Invasión',
  mcd: 'MCD', npt: 'NPT', welcome_party: 'Fiesta de bienvenida',
  lbs_1: 'LBS · Liberación', lbs_2: 'LBS · Bendición', lbs_3: 'LBS · Sanidad',
  retreat: 'Retiro', graduation: 'Graduación', discipleship_handoff: 'Entrega a discipulado',
};


const DiscipleCard = ({ enrollment, canEdit, onChanged, API, getAuthHeaders }) => {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const currentStage = enrollment.stages?.find((stage) => stage.stage_key === enrollment.current_stage_key);

  const toggleTask = async (taskId, completed) => {
    setBusy(true);
    try {
      await axios.put(`${API}/api/processes/enrollments/${enrollment.enrollment_id}/stages/${enrollment.current_stage_key}/tasks/${taskId}`, { completed }, getAuthHeaders());
      if (onChanged) onChanged();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo actualizar el paso'));
    } finally {
      setBusy(false);
    }
  };

  const completeStage = async () => {
    setBusy(true);
    try {
      await axios.put(`${API}/api/processes/enrollments/${enrollment.enrollment_id}/stages/${enrollment.current_stage_key}`, { status: 'completed' }, getAuthHeaders());
      toast.success('Etapa completada');
      if (onChanged) onChanged();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo completar la etapa'));
    } finally {
      setBusy(false);
    }
  };

  const lbsStages = (enrollment.stages || []).filter((stage) => stage.stage_key.startsWith('lbs_'));

  return (
    <div className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid={`disciple-card-${enrollment.enrollment_id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-semibold text-[#101D36]">{enrollment.person?.name || 'Sin nombre'}</p>
          <p className="text-xs text-slate-500">{enrollment.person?.person_number}</p>
        </div>
        <Badge variant="outline" data-testid={`disciple-current-stage-${enrollment.enrollment_id}`}>
          {STAGE_SHORT_LABELS[enrollment.current_stage_key] || enrollment.current_stage_key}
        </Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
        {['mcd', 'npt'].map((key) => {
          const stage = enrollment.stages?.find((item) => item.stage_key === key);
          return <Badge key={key} className={stage?.status === 'completed' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500'}>{STAGE_SHORT_LABELS[key]}{stage?.status === 'completed' ? ' ✓' : ''}</Badge>;
        })}
        {lbsStages.map((stage) => (
          <Badge key={stage.stage_key} className={stage.status === 'completed' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500'}>
            {STAGE_SHORT_LABELS[stage.stage_key]}{stage.status === 'completed' ? ' ✓' : ''}
          </Badge>
        ))}
        <span className="text-slate-400">(LBS: 3 pasos, 21 días en total)</span>
      </div>

      {canEdit && (
        <div className="mt-3">
          <Button size="sm" variant="ghost" onClick={() => setExpanded((prev) => !prev)} data-testid={`disciple-toggle-progress-${enrollment.enrollment_id}`}>
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />} Marcar avance de &quot;{STAGE_SHORT_LABELS[enrollment.current_stage_key] || enrollment.current_stage_key}&quot;
          </Button>
          {expanded && currentStage && (
            <div className="mt-2 space-y-2 rounded-lg border border-slate-200 p-3">
              {(currentStage.tasks || []).map((task) => (
                <label key={task.task_id} className="flex items-center gap-2 text-sm" data-testid={`disciple-task-${task.task_id}`}>
                  <Checkbox checked={Boolean(task.completed)} disabled={busy} onCheckedChange={(value) => toggleTask(task.task_id, Boolean(value))} />
                  {task.label || task.task_id}
                </label>
              ))}
              {(currentStage.tasks || []).length === 0 && <p className="text-xs text-slate-400">Esta etapa no tiene pasos individuales.</p>}
              {enrollment.current_stage_key === 'welcome_party' && (
                <p className="text-xs text-amber-700" data-testid={`disciple-welcome-party-hint-${enrollment.enrollment_id}`}>
                  Para cerrar la Fiesta de bienvenida y avanzar a LBS (Liberación, Bendición y Sanidad · 21 días) se necesita la firma de la Carta de Membresía y que el mentor esté autorizado para LBS. Si falta, pide apoyo a tu líder o coordinador.
                </p>
              )}
              <Button size="sm" disabled={busy || currentStage.status === 'completed'} onClick={completeStage} className="bg-[#132443]" data-testid={`disciple-complete-stage-${enrollment.enrollment_id}`}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />} Completar etapa
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default function MentorDisciplesSection({ personId, isOwnProfile, API, getAuthHeaders }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addOpen, setAddOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get(`${API}/api/processes/consolidation/by-mentor/${personId}`, getAuthHeaders());
      setData(response.data);
    } catch (requestError) {
      setError(errorDetailText(requestError, 'No se pudieron cargar los discípulos.'));
    } finally {
      setLoading(false);
    }
  }, [API, getAuthHeaders, personId]);

  useEffect(() => { load(); }, [load]);

  if (loading && !data) return <Loader2 className="h-5 w-5 animate-spin text-slate-400" data-testid="mentor-disciples-loading" />;
  if (error) return <p className="text-sm text-red-600" data-testid="mentor-disciples-error">{error}</p>;

  return (
    <section className="space-y-3" data-testid="mentor-disciples-section">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-['Spectral'] text-base font-semibold text-[#101D36]">
          {isOwnProfile ? 'Mis discípulos' : `Discípulos de ${data?.mentor_name || 'este mentor'}`}
        </h4>
        {isOwnProfile && (
          <Button size="sm" onClick={() => setAddOpen(true)} className="bg-[#132443]" data-testid="add-disciple-open-button">
            <UserPlus className="h-4 w-4" /> Agregar discípulo
          </Button>
        )}
      </div>
      {(data?.items || []).length === 0 && <p className="text-sm text-slate-400" data-testid="mentor-disciples-empty">Todavía no hay discípulos registrados.</p>}
      <div className="space-y-3">
        {(data?.items || []).map((enrollment) => (
          <DiscipleCard key={enrollment.enrollment_id} enrollment={enrollment} canEdit={isOwnProfile} onChanged={load} API={API} getAuthHeaders={getAuthHeaders} />
        ))}
      </div>
      {isOwnProfile && (
        <AddDiscipleDialog open={addOpen} onOpenChange={setAddOpen} mentorPersonId={personId} API={API} getAuthHeaders={getAuthHeaders} onCreated={load} />
      )}
    </section>
  );
}
