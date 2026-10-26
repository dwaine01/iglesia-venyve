import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowDownRight, ArrowUpRight, BarChart3, BookOpen, CalendarCheck, CalendarDays, FileSpreadsheet, Footprints, GraduationCap, HelpCircle, Landmark, Loader2, Minus, MonitorPlay, Network, Printer, Sprout, TriangleAlert } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { downloadXlsx } from '../lib/xlsx';
import { StatsPresenter, unitText } from '../components/StatsPresenter';
import { LeaderWorkDetail } from '../components/LeaderWorkDetail';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';

/* Centro de Estadísticas Globales (G1): resumen de la iglesia, Consolidación y
 * asistencia. Cada cifra sale de la misma fuente que su módulo (el backend lo
 * agrega); cada tarjeta dice cómo se calcula, su unidad y su fuente, y si no hay
 * datos dice por qué. La pastora no cuenta en participación. */

const PERIODS = [['today', 'Hoy'], ['week', 'Semana'], ['month', 'Mes'], ['quarter', 'Trimestre'], ['year', 'Año'], ['custom', 'Rango']];
const SECTIONS = [['summary', 'Resumen de la iglesia', BarChart3], ['consolidation', 'Consolidación', Sprout], ['attendance', 'Asistencia', CalendarCheck], ['finance', 'Finanzas', Landmark], ['activities', 'Proyectos y actividades', CalendarDays], ['invasions', 'Invasiones', Footprints], ['books', 'Libros', BookOpen], ['groups', 'Grupos Frontales', Network], ['education', 'Educación y procesos', GraduationCap]];
const SERVICES = [['all', 'Todos'], ['sunday', 'Domingo'], ['wednesday', 'Miércoles'], ['special', 'Actividades especiales'], ['cell', 'Células']];
const fmt = (value) => (value == null ? '' : typeof value === 'number' ? value.toLocaleString('es') : value);
const usd = (value) => (value == null ? '—' : value.toLocaleString('es-US', { style: 'currency', currency: 'USD' }));
const fmtDate = (iso) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('es', { day: 'numeric', month: 'long', year: 'numeric' }) : '');

function Change({ pct }) {
  if (pct == null) return null;
  const Icon = pct > 0 ? ArrowUpRight : pct < 0 ? ArrowDownRight : Minus;
  return <span className="inline-flex items-center gap-0.5 text-sm font-semibold text-[#132443]" title="Comparado con el período anterior de igual duración"><Icon className="h-4 w-4" />{pct > 0 ? '+' : ''}{pct} % vs. período anterior</span>;
}

