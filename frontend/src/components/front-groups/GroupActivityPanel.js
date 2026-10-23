import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { ArrowLeft, Calculator, ChevronRight, Loader2, X } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { canViewDirectory } from '../../lib/accessControl';
import { PeriodSelector, periodParams } from './PeriodSelector';
import { Semaphore, SERIES, STATUS } from './GroupStatsPanel';

// Niveles de avance hacia las metas (verde/ámbar/rojo apagados, siempre con texto).
const LEVELS = {
  A: { status: 'green', label: 'Cumple' },
  B: { status: 'yellow', label: 'En camino' },
  C: { status: 'red', label: 'Se queda atrás' },
};
const NO_DATA = '#94a3b8';
const TYPE_LABEL = { pair: 'Equipo', individual: 'Integrante individual', leadership: 'Liderazgo del grupo' };
const PROCESS_LABELS = { consolidation: 'Consolidación', seven_weeks: 'Ley de las 7 Semanas', discipleship: 'Discipulado', mentorship: 'Mentoría', cap: 'CAP', outreach_invasion: 'Invasión' };
const GOAL_LABELS = {
  goal_attendance_ratio: 'Meta de asistencia', goal_activity_ratio: 'Meta de participación en actividades', goal_outreach_ratio: 'Meta de impacto en invasiones',
  goal_persons_reached_per_member_week: 'Meta de personas alcanzadas por integrante por semana', goal_progress_green: 'Avance mínimo para A (cumple)', goal_progress_yellow: 'Avance mínimo para B (en camino)',
};
const pct = (value) => `${Math.round((value || 0) * 100)}%`;
const plural = (count, one, many) => `${count ?? 0} ${count === 1 ? one : many}`;
const teamName = (team) => `${team.type === 'leadership' ? 'Liderazgo: ' : ''}${team.members.map((member) => member.name.split(' ')[0]).join(' y ')}`;

function levelOf(progress, criteria) {
  if (progress === null || progress === undefined) return null;
  if (progress >= criteria.goals.goal_progress_green.value) return 'A';
  if (progress >= criteria.goals.goal_progress_yellow.value) return 'B';
  return 'C';
}
const levelColor = (level) => (level ? STATUS[LEVELS[level].status].color : NO_DATA);
const formatValue = (indicator) => (indicator.unit === 'ratio' ? pct(indicator.value) : `${indicator.value} por integrante`);
const formatGoal = (indicator) => (indicator.goal === null || indicator.goal === undefined ? 'sin meta en este período' : indicator.unit === 'ratio' ? pct(indicator.goal) : `${indicator.goal}`);

function LevelBadge({ level, large = false }) {
  if (!level) return <span className={`inline-flex items-center rounded-full border border-slate-300 bg-white font-semibold text-slate-500 ${large ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'}`} data-testid="level-none">Sin datos</span>;
  const status = STATUS[LEVELS[level].status];
  const Icon = status.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border bg-white font-bold text-[#101D36] ${large ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'}`} style={{ borderColor: status.color }} data-testid={`level-${level}`}>
      <Icon className={large ? 'h-4 w-4' : 'h-3.5 w-3.5'} style={{ color: status.color }} aria-hidden="true" />{level} · {LEVELS[level].label}
    </span>
  );
}

