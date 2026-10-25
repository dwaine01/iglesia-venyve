import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { ClipboardList, Copy, FileText, HeartHandshake, Loader2, Tablet, TriangleAlert } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { hasCapability, isPastoralAuthority } from '../lib/accessControl';
import VisitorFollowup from '../components/visitors/VisitorFollowup';

/* Registro de visitantes › administración: emparejar las tabletas (código de un
 * solo uso), textos editables (bienvenida, privacidad, confirmación), servicio de
 * hoy y los registros recibidos. Todo lo valida el backend con capacidades 5A. */

const can = (user, capability) => isPastoralAuthority(user) || hasCapability(user, capability);
const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString('es', { day: 'numeric', month: 'long', hour: 'numeric', minute: '2-digit' }) : '—');

function Devices() {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState(null);
  const [name, setName] = useState('');
  const [fresh, setFresh] = useState(null);
  const kioskUrl = `${window.location.origin}/quiosco`;
  const load = useCallback(() => axios.get(`${API}/api/visitors/devices`, getAuthHeaders()).then((response) => setItems(response.data.items)).catch((error) => toast.error(apiErrorMessage(error, 'No se pudieron cargar las tabletas'))), [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  const create = async (event) => {
    event.preventDefault();
    try { const response = await axios.post(`${API}/api/visitors/devices`, { name: name.trim() }, getAuthHeaders()); setFresh(response.data); setName(''); load(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo crear la tableta')); }
  };
  const newCode = async (device) => { try { const response = await axios.post(`${API}/api/visitors/devices/${device.device_id}/new-code`, {}, getAuthHeaders()); setFresh(response.data); load(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo generar el código')); } };
  const revoke = async (device) => {
    if (!window.confirm(`¿Desactivar ${device.name}? Dejará de poder registrar visitantes hasta que la emparejes de nuevo.`)) return;
    try { await axios.post(`${API}/api/visitors/devices/${device.device_id}/revoke`, {}, getAuthHeaders()); toast.success(`${device.name} desactivada`); load(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo desactivar')); }
  };
  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-[#E8E5DE] bg-white p-4" data-testid="visitors-how">
        <h3 className="font-['Spectral'] text-xl font-semibold text-[#101D36]">Cómo preparar cada tableta</h3>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-[15px] text-slate-700">
          <li>Aquí escribe el nombre (por ejemplo «Tableta 1») y toca «Crear tableta». Aparece un código de 8 letras, válido por 24 horas y de un solo uso.</li>
          <li>En la tableta abre <b className="break-all">{kioskUrl}</b> <button type="button" onClick={() => navigator.clipboard?.writeText(kioskUrl).then(() => toast.success('Dirección copiada'))} className="inline-flex items-center gap-1 text-[#0879BE] underline"><Copy className="h-3.5 w-3.5" />copiar</button>, escribe el código y toca «Emparejar tableta».</li>
          <li>Deja la tableta fija en esa pantalla (en iPad: Acceso Guiado; en Android: fijar pantalla). No inicies sesión de personal en la tableta.</li>
        </ol>
      </section>
      <form onSubmit={create} className="flex flex-wrap items-end gap-2 rounded-2xl border border-[#E8E5DE] bg-white p-4">
        <label className="min-w-[220px] flex-1 text-sm font-semibold text-slate-700">Nombre de la tableta<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Tableta 1" className="mt-1 block h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="visitors-device-name" /></label>
        <button type="submit" disabled={name.trim().length < 2} className="min-h-12 rounded-xl bg-[#132443] px-5 text-base font-semibold text-white disabled:opacity-50" data-testid="visitors-device-create">Crear tableta</button>
      </form>
      {fresh && (
        <section className="rounded-2xl border-2 border-[#C8A951] bg-[#FBF6EA] p-4" data-testid="visitors-fresh-code">
          <p className="text-[15px] font-semibold text-[#101D36]">Código para {fresh.name} (válido 24 horas, un solo uso):</p>
          <p className="mt-1 font-mono text-4xl font-bold tracking-[0.2em] text-[#14213D]" data-testid="visitors-pairing-code">{fresh.pairing_code}</p>
          <p className="mt-1 text-sm text-slate-600">Escríbelo en la tableta, en {kioskUrl}. Por seguridad no se volverá a mostrar; si lo pierdes, toca «Nuevo código».</p>
        </section>
      )}
      {!items ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : items.length === 0 ? <p className="text-[15px] text-slate-600">Todavía no hay tabletas.</p> : (
        <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">{items.map((device) => (
          <li key={device.device_id} className="rounded-2xl border border-[#E8E5DE] bg-white p-4" data-testid="visitors-device">
            <p className="flex items-center gap-2 text-lg font-semibold text-[#101D36]"><Tablet className="h-5 w-5 text-[#9A7A2F]" />{device.name}</p>
            <p className="text-[15px] text-slate-700">Estado: <b>{device.status_label}</b>{device.status === 'paired' ? ` · ${device.registrations} registro(s) · última conexión ${fmtDateTime(device.last_seen_at)}` : ''}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button type="button" onClick={() => newCode(device)} className="min-h-11 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold">Nuevo código</button>
              {device.status !== 'revoked' && <button type="button" onClick={() => revoke(device)} className="min-h-11 rounded-lg border border-red-200 px-3 text-[15px] font-semibold text-red-700" data-testid="visitors-device-revoke">Desactivar</button>}
            </div>
          </li>
        ))}</ul>
      )}
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
      {area('welcome', 'Mensaje de bienvenida', 'Lo primero que ve el visitante.')}
      {area('privacy', `Aviso de privacidad (versión ${texts.privacy_version})`, 'Para qué se usan los datos. Si lo cambias, sube la versión y cada registro guarda la versión que aceptó.', 5)}
      {area('confirmation', 'Mensaje de confirmación', 'Se muestra con el número de registro al terminar.', 3)}
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
            <p className="text-sm text-slate-600">Seguimiento: {item.consents.followup ? 'sí' : 'no'} · Anunciar: {item.consents.announce ? 'sí' : 'no'} · Pantallas: {item.consents.screens ? 'sí' : 'no'}</p>
            {item.person_id && <Link to={`/personas/${item.person_id}`} className="text-sm font-semibold text-[#0879BE] underline">Perfil 360</Link>}
          </li>
        ))}</ul>
      )}
    </div>
  );
}

const TABS = [['seguimiento', 'Seguimiento', HeartHandshake, 'any'], ['tabletas', 'Tabletas', Tablet, 'visitors.devices.manage'], ['textos', 'Textos y servicio de hoy', FileText, null], ['registros', 'Registros', ClipboardList, 'visitors.read']];

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
          {tab === 'tabletas' && <Devices />}
          {tab === 'textos' && <Texts canEdit={can(user, 'visitors.texts.manage')} />}
          {tab === 'registros' && <Registrations />}
        </>}
      </div>
    </div>
  );
}
