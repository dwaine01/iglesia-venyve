import React, { useRef, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Check, CheckCircle2, ChevronDown, Loader2, Minus, Plus, Save } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { PersonMatchDialog } from '../outreach/PersonMatchDialog';

export const newRequestId = () => (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);

const LEVELS = [['brief', 'Atención breve'], ['conversation', 'Conversamos'], ['invited_in', 'Nos invitaron a pasar']];
const ACTIONS = [['invitation', 'Invitación'], ['prayer', 'Oración'], ['book', 'Entrega de libro'], ['other_material', 'Otro material']];
const FOLLOWUP = [['yes', 'Sí'], ['no', 'No'], ['not_asked', 'No se preguntó']];
// Próxima acción del seguimiento (mismo modelo que Consolidación: acción + fecha). No inicia Consolidación.
const NEXT_ACTIONS = ['Visitar de nuevo', 'Llamar por teléfono', 'Enviar mensaje', 'Invitar a la iglesia'];
const LANGUAGES = [['es', 'Español'], ['en', 'Inglés'], ['other', 'Otro'], ['unknown', 'Desconocido']];

const emptyVisit = () => ({ opened: null, contact_level: null, actions: [], books: {}, other_material_count: 0, followup: 'not_asked', followup_date: '', followup_next_action: 'Visitar de nuevo',
  language: null, language_other: '', impression: false, name: '', phone: '', note: '', shared: false, religion: '', origin: '', start_consolidation: false });

// Botón grande de opción (táctil 48 px, estado visible también sin color).
const Choice = ({ active, onClick, children, testId, tone = 'navy' }) => (
  <button type="button" onClick={onClick} aria-pressed={active} data-testid={testId}
    className={`inline-flex min-h-12 items-center justify-center gap-1.5 rounded-xl border-2 px-3 text-[15px] font-semibold transition ${active ? (tone === 'green' ? 'border-[#2f6e47] bg-[#2f6e47] text-white' : tone === 'red' ? 'border-[#8f382f] bg-[#8f382f] text-white' : 'border-[#132443] bg-[#132443] text-white') : 'border-[#D9D4C7] bg-white text-[#101D36]'}`}>
    {active && <Check className="h-4 w-4" />}{children}
  </button>
);

function Stepper({ value, onChange, testId, max = 50 }) {
  return (
    <div className="inline-flex items-center gap-1" data-testid={testId}>
      <button type="button" onClick={() => onChange(Math.max(0, value - 1))} className="grid h-11 w-11 place-items-center rounded-lg border border-[#D9D4C7] bg-white" aria-label="Menos"><Minus className="h-5 w-5" /></button>
      <span className="w-8 text-center text-lg font-semibold" data-testid={`${testId}-value`}>{value}</span>
      <button type="button" onClick={() => onChange(Math.min(max, value + 1))} className="grid h-11 w-11 place-items-center rounded-lg border border-[#D9D4C7] bg-white" aria-label="Más" data-testid={`${testId}-plus`}><Plus className="h-5 w-5" /></button>
    </div>
  );
}

const Label = ({ children }) => <p className="mb-1.5 text-sm font-semibold text-slate-700">{children}</p>;

/** Registro de una puerta: solo número y apartamento (la calle ya está
 * activa) y la visita con botones grandes. Cada guardado lleva su clave
 * única: un doble toque nunca duplica el registro. */
