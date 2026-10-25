import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';

import { enqueue, flush, pendingCount } from '../lib/kioskQueue';

/* Quiosco de registro de visitantes (/quiosco). Sin menú, sin sesión de
 * personal: la tableta usa SOLO su token de dispositivo (permiso único: crear
 * registros). Nada del visitante se guarda en el navegador salvo, si falla el
 * internet, en la cola cifrada hasta enviarse. Reinicio por inactividad. */

const API = process.env.REACT_APP_BACKEND_URL;
const DEVICE_KEY = 'vv_kiosk_device';
const IDLE_WARN = 60;
const IDLE_RESET = 75;
const CONFIRM_RESET = 25;
const C = { navy: '#14213D', ink: '#101D36', gold: '#C8A951', goldDark: '#8A6A1F', bg: '#F7F5EF', line: '#DDD6C6', muted: '#475467' };

const CONTACT = [['call', 'Llamada'], ['whatsapp', 'WhatsApp'], ['text', 'Mensaje de texto'], ['email', 'Correo electrónico'], ['none', 'Prefiero que no me contacten']];
const HEARD = ['Un amigo o familiar', 'Redes sociales', 'Pasaba por aquí', 'Visitaron mi casa (invasión)', 'Internet o Google', 'Otro'];
const REQUESTS = [['prayer', 'Oración'], ['visit', 'Una visita'], ['info', 'Información de la iglesia'], ['counseling_personal', 'Consejería personal'], ['counseling_marriage', 'Consejería matrimonial'],
  ['counseling_family', 'Consejería familiar'], ['support_child', 'Apoyo para un hijo o familiar'], ['other_help', 'Otro tipo de ayuda'], ['no_followup', 'Prefiero no recibir seguimiento por ahora']];
const STEPS = ['Bienvenida', 'Tu nombre', 'Cómo contactarte', 'Tu visita', 'Familia', 'Cómo podemos servirte', 'Tu autorización', 'Revisar'];

const emptyForm = () => ({
  idempotency_key: (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).replace(/[^a-zA-Z0-9-]/g, '') + Date.now().toString(36),
  started_at: new Date().toISOString(), privacy_accepted: false, first_name: '', last_name: '', preferred_name: '', phone: '', email: '', contact_method: null, city: '', address: '',
  birth_date: '', first_visit: null, invited: null, invited_by: '', visiting_from: '', other_church: null, other_church_name: '', how_heard: '', family: [], requests: [],
  prayer_request: '', counseling_note: '', needs_note: '', consent_followup: false, consent_announce: false, consent_screens: false, consent_family_announce: false,
});

const readDevice = () => { try { return JSON.parse(localStorage.getItem(DEVICE_KEY) || 'null'); } catch { return null; } };

