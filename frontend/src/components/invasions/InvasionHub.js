import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { Loader2, Plus, Send, X } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { CreateCampaignDialog, PersonPicker } from '../outreach/CreateCampaignDialog';
import { PrayerPanel } from './PrayerProgress';

// Avisa a las demás partes de la pantalla que cambió una invasión o solicitud.
const CHANGED = 'invasions:changed';
const announceChange = () => window.dispatchEvent(new Event(CHANGED));

const STATUS = {
  pending: { label: 'Pendiente', className: 'bg-amber-50 text-amber-800 border-amber-200' },
  changes_requested: { label: 'Cambios pedidos', className: 'bg-[#FBF6EA] text-[#7A5F22] border-[#D9CFB4]' },
  approved: { label: 'Aprobada', className: 'bg-[#eef5f0] text-[#2f6e47] border-[#bcd8c4]' },
  rejected: { label: 'Rechazada', className: 'bg-[#f8ecea] text-[#8f382f] border-[#e3c2bd]' },
};
const inputClass = 'h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base';
const formatDate = (iso) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');

function Sheet({ title, onClose, children, testId, wide = false }) {
  return (
    <div className="vv-fit fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-6" role="dialog" aria-modal="true" data-testid={testId}>
      <div className={`max-h-[min(92vh,calc(var(--vvh,100dvh)-8px))] w-full ${wide ? 'max-w-5xl' : 'max-w-xl'} overflow-y-auto rounded-t-2xl bg-white text-[#101D36] sm:rounded-2xl`}>
        <div className="sticky top-0 flex items-center gap-2 border-b border-[#E8E5DE] bg-white px-3 py-2"><p className="flex-1 font-['Spectral'] text-lg font-semibold text-[#101D36]">{title}</p><button type="button" onClick={onClose} className="grid h-11 w-11 place-items-center rounded-md hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button></div>
        <div className="space-y-3 p-4">{children}</div>
      </div>
    </div>
  );
}

