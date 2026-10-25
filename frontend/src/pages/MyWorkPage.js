import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { BookOpen, CalendarClock, ClipboardList, DoorOpen, Home, Info, Loader2, Map as MapIcon, MessageCircle, Sprout, UserCheck, Users } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { OUTREACH_CHANGED_EVENT } from '../context/InvasionTodayContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { RevisitSheet, ScheduleDialog } from '../components/doors/PendingDoors';
import { InvasionHousesMap } from '../components/outreach/InvasionHousesMap';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';

const FIGURES = [
  ['visited', 'Viviendas visitadas', Home], ['opened', 'Abrieron', DoorOpen], ['pending_return', 'Pendientes de regresar', CalendarClock],
  ['people_to_attend', 'Personas por atender', Users], ['started_consolidation', 'Comenzaron consolidación', Sprout],
];
const BUCKETS = [['overdue', 'Con fecha pasada'], ['today', 'Hoy'], ['upcoming', 'Próximos'], ['no_date', 'Sin fecha programada']];
const NEXT_ACTIONS = ['Visitar de nuevo', 'Llamar por teléfono', 'Enviar mensaje', 'Invitar a la iglesia'];
// Fecha de hoy en el calendario local (AAAA-MM-DD) para programar con un toque.
const localToday = () => { const now = new Date(); return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
const fmtDay = (iso) => (iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString('es', { weekday: 'short', day: 'numeric', month: 'short' }) : '');

// Seguimiento de una persona contactada: próxima acción y fecha (no inicia Consolidación).
function FollowupDialog({ item, onClose, onSaved }) {
  const { API, getAuthHeaders } = useAuth();
  const [action, setAction] = useState('');
  const [day, setDay] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { setAction(item?.next_action && NEXT_ACTIONS.includes(item.next_action) ? item.next_action : 'Llamar por teléfono'); setDay(item?.due_date || localToday()); }, [item]);
  const save = async () => {
    setBusy(true);
    try {
      await axios.put(`${API}/api/mentorship/outreach/visits/${item.visit_id}/followup`, { accepted: true, next_action: action, next_action_date: day || null }, getAuthHeaders());
      toast.success('Seguimiento actualizado', { id: 'my-work-saved' }); onSaved(); onClose();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); } finally { setBusy(false); }
  };
  return (
    <Dialog open={Boolean(item)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="vv-fit bg-white sm:max-w-md" data-testid="my-work-followup">
        <DialogHeader><DialogTitle>{item?.title}</DialogTitle><DialogDescription>Registra el contacto y programa la próxima atención.</DialogDescription></DialogHeader>
        <div className="grid grid-cols-2 gap-2">{NEXT_ACTIONS.map((value) => <button key={value} type="button" onClick={() => setAction(value)} aria-pressed={action === value} className={`min-h-12 rounded-xl border-2 px-2 text-[15px] font-semibold ${action === value ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-[#101D36]'}`}>{value}</button>)}</div>
        <label className="block"><span className="text-sm font-semibold text-slate-700">Fecha</span><input type="date" value={day} onChange={(event) => setDay(event.target.value)} className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="my-work-followup-date" /></label>
        <div className="sticky-actions"><button type="button" onClick={save} disabled={busy} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-60" data-testid="my-work-followup-save">{busy && <Loader2 className="h-5 w-5 animate-spin" />}Guardar</button></div>
      </DialogContent>
    </Dialog>
  );
}

