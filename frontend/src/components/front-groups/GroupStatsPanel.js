import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, CheckCircle2, ChevronRight, HelpCircle, Loader2, OctagonAlert, Trophy } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { PeriodSelector, periodParams } from './PeriodSelector';

// Paleta validada (scripts/validate_palette.js): categórica en orden fijo y
// estados reservados para el semáforo: verde, ámbar y rojo apagados
// (contraste ≥ 3:1), siempre con ícono + texto.
export const SERIES = { blue: '#2a78d6', orange: '#eb6834', aqua: '#1baf7a', yellow: '#eda100' };
export const STATUS = {
  green: { color: '#3d8b5a', label: 'Avanza', icon: CheckCircle2 },
  yellow: { color: '#b8862b', label: 'Atención', icon: AlertTriangle },
  red: { color: '#b4493d', label: 'Necesita seguimiento', icon: OctagonAlert },
};
const RESULTS = [
  { key: 'contacted', label: 'Contactados', color: SERIES.blue },
  { key: 'no_answer', label: 'Sin respuesta', color: SERIES.orange },
  { key: 'not_home', label: 'No estaba', color: SERIES.aqua },
  { key: 'refused', label: 'Rechazó', color: SERIES.yellow },
];
const ROLE = { leader: 'Líder', co_leader: 'Colíder' };
const plural = (count, one, many) => `${count ?? 0} ${count === 1 ? one : many}`;
const pct = (value) => `${Math.round((value || 0) * 100)}%`;
const shortName = (name) => (name && name.length > 14 ? `${name.slice(0, 13)}…` : name);

export function Semaphore({ value, testId }) {
  const status = STATUS[value] || STATUS.red;
  const Icon = status.icon;
  return <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-700" data-testid={testId}><Icon className="h-4 w-4" style={{ color: status.color }} aria-hidden="true" />{status.label}</span>;
}

const Tile = ({ label, value, hint }) => (
  <div className="rounded-lg border border-[#EEECE6] bg-white p-2.5">
    <div className="text-xl font-semibold text-[#101D36]">{value ?? 0}</div>
    <div className="text-[11px] leading-tight text-slate-500">{label}</div>
    {hint && <div className="mt-0.5 text-[10px] text-slate-400">{hint}</div>}
  </div>
);

const ChartCard = ({ title, subtitle, children, testId }) => (
  <section className="rounded-xl border border-[#E8E5DE] bg-white p-3 shadow-sm" data-testid={testId}>
    <h3 className="text-sm font-semibold text-[#101D36]">{title}</h3>
    {subtitle && <p className="text-[11px] text-slate-500">{subtitle}</p>}
    <div className="mt-2">{children}</div>
  </section>
);

const axisProps = { tick: { fontSize: 11, fill: '#475569' }, tickLine: false, axisLine: { stroke: '#E2E8F0' } };

