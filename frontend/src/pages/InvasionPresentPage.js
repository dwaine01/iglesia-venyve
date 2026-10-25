import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Download, EyeOff, FileText, List, LogOut, Maximize, Minimize, UserX } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { isGeneralCoordinator, isPastoralAuthority } from '../lib/accessControl';
import { apiErrorMessage } from '../lib/apiErrors';
import { useScreenZoom } from '../hooks/useScreenZoom';
import { InvasionHousesMap } from '../components/outreach/InvasionHousesMap';

/* Modo Presentar del Reporte de invasión (pantalla gigante / proyector).
 * Misma línea visual de VEN Y VE 360: fondo claro, banda azul marino del
 * Panel General, tarjetas blancas y acento dorado/morado; títulos en Spectral.
 * Láminas 16:9 medidas en cqw (1 cqw = 1 % del ancho de la lámina): en
 * 1920×1080 el cuerpo mide ≥ 29 px y los títulos ≥ 57 px; escala igual en
 * 1366×768 y en un LED 3840×1080 (la lámina se centra).
 * Nada se corta ni se abrevia: los textos bajan de línea y las listas largas
 * se reparten en varias láminas («1 de 3»). Cada cifra dice qué mide. */

const ORDINALS = ['primer', 'segundo', 'tercer', 'cuarto', 'quinto', 'sexto', 'séptimo', 'octavo', 'noveno', 'décimo'];
const C = {
  bg: '#F7F5EF', band: 'linear-gradient(90deg, #14213D 0%, #1B2A4A 60%, #0E5B5A 100%)', card: '#FFFFFF', line: '#DDD6C6', track: '#EEEAE0',
  text: '#101D36', muted: '#3F4A5C', bandText: '#FFFFFF', bandSub: '#E7D28D',
  gold: '#8A6A1F', goldBar: '#C8A951', navy: '#1B2A4A', purple: '#6B3FA0', teal: '#0E5B5A', green: '#1E7A4C', blue: '#1F5FA8', red: '#B42318', amber: '#A35A00', gray: '#7B8494',
};
const SERIF = 'Spectral, Georgia, serif';
const fmtDate = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('es', { day: 'numeric', month: 'long', year: 'numeric' }) : '');
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleTimeString('es', { hour: 'numeric', minute: '2-digit' }) : '');
const duration = (minutes) => (minutes == null ? '' : minutes < 60 ? `${minutes} minutos` : `${Math.floor(minutes / 60)} h ${minutes % 60} minutos`);
const fs = (value) => `calc(${value}cqw * var(--z, 1))`;
const T = { title: 3.0, body: 1.55, small: 1.5, number: 4.4 };  // tamaños mínimos (cqw)
const plural = (n, one, many) => `${n ?? 0} ${(n ?? 0) === 1 ? one : many}`;
const attendedOf = (attended, invited, rate) => `${plural(attended, 'asistió', 'asistieron')} de ${plural(invited, 'invitado', 'invitados')} = ${rate ?? (invited ? Math.round(((attended || 0) / invited) * 100) : 0)} %`;
const pct = (part, total) => (total ? Math.round((part / total) * 100) : null);
const chunk = (rows, size) => { const out = []; for (let i = 0; i < rows.length; i += size) out.push(rows.slice(i, i + size)); return out.length ? out : [[]]; };
const PER_SLIDE = 7;

// ---------------------------------------------------------------- piezas
/** Cifra grande + qué mide + de dónde sale (una línea). */
function Fig({ value, label, detail, color = C.navy, emptyText, suffix = '' }) {
  const empty = emptyText && (value === 0 || value === null || value === undefined);
  return (
    <div style={{ background: C.card, border: `0.12cqw solid ${C.line}`, borderTop: `0.5cqw solid ${color}`, borderRadius: '1cqw', padding: '1.2cqw 1.5cqw', minWidth: 0, boxShadow: '0 0.2cqw 0.6cqw rgba(16,29,54,0.06)' }}>
      {empty
        ? <p style={{ fontSize: fs(T.body), color: C.muted, fontWeight: 700, lineHeight: 1.25, margin: 0 }}>{emptyText}</p>
        : <p style={{ fontSize: fs(T.number), color, fontWeight: 800, lineHeight: 1, margin: 0 }}>{value ?? 0}{suffix}</p>}
      <p style={{ fontSize: fs(T.body), color: C.text, fontWeight: 700, marginTop: '0.5cqw', lineHeight: 1.2 }}>{label}</p>
      {detail && <p style={{ fontSize: fs(T.small), color: C.muted, marginTop: '0.3cqw', lineHeight: 1.25 }}>{detail}</p>}
    </div>
  );
}

/** Barras con etiqueta COMPLETA (baja de línea) y valor escrito al lado. */
function Bars({ rows, color = C.blue, max, emptyText }) {
  const top = max || Math.max(1, ...rows.map((row) => row.value || 0));
  if (!rows.length || rows.every((row) => !row.value && !row.text)) return <Empty text={emptyText} />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8cqw' }}>
      {rows.map((row, index) => (
        <div key={`${row.label}-${index}`} style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 30%) minmax(0, 1fr) minmax(0, 34%)', alignItems: 'center', gap: '1.2cqw' }}>
          <span style={{ fontSize: fs(T.body), color: C.text, fontWeight: 700, lineHeight: 1.2, overflowWrap: 'anywhere' }}>{row.label}</span>
          <div style={{ height: '2.4cqw', background: C.track, borderRadius: '0.5cqw', overflow: 'hidden' }}>
            <div style={{ width: `${row.value ? Math.max(1.5, Math.round(((row.value || 0) / top) * 100)) : 0}%`, height: '100%', background: row.color || color }} />
          </div>
          <span style={{ fontSize: fs(T.small), color: C.text, lineHeight: 1.2 }}>{row.text ?? row.value ?? 0}</span>
        </div>
      ))}
    </div>
  );
}

const Empty = ({ text = 'Todavía no hay registros.' }) => <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, minHeight: '12cqw', fontSize: fs(2), color: C.muted, fontWeight: 700, textAlign: 'center', padding: '0 4cqw', lineHeight: 1.3 }}>{text}</div>;
const Grid = ({ cols = 3, children, gap = 1.3 }) => <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gap: `${gap}cqw` }}>{children}</div>;
const H = ({ children }) => <p style={{ fontSize: fs(T.body), color: C.purple, fontWeight: 800, margin: '0 0 0.7cqw', lineHeight: 1.2 }}>{children}</p>;

