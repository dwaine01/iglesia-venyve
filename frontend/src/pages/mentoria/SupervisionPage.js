import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Loader2, BarChart3, ChevronRight, Home, Users, UserCheck, AlertTriangle, BookOpen, Settings2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { canCreateOutreachCampaign } from '../../lib/accessControl';
import { Button } from '../../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Input } from '../../components/ui/input';

const SEMAPHORE_COLOR = { red: 'bg-rose-500', yellow: 'bg-amber-400', green: 'bg-emerald-500' };
const SEMAPHORE_LABEL = { red: 'Necesita acompañamiento', yellow: 'Vigilar', green: 'Al día' };

const SemaphoreDot = ({ value }) => (
  <span className="inline-flex items-center gap-1.5 text-xs font-medium" data-testid={`semaphore-${value}`}>
    <span className={`h-2.5 w-2.5 rounded-full ${SEMAPHORE_COLOR[value] || 'bg-slate-300'}`} />
    {SEMAPHORE_LABEL[value] || 'Sin datos'}
  </span>
);

const Stat = ({ label, value, onClick, testId }) => (
  <button type="button" disabled={!onClick} onClick={onClick}
    className={`rounded-xl border border-[#E8E5DE] bg-white p-3 text-left ${onClick ? 'cursor-pointer hover:border-[#132443]/40 hover:shadow-sm' : 'cursor-default'}`}
    data-testid={testId}>
    <div className="text-2xl font-semibold text-[#101D36]">{value ?? 0}</div>
    <div className="text-xs text-slate-500">{label}</div>
  </button>
);

