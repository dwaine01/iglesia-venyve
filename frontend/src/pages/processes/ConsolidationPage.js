import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, BadgeCheck, Route, UsersRound } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { ConsolidationIntakeDialog } from '../../components/processes/ConsolidationIntakeDialog';
import { ConsolidationJourneyCard } from '../../components/processes/ConsolidationJourneyCard';
import { ProcessError, ProcessLoading, ProcessShell } from '../../components/processes/ProcessShell';

const metrics = [
  ['total', 'Rutas registradas', Route],
  ['active', 'En progreso', UsersRound],
  ['members', 'Miembros activos', BadgeCheck],
  ['mentor_transfer_required', 'Transferencia requerida', AlertTriangle],
];
const filters = [['all', 'Todas'], ['visitor_followup', 'Seguimiento'], ['complete_cycle', 'Ciclo completo'], ['direct_church', 'Iglesia'], ['cell', 'Célula']];
const entryNames = { complete_cycle: 'Ciclo completo', direct_church: 'Iglesia', cell: 'Célula', visitor_followup: 'Seguimiento' };

export default function ConsolidationPage() {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState({ dashboard: {}, items: [], groups: [], assignees: [] });
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [dashboard, enrollments, groups, catalog] = await Promise.all([
        axios.get(`${API}/api/processes/consolidation/dashboard`, getAuthHeaders()),
        axios.get(`${API}/api/processes/enrollments?process_key=consolidation`, getAuthHeaders()),
        axios.get(`${API}/api/front-groups`, getAuthHeaders()),
        axios.get(`${API}/api/processes/catalog`, getAuthHeaders()),
      ]);
      setData({ dashboard: dashboard.data, items: (enrollments.data.items || []).filter((item) => item.definition_version >= 2), groups: groups.data.items || [], assignees: catalog.data.assignees || [] });
    } catch (requestError) { setError(requestError?.response?.data?.detail || 'No se pudo cargar Consolidación'); } finally { setLoading(false); }
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  const visible = useMemo(() => filter === 'all' ? data.items : data.items.filter((item) => item.entry_mode === filter), [data.items, filter]);
  return <ProcessShell title="Consolidación" eyebrow="Ruta oficial" description="Cuatro puertas de entrada, un solo recorrido y un historial permanente hasta Membresía, Retiro y Discipulado." actions={<ConsolidationIntakeDialog groups={data.groups} assignees={data.assignees} onCreated={load} />}>
    {loading ? <ProcessLoading /> : error ? <ProcessError message={error} /> : <>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="consolidation-metrics">{metrics.map(([key, label, Icon]) => <article key={key} className="border border-slate-200 bg-white p-4"><Icon className="h-5 w-5 text-amber-600" /><strong className="mt-5 block font-['Spectral'] text-3xl text-slate-950" data-testid={`consolidation-metric-${key}`}>{data.dashboard[key] || 0}</strong><span className="text-xs text-slate-500">{label}</span></article>)}</section>
      <section className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="font-['Spectral'] text-2xl font-semibold">Expedientes activos e históricos</h2><p className="text-sm text-slate-500">La puerta de entrada se conserva aunque todas converjan en MCD.</p></div><div className="flex flex-wrap gap-2">{filters.map(([value, label]) => <button key={value} onClick={() => setFilter(value)} className={`border px-3 py-2 text-xs font-semibold ${filter === value ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white text-slate-600'}`} data-testid={`consolidation-filter-${value}`}>{label}</button>)}</div></div>
      {visible.length ? <div className="grid gap-4 lg:grid-cols-2">{visible.map((item) => <ConsolidationJourneyCard key={item.enrollment_id} item={item} />)}</div> : <div className="border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500" data-testid="consolidation-empty-state">No hay rutas en este filtro.</div>}</section>
      <section className="grid gap-5 xl:grid-cols-2" data-testid="consolidation-reports"><article className="border bg-white p-5"><h2 className="font-['Spectral'] text-2xl font-semibold">Efectividad por puerta</h2><div className="mt-4 space-y-3">{Object.entries(data.dashboard.by_entry || {}).map(([key, value]) => <div key={key}><div className="mb-1 flex justify-between text-xs"><span>{entryNames[key] || key}</span><b>{value}</b></div><div className="h-2 bg-slate-100"><div className="h-full bg-amber-500" style={{ width: `${data.dashboard.total ? value / data.dashboard.total * 100 : 0}%` }} /></div></div>)}</div><div className="mt-5 grid grid-cols-3 gap-2 border-t pt-4 text-center"><div><b>{data.dashboard.membership_conversion_pct || 0}%</b><span className="block text-[10px] text-slate-500">A membresía</span></div><div><b>{data.dashboard.retreat_conversion_pct || 0}%</b><span className="block text-[10px] text-slate-500">A Retiro</span></div><div><b>{data.dashboard.avg_days_to_membership ?? '—'}</b><span className="block text-[10px] text-slate-500">Días a membresía</span></div></div></article><article className="border bg-white p-5"><h2 className="font-['Spectral'] text-2xl font-semibold">Embudo formativo</h2><div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">{Object.entries(data.dashboard.by_stage || {}).map(([stage, value]) => <div key={stage} className="border border-slate-100 p-3"><b className="text-xl">{value}</b><span className="block text-[10px] uppercase text-slate-500">{stage.replaceAll('_', ' ')}</span></div>)}</div><div className={`mt-4 border p-3 text-sm ${data.dashboard.active_alerts ? 'border-red-200 bg-red-50 text-red-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`} data-testid="consolidation-alert-summary">{data.dashboard.active_alerts || 0} alertas operativas activas</div></article></section>
    </>}
  </ProcessShell>;
}