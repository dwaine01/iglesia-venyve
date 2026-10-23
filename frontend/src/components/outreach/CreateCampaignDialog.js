import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { Check, Loader2, Search, Users, X } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { mentorAccountBlocked, mentorAccessHint, mentorNeedsAccountCreation } from '../../lib/accessControl';

const STEPS = [
  { key: 'general', label: 'Datos generales' },
  { key: 'place', label: 'Lugar y fechas' },
  { key: 'leads', label: 'Responsables' },
  { key: 'meeting', label: 'Puntos de encuentro' },
  { key: 'prayer', label: 'Preparación en oración' },
  { key: 'people', label: 'Participantes' },
  { key: 'review', label: 'Revisar y guardar' },
];

const addDays = (iso, days) => { const value = new Date(`${iso}T12:00:00`); value.setDate(value.getDate() + days); return value.toISOString().slice(0, 10); };
const daysBetween = (start, end) => {
  if (!start || !end || end < start) return [];
  const list = []; let cursor = start;
  while (cursor <= end && list.length < 60) { list.push(cursor); cursor = addDays(cursor, 1); }
  return list;
};
const formatDate = (iso) => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('es', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }) : '—');
const durationLabel = (minutes) => `${Math.floor(minutes / 60)} h${minutes % 60 ? ` ${minutes % 60} min` : ''}`;

const Field = ({ label, hint, children, required }) => (
  <label className="block space-y-1">
    <span className="text-sm font-semibold text-[#101D36]">{label}{required && <span className="text-[#b4493d]"> *</span>}</span>
    {children}
    {hint && <span className="block text-xs text-slate-500">{hint}</span>}
  </label>
);
const inputClass = 'h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base text-[#101D36] focus:border-[#101D36] focus:outline-none';

export function PersonPicker({ value, onChange, placeholder, testId }) {
  const { API, getAuthHeaders } = useAuth();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return undefined; }
    const timer = setTimeout(() => {
      axios.get(`${API}/api/mentorship/outreach/person-search`, { ...getAuthHeaders(), params: { q: query.trim(), limit: 8 } })
        .then((response) => setResults(response.data.items || [])).catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [API, getAuthHeaders, query]);
  if (value) {
    return <div className="flex min-h-12 items-center justify-between gap-2 rounded-lg border border-[#D9D4C7] bg-[#FBFAF7] px-3" data-testid={`${testId}-chosen`}><span className="text-base text-[#101D36]">{value.name}</span><button type="button" onClick={() => onChange(null)} className="grid h-10 w-10 place-items-center rounded-md hover:bg-slate-100" aria-label="Quitar"><X className="h-4 w-4" /></button></div>;
  }
  return (
    <div className="space-y-1">
      <div className="relative"><Search className="absolute left-3 top-3.5 h-5 w-5 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={placeholder || 'Buscar en Persona 360…'} className={`${inputClass} pl-10`} data-testid={`${testId}-search`} /></div>
      {results.length > 0 && <ul className="max-h-48 overflow-y-auto rounded-lg border border-[#E8E5DE] bg-white">{results.map((item) => <li key={item.person_id}><button type="button" onClick={() => { onChange(item); setQuery(''); }} className="block min-h-11 w-full px-3 text-left text-sm hover:bg-[#FBF6EA]" data-testid={`${testId}-result`}>{item.name}</button></li>)}</ul>}
    </div>
  );
}

function ReviewRow({ label, value }) {
  return <div className="grid gap-0.5 border-b border-[#EEECE6] py-2 sm:grid-cols-3"><dt className="text-sm text-slate-500">{label}</dt><dd className="whitespace-pre-line text-sm font-medium text-[#101D36] sm:col-span-2">{value || <span className="text-slate-400">Sin indicar</span>}</dd></div>;
}

const emptyForm = () => ({
  name: '', purpose: '', description: '', location: '', start_date: '', end_date: '', schedule: {},
  general_lead: null, logistics_lead: null, emergency_name: '', emergency_phone: '',
  departure_point: 'La iglesia', site_address: '', site_reference: '', site_maps_url: '',
  prayer_start_date: '', prayer_touched: false, mentor_ids: [], front_group_ids: [],
  sectors_text: '', zone_notes: '', instructions: '', credentials: {}, collaborators: [],
});