// ---------------------------------------------------------------- piezas grandes (tableta)
const Big = ({ children, onClick, kind = 'primary', disabled, testId, type = 'button' }) => (
  <button type={type} onClick={onClick} disabled={disabled} data-testid={testId}
    style={{ minHeight: 64, padding: '0 28px', borderRadius: 16, fontSize: 22, fontWeight: 700, border: kind === 'primary' ? 'none' : `2px solid ${C.line}`,
      background: kind === 'primary' ? C.navy : '#fff', color: kind === 'primary' ? '#fff' : C.ink, opacity: disabled ? 0.45 : 1, cursor: disabled ? 'default' : 'pointer' }}>{children}</button>
);
const Label = ({ children, optional }) => <span style={{ display: 'block', fontSize: 20, fontWeight: 700, color: C.ink, marginBottom: 6 }}>{children}{optional && <span style={{ fontWeight: 500, color: C.muted }}> (opcional)</span>}</span>;
const inputStyle = { width: '100%', minHeight: 60, borderRadius: 14, border: `2px solid ${C.line}`, padding: '0 16px', fontSize: 22, background: '#fff', color: C.ink };
function Field({ label, optional, value, onChange, type = 'text', placeholder, testId, autoComplete = 'off' }) {
  return <label style={{ display: 'block' }}><Label optional={optional}>{label}</Label><input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} autoComplete={autoComplete} style={inputStyle} data-testid={testId} /></label>;
}
function Area({ label, value, onChange, testId, hint }) {
  return <label style={{ display: 'block' }}><Label optional>{label}</Label>{hint && <span style={{ display: 'block', fontSize: 17, color: C.muted, marginBottom: 6 }}>{hint}</span>}<textarea value={value} onChange={(event) => onChange(event.target.value)} rows={3} style={{ ...inputStyle, minHeight: 110, padding: 14 }} data-testid={testId} /></label>;
}
function Chips({ options, value, onChange, multiple, testId }) {
  const selected = (key) => (multiple ? value.includes(key) : value === key);
  const toggle = (key) => (multiple ? onChange(selected(key) ? value.filter((item) => item !== key) : [...value, key]) : onChange(selected(key) ? null : key));
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }} data-testid={testId}>
      {options.map(([key, label]) => <button key={key} type="button" onClick={() => toggle(key)} aria-pressed={selected(key)}
        style={{ minHeight: 58, padding: '0 20px', borderRadius: 999, fontSize: 20, fontWeight: 600, border: `2px solid ${selected(key) ? C.navy : C.line}`, background: selected(key) ? C.navy : '#fff', color: selected(key) ? '#fff' : C.ink }}>{label}</button>)}
    </div>
  );
}
const YesNo = ({ value, onChange, testId }) => <Chips options={[[true, 'Sí'], [false, 'No']]} value={value} onChange={onChange} testId={testId} />;
function Switch({ checked, onChange, label, help, testId }) {
  return (
    <button type="button" onClick={() => onChange(!checked)} aria-pressed={checked} data-testid={testId}
      style={{ display: 'flex', alignItems: 'center', gap: 16, width: '100%', textAlign: 'left', padding: 18, borderRadius: 16, border: `2px solid ${checked ? C.navy : C.line}`, background: checked ? '#EEF2FA' : '#fff' }}>
      <span style={{ flex: '0 0 auto', width: 64, height: 36, borderRadius: 999, background: checked ? C.navy : '#C9CDD6', position: 'relative' }}><span style={{ position: 'absolute', top: 4, left: checked ? 32 : 4, width: 28, height: 28, borderRadius: 999, background: '#fff', transition: 'left .15s' }} /></span>
      <span><span style={{ display: 'block', fontSize: 21, fontWeight: 700, color: C.ink }}>{label}</span>{help && <span style={{ display: 'block', fontSize: 17, color: C.muted, marginTop: 2 }}>{help}</span>}</span>
    </button>
  );
}

