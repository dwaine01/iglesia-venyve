import React, { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Search } from 'lucide-react';

const pct = (value) => (value == null ? '' : `${value}%`);
const yes = (value) => (value ? 'Sí' : 'No');

/** Las tablas de la sección 9 (las mismas van al Excel, una hoja por tabla). */
export function reportTables(report) {
  const doorsByMentor = Object.fromEntries((report.field?.doors?.by_mentor || []).map((row) => [row.mentor_person_id, row]));
  const teams = Object.fromEntries((report.ranking?.teams || []).map((row) => [row.front_group_id || '', row]));
  return [
    {
      key: 'mentors', name: 'Por mentor',
      columns: [['name', 'Mentor'], ['front_group', 'Grupo Frontal'], ['houses_visited', 'Viviendas visitadas'], ['attempts', 'Intentos'], ['opened', 'Abrieron'], ['books', 'Libros'],
        ['people', 'Personas alcanzadas'], ['wants_followup', 'Quieren seguimiento'], ['seven_weeks', 'Iniciaron 7 Semanas'], ['attended', 'Asistió']],
      rows: (report.ranking?.mentors || []).map((row) => ({ ...row, opened: doorsByMentor[row.person_id]?.opened ?? 0, books: doorsByMentor[row.person_id]?.books ?? 0, attended: yes(row.attended) })),
    },
    {
      key: 'groups', name: 'Por Grupo Frontal',
      columns: [['name', 'Grupo Frontal'], ['invited', 'Invitados'], ['confirmed', 'Confirmados'], ['attended', 'Asistieron'], ['attendance_pct', 'Asistencia %'], ['people', 'Personas alcanzadas'], ['houses_visited', 'Viviendas visitadas']],
      rows: (report.participation?.by_group || []).map((row) => ({ ...row, people: teams[row.front_group_id || '']?.people ?? 0, houses_visited: teams[row.front_group_id || '']?.houses_visited ?? 0 })),
      format: { attendance_pct: pct },
    },
    {
      key: 'sectors', name: 'Por sector',
      columns: [['sector', 'Sector'], ['houses', 'Casas'], ['visited', 'Visitadas'], ['coverage_pct', 'Cobertura %'], ['people', 'Personas']],
      rows: report.field?.by_sector || [], format: { coverage_pct: pct },
    },
    {
      key: 'attendance', name: 'Asistencia',
      columns: [['label', 'Rol'], ['invited', 'Invitados'], ['confirmed', 'Confirmados'], ['declined', 'No pueden'], ['no_response', 'Sin respuesta'], ['attended', 'Asistieron'], ['attendance_pct', 'Asistencia %']],
      rows: report.participation?.by_role || [], format: { attendance_pct: pct },
    },
    {
      key: 'attendance_days', name: 'Asistencia por jornada',
      columns: [['day', 'Jornada'], ['attended', 'Asistieron'], ['invited', 'Invitados'], ['pct', 'Asistencia %']],
      rows: report.participation?.by_day || [], format: { pct },
    },
    {
      key: 'people', name: 'Personas alcanzadas',
      columns: [['name', 'Persona'], ['mentor', 'Mentor'], ['sector', 'Sector'], ['address', 'Dirección'], ['status', 'Estado'], ['followup', 'Seguimiento'], ['next_action', 'Próxima acción'], ['consolidation', 'En Consolidación'], ['date', 'Fecha']],
      rows: (report.people_reached || []).map((row) => ({ ...row, followup: yes(row.followup), consolidation: yes(row.consolidation) })),
    },
  ];
}

function DataTable({ table }) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState({ key: null, dir: 1 });
  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = needle ? table.rows.filter((row) => table.columns.some(([key]) => String(row[key] ?? '').toLowerCase().includes(needle))) : table.rows;
    if (!sort.key) return filtered;
    return [...filtered].sort((a, b) => {
      const left = a[sort.key]; const right = b[sort.key];
      if (typeof left === 'number' || typeof right === 'number') return ((left ?? -Infinity) - (right ?? -Infinity)) * sort.dir;
      return String(left ?? '').localeCompare(String(right ?? ''), 'es') * sort.dir;
    });
  }, [table, query, sort]);
  const toggle = (key) => setSort((current) => ({ key, dir: current.key === key ? -current.dir : (typeof table.rows[0]?.[key] === 'number' ? -1 : 1) }));
  if (!table.rows.length) return <p className="text-sm text-slate-500">Aún sin datos.</p>;
  return (
    <div className="space-y-2">
      <label className="relative block print:hidden">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar en la tabla" className="h-11 w-full rounded-lg border border-[#D9D4C7] bg-white pl-9 pr-3 text-[15px]" data-testid={`report-table-search-${table.key}`} />
      </label>
      <div className="overflow-x-auto rounded-xl border border-[#EEECE6] print:overflow-visible">
        <table className="w-full min-w-[640px] text-sm print:min-w-0" data-testid={`report-table-${table.key}`}>
          <thead><tr className="border-b border-[#E8E5DE] bg-[#FBFAF7] text-left text-xs text-slate-600">
            {table.columns.map(([key, label]) => <th key={key} className="px-2 py-2"><button type="button" onClick={() => toggle(key)} className="min-h-9 text-left font-semibold">{label} {sort.key === key ? (sort.dir > 0 ? <ArrowUp className="inline h-3 w-3" /> : <ArrowDown className="inline h-3 w-3" />) : null}</button></th>)}
          </tr></thead>
          <tbody>{rows.map((row, index) => <tr key={row.visit_id || row.person_id || row.front_group_id || row.sector || row.role || row.day || index} className="border-b border-[#F1EFEA]">
            {table.columns.map(([key]) => <td key={key} className="px-2 py-1.5 text-[#101D36]">{table.format?.[key] ? table.format[key](row[key]) : (row[key] ?? '—')}</td>)}
          </tr>)}</tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">{rows.length} de {table.rows.length} fila(s)</p>
    </div>
  );
}

/** Sección 9 · Tablas ordenables y con búsqueda. En el PDF salen todas, una tras otra. */
export function ReportTables({ report }) {
  const tables = reportTables(report);
  const [active, setActive] = useState(tables[0].key);
  return (
    <div className="space-y-3" data-testid="report-tables">
      <div className="flex flex-wrap gap-1 rounded-xl bg-[#EEECE6] p-1 print:hidden" role="tablist">
        {tables.map((table) => <button key={table.key} type="button" role="tab" aria-selected={active === table.key} onClick={() => setActive(table.key)} className={`min-h-11 rounded-lg px-3 text-sm font-semibold ${active === table.key ? 'bg-white shadow' : 'text-slate-600'}`} data-testid={`report-tables-tab-${table.key}`}>{table.name} ({table.rows.length})</button>)}
      </div>
      {tables.map((table) => (
        <div key={table.key} className={`${active === table.key ? '' : 'hidden'} print:block`}>
          <p className="mb-1 hidden text-base font-semibold text-[#101D36] print:block">{table.name}</p>
          <DataTable table={table} />
        </div>
      ))}
    </div>
  );
}