/** Lámina: banda azul marino con el título (qué se mide) y nota al pie con la lógica del cálculo. */
function Slide({ title, kicker, subtitle, children, footer }) {
  return (
    <div className="present-slide" style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', color: C.text, background: C.bg, overflow: 'hidden' }}>
      <div style={{ background: C.band, padding: '1.6cqw 3cqw 1.4cqw', color: C.bandText }}>
        <p style={{ fontSize: fs(T.small), color: C.bandSub, fontWeight: 700, margin: 0, lineHeight: 1.2 }}>{kicker}</p>
        <h2 style={{ fontSize: fs(T.title), fontWeight: 700, margin: '0.3cqw 0 0', lineHeight: 1.1, fontFamily: SERIF }}>{title}</h2>
      </div>
      <div style={{ flex: 1, minHeight: 0, padding: '1.6cqw 3cqw 0', display: 'flex', flexDirection: 'column', gap: '1.3cqw' }}>
        {subtitle && <p style={{ fontSize: fs(T.body), color: C.muted, margin: 0, lineHeight: 1.25 }}>{subtitle}</p>}
        {children}
      </div>
      {footer && <p style={{ fontSize: fs(T.small), color: C.muted, margin: 0, padding: '0.9cqw 3cqw 1.5cqw', lineHeight: 1.25, borderTop: `0.1cqw solid ${C.line}` }}>{footer}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- láminas
function buildSlides({ day, week, period, campaignId, mapHeight }) {
  const r = day || week;
  if (!r) return [];
  const dayMode = Boolean(day && period?.index);
  const s = r.summary; const k = s.key_figures; const wk = week?.summary?.key_figures || {};
  const doors = r.field?.doors?.totals || {};
  const books = r.books_trace || {};
  const follow = r.followup || {};
  const part = r.participation || {};
  const periodLabel = dayMode ? `Día ${period.index} de ${period.days_total} · ${period.label}` : 'Toda la semana (acumulado)';
  const kicker = `${s.name} · ${periodLabel}`;
  const when = dayMode ? 'ese día' : 'en la invasión';
  const weekNote = dayMode ? `Acumulado de la semana hasta hoy: ${plural(wk.houses_visited, 'vivienda visitada', 'viviendas visitadas')}, ${plural(wk.people_reached, 'persona alcanzada', 'personas alcanzadas')}, ${plural(wk.wants_followup, 'persona quiere', 'personas quieren')} seguimiento.` : null;
  const noPastor = 'No incluye a la pastora ni las cuentas de prueba.';
  const slides = [];
  const add = (key, render, show = true) => { if (show) slides.push({ key, title: render.title, render: render.view }); };
  const page = (items, index, total) => (total > 1 ? ` (${index + 1} de ${total})` : '');
  const goalText = (row) => { const ratio = row.goal != null && row.goal <= 1 && (row.value == null || row.value <= 1.0001); const show = (value) => (value == null ? 'sin dato' : ratio ? `${Math.round(value * 100)} %` : value); return `${show(row.value)} de la meta ${show(row.goal)}`; };

  add('cover', { title: 'Portada', view: () => (
    <div className="present-slide" style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', background: C.bg }}>
      <div style={{ background: C.band, flex: '0 0 62%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', color: '#fff', padding: '3cqw 5cqw' }}>
        <p style={{ fontSize: fs(T.small), letterSpacing: '0.3em', color: C.bandSub, fontWeight: 700, textTransform: 'uppercase', margin: 0 }}>VEN Y VE 360 · Reporte de invasión</p>
        <h1 style={{ fontSize: fs(5), fontWeight: 700, lineHeight: 1.08, margin: '1.2cqw 0 0', fontFamily: SERIF }}>{s.name}</h1>
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '1.5cqw 5cqw' }}>
        <p style={{ fontSize: fs(2.6), fontWeight: 800, color: C.text, margin: 0, lineHeight: 1.2 }}>{dayMode ? `Reporte del ${ORDINALS[period.index - 1] || `día ${period.index}`} día — ${period.label}` : `Reporte de la semana — ${fmtDate(s.start_date)}${s.end_date && s.end_date !== s.start_date ? ` al ${fmtDate(s.end_date)}` : ''}`}</p>
        {s.location && <p style={{ fontSize: fs(T.body), color: C.muted, marginTop: '0.6cqw' }}>Lugar: {s.location}</p>}
        <p style={{ marginTop: '1.2cqw', fontSize: fs(T.small), padding: '0.4cqw 1.6cqw', borderRadius: '99cqw', border: `0.15cqw solid ${r.mode === 'final' ? C.green : C.amber}`, color: r.mode === 'final' ? C.green : C.amber, fontWeight: 700 }}>{r.mode === 'final' ? 'Reporte final (cerrado)' : 'Invasión en curso · datos en vivo'}</p>
      </div>
    </div>
  ) });

  add('summary', { title: 'Resumen', view: () => (
    <Slide title={dayMode ? 'Resumen del día: lo más importante' : 'Resumen de la semana: lo más importante'} kicker={kicker} footer={weekNote || noPastor}>
      <Grid cols={3}>
        <Fig value={k.houses_visited} label="Viviendas visitadas" detail="Puertas tocadas al menos una vez; cada apartamento cuenta como una vivienda." color={C.blue} emptyText={dayMode && 'Ese día no se registraron viviendas visitadas.'} />
        <Fig value={k.people_reached} label="Personas alcanzadas" detail="Personas con las que se conversó y quedaron registradas con su nombre." color={C.green} emptyText={dayMode && 'Ese día no se registró a ninguna persona.'} />
        <Fig value={k.attended} label="Servidores que asistieron" detail={k.participants ? `${attendedOf(k.attended, k.participants)}.` : 'No hay invitados registrados.'} color={C.gold} emptyText={dayMode && 'Ese día no se marcó asistencia.'} />
        <Fig value={k.wants_followup} label="Quieren seguimiento" detail="Personas que aceptaron que un mentor las vuelva a contactar." color={C.teal} emptyText={dayMode && 'Ese día nadie pidió seguimiento.'} />
        <Fig value={k.to_consolidation} label="Pasaron a Consolidación" detail="Personas a las que ya se les abrió el proceso de 7 Semanas con su mentor." color={C.purple} emptyText="Todavía no se ha pasado a ninguna persona a Consolidación." />
        <Fig value={books.delivered} label="Libros entregados" detail="Libros que los mentores entregaron en las viviendas (MCD, NPT y otros)." color={C.amber} emptyText={dayMode && 'Ese día no se entregaron libros.'} />
      </Grid>
    </Slide>
  ) });

  add('funnel', { title: 'Del invitado a la Consolidación', view: () => (
    <Slide title="Del servidor invitado a la persona en Consolidación" kicker={kicker} subtitle="Cada barra es un paso del recorrido; el número de la derecha es la cantidad en ese paso." footer={`Porcentajes: cada paso comparado con el anterior. ${noPastor}`}>
      <Bars rows={[
        { label: 'Servidores invitados', value: k.participants, color: C.gray, text: plural(k.participants, 'servidor invitado', 'servidores invitados') },
        { label: 'Servidores que asistieron', value: k.attended, color: C.goldBar, text: `${plural(k.attended, 'asistió', 'asistieron')}${k.participants ? ` (${pct(k.attended, k.participants)} % de los invitados)` : ''}` },
        { label: 'Viviendas visitadas', value: k.houses_visited, color: C.blue, text: plural(k.houses_visited, 'vivienda visitada', 'viviendas visitadas') },
        { label: 'Personas alcanzadas', value: k.people_reached, color: C.green, text: plural(k.people_reached, 'persona alcanzada', 'personas alcanzadas') },
        { label: 'Quieren seguimiento', value: k.wants_followup, color: C.teal, text: `${plural(k.wants_followup, 'persona', 'personas')}${k.people_reached ? ` (${pct(k.wants_followup, k.people_reached)} % de las alcanzadas)` : ''}` },
        { label: 'Pasaron a Consolidación', value: k.to_consolidation, color: C.purple, text: k.to_consolidation ? `${plural(k.to_consolidation, 'persona', 'personas')}${k.wants_followup ? ` (${pct(k.to_consolidation, k.wants_followup)} % de quienes quieren seguimiento)` : ''}` : 'Todavía ninguna' },
      ]} emptyText={`No hay registros ${when}.`} />
    </Slide>
  ) });

  const totals = part.totals || {};
  add('participation', { title: 'Participación', view: () => (
    <Slide title={dayMode ? 'Servidores que participaron ese día' : 'Servidores que participaron en la semana'} kicker={kicker} footer={`Asistencia = servidores que asistieron ÷ servidores invitados. ${noPastor}`}>
      <Grid cols={4}>
        <Fig value={totals.invited} label="Invitados" detail="Servidores invitados a la invasión." color={C.gray} />
        <Fig value={totals.confirmed} label="Confirmaron" detail={`${totals.confirmed ?? 0} de ${plural(totals.invited, 'invitado', 'invitados')} dijeron que vienen.`} color={C.blue} />
        <Fig value={totals.attended} label={dayMode ? 'Asistieron ese día' : 'Asistieron'} detail={`${totals.attended ?? 0} de ${plural(totals.invited, 'invitado', 'invitados')}.`} color={C.green} emptyText={dayMode && 'Ese día no se marcó asistencia.'} />
        <Fig value={totals.attendance_pct} suffix=" %" label="Asistencia" detail={`${attendedOf(totals.attended, totals.invited, totals.attendance_pct)}.`} color={C.gold} />
      </Grid>
    </Slide>
  ) }, Boolean(totals.invited));

  const attendanceRows = (rows, labelOf) => rows.filter((row) => row.invited).map((row) => ({ label: labelOf(row), value: row.attendance_pct || 0, text: attendedOf(row.attended, row.invited, row.attendance_pct) }));
  const roleRows = attendanceRows(part.by_role || [], (row) => row.label);
  chunk(roleRows, PER_SLIDE).forEach((rows, index, all) => add(`role-${index}`, { title: `Asistencia por rol${page(rows, index, all.length)}`, view: () => (
    <Slide title={`Asistencia por rol${page(rows, index, all.length)}`} kicker={kicker} subtitle="Para cada rol: cuántos servidores asistieron de los que fueron invitados." footer={`Asistencia = asistentes ÷ invitados de ese rol. ${noPastor}`}>
      <Bars rows={rows} max={100} color={C.green} />
    </Slide>
  ) }, roleRows.length > 0));
  const groupRows = attendanceRows(part.by_group || [], (row) => row.name);
  chunk(groupRows, PER_SLIDE).forEach((rows, index, all) => add(`group-${index}`, { title: `Asistencia por Grupo Frontal${page(rows, index, all.length)}`, view: () => (
    <Slide title={`Asistencia por Grupo Frontal${page(rows, index, all.length)}`} kicker={kicker} subtitle="Para cada Grupo Frontal (equipo): cuántos de sus servidores asistieron de los invitados." footer={`Asistencia = asistentes ÷ invitados del grupo. ${noPastor}`}>
      <Bars rows={rows} max={100} color={C.teal} />
    </Slide>
  ) }, groupRows.length > 0));

  // Todos los mentores (con trabajo), repartidos en láminas; nunca «Top 8».
  const mentors = [...(r.ranking?.mentors || [])].filter((row) => row.people || row.houses_visited).sort((a, b) => b.people - a.people || b.houses_visited - a.houses_visited || a.name.localeCompare(b.name, 'es'));
  const mentorPages = chunk(mentors, PER_SLIDE);
  mentorPages.forEach((rows, index) => add(`mentors-${index}`, { title: `Personas alcanzadas por mentor${page(rows, index, mentorPages.length)}`, view: () => (
    <Slide title={`Personas alcanzadas por mentor${page(rows, index, mentorPages.length)}`} kicker={kicker}
      subtitle={mentors.length ? `${mentors.length === 1 ? 'El mentor que registró' : `Los ${mentors.length} mentores que registraron`} trabajo ${when}${mentors.length > 1 ? ', de más a menos personas alcanzadas' : ''}.` : null}
      footer="Personas alcanzadas = personas registradas por el mentor. Viviendas visitadas = viviendas donde tocó la puerta.">
      <Bars rows={rows.map((row) => ({ label: row.front_group ? `${row.name} (${row.front_group})` : row.name, value: row.people, text: `${plural(row.people, 'persona alcanzada', 'personas alcanzadas')} · ${plural(row.houses_visited, 'vivienda visitada', 'viviendas visitadas')}` }))}
        color={C.blue} emptyText={`Ningún mentor registró viviendas ni personas ${when}.`} />
    </Slide>
  ) }, mentors.length > 0 || dayMode));

  const teams = (r.ranking?.teams || []).filter((row) => row.people || row.houses_visited);
  chunk(teams, PER_SLIDE).forEach((rows, index, all) => add(`teams-${index}`, { title: `Trabajo por Grupo Frontal${page(rows, index, all.length)}`, view: () => (
    <Slide title={`Trabajo por Grupo Frontal (equipo)${page(rows, index, all.length)}`} kicker={kicker} subtitle="Suma del trabajo de los mentores de cada Grupo Frontal." footer="Cada mentor cuenta en el Grupo Frontal al que pertenece.">
      <Bars rows={rows.map((row) => ({ label: row.name, value: row.people, text: `${plural(row.people, 'persona alcanzada', 'personas alcanzadas')} · ${plural(row.houses_visited, 'vivienda visitada', 'viviendas visitadas')}` }))} color={C.purple} />
    </Slide>
  ) }, teams.length > 0));

  add('field', { title: 'Resultados en las puertas', view: () => (
    <Slide title={dayMode ? 'Qué pasó en las puertas ese día' : 'Qué pasó en las puertas'} kicker={kicker}
      footer={doors.attempts ? `${plural(doors.attempts, 'intento', 'intentos')} en ${plural(doors.houses_visited, 'vivienda', 'viviendas')}: si se volvió a una vivienda, la vivienda cuenta una sola vez.` : `No hay intentos registrados ${when}.`}>
      <Grid cols={3}>
        <Fig value={doors.houses_visited} label="Viviendas visitadas" detail={`En ${plural(doors.opened, 'vivienda abrieron', 'viviendas abrieron')} y en ${doors.not_opened ?? 0} no abrieron.`} color={C.blue} emptyText={dayMode && 'Ese día no se visitaron viviendas.'} />
        <Fig value={doors.opened} label="Abrieron la puerta" detail={doors.houses_visited ? `${doors.opened ?? 0} de ${doors.houses_visited} viviendas = ${pct(doors.opened, doors.houses_visited)} %.` : null} color={C.green} />
        <Fig value={doors.conversed} label="Conversamos" detail={`En ${plural(doors.conversed, 'vivienda', 'viviendas')} hubo conversación; en ${doors.invited_in ?? 0} nos invitaron a pasar.`} color={C.teal} />
        <Fig value={doors.books} label="Libros entregados en la puerta" detail="Cantidad de libros que quedaron en las viviendas." color={C.amber} />
        <Fig value={doors.followup_people} label="Aceptaron seguimiento" detail="Personas que dijeron que sí a una nueva visita o llamada." color={C.purple} />
        <Fig value={doors.pending_revisit} label="Pendientes de volver" detail="Viviendas donde no abrieron o pidieron que se regrese." color={C.gray} />
      </Grid>
    </Slide>
  ) });

  const streets = r.field?.doors?.by_street || [];
  chunk(streets, 5).forEach((rows, index, all) => add(`streets-${index}`, { title: `Calles trabajadas${page(rows, index, all.length)}`, view: () => (
    <Slide title={`Calles trabajadas${page(rows, index, all.length)}`} kicker={kicker} subtitle={streets.length ? `${plural(streets.length, 'calle trabajada', 'calles trabajadas')} ${when}.` : null} footer="Hora de inicio y de cierre de la calle según el registro del mentor.">
      {rows.length === 0 ? <Empty text={`No se registraron calles ${when}.`} /> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8cqw' }}>
          {rows.map((row) => (
            <div key={row.street_key || row.name} style={{ background: C.card, border: `0.12cqw solid ${C.line}`, borderLeft: `0.5cqw solid ${C.goldBar}`, borderRadius: '0.8cqw', padding: '0.8cqw 1.4cqw' }}>
              <p style={{ fontSize: fs(T.body), fontWeight: 800, margin: 0, lineHeight: 1.2 }}>{row.name}{row.started_at ? <span style={{ fontWeight: 600, color: C.gold }}> · {row.ended_at ? `de ${fmtTime(row.started_at)} a ${fmtTime(row.ended_at)}` : `desde las ${fmtTime(row.started_at)} (todavía abierta)`}{row.duration_minutes != null ? ` · ${duration(row.duration_minutes)}` : ''}</span> : null}</p>
              <p style={{ fontSize: fs(T.small), color: C.muted, margin: '0.2cqw 0 0', lineHeight: 1.25 }}>{plural(row.houses_visited, 'vivienda visitada', 'viviendas visitadas')} · {plural(row.opened, 'abrió', 'abrieron')} · {plural(row.books, 'libro entregado', 'libros entregados')}{row.mentors?.length ? ` · Mentores: ${row.mentors.join(', ')}` : ''}</p>
            </div>
          ))}
        </div>
      )}
    </Slide>
  ) }));

  add('map', { title: 'Mapa de las viviendas', view: () => (
    <Slide title="Mapa de las viviendas visitadas" kicker={kicker} footer="Cada punto es una vivienda; el color indica qué pasó en la puerta (toda la invasión).">
      <div style={{ flex: 1, minHeight: 0, borderRadius: '1cqw', overflow: 'hidden', marginBottom: '1cqw' }} className="present-map">
        <InvasionHousesMap campaigns={[{ campaign_id: campaignId, name: s.name }]} colorBy="door" fixedHeight={mapHeight} />
      </div>
    </Slide>
  ) }, Boolean(r.field?.houses?.located));

  add('followup', { title: 'Seguimiento y Consolidación', view: () => (
    <Slide title="Seguimiento a las personas y paso a Consolidación" kicker={kicker} footer={`«Sin atender» = quiere seguimiento y nadie la contactó en ${follow.unattended_hours || 48} horas.`}>
      <Grid cols={4}>
        <Fig value={follow.wants_followup} label="Quieren seguimiento" detail="Aceptaron que un mentor las vuelva a contactar." color={C.teal} emptyText={`Nadie pidió seguimiento ${when}.`} />
        <Fig value={follow.attended} label="Ya contactadas" detail={`${follow.attended ?? 0} de ${follow.wants_followup ?? 0} ya recibieron el contacto.`} color={C.green} />
        <Fig value={follow.unattended} label="Sin atender" detail={`Más de ${follow.unattended_hours || 48} horas sin contacto.`} color={follow.unattended ? C.red : C.gray} />
        <Fig value={follow.to_consolidation} label="Pasaron a Consolidación" detail={follow.wants_followup ? `${follow.to_consolidation ?? 0} de ${follow.wants_followup} que quieren seguimiento.` : null} color={C.purple} emptyText="Todavía no se ha pasado a ninguna persona a Consolidación." />
      </Grid>
      <div><H>Cuánto tardó el primer contacto</H><Bars rows={(follow.first_contact || []).map((row) => ({ label: row.bucket, value: row.total, color: row.bucket === 'Sin contacto' ? C.red : C.teal, text: plural(row.total, 'persona', 'personas') }))} emptyText="Todavía no hay contactos de seguimiento registrados." /></div>
    </Slide>
  ) });

  add('books', { title: 'Libros entregados', view: () => (
    <Slide title="Libros entregados y a quién" kicker={kicker} footer="«Con nombre» = se sabe a qué persona se entregó. Los que no tienen nombre se completan desde Mi Trabajo.">
      <Grid cols={3}>
        <Fig value={books.delivered} label="Libros entregados" detail="Todos los libros entregados por los mentores." color={C.amber} emptyText={`No se entregaron libros ${when}.`} />
        <Fig value={books.identified} label="Con nombre de la persona" detail={books.delivered ? `${books.identified ?? 0} de ${books.delivered} libros.` : null} color={C.green} />
        <Fig value={books.with_followup} label="La persona quiere seguimiento" detail="Libros entregados a personas que aceptaron seguimiento." color={C.purple} />
      </Grid>
      <Grid cols={2}>
        <div><H>Por material</H><Bars rows={(books.by_material || []).slice(0, 4).map((row) => ({ label: row.name, value: row.total, text: plural(row.total, 'libro', 'libros') }))} color={C.amber} emptyText="Sin libros registrados." /></div>
        <div><H>Por mentor (los que más entregaron)</H><Bars rows={(books.by_mentor || []).slice(0, 4).map((row) => ({ label: row.name, value: row.total, text: plural(row.total, 'libro', 'libros') }))} color={C.blue} emptyText="Sin libros registrados." /></div>
      </Grid>
    </Slide>
  ) }, Boolean(books.delivered || dayMode));
  const bookMentors = books.by_mentor || [];
  if (bookMentors.length > 4) chunk(bookMentors, PER_SLIDE).forEach((rows, index, all) => add(`books-mentor-${index}`, { title: `Libros por mentor${page(rows, index, all.length)}`, view: () => (
    <Slide title={`Libros entregados por cada mentor${page(rows, index, all.length)}`} kicker={kicker} subtitle={`Los ${bookMentors.length} mentores que entregaron libros ${when}.`}>
      <Bars rows={rows.map((row) => ({ label: row.name, value: row.total, text: plural(row.total, 'libro entregado', 'libros entregados') }))} color={C.blue} />
    </Slide>
  ) }));

  const prayer = week?.prayer;
  add('prayer', { title: 'Preparación en oración', view: () => (
    <Slide title="Preparación en oración antes de la invasión" kicker={`${s.name} · semana de preparación`} footer="Porcentaje = participantes que marcaron al menos un día de oración ÷ participantes.">
      <Grid cols={3}>
        <Fig value={prayer.totals?.prayed_any_pct} suffix=" %" label="Participantes que oraron" detail="Oraron al menos un día de la preparación." color={C.gold} />
        <Fig value={prayer.totals?.avg_days} label="Días de oración (promedio)" detail="Promedio de días que oró cada participante." color={C.teal} />
        <Fig value={prayer.totals?.meetings_held} label="Reuniones de oración" detail="Reuniones de oración realizadas." color={C.blue} />
      </Grid>
      <div><H>Oraron por semana</H><Bars rows={(prayer.by_week || []).map((row) => ({ label: row.week, value: row.pct, text: `${plural(row.prayed, 'participante oró', 'participantes oraron')} = ${row.pct} %` }))} max={100} color={C.goldBar} /></div>
    </Slide>
  ) }, Boolean(prayer?.totals?.participants));

  const help = r.help_alerts || {};
  add('help', { title: 'Alertas de ayuda', view: () => (
    <Slide title="Alertas de ayuda enviadas desde la calle" kicker={kicker} footer="Tiempo de respuesta = desde que se envió la alerta hasta que alguien la atendió.">
      <Grid cols={3}>
        <Fig value={help.total} label="Alertas enviadas" color={help.total ? C.amber : C.gray} />
        <Fig value={help.resolved} label="Alertas atendidas" detail={`${help.resolved ?? 0} de ${help.total ?? 0}.`} color={C.green} />
        <Fig value={help.avg_response_minutes} suffix=" minutos" label="Respuesta promedio" color={C.blue} />
      </Grid>
      <div><H>Motivo de la alerta</H><Bars rows={(help.by_reason || []).filter((row) => row.total).map((row) => ({ label: row.label, value: row.total, text: plural(row.total, 'alerta', 'alertas') }))} color={C.amber} /></div>
    </Slide>
  ) }, Boolean(help.total));

  const goals = week?.goals?.items || [];
  const sem = { verde: C.green, ambar: C.amber, rojo: C.red };
  chunk(goals, PER_SLIDE).forEach((rows, index, all) => add(`goals-${index}`, { title: `Metas de la semana${page(rows, index, all.length)}`, view: () => (
    <Slide title={`Metas de la semana: cuánto se avanzó${page(rows, index, all.length)}`} kicker={`${s.name} · acumulado de la semana`} footer="Avance = valor logrado ÷ meta. Verde: en camino; ámbar: atención; rojo: por debajo.">
      <Bars rows={rows.map((row) => ({ label: row.label, value: row.progress == null ? 0 : Math.round(row.progress * 100), color: sem[row.semaphore] || C.gray, text: `${goalText(row)}${row.progress == null ? '' : ` · avance ${Math.round(row.progress * 100)} %`}` }))} max={100} />
    </Slide>
  ) }, goals.length > 0));

  const comparison = week?.comparison || [];
  chunk(comparison, PER_SLIDE).forEach((rows, index, all) => add(`comparison-${index}`, { title: 'Comparado con invasiones anteriores', view: () => (
    <Slide title={`Comparado con invasiones anteriores${page(rows, index, all.length)}`} kicker="Semana completa de cada invasión" footer="La barra dorada es esta invasión.">
      <Bars rows={rows.map((row) => ({ label: row.current ? `${row.name} (esta invasión)` : row.name, value: row.people, color: row.current ? C.goldBar : C.blue, text: `${plural(row.people, 'persona alcanzada', 'personas alcanzadas')} · ${plural(row.followup, 'quiere', 'quieren')} seguimiento` }))} />
    </Slide>
  ) }, comparison.length > 1));

  const recs = (week?.recommendations || []).filter((item) => !item.resolved);
  chunk(recs, 3).forEach((rows, index, all) => add(`recommendations-${index}`, { title: 'Recomendaciones', view: () => (
    <Slide title={`Recomendaciones según los datos${page(rows, index, all.length)}`} kicker={`${s.name} · semana`} footer="Rojo: prioridad alta · ámbar: media · azul: baja.">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1cqw' }}>
        {rows.map((item) => (
          <div key={item.id} style={{ background: C.card, border: `0.12cqw solid ${C.line}`, borderLeft: `0.6cqw solid ${item.priority === 'alta' ? C.red : item.priority === 'media' ? C.amber : C.blue}`, borderRadius: '0.8cqw', padding: '1cqw 1.5cqw' }}>
            <p style={{ fontSize: fs(1.8), fontWeight: 800, margin: 0, lineHeight: 1.2 }}>{item.title}</p>
            <p style={{ fontSize: fs(T.small), color: C.muted, marginTop: '0.3cqw', lineHeight: 1.25 }}>{item.evidence?.label}: {item.evidence?.value}{item.evidence?.total ? ` de ${item.evidence.total}` : ''}{item.responsible ? ` · Responsable: ${item.responsible}` : ''}</p>
          </div>
        ))}
      </div>
    </Slide>
  ) }, recs.length > 0));

  const notes = week?.notes || {};
  [['worked', 'Lo que funcionó'], ['improve', 'Qué mejorar'], ['pastor_recommendations', 'Recomendaciones del pastor']].filter(([key]) => (notes[key] || '').trim()).forEach(([key, label]) => add(`lessons-${key}`, { title: label, view: () => (
    <Slide title={`Lecciones aprendidas: ${label.toLowerCase()}`} kicker={s.name}>
      <p style={{ fontSize: fs(1.8), lineHeight: 1.35, whiteSpace: 'pre-line', margin: 0, background: C.card, border: `0.12cqw solid ${C.line}`, borderRadius: '1cqw', padding: '1.4cqw 1.8cqw' }}>{notes[key]}</p>
    </Slide>
  ) }));

  const highlights = [
    k.people_reached ? `${plural(k.people_reached, 'persona alcanzada', 'personas alcanzadas')}${dayMode ? ' ese día' : ''}` : null,
    k.houses_visited ? `${plural(k.houses_visited, 'vivienda visitada', 'viviendas visitadas')}${doors.opened ? `; abrieron en ${doors.opened}` : ''}` : null,
    k.wants_followup ? `${plural(k.wants_followup, 'persona quiere', 'personas quieren')} seguimiento${k.to_consolidation ? ` y ${k.to_consolidation} ya están en Consolidación` : ''}` : null,
    books.delivered ? plural(books.delivered, 'libro entregado', 'libros entregados') : null,
    k.attended ? `${plural(k.attended, 'servidor asistió', 'servidores asistieron')}` : null,
  ].filter(Boolean).slice(0, 4);
  const nextDay = dayMode && period.index < period.days_total ? period.days[period.index] : null;
  const nextSteps = [
    doors.pending_revisit ? `Volver a ${plural(doors.pending_revisit, 'vivienda', 'viviendas')} donde no abrieron o pidieron que se regrese` : null,
    follow.unattended ? `Contactar a ${plural(follow.unattended, 'persona', 'personas')} que pidieron seguimiento y aún no se atendieron` : null,
    follow.wants_followup && follow.to_consolidation < follow.wants_followup ? `Dar seguimiento a ${plural(follow.wants_followup - (follow.to_consolidation || 0), 'persona', 'personas')} que lo pidieron` : null,
    books.unidentified ? `Completar a quién se entregaron ${plural(books.unidentified, 'libro', 'libros')}` : null,
  ].filter(Boolean).slice(0, 3);
  add('thanks', { title: nextDay ? `Qué sigue para el día ${nextDay.index}` : '¡Gracias!', view: () => (
    <Slide title={nextDay ? `¡Gracias! Qué sigue para el día ${nextDay.index} (${nextDay.label})` : '¡Gracias!'} kicker={kicker}>
      {highlights.length > 0 && <div><H>Lo que se logró {dayMode ? 'ese día' : 'en la invasión'}</H>
        <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5cqw', fontSize: fs(1.9), fontWeight: 700, margin: 0, paddingLeft: '2cqw' }}>{highlights.map((line) => <li key={line}>{line}</li>)}</ul></div>}
      {nextDay && <div><H>Próximos pasos</H>
        <ul style={{ display: 'flex', flexDirection: 'column', gap: '0.5cqw', fontSize: fs(1.9), margin: 0, paddingLeft: '2cqw' }}>{(nextSteps.length ? nextSteps : ['Seguir con las calles y viviendas pendientes']).map((line) => <li key={line}>{line}</li>)}</ul></div>}
    </Slide>
  ) });
  return slides;
}

// ---------------------------------------------------------------- cuentas de prueba (autoridad / coordinador)
function ExclusionsDialog({ onClose, onSaved }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [chosen, setChosen] = useState(new Set());
  useEffect(() => { axios.get(`${API}/api/invasions/report-settings/exclusions`, getAuthHeaders()).then((response) => { setData(response.data); setChosen(new Set(response.data.excluded.map((item) => item.person_id))); }).catch((error) => { toast.error(apiErrorMessage(error, 'Sin acceso')); onClose(); }); }, [API, getAuthHeaders]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = async () => {
    try { await axios.put(`${API}/api/invasions/report-settings/exclusions`, { person_ids: Array.from(chosen) }, getAuthHeaders()); toast.success('Cuentas de prueba actualizadas'); onSaved(); onClose(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); }
  };
  const list = data ? [...data.excluded.map((item) => ({ ...item, excluded: true })), ...data.suggestions] : [];
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }} data-testid="present-exclusions">
      <div style={{ background: '#fff', color: '#101D36', borderRadius: 16, padding: 20, width: 'min(560px, 100%)', maxHeight: '85vh', overflowY: 'auto' }}>
        <p style={{ fontSize: 20, fontWeight: 700 }}>Cuentas de prueba (no cuentan en el reporte)</p>
        <p style={{ fontSize: 14, color: '#475569', marginTop: 4 }}>Marca las cuentas de prueba (p. ej. Josue, Luis de prueba). Nada se borra; solo dejan de contar en las cifras.</p>
        {!data ? <p style={{ marginTop: 12 }}>Cargando…</p> : list.length === 0 ? <p style={{ marginTop: 12 }}>No hay sugerencias.</p> : (
          <ul style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>{list.map((item) => (
            <li key={item.person_id}><label style={{ display: 'flex', gap: 10, alignItems: 'center', minHeight: 44, fontSize: 15 }}><input type="checkbox" checked={chosen.has(item.person_id)} onChange={(event) => setChosen((current) => { const next = new Set(current); if (event.target.checked) next.add(item.person_id); else next.delete(item.person_id); return next; })} style={{ width: 22, height: 22 }} />{item.name || 'Persona'} <span style={{ color: '#64748b' }}>{item.email || ''}</span></label></li>
          ))}</ul>
        )}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}><button type="button" onClick={save} style={{ flex: 1, minHeight: 48, borderRadius: 12, background: '#132443', color: '#fff', fontWeight: 700 }} data-testid="present-exclusions-save">Guardar</button><button type="button" onClick={onClose} style={{ minHeight: 48, padding: '0 16px', borderRadius: 12, border: '1px solid #cbd5e1' }}>Cerrar</button></div>
      </div>
    </div>
  );
}

