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
// Dos pantallas para que todo quepa sin desplazar: oración, visita y servir; luego consejería y ayuda.
const SERVE_GROUPS = [['prayer', ['prayer_me', 'prayer_family', 'call_prayer']], ['visit', ['visit', 'info']], ['serve', ['membership', 'serve', 'home_service']]];
const HELP_KEYS = ['counseling_personal', 'counseling_marriage', 'counseling_family', 'support_child', 'other_help'];
const CHRISTIAN = ['yes', 'on_way', 'not_yet'];
const ACCEPT = ['today', 'another_day'];
const MARITAL = ['single', 'married', 'other'];
const pairs = (keys, labels) => keys.map((key) => [key, labels[key]]);
const PRAYER = ['prayer_me', 'prayer_family', 'call_prayer'];
// Formulario ÚNICO (los 3 papeles + el digital), un tema por paso. «Cuéntanos más» solo aparece
// si eligió oración, consejería u otra ayuda (así ninguna pantalla necesita desplazarse).
const needsNotes = (requests) => requests.some((item) => PRAYER.includes(item) || item.startsWith('counseling') || ['support_child', 'other_help'].includes(item));
const stepOrder = (form) => ['nombre', 'contacto', 'vives', 'visita', 'fe', 'familia', 'servir', 'ayuda', ...(needsNotes(form.requests) ? ['notas'] : []), 'apoyo', 'cierre'];

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

// ---------------------------------------------------------------- tamaños (tableta de 10")
// Todo se calcula aquí en píxeles (sin clamp(), min(), dvh ni gap en flex): el navegador interno de
// las tabletas Amazon Fire viejas no los entiende y el formulario quedaba chico o apretado.
// Base: 800 × 1280 en vertical y 1280 × 800 en horizontal; en pantallas mayores todo crece igual.
export function kioskSizes(width, fullHeight) {
  const landscape = width > fullHeight;
  const scale = Math.max(1, Math.min(1.6, landscape ? Math.min(width / 1280, fullHeight / 800) : Math.min(width / 800, fullHeight / 1280)));
  const px = (value) => Math.round(value * scale);
  return {
    scale, landscape, text: px(22), hint: px(20), label: px(24), title: px(landscape ? 36 : 40), step: px(21),
    tap: px(72), tapFont: px(24), input: px(72), inputFont: px(26), space: px(landscape ? 20 : 30), chip: px(16),
    side: px(landscape ? 40 : 36), header: px(84), footer: px(112), footButton: px(80), footFont: px(28), row: px(landscape ? 64 : 72), radius: px(18), box: px(36),
    content: landscape ? px(1180) : px(728),
  };
}
/** Desplaza solo el centro para que el campo enfocado (con su título) se vea entero. */
function revealFocused() {
  const main = document.querySelector('[data-testid=kiosk-main]');
  const field = document.activeElement;
  if (!main || !field || !/^(INPUT|TEXTAREA|SELECT)$/.test(field.tagName) || !main.contains(field)) return;
  const box = main.getBoundingClientRect(); const rect = field.getBoundingClientRect();
  const label = field.closest ? field.closest('label') : null;
  const top = label ? Math.min(rect.top, label.getBoundingClientRect().top) : rect.top;
  if (top < box.top + 8 || rect.bottom > box.bottom - 8) main.scrollTop += top - box.top - Math.max(8, (box.height - (rect.bottom - top)) / 3);
}
const SizeContext = React.createContext(kioskSizes(800, 1280));
const useSizes = () => React.useContext(SizeContext);
const viewportNow = () => {
  const view = window.visualViewport;
  return { width: Math.round(view ? view.width : window.innerWidth), height: Math.round(view ? view.height : window.innerHeight), top: Math.round(view ? view.offsetTop : 0) };
};
/** Área visible y su alto SIN teclado (el teclado achica el alto, pero no el tamaño de las letras). */
function useScreen() {
  const [screen, setScreen] = useState(viewportNow);
  const tallest = useRef({});
  useEffect(() => {
    const update = () => setScreen(viewportNow());
    const view = window.visualViewport;
    window.addEventListener('resize', update); window.addEventListener('orientationchange', update);
    if (view) { view.addEventListener('resize', update); view.addEventListener('scroll', update); }
    return () => {
      window.removeEventListener('resize', update); window.removeEventListener('orientationchange', update);
      if (view) { view.removeEventListener('resize', update); view.removeEventListener('scroll', update); }
    };
  }, []);
  const full = Math.max(tallest.current[screen.width] || 0, screen.height);
  tallest.current[screen.width] = full;
  return { ...screen, full, keyboard: screen.height < full * 0.8 };
}

