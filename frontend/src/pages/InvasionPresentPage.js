import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Download, EyeOff, FileText, Maximize, UserX } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { isGeneralCoordinator, isPastoralAuthority } from '../lib/accessControl';
import { apiErrorMessage } from '../lib/apiErrors';
import { useScreenZoom } from '../hooks/useScreenZoom';
import { InvasionHousesMap } from '../components/outreach/InvasionHousesMap';

/* Modo Presentar del Reporte de invasión (pantalla LED / proyector).
 * Láminas 16:9 que se leen desde lejos; todo se dimensiona con unidades
 * relativas a la lámina (cqw), así se ve igual en una laptop 1366×768, en
 * 1920×1080 o en un LED ancho 17:7 (la lámina se centra). Sin scroll dentro
 * de cada lámina: máximo 8 filas («Top 8» + total). */

const ORDINALS = ['primer', 'segundo', 'tercer', 'cuarto', 'quinto', 'sexto', 'séptimo', 'octavo', 'noveno', 'décimo'];
const C = { bg: '#070d1c', card: '#111a2e', line: '#24304a', text: '#f5f3ee', muted: '#a9b4c8', gold: '#e2c26d', green: '#4ade80', blue: '#60a5fa', amber: '#fbbf24', red: '#f87171', violet: '#c4b5fd', teal: '#5eead4' };
const fmtDate = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('es', { day: 'numeric', month: 'long', year: 'numeric' }) : '');
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleTimeString('es', { hour: 'numeric', minute: '2-digit' }) : '');
const duration = (minutes) => (minutes == null ? '' : minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`);
const fs = (value) => `calc(${value}cqw * var(--z, 1))`;

// ---------------------------------------------------------------- piezas
function Fig({ value, label, color = C.text, day, suffix = '' }) {
  const empty = day && (value === 0 || value === null || value === undefined);
  return (
    <div style={{ background: C.card, border: `0.15cqw solid ${C.line}`, borderRadius: '1.2cqw', padding: '1.4cqw 1.6cqw', minWidth: 0 }}>
      {empty
        ? <p style={{ fontSize: fs(1.7), color: C.muted, fontWeight: 600, lineHeight: 1.2, margin: 0 }}>Sin registros ese día</p>
        : <p style={{ fontSize: fs(4.4), color, fontWeight: 800, lineHeight: 1, margin: 0 }}>{value ?? '—'}{suffix}</p>}
      <p style={{ fontSize: fs(1.5), color: C.muted, marginTop: '0.6cqw', lineHeight: 1.2 }}>{label}</p>
    </div>
  );
}

function Bars({ rows, color = C.blue, max, unit = '', emptyText, zeroText }) {
  const shown = rows.slice(0, 8);
  const top = max || Math.max(1, ...shown.map((row) => row.value || 0));
  if (!shown.length || shown.every((row) => !row.value)) return <Empty text={emptyText} />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9cqw' }}>
      {shown.map((row, index) => (
        <div key={`${row.label}-${index}`} style={{ display: 'grid', gridTemplateColumns: '28% 1fr', alignItems: 'center', gap: '1.2cqw' }}>
          <span style={{ fontSize: fs(1.45), color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.label}>{row.label}</span>
          <div style={{ position: 'relative', height: '2.7cqw', background: '#0b1324', borderRadius: '0.6cqw' }}>
            <div style={{ width: `${Math.max(2, Math.round(((row.value || 0) / top) * 100))}%`, height: '100%', background: row.color || color, borderRadius: '0.6cqw' }} />
            <span style={{ position: 'absolute', right: '0.8cqw', top: '50%', transform: 'translateY(-50%)', fontSize: fs(1.5), fontWeight: 800, color: C.text, textShadow: '0 0 0.4cqw #000' }}>{!row.value && zeroText ? zeroText : (row.text ?? `${row.value ?? 0}${unit}`)}</span>
          </div>
        </div>
      ))}
      {rows.length > 8 && <p style={{ fontSize: fs(1.25), color: C.muted }}>Top 8 de {rows.length}</p>}
    </div>
  );
}

const Empty = ({ text = 'Aún sin datos' }) => <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '12cqw', fontSize: fs(3), color: C.muted, fontWeight: 700 }}>{text}</div>;
const Grid = ({ cols = 3, children, gap = 1.4 }) => <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gap: `${gap}cqw` }}>{children}</div>;
const H = ({ children }) => <p style={{ fontSize: fs(1.6), color: C.gold, fontWeight: 700, margin: '0 0 0.8cqw' }}>{children}</p>;

function Slide({ title, kicker, children, footer }) {
  return (
    <div className="present-slide" style={{ position: 'absolute', inset: 0, padding: '2.6cqw 3.4cqw 3.2cqw', display: 'flex', flexDirection: 'column', color: C.text, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '2cqw' }}>
        <h2 style={{ fontSize: fs(3.2), fontWeight: 800, margin: 0, lineHeight: 1.1 }}>{title}</h2>
        <span style={{ fontSize: fs(1.25), color: C.muted, whiteSpace: 'nowrap' }}>{kicker}</span>
      </div>
      <div style={{ flex: 1, minHeight: 0, marginTop: '1.8cqw', display: 'flex', flexDirection: 'column', gap: '1.6cqw' }}>{children}</div>
      {footer && <p style={{ fontSize: fs(1.25), color: C.muted, marginTop: '1cqw' }}>{footer}</p>}
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
  const weekNote = dayMode ? `Acumulado de la semana: ${wk.houses_visited ?? 0} viviendas · ${wk.people_reached ?? 0} personas · ${wk.wants_followup ?? 0} quieren seguimiento · Día ${period.index} de ${period.days_total}` : null;
  const slides = [];
  const add = (key, render, hasData = true) => { if (hasData !== 'skip') slides.push({ key, render: () => render() }); };
  const none = dayMode ? 'Sin registros ese día' : 'Aún sin datos';
  const zero = dayMode ? 'sin registros' : undefined;
  // Metas: las tasas (0–1) se muestran como porcentaje.
  const goalText = (row) => { const ratio = row.goal != null && row.goal <= 1 && (row.value == null || row.value <= 1.0001); const show = (value) => (value == null ? '—' : ratio ? `${Math.round(value * 100)}%` : value); return `${show(row.value)} de ${show(row.goal)}`; };

  add('cover', () => (
    <div className="present-slide" style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', color: C.text, padding: '4cqw' }}>
      <p style={{ fontSize: fs(1.6), letterSpacing: '0.4em', color: C.gold, fontWeight: 700, textTransform: 'uppercase' }}>Reporte de invasión</p>
      <h1 style={{ fontSize: fs(5.6), fontWeight: 800, lineHeight: 1.05, margin: '1.6cqw 0' }}>{s.name}</h1>
      <p style={{ fontSize: fs(3), fontWeight: 700, color: C.text }}>{dayMode ? `Reporte del ${ORDINALS[period.index - 1] || `día ${period.index}`} día — ${period.label}` : `Reporte de la semana — ${fmtDate(s.start_date)}${s.end_date && s.end_date !== s.start_date ? ` al ${fmtDate(s.end_date)}` : ''}`}</p>
      {s.location && <p style={{ fontSize: fs(2.2), color: C.muted, marginTop: '1cqw' }}>{s.location}</p>}
      <p style={{ marginTop: '2.4cqw', fontSize: fs(1.6), padding: '0.6cqw 1.8cqw', borderRadius: '99cqw', border: `0.15cqw solid ${r.mode === 'final' ? C.green : C.amber}`, color: r.mode === 'final' ? C.green : C.amber }}>{r.mode === 'final' ? 'Reporte final' : 'En curso · datos en vivo'}</p>
    </div>
  ));

  add('summary', () => (
    <Slide title="Resumen" kicker={kicker} footer={weekNote}>
      <Grid cols={3}>
        <Fig value={k.houses_visited} label="Viviendas visitadas" color={C.blue} day={dayMode} />
        <Fig value={k.people_reached} label="Personas alcanzadas" color={C.green} day={dayMode} />
        <Fig value={k.attended} label={`Asistieron${k.participants ? ` de ${k.participants} invitados` : ''}`} color={C.gold} day={dayMode} />
        <Fig value={k.wants_followup} label="Quieren seguimiento" color={C.teal} day={dayMode} />
        <Fig value={k.to_consolidation} label="Pasaron a Consolidación" color={C.violet} day={dayMode} />
        <Fig value={books.delivered} label="Libros entregados" color={C.amber} day={dayMode} />
      </Grid>
    </Slide>
  ));

  add('funnel', () => (
    <Slide title="Del invitado a la Consolidación" kicker={kicker} footer={weekNote}>
      <Bars rows={[
        { label: 'Invitados', value: k.participants, color: C.muted }, { label: 'Asistieron', value: k.attended, color: C.gold },
        { label: 'Viviendas visitadas', value: k.houses_visited, color: C.blue }, { label: 'Personas alcanzadas', value: k.people_reached, color: C.green },
        { label: 'Quieren seguimiento', value: k.wants_followup, color: C.teal }, { label: 'Pasaron a Consolidación', value: k.to_consolidation, color: C.violet },
      ]} zeroText={zero} emptyText={none} />
    </Slide>
  ));

  const totals = part.totals || {};
  add('participation', () => (
    <Slide title="Participación" kicker={kicker} footer="La pastora/pastor general supervisa y no cuenta en estas cifras.">
      <Grid cols={4}>
        <Fig value={totals.invited} label="Invitados" />
        <Fig value={totals.confirmed} label="Confirmaron" color={C.blue} />
        <Fig value={totals.attended} label={dayMode ? 'Asistieron ese día' : 'Asistieron'} color={C.green} day={dayMode} />
        <Fig value={totals.attendance_pct} suffix="%" label="Asistencia" color={C.gold} day={dayMode} />
      </Grid>
      <Grid cols={2}>
        <div><H>Asistencia por rol</H><Bars rows={(part.by_role || []).filter((row) => row.invited).map((row) => ({ label: row.label, value: row.attendance_pct || 0, text: `${row.attended} de ${row.invited} · ${row.attendance_pct ?? 0}%` }))} max={100} color={C.green} /></div>
        <div><H>Por Grupo Frontal</H><Bars rows={(part.by_group || []).map((row) => ({ label: row.name, value: row.attendance_pct || 0, text: `${row.attended} de ${row.invited} · ${row.attendance_pct ?? 0}%` }))} max={100} color={C.teal} /></div>
      </Grid>
    </Slide>
  ), (part.totals?.invited ? true : 'skip'));

  const mentors = r.ranking?.mentors || [];
  add('ranking', () => (
    <Slide title="Mentores y equipos" kicker={kicker}>
      <Grid cols={2}>
        <div><H>Personas alcanzadas por mentor</H><Bars rows={[...mentors].sort((a, b) => b.people - a.people || b.houses_visited - a.houses_visited).map((row) => ({ label: row.name, value: row.people, text: `${row.people} pers. · ${row.houses_visited} viv.` }))} color={C.blue} emptyText={none} /></div>
        <div><H>Por equipo (Grupo Frontal)</H><Bars rows={(r.ranking?.teams || []).map((row) => ({ label: row.name, value: row.people, text: `${row.people} pers. · ${row.houses_visited} viv.` }))} color={C.violet} emptyText={none} /></div>
      </Grid>
    </Slide>
  ), mentors.some((row) => row.people || row.houses_visited) ? true : (dayMode ? true : 'skip'));

  add('field', () => (
    <Slide title="Resultados de campo" kicker={kicker} footer={doors.attempts ? `${doors.attempts} intento(s) en ${doors.houses_visited} vivienda(s): cada vivienda cuenta una vez; cada apartamento es una vivienda.` : null}>
      <Grid cols={4}>
        <Fig value={doors.houses_visited} label="Viviendas visitadas" color={C.blue} day={dayMode} />
        <Fig value={doors.opened} label="Abrieron" color={C.green} day={dayMode} />
        <Fig value={doors.not_opened} label="No abrieron" color={C.muted} day={dayMode} />
        <Fig value={doors.conversed} label="Conversamos" color={C.teal} day={dayMode} />
        <Fig value={doors.invited_in} label="Nos invitaron a pasar" color={C.gold} day={dayMode} />
        <Fig value={doors.books} label="Libros entregados" color={C.amber} day={dayMode} />
        <Fig value={doors.followup_people} label="Aceptaron seguimiento" color={C.violet} day={dayMode} />
        <Fig value={doors.people} label="Personas registradas" color={C.text} day={dayMode} />
      </Grid>
    </Slide>
  ));

  const streets = r.field?.doors?.by_street || [];
  add('streets', () => (
    <Slide title="Calles trabajadas" kicker={kicker}>
      {streets.length === 0 ? <Empty text={dayMode ? 'Sin calles registradas ese día' : 'Aún sin datos'} /> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8cqw' }}>
          {streets.slice(0, 8).map((row) => (
            <div key={row.street_key || row.name} style={{ display: 'grid', gridTemplateColumns: '30% 1fr auto', gap: '1.4cqw', alignItems: 'center', background: C.card, borderRadius: '0.9cqw', padding: '0.9cqw 1.4cqw' }}>
              <span style={{ fontSize: fs(1.7), fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.name}</span>
              <span style={{ fontSize: fs(1.45), color: C.muted }}>{row.houses_visited} viviendas · {row.opened} abrieron · {row.books} libros{row.mentors?.length ? ` · ${row.mentors.join(', ')}` : ''}</span>
              <span style={{ fontSize: fs(1.45), color: C.gold, whiteSpace: 'nowrap' }}>{row.started_at ? `${fmtTime(row.started_at)}–${row.ended_at ? fmtTime(row.ended_at) : 'activa'}${row.duration_minutes != null ? ` · ${duration(row.duration_minutes)}` : ''}` : ''}</span>
            </div>
          ))}
          {streets.length > 8 && <p style={{ fontSize: fs(1.25), color: C.muted }}>Top 8 de {streets.length} calles</p>}
        </div>
      )}
    </Slide>
  ));

  add('map', () => (
    <Slide title="Mapa de las viviendas" kicker={kicker} footer="Puntos por estado de la puerta (toda la invasión).">
      <div style={{ flex: 1, minHeight: 0, borderRadius: '1cqw', overflow: 'hidden' }} className="present-map">
        <InvasionHousesMap campaigns={[{ campaign_id: campaignId, name: s.name }]} colorBy="door" fixedHeight={mapHeight} />
      </div>
    </Slide>
  ), (r.field?.houses?.located ? true : 'skip'));

  add('followup', () => (
    <Slide title="Seguimiento y Consolidación" kicker={kicker}>
      <Grid cols={4}>
        <Fig value={follow.wants_followup} label="Quieren seguimiento" color={C.teal} day={dayMode} />
        <Fig value={follow.to_consolidation} label="Pasaron a Consolidación" color={C.violet} day={dayMode} />
        <Fig value={follow.attended} label="Ya atendidas" color={C.green} day={dayMode} />
        <Fig value={follow.unattended} label={`Sin atender (> ${follow.unattended_hours || 48} h)`} color={follow.unattended ? C.red : C.text} day={dayMode} />
      </Grid>
      <div><H>Tiempo hasta el primer contacto</H><Bars rows={(follow.first_contact || []).map((row) => ({ label: row.bucket, value: row.total, color: row.bucket === 'Sin contacto' ? C.red : C.teal }))} emptyText={none} /></div>
    </Slide>
  ));

  add('books', () => (
    <Slide title="Libros entregados" kicker={kicker}>
      <Grid cols={3}>
        <Fig value={books.delivered} label="Libros entregados" color={C.amber} day={dayMode} />
        <Fig value={books.identified} label="Con destinatario" color={C.green} day={dayMode} />
        <Fig value={books.with_followup} label="Con seguimiento" color={C.violet} day={dayMode} />
      </Grid>
      <Grid cols={2}>
        <div><H>Por material</H><Bars rows={(books.by_material || []).map((row) => ({ label: row.name, value: row.total }))} color={C.amber} emptyText={none} /></div>
        <div><H>Por mentor</H><Bars rows={(books.by_mentor || []).map((row) => ({ label: row.name, value: row.total }))} color={C.blue} emptyText={none} /></div>
      </Grid>
    </Slide>
  ), (books.delivered || dayMode ? true : 'skip'));

  const prayer = week?.prayer;
  add('prayer', () => (
    <Slide title="Preparación en oración" kicker={`${s.name} · semana de preparación`}>
      <Grid cols={3}>
        <Fig value={prayer.totals?.prayed_any_pct} suffix="%" label="Participantes que oraron" color={C.gold} />
        <Fig value={prayer.totals?.avg_days} label="Días de oración en promedio" color={C.teal} />
        <Fig value={prayer.totals?.meetings_held} label="Reuniones de oración realizadas" color={C.blue} />
      </Grid>
      <div><H>Oraron por semana</H><Bars rows={(prayer.by_week || []).map((row) => ({ label: row.week, value: row.pct, text: `${row.prayed} · ${row.pct}%` }))} max={100} color={C.gold} /></div>
    </Slide>
  ), (prayer?.totals?.participants ? true : 'skip'));

  const help = r.help_alerts || {};
  add('help', () => (
    <Slide title="Alertas de ayuda" kicker={kicker}>
      <Grid cols={3}>
        <Fig value={help.total} label="Alertas" color={help.total ? C.amber : C.text} />
        <Fig value={help.resolved} label="Atendidas" color={C.green} />
        <Fig value={help.avg_response_minutes} suffix=" min" label="Tiempo promedio de respuesta" color={C.blue} />
      </Grid>
      <div><H>Motivo</H><Bars rows={(help.by_reason || []).filter((row) => row.total).map((row) => ({ label: row.label, value: row.total }))} color={C.amber} /></div>
    </Slide>
  ), (help.total ? true : 'skip'));

  const goals = week?.goals?.items || [];
  const sem = { verde: C.green, ambar: C.amber, rojo: C.red };
  add('goals', () => (
    <Slide title="Metas de la semana" kicker={`${s.name} · acumulado`} footer={dayMode ? `Día ${period.index} de ${period.days_total}: avance acumulado de la semana.` : null}>
      <Bars rows={goals.map((row) => ({ label: row.label, value: row.progress == null ? 0 : Math.round(row.progress * 100), color: sem[row.semaphore] || C.muted, text: `${goalText(row)}${row.progress == null ? '' : ` · avance ${Math.round(row.progress * 100)}%`}` }))} max={100} />
    </Slide>
  ), (goals.length ? true : 'skip'));

  const comparison = week?.comparison || [];
  add('comparison', () => (
    <Slide title="Comparado con invasiones anteriores" kicker="Personas alcanzadas (semana completa)">
      <Bars rows={comparison.map((row) => ({ label: row.current ? `${row.name} (esta)` : row.name, value: row.people, color: row.current ? C.gold : C.blue, text: `${row.people} pers. · ${row.followup} seguim.` }))} />
    </Slide>
  ), (comparison.length > 1 ? true : 'skip'));

  const recs = (week?.recommendations || []).filter((item) => !item.resolved).slice(0, 3);
  add('recommendations', () => (
    <Slide title="Recomendaciones" kicker="Según los datos (semana)">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2cqw' }}>
        {recs.map((item) => (
          <div key={item.id} style={{ background: C.card, borderLeft: `0.6cqw solid ${item.priority === 'alta' ? C.red : item.priority === 'media' ? C.amber : C.blue}`, borderRadius: '0.9cqw', padding: '1.2cqw 1.6cqw' }}>
            <p style={{ fontSize: fs(2), fontWeight: 800, margin: 0 }}>{item.title}</p>
            <p style={{ fontSize: fs(1.5), color: C.muted, marginTop: '0.4cqw' }}>{item.evidence?.label}: {item.evidence?.value}{item.evidence?.total ? ` de ${item.evidence.total}` : ''}{item.responsible ? ` · ${item.responsible}` : ''}</p>
          </div>
        ))}
      </div>
    </Slide>
  ), (recs.length ? true : 'skip'));

  const notes = week?.notes || {};
  const lessons = [['worked', 'Lo que funcionó'], ['improve', 'Qué mejorar'], ['pastor_recommendations', 'Recomendaciones del pastor']].filter(([key]) => (notes[key] || '').trim());
  add('lessons', () => (
    <Slide title="Lecciones aprendidas" kicker={s.name}>
      <Grid cols={lessons.length > 1 ? lessons.length : 1}>
        {lessons.map(([key, label]) => <div key={key} style={{ background: C.card, borderRadius: '1cqw', padding: '1.4cqw' }}><H>{label}</H><p style={{ fontSize: fs(1.6), lineHeight: 1.35, whiteSpace: 'pre-line', display: '-webkit-box', WebkitLineClamp: 9, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{notes[key]}</p></div>)}
      </Grid>
    </Slide>
  ), (lessons.length ? true : 'skip'));

  const highlights = [
    k.people_reached ? `${k.people_reached} persona(s) alcanzada(s)${dayMode ? ' este día' : ''}` : null,
    k.houses_visited ? `${k.houses_visited} vivienda(s) visitada(s)${doors.opened ? `, abrieron ${doors.opened}` : ''}` : null,
    k.wants_followup ? `${k.wants_followup} quieren seguimiento${k.to_consolidation ? ` · ${k.to_consolidation} en Consolidación` : ''}` : null,
    books.delivered ? `${books.delivered} libro(s) entregado(s)` : null,
    k.attended ? `${k.attended} servidor(es) asistieron` : null,
  ].filter(Boolean).slice(0, 3);
  const nextDay = dayMode && period.index < period.days_total ? period.days[period.index] : null;
  const nextSteps = [
    doors.pending_revisit ? `Regresar a ${doors.pending_revisit} vivienda(s) donde no abrieron` : null,
    follow.unattended ? `Atender a ${follow.unattended} persona(s) sin contacto` : null,
    follow.wants_followup && follow.to_consolidation < follow.wants_followup ? `Dar seguimiento a ${follow.wants_followup - (follow.to_consolidation || 0)} persona(s) que lo pidieron` : null,
    books.unidentified ? `Completar a quién se entregaron ${books.unidentified} libro(s)` : null,
  ].filter(Boolean).slice(0, 3);
  add('thanks', () => (
    <div className="present-slide" style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '4cqw 6cqw', color: C.text }}>
      <h2 style={{ fontSize: fs(6), fontWeight: 800, margin: 0, color: C.gold }}>¡Gracias!</h2>
      {highlights.length > 0 && <ul style={{ marginTop: '2cqw', display: 'flex', flexDirection: 'column', gap: '0.8cqw', fontSize: fs(2.4), fontWeight: 700 }}>{highlights.map((line) => <li key={line}>• {line}</li>)}</ul>}
      {nextDay && <div style={{ marginTop: '2.6cqw' }}><p style={{ fontSize: fs(1.8), color: C.gold, fontWeight: 700 }}>Qué sigue para el día {nextDay.index} ({nextDay.label})</p>
        <ul style={{ marginTop: '0.6cqw', fontSize: fs(1.8), color: C.text, display: 'flex', flexDirection: 'column', gap: '0.4cqw' }}>{(nextSteps.length ? nextSteps : ['Seguir con las calles y viviendas pendientes']).map((line) => <li key={line}>→ {line}</li>)}</ul></div>}
    </div>
  ));
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
    style.textContent = '@page { size: 13.333in 7.5in; margin: 0; } @media print { html, body { background: #070d1c !important; } }';
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
  useEffect(() => {
    const onKey = (event) => {
      if (exclusions || event.target?.tagName === 'SELECT') return;
      if (['ArrowRight', 'PageDown', ' ', 'Enter', 'ArrowDown'].includes(event.key)) { event.preventDefault(); go(1); }
      else if (['ArrowLeft', 'PageUp', 'Backspace', 'ArrowUp'].includes(event.key)) { event.preventDefault(); go(-1); }
      else if (event.key === 'Home') setIndex(0);
      else if (event.key === 'End') setIndex(total - 1);
      else if (event.key.toLowerCase() === 'f') fullscreen();
      else if (event.key.toLowerCase() === 'g') setHideUi((value) => !value);
      else if (event.key === '+' || event.key === '=') increment();
      else if (event.key === '-') decrement();
    };
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, [go, total, exclusions, increment, decrement]);
  const setDayIndex = (value) => { const next = new URLSearchParams(params); next.set('dia', String(value)); setParams(next, { replace: true }); setIndex(0); };
  const days = week?.period?.days || [];
  const stageStyle = { width: stageSize.width, height: stageSize.height, containerType: 'inline-size', position: 'relative', background: C.bg, overflow: 'hidden', '--z': zoom, fontFamily: 'Inter, system-ui, sans-serif' };

  if (error) return <div style={{ position: 'fixed', inset: 0, background: C.bg, color: C.text, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, fontSize: 22, textAlign: 'center' }} data-testid="present-error">{error}</div>;
  if (!week) return <div style={{ position: 'fixed', inset: 0, background: C.bg, color: C.muted, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24 }}>Cargando reporte…</div>;
  const current = slides[index];
  const pageHeader = period ? `Día ${period.index} · ${period.label}` : 'Toda la semana';

  return (
    <div className="present-root" style={{ position: 'fixed', inset: 0, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, userSelect: 'none' }} data-testid="present-page">
      <div ref={stageRef} className="present-stage" style={stageStyle} data-testid="present-stage" data-slide={current?.key}
        onClick={(event) => { const rect = event.currentTarget.getBoundingClientRect(); go(event.clientX - rect.left > rect.width / 3 ? 1 : -1); }}>
        {current?.render()}
        <div style={{ position: 'absolute', left: 0, bottom: 0, height: '0.35cqw', width: `${((index + 1) / Math.max(1, total)) * 100}%`, background: C.gold, transition: 'width .2s' }} data-testid="present-progress" />
        {!hideUi && <span style={{ position: 'absolute', right: '1.2cqw', bottom: '0.9cqw', fontSize: fs(1.1), color: C.muted }}>{index + 1} / {total}</span>}
      </div>

      {/* Todas las láminas para el PDF de respaldo (una por página, con el día en el encabezado). */}
      <div className="present-print">
        {slides.filter((slide) => slide.key !== 'map').map((slide) => (
          <div key={slide.key} style={{ width: '13.333in', height: '7.5in', containerType: 'inline-size', position: 'relative', background: C.bg, overflow: 'hidden', breakAfter: 'page', '--z': 1 }}>
            <span style={{ position: 'absolute', top: '0.8cqw', right: '1.2cqw', fontSize: '1cqw', color: C.muted, zIndex: 2 }}>{week.summary.name} · {pageHeader}</span>
            {slide.render()}
          </div>
        ))}
      </div>

      {!hideUi && !idle && (
        <div className="present-ui" style={{ position: 'fixed', top: 8, left: 8, right: 8, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', justifyContent: 'space-between', pointerEvents: 'none' }} data-testid="present-toolbar">
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', pointerEvents: 'auto' }}>
            <select value={dayIndex} onChange={(event) => setDayIndex(parseInt(event.target.value, 10))} style={{ height: 40, borderRadius: 10, padding: '0 10px', background: '#111a2e', color: '#fff', border: '1px solid #24304a', fontSize: 15 }} data-testid="present-day">
              {days.map((item) => <option key={item.day} value={item.index}>Día {item.index} · {item.label}</option>)}
              <option value={0}>Toda la semana (acumulado)</option>
            </select>
            <Link to={`/invasiones/${campaignId}/reporte${dayIndex ? `?dia=${dayIndex}` : ''}`} style={btn} data-testid="present-one-page"><FileText size={16} />Ver todo en una página</Link>
            <button type="button" onClick={() => window.print()} style={btn} data-testid="present-pdf"><Download size={16} />Descargar PDF</button>
            {canExclude && <button type="button" onClick={() => setExclusions(true)} style={btn} data-testid="present-exclusions-open"><UserX size={16} />Cuentas de prueba</button>}
          </div>
          <div style={{ display: 'flex', gap: 6, pointerEvents: 'auto' }}>
            <button type="button" onClick={decrement} style={btn} aria-label="Texto más pequeño">A−</button>
            <button type="button" onClick={increment} style={btn} aria-label="Texto más grande">A+</button>
            <button type="button" onClick={() => go(-1)} style={btn} aria-label="Anterior"><ChevronLeft size={18} /></button>
            <button type="button" onClick={() => go(1)} style={btn} aria-label="Siguiente" data-testid="present-next"><ChevronRight size={18} /></button>
            <button type="button" onClick={fullscreen} style={btn} title="Pantalla completa (F)"><Maximize size={16} /></button>
            <button type="button" onClick={() => setHideUi(true)} style={btn} title="Ocultar controles (G)"><EyeOff size={16} /></button>
          </div>
        </div>
      )}
      {exclusions && <ExclusionsDialog onClose={() => setExclusions(false)} onSaved={load} />}
    </div>
  );
}

const btn = { display: 'inline-flex', alignItems: 'center', gap: 6, height: 40, padding: '0 12px', borderRadius: 10, background: 'rgba(17,26,46,0.85)', color: '#fff', border: '1px solid #24304a', fontSize: 14, fontWeight: 600, cursor: 'pointer', textDecoration: 'none' };
