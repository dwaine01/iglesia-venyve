import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { Check, HeartHandshake, Lock, Users, X } from 'lucide-react';

import { enqueue, flush, pendingCount } from '../lib/kioskQueue';
import { rememberedToken, useAppManifest } from '../lib/appManifest';

/* Quiosco de registro de visitantes (/quiosco/<enlace>). Un único enlace para
 * todas las tabletas: sin código, sin sesión. El enlace solo permite CREAR
 * registros. Cada tableta se nombra sola («Tableta 3F9A») para trazabilidad.
 * Nada del visitante se guarda en el navegador salvo, si falla el internet, en la
 * cola cifrada hasta enviarse. Reinicio por inactividad. */

const API = process.env.REACT_APP_BACKEND_URL;
const NAME_KEY = 'vv_tablet_name';
// Tiempos de espera por defecto (segundos); la administración los cambia y llegan en la configuración.
const DEFAULT_TIMEOUTS = { form_warn_seconds: 240, form_reset_seconds: 300, start_reset_seconds: 600, confirm_reset_seconds: 60 };
const C = { navy: '#14213D', ink: '#101D36', gold: '#C8A951', goldDark: '#8A6A1F', goldSoft: '#F6EEDA', bg: '#F7F5EF', line: '#DDD6C6', muted: '#475467' };

const CONTACT = [['call', 'Llamada'], ['text', 'Mensaje de texto'], ['whatsapp', 'WhatsApp'], ['email', 'Correo electrónico']];
const VISIT_MODES = [['nearby', 'Vivo cerca de la iglesia'], ['other_city', 'Vengo de otra ciudad'], ['passing', 'Estoy de paso'], ['new_in_area', 'Soy nuevo en el área']];
const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
/** Teléfono de EE. UU. con guiones mientras se escribe: 555-123-4567 (se guarda solo con dígitos). */
export const phoneDigits = (value) => (value || '').replace(/\D/g, '').replace(/^1(?=\d{10})/, '').slice(0, 10);
export const formatPhone = (value) => {
  const digits = phoneDigits(value);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
};
const HEARD = ['Invitación de alguien', 'Redes sociales', 'Internet', 'Pasé por la iglesia', 'Evento o campaña Ven y Come', 'Otro'];
const REQUESTS = [['prayer_me', 'Quiero oración por mí'], ['prayer_family', 'Quiero oración por mi familia'], ['call_prayer', 'Llámenme para orar'], ['visit', 'Me gustaría que me visiten'],
  ['info', 'Quiero saber más de esta iglesia'], ['counseling_personal', 'Consejería personal'], ['counseling_marriage', 'Consejería matrimonial'], ['counseling_family', 'Consejería familiar'],
  ['support_child', 'Apoyo para un hijo o familiar'], ['membership', 'Me gustaría pertenecer a la iglesia'], ['serve', 'Quiero servir en la iglesia'], ['home_service', 'Me gustaría un culto en mi casa'],
  ['other_help', 'Otra ayuda'], ['no_followup', 'Prefiero no recibir seguimiento por ahora']];
const CHRISTIAN = [['yes', 'Sí'], ['on_way', 'Estoy en camino'], ['not_yet', 'No todavía']];
const ACCEPT = [['today', 'Hoy'], ['another_day', 'Otro día']];
const MARITAL = [['single', 'Soltero o soltera'], ['married', 'Casado o casada'], ['other', 'Otro']];
const PRAYER = ['prayer_me', 'prayer_family', 'call_prayer'];
// Formulario ÚNICO (los 3 papeles + el digital), un tema por paso. «Cuéntanos más» solo aparece
// si eligió oración, consejería u otra ayuda (así ninguna pantalla necesita desplazarse).
const needsNotes = (requests) => requests.some((item) => PRAYER.includes(item) || item.startsWith('counseling') || ['support_child', 'other_help'].includes(item));
const stepOrder = (form) => ['nombre', 'contacto', 'vives', 'visita', 'fe', 'familia', 'servir', ...(needsNotes(form.requests) ? ['notas'] : []), 'apoyo', 'cierre'];

const emptyForm = () => ({
  idempotency_key: (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).replace(/[^a-zA-Z0-9-]/g, '') + Date.now().toString(36),
  started_at: new Date().toISOString(), privacy_accepted: false, first_name: '', last_name: '', preferred_name: '', phone: '', email: '', contact_methods: [], city: '', address: '',
  zip_code: '', birth_date: '', first_visit: null, invited_by: '', visit_mode: null, how_heard: '',
  faith_christian: null, accept_jesus: null, reconcile: false, faith_info: false, other_church: null, other_church_name: '', other_church_pastor: '',
  marital_status: null, spouse_name: '', has_children: null, children: [], companions: '', kids_ministry: false, requests: [], giving_info: false,
  prayer_request: '', counseling_note: '', needs_note: '', consent_followup: null, website: '',
});

// Nombre automático de esta tableta, solo para saber de cuál vino cada registro.
function tabletName() {
  try {
    const saved = localStorage.getItem(NAME_KEY);
    if (saved && /^Tableta [0-9A-F]{4}$/.test(saved)) return saved;
    const value = `Tableta ${Array.from(crypto.getRandomValues(new Uint8Array(2))).map((byte) => byte.toString(16).padStart(2, '0')).join('').toUpperCase()}`;
    localStorage.setItem(NAME_KEY, value);
    return value;
  } catch { return 'Tableta sin nombre'; }
}

