import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { ArrowDown, ArrowUp, Download, Loader2, Search } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { downloadCsv } from '../../lib/csv';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { COLORS, ChartCard, HBars } from '../invasions/reportCharts';
import { DOOR_STATUS } from './DoorStats';

// Cifras sin duplicados: la vivienda cuenta una vez; los intentos van aparte.
// `drill` = se puede tocar para ver las viviendas que la componen.
const COLUMNS = [
  { key: 'houses_visited', label: 'Viviendas visitadas', short: 'Viviendas', drill: true },
  { key: 'attempts', label: 'Intentos de visita', short: 'Intentos' },
  { key: 'opened', label: 'Abrieron', short: 'Abrieron', drill: true },
  { key: 'not_opened', label: 'No abrieron', short: 'No abrieron', drill: true },
  { key: 'conversed', label: 'Conversaciones', short: 'Convers.', drill: true },
  { key: 'invited_in', label: 'Los invitaron a pasar', short: 'Pasaron', drill: true },
  { key: 'houses_with_books', label: 'Viviendas con libros', short: 'Con libros', drill: true },
  { key: 'books', label: 'Libros entregados', short: 'Libros' },
  { key: 'followup_people', label: 'Aceptaron seguimiento', short: 'Seguim.' },
  { key: 'consolidation', label: 'Iniciaron consolidación', short: 'Consolid.' },
  { key: 'pending_revisit', label: 'Pendientes de nueva visita', short: 'Pendientes', drill: true },
  { key: 'followup_scheduled', label: 'Seguimiento programado', short: 'Programadas', drill: true },
];
const GROUPS = [
  { key: 'by_mentor', label: 'Por mentor', name: 'Mentor', filter: (row) => ({ mentor_person_id: row.mentor_person_id }) },
  { key: 'by_team', label: 'Por equipo', name: 'Equipo', filter: (row) => ({ front_group_id: row.front_group_id }) },
  { key: 'by_street', label: 'Por calle', name: 'Calle', filter: (row) => ({ street_key: row.street_key }) },
];
const when = (iso) => (iso ? new Date(iso).toLocaleString('es', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '');

// Viviendas detrás de una cifra (paginado en el servidor).
function HouseList({ campaignId, open, onClose }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const last = useRef(null);
  if (open) last.current = open;
  const current = open || last.current;
  useEffect(() => {
    if (!open) return;
    setData(null);
    const params = { metric: open.metric, limit: 100, ...Object.fromEntries(Object.entries(open.filter || {}).filter(([, value]) => value != null)) };
    axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/door-report/houses`, { ...getAuthHeaders(), params })
      .then((response) => setData(response.data)).catch(() => setData({ items: [], total: 0 }));
  }, [API, getAuthHeaders, campaignId, open]);
  if (!current) return null;
  return (
    <Dialog open={Boolean(open)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="bg-white sm:max-w-lg" data-testid="door-report-houses">
        <DialogHeader><DialogTitle>{current.title}</DialogTitle><DialogDescription>{data ? `${data.total} vivienda(s)` : 'Cargando…'}</DialogDescription></DialogHeader>
        {!data ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : data.items.length === 0 ? <p className="text-base text-slate-500">Aún sin viviendas.</p> : (
          <ul className="divide-y divide-[#EEECE6]">
            {data.items.map((item) => (
              <li key={item.household_id} className="py-2" data-testid={`door-report-house-${item.household_id}`}>
                <p className="text-base font-semibold text-[#101D36]">{item.address_line1 || item.street_name || 'Vivienda'}{item.address_line2 ? ` · ${item.address_line2}` : ''}</p>
                <p className="text-sm text-slate-600">{DOOR_STATUS[item.door_status]?.label || '—'} · {item.attempts_count} intento(s){item.books_total ? ` · ${item.books_total} libro(s)` : ''}{item.mentor_name ? ` · ${item.mentor_name}` : ''}</p>
                <p className="text-xs text-slate-500">Última visita: {when(item.last_attempt_at)}</p>
              </li>
            ))}
          </ul>
        )}
        {data && data.total > data.items.length && <p className="text-xs text-slate-500">Se muestran las {data.items.length} más recientes.</p>}
      </DialogContent>
    </Dialog>
  );
}

function GroupTable({ group, rows, onDrill, fileName, live }) {
  // «Sin mentor» / «Sin Grupo Frontal» no tienen un filtro exacto: esas cifras no se abren.
  const canDrill = (row) => live && Object.values(group.filter(row)).every((value) => value != null);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState({ key: 'houses_visited', dir: -1 });
  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = needle ? rows.filter((row) => `${row.name} ${row.front_group || ''} ${(row.mentors || []).join(' ')}`.toLowerCase().includes(needle)) : rows;
    return [...filtered].sort((a, b) => (sort.key === 'name' ? a.name.localeCompare(b.name) * sort.dir : ((a[sort.key] || 0) - (b[sort.key] || 0)) * sort.dir || a.name.localeCompare(b.name)));
  }, [rows, query, sort]);
  const toggle = (key) => setSort((current) => ({ key, dir: current.key === key ? -current.dir : key === 'name' ? 1 : -1 }));
  const Arrow = ({ column }) => (sort.key === column ? (sort.dir > 0 ? <ArrowUp className="inline h-3 w-3" /> : <ArrowDown className="inline h-3 w-3" />) : null);
  const csv = () => downloadCsv(fileName, shown.map((row) => ({ [group.name.toLowerCase()]: row.name, ...(row.front_group !== undefined ? { equipo: row.front_group || '' } : {}),
    ...(row.mentors ? { mentores: row.mentors.join(' / ') } : {}), ...Object.fromEntries(COLUMNS.map((column) => [column.label, row[column.key] || 0])), personas: row.people })));
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Buscar ${group.name.toLowerCase()}`} className="h-11 w-full rounded-lg border border-[#D9D4C7] bg-white pl-9 pr-3 text-[15px]" data-testid="door-report-search" />
        </label>
        <button type="button" onClick={csv} className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-[#D9D4C7] bg-white px-3 text-sm font-semibold text-[#101D36] print:hidden" data-testid="door-report-csv"><Download className="h-4 w-4" />CSV</button>
      </div>
      {shown.length === 0 ? <p className="text-sm text-slate-500">Sin datos todavía.</p> : (
        <div className="overflow-x-auto rounded-xl border border-[#EEECE6]">
          <table className="w-full min-w-[900px] text-sm" data-testid={`door-report-table-${group.key}`}>
            <thead>
              <tr className="border-b border-[#E8E5DE] bg-[#FBFAF7] text-left text-xs text-slate-600">
                <th className="sticky left-0 z-10 bg-[#FBFAF7] px-2 py-2"><button type="button" onClick={() => toggle('name')} className="min-h-9 font-semibold">{group.name} <Arrow column="name" /></button></th>
                {COLUMNS.map((column) => <th key={column.key} className="px-1.5 py-2 text-right" title={column.label}><button type="button" onClick={() => toggle(column.key)} className="min-h-9 font-semibold">{column.short} <Arrow column={column.key} /></button></th>)}
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => (
                <tr key={row[group.key === 'by_street' ? 'street_key' : group.key === 'by_team' ? 'front_group_id' : 'mentor_person_id'] || row.name} className="border-b border-[#F1EFEA]">
                  <td className="sticky left-0 z-10 max-w-[180px] bg-white px-2 py-2 text-[#101D36]"><p className="truncate font-semibold">{row.name}</p>{row.front_group && <p className="truncate text-xs text-slate-500">{row.front_group}</p>}{row.mentors?.length > 0 && <p className="truncate text-xs text-slate-500">{row.mentors.join(', ')}</p>}</td>
                  {COLUMNS.map((column) => (
                    <td key={column.key} className="px-1.5 py-1 text-right tabular-nums text-[#101D36]">
                      {column.drill && row[column.key] && canDrill(row) ? <button type="button" onClick={() => onDrill(column, row, group)} className="min-h-9 min-w-9 rounded-md px-1 font-semibold text-[#1d4ed8] underline decoration-dotted underline-offset-2">{row[column.key]}</button> : (row[column.key] || 0)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Reporte de puerta a puerta por mentor, equipo y calle. Si `data` viene del
 * reporte de la invasión se usa tal cual; si no, se pide al servidor (el
 * mentor recibe solo su trabajo). `live=false` (reporte final) desactiva el
 * detalle con clic porque las viviendas pueden haber cambiado. */
export function DoorReport({ campaignId, data: given, live = true, fileTag = 'invasion' }) {
  const { API, getAuthHeaders } = useAuth();
  const [fetched, setFetched] = useState(null);
  const [error, setError] = useState('');
  const [groupKey, setGroupKey] = useState('');
  const [drill, setDrill] = useState(null);
  useEffect(() => {
    if (given || !campaignId) return;
    setFetched(null); setError('');
    axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/door-report`, getAuthHeaders())
      .then((response) => setFetched(response.data)).catch((requestError) => setError(requestError?.response?.data?.detail || 'No se pudo cargar el reporte'));
  }, [API, getAuthHeaders, campaignId, given]);
  const data = given || fetched;
  if (error) return <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-base text-amber-900">{error}</p>;
  if (!data) return <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />;
  const mine = data.scope === 'mine';
  const groups = GROUPS.filter((group) => (mine ? group.key === 'by_street' : true));
  const group = groups.find((item) => item.key === groupKey) || groups[0];
  const totals = data.totals;
  const open = (column, filter = {}, title = column.label) => { if (live && column.drill) setDrill({ metric: column.key, filter, title }); };
  const profile = data.profile || {};
  const knownLanguage = (profile.language || []).reduce((sum, row) => sum + row.total, 0);

  return (
    <div className="space-y-4" data-testid="door-report">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {COLUMNS.map((column) => {
          const clickable = live && column.drill && totals[column.key] > 0;
          const Tag = clickable ? 'button' : 'div';
          return (
            <Tag key={column.key} type={clickable ? 'button' : undefined} onClick={clickable ? () => open(column) : undefined} className={`min-h-[68px] rounded-xl border border-[#E8E5DE] bg-white p-3 text-left shadow-sm ${clickable ? 'active:bg-[#FBFAF7]' : ''}`} data-testid={`door-report-total-${column.key}`}>
              <span className={`block text-2xl font-semibold leading-7 ${clickable ? 'text-[#1d4ed8]' : 'text-[#101D36]'}`}>{totals[column.key] || 0}</span>
              <span className="block text-[13px] leading-4 text-slate-600">{column.label}</span>
            </Tag>
          );
        })}
      </div>
      <p className="text-sm text-slate-600" data-testid="door-report-note">{totals.attempts} intento(s) en {totals.houses_visited} vivienda(s): una vivienda cuenta una vez aunque se visite varias veces; cada apartamento es una vivienda. {totals.people} persona(s) registrada(s).</p>

      <div className={`grid gap-1 rounded-xl bg-[#EEECE6] p-1 ${groups.length === 3 ? 'grid-cols-3' : 'grid-cols-1'}`} role="tablist">
        {groups.map((item) => <button key={item.key} type="button" role="tab" aria-selected={group.key === item.key} onClick={() => setGroupKey(item.key)} className={`min-h-11 rounded-lg text-[15px] font-semibold ${group.key === item.key ? 'bg-white text-[#101D36] shadow' : 'text-slate-600'}`} data-testid={`door-report-group-${item.key}`}>{item.label}</button>)}
      </div>
      <GroupTable key={group.key} group={group} rows={data[group.key] || []} fileName={`puerta-a-puerta-${group.key.replace('by_', '')}-${fileTag}.csv`} live={live}
        onDrill={(column, row) => open(column, group.filter(row), `${column.label} · ${row.name}`)} />

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3" data-testid="door-report-profile">
        <ChartCard title="Idioma" subtitle={knownLanguage ? `${profile.language_confirmed || 0} confirmado(s) · ${profile.language_impression || 0} por impresión. Una vivienda cuenta una vez.` : 'Sin datos de idioma todavía.'}>
          <HBars data={(profile.language || []).map((row) => ({ name: row.label, value: row.total }))} color={COLORS.teal} />
        </ChartCard>
        <ChartCard title="Religión" subtitle={`Solo lo que la persona compartió (${profile.shared_houses || 0} vivienda(s)). Totales, sin nombres.`}>
          <HBars data={(profile.religion || []).map((row) => ({ name: row.label, value: row.total }))} color={COLORS.violet} />
        </ChartCard>
        <ChartCard title="Origen" subtitle="Solo lo que la persona compartió. Totales, sin nombres.">
          <HBars data={(profile.origin || []).map((row) => ({ name: row.label, value: row.total }))} color={COLORS.amber} />
        </ChartCard>
      </div>
      <HouseList campaignId={campaignId} open={drill} onClose={() => setDrill(null)} />
    </div>
  );
}
