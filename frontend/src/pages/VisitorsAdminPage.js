import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import QRCode from 'qrcode';
import { ClipboardList, Copy, FileText, HeartHandshake, Link2, Loader2, Monitor, Tablet, TriangleAlert } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { hasCapability, isPastoralAuthority } from '../lib/accessControl';
import VisitorFollowup from '../components/visitors/VisitorFollowup';
import WelcomeOperator from '../components/visitors/WelcomeOperator';

/* Registro de visitantes › administración: seguimiento, bienvenida en vivo, los
 * dos enlaces (tabletas y pantalla de bienvenida, con QR y «Generar enlace
 * nuevo»), textos editables (bienvenida, privacidad, confirmación), servicio de
 * hoy y los registros recibidos. Todo lo valida el backend con capacidades 5A. */

const can = (user, capability) => isPastoralAuthority(user) || hasCapability(user, capability);
const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString('es', { day: 'numeric', month: 'long', hour: 'numeric', minute: '2-digit' }) : '—');

function LinkCard({ item, onRotate }) {
  const url = `${window.location.origin}${item.path}`;
  const [qr, setQr] = useState('');
  useEffect(() => { QRCode.toDataURL(url, { width: 360, margin: 1 }).then(setQr).catch(() => setQr('')); }, [url]);
  const tablet = item.kind === 'tablet';
  const rotate = async () => {
    if (!window.confirm(`¿Generar un ${item.label.toLowerCase()} nuevo? El actual dejará de funcionar en el acto y habrá que abrir el nuevo en ${tablet ? 'cada tableta' : 'la pantalla'}.`)) return;
    onRotate(item.kind);
  };
  return (
    <section className="rounded-2xl border border-[#E8E5DE] bg-white p-4" data-testid={`visitors-link-${item.kind}`}>
      <h3 className="flex items-center gap-2 font-['Spectral'] text-xl font-semibold text-[#101D36]">{tablet ? <Tablet className="h-5 w-5 text-[#9A7A2F]" /> : <Monitor className="h-5 w-5 text-[#9A7A2F]" />}{item.label}</h3>
      <p className="mt-1 text-[15px] text-slate-700">{tablet ? 'Uno solo para todas las tabletas: ábrelo en cada tableta y queda lista, sin código ni sesión. Solo permite crear registros.' : 'Para la pantalla o televisor de la pastora (también ProPresenter). Solo muestra los nombres, uno a la vez.'}</p>
      <div className="mt-3 flex flex-wrap items-start gap-4">
        {qr ? <img src={qr} alt={`Código QR del ${item.label.toLowerCase()}`} className="h-44 w-44 rounded-lg border border-[#E8E5DE]" data-testid={`visitors-link-qr-${item.kind}`} /> : <div className="h-44 w-44 rounded-lg bg-slate-100" />}
        <div className="min-w-0 flex-1 space-y-2">
          <p className="break-all rounded-lg bg-[#F8F6F0] p-3 font-mono text-[15px] text-[#14213D]" data-testid={`visitors-link-url-${item.kind}`}>{url}</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => navigator.clipboard?.writeText(url).then(() => toast.success('Enlace copiado')).catch(() => toast.error('No se pudo copiar; mantén presionado el enlace para copiarlo'))} className="inline-flex min-h-12 items-center gap-2 rounded-xl bg-[#132443] px-5 text-base font-semibold text-white" data-testid={`visitors-link-copy-${item.kind}`}><Copy className="h-4 w-4" />Copiar</button>
            <a href={url} target="_blank" rel="noreferrer" className="inline-flex min-h-12 items-center rounded-xl border border-[#D9D4C7] px-4 text-base font-semibold text-[#101D36]">Abrir</a>
            <button type="button" onClick={rotate} className="min-h-12 rounded-xl border border-red-200 px-4 text-base font-semibold text-red-700" data-testid={`visitors-link-rotate-${item.kind}`}>Generar enlace nuevo</button>
          </div>
          <p className="text-sm text-slate-600">Úsalo solo si el enlace se compartió fuera de la iglesia: el anterior deja de funcionar.</p>
        </div>
      </div>
    </section>
  );
}

