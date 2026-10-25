import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { HeartHandshake, Lock, Users } from 'lucide-react';

import { enqueue, flush, pendingCount } from '../lib/kioskQueue';

/* Quiosco de registro de visitantes (/quiosco/<enlace>). Un único enlace para
 * todas las tabletas: sin código, sin sesión. El enlace solo permite CREAR
 * registros. Cada tableta se nombra sola («Tableta 3F9A») para trazabilidad.
 * Nada del visitante se guarda en el navegador salvo, si falla el internet, en la
 * cola cifrada hasta enviarse. Reinicio por inactividad. */

const API = process.env.REACT_APP_BACKEND_URL;
const NAME_KEY = 'vv_tablet_name';
const IDLE_WARN = 60;
const IDLE_RESET = 75;
const CONFIRM_RESET = 25;
const C = { navy: '#14213D', ink: '#101D36', gold: '#C8A951', goldDark: '#8A6A1F', goldSoft: '#F6EEDA', bg: '#F7F5EF', line: '#DDD6C6', muted: '#475467' };

const CONTACT = [['call', 'Llamada'], ['whatsapp', 'WhatsApp'], ['text', 'Mensaje de texto'], ['email', 'Correo electrónico']];
const HEARD = ['Un amigo o familiar', 'Redes sociales', 'Pasaba por aquí', 'Visitaron mi casa (invasión)', 'Internet o Google', 'Otro'];
const REQUESTS = [['prayer', 'Oración'], ['visit', 'Una visita'], ['info', 'Información de la iglesia'], ['counseling_personal', 'Consejería personal'], ['counseling_marriage', 'Consejería matrimonial'],
  ['counseling_family', 'Consejería familiar'], ['support_child', 'Apoyo para un hijo o familiar'], ['other_help', 'Otro tipo de ayuda']];
// Pasos en orden; «notas» solo aparece si eligió oración, consejería o ayuda (así ninguna pantalla necesita desplazarse).
const needsNotes = (requests) => requests.some((item) => item === 'prayer' || item.startsWith('counseling') || ['support_child', 'other_help'].includes(item));
const stepOrder = (form) => ['aviso', 'nombre', 'contacto', 'visita', 'familia', 'servir', ...(needsNotes(form.requests) ? ['notas'] : []), 'seguimiento', 'revisar'];

