import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Loader2, Lock, Phone } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';

/* Visitantes V2 › Seguimiento por servicio y fecha: asignar a un servidor,
 * registrar llamada, visita o mensaje con su resultado y revisar las posibles
 * coincidencias con Persona 360. La consejería y las necesidades solo las ve
 * quien tiene el permiso restringido (lo valida el backend). */

const SERVICES = [['', 'Todos los servicios'], ['sunday', 'Domingo'], ['wednesday', 'Miércoles'], ['special', 'Actividad especial']];
const CONTACT = { call: 'Llamada', whatsapp: 'WhatsApp', text: 'Mensaje de texto', email: 'Correo electrónico' };
const VISIT_MODES = { nearby: 'Vive cerca de la iglesia', other_city: 'Viene de otra ciudad', passing: 'Está de paso' };
const fmtPhone = (value) => { const digits = (value || '').replace(/\D/g, ''); return digits.length === 10 ? `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}` : value; };
const KINDS = [['call', 'Llamada'], ['visit', 'Visita'], ['message', 'Mensaje']];
const OUTCOMES = [['reached', 'Se habló con la persona'], ['no_answer', 'No contestó'], ['wrong_number', 'Número equivocado'], ['visit_done', 'Visita realizada'],
  ['wants_more', 'Quiere más información o acompañamiento'], ['declined', 'Prefiere no recibir seguimiento'], ['other', 'Otro resultado']];
const STATUS_STYLE = { pending: 'bg-amber-100 text-amber-900', assigned: 'bg-sky-100 text-sky-900', in_progress: 'bg-indigo-100 text-indigo-900', done: 'bg-emerald-100 text-emerald-900', not_requested: 'bg-slate-100 text-slate-700' };
const fmtDate = (iso) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('es', { weekday: 'long', day: 'numeric', month: 'long' }) : '');
const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString('es', { day: 'numeric', month: 'long', hour: 'numeric', minute: '2-digit' }) : '');
const chip = (active) => `min-h-11 rounded-full border px-4 text-[15px] font-semibold ${active ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-slate-700'}`;

function AssignBox({ item, onDone }) {
  const { API, getAuthHeaders } = useAuth();
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState([]);
  useEffect(() => {
    if (query.trim().length < 2) { setOptions([]); return undefined; }
    const timer = setTimeout(() => axios.get(`${API}/api/visitors/followup/assignees`, { ...getAuthHeaders(), params: { q: query } }).then((response) => setOptions(response.data.items)).catch(() => setOptions([])), 300);
    return () => clearTimeout(timer);
  }, [API, getAuthHeaders, query]);
  const assign = async (personId) => {
    try { onDone((await axios.post(`${API}/api/visitors/registrations/${item.registration_id}/assign`, { person_id: personId }, getAuthHeaders())).data); toast.success(personId ? 'Seguimiento asignado' : 'Asignación quitada'); setQuery(''); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo asignar')); }
  };
  return (
    <div className="space-y-2">
      <label className="block text-[15px] font-semibold text-slate-700">{item.assigned_name ? 'Cambiar a otra persona' : 'Asignar a un servidor'}
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Escribe el nombre" className="mt-1 block h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="followup-assign-search" /></label>
      {options.length > 0 && <ul className="divide-y divide-[#EEECE6] rounded-lg border border-[#E8E5DE]">{options.map((option) => (
        <li key={option.person_id}><button type="button" onClick={() => assign(option.person_id)} className="min-h-12 w-full px-3 text-left text-base hover:bg-[#F8F6F0]" data-testid="followup-assign-option">{option.name}</button></li>
      ))}</ul>}
      {item.assigned_person_id && <button type="button" onClick={() => assign(null)} className="min-h-11 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold text-slate-700">Quitar asignación</button>}
    </div>
  );
}

function AttemptForm({ item, onDone }) {
  const { API, getAuthHeaders } = useAuth();
  const [kind, setKind] = useState('call');
  const [outcome, setOutcome] = useState(null);
  const [note, setNote] = useState('');
  const [complete, setComplete] = useState(false);
  const [saving, setSaving] = useState(false);
  const [key, setKey] = useState(() => `att-${crypto.randomUUID()}`);
  const save = async () => {
    setSaving(true);
    try {
      onDone((await axios.post(`${API}/api/visitors/registrations/${item.registration_id}/attempts`, { kind, outcome, note: note.trim() || null, complete, idempotency_key: key }, getAuthHeaders())).data);
      toast.success('Seguimiento registrado'); setOutcome(null); setNote(''); setComplete(false); setKey(`att-${crypto.randomUUID()}`);
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); }
    setSaving(false);
  };
  return (
    <div className="space-y-3" data-testid="followup-attempt-form">
      <p className="text-[15px] font-semibold text-[#101D36]">Registrar llamada, visita o mensaje</p>
      <div className="flex flex-wrap gap-2">{KINDS.map(([value, label]) => <button key={value} type="button" onClick={() => setKind(value)} className={chip(kind === value)} data-testid={`followup-kind-${value}`}>{label}</button>)}</div>
      <div className="flex flex-wrap gap-2">{OUTCOMES.map(([value, label]) => <button key={value} type="button" onClick={() => setOutcome(value)} className={chip(outcome === value)} data-testid={`followup-outcome-${value}`}>{label}</button>)}</div>
      <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} placeholder="Nota (opcional). No escribas aquí datos de consejería." className="w-full rounded-lg border border-[#D9D4C7] p-3 text-base" data-testid="followup-note" />
      <label className="flex min-h-11 items-center gap-3 text-base"><input type="checkbox" checked={complete} onChange={(event) => setComplete(event.target.checked)} className="h-5 w-5" data-testid="followup-complete" />El seguimiento quedó completado</label>
      <button type="button" disabled={!outcome || saving} onClick={save} className="min-h-12 rounded-xl bg-[#132443] px-5 text-base font-semibold text-white disabled:opacity-50" data-testid="followup-save">{saving ? 'Guardando…' : 'Guardar resultado'}</button>
    </div>
  );
}

