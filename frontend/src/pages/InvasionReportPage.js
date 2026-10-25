import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Download, Lock, Printer } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { InvasionHousesMap } from '../components/outreach/InvasionHousesMap';
import { LessonsBlock, RecommendationsBlock } from '../components/invasions/ReportRecommendations';
import { downloadCsv } from '../lib/csv';
import { DoorReport } from '../components/doors/DoorReport';
import { COLORS, ChartCard, Donut, GoalBar, HBars, Lines, PALETTE, VBars, semaphoreStyle } from '../components/invasions/reportCharts';

const STATE = { upcoming: 'Próxima', active: 'En curso', finished: 'Terminada (sin cerrar)', closed: 'Cerrada' };
const fmtDate = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
const pct = (value) => (value == null ? 'Sin datos' : `${value}%`);
const ratio = (part, total) => (total ? Math.round((part / total) * 100) : null);

function Section({ title, children, csv, className = '', testId }) {
  return (
    <section className={`print-break-avoid min-w-0 rounded-2xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:p-5 ${className}`} data-testid={testId}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-['Spectral'] text-xl font-semibold text-[#101D36]">{title}</h2>
        {csv && <button type="button" onClick={csv} className="inline-flex min-h-10 items-center gap-1 rounded-md border border-[#D9D4C7] px-3 text-xs font-semibold text-[#101D36] print:hidden"><Download className="h-3.5 w-3.5" />CSV</button>}
      </div>
      {children}
    </section>
  );
}

const Tile = ({ label, value, hint }) => <div className="rounded-xl border border-[#EEECE6] bg-[#FBFAF7] p-3"><p className="text-2xl font-semibold text-[#101D36]">{value}</p><p className="text-xs text-slate-600">{label}</p>{hint && <p className="text-[11px] text-slate-400">{hint}</p>}</div>;

function Table({ columns, rows, empty = 'Sin datos todavía' }) {
  if (!rows?.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-sm">
        <thead><tr className="border-b border-[#E8E5DE] text-left text-xs uppercase tracking-wide text-slate-500">{columns.map(([key, label]) => <th key={key} className="px-2 py-2 font-semibold">{label}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={row.key || index} className="border-b border-[#F1EFEA]">{columns.map(([key, , render]) => <td key={key} className="px-2 py-2 text-[#101D36]">{render ? render(row) : row[key] ?? '—'}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

// A quién entregó cada mentor cada libro (mismo detalle que el Informe anterior).
function BookDeliveries({ campaignId, books }) {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState('');
  const [rows, setRows] = useState({});
  const toggle = async (row) => {
    const key = `${row.mentor_person_id}-${row.book_id}`;
    if (open === key) { setOpen(''); return; }
    setOpen(key);
    if (rows[key]) return;
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/books/${row.book_id}/deliveries`, { ...getAuthHeaders(), params: { mentor_person_id: row.mentor_person_id } });
      setRows((current) => ({ ...current, [key]: response.data.items || [] }));
    } catch (error) { setRows((current) => ({ ...current, [key]: null })); }
  };
  return (
    <div className="mt-2 space-y-1 print:hidden">
      {books.filter((row) => row.delivered > 0).map((row) => { const key = `${row.mentor_person_id}-${row.book_id}`; return (
        <div key={key}>
          <button type="button" onClick={() => toggle(row)} className="min-h-10 text-left text-xs font-semibold text-[#101D36] underline">Entregas de {row.mentor_name} · {row.book_name}</button>
          {open === key && (rows[key] === null ? <p className="text-xs text-slate-500">Sin permiso para ver a quién se entregó.</p> : <ul className="ml-3 list-disc text-xs text-slate-600">{(rows[key] || []).map((item, index) => <li key={index}>{item.person_name || item.recipient_name || 'Persona'}{item.quantity ? ` · ${item.quantity}` : ''}</li>)}</ul>)}
        </div>
      ); })}
    </div>
  );
}

export default function InvasionReportPage() {
  const { campaignId } = useParams();
  const navigate = useNavigate();
  const { API, getAuthHeaders, user } = useAuth();
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [closing, setClosing] = useState(false);
  const load = useCallback(() => {
    axios.get(`${API}/api/invasions/${campaignId}/report`, getAuthHeaders()).then((response) => setReport(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar el reporte')));
  }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { load(); }, [load]);
  const finalize = async () => {
    if (!window.confirm('¿Cerrar la invasión y generar el Reporte final? Las cifras quedarán congeladas.')) return;
    setClosing(true);
    try { setReport((await axios.post(`${API}/api/invasions/${campaignId}/report/finalize`, {}, getAuthHeaders())).data); toast.success('Reporte final generado'); } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo cerrar la invasión')); } finally { setClosing(false); }
  };

  if (error) return <div className="p-6"><p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p></div>;
  if (!report) return <div className="p-6 text-sm text-slate-500">Cargando reporte…</div>;
  const s = report.summary; const figures = s.key_figures;
  const header = (
    <header className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <button type="button" onClick={() => navigate(-1)} className="inline-flex min-h-10 items-center gap-1 text-sm text-slate-500 print:hidden"><ArrowLeft className="h-4 w-4" />Volver</button>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7A5F22]">Reporte de invasión</p>
        <h1 className="font-['Spectral'] text-3xl font-semibold text-[#101D36]">{s.name}</h1>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-sm">
          <span className={`rounded-full border px-3 py-0.5 text-xs font-semibold ${report.mode === 'final' ? 'border-[#101D36] bg-[#101D36] text-white' : 'border-amber-200 bg-amber-50 text-amber-800'}`} data-testid="report-mode">{report.mode === 'final' ? <><Lock className="mr-1 inline h-3 w-3" />Reporte final · {fmtDate(report.frozen_at)}</> : 'En curso · datos vivos'}</span>
          <span className="text-slate-500">{STATE[s.state] || s.state}</span>
        </p>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:flex print:hidden">
        <button type="button" onClick={() => window.print()} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-[#D9D4C7] bg-white px-4 text-sm font-semibold text-[#101D36]" data-testid="report-print"><Printer className="h-4 w-4" />Imprimir / PDF</button>
        {report.can_finalize && <button type="button" onClick={finalize} disabled={closing} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#101D36] px-4 text-sm font-semibold text-white" data-testid="report-finalize"><Lock className="h-4 w-4" />Cerrar invasión y generar reporte final</button>}
      </div>
    </header>
  );

  if (report.scope === 'personal') {
    const mine = report.mine;
    return (
      <div className="mx-auto w-full max-w-5xl space-y-4 p-4 sm:p-6" data-testid="invasion-report-personal">
        {header}
        <Section title="Mi reporte">
          {mine ? <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Tile label="Personas alcanzadas" value={mine.people} /><Tile label="Casas visitadas" value={`${mine.houses_visited} de ${mine.houses}`} />
            <Tile label="Quieren seguimiento" value={mine.wants_followup} /><Tile label="Iniciaron 7 Semanas" value={mine.seven_weeks} />
          </div> : <p className="text-sm text-slate-500">Todavía no registraste actividad en esta invasión.</p>}
          {report.position && <p className="mt-3 text-sm text-slate-600">Puesto {report.position} de {report.mentors_total} mentores.</p>}
        </Section>
      </div>
    );
  }

  const field = report.field; const part = report.participation; const follow = report.followup; const prayer = report.prayer;
  // Embudo: cada paso se compara con su base real (personas con personas; las casas no se mezclan).
  const funnelSteps = [
    ['Invitados', figures.participants, null], ['Confirmados', figures.confirmed, 'Invitados'], ['Asistieron', figures.attended, 'Invitados'],
    ['Casas visitadas', figures.houses_visited, null], ['Personas alcanzadas', figures.people_reached, null], ['Quieren seguimiento', figures.wants_followup, 'Personas alcanzadas'],
    ['Pasaron a Consolidación', figures.to_consolidation, 'Quieren seguimiento'], ['Ruta iniciada (MCD)', figures.route_started, 'Pasaron a Consolidación'],
  ];
  const stepValue = Object.fromEntries(funnelSteps.map(([name, value]) => [name, value || 0]));
  const funnel = funnelSteps.map(([name, value, base], index) => ({ name, value: value || 0, color: PALETTE[index % PALETTE.length],
    label: `${value || 0}${base ? ` (${stepValue[base] ? Math.round(((value || 0) / stepValue[base]) * 100) : 0}%)` : ''}` }));
  const attendanceTitle = figures.attendance_pct == null ? 'Asistencia: aún sin invitados' : `${figures.attendance_pct}% de los invitados asistió`;
  const roleRows = part.by_role.filter((row) => row.invited).map((row) => ({ name: row.label, Confirmados: row.confirmed, 'Sin responder': row.no_response, 'No participará': row.declined, Asistieron: row.attended }));
  const groupRows = part.by_group.map((row) => ({ name: row.name, value: row.attendance_pct ?? 0, label: `${pct(row.attendance_pct)} (${row.attended}/${row.invited})` }));
  const bestGroup = part.by_group.find((row) => row.attendance_pct > 0);
  const mentors = report.ranking.mentors.slice(0, 10).map((row) => ({ name: row.name, value: row.score, label: `${row.score} pts · ${row.people} pers.` }));
  const teams = report.ranking.teams.map((row) => ({ name: row.name, value: row.score, label: `${row.score} pts` }));
  const results = [
    { name: 'Quieren seguimiento', value: field.results.wants_followup, color: COLORS.green }, { name: 'Mi Conexión con Dios', value: field.results.received_mcd, color: COLORS.blue },
    { name: 'Nací para Triunfar', value: field.results.received_npt, color: COLORS.teal }, { name: 'LBS pendiente', value: field.results.lbs_pending, color: COLORS.amber },
    { name: 'Iniciaron 7 Semanas', value: field.results.seven_weeks, color: COLORS.violet },
    { name: 'Sin respuesta (intentos)', value: (field.attempts_by_result.find((row) => row.result === 'no_answer') || {}).total || 0, color: COLORS.slate },
  ];
  const topSector = field.by_sector[0];
  const days = field.by_day.map((row) => ({ name: fmtDate(row.day).replace(/ de \d{4}| \d{4}/, ''), 'Intentos en casas': row.attempts, 'Personas alcanzadas': row.people }));
  const unattendedTitle = follow.unattended ? `${follow.unattended} persona(s) SIN atender por más de ${follow.unattended_hours} h` : follow.wants_followup ? 'Todas las personas con seguimiento fueron atendidas' : 'Aún sin personas para dar seguimiento';
  const comparison = report.comparison.map((row) => ({ name: row.current ? `${row.name} (esta)` : row.name, Personas: row.people, Seguimiento: row.followup, 'Asistencia %': row.attendance_pct ?? 0 }));
  const previousAvg = report.comparison.filter((row) => !row.current);
  const avgPeople = previousAvg.length ? Math.round(previousAvg.reduce((sum, row) => sum + row.people, 0) / previousAvg.length) : null;
  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-4 p-4 sm:p-6 print:max-w-none print:p-0" data-testid="invasion-report">
      {header}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Section title="1. Resumen ejecutivo" className="xl:col-span-2" testId="report-summary" csv={() => downloadCsv(`resumen-${s.name}.csv`, [{ invasion: s.name, inicio: s.start_date, fin: s.end_date, lugar: s.location, proposito: s.purpose, organizador: s.organizer, encargado_general: s.general_lead, estado: STATE[s.state], ...figures }])}>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
            <div className="space-y-3">
              <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
                {[['Fechas', `${fmtDate(s.start_date)} → ${fmtDate(s.end_date)}`], ['Lugar', s.location], ['Propósito', s.purpose], ['Organizador', s.organizer], ['Encargado general', s.general_lead], ['Logística', s.logistics_lead]].map(([label, value]) => <div key={label} className="flex flex-col"><dt className="text-xs text-slate-500">{label}</dt><dd className="font-medium text-[#101D36]">{value || '—'}</dd></div>)}
              </dl>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="report-key-figures">
                <Tile label="Casas visitadas" value={figures.houses_visited} hint={`de ${figures.houses_total}`} />
                <Tile label="Personas alcanzadas" value={figures.people_reached} />
                <Tile label="Quieren seguimiento" value={figures.wants_followup} />
                <Tile label="Iniciaron 7 Semanas" value={figures.seven_weeks} />
                <Tile label="Asistencia" value={pct(figures.attendance_pct)} hint={`${figures.attended} de ${figures.participants}`} />
                <Tile label="Metas cumplidas" value={report.goals.overall == null ? 'Sin datos' : `${Math.round(report.goals.overall * 100)}%`} hint={semaphoreStyle(report.goals.overall_semaphore).label} />
              </div>
            </div>
            <ChartCard title={figures.participants ? `De ${figures.participants} invitados, ${figures.attended} asistieron y ${figures.route_started} personas iniciaron la ruta` : 'Embudo de la invasión'} subtitle="Total y (%): confirmados y asistieron sobre invitados; quieren seguimiento sobre personas alcanzadas; Consolidación sobre quieren seguimiento; ruta sobre Consolidación." testId="report-funnel">
              <HBars data={funnel} labelKey="label" colors={funnel.map((row) => row.color)} height={320} />
            </ChartCard>
          </div>
        </Section>

        <Section title="2. Participación" testId="report-participation" csv={() => downloadCsv(`participacion-${s.name}.csv`, [...part.by_role.map((row) => ({ grupo: `Rol: ${row.label}`, invitados: row.invited, confirmados: row.confirmed, no_participaran: row.declined, sin_responder: row.no_response, asistieron: row.attended, asistencia_pct: row.attendance_pct })), ...part.by_group.map((row) => ({ grupo: `Grupo: ${row.name}`, invitados: row.invited, confirmados: row.confirmed, no_participaran: row.declined, sin_responder: row.no_response, asistieron: row.attended, asistencia_pct: row.attendance_pct }))])}>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
            <Tile label="Invitados" value={part.totals.invited} /><Tile label="Confirmados" value={part.totals.confirmed} /><Tile label="No participarán" value={part.totals.declined} /><Tile label="Asistieron" value={part.totals.attended} /><Tile label="% asistencia" value={pct(part.totals.attendance_pct)} />
          </div>
          <div className="grid grid-cols-1 gap-3">
            <ChartCard title={attendanceTitle} testId="report-attendance-donut"><Donut data={[{ name: 'Asistieron', value: part.totals.attended, color: COLORS.green }, { name: 'Confirmados que no asistieron', value: Math.max(part.totals.confirmed - part.totals.attended, 0), color: COLORS.amber }, { name: 'Sin responder', value: part.totals.no_response, color: COLORS.slate }, { name: 'No participarán', value: part.totals.declined, color: COLORS.red }]} center={{ value: pct(part.totals.attendance_pct), label: 'asistencia' }} /></ChartCard>
            <ChartCard title="Respuesta por rol" subtitle="Barras apiladas: confirmados, sin responder y no participará; asistieron aparte." testId="report-roles"><VBars data={roleRows} series={[{ key: 'Confirmados', label: 'Confirmados', color: COLORS.blue, stack: 'respuesta' }, { key: 'Sin responder', label: 'Sin responder', color: COLORS.slate, stack: 'respuesta' }, { key: 'No participará', label: 'No participará', color: COLORS.red, stack: 'respuesta' }, { key: 'Asistieron', label: 'Asistieron', color: COLORS.green }]} /></ChartCard>
            <ChartCard title={bestGroup ? `${bestGroup.name} tuvo la mayor asistencia (${pct(bestGroup.attendance_pct)})` : 'Asistencia por Grupo Frontal'} testId="report-groups"><HBars data={groupRows} labelKey="label" max={100} color={COLORS.teal} /></ChartCard>
          </div>
          <p className="mb-1 mt-3 text-sm font-semibold">Detalle por rol</p>
          <Table columns={[['label', 'Rol'], ['invited', 'Invitados'], ['confirmed', 'Confirmados'], ['declined', 'No'], ['attended', 'Asistieron'], ['attendance_pct', '%', (row) => pct(row.attendance_pct)]]} rows={part.by_role.filter((row) => row.invited)} />
          <p className="mt-2 text-[11px] text-slate-500">La pastora/pastor general supervisa y no cuenta en estas cifras.</p>
        </Section>

        <Section title="Ranking de mentores y equipos" testId="report-ranking" csv={() => downloadCsv(`mentores-${s.name}.csv`, report.ranking.mentors.map((row, index) => ({ puesto: index + 1, mentor: row.name, grupo: row.front_group, casas: row.houses, casas_visitadas: row.houses_visited, intentos: row.attempts, personas: row.people, seguimiento: row.wants_followup, siete_semanas: row.seven_weeks, puntaje: row.score })))}>
          <div className="grid grid-cols-1 gap-3">
            <ChartCard title={report.ranking.mentors[0]?.score ? `${report.ranking.mentors[0].name} lidera con ${report.ranking.mentors[0].score} puntos` : 'Ranking de mentores'} subtitle="Puntaje = personas × 3 + casas visitadas × 2 + quieren seguimiento × 2 + 7 Semanas × 3." testId="report-mentor-ranking"><HBars data={mentors} labelKey="label" color={COLORS.blue} /></ChartCard>
            <ChartCard title={report.ranking.teams[0]?.score ? `El equipo ${report.ranking.teams[0].name} va primero` : 'Ranking de equipos'} testId="report-team-ranking"><HBars data={teams} labelKey="label" color={COLORS.violet} /></ChartCard>
          </div>
          <Table columns={[['pos', '#', (row) => report.ranking.mentors.indexOf(row) + 1], ['name', 'Mentor'], ['people', 'Personas'], ['houses_visited', 'Casas'], ['wants_followup', 'Seguim.'], ['score', 'Puntaje']]} rows={report.ranking.mentors.slice(0, 15)} empty="Sin actividad de mentores todavía" />
        </Section>

        <Section title="3. Resultados de campo" className="xl:col-span-2" testId="report-field" csv={() => downloadCsv(`sectores-${s.name}.csv`, field.by_sector.map((row) => ({ sector: row.sector, casas: row.houses, visitadas: row.visited, cobertura_pct: row.coverage_pct, personas: row.people })))}>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-6">
            <Tile label="Disponibles" value={field.houses.available} /><Tile label="Asignadas" value={field.houses.assigned} /><Tile label="Visitadas" value={field.houses.visited} /><Tile label="En el mapa" value={`${field.houses.located} de ${field.houses.total}`} /><Tile label="Personas alcanzadas" value={figures.people_reached} /><Tile label="Quieren seguimiento" value={field.results.wants_followup} />
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
            <ChartCard title={days.length ? `${days.reduce((sum, row) => sum + row['Personas alcanzadas'], 0)} personas alcanzadas en ${days.length} día(s)` : 'Visitas por jornada'} testId="report-days"><Lines data={days} series={[{ key: 'Intentos en casas', label: 'Intentos en casas', color: COLORS.slate }, { key: 'Personas alcanzadas', label: 'Personas alcanzadas', color: COLORS.blue }]} /></ChartCard>
            <ChartCard title={field.houses.total ? `${ratio(field.houses.visited, field.houses.total)}% de las casas fue visitada` : 'Casas de la invasión'} testId="report-houses"><HBars data={[{ name: 'Disponibles', value: field.houses.available, color: COLORS.amber }, { name: 'Asignadas', value: field.houses.assigned, color: COLORS.blue }, { name: 'Visitadas', value: field.houses.visited, color: COLORS.green }]} /></ChartCard>
            <ChartCard title={field.results.wants_followup ? `${field.results.wants_followup} persona(s) quieren seguimiento` : 'Resultados de las visitas'} testId="report-results"><Donut data={results} /></ChartCard>
            <ChartCard title={topSector ? `${topSector.sector}: ${topSector.people} personas alcanzadas (${pct(topSector.coverage_pct)} de cobertura)` : 'Por sector'} subtitle="Casas, casas visitadas y personas por sector." testId="report-sectors"><VBars data={field.by_sector.map((row) => ({ name: row.sector, Casas: row.houses, Visitadas: row.visited, Personas: row.people }))} series={[{ key: 'Casas', label: 'Casas', color: COLORS.slate }, { key: 'Visitadas', label: 'Visitadas', color: COLORS.green }, { key: 'Personas', label: 'Personas', color: COLORS.blue }]} /></ChartCard>
            <div className="min-w-0 lg:col-span-2 print:hidden">
              <ChartCard title="Mapa de casas por resultado" subtitle="Filtra por mentor o sector; toca un punto para ver la casa."><InvasionHousesMap campaigns={[{ campaign_id: campaignId, name: s.name, assigned_mentor_ids: [] }]} mentorPersonId={user?.person_id} colorBy="result" fixedHeight={460} /></ChartCard>
            </div>
          </div>
          <p className="mb-1 mt-3 text-sm font-semibold">Detalle por sector</p>
          <Table columns={[['sector', 'Sector'], ['houses', 'Casas'], ['visited', 'Visitadas'], ['coverage_pct', 'Cobertura', (row) => pct(row.coverage_pct)], ['people', 'Personas']]} rows={field.by_sector} />
          {field.doors && <div className="mt-5" data-testid="report-doors">
            <p className="mb-2 text-base font-semibold text-[#101D36]">Puerta a puerta: viviendas, intentos y libros</p>
            <DoorReport campaignId={campaignId} data={field.doors} live={report.mode !== 'final'} fileTag={s.name.replace(/\s+/g, '-')} />
          </div>}
        </Section>

        <Section title="4. Seguimiento y Consolidación" className="xl:col-span-2" testId="report-followup" csv={() => downloadCsv(`seguimiento-${s.name}.csv`, [...follow.first_contact.map((row) => ({ indicador: `Primer contacto ${row.bucket}`, total: row.total })), ...follow.routes.map((row) => ({ indicador: `Llegaron a ${row.route}`, total: row.total })), { indicador: 'Pasaron a Consolidación', total: follow.to_consolidation }, { indicador: 'Con mentor asignado', total: follow.assigned_mentor }, { indicador: 'Transferidas', total: follow.transferred }, { indicador: `Sin atender > ${follow.unattended_hours} h`, total: follow.unattended }])}>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
            <Tile label="Quieren seguimiento" value={follow.wants_followup} /><Tile label="Pasaron a Consolidación" value={follow.to_consolidation} /><Tile label="Con mentor asignado" value={follow.assigned_mentor} /><Tile label="Transferidas" value={follow.transferred} />
            <div className={`rounded-xl border p-3 ${follow.unattended ? 'border-red-300 bg-red-50' : 'border-[#EEECE6] bg-[#FBFAF7]'}`} data-testid="report-unattended"><p className={`text-2xl font-semibold ${follow.unattended ? 'text-red-700' : 'text-[#101D36]'}`}>{follow.unattended}</p><p className="text-xs text-slate-600">SIN atender (&gt; {follow.unattended_hours} h)</p></div>
            <Tile label="Atendidas" value={follow.attended} />
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-4">
            <ChartCard title={unattendedTitle} testId="report-attended-donut"><Donut data={[{ name: 'Atendidas', value: follow.attended, color: COLORS.green }, { name: `Sin atender (> ${follow.unattended_hours} h)`, value: follow.unattended, color: COLORS.red }, { name: 'Recientes, aún en plazo', value: follow.pending_recent, color: COLORS.amber }]} /></ChartCard>
            <ChartCard title="Tiempo hasta el primer contacto" subtitle="Desde la visita hasta la primera actividad de consolidación realizada." testId="report-first-contact"><HBars data={follow.first_contact.map((row) => ({ name: row.bucket, value: row.total, color: row.bucket === 'Sin contacto' ? COLORS.red : COLORS.teal }))} /></ChartCard>
            <ChartCard title={follow.to_consolidation ? `${follow.routes[0].total} de ${follow.to_consolidation} llegaron a MCD` : 'Conversión por ruta'} testId="report-routes"><HBars data={follow.routes.map((row, index) => ({ name: row.route, value: row.total, color: [COLORS.blue, COLORS.teal, COLORS.violet][index] }))} /></ChartCard>
            <ChartCard title="Personas que pasaron a Consolidación por día" testId="report-consolidation-days"><Lines data={follow.consolidation_by_day.map((row) => ({ name: fmtDate(row.day).replace(/ de \d{4}| \d{4}/, ''), Personas: row.total }))} series={[{ key: 'Personas', label: 'Personas', color: COLORS.violet }]} /></ChartCard>
          </div>
        </Section>

        {prayer && <Section title="5. Preparación en oración" testId="report-prayer" csv={() => downloadCsv(`oracion-${s.name}.csv`, [...prayer.by_week.map((row) => ({ periodo: row.week, desde: row.from, hasta: row.to, oraron: row.prayed, pct: row.pct })), ...prayer.meetings.map((row) => ({ periodo: `Reunión ${row.day}`, desde: row.day, hasta: row.day, oraron: row.attendees, pct: row.pct }))])}>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Tile label="Oraron al menos un día" value={pct(prayer.totals.prayed_any_pct)} hint={`${prayer.totals.prayed_any} de ${prayer.totals.participants}`} />
            <Tile label="Promedio de días" value={prayer.totals.avg_days ?? 'Sin datos'} hint={`de ${prayer.period.total_days}`} />
            <Tile label="Asistencia a reuniones" value={pct(prayer.totals.meeting_attendance_pct)} hint={`${prayer.totals.meetings_held} realizada(s)`} />
            <Tile label="Necesitaron seguimiento" value={prayer.totals.needs_followup} />
          </div>
          <div className="grid grid-cols-1 gap-3">
            <ChartCard title={prayer.totals.prayed_any_pct == null ? 'Oración por semana' : `${prayer.totals.prayed_any_pct}% de los participantes oró`} subtitle="% de participantes que registró oración en cada semana." testId="report-prayer-weeks"><HBars data={prayer.by_week.map((row) => ({ name: row.week, value: row.pct, label: `${row.pct}% (${row.prayed})` }))} labelKey="label" max={100} color={COLORS.gold} /></ChartCard>
            <ChartCard title="Asistencia a reuniones de oración" testId="report-prayer-meetings"><HBars data={prayer.meetings.map((row) => ({ name: fmtDate(row.day), value: row.pct || 0, label: `${row.pct ?? 0}% (${row.attendees})` }))} labelKey="label" max={100} color={COLORS.teal} /></ChartCard>
          </div>
        </Section>}

        <Section title="6. Metas vs resultado real" testId="report-goals" csv={() => downloadCsv(`metas-${s.name}.csv`, report.goals.items.map((row) => ({ indicador: row.label, real: row.value, meta: row.goal, avance_pct: row.progress == null ? '' : Math.round(row.progress * 100), semaforo: semaphoreStyle(row.semaphore).label, detalle: row.explanation })))}>
          <p className="mb-2 text-sm font-semibold" style={{ color: semaphoreStyle(report.goals.overall_semaphore).color }}>{report.goals.overall == null ? 'Aún sin datos para medir las metas' : `Avance general: ${Math.round(report.goals.overall * 100)}% de las metas (${semaphoreStyle(report.goals.overall_semaphore).label})`}</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">{report.goals.items.map((item) => <GoalBar key={item.key} item={item} />)}</div>
          <p className="mt-2 text-[11px] text-slate-500">{report.goals.rule}</p>
        </Section>

        <Section title="7. Comparativo con invasiones anteriores" className="xl:col-span-2" testId="report-comparison" csv={() => downloadCsv(`comparativo-${s.name}.csv`, report.comparison.map((row) => ({ invasion: row.name, inicio: row.start_date, personas: row.people, seguimiento: row.followup, asistencia_pct: row.attendance_pct })))}>
          {report.comparison.length > 1
            ? <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                <ChartCard title={avgPeople != null ? `${figures.people_reached} personas alcanzadas vs. ${avgPeople} de promedio en las anteriores` : 'Personas y seguimiento'} testId="report-compare-people"><VBars data={comparison} series={[{ key: 'Personas', label: 'Personas alcanzadas', color: COLORS.blue }, { key: 'Seguimiento', label: 'Quieren seguimiento', color: COLORS.green }]} /></ChartCard>
                <ChartCard title="Asistencia de invitados (%)" testId="report-compare-attendance"><VBars data={comparison} series={[{ key: 'Asistencia %', label: 'Asistencia %', color: COLORS.teal }]} format={(value) => `${value}%`} /></ChartCard>
              </div>
            : <p className="text-sm text-slate-500">Aún no hay invasiones anteriores para comparar.</p>}
          <Table columns={[['name', 'Invasión'], ['start_date', 'Inicio', (row) => fmtDate(row.start_date)], ['people', 'Personas'], ['followup', 'Seguimiento'], ['attendance_pct', 'Asistencia', (row) => pct(row.attendance_pct)]]} rows={report.comparison.map((row) => ({ ...row, key: row.campaign_id }))} />
        </Section>

        <Section title="8. Recomendaciones" className="xl:col-span-2" testId="report-recommendations" csv={() => downloadCsv(`recomendaciones-${s.name}.csv`, (report.recommendations || []).map((row) => ({ prioridad: row.priority, recomendacion: row.title, detalle: row.detail, evidencia: row.evidence.label, valor: row.evidence.value, base: row.evidence.total ?? '', pct: row.evidence.pct ?? '', responsable: row.responsible, regla: row.rule, resuelta: row.resolved ? 'sí' : 'no', nota: row.resolved_note || '' })))}>
          <RecommendationsBlock key={`rec-${report.mode}`} campaignId={campaignId} items={report.recommendations} />
        </Section>

        <Section title="Lecciones aprendidas" className="xl:col-span-2" testId="report-lessons-section">
          <LessonsBlock key={`notes-${report.mode}`} campaignId={campaignId} notes={report.notes} />
        </Section>

        {report.help_alerts && <Section title="Alertas de ayuda" testId="report-help" csv={() => downloadCsv(`alertas-${s.name}.csv`, report.help_alerts.items.map((row) => ({ persona: row.person_name, motivo: row.reason_label, nota: row.note || '', hora: row.created_at, estado: row.status, respuesta_min: row.response_minutes ?? '', atendio: row.acknowledged_by_name || '', resolvio: row.resolved_by_name || '' })))}>
          {report.help_alerts.total === 0 ? <p className="text-sm text-slate-500">No hubo alertas de ayuda.</p> : <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Tile label="Alertas" value={report.help_alerts.total} /><Tile label="Resueltas" value={report.help_alerts.resolved} />
              <Tile label="Sin resolver" value={report.help_alerts.open} /><Tile label="Respuesta promedio" value={report.help_alerts.avg_response_minutes == null ? '—' : `${report.help_alerts.avg_response_minutes} min`} />
            </div>
            <div className="mt-3"><Table columns={[['person_name', 'Persona'], ['reason_label', 'Motivo'], ['created_at', 'Hora', (row) => new Date(row.created_at).toLocaleString('es', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })], ['response_minutes', 'Respuesta', (row) => (row.response_minutes == null ? 'Sin atender' : `${row.response_minutes} min`)], ['resolved_by_name', 'Resolvió']]} rows={report.help_alerts.items.map((row) => ({ ...row, key: row.alert_id }))} /></div>
          </>}
        </Section>}

        {report.books?.length > 0 && <Section title="Libros por mentor" testId="report-books" csv={() => downloadCsv(`libros-${s.name}.csv`, report.books.map((row) => ({ mentor: row.mentor_name, libro: row.book_name, asignados: row.assigned, entregados: row.delivered, le_quedan: row.remaining })))}>
          <Table columns={[['mentor_name', 'Mentor'], ['book_name', 'Libro'], ['assigned', 'Asignados'], ['delivered', 'Entregados'], ['remaining', 'Le quedan']]} rows={report.books.map((row) => ({ ...row, key: `${row.mentor_person_id}-${row.book_id}` }))} />
          <BookDeliveries campaignId={campaignId} books={report.books} />
        </Section>}
      </div>
      <p className="text-center text-[11px] text-slate-400">{report.mode === 'final' ? `Reporte final congelado el ${fmtDate(report.frozen_at)}.` : 'Datos vivos: cambian mientras la invasión siga abierta.'}</p>
    </div>
  );
}