// Barra "lleva X frente a la meta Y": relleno = valor real, línea = meta.
function GoalBullet({ indicator, criteria, onSelect, compact = false }) {
  const level = levelOf(indicator.progress, criteria);
  const scaleMax = indicator.unit === 'ratio' ? 1 : Math.max(indicator.goal || 0, indicator.value || 0, 0.0001) * 1.15;
  const fill = indicator.has_data ? Math.min((indicator.value || 0) / scaleMax, 1) * 100 : 0;
  const goalAt = indicator.goal ? Math.min(indicator.goal / scaleMax, 1) * 100 : null;
  const tip = indicator.has_data ? `${indicator.label}: lleva ${formatValue(indicator)} · meta ${formatGoal(indicator)} · ${indicator.explanation}` : `${indicator.label}: sin datos registrados en el período`;
  const Tag = onSelect ? 'button' : 'div';
  return (
    <Tag type={onSelect ? 'button' : undefined} onClick={onSelect ? () => onSelect(indicator) : undefined} title={tip} aria-label={tip} className={`block w-full text-left ${onSelect ? 'rounded-lg p-1.5 hover:bg-slate-50' : ''}`} data-testid={`goal-${indicator.key}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-2">
        <span className={`font-medium text-slate-700 ${compact ? 'text-[0.72rem]' : 'text-sm'}`}>{indicator.label}</span>
        {indicator.has_data
          ? <span className={`text-right ${compact ? 'text-[0.72rem]' : 'text-sm'}`}><b className="text-[#101D36]">{formatValue(indicator)}</b><span className="text-slate-500"> / meta {formatGoal(indicator)}</span></span>
          : <span className={`shrink-0 font-semibold text-slate-500 ${compact ? 'text-[0.72rem]' : 'text-sm'}`} data-testid={`goal-${indicator.key}-sin-datos`}>Sin datos</span>}
      </div>
      <div className={`relative mt-1 w-full overflow-visible rounded-full ${indicator.has_data ? 'bg-slate-100' : 'border border-dashed border-slate-300 bg-white'} ${compact ? 'h-2' : 'h-3'}`}>
        {indicator.has_data && <div className="h-full rounded-full" style={{ width: `${Math.max(fill, fill > 0 ? 2 : 0)}%`, backgroundColor: levelColor(level) }} />}
        {goalAt !== null && <div className="absolute -top-1 bottom-[-4px] w-0.5 rounded bg-[#101D36]" style={{ left: `calc(${goalAt}% - 1px)` }} aria-hidden="true" />}
      </div>
      {!compact && indicator.has_data && <p className="mt-1 text-[0.72rem] text-slate-500">{indicator.progress === null ? 'Sin meta para este período' : `${pct(indicator.progress)} de la meta`}</p>}
    </Tag>
  );
}

const MiniStat = ({ label, value }) => <div className="rounded-md bg-[#FBFAF7] px-1.5 py-1.5 text-center"><div className="text-base font-semibold text-[#101D36]">{value ?? 0}</div><div className="text-[0.72rem] leading-tight text-slate-500">{label}</div></div>;
const Card = ({ title, subtitle, children, testId, className = '' }) => (
  <section className={`min-w-0 rounded-xl border border-[#E8E5DE] bg-white p-3 shadow-sm sm:p-4 ${className}`} data-testid={testId}>
    {title && <h3 className="text-base font-semibold text-[#101D36]">{title}</h3>}
    {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
    <div className={title || subtitle ? 'mt-3' : ''}>{children}</div>
  </section>
);

function Sheet({ title, subtitle, onClose, children, testId }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-6" role="dialog" aria-modal="true" data-testid={testId}>
      <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-t-2xl bg-[#F8F6F0] sm:rounded-2xl">
        <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[#E8E5DE] bg-white px-3 py-2">
          <button type="button" onClick={onClose} className="grid h-11 w-11 shrink-0 place-items-center rounded-md hover:bg-slate-100" aria-label="Atrás"><ArrowLeft className="h-5 w-5" /></button>
          <div className="min-w-0 flex-1"><p className="truncate font-['Spectral'] text-lg font-semibold text-[#101D36]">{title}</p>{subtitle && <p className="truncate text-xs text-slate-500">{subtitle}</p>}</div>
          <button type="button" onClick={onClose} className="grid h-11 w-11 shrink-0 place-items-center rounded-md hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>
        <div className="space-y-3 p-3 sm:p-4">{children}</div>
      </div>
    </div>
  );
}

function NoData({ items }) {
  return (
    <div className="space-y-1 rounded-xl border border-dashed border-slate-300 bg-white p-3" data-testid="panel-sin-datos">
      {items.map((item) => <p key={item.key} className="text-xs text-slate-600"><b>{item.label}: sin datos.</b> {item.reason}</p>)}
    </div>
  );
}

function GoalsEditor({ goals, onSaved }) {
  const { API, getAuthHeaders } = useAuth();
  const [saving, setSaving] = useState('');
  const save = async (key, raw, isRatio) => {
    const value = isRatio ? Number(raw) / 100 : Number(raw);
    if (Number.isNaN(value) || value < 0 || (isRatio && value > 1)) { toast.error(isRatio ? 'Escribe un porcentaje entre 0 y 100' : 'Escribe un número válido'); return; }
    setSaving(key);
    try { await axios.put(`${API}/api/supervision/thresholds/${key}`, { value }, getAuthHeaders()); toast.success('Meta guardada (confirmada)'); await onSaved(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar la meta')); } finally { setSaving(''); }
  };
  return (
    <section className="space-y-2 rounded-xl bg-white p-3" data-testid="goals-editor">
      <p className="text-sm font-semibold text-[#101D36]">Editar metas</p>
      {Object.entries(goals).map(([key, entry]) => {
        const isRatio = key !== 'goal_persons_reached_per_member_week';
        return (
          <form key={key} className="flex flex-wrap items-center gap-2 text-xs" onSubmit={(event) => { event.preventDefault(); save(key, event.currentTarget.elements.value.value, isRatio); }}>
            <label htmlFor={`goal-${key}`} className="min-w-0 flex-1 text-slate-700">{GOAL_LABELS[key] || key} <span className="text-slate-400">({entry.status})</span></label>
            <input id={`goal-${key}`} name="value" type="number" step={isRatio ? 1 : 0.1} min="0" max={isRatio ? 100 : undefined} defaultValue={isRatio ? Math.round(entry.value * 100) : entry.value} className="h-10 w-20 rounded-md border border-[#E8E5DE] px-2 text-sm" data-testid={`goal-input-${key}`} />
            <span className="w-4 text-slate-500">{isRatio ? '%' : ''}</span>
            <button type="submit" disabled={saving === key} className="h-10 rounded-md bg-[#101D36] px-3 font-semibold text-white disabled:opacity-50">{saving === key ? '…' : 'Guardar'}</button>
          </form>
        );
      })}
    </section>
  );
}

function HowCalculated({ data, onClose, onGoalsSaved }) {
  const { criteria } = data;
  const goals = criteria.goals;
  return (
    <Sheet title="Cómo se calcula" subtitle={`Período evaluado: ${data.period.label}`} onClose={onClose} testId="como-se-calcula">
      <section className="space-y-2 rounded-xl bg-white p-3 text-sm text-slate-700">
        <p className="font-semibold text-[#101D36]">Avance hacia las metas</p>
        <p>{criteria.overall_formula}</p>
        <p className="font-semibold text-[#101D36]">Niveles</p>
        <p className="flex flex-wrap items-center gap-2"><LevelBadge level="A" /> avance ≥ {pct(goals.goal_progress_green.value)}</p>
        <p className="flex flex-wrap items-center gap-2"><LevelBadge level="B" /> avance ≥ {pct(goals.goal_progress_yellow.value)}</p>
        <p className="flex flex-wrap items-center gap-2"><LevelBadge level="C" /> avance menor que {pct(goals.goal_progress_yellow.value)}</p>
        <p className="flex flex-wrap items-center gap-2"><LevelBadge level={null} /> {criteria.classes['—']}</p>
      </section>
      <section className="space-y-2 rounded-xl bg-white p-3 text-sm text-slate-700" data-testid="como-indicadores">
        <p className="font-semibold text-[#101D36]">Cada indicador frente a su meta</p>
        {data.group.goals.map((indicator) => <p key={indicator.key}><b>{indicator.label}</b> — meta {formatGoal(indicator)} <span className="text-slate-400">({indicator.goal_status})</span>. {indicator.has_data ? indicator.explanation : 'Sin registros en este período.'}</p>)}
        <p>{criteria.attendance}</p>
        <p>{criteria.activities}</p>
        <p>{criteria.outreach}</p>
        <p>{criteria.invasion_dates}</p>
        <p>{criteria.rank} {criteria.score}.</p>
        <p>{criteria.member}</p>
        <p className="text-slate-500">{criteria.editable}</p>
      </section>
      {data.can_edit_goals && <GoalsEditor goals={goals} onSaved={onGoalsSaved} />}
      <NoData items={data.unavailable} />
    </Sheet>
  );
}

function MemberActivity({ member, period, campaignId, criteria, onClose }) {
  const { API, getAuthHeaders, user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    axios.get(`${API}/api/front-group-structure/people/${member.person_id}/activity`, { ...getAuthHeaders(), params: periodParams(period, campaignId) })
      .then((response) => setData(response.data))
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar la actividad')));
  }, [API, getAuthHeaders, member.person_id, period, campaignId]);
  const block = (title, stats) => stats && (
    <section className="rounded-xl bg-white p-3"><p className="text-xs font-semibold uppercase text-slate-500">{title}</p>
      <div className="mt-2 grid grid-cols-3 gap-1.5"><MiniStat label="Hogares" value={stats.invasion?.households_visited} /><MiniStat label="Intentos" value={stats.invasion?.attempts_total} /><MiniStat label="Alcanzadas" value={stats.invasion?.unique_persons_contacted} /><MiniStat label="Aceptaron" value={stats.consolidation?.accepted} /><MiniStat label="Act. realizadas" value={stats.consolidation?.activities_done} /><MiniStat label="Act. vencidas" value={stats.consolidation?.activities_overdue} /></div>
    </section>
  );
  return (
    <Sheet title={member.name} subtitle={member.functions.join(' · ') || 'Integrante'} onClose={onClose} testId="member-activity-sheet">
      {member.goals && <Card title="Frente a las metas" subtitle={`Período: ${data?.period.label || ''}`} testId="member-goals"><div className="space-y-2">{member.goals.indicators.map((indicator) => <GoalBullet key={indicator.key} indicator={indicator} criteria={criteria} compact />)}</div></Card>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!data && !error && <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-[#9A7A2F]" /></div>}
      {data && <>
        <section className="rounded-xl bg-white p-3" data-testid="member-in-period">
          <div className="flex items-center justify-between"><p className="text-xs font-semibold uppercase text-slate-500">En el período · {data.period.label}</p><Semaphore value={data.in_period.semaphore} /></div>
          <div className="mt-2 grid grid-cols-3 gap-1.5"><MiniStat label="Avance" value={data.in_period.score} /><MiniStat label="Intentos" value={data.in_period.attempts} /><MiniStat label="Alcanzadas" value={data.in_period.persons_reached} /><MiniStat label="Hogares" value={data.in_period.households} /><MiniStat label="Asistencias" value={data.in_period.attendance} /><MiniStat label="Apoyo (turnos)" value={data.in_period.support_shifts} /></div>
        </section>
        <section className="rounded-xl bg-white p-3"><p className="text-xs font-semibold uppercase text-slate-500">Como persona</p>
          {data.as_person.processes.length ? <ul className="mt-1 space-y-1 text-sm">{data.as_person.processes.map((item, index) => <li key={`${item.process_key}-${index}`}>{PROCESS_LABELS[item.process_key] || item.process_key} · {item.status}{item.current_stage_name ? ` · ${item.current_stage_name}` : ''}</li>)}</ul> : <p className="mt-1 text-sm text-slate-400">Sin procesos registrados.</p>}
          {data.as_person.groups.length > 0 && <p className="mt-1 text-xs text-slate-500">Grupos: {data.as_person.groups.map((item) => item.name).join(', ')}</p>}
        </section>
        {data.is_mentor ? block('Como mentor (historial)', data.as_mentor) : <p className="rounded-xl bg-white p-3 text-sm text-slate-400">No tiene insignia de Mentor activa.</p>}
        {data.as_leader ? block(`Como líder (${data.as_leader.led_group_count} grupo/s y su rama)`, data.as_leader) : <p className="rounded-xl bg-white p-3 text-sm text-slate-400">Aún no lidera un grupo.</p>}
        {canViewDirectory(user) && <Link to={data.person.profile_path} className="flex min-h-11 items-center justify-center rounded-md border border-[#D9CFB4] bg-white text-sm font-semibold text-[#7A5F22]">Abrir Persona 360</Link>}
      </>}
    </Sheet>
  );
}

// Rankings de miembros: cada categoría usa un dato registrado (nunca estimado).
const RANKINGS = [
  { key: 'score', label: 'Más aventajado', value: (m) => m.metrics.score, unit: 'de avance' },
  { key: 'work', label: 'Trabaja más', value: (m) => m.metrics.attempts + m.metrics.activities_done, unit: 'intentos + actividades' },
  { key: 'reached', label: 'Alcanza más personas', value: (m) => m.metrics.persons_reached, unit: 'personas alcanzadas' },
  { key: 'visits', label: 'Visita más', value: (m) => m.metrics.attempts, unit: 'intentos de visita' },
  { key: 'support', label: 'Apoya más', value: (m) => m.metrics.support_shifts, unit: 'turnos de servicio' },
  { key: 'brought', label: 'Trajo más personas', value: null },
];

function MemberRanking({ members, onOpenMember, testId }) {
  const [category, setCategory] = useState('score');
  const ranking = RANKINGS.find((item) => item.key === category);
  const rows = ranking.value ? [...members].sort((a, b) => ranking.value(b) - ranking.value(a) || a.name.localeCompare(b.name)) : [];
  const best = rows.length ? ranking.value(rows[0]) : 0;
  return (
    <Card title="Ranking de miembros" subtitle="Toca un miembro para ver su actividad" testId={testId}>
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Categoría del ranking">
        {RANKINGS.map((item) => <button key={item.key} type="button" role="tab" aria-selected={category === item.key} onClick={() => setCategory(item.key)} className={`min-h-10 rounded-full border px-3 text-xs font-semibold ${category === item.key ? 'border-[#101D36] bg-[#101D36] text-white' : 'border-[#E8E5DE] bg-white text-slate-600'}`} data-testid={`ranking-cat-${item.key}`}>{item.label}</button>)}
      </div>
      {!ranking.value ? <div className="mt-2"><NoData items={[{ key: 'brought', label: 'Personas traídas a la iglesia', reason: 'No hay un registro que vincule a la persona que llegó con el integrante que la invitó.' }]} /></div> : (
        <ol className="mt-2 divide-y divide-[#EEECE6]">
          {rows.slice(0, 15).map((member, index) => {
            const value = ranking.value(member);
            const top = best > 0 && value === best;
            return (
              <li key={member.person_id}>
                <button type="button" onClick={() => onOpenMember(member)} className={`flex min-h-14 w-full items-center gap-3 rounded-md px-1 py-2 text-left hover:bg-slate-50 ${top ? 'bg-[#eef5f0]' : ''}`} data-testid={`member-rank-${member.person_id}`}>
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#101D36] text-xs font-bold text-white">{index + 1}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-[#101D36]">{member.name}</p>
                    {member.functions.length > 0 && <p className="truncate text-xs text-[#7A5F22]">{member.functions.join(' · ')}</p>}
                    {top && <p className="text-xs font-semibold text-[#2f6e47]" data-testid="member-rank-top">Primero en «{ranking.label}»</p>}
                    {!top && member.semaphore === 'red' && <p className="text-xs font-semibold text-[#9a3b31]">Necesita seguimiento</p>}
                  </div>
                  <div className="shrink-0 text-right"><div className="text-lg font-semibold text-[#101D36]">{value}</div><div className="max-w-[96px] text-[0.72rem] leading-tight text-slate-400">{ranking.unit}</div></div>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}

function TeamDetail({ team, data, period, campaignId, onClose, onOpenGroup }) {
  const [member, setMember] = useState(null);
  const summary = team.summary;
  const criteria = data.criteria;
  const measured = data.teams.map((item) => item.summary.overall_progress).filter((value) => value !== null && value !== undefined);
  const best = measured.length ? Math.max(...measured) : null;
  const participating = team.members.filter((item) => item.active);
  const needSupport = team.members.filter((item) => item.semaphore === 'red');
  const comparison = [['Este equipo', summary.overall_progress], ['Todo el grupo', data.group.overall_progress], ['Equipo con más avance', best]];
  return (
    <Sheet title={teamName(team)} subtitle={`${TYPE_LABEL[team.type]} · ${data.period.label}`} onClose={onClose} testId="team-detail">
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Card testId="team-detail-summary">
          <div className="flex items-center justify-between gap-2"><LevelBadge level={summary.class} large /><span className="text-xs text-slate-500">Puesto {summary.rank} de {data.teams.length} equipos</span></div>
          <p className="mt-3 text-4xl font-bold text-[#101D36]">{summary.overall_progress === null ? 'Sin datos' : pct(summary.overall_progress)}<span className="ml-1 text-sm font-normal text-slate-500">{summary.overall_progress === null ? '' : 'de las metas'}</span></p>
          <div className="mt-3 space-y-1.5 text-xs text-slate-600" data-testid="team-comparison">
            <p className="font-semibold text-[#101D36]">Comparación con los demás equipos del grupo</p>
            {comparison.map(([label, value]) => (
              <div key={label} className="flex items-center gap-2"><span className="w-36 shrink-0">{label}</span><div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full" style={{ width: `${value ? value * 100 : 0}%`, backgroundColor: levelColor(levelOf(value, criteria)) }} /></div><span className="w-16 text-right font-semibold text-[#101D36]">{value === null || value === undefined ? 'sin datos' : pct(value)}</span></div>
            ))}
          </div>
        </Card>
        <Card title="Indicadores frente a la meta" subtitle={`Período: ${data.period.label}`} testId="team-goals">
          <div className="space-y-2">{team.goals.map((indicator) => <GoalBullet key={indicator.key} indicator={indicator} criteria={criteria} />)}</div>
        </Card>
      </div>
      <Card title="Actividad registrada del equipo">
        <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-5">
          <MiniStat label="Visitas (intentos)" value={summary.attempts} /><MiniStat label="Sin respuesta" value={summary.attempts_by_result?.no_answer} /><MiniStat label="Personas alcanzadas" value={summary.persons_reached} />
          <MiniStat label="Hogares" value={summary.households} /><MiniStat label="Quieren seguimiento" value={summary.followups} /><MiniStat label="Aceptaron consolidación" value={summary.accepted} />
          <MiniStat label="Asistencias" value={summary.attendance} /><MiniStat label="Apoyo (turnos)" value={summary.support_shifts} /><MiniStat label="Act. realizadas" value={summary.activities_done} /><MiniStat label="Act. vencidas" value={summary.activities_overdue} />
        </div>
      </Card>
      <Card title="Integrantes y funciones" subtitle="Toca un integrante para ver su actividad individual" testId="team-members">
        <ul className="grid gap-2 lg:grid-cols-2">
          {team.members.map((item) => (
            <li key={item.person_id} className="rounded-lg border border-[#EEECE6] p-3">
              <div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-semibold text-[#101D36]">{item.name}</p><p className="text-xs text-[#7A5F22]">{item.functions.join(' · ') || 'Integrante'}</p></div><Semaphore value={item.semaphore} /></div>
              <div className="mt-2 space-y-1.5">{item.goals.indicators.slice(0, 3).map((indicator) => <GoalBullet key={indicator.key} indicator={indicator} criteria={criteria} compact />)}</div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <button type="button" onClick={() => setMember(item)} className="min-h-11 rounded-md bg-[#101D36] text-sm font-semibold text-white" data-testid={`team-member-activity-${item.person_id}`}>Ver su actividad</button>
                {item.led_group ? <button type="button" onClick={() => onOpenGroup?.(item.led_group.front_group_id)} className="min-h-11 rounded-md border border-[#D9CFB4] text-sm font-semibold text-[#7A5F22]" data-testid={`team-member-group-${item.person_id}`}>Ver su grupo →</button> : <span />}
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-slate-600"><b>Participan más:</b> {participating.length ? [...participating].sort((a, b) => b.metrics.score - a.metrics.score).map((item) => item.name).join(', ') : 'nadie con actividad en el período'}.</p>
        <p className="text-sm text-slate-600"><b>Necesitan seguimiento:</b> {needSupport.length ? needSupport.map((item) => item.name).join(', ') : 'nadie'}.</p>
      </Card>
      <NoData items={data.unavailable} />
      {member && <MemberActivity member={member} period={period} campaignId={campaignId} criteria={criteria} onClose={() => setMember(null)} />}
    </Sheet>
  );
}

function IndicatorSheet({ indicatorKey, data, onClose, onOpenTeam }) {
  const groupIndicator = data.group.goals.find((item) => item.key === indicatorKey);
  const rows = data.teams.map((team) => ({ team, indicator: team.goals.find((item) => item.key === indicatorKey) }))
    .sort((a, b) => (b.indicator.has_data - a.indicator.has_data) || ((b.indicator.progress ?? -1) - (a.indicator.progress ?? -1)));
  return (
    <Sheet title={groupIndicator.label} subtitle={`Meta ${formatGoal(groupIndicator)} · ${data.period.label}`} onClose={onClose} testId="indicator-sheet">
      <Card><GoalBullet indicator={groupIndicator} criteria={data.criteria} /><p className="mt-2 text-xs text-slate-500">{groupIndicator.has_data ? groupIndicator.explanation : 'Sin registros en este período.'}</p></Card>
      <Card title="Por equipo" subtitle="Toca un equipo para ver su detalle">
        <div className="space-y-1">{rows.map(({ team, indicator }) => (
          <button key={team.team_id} type="button" onClick={() => onOpenTeam(team.team_id)} className="block w-full rounded-lg p-2 text-left hover:bg-slate-50" data-testid={`indicator-team-${team.team_id}`}>
            <p className="text-sm font-semibold text-[#101D36]">{teamName(team)}</p>
            <GoalBullet indicator={indicator} criteria={data.criteria} compact />
          </button>
        ))}</div>
      </Card>
    </Sheet>
  );
}

function OverviewCard({ data, onSelectIndicator, onShowHow }) {
  const { group, criteria } = data;
  const level = group.class;
  const meets = group.goals.filter((item) => item.progress !== null && item.progress >= 1);
  const behind = group.goals.filter((item) => item.progress !== null && item.progress < criteria.goals.goal_progress_yellow.value);
  return (
    <Card testId="panel-resumen" className="lg:col-span-1">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><h3 className="text-base font-semibold text-[#101D36]">Resumen general del grupo</h3><p className="text-xs text-slate-500" data-testid="panel-periodo">Período evaluado: {data.period.label}</p></div>
        <LevelBadge level={level} large />
      </div>
      <div className="mt-3 flex items-end gap-3">
        <p className="text-5xl font-bold leading-none text-[#101D36]" data-testid="panel-avance-global">{group.overall_progress === null ? 'Sin datos' : pct(group.overall_progress)}</p>
        {group.overall_progress !== null && <p className="pb-1 text-sm text-slate-500">de avance hacia las metas</p>}
      </div>
      <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full" style={{ width: `${(group.overall_progress || 0) * 100}%`, backgroundColor: levelColor(level) }} /></div>
      <p className="mt-1 text-xs text-slate-500">{group.people} personas en {group.teams} equipos · toca un indicador para ver cada equipo</p>
      <div className="mt-3 space-y-1">{group.goals.map((indicator) => <GoalBullet key={indicator.key} indicator={indicator} criteria={criteria} onSelect={(item) => onSelectIndicator(item.key)} />)}</div>
      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <p className="rounded-lg bg-[#eef5f0] p-2 text-[#2f6e47]" data-testid="panel-cumple"><b>Cumple la meta:</b> {meets.length ? meets.map((item) => item.label).join(', ') : 'ningún indicador todavía'}</p>
        <p className="rounded-lg bg-[#f8ecea] p-2 text-[#8f382f]" data-testid="panel-atras"><b>Se queda atrás:</b> {behind.length ? behind.map((item) => item.label).join(', ') : 'ningún indicador'}</p>
      </div>
      <button type="button" onClick={onShowHow} className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-[#D9CFB4] bg-[#FBF6EA] text-sm font-semibold text-[#7A5F22]" data-testid="panel-como-se-calcula"><Calculator className="h-4 w-4" />Cómo se calcula{data.can_edit_goals ? ' · editar metas' : ''}</button>
    </Card>
  );
}

function TeamsChart({ data, onOpenTeam }) {
  const rows = [...data.teams].sort((a, b) => (b.summary.overall_progress ?? -1) - (a.summary.overall_progress ?? -1)).map((team) => ({
    team_id: team.team_id, name: teamName(team), value: team.summary.overall_progress === null ? 0 : Math.round(team.summary.overall_progress * 100),
    level: team.summary.class, label: team.summary.overall_progress === null ? 'Sin datos' : `${Math.round(team.summary.overall_progress * 100)}% · ${team.summary.class}`,
  }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(140, rows.length * 38)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 2, right: 72, bottom: 2, left: 4 }}>
        <CartesianGrid horizontal={false} stroke="#F1F5F9" />
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis type="category" dataKey="name" width={124} tick={{ fontSize: 12, fill: '#334155' }} tickLine={false} axisLine={false} />
        <Tooltip cursor={{ fill: 'rgba(16, 29, 54, 0.05)' }} formatter={(value, _name, item) => [item.payload.label, 'Avance hacia las metas']} />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20} background={{ fill: '#F1F5F9', radius: 4 }} cursor="pointer" onClick={(entry) => onOpenTeam(entry.team_id ?? entry.payload?.team_id)}>
          {rows.map((row) => <Cell key={row.team_id} fill={levelColor(row.level)} />)}
          <LabelList dataKey="label" position="right" style={{ fontSize: 12, fill: '#334155', fontWeight: 600 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function OutreachChart({ data, onOpenTeam }) {
  const rows = data.teams.filter((team) => team.goals.find((item) => item.key === 'outreach')?.has_data).map((team) => ({ team_id: team.team_id, name: teamName(team), attempts: team.summary.attempts, persons_reached: team.summary.persons_reached }));
  if (!rows.length) return <p className="py-6 text-center text-sm font-semibold text-slate-500" data-testid="outreach-sin-datos">Sin datos de invasiones en este período.</p>;
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 44)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 2, right: 24, bottom: 2, left: 4 }} barGap={2}>
        <CartesianGrid horizontal={false} stroke="#F1F5F9" />
        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: '#475569' }} tickLine={false} axisLine={{ stroke: '#E2E8F0' }} />
        <YAxis type="category" dataKey="name" width={124} tick={{ fontSize: 12, fill: '#334155' }} tickLine={false} axisLine={false} />
        <Tooltip cursor={{ fill: 'rgba(16, 29, 54, 0.05)' }} />
        <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" formatter={(value) => <span style={{ color: '#475569' }}>{value}</span>} />
        <Bar dataKey="attempts" name="Intentos de visita" fill={SERIES.blue} radius={[0, 4, 4, 0]} barSize={12} cursor="pointer" onClick={(entry) => onOpenTeam(entry.team_id ?? entry.payload?.team_id)} />
        <Bar dataKey="persons_reached" name="Personas alcanzadas" fill={SERIES.orange} radius={[0, 4, 4, 0]} barSize={12} cursor="pointer" onClick={(entry) => onOpenTeam(entry.team_id ?? entry.payload?.team_id)} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ETAPA 5C: panel dinámico de "Mi Grupo Frontal" — adaptable (cuadrícula en
// computadora, una columna en celular), con metas configurables, valores reales
// registrados y "sin datos" cuando no hay registros.
export function GroupActivityPanel({ groupId, onOpenGroup }) {
  const { API, getAuthHeaders } = useAuth();
  const [period, setPeriod] = useState('month');
  const [campaignId, setCampaignId] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [teamId, setTeamId] = useState(null);
  const [indicatorKey, setIndicatorKey] = useState(null);
  const [showHow, setShowHow] = useState(false);
  const [member, setMember] = useState(null);

  const load = useCallback(async () => {
    setError('');
    try {
      const response = await axios.get(`${API}/api/front-group-structure/groups/${groupId}/panel`, { ...getAuthHeaders(), params: periodParams(period, campaignId) });
      setData(response.data);
    } catch (requestError) { setError(apiErrorMessage(requestError, 'No se pudo cargar el panel.')); }
  }, [API, getAuthHeaders, groupId, period, campaignId]);
  useEffect(() => { setData(null); load(); }, [load]);

  const allMembers = useMemo(() => {
    const seen = new Map();
    (data?.teams || []).forEach((team) => team.members.forEach((item) => { if (!seen.has(item.person_id)) seen.set(item.person_id, item); }));
    return [...seen.values()];
  }, [data]);
  const team = data?.teams.find((item) => item.team_id === teamId);
  const openTeam = (id) => { setIndicatorKey(null); setTeamId(id); };

  return (
    <section className="space-y-3" data-testid="group-activity-panel">
      <div className="lg:max-w-xl"><PeriodSelector period={period} campaignId={campaignId} onChange={(nextPeriod, nextCampaign) => { setPeriod(nextPeriod); setCampaignId(nextCampaign || ''); }} /></div>
      {error && <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {!data && !error && <div className="flex justify-center py-12"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>}
      {data && <>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <OverviewCard data={data} onSelectIndicator={setIndicatorKey} onShowHow={() => setShowHow(true)} />
          {data.teams.length > 0 && <Card title="Comparación de equipos" subtitle="Avance de cada equipo hacia las metas · toca una barra para ver el equipo" testId="panel-grafica-equipos"><TeamsChart data={data} onOpenTeam={openTeam} /></Card>}
        </div>

        <h3 className="pt-1 text-base font-semibold text-[#101D36]">Equipos de servicio ({data.teams.length})</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 [&>*]:min-w-0" data-testid="panel-equipos">
          {data.teams.map((item) => {
            const level = item.summary.class;
            return (
              <button key={item.team_id} type="button" onClick={() => openTeam(item.team_id)} className="flex w-full flex-col rounded-2xl border-2 bg-white p-4 text-left shadow-sm transition hover:shadow-md" style={{ borderColor: `${levelColor(level)}66` }} data-testid={`team-card-${item.team_id}`}>
                <div className="flex items-start justify-between gap-2">
                  <span className="rounded bg-[#F3EBD7] px-1.5 py-0.5 text-[0.72rem] font-semibold uppercase text-[#7A5F22]">{TYPE_LABEL[item.type]}</span>
                  <LevelBadge level={level} />
                </div>
                <div className="mt-2 space-y-0.5">{item.members.map((person) => <p key={person.person_id} className="truncate text-base font-semibold text-[#101D36]">{person.name}</p>)}</div>
                <div className="mt-3 flex items-end justify-between gap-2"><p className="text-3xl font-bold text-[#101D36]">{item.summary.overall_progress === null ? 'Sin datos' : pct(item.summary.overall_progress)}</p><p className="text-right text-xs text-slate-500">{item.summary.overall_progress === null ? '' : 'de las metas'}<br />puesto {item.summary.rank}</p></div>
                <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full" style={{ width: `${(item.summary.overall_progress || 0) * 100}%`, backgroundColor: levelColor(level) }} /></div>
                <div className="mt-3 space-y-1.5">{item.goals.slice(0, 3).map((indicator) => <GoalBullet key={indicator.key} indicator={indicator} criteria={data.criteria} compact />)}</div>
                <p className="mt-auto flex items-center justify-end gap-1 pt-2 text-sm font-semibold text-[#7A5F22]">Ver equipo <ChevronRight className="h-4 w-4" /></p>
              </button>
            );
          })}
          {!data.teams.length && <p className="rounded-xl border border-[#E8E5DE] bg-white p-4 text-sm text-slate-500">Aún no hay integrantes registrados en este grupo.</p>}
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <Card title="Impacto en invasiones por equipo" subtitle={`Intentos de visita y personas alcanzadas · ${data.period.label} · toca una barra`} testId="panel-grafica-invasiones"><OutreachChart data={data} onOpenTeam={openTeam} /></Card>
          {allMembers.length > 0 && <MemberRanking members={allMembers} onOpenMember={setMember} testId="panel-ranking" />}
        </div>
        <NoData items={data.unavailable} />
      </>}
      {showHow && data && <HowCalculated data={data} onClose={() => setShowHow(false)} onGoalsSaved={load} />}
      {indicatorKey && data && <IndicatorSheet indicatorKey={indicatorKey} data={data} onClose={() => setIndicatorKey(null)} onOpenTeam={openTeam} />}
      {team && <TeamDetail team={team} data={data} period={period} campaignId={campaignId} onClose={() => setTeamId(null)} onOpenGroup={(id) => { setTeamId(null); onOpenGroup?.(id); }} />}
      {member && <MemberActivity member={member} period={period} campaignId={campaignId} criteria={data.criteria} onClose={() => setMember(null)} />}
    </section>
  );
}