function MatchReview({ item, onDone }) {
  const { API, getAuthHeaders } = useAuth();
  const resolve = async (body) => {
    try { onDone((await axios.post(`${API}/api/visitors/registrations/${item.registration_id}/resolve-match`, body, getAuthHeaders())).data); toast.success('Persona 360 actualizada'); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); }
  };
  return (
    <div className="space-y-2 rounded-xl border-2 border-amber-300 bg-amber-50 p-3" data-testid="followup-match-review">
      <p className="text-[15px] font-semibold text-amber-900">Posible coincidencia en Persona 360. ¿Es la misma persona?</p>
      {item.possible_people.map((person) => (
        <div key={person.person_id} className="flex flex-wrap items-center gap-2">
          <Link to={`/personas/${person.person_id}`} className="text-base font-semibold text-[#0879BE] underline">{person.name}</Link>
          <button type="button" onClick={() => resolve({ person_id: person.person_id })} className="min-h-11 rounded-lg bg-[#132443] px-3 text-[15px] font-semibold text-white" data-testid="followup-match-link">Sí, es esta persona</button>
        </div>
      ))}
      <button type="button" onClick={() => resolve({ create_new: true })} className="min-h-11 rounded-lg border border-amber-400 bg-white px-3 text-[15px] font-semibold text-amber-900" data-testid="followup-match-new">Es otra persona: crear su perfil</button>
    </div>
  );
}

function Restricted({ item }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const open = async () => { try { setData((await axios.get(`${API}/api/visitors/registrations/${item.registration_id}`, getAuthHeaders())).data.restricted || {}); } catch (error) { toast.error(apiErrorMessage(error, 'Sin acceso')); } };
  if (!data) return <button type="button" onClick={open} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold text-slate-700" data-testid="followup-restricted-open"><Lock className="h-4 w-4" />Ver notas confidenciales (queda registrado)</button>;
  return (
    <div className="space-y-1 rounded-xl border border-[#E8E5DE] bg-[#FBFAF6] p-3 text-[15px]" data-testid="followup-restricted">
      {data.prayer_request && <p><b>Petición de oración:</b> {data.prayer_request}</p>}
      {data.counseling_note && <p><b>Consejería:</b> {data.counseling_note}</p>}
      {data.needs_note && <p><b>Necesidad:</b> {data.needs_note}</p>}
      {!data.prayer_request && !data.counseling_note && !data.needs_note && <p>No escribió notas.</p>}
    </div>
  );
}