// Solicitud de un líder de Grupo Frontal (lugar y fecha propuestos).
function RequestForm({ existing, onClose, onSaved }) {
  const { API, getAuthHeaders } = useAuth();
  const [authorities, setAuthorities] = useState([]);
  const [groups, setGroups] = useState([]);
  const [form, setForm] = useState({
    authority_user_id: existing?.authority_user_id || '', front_group_id: existing?.front_group_id || '', proposed_name: existing?.proposed_name || '',
    proposed_location: existing?.proposed_location || '', proposed_start_date: existing?.proposed_start_date || '', proposed_end_date: existing?.proposed_end_date || '', notes: existing?.notes || '',
  });
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    axios.get(`${API}/api/invasions/authorities`, getAuthHeaders()).then((response) => setAuthorities(response.data.items || [])).catch(() => setAuthorities([]));
    axios.get(`${API}/api/core/me/front-groups`, getAuthHeaders()).then((response) => setGroups((response.data.items || []).filter((item) => item.can_manage))).catch(() => setGroups([]));
  }, [API, getAuthHeaders]);
  const set = (patch) => setForm((current) => ({ ...current, ...patch }));
  const submit = async () => {
    if (!form.authority_user_id || form.proposed_location.trim().length < 2 || !form.proposed_start_date || !form.proposed_end_date) { toast.error('Completa a quién va dirigida, el lugar y las fechas'); return; }
    setSaving(true);
    try {
      const body = { ...form, front_group_id: form.front_group_id || null, proposed_name: form.proposed_name || null, notes: form.notes || null };
      if (existing) await axios.put(`${API}/api/invasions/requests/${existing.request_id}`, body, getAuthHeaders());
      else await axios.post(`${API}/api/invasions/requests`, body, getAuthHeaders());
      toast.success('Solicitud enviada'); onSaved(); onClose();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo enviar la solicitud')); } finally { setSaving(false); }
  };
  return (
    <Sheet title={existing ? 'Corregir solicitud de invasión' : 'Solicitar una invasión'} onClose={onClose} testId="invasion-request-form">
      {existing?.review_note && <p className="rounded-lg bg-[#FBF6EA] p-3 text-sm text-[#7A5F22]"><b>Te pidieron:</b> {existing.review_note}</p>}
      <label className="block space-y-1"><span className="text-sm font-semibold">Dirigida a *</span>
        <select value={form.authority_user_id} onChange={(event) => set({ authority_user_id: event.target.value })} className={inputClass} data-testid="request-authority"><option value="">Elige pastor o coordinador general…</option>{authorities.map((item) => <option key={item.user_id} value={item.user_id}>{item.name} · {item.title}</option>)}</select>
      </label>
      {groups.length > 1 && <label className="block space-y-1"><span className="text-sm font-semibold">Grupo Frontal</span><select value={form.front_group_id} onChange={(event) => set({ front_group_id: event.target.value })} className={inputClass}><option value="">El primero que lidero</option>{groups.map((item) => <option key={item.front_group_id} value={item.front_group_id}>{item.name}</option>)}</select></label>}
      <label className="block space-y-1"><span className="text-sm font-semibold">Lugar propuesto *</span><input value={form.proposed_location} onChange={(event) => set({ proposed_location: event.target.value })} className={inputClass} data-testid="request-location" /></label>
      <div className="grid grid-cols-2 gap-2">
        <label className="block space-y-1"><span className="text-sm font-semibold">Desde *</span><input type="date" value={form.proposed_start_date} onChange={(event) => set({ proposed_start_date: event.target.value, proposed_end_date: form.proposed_end_date >= event.target.value ? form.proposed_end_date : event.target.value })} className={inputClass} data-testid="request-start" /></label>
        <label className="block space-y-1"><span className="text-sm font-semibold">Hasta *</span><input type="date" value={form.proposed_end_date} min={form.proposed_start_date || undefined} onChange={(event) => set({ proposed_end_date: event.target.value })} className={inputClass} data-testid="request-end" /></label>
      </div>
      <label className="block space-y-1"><span className="text-sm font-semibold">Nombre sugerido</span><input value={form.proposed_name} onChange={(event) => set({ proposed_name: event.target.value })} className={inputClass} /></label>
      <label className="block space-y-1"><span className="text-sm font-semibold">Notas</span><textarea value={form.notes} onChange={(event) => set({ notes: event.target.value })} rows={3} className="w-full rounded-lg border border-[#D9D4C7] p-3 text-base" /></label>
      <button type="button" onClick={submit} disabled={saving} className="min-h-12 w-full rounded-lg bg-[#101D36] text-base font-semibold text-white disabled:opacity-60" data-testid="request-submit">{saving ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : existing ? 'Reenviar solicitud' : 'Enviar solicitud'}</button>
    </Sheet>
  );
}

