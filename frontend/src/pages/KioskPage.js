import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { Check, HeartHandshake, Lock, Users, X } from 'lucide-react';

import { enqueue, flush, pendingCount } from '../lib/kioskQueue';
import { adoptShortPath, rememberedToken, useAppManifest } from '../lib/appManifest';
import { KIOSK_TEXT, LANGUAGES } from '../lib/kioskI18n';
import { API_BASE, API_SAME_ORIGIN, DIRECT_BACKEND_URL } from '../lib/apiBase';

/* Quiosco de registro de visitantes (/quiosco/<enlace>). Un único enlace para
 * todas las tabletas: sin código, sin sesión. El enlace solo permite CREAR
 * registros. Cada tableta se nombra sola («Tableta 3F9A») para trazabilidad.
 * Nada del visitante se guarda en el navegador salvo, si falla el internet, en la
 * cola cifrada hasta enviarse. Reinicio por inactividad. */

const API = API_BASE;
const NAME_KEY = 'vv_tablet_name';
// Tiempos de espera por defecto (segundos); la administración los cambia y llegan en la configuración.
const DEFAULT_TIMEOUTS = { form_warn_seconds: 240, form_reset_seconds: 300, start_reset_seconds: 600, confirm_reset_seconds: 60 };
const C = { navy: '#14213D', ink: '#101D36', gold: '#C8A951', goldDark: '#8A6A1F', goldSoft: '#F6EEDA', bg: '#F7F5EF', line: '#DDD6C6', muted: '#475467' };

// Claves que se guardan (las etiquetas salen del diccionario del idioma elegido).
const CONTACT = ['call', 'text', 'whatsapp', 'email'];
const MONTH_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
/** Teléfono de EE. UU. con guiones mientras se escribe: 555-123-4567 (se guarda solo con dígitos). */
export const phoneDigits = (value) => (value || '').replace(/\D/g, '').replace(/^1(?=\d{10})/, '').slice(0, 10);
export const formatPhone = (value) => {
  const digits = phoneDigits(value);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
};
const HEARD = ['Invitación de alguien', 'Redes sociales', 'Internet', 'Pasé por la iglesia', 'Evento o campaña Ven y Come', 'Otro'];
// «¿Cómo podemos servirte?» en grupos con subtítulo; «prefiero no recibir seguimiento» va aparte al final.
const SERVE_GROUPS = [['prayer', ['prayer_me', 'prayer_family', 'call_prayer']], ['visit', ['visit', 'info']],
  ['counseling', ['counseling_personal', 'counseling_marriage', 'counseling_family', 'support_child', 'other_help']], ['serve', ['membership', 'serve', 'home_service']]];
const CHRISTIAN = ['yes', 'on_way', 'not_yet'];
const ACCEPT = ['today', 'another_day'];
const MARITAL = ['single', 'married', 'other'];
const pairs = (keys, labels) => keys.map((key) => [key, labels[key]]);
const PRAYER = ['prayer_me', 'prayer_family', 'call_prayer'];
// Formulario ÚNICO (los 3 papeles + el digital), un tema por paso. «Cuéntanos más» solo aparece
// si eligió oración, consejería u otra ayuda (así ninguna pantalla necesita desplazarse).
const needsNotes = (requests) => requests.some((item) => PRAYER.includes(item) || item.startsWith('counseling') || ['support_child', 'other_help'].includes(item));
const stepOrder = (form) => ['nombre', 'contacto', 'vives', 'visita', 'fe', 'familia', 'servir', ...(needsNotes(form.requests) ? ['notas'] : []), 'apoyo', 'cierre'];