const IndicatorDetailDialog = ({ indicatorKey, label, query, onClose }) => {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]); const [total, setTotal] = useState(0); const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!indicatorKey) return;
    setLoading(true);
    axios.get(`${API}/api/supervision/indicators/${indicatorKey}${query}`, getAuthHeaders())
      .then(({ data }) => { setItems(data.items || []); setTotal(data.total || 0); })
      .catch((error) => toast.error(errorDetailText(error, 'No se pudo cargar el detalle')))
      .finally(() => setLoading(false));
  }, [indicatorKey, query, API, getAuthHeaders]);

  return (
    <Dialog open={Boolean(indicatorKey)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="max-h-[80vh] overflow-y-auto bg-white" data-testid="indicator-detail-dialog">
        <DialogHeader><DialogTitle>{label} ({total})</DialogTitle></DialogHeader>
        {loading && <Loader2 className="h-5 w-5 animate-spin text-slate-400" />}
        {!loading && items.length === 0 && <p className="text-sm text-slate-400">Nada que mostrar — buena señal.</p>}
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={item.enrollment_id || item.visit_id || item.mentor_person_id || index} className="rounded-lg border border-[#E8E5DE] p-3 text-sm" data-testid={`indicator-detail-row-${index}`}>
              {item.person_name && <div className="font-medium text-[#101D36]">{item.person_name}</div>}
              {item.mentor_name && <div className="text-slate-500">Mentor: {item.mentor_name}</div>}
              {item.scheduled_date && <div className="text-slate-500">Programada: {item.scheduled_date}</div>}
              {item.decision_status && <div className="text-slate-500">Estado: {item.decision_status}</div>}
              {item.decision_paused_reason && <div className="text-slate-500">Motivo: {item.decision_paused_reason}</div>}
              {item.note !== undefined && <div className="text-slate-500">Nota: {item.note || '—'}</div>}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
};

const ThresholdsPanel = ({ onClose }) => {
  const { API, getAuthHeaders } = useAuth();
  const [thresholds, setThresholds] = useState(null); const [saving, setSaving] = useState('');

  const load = useCallback(() => {
    axios.get(`${API}/api/supervision/thresholds`, getAuthHeaders()).then(({ data }) => setThresholds(data));
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);

  const save = async (key, value) => {
    setSaving(key);
    try {
      const { data } = await axios.put(`${API}/api/supervision/thresholds/${key}`, { value: Number(value) }, getAuthHeaders());
      setThresholds(data); toast.success('Umbral actualizado');
    } catch (error) { toast.error(errorDetailText(error, 'No se pudo actualizar el umbral')); }
    finally { setSaving(''); }
  };

  return (
    <Dialog open onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="max-h-[80vh] overflow-y-auto bg-white" data-testid="supervision-thresholds-dialog">
        <DialogHeader><DialogTitle>Criterios del semáforo</DialogTitle></DialogHeader>
        {!thresholds && <Loader2 className="h-5 w-5 animate-spin text-slate-400" />}
        {thresholds && Object.entries(thresholds).filter(([key]) => key !== 'updated_at' && key !== 'updated_by_user_id' && key !== '_id').map(([key, entry]) => (
          <div key={key} className="space-y-1 rounded-lg border border-[#E8E5DE] p-3" data-testid={`threshold-row-${key}`}>
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm text-[#101D36]">{entry.label}</p>
              {entry.status === 'propuesta' && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-700">Propuesta</span>}
            </div>
            <div className="flex items-center gap-2">
              <Input type="number" step="0.01" defaultValue={entry.value} className="w-32" id={`threshold-input-${key}`} data-testid={`threshold-input-${key}`} />
              <Button size="sm" disabled={saving === key} onClick={() => save(key, document.getElementById(`threshold-input-${key}`).value)} data-testid={`threshold-save-${key}`}>
                {saving === key ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Guardar'}
              </Button>
            </div>
          </div>
        ))}
      </DialogContent>
    </Dialog>
  );
};

export default function SupervisionPage() {
  const { user, API, getAuthHeaders } = useAuth();
  const [scope, setScope] = useState(null);
  const [path, setPath] = useState([]); // [{id,name}] breadcrumb of groups
  const [selectedMentor, setSelectedMentor] = useState(null);
  const [overview, setOverview] = useState(null);
  const [groups, setGroups] = useState([]);
  const [mentors, setMentors] = useState([]);
  const [disciples, setDisciples] = useState([]);
  const [loading, setLoading] = useState(true);
  const [indicator, setIndicator] = useState(null);
  const [showThresholds, setShowThresholds] = useState(false);

  const currentGroupId = path.length ? path[path.length - 1].id : null;
  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (currentGroupId) params.set('front_group_id', currentGroupId);
    if (selectedMentor) params.set('mentor_person_id', selectedMentor.id);
    const str = params.toString();
    return str ? `?${str}` : '';
  }, [currentGroupId, selectedMentor]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [scopeRes, overviewRes] = await Promise.all([
        axios.get(`${API}/api/supervision/scope`, getAuthHeaders()),
        axios.get(`${API}/api/supervision/overview${queryString}`, getAuthHeaders()),
      ]);
      setScope(scopeRes.data);
      setOverview(overviewRes.data);
      if (overviewRes.data.scope_level !== 'self' && !selectedMentor) {
        const groupsRes = await axios.get(`${API}/api/supervision/groups${currentGroupId ? `?parent_group_id=${currentGroupId}` : ''}`, getAuthHeaders());
        setGroups(groupsRes.data.groups || []);
        if (currentGroupId) {
          const mentorsRes = await axios.get(`${API}/api/supervision/mentors?front_group_id=${currentGroupId}`, getAuthHeaders());
          setMentors(mentorsRes.data.mentors || []);
        } else {
          setMentors([]);
        }
      } else {
        setGroups([]); setMentors([]);
      }
      if (overviewRes.data.scope_level === 'self' || selectedMentor) {
        const discRes = await axios.get(`${API}/api/supervision/disciples${queryString}`, getAuthHeaders());
        setDisciples(discRes.data.items || []);
      } else {
        setDisciples([]);
      }
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo cargar la supervisión'));
    } finally { setLoading(false); }
  }, [API, getAuthHeaders, queryString, currentGroupId, selectedMentor]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const enterGroup = (group) => { setSelectedMentor(null); setPath((prev) => [...prev, { id: group.front_group_id, name: group.display_name || group.name }]); };
  const enterMentor = (mentor) => setSelectedMentor({ id: mentor.mentor_person_id, name: mentor.mentor_name });
  const goTo = (index) => { setSelectedMentor(null); setPath((prev) => prev.slice(0, index + 1)); };
  const goRoot = () => { setSelectedMentor(null); setPath([]); };

  if (loading && !overview) return <div className="flex min-h-[40vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-slate-400" /></div>;

  const isSelf = overview?.scope_level === 'self';

  return (
    <div className="space-y-6 p-4 sm:p-6" data-testid="supervision-page">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#132443]/10 text-[#132443]"><BarChart3 className="h-5 w-5" /></div>
          <div>
            <h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36] sm:text-3xl">{isSelf ? 'Mi Progreso' : 'Supervisión de Invasiones'}</h1>
            <p className="text-sm text-slate-500">Iglesia → grupo/líder → mentor → discípulo → etapa → actividad</p>
          </div>
        </div>
        {canCreateOutreachCampaign(user) && (
          <Button variant="outline" size="sm" onClick={() => setShowThresholds(true)} data-testid="supervision-open-thresholds"><Settings2 className="h-4 w-4" />Criterios del semáforo</Button>
        )}
      </header>

      {!isSelf && (
        <div className="flex flex-wrap items-center gap-1 text-sm text-slate-500" data-testid="supervision-breadcrumb">
          <button type="button" onClick={goRoot} className="flex items-center gap-1 font-medium text-[#132443] hover:underline" data-testid="supervision-breadcrumb-root"><Home className="h-3.5 w-3.5" />Iglesia</button>
          {path.map((item, index) => (
            <span key={item.id} className="flex items-center gap-1">
              <ChevronRight className="h-3.5 w-3.5" />
              <button type="button" onClick={() => goTo(index)} className="font-medium text-[#132443] hover:underline" data-testid={`supervision-breadcrumb-${index}`}>{item.name}</button>
            </span>
          ))}
          {selectedMentor && <span className="flex items-center gap-1"><ChevronRight className="h-3.5 w-3.5" /><span className="font-medium text-[#101D36]">{selectedMentor.name}</span></span>}
        </div>
      )}

      {overview && (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-xl border border-[#E8E5DE] bg-[#F6F4EF] p-3" data-testid="supervision-semaphore-banner">
            <SemaphoreDot value={overview.semaphore} />
            <span className="text-xs text-slate-500">Alcance: {overview.scope_level === 'global' ? 'toda la iglesia' : overview.scope_level === 'branch' ? 'mi rama' : 'lo mío'}</span>
          </div>

          <div>
            <h3 className="mb-2 font-['Spectral'] text-lg font-semibold text-[#101D36]">Invasión</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="supervision-invasion-stats">
              <Stat label="Mentores asignados" value={overview.invasion.mentors_assigned} testId="stat-mentors-assigned" />
              <Stat label="Participación confirmada" value={overview.invasion.mentors_confirmed} testId="stat-mentors-confirmed" />
              <Stat label="Con actividad" value={overview.invasion.mentors_with_activity} testId="stat-mentors-active" />
              <Stat label="Hogares visitados" value={overview.invasion.households_visited} testId="stat-households" />
              <Stat label="Visitas" value={overview.invasion.visits_total} testId="stat-visits" />
              <Stat label="Intentos" value={overview.invasion.attempts_total} testId="stat-attempts" />
              <Stat label="Personas únicas contactadas" value={overview.invasion.unique_persons_contacted} testId="stat-unique-persons" />
              <Stat label="Interesadas" value={overview.invasion.interested} testId="stat-interested" />
              <Stat label="Contactos sin seguimiento" value={overview.invasion.contacts_without_followup} onClick={() => setIndicator({ key: 'contacts_without_followup', label: 'Contactos sin seguimiento' })} testId="stat-contacts-without-followup" />
            </div>
          </div>

          <div>
            <h3 className="mb-2 font-['Spectral'] text-lg font-semibold text-[#101D36]">Consolidación</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="supervision-consolidation-stats">
              <Stat label="Aceptaron" value={overview.consolidation.accepted} testId="stat-accepted" />
              <Stat label="Inicio programado" value={overview.consolidation.start_scheduled} testId="stat-start-scheduled" />
              <Stat label="Iniciaron" value={overview.consolidation.started} testId="stat-started" />
              <Stat label="Completaron" value={overview.consolidation.completed} testId="stat-completed" />
              <Stat label="Actividades realizadas" value={overview.consolidation.activities_done} testId="stat-activities-done" />
              <Stat label="Actividades vencidas" value={overview.consolidation.activities_overdue} onClick={() => setIndicator({ key: 'activities_overdue', label: 'Actividades vencidas' })} testId="stat-activities-overdue" />
              <Stat label="Pausados" value={overview.consolidation.paused_total} onClick={() => setIndicator({ key: 'paused', label: 'Procesos pausados' })} testId="stat-paused" />
            </div>
            {overview.consolidation.by_stage.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2" data-testid="supervision-by-stage">
                {overview.consolidation.by_stage.map((row) => (
                  <span key={row.stage_key} className="rounded-full border border-[#E8E5DE] bg-white px-3 py-1 text-xs text-slate-600">{row.stage_name}: <b className="text-[#101D36]">{row.total}</b></span>
                ))}
              </div>
            )}
          </div>

          <div>
            <h3 className="mb-2 flex items-center gap-1.5 font-['Spectral'] text-lg font-semibold text-[#101D36]"><AlertTriangle className="h-4 w-4 text-amber-500" />Debilidades detectadas</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="supervision-weakness-stats">
              <Stat label="Mentores sin actividad" value={overview.weaknesses.mentors_without_activity} onClick={() => setIndicator({ key: 'mentors_without_activity', label: 'Mentores sin actividad' })} testId="stat-weak-mentors" />
              <Stat label="Aceptaron y no iniciaron" value={overview.weaknesses.accepted_not_started} onClick={() => setIndicator({ key: 'accepted_not_started', label: 'Aceptaron y no iniciaron' })} testId="stat-weak-accepted" />
              <Stat label="Discípulos atrasados" value={overview.weaknesses.delayed_disciples} testId="stat-weak-delayed" />
            </div>
          </div>

          <div>
            <h3 className="mb-2 flex items-center gap-1.5 font-['Spectral'] text-lg font-semibold text-[#101D36]"><BookOpen className="h-4 w-4" />Librería</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="supervision-library-stats">
              <Stat label="Disponibles (central)" value={overview.library.global.available} testId="stat-lib-available" />
              <Stat label="En custodia de líderes" value={overview.library.global.with_leaders} testId="stat-lib-custody" />
              <Stat label="Entregados" value={overview.library.global.delivered} testId="stat-lib-delivered" />
              <Stat label="Devueltos" value={overview.library.global.returned} testId="stat-lib-returned" />
            </div>
            {overview.library.mentor_custody.scoped && (
              <p className="mt-2 text-xs text-slate-500" data-testid="supervision-library-custody-scoped">De mi rama: asignados {overview.library.mentor_custody.assigned} · entregados {overview.library.mentor_custody.delivered} · devueltos {overview.library.mentor_custody.returned} · en custodia {overview.library.mentor_custody.in_custody}</p>
            )}
          </div>
        </div>
      )}

      {!isSelf && !selectedMentor && (
        <div>
          <h3 className="mb-2 flex items-center gap-1.5 font-['Spectral'] text-lg font-semibold text-[#101D36]"><Users className="h-4 w-4" />{currentGroupId ? 'Sub-ramas' : 'Grupos Frontales'}</h3>
          <div className="space-y-2" data-testid="supervision-groups-list">
            {groups.map((group) => (
              <button key={group.front_group_id} type="button" onClick={() => enterGroup(group)}
                className="flex w-full items-center justify-between rounded-xl border border-[#E8E5DE] bg-white p-3 text-left hover:border-[#132443]/40 hover:shadow-sm"
                data-testid={`supervision-group-card-${group.front_group_id}`}>
                <div>
                  <p className="font-medium text-[#101D36]">{group.name || 'Equipo sin nombre'}</p>
                  <p className="text-xs text-slate-500">{group.direct_members} directo(s) · {group.total_members} en toda la rama · {group.activities_overdue}/{group.activities_total} vencidas</p>
                </div>
                <div className="flex items-center gap-2">
                  <SemaphoreDot value={group.semaphore} />
                  <ChevronRight className="h-4 w-4 text-slate-400" />
                </div>
              </button>
            ))}
            {groups.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">Sin Grupos Frontales aquí.</p>}
          </div>
        </div>
      )}

      {!isSelf && currentGroupId && !selectedMentor && (
        <div>
          <h3 className="mb-2 flex items-center gap-1.5 font-['Spectral'] text-lg font-semibold text-[#101D36]"><UserCheck className="h-4 w-4" />Integrantes directos</h3>
          <div className="space-y-2" data-testid="supervision-mentors-list">
            {mentors.map((mentor) => (
              <button key={mentor.mentor_person_id} type="button" onClick={() => enterMentor(mentor)}
                className="flex w-full items-center justify-between rounded-xl border border-[#E8E5DE] bg-white p-3 text-left hover:border-[#132443]/40 hover:shadow-sm"
                data-testid={`supervision-mentor-card-${mentor.mentor_person_id}`}>
                <div>
                  <p className="font-medium text-[#101D36]">{mentor.mentor_name}</p>
                  <p className="text-xs text-slate-500">{mentor.visits} visitas · {mentor.disciples} discípulo(s) · {mentor.activities_overdue}/{mentor.activities_total} vencidas</p>
                </div>
                <div className="flex items-center gap-2">
                  <SemaphoreDot value={mentor.semaphore} />
                  <ChevronRight className="h-4 w-4 text-slate-400" />
                </div>
              </button>
            ))}
            {mentors.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">Sin integrantes directos en este grupo.</p>}
          </div>
        </div>
      )}

      {(isSelf || selectedMentor) && (
        <div>
          <h3 className="mb-2 font-['Spectral'] text-lg font-semibold text-[#101D36]">Discípulos</h3>
          <div className="space-y-2" data-testid="supervision-disciples-list">
            {disciples.map((item) => (
              <div key={item.enrollment_id} className="rounded-xl border border-[#E8E5DE] bg-white p-3 text-sm" data-testid={`supervision-disciple-row-${item.enrollment_id}`}>
                <p className="font-medium text-[#101D36]">{item.person_name}</p>
                <p className="text-xs text-slate-500">Etapa: {item.current_stage_key || '—'} · Estado: {item.decision_status || '—'}</p>
              </div>
            ))}
            {disciples.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500">Sin discípulos todavía.</p>}
          </div>
        </div>
      )}

      {indicator && <IndicatorDetailDialog indicatorKey={indicator.key} label={indicator.label} query={queryString} onClose={() => setIndicator(null)} />}
      {showThresholds && <ThresholdsPanel onClose={() => setShowThresholds(false)} />}
    </div>
  );
}