// ---------------------------------------------------------------- piezas grandes (tableta)
const Big = ({ children, onClick, kind = 'primary', disabled, testId, type = 'button', full }) => {
  const z = useSizes();
  return (
    <button type={type} onClick={onClick} disabled={disabled} data-testid={testId}
      style={{ minHeight: z.tap, width: full ? '100%' : 'auto', padding: `0 ${Math.round(z.tap * 0.45)}px`, borderRadius: z.radius, fontSize: z.tapFont, fontWeight: 700, border: kind === 'primary' ? 'none' : `2px solid ${C.line}`,
        background: kind === 'primary' ? C.navy : '#fff', color: kind === 'primary' ? '#fff' : C.ink, opacity: disabled ? 0.45 : 1, cursor: disabled ? 'default' : 'pointer' }}>{children}</button>
  );
};
const Label = ({ children }) => { const z = useSizes(); return <span style={{ display: 'block', fontSize: z.label, fontWeight: 700, color: C.ink, marginBottom: Math.round(z.space * 0.35), lineHeight: 1.25 }}>{children}</span>; };
const Hint = ({ children, style }) => { const z = useSizes(); return <span style={{ display: 'block', fontSize: z.hint, color: C.muted, lineHeight: 1.35, ...style }}>{children}</span>; };
const inputStyleFor = (z) => ({ display: 'block', width: '100%', height: z.input, minHeight: z.input, borderRadius: z.radius, border: `2px solid ${C.line}`, padding: `0 ${Math.round(z.inputFont * 0.75)}px`, fontSize: z.inputFont, background: '#fff', color: C.ink, boxSizing: 'border-box', WebkitAppearance: 'none' });
const useInputStyle = () => inputStyleFor(useSizes());
function Field({ label, value, onChange, type = 'text', placeholder, testId, autoComplete = 'off', inputMode }) {
  const inputStyle = useInputStyle();
  return <label style={{ display: 'block' }}><Label>{label}</Label><input type={type} inputMode={inputMode} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} autoComplete={autoComplete} style={inputStyle} data-testid={testId} /></label>;
}
function Area({ label, value, onChange, testId, hint }) {
  const z = useSizes(); const inputStyle = useInputStyle();
  return <label style={{ display: 'block' }}><Label>{label}</Label>{hint && <Hint style={{ margin: `-4px 0 ${Math.round(z.space * 0.35)}px` }}>{hint}</Hint>}<textarea value={value} onChange={(event) => onChange(event.target.value)} rows={3} style={{ ...inputStyle, height: Math.round(z.input * (z.landscape ? 1.75 : 2.1)), padding: Math.round(z.inputFont * 0.6), lineHeight: 1.35, resize: 'none' }} data-testid={testId} /></label>;
}
/** Opciones grandes en cuadrícula (mismo ancho, separadas): un toque elige o marca. */
function OptionGrid({ options, isOn, onToggle, cols, testId, itemTestId, check }) {
  const z = useSizes();
  const half = Math.round(z.chip / 2);
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', margin: -half }} data-testid={testId}>
      {options.map(([key, label]) => {
        const on = isOn(key);
        return (
          <div key={String(key)} style={{ width: `${100 / cols}%`, padding: half, boxSizing: 'border-box' }}>
            <button type="button" onClick={() => onToggle(key)} {...(check ? { role: 'checkbox', 'aria-checked': on } : { 'aria-pressed': on })} data-testid={itemTestId ? itemTestId(key) : undefined}
              style={{ width: '100%', minHeight: z.tap, padding: `${Math.round(z.tap * 0.14)}px ${Math.round(z.tap * 0.25)}px`, borderRadius: z.radius, fontSize: z.tapFont, fontWeight: on ? 800 : 600, lineHeight: 1.2,
                display: 'flex', alignItems: 'center', justifyContent: check ? 'flex-start' : 'center', textAlign: check ? 'left' : 'center',
                border: `2px solid ${on ? C.navy : C.line}`, background: on ? (check ? '#EEF2FA' : C.navy) : '#fff', color: on && !check ? '#fff' : C.ink }}>
              {check && <CheckBox on={on} />}<span>{label}</span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
function CheckBox({ on }) {
  const z = useSizes();
  return <span aria-hidden style={{ flex: '0 0 auto', width: z.box, height: z.box, marginRight: Math.round(z.box * 0.45), borderRadius: Math.round(z.box * 0.25), border: `2px solid ${on ? C.navy : '#8E97A8'}`, background: on ? C.navy : '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>{on && <Check size={Math.round(z.box * 0.7)} color="#fff" strokeWidth={3} />}</span>;
}
function Chips({ options, value, onChange, multiple, testId, cols }) {
  const selected = (key) => (multiple ? value.includes(key) : value === key);
  const toggle = (key) => (multiple ? onChange(selected(key) ? value.filter((item) => item !== key) : [...value, key]) : onChange(selected(key) ? null : key));
  return <OptionGrid options={options} isOn={selected} onToggle={toggle} cols={cols || options.length} testId={testId} />;
}
// Casillas grandes (se pueden marcar varias).
function CheckChips({ options, value, onChange, testId, cols }) {
  return <OptionGrid check options={options} isOn={(key) => value.includes(key)} onToggle={(key) => onChange(value.includes(key) ? value.filter((item) => item !== key) : [...value, key])} cols={cols || 1} testId={testId} itemTestId={(key) => `${testId}-${key}`} />;
}
// Cumpleaños con listas grandes: día y mes (el año solo si la administración lo pide).
function BirthdayPicker({ value, onChange, withYear, t }) {
  const z = useSizes(); const inputStyle = useInputStyle();
  const update = (key, next) => {
    const merged = { ...value, [key]: next };
    // Un día que no existe en el mes elegido (31 de abril) se borra; el 29 de febrero sí existe.
    if (merged.month && merged.day && Number(merged.day) > MONTH_DAYS[Number(merged.month) - 1]) merged.day = '';
    onChange(merged);
  };
  const thisYear = new Date().getFullYear();
  const days = (current) => (current.month ? MONTH_DAYS[Number(current.month) - 1] : 31);
  // Listas grandes: alto fijo y letra grande (sin la apariencia nativa, que ignora el alto).
  const select = { ...inputStyle, padding: `0 ${Math.round(z.inputFont * 1.9)}px 0 ${Math.round(z.inputFont * 0.6)}px`, appearance: 'none', MozAppearance: 'none', cursor: 'pointer',
    backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%23101D36' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
    backgroundRepeat: 'no-repeat', backgroundPosition: `right ${Math.round(z.inputFont * 0.6)}px center`, backgroundSize: `${z.inputFont}px ${z.inputFont}px` };
  const half = Math.round(z.chip / 2);
  const cell = (flex, child) => <div style={{ flex, minWidth: 0, padding: `0 ${half}px` }}>{child}</div>;
  return (
    <div style={{ display: 'flex', margin: `0 -${half}px` }} data-testid="kiosk-birth">
      {cell('1 1 0', <select value={value.day} onChange={(event) => update('day', event.target.value)} aria-label={t.day} style={select} data-testid="kiosk-birth-day"><option value="">{t.day}</option>{Array.from({ length: days(value) }, (_, index) => String(index + 1).padStart(2, '0')).map((item) => <option key={item} value={item}>{Number(item)}</option>)}</select>)}
      {cell('1.7 1 0', <select value={value.month} onChange={(event) => update('month', event.target.value)} aria-label={t.month} style={select} data-testid="kiosk-birth-month"><option value="">{t.month}</option>{t.months.map((name, index) => <option key={name} value={String(index + 1).padStart(2, '0')}>{name}</option>)}</select>)}
      {withYear && cell('1.2 1 0', <select value={value.year} onChange={(event) => update('year', event.target.value)} aria-label={t.year} style={select} data-testid="kiosk-birth-year"><option value="">{t.year}</option>{Array.from({ length: 100 }, (_, index) => String(thisYear - index)).map((item) => <option key={item} value={item}>{item}</option>)}</select>)}
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
  const z = useSizes();
  return (
    <button type="button" role="checkbox" aria-checked={on} onClick={onClick} data-testid={testId} className="vk-row"
      style={{ display: 'flex', alignItems: 'center', width: '100%', minHeight: z.row, marginBottom: Math.round(z.chip * 0.5), padding: `0 ${Math.round(z.chip)}px`, border: `2px solid ${on ? C.navy : C.line}`, borderRadius: z.radius,
        background: on ? '#EEF2FA' : '#fff', color: C.ink, textAlign: 'left', fontSize: z.tapFont, fontWeight: on ? 700 : 500, lineHeight: 1.2 }}>
      <CheckBox on={on} /><span>{label}</span>
    </button>
  );
}
const YesNo = ({ value, onChange, testId, t }) => <Chips options={[[true, t.yes], [false, t.no]]} value={value} onChange={onChange} testId={testId} />;
const Accent = () => <span aria-hidden style={{ display: 'block', width: 88, height: 2, background: C.gold, margin: '18px auto' }} />;
// Cada campo es un bloque; en horizontal van en dos columnas (los «Wide» ocupan todo el ancho).
const Section = ({ children, testId }) => <div className="vk-grid" data-testid={testId}>{children}</div>;
const Wide = ({ children }) => <div className="vk-wide">{children}</div>;
const EMBLEM = { src: '/emblema-iglesia.png', srcSet: '/emblema-iglesia.png 1x, /emblema-iglesia@2x.png 2x', alt: 'Casa de oración Ven y Ve' };
const LOGO = { src: '/logo-iglesia.png', srcSet: '/logo-iglesia.png 1x, /logo-iglesia@2x.png 2x', alt: 'Primera Iglesia del Nazareno · Casa de oración Ven y Ve' };
const kioskCss = (z) => `
  .vk-grid > * { box-sizing: border-box; width: 100%; margin-bottom: ${z.space}px; }
  .vk-grid > *:last-child { margin-bottom: 0; }
  .vk-row:focus-visible, .vk-grid button:focus-visible { outline: 3px solid #C8A951; outline-offset: 2px; }
  .vk-grid input::placeholder { color: #98A2B3; }
  ${z.landscape ? `
  .vk-grid { display: flex; flex-wrap: wrap; align-items: flex-start; margin: 0 -${Math.round(z.side * 0.45)}px; }
  .vk-grid > * { width: 50%; padding: 0 ${Math.round(z.side * 0.45)}px; }
  .vk-grid > .vk-wide { width: 100%; }
  .vk-grid > *:last-child { margin-bottom: 0; }` : ''}
`;

export default function KioskPage() {
  const params = useParams();
  // El enlace se guarda en la tableta: el acceso directo «Registro» abre /quiosco sin el enlace.
  const [token] = useState(() => rememberedToken('vv_kiosk_link', params.token));
  useAppManifest('/manifest-registro.json', 'Registro');
  const [device] = useState(tabletName);
  const screen = useScreen();
  const z = kioskSizes(screen.width, screen.full);
  const inputStyle = inputStyleFor(z);
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
  // Con el teclado abierto, el campo que se escribe queda a la vista, por encima de los botones de abajo.
  useEffect(() => {
    const later = () => { setTimeout(revealFocused, 80); setTimeout(revealFocused, 450); };
    document.addEventListener('focusin', later);
    return () => document.removeEventListener('focusin', later);
  }, []);
  useEffect(() => { setTimeout(revealFocused, 60); }, [screen.height]);

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
  // «Español | English» en la barra: cambia el idioma en cualquier paso sin perder lo escrito.
  const switcher = lang && (
    <span role="group" aria-label="Idioma · Language" style={{ display: 'inline-flex', border: `2px solid ${C.line}`, borderRadius: z.radius, overflow: 'hidden', flex: '0 0 auto' }} data-testid="kiosk-lang-switch">
      {LANGUAGES.map(([key, label], index) => (
        <button key={key} type="button" onClick={() => setLang(key)} aria-pressed={lang === key} data-testid={`kiosk-lang-switch-${key}`}
          style={{ minHeight: Math.round(z.tap * 0.9), padding: `0 ${Math.round(z.chip * 1.2)}px`, border: 'none', borderLeft: index ? `2px solid ${C.line}` : 'none', fontSize: z.hint, fontWeight: lang === key ? 800 : 500, background: lang === key ? C.navy : '#fff', color: lang === key ? '#fff' : C.ink }}>{label}</button>
      ))}
    </span>
  );
  // Pantalla fija de app: encabezado y botones nunca se mueven; solo el centro se desplaza si de verdad no cabe.
  // Alto = área visible: con el teclado abierto los botones quedan justo encima del teclado.
  // `center`: el contenido va centrado en el alto (sin zonas vacías abajo ni todo apretado arriba).
  const shell = (children, footer = null, hideLogo = false, maxWidth = z.content) => {
    const typing = screen.keyboard && footer;
    return (
      <SizeContext.Provider value={z}>
        <div style={{ position: 'fixed', left: 0, top: screen.top, width: '100%', height: screen.height, overflow: 'hidden', touchAction: 'manipulation',
          background: C.bg, color: C.ink, fontFamily: 'Inter, system-ui, sans-serif', display: 'flex', flexDirection: 'column', userSelect: 'none', WebkitUserSelect: 'none' }} data-testid="kiosk-page" onContextMenu={(event) => event.preventDefault()}>
          <style>{kioskCss(z)}</style>
          {/* Barra clara con el emblema; en la bienvenida no se repite. Con el teclado abierto se oculta (más espacio para escribir). */}
          {!typing && (
            <header style={{ flex: '0 0 auto', background: '#fff', borderBottom: `2px solid ${C.gold}`, padding: `0 ${z.side}px`, height: z.header, boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              {!hideLogo ? <img {...EMBLEM} style={{ height: Math.round(z.header * 0.66), width: 'auto' }} data-testid="kiosk-header-logo" /> : <span />}
              <span style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
                {config && <span style={{ fontSize: z.hint, color: C.muted, textAlign: 'right', marginRight: z.chip }}>{serviceLabel}{pending ? ` · ${t.waiting(pending)}` : ''}</span>}
                {switcher}
              </span>
            </header>
          )}
          <main data-testid="kiosk-main" style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', overflowX: 'hidden', WebkitOverflowScrolling: 'touch', display: 'flex', flexDirection: 'column' }}>
            {/* margin auto: centrado si cabe; si no cabe, empieza arriba y se desplaza (nunca se corta). */}
            <div style={{ width: '100%', maxWidth: maxWidth + z.side * 2, margin: typing ? '0 auto' : 'auto', padding: `${Math.round(z.space * (typing ? 0.6 : 1))}px ${z.side}px`, boxSizing: 'border-box' }}>{children}</div>
          </main>
          {footer && <footer style={{ flex: '0 0 auto', background: '#fff', borderTop: `2px solid ${C.line}`, height: z.footer, padding: `0 ${z.side}px`, boxSizing: 'border-box', display: 'flex', alignItems: 'center' }}>{footer}</footer>}
          {idle >= times.form_warn_seconds && step >= 0 && !result && (
            <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(20,33,61,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: z.side }} data-testid="kiosk-idle">
              <div style={{ background: '#fff', borderRadius: z.radius * 1.4, padding: z.side, width: '100%', maxWidth: Math.round(600 * z.scale), textAlign: 'center', boxSizing: 'border-box' }}>
                <p style={{ fontSize: z.title, fontWeight: 800, margin: 0 }}>{t.stillThere}</p>
                <p style={{ fontSize: z.text, color: C.muted, lineHeight: 1.4 }}>{t.idleWarning(Math.max(0, times.form_reset_seconds - idle))}</p>
                <button type="button" onClick={() => { lastTouch.current = Date.now(); setIdle(0); }} data-testid="kiosk-continue"
                  style={{ minHeight: Math.round(z.tap * 1.2), width: '100%', borderRadius: z.radius * 1.2, fontSize: Math.round(z.title * 0.8), fontWeight: 800, border: 'none', background: C.gold, color: C.navy }}>{t.continue}</button>
              </div>
            </div>
          )}
        </div>
      </SizeContext.Provider>
    );
  };
  const serif = 'Spectral, Georgia, serif';
  const centered = { textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' };
  const bigGold = { borderRadius: Math.round(z.radius * 1.5), fontWeight: 800, background: C.gold, color: C.navy, border: 'none', boxShadow: '0 8px 24px rgba(20,33,61,0.22)' };

  if (linkError) {
    return shell(
      <div style={{ textAlign: 'center' }} data-testid="kiosk-link-error">
        <p style={{ fontSize: z.title, fontWeight: 800, margin: 0, fontFamily: serif, lineHeight: 1.2 }}>{t.needLinkTitle}</p>
        <p style={{ fontSize: z.text, color: C.muted, marginTop: z.space, lineHeight: 1.4 }}>{linkError}</p>
      </div>,
    );
  }
  if (!config) {
    return shell(
      <div style={{ textAlign: 'center' }} data-testid="kiosk-loading">
        <p style={{ fontSize: z.label, margin: 0 }}>{KIOSK_TEXT.es.preparing}</p>
        <p style={{ fontSize: z.text, margin: '4px 0 0', color: C.muted }}>{KIOSK_TEXT.en.preparing}</p>
        {configProblem && <p style={{ fontSize: z.hint, color: C.goldDark, marginTop: z.space, lineHeight: 1.4 }} data-testid="kiosk-config-problem">{configProblem}</p>}
        {configProblem && <div style={{ marginTop: z.space }}><Big kind="secondary" onClick={() => { setConfigProblem(KIOSK_TEXT.es.retrying); loadConfig(); }} testId="kiosk-retry">{KIOSK_TEXT.es.retryNow} · {KIOSK_TEXT.en.retryNow}</Big></div>}
      </div>,
    );
  }

  // ---------------------------------------------------------------- confirmación
  if (result) {
    const extra = phrases(result.confirmation).filter((line) => !/^¡?(gracias|thank you)/i.test(line));
    return shell(
      <div style={centered} data-testid="kiosk-confirmation">
        <p style={{ fontSize: Math.round(z.title * 1.35), fontWeight: 700, margin: 0, fontFamily: serif, lineHeight: 1.15, color: C.navy }}>{t.thanks(result.greeting_name)}</p>
        <Accent />
        {result.offline
          ? <p style={{ fontSize: z.label, margin: `${z.space}px auto`, maxWidth: Math.round(680 * z.scale), color: C.goldDark, fontWeight: 700, lineHeight: 1.4 }} data-testid="kiosk-offline">{t.offlineSaved}</p>
          : <>
              <p style={{ fontSize: z.label, margin: 0, color: C.muted }}>{t.yourNumber}</p>
              <p style={{ fontSize: Math.round(z.title * 2.2), whiteSpace: 'nowrap', fontWeight: 800, letterSpacing: '0.04em', margin: `4px 0 ${z.space}px`, color: C.navy, lineHeight: 1.1 }} data-testid="kiosk-number">{result.visitor_number}</p>
            </>}
        <div style={{ margin: `0 auto ${Math.round(z.space * 1.3)}px`, maxWidth: Math.round(720 * z.scale) }}>{extra.map((line) => <p key={line} style={{ fontSize: Math.round(z.text * 1.15), lineHeight: 1.4, margin: `0 0 ${Math.round(z.space * 0.4)}px` }}>{line}</p>)}</div>
        <button type="button" onClick={reset} data-testid="kiosk-done" style={{ ...bigGold, minHeight: Math.round(z.tap * 1.2), minWidth: Math.round(340 * z.scale), padding: `0 ${z.side}px`, fontSize: Math.round(z.title * 0.85) }}>{t.done}</button>
      </div>, null, false, Math.round(900 * z.scale),
    );
  }

  // ---------------------------------------------------------------- idioma (antes de la bienvenida)
  if (!lang) {
    const choose = (key) => { setLang(key); setForm(emptyForm()); setStep(-1); lastTouch.current = Date.now(); };
    return shell(
      <div style={centered} data-testid="kiosk-language">
        <img {...LOGO} style={{ width: Math.round((z.landscape ? 380 : 480) * z.scale), maxWidth: '80%', height: 'auto' }} data-testid="kiosk-logo" />
        <h1 style={{ fontSize: Math.round(z.title * 1.15), margin: `${Math.round(z.space * 1.3)}px 0 0`, fontFamily: serif, fontWeight: 600, lineHeight: 1.15, color: C.navy }}>{KIOSK_TEXT.es.chooseTitle}</h1>
        <p style={{ fontSize: Math.round(z.title * 0.85), margin: '6px 0 0', color: C.goldDark, fontWeight: 700 }}>{KIOSK_TEXT.en.chooseTitle}</p>
        <div style={{ display: 'flex', flexDirection: z.landscape ? 'row' : 'column', alignItems: 'center', justifyContent: 'center', marginTop: Math.round(z.space * 1.5), width: '100%' }}>
          {LANGUAGES.map(([key, label], index) => (
            <button key={key} type="button" onClick={() => choose(key)} data-testid={`kiosk-lang-${key}`}
              style={{ ...bigGold, width: Math.round(420 * z.scale), maxWidth: '100%', minHeight: Math.round(z.tap * 1.75), fontSize: Math.round(z.title * 1.1), margin: index ? (z.landscape ? `0 0 0 ${z.space * 1.5}px` : `${z.space}px 0 0`) : 0 }}>{label}</button>
          ))}
        </div>
        <p style={{ margin: `${Math.round(z.space * 1.2)}px 0 0`, fontSize: 15, color: C.muted }}>{device}</p>
      </div>, null, true, Math.round(1000 * z.scale),
    );
  }

  // ---------------------------------------------------------------- inicio
  if (step < 0) {
    // Logo, título y subtítulo arriba; la frase PRINCIPAL (3.ª línea), la más grande, al centro con una
    // línea dorada fina; las demás, secundarias, justo encima del botón.
    const [title, subtitle, main, ...closing] = phrases(texts.welcome);
    return shell(
      <div style={centered} data-testid="kiosk-start">
        <img {...LOGO} style={{ width: Math.round((z.landscape ? 280 : 460) * z.scale), maxWidth: '80%', height: 'auto' }} data-testid="kiosk-logo" />
        <h1 style={{ fontSize: Math.round(z.title * 1.05), margin: `${Math.round(z.space * (z.landscape ? 0.6 : 1))}px 0 0`, fontFamily: serif, fontWeight: 600, lineHeight: 1.15, color: C.navy }} data-testid="kiosk-title">{title}</h1>
        {subtitle && <p style={{ fontSize: Math.round(z.label * 1.1), margin: '8px 0 0', color: C.goldDark, fontWeight: 700 }} data-testid="kiosk-subtitle">{subtitle}</p>}
        {main && (
          <div style={{ width: '100%', margin: `${z.space}px 0 0` }} data-testid="kiosk-main-phrase">
            <span aria-hidden style={{ display: 'block', width: 120, height: 2, background: C.gold, margin: `0 auto ${Math.round(z.space * 0.7)}px` }} />
            <p style={{ margin: 0, fontFamily: serif, fontWeight: 700, fontSize: Math.round(z.title * (z.landscape ? 1.15 : 1.25)), lineHeight: 1.2, color: C.navy, overflowWrap: 'break-word' }}>{main}</p>
          </div>
        )}
        {closing.map((line) => <p key={line} style={{ margin: `${z.space}px 0 0`, fontSize: Math.round(z.text * 1.1), lineHeight: 1.4, color: C.muted }} data-testid="kiosk-closing">{line}</p>)}
        <button type="button" onClick={() => { setStep(0); lastTouch.current = Date.now(); }} data-testid="kiosk-begin"
          style={{ ...bigGold, marginTop: Math.round(z.space * 1.3), minHeight: Math.round(z.tap * 1.4), padding: `0 ${Math.round(z.side * 1.6)}px`, whiteSpace: 'nowrap', fontSize: Math.round(z.title * 0.95) }}>{t.begin}</button>
        <p style={{ margin: `${Math.round(z.space * 0.6)}px 0 0`, fontSize: 15, color: C.muted }}>{device}</p>
      </div>, null, true, Math.round(1000 * z.scale),
    );
  }

  // ---------------------------------------------------------------- pasos
  // Botones fijos abajo, grandes y separados: «Atrás» a la izquierda, «Siguiente» (más ancho) a la derecha.
  const footButton = (primary) => ({ height: z.footButton, borderRadius: z.radius, fontSize: z.footFont, fontWeight: 800, border: primary ? 'none' : `2px solid ${C.line}`, background: primary ? C.navy : '#fff', color: primary ? '#fff' : C.ink });
  const last = step >= order.length - 1;
  const nextOff = last ? saving || missingContact : !canNext();
  const footer = (
    <>
      <button type="button" onClick={() => (step === 0 ? reset() : setStep(step - 1))} data-testid="kiosk-back" style={{ ...footButton(false), flex: '1 1 0', marginRight: z.space }}>{step === 0 ? t.cancel : `‹ ${t.back}`}</button>
      <button type="button" onClick={last ? submit : () => { saveDraft(); setStep(step + 1); }} disabled={nextOff} data-testid={last ? 'kiosk-submit' : 'kiosk-next'}
        style={{ ...footButton(true), flex: '2 1 0', opacity: nextOff ? 0.45 : 1 }}>{last ? (saving ? t.saving : t.finish) : `${t.next} ›`}</button>
    </>
  );
  const title = (text, sub) => (
    <div className="vk-wide">
      <p style={{ fontSize: z.step, color: C.goldDark, fontWeight: 700, margin: 0 }}>{t.step(step + 1, order.length)}{sub ? ` · ${sub}` : ''}</p>
      {/* Avance: una barra fina que se llena paso a paso. */}
      <div aria-hidden style={{ height: 6, borderRadius: 3, background: C.line, margin: '10px 0 0', overflow: 'hidden' }}><div style={{ height: 6, width: `${Math.round(((step + 1) / order.length) * 100)}%`, background: C.gold }} /></div>
      <h2 style={{ fontSize: z.title, margin: `${Math.round(z.space * 0.5)}px 0 0`, fontFamily: serif, fontWeight: 600, lineHeight: 1.15, color: C.navy }}>{text}</h2>
    </div>
  );
  const setChild = (index, key, value) => set('children', form.children.map((item, position) => (position === index ? { ...item, [key]: value } : item)));
  // «Prefiero no recibir seguimiento» excluye lo demás (y al revés).
  const toggleRequest = (key) => {
    const on = form.requests.includes(key);
    if (key === 'no_followup') set('requests', on ? [] : ['no_followup']);
    else set('requests', on ? form.requests.filter((item) => item !== key) : [...form.requests.filter((item) => item !== 'no_followup'), key]);
  };
  const rows = (keys) => keys.map((key) => <CheckRow key={key} on={form.requests.includes(key)} label={t.requests[key]} onClick={() => toggleRequest(key)} testId={`kiosk-requests-${key}`} />);
  const group = (name, keys) => (
    <section key={name} data-testid={`kiosk-serve-${name}`} style={{ marginBottom: Math.round(z.space * (z.landscape ? 0.3 : 0.6)) }}>
      <h3 style={{ margin: `0 0 ${Math.round(z.chip * 0.6)}px`, fontSize: z.label, fontWeight: 800, color: C.goldDark }}>{t.serveGroups[name]}</h3>
      {rows(keys)}
    </section>
  );
  const half = Math.round(z.side * 0.45);
  const columns = (left, right) => (z.landscape
    ? <div style={{ display: 'flex', alignItems: 'flex-start', margin: `0 -${half}px` }}><div style={{ width: '50%', padding: `0 ${half}px`, boxSizing: 'border-box' }}>{left}</div><div style={{ width: '50%', padding: `0 ${half}px`, boxSizing: 'border-box' }}>{right}</div></div>
    : <div>{left}{right}</div>);
  const lineInput = (props) => <input autoComplete="off" {...props} style={{ ...inputStyle, ...(props.style || {}) }} />;
  const inlinePair = (first, second) => (
    <div style={{ display: 'flex', margin: `${Math.round(z.chip)}px -${Math.round(z.chip / 2)}px 0` }}>
      <div style={{ flex: '1 1 0', minWidth: 0, padding: `0 ${Math.round(z.chip / 2)}px` }}>{first}</div>
      {second && <div style={{ flex: '1 1 0', minWidth: 0, padding: `0 ${Math.round(z.chip / 2)}px` }}>{second}</div>}
    </div>
  );
  const body = {
    nombre: <Section testId="kiosk-step-nombre">{title(t.nameTitle)}
      <Field label={t.firstName} value={form.first_name} onChange={(value) => set('first_name', value)} testId="kiosk-first-name" />
      <Field label={t.lastName} value={form.last_name} onChange={(value) => set('last_name', value)} testId="kiosk-last-name" />
      <Field label={t.preferred} value={form.preferred_name} onChange={(value) => set('preferred_name', value)} placeholder={t.preferredHint} testId="kiosk-preferred" />
      <div><Label>{t.sex}</Label><Chips options={[['female', t.female], ['male', t.male]]} value={form.sex} onChange={(value) => set('sex', value)} testId="kiosk-sex" /></div>
      <Wide><p style={{ margin: 0, fontSize: z.hint, color: C.muted, display: 'flex', alignItems: 'center', lineHeight: 1.35 }}><Lock size={Math.round(z.hint * 1.1)} color={C.goldDark} aria-hidden style={{ flex: '0 0 auto', marginRight: 10 }} />{t.careNote}</p></Wide>
      {/* Campo trampa: invisible para personas; los robots lo llenan. */}
      <input type="text" name="website" value={form.website} onChange={(event) => set('website', event.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true"
        style={{ position: 'absolute', left: '-10000px', width: 1, height: 1, opacity: 0 }} data-testid="kiosk-website" /></Section>,
    contacto: <Section testId="kiosk-step-contacto">{title(t.contactTitle)}
      <label style={{ display: 'block' }}><Label>{t.phone}</Label>{lineInput({ type: 'tel', inputMode: 'numeric', value: formatPhone(form.phone), onChange: (event) => set('phone', phoneDigits(event.target.value)), placeholder: '555-123-4567', 'data-testid': 'kiosk-phone' })}</label>
      <Field label={t.email} type="email" inputMode="email" value={form.email} onChange={(value) => set('email', value)} testId="kiosk-email" />
      <Wide><Label>{t.methodsLabel}</Label><CheckChips cols={z.landscape ? 4 : 2} options={pairs(CONTACT, t.methods)} value={form.contact_methods} onChange={(value) => set('contact_methods', value)} testId="kiosk-contact-methods" /></Wide></Section>,
    vives: <Section testId="kiosk-step-vives">{title(t.homeTitle)}
      <Wide><Field label={t.street} value={form.address} onChange={(value) => set('address', value)} testId="kiosk-address" /></Wide>
      <Field label={t.city} value={form.city} onChange={(value) => set('city', value)} testId="kiosk-city" />
      <label style={{ display: 'block' }}><Label>{t.zip}</Label>{lineInput({ inputMode: 'numeric', value: form.zip_code, onChange: (event) => set('zip_code', event.target.value.replace(/[^0-9-]/g, '').slice(0, 10)), 'data-testid': 'kiosk-zip' })}</label>
      <div><Label>{t.newInArea}</Label><YesNo t={t} value={form.new_in_area} onChange={(value) => set('new_in_area', value)} testId="kiosk-new-in-area" /></div>
      <div><Label>{t.birthTitle}</Label><Hint style={{ margin: `-4px 0 ${Math.round(z.space * 0.35)}px` }}>{t.birthHint}</Hint><BirthdayPicker t={t} withYear={withYear} value={form.birth} onChange={(value) => set('birth', value)} /></div></Section>,
    visita: <Section testId="kiosk-step-visita">{title(t.visitTitle)}
      <div><Label>{t.firstVisit}</Label><Chips options={[[true, t.firstTime], [false, t.beenBefore]]} value={form.first_visit} onChange={(value) => set('first_visit', value)} testId="kiosk-first-visit" /></div>
      <Field label={t.invitedBy} value={form.invited_by} onChange={(value) => set('invited_by', value)} placeholder={t.invitedHint} testId="kiosk-invited-by" />
      <Wide><Label>{t.heard}</Label><Chips cols={z.landscape ? 3 : 2} options={HEARD.map((item) => [item, t.heardOptions[item]])} value={form.how_heard || null} onChange={(value) => set('how_heard', value || '')} testId="kiosk-heard" /></Wide></Section>,
    fe: <Section testId="kiosk-step-fe">{title(t.faithTitle)}
      <div><Label>{t.christian}</Label><Chips options={pairs(CHRISTIAN, t.christianOptions)} value={form.faith_christian} onChange={(value) => set('faith_christian', value)} testId="kiosk-christian" /></div>
      <div><Label>{t.accept}</Label><Chips options={pairs(ACCEPT, t.acceptOptions)} value={form.accept_jesus} onChange={(value) => set('accept_jesus', value)} testId="kiosk-accept-jesus" /></div>
      <Wide><CheckChips cols={z.landscape ? 2 : 1} options={[['reconcile', t.reconcile], ['faith_info', t.faithInfo]]} value={['reconcile', 'faith_info'].filter((key) => form[key])}
        onChange={(value) => setForm((current) => ({ ...current, reconcile: value.includes('reconcile'), faith_info: value.includes('faith_info') }))} testId="kiosk-faith" /></Wide>
      <Wide><Label>{t.otherChurch}</Label>
        <div style={{ maxWidth: z.landscape ? '50%' : '100%' }}><YesNo t={t} value={form.other_church} onChange={(value) => set('other_church', value)} testId="kiosk-other-church" /></div>
        {form.other_church && inlinePair(
          lineInput({ value: form.other_church_name, onChange: (event) => set('other_church_name', event.target.value), placeholder: t.churchName, 'aria-label': t.churchName, 'data-testid': 'kiosk-other-church-name' }),
          lineInput({ value: form.other_church_pastor, onChange: (event) => set('other_church_pastor', event.target.value), placeholder: t.pastorName, 'aria-label': t.pastorName, 'data-testid': 'kiosk-other-church-pastor' }),
        )}</Wide></Section>,
    familia: <Section testId="kiosk-step-familia">{title(t.familyTitle)}
      <div><Label>{t.marital}</Label><Chips options={pairs(MARITAL, t.maritalOptions)} value={form.marital_status} onChange={(value) => set('marital_status', value)} testId="kiosk-marital" /></div>
      {form.marital_status === 'married' && <label style={{ display: 'block' }}><Label>{t.spouse}</Label>{lineInput({ value: form.spouse_name, onChange: (event) => set('spouse_name', event.target.value), 'aria-label': t.spouse, 'data-testid': 'kiosk-spouse' })}</label>}
      <div><Label>{t.hasChildren}</Label><YesNo t={t} value={form.has_children} onChange={(value) => setForm((current) => ({ ...current, has_children: value, children: value && !current.children.length ? [{ name: '', age: '' }] : current.children }))} testId="kiosk-has-children" /></div>
      <Field label={t.companions} value={form.companions} onChange={(value) => set('companions', value)} placeholder={t.companionsHint} testId="kiosk-companions" />
      {form.has_children && <Wide><div data-testid="kiosk-children" style={{ display: 'flex', flexWrap: 'wrap', margin: `0 -${Math.round(z.chip / 2)}px -${z.chip}px` }}>
        {form.children.map((child, index) => (
          <div key={index} style={{ width: z.landscape ? '50%' : '100%', padding: `0 ${Math.round(z.chip / 2)}px`, marginBottom: z.chip, boxSizing: 'border-box', display: 'flex', alignItems: 'center' }}>
            {lineInput({ value: child.name, onChange: (event) => setChild(index, 'name', event.target.value), placeholder: t.childName(index + 1), 'aria-label': t.childName(index + 1), 'data-testid': `kiosk-child-name-${index}`, style: { flex: '1 1 auto', width: 'auto', minWidth: 0 } })}
            {lineInput({ value: child.age, onChange: (event) => setChild(index, 'age', event.target.value.replace(/\D/g, '').slice(0, 2)), inputMode: 'numeric', placeholder: t.age, 'aria-label': t.childAge(index + 1), 'data-testid': `kiosk-child-age-${index}`, style: { flex: `0 0 ${Math.round(120 * z.scale)}px`, width: Math.round(120 * z.scale), marginLeft: z.chip } })}
            <button type="button" onClick={() => set('children', form.children.filter((_, position) => position !== index))} aria-label={t.removeChild(index + 1)} title={t.remove}
              style={{ flex: `0 0 ${z.input}px`, width: z.input, height: z.input, marginLeft: z.chip, borderRadius: z.radius, border: `2px solid ${C.line}`, background: '#fff', color: C.ink, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}><X size={Math.round(z.input * 0.4)} aria-hidden /></button>
          </div>
        ))}
      </div></Wide>}
      {/* «Agregar otro hijo» y «ministerio de niños» en un renglón (en horizontal) para que todo quepa. */}
      <Wide><div style={{ display: 'flex', flexDirection: z.landscape ? 'row' : 'column', alignItems: z.landscape ? 'center' : 'stretch' }}>
        {form.has_children && <div style={{ flex: '0 0 auto', margin: z.landscape ? `0 ${z.chip}px 0 0` : `0 0 ${z.space}px` }}><Big kind="secondary" full={!z.landscape} onClick={() => set('children', [...form.children, { name: '', age: '' }])} testId="kiosk-child-add">+ {t.addChild}</Big></div>}
        <div style={{ flex: '1 1 auto', minWidth: 0 }}><CheckChips options={[['kids', t.kids]]} value={form.kids_ministry ? ['kids'] : []} onChange={(value) => set('kids_ministry', value.includes('kids'))} testId="kiosk-kids-ministry" /></div>
      </div></Wide></Section>,
    // Renglones grandes alineados: 2 columnas en horizontal, 1 en vertical; subtítulos cortos.
    servir: <div data-testid="kiosk-step-servir">{title(t.serveTitle, t.serveHint)}
      <div style={{ marginTop: Math.round(z.space * (z.landscape ? 0.6 : 1)) }} data-testid="kiosk-requests">
        {columns(<>{group(...SERVE_GROUPS[0])}{group(...SERVE_GROUPS[1])}</>, group(...SERVE_GROUPS[2]))}
      </div></div>,
    // Consejería y ayuda; «Prefiero no recibir seguimiento» va aparte, al final.
    ayuda: <div data-testid="kiosk-step-ayuda">{title(t.serveGroups.counseling, t.serveHint)}
      <div style={{ marginTop: z.space }} data-testid="kiosk-requests-help">
        {columns(rows(HELP_KEYS.slice(0, z.landscape ? 3 : 5)), <>{z.landscape && rows(HELP_KEYS.slice(3))}</>)}
        <div style={{ marginTop: Math.round(z.space * 0.6), paddingTop: Math.round(z.space * 0.6), borderTop: `2px solid ${C.line}` }}>
          <CheckRow on={form.requests.includes('no_followup')} label={t.requests.no_followup} onClick={() => toggleRequest('no_followup')} testId="kiosk-requests-no_followup" />
        </div>
      </div></div>,
    notas: <Section testId="kiosk-step-notas">{title(t.notesTitle, t.notesHint)}
      {form.requests.some((item) => PRAYER.includes(item)) && <div><Area label={t.prayerWhy} hint={t.prayerOnly} value={form.prayer_request} onChange={(value) => set('prayer_request', value)} testId="kiosk-prayer" /></div>}
      {form.requests.some((item) => item.startsWith('counseling')) && <div><Area label={t.counselingTell} hint={t.counselingOnly} value={form.counseling_note} onChange={(value) => set('counseling_note', value)} testId="kiosk-counseling" /></div>}
      {form.requests.some((item) => ['support_child', 'other_help'].includes(item)) && <div><Area label={t.needsWhat} hint={t.confidential} value={form.needs_note} onChange={(value) => set('needs_note', value)} testId="kiosk-needs" /></div>}</Section>,
    apoyo: <Section testId="kiosk-step-apoyo">{title(t.givingTitle)}
      <Wide><CheckChips options={[['giving', t.giving]]} value={form.giving_info ? ['giving'] : []} onChange={(value) => set('giving_info', value.includes('giving'))} testId="kiosk-giving" /></Wide>
      <Wide><p style={{ margin: 0, fontSize: z.text, color: C.muted, lineHeight: 1.4 }}>{t.givingNote}</p></Wide></Section>,
    cierre: <Section testId="kiosk-step-cierre">{title(t.closeTitle)}
      <Wide><div style={{ maxWidth: z.landscape ? '50%' : '100%' }}><YesNo t={t} value={form.consent_followup} onChange={(value) => set('consent_followup', value)} testId="kiosk-consent-followup" /></div></Wide>
      {missingContact && (
        <Wide><div data-testid="kiosk-need-contact">
          <p style={{ margin: `0 0 ${z.chip}px`, fontSize: z.text, color: C.goldDark, fontWeight: 700, lineHeight: 1.35 }}>{t.needContact}</p>
          <Big kind="secondary" onClick={() => setStep(order.indexOf('contacto'))} testId="kiosk-add-contact">{t.addContact}</Big>
        </div></Wide>
      )}
      <Wide><ul style={{ margin: 0, padding: 0, listStyle: 'none' }} data-testid="kiosk-privacy">
        {phrases(texts.privacy).map((line, index) => {
          const Icon = [Lock, Users, HeartHandshake][index % 3];
          return <li key={line} style={{ display: 'flex', alignItems: 'flex-start', marginBottom: Math.round(z.space * 0.5), fontSize: z.text, lineHeight: 1.4, color: C.muted }}><Icon size={Math.round(z.text * 1.2)} color={C.goldDark} aria-hidden style={{ flex: '0 0 auto', marginTop: 2, marginRight: 14 }} /><span>{line}</span></li>;
        })}
      </ul></Wide>
      {error && <p className="vk-wide" style={{ fontSize: z.text, color: '#B42318' }}>{error}</p>}</Section>,
  }[stepKey];
  return shell(body, footer);
}