const emptyForm = () => ({
  idempotency_key: (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).replace(/[^a-zA-Z0-9-]/g, '') + Date.now().toString(36),
  started_at: new Date().toISOString(), privacy_accepted: false, first_name: '', last_name: '', preferred_name: '', phone: '', email: '', contact_methods: [], city: '', address: '',
  zip_code: '', birth: { day: '', month: '', year: '' }, sex: null, new_in_area: null, first_visit: null, invited_by: '', how_heard: '',
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
// Cumpleaños con listas grandes: día y mes (el año solo si la administración lo pide).
function BirthdayPicker({ value, onChange, withYear, t }) {
  const update = (key, next) => {
    const merged = { ...value, [key]: next };
    // Un día que no existe en el mes elegido (31 de abril) se borra; el 29 de febrero sí existe.
    if (merged.month && merged.day && Number(merged.day) > MONTH_DAYS[Number(merged.month) - 1]) merged.day = '';
    onChange(merged);
  };
  const thisYear = new Date().getFullYear();
  const days = (current) => (current.month ? MONTH_DAYS[Number(current.month) - 1] : 31);
  // Listas grandes para tableta: alto fijo de 64 px y letra de 22 px (iPad respeta el alto solo sin la apariencia nativa).
  const select = { ...inputStyle, height: 64, minHeight: 64, fontSize: 22, padding: '0 44px 0 16px', appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer',
    backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%23101D36' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
    backgroundRepeat: 'no-repeat', backgroundPosition: 'right 14px center' };
  return (
    <div style={{ display: 'grid', gridTemplateColumns: withYear ? '1fr 1.6fr 1.2fr' : '1fr 1.6fr', gap: 12 }} data-testid="kiosk-birth">
      <select value={value.day} onChange={(event) => update('day', event.target.value)} aria-label={t.day} style={select} data-testid="kiosk-birth-day"><option value="">{t.day}</option>{Array.from({ length: days(value) }, (_, index) => String(index + 1).padStart(2, '0')).map((item) => <option key={item} value={item}>{Number(item)}</option>)}</select>
      <select value={value.month} onChange={(event) => update('month', event.target.value)} aria-label={t.month} style={select} data-testid="kiosk-birth-month"><option value="">{t.month}</option>{t.months.map((name, index) => <option key={name} value={String(index + 1).padStart(2, '0')}>{name}</option>)}</select>
      {withYear && <select value={value.year} onChange={(event) => update('year', event.target.value)} aria-label={t.year} style={select} data-testid="kiosk-birth-year"><option value="">{t.year}</option>{Array.from({ length: 100 }, (_, index) => String(thisYear - index)).map((item) => <option key={item} value={item}>{item}</option>)}</select>}
    </div>
  );
}
/** Fecha para el servidor: día y mes siempre; la fecha completa solo con año (y si existe, p. ej. no el 29 de febrero de 2023). */
export function birthPayload(birth, withYear) {
  if (!birth.day || !birth.month) return { birth_day: null, birth_month: null, birth_date: null };
  const day = Number(birth.day); const month = Number(birth.month);
  const year = withYear && birth.year ? Number(birth.year) : null;
  const valid = year && new Date(year, month, 0).getDate() >= day;
  return { birth_day: day, birth_month: month, birth_date: valid ? `${birth.year}-${birth.month}-${birth.day}` : null };
}
// Renglones alineados: casilla a la izquierda, texto a la derecha, todos del mismo alto.
function CheckRow({ on, label, onClick, testId }) {
  return (
    <button type="button" role="checkbox" aria-checked={on} onClick={onClick} data-testid={testId} className="vk-row"
      style={{ display: 'flex', alignItems: 'center', gap: 14, width: '100%', padding: '0 6px', border: 'none', borderRadius: 12, background: on ? '#EEF2FA' : 'transparent', color: C.ink, textAlign: 'left', fontSize: 'clamp(19px, 2.7vh, 21px)', fontWeight: on ? 700 : 500, lineHeight: 1.2 }}>
      <span aria-hidden style={{ flex: '0 0 auto', width: 32, height: 32, borderRadius: 8, border: `2px solid ${on ? C.navy : '#8E97A8'}`, background: on ? C.navy : '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{on && <Check size={22} color="#fff" strokeWidth={3} />}</span>
      <span>{label}</span>
    </button>
  );
}
const YesNo = ({ value, onChange, testId, t }) => <Chips options={[[true, t.yes], [false, t.no]]} value={value} onChange={onChange} testId={testId} />;
const Accent = () => <span aria-hidden style={{ display: 'block', width: 88, height: 2, background: C.gold, margin: 'clamp(10px, 2vh, 18px) auto' }} />;
// En horizontal los campos van en dos columnas para que todo quepa sin desplazar.
const Section = ({ children, testId }) => <div className="vk-grid" data-testid={testId}>{children}</div>;
const Wide = ({ children }) => <div className="vk-wide">{children}</div>;
const EMBLEM = { src: '/emblema-iglesia.png', srcSet: '/emblema-iglesia.png 1x, /emblema-iglesia@2x.png 2x', alt: 'Casa de oración Ven y Ve' };
const LOGO = { src: '/logo-iglesia.png', srcSet: '/logo-iglesia.png 1x, /logo-iglesia@2x.png 2x', alt: 'Primera Iglesia del Nazareno · Casa de oración Ven y Ve' };
const KIOSK_CSS = `
  .vk-grid { display: grid; gap: clamp(12px, 2vh, 22px); align-content: start; }
  .vk-kids { display: grid; gap: 8px; }
  @media (min-width: 700px) { .vk-kids { grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 24px; } }
  .vk-serve { display: grid; gap: clamp(8px, 1.6vh, 16px); }
  .vk-rows { display: grid; grid-auto-rows: clamp(46px, 4.1vh, 56px); gap: 4px; }
  .vk-row:focus-visible { outline: 3px solid #C8A951; outline-offset: 2px; }
  @media (orientation: landscape) and (min-width: 900px) {
    .vk-grid { grid-template-columns: 1fr 1fr; column-gap: 36px; }
    .vk-wide { grid-column: 1 / -1; }
    .vk-serve { grid-template-columns: 1fr 1fr; column-gap: 36px; align-items: start; }
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
  const [configProblem, setConfigProblem] = useState('');
  const retryTimer = useRef(null);
  const [error, setError] = useState('');
  // Idioma: null = primera pantalla («Español» / «English»). Se puede cambiar en cualquier paso sin perder lo escrito.
  const [lang, setLang] = useState(null);
  const t = KIOSK_TEXT[lang || 'es'];
  const [step, setStep] = useState(-1);  // -1 = inicio
  const [form, setForm] = useState(emptyForm);
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [idle, setIdle] = useState(0);
  const [pending, setPending] = useState(0);
  const lastTouch = useRef(Date.now());
  const times = useMemo(() => ({ ...DEFAULT_TIMEOUTS, ...(config?.timeouts || {}) }), [config]);
  // Textos editables (bienvenida, privacidad, confirmación) en el idioma elegido.
  const texts = config ? (lang === 'en' && config.texts_en ? config.texts_en : config.texts) : null;
  const withYear = !!config?.ask_birth_year;
  // Pedidos «simples» (sin encabezados propios y con el cuerpo como texto): el navegador no necesita
  // pedir permiso antes, algo que Silk de las tabletas Amazon Fire a veces no completa.
  const linkParams = { link: token || '', tablet: device };
  const simplePost = (path, body, timeout) => axios.post(`${API}${path}`, JSON.stringify(body), { params: linkParams, headers: { 'Content-Type': 'text/plain' }, timeout });
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const reset = useCallback(() => { setForm(emptyForm()); setStep(-1); setLang(null); setResult(null); setError(''); setSaving(false); window.scrollTo(0, 0); }, []);

  // Textos y servicio de hoy. Un enlace viejo o equivocado muestra cómo pedir el nuevo.
  // ¿Por qué no llegó la configuración? Prueba automática: internet, el panel y el servidor (por el
  // panel y, si aplica, directo), para saber qué falla sin adivinar.
  const diagnose = async (requestError, words) => {
    const host = (value) => { try { return new URL(value).host; } catch { return value || '—'; } };
    const probe = (url, options = {}) => new Promise((resolve) => {
      const timer = setTimeout(() => resolve(null), 7000);
      fetch(url, { cache: 'no-store', ...options })
        .then((response) => { clearTimeout(timer); resolve(response); })
        .catch(() => { clearTimeout(timer); resolve(null); });
    });
    const stamp = Date.now();
    const [internet, panel, server, direct] = await Promise.all([
      probe(`https://www.gstatic.com/generate_204?t=${stamp}`, { mode: 'no-cors' }),
      probe(`${window.location.origin}/manifest.json?t=${stamp}`),
      probe(`${API_BASE}/api/kiosk/ping?t=${stamp}`),
      API_SAME_ORIGIN && DIRECT_BACKEND_URL && host(DIRECT_BACKEND_URL) !== window.location.host ? probe(`${DIRECT_BACKEND_URL}/api/kiosk/ping?t=${stamp}`) : Promise.resolve(undefined),
    ]);
    const ok = (response) => !!response && (response.type === 'opaque' || response.ok);
    const yes = (value) => (value ? 'sí' : 'no');
    let version = 0;
    if (ok(server)) { try { version = (await server.json()).kiosk_api || 0; } catch { version = 0; } }
    const internetOk = ok(internet) || ok(panel) || ok(server);
    const checks = [`Internet: ${yes(internetOk)}`, `Panel: ${yes(ok(panel))}`, `Servidor: ${yes(ok(server))}`];
    if (direct !== undefined) checks.push(`Servidor directo: ${yes(ok(direct))}`);
    const detail = ` · ${checks.join(' · ')} (servidor: ${host(API_BASE)}; página: ${window.location.host}; código: ${requestError?.code || 'sin código'})`;
    if (requestError?.code === 'ECONNABORTED') return `${words.slow}${detail}`;
    if (ok(server)) return `${version < 5 ? words.outdated : words.blocked}${detail}`;
    if (server && server.status === 404) return `${words.outdated}${detail}`;
    if (internetOk && ok(panel)) return `${words.serverUnreachable}${detail}`;
    return `${words.offlineServer}${detail}`;
  };

  const loadConfig = useCallback(() => {
    const words = KIOSK_TEXT.es;
    if (!token) { setLinkError(words.openLink); return; }
    axios.get(`${API}/api/kiosk/config`, { params: { link: token, tablet: device }, timeout: 12000 })
      .then((response) => { setConfig(response.data); setLinkError(''); setConfigProblem(''); adoptShortPath('vv_kiosk_link', response.data.short_path); })
      .catch((requestError) => {
        const status = requestError?.response?.status;
        if (status === 401) { setLinkError(requestError.response.data?.detail || words.linkGone); return; }
        // Sin servidor (se está actualizando, sin internet, error): se dice y se reintenta solo, nunca se queda colgado.
        // 502/503/504: el panel abrió pero no llegó al servidor; se prueba qué falla.
        if (status && status < 502) setConfigProblem(words.serverError(status));
        else diagnose(status ? { code: `HTTP ${status}` } : requestError, words).then(setConfigProblem);
        clearTimeout(retryTimer.current);
        retryTimer.current = setTimeout(loadConfig, 5000);
      });
  }, [token, device]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { loadConfig(); const timer = setInterval(loadConfig, 10 * 60 * 1000); return () => { clearInterval(timer); clearTimeout(retryTimer.current); }; }, [loadConfig]);

  // Cola sin internet: se reenvía con la misma clave de idempotencia. Solo un dato
  // inválido (400/422) se descarta; sin internet, límite o enlace viejo, se reintenta.
  const send = useCallback(async (payload) => {
    try {
      return (await simplePost('/api/kiosk/registrations', payload, 20000)).data;
    } catch (requestError) {
      const status = requestError?.response?.status;
      if (status === 400 || status === 422) {
        const detail = requestError.response.data?.detail;
        const permanent = new Error(payload.language === 'en' || typeof detail !== 'string' ? KIOSK_TEXT[payload.language || 'es'].checkData : detail);
        permanent.permanent = true; throw permanent;
      }
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
  useEffect(() => { const main = document.querySelector('[data-testid=kiosk-main]'); if (main) main.scrollTop = 0; }, [step, result, lang]);

  // Sin desplazamiento ni rebote del documento mientras está el quiosco.
  useEffect(() => {
    const root = document.documentElement; const body = document.body;
    const before = [root.style.overflow, root.style.overscrollBehavior, body.style.overflow, body.style.overscrollBehavior, root.style.height, body.style.height];
    root.style.overflow = 'hidden'; root.style.overscrollBehavior = 'none'; body.style.overflow = 'hidden'; body.style.overscrollBehavior = 'none'; root.style.height = '100%'; body.style.height = '100%';
    return () => { [root.style.overflow, root.style.overscrollBehavior, body.style.overflow, body.style.overscrollBehavior, root.style.height, body.style.height] = before; };
  }, []);
  useEffect(() => { document.documentElement.lang = lang || 'es'; }, [lang]);

  // Modo quiosco: el botón «atrás» no sale de la página.
  useEffect(() => {
    window.history.pushState(null, '', window.location.href);
    const stay = () => window.history.pushState(null, '', window.location.href);
    window.addEventListener('popstate', stay);
    return () => window.removeEventListener('popstate', stay);
  }, []);
  // Inactividad: aviso y luego reinicio (borra todo lo escrito y vuelve a elegir idioma).
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

  // Lo que se envía (en cada paso al borrador y al terminar). Al continuar después del nombre la persona
  // acepta el aviso corto (lo ve completo al final).
  const buildPayload = () => {
    const { birth, ...rest } = form;
    const payload = {
      ...rest, ...birthPayload(birth, withYear), language: lang || 'es', privacy_accepted: true, privacy_version: config.texts.privacy_version, phone: phoneDigits(form.phone),
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
    simplePost('/api/kiosk/registrations/draft', buildPayload(), 8000).catch(() => {});
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
      setResult({ offline: true, greeting_name: form.preferred_name || form.first_name, confirmation: texts.confirmation });
    }
    setSaving(false); lastTouch.current = Date.now();
  };

  const order = stepOrder(form);
  const stepKey = order[Math.min(step, order.length - 1)];
  // Obligatorio: nombre y apellido, y un medio de contacto solo si aceptó el seguimiento.
  const missingContact = form.consent_followup === true && !phoneDigits(form.phone) && !form.email.trim();
  const canNext = () => (stepKey === 'nombre' ? form.first_name.trim() && form.last_name.trim() : true);
  const serviceLabel = config ? (lang === 'en' ? t.services[config.service.kind] || config.service.label : config.service.label) : '';
  // «Español | English» pequeño en la barra: cambia el idioma en cualquier paso sin perder lo escrito.
  const switcher = lang && (
    <span role="group" aria-label="Idioma · Language" style={{ display: 'inline-flex', border: `2px solid ${C.line}`, borderRadius: 12, overflow: 'hidden', flex: '0 0 auto' }} data-testid="kiosk-lang-switch">
      {LANGUAGES.map(([key, label], index) => (
        <button key={key} type="button" onClick={() => setLang(key)} aria-pressed={lang === key} data-testid={`kiosk-lang-switch-${key}`}
          style={{ minHeight: 44, padding: '0 14px', border: 'none', borderLeft: index ? `2px solid ${C.line}` : 'none', fontSize: 17, fontWeight: lang === key ? 800 : 500, background: lang === key ? C.navy : '#fff', color: lang === key ? '#fff' : C.ink }}>{label}</button>
      ))}
    </span>
  );
  const shell = (children, footer = null, hideLogo = false) => (
    // Pantalla fija de app: encabezado y botones nunca se mueven; solo el centro se desplaza si de verdad no cabe.
    // Alto = área visible (visualViewport), así el teclado no empuja el encabezado fuera de vista.
    <div style={{ position: 'fixed', left: 0, right: 0, top: 'var(--vv-top, 0px)', height: 'var(--vvh, 100dvh)', overflow: 'hidden', overscrollBehavior: 'none', touchAction: 'manipulation',
      background: C.bg, color: C.ink, fontFamily: 'Inter, system-ui, sans-serif', display: 'flex', flexDirection: 'column', userSelect: 'none' }} data-testid="kiosk-page" onContextMenu={(event) => event.preventDefault()}>
      <style>{KIOSK_CSS}</style>
      {/* Barra clara: el logo (letras verdes y azules) se ve nítido; en la bienvenida no se repite. */}
      <header style={{ flex: '0 0 auto', background: '#fff', borderBottom: `2px solid ${C.gold}`, padding: '8px 24px', minHeight: 70, boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        {/* En la barra solo el emblema (óvalo con la cruz), legible; el logo completo va grande en la bienvenida. */}
        {!hideLogo ? <img {...EMBLEM} style={{ height: 52, width: 'auto' }} data-testid="kiosk-header-logo" /> : <span />}
        <span style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
          {config && <span style={{ fontSize: 19, color: C.muted, textAlign: 'right' }}>{serviceLabel}{pending ? ` · ${t.waiting(pending)}` : ''}</span>}
          {switcher}
        </span>
      </header>
      <main className="vk-main" data-testid="kiosk-main" style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', overscrollBehavior: 'contain', touchAction: 'pan-y', WebkitOverflowScrolling: 'touch' }}>
        <div style={{ width: '100%', maxWidth: hideLogo || result ? 1040 : 1120, minHeight: '100%', margin: '0 auto', padding: 'clamp(10px, 2.4vh, 28px) 24px 20px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column' }}>{children}</div>
      </main>
      {footer && <footer style={{ flex: '0 0 auto', background: '#fff', borderTop: `2px solid ${C.line}`, padding: 16, display: 'flex', justifyContent: 'space-between', gap: 12 }}>{footer}</footer>}
      {idle >= times.form_warn_seconds && step >= 0 && !result && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(20,33,61,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }} data-testid="kiosk-idle">
          <div style={{ background: '#fff', borderRadius: 24, padding: 32, maxWidth: 560, textAlign: 'center' }}>
            <p style={{ fontSize: 30, fontWeight: 800, margin: 0 }}>{t.stillThere}</p>
            <p style={{ fontSize: 21, color: C.muted }}>{t.idleWarning(Math.max(0, times.form_reset_seconds - idle))}</p>
            <button type="button" onClick={() => { lastTouch.current = Date.now(); setIdle(0); }} data-testid="kiosk-continue"
              style={{ minHeight: 84, width: '100%', borderRadius: 20, fontSize: 30, fontWeight: 800, border: 'none', background: C.gold, color: C.navy }}>{t.continue}</button>
          </div>
        </div>
      )}
    </div>
  );

  if (linkError) {
    return shell(
      <div style={{ textAlign: 'center', marginTop: 60 }} data-testid="kiosk-link-error">
        <p style={{ fontSize: 32, fontWeight: 800, margin: 0, fontFamily: 'Spectral, Georgia, serif' }}>{t.needLinkTitle}</p>
        <p style={{ fontSize: 22, color: C.muted, marginTop: 16 }}>{linkError}</p>
      </div>,
    );
  }
  if (!config) {
    return shell(
      <div style={{ textAlign: 'center', marginTop: 40 }} data-testid="kiosk-loading">
        <p style={{ fontSize: 22, margin: 0 }}>{KIOSK_TEXT.es.preparing}</p>
        <p style={{ fontSize: 20, margin: '4px 0 0', color: C.muted }}>{KIOSK_TEXT.en.preparing}</p>
        {configProblem && <p style={{ fontSize: 20, color: C.goldDark, marginTop: 16 }} data-testid="kiosk-config-problem">{configProblem}</p>}
        {configProblem && <div style={{ marginTop: 20 }}><Big kind="secondary" onClick={() => { setConfigProblem(KIOSK_TEXT.es.retrying); loadConfig(); }} testId="kiosk-retry">{KIOSK_TEXT.es.retryNow} · {KIOSK_TEXT.en.retryNow}</Big></div>}
      </div>,
    );
  }

  // ---------------------------------------------------------------- confirmación
  if (result) {
    const extra = phrases(result.confirmation).filter((line) => !/^¡?(gracias|thank you)/i.test(line));
    return shell(
      <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1 }} data-testid="kiosk-confirmation">
        <p style={{ fontSize: 'clamp(34px, min(5.4vw, 6.4vh), 50px)', fontWeight: 700, margin: 0, fontFamily: 'Spectral, Georgia, serif', lineHeight: 1.15, color: C.navy }}>{t.thanks(result.greeting_name)}</p>
        <Accent />
        {result.offline
          ? <p style={{ fontSize: 24, margin: '20px auto', maxWidth: 680, color: C.goldDark, fontWeight: 700 }} data-testid="kiosk-offline">{t.offlineSaved}</p>
          : <>
              <p style={{ fontSize: 22, margin: 0, color: C.muted }}>{t.yourNumber}</p>
              <p style={{ fontSize: 'clamp(40px, min(10vw, 9vh), 76px)', whiteSpace: 'nowrap', fontWeight: 800, letterSpacing: '0.04em', margin: '4px 0 clamp(14px, 3vh, 28px)', color: C.navy }} data-testid="kiosk-number">{result.visitor_number}</p>
            </>}
        <div style={{ display: 'grid', gap: 8, margin: '0 auto clamp(18px, 3vh, 30px)', maxWidth: 720 }}>{extra.map((line) => <p key={line} style={{ fontSize: 'clamp(21px, 3.2vh, 25px)', lineHeight: 1.35, margin: 0 }}>{line}</p>)}</div>
        <Big onClick={reset} testId="kiosk-done">{t.done}</Big>
      </div>,
    );
  }

  // ---------------------------------------------------------------- idioma (antes de la bienvenida)
  if (!lang) {
    const choose = (key) => { setLang(key); setForm(emptyForm()); setStep(-1); lastTouch.current = Date.now(); };
    return shell(
      <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1 }} data-testid="kiosk-language">
        <img {...LOGO} style={{ width: 'min(420px, 62vw)', maxHeight: '22vh', objectFit: 'contain' }} data-testid="kiosk-logo" />
        <h1 style={{ fontSize: 'clamp(30px, min(4.6vw, 5.4vh), 44px)', margin: 'clamp(16px, 3vh, 34px) 0 0', fontFamily: 'Spectral, Georgia, serif', fontWeight: 600, lineHeight: 1.15, color: C.navy }}>{KIOSK_TEXT.es.chooseTitle}</h1>
        <p style={{ fontSize: 'clamp(24px, min(3.4vw, 4vh), 32px)', margin: '4px 0 0', color: C.goldDark, fontWeight: 700 }}>{KIOSK_TEXT.en.chooseTitle}</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 'clamp(16px, 3vw, 32px)', marginTop: 'clamp(22px, 4.4vh, 48px)', width: '100%' }}>
          {LANGUAGES.map(([key, label]) => (
            <button key={key} type="button" onClick={() => choose(key)} data-testid={`kiosk-lang-${key}`}
              style={{ flex: '0 1 340px', minHeight: 'clamp(96px, 14vh, 130px)', borderRadius: 28, fontSize: 'clamp(32px, 4.8vh, 42px)', fontWeight: 800, background: C.gold, color: C.navy, border: 'none', boxShadow: '0 8px 24px rgba(20,33,61,0.22)' }}>{label}</button>
          ))}
        </div>
        <p style={{ margin: 'clamp(14px, 3vh, 30px) 0 0', fontSize: 15, color: C.muted }}>{device}</p>
      </div>, null, true,
    );
  }

  // ---------------------------------------------------------------- inicio
  if (step < 0) {
    // Composición sin cajas: logo, título y subtítulo arriba; la frase PRINCIPAL (3.ª
    // línea), la más grande, entera al centro con una línea dorada fina; las demás,
    // secundarias, justo encima del botón.
    const [title, subtitle, main, ...closing] = phrases(texts.welcome);
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
        <button type="button" onClick={() => { setStep(0); lastTouch.current = Date.now(); }} data-testid="kiosk-begin"
          style={{ marginTop: 'clamp(14px, 2.6vh, 28px)', minHeight: 'clamp(72px, 10vh, 100px)', padding: '0 clamp(28px, 7vw, 64px)', whiteSpace: 'nowrap', borderRadius: 28, fontSize: 'clamp(28px, 4.2vh, 34px)', fontWeight: 800, background: C.gold, color: C.navy, border: 'none', boxShadow: '0 8px 24px rgba(20,33,61,0.22)' }}>{t.begin}</button>
        <p style={{ margin: 'clamp(8px, 1.6vh, 16px) 0 0', fontSize: 15, color: C.muted }}>{device}</p>
      </div>, null, true,
    );
  }

  // ---------------------------------------------------------------- pasos
  const footer = (
    <>
      <Big kind="secondary" onClick={() => (step === 0 ? reset() : setStep(step - 1))} testId="kiosk-back">{step === 0 ? t.cancel : t.back}</Big>
      {step < order.length - 1
        ? <Big onClick={() => { saveDraft(); setStep(step + 1); }} disabled={!canNext()} testId="kiosk-next">{t.next}</Big>
        : <Big onClick={submit} disabled={saving || missingContact} testId="kiosk-submit">{saving ? t.saving : t.finish}</Big>}
    </>
  );
  const title = (text, sub) => (
    <div className="vk-wide" style={{ marginBottom: 4 }}>
      <p style={{ fontSize: 18, color: C.goldDark, fontWeight: 700, margin: 0 }}>{t.step(step + 1, order.length)}{sub ? ` · ${sub}` : ''}</p>
      <h2 style={{ fontSize: 'clamp(28px, 4.4vh, 36px)', margin: '4px 0 0', fontFamily: 'Spectral, Georgia, serif', fontWeight: 600, lineHeight: 1.15, color: C.navy }}>{text}</h2>
    </div>
  );
  const setChild = (index, key, value) => set('children', form.children.map((item, position) => (position === index ? { ...item, [key]: value } : item)));
  // «Prefiero no recibir seguimiento» excluye lo demás (y al revés).
  const toggleRequest = (key) => {
    const on = form.requests.includes(key);
    if (key === 'no_followup') set('requests', on ? [] : ['no_followup']);
    else set('requests', on ? form.requests.filter((item) => item !== key) : [...form.requests.filter((item) => item !== 'no_followup'), key]);
  };
  const body = {
    nombre: <Section testId="kiosk-step-nombre">{title(t.nameTitle)}
      <Field label={t.firstName} value={form.first_name} onChange={(value) => set('first_name', value)} testId="kiosk-first-name" />
      <Field label={t.lastName} value={form.last_name} onChange={(value) => set('last_name', value)} testId="kiosk-last-name" />
      <Field label={t.preferred} value={form.preferred_name} onChange={(value) => set('preferred_name', value)} placeholder={t.preferredHint} testId="kiosk-preferred" />
      <div><Label>{t.sex}</Label><Chips options={[['female', t.female], ['male', t.male]]} value={form.sex} onChange={(value) => set('sex', value)} testId="kiosk-sex" /></div>
      <Wide><p style={{ margin: 0, fontSize: 18, color: C.muted, display: 'flex', alignItems: 'center', gap: 10 }}><Lock size={20} color={C.goldDark} aria-hidden />{t.careNote}</p></Wide>
      {/* Campo trampa: invisible para personas; los robots lo llenan. */}
      <input type="text" name="website" value={form.website} onChange={(event) => set('website', event.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true"
        style={{ position: 'absolute', left: '-10000px', width: 1, height: 1, opacity: 0 }} data-testid="kiosk-website" /></Section>,
    contacto: <Section testId="kiosk-step-contacto">{title(t.contactTitle)}
      <label style={{ display: 'block' }}><Label>{t.phone}</Label><input type="tel" inputMode="numeric" autoComplete="off" value={formatPhone(form.phone)} onChange={(event) => set('phone', phoneDigits(event.target.value))} placeholder="555-123-4567" style={inputStyle} data-testid="kiosk-phone" /></label>
      <Field label={t.email} type="email" value={form.email} onChange={(value) => set('email', value)} testId="kiosk-email" />
      <Wide><Label>{t.methodsLabel}</Label><CheckChips options={pairs(CONTACT, t.methods)} value={form.contact_methods} onChange={(value) => set('contact_methods', value)} testId="kiosk-contact-methods" /></Wide></Section>,
    vives: <Section testId="kiosk-step-vives">{title(t.homeTitle)}
      <Wide><Field label={t.street} value={form.address} onChange={(value) => set('address', value)} testId="kiosk-address" /></Wide>
      <Field label={t.city} value={form.city} onChange={(value) => set('city', value)} testId="kiosk-city" />
      <label style={{ display: 'block' }}><Label>{t.zip}</Label><input inputMode="numeric" autoComplete="off" value={form.zip_code} onChange={(event) => set('zip_code', event.target.value.replace(/[^0-9-]/g, '').slice(0, 10))} style={inputStyle} data-testid="kiosk-zip" /></label>
      <div><Label>{t.newInArea}</Label><YesNo t={t} value={form.new_in_area} onChange={(value) => set('new_in_area', value)} testId="kiosk-new-in-area" /></div>
      <div><Label>{t.birthTitle}</Label><p style={{ margin: '-4px 0 10px', fontSize: 19, color: C.muted }}>{t.birthHint}</p><BirthdayPicker t={t} withYear={withYear} value={form.birth} onChange={(value) => set('birth', value)} /></div></Section>,
    visita: <Section testId="kiosk-step-visita">{title(t.visitTitle)}
      <div><Label>{t.firstVisit}</Label><Chips options={[[true, t.firstTime], [false, t.beenBefore]]} value={form.first_visit} onChange={(value) => set('first_visit', value)} testId="kiosk-first-visit" /></div>
      <Field label={t.invitedBy} value={form.invited_by} onChange={(value) => set('invited_by', value)} placeholder={t.invitedHint} testId="kiosk-invited-by" />
      <Wide><Label>{t.heard}</Label><Chips options={HEARD.map((item) => [item, t.heardOptions[item]])} value={form.how_heard || null} onChange={(value) => set('how_heard', value || '')} testId="kiosk-heard" /></Wide></Section>,
    fe: <Section testId="kiosk-step-fe">{title(t.faithTitle)}
      <div><Label>{t.christian}</Label><Chips options={pairs(CHRISTIAN, t.christianOptions)} value={form.faith_christian} onChange={(value) => set('faith_christian', value)} testId="kiosk-christian" /></div>
      <div><Label>{t.accept}</Label><Chips options={pairs(ACCEPT, t.acceptOptions)} value={form.accept_jesus} onChange={(value) => set('accept_jesus', value)} testId="kiosk-accept-jesus" /></div>
      <Wide><CheckChips options={[['reconcile', t.reconcile], ['faith_info', t.faithInfo]]} value={['reconcile', 'faith_info'].filter((key) => form[key])}
        onChange={(value) => setForm((current) => ({ ...current, reconcile: value.includes('reconcile'), faith_info: value.includes('faith_info') }))} testId="kiosk-faith" /></Wide>
      <Wide><Label>{t.otherChurch}</Label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <YesNo t={t} value={form.other_church} onChange={(value) => set('other_church', value)} testId="kiosk-other-church" />
          {form.other_church && <>
            <input value={form.other_church_name} onChange={(event) => set('other_church_name', event.target.value)} placeholder={t.churchName} aria-label={t.churchName} autoComplete="off" style={{ ...inputStyle, flex: '1 1 220px', width: 'auto', minWidth: 0 }} data-testid="kiosk-other-church-name" />
            <input value={form.other_church_pastor} onChange={(event) => set('other_church_pastor', event.target.value)} placeholder={t.pastorName} aria-label={t.pastorName} autoComplete="off" style={{ ...inputStyle, flex: '1 1 220px', width: 'auto', minWidth: 0 }} data-testid="kiosk-other-church-pastor" />
          </>}
        </div></Wide></Section>,
    familia: <Section testId="kiosk-step-familia">{title(t.familyTitle)}
      <Wide><Label>{t.marital}</Label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <Chips options={pairs(MARITAL, t.maritalOptions)} value={form.marital_status} onChange={(value) => set('marital_status', value)} testId="kiosk-marital" />
          {form.marital_status === 'married' && <input value={form.spouse_name} onChange={(event) => set('spouse_name', event.target.value)} placeholder={t.spouse} aria-label={t.spouse} autoComplete="off" style={{ ...inputStyle, flex: '1 1 260px', width: 'auto', minWidth: 0 }} data-testid="kiosk-spouse" />}
        </div></Wide>
      <div><Label>{t.hasChildren}</Label><YesNo t={t} value={form.has_children} onChange={(value) => setForm((current) => ({ ...current, has_children: value, children: value && !current.children.length ? [{ name: '', age: '' }] : current.children }))} testId="kiosk-has-children" /></div>
      <Field label={t.companions} value={form.companions} onChange={(value) => set('companions', value)} placeholder={t.companionsHint} testId="kiosk-companions" />
      {form.has_children && <Wide><div className="vk-kids" data-testid="kiosk-children">
        {form.children.map((child, index) => (
          <div key={index} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <input value={child.name} onChange={(event) => setChild(index, 'name', event.target.value)} placeholder={t.childName(index + 1)} aria-label={t.childName(index + 1)} autoComplete="off" style={{ ...inputStyle, minHeight: 56, flex: '1 1 auto', width: 'auto', minWidth: 0 }} data-testid={`kiosk-child-name-${index}`} />
            <input value={child.age} onChange={(event) => setChild(index, 'age', event.target.value.replace(/\D/g, '').slice(0, 2))} inputMode="numeric" placeholder={t.age} aria-label={t.childAge(index + 1)} style={{ ...inputStyle, minHeight: 56, flex: '0 0 96px', width: 96 }} data-testid={`kiosk-child-age-${index}`} />
            <button type="button" onClick={() => set('children', form.children.filter((_, position) => position !== index))} aria-label={t.removeChild(index + 1)} title={t.remove}
              style={{ flex: '0 0 56px', height: 56, borderRadius: 14, border: `2px solid ${C.line}`, background: '#fff', color: C.ink, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}><X size={26} aria-hidden /></button>
          </div>
        ))}
      </div></Wide>}
      <Wide><div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        {form.has_children && <Big kind="secondary" onClick={() => set('children', [...form.children, { name: '', age: '' }])} testId="kiosk-child-add">{t.addChild}</Big>}
        <CheckChips options={[['kids', t.kids]]} value={form.kids_ministry ? ['kids'] : []} onChange={(value) => set('kids_ministry', value.includes('kids'))} testId="kiosk-kids-ministry" />
      </div></Wide></Section>,
    // Cuadrícula de renglones alineados: 2 columnas en horizontal, 1 en vertical; subtítulos cortos.
    servir: <div data-testid="kiosk-step-servir">{title(t.serveTitle, t.serveHint)}
      {/* «Prefiero no recibir seguimiento» va aparte, al final (en horizontal ocupa el hueco bajo «Participar y servir», así nada se desplaza). */}
      <div className="vk-serve" style={{ marginTop: 'clamp(6px, 1.4vh, 14px)' }} data-testid="kiosk-requests">
        {SERVE_GROUPS.map(([group, keys], index) => {
          const section = (
            <section key={group} data-testid={`kiosk-serve-${group}`}>
              <h3 style={{ margin: '0 0 2px', fontSize: 'clamp(18px, 2.5vh, 20px)', fontWeight: 800, color: C.goldDark, letterSpacing: '0.02em' }}>{t.serveGroups[group]}</h3>
              <div className="vk-rows">{keys.map((key) => <CheckRow key={key} on={form.requests.includes(key)} label={t.requests[key]} onClick={() => toggleRequest(key)} testId={`kiosk-requests-${key}`} />)}</div>
            </section>
          );
          if (index < SERVE_GROUPS.length - 1) return section;
          return (
            <div key={group}>{section}
              <div className="vk-rows" style={{ marginTop: 'clamp(10px, 1.8vh, 18px)', paddingTop: 'clamp(8px, 1.4vh, 12px)', borderTop: `2px solid ${C.line}` }}>
                <CheckRow on={form.requests.includes('no_followup')} label={t.requests.no_followup} onClick={() => toggleRequest('no_followup')} testId="kiosk-requests-no_followup" />
              </div>
            </div>
          );
        })}
      </div></div>,
    notas: <Section testId="kiosk-step-notas">{title(t.notesTitle, t.notesHint)}
      {form.requests.some((item) => PRAYER.includes(item)) && <Area label={t.prayerWhy} hint={t.prayerOnly} value={form.prayer_request} onChange={(value) => set('prayer_request', value)} testId="kiosk-prayer" />}
      {form.requests.some((item) => item.startsWith('counseling')) && <Area label={t.counselingTell} hint={t.counselingOnly} value={form.counseling_note} onChange={(value) => set('counseling_note', value)} testId="kiosk-counseling" />}
      {form.requests.some((item) => ['support_child', 'other_help'].includes(item)) && <Area label={t.needsWhat} hint={t.confidential} value={form.needs_note} onChange={(value) => set('needs_note', value)} testId="kiosk-needs" />}</Section>,
    apoyo: <Section testId="kiosk-step-apoyo">{title(t.givingTitle)}
      <Wide><CheckChips options={[['giving', t.giving]]} value={form.giving_info ? ['giving'] : []} onChange={(value) => set('giving_info', value.includes('giving'))} testId="kiosk-giving" /></Wide>
      <Wide><p style={{ margin: 0, fontSize: 20, color: C.muted }}>{t.givingNote}</p></Wide></Section>,
    cierre: <Section testId="kiosk-step-cierre">{title(t.closeTitle)}
      <Wide><YesNo t={t} value={form.consent_followup} onChange={(value) => set('consent_followup', value)} testId="kiosk-consent-followup" /></Wide>
      {missingContact && (
        <Wide><div style={{ display: 'grid', gap: 12, justifyItems: 'start' }} data-testid="kiosk-need-contact">
          <p style={{ margin: 0, fontSize: 22, color: C.goldDark, fontWeight: 700 }}>{t.needContact}</p>
          <Big kind="secondary" onClick={() => setStep(order.indexOf('contacto'))} testId="kiosk-add-contact">{t.addContact}</Big>
        </div></Wide>
      )}
      <Wide><ul style={{ display: 'grid', gap: 'clamp(10px, 2vh, 18px)', margin: '6px 0 0', padding: 0, listStyle: 'none', maxWidth: 860 }} data-testid="kiosk-privacy">
        {phrases(texts.privacy).map((line, index) => {
          const Icon = [Lock, Users, HeartHandshake][index % 3];
          return <li key={line} style={{ display: 'flex', alignItems: 'flex-start', gap: 14, fontSize: 'clamp(19px, 2.8vh, 22px)', lineHeight: 1.35, color: C.muted }}><Icon size={26} color={C.goldDark} aria-hidden style={{ flex: '0 0 auto', marginTop: 2 }} /><span>{line}</span></li>;
        })}
      </ul></Wide>
      {error && <p className="vk-wide" style={{ fontSize: 20, color: '#B42318' }}>{error}</p>}</Section>,
  }[stepKey];
  return shell(body, footer);
}
