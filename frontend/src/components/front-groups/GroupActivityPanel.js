import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { ArrowLeft, Calculator, ChevronRight, CircleSlash, Crown, Loader2, Trophy, Users, X } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { canViewDirectory } from '../../lib/accessControl';
import { PeriodSelector, periodParams } from './PeriodSelector';
import { Semaphore, STATUS } from './GroupStatsPanel';

const CLASS_TO_STATUS = { A: 'green', B: 'yellow', C: 'red' };
const TYPE_LABEL = { pair: 'Pareja', individual: 'Individual', leadership: 'Liderazgo del grupo' };
const PROCESS_LABELS = { consolidation: 'Consolidación', seven_weeks: 'Ley de las 7 Semanas', discipleship: 'Discipulado', mentorship: 'Mentoría', cap: 'CAP', outreach_invasion: 'Invasión' };
const pct = (value) => `${Math.round((value || 0) * 100)}%`;
const plural = (count, one, many) => `${count ?? 0} ${count === 1 ? one : many}`;
const teamName = (team) => `${team.type === 'leadership' ? 'Liderazgo: ' : ''}${team.members.map((member) => member.name.split(' ')[0]).join(' y ')}`;

// Rankings de miembros: cada categoría usa un dato registrado (nunca estimado).
const RANKINGS = [
  { key: 'score', label: 'Más aventajado', value: (m) => m.metrics.score, unit: 'de avance' },
  { key: 'work', label: 'Trabaja más', value: (m) => m.metrics.attempts + m.metrics.activities_done, unit: 'intentos + actividades' },
  { key: 'reached', label: 'Alcanza más personas', value: (m) => m.metrics.persons_reached, unit: 'personas alcanzadas' },
  { key: 'visits', label: 'Visita más', value: (m) => m.metrics.attempts, unit: 'intentos de visita' },
  { key: 'support', label: 'Apoya más', value: (m) => m.metrics.support_shifts, unit: 'turnos de servicio' },
  { key: 'brought', label: 'Trajo más personas', value: null },
];

function ClassBadge({ value, large = false }) {
  const status = STATUS[CLASS_TO_STATUS[value]] || STATUS.red;
  const Icon = status.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border bg-white font-bold text-[#101D36] ${large ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs'}`} style={{ borderColor: status.color }} data-testid={`class-${value}`}>
      <Icon className={large ? 'h-4 w-4' : 'h-3.5 w-3.5'} style={{ color: status.color }} aria-hidden="true" />{value} · {status.label}
    </span>
  );
}

function ProgressBar({ value, status }) {
  return (
    <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`Avance ${value}%`}>
      <div className="h-full rounded-full" style={{ width: `${Math.max(value, value > 0 ? 4 : 0)}%`, backgroundColor: (STATUS[status] || STATUS.red).color }} />
    </div>
  );
}

const MiniStat = ({ label, value }) => <div className="rounded-md bg-[#FBFAF7] px-1.5 py-1 text-center"><div className="text-sm font-semibold text-[#101D36]">{value ?? 0}</div><div className="text-[10px] leading-tight text-slate-500">{label}</div></div>;