function ReviewForm({ request, decision, onClose, onSaved }) {
  const { API, getAuthHeaders } = useAuth();
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const submit = async () => {
    if (note.trim().length < 3) { toast.error('Escribe el motivo o los cambios que pides'); return; }
    setSaving(true);
    try { await axios.post(`${API}/api/invasions/requests/${request.request_id}/review`, { decision, note: note.trim() }, getAuthHeaders()); toast.success('Respuesta enviada al líder'); onSaved(); onClose(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo responder')); } finally { setSaving(false); }
  };
  return (
    <Sheet title={decision === 'reject' ? 'Rechazar solicitud' : 'Pedir cambios'} onClose={onClose} testId="invasion-review-form">
      <p className="text-sm text-slate-600">{request.requested_by_name} · {request.proposed_location} · {formatDate(request.proposed_start_date)}</p>
      <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={4} placeholder={decision === 'reject' ? 'Motivo del rechazo' : '¿Qué debe cambiar?'} className="w-full rounded-lg border border-[#D9D4C7] p-3 text-base" data-testid="review-note" />
      <button type="button" onClick={submit} disabled={saving} className="min-h-12 w-full rounded-lg bg-[#101D36] text-base font-semibold text-white" data-testid="review-submit">{saving ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : 'Enviar'}</button>
    </Sheet>
  );
}

const PARTICIPANT_STATUS = {
  invited: 'bg-amber-50 text-amber-800 border-amber-200',
  confirmed: 'bg-[#eef5f0] text-[#2f6e47] border-[#bcd8c4]',
  declined: 'bg-[#f8ecea] text-[#8f382f] border-[#e3c2bd]',
  attended: 'bg-[#e8eefb] text-[#1d4ed8] border-[#c3d3f5]',
};

// Lista de participantes (mentores, colaboradores, encargados) con su estado.
// Agregar/quitar: autoridad, organizador o encargado general (el backend lo valida).
function ParticipantsPanel({ campaignId }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [role, setRole] = useState('collaborator');
  const [groups, setGroups] = useState([]);
  const [groupId, setGroupId] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    axios.get(`${API}/api/invasions/${campaignId}/participants`, getAuthHeaders()).then((response) => setData(response.data)).catch(() => setData({ items: [], counts: {}, can_edit: false }));
  }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!data?.can_edit) return;
    axios.get(`${API}/api/front-groups`, getAuthHeaders()).then((response) => setGroups((response.data.items || []).filter((item) => !item.member_view))).catch(() => setGroups([]));
  }, [API, getAuthHeaders, data?.can_edit]);
  const add = async (body) => {
    setBusy(true);
    try {
      const response = await axios.post(`${API}/api/invasions/${campaignId}/participants`, body, getAuthHeaders());
      setData(response.data);
      (response.data.rejected || []).forEach((item) => toast.error(`${item.name}: ${item.reason}`));
      if (response.data.added?.length) toast.success(`${response.data.added.length} invitado(s) y avisado(s)`);
      announceChange();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo agregar')); } finally { setBusy(false); }
  };
  const toggleAttendance = async (item) => {
    try { const response = await axios.put(`${API}/api/invasions/${campaignId}/participants/${item.person_id}/attendance`, { attended: !item.attended }, getAuthHeaders()); setData(response.data); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo marcar la asistencia')); }
  };
  const remove = async (item, removeRole) => {
    if (!window.confirm(`¿Quitar a ${item.name} como ${removeRole === 'mentor' ? 'mentor' : 'colaborador'}?`)) return;
    try { const response = await axios.delete(`${API}/api/invasions/${campaignId}/participants/${item.person_id}`, { ...getAuthHeaders(), params: { role: removeRole } }); setData(response.data); announceChange(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo quitar')); }
  };
  if (!data) return <Loader2 className="mx-auto h-6 w-6 animate-spin text-[#9A7A2F]" />;
  const counts = data.counts || {};
  return (
    <section className="space-y-3 border-t border-[#EEECE6] pt-3" data-testid="invasion-participants">
      <h4 className="text-base font-semibold text-[#101D36]">Participantes</h4>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5" data-testid="participants-counts">{[['total', 'Invitados'], ['confirmed', 'Confirmados'], ['no_response', 'Sin responder'], ['declined', 'No podrán'], ['attended', 'Asistieron']].map(([key, label]) => <div key={key} className="rounded-lg border border-[#EEECE6] bg-[#FBFAF7] p-2 text-center"><p className="text-xl font-semibold text-[#101D36]" data-testid={`participants-count-${key}`}>{counts[key] || 0}</p><p className="text-[11px] text-slate-500">{label}</p></div>)}</div>
      <ul className="space-y-2">{data.items.map((item) => (
        <li key={item.person_id} className="rounded-lg border border-[#EEECE6] p-3" data-testid={`participant-${item.person_id}`}>
          <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="text-sm font-semibold text-[#101D36]">{item.name}</p><p className="text-xs text-slate-500">{item.role_labels.join(' · ')}</p></div><span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${PARTICIPANT_STATUS[item.attended ? 'attended' : item.status] || PARTICIPANT_STATUS.invited}`}>{item.status_label}</span></div>
          {item.response_note && <p className="mt-1 text-xs text-slate-500">«{item.response_note}»</p>}
          {data.can_edit && <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" onClick={() => toggleAttendance(item)} className={`min-h-10 rounded-md border px-3 text-xs font-semibold ${item.attended ? 'border-[#c3d3f5] bg-[#e8eefb] text-[#1d4ed8]' : 'border-[#D9D4C7] text-[#101D36]'}`} data-testid={`participant-attendance-${item.person_id}`}>{item.attended ? '✓ Asistió' : 'Marcar asistencia'}</button>
          </div>}
          {data.can_edit && (item.roles.includes('mentor') || item.roles.includes('collaborator')) && <div className="mt-2 flex flex-wrap gap-2">{['mentor', 'collaborator'].filter((value) => item.roles.includes(value)).map((value) => <button key={value} type="button" onClick={() => remove(item, value)} className="min-h-10 rounded-md border border-[#e3c2bd] px-3 text-xs font-semibold text-[#8f382f]" data-testid={`participant-remove-${value}-${item.person_id}`}>Quitar como {value === 'mentor' ? 'mentor' : 'colaborador'}</button>)}</div>}
        </li>
      ))}</ul>
      {data.items.length === 0 && <p className="text-sm text-slate-500">Todavía no hay participantes.</p>}
      {data.can_edit && <div className="space-y-2 rounded-lg border border-dashed border-[#D9CFB4] bg-[#FBFAF7] p-3" data-testid="participants-add">
        <p className="text-sm font-semibold text-[#101D36]">Invitar</p>
        <div className="grid grid-cols-2 gap-2">{[['collaborator', 'Colaborador'], ['mentor', 'Mentor']].map(([value, label]) => <button key={value} type="button" onClick={() => setRole(value)} className={`min-h-11 rounded-md border text-sm font-semibold ${role === value ? 'border-[#101D36] bg-[#101D36] text-white' : 'border-[#D9D4C7] bg-white text-[#101D36]'}`} data-testid={`participants-role-${value}`}>{label}</button>)}</div>
        <PersonPicker value={null} onChange={(person) => { if (person && !busy) add({ role, person_ids: [person.person_id] }); }} placeholder={role === 'mentor' ? 'Buscar mentor (con insignia activa)…' : 'Buscar colaborador en Persona 360…'} testId="participants-person" />
        {groups.length > 0 && <div className="flex flex-col gap-2 sm:flex-row"><select value={groupId} onChange={(event) => setGroupId(event.target.value)} className={inputClass}><option value="">Invitar un Grupo Frontal completo…</option>{groups.map((item) => <option key={item.front_group_id} value={item.front_group_id}>{item.display_name || item.name}</option>)}</select><button type="button" disabled={!groupId || busy} onClick={() => add({ role: 'collaborator', front_group_ids: [groupId] })} className="min-h-12 shrink-0 rounded-lg bg-[#101D36] px-4 text-sm font-semibold text-white disabled:opacity-50" data-testid="participants-add-group">Invitar grupo</button></div>}
      </div>}
    </section>
  );
}

function InvasionSummary({ campaignId, onClose }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { axios.get(`${API}/api/invasions/${campaignId}`, getAuthHeaders()).then((response) => setData(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo abrir la invasión'))); }, [API, getAuthHeaders, campaignId]);
  const row = (label, value) => <div className="border-b border-[#EEECE6] py-2"><p className="text-xs text-slate-500">{label}</p><p className="whitespace-pre-line text-sm font-medium text-[#101D36]">{value || '—'}</p></div>;
  return (
    <Sheet title={data?.name || 'Invasión'} onClose={onClose} testId="invasion-summary" wide>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!data && !error && <Loader2 className="mx-auto h-6 w-6 animate-spin text-[#9A7A2F]" />}
      {data && <>
        {row('Propósito', data.purpose)}
        {row('Lugar y fechas', `${data.location} · ${formatDate(data.start_date)} → ${formatDate(data.end_date)}`)}
        {row('Jornadas', (data.schedule_days || []).map((item) => `${formatDate(item.day)} · ${item.start_time} · ${Math.round(item.duration_minutes / 60 * 10) / 10} h`).join('\n'))}
        {row('Encuentro inicial', data.departure_point)}
        {row('Encuentro en el lugar', [data.site_meeting_point?.address, data.site_meeting_point?.reference].filter(Boolean).join(' · '))}
        {row('Preparación en oración desde', formatDate(data.prayer_start_date))}
        {row('Encargado general / logística', [data.general_lead?.name, data.logistics_lead?.name].filter(Boolean).join(' / '))}
        {row('Emergencias', data.emergency_contact ? `${data.emergency_contact.name} · ${data.emergency_contact.phone}` : '')}
        {row('Descripción', data.description)}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Link to={`/invasiones/${campaignId}/programa`} className="inline-flex min-h-11 items-center justify-center rounded-lg border border-[#101D36] text-sm font-semibold text-[#101D36]" data-testid="invasion-summary-program">Programa</Link>
          {data.can_edit_participants && <Link to={`/invasiones/${campaignId}/asistencia`} className="inline-flex min-h-11 items-center justify-center rounded-lg border border-[#101D36] text-sm font-semibold text-[#101D36]" data-testid="invasion-summary-attendance">Asistencia</Link>}
          <Link to={`/invasiones/${campaignId}/reporte`} className="inline-flex min-h-11 items-center justify-center rounded-lg bg-[#101D36] text-sm font-semibold text-white" data-testid="invasion-summary-report">Ver reporte de la invasión</Link>
        </div>
        {data.can_edit_participants && <Link to={`/invasiones/${campaignId}/reporte/presentar?dia=1`} className="inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-[#C8A951] text-base font-bold text-[#14213D]" data-testid="invasion-summary-present">Presentar reporte (pantalla grande)</Link>}
        <ParticipantsPanel campaignId={campaignId} />
        <PrayerPanel campaignId={campaignId} />
      </>}
    </Sheet>
  );
}

// Botón principal junto al encabezado: "Crear invasión" (pastor general y
// coordinadores generales) o "Solicitar invasión" (líderes de Grupo Frontal).
// El backend decide los permisos (`can_review` / `can_request`).
export function InvasionHeaderActions({ onDark = false }) {
  const { API, getAuthHeaders } = useAuth();
  const [access, setAccess] = useState({ can_review: false, can_request: false });
  const [creating, setCreating] = useState(false);
  const [requesting, setRequesting] = useState(false);
  useEffect(() => {
    axios.get(`${API}/api/invasions/requests`, getAuthHeaders()).then((response) => setAccess({ can_review: response.data.can_review, can_request: response.data.can_request })).catch(() => {});
  }, [API, getAuthHeaders]);
  if (!access.can_review && !access.can_request) return null;
  const buttonClass = `inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl px-6 text-base font-semibold shadow-sm sm:w-auto ${onDark ? 'bg-white text-[#101D36] hover:bg-[#F3F0E8]' : 'bg-[#101D36] text-white'}`;
  return <>
    {access.can_review
      ? <button type="button" onClick={() => setCreating(true)} className={buttonClass} data-testid="crear-invasion-button"><Plus className="h-5 w-5" />Crear invasión</button>
      : <button type="button" onClick={() => setRequesting(true)} className={buttonClass} data-testid="solicitar-invasion-button"><Send className="h-5 w-5" />Solicitar invasión</button>}
    <CreateCampaignDialog open={creating} onOpenChange={setCreating} onCreated={announceChange} />
    {requesting && <RequestForm onClose={() => setRequesting(false)} onSaved={announceChange} />}
  </>;
}

// FASE 6A: invasiones y solicitudes en el Panel de Consolidación y en Mi Grupo
// Frontal. Con `showAction` muestra también el botón principal (donde no hay
// encabezado con acciones).
export function InvasionHub({ showAction = false }) {
  const { API, getAuthHeaders } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [requests, setRequests] = useState({ items: [], can_review: false, can_request: false });
  const [campaigns, setCampaigns] = useState([]);
  const [counts, setCounts] = useState({});
  const [wizard, setWizard] = useState(null);
  const [requestForm, setRequestForm] = useState(null);
  const [review, setReview] = useState(null);
  const [summaryId, setSummaryId] = useState(null);

  const load = useCallback(() => {
    axios.get(`${API}/api/invasions/requests`, getAuthHeaders()).then((response) => setRequests(response.data)).catch(() => {});
    axios.get(`${API}/api/mentorship/outreach/campaigns`, getAuthHeaders()).then((response) => setCampaigns(response.data.items || [])).catch(() => setCampaigns([]));
    axios.get(`${API}/api/invasions/participants/summary`, getAuthHeaders()).then((response) => setCounts(response.data.items || {})).catch(() => setCounts({}));
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { window.addEventListener(CHANGED, load); return () => window.removeEventListener(CHANGED, load); }, [load]);
  useEffect(() => {
    const invasion = searchParams.get('invasion');
    if (invasion) { setSummaryId(invasion); searchParams.delete('invasion'); setSearchParams(searchParams, { replace: true }); }
  }, [searchParams, setSearchParams]);

  const highlighted = searchParams.get('solicitud');
  const canCreate = requests.can_review;
  const open = requests.items.filter((item) => ['pending', 'changes_requested'].includes(item.status));
  const closed = requests.items.filter((item) => !['pending', 'changes_requested'].includes(item.status)).slice(0, 6);
  const upcoming = campaigns.filter((item) => item.status !== 'closed').slice(0, 6);
  if (!canCreate && !requests.can_request && !requests.items.length && !upcoming.length) return null;

  return (
    <section className="space-y-3" data-testid="invasion-hub">
      <div className="flex flex-col gap-3 rounded-2xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div><h2 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">Invasiones</h2><p className="text-sm text-slate-500">{canCreate ? 'Invasiones oficiales y solicitudes de los líderes.' : 'Propón una invasión al pastor general o a un coordinador general.'}</p></div>
        {showAction && <InvasionHeaderActions />}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {(open.length > 0 || closed.length > 0) && <section className="min-w-0 rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid="invasion-requests">
          <h3 className="text-base font-semibold text-[#101D36]">{canCreate ? 'Solicitudes de invasión' : 'Mis solicitudes'}</h3>
          <ul className="mt-2 space-y-2">{[...open, ...closed].map((item) => {
            const status = STATUS[item.status] || STATUS.pending;
            return (
              <li key={item.request_id} className={`rounded-lg border p-3 ${highlighted === item.request_id ? 'border-[#101D36] ring-2 ring-[#101D36]/20' : 'border-[#EEECE6]'}`} data-testid={`invasion-request-${item.request_id}`}>
                <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="text-sm font-semibold text-[#101D36]">{item.proposed_name || item.proposed_location}</p><p className="text-xs text-slate-500">{item.proposed_location} · {formatDate(item.proposed_start_date)} → {formatDate(item.proposed_end_date)}</p><p className="text-xs text-slate-500">{canCreate ? `De ${item.requested_by_name || 'un líder'}${item.front_group_name ? ` (${item.front_group_name})` : ''}` : `Para ${item.authority_name || 'la autoridad'}`}</p></div><span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${status.className}`}>{status.label}</span></div>
                {item.notes && <p className="mt-1 text-sm text-slate-600">{item.notes}</p>}
                {item.review_note && <p className="mt-1 text-sm text-[#7A5F22]"><b>Respuesta:</b> {item.review_note}</p>}
                {canCreate && ['pending', 'changes_requested'].includes(item.status) && <div className="mt-2 grid grid-cols-3 gap-2">
                  <button type="button" onClick={() => setWizard({ request: item })} className="min-h-11 rounded-md bg-[#3d8b5a] text-sm font-semibold text-white" data-testid="request-approve">Aprobar</button>
                  <button type="button" onClick={() => setReview({ request: item, decision: 'request_changes' })} className="min-h-11 rounded-md border border-[#D9CFB4] text-sm font-semibold text-[#7A5F22]" data-testid="request-changes">Pedir cambios</button>
                  <button type="button" onClick={() => setReview({ request: item, decision: 'reject' })} className="min-h-11 rounded-md border border-[#e3c2bd] text-sm font-semibold text-[#8f382f]" data-testid="request-reject">Rechazar</button>
                </div>}
                {!canCreate && item.status === 'changes_requested' && <button type="button" onClick={() => setRequestForm({ existing: item })} className="mt-2 min-h-11 w-full rounded-md border border-[#D9CFB4] text-sm font-semibold text-[#7A5F22]" data-testid="request-edit">Corregir y reenviar</button>}
                {item.campaign_id && <button type="button" onClick={() => setSummaryId(item.campaign_id)} className="mt-2 min-h-10 text-sm font-semibold text-[#101D36] underline">Ver invasión creada</button>}
              </li>
            );
          })}</ul>
        </section>}
        {upcoming.length > 0 && <section className="min-w-0 rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid="invasion-list">
          <h3 className="text-base font-semibold text-[#101D36]">Invasiones activas</h3>
          <ul className="mt-2 space-y-2">{upcoming.map((item) => (
            <li key={item.campaign_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#EEECE6] p-3">
              <button type="button" onClick={() => setSummaryId(item.campaign_id)} className="min-w-0 flex-1 text-left"><p className="truncate text-sm font-semibold text-[#101D36]">{item.name}</p><p className="text-xs text-slate-500">{item.location} · {formatDate(item.start_date)} → {formatDate(item.end_date)}</p>{counts[item.campaign_id] && <p className="mt-1 text-xs font-medium text-[#101D36]" data-testid={`invasion-counts-${item.campaign_id}`}>{counts[item.campaign_id].total} invitados · {counts[item.campaign_id].confirmed} confirmados · {counts[item.campaign_id].no_response} sin responder · {counts[item.campaign_id].attended} asistieron</p>}</button>
              <div className="flex flex-wrap gap-2">
                <Link to={`/invasiones/${item.campaign_id}/programa`} className="inline-flex min-h-11 items-center rounded-md border border-[#D9D4C7] px-4 text-sm font-semibold text-[#101D36]" data-testid={`invasion-program-${item.campaign_id}`}>Programa</Link>
                {counts[item.campaign_id] && <Link to={`/invasiones/${item.campaign_id}/asistencia`} className="inline-flex min-h-11 items-center rounded-md border border-[#D9D4C7] px-4 text-sm font-semibold text-[#101D36]" data-testid={`invasion-attendance-${item.campaign_id}`}>Asistencia</Link>}
                <Link to={`/invasiones/${item.campaign_id}/reporte`} className="inline-flex min-h-11 items-center rounded-md border border-[#D9D4C7] px-4 text-sm font-semibold text-[#101D36]" data-testid={`invasion-report-${item.campaign_id}`}>Reporte</Link>
                {counts[item.campaign_id] && <Link to={`/invasiones/${item.campaign_id}/reporte/presentar?dia=1`} className="inline-flex min-h-11 items-center rounded-md bg-[#C8A951] px-4 text-sm font-bold text-[#14213D]" data-testid={`invasion-present-${item.campaign_id}`}>Presentar reporte</Link>}
                {canCreate && <button type="button" onClick={() => setWizard({ campaignId: item.campaign_id })} className="min-h-11 rounded-md border border-[#D9D4C7] px-4 text-sm font-semibold text-[#101D36]" data-testid={`invasion-edit-${item.campaign_id}`}>Editar</button>}
              </div>
            </li>
          ))}</ul>
        </section>}
      </div>

      <CreateCampaignDialog open={Boolean(wizard)} onOpenChange={(next) => { if (!next) setWizard(null); }} onCreated={announceChange} request={wizard?.request || null} campaignId={wizard?.campaignId || null} />
      {requestForm && <RequestForm existing={requestForm.existing} onClose={() => setRequestForm(null)} onSaved={announceChange} />}
      {review && <ReviewForm request={review.request} decision={review.decision} onClose={() => setReview(null)} onSaved={announceChange} />}
      {summaryId && <InvasionSummary campaignId={summaryId} onClose={() => setSummaryId(null)} />}
    </section>
  );
}