// FASE 6A: ÚNICO formulario de invasiones (Panel de Consolidación y Visitas e
// Invasiones → Panel de líderes). Por pasos, con revisión y "Corregir" antes de
// guardar; también edita invasiones ya creadas (las anteriores sin los campos
// nuevos se abren con esos campos vacíos). El backend vuelve a validar todo.
export function CreateCampaignDialog({ open, onOpenChange, onCreated, mentorOptions = null, request = null, campaignId = null }) {
  const { API, getAuthHeaders } = useAuth();
  const onClose = () => onOpenChange(false);
  // La lista de mentores del panel se lee al abrir (sin reiniciar el formulario si el panel se vuelve a dibujar).
  const mentorOptionsRef = useRef(mentorOptions);
  mentorOptionsRef.current = mentorOptions;
  const onSaved = onCreated;
  const [groupToAdd, setGroupToAdd] = useState('');
  const [loadingGroup, setLoadingGroup] = useState(false);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(emptyForm);
  const [mentors, setMentors] = useState([]);
  const [groups, setGroups] = useState([]);
  const [mentorQuery, setMentorQuery] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const set = (patch) => setForm((current) => ({ ...current, ...patch }));

  useEffect(() => {
    if (!open) return;
    setStep(0); setMentorQuery('');
    setGroupToAdd('');
    if (mentorOptionsRef.current) setMentors(mentorOptionsRef.current);
    else axios.get(`${API}/api/mentorship/mentors`, getAuthHeaders()).then((response) => setMentors(response.data.items || [])).catch(() => setMentors([]));
    axios.get(`${API}/api/front-groups`, getAuthHeaders()).then((response) => setGroups((response.data.items || []).filter((item) => !item.member_view))).catch(() => setGroups([]));
    if (campaignId) {
      setLoading(true);
      axios.get(`${API}/api/invasions/${campaignId}`, getAuthHeaders()).then(({ data }) => {
        setForm({
          ...emptyForm(), name: data.name || '', purpose: data.purpose || '', description: data.description || data.instructions || '', location: data.location || '',
          start_date: data.start_date, end_date: data.end_date,
          schedule: Object.fromEntries((data.schedule_days || []).map((item) => [item.day, { start_time: item.start_time, duration_minutes: item.duration_minutes }])),
          general_lead: data.general_lead, logistics_lead: data.logistics_lead,
          emergency_name: data.emergency_contact?.name || '', emergency_phone: data.emergency_contact?.phone || '',
          departure_point: data.departure_point || data.meeting_place || 'La iglesia',
          site_address: data.site_meeting_point?.address || '', site_reference: data.site_meeting_point?.reference || '', site_maps_url: data.site_meeting_point?.maps_url || '',
          prayer_start_date: data.prayer_start_date || '', prayer_touched: data.prayer_default === false,
          mentor_ids: data.assigned_mentor_ids || [], front_group_ids: data.invited_front_group_ids || [],
          sectors_text: (data.sectors || []).join('\n'), zone_notes: data.zone_notes || '', instructions: data.instructions || '',
        });
      }).catch((error) => toast.error(apiErrorMessage(error, 'No se pudo cargar la invasión'))).finally(() => setLoading(false));
    } else if (request) {
      setForm({ ...emptyForm(), name: request.proposed_name || (request.proposed_location ? `Invasión ${request.proposed_location}` : ''), location: request.proposed_location || '', start_date: request.proposed_start_date || '', end_date: request.proposed_end_date || '', description: request.notes || '', front_group_ids: request.front_group_id ? [request.front_group_id] : [] });
    } else {
      setForm(emptyForm());
    }
  }, [open, API, getAuthHeaders, campaignId, request]);

  const days = useMemo(() => daysBetween(form.start_date, form.end_date), [form.start_date, form.end_date]);
  const prayerDate = form.prayer_touched && form.prayer_start_date ? form.prayer_start_date : (form.start_date ? addDays(form.start_date, -7) : '');
  const scheduleFor = (day) => form.schedule[day] || { start_time: '09:00', duration_minutes: 180 };
  const setSchedule = (day, patch) => set({ schedule: { ...form.schedule, [day]: { ...scheduleFor(day), ...patch } } });

  const stepError = (index) => {
    const key = STEPS[index].key;
    if (key === 'general' && form.name.trim().length < 2) return 'Escribe el nombre de la invasión';
    if (key === 'place') {
      if (form.location.trim().length < 2) return 'Indica el barrio o lugar';
      if (!form.start_date || !form.end_date) return 'Indica las fechas de inicio y fin';
      if (form.end_date < form.start_date) return 'La fecha de fin no puede ser anterior a la de inicio';
    }
    if (key === 'leads' && (form.emergency_name || form.emergency_phone) && (form.emergency_name.trim().length < 2 || form.emergency_phone.trim().length < 4)) return 'Completa nombre y teléfono del contacto de emergencias';
    if (key === 'prayer' && prayerDate && form.start_date && prayerDate > form.start_date) return 'La oración debe empezar antes de la invasión';
    if (key === 'people' && !campaignId) {
      for (const personId of form.mentor_ids) {
        const mentor = mentors.find((item) => item.person_id === personId);
        if (!mentorNeedsAccountCreation(mentor)) continue;
        const cred = form.credentials[personId] || {};
        if (!cred.email || !cred.password || cred.password.length < 10) return `Indica correo y una clave temporal de al menos 10 caracteres para ${mentor.name}`;
        if (cred.password !== cred.confirm) return `Las claves no coinciden para ${mentor.name}`;
      }
    }
    return '';
  };
  const firstError = () => { for (let index = 0; index < STEPS.length - 1; index += 1) { const error = stepError(index); if (error) return { index, error }; } return null; };
  const next = () => { const error = stepError(step); if (error) { toast.error(error); return; } setStep((value) => Math.min(value + 1, STEPS.length - 1)); };

  const payload = () => ({
    name: form.name.trim(), location: form.location.trim(), purpose: form.purpose.trim() || null, description: form.description.trim() || null,
    start_date: form.start_date, end_date: form.end_date,
    schedule_days: days.map((day) => ({ day, ...scheduleFor(day) })),
    general_lead_person_id: form.general_lead?.person_id || null, logistics_lead_person_id: form.logistics_lead?.person_id || null,
    emergency_contact: form.emergency_name.trim() ? { name: form.emergency_name.trim(), phone: form.emergency_phone.trim() } : null,
    departure_point: form.departure_point.trim() || 'La iglesia',
    site_meeting_point: form.site_address || form.site_reference || form.site_maps_url ? { address: form.site_address || null, reference: form.site_reference || null, maps_url: form.site_maps_url || null } : null,
    prayer_start_date: form.prayer_touched ? form.prayer_start_date || null : null,
    invited_front_group_ids: form.front_group_ids,
    ...(campaignId ? {} : { collaborator_person_ids: form.collaborators.map((item) => item.person_id) }),
    sectors: form.sectors_text.split(/\n|,/).map((item) => item.trim()).filter(Boolean),
    zone_notes: form.zone_notes.trim() || null,
    instructions: form.instructions.trim() || null,
  });
  const assignedMentors = () => form.mentor_ids.map((personId) => {
    const mentor = mentors.find((item) => item.person_id === personId);
    const cred = form.credentials[personId];
    return mentorNeedsAccountCreation(mentor) && cred ? { person_id: personId, email: cred.email.trim(), temporary_password: cred.password } : { person_id: personId };
  });
  const setCredential = (personId, field, value) => set({ credentials: { ...form.credentials, [personId]: { ...form.credentials[personId], [field]: value } } });
  const addGroupMentors = async () => {
    if (!groupToAdd) { toast.error('Elige un Grupo Frontal'); return; }
    setLoadingGroup(true);
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/mentors-by-group/${groupToAdd}`, getAuthHeaders());
      const found = response.data.items || [];
      if (!found.length) { toast.message('Ese grupo no tiene mentores con insignia activa todavía'); return; }
      setMentors((current) => { const map = new Map(current.map((item) => [item.person_id, item])); found.forEach((item) => map.set(item.person_id, item)); return Array.from(map.values()); });
      const addable = found.filter((item) => !mentorAccountBlocked(item)).map((item) => item.person_id);
      setForm((current) => ({ ...current, mentor_ids: Array.from(new Set([...current.mentor_ids, ...addable])) }));
      toast.success(`${found.length} mentor(es) del grupo agregados`);
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudieron cargar los mentores de ese grupo')); } finally { setLoadingGroup(false); }
  };

  const save = async () => {
    const problem = firstError();
    if (problem) { toast.error(problem.error); setStep(problem.index); return; }
    setSaving(true);
    try {
      const response = campaignId
        ? await axios.put(`${API}/api/invasions/${campaignId}`, payload(), getAuthHeaders())
        : await axios.post(`${API}/api/invasions`, { ...payload(), assigned_mentors: assignedMentors(), request_id: request?.request_id || null }, getAuthHeaders());
      const accounts = response.data.accounts_created || [];
      toast.success(campaignId ? 'Invasión actualizada; se avisó a los invitados' : `Invasión creada; se avisó a los invitados${accounts.length ? ` · ${accounts.length} cuenta(s) de mentor nuevas` : ''}`);
      onSaved?.(response.data);
      onClose();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar la invasión')); } finally { setSaving(false); }
  };

  if (!open) return null;
  const current = STEPS[step];
  const filteredMentors = mentors.filter((item) => item.name?.toLowerCase().includes(mentorQuery.trim().toLowerCase()));
  const mentorName = (id) => mentors.find((item) => item.person_id === id)?.name || 'Mentor';
  const groupName = (id) => groups.find((item) => item.front_group_id === id)?.display_name || groups.find((item) => item.front_group_id === id)?.name || 'Grupo';

  const body = {
    general: <div className="space-y-4">
      <Field label="Nombre de la invasión" required><input value={form.name} onChange={(event) => set({ name: event.target.value })} className={inputClass} data-testid="wizard-name" /></Field>
      <Field label="Propósito" hint="En una frase: qué se busca lograr."><input value={form.purpose} onChange={(event) => set({ purpose: event.target.value })} className={inputClass} data-testid="wizard-purpose" /></Field>
      <Field label="Descripción"><textarea value={form.description} onChange={(event) => set({ description: event.target.value })} rows={5} className="w-full rounded-lg border border-[#D9D4C7] bg-white p-3 text-base" data-testid="wizard-description" /></Field>
    </div>,
    place: <div className="space-y-4">
      <Field label="Barrio o lugar" required><input value={form.location} onChange={(event) => set({ location: event.target.value })} className={inputClass} data-testid="wizard-location" /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Fecha de inicio" required><input type="date" value={form.start_date} onChange={(event) => set({ start_date: event.target.value, end_date: form.end_date && form.end_date >= event.target.value ? form.end_date : event.target.value })} className={inputClass} data-testid="wizard-start" /></Field>
        <Field label="Fecha de fin" required><input type="date" value={form.end_date} min={form.start_date || undefined} onChange={(event) => set({ end_date: event.target.value })} className={inputClass} data-testid="wizard-end" /></Field>
      </div>
      <Field label="Sectores o calles a cubrir" hint="Uno por línea (opcional)."><textarea value={form.sectors_text} onChange={(event) => set({ sectors_text: event.target.value })} rows={3} className="w-full rounded-lg border border-[#D9D4C7] bg-white p-3 text-base" data-testid="wizard-sectors" /></Field>
      <Field label="Notas de la zona (opcional)"><textarea value={form.zone_notes} onChange={(event) => set({ zone_notes: event.target.value })} rows={2} className="w-full rounded-lg border border-[#D9D4C7] bg-white p-3 text-base" data-testid="wizard-zone-notes" /></Field>
      {days.length > 0 && <div className="space-y-2" data-testid="wizard-schedule">
        <p className="text-sm font-semibold text-[#101D36]">Horario y duración de cada jornada</p>
        <div className="grid gap-2 lg:grid-cols-2">{days.map((day) => (
          <div key={day} className="grid grid-cols-2 items-end gap-2 rounded-lg border border-[#EEECE6] bg-[#FBFAF7] p-3">
            <p className="col-span-2 text-sm font-semibold capitalize text-[#101D36]">{formatDate(day)}</p>
            <Field label="Hora de inicio"><input type="time" value={scheduleFor(day).start_time} onChange={(event) => setSchedule(day, { start_time: event.target.value })} className={inputClass} /></Field>
            <Field label="Duración"><select value={scheduleFor(day).duration_minutes} onChange={(event) => setSchedule(day, { duration_minutes: Number(event.target.value) })} className={inputClass}>{[60, 90, 120, 150, 180, 240, 300, 360, 480].map((minutes) => <option key={minutes} value={minutes}>{durationLabel(minutes)}</option>)}</select></Field>
          </div>
        ))}</div>
      </div>}
    </div>,
    leads: <div className="space-y-4">
      <Field label="Encargado general"><PersonPicker value={form.general_lead} onChange={(value) => set({ general_lead: value })} testId="wizard-general-lead" /></Field>
      <Field label="Encargado de logística"><PersonPicker value={form.logistics_lead} onChange={(value) => set({ logistics_lead: value })} testId="wizard-logistics-lead" /></Field>
      <Field label="Logística e instrucciones" hint="Qué llevar, transporte, cómo presentarse, seguridad."><textarea value={form.instructions} onChange={(event) => set({ instructions: event.target.value })} rows={3} className="w-full rounded-lg border border-[#D9D4C7] bg-white p-3 text-base" data-testid="wizard-instructions" /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Contacto de emergencias (nombre)"><input value={form.emergency_name} onChange={(event) => set({ emergency_name: event.target.value })} className={inputClass} data-testid="wizard-emergency-name" /></Field>
        <Field label="Teléfono de emergencias"><input type="tel" inputMode="tel" value={form.emergency_phone} onChange={(event) => set({ emergency_phone: event.target.value })} className={inputClass} data-testid="wizard-emergency-phone" /></Field>
      </div>
    </div>,
    meeting: <div className="space-y-4">
      <Field label="Punto de encuentro inicial" hint="Por defecto, la iglesia."><input value={form.departure_point} onChange={(event) => set({ departure_point: event.target.value })} className={inputClass} data-testid="wizard-departure" /></Field>
      <p className="pt-2 text-sm font-semibold text-[#101D36]">Punto de encuentro en el lugar</p>
      <Field label="Dirección"><input value={form.site_address} onChange={(event) => set({ site_address: event.target.value })} className={inputClass} data-testid="wizard-site-address" /></Field>
      <Field label="Referencia" hint="Ej.: frente al colmado, en la cancha."><input value={form.site_reference} onChange={(event) => set({ site_reference: event.target.value })} className={inputClass} data-testid="wizard-site-reference" /></Field>
      <Field label="Ubicación (enlace de mapa, opcional)"><input type="url" value={form.site_maps_url} onChange={(event) => set({ site_maps_url: event.target.value })} className={inputClass} placeholder="https://maps…" /></Field>
    </div>,
    prayer: <div className="space-y-4">
      <p className="text-sm text-slate-600">La primera etapa es la preparación en oración. Por defecto empieza <b>una semana antes</b> de salir.</p>
      <Field label="Inicio de la preparación en oración" hint={form.prayer_touched ? 'Fecha elegida manualmente.' : 'Calculada automáticamente: una semana antes del inicio.'}>
        <input type="date" value={prayerDate} max={form.start_date || undefined} onChange={(event) => set({ prayer_start_date: event.target.value, prayer_touched: true })} className={inputClass} data-testid="wizard-prayer" />
      </Field>
      {form.prayer_touched && <button type="button" onClick={() => set({ prayer_touched: false, prayer_start_date: '' })} className="min-h-10 text-sm font-semibold text-[#7A5F22] underline">Volver a una semana antes</button>}
    </div>,
    people: <div className="space-y-5">
      {campaignId && <p className="rounded-lg bg-[#FBF6EA] p-3 text-sm text-[#7A5F22]">Los mentores ya invitados se administran desde la lista de participantes de la invasión.</p>}
      {!campaignId && <div className="space-y-2">
        <p className="text-sm font-semibold text-[#101D36]">Mentores invitados ({form.mentor_ids.length})</p>
        {groups.length > 0 && <div className="flex flex-col gap-2 rounded-lg border border-dashed border-[#D9CFB4] bg-[#FBFAF7] p-2 sm:flex-row">
          <select value={groupToAdd} onChange={(event) => setGroupToAdd(event.target.value)} className={inputClass} data-testid="wizard-add-group-select"><option value="">Agregar los mentores de un Grupo Frontal…</option>{groups.map((item) => <option key={item.front_group_id} value={item.front_group_id}>{item.display_name || item.name}</option>)}</select>
          <button type="button" onClick={addGroupMentors} disabled={loadingGroup} className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-lg border border-[#D9D4C7] bg-white px-4 text-sm font-semibold text-[#101D36]" data-testid="wizard-add-group-button">{loadingGroup ? <Loader2 className="h-4 w-4 animate-spin" /> : <Users className="h-4 w-4" />} Agregar grupo</button>
        </div>}
        <input value={mentorQuery} onChange={(event) => setMentorQuery(event.target.value)} placeholder="Buscar mentor…" className={inputClass} data-testid="wizard-mentor-search" />
        <ul className="grid max-h-80 gap-1 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">{filteredMentors.map((item) => {
          const blocked = mentorAccountBlocked(item);
          const needsAccount = mentorNeedsAccountCreation(item);
          const checked = form.mentor_ids.includes(item.person_id);
          return <li key={item.person_id} className={checked && needsAccount ? 'sm:col-span-2 xl:col-span-3' : ''}>
            <label className={`flex min-h-12 items-center gap-3 rounded-lg border px-3 ${checked ? 'border-[#101D36] bg-[#F3F5F9]' : 'border-[#EEECE6]'} ${blocked ? 'opacity-60' : ''}`}><input type="checkbox" className="h-5 w-5" disabled={blocked} checked={checked} onChange={() => set({ mentor_ids: checked ? form.mentor_ids.filter((id) => id !== item.person_id) : [...form.mentor_ids, item.person_id] })} data-testid={`wizard-mentor-${item.person_id}`} /><span className="text-sm">{item.lbs_qualified ? `${item.name} (LBS)` : item.name}{blocked && <span className="block text-xs text-slate-500">Cuenta inactiva</span>}{needsAccount && <span className="block text-xs text-slate-500">Sin cuenta: se crea al guardar</span>}</span></label>
            {checked && needsAccount && <div className="mt-1 grid gap-2 rounded-lg border border-dashed border-[#D9CFB4] bg-[#FBFAF7] p-2 sm:grid-cols-3" data-testid={`wizard-mentor-credentials-${item.person_id}`}>
              <input type="email" placeholder="Correo" value={form.credentials[item.person_id]?.email || ''} onChange={(event) => setCredential(item.person_id, 'email', event.target.value)} className={inputClass} />
              <input type="password" placeholder="Clave temporal" value={form.credentials[item.person_id]?.password || ''} onChange={(event) => setCredential(item.person_id, 'password', event.target.value)} className={inputClass} />
              <input type="password" placeholder="Confirmar clave" value={form.credentials[item.person_id]?.confirm || ''} onChange={(event) => setCredential(item.person_id, 'confirm', event.target.value)} className={inputClass} />
            </div>}
          </li>;
        })}</ul>
        {filteredMentors.length === 0 && <p className="text-xs text-slate-500">Sin mentores con insignia activa.</p>}
        {mentors.some(mentorAccountBlocked) && <p className="text-xs text-slate-500">{mentorAccessHint}</p>}
      </div>}
      {!campaignId && <div className="space-y-2" data-testid="wizard-collaborators">
        <p className="text-sm font-semibold text-[#101D36]">Colaboradores invitados ({form.collaborators.length})</p>
        <p className="text-xs text-slate-500">Ayudan a registrar personas y hogares. No reciben cuenta ni acceso a módulos por estar invitados.</p>
        {form.collaborators.length > 0 && <ul className="flex flex-wrap gap-2">{form.collaborators.map((item) => <li key={item.person_id} className="inline-flex min-h-10 items-center gap-1 rounded-full border border-[#D9D4C7] bg-white pl-3 text-sm text-[#101D36]" data-testid="wizard-collaborator-chip">{item.name}<button type="button" onClick={() => set({ collaborators: form.collaborators.filter((entry) => entry.person_id !== item.person_id) })} className="grid h-10 w-10 place-items-center rounded-full hover:bg-slate-100" aria-label={`Quitar a ${item.name}`}><X className="h-4 w-4" /></button></li>)}</ul>}
        <PersonPicker value={null} onChange={(person) => { if (person && !form.collaborators.some((item) => item.person_id === person.person_id) && !form.mentor_ids.includes(person.person_id)) set({ collaborators: [...form.collaborators, person] }); }} placeholder="Buscar colaborador en Persona 360…" testId="wizard-collaborator" />
      </div>}
      <div className="space-y-2">
        <p className="text-sm font-semibold text-[#101D36]">Grupos Frontales invitados ({form.front_group_ids.length})</p>
        <ul className="grid gap-1 sm:grid-cols-2 xl:grid-cols-3">{groups.map((item) => {
          const checked = form.front_group_ids.includes(item.front_group_id);
          return <li key={item.front_group_id}><label className={`flex min-h-12 items-center gap-3 rounded-lg border px-3 ${checked ? 'border-[#101D36] bg-[#F3F5F9]' : 'border-[#EEECE6]'}`}><input type="checkbox" className="h-5 w-5" checked={checked} onChange={() => set({ front_group_ids: checked ? form.front_group_ids.filter((id) => id !== item.front_group_id) : [...form.front_group_ids, item.front_group_id] })} data-testid={`wizard-group-${item.front_group_id}`} /><span className="text-sm">{item.display_name || item.name}</span></label></li>;
        })}</ul>
      </div>
      <p className="text-xs text-slate-500">Los integrantes de los Grupos Frontales invitados entran como colaboradores. La pastora/pastor general supervisa y no se agrega como participante. Después de guardar, la lista se ajusta en «Participantes».</p>
    </div>,
    review: (() => {
      const section = (index, title, rows) => (
        <section className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid={`wizard-review-${STEPS[index].key}`}>
          <div className="flex items-center justify-between gap-2"><h4 className="text-base font-semibold text-[#101D36]">{title}</h4><button type="button" onClick={() => setStep(index)} className="min-h-10 rounded-md border border-[#D9CFB4] px-3 text-sm font-semibold text-[#7A5F22]" data-testid={`wizard-fix-${STEPS[index].key}`}>Corregir</button></div>
          <dl className="mt-2">{rows.map(([label, value]) => <ReviewRow key={label} label={label} value={value} />)}</dl>
        </section>
      );
      return <div className="grid gap-3 lg:grid-cols-2">
        {section(0, 'Datos generales', [['Nombre', form.name], ['Propósito', form.purpose], ['Descripción', form.description]])}
        {section(1, 'Lugar y fechas', [['Lugar', form.location], ['Sectores', form.sectors_text.split(/\n|,/).map((item) => item.trim()).filter(Boolean).join(', ')], ['Notas de la zona', form.zone_notes], ['Fechas', form.start_date ? `${formatDate(form.start_date)} → ${formatDate(form.end_date)}` : ''], ['Jornadas', days.map((day) => `${formatDate(day)} · ${scheduleFor(day).start_time} · ${durationLabel(scheduleFor(day).duration_minutes)}`).join('\n')]])}
        {section(2, 'Responsables', [['Encargado general', form.general_lead?.name], ['Logística', form.logistics_lead?.name], ['Instrucciones', form.instructions], ['Emergencias', form.emergency_name ? `${form.emergency_name} · ${form.emergency_phone}` : '']])}
        {section(3, 'Puntos de encuentro', [['Inicial', form.departure_point], ['En el lugar', [form.site_address, form.site_reference].filter(Boolean).join(' · ')]])}
        {section(4, 'Preparación en oración', [['Inicio', prayerDate ? `${formatDate(prayerDate)}${form.prayer_touched ? '' : ' (una semana antes)'}` : '']])}
        {section(5, 'Participantes', [['Mentores', campaignId ? 'Se administran en la lista de participantes' : form.mentor_ids.map(mentorName).join(', ')], ['Colaboradores', campaignId ? 'Se administran en la lista de participantes' : form.collaborators.map((item) => item.name).join(', ')], ['Grupos Frontales', form.front_group_ids.map(groupName).join(', ')]])}
      </div>;
    })(),
  }[current.key];

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#F8F6F0] text-[#101D36]" role="dialog" aria-modal="true" aria-label={campaignId ? 'Editar invasión' : 'Crear invasión'} data-testid="invasion-wizard">
      <header className="flex items-center gap-2 border-b border-[#E8E5DE] bg-white px-3 py-2 sm:px-6">
        <button type="button" onClick={onClose} className="grid h-11 w-11 place-items-center rounded-md hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        <div className="min-w-0 flex-1">
          <p className="truncate font-['Spectral'] text-lg font-semibold text-[#101D36]">{campaignId ? 'Editar invasión' : request ? 'Aprobar solicitud: crear invasión' : 'Crear invasión'}</p>
          <p className="text-xs text-slate-500">Paso {step + 1} de {STEPS.length} · {current.label}</p>
        </div>
      </header>
      <div className="h-1 bg-slate-200"><div className="h-full bg-[#101D36] transition-all" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} /></div>
      <div className="flex min-h-0 flex-1">
        <nav className="hidden w-64 shrink-0 border-r border-[#E8E5DE] bg-white p-3 lg:block" aria-label="Pasos">
          <ol className="space-y-1">{STEPS.map((item, index) => (
            <li key={item.key}><button type="button" onClick={() => setStep(index)} className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-left text-sm ${index === step ? 'bg-[#101D36] font-semibold text-white' : 'text-slate-700 hover:bg-slate-50'}`}>
              <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs ${index === step ? 'bg-white text-[#101D36]' : index < step ? 'bg-[#3d8b5a] text-white' : 'bg-slate-100 text-slate-600'}`}>{index < step ? <Check className="h-3.5 w-3.5" /> : index + 1}</span>{item.label}
            </button></li>
          ))}</ol>
        </nav>
        <main className="min-w-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6 lg:px-10">
          <div className="mx-auto w-full max-w-5xl">
            <h3 className="mb-4 font-['Spectral'] text-2xl font-semibold text-[#101D36]" data-testid="wizard-step-title">{current.label}</h3>
            {loading ? <div className="flex justify-center py-16"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div> : body}
          </div>
        </main>
      </div>
      <footer className="grid grid-cols-2 gap-2 border-t border-[#E8E5DE] bg-white p-3 sm:flex sm:justify-end sm:px-6" style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}>
        <button type="button" onClick={() => (step === 0 ? onClose() : setStep(step - 1))} className="min-h-12 rounded-lg border border-[#D9D4C7] bg-white px-6 text-base font-semibold text-[#101D36]" data-testid="wizard-back">{step === 0 ? 'Cancelar' : 'Atrás'}</button>
        {current.key === 'review'
          ? <button type="button" onClick={save} disabled={saving} className="min-h-12 rounded-lg bg-[#101D36] px-6 text-base font-semibold text-white disabled:opacity-60" data-testid="wizard-save">{saving ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : campaignId ? 'Guardar cambios' : 'Crear invasión'}</button>
          : <button type="button" onClick={next} className="min-h-12 rounded-lg bg-[#101D36] px-6 text-base font-semibold text-white" data-testid="wizard-next">{step === STEPS.length - 2 ? 'Revisar' : 'Siguiente'}</button>}
      </footer>
    </div>
  );
}