function FollowupCard({ item: initial, canManage, canRestricted }) {
  const { user } = useAuth();
  const [item, setItem] = useState(initial);
  const [open, setOpen] = useState(false);
  const isAssignee = item.assigned_person_id && item.assigned_person_id === user?.person_id;
  return (
    <li className="rounded-2xl border border-[#E8E5DE] bg-white p-4" data-testid="followup-item">
      <button type="button" onClick={() => setOpen(!open)} className="w-full text-left" aria-expanded={open}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-lg font-semibold text-[#101D36]">{item.name}{item.preferred_name && !item.name.startsWith(item.preferred_name) ? ` («${item.preferred_name}»)` : ''}</p>
            <p className="text-[15px] text-slate-600">{item.visitor_number} · {item.service.label} · {fmtDate(item.service.date)}{item.first_visit ? ' · Primera visita' : ''}</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-sm font-semibold ${STATUS_STYLE[item.status] || ''}`} data-testid="followup-status">{item.status_label}</span>
        </div>
        <p className="mt-1 text-[15px] text-slate-700">{item.assigned_name ? `Asignado a ${item.assigned_name}` : 'Sin asignar'}{item.requests.length ? ` · Pide: ${item.requests.join(', ')}` : ''}</p>
        {item.match_status === 'possible' && <p className="text-[15px] font-semibold text-amber-800">{item.match_label}</p>}
      </button>
      {open && (
        <div className="mt-3 space-y-4 border-t border-[#EEECE6] pt-3">
          <div className="grid gap-1 text-base text-slate-800 sm:grid-cols-2">
            {item.phone ? <a href={`tel:${item.phone}`} className="inline-flex min-h-11 items-center gap-2 font-semibold text-[#0879BE]"><Phone className="h-4 w-4" />{fmtPhone(item.phone)}</a> : <p>Sin teléfono</p>}
            <p>Prefiere: {(item.contact_methods || []).map((key) => CONTACT[key]).filter(Boolean).join(', ') || 'No indicó'}</p>
            {item.visit_mode && <p>Hoy: {VISIT_MODES[item.visit_mode]}</p>}
            {item.invited_by && <p>Invitado por {item.invited_by}</p>}
            {item.email && <p className="break-all">Correo: {item.email}</p>}
            {item.city && <p>Ciudad o zona: {item.city}</p>}
            <p>¿Podemos comunicarnos?: {item.consent_followup === true ? 'Sí' : item.consent_followup === false ? 'No' : 'No respondió'}</p>
            {item.person_id && <Link to={`/personas/${item.person_id}`} className="font-semibold text-[#0879BE] underline">Ver Perfil 360</Link>}
          </div>
          {item.has_restricted && canRestricted && <Restricted item={item} />}
          {canManage && item.match_status === 'possible' && <MatchReview item={item} onDone={setItem} />}
          {canManage && <AssignBox item={item} onDone={setItem} />}
          {(canManage || isAssignee) && <AttemptForm item={item} onDone={setItem} />}
          {item.attempts.length > 0 && (
            <div><p className="text-[15px] font-semibold text-[#101D36]">Historial</p>
              <ul className="mt-1 space-y-1" data-testid="followup-history">{[...item.attempts].reverse().map((attempt) => (
                <li key={attempt.key} className="rounded-lg bg-[#F8F6F0] p-2 text-[15px]">{attempt.kind_label}: <b>{attempt.outcome_label}</b> · {fmtDateTime(attempt.at)}{attempt.by_name ? ` · ${attempt.by_name}` : ''}{attempt.note ? <span className="block text-slate-700">{attempt.note}</span> : null}</li>
              ))}</ul>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export default function VisitorFollowup() {
  const { API, getAuthHeaders } = useAuth();
  const [day, setDay] = useState('');
  const [kind, setKind] = useState('');
  const [status, setStatus] = useState('');
  const [data, setData] = useState(null);
  const load = useCallback(() => {
    setData(null);
    axios.get(`${API}/api/visitors/followup`, { ...getAuthHeaders(), params: { ...(day ? { service_date: day } : {}), ...(kind ? { service_kind: kind } : {}), ...(status ? { status } : {}) } })
      .then((response) => setData(response.data)).catch((error) => { toast.error(apiErrorMessage(error, 'No se pudo cargar el seguimiento')); setData({ items: [], counts: [] }); });
  }, [API, getAuthHeaders, day, kind, status]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-3" data-testid="visitors-followup">
      {data && !data.can_manage && <p className="rounded-xl bg-sky-50 p-3 text-[15px] text-sky-900">Aquí ves los visitantes que te asignaron. Llama o visita y registra el resultado.</p>}
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-[15px] font-semibold text-slate-700">Fecha del servicio<input type="date" value={day} onChange={(event) => setDay(event.target.value)} className="mt-1 block h-12 rounded-lg border border-[#D9D4C7] px-2 text-base" data-testid="followup-date" /></label>
        {day && <button type="button" onClick={() => setDay('')} className="min-h-12 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold">Todas las fechas</button>}
      </div>
      <div className="flex flex-wrap gap-2">{SERVICES.map(([value, label]) => <button key={value || 'all'} type="button" onClick={() => setKind(value)} className={chip(kind === value)} data-testid={`followup-service-${value || 'all'}`}>{label}</button>)}</div>
      {data?.counts && <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => setStatus('')} className={chip(status === '')}>Todos</button>
        {data.counts.map((count) => <button key={count.status} type="button" onClick={() => setStatus(count.status)} className={chip(status === count.status)} data-testid={`followup-filter-${count.status}`}>{count.label}{status ? '' : `: ${count.count}`}</button>)}
      </div>}
      {!data ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : data.items.length === 0
        ? <p className="rounded-xl bg-white p-4 text-[15px] text-slate-600">No hay visitantes con estos filtros.</p>
        : <ul className="grid grid-cols-1 gap-3 xl:grid-cols-2">{data.items.map((item) => <FollowupCard key={item.registration_id} item={item} canManage={data.can_manage} canRestricted={data.can_restricted} />)}</ul>}
    </div>
  );
}