/** Frases del texto editable: una por línea; si viene en un solo párrafo, por oraciones. */
export function phrases(text) {
  const lines = (text || '').split(/\n+/).map((line) => line.trim()).filter(Boolean);
  if (lines.length > 1) return lines;
  // Sin «lookbehind» en la expresión: las tabletas con Safari antiguo no lo entienden.
  return (lines[0] || '').replace(/([.!?])\s+(?=[¡¿A-ZÁÉÍÓÚÑ])/g, '$1\n').split('\n').map((line) => line.trim()).filter(Boolean);
}

// ---------------------------------------------------------------- piezas grandes (tableta)
const Big = ({ children, onClick, kind = 'primary', disabled, testId, type = 'button' }) => (
  <button type={type} onClick={onClick} disabled={disabled} data-testid={testId}
    style={{ minHeight: 64, padding: '0 28px', borderRadius: 16, fontSize: 22, fontWeight: 700, border: kind === 'primary' ? 'none' : `2px solid ${C.line}`,
      background: kind === 'primary' ? C.navy : '#fff', color: kind === 'primary' ? '#fff' : C.ink, opacity: disabled ? 0.45 : 1, cursor: disabled ? 'default' : 'pointer' }}>{children}</button>
);
const Label = ({ children }) => <span style={{ display: 'block', fontSize: 21, fontWeight: 700, color: C.ink, marginBottom: 8 }}>{children}</span>;
const inputStyle = { width: '100%', minHeight: 62, borderRadius: 14, border: `2px solid ${C.line}`, padding: '0 16px', fontSize: 22, background: '#fff', color: C.ink, boxSizing: 'border-box' };
function Field({ label, value, onChange, type = 'text', placeholder, testId, autoComplete = 'off' }) {
  return <label style={{ display: 'block' }}><Label>{label}</Label><input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} autoComplete={autoComplete} style={inputStyle} data-testid={testId} /></label>;
}
function Area({ label, value, onChange, testId, hint }) {
  return <label style={{ display: 'block' }}><Label>{label}</Label>{hint && <span style={{ display: 'block', fontSize: 18, color: C.muted, marginBottom: 8 }}>{hint}</span>}<textarea value={value} onChange={(event) => onChange(event.target.value)} rows={3} style={{ ...inputStyle, minHeight: 110, padding: 14 }} data-testid={testId} /></label>;
}
function Chips({ options, value, onChange, multiple, testId }) {
  const selected = (key) => (multiple ? value.includes(key) : value === key);
  const toggle = (key) => (multiple ? onChange(selected(key) ? value.filter((item) => item !== key) : [...value, key]) : onChange(selected(key) ? null : key));
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }} data-testid={testId}>
      {options.map(([key, label]) => <button key={String(key)} type="button" onClick={() => toggle(key)} aria-pressed={selected(key)}
        style={{ minHeight: 60, padding: '0 22px', borderRadius: 999, fontSize: 21, fontWeight: 600, border: `2px solid ${selected(key) ? C.navy : C.line}`, background: selected(key) ? C.navy : '#fff', color: selected(key) ? '#fff' : C.ink }}>{label}</button>)}
    </div>
  );
}
// Casillas grandes (se pueden marcar varias).
function CheckChips({ options, value, onChange, testId }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }} data-testid={testId}>
      {options.map(([key, label]) => {
        const on = value.includes(key);
        return (
          <button key={key} type="button" role="checkbox" aria-checked={on} onClick={() => onChange(on ? value.filter((item) => item !== key) : [...value, key])} data-testid={`${testId}-${key}`}
            style={{ minHeight: 62, padding: '0 22px 0 16px', borderRadius: 16, fontSize: 21, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 12, border: `2px solid ${on ? C.navy : C.line}`, background: on ? '#EEF2FA' : '#fff', color: C.ink }}>
            <span aria-hidden style={{ width: 30, height: 30, borderRadius: 8, border: `2px solid ${on ? C.navy : '#9AA3B2'}`, background: on ? C.navy : '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{on && <Check size={22} color="#fff" strokeWidth={3} />}</span>
            {label}
          </button>
        );
      })}
    </div>
  );
}
// Cumpleaños con tres listas grandes (día, mes, año): más fácil que un calendario en tableta.
function BirthdayPicker({ value, onChange }) {
  const [year, month, day] = (value || '--').split('-');
  const parts = { year: year || '', month: month || '', day: day || '' };
  const [draft, setDraft] = useState(parts);
  const update = (key, next) => {
    const merged = { ...draft, [key]: next };
    setDraft(merged);
    const max = merged.year && merged.month ? new Date(Number(merged.year), Number(merged.month), 0).getDate() : 31;
    onChange(merged.year && merged.month && merged.day && Number(merged.day) <= max ? `${merged.year}-${merged.month}-${merged.day}` : '');
  };
  const thisYear = new Date().getFullYear();
  const select = { ...inputStyle, appearance: 'auto', cursor: 'pointer' };
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr 1.2fr', gap: 12 }} data-testid="kiosk-birth">
      <select value={draft.day} onChange={(event) => update('day', event.target.value)} aria-label="Día" style={select} data-testid="kiosk-birth-day"><option value="">Día</option>{Array.from({ length: 31 }, (_, index) => String(index + 1).padStart(2, '0')).map((item) => <option key={item} value={item}>{Number(item)}</option>)}</select>
      <select value={draft.month} onChange={(event) => update('month', event.target.value)} aria-label="Mes" style={select} data-testid="kiosk-birth-month"><option value="">Mes</option>{MONTHS.map((name, index) => <option key={name} value={String(index + 1).padStart(2, '0')}>{name}</option>)}</select>
      <select value={draft.year} onChange={(event) => update('year', event.target.value)} aria-label="Año" style={select} data-testid="kiosk-birth-year"><option value="">Año</option>{Array.from({ length: 100 }, (_, index) => String(thisYear - index)).map((item) => <option key={item} value={item}>{item}</option>)}</select>
    </div>
  );
}
const YesNo = ({ value, onChange, testId }) => <Chips options={[[true, 'Sí'], [false, 'No']]} value={value} onChange={onChange} testId={testId} />;
const Accent = () => <span aria-hidden style={{ display: 'block', width: 88, height: 2, background: C.gold, margin: 'clamp(10px, 2vh, 18px) auto' }} />;
// En horizontal los campos van en dos columnas para que todo quepa sin desplazar.
const Section = ({ children, testId }) => <div className="vk-grid" data-testid={testId}>{children}</div>;
const Wide = ({ children }) => <div className="vk-wide">{children}</div>;
const LOGO = { src: '/logo-iglesia.png', srcSet: '/logo-iglesia.png 1x, /logo-iglesia@2x.png 2x', alt: 'Primera Iglesia del Nazareno · Casa de oración Ven y Ve' };
const KIOSK_CSS = `
  .vk-grid { display: grid; gap: clamp(12px, 2vh, 22px); align-content: start; }
  .vk-kids { display: grid; gap: 8px; }
  @media (min-width: 700px) { .vk-kids { grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 24px; } }
  @media (orientation: landscape) and (min-width: 900px) {
    .vk-grid { grid-template-columns: 1fr 1fr; column-gap: 36px; }
    .vk-wide { grid-column: 1 / -1; }
  }
`;