// Lo que compone una cifra del resumen.
function FigureList({ query, onClose }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const last = useRef(null);
  if (query) last.current = query;
  const current = query || last.current;
  useEffect(() => {
    if (!query) return;
    setData(null);
    axios.get(`${API}/api/my-work/summary/${query.metric}`, { ...getAuthHeaders(), params: { ...query.params, limit: 100 } }).then((response) => setData(response.data)).catch(() => setData({ items: [], total: 0 }));
  }, [API, getAuthHeaders, query]);
  if (!current) return null;
  return (
    <Dialog open={Boolean(query)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="bg-white sm:max-w-lg" data-testid="my-work-figure-list">
        <DialogHeader><DialogTitle>{current.label}</DialogTitle><DialogDescription>{data ? `${data.total} registro(s)` : 'Cargando…'}</DialogDescription></DialogHeader>
        {!data ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : data.items.length === 0 ? <p className="text-base text-slate-500">Aún sin registros.</p> : (
          <ul className="divide-y divide-[#EEECE6]">{data.items.map((item) => (
            <li key={item.household_id || item.visit_id || item.id} className="py-2">
              <p className="text-[15px] font-semibold text-[#101D36]">{item.address_line1 ? `${item.address_line1}${item.address_line2 ? ` · ${item.address_line2}` : ''}` : item.title || item.name || item.contact_name || 'Persona'}</p>
              <p className="text-sm text-slate-600">{item.subtitle || (item.attempts_count != null ? `${item.attempts_count} intento(s)` : '')}{item.last_attempt_at ? ` · última: ${fmtDay(item.last_attempt_at)}` : ''}{item.next_action ? ` · ${item.next_action}` : ''}</p>
            </li>))}</ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

function PendingCard({ item, onRevisit, onSchedule, onFollowup, readOnly = false, selectable = false, selected = false, onSelect }) {
  return (
    <li className={`rounded-2xl border bg-white p-3 shadow-sm ${selected ? 'border-[#132443] ring-2 ring-[#132443]/20' : 'border-[#E8E5DE]'}`} data-testid={`my-work-item-${item.kind}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-base font-semibold text-[#101D36]">{item.kind === 'household' ? <Home className="h-4 w-4 shrink-0 text-[#9A7A2F]" /> : <UserCheck className="h-4 w-4 shrink-0 text-[#9A7A2F]" />}<span className="truncate">{item.title}</span></p>
          {item.subtitle && <p className="truncate text-sm text-slate-600">{item.kind === 'person' ? `Etapa: ${item.subtitle}` : item.subtitle}</p>}
          <p className="text-sm text-slate-600">Última atención: {item.last_at ? fmtDay(item.last_at) : '—'}{item.last_result ? ` · ${item.last_result}` : ''}</p>
          <p className="text-sm font-semibold text-[#132443]">Próximo: {item.next_action}{item.due_date ? ` · ${fmtDay(item.due_date)}` : ''}</p>
          {item.campaign_name && <p className="text-xs text-slate-500">Invasión de origen: {item.campaign_name}</p>}
        </div>
        {selectable && <input type="checkbox" checked={selected} onChange={(event) => onSelect(event.target.checked)} className="mt-1 h-6 w-6 shrink-0 accent-[#132443]" aria-label={`Seleccionar ${item.title}`} data-testid="my-work-select" />}
      </div>
      {!readOnly && <div className="mt-2 grid grid-cols-2 gap-2">
        {item.kind === 'household' && <>
          <button type="button" onClick={() => onRevisit(item)} className="min-h-11 rounded-xl bg-[#132443] text-[15px] font-semibold text-white" data-testid="my-work-revisit">Registrar visita</button>
          <button type="button" onClick={() => onSchedule(item)} className="min-h-11 rounded-xl border border-[#D9D4C7] bg-white text-[15px] font-semibold text-[#101D36]" data-testid="my-work-schedule">Reprogramar</button>
        </>}
        {item.kind === 'contact' && <>
          <button type="button" onClick={() => onFollowup(item)} className="min-h-11 rounded-xl bg-[#132443] text-[15px] font-semibold text-white" data-testid="my-work-contact">Registrar contacto</button>
          <button type="button" onClick={() => onFollowup(item)} className="min-h-11 rounded-xl border border-[#D9D4C7] bg-white text-[15px] font-semibold text-[#101D36]">Reprogramar</button>
        </>}
        {item.kind === 'person' && <>
          <Link to={`/procesos/consolidacion/${item.enrollment_id}`} className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[#132443] text-[15px] font-semibold text-white" data-testid="my-work-progress">Registrar avance</Link>
          <Link to={`/personas/${item.person_id}`} className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#D9D4C7] bg-white text-[15px] font-semibold text-[#101D36]">Perfil</Link>
        </>}
      </div>}
    </li>
  );
}

const PEOPLE_FILTERS = [['all', 'Todas'], ['no_next', 'Sin próxima atención'], ['followup', 'Seguimiento aceptado'], ['consolidation', 'En Consolidación']];
const HOUSE_FILTERS = [['all', 'Todas'], ['pending', 'Pendientes'], ['visited', 'Visitadas']];
const STATUS_TONE = { contacted: 'bg-amber-100 text-amber-900', followup: 'bg-sky-100 text-sky-900', consolidation: 'bg-emerald-100 text-emerald-900' };

/** Etiqueta del mentor con su trabajo real (no solo pendientes). */
export const mentorLabel = (item) => `${item.name} · ${item.houses_visited ?? item.households} vivienda(s) visitada(s) · ${item.books_delivered ?? 0} libro(s) · ${item.people_contacted ?? item.people} persona(s) contactada(s) · ${item.pending ?? 0} pendiente(s)`;

function Chips({ options, value, onChange, counts = {}, testId }) {
  return (
    <div className="flex flex-wrap gap-1.5" data-testid={testId}>
      {options.map(([key, label]) => <button key={key} type="button" onClick={() => onChange(key)} aria-pressed={value === key} className={`min-h-11 rounded-full border px-3 text-[15px] font-semibold ${value === key ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-[#101D36]'}`} data-testid={`${testId}-${key}`}>{label}{counts[key] != null ? ` (${counts[key]})` : ''}</button>)}
    </div>
  );
}

// «Mis personas»: TODAS las que contactó o a las que entregó libro, con su estado.
function PersonRow({ item, readOnly, onSchedule, onStart }) {
  return (
    <li className="rounded-2xl border border-[#E8E5DE] bg-white p-3 shadow-sm" data-testid="my-work-person">
      <div className="flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
        <p className="flex min-w-0 items-center gap-1.5 text-base font-semibold text-[#101D36]"><UserCheck className="h-4 w-4 shrink-0 text-[#9A7A2F]" /><span className="truncate">{item.title}</span></p>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_TONE[item.status] || ''}`} data-testid="my-work-person-status">{item.status_label}</span>
      </div>
      {item.address && <p className="truncate text-sm text-slate-600">{item.address}</p>}
      <p className="text-sm text-slate-600">Última atención: {item.last_at ? fmtDay(item.last_at) : '—'}{item.books ? ` · ${item.books} libro(s)` : ''}{item.stage ? ` · Etapa: ${item.stage}` : ''}</p>
      {item.due_date && <p className="text-sm font-semibold text-[#132443]">Próximo: {item.next_action || 'Seguimiento'} · {fmtDay(item.due_date)}</p>}
      {item.campaign_name && <p className="text-xs text-slate-500">Invasión de origen: {item.campaign_name}</p>}
      <div className="mt-2 grid grid-cols-2 gap-2">
        {!readOnly && item.can_schedule && <button type="button" onClick={() => onSchedule(item)} className="min-h-11 rounded-xl bg-[#132443] text-[15px] font-semibold text-white" data-testid="my-work-person-schedule">Programar</button>}
        {!readOnly && item.can_start_consolidation && <button type="button" onClick={() => onStart(item)} className="min-h-11 rounded-xl border border-[#132443] bg-white text-[15px] font-semibold text-[#132443]" data-testid="my-work-person-start">Pasar a Consolidación</button>}
        {item.enrollment_id && <Link to={`/procesos/consolidacion/${item.enrollment_id}`} className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#D9D4C7] bg-white text-[15px] font-semibold text-[#101D36]">Expediente</Link>}
        {item.person_id && <Link to={`/personas/${item.person_id}`} className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#D9D4C7] bg-white text-[15px] font-semibold text-[#101D36]" data-testid="my-work-person-profile">Perfil</Link>}
      </div>
    </li>
  );
}

function HouseRow({ item, readOnly, onRevisit, onSchedule }) {
  return (
    <li className="rounded-2xl border border-[#E8E5DE] bg-white p-3 shadow-sm" data-testid="my-work-house">
      <div className="flex items-start justify-between gap-2">
        <p className="flex min-w-0 items-center gap-1.5 text-base font-semibold text-[#101D36]"><Home className="h-4 w-4 shrink-0 text-[#9A7A2F]" /><span className="truncate">{item.title}</span></p>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${item.pending ? 'bg-amber-100 text-amber-900' : 'bg-emerald-100 text-emerald-900'}`}>{item.pending ? 'Pendiente' : item.attempts_count ? 'Visitada' : 'Sin visitar'}</span>
      </div>
      <p className="text-sm text-slate-600">{item.attempts_count || 0} intento(s){item.last_attempt_at ? ` · última: ${fmtDay(item.last_attempt_at)}` : ''}{item.last_result_label ? ` · ${item.last_result_label}` : ''}{item.books_total ? ` · ${item.books_total} libro(s)` : ''}</p>
      {item.followup_date && <p className="text-sm font-semibold text-[#132443]">Próxima visita: {fmtDay(item.followup_date)}</p>}
      {item.campaign_name && <p className="text-xs text-slate-500">Invasión: {item.campaign_name}</p>}
      {!readOnly && item.kind === 'household' && <div className="mt-2 grid grid-cols-2 gap-2">
        <button type="button" onClick={() => onRevisit(item)} className="min-h-11 rounded-xl bg-[#132443] text-[15px] font-semibold text-white" data-testid="my-work-house-revisit">Registrar visita</button>
        <button type="button" onClick={() => onSchedule(item)} className="min-h-11 rounded-xl border border-[#D9D4C7] bg-white text-[15px] font-semibold text-[#101D36]">{item.pending ? 'Reprogramar' : 'Programar'}</button>
      </div>}
    </li>
  );
}

/** MT2 · «Mi Trabajo»: inicio del mentor. Resumen arriba, pendientes debajo
 * (con fecha pasada → hoy → próximos) y accesos a Mis viviendas / Mis personas. */
// MT3: reasignar los pendientes elegidos a otro mentor (historial + aviso al nuevo mentor).
function ReassignDialog({ open, count, mentors, currentMentor, onClose, onConfirm }) {
  const [target, setTarget] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setTarget(''); setReason(''); } }, [open]);
  const run = async () => { setBusy(true); try { await onConfirm(target, reason.trim()); } finally { setBusy(false); } };
  return (
    <Dialog open={open} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="vv-fit bg-white sm:max-w-md" data-testid="my-work-reassign-dialog">
        <DialogHeader><DialogTitle>Reasignar {count} pendiente(s)</DialogTitle><DialogDescription>Quién hizo cada atención se conserva; el nuevo mentor recibe un aviso.</DialogDescription></DialogHeader>
        <label className="block"><span className="text-sm font-semibold text-slate-700">Nuevo mentor</span>
          <select value={target} onChange={(event) => setTarget(event.target.value)} className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" data-testid="my-work-reassign-target"><option value="">Elegir…</option>{mentors.filter((item) => item.person_id !== currentMentor).map((item) => <option key={item.person_id} value={item.person_id}>{item.name} · {item.pending ?? 0} pendiente(s)</option>)}</select></label>
        <label className="block"><span className="text-sm font-semibold text-slate-700">Motivo</span><input value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" placeholder="Ej.: cambio de zona" data-testid="my-work-reassign-reason" /></label>
        <div className="sticky-actions"><button type="button" onClick={run} disabled={busy || !target || reason.trim().length < 3} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-50" data-testid="my-work-reassign-run">{busy && <Loader2 className="h-5 w-5 animate-spin" />}Reasignar</button></div>
      </DialogContent>
    </Dialog>
  );
}

export default function MyWorkPage({ mentorPersonId = null, header = null, supervise = false, mentors = [] }) {
  const { API, getAuthHeaders, user } = useAuth();
  const [params, setParams] = useSearchParams();
  const view = ['viviendas', 'personas'].includes(params.get('vista')) ? params.get('vista') : 'pendientes';
  const [period, setPeriod] = useState('week');
  const [campaignId, setCampaignId] = useState('');
  const [campaigns, setCampaigns] = useState([]);
  const [summary, setSummary] = useState(null);
  const [pending, setPending] = useState(null);
  const [books, setBooks] = useState([]);
  const [figure, setFigure] = useState(null);
  const [revisit, setRevisit] = useState(null);
  const [schedule, setSchedule] = useState(null);
  const [followup, setFollowup] = useState(null);
  const [showMap, setShowMap] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [selected, setSelected] = useState([]);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [peopleFilter, setPeopleFilter] = useState('all');
  const [houseFilter, setHouseFilter] = useState('all');
  const [people, setPeople] = useState(null);
  const [houses, setHouses] = useState(null);
  const [startItem, setStartItem] = useState(null);
  const scopeParams = mentorPersonId ? { mentor_person_id: mentorPersonId } : {};
  const setView = (value) => { const next = new URLSearchParams(params); if (value === 'pendientes') next.delete('vista'); else next.set('vista', value); setParams(next, { replace: true }); };

  const load = useCallback(() => {
    const filter = { period, ...(period === 'invasion' && campaignId ? { campaign_id: campaignId } : {}), ...scopeParams };
    if (period === 'invasion' && !campaignId) return;
    axios.get(`${API}/api/my-work/summary`, { ...getAuthHeaders(), params: filter }).then((response) => setSummary(response.data)).catch((error) => toast.error(apiErrorMessage(error, 'No se pudo cargar Mi Trabajo')));
    if (view === 'pendientes') axios.get(`${API}/api/my-work/pending`, { ...getAuthHeaders(), params: { limit: 100, kind: 'all', ...scopeParams } })
      .then((response) => setPending(response.data)).catch(() => setPending({ items: [], total: 0, counts: {} }));
    // Mis personas / Mis viviendas: TODO el trabajo (no solo pendientes).
    if (view === 'personas') axios.get(`${API}/api/my-work/people`, { ...getAuthHeaders(), params: { status: peopleFilter, ...scopeParams } })
      .then((response) => setPeople(response.data)).catch(() => setPeople({ items: [], total: 0, counts: {} }));
    if (view === 'viviendas') axios.get(`${API}/api/my-work/households`, { ...getAuthHeaders(), params: { state: houseFilter, limit: 200, ...scopeParams } })
      .then((response) => setHouses(response.data)).catch(() => setHouses({ items: [], total: 0 }));
  }, [API, getAuthHeaders, period, campaignId, view, mentorPersonId, peopleFilter, houseFilter]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load, refreshKey]);
  useEffect(() => {
    axios.get(`${API}/api/my-work/campaigns`, { ...getAuthHeaders(), params: scopeParams }).then((response) => setCampaigns(response.data.items || [])).catch(() => setCampaigns([]));
    if (!mentorPersonId) axios.get(`${API}/api/mentorship/outreach/door-books`, getAuthHeaders()).then((response) => setBooks(response.data.items || [])).catch(() => setBooks([]));
  }, [API, getAuthHeaders, mentorPersonId]); // eslint-disable-line react-hooks/exhaustive-deps
  // Se actualiza al guardar una actividad (en esta u otra pantalla).
  useEffect(() => { const refresh = () => setRefreshKey((value) => value + 1); window.addEventListener(OUTREACH_CHANGED_EVENT, refresh); return () => window.removeEventListener(OUTREACH_CHANGED_EVENT, refresh); }, []);
  const saved = () => { setRefreshKey((value) => value + 1); window.dispatchEvent(new Event(OUTREACH_CHANGED_EVENT)); };
  const readOnly = Boolean(mentorPersonId && mentorPersonId !== user?.person_id);
  useEffect(() => { setSelected([]); }, [mentorPersonId, view]);
  const keyOf = (item) => `${item.kind}:${item.id}`;
  const toggle = (item, on) => setSelected((current) => (on ? [...current, keyOf(item)] : current.filter((key) => key !== keyOf(item))));
  const reassign = async (target, reason) => {
    try {
      const response = await axios.post(`${API}/api/my-work/reassign`, { items: selected.map((key) => { const [kind, ...rest] = key.split(':'); return { kind, id: rest.join(':') }; }), to_mentor_person_id: target, reason }, getAuthHeaders());
      toast.success(`${response.data.reassigned} pendiente(s) reasignado(s)`); setReassignOpen(false); setSelected([]); saved();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo reasignar')); }
  };
  const items = pending?.items || [];
  const startConsolidation = async () => {
    try {
      await axios.post(`${API}/api/mentorship/outreach/visits/${startItem.visit_id}/start-seven-weeks`, {}, getAuthHeaders());
      toast.success(`${startItem.title} pasó a Consolidación`); setStartItem(null); saved();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo pasar a Consolidación')); }
  };

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4 p-4 sm:p-6" data-testid="my-work-page">
      {header || <header><p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.2em] text-[#7A5F22]"><ClipboardList className="h-4 w-4" />Mi Trabajo</p><h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">Hola{user?.nombre ? `, ${user.nombre.split(' ')[0]}` : ''}</h1></header>}

      <div className="flex flex-wrap items-center gap-2" data-testid="my-work-filter">
        <div className="grid grid-cols-3 gap-1 rounded-xl bg-[#EEECE6] p-1">{[['week', 'Esta semana'], ['invasion', 'Invasión'], ['all', 'Todo']].map(([key, label]) => <button key={key} type="button" onClick={() => setPeriod(key)} aria-pressed={period === key} className={`min-h-11 rounded-lg px-3 text-[15px] font-semibold ${period === key ? 'bg-white shadow' : 'text-slate-600'}`} data-testid={`my-work-period-${key}`}>{label}</button>)}</div>
        {period === 'invasion' && <select value={campaignId} onChange={(event) => setCampaignId(event.target.value)} className="h-11 min-w-0 flex-1 rounded-lg border border-[#D9D4C7] bg-white px-3 text-[15px]" data-testid="my-work-campaign"><option value="">Elige la invasión…</option>{campaigns.map((item) => <option key={item.campaign_id} value={item.campaign_id}>{item.name}</option>)}</select>}
      </div>

      {summary && <>
        <p className="rounded-xl bg-[#F4F6FA] p-3 text-[15px] text-[#101D36]" data-testid="my-work-message">{summary.message}</p>
        {summary.totals && <div className="grid grid-cols-3 gap-2" data-testid="my-work-totals">
          {[['houses_visited', 'viviendas visitadas', Home], ['people_contacted', 'personas contactadas', Users], ['books_delivered', 'libros entregados', BookOpen]].map(([key, label, Icon]) => (
            <div key={key} className="rounded-xl border border-[#E8E5DE] bg-[#FBFAF7] p-2 text-center"><Icon className="mx-auto h-4 w-4 text-[#9A7A2F]" /><b className="block text-xl text-[#101D36]">{summary.totals[key]}</b><span className="block text-xs leading-4 text-slate-600">{label} (total)</span></div>
          ))}
        </div>}
        {supervise && summary.totals?.inventory && <p className="rounded-xl border border-[#E8E5DE] bg-white p-3 text-[15px] text-[#101D36]" data-testid="my-work-inventory"><BookOpen className="mr-1 inline h-4 w-4 text-[#9A7A2F]" />Inventario de libros: <b>{summary.totals.inventory.received}</b> recibidos · <b>{summary.totals.inventory.delivered}</b> entregados · <b>{summary.totals.inventory.available}</b> disponibles</p>}
        {summary.notices.length > 0 && <ul className="space-y-1" data-testid="my-work-notices">{summary.notices.map((notice) => <li key={notice.key} className="flex flex-wrap items-center gap-2 text-sm text-slate-700"><Info className="h-4 w-4 shrink-0 text-[#0879BE]" />{notice.text}{notice.action === 'personas' && <button type="button" onClick={() => { setPeopleFilter('no_next'); setView('personas'); }} className="min-h-9 rounded-lg border border-[#D9D4C7] bg-white px-2 text-sm font-semibold text-[#132443]" data-testid="my-work-notice-people">Ver y programar</button>}</li>)}</ul>}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" data-testid="my-work-figures">
          {FIGURES.map(([key, label, Icon]) => (
            <button key={key} type="button" onClick={() => setFigure({ metric: key, label, params: { period, ...(period === 'invasion' && campaignId ? { campaign_id: campaignId } : {}), ...scopeParams } })} className="flex min-h-[72px] items-center gap-3 rounded-xl border border-[#E8E5DE] bg-white p-3 text-left shadow-sm active:bg-[#FBFAF7]" data-testid={`my-work-figure-${key}`}>
              <Icon className="h-6 w-6 shrink-0 text-[#9A7A2F]" /><span className="min-w-0"><span className="block text-2xl font-semibold leading-7 text-[#101D36]">{summary.figures[key]}</span><span className="block text-[13px] leading-4 text-slate-600">{label}</span></span>
            </button>
          ))}
        </div>
      </>}

      <div className="grid grid-cols-3 gap-1 rounded-xl bg-[#EEECE6] p-1" role="tablist" data-testid="my-work-views">
        {[['pendientes', 'Pendientes', ClipboardList], ['viviendas', 'Mis viviendas', Home], ['personas', 'Mis personas', Users]].map(([key, label, Icon]) => <button key={key} type="button" role="tab" aria-selected={view === key} onClick={() => setView(key)} className={`inline-flex min-h-12 min-w-0 items-center justify-center gap-1.5 rounded-lg px-1 text-[14px] font-semibold sm:text-[15px] ${view === key ? 'bg-white text-[#101D36] shadow' : 'text-slate-600'}`} data-testid={`my-work-view-${key}`}><Icon className="h-4 w-4 shrink-0 max-[439px]:hidden" /><span className="truncate">{label}</span></button>)}
      </div>

      {view === 'viviendas' && campaigns.length > 0 && <button type="button" onClick={() => setShowMap((value) => !value)} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-[#D9D4C7] bg-white px-3 text-[15px] font-semibold text-[#101D36]" data-testid="my-work-map-toggle"><MapIcon className="h-4 w-4" />{showMap ? 'Ver lista' : 'Ver en el mapa'}</button>}
      {view === 'personas' && <div className="space-y-3" data-testid="my-work-people">
        <Chips options={PEOPLE_FILTERS} value={peopleFilter} onChange={setPeopleFilter} counts={people?.counts ? { ...people.counts, all: Object.entries(people.counts).filter(([key]) => key !== 'no_next').reduce((sum, [, value]) => sum + value, 0) } : {}} testId="my-work-people-filter" />
        {!people ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : people.items.length === 0
          ? <p className="rounded-xl border border-dashed border-slate-300 bg-white p-5 text-center text-base text-slate-600" data-testid="my-work-empty">Sin personas en este filtro.</p>
          : <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">{people.items.map((item) => <PersonRow key={item.id} item={item} readOnly={readOnly} onSchedule={(value) => setFollowup({ visit_id: value.visit_id, title: value.title, next_action: value.next_action, due_date: value.due_date })} onStart={setStartItem} />)}</ul>}
      </div>}
      {view === 'viviendas' && !showMap && <Chips options={HOUSE_FILTERS} value={houseFilter} onChange={setHouseFilter} testId="my-work-houses-filter" />}
      {view === 'personas' ? null : view === 'viviendas' && !showMap ? (!houses ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : houses.items.length === 0
          ? <p className="rounded-xl border border-dashed border-slate-300 bg-white p-5 text-center text-base text-slate-600" data-testid="my-work-empty">Sin viviendas en este filtro.</p>
          : <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2" data-testid="my-work-houses">{houses.items.map((item) => <HouseRow key={`${item.kind}-${item.id}`} item={item} readOnly={readOnly}
              onRevisit={(value) => setRevisit({ household_id: value.household_id, address_line1: value.title, address_line2: null })} onSchedule={(value) => setSchedule({ household_id: value.household_id, followup_date: value.followup_date })} />)}</ul>)
      : view === 'viviendas' && showMap
        ? <InvasionHousesMap campaigns={campaigns.map((item) => ({ campaign_id: item.campaign_id, name: item.name }))} colorBy="door" fixedHeight={460} refreshKey={refreshKey} mentorPersonId={mentorPersonId || user?.person_id}
            onRegisterVisit={readOnly ? undefined : (point) => setRevisit(point)} onChanged={saved} />
        : !pending ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : items.length === 0
          ? <p className="rounded-xl border border-dashed border-slate-300 bg-white p-5 text-center text-base text-slate-600" data-testid="my-work-empty">No tienes pendientes. ¡Buen trabajo!</p>
          : <div className="space-y-4" data-testid="my-work-pending">
              {BUCKETS.map(([bucket, label]) => {
                const group = items.filter((item) => item.bucket === bucket);
                if (!group.length) return null;
                return <section key={bucket} data-testid={`my-work-bucket-${bucket}`}><p className="mb-2 text-sm font-semibold text-slate-700">{label} ({group.length})</p>
                  <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">{group.map((item) => <PendingCard key={`${item.kind}-${item.id}`} item={item} onRevisit={readOnly ? () => {} : (value) => setRevisit({ household_id: value.household_id, address_line1: value.title, address_line2: null })}
                    onSchedule={readOnly ? () => {} : (value) => setSchedule({ household_id: value.household_id, followup_date: value.due_date })} onFollowup={readOnly ? () => {} : setFollowup}
                    readOnly={readOnly} selectable={supervise} selected={selected.includes(keyOf(item))} onSelect={(on) => toggle(item, on)} />)}</ul></section>;
              })}
            </div>}

      {!readOnly && <Link to="/mentoria/visitas" className="inline-flex min-h-12 items-center gap-2 rounded-xl border border-[#D9D4C7] bg-white px-4 text-[15px] font-semibold text-[#101D36]"><MessageCircle className="h-5 w-5" />Visitas e invasiones</Link>}
      {supervise && selected.length > 0 && <div className="sticky bottom-2 z-10"><button type="button" onClick={() => setReassignOpen(true)} className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-[#132443] text-base font-semibold text-white shadow-lg" data-testid="my-work-reassign">Reasignar {selected.length} pendiente(s)</button></div>}
      <ReassignDialog open={reassignOpen} count={selected.length} mentors={mentors} currentMentor={mentorPersonId} onClose={() => setReassignOpen(false)} onConfirm={reassign} />
      <FigureList query={figure} onClose={() => setFigure(null)} />
      <RevisitSheet household={revisit} books={books} onClose={() => setRevisit(null)} onSaved={saved} />
      <ScheduleDialog household={schedule} onClose={() => setSchedule(null)} onSaved={saved} />
      <FollowupDialog item={followup} onClose={() => setFollowup(null)} onSaved={saved} />
      <Dialog open={Boolean(startItem)} onOpenChange={(value) => { if (!value) setStartItem(null); }}>
        <DialogContent className="vv-fit bg-white sm:max-w-md" data-testid="my-work-start-dialog">
          <DialogHeader><DialogTitle>¿Pasar a {startItem?.title} a Consolidación?</DialogTitle><DialogDescription>Se inicia la Ley de las 7 Semanas contigo como mentor (igual que desde la visita).</DialogDescription></DialogHeader>
          <div className="sticky-actions"><button type="button" onClick={startConsolidation} className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-[#132443] text-base font-semibold text-white" data-testid="my-work-start-confirm">Sí, pasar a Consolidación</button></div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