const emptyForm = () => ({
  idempotency_key: (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).replace(/[^a-zA-Z0-9-]/g, '') + Date.now().toString(36),
  started_at: new Date().toISOString(), privacy_accepted: false, first_name: '', last_name: '', preferred_name: '', phone: '', email: '', contact_method: null, city: '', address: '',
  birth_date: '', first_visit: null, invited: null, invited_by: '', visiting_from: '', other_church: null, other_church_name: '', how_heard: '', family: [], requests: [],
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
const Label = ({ children, optional }) => <span style={{ display: 'block', fontSize: 21, fontWeight: 700, color: C.ink, marginBottom: 8 }}>{children}{optional && <span style={{ fontWeight: 500, color: C.muted }}> (opcional)</span>}</span>;
const inputStyle = { width: '100%', minHeight: 62, borderRadius: 14, border: `2px solid ${C.line}`, padding: '0 16px', fontSize: 22, background: '#fff', color: C.ink, boxSizing: 'border-box' };
function Field({ label, optional, value, onChange, type = 'text', placeholder, testId, autoComplete = 'off' }) {
  return <label style={{ display: 'block' }}><Label optional={optional}>{label}</Label><input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} autoComplete={autoComplete} style={inputStyle} data-testid={testId} /></label>;
}
function Area({ label, value, onChange, testId, hint }) {
  return <label style={{ display: 'block' }}><Label optional>{label}</Label>{hint && <span style={{ display: 'block', fontSize: 18, color: C.muted, marginBottom: 8 }}>{hint}</span>}<textarea value={value} onChange={(event) => onChange(event.target.value)} rows={3} style={{ ...inputStyle, minHeight: 110, padding: 14 }} data-testid={testId} /></label>;
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
const YesNo = ({ value, onChange, testId }) => <Chips options={[[true, 'Sí'], [false, 'No']]} value={value} onChange={onChange} testId={testId} />;
// Sí/No con su detalle en la MISMA fila (al decir «Sí» no crece la pantalla).
function YesNoDetail({ value, onChange, testId, detail, onDetail, placeholder, detailTestId }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
      <YesNo value={value} onChange={onChange} testId={testId} />
      {value && <input value={detail} onChange={(event) => onDetail(event.target.value)} placeholder={placeholder} autoComplete="off" aria-label={placeholder} style={{ ...inputStyle, flex: '1 1 220px', width: 'auto', minWidth: 0 }} data-testid={detailTestId} />}
    </div>
  );
}
const Accent = () => <span aria-hidden style={{ display: 'block', width: 88, height: 2, background: C.gold, margin: 'clamp(10px, 2vh, 18px) auto' }} />;
// En horizontal los campos van en dos columnas para que todo quepa sin desplazar.
const Section = ({ children, testId }) => <div className="vk-grid" data-testid={testId}>{children}</div>;
const Wide = ({ children }) => <div className="vk-wide">{children}</div>;
const LOGO = { src: '/logo-iglesia.png', srcSet: '/logo-iglesia.png 1x, /logo-iglesia@2x.png 2x', alt: 'Primera Iglesia del Nazareno · Casa de oración Ven y Ve' };
const KIOSK_CSS = `
  .vk-grid { display: grid; gap: clamp(14px, 2.2vh, 22px); align-content: start; }
  @media (orientation: landscape) and (min-width: 900px) {
    .vk-grid { grid-template-columns: 1fr 1fr; column-gap: 36px; }
    .vk-wide { grid-column: 1 / -1; }
  }
`;

export default function KioskPage() {
  const { token } = useParams();
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
    ['pointerdown', 'keydown', 'touchstart'].forEach((name) => window.addEventListener(name, touch, { passive: true }));
    const timer = setInterval(() => {
      const seconds = Math.floor((Date.now() - lastTouch.current) / 1000);
      if (result && seconds >= CONFIRM_RESET) { reset(); lastTouch.current = Date.now(); return; }
      if (step >= 0 && !result) { if (seconds >= IDLE_RESET) { reset(); lastTouch.current = Date.now(); } else setIdle(seconds); }
    }, 1000);
    return () => { clearInterval(timer); ['pointerdown', 'keydown', 'touchstart'].forEach((name) => window.removeEventListener(name, touch)); };
  }, [step, result, reset]);

  const submit = async () => {
    setSaving(true); setError('');
    const payload = {
      ...form, privacy_accepted: true, privacy_version: config.texts.privacy_version, birth_date: form.birth_date || null, contact_method: form.contact_method || null,
      family: form.family.filter((item) => item.name.trim()), ...(form.invited ? {} : { invited_by: '' }), ...(form.other_church ? {} : { other_church_name: '' }),
    };
    Object.keys(payload).forEach((key) => { if (payload[key] === '') payload[key] = null; });
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
  const canNext = () => (stepKey === 'nombre' ? form.first_name.trim() && form.last_name.trim() : true);
  const shell = (children, footer = null, hideLogo = false) => (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.ink, fontFamily: 'Inter, system-ui, sans-serif', display: 'flex', flexDirection: 'column', userSelect: 'none' }} data-testid="kiosk-page" onContextMenu={(event) => event.preventDefault()}>
      <style>{KIOSK_CSS}</style>
      {/* Barra clara: el logo (letras verdes y azules) se ve nítido; en la bienvenida no se repite. */}
      <header style={{ background: '#fff', borderBottom: `2px solid ${C.gold}`, padding: '8px 24px', minHeight: 64, boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        {!hideLogo ? <img {...LOGO} style={{ height: 48, width: 'auto' }} data-testid="kiosk-header-logo" /> : <span />}
        {config && <span style={{ fontSize: 19, color: C.muted, textAlign: 'right' }}>{config.service.label}{pending ? ` · ${pending} registro(s) esperando internet` : ''}</span>}
      </header>
      <main style={{ flex: 1, width: '100%', maxWidth: hideLogo || result ? 1040 : 1120, margin: '0 auto', padding: `clamp(14px, 3vh, 28px) 24px ${footer ? 120 : 24}px`, boxSizing: 'border-box' }}>{children}</main>
      {footer && <footer style={{ position: 'fixed', left: 0, right: 0, bottom: 0, background: '#fff', borderTop: `2px solid ${C.line}`, padding: 16, display: 'flex', justifyContent: 'space-between', gap: 12 }}>{footer}</footer>}
      {idle >= IDLE_WARN && step >= 0 && !result && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(20,33,61,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }} data-testid="kiosk-idle">
          <div style={{ background: '#fff', borderRadius: 24, padding: 32, maxWidth: 560, textAlign: 'center' }}>
            <p style={{ fontSize: 30, fontWeight: 800, margin: 0 }}>¿Sigues ahí?</p>
            <p style={{ fontSize: 21, color: C.muted }}>Por tu privacidad, el registro se borrará en {Math.max(0, IDLE_RESET - idle)} segundos.</p>
            <Big onClick={() => { lastTouch.current = Date.now(); setIdle(0); }} testId="kiosk-continue">Continuar mi registro</Big>
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
      <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 140px)' }} data-testid="kiosk-confirmation">
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
      <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 140px)' }} data-testid="kiosk-start">
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
        ? <Big onClick={() => { if (step === 0) set('privacy_accepted', true); setStep(step + 1); }} disabled={!canNext()} testId="kiosk-next">{step === 0 ? 'Acepto y continuar' : 'Siguiente'}</Big>
        : <Big onClick={submit} disabled={saving} testId="kiosk-submit">{saving ? 'Guardando…' : 'Terminar registro'}</Big>}
    </>
  );
  const title = (text, sub) => (
    <div className="vk-wide" style={{ marginBottom: 4 }}>
      <p style={{ fontSize: 18, color: C.goldDark, fontWeight: 700, margin: 0 }}>Paso {step + 1} de {order.length}</p>
      <h2 style={{ fontSize: 'clamp(28px, 4.4vh, 36px)', margin: '4px 0 0', fontFamily: 'Spectral, Georgia, serif', fontWeight: 600, lineHeight: 1.15, color: C.navy }}>{text}</h2>
      {sub && <p style={{ fontSize: 20, color: C.muted, margin: '6px 0 0' }}>{sub}</p>}
    </div>
  );
  const body = {
    aviso: <Section testId="kiosk-step-aviso">{title('Antes de empezar', 'Así cuidamos tus datos:')}
      <Wide><ul style={{ display: 'grid', gap: 'clamp(18px, 3.4vh, 34px)', margin: '8px 0 0', padding: 0, listStyle: 'none', maxWidth: 820 }} data-testid="kiosk-privacy">
        {phrases(config.texts.privacy).map((line, index) => {
          const Icon = [Lock, Users, HeartHandshake][index % 3];
          return <li key={line} style={{ display: 'flex', alignItems: 'flex-start', gap: 18, fontSize: 'clamp(23px, 3.4vh, 27px)', lineHeight: 1.35 }}><Icon size={30} color={C.goldDark} aria-hidden style={{ flex: '0 0 auto', marginTop: 3 }} /><span>{line}</span></li>;
        })}
      </ul></Wide></Section>,
    nombre: <Section testId="kiosk-step-nombre">{title('¿Cómo te llamas?')}
      <Field label="Nombre" value={form.first_name} onChange={(value) => set('first_name', value)} testId="kiosk-first-name" />
      <Field label="Apellido" value={form.last_name} onChange={(value) => set('last_name', value)} testId="kiosk-last-name" />
      <Field label="¿Cómo te gusta que te llamen?" optional value={form.preferred_name} onChange={(value) => set('preferred_name', value)} placeholder="Ej.: Toño" testId="kiosk-preferred" />
      <Field label="Fecha de nacimiento" optional type="date" value={form.birth_date} onChange={(value) => set('birth_date', value)} testId="kiosk-birth" />
      {/* Campo trampa: invisible para personas; los robots lo llenan. */}
      <input type="text" name="website" value={form.website} onChange={(event) => set('website', event.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true"
        style={{ position: 'absolute', left: '-10000px', width: 1, height: 1, opacity: 0 }} data-testid="kiosk-website" /></Section>,
    contacto: <Section testId="kiosk-step-contacto">{title('¿Cómo te contactamos?', 'Todo es opcional.')}
      <Field label="Teléfono" optional type="tel" value={form.phone} onChange={(value) => set('phone', value)} testId="kiosk-phone" />
      <div><Label optional>Forma preferida</Label><Chips options={CONTACT} value={form.contact_method} onChange={(value) => set('contact_method', value)} testId="kiosk-contact-method" /></div>
      <Field label="Correo electrónico" optional type="email" value={form.email} onChange={(value) => set('email', value)} testId="kiosk-email" />
      <Field label="Ciudad o zona donde vives" optional value={form.city} onChange={(value) => set('city', value)} testId="kiosk-city" />
      <Field label="Dirección completa" optional value={form.address} onChange={(value) => set('address', value)} testId="kiosk-address" /></Section>,
    visita: <Section testId="kiosk-step-visita">{title('Sobre tu visita', 'Todo es opcional.')}
      <div><Label optional>¿Es tu primera visita?</Label><YesNo value={form.first_visit} onChange={(value) => set('first_visit', value)} testId="kiosk-first-visit" /></div>
      <div><Label optional>¿Alguien te invitó?</Label><YesNoDetail value={form.invited} onChange={(value) => set('invited', value)} testId="kiosk-invited" detail={form.invited_by} onDetail={(value) => set('invited_by', value)} placeholder="¿Quién te invitó?" detailTestId="kiosk-invited-by" /></div>
      <Field label="¿De dónde nos visitas?" optional value={form.visiting_from} onChange={(value) => set('visiting_from', value)} placeholder="Ciudad, país o iglesia" testId="kiosk-from" />
      <div><Label optional>¿Asistes a otra iglesia?</Label><YesNoDetail value={form.other_church} onChange={(value) => set('other_church', value)} testId="kiosk-other-church" detail={form.other_church_name} onDetail={(value) => set('other_church_name', value)} placeholder="¿Cuál?" detailTestId="kiosk-other-church-name" /></div>
      <Wide><Label optional>¿Cómo supiste de nosotros?</Label><Chips options={HEARD.map((item) => [item, item])} value={form.how_heard || null} onChange={(value) => set('how_heard', value || '')} testId="kiosk-heard" /></Wide>
</Section>,
    familia: <Section testId="kiosk-step-familia">{title('¿Vienes con familiares?', 'Opcional.')}
      {form.family.map((member, index) => (
        <div key={index} className="vk-wide" style={{ display: 'grid', gap: 12, paddingTop: index ? 18 : 0, borderTop: index ? `1px solid ${C.line}` : 'none' }}>
          <Field label={`Nombre del familiar ${index + 1}`} value={member.name} onChange={(value) => set('family', form.family.map((item, position) => (position === index ? { ...item, name: value } : item)))} testId={`kiosk-family-name-${index}`} />
          <Chips options={[['Esposo o esposa', 'Esposo o esposa'], ['Hijo o hija', 'Hijo o hija'], ['Padre o madre', 'Padre o madre'], ['Otro familiar', 'Otro familiar']]} value={member.relation} onChange={(value) => set('family', form.family.map((item, position) => (position === index ? { ...item, relation: value, is_minor: value === 'Hijo o hija' ? item.is_minor : false } : item)))} />
          {member.relation === 'Hijo o hija' && <div><Label>¿Es menor de edad?</Label><YesNo value={member.is_minor} onChange={(value) => set('family', form.family.map((item, position) => (position === index ? { ...item, is_minor: Boolean(value) } : item)))} /></div>}
          <Big kind="secondary" onClick={() => set('family', form.family.filter((_, position) => position !== index))}>Quitar</Big>
        </div>
      ))}
      {form.family.length < 8 && <Wide><Big kind="secondary" onClick={() => set('family', [...form.family, { name: '', relation: null, is_minor: false }])} testId="kiosk-family-add">Agregar un familiar</Big></Wide>}</Section>,
    servir: <Section testId="kiosk-step-servir">{title('¿Cómo podemos servirte?', 'Elige lo que quieras. Es opcional y confidencial.')}
      <Wide><Chips multiple options={REQUESTS} value={form.requests} onChange={(value) => set('requests', value)} testId="kiosk-requests" /></Wide></Section>,
    notas: <Section testId="kiosk-step-notas">{title('Cuéntanos un poco más', 'Opcional y confidencial.')}
      {form.requests.includes('prayer') && <Area label="Tu petición de oración" hint="Solo la verá el equipo de oración." value={form.prayer_request} onChange={(value) => set('prayer_request', value)} testId="kiosk-prayer" />}
      {form.requests.some((item) => item.startsWith('counseling')) && <Area label="Cuéntanos brevemente" hint="Solo lo verá el equipo pastoral." value={form.counseling_note} onChange={(value) => set('counseling_note', value)} testId="kiosk-counseling" />}
      {form.requests.some((item) => ['support_child', 'other_help'].includes(item)) && <Area label="¿En qué te podemos ayudar?" hint="Confidencial." value={form.needs_note} onChange={(value) => set('needs_note', value)} testId="kiosk-needs" />}</Section>,
    seguimiento: <Section testId="kiosk-step-seguimiento">{title('¿Podemos comunicarnos contigo para darte seguimiento?', 'Opcional.')}
      <Wide><YesNo value={form.consent_followup} onChange={(value) => set('consent_followup', value)} testId="kiosk-consent-followup" /></Wide></Section>,
    revisar: <Section testId="kiosk-step-revisar">{title('Revisa tus datos')}
      <dl className="vk-grid vk-wide" style={{ fontSize: 23, margin: 0 }}>
        {[['Nombre', `${form.first_name} ${form.last_name}`], ['Te llamaremos', form.preferred_name || form.first_name], ['Teléfono', form.phone], ['Ciudad o zona', form.city],
          ['Cómo podemos servirte', form.requests.map((key) => REQUESTS.find(([value]) => value === key)?.[1]).join(', ')],
          ['Seguimiento', form.consent_followup === true ? 'Sí' : form.consent_followup === false ? 'No' : null]]
          .filter(([, value]) => value).map(([label, value]) => <div key={label} style={{ borderBottom: `1px solid ${C.line}`, paddingBottom: 10 }}><dt style={{ fontWeight: 700, color: C.muted, fontSize: 19 }}>{label}</dt><dd style={{ margin: '2px 0 0' }}>{value}</dd></div>)}
      </dl>
      {error && <p className="vk-wide" style={{ fontSize: 20, color: '#B42318' }}>{error}</p>}</Section>,
  }[stepKey];
  return shell(body, footer);
}