function Sheet({ title, subtitle, onClose, children, testId }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center" role="dialog" aria-modal="true" data-testid={testId}>
      <div className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-t-2xl bg-[#F8F6F0] sm:rounded-2xl">
        <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[#E8E5DE] bg-white px-3 py-2">
          <button type="button" onClick={onClose} className="grid h-11 w-11 shrink-0 place-items-center rounded-md hover:bg-slate-100" aria-label="Atrás"><ArrowLeft className="h-5 w-5" /></button>
          <div className="min-w-0 flex-1"><p className="truncate font-['Spectral'] text-lg font-semibold text-[#101D36]">{title}</p>{subtitle && <p className="truncate text-[11px] text-slate-500">{subtitle}</p>}</div>
          <button type="button" onClick={onClose} className="grid h-11 w-11 shrink-0 place-items-center rounded-md hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>
        <div className="space-y-3 p-3">{children}</div>
      </div>
    </div>
  );
}

function NoData({ items }) {
  return (
    <div className="space-y-1 rounded-xl border border-dashed border-slate-300 bg-white p-3" data-testid="panel-sin-datos">
      {items.map((item) => <p key={item.key} className="flex items-start gap-1.5 text-[11px] text-slate-600"><CircleSlash className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" /><span><b>{item.label}: sin datos.</b> {item.reason}</span></p>)}
    </div>
  );
}

function HowCalculated({ data, onClose }) {
  const { criteria } = data;
  return (
    <Sheet title="Cómo se calcula" subtitle={`Período evaluado: ${data.period.label}`} onClose={onClose} testId="como-se-calcula">
      <section className="space-y-1.5 rounded-xl bg-white p-3 text-xs text-slate-700">
        <p className="font-semibold text-[#101D36]">Clasificación A / B / C (semáforo)</p>
        {Object.entries(criteria.classes).map(([key, text]) => <p key={key} className="flex items-start gap-2"><ClassBadge value={key} /><span>{text}</span></p>)}
        <p className="pt-1">Umbrales de participación: verde ≥ <b>{pct(criteria.participation.participation_ratio_green.value)}</b>, amarillo ≥ <b>{pct(criteria.participation.participation_ratio_yellow.value)}</b> <span className="text-slate-400">({criteria.participation.participation_ratio_green.status})</span>.</p>
        <p>Umbrales de actividades vencidas: amarillo ≥ <b>{pct(criteria.overdue.overdue_activity_ratio_yellow.value)}</b>, rojo ≥ <b>{pct(criteria.overdue.overdue_activity_ratio_red.value)}</b> <span className="text-slate-400">({criteria.overdue.overdue_activity_ratio_red.status})</span>.</p>
        <p className="text-slate-400">Los umbrales «propuesta» aún no los confirmó el dueño; se ajustan en Supervisión → Criterios del semáforo.</p>
      </section>
      <section className="space-y-1.5 rounded-xl bg-white p-3 text-xs text-slate-700">
        <p className="font-semibold text-[#101D36]">Indicadores</p>
        <p>{criteria.participation_formula}</p>
        <p>{criteria.score}.</p>
        <p>{criteria.progress_formula}</p>
        <p>{criteria.attendance}</p>
        <p>{criteria.support}</p>
        <p>{criteria.invasion_dates}</p>
        <p>{criteria.member}</p>
      </section>
      <NoData items={data.unavailable} />
    </Sheet>
  );
}

function MemberActivity({ member, period, campaignId, onClose }) {
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

function MemberRanking({ members, onOpenMember, testId }) {
  const [category, setCategory] = useState('score');
  const ranking = RANKINGS.find((item) => item.key === category);
  const rows = ranking.value ? [...members].sort((a, b) => ranking.value(b) - ranking.value(a) || a.name.localeCompare(b.name)) : [];
  const best = rows.length ? ranking.value(rows[0]) : 0;
  return (
    <section className="rounded-xl border border-[#E8E5DE] bg-white p-3 shadow-sm" data-testid={testId}>
      <h3 className="flex items-center gap-2 text-sm font-semibold text-[#101D36]"><Trophy className="h-4 w-4 text-[#9A7A2F]" />Ranking de miembros</h3>
      <div className="-mx-1 mt-2 flex gap-1 overflow-x-auto px-1 pb-1" role="tablist" aria-label="Categoría del ranking">
        {RANKINGS.map((item) => <button key={item.key} type="button" role="tab" aria-selected={category === item.key} onClick={() => setCategory(item.key)} className={`min-h-10 shrink-0 rounded-full border px-3 text-xs font-semibold ${category === item.key ? 'border-[#101D36] bg-[#101D36] text-white' : 'border-[#E8E5DE] bg-white text-slate-600'}`} data-testid={`ranking-cat-${item.key}`}>{item.label}</button>)}
      </div>
      {!ranking.value ? <NoData items={[{ key: 'brought', label: 'Personas traídas a la iglesia', reason: 'No hay un registro que vincule a la persona que llegó con el integrante que la invitó.' }]} /> : (
        <ol className="mt-2 divide-y divide-[#EEECE6]">
          {rows.map((member, index) => {
            const value = ranking.value(member);
            const top = best > 0 && value === best;
            const support = member.semaphore === 'red';
            return (
              <li key={member.person_id}>
                <button type="button" onClick={() => onOpenMember(member)} className={`flex min-h-14 w-full items-center gap-3 py-2 text-left ${top ? 'bg-emerald-50/60' : ''}`} data-testid={`member-rank-${member.person_id}`}>
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#101D36] text-xs font-bold text-white">{index + 1}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-[#101D36]">{member.name}</p>
                    {member.functions.length > 0 && <p className="truncate text-[11px] text-[#7A5F22]">{member.functions.join(' · ')}</p>}
                    {top && <p className="flex items-center gap-1 text-[11px] font-semibold text-emerald-800" data-testid="member-rank-top"><Trophy className="h-3.5 w-3.5" />Primero en «{ranking.label}»</p>}
                    {!top && support && <p className="text-[11px] font-semibold text-red-700">Necesita seguimiento</p>}
                  </div>
                  <div className="shrink-0 text-right"><div className="text-lg font-semibold text-[#101D36]">{value}</div><div className="max-w-[88px] text-[10px] leading-tight text-slate-400">{ranking.unit}</div></div>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function TeamDetail({ team, data, period, campaignId, onClose, onOpenGroup }) {
  const [member, setMember] = useState(null);
  const summary = team.summary;
  const others = data.teams.filter((item) => item.team_id !== team.team_id);
  const average = data.teams.length ? Math.round(data.teams.reduce((total, item) => total + item.summary.score, 0) / data.teams.length) : 0;
  const best = Math.max(...data.teams.map((item) => item.summary.score), 0);
  const participating = team.members.filter((item) => item.active);
  const needSupport = team.members.filter((item) => item.semaphore === 'red');
  return (
    <Sheet title={teamName(team)} subtitle={`${TYPE_LABEL[team.type]} · ${data.period.label}`} onClose={onClose} testId="team-detail">
      <section className="rounded-xl bg-white p-3" data-testid="team-detail-summary">
        <div className="flex items-center justify-between gap-2"><ClassBadge value={summary.class} large /><span className="text-xs text-slate-500">Puesto {summary.rank} de {data.teams.length} equipos</span></div>
        <p className="mt-3 text-3xl font-bold text-[#101D36]">{summary.progress_pct}%<span className="ml-1 text-xs font-normal text-slate-500">de avance</span></p>
        <ProgressBar value={summary.progress_pct} status={CLASS_TO_STATUS[summary.class]} />
        <p className="mt-2 text-xs text-slate-600">Participación: {summary.participants} de {summary.people} con actividad ({pct(summary.participation_ratio)}).</p>
        <div className="mt-3 space-y-1 text-xs text-slate-600" data-testid="team-comparison">
          <p className="font-semibold text-[#101D36]">Comparación con los demás equipos del grupo</p>
          {[['Este equipo', summary.score], ['Promedio del grupo', average], ['Equipo con más avance', best]].map(([label, value]) => (
            <div key={label} className="flex items-center gap-2"><span className="w-32 shrink-0">{label}</span><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-[#2a78d6]" style={{ width: `${best ? (value / best) * 100 : 0}%` }} /></div><span className="w-8 text-right font-semibold text-[#101D36]">{value}</span></div>
          ))}
          {!others.length && <p className="text-slate-400">Es el único equipo del grupo.</p>}
        </div>
      </section>
      <section className="rounded-xl bg-white p-3">
        <p className="text-xs font-semibold uppercase text-slate-500">Actividad del equipo</p>
        <div className="mt-2 grid grid-cols-3 gap-1.5">
          <MiniStat label="Visitas (intentos)" value={summary.attempts} /><MiniStat label="Sin respuesta" value={summary.attempts_by_result?.no_answer} /><MiniStat label="Personas alcanzadas" value={summary.persons_reached} />
          <MiniStat label="Hogares" value={summary.households} /><MiniStat label="Quieren seguimiento" value={summary.followups} /><MiniStat label="Aceptaron consolidación" value={summary.accepted} />
          <MiniStat label="Asistencias" value={summary.attendance} /><MiniStat label="Apoyo (turnos)" value={summary.support_shifts} /><MiniStat label="Act. realizadas" value={summary.activities_done} />
        </div>
      </section>
      <section className="rounded-xl bg-white p-3" data-testid="team-members">
        <p className="text-xs font-semibold uppercase text-slate-500">Integrantes y funciones</p>
        <ul className="mt-2 space-y-2">
          {team.members.map((item) => (
            <li key={item.person_id} className="rounded-lg border border-[#EEECE6] p-2.5">
              <div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="truncate text-sm font-semibold text-[#101D36]">{item.name}</p><p className="text-[11px] text-[#7A5F22]">{item.functions.join(' · ') || 'Integrante'}</p></div><Semaphore value={item.semaphore} /></div>
              <p className="mt-1 text-[11px] text-slate-500">{plural(item.metrics.attempts, 'intento', 'intentos')} · {plural(item.metrics.persons_reached, 'persona alcanzada', 'personas alcanzadas')} · {plural(item.metrics.attendance, 'asistencia', 'asistencias')} · {plural(item.metrics.support_shifts, 'turno', 'turnos')}</p>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <button type="button" onClick={() => setMember(item)} className="min-h-10 rounded-md bg-[#101D36] text-xs font-semibold text-white" data-testid={`team-member-activity-${item.person_id}`}>Ver su actividad</button>
                {item.led_group ? <button type="button" onClick={() => onOpenGroup?.(item.led_group.front_group_id)} className="min-h-10 rounded-md border border-[#D9CFB4] text-xs font-semibold text-[#7A5F22]" data-testid={`team-member-group-${item.person_id}`}>Ver su grupo →</button> : <span />}
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-slate-600"><b>Participan más:</b> {participating.length ? [...participating].sort((a, b) => b.metrics.score - a.metrics.score).map((item) => item.name).join(', ') : 'nadie con actividad en el período'}.</p>
        <p className="text-xs text-slate-600"><b>Necesitan seguimiento:</b> {needSupport.length ? needSupport.map((item) => item.name).join(', ') : 'nadie'}.</p>
      </section>
      <NoData items={data.unavailable} />
      {member && <MemberActivity member={member} period={period} campaignId={campaignId} onClose={() => setMember(null)} />}
    </Sheet>
  );
}

function TeamsChart({ teams }) {
  const rows = [...teams].sort((a, b) => b.summary.progress_pct - a.summary.progress_pct).map((team) => ({ name: teamName(team), value: team.summary.progress_pct, status: CLASS_TO_STATUS[team.summary.class], label: `${team.summary.progress_pct}% · ${team.summary.class}` }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(120, rows.length * 40)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 2, right: 56, bottom: 2, left: 4 }}>
        <CartesianGrid horizontal={false} stroke="#F1F5F9" />
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis type="category" dataKey="name" width={112} tick={{ fontSize: 12, fill: '#334155' }} tickLine={false} axisLine={false} />
        <Tooltip cursor={{ fill: 'rgba(16, 29, 54, 0.05)' }} formatter={(value) => [`${value}%`, 'Avance']} />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20} background={{ fill: '#F1F5F9', radius: 4 }}>
          {rows.map((row) => <Cell key={row.name} fill={(STATUS[row.status] || STATUS.red).color} />)}
          <LabelList dataKey="label" position="right" style={{ fontSize: 11, fill: '#334155', fontWeight: 600 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ETAPA 5C: panel dinámico de "Mi Grupo Frontal" — un recuadro por equipo
// (pareja o individuo según la lista registrada) con su actividad y progreso.
export function GroupActivityPanel({ groupId, onOpenGroup }) {
  const { API, getAuthHeaders } = useAuth();
  const [period, setPeriod] = useState('month');
  const [campaignId, setCampaignId] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [teamId, setTeamId] = useState(null);
  const [showHow, setShowHow] = useState(false);
  const [member, setMember] = useState(null);

  useEffect(() => {
    setData(null); setError('');
    axios.get(`${API}/api/front-group-structure/groups/${groupId}/panel`, { ...getAuthHeaders(), params: periodParams(period, campaignId) })
      .then((response) => setData(response.data))
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar el panel.')));
  }, [API, getAuthHeaders, groupId, period, campaignId]);

  const allMembers = useMemo(() => {
    const seen = new Map();
    (data?.teams || []).forEach((team) => team.members.forEach((item) => { if (!seen.has(item.person_id)) seen.set(item.person_id, item); }));
    return [...seen.values()];
  }, [data]);
  const team = data?.teams.find((item) => item.team_id === teamId);
  const group = data?.group;

  return (
    <section className="space-y-3" data-testid="group-activity-panel">
      <PeriodSelector period={period} campaignId={campaignId} onChange={(nextPeriod, nextCampaign) => { setPeriod(nextPeriod); setCampaignId(nextCampaign || ''); }} />
      {error && <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {!data && !error && <div className="flex justify-center py-12"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>}
      {data && <>
        <section className="rounded-xl border border-[#E8E5DE] bg-white p-3 shadow-sm" data-testid="panel-resumen">
          <div className="flex items-start justify-between gap-2">
            <div><p className="text-[11px] uppercase text-slate-500">Período evaluado</p><p className="text-sm font-semibold text-[#101D36]" data-testid="panel-periodo">{data.period.label}</p></div>
            <ClassBadge value={group.class} large />
          </div>
          <div className="mt-3 grid grid-cols-4 gap-1.5"><MiniStat label="Equipos" value={group.teams} /><MiniStat label="Personas" value={group.people} /><MiniStat label="Participan" value={pct(group.participation_ratio)} /><MiniStat label="Alcanzadas" value={group.persons_reached} /></div>
          <button type="button" onClick={() => setShowHow(true)} className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-[#D9CFB4] bg-[#FBF6EA] text-sm font-semibold text-[#7A5F22]" data-testid="panel-como-se-calcula"><Calculator className="h-4 w-4" />Cómo se calcula</button>
        </section>

        {data.teams.length > 0 && (
          <section className="rounded-xl border border-[#E8E5DE] bg-white p-3 shadow-sm" data-testid="panel-grafica-equipos">
            <h3 className="text-sm font-semibold text-[#101D36]">Comparación de equipos</h3>
            <p className="text-[11px] text-slate-500">% de avance de cada equipo frente al de más avance · color = clase A/B/C</p>
            <TeamsChart teams={data.teams} />
          </section>
        )}

        <div className="grid gap-3 sm:grid-cols-2" data-testid="panel-equipos">
          {data.teams.map((item) => {
            const status = CLASS_TO_STATUS[item.summary.class];
            return (
              <button key={item.team_id} type="button" onClick={() => setTeamId(item.team_id)} className="block w-full rounded-2xl border-2 bg-white p-4 text-left shadow-sm transition hover:shadow-md" style={{ borderColor: `${(STATUS[status] || STATUS.red).color}55` }} data-testid={`team-card-${item.team_id}`}>
                <div className="flex items-start justify-between gap-2">
                  <span className="inline-flex items-center gap-1 rounded bg-[#F3EBD7] px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[#7A5F22]">{item.type === 'leadership' ? <Crown className="h-3 w-3" /> : <Users className="h-3 w-3" />}{TYPE_LABEL[item.type]}</span>
                  <ClassBadge value={item.summary.class} />
                </div>
                <div className="mt-2 space-y-0.5">{item.members.map((person) => <p key={person.person_id} className="truncate text-base font-semibold text-[#101D36]">{person.name}</p>)}</div>
                <div className="mt-3 flex items-end justify-between"><p className="text-3xl font-bold text-[#101D36]">{item.summary.progress_pct}%</p><p className="text-right text-xs text-slate-500">avance<br />puesto {item.summary.rank}</p></div>
                <ProgressBar value={item.summary.progress_pct} status={status} />
                <p className="mt-2 text-xs text-slate-600">Participación {item.summary.participants}/{item.summary.people} · <Semaphore value={item.summary.semaphore_reasons.participation} /></p>
                <div className="mt-2 grid grid-cols-4 gap-1"><MiniStat label="Visitas" value={item.summary.attempts} /><MiniStat label="Alcanzadas" value={item.summary.persons_reached} /><MiniStat label="Asistencias" value={item.summary.attendance} /><MiniStat label="Apoyo" value={item.summary.support_shifts} /></div>
                <p className="mt-2 flex items-center justify-end gap-1 text-xs font-semibold text-[#7A5F22]">Ver equipo <ChevronRight className="h-4 w-4" /></p>
              </button>
            );
          })}
          {!data.teams.length && <p className="rounded-xl border border-[#E8E5DE] bg-white p-4 text-sm text-slate-500">Aún no hay integrantes registrados en este grupo.</p>}
        </div>

        {allMembers.length > 0 && <MemberRanking members={allMembers} onOpenMember={setMember} testId="panel-ranking" />}
        <NoData items={data.unavailable} />
      </>}
      {showHow && data && <HowCalculated data={data} onClose={() => setShowHow(false)} />}
      {team && <TeamDetail team={team} data={data} period={period} campaignId={campaignId} onClose={() => setTeamId(null)} onOpenGroup={(id) => { setTeamId(null); onOpenGroup?.(id); }} />}
      {member && <MemberActivity member={member} period={period} campaignId={campaignId} onClose={() => setMember(null)} />}
    </section>
  );
}