export function DoorForm({ campaignId, street, books, household = null, onSaved }) {
  const { API, getAuthHeaders } = useAuth();
  const numberRef = useRef(null);
  const requestId = useRef(newRequestId());
  const [number, setNumber] = useState('');
  const [unit, setUnit] = useState('');
  const [visit, setVisit] = useState(emptyVisit);
  const [saving, setSaving] = useState(false);
  const [more, setMore] = useState(false);
  const [match, setMatch] = useState(null);
  // Confirmación visible y fija (un solo aviso breve; no se apilan sobre los botones).
  const [lastSaved, setLastSaved] = useState(null);
  const set = (patch) => setVisit((current) => ({ ...current, ...patch }));
  const toggleAction = (key) => set({ actions: visit.actions.includes(key) ? visit.actions.filter((item) => item !== key) : [...visit.actions, key] });

  const reset = (keepFocus) => {
    requestId.current = newRequestId();
    setNumber(''); setUnit(''); setVisit(emptyVisit()); setMore(false);
    if (keepFocus) setTimeout(() => numberRef.current?.focus(), 50);
  };

  const startConsolidation = async (visitId, overrides = {}) => {
    try {
      await axios.post(`${API}/api/mentorship/outreach/visits/${visitId}/start-seven-weeks`, overrides, getAuthHeaders());
      toast.success('La persona comenzó Consolidación'); setMatch(null);
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (error?.response?.status === 409 && detail?.candidates) setMatch({ visitId, message: detail.message, candidates: detail.candidates, requiresConfirmation: Boolean(detail.requires_confirmation), action: overrides });
      else toast.error(`${apiErrorMessage(error, 'No se pudo iniciar Consolidación')}. La visita sí quedó guardada; puedes iniciarla desde Mis visitas.`);
    }
  };

  const save = async (addAnother) => {
    if (!household && !number.trim()) { toast.error('Escribe el número de la casa o edificio'); numberRef.current?.focus(); return; }
    if (visit.opened === null) { toast.error('Indica si abrieron'); return; }
    if (saving) return;
    setSaving(true);
    const opened = visit.opened;
    const body = {
      client_request_id: requestId.current, opened, note: visit.note.trim() || null,
      books: Object.entries(visit.books).filter(([, quantity]) => quantity > 0).map(([book, quantity]) => ({ book, quantity })),
      other_material_count: visit.actions.includes('other_material') ? visit.other_material_count : 0,
      ...(opened ? {
        contact_level: visit.contact_level, actions: visit.actions, followup: visit.followup, followup_date: visit.followup === 'yes' && visit.followup_date ? visit.followup_date : null,
        followup_next_action: visit.followup === 'yes' ? visit.followup_next_action : null,
        language: visit.language, language_other: visit.language === 'other' ? visit.language_other.trim() || null : null,
        language_basis: visit.language && visit.language !== 'unknown' ? (visit.impression ? 'impression' : 'confirmed') : null,
        shared_by_person: visit.shared, religion: visit.shared ? visit.religion.trim() || null : null, origin: visit.shared ? visit.origin.trim() || null : null,
        person: visit.name.trim() || visit.phone.trim() ? { contact_type: 'new', contact_name: visit.name.trim() || null, contact_phone: visit.phone.trim() || null } : null,
      } : { actions: visit.actions.filter((item) => item === 'book' || item === 'other_material') }),
    };
    try {
      const url = household ? `${API}/api/mentorship/outreach/households/${household.household_id}/attempts` : `${API}/api/mentorship/outreach/campaigns/${campaignId}/doors`;
      const response = await axios.post(url, household ? body : { ...body, house_number: number.trim(), unit: unit.trim() || null, street_name: street?.street_name }, getAuthHeaders());
      const data = response.data;
      const place = [data.household.address_line1, data.household.address_line2].filter(Boolean).join(' · ');
      // Confirmación fija en el formulario (sin aviso flotante que tape los botones).
      const pendingBooks = (data.event.books || []).filter((item) => item.inventory_status !== 'discounted');
      setLastSaved({ place, duplicate: data.duplicate, opened: data.event.opened, at: new Date(),
        warnings: [data.person_warning && `La visita quedó guardada, pero ${data.person_warning.charAt(0).toLowerCase()}${data.person_warning.slice(1)}`,
          pendingBooks.length && `Libros sin descuento de inventario (para conciliar): ${pendingBooks.map((item) => `${item.quantity} ${item.name}`).join(', ')}`].filter(Boolean) });
      const createdVisit = data.visits?.[0];
      if (visit.start_consolidation && createdVisit && !data.duplicate) await startConsolidation(createdVisit.visit_id);
      onSaved?.(data);
      reset(addAnother);
    } catch (error) {
      // La clave se conserva: reintentar no duplica.
      toast.error(apiErrorMessage(error, 'No se pudo guardar. Revisa la conexión e intenta de nuevo.'));
    } finally { setSaving(false); }
  };

  const opened = visit.opened === true;
  return (
    <section className="space-y-4 rounded-2xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid="door-form">
      {lastSaved && <div className="rounded-xl border border-[#bcd8c4] bg-[#eef5f0] p-3" role="status" data-testid="door-last-saved">
        <p className="flex items-center gap-2 text-[15px] font-semibold text-[#2f6e47]"><CheckCircle2 className="h-5 w-5 shrink-0" />{lastSaved.duplicate ? 'Ya estaba guardado' : 'Guardado'}: {lastSaved.place} · {lastSaved.opened ? 'abrieron' : 'no abrieron'} · {lastSaved.at.toLocaleTimeString('es', { hour: 'numeric', minute: '2-digit' })}</p>
        {lastSaved.warnings.map((warning) => <p key={warning} className="mt-1 flex items-start gap-2 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{warning}</p>)}
      </div>}
      {household
        ? <p className="text-base font-semibold text-[#101D36]">Nueva visita: {household.address_line1}{household.address_line2 ? ` · ${household.address_line2}` : ''}</p>
        : <div className="grid grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-2">
            <label className="min-w-0"><Label>N.º casa o edificio</Label><input ref={numberRef} value={number} onChange={(event) => setNumber(event.target.value)} inputMode="text" autoComplete="off" placeholder="Ej.: 1520" className="h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-lg font-semibold" data-testid="door-number" /></label>
            <label className="min-w-0"><Label>Apartamento</Label><input value={unit} onChange={(event) => setUnit(event.target.value)} autoComplete="off" placeholder="Opcional" className="h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-lg" data-testid="door-unit" /></label>
          </div>}

      <div>
        <Label>¿Abrieron?</Label>
        <div className="grid grid-cols-2 gap-2">
          <Choice active={visit.opened === true} onClick={() => set({ opened: true })} tone="green" testId="door-opened-yes">Sí</Choice>
          <Choice active={visit.opened === false} onClick={() => set({ opened: false, contact_level: null, followup: 'not_asked' })} tone="red" testId="door-opened-no">No</Choice>
        </div>
        {visit.opened === false && <p className="mt-2 text-sm text-slate-600">Quedará como pendiente de nueva visita. Puedes guardar ya.</p>}
      </div>

      {opened && <>
        <div>
          <Label>Atención</Label>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">{LEVELS.map(([key, label]) => <Choice key={key} active={visit.contact_level === key} onClick={() => set({ contact_level: visit.contact_level === key ? null : key })} testId={`door-level-${key}`}>{label}</Choice>)}</div>
        </div>
        <div>
          <Label>Qué se realizó (puedes elegir varias)</Label>
          <div className="grid grid-cols-2 gap-2">{ACTIONS.map(([key, label]) => <Choice key={key} active={visit.actions.includes(key)} onClick={() => toggleAction(key)} testId={`door-action-${key}`}>{label}</Choice>)}</div>
        </div>
      </>}

      {visit.opened === false && <div>
        <Label>¿Dejaron material en la puerta? (opcional)</Label>
        <div className="grid grid-cols-2 gap-2">{ACTIONS.filter(([key]) => key === 'book' || key === 'other_material').map(([key, label]) => <Choice key={key} active={visit.actions.includes(key)} onClick={() => toggleAction(key)} testId={`door-action-${key}`}>{label}</Choice>)}</div>
      </div>}

      {visit.actions.includes('book') && <div className="space-y-2 rounded-xl bg-[#FBFAF7] p-3" data-testid="door-books">
        <Label>Libros entregados</Label>
        {(books || []).map((book) => (
          <div key={book.book} className="flex items-center justify-between gap-2">
            <span className="min-w-0"><span className="block truncate text-base font-semibold text-[#101D36]">{book.name}</span><span className="block text-xs text-slate-500">{book.on_hand > 0 ? `Tienes ${book.on_hand}` : 'Sin existencias cargadas: se guarda para conciliar'}</span></span>
            <Stepper value={visit.books[book.book] || 0} onChange={(value) => set({ books: { ...visit.books, [book.book]: value } })} testId={`door-book-${book.sku || book.book}`} />
          </div>
        ))}
      </div>}
      {visit.actions.includes('other_material') && <div className="flex items-center justify-between rounded-xl bg-[#FBFAF7] p-3"><span className="text-base font-semibold text-[#101D36]">Otro material (cantidad)</span><Stepper value={visit.other_material_count} onChange={(value) => set({ other_material_count: value })} testId="door-other-material" max={200} /></div>}

      {opened && <>
        <div>
          <Label>¿Aceptó seguimiento?</Label>
          <div className="grid grid-cols-3 gap-2">{FOLLOWUP.map(([key, label]) => <Choice key={key} active={visit.followup === key} onClick={() => set({ followup: key })} testId={`door-followup-${key}`}>{label}</Choice>)}</div>
          {visit.followup === 'yes' && <div className="mt-2" data-testid="door-next-action"><Label>Próxima acción (responsable: tú)</Label><div className="grid grid-cols-2 gap-2">{NEXT_ACTIONS.map((action) => <Choice key={action} active={visit.followup_next_action === action} onClick={() => set({ followup_next_action: action })} testId={`door-next-action-${NEXT_ACTIONS.indexOf(action)}`}>{action}</Choice>)}</div></div>}
          {visit.followup === 'yes' && <label className="mt-2 block"><Label>Fecha (opcional)</Label><input type="date" value={visit.followup_date} onChange={(event) => set({ followup_date: event.target.value })} className="h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="door-followup-date" /></label>}
        </div>
        <div>
          <Label>Idioma</Label>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{LANGUAGES.map(([key, label]) => <Choice key={key} active={visit.language === key} onClick={() => set({ language: visit.language === key ? null : key })} testId={`door-language-${key}`}>{label}</Choice>)}</div>
          {visit.language === 'other' && <input value={visit.language_other} onChange={(event) => set({ language_other: event.target.value })} placeholder="¿Cuál?" className="mt-2 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" />}
          {visit.language && visit.language !== 'unknown' && <label className="mt-2 flex min-h-11 items-center gap-2 text-[15px] text-[#101D36]"><input type="checkbox" checked={visit.impression} onChange={(event) => set({ impression: event.target.checked })} className="h-5 w-5" data-testid="door-language-impression" />Es una impresión, sin confirmar</label>}
        </div>

        <button type="button" onClick={() => setMore(!more)} className="flex min-h-12 w-full items-center justify-between rounded-xl border border-[#D9D4C7] px-3 text-[15px] font-semibold text-[#101D36]" aria-expanded={more} data-testid="door-more">
          Datos de la persona y notas (opcional)<ChevronDown className={`h-5 w-5 transition ${more ? 'rotate-180' : ''}`} />
        </button>
        {more && <div className="space-y-3" data-testid="door-person">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <input value={visit.name} onChange={(event) => set({ name: event.target.value })} placeholder="Nombre" autoComplete="off" className="h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="door-person-name" />
            <input value={visit.phone} onChange={(event) => set({ phone: event.target.value })} placeholder="Teléfono" inputMode="tel" autoComplete="off" className="h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="door-person-phone" />
          </div>
          {(visit.name.trim() || visit.phone.trim()) && visit.followup === 'yes' && <label className="flex min-h-12 items-center gap-2 rounded-xl border border-[#bcd8c4] bg-[#eef5f0] px-3 text-[15px] font-semibold text-[#2f6e47]"><input type="checkbox" checked={visit.start_consolidation} onChange={(event) => set({ start_consolidation: event.target.checked })} className="h-5 w-5" data-testid="door-start-consolidation" />Comenzó consolidación (vincular o registrar en Persona 360)</label>}
          <textarea value={visit.note} onChange={(event) => set({ note: event.target.value })} rows={2} placeholder="Notas" className="w-full rounded-lg border border-[#D9D4C7] p-3 text-base" data-testid="door-note" />
          <label className="flex min-h-11 items-center gap-2 text-[15px] text-[#101D36]"><input type="checkbox" checked={visit.shared} onChange={(event) => set({ shared: event.target.checked })} className="h-5 w-5" data-testid="door-shared" />La persona compartió su religión u origen</label>
          {visit.shared && <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <input value={visit.religion} onChange={(event) => set({ religion: event.target.value })} placeholder="Religión (lo que dijo)" className="h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="door-religion" />
            <input value={visit.origin} onChange={(event) => set({ origin: event.target.value })} placeholder="Origen (lo que dijo)" className="h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="door-origin" />
          </div>}
          <p className="text-xs text-slate-500">Nunca se deduce por apariencia; solo lo que la persona compartió.</p>
        </div>}
      </>}
      {visit.opened === false && <textarea value={visit.note} onChange={(event) => set({ note: event.target.value })} rows={1} placeholder="Nota (opcional)" className="w-full rounded-lg border border-[#D9D4C7] p-3 text-base" data-testid="door-note" />}

      {/* Barra compacta (una fila, 48 px) pegada al fondo de lo visible: no tapa las opciones. */}
      <div className={`sticky-actions -mx-4 grid gap-2 px-4 ${household ? 'grid-cols-1' : 'grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]'}`} data-testid="door-actions">
        {!household && <button type="button" onClick={() => save(true)} disabled={saving} aria-label="Guardar y agregar otra vivienda" className="inline-flex min-h-12 items-center justify-center gap-1.5 rounded-xl bg-[#132443] px-2 text-[15px] font-semibold leading-tight text-white disabled:opacity-60" data-testid="door-save-next">{saving ? <Loader2 className="h-5 w-5 shrink-0 animate-spin" /> : <Plus className="h-5 w-5 shrink-0" />}<span className="sm:hidden">Guardar y otra</span><span className="hidden sm:inline">Guardar y agregar otra vivienda</span></button>}
        <button type="button" onClick={() => save(false)} disabled={saving} className={`inline-flex min-h-12 items-center justify-center gap-1.5 rounded-xl px-2 text-[15px] font-semibold disabled:opacity-60 ${household ? 'bg-[#132443] text-white' : 'border-2 border-[#132443] bg-white text-[#132443]'}`} data-testid="door-save">{saving ? <Loader2 className="h-5 w-5 shrink-0 animate-spin" /> : <Save className="h-5 w-5 shrink-0" />}Guardar</button>
      </div>
      <PersonMatchDialog match={match} busy={false} onPick={(personId) => startConsolidation(match.visitId, { ...match.action, person_id: personId })} onConfirmDistinct={(reason) => startConsolidation(match.visitId, { ...match.action, confirm_distinct_person: true, distinct_reason: reason })} onClose={() => setMatch(null)} />
    </section>
  );
}