/** Modo Presentar: /invasiones/:id/reporte/presentar?dia=1 (0 = toda la semana). */
export default function InvasionPresentPage() {
  const { campaignId } = useParams();
  const { API, getAuthHeaders, user } = useAuth();
  const [params, setParams] = useSearchParams();
  const dayIndex = Math.max(0, parseInt(params.get('dia') ?? '1', 10) || 0);
  const [week, setWeek] = useState(null);
  const [day, setDay] = useState(null);
  const [error, setError] = useState('');
  const [index, setIndex] = useState(0);
  const [hideUi, setHideUi] = useState(false);
  const [idle, setIdle] = useState(false);  // la barra se oculta sola sin movimiento (reaparece al mover el mouse o tocar)
  const [exclusions, setExclusions] = useState(false);
  const [indexOpen, setIndexOpen] = useState(false);
  const [isFull, setIsFull] = useState(Boolean(document.fullscreenElement));
  const navigate = useNavigate();
  const [stageSize, setStageSize] = useState({ width: 1280, height: 720 });
  const stageRef = useRef(null);
  const { zoom, increment, decrement } = useScreenZoom('presentar_reporte_zoom', 1.0);
  const canExclude = isPastoralAuthority(user) || isGeneralCoordinator(user);

  const load = useCallback(() => {
    const weekRequest = axios.get(`${API}/api/invasions/${campaignId}/report`, getAuthHeaders());
    const dayRequest = dayIndex ? axios.get(`${API}/api/invasions/${campaignId}/report`, { ...getAuthHeaders(), params: { day_index: dayIndex } }) : null;
    Promise.all([weekRequest, dayRequest]).then(([weekResponse, dayResponse]) => {
      if (weekResponse.data.scope !== 'full') { setError('El modo presentar es para la autoridad pastoral, coordinadores generales, el organizador y el encargado general.'); return; }
      setWeek(weekResponse.data); setDay(dayResponse ? dayResponse.data : null); setError('');
    }).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar el reporte')));
  }, [API, getAuthHeaders, campaignId, dayIndex]);
  useEffect(() => { load(); }, [load]);
  // Datos en vivo mientras la invasión esté en curso.
  useEffect(() => { if (week?.mode !== 'live') return undefined; const timer = setInterval(load, 60000); return () => clearInterval(timer); }, [week?.mode, load]);
  // Lámina 16:9 que cabe en cualquier pantalla (laptop, 1920×1080 o LED 17:7).
  useEffect(() => {
    const fit = () => { const width = Math.min(window.innerWidth, window.innerHeight * 16 / 9); setStageSize({ width, height: width * 9 / 16 }); };
    fit(); window.addEventListener('resize', fit); return () => window.removeEventListener('resize', fit);
  }, []);
  // PDF de respaldo: una lámina por página horizontal.
  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = '@page { size: 13.333in 7.5in; margin: 0; } @media print { html, body { background: #F7F5EF !important; } }';
    document.head.appendChild(style); return () => style.remove();
  }, []);

  useEffect(() => {
    let timer;
    const wake = () => { setIdle(false); clearTimeout(timer); timer = setTimeout(() => setIdle(true), 3500); };
    wake(); window.addEventListener('mousemove', wake); window.addEventListener('touchstart', wake);
    return () => { clearTimeout(timer); window.removeEventListener('mousemove', wake); window.removeEventListener('touchstart', wake); };
  }, []);
  const period = day?.period || null;
  const slides = useMemo(() => buildSlides({ day, week, period, campaignId, mapHeight: Math.round(stageSize.height * 0.66) }), [day, week, period, campaignId, stageSize.height]);
  const total = slides.length;
  useEffect(() => { setIndex((current) => Math.min(current, Math.max(0, total - 1))); }, [total]);
  const go = useCallback((delta) => setIndex((current) => Math.max(0, Math.min(total - 1, current + delta))), [total]);
  const fullscreen = () => { if (document.fullscreenElement) document.exitFullscreen?.(); else document.documentElement.requestFullscreen?.().catch(() => {}); };
  useEffect(() => { const sync = () => setIsFull(Boolean(document.fullscreenElement)); document.addEventListener('fullscreenchange', sync); return () => document.removeEventListener('fullscreenchange', sync); }, []);
  const exit = () => { if (document.fullscreenElement) document.exitFullscreen?.(); navigate(`/invasiones/${campaignId}/reporte${dayIndex ? `?dia=${dayIndex}` : ''}`); };
  useEffect(() => {
    const onKey = (event) => {
      if (exclusions || indexOpen || event.target?.tagName === 'SELECT') return;
      if (['ArrowRight', 'PageDown', ' ', 'Enter', 'ArrowDown'].includes(event.key)) { event.preventDefault(); go(1); }
      else if (['ArrowLeft', 'PageUp', 'Backspace', 'ArrowUp'].includes(event.key)) { event.preventDefault(); go(-1); }
      else if (event.key === 'Home') setIndex(0);
      else if (event.key === 'End') setIndex(total - 1);
      else if (event.key.toLowerCase() === 'i') setIndexOpen(true);
      else if (event.key.toLowerCase() === 'f') fullscreen();
      else if (event.key.toLowerCase() === 'g') setHideUi((value) => !value);
      else if (event.key === '+' || event.key === '=') increment();
      else if (event.key === '-') decrement();
    };
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, [go, total, exclusions, indexOpen, increment, decrement]);
  const setDayIndex = (value) => { const next = new URLSearchParams(params); next.set('dia', String(value)); setParams(next, { replace: true }); setIndex(0); };
  const days = week?.period?.days || [];
  const stageStyle = { width: stageSize.width, height: stageSize.height, containerType: 'inline-size', position: 'relative', background: C.bg, overflow: 'hidden', '--z': zoom, fontFamily: 'Inter, system-ui, sans-serif', boxShadow: '0 0 0 1px #DDD6C6' };

  if (error) return <div style={{ position: 'fixed', inset: 0, background: C.bg, color: C.text, flexDirection: 'column', gap: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, fontSize: 22, textAlign: 'center' }} data-testid="present-error">{error}</div>;
  if (!week) return <div style={{ position: 'fixed', inset: 0, background: C.bg, color: C.muted, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24 }}>Cargando reporte…</div>;
  const current = slides[index];
  const pageHeader = period ? `Día ${period.index} · ${period.label}` : 'Toda la semana';

  return (
    <div className="present-root" style={{ position: 'fixed', inset: 0, background: '#E9E4D8', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, userSelect: 'none' }} data-testid="present-page">
      <div ref={stageRef} className="present-stage" style={stageStyle} data-testid="present-stage" data-slide={current?.key}
        onClick={(event) => { const rect = event.currentTarget.getBoundingClientRect(); go(event.clientX - rect.left > rect.width / 3 ? 1 : -1); }}>
        {current?.render()}
        <div style={{ position: 'absolute', left: 0, bottom: 0, height: '0.4cqw', width: `${((index + 1) / Math.max(1, total)) * 100}%`, background: C.goldBar, transition: 'width .2s' }} data-testid="present-progress" />
        <span style={{ position: 'absolute', right: '1.2cqw', top: '0.8cqw', fontSize: fs(1.1), color: C.bandSub, fontWeight: 700 }} data-testid="present-counter">{index + 1} / {total}</span>
      </div>

      {/* Todas las láminas para el PDF de respaldo (una por página, con el día en el encabezado). */}
      <div className="present-print">
        {slides.filter((slide) => slide.key !== 'map').map((slide) => (
          <div key={slide.key} style={{ width: '13.333in', height: '7.5in', containerType: 'inline-size', position: 'relative', background: C.bg, overflow: 'hidden', breakAfter: 'page', '--z': 1, fontFamily: 'Inter, system-ui, sans-serif' }}>
            {slide.render()}
            <span style={{ position: 'absolute', top: '0.8cqw', right: '1.2cqw', fontSize: '1cqw', color: C.bandSub, zIndex: 2 }}>{week.summary.name} · {pageHeader}</span>
          </div>
        ))}
      </div>

      {!hideUi && !idle && (
        <div className="present-ui" style={{ position: 'fixed', top: 8, left: 8, right: 8, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', justifyContent: 'space-between', pointerEvents: 'none' }} data-testid="present-toolbar">
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', pointerEvents: 'auto' }}>
            <select value={dayIndex} onChange={(event) => setDayIndex(parseInt(event.target.value, 10))} style={{ ...btn, paddingRight: 8 }} data-testid="present-day" aria-label="Día del reporte">
              {days.map((item) => <option key={item.day} value={item.index}>Día {item.index} · {item.label}</option>)}
              <option value={0}>Toda la semana (acumulado)</option>
            </select>
            <Link to={`/invasiones/${campaignId}/reporte${dayIndex ? `?dia=${dayIndex}` : ''}`} style={btn} data-testid="present-one-page"><FileText size={18} />Ver todo en una página</Link>
            <button type="button" onClick={() => window.print()} style={btn} data-testid="present-pdf"><Download size={18} />Descargar PDF</button>
            {canExclude && <button type="button" onClick={() => setExclusions(true)} style={btn} data-testid="present-exclusions-open"><UserX size={18} />Cuentas de prueba</button>}
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', pointerEvents: 'auto' }}>
            <button type="button" onClick={decrement} style={btn} aria-label="Texto más pequeño">A−</button>
            <button type="button" onClick={increment} style={btn} aria-label="Texto más grande">A+</button>
            <button type="button" onClick={fullscreen} style={btn} data-testid="present-fullscreen">{isFull ? <><Minimize size={18} />Salir de pantalla completa</> : <><Maximize size={18} />Pantalla completa</>}</button>
            <button type="button" onClick={() => setHideUi(true)} style={btn} title="Ocultar controles (G)"><EyeOff size={18} />Ocultar</button>
            <button type="button" onClick={exit} style={btn} data-testid="present-exit"><LogOut size={18} />Salir</button>
          </div>
        </div>
      )}
      {/* Navegación grande abajo: Anterior · índice · Siguiente. */}
      {!hideUi && !idle && (
        <div className="present-ui" style={{ position: 'fixed', bottom: 10, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 10, pointerEvents: 'none' }} data-testid="present-nav">
          <button type="button" onClick={() => go(-1)} disabled={index === 0} style={{ ...navBtn, opacity: index === 0 ? 0.5 : 1 }} data-testid="present-prev"><ChevronLeft size={24} />Anterior</button>
          <button type="button" onClick={() => setIndexOpen(true)} style={{ ...navBtn, background: '#FFFFFF', color: '#14213D' }} data-testid="present-index-open"><List size={22} />Diapositiva {index + 1} de {total}</button>
          <button type="button" onClick={() => go(1)} disabled={index >= total - 1} style={{ ...navBtn, opacity: index >= total - 1 ? 0.5 : 1 }} data-testid="present-next">Siguiente<ChevronRight size={24} /></button>
        </div>
      )}
      {indexOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(20,33,61,0.55)', zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }} onClick={() => setIndexOpen(false)} data-testid="present-index">
          <div onClick={(event) => event.stopPropagation()} style={{ background: '#fff', color: '#101D36', borderRadius: 16, padding: 20, width: 'min(720px, 100%)', maxHeight: '85vh', overflowY: 'auto' }}>
            <p style={{ fontSize: 22, fontWeight: 700, fontFamily: SERIF }}>Índice de diapositivas</p>
            <ol style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {slides.map((slide, position) => (
                <li key={slide.key}><button type="button" onClick={() => { setIndex(position); setIndexOpen(false); }} style={{ width: '100%', textAlign: 'left', minHeight: 48, padding: '8px 12px', borderRadius: 10, border: '1px solid #E3DED2', background: position === index ? '#14213D' : '#fff', color: position === index ? '#fff' : '#101D36', fontSize: 17, fontWeight: 600 }} data-testid={`present-index-${slide.key}`}>{position + 1}. {slide.title}</button></li>
              ))}
            </ol>
            <button type="button" onClick={() => setIndexOpen(false)} style={{ marginTop: 12, minHeight: 48, width: '100%', borderRadius: 12, border: '1px solid #cbd5e1', fontSize: 16, fontWeight: 600 }}>Cerrar</button>
          </div>
        </div>
      )}
      {exclusions && <ExclusionsDialog onClose={() => setExclusions(false)} onSaved={load} />}
    </div>
  );
}

const btn = { display: 'inline-flex', alignItems: 'center', gap: 6, minHeight: 48, padding: '0 14px', borderRadius: 12, background: 'rgba(20,33,61,0.92)', color: '#fff', border: '1px solid #C8A951', fontSize: 16, fontWeight: 600, cursor: 'pointer', textDecoration: 'none' };
const navBtn = { display: 'inline-flex', alignItems: 'center', gap: 8, minHeight: 56, padding: '0 22px', borderRadius: 14, background: '#14213D', color: '#fff', border: '2px solid #C8A951', fontSize: 19, fontWeight: 700, cursor: 'pointer', pointerEvents: 'auto', boxShadow: '0 4px 14px rgba(20,33,61,0.25)' };