function Links() {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState(null);
  const load = useCallback(() => axios.get(`${API}/api/visitors/links`, getAuthHeaders()).then((response) => setItems(response.data.items)).catch((error) => toast.error(apiErrorMessage(error, 'No se pudieron cargar los enlaces'))), [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  const rotate = async (kind) => { try { await axios.post(`${API}/api/visitors/links/${kind}/rotate`, {}, getAuthHeaders()); toast.success('Enlace nuevo listo'); load(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo generar')); } };
  if (!items) return <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />;
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      {items.map((item) => <LinkCard key={item.kind} item={item} onRotate={rotate} />)}
      <p className="text-[15px] text-slate-600 xl:col-span-2">Consejo: deja cada tableta fija en la página (iPad: Acceso Guiado; Android: fijar pantalla). Cada tableta se nombra sola (por ejemplo «Tableta 3F9A») para saber de dónde vino cada registro.</p>
    </div>
  );
}

function Texts({ canEdit }) {
  const { API, getAuthHeaders } = useAuth();
  const [texts, setTexts] = useState(null);
  const [service, setService] = useState('');
  useEffect(() => { axios.get(`${API}/api/visitors/texts`, getAuthHeaders()).then((response) => setTexts(response.data)).catch((error) => toast.error(apiErrorMessage(error, 'No se pudieron cargar los textos'))); }, [API, getAuthHeaders]);
  if (!texts) return <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />;
  const save = async () => { try { const response = await axios.put(`${API}/api/visitors/texts`, { welcome: texts.welcome, privacy: texts.privacy, confirmation: texts.confirmation }, getAuthHeaders()); setTexts(response.data); toast.success('Textos guardados'); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudieron guardar')); } };
  const saveService = async () => { try { const response = await axios.put(`${API}/api/visitors/service-today`, { label: service.trim(), kind: 'special' }, getAuthHeaders()); toast.success(`Hoy: ${response.data.label}`); setService(''); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); } };
  const area = (key, label, help, rows = 4) => (
    <label className="block"><span className="text-[15px] font-semibold text-[#101D36]">{label}</span><span className="block text-sm text-slate-600">{help}</span>
      <textarea value={texts[key]} disabled={!canEdit} onChange={(event) => setTexts((current) => ({ ...current, [key]: event.target.value }))} rows={rows} className="mt-1 w-full rounded-lg border border-[#D9D4C7] p-3 text-base" data-testid={`visitors-text-${key}`} /></label>
  );
  return (
    <div className="space-y-4 rounded-2xl border border-[#E8E5DE] bg-white p-4">
      {area('welcome', 'Mensaje de bienvenida', 'Una frase por línea. 1.ª: título. 2.ª: subtítulo. 3.ª: la frase principal, en un bloque destacado al centro (escríbela completa en una sola línea). Las demás se muestran más pequeñas, encima del botón «Iniciar registro».', 6)}
      {area('privacy', `Aviso de privacidad (versión ${texts.privacy_version})`, 'Corto, una frase por línea. Si lo cambias, sube la versión y cada registro guarda la versión que aceptó.', 5)}
      {area('confirmation', 'Mensaje de confirmación', 'Se muestra con el número de registro al terminar. Una frase por línea.', 3)}
      {canEdit && <button type="button" onClick={save} className="min-h-12 rounded-xl bg-[#132443] px-5 text-base font-semibold text-white" data-testid="visitors-texts-save">Guardar textos</button>}
      <div className="border-t border-[#EEECE6] pt-4">
        <p className="text-[15px] font-semibold text-[#101D36]">Servicio o actividad de hoy</p>
        <p className="text-sm text-slate-600">El registro toma «Servicio del domingo» o «Servicio del miércoles» según el día. Para una actividad especial, escribe su nombre (vale solo por hoy).</p>
        <div className="mt-2 flex flex-wrap gap-2"><input value={service} onChange={(event) => setService(event.target.value)} placeholder="Ej.: Conferencia de mujeres" className="h-12 min-w-[240px] flex-1 rounded-lg border border-[#D9D4C7] px-3 text-base" /><button type="button" disabled={service.trim().length < 3} onClick={saveService} className="min-h-12 rounded-xl border border-[#D9D4C7] px-4 text-base font-semibold disabled:opacity-50">Usar para hoy</button></div>
      </div>
    </div>
  );
}

function Registrations() {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState(null);
  const [day, setDay] = useState('');
  useEffect(() => { setItems(null); axios.get(`${API}/api/visitors/registrations`, { ...getAuthHeaders(), params: day ? { service_date: day } : {} }).then((response) => setItems(response.data.items)).catch((error) => { toast.error(apiErrorMessage(error, 'Sin acceso a los registros')); setItems([]); }); }, [API, getAuthHeaders, day]);
  return (
    <div className="space-y-3">
      <label className="text-sm font-semibold text-slate-700">Fecha del servicio<input type="date" value={day} onChange={(event) => setDay(event.target.value)} className="mt-1 block h-11 rounded-lg border border-[#D9D4C7] px-2 text-base" /></label>
      {!items ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : items.length === 0 ? <p className="text-[15px] text-slate-600">No hay registros{day ? ' en esa fecha' : ''}.</p> : (
        <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2" data-testid="visitors-registrations">{items.map((item) => (
          <li key={item.registration_id} className="rounded-2xl border border-[#E8E5DE] bg-white p-4">
            <p className="text-lg font-semibold text-[#101D36]">{item.visitor_number} · {item.first_name} {item.last_name}{item.preferred_name !== item.first_name ? ` («${item.preferred_name}»)` : ''}</p>
            <p className="text-[15px] text-slate-700">{item.service.label} · {fmtDateTime(item.created_at)} · {item.device_name}</p>
            <p className={`text-[15px] font-semibold ${item.match_status === 'possible' ? 'text-amber-800' : 'text-emerald-800'}`}>{item.match_label}</p>
            {item.contact?.phone && <p className="text-[15px] text-slate-700">Teléfono: {item.contact.phone}</p>}
            {item.requests.length > 0 && <p className="text-[15px] text-slate-700">Pide: {item.requests.join(', ')}{item.has_restricted ? ' · tiene notas confidenciales' : ''}</p>}
            <p className="text-sm text-slate-600">¿Podemos comunicarnos?: {item.consents.followup === true ? 'Sí' : item.consents.followup === false ? 'No' : 'No respondió'}</p>
            {item.person_id && <Link to={`/personas/${item.person_id}`} className="text-sm font-semibold text-[#0879BE] underline">Perfil 360</Link>}
          </li>
        ))}</ul>
      )}
    </div>
  );
}

const TABS = [['seguimiento', 'Seguimiento', HeartHandshake, 'any'], ['bienvenida', 'Bienvenida en vivo', Monitor, 'visitors.welcome.operate'], ['enlaces', 'Enlaces', Link2, 'visitors.devices.manage'], ['textos', 'Textos y servicio de hoy', FileText, null], ['registros', 'Registros', ClipboardList, 'visitors.read']];

export default function VisitorsAdminPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const allowed = TABS.filter(([, , , capability]) => (capability === 'any' ? true : capability ? can(user, capability) : ['visitors.texts.manage', 'visitors.devices.manage', 'visitors.read'].some((item) => can(user, item))));
  const tab = allowed.some(([key]) => key === params.get('tab')) ? params.get('tab') : allowed[0]?.[0];
  return (
    <div className="min-h-screen bg-[#F8F6F0] pb-10" data-testid="visitors-admin">
      <header className="bg-gradient-to-r from-[#14213D] via-[#1B2A4A] to-[#0E5B5A] px-4 py-6 text-white sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-[1400px]"><p className="text-xs font-semibold uppercase tracking-widest text-[#E7D28D]">Bienvenida</p><h1 className="mt-1 font-['Spectral'] text-3xl font-bold">Registro de visitantes</h1>
          <p className="mt-1 text-[15px] text-white/80">Tabletas de registro, textos y registros recibidos. Los datos personales solo los ve el personal autorizado.</p></div>
      </header>
      <div className="mx-auto w-full max-w-[1400px] space-y-4 px-4 py-4 sm:px-6 lg:px-8">
        {allowed.length === 0 ? <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-[15px] text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4" />Tu cuenta no tiene permiso para el Registro de visitantes.</div> : <>
          <div className="flex flex-wrap gap-1 rounded-xl bg-[#EEECE6] p-1" role="tablist">{allowed.map(([key, label, Icon]) => <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setParams({ tab: key }, { replace: true })} className={`inline-flex min-h-12 items-center gap-2 rounded-lg px-4 text-[15px] font-semibold ${tab === key ? 'bg-white text-[#101D36] shadow' : 'text-slate-600'}`} data-testid={`visitors-tab-${key}`}><Icon className="h-4 w-4" />{label}</button>)}</div>
          {tab === 'seguimiento' && <VisitorFollowup />}
          {tab === 'bienvenida' && <WelcomeOperator />}
          {tab === 'enlaces' && <Links />}
          {tab === 'textos' && <Texts canEdit={can(user, 'visitors.texts.manage')} />}
          {tab === 'registros' && <Registrations />}
        </>}
      </div>
    </div>
  );
}