export default function KioskPage() {
  const [device, setDevice] = useState(readDevice);
  const [config, setConfig] = useState(null);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [step, setStep] = useState(-1);  // -1 = inicio
  const [form, setForm] = useState(emptyForm);
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [idle, setIdle] = useState(0);
  const [pending, setPending] = useState(0);
  const lastTouch = useRef(Date.now());
  const headers = device ? { 'X-Device-Token': device.token } : {};
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const reset = useCallback(() => { setForm(emptyForm()); setStep(-1); setResult(null); setError(''); setSaving(false); window.scrollTo(0, 0); }, []);
  const unpair = useCallback(() => { try { localStorage.removeItem(DEVICE_KEY); } catch { /* sin almacenamiento */ } setDevice(null); setConfig(null); }, []);

  // Configuración (textos y servicio de hoy). Si la tableta fue desactivada, vuelve a emparejar.
  const loadConfig = useCallback(() => {
    if (!device) return;
    axios.get(`${API}/api/kiosk/config`, { headers: { 'X-Device-Token': device.token } }).then((response) => setConfig(response.data))
      .catch((requestError) => { if (requestError?.response?.status === 401) unpair(); });
  }, [device, unpair]);
  useEffect(() => { loadConfig(); const timer = setInterval(loadConfig, 10 * 60 * 1000); return () => clearInterval(timer); }, [loadConfig]);

  // Cola sin internet: se reenvía con la misma clave de idempotencia.
  const send = useCallback(async (payload) => {
    try {
      return (await axios.post(`${API}/api/kiosk/registrations`, payload, { headers, timeout: 20000 })).data;
    } catch (requestError) {
      const status = requestError?.response?.status;
      if (status === 401) { unpair(); }
      if (status && status < 500) { const permanent = new Error(requestError.response.data?.detail || 'Error'); permanent.permanent = true; throw permanent; }
      throw requestError;
    }
  }, [device]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!device) return undefined;
    const tick = async () => { await flush(send); setPending(await pendingCount()); };
    tick(); const timer = setInterval(tick, 15000); window.addEventListener('online', tick);
    return () => { clearInterval(timer); window.removeEventListener('online', tick); };
  }, [device, send]);

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

  const pairDevice = async (event) => {
    event.preventDefault(); setError('');
    try {
      const response = await axios.post(`${API}/api/kiosk/pair`, { code, expected_kinds: ['tablet'] });
      const value = { token: response.data.token, name: response.data.device_name };
      try { localStorage.setItem(DEVICE_KEY, JSON.stringify(value)); } catch { /* sin almacenamiento */ }
      setDevice(value); setCode('');
    } catch (requestError) { setError(requestError?.response?.data?.detail || 'No se pudo emparejar. Revise el código y la conexión.'); }
  };

  const submit = async () => {
    setSaving(true); setError('');
    const payload = {
      ...form, privacy_version: config.texts.privacy_version, birth_date: form.birth_date || null, contact_method: form.contact_method || null,
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

  const canNext = () => {
    if (step === 0) return form.privacy_accepted;
    if (step === 1) return form.first_name.trim() && form.last_name.trim();
    return true;
  };
  const shell = (children, footer = null) => (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.ink, fontFamily: 'Inter, system-ui, sans-serif', display: 'flex', flexDirection: 'column', userSelect: 'none' }} data-testid="kiosk-page" onContextMenu={(event) => event.preventDefault()}>
      <header style={{ background: 'linear-gradient(90deg, #14213D 0%, #1B2A4A 60%, #0E5B5A 100%)', color: '#fff', padding: '18px 28px' }}>
        <p style={{ margin: 0, fontSize: 16, letterSpacing: '0.2em', color: '#E7D28D', fontWeight: 700, textTransform: 'uppercase' }}>Casa de Oración · Bienvenida</p>
        {config && <p style={{ margin: '4px 0 0', fontSize: 18, color: 'rgba(255,255,255,0.85)' }}>{config.service.label}{pending ? ` · ${pending} registro(s) esperando internet` : ''}</p>}
      </header>
      <main style={{ flex: 1, width: '100%', maxWidth: 900, margin: '0 auto', padding: '24px 24px 140px' }}>{children}</main>
      {footer && <footer style={{ position: 'fixed', left: 0, right: 0, bottom: 0, background: '#fff', borderTop: `2px solid ${C.line}`, padding: 16, display: 'flex', justifyContent: 'space-between', gap: 12 }}>{footer}</footer>}
      {idle >= IDLE_WARN && step >= 0 && !result && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(20,33,61,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }} data-testid="kiosk-idle">
          <div style={{ background: '#fff', borderRadius: 24, padding: 32, maxWidth: 560, textAlign: 'center' }}>
            <p style={{ fontSize: 28, fontWeight: 800, margin: 0 }}>¿Sigues ahí?</p>
            <p style={{ fontSize: 20, color: C.muted }}>Por tu privacidad, el registro se borrará en {Math.max(0, IDLE_RESET - idle)} segundos.</p>
            <Big onClick={() => { lastTouch.current = Date.now(); setIdle(0); }} testId="kiosk-continue">Continuar mi registro</Big>
          </div>
        </div>
      )}
    </div>
  );

  // ---------------------------------------------------------------- emparejar
  if (!device) {
    return shell(
      <form onSubmit={pairDevice} style={{ display: 'grid', gap: 20, marginTop: 40 }} data-testid="kiosk-pair">
        <h1 style={{ fontSize: 34, margin: 0, fontFamily: 'Spectral, Georgia, serif' }}>Emparejar esta tableta</h1>
        <p style={{ fontSize: 20, color: C.muted, margin: 0 }}>Escriba el código que aparece en el panel de administración (Registro de visitantes › Tabletas). Solo lo hace el personal autorizado.</p>
        <Field label="Código de emparejamiento" value={code} onChange={(value) => setCode(value.toUpperCase())} placeholder="Ej.: K7M2Q9XA" testId="kiosk-code" />
        {error && <p style={{ fontSize: 19, color: '#B42318', margin: 0 }}>{error}</p>}
        <Big type="submit" disabled={code.trim().length < 6} testId="kiosk-pair-submit">Emparejar tableta</Big>
      </form>,
    );
  }
  if (!config) return shell(<p style={{ fontSize: 22, marginTop: 40 }}>Preparando el registro…</p>);

  // ---------------------------------------------------------------- confirmación
  if (result) {
    return shell(
      <div style={{ textAlign: 'center', marginTop: 30 }} data-testid="kiosk-confirmation">
        <p style={{ fontSize: 40, fontWeight: 800, margin: 0, fontFamily: 'Spectral, Georgia, serif' }}>¡Gracias, {result.greeting_name}!</p>
        {result.offline
          ? <p style={{ fontSize: 24, margin: '20px 0', color: C.goldDark, fontWeight: 700 }} data-testid="kiosk-offline">Tu registro quedó guardado en esta tableta y se enviará apenas vuelva el internet. Un servidor te dará tu número.</p>
          : <><p style={{ fontSize: 22, margin: '18px 0 6px', color: C.muted }}>Tu número de registro es</p><p style={{ fontSize: 'min(64px, 10vw)', whiteSpace: 'nowrap', fontWeight: 800, letterSpacing: '0.04em', margin: 0, color: C.navy }} data-testid="kiosk-number">{result.visitor_number}</p></>}
        <p style={{ fontSize: 22, lineHeight: 1.4, margin: '24px auto', maxWidth: 680 }}>{result.confirmation}</p>
        <Big onClick={reset} testId="kiosk-done">Listo</Big>
      </div>,
    );
  }

  // ---------------------------------------------------------------- inicio
  if (step < 0) {
    return shell(
      <div style={{ textAlign: 'center', marginTop: 40 }} data-testid="kiosk-start">
        <h1 style={{ fontSize: 44, margin: 0, fontFamily: 'Spectral, Georgia, serif', lineHeight: 1.15 }}>¡Bienvenido!</h1>
        <p style={{ fontSize: 24, lineHeight: 1.4, maxWidth: 720, margin: '20px auto 36px' }}>{config.texts.welcome}</p>
        <button type="button" onClick={() => { setForm(emptyForm()); setStep(0); lastTouch.current = Date.now(); }} data-testid="kiosk-begin"
          style={{ minHeight: 110, padding: '0 64px', borderRadius: 28, fontSize: 36, fontWeight: 800, background: C.gold, color: C.navy, border: 'none', boxShadow: '0 8px 24px rgba(20,33,61,0.25)' }}>Iniciar registro</button>
      </div>,
    );
  }

  // ---------------------------------------------------------------- pasos
  const footer = (
    <>
      <Big kind="secondary" onClick={() => (step === 0 ? reset() : setStep(step - 1))} testId="kiosk-back">{step === 0 ? 'Cancelar' : 'Atrás'}</Big>
      {step < STEPS.length - 1
        ? <Big onClick={() => setStep(step + 1)} disabled={!canNext()} testId="kiosk-next">Siguiente</Big>
        : <Big onClick={submit} disabled={saving} testId="kiosk-submit">{saving ? 'Guardando…' : 'Terminar registro'}</Big>}
    </>
  );
  const title = (text, sub) => (
    <div style={{ marginBottom: 22 }}>
      <p style={{ fontSize: 17, color: C.goldDark, fontWeight: 700, margin: 0 }}>Paso {step + 1} de {STEPS.length}</p>
      <h2 style={{ fontSize: 32, margin: '4px 0 0', fontFamily: 'Spectral, Georgia, serif' }}>{text}</h2>
      {sub && <p style={{ fontSize: 19, color: C.muted, margin: '6px 0 0' }}>{sub}</p>}
    </div>
  );
  const body = {
    0: <div data-testid="kiosk-step-0">{title('Antes de empezar')}
      <p style={{ fontSize: 22, lineHeight: 1.45 }}>{config.texts.welcome}</p>
      <div style={{ background: '#fff', border: `2px solid ${C.line}`, borderRadius: 16, padding: 18, marginTop: 16 }}><p style={{ fontSize: 19, fontWeight: 700, margin: '0 0 6px' }}>Para qué usamos tus datos</p><p style={{ fontSize: 19, lineHeight: 1.45, margin: 0 }} data-testid="kiosk-privacy">{config.texts.privacy}</p></div>
      <div style={{ marginTop: 16 }}><Switch checked={form.privacy_accepted} onChange={(value) => set('privacy_accepted', value)} label="Leí y acepto" help="Necesario para continuar." testId="kiosk-accept" /></div></div>,
    1: <div style={{ display: 'grid', gap: 18 }} data-testid="kiosk-step-1">{title('¿Cómo te llamas?')}
      <Field label="Nombre" value={form.first_name} onChange={(value) => set('first_name', value)} testId="kiosk-first-name" />
      <Field label="Apellido" value={form.last_name} onChange={(value) => set('last_name', value)} testId="kiosk-last-name" />
      <Field label="¿Cómo te gusta que te llamen?" optional value={form.preferred_name} onChange={(value) => set('preferred_name', value)} placeholder="Ej.: Toño" testId="kiosk-preferred" /></div>,
    2: <div style={{ display: 'grid', gap: 18 }} data-testid="kiosk-step-2">{title('¿Cómo podemos contactarte?', 'Todo en esta pantalla es opcional.')}
      <Field label="Teléfono" optional type="tel" value={form.phone} onChange={(value) => set('phone', value)} testId="kiosk-phone" />
      <div><Label optional>Forma preferida de contacto</Label><Chips options={CONTACT} value={form.contact_method} onChange={(value) => set('contact_method', value)} testId="kiosk-contact-method" /></div>
      <Field label="Correo electrónico" optional type="email" value={form.email} onChange={(value) => set('email', value)} testId="kiosk-email" />
      <Field label="Ciudad o zona donde vives" optional value={form.city} onChange={(value) => set('city', value)} testId="kiosk-city" />
      <Field label="Dirección completa" optional value={form.address} onChange={(value) => set('address', value)} testId="kiosk-address" /></div>,
    3: <div style={{ display: 'grid', gap: 20 }} data-testid="kiosk-step-3">{title('Sobre tu visita', 'Todo en esta pantalla es opcional.')}
      <div><Label optional>¿Es tu primera visita?</Label><YesNo value={form.first_visit} onChange={(value) => set('first_visit', value)} testId="kiosk-first-visit" /></div>
      <div><Label optional>¿Alguien te invitó?</Label><YesNo value={form.invited} onChange={(value) => set('invited', value)} testId="kiosk-invited" /></div>
      {form.invited && <Field label="¿Quién te invitó?" optional value={form.invited_by} onChange={(value) => set('invited_by', value)} testId="kiosk-invited-by" />}
      <Field label="¿De dónde nos visitas?" optional value={form.visiting_from} onChange={(value) => set('visiting_from', value)} placeholder="Ciudad, país o iglesia" testId="kiosk-from" />
      <div><Label optional>¿Asistes a otra iglesia?</Label><YesNo value={form.other_church} onChange={(value) => set('other_church', value)} testId="kiosk-other-church" /></div>
      {form.other_church && <Field label="¿Cuál?" optional value={form.other_church_name} onChange={(value) => set('other_church_name', value)} testId="kiosk-other-church-name" />}
      <div><Label optional>¿Cómo supiste de la iglesia?</Label><Chips options={HEARD.map((item) => [item, item])} value={form.how_heard || null} onChange={(value) => set('how_heard', value || '')} testId="kiosk-heard" /></div>
      <Field label="Fecha de nacimiento" optional type="date" value={form.birth_date} onChange={(value) => set('birth_date', value)} testId="kiosk-birth" /></div>,
    4: <div style={{ display: 'grid', gap: 16 }} data-testid="kiosk-step-4">{title('¿Vienes con familiares?', 'Opcional. Sus nombres no se anuncian ni se muestran sin tu autorización.')}
      {form.family.map((member, index) => (
        <div key={index} style={{ display: 'grid', gap: 10, background: '#fff', border: `2px solid ${C.line}`, borderRadius: 16, padding: 14 }}>
          <Field label={`Nombre del familiar ${index + 1}`} value={member.name} onChange={(value) => set('family', form.family.map((item, position) => (position === index ? { ...item, name: value } : item)))} testId={`kiosk-family-name-${index}`} />
          <Chips options={[['Esposo o esposa', 'Esposo o esposa'], ['Hijo o hija', 'Hijo o hija'], ['Padre o madre', 'Padre o madre'], ['Otro familiar', 'Otro familiar']]} value={member.relation} onChange={(value) => set('family', form.family.map((item, position) => (position === index ? { ...item, relation: value, is_minor: value === 'Hijo o hija' ? item.is_minor : false } : item)))} />
          {member.relation === 'Hijo o hija' && <Switch checked={member.is_minor} onChange={(value) => set('family', form.family.map((item, position) => (position === index ? { ...item, is_minor: value } : item)))} label="Es menor de edad" help="Solo guardamos su nombre." />}
          <Big kind="secondary" onClick={() => set('family', form.family.filter((_, position) => position !== index))}>Quitar</Big>
        </div>
      ))}
      {form.family.length < 8 && <Big kind="secondary" onClick={() => set('family', [...form.family, { name: '', relation: null, is_minor: false }])} testId="kiosk-family-add">Agregar un familiar</Big>}</div>,
    5: <div style={{ display: 'grid', gap: 18 }} data-testid="kiosk-step-5">{title('¿Cómo podemos servirte?', 'Elige lo que quieras. La oración, la consejería y las necesidades personales son opcionales y confidenciales.')}
      <Chips multiple options={REQUESTS} value={form.requests} onChange={(value) => set('requests', value.includes('no_followup') && !form.requests.includes('no_followup') ? ['no_followup'] : value.filter((item) => item !== 'no_followup' || value.length === 1))} testId="kiosk-requests" />
      {form.requests.includes('prayer') && <Area label="Tu petición de oración" hint="Solo la verá el equipo de oración autorizado." value={form.prayer_request} onChange={(value) => set('prayer_request', value)} testId="kiosk-prayer" />}
      {form.requests.some((item) => item.startsWith('counseling')) && <Area label="Cuéntanos brevemente (consejería)" hint="Confidencial: solo la verá el equipo pastoral autorizado." value={form.counseling_note} onChange={(value) => set('counseling_note', value)} testId="kiosk-counseling" />}
      {form.requests.some((item) => ['support_child', 'other_help'].includes(item)) && <Area label="¿En qué te podemos ayudar?" hint="Confidencial." value={form.needs_note} onChange={(value) => set('needs_note', value)} testId="kiosk-needs" />}</div>,
    6: <div style={{ display: 'grid', gap: 14 }} data-testid="kiosk-step-6">{title('Tu autorización', 'Cada opción es independiente: puedes aceptar el seguimiento sin aceptar que se anuncie tu nombre.')}
      <Switch checked={form.consent_followup} onChange={(value) => set('consent_followup', value)} label="Acepto que la iglesia se comunique conmigo para darme seguimiento" testId="kiosk-consent-followup" />
      <Switch checked={form.consent_announce} onChange={(value) => set('consent_announce', value)} label="Acepto que se mencione mi nombre en la bienvenida" help={`Se diría: «${form.preferred_name || form.first_name || 'tu nombre'}».`} testId="kiosk-consent-announce" />
      <Switch checked={form.consent_screens} onChange={(value) => set('consent_screens', value)} label="Acepto que mi nombre aparezca en las pantallas de la iglesia" testId="kiosk-consent-screens" />
      {form.family.some((item) => item.name.trim()) && <Switch checked={form.consent_family_announce} onChange={(value) => set('consent_family_announce', value)} label="Acepto que también se mencione a mis familiares" testId="kiosk-consent-family" />}</div>,
    7: <div data-testid="kiosk-step-7">{title('Revisa tus datos')}
      <dl style={{ display: 'grid', gap: 10, fontSize: 21, background: '#fff', border: `2px solid ${C.line}`, borderRadius: 16, padding: 18, margin: 0 }}>
        {[['Nombre', `${form.first_name} ${form.last_name}`], ['Te llamaremos', form.preferred_name || form.first_name], ['Teléfono', form.phone], ['Ciudad o zona', form.city],
          ['Cómo podemos servirte', form.requests.map((key) => REQUESTS.find(([value]) => value === key)?.[1]).join(', ')],
          ['Seguimiento', form.consent_followup ? 'Sí' : 'No'], ['Anunciar tu nombre', form.consent_announce ? 'Sí' : 'No'], ['Mostrar en pantallas', form.consent_screens ? 'Sí' : 'No']]
          .filter(([, value]) => value).map(([label, value]) => <div key={label}><dt style={{ fontWeight: 700 }}>{label}</dt><dd style={{ margin: 0 }}>{value}</dd></div>)}
      </dl>
      {error && <p style={{ fontSize: 20, color: '#B42318' }}>{error}</p>}</div>,
  }[step];
  return shell(body, footer);
}
