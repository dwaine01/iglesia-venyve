import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { ChevronLeft, ChevronRight, EyeOff, Eye, Loader2, Pencil, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';

/* Visitantes › Bienvenida en vivo: qué servicio muestra la pantalla de
 * bienvenida, y cada nombre registrado (todos entran por defecto) con «Corregir»
 * y «Quitar de la bienvenida» (el registro no se borra). En la pantalla se avanza
 * con las flechas. Nada de contacto ni pedidos (lista blanca). */

const SERVICES = [['all', 'Todos'], ['sunday', 'Domingo'], ['wednesday', 'Miércoles'], ['special', 'Actividad especial']];
// «Agregar nombre»: siempre visible, con el teclado listo; Enter lo agrega YA a la lista.
function AddName({ currentId, onAdded }) {
  const { API, getAuthHeaders } = useAuth();
  const [name, setName] = useState('');
  const [invited, setInvited] = useState('');
  const [position, setPosition] = useState('next');
  const [saving, setSaving] = useState(false);
  const input = useRef(null);
  useEffect(() => { input.current?.focus(); }, []);
  const add = async (event) => {
    event.preventDefault();
    if (name.trim().length < 2 || saving) return;
    setSaving(true);
    try {
      const response = await axios.post(`${API}/api/visitors/welcome/manual`, { name: name.trim(), invited_by: invited.trim() || null, position: currentId ? position : 'end', after_id: currentId }, getAuthHeaders());
      toast.success(`${response.data.name} entró a la lista`); setName(''); setInvited(''); onAdded(response.data);
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo agregar')); }
    setSaving(false); input.current?.focus();
  };
  return (
    <form onSubmit={add} className="rounded-2xl border-2 border-[#C8A951] bg-[#FBF6EA] p-4" data-testid="welcome-add">
      <p className="flex items-center gap-2 text-[15px] font-semibold text-[#101D36]"><UserPlus className="h-5 w-5" />Agregar nombre</p>
      <div className="mt-2 grid gap-2 md:grid-cols-[2fr_1.4fr_auto]">
        <input ref={input} value={name} onChange={(event) => setName(event.target.value)} placeholder="Nombre y apellido" aria-label="Nombre y apellido" autoComplete="off" className="h-14 rounded-xl border border-[#D9D4C7] bg-white px-4 text-lg" data-testid="welcome-add-name" />
        <input value={invited} onChange={(event) => setInvited(event.target.value)} placeholder="Invitado por (si lo sabes)" aria-label="Invitado por" autoComplete="off" className="h-14 rounded-xl border border-[#D9D4C7] bg-white px-4 text-lg" data-testid="welcome-add-invited" />
        <button type="submit" disabled={name.trim().length < 2 || saving} className="min-h-14 rounded-xl bg-[#132443] px-6 text-lg font-semibold text-white disabled:opacity-50" data-testid="welcome-add-submit">Agregar</button>
      </div>
      <div className="mt-2 flex flex-wrap gap-2" role="radiogroup" aria-label="Dónde se agrega">
        <button type="button" role="radio" aria-checked={position === 'next'} onClick={() => setPosition('next')} className={chip(position === 'next')} data-testid="welcome-add-next">Siguiente (después del nombre actual)</button>
        <button type="button" role="radio" aria-checked={position === 'end'} onClick={() => setPosition('end')} className={chip(position === 'end')} data-testid="welcome-add-end">Al final</button>
      </div>
      <p className="mt-2 text-sm text-slate-600">Queda como «Agregado a mano» en Seguimiento para completarlo o transcribir su hoja. Si ya está en la lista de hoy, te avisa.</p>
    </form>
  );
}

const chip = (active) => `min-h-12 rounded-full border px-4 text-[15px] font-semibold ${active ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-slate-700'}`;

export default function WelcomeOperator() {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState('');
  const [draftInvited, setDraftInvited] = useState('');
  const [currentId, setCurrentId] = useState(null);
  const load = useCallback(() => axios.get(`${API}/api/visitors/welcome`, getAuthHeaders()).then((response) => setData(response.data))
    .catch((error) => toast.error(apiErrorMessage(error, 'No se pudo cargar la bienvenida'))), [API, getAuthHeaders]);
  useEffect(() => { load(); const timer = setInterval(load, 8000); return () => clearInterval(timer); }, [load]);

  const run = async (request) => { try { await request(); await load(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); } };
  const setState = (body) => run(() => axios.put(`${API}/api/visitors/welcome/state`, body, getAuthHeaders()));
  const updateItem = (item, body) => run(() => axios.post(`${API}/api/visitors/welcome/items/${item.registration_id}`, body, getAuthHeaders()));

  if (!data) return <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />;
  const { state } = data;
  const serviceKind = state.service_kind || 'all';
  const visible = data.items.filter((item) => !item.hidden);
  const shown = visible.length;
  // Modo operador: el nombre que se está leyendo (las flechas lo mueven, como en la pantalla).
  let index = visible.findIndex((item) => item.registration_id === currentId);
  if (index < 0) index = 0;
  const current = visible[index];
  const go = (delta) => { const next = visible[Math.min(visible.length - 1, Math.max(0, index + delta))]; if (next) setCurrentId(next.registration_id); };
  return (
    <div className="space-y-4" data-testid="welcome-operator"
      onKeyDown={(event) => { if (event.target.tagName === 'INPUT') return; if (event.key === 'ArrowRight') go(1); if (event.key === 'ArrowLeft') go(-1); }}>
      <section className="rounded-2xl bg-[#0B1530] p-4 text-center text-white" data-testid="welcome-current">
        <p className="text-sm font-semibold uppercase tracking-widest text-[#E7C766]">Leyendo ahora · Nombre {shown ? index + 1 : 0} de {shown}</p>
        {current ? <>
          <p className="mt-1 text-3xl font-extrabold md:text-4xl" data-testid="welcome-current-name">{current.name}</p>
          {current.invited_by && <p className="mt-1 text-xl font-semibold text-[#E7C766]">Invitado por {current.invited_by}</p>}
        </> : <p className="mt-1 text-xl">Todavía no hay nombres</p>}
        <div className="mt-3 flex justify-center gap-2">
          <button type="button" onClick={() => go(-1)} disabled={index <= 0} className="inline-flex min-h-12 items-center gap-1 rounded-xl border border-white/40 px-4 text-base font-semibold disabled:opacity-30" data-testid="welcome-op-prev"><ChevronLeft className="h-5 w-5" />Anterior</button>
          <button type="button" onClick={() => go(1)} disabled={index >= shown - 1} className="inline-flex min-h-12 items-center gap-1 rounded-xl border border-white/40 px-4 text-base font-semibold disabled:opacity-30" data-testid="welcome-op-next">Siguiente<ChevronRight className="h-5 w-5" /></button>
        </div>
      </section>
      <AddName currentId={current?.registration_id} onAdded={() => load()} />
      <section className="space-y-2 rounded-2xl border border-[#E8E5DE] bg-white p-4">
        <p className="text-[15px] text-slate-700">La pantalla de bienvenida muestra un nombre a la vez. Se avanza con la <b>flecha derecha</b> y se retrocede con la <b>izquierda</b> (o con los botones grandes de la pantalla). Todos los visitantes registrados aparecen; aquí puedes corregir un nombre (o «Invitado por») antes de leerlo, o quitarlo.</p>
        <p className="text-[15px] font-semibold text-[#101D36]">Servicio que se muestra</p>
        <div className="flex flex-wrap items-end gap-2">
          {SERVICES.map(([value, label]) => <button key={value} type="button" onClick={() => setState({ service_kind: value })} className={chip(serviceKind === value)} data-testid={`welcome-service-${value}`}>{label}</button>)}
          <label className="text-sm font-semibold text-slate-700">Fecha<input type="date" value={state.service_date || data.today.date} onChange={(event) => event.target.value && setState({ service_date: event.target.value })} className="mt-1 block h-12 rounded-lg border border-[#D9D4C7] px-2 text-base" /></label>
          {state.service_date && <button type="button" onClick={() => setState({ today: true })} className="min-h-12 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold">Volver a hoy</button>}
        </div>
      </section>

      <section className="rounded-2xl border border-[#E8E5DE] bg-white p-4">
        <p className="text-[15px] font-semibold text-[#101D36]">Nombres en la bienvenida: {shown} de {data.items.length}</p>
        {data.items.length === 0 ? <p className="mt-1 text-[15px] text-slate-600">Todavía no hay visitantes registrados en este servicio.</p> : (
          <ol className="mt-2 divide-y divide-[#EEECE6]" data-testid="welcome-items">{data.items.map((item) => (
            <li key={item.registration_id} className="flex flex-wrap items-center gap-2 py-2" data-testid="welcome-item">
              {editing === item.registration_id ? (
                <form className="flex flex-1 flex-wrap gap-2" onSubmit={(event) => {
                  event.preventDefault();
                  updateItem(item, { display_name: draft, ...(item.invited_by && draftInvited.trim() && draftInvited.trim() !== item.invited_by ? { invited_by_display: draftInvited } : {}) });
                  setEditing(null);
                }}>
                  <label className="min-w-[200px] flex-1 text-sm font-semibold text-slate-700">Nombre que se lee<input value={draft} onChange={(event) => setDraft(event.target.value)} className="mt-1 block h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" autoFocus data-testid="welcome-edit-input" /></label>
                  {item.invited_by && <label className="min-w-[200px] flex-1 text-sm font-semibold text-slate-700">Invitado por<input value={draftInvited} onChange={(event) => setDraftInvited(event.target.value)} className="mt-1 block h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="welcome-edit-invited" /></label>}
                  <button type="submit" disabled={!draft.trim()} className="min-h-12 rounded-lg bg-[#132443] px-4 text-[15px] font-semibold text-white disabled:opacity-50" data-testid="welcome-edit-save">Guardar</button>
                  {(item.corrected || item.invited_corrected) && <button type="button" onClick={() => { updateItem(item, { reset_name: true, reset_invited: true }); setEditing(null); }} className="min-h-12 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold">Usar lo original ({item.default_name}{item.default_invited_by ? ` · invitado por ${item.default_invited_by}` : ''})</button>}
                  <button type="button" onClick={() => setEditing(null)} className="min-h-12 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold">Cancelar</button>
                </form>
              ) : (
                <>
                  <p className={`min-w-0 flex-1 text-lg ${item.hidden ? 'text-slate-400 line-through' : 'font-semibold text-[#101D36]'}`}>{item.name}{item.corrected ? <span className="ml-2 text-sm font-normal text-slate-500">(corregido)</span> : null}{item.registering ? <span className="ml-2 text-sm font-normal italic text-violet-700" data-testid="welcome-item-registering">registrando…</span> : null}{item.manual ? <span className="ml-2 text-sm font-normal text-amber-800" data-testid="welcome-item-manual">agregado a mano</span> : null}{item.hidden ? <span className="ml-2 text-sm font-normal">quitado de la bienvenida</span> : null}
                    {item.invited_by && <span className="block text-[15px] font-normal text-slate-600" data-testid="welcome-item-invited">Invitado por {item.invited_by}{item.invited_corrected ? ' (corregido)' : ''}</span>}</p>
                  <button type="button" onClick={() => { setEditing(item.registration_id); setDraft(item.name); setDraftInvited(item.invited_by || ''); }} className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold" data-testid="welcome-edit"><Pencil className="h-4 w-4" />Corregir</button>
                  <button type="button" onClick={() => updateItem(item, { hidden: !item.hidden })} className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold" data-testid="welcome-hide">{item.hidden ? <><Eye className="h-4 w-4" />Volver a mostrar</> : <><EyeOff className="h-4 w-4" />Quitar de la bienvenida</>}</button>
                </>
              )}
            </li>
          ))}</ol>
        )}
        <p className="mt-2 text-sm text-slate-600">Quitar de la bienvenida no borra el registro ni el seguimiento. Los familiares que acompañan (y los menores) nunca aparecen en la pantalla.</p>
      </section>
    </div>
  );
}