function ParticipationChart({ groups }) {
  const data = groups.map((group) => ({ name: shortName(group.name), full: group.name, value: Math.round(group.participation_ratio * 100), semaphore: group.semaphore_reasons.participation, label: `${group.participants}/${group.people}` }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(140, data.length * 44)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }}>
        <CartesianGrid horizontal={false} stroke="#F1F5F9" />
        <XAxis type="number" domain={[0, 100]} unit="%" {...axisProps} />
        <YAxis type="category" dataKey="name" width={96} {...axisProps} />
        <Tooltip formatter={(value, _name, item) => [`${value}% (${item.payload.label} integrantes con actividad)`, 'Participación']} labelFormatter={(_label, payload) => payload?.[0]?.payload?.full} />
        <Bar dataKey="value" name="Participación" radius={[0, 4, 4, 0]} barSize={18}>
          {data.map((item) => <Cell key={item.full} fill={(STATUS[item.semaphore] || STATUS.red).color} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function GroupedBars({ data, series, height = 220 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -16 }} barGap={2}>
        <CartesianGrid vertical={false} stroke="#F1F5F9" />
        <XAxis dataKey="name" {...axisProps} interval={0} />
        <YAxis allowDecimals={false} {...axisProps} />
        <Tooltip labelFormatter={(_label, payload) => payload?.[0]?.payload?.full || _label} />
        <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" itemSorter={(item) => series.findIndex((entry) => entry.key === item.dataKey)} formatter={(value) => <span style={{ color: '#475569' }}>{value}</span>} />
        {series.map((item) => <Bar key={item.key} dataKey={item.key} name={item.label} fill={item.color} stackId={item.stack} radius={item.stack ? undefined : [4, 4, 0, 0]} maxBarSize={28} stroke="#fff" strokeWidth={item.stack ? 1 : 0} />)}
      </BarChart>
    </ResponsiveContainer>
  );
}

function RankingList({ rows, testId }) {
  if (!rows.length) return <p className="text-sm text-slate-400">Sin integrantes.</p>;
  return (
    <ol className="divide-y divide-[#EEECE6]" data-testid={testId}>
      {rows.map((row) => (
        <li key={row.person_id} className={`flex items-center gap-3 py-2.5 ${row.highlight === 'top' ? 'bg-emerald-50/60' : row.highlight === 'needs_support' ? 'bg-red-50/40' : ''}`} data-testid={`ranking-row-${row.person_id}`}>
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-[#101D36] text-xs font-bold text-white">{row.rank}</span>
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-[#101D36]"><span className="truncate">{row.name}</span>{ROLE[row.role] && <span className="shrink-0 rounded bg-[#F3EBD7] px-1.5 text-[10px] font-semibold text-[#7A5F22]">{ROLE[row.role]}</span>}</p>
            <p className="text-[11px] text-slate-500">{plural(row.persons_reached, 'persona', 'personas')} · {plural(row.households, 'hogar', 'hogares')} · {plural(row.attempts, 'intento', 'intentos')} · {plural(row.activities_done, 'actividad', 'actividades')}</p>
            {row.highlight === 'top' && <p className="flex items-center gap-1 text-[11px] font-semibold text-emerald-800" data-testid="ranking-top"><Trophy className="h-3.5 w-3.5" />Avanza más</p>}
            {row.highlight === 'needs_support' && <p className="text-[11px] font-semibold text-red-700" data-testid="ranking-needs-support">Necesita apoyo</p>}
          </div>
          <div className="shrink-0 text-right"><div className="text-lg font-semibold text-[#101D36]">{row.score}</div><div className="text-[10px] text-slate-400">avance</div></div>
        </li>
      ))}
    </ol>
  );
}

// ETAPA 5C-3: estadísticas del grupo y su rama con los mismos registros de
// invasión y consolidación; semáforo con criterios visibles y configurables.
export function GroupStatsPanel({ groupId, onOpenGroup }) {
  const { API, getAuthHeaders } = useAuth();
  const [period, setPeriod] = useState('month');
  const [campaignId, setCampaignId] = useState('');
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');
  const [rankingScope, setRankingScope] = useState('group');
  const [showCriteria, setShowCriteria] = useState(false);

  useEffect(() => {
    setStats(null); setError('');
    const params = periodParams(period, campaignId);
    axios.get(`${API}/api/front-group-structure/groups/${groupId}/stats`, { ...getAuthHeaders(), params })
      .then((response) => setStats(response.data))
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudieron cargar las estadísticas.')));
  }, [API, getAuthHeaders, groupId, period, campaignId]);

  const branch = stats?.branch;
  const children = stats?.children || [];
  const reachData = children.map((group) => ({ name: shortName(group.name), full: group.name, persons_reached: group.persons_reached, households: group.households }));
  const attemptsData = (children.length ? children : (branch ? [{ name: 'Esta rama', ...branch }] : [])).map((group) => ({ name: shortName(group.name), full: group.name, ...group.attempts_by_result }));
  const timelineData = (stats?.timeline || []).map((point) => ({ ...point, name: point.bucket.length > 7 ? point.bucket.slice(5) : point.bucket }));

  return (
    <section className="space-y-3" data-testid="group-stats-panel">
      <h2 className="font-semibold text-[#101D36]">Estadísticas del grupo y su rama</h2>
      <PeriodSelector period={period} campaignId={campaignId} onChange={(nextPeriod, nextCampaign) => { setPeriod(nextPeriod); setCampaignId(nextCampaign || ''); }} />
      {error && <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {!stats && !error && <div className="flex justify-center py-10"><Loader2 className="h-6 w-6 animate-spin text-[#9A7A2F]" /></div>}
      {stats && <>
        <div className="rounded-xl border border-[#E8E5DE] bg-[#FBFAF7] p-3" data-testid="stats-semaphore">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><p className="text-[11px] uppercase text-slate-500">{stats.period.label}</p><Semaphore value={branch.semaphore} testId="branch-semaphore" /></div>
            <button type="button" onClick={() => setShowCriteria((value) => !value)} className="inline-flex min-h-10 items-center gap-1 text-xs font-semibold text-[#7A5F22]" data-testid="stats-criteria-toggle"><HelpCircle className="h-4 w-4" />{showCriteria ? 'Ocultar criterios' : 'Ver criterios'}</button>
          </div>
          <p className="mt-1 text-xs text-slate-600">Participación: {branch.participants} de {branch.people} integrantes con actividad ({pct(branch.participation_ratio)}) · <Semaphore value={branch.semaphore_reasons.participation} /> · Actividades vencidas: {branch.activities_overdue} de {branch.activities_total} · <Semaphore value={branch.semaphore_reasons.overdue} /></p>
          {showCriteria && <ul className="mt-2 space-y-1 rounded-lg bg-white p-2 text-[11px] text-slate-600" data-testid="stats-criteria">
            <li><b>Verde</b> si al menos {pct(stats.criteria.participation.participation_ratio_green.value)} de los integrantes tuvo actividad; <b>amarillo</b> desde {pct(stats.criteria.participation.participation_ratio_yellow.value)}; debajo, <b>rojo</b>.</li>
            <li>Actividades vencidas: <b>amarillo</b> desde {pct(stats.criteria.overdue.overdue_activity_ratio_yellow.value)}, <b>rojo</b> desde {pct(stats.criteria.overdue.overdue_activity_ratio_red.value)}. El grupo toma el peor de los dos.</li>
            <li>Integrante: {stats.criteria.member}</li>
            <li>{stats.criteria.score}.</li>
            <li className="text-slate-400">La pastora o el coordinador general ajustan estos umbrales en Supervisión → Criterios del semáforo.</li>
          </ul>}
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="stats-kpis">
          <Tile label="Integrantes en la rama" value={branch.people} hint={`${branch.leaders} líderes y colíderes`} />
          <Tile label="Participaron" value={branch.participants} hint={pct(branch.participation_ratio)} />
          <Tile label="Personas alcanzadas" value={branch.persons_reached} hint={`${branch.followups} quieren seguimiento`} />
          <Tile label="Hogares" value={branch.households} />
          <Tile label="Intentos de visita" value={branch.attempts} hint={`${branch.attempts_by_result.no_answer} sin respuesta`} />
          <Tile label="Aceptaron consolidación" value={branch.accepted} />
          <Tile label="Actividades realizadas" value={branch.activities_done} />
          <Tile label="Actividades vencidas" value={branch.activities_overdue} />
        </div>

        {children.length > 0 && <>
          <ChartCard title="Participación por grupo en invasiones" subtitle="% de integrantes con actividad en el período · color = semáforo" testId="chart-participation"><ParticipationChart groups={children} /></ChartCard>
          <ChartCard title="Personas y hogares alcanzados por grupo" testId="chart-reach"><GroupedBars data={reachData} series={[{ key: 'persons_reached', label: 'Personas alcanzadas', color: SERIES.blue }, { key: 'households', label: 'Hogares', color: SERIES.orange }]} /></ChartCard>
        </>}
        <ChartCard title="Visitas y seguimientos" subtitle="Intentos de visita por resultado, incluidos los sin respuesta" testId="chart-attempts"><GroupedBars data={attemptsData} series={RESULTS.map((item) => ({ ...item, stack: 'r' }))} /></ChartCard>
        {timelineData.length > 0 && <ChartCard title="Avance en el período" subtitle={stats.period.label} testId="chart-timeline"><GroupedBars data={timelineData} height={200} series={[{ key: 'attempts', label: 'Intentos de visita', color: SERIES.blue }, { key: 'persons_reached', label: 'Personas alcanzadas', color: SERIES.orange }]} /></ChartCard>}

        {children.length > 0 && <section className="rounded-xl border border-[#E8E5DE] bg-white p-3 shadow-sm" data-testid="stats-comparison">
          <h3 className="text-sm font-semibold text-[#101D36]">Comparación entre grupos y sus líderes</h3>
          <ul className="mt-2 divide-y divide-[#EEECE6]">
            {[...children].sort((a, b) => b.score - a.score).map((group) => (
              <li key={group.front_group_id}>
                <button type="button" onClick={() => onOpenGroup?.(group.front_group_id)} className="flex min-h-14 w-full items-center gap-2 py-2 text-left">
                  <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-[#101D36]">{group.name}</p><p className="truncate text-[11px] text-slate-500">Líder: {group.leader_name || 'Por definir'} · {plural(group.people, 'persona', 'personas')} · {pct(group.participation_ratio)} participó · {group.persons_reached} alcanzadas · avance {group.score}</p><Semaphore value={group.semaphore} /></div>
                  <ChevronRight className="h-5 w-5 shrink-0 text-slate-400" />
                </button>
              </li>
            ))}
          </ul>
        </section>}

        <section className="rounded-xl border border-[#E8E5DE] bg-white p-3 shadow-sm" data-testid="stats-ranking">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-[#101D36]">¿Qué integrante avanza más?</h3>
            <div className="grid grid-cols-2 gap-1 rounded-lg bg-[#EEECE6] p-1" role="tablist" aria-label="Alcance del ranking">
              {[['group', 'Este grupo'], ['branch', 'Toda la rama']].map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={rankingScope === key} onClick={() => setRankingScope(key)} className={`min-h-9 rounded-md px-2 text-[11px] font-semibold ${rankingScope === key ? 'bg-white text-[#101D36] shadow-sm' : 'text-slate-600'}`} data-testid={`ranking-scope-${key}`}>{label}</button>)}
            </div>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">{stats.criteria.score}</p>
          <RankingList rows={rankingScope === 'group' ? stats.ranking_group : stats.ranking_branch} testId="ranking-list" />
        </section>
      </>}
    </section>
  );
}
