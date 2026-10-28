import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Clock, Filter, Loader2, PauseCircle, Repeat, Sprout, UserX, UsersRound } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { ChartCard, COLORS, HBars, Lines, PALETTE, VBars } from '../invasions/reportCharts';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';

const PERIODS = [['week', 'Semana'], ['month', 'Mes'], ['quarter', 'Trimestre'], ['all', 'Todo']];
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('es', { day: 'numeric', month: 'short' }) : '—');
const hoursLabel = (value) => (value == null ? 'Sin datos' : value < 48 ? `${value} h` : `${Math.round(value / 24 * 10) / 10} días`);

// Lista de personas detrás de una cifra (paginada en el servidor).
function MetricList({ metric, filters, onClose }) {
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!metric) return;
    setData(null);
    axios.get(`${API}/api/consolidation/panorama/list/${metric.key}`, { ...getAuthHeaders(), params: { ...filters, limit: 200 } })
      .then((response) => setData(response.data)).catch(() => setData({ items: [], total: 0 }));
  }, [API, getAuthHeaders, metric, filters]);
  return (
    <Dialog open={Boolean(metric)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="bg-white sm:max-w-2xl" data-testid="panorama-list">
        <DialogHeader><DialogTitle>{metric?.label}</DialogTitle><DialogDescription>{data ? `${data.total} persona(s)` : 'Cargando…'}</DialogDescription></DialogHeader>
        {!data ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : data.items.length === 0 ? <p className="text-base text-slate-500">Nadie en esta lista.</p> : (
          <ul className="divide-y divide-[#EEECE6]">
            {data.items.map((item) => (
              <li key={item.enrollment_id || item.person_id}>
                <button type="button" onClick={() => navigate(item.enrollment_id ? `/procesos/consolidacion/${item.enrollment_id}` : `/personas/${item.person_id}`)} className="flex min-h-14 w-full items-start justify-between gap-3 py-2 text-left" data-testid={`panorama-row-${item.enrollment_id || item.person_id}`}>
                  <span className="min-w-0"><span className="block truncate text-base font-semibold text-[#101D36]">{item.name}</span>
                    <span className="block text-sm text-slate-600">{item.stage_label || 'Sin etapa'} · {item.reason || item.mentor_name || 'Sin mentor'}</span>
                    <span className="block text-xs text-slate-500">Desde {fmtDate(item.created_at)} · última actividad {fmtDate(item.last_activity_at)}{item.next_action ? ` · próxima: ${item.next_action}${item.next_action_at ? ` (${fmtDate(item.next_action_at)})` : ''}` : ''}</span></span>
                  <span className="shrink-0 text-sm font-semibold text-[#101D36] underline">Abrir</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Tile({ icon: Icon, label, value, hint, tone, onClick, testId }) {
  const tones = { warn: 'border-amber-300 bg-amber-50', alert: 'border-[#e3c2bd] bg-[#fdf2f1]', normal: 'border-[#E8E5DE] bg-white' };
  return (
    <button type="button" onClick={onClick} className={`flex min-h-[84px] min-w-0 items-start gap-3 rounded-xl border p-3 text-left shadow-sm ${tones[tone] || tones.normal}`} data-testid={testId}>
      <Icon className="mt-1 h-5 w-5 shrink-0 text-[#9A7A2F]" />
      <span className="min-w-0"><span className="block text-2xl font-semibold leading-7 text-[#101D36]">{value}</span><span className="block text-[13px] leading-4 text-slate-700">{label}</span>{hint && <span className="mt-0.5 block text-[11px] text-slate-500">{hint}</span>}</span>
    </button>
  );
}

/** C3 · Panorama de Consolidación (pastoral, coordinador general y encargados). */
export function ConsolidationPanorama({ groups = [] }) {
  const { API, getAuthHeaders } = useAuth();
  const [filters, setFilters] = useState({ period: 'month' });
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [campaigns, setCampaigns] = useState([]);
  const [open, setOpen] = useState(null);
  const [showFilters, setShowFilters] = useState(false);
  const load = useCallback(() => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
    axios.get(`${API}/api/consolidation/panorama`, { ...getAuthHeaders(), params }).then((response) => { setData(response.data); setError(''); })
      .catch((requestError) => setError(requestError?.response?.data?.detail || 'No se pudo cargar el panorama'));
  }, [API, getAuthHeaders, filters]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    axios.get(`${API}/api/mentorship/outreach/campaigns`, getAuthHeaders()).then((response) => setCampaigns(response.data.items || [])).catch(() => setCampaigns([]));
  }, [API, getAuthHeaders]);
  const set = (patch) => setFilters((current) => ({ ...current, ...patch }));
  const listFilters = Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
  const show = (key, label) => setOpen({ key, label });

  if (error) return <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" data-testid="panorama-error">{error}</p>;
  if (!data) return <div className="flex justify-center p-6"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  const f = data.figures;
  const activeFilters = ['campaign_id', 'mentor_person_id', 'front_group_id', 'stage_key'].filter((key) => filters[key]).length;
  const delta = f.new_delta;
  const funnel = data.funnel.map((row, index) => ({ name: row.label, value: row.value, key: row.key, color: PALETTE[index % PALETTE.length], label: `${row.value}${data.funnel[0].value && index ? ` (${Math.round((row.value / data.funnel[0].value) * 100)}%)` : ''}` }));
  const loads = data.mentor_load.items.slice(0, 12).map((row) => ({ name: row.name, value: row.active, color: row.above_average ? COLORS.amber : COLORS.blue, label: `${row.active}${row.above_average ? ' · alta' : ''}` }));
  const heavy = data.mentor_load.items.filter((row) => row.above_average);
  const trend = data.trend.map((row) => ({ name: row.label, Nuevos: row.new, Actividades: row.activities }));
  const byStage = data.by_stage.map((row) => ({ name: row.label, Activas: row.active, key: row.stage_key }));
  const periodLabel = filters.campaign_id && filters.period === 'invasion' ? 'en la invasión' : { week: 'esta semana', month: 'este mes', quarter: 'este trimestre', all: 'en total' }[filters.period];

  return (
    <section className="space-y-4" data-testid="consolidation-panorama">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div><h2 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">Panorama de Consolidación</h2><p className="text-sm text-slate-600">{data.scope === 'mine' ? 'Tus personas' : 'Toda la iglesia'}{data.filters.campaign_name ? ` · ${data.filters.campaign_name}` : ''}</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="grid grid-cols-4 gap-1 rounded-xl bg-[#EEECE6] p-1" role="tablist" data-testid="panorama-period">
            {PERIODS.map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={filters.period === key} onClick={() => set({ period: key })} className={`min-h-11 rounded-lg px-3 text-[15px] font-semibold ${filters.period === key ? 'bg-white text-[#101D36] shadow' : 'text-slate-600'}`}>{label}</button>)}
          </div>
          <button type="button" onClick={() => setShowFilters(!showFilters)} className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-[#D9D4C7] bg-white px-3 text-[15px] font-semibold text-[#101D36]" aria-expanded={showFilters} data-testid="panorama-filters-toggle"><Filter className="h-4 w-4" />Filtros{activeFilters ? ` (${activeFilters})` : ''}</button>
        </div>
      </div>
      {showFilters && <div className="grid grid-cols-1 gap-2 rounded-xl border border-[#E8E5DE] bg-white p-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="panorama-filters">
        <select value={filters.campaign_id || ''} onChange={(event) => set({ campaign_id: event.target.value || undefined, period: event.target.value ? 'invasion' : 'month' })} className="h-12 rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" aria-label="Invasión"><option value="">Todas las invasiones</option>{campaigns.map((item) => <option key={item.campaign_id} value={item.campaign_id}>{item.name}</option>)}</select>
        {data.scope === 'all' && <select value={filters.mentor_person_id || ''} onChange={(event) => set({ mentor_person_id: event.target.value || undefined })} className="h-12 rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" aria-label="Mentor"><option value="">Todos los mentores</option>{data.mentor_load.items.map((row) => <option key={row.mentor_person_id} value={row.mentor_person_id}>{row.name}</option>)}</select>}
        <select value={filters.front_group_id || ''} onChange={(event) => set({ front_group_id: event.target.value || undefined })} className="h-12 rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" aria-label="Grupo Frontal"><option value="">Todos los Grupos Frontales</option>{groups.map((item) => <option key={item.front_group_id} value={item.front_group_id}>{item.display_name || item.name}</option>)}</select>
        <select value={filters.stage_key || ''} onChange={(event) => set({ stage_key: event.target.value || undefined })} className="h-12 rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" aria-label="Etapa"><option value="">Todas las etapas</option>{data.by_stage.map((row) => <option key={row.stage_key} value={row.stage_key}>{row.label}</option>)}</select>
        {activeFilters > 0 && <button type="button" onClick={() => setFilters({ period: 'month' })} className="min-h-11 text-left text-[15px] font-semibold text-[#8f382f] underline sm:col-span-2 xl:col-span-4">Quitar filtros</button>}
      </div>}

      {f.unattended > 0 && <button type="button" onClick={() => show('unattended', `Sin atender (más de ${data.unattended_hours} h)`)} className="flex min-h-14 w-full items-center gap-3 rounded-xl border-2 border-amber-400 bg-amber-50 p-3 text-left" data-testid="panorama-alert"><AlertTriangle className="h-6 w-6 shrink-0 text-amber-700" /><span className="text-[15px] font-semibold text-amber-900">{f.unattended} persona(s) sin atender por más de {data.unattended_hours} h. Toca para ver la lista y asignar.</span></button>}

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4" data-testid="panorama-figures">
        <Tile icon={UsersRound} label="Personas en Consolidación" value={f.total} hint={`${f.active} activas`} onClick={() => show('total', 'Personas en Consolidación')} testId="panorama-total" />
        <Tile icon={Sprout} label={`Nuevas ${periodLabel || ''}`} value={f.new} hint={delta == null ? null : delta === 0 ? 'Igual que el periodo anterior' : `${delta > 0 ? '+' : ''}${delta} vs. periodo anterior`} onClick={() => show('new', `Nuevas ${periodLabel || ''}`)} testId="panorama-new" />
        <Tile icon={UserX} label={`Sin atender (> ${data.unattended_hours} h)`} value={f.unattended} tone={f.unattended ? 'warn' : 'normal'} onClick={() => show('unattended', 'Sin atender')} testId="panorama-unattended" />
        <Tile icon={PauseCircle} label={`Parados (${data.stalled_days} días sin actividad)`} value={f.stalled} tone={f.stalled ? 'warn' : 'normal'} onClick={() => show('stalled', `Parados: ${data.stalled_days} días sin actividad`)} testId="panorama-stalled" />
        {f.without_leader != null && <Tile icon={UserX} label="Personas sin líder" value={f.without_leader} tone={f.without_leader ? 'warn' : 'normal'} hint="La misma lista del Panel General" onClick={() => show('without_leader', 'Personas sin líder')} testId="panorama-without-leader" />}
        <Tile icon={Clock} label="Sin próxima acción" value={f.no_next_action} tone={f.no_next_action ? 'warn' : 'normal'} onClick={() => show('no_next_action', 'Sin próxima acción programada')} testId="panorama-no-next" />
        <Tile icon={Clock} label="Primer contacto (promedio)" value={hoursLabel(f.first_contact_avg_hours)} hint={f.first_contact_count ? `${f.first_contact_count} con contacto` : null} onClick={() => show('first_contact', 'Con primer contacto registrado')} testId="panorama-first-contact" />
        <Tile icon={Repeat} label="Transferencias pendientes" value={f.transfers} tone={f.transfers ? 'warn' : 'normal'} onClick={() => show('transfers', 'Transferencias pendientes')} testId="panorama-transfers" />
        <Tile icon={UsersRound} label="Mentores con personas" value={data.mentor_load.mentors} hint={data.mentor_load.average ? `${data.mentor_load.average} por mentor en promedio` : null} onClick={() => show('total', 'Personas en Consolidación')} testId="panorama-mentors" />
        <Tile icon={Sprout} label="Ya son miembros" value={f.memberships} onClick={() => show('memberships', 'Ya son miembros')} testId="panorama-members" />
      </div>
      {delta != null && <p className="flex items-center gap-1 text-sm text-slate-600">{delta >= 0 ? <ArrowUpRight className="h-4 w-4 text-[#2f6e47]" /> : <ArrowDownRight className="h-4 w-4 text-[#8f382f]" />}{f.new} nuevas {periodLabel} frente a {f.new_previous} en el periodo anterior.</p>}

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <ChartCard title={funnel[0].value ? `${funnel[2].value} de ${funnel[0].value} llegaron a MCD (${Math.round((funnel[2].value / funnel[0].value) * 100)}%)` : 'Embudo: aún sin personas'} subtitle="Personas que alcanzaron cada paso · toca una barra para ver la lista" testId="panorama-funnel">
          <HBars data={funnel} labelKey="label" />
          <div className="mt-2 flex flex-wrap gap-2">{data.funnel.map((row) => <button key={row.key} type="button" onClick={() => show(`funnel:${row.key}`, row.label)} className="min-h-10 rounded-full border border-[#D9D4C7] px-3 text-sm font-semibold text-[#101D36]">{row.label}: {row.value}</button>)}</div>
        </ChartCard>
        <ChartCard title={heavy.length ? `${heavy.length} mentor(es) con más del doble del promedio` : 'Carga repartida entre los mentores'} subtitle="Personas activas por mentor (máx. 12)" testId="panorama-load"><HBars data={loads} labelKey="label" /></ChartCard>
        <ChartCard title={trend.length ? `${trend.reduce((sum, row) => sum + row.Nuevos, 0)} nuevas y ${trend.reduce((sum, row) => sum + row.Actividades, 0)} actividades en 8 semanas` : 'Tendencia'} subtitle="Por semana" testId="panorama-trend"><Lines data={trend} series={[{ key: 'Nuevos', label: 'Expedientes nuevos', color: COLORS.blue }, { key: 'Actividades', label: 'Actividades realizadas', color: COLORS.green }]} /></ChartCard>
        <ChartCard title={byStage.length ? `La etapa con más personas: ${[...byStage].sort((a, b) => b.Activas - a.Activas)[0].name}` : 'Personas activas por etapa'} subtitle="Toca una etapa para ver la lista" testId="panorama-stages">
          <VBars data={byStage} series={[{ key: 'Activas', label: 'Activas', color: COLORS.teal }]} />
          <div className="mt-2 flex flex-wrap gap-2">{data.by_stage.map((row) => <button key={row.stage_key} type="button" onClick={() => show(`stage:${row.stage_key}`, row.label)} className="min-h-10 rounded-full border border-[#D9D4C7] px-3 text-sm font-semibold text-[#101D36]">{row.label}: {row.active}</button>)}</div>
        </ChartCard>
      </div>

      {data.by_campaign.length > 0 && <ChartCard title="Avance por invasión de origen" subtitle="Toca una invasión para filtrar el panorama" testId="panorama-campaigns">
        <div className="overflow-x-auto"><table className="w-full min-w-[420px] text-sm"><thead><tr className="border-b border-[#E8E5DE] text-left text-xs uppercase tracking-wide text-slate-500"><th className="px-2 py-2">Invasión</th><th className="px-2 py-2">Personas</th><th className="px-2 py-2">En ruta</th><th className="px-2 py-2">Retiro</th><th className="px-2 py-2">Sin atender</th></tr></thead>
          <tbody>{data.by_campaign.map((row) => <tr key={row.campaign_id} className="border-b border-[#F1EFEA]"><td className="px-2 py-1"><button type="button" onClick={() => set({ campaign_id: row.campaign_id, period: 'invasion' })} className="min-h-10 text-left font-semibold text-[#101D36] underline">{row.name}</button></td><td className="px-2">{row.total}</td><td className="px-2">{row.in_route}</td><td className="px-2">{row.retreat}</td><td className={`px-2 ${row.unattended ? 'font-semibold text-amber-800' : ''}`}>{row.unattended}</td></tr>)}</tbody></table></div>
      </ChartCard>}

      <MetricList metric={open} filters={listFilters} onClose={() => setOpen(null)} />
    </section>
  );
}
