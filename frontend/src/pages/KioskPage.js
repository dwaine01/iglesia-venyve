import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { Church, HeartHandshake } from 'lucide-react';

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
const STEPS = ['Aviso', 'Tu nombre', 'Contacto', 'Tu visita', 'Familia', 'Cómo servirte', 'Seguimiento', 'Revisar'];

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
const Accent = () => <span aria-hidden style={{ display: 'block', width: 72, height: 4, borderRadius: 4, background: C.gold, margin: '18px auto' }} />;
const Section = ({ children, testId }) => <div style={{ display: 'grid', gap: 22 }} data-testid={testId}>{children}</div>;

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

  const canNext = () => (step === 1 ? form.first_name.trim() && form.last_name.trim() : true);
  const shell = (children, footer = null) => (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.ink, fontFamily: 'Inter, system-ui, sans-serif', display: 'flex', flexDirection: 'column', userSelect: 'none' }} data-testid="kiosk-page" onContextMenu={(event) => event.preventDefault()}>
      <header style={{ background: 'linear-gradient(90deg, #14213D 0%, #1B2A4A 60%, #0E5B5A 100%)', color: '#fff', padding: '14px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 44, height: 44, borderRadius: 999, border: '2px solid #E7D28D' }}><Church size={24} color="#E7D28D" aria-hidden /></span>
        {config && <span style={{ fontSize: 19, color: 'rgba(255,255,255,0.9)', textAlign: 'right' }}>{config.service.label}{pending ? ` · ${pending} registro(s) esperando internet` : ''}</span>}
      </header>
      <main style={{ flex: 1, width: '100%', maxWidth: 860, margin: '0 auto', padding: '28px 24px 150px', boxSizing: 'border-box' }}>{children}</main>
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
      <div style={{ textAlign: 'center', marginTop: 24 }} data-testid="kiosk-confirmation">
        <p style={{ fontSize: 44, fontWeight: 800, margin: 0, fontFamily: 'Spectral, Georgia, serif', lineHeight: 1.15 }}>¡Gracias, {result.greeting_name}!</p>
        <Accent />
        {result.offline
          ? <p style={{ fontSize: 24, margin: '20px 0', color: C.goldDark, fontWeight: 700 }} data-testid="kiosk-offline">Tu registro quedó guardado en esta tableta y se enviará apenas vuelva el internet. Un servidor te dará tu número.</p>
          : <div style={{ background: '#fff', border: `2px solid ${C.gold}`, borderRadius: 24, padding: '20px 16px', margin: '8px auto 24px', maxWidth: 560 }}>
              <p style={{ fontSize: 22, margin: 0, color: C.muted }}>Tu número de registro</p>
              <p style={{ fontSize: 'min(64px, 10vw)', whiteSpace: 'nowrap', fontWeight: 800, letterSpacing: '0.04em', margin: '6px 0 0', color: C.navy }} data-testid="kiosk-number">{result.visitor_number}</p>
            </div>}
        <div style={{ display: 'grid', gap: 10, margin: '0 auto 28px', maxWidth: 680 }}>{extra.map((line) => <p key={line} style={{ fontSize: 24, lineHeight: 1.35, margin: 0 }}>{line}</p>)}</div>
        <Big onClick={reset} testId="kiosk-done">Listo</Big>
      </div>,
    );
  }

  // ---------------------------------------------------------------- inicio
  if (step < 0) {
    const [title, subtitle, ...lines] = phrases(config.texts.welcome);
    return shell(
      <div style={{ textAlign: 'center', marginTop: 12 }} data-testid="kiosk-start">
        <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 84, height: 84, borderRadius: 999, background: C.goldSoft, border: `3px solid ${C.gold}` }}><HeartHandshake size={44} color={C.goldDark} aria-hidden /></span>
        <h1 style={{ fontSize: 'clamp(36px, 6vw, 54px)', margin: '22px 0 0', fontFamily: 'Spectral, Georgia, serif', lineHeight: 1.12, color: C.navy }} data-testid="kiosk-title">{title}</h1>
        <Accent />
        {subtitle && <p style={{ fontSize: 'clamp(26px, 4vw, 34px)', margin: 0, color: C.goldDark, fontWeight: 700 }} data-testid="kiosk-subtitle">{subtitle}</p>}
        {lines.length > 0 && (
          <div style={{ display: 'grid', gap: 14, maxWidth: 680, margin: '30px auto 0' }} data-testid="kiosk-phrases">
            {lines.map((line) => <p key={line} style={{ margin: 0, fontSize: 'clamp(23px, 3.4vw, 28px)', lineHeight: 1.35, background: '#fff', border: `2px solid ${C.line}`, borderLeft: `6px solid ${C.gold}`, borderRadius: 18, padding: '16px 20px' }}>{line}</p>)}
          </div>
        )}
        <button type="button" onClick={() => { setForm(emptyForm()); setStep(0); lastTouch.current = Date.now(); }} data-testid="kiosk-begin"
          style={{ marginTop: 36, minHeight: 104, padding: '0 64px', borderRadius: 28, fontSize: 34, fontWeight: 800, background: C.gold, color: C.navy, border: 'none', boxShadow: '0 8px 24px rgba(20,33,61,0.25)' }}>Iniciar registro</button>
        <p style={{ marginTop: 28, fontSize: 15, color: C.muted }}>{device}</p>
      </div>,
    );
  }

  // ---------------------------------------------------------------- pasos
  const footer = (
    <>
      <Big kind="secondary" onClick={() => (step === 0 ? reset() : setStep(step - 1))} testId="kiosk-back">{step === 0 ? 'Cancelar' : 'Atrás'}</Big>
      {step < STEPS.length - 1
        ? <Big onClick={() => { if (step === 0) set('privacy_accepted', true); setStep(step + 1); }} disabled={!canNext()} testId="kiosk-next">{step === 0 ? 'Acepto y continuar' : 'Siguiente'}</Big>
        : <Big onClick={submit} disabled={saving} testId="kiosk-submit">{saving ? 'Guardando…' : 'Terminar registro'}</Big>}
    </>
  );
  const title = (text, sub) => (
    <div style={{ marginBottom: 6 }}>
      <p style={{ fontSize: 18, color: C.goldDark, fontWeight: 700, margin: 0 }}>Paso {step + 1} de {STEPS.length}</p>
      <h2 style={{ fontSize: 34, margin: '6px 0 0', fontFamily: 'Spectral, Georgia, serif', lineHeight: 1.15 }}>{text}</h2>
      {sub && <p style={{ fontSize: 20, color: C.muted, margin: '8px 0 0' }}>{sub}</p>}
    </div>
  );
  const body = {
    0: <Section testId="kiosk-step-0">{title('Antes de empezar', 'Así cuidamos tus datos:')}
      <ul style={{ display: 'grid', gap: 12, margin: 0, padding: 0, listStyle: 'none' }} data-testid="kiosk-privacy">
        {phrases(config.texts.privacy).map((line) => <li key={line} style={{ fontSize: 23, lineHeight: 1.35, background: '#fff', border: `2px solid ${C.line}`, borderLeft: `6px solid ${C.gold}`, borderRadius: 16, padding: '14px 18px' }}>{line}</li>)}
      </ul></Section>,
    1: <Section testId="kiosk-step-1">{title('¿Cómo te llamas?')}
      <Field label="Nombre" value={form.first_name} onChange={(value) => set('first_name', value)} testId="kiosk-first-name" />
      <Field label="Apellido" value={form.last_name} onChange={(value) => set('last_name', value)} testId="kiosk-last-name" />
      <Field label="¿Cómo te gusta que te llamen?" optional value={form.preferred_name} onChange={(value) => set('preferred_name', value)} placeholder="Ej.: Toño" testId="kiosk-preferred" />
      {/* Campo trampa: invisible para personas; los robots lo llenan. */}
      <input type="text" name="website" value={form.website} onChange={(event) => set('website', event.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true"
        style={{ position: 'absolute', left: '-10000px', width: 1, height: 1, opacity: 0 }} data-testid="kiosk-website" /></Section>,
    2: <Section testId="kiosk-step-2">{title('¿Cómo te contactamos?', 'Todo es opcional.')}
      <Field label="Teléfono" optional type="tel" value={form.phone} onChange={(value) => set('phone', value)} testId="kiosk-phone" />
      <div><Label optional>Forma preferida</Label><Chips options={CONTACT} value={form.contact_method} onChange={(value) => set('contact_method', value)} testId="kiosk-contact-method" /></div>
      <Field label="Correo electrónico" optional type="email" value={form.email} onChange={(value) => set('email', value)} testId="kiosk-email" />
      <Field label="Ciudad o zona donde vives" optional value={form.city} onChange={(value) => set('city', value)} testId="kiosk-city" />
      <Field label="Dirección completa" optional value={form.address} onChange={(value) => set('address', value)} testId="kiosk-address" /></Section>,
    3: <Section testId="kiosk-step-3">{title('Sobre tu visita', 'Todo es opcional.')}
      <div><Label optional>¿Es tu primera visita?</Label><YesNo value={form.first_visit} onChange={(value) => set('first_visit', value)} testId="kiosk-first-visit" /></div>
      <div><Label optional>¿Alguien te invitó?</Label><YesNo value={form.invited} onChange={(value) => set('invited', value)} testId="kiosk-invited" /></div>
      {form.invited && <Field label="¿Quién te invitó?" optional value={form.invited_by} onChange={(value) => set('invited_by', value)} testId="kiosk-invited-by" />}
      <Field label="¿De dónde nos visitas?" optional value={form.visiting_from} onChange={(value) => set('visiting_from', value)} placeholder="Ciudad, país o iglesia" testId="kiosk-from" />
      <div><Label optional>¿Asistes a otra iglesia?</Label><YesNo value={form.other_church} onChange={(value) => set('other_church', value)} testId="kiosk-other-church" /></div>
      {form.other_church && <Field label="¿Cuál?" optional value={form.other_church_name} onChange={(value) => set('other_church_name', value)} testId="kiosk-other-church-name" />}
      <div><Label optional>¿Cómo supiste de nosotros?</Label><Chips options={HEARD.map((item) => [item, item])} value={form.how_heard || null} onChange={(value) => set('how_heard', value || '')} testId="kiosk-heard" /></div>
      <Field label="Fecha de nacimiento" optional type="date" value={form.birth_date} onChange={(value) => set('birth_date', value)} testId="kiosk-birth" /></Section>,
    4: <Section testId="kiosk-step-4">{title('¿Vienes con familiares?', 'Opcional.')}
      {form.family.map((member, index) => (
        <div key={index} style={{ display: 'grid', gap: 12, background: '#fff', border: `2px solid ${C.line}`, borderRadius: 16, padding: 16 }}>
          <Field label={`Nombre del familiar ${index + 1}`} value={member.name} onChange={(value) => set('family', form.family.map((item, position) => (position === index ? { ...item, name: value } : item)))} testId={`kiosk-family-name-${index}`} />
          <Chips options={[['Esposo o esposa', 'Esposo o esposa'], ['Hijo o hija', 'Hijo o hija'], ['Padre o madre', 'Padre o madre'], ['Otro familiar', 'Otro familiar']]} value={member.relation} onChange={(value) => set('family', form.family.map((item, position) => (position === index ? { ...item, relation: value, is_minor: value === 'Hijo o hija' ? item.is_minor : false } : item)))} />
          {member.relation === 'Hijo o hija' && <div><Label>¿Es menor de edad?</Label><YesNo value={member.is_minor} onChange={(value) => set('family', form.family.map((item, position) => (position === index ? { ...item, is_minor: Boolean(value) } : item)))} /></div>}
          <Big kind="secondary" onClick={() => set('family', form.family.filter((_, position) => position !== index))}>Quitar</Big>
        </div>
      ))}
      {form.family.length < 8 && <Big kind="secondary" onClick={() => set('family', [...form.family, { name: '', relation: null, is_minor: false }])} testId="kiosk-family-add">Agregar un familiar</Big>}</Section>,
    5: <Section testId="kiosk-step-5">{title('¿Cómo podemos servirte?', 'Elige lo que quieras. Es opcional y confidencial.')}
      <Chips multiple options={REQUESTS} value={form.requests} onChange={(value) => set('requests', value)} testId="kiosk-requests" />
      {form.requests.includes('prayer') && <Area label="Tu petición de oración" hint="Solo la verá el equipo de oración." value={form.prayer_request} onChange={(value) => set('prayer_request', value)} testId="kiosk-prayer" />}
      {form.requests.some((item) => item.startsWith('counseling')) && <Area label="Cuéntanos brevemente" hint="Solo lo verá el equipo pastoral." value={form.counseling_note} onChange={(value) => set('counseling_note', value)} testId="kiosk-counseling" />}
      {form.requests.some((item) => ['support_child', 'other_help'].includes(item)) && <Area label="¿En qué te podemos ayudar?" hint="Confidencial." value={form.needs_note} onChange={(value) => set('needs_note', value)} testId="kiosk-needs" />}</Section>,
    6: <Section testId="kiosk-step-6">{title('¿Podemos comunicarnos contigo para darte seguimiento?', 'Opcional.')}
      <YesNo value={form.consent_followup} onChange={(value) => set('consent_followup', value)} testId="kiosk-consent-followup" /></Section>,
    7: <Section testId="kiosk-step-7">{title('Revisa tus datos')}
      <dl style={{ display: 'grid', gap: 14, fontSize: 22, background: '#fff', border: `2px solid ${C.line}`, borderRadius: 16, padding: 20, margin: 0 }}>
        {[['Nombre', `${form.first_name} ${form.last_name}`], ['Te llamaremos', form.preferred_name || form.first_name], ['Teléfono', form.phone], ['Ciudad o zona', form.city],
          ['Cómo podemos servirte', form.requests.map((key) => REQUESTS.find(([value]) => value === key)?.[1]).join(', ')],
          ['Seguimiento', form.consent_followup === true ? 'Sí' : form.consent_followup === false ? 'No' : null]]
          .filter(([, value]) => value).map(([label, value]) => <div key={label}><dt style={{ fontWeight: 700, color: C.muted, fontSize: 19 }}>{label}</dt><dd style={{ margin: '2px 0 0' }}>{value}</dd></div>)}
      </dl>
      {error && <p style={{ fontSize: 20, color: '#B42318' }}>{error}</p>}</Section>,
  }[step];
  return shell(body, footer);
}