export default function KioskPage() {
  const params = useParams();
  // El enlace se guarda en la tableta: el acceso directo «Registro» abre /quiosco sin el enlace.
  const [token] = useState(() => rememberedToken('vv_kiosk_link', params.token));
  useAppManifest('/manifest-registro.json', 'Registro');
  const [device] = useState(tabletName);
  const [config, setConfig] = useState(null);
  const [linkError, setLinkError] = useState('');
  const [error, setError] = useState('');
  const [step, setStep] = useState(-1);  // -1 = inicio
  const [form, setForm] = useState(emptyForm);
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [idle, setIdle] = useState(0);
  const [pending, setPending] = useState(0);
  const lastTouch = useRef(Date.now());
  const times = useMemo(() => ({ ...DEFAULT_TIMEOUTS, ...(config?.timeouts || {}) }), [config]);
  const headers = { 'X-Link-Token': token || '', 'X-Tablet-Name': device };
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const reset = useCallback(() => { setForm(emptyForm()); setStep(-1); setResult(null); setError(''); setSaving(false); window.scrollTo(0, 0); }, []);

  // Textos y servicio de hoy. Un enlace viejo o equivocado muestra cómo pedir el nuevo.
  const loadConfig = useCallback(() => {
    if (!token) { setLinkError('Abra el enlace de tabletas que aparece en Registro de visitantes › Enlaces.'); return; }
    axios.get(`${API}/api/kiosk/config`, { headers: { 'X-Link-Token': token, 'X-Tablet-Name': device } }).then((response) => { setConfig(response.data); setLinkError(''); })
      .catch((requestError) => { if (requestError?.response?.status === 401) setLinkError(requestError.response.data?.detail || 'Este enlace ya no funciona.'); });
  }, [token, device]);
  useEffect(() => { loadConfig(); const timer = setInterval(loadConfig, 10 * 60 * 1000); return () => clearInterval(timer); }, [loadConfig]);

  // Cola sin internet: se reenvía con la misma clave de idempotencia. Solo un dato
  // inválido (400/422) se descarta; sin internet, límite o enlace viejo, se reintenta.
  const send = useCallback(async (payload) => {
    try {
      return (await axios.post(`${API}/api/kiosk/registrations`, payload, { headers, timeout: 20000 })).data;
    } catch (requestError) {
      const status = requestError?.response?.status;
      if (status === 400 || status === 422) { const permanent = new Error(requestError.response.data?.detail || 'Revise los datos'); permanent.permanent = true; throw permanent; }
      throw requestError;
    }
  }, [token, device]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!token) return undefined;
    const tick = async () => { await flush(send); setPending(await pendingCount()); };
    tick(); const timer = setInterval(tick, 15000); window.addEventListener('online', tick);
    return () => { clearInterval(timer); window.removeEventListener('online', tick); };
  }, [token, send]);

  // Cada paso empieza arriba (el centro es lo único que se desplaza).
  useEffect(() => { document.querySelector('[data-testid=kiosk-main]')?.scrollTo(0, 0); }, [step, result]);

  // Sin desplazamiento ni rebote del documento mientras está el quiosco.
  useEffect(() => {
    const root = document.documentElement; const body = document.body;
    const before = [root.style.overflow, root.style.overscrollBehavior, body.style.overflow, body.style.overscrollBehavior, root.style.height, body.style.height];
    root.style.overflow = 'hidden'; root.style.overscrollBehavior = 'none'; body.style.overflow = 'hidden'; body.style.overscrollBehavior = 'none'; root.style.height = '100%'; body.style.height = '100%';
    return () => { [root.style.overflow, root.style.overscrollBehavior, body.style.overflow, body.style.overscrollBehavior, root.style.height, body.style.height] = before; };
  }, []);

  // Modo quiosco: el botón «atrás» no sale de la página.
  useEffect(() => {
    window.history.pushState(null, '', window.location.href);
    const stay = () => window.history.pushState(null, '', window.location.href);
    window.addEventListener('popstate', stay);
    return () => window.removeEventListener('popstate', stay);
  }, []);
  // Inactividad: aviso a los 60 s y reinicio a los 75 s (borra todo lo escrito).
  useEffect(() => {
    const touch = () => { lastTouch.current = Date.now(); setIdle(0); };
    // Cualquier toque, tecla o cambio en un campo reinicia el contador: nunca se borra mientras escribe.
    ['pointerdown', 'keydown', 'touchstart', 'input', 'change', 'scroll'].forEach((name) => window.addEventListener(name, touch, { passive: true, capture: true }));
    const timer = setInterval(() => {
      const seconds = Math.floor((Date.now() - lastTouch.current) / 1000);
      if (result && seconds >= times.confirm_reset_seconds) { reset(); lastTouch.current = Date.now(); return; }
      if (step < 0 && !result && seconds >= times.start_reset_seconds) { reset(); loadConfig(); lastTouch.current = Date.now(); return; }
      if (step >= 0 && !result) { if (seconds >= times.form_reset_seconds) { reset(); lastTouch.current = Date.now(); } else setIdle(seconds); }
    }, 1000);
    return () => { clearInterval(timer); ['pointerdown', 'keydown', 'touchstart', 'input', 'change', 'scroll'].forEach((name) => window.removeEventListener(name, touch, { capture: true })); };
  }, [step, result, reset, times, loadConfig]);

  // Al continuar después del nombre: borrador en el servidor para que el nombre aparezca YA en la
  // bienvenida de la pastora. No detiene a la persona (si falla, el registro final lo crea igual).
  // Lo que se envía (en cada paso al borrador y al terminar). Al continuar después del nombre la persona
  // acepta el aviso corto (lo ve completo al final).
  const buildPayload = () => {
    const payload = {
      ...form, privacy_accepted: true, privacy_version: config.texts.privacy_version, birth_date: form.birth_date || null, phone: phoneDigits(form.phone),
      invited: form.invited_by.trim() ? true : null, children: form.has_children ? form.children.filter((item) => item.name.trim()).map((item) => ({ name: item.name.trim(), age: item.age === '' || item.age == null ? null : Number(item.age) })) : [],
      ...(form.other_church ? {} : { other_church_name: '', other_church_pastor: '' }), ...(form.marital_status === 'married' ? {} : { spouse_name: '' }),
    };
    Object.keys(payload).forEach((key) => { if (payload[key] === '') payload[key] = null; });
    return payload;
  };
  // En cada «Siguiente» se guarda el borrador: el nombre aparece YA en la bienvenida y nada se pierde si
  // la persona abandona. No detiene a la persona (si falla, el registro final lo guarda igual).
  const saveDraft = () => {
    if (!config || !form.first_name.trim() || !form.last_name.trim()) return;
    axios.post(`${API}/api/kiosk/registrations/draft`, buildPayload(), { headers, timeout: 8000 }).catch(() => {});
  };

  const submit = async () => {
    setSaving(true); setError('');
    const payload = buildPayload();
    try {
      const data = await send(payload);
      setResult({ ...data, offline: false });
    } catch (requestError) {
      if (requestError?.permanent) { setError(requestError.message); setSaving(false); return; }
      await enqueue(payload); setPending(await pendingCount());
      setResult({ offline: true, greeting_name: form.preferred_name || form.first_name, confirmation: config.texts.confirmation });
    }
    setSaving(false); lastTouch.current = Date.now();
  };

  const order = stepOrder(form);
  const stepKey = order[Math.min(step, order.length - 1)];
  // Obligatorio: nombre y apellido, y un medio de contacto solo si aceptó el seguimiento.
  const missingContact = form.consent_followup === true && !phoneDigits(form.phone) && !form.email.trim();
  const canNext = () => (stepKey === 'nombre' ? form.first_name.trim() && form.last_name.trim() : true);
  const shell = (children, footer = null, hideLogo = false) => (
    // Pantalla fija de app: encabezado y botones nunca se mueven; solo el centro se desplaza si de verdad no cabe.
    // Alto = área visible (visualViewport), así el teclado no empuja el encabezado fuera de vista.
    <div style={{ position: 'fixed', left: 0, right: 0, top: 'var(--vv-top, 0px)', height: 'var(--vvh, 100dvh)', overflow: 'hidden', overscrollBehavior: 'none', touchAction: 'manipulation',
      background: C.bg, color: C.ink, fontFamily: 'Inter, system-ui, sans-serif', display: 'flex', flexDirection: 'column', userSelect: 'none' }} data-testid="kiosk-page" onContextMenu={(event) => event.preventDefault()}>
      <style>{KIOSK_CSS}</style>
      {/* Barra clara: el logo (letras verdes y azules) se ve nítido; en la bienvenida no se repite. */}
      <header style={{ flex: '0 0 auto', background: '#fff', borderBottom: `2px solid ${C.gold}`, padding: '8px 24px', minHeight: 64, boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        {!hideLogo ? <img {...LOGO} style={{ height: 48, width: 'auto' }} data-testid="kiosk-header-logo" /> : <span />}
        {config && <span style={{ fontSize: 19, color: C.muted, textAlign: 'right' }}>{config.service.label}{pending ? ` · ${pending} registro(s) esperando internet` : ''}</span>}
      </header>
      <main className="vk-main" data-testid="kiosk-main" style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', overscrollBehavior: 'contain', touchAction: 'pan-y', WebkitOverflowScrolling: 'touch' }}>
        <div style={{ width: '100%', maxWidth: hideLogo || result ? 1040 : 1120, minHeight: '100%', margin: '0 auto', padding: 'clamp(10px, 2.4vh, 28px) 24px 20px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column' }}>{children}</div>
      </main>
      {footer && <footer style={{ flex: '0 0 auto', background: '#fff', borderTop: `2px solid ${C.line}`, padding: 16, display: 'flex', justifyContent: 'space-between', gap: 12 }}>{footer}</footer>}
      {idle >= times.form_warn_seconds && step >= 0 && !result && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(20,33,61,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }} data-testid="kiosk-idle">
          <div style={{ background: '#fff', borderRadius: 24, padding: 32, maxWidth: 560, textAlign: 'center' }}>
            <p style={{ fontSize: 30, fontWeight: 800, margin: 0 }}>¿Sigues ahí?</p>
            <p style={{ fontSize: 21, color: C.muted }}>Por tu privacidad, el registro se borrará en {Math.max(0, times.form_reset_seconds - idle)} segundos.</p>
            <button type="button" onClick={() => { lastTouch.current = Date.now(); setIdle(0); }} data-testid="kiosk-continue"
              style={{ minHeight: 84, width: '100%', borderRadius: 20, fontSize: 30, fontWeight: 800, border: 'none', background: C.gold, color: C.navy }}>Continuar</button>
          </div>
        </div>
      )}
    </div>
  );

  if (linkError) {
    return shell(
      <div style={{ textAlign: 'center', marginTop: 60 }} data-testid="kiosk-link-error">
        <p style={{ fontSize: 32, fontWeight: 800, margin: 0, fontFamily: 'Spectral, Georgia, serif' }}>Esta tableta necesita el enlace nuevo</p>
        <p style={{ fontSize: 22, color: C.muted, marginTop: 16 }}>{linkError}</p>
      </div>,
    );
  }
  if (!config) return shell(<p style={{ fontSize: 22, marginTop: 40, textAlign: 'center' }}>Preparando el registro…</p>);

  // ---------------------------------------------------------------- confirmación
  if (result) {
    const extra = phrases(result.confirmation).filter((line) => !/^¡?gracias/i.test(line));
    return shell(
      <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1 }} data-testid="kiosk-confirmation">
        <p style={{ fontSize: 'clamp(34px, min(5.4vw, 6.4vh), 50px)', fontWeight: 700, margin: 0, fontFamily: 'Spectral, Georgia, serif', lineHeight: 1.15, color: C.navy }}>¡Gracias, {result.greeting_name}!</p>
        <Accent />
        {result.offline
          ? <p style={{ fontSize: 24, margin: '20px auto', maxWidth: 680, color: C.goldDark, fontWeight: 700 }} data-testid="kiosk-offline">Tu registro quedó guardado en esta tableta y se enviará apenas vuelva el internet. Un servidor te dará tu número.</p>
          : <>
              <p style={{ fontSize: 22, margin: 0, color: C.muted }}>Tu número de registro</p>
              <p style={{ fontSize: 'clamp(40px, min(10vw, 9vh), 76px)', whiteSpace: 'nowrap', fontWeight: 800, letterSpacing: '0.04em', margin: '4px 0 clamp(14px, 3vh, 28px)', color: C.navy }} data-testid="kiosk-number">{result.visitor_number}</p>
            </>}
        <div style={{ display: 'grid', gap: 8, margin: '0 auto clamp(18px, 3vh, 30px)', maxWidth: 720 }}>{extra.map((line) => <p key={line} style={{ fontSize: 'clamp(21px, 3.2vh, 25px)', lineHeight: 1.35, margin: 0 }}>{line}</p>)}</div>
        <Big onClick={reset} testId="kiosk-done">Listo</Big>
      </div>,
    );
  }

  // ---------------------------------------------------------------- inicio
  if (step < 0) {
    // Composición sin cajas: logo, título y subtítulo arriba; la frase PRINCIPAL (3.ª
    // línea), la más grande, entera al centro con una línea dorada fina; las demás,
    // secundarias, justo encima del botón.
    const [title, subtitle, main, ...closing] = phrases(config.texts.welcome);
    return shell(
      <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1 }} data-testid="kiosk-start">
        <img {...LOGO} style={{ width: 'min(420px, 62vw)', maxHeight: '22vh', objectFit: 'contain' }} data-testid="kiosk-logo" />
        <h1 style={{ fontSize: 'clamp(28px, min(4.4vw, 5vh), 42px)', margin: 'clamp(12px, 2.4vh, 26px) 0 0', fontFamily: 'Spectral, Georgia, serif', fontWeight: 600, lineHeight: 1.12, color: C.navy }} data-testid="kiosk-title">{title}</h1>
        {subtitle && <p style={{ fontSize: 'clamp(21px, min(3vw, 3.6vh), 28px)', margin: '6px 0 0', color: C.goldDark, fontWeight: 700 }} data-testid="kiosk-subtitle">{subtitle}</p>}
        {main && (
          <div style={{ width: '100%', maxWidth: 960, margin: 'clamp(16px, 3vh, 34px) 0 0' }} data-testid="kiosk-main-phrase">
            <span aria-hidden style={{ display: 'block', width: 120, height: 2, background: C.gold, margin: '0 auto clamp(12px, 2.2vh, 22px)' }} />
            <p style={{ margin: 0, fontFamily: 'Spectral, Georgia, serif', fontWeight: 700, fontSize: 'clamp(30px, min(5.2vw, 6vh), 54px)', lineHeight: 1.2, color: C.navy, textWrap: 'balance', overflowWrap: 'break-word' }}>{main}</p>
          </div>
        )}
        {closing.map((line) => <p key={line} style={{ margin: 'clamp(14px, 2.6vh, 28px) 0 0', fontSize: 'clamp(20px, min(2.6vw, 3.2vh), 24px)', lineHeight: 1.35, color: C.muted }} data-testid="kiosk-closing">{line}</p>)}
        <button type="button" onClick={() => { setForm(emptyForm()); setStep(0); lastTouch.current = Date.now(); }} data-testid="kiosk-begin"
          style={{ marginTop: 'clamp(14px, 2.6vh, 28px)', minHeight: 'clamp(72px, 10vh, 100px)', padding: '0 clamp(28px, 7vw, 64px)', whiteSpace: 'nowrap', borderRadius: 28, fontSize: 'clamp(28px, 4.2vh, 34px)', fontWeight: 800, background: C.gold, color: C.navy, border: 'none', boxShadow: '0 8px 24px rgba(20,33,61,0.22)' }}>Iniciar registro</button>
        <p style={{ margin: 'clamp(8px, 1.6vh, 16px) 0 0', fontSize: 15, color: C.muted }}>{device}</p>
      </div>, null, true,
    );
  }

  // ---------------------------------------------------------------- pasos
  const footer = (
    <>
      <Big kind="secondary" onClick={() => (step === 0 ? reset() : setStep(step - 1))} testId="kiosk-back">{step === 0 ? 'Cancelar' : 'Atrás'}</Big>
      {step < order.length - 1
        ? <Big onClick={() => { saveDraft(); setStep(step + 1); }} disabled={!canNext()} testId="kiosk-next">Siguiente</Big>
        : <Big onClick={submit} disabled={saving || missingContact} testId="kiosk-submit">{saving ? 'Guardando…' : 'Terminar registro'}</Big>}
    </>
  );
  const title = (text, sub) => (
    <div className="vk-wide" style={{ marginBottom: 4 }}>
      <p style={{ fontSize: 18, color: C.goldDark, fontWeight: 700, margin: 0 }}>Paso {step + 1} de {order.length}</p>
      <h2 style={{ fontSize: 'clamp(28px, 4.4vh, 36px)', margin: '4px 0 0', fontFamily: 'Spectral, Georgia, serif', fontWeight: 600, lineHeight: 1.15, color: C.navy }}>{text}</h2>
      {sub && <p style={{ fontSize: 20, color: C.muted, margin: '6px 0 0' }}>{sub}</p>}
    </div>
  );
  const setChild = (index, key, value) => set('children', form.children.map((item, position) => (position === index ? { ...item, [key]: value } : item)));
  const body = {
    nombre: <Section testId="kiosk-step-nombre">{title('¿Cómo te llamas?')}
      <Field label="Nombre" value={form.first_name} onChange={(value) => set('first_name', value)} testId="kiosk-first-name" />
      <Field label="Apellidos" value={form.last_name} onChange={(value) => set('last_name', value)} testId="kiosk-last-name" />
      <Field label="¿Cómo te gusta que te llamen?" value={form.preferred_name} onChange={(value) => set('preferred_name', value)} placeholder="Ej.: Toño" testId="kiosk-preferred" />
      <Wide><p style={{ margin: 0, fontSize: 18, color: C.muted, display: 'flex', alignItems: 'center', gap: 10 }}><Lock size={20} color={C.goldDark} aria-hidden />Cuidamos tus datos: solo los usamos para darte la bienvenida y servirte.</p></Wide>
      {/* Campo trampa: invisible para personas; los robots lo llenan. */}
      <input type="text" name="website" value={form.website} onChange={(event) => set('website', event.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true"
        style={{ position: 'absolute', left: '-10000px', width: 1, height: 1, opacity: 0 }} data-testid="kiosk-website" /></Section>,
    contacto: <Section testId="kiosk-step-contacto">{title('¿Cómo te contactamos?')}
      <label style={{ display: 'block' }}><Label>Teléfono</Label><input type="tel" inputMode="numeric" autoComplete="off" value={formatPhone(form.phone)} onChange={(event) => set('phone', phoneDigits(event.target.value))} placeholder="555-123-4567" style={inputStyle} data-testid="kiosk-phone" /></label>
      <Field label="Correo electrónico" type="email" value={form.email} onChange={(value) => set('email', value)} testId="kiosk-email" />
      <Wide><Label>¿Cómo prefieres que te contactemos? Puedes elegir varias.</Label><CheckChips options={CONTACT} value={form.contact_methods} onChange={(value) => set('contact_methods', value)} testId="kiosk-contact-methods" /></Wide></Section>,
    vives: <Section testId="kiosk-step-vives">{title('¿Dónde vives?')}
      <Wide><Field label="Calle y número" value={form.address} onChange={(value) => set('address', value)} testId="kiosk-address" /></Wide>
      <Field label="Ciudad" value={form.city} onChange={(value) => set('city', value)} testId="kiosk-city" />
      <label style={{ display: 'block' }}><Label>Código postal</Label><input inputMode="numeric" autoComplete="off" value={form.zip_code} onChange={(event) => set('zip_code', event.target.value.replace(/[^0-9-]/g, '').slice(0, 10))} style={inputStyle} data-testid="kiosk-zip" /></label>
      <Wide><Label>¿Cómo nos visitas hoy?</Label><Chips options={VISIT_MODES} value={form.visit_mode} onChange={(value) => set('visit_mode', value)} testId="kiosk-visit-mode" /></Wide>
      <Wide><Label>Para tenerte presente el día de tu cumpleaños</Label><div style={{ maxWidth: 720 }}><BirthdayPicker value={form.birth_date} onChange={(value) => set('birth_date', value)} /></div></Wide></Section>,
    visita: <Section testId="kiosk-step-visita">{title('Tu visita')}
      <div><Label>¿Es tu primera vez con nosotros?</Label><Chips options={[[true, 'Primera vez'], [false, 'Ya los había visitado']]} value={form.first_visit} onChange={(value) => set('first_visit', value)} testId="kiosk-first-visit" /></div>
      <Field label="¿Quién te invitó?" value={form.invited_by} onChange={(value) => set('invited_by', value)} placeholder="Nombre de quien te invitó" testId="kiosk-invited-by" />
      <Wide><Label>¿Cómo te enteraste de nosotros?</Label><Chips options={HEARD.map((item) => [item, item])} value={form.how_heard || null} onChange={(value) => set('how_heard', value || '')} testId="kiosk-heard" /></Wide></Section>,
    fe: <Section testId="kiosk-step-fe">{title('Tu fe')}
      <div><Label>¿Eres cristiano o cristiana?</Label><Chips options={CHRISTIAN} value={form.faith_christian} onChange={(value) => set('faith_christian', value)} testId="kiosk-christian" /></div>
      <div><Label>Quiero aceptar a Jesús como mi Salvador</Label><Chips options={ACCEPT} value={form.accept_jesus} onChange={(value) => set('accept_jesus', value)} testId="kiosk-accept-jesus" /></div>
      <Wide><CheckChips options={[['reconcile', 'Deseo reconciliarme con Dios'], ['faith_info', 'Quiero informarme de cómo ser cristiano']]} value={['reconcile', 'faith_info'].filter((key) => form[key])}
        onChange={(value) => setForm((current) => ({ ...current, reconcile: value.includes('reconcile'), faith_info: value.includes('faith_info') }))} testId="kiosk-faith" /></Wide>
      <Wide><Label>¿Asistes a otra iglesia?</Label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <YesNo value={form.other_church} onChange={(value) => set('other_church', value)} testId="kiosk-other-church" />
          {form.other_church && <>
            <input value={form.other_church_name} onChange={(event) => set('other_church_name', event.target.value)} placeholder="Nombre de la iglesia" aria-label="Nombre de la iglesia" autoComplete="off" style={{ ...inputStyle, flex: '1 1 220px', width: 'auto', minWidth: 0 }} data-testid="kiosk-other-church-name" />
            <input value={form.other_church_pastor} onChange={(event) => set('other_church_pastor', event.target.value)} placeholder="Nombre del pastor" aria-label="Nombre del pastor" autoComplete="off" style={{ ...inputStyle, flex: '1 1 220px', width: 'auto', minWidth: 0 }} data-testid="kiosk-other-church-pastor" />
          </>}
        </div></Wide></Section>,
    familia: <Section testId="kiosk-step-familia">{title('Tu familia')}
      <Wide><Label>Estado civil</Label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <Chips options={MARITAL} value={form.marital_status} onChange={(value) => set('marital_status', value)} testId="kiosk-marital" />
          {form.marital_status === 'married' && <input value={form.spouse_name} onChange={(event) => set('spouse_name', event.target.value)} placeholder="Nombre de tu esposo o esposa" aria-label="Nombre de tu esposo o esposa" autoComplete="off" style={{ ...inputStyle, flex: '1 1 260px', width: 'auto', minWidth: 0 }} data-testid="kiosk-spouse" />}
        </div></Wide>
      <div><Label>¿Tienes hijos?</Label><YesNo value={form.has_children} onChange={(value) => setForm((current) => ({ ...current, has_children: value, children: value && !current.children.length ? [{ name: '', age: '' }] : current.children }))} testId="kiosk-has-children" /></div>
      <Field label="¿Quién te acompaña hoy?" value={form.companions} onChange={(value) => set('companions', value)} placeholder="Ej.: mi esposa y mis dos hijos" testId="kiosk-companions" />
      {form.has_children && <Wide><div className="vk-kids" data-testid="kiosk-children">
        {form.children.map((child, index) => (
          <div key={index} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input value={child.name} onChange={(event) => setChild(index, 'name', event.target.value)} placeholder={`Nombre del hijo o hija ${index + 1}`} aria-label={`Nombre del hijo o hija ${index + 1}`} autoComplete="off" style={{ ...inputStyle, minHeight: 56, flex: '1 1 auto', width: 'auto', minWidth: 0 }} data-testid={`kiosk-child-name-${index}`} />
            <input value={child.age} onChange={(event) => setChild(index, 'age', event.target.value.replace(/\D/g, '').slice(0, 2))} inputMode="numeric" placeholder="Edad" aria-label={`Edad del hijo o hija ${index + 1}`} style={{ ...inputStyle, minHeight: 56, flex: '0 0 96px', width: 96 }} data-testid={`kiosk-child-age-${index}`} />
            <button type="button" onClick={() => set('children', form.children.filter((_, position) => position !== index))} aria-label={`Quitar al hijo o hija ${index + 1}`} title="Quitar"
              style={{ flex: '0 0 56px', height: 56, borderRadius: 14, border: `2px solid ${C.line}`, background: '#fff', color: C.ink, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}><X size={26} aria-hidden /></button>
          </div>
        ))}
      </div></Wide>}
      <Wide><div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        {form.has_children && <Big kind="secondary" onClick={() => set('children', [...form.children, { name: '', age: '' }])} testId="kiosk-child-add">Agregar otro hijo</Big>}
        <CheckChips options={[['kids', 'Deseo que mis hijos participen en el ministerio de niños']]} value={form.kids_ministry ? ['kids'] : []} onChange={(value) => set('kids_ministry', value.includes('kids'))} testId="kiosk-kids-ministry" />
      </div></Wide></Section>,
    servir: <Section testId="kiosk-step-servir">{title('¿Cómo podemos servirte?', 'Puedes elegir varias.')}
      <Wide><CheckChips options={REQUESTS} value={form.requests} onChange={(value) => set('requests', value.includes('no_followup') && !form.requests.includes('no_followup') ? ['no_followup'] : value.filter((item) => item !== 'no_followup' || value.length === 1))} testId="kiosk-requests" /></Wide></Section>,
    notas: <Section testId="kiosk-step-notas">{title('Cuéntanos un poco más', 'Es confidencial.')}
      {form.requests.some((item) => PRAYER.includes(item)) && <Area label="¿Por qué quieres que oremos?" hint="Solo lo verá el equipo de oración." value={form.prayer_request} onChange={(value) => set('prayer_request', value)} testId="kiosk-prayer" />}
      {form.requests.some((item) => item.startsWith('counseling')) && <Area label="Cuéntanos brevemente" hint="Solo lo verá el equipo pastoral." value={form.counseling_note} onChange={(value) => set('counseling_note', value)} testId="kiosk-counseling" />}
      {form.requests.some((item) => ['support_child', 'other_help'].includes(item)) && <Area label="¿Qué otra ayuda necesitas?" hint="Confidencial." value={form.needs_note} onChange={(value) => set('needs_note', value)} testId="kiosk-needs" />}</Section>,
    apoyo: <Section testId="kiosk-step-apoyo">{title('Apoyo')}
      <Wide><CheckChips options={[['giving', 'Quiero información para ofrendar o donar mensualmente']]} value={form.giving_info ? ['giving'] : []} onChange={(value) => set('giving_info', value.includes('giving'))} testId="kiosk-giving" /></Wide>
      <Wide><p style={{ margin: 0, fontSize: 20, color: C.muted }}>No pedimos datos de pago. La encargada de finanzas te dará la información.</p></Wide></Section>,
    cierre: <Section testId="kiosk-step-cierre">{title('¿Podemos comunicarnos contigo para darte seguimiento?')}
      <Wide><YesNo value={form.consent_followup} onChange={(value) => set('consent_followup', value)} testId="kiosk-consent-followup" /></Wide>
      {missingContact && (
        <Wide><div style={{ display: 'grid', gap: 12, justifyItems: 'start' }} data-testid="kiosk-need-contact">
          <p style={{ margin: 0, fontSize: 22, color: C.goldDark, fontWeight: 700 }}>Para darte seguimiento necesitamos tu teléfono o tu correo.</p>
          <Big kind="secondary" onClick={() => setStep(order.indexOf('contacto'))} testId="kiosk-add-contact">Escribir mi teléfono o correo</Big>
        </div></Wide>
      )}
      <Wide><ul style={{ display: 'grid', gap: 'clamp(10px, 2vh, 18px)', margin: '6px 0 0', padding: 0, listStyle: 'none', maxWidth: 860 }} data-testid="kiosk-privacy">
        {phrases(config.texts.privacy).map((line, index) => {
          const Icon = [Lock, Users, HeartHandshake][index % 3];
          return <li key={line} style={{ display: 'flex', alignItems: 'flex-start', gap: 14, fontSize: 'clamp(19px, 2.8vh, 22px)', lineHeight: 1.35, color: C.muted }}><Icon size={26} color={C.goldDark} aria-hidden style={{ flex: '0 0 auto', marginTop: 2 }} /><span>{line}</span></li>;
        })}
      </ul></Wide>
      {error && <p className="vk-wide" style={{ fontSize: 20, color: '#B42318' }}>{error}</p>}</Section>,
  }[stepKey];
  return shell(body, footer);
}
