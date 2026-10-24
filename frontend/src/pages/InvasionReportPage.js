import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ArrowLeft, Download, Lock, Printer } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { InvasionHousesMap } from '../components/outreach/InvasionHousesMap';

const STATE = { upcoming: 'Próxima', active: 'En curso', finished: 'Terminada (sin cerrar)', closed: 'Cerrada' };
const fmtDate = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
const pct = (value) => (value == null ? 'Sin datos' : `${value}%`);
const ratio = (part, total) => (total ? Math.round((part / total) * 100) : null);

// CSV por sección (Excel lo abre directo; BOM para acentos).
function downloadCsv(filename, rows) {
  if (!rows?.length) { toast.message('No hay datos para exportar'); return; }
  const headers = Object.keys(rows[0]);
  const escape = (value) => { const text = value == null ? '' : String(value); return /[",\n;]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text; };
  const csv = [headers.join(','), ...rows.map((row) => headers.map((key) => escape(row[key])).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

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

function SummaryChart({ figures }) {
  const data = [
    ['Asistencia', figures.attendance_pct], ['Casas visitadas', ratio(figures.houses_visited, figures.houses_total)],
    ['Quieren seguimiento', ratio(figures.wants_followup, figures.people_reached)], ['Iniciaron 7 Semanas', ratio(figures.seven_weeks, figures.people_reached)],
  ].map(([name, value]) => ({ name, value: value ?? 0, label: value == null ? 'Sin datos' : `${value}%` }));
  return (
    <div className="h-56 w-full" data-testid="report-summary-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 40, top: 4, bottom: 4 }}>
          <CartesianGrid horizontal={false} stroke="#EEECE6" />
          <XAxis type="number" domain={[0, 100]} tickFormatter={(value) => `${value}%`} fontSize={11} />
          <YAxis type="category" dataKey="name" width={130} fontSize={12} />
          <Tooltip formatter={(value, name, item) => item.payload.label} />
          <Bar dataKey="value" radius={[0, 6, 6, 0]} isAnimationActive={false}>
            {data.map((item, index) => <Cell key={item.name} fill={['#2f6e47', '#2563eb', '#d97706', '#7A5F22'][index]} />)}
            <LabelList dataKey="label" position="right" fontSize={11} fill="#101D36" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
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

  const field = report.field; const part = report.participation;
  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-4 p-4 sm:p-6 print:max-w-none print:p-0" data-testid="invasion-report">
      {header}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Section title="1. Resumen ejecutivo" className="xl:col-span-2" testId="report-summary" csv={() => downloadCsv(`resumen-${s.name}.csv`, [{ invasion: s.name, inicio: s.start_date, fin: s.end_date, lugar: s.location, proposito: s.purpose, organizador: s.organizer, encargado_general: s.general_lead, estado: STATE[s.state], ...figures }])}>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
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
              </div>
            </div>
            <div><p className="mb-1 text-sm font-semibold text-[#101D36]">Resumen en porcentajes</p><SummaryChart figures={figures} /></div>
          </div>
        </Section>

        <Section title="2. Participación" testId="report-participation" csv={() => downloadCsv(`participacion-${s.name}.csv`, [...part.by_role.map((row) => ({ grupo: `Rol: ${row.label}`, invitados: row.invited, confirmados: row.confirmed, no_participaran: row.declined, sin_responder: row.no_response, asistieron: row.attended, asistencia_pct: row.attendance_pct })), ...part.by_group.map((row) => ({ grupo: `Grupo: ${row.name}`, invitados: row.invited, confirmados: row.confirmed, no_participaran: row.declined, sin_responder: row.no_response, asistieron: row.attended, asistencia_pct: row.attendance_pct }))])}>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
            <Tile label="Invitados" value={part.totals.invited} /><Tile label="Confirmados" value={part.totals.confirmed} /><Tile label="No participarán" value={part.totals.declined} /><Tile label="Asistieron" value={part.totals.attended} /><Tile label="% asistencia" value={pct(part.totals.attendance_pct)} />
          </div>
          <p className="mb-1 text-sm font-semibold">Por rol</p>
          <Table columns={[['label', 'Rol'], ['invited', 'Invitados'], ['confirmed', 'Confirmados'], ['declined', 'No'], ['attended', 'Asistieron'], ['attendance_pct', '%', (row) => pct(row.attendance_pct)]]} rows={part.by_role.filter((row) => row.invited)} />
          <p className="mb-1 mt-3 text-sm font-semibold">Por Grupo Frontal</p>
          <Table columns={[['name', 'Grupo'], ['invited', 'Invitados'], ['confirmed', 'Confirmados'], ['attended', 'Asistieron'], ['attendance_pct', '%', (row) => pct(row.attendance_pct)]]} rows={part.by_group} />
          <p className="mt-2 text-[11px] text-slate-500">La pastora/pastor general supervisa y no cuenta en estas cifras.</p>
        </Section>

        <Section title="Ranking de mentores y equipos" testId="report-ranking" csv={() => downloadCsv(`mentores-${s.name}.csv`, report.ranking.mentors.map((row, index) => ({ puesto: index + 1, mentor: row.name, grupo: row.front_group, casas: row.houses, casas_visitadas: row.houses_visited, intentos: row.attempts, personas: row.people, seguimiento: row.wants_followup, siete_semanas: row.seven_weeks, puntaje: row.score })))}>
          <Table columns={[['pos', '#', (row) => report.ranking.mentors.indexOf(row) + 1], ['name', 'Mentor'], ['people', 'Personas'], ['houses_visited', 'Casas'], ['wants_followup', 'Seguim.'], ['score', 'Puntaje']]} rows={report.ranking.mentors.slice(0, 15)} empty="Sin actividad de mentores todavía" />
          <p className="mb-1 mt-3 text-sm font-semibold">Equipos (Grupos Frontales)</p>
          <Table columns={[['name', 'Grupo'], ['mentors', 'Mentores'], ['people', 'Personas'], ['houses_visited', 'Casas'], ['score', 'Puntaje']]} rows={report.ranking.teams} />
          <p className="mt-2 text-[11px] text-slate-500">Puntaje = personas × 3 + casas visitadas × 2 + quieren seguimiento × 2 + 7 Semanas × 3.</p>
        </Section>

        {report.books?.length > 0 && <Section title="Libros por mentor" testId="report-books" csv={() => downloadCsv(`libros-${s.name}.csv`, report.books.map((row) => ({ mentor: row.mentor_name, libro: row.book_name, asignados: row.assigned, entregados: row.delivered, le_quedan: row.remaining })))}>
          <Table columns={[['mentor_name', 'Mentor'], ['book_name', 'Libro'], ['assigned', 'Asignados'], ['delivered', 'Entregados'], ['remaining', 'Le quedan']]} rows={report.books.map((row) => ({ ...row, key: `${row.mentor_person_id}-${row.book_id}` }))} />
          <BookDeliveries campaignId={campaignId} books={report.books} />
        </Section>}

        <Section title="3. Resultados de campo" className="xl:col-span-2" testId="report-field" csv={() => downloadCsv(`sectores-${s.name}.csv`, field.by_sector.map((row) => ({ sector: row.sector, casas: row.houses, visitadas: row.visited, cobertura_pct: row.coverage_pct, personas: row.people })))}>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Tile label="Disponibles" value={field.houses.available} /><Tile label="Asignadas" value={field.houses.assigned} /><Tile label="Visitadas" value={field.houses.visited} /><Tile label="En el mapa" value={`${field.houses.located} de ${field.houses.total}`} />
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Tile label="Quieren seguimiento" value={field.results.wants_followup} /><Tile label="Mi Conexión con Dios" value={field.results.received_mcd} /><Tile label="Nací para Triunfar" value={field.results.received_npt} />
                <Tile label="LBS pendiente" value={field.results.lbs_pending} /><Tile label="Iniciaron 7 Semanas" value={field.results.seven_weeks} /><Tile label="Rechazaron" value={field.results.rejected} />
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold">Visitas por jornada</p>
                {field.by_day.length ? <div className="h-48"><ResponsiveContainer width="100%" height="100%"><BarChart data={field.by_day.map((row) => ({ ...row, dia: fmtDate(row.day) }))}><CartesianGrid vertical={false} stroke="#EEECE6" /><XAxis dataKey="dia" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} /><Tooltip /><Bar dataKey="attempts" name="Intentos en casas" fill="#94a3b8" isAnimationActive={false} /><Bar dataKey="people" name="Personas alcanzadas" fill="#2563eb" isAnimationActive={false} /></BarChart></ResponsiveContainer></div> : <p className="text-sm text-slate-500">Sin visitas registradas todavía.</p>}
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold">Por sector</p>
                <Table columns={[['sector', 'Sector'], ['houses', 'Casas'], ['visited', 'Visitadas'], ['coverage_pct', 'Cobertura', (row) => pct(row.coverage_pct)], ['people', 'Personas']]} rows={field.by_sector} />
              </div>
            </div>
            <div className="min-w-0 print:hidden">
              <p className="mb-1 text-sm font-semibold">Mapa de casas</p>
              <InvasionHousesMap campaigns={[{ campaign_id: campaignId, name: s.name, assigned_mentor_ids: [] }]} mentorPersonId={user?.person_id} />
            </div>
          </div>
        </Section>

        {report.prayer && <Section title="5. Preparación en oración" testId="report-prayer" csv={() => downloadCsv(`oracion-${s.name}.csv`, [{ ...report.prayer.totals, inicio: report.prayer.period.prayer_start, fin: report.prayer.period.prep_end }])}>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Tile label="Oraron al menos un día" value={pct(report.prayer.totals.prayed_any_pct)} hint={`${report.prayer.totals.prayed_any} de ${report.prayer.totals.participants}`} />
            <Tile label="Promedio de días" value={report.prayer.totals.avg_days ?? 'Sin datos'} hint={`de ${report.prayer.period.total_days}`} />
            <Tile label="Asistencia a reuniones" value={pct(report.prayer.totals.meeting_attendance_pct)} hint={`${report.prayer.totals.meetings_held} realizada(s)`} />
            <Tile label="Necesitaron seguimiento" value={report.prayer.totals.needs_followup} />
          </div>
        </Section>}
      </div>
      <p className="text-center text-[11px] text-slate-400">{report.mode === 'final' ? `Reporte final congelado el ${fmtDate(report.frozen_at)}.` : 'Datos vivos: cambian mientras la invasión siga abierta.'}</p>
    </div>
  );
}