/** Tarjeta: cifra grande, qué mide, cambio vs. período anterior y «¿Cómo se calcula?». */
function StatCard({ item }) {
  const [help, setHelp] = useState(false);
  return (
    <article className="flex flex-col rounded-2xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid={`gs-card-${item.key}`}>
      <p className="text-[15px] font-semibold text-[#101D36]">{item.label}</p>
      {item.empty_reason
        ? <p className="mt-2 text-[15px] text-slate-600" data-testid="gs-empty-reason">{item.empty_reason}</p>
        : <p className="mt-1"><span className="text-4xl font-bold text-[#132443]">{item.unit === 'USD' ? usd(item.value) : (fmt(item.value) || 0)}</span>{item.unit && item.unit !== 'USD' && <span className="ml-1.5 text-[15px] text-slate-600">{unitText(item.value, item.unit)}</span>}</p>}
      {!item.empty_reason && <Change pct={item.change_pct} />}
      {item.previous != null && !item.empty_reason && <p className="text-sm text-slate-500">Período anterior: {item.unit === 'USD' ? usd(item.previous) : fmt(item.previous)}</p>}
      <div className="mt-auto flex flex-wrap items-center gap-3 pt-3">
        <button type="button" onClick={() => setHelp((value) => !value)} aria-expanded={help} className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-[#7A5F22]" data-testid="gs-help"><HelpCircle className="h-4 w-4" />¿Cómo se calcula?</button>
        {item.link && <Link to={item.link} className="text-sm font-semibold text-[#0879BE] underline">Ver en el módulo</Link>}
      </div>
      {help && <p className="mt-1 rounded-lg bg-[#FBFAF7] p-2 text-sm text-slate-700" data-testid="gs-definition">{item.definition} <b>Fuente:</b> {item.source}.</p>}
    </article>
  );
}

const Cards = ({ items }) => <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">{items.map((item) => <StatCard key={item.key} item={item} />)}</div>;
const Panel = ({ title, note, children, testId }) => (
  <section className="rounded-2xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid={testId}>
    <h3 className="font-['Spectral'] text-xl font-semibold text-[#101D36]">{title}</h3>
    {note && <p className="mt-0.5 text-sm text-slate-600">{note}</p>}
    <div className="mt-3">{children}</div>
  </section>
);

/** Barras horizontales con la etiqueta completa y el valor escrito. */
function Bars({ rows, empty, color = '#1F5FA8', suffix = '' }) {
  const top = Math.max(1, ...rows.map((row) => row.value || 0));
  if (!rows.length || rows.every((row) => !row.value)) return <p className="text-[15px] text-slate-600">{empty}</p>;
  return (
    <ul className="space-y-2">{rows.map((row) => (
      <li key={row.label} className="grid grid-cols-[minmax(0,38%)_minmax(0,1fr)_auto] items-center gap-3">
        <span className="text-[15px] text-[#101D36]">{row.label}</span>
        <span className="h-4 overflow-hidden rounded bg-[#EEEAE0]"><span className="block h-full rounded" style={{ width: `${row.value ? Math.max(2, (row.value / top) * 100) : 0}%`, background: row.color || color }} /></span>
        <span className="text-[15px] font-semibold text-[#101D36]">{fmt(row.value)}{suffix}</span>
      </li>
    ))}</ul>
  );
}

/** Tabla simple, nombres completos y valores alineados. */
function Table({ columns, rows, empty, testId }) {
  if (!rows.length) return <p className="text-[15px] text-slate-600">{empty}</p>;
  return (
    <div className="overflow-x-auto"><table className="w-full min-w-[520px] text-[15px]" data-testid={testId}>
      <thead><tr className="border-b border-[#E8E5DE] text-left text-sm text-slate-600">{columns.map(([key, label]) => <th key={key} className="px-2 py-2 font-semibold">{label}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={row.id || row.label || index} className="border-b border-[#F1EFEA]">{columns.map(([key, , render]) => <td key={key} className="px-2 py-2 text-[#101D36]">{render ? render(row) : (row[key] ?? '—')}</td>)}</tr>)}</tbody>
    </table></div>
  );
}

function SummarySection({ data }) {
  return (
    <div className="space-y-4">
      <Cards items={data.cards} />
      {data.finance_note && <p className="rounded-xl border border-[#E8E5DE] bg-[#FBFAF7] p-3 text-[15px] text-slate-700">{data.finance_note}</p>}
    </div>
  );
}

function FinanceSection({ data }) {
  const kinds = Array.from(new Set(data.trend.flatMap((row) => Object.keys(row).filter((key) => !['bucket', 'label', 'total'].includes(key)))));
  return (
    <div className="space-y-4">
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-[15px] text-amber-900" data-testid="gs-finance-privacy">{data.notes.privacy}</p>
      <Cards items={data.cards} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Ingresos por concepto" note="Contribuciones del período por concepto, comparadas con el período anterior." testId="gs-finance-types">
          <Table columns={[['label', 'Concepto'], ['amount', 'Este período', (row) => usd(row.amount)], ['previous', 'Período anterior', (row) => usd(row.previous)], ['change', 'Cambio', (row) => (row.change_pct == null ? '—' : `${row.change_pct > 0 ? '+' : ''}${row.change_pct} %`)]]} rows={data.by_type} empty="Aún no se han registrado contribuciones en este período." />
        </Panel>
        <Panel title="Gastos por categoría" note="Gastos aprobados o pagados con fecha en el período."><Bars rows={data.expenses_by_category.map((row) => ({ label: row.label, value: row.amount }))} color="#A35A00" empty="Aún no se han registrado gastos aprobados en este período." /></Panel>
      </div>
      <Panel title={`Tendencia por ${data.trend_unit}`} note="Contribuciones por concepto.">
        <Table columns={[['label', data.trend_unit === 'mes' ? 'Mes' : 'Semana'], ...kinds.map((key) => [key, key, (row) => usd(row[key] || 0)]), ['total', 'Total', (row) => usd(row.total)]]} rows={data.trend} empty="Aún no se han registrado contribuciones en este período." />
      </Panel>
      <Panel title="Proyectos y campañas" note="Meta y presupuesto de cada proyecto de Finanzas; recaudado y gastado en toda su duración." testId="gs-projects">
        <Table columns={[['name', 'Proyecto'], ['type', 'Tipo'], ['goal', 'Meta', (row) => usd(row.goal)], ['raised', 'Recaudado', (row) => `${usd(row.raised)}${row.goal_pct != null ? ` (${row.goal_pct} %)` : ''}`], ['budget', 'Presupuesto', (row) => usd(row.budget)], ['spent', 'Gastado', (row) => `${usd(row.spent)}${row.budget_pct != null ? ` (${row.budget_pct} %)` : ''}`]]} rows={data.projects} empty="Todavía no hay proyectos ni campañas registrados en Finanzas." />
      </Panel>
      <p className="text-sm text-slate-600">{data.notes.basis}</p>
    </div>
  );
}

function InvasionsSection({ data }) {
  return (
    <div className="space-y-4">
      <Cards items={data.cards} />
      <Panel title="Comparar invasiones" note={data.notes.compare} testId="gs-invasions">
        <Table columns={[['name', 'Invasión'], ['houses_visited', 'Viviendas visitadas'], ['people_reached', 'Personas alcanzadas'], ['wants_followup', 'Quieren seguimiento'], ['to_consolidation', 'Pasaron a Consolidación'], ['books', 'Libros'],
          ['attendance', 'Asistencia', (row) => (row.participants ? `${row.attended} de ${row.participants}${row.attendance_pct != null ? ` (${row.attendance_pct} %)` : ''}` : '—')],
          ['links', 'Ver', (row) => <span className="flex flex-wrap gap-2"><Link to={row.report} className="font-semibold text-[#0879BE] underline">Reporte</Link><Link to={row.present} className="font-semibold text-[#0879BE] underline">Presentar</Link></span>]]} rows={data.items} empty="No hubo invasiones en este período." />
      </Panel>
    </div>
  );
}

function BooksSection({ data }) {
  return (
    <div className="space-y-4">
      <Cards items={data.cards} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Por mentor" note={data.notes.balances} testId="gs-books-mentors"><Table columns={[['name', 'Mentor'], ['received', 'Recibidos'], ['delivered', 'Entregados'], ['available', 'Disponibles']]} rows={data.by_mentor} empty="Ningún mentor ha recibido libros." /></Panel>
        <Panel title="Entregados por invasión (en el período)"><Bars rows={data.by_campaign.map((row) => ({ label: row.name, value: row.delivered }))} color="#A35A00" empty="No se entregaron libros en este período." /></Panel>
      </div>
    </div>
  );
}

function GroupsSection({ data }) {
  const [work, setWork] = useState(null);
  return (
    <div className="space-y-4">
      <Cards items={data.cards} />
      <Panel title={data.root ? `Ramas de ${data.root.name}` : 'Ramas del árbol'} note={data.notes.branches} testId="gs-branches">
        <Table columns={[['name', 'Rama'], ['leader', 'Líder'], ['status', 'Estado'], ['people', 'Personas en la rama'], ['progress', 'Avance', (row) => (row.progress == null ? '—' : `${row.progress} %`)],
          ['work', 'Trabajo', (row) => (row.leader_person_id ? <button type="button" onClick={() => setWork({ person_id: row.leader_person_id, name: row.leader })} className="font-semibold text-[#0879BE] underline">Ver el trabajo del líder</button> : '—')]]} rows={data.branches} empty="Todavía no hay equipos en el grupo de la pastora." />
        <Link to="/grupo-frontal?tab=ramas" className="mt-3 inline-flex min-h-11 items-center text-[15px] font-semibold text-[#0879BE] underline">Abrir el árbol completo (Mis ramas)</Link>
      </Panel>
      <Panel title="Líderes sin actividad en el período" note={data.notes.work} testId="gs-idle">
        {data.idle_leaders.length === 0 ? <p className="text-[15px] text-slate-600">Todos los líderes registraron actividad en el período.</p> : (
          <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">{data.idle_leaders.map((row) => <li key={row.person_id} className="flex items-center justify-between gap-2 rounded-lg border border-[#F1EFEA] px-3 py-2 text-[15px]"><span>{row.name}</span><button type="button" onClick={() => setWork(row)} className="text-sm font-semibold text-[#0879BE] underline">Ver su trabajo</button></li>)}</ul>
        )}
      </Panel>
      <Dialog open={Boolean(work)} onOpenChange={(value) => { if (!value) setWork(null); }}>
        <DialogContent className="max-h-[90vh] overflow-y-auto bg-white sm:max-w-4xl"><DialogHeader><DialogTitle>Trabajo de {work?.name}</DialogTitle><DialogDescription>Hoy, esta semana y total.</DialogDescription></DialogHeader>{work && <LeaderWorkDetail mentorPersonId={work.person_id} />}</DialogContent>
      </Dialog>
    </div>
  );
}

function ActivitiesSection({ data }) {
  const columns = [['title', 'Actividad'], ['type', 'Tipo'], ['starts_at', 'Fecha y hora'], ['registered', 'Inscritos'], ['attended', 'Asistentes'], ['volunteers', 'Voluntarios', (row) => (row.volunteers_needed ? `${row.volunteers} de ${row.volunteers_needed}` : row.volunteers)]];
  return (
    <div className="space-y-4">
      <Cards items={data.cards} />
      <Panel title="Por tipo de actividad" note="Actividades realizadas y asistentes en el período."><Table columns={[['label', 'Tipo'], ['activities', 'Actividades'], ['attended', 'Asistentes']]} rows={data.by_type} empty="No hay actividades en este período." /></Panel>
      <Panel title="Actividades del período" testId="gs-activities-done"><Table columns={columns} rows={data.done} empty="No hay actividades programadas en este período." /></Panel>
      <Panel title="Próximas actividades (30 días)"><Table columns={columns} rows={data.upcoming} empty="No hay actividades programadas en los próximos 30 días." /></Panel>
      <p className="text-sm text-slate-600">{data.notes.projects}</p>
    </div>
  );
}

function ConsolidationSection({ data }) {
  return (
    <div className="space-y-4">
      <Cards items={data.cards} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Embudo de Consolidación" note={data.notes.funnel} testId="gs-funnel"><Bars rows={data.funnel.map((row) => ({ label: row.label, value: row.value }))} color="#6B3FA0" empty="Todavía no hay expedientes de Consolidación." /></Panel>
        <Panel title="Personas activas por etapa" note="Expedientes activos según la etapa en la que están hoy."><Bars rows={data.by_stage.map((row) => ({ label: row.label, value: row.active }))} color="#0E5B5A" empty="No hay expedientes activos." /></Panel>
        <Panel title="Tiempo promedio por etapa" note={data.notes.stage_times}><Table columns={[['label', 'Etapa'], ['average_days', 'Días promedio', (row) => `${fmt(row.average_days)} días`], ['completed', 'Etapas cerradas']]} rows={data.stage_times} empty="Todavía no hay etapas cerradas para calcular tiempos." /></Panel>
        <Panel title="Carga por mentor" note={`Personas en Consolidación ahora (planificadas, activas o en pausa) por mentor. Promedio: ${fmt(data.mentor_load.average)} por mentor.`}><Table columns={[['name', 'Mentor'], ['active', 'En Consolidación'], ['above', 'Atención', (row) => (row.above_average ? 'Más del doble del promedio' : '—')]]} rows={data.mentor_load.items} empty="Ningún mentor tiene personas en Consolidación." /></Panel>
        <Panel title="Por Grupo Frontal" note="Personas activas según el Grupo Frontal del expediente."><Table columns={[['name', 'Grupo Frontal'], ['active', 'En Consolidación']]} rows={data.by_group} empty="No hay expedientes activos." /></Panel>
        <Panel title="Por invasión de origen" note="Personas que entraron a Consolidación desde cada invasión."><Table columns={[['name', 'Invasión'], ['total', 'Personas'], ['in_route', 'En ruta MCD o más'], ['retreat', 'Llegaron al Retiro'], ['unattended', 'Sin atender']]} rows={data.by_campaign} empty="Ningún expediente viene de una invasión todavía." /></Panel>
      </div>
      <Panel title="Últimas 8 semanas" note="Expedientes nuevos y actividades realizadas por semana."><Table columns={[['label', 'Semana del'], ['new', 'Expedientes nuevos'], ['activities', 'Actividades realizadas']]} rows={data.trend} empty="Sin actividad en las últimas semanas." /></Panel>
    </div>
  );
}

const SERIES_GROUPS = [['week', 'Por semana'], ['month', 'Por mes'], ['year', 'Por año']];

/** G1b: asistencia por semana, mes o año (calendario de Nueva York). */
function AttendanceSeries() {
  const { API, getAuthHeaders } = useAuth();
  const [group, setGroup] = useState('week');
  const [series, setSeries] = useState(null);
  useEffect(() => {
    setSeries(null);
    axios.get(`${API}/api/global-stats/attendance/series`, { ...getAuthHeaders(), params: { group } }).then((response) => setSeries(response.data)).catch(() => setSeries({ points: [] }));
  }, [API, getAuthHeaders, group]);
  return (
    <Panel title="Asistencia por semana, mes y año" note={series?.definition || 'Asistencias por período y por tipo de servicio.'} testId="gs-attendance-series">
      <div className="mb-3 flex flex-wrap gap-2">{SERIES_GROUPS.map(([key, label]) => (
        <button key={key} type="button" onClick={() => setGroup(key)} className={`min-h-11 rounded-lg border px-4 text-[15px] font-semibold ${group === key ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-[#101D36]'}`} data-testid={`gs-series-${key}`}>{label}</button>
      ))}</div>
      {!series ? <Loader2 className="h-5 w-5 animate-spin text-slate-400" /> : (
        <Table columns={[['label', group === 'week' ? 'Semana del' : group === 'month' ? 'Mes' : 'Año'], ['total', 'Asistencias'], ['unique_people', 'Personas distintas'], ['service_average', 'Promedio por servicio', (row) => (row.service_average == null ? '—' : fmt(row.service_average))],
          ['sunday', 'Domingo'], ['wednesday', 'Miércoles'], ['special', 'Actividades especiales'], ['cell', 'Células']]} rows={[...series.points].reverse()} empty="Sin asistencias registradas." />
      )}
    </Panel>
  );
}

function AttendanceSection({ data }) {
  return (
    <div className="space-y-4">
      <Cards items={data.cards} />
      <Panel title="Por tipo de servicio" note={data.notes.service} testId="gs-by-service">
        <Table columns={[['label', 'Servicio'], ['sessions', 'Servicios o reuniones'], ['attendance', 'Asistencias'], ['average', 'Promedio por servicio', (row) => (row.average == null ? 'Sin registros' : fmt(row.average))], ['unique_people', 'Personas distintas'],
          ['change', 'Cambio del promedio', (row) => (row.change_pct == null ? '—' : `${row.change_pct > 0 ? '+' : ''}${row.change_pct} %`)]]} rows={data.by_service.filter((row) => row.sessions || row.previous_average != null)} empty="Aún no se ha registrado asistencia en este período." />
      </Panel>
      <AttendanceSeries />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Ausentes frecuentes" note="Asistían con regularidad y no han venido en las últimas 3 semanas." testId="gs-absent">
          {data.frequent_absent.length === 0 ? <p className="text-[15px] text-slate-600">No hay personas que hayan dejado de asistir.</p> : (
            <ul className="divide-y divide-[#F1EFEA]">{data.frequent_absent.map((row) => <li key={row.person_id} className="flex items-center justify-between gap-2 py-2 text-[15px]"><Link to={`/personas/${row.person_id}`} className="font-semibold text-[#0879BE] underline">{row.name}</Link><span className="text-slate-600">{row.previous_attendance} asistencias antes</span></li>)}</ul>
          )}
        </Panel>
        <Panel title="Asistencia a invasiones" note={data.notes.invasions}>
          <Table columns={[['name', 'Invasión'], ['invited', 'Invitados'], ['attended', 'Asistieron'], ['attendance_pct', 'Asistencia', (row) => (row.attendance_pct == null ? '—' : `${row.attendance_pct} %`)]]} rows={data.invasions} empty="No hubo invasiones en este período." />
        </Panel>
      </div>
    </div>
  );
}

function sheetsFor(section, data) {
  const cards = { name: 'Indicadores', columns: [['label', 'Indicador'], ['value', 'Valor'], ['unit', 'Unidad'], ['previous', 'Período anterior'], ['change_pct', 'Cambio %'], ['definition', 'Cómo se calcula'], ['source', 'Fuente'], ['empty_reason', 'Motivo si no hay datos']], rows: data.cards };
  if (section === 'consolidation') return [cards, { name: 'Embudo', columns: [['label', 'Paso'], ['value', 'Personas']], rows: data.funnel }, { name: 'Por etapa', columns: [['label', 'Etapa'], ['active', 'Activas']], rows: data.by_stage },
    { name: 'Tiempo por etapa', columns: [['label', 'Etapa'], ['average_days', 'Días promedio'], ['completed', 'Etapas cerradas']], rows: data.stage_times }, { name: 'Por mentor', columns: [['name', 'Mentor'], ['active', 'En Consolidación']], rows: data.mentor_load.items },
    { name: 'Por Grupo Frontal', columns: [['name', 'Grupo Frontal'], ['active', 'En Consolidación']], rows: data.by_group }, { name: 'Por invasión', columns: [['name', 'Invasión'], ['total', 'Personas'], ['in_route', 'En ruta MCD o más'], ['retreat', 'Retiro'], ['unattended', 'Sin atender']], rows: data.by_campaign }];
  if (section === 'attendance') return [cards, { name: 'Por servicio', columns: [['label', 'Servicio'], ['sessions', 'Servicios'], ['attendance', 'Asistencias'], ['average', 'Promedio'], ['unique_people', 'Personas distintas']], rows: data.by_service },
    { name: 'Tendencia', columns: [['label', 'Semana del'], ['sunday', 'Domingo'], ['wednesday', 'Miércoles'], ['special', 'Actividades especiales'], ['cell', 'Células']], rows: data.trend },
    { name: 'Ausentes frecuentes', columns: [['name', 'Persona'], ['previous_attendance', 'Asistencias anteriores']], rows: data.frequent_absent }, { name: 'Invasiones', columns: [['name', 'Invasión'], ['invited', 'Invitados'], ['attended', 'Asistieron'], ['attendance_pct', 'Asistencia %']], rows: data.invasions }];
  if (section === 'finance') return [cards, { name: 'Por concepto', columns: [['label', 'Concepto'], ['amount', 'Este período (USD)'], ['previous', 'Período anterior (USD)'], ['change_pct', 'Cambio %']], rows: data.by_type },
    { name: 'Gastos por categoría', columns: [['label', 'Categoría'], ['amount', 'USD']], rows: data.expenses_by_category }, { name: 'Tendencia', columns: Object.keys(data.trend[0] || { label: '', total: 0 }).filter((key) => key !== 'bucket').map((key) => [key, key === 'label' ? 'Período' : key === 'total' ? 'Total (USD)' : `${key} (USD)`]), rows: data.trend },
    { name: 'Proyectos', columns: [['name', 'Proyecto'], ['type', 'Tipo'], ['goal', 'Meta (USD)'], ['raised', 'Recaudado (USD)'], ['goal_pct', 'Recaudado %'], ['budget', 'Presupuesto (USD)'], ['spent', 'Gastado (USD)'], ['budget_pct', 'Gastado %']], rows: data.projects }];
  if (section === 'invasions') return [cards, { name: 'Invasiones', columns: [['name', 'Invasión'], ['start_date', 'Inicio'], ['end_date', 'Fin'], ['houses_visited', 'Viviendas visitadas'], ['people_reached', 'Personas alcanzadas'], ['wants_followup', 'Quieren seguimiento'], ['to_consolidation', 'Pasaron a Consolidación'], ['books', 'Libros'], ['attended', 'Asistieron'], ['participants', 'Invitados']], rows: data.items }];
  if (section === 'books') return [cards, { name: 'Por mentor', columns: [['name', 'Mentor'], ['received', 'Recibidos'], ['delivered', 'Entregados'], ['available', 'Disponibles']], rows: data.by_mentor }, { name: 'Por invasión', columns: [['name', 'Invasión'], ['delivered', 'Entregados']], rows: data.by_campaign }];
  if (section === 'groups') return [cards, { name: 'Ramas', columns: [['name', 'Rama'], ['leader', 'Líder'], ['status', 'Estado'], ['people', 'Personas'], ['progress', 'Avance %']], rows: data.branches }, { name: 'Líderes sin actividad', columns: [['name', 'Líder']], rows: data.idle_leaders }];
  if (section === 'activities') return [cards, { name: 'Realizadas', columns: [['title', 'Actividad'], ['type', 'Tipo'], ['starts_at', 'Fecha y hora'], ['registered', 'Inscritos'], ['attended', 'Asistentes'], ['volunteers', 'Voluntarios'], ['volunteers_needed', 'Voluntarios requeridos']], rows: data.done },
    { name: 'Próximas', columns: [['title', 'Actividad'], ['type', 'Tipo'], ['starts_at', 'Fecha y hora'], ['registered', 'Inscritos']], rows: data.upcoming }];
  return [cards];
}

export default function GlobalStatsPage() {
  const { API, getAuthHeaders } = useAuth();
  const [params, setParams] = useSearchParams();
  const [access, setAccess] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [presenting, setPresenting] = useState(false);
  const period = PERIODS.some(([key]) => key === params.get('periodo')) ? params.get('periodo') : 'month';
  const service = params.get('servicio') || 'all';
  const [range, setRange] = useState({ from: params.get('desde') || '', to: params.get('hasta') || '' });
  const allowed = useMemo(() => SECTIONS.filter(([key]) => access?.sections?.[key]), [access]);
  const section = allowed.some(([key]) => key === params.get('seccion')) ? params.get('seccion') : allowed[0]?.[0];
  const setParam = (changes) => { const next = new URLSearchParams(params); Object.entries(changes).forEach(([key, value]) => { if (value) next.set(key, value); else next.delete(key); }); setParams(next, { replace: true }); };

  useEffect(() => { axios.get(`${API}/api/global-stats/access`, getAuthHeaders()).then((response) => setAccess(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'Sin acceso a las Estadísticas Globales'))); }, [API, getAuthHeaders]);
  const load = useCallback(() => {
    if (!section || (period === 'custom' && (!params.get('desde') || !params.get('hasta')))) return;
    setData(null);
    const query = { period, ...(period === 'custom' ? { date_from: params.get('desde'), date_to: params.get('hasta') } : {}), ...(section === 'attendance' ? { service } : {}) };
    axios.get(`${API}/api/global-stats/${section}`, { ...getAuthHeaders(), params: query }).then((response) => setData({ section, ...response.data })).catch((requestError) => setData({ section, error: apiErrorMessage(requestError, 'No se pudo cargar esta sección') }));
  }, [API, getAuthHeaders, section, period, service, params]);
  useEffect(() => { load(); }, [load]);

  const exportExcel = () => { if (data && !data.error) downloadXlsx(`estadisticas-${section}-${data.period.from}-a-${data.period.to}.xlsx`, sheetsFor(section, data)); };

  return (
    <div className="min-h-screen bg-[#F8F6F0] pb-10" data-testid="global-stats-page">
      <header className="bg-gradient-to-r from-[#14213D] via-[#1B2A4A] to-[#0E5B5A] px-4 py-6 text-white sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-[1600px]">
          <p className="text-xs font-semibold uppercase tracking-widest text-[#E7D28D]">Administración</p>
          <h1 className="mt-1 font-['Spectral'] text-3xl font-bold">Estadísticas Globales</h1>
          <p className="mt-1 text-[15px] text-white/80">Toda la iglesia en un solo lugar. Cada cifra sale del mismo módulo que la registra; toca «¿Cómo se calcula?» para ver su definición.</p>
        </div>
      </header>
      <div className="mx-auto w-full max-w-[1600px] space-y-4 px-4 py-4 sm:px-6 lg:px-8">
        {error && <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-[15px] text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
        {!access && !error && <div className="flex justify-center py-16"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>}
        {access && <>
          <div className="flex flex-wrap gap-1 rounded-xl bg-[#EEECE6] p-1" role="tablist" data-testid="gs-sections">
            {allowed.map(([key, label, Icon]) => <button key={key} type="button" role="tab" aria-selected={section === key} onClick={() => setParam({ seccion: key })} className={`inline-flex min-h-12 items-center gap-2 rounded-lg px-4 text-[15px] font-semibold ${section === key ? 'bg-white text-[#101D36] shadow' : 'text-slate-600'}`} data-testid={`gs-section-${key}`}><Icon className="h-4 w-4" />{label}</button>)}
          </div>
          <div className="flex flex-wrap items-end gap-3 rounded-xl border border-[#E8E5DE] bg-white p-3" data-testid="gs-filters">
            <div><p className="text-sm font-semibold text-slate-700">Período</p>
              <div className="mt-1 flex flex-wrap gap-1">{PERIODS.map(([key, label]) => <button key={key} type="button" onClick={() => setParam({ periodo: key })} aria-pressed={period === key} className={`min-h-11 rounded-full border px-3 text-[15px] font-semibold ${period === key ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-[#101D36]'}`} data-testid={`gs-period-${key}`}>{label}</button>)}</div></div>
            {period === 'custom' && <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); setParam({ desde: range.from, hasta: range.to }); }}>
              <label className="text-sm font-semibold text-slate-700">Desde<input type="date" value={range.from} onChange={(event) => setRange((current) => ({ ...current, from: event.target.value }))} className="mt-1 block h-11 rounded-lg border border-[#D9D4C7] px-2 text-[15px]" /></label>
              <label className="text-sm font-semibold text-slate-700">Hasta<input type="date" value={range.to} onChange={(event) => setRange((current) => ({ ...current, to: event.target.value }))} className="mt-1 block h-11 rounded-lg border border-[#D9D4C7] px-2 text-[15px]" /></label>
              <button type="submit" className="min-h-11 rounded-lg bg-[#132443] px-4 text-[15px] font-semibold text-white">Aplicar</button>
            </form>}
            {section === 'attendance' && <label className="text-sm font-semibold text-slate-700">Servicio<select value={service} onChange={(event) => setParam({ servicio: event.target.value === 'all' ? null : event.target.value })} className="mt-1 block h-11 rounded-lg border border-[#D9D4C7] bg-white px-2 text-[15px]" data-testid="gs-service">{SERVICES.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>}
            <div className="ml-auto flex flex-wrap gap-2">
              <button type="button" onClick={exportExcel} disabled={!data || data.error} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-[#D9D4C7] bg-white px-3 text-[15px] font-semibold text-[#101D36] disabled:opacity-50" data-testid="gs-excel"><FileSpreadsheet className="h-4 w-4" />Excel de esta sección</button>
              <button type="button" onClick={() => window.print()} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-[#D9D4C7] bg-white px-3 text-[15px] font-semibold text-[#101D36]"><Printer className="h-4 w-4" />PDF</button>
              <button type="button" onClick={() => setPresenting(true)} disabled={!data || data.error} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg bg-[#C8A951] px-3 text-[15px] font-bold text-[#14213D] disabled:opacity-50" data-testid="gs-present"><MonitorPlay className="h-4 w-4" />Presentar</button>
            </div>
          </div>
          {data?.period && <p className="text-[15px] text-slate-700" data-testid="gs-period-label">{data.period.label}: del {fmtDate(data.period.from)} al {fmtDate(data.period.to)} · comparado con el {fmtDate(data.period.previous_from)} al {fmtDate(data.period.previous_to)}. No incluye a la pastora ni las cuentas de prueba en participación.</p>}
          {period === 'custom' && (!params.get('desde') || !params.get('hasta')) && <p className="text-[15px] text-slate-600">Elige las fechas «Desde» y «Hasta» y toca «Aplicar».</p>}
          {!data && section && !(period === 'custom' && (!params.get('desde') || !params.get('hasta'))) && <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>}
          {data?.error && <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{data.error}</p>}
          {data && !data.error && data.section === 'summary' && <SummarySection data={data} />}
          {data && !data.error && data.section === 'consolidation' && <ConsolidationSection data={data} />}
          {data && !data.error && data.section === 'attendance' && <AttendanceSection data={data} />}
          {data && !data.error && data.section === 'finance' && <FinanceSection data={data} />}
          {data && !data.error && data.section === 'activities' && <ActivitiesSection data={data} />}
          {data && !data.error && data.section === 'invasions' && <InvasionsSection data={data} />}
          {data && !data.error && data.section === 'books' && <BooksSection data={data} />}
          {data && !data.error && data.section === 'groups' && <GroupsSection data={data} />}
          {data && !data.error && data.section === 'education' && <Cards items={data.cards} />}
          {presenting && data && !data.error && <StatsPresenter title={SECTIONS.find(([key]) => key === section)?.[1] || 'Estadísticas'} periodText={`${data.period.label}: del ${fmtDate(data.period.from)} al ${fmtDate(data.period.to)}`} cards={data.cards} onClose={() => setPresenting(false)} />}
        </>}
      </div>
    </div>
  );
}
