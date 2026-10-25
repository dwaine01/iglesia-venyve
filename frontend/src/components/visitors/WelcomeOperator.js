import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ChevronLeft, ChevronRight, EyeOff, Eye, Loader2, Pause, Pencil, Play } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';

/* Visitantes V3 › Bienvenida en vivo: el operador controla la pantalla del salón
 * y la de la pastora (modo, pausa, adelante, atrás, servicio), corrige nombres y
 * quita a alguien de la pantalla sin borrar su registro. Solo se listan los que
 * autorizaron esa pantalla; nada de contacto ni pedidos (lista blanca). */

const AUDIENCES = [['tv', 'Pantalla del salón'], ['pastora', 'Pantalla de la pastora']];
const SERVICES = [['all', 'Todos'], ['sunday', 'Domingo'], ['wednesday', 'Miércoles'], ['special', 'Actividad especial']];
const chip = (active) => `min-h-12 rounded-full border px-4 text-[15px] font-semibold ${active ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-slate-700'}`;

export default function WelcomeOperator() {
  const { API, getAuthHeaders } = useAuth();
  const [audience, setAudience] = useState('tv');
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState('');
  const load = useCallback(() => axios.get(`${API}/api/visitors/welcome`, { ...getAuthHeaders(), params: { audience } }).then((response) => setData(response.data))
    .catch((error) => toast.error(apiErrorMessage(error, 'No se pudo cargar la bienvenida'))), [API, getAuthHeaders, audience]);
  useEffect(() => { setData(null); load(); const timer = setInterval(load, 5000); return () => clearInterval(timer); }, [load]);

  const run = async (request) => { try { await request(); await load(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); } };
  const control = (action) => run(() => axios.post(`${API}/api/visitors/welcome/control`, { audience, action }, getAuthHeaders()));
  const setState = (body) => run(() => axios.put(`${API}/api/visitors/welcome/state`, { audience, ...body }, getAuthHeaders()));
  const updateItem = (item, body) => run(() => axios.post(`${API}/api/visitors/welcome/items/${item.registration_id}`, body, getAuthHeaders()));

  if (!data) return <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />;
  const { presentation: show, state } = data;
  const serviceKind = state.service_kind || 'all';
  return (
    <div className="space-y-4" data-testid="welcome-operator">
      <div className="flex flex-wrap gap-2">{AUDIENCES.map(([value, label]) => <button key={value} type="button" onClick={() => setAudience(value)} className={chip(audience === value)} data-testid={`welcome-audience-${value}`}>{label}</button>)}</div>
      <p className="text-[15px] text-slate-600">{audience === 'tv' ? 'Muestra a quienes autorizaron que su nombre aparezca en las pantallas. Nunca muestra familiares.' : 'Muestra a quienes autorizaron que se anuncie su nombre; sus familiares solo si también lo autorizaron.'}</p>

      <section className="rounded-2xl bg-[#0B1530] p-5 text-center text-white" data-testid="welcome-preview">
        <p className="text-sm font-semibold uppercase tracking-widest text-[#E7C766]">Ahora en pantalla{show.paused ? ' · en pausa' : ''}</p>
        {show.names.length === 0 ? <p className="mt-2 text-2xl font-bold">Nadie todavía: se ve «Nos alegra que estés aquí»</p>
          : show.names.map((name) => <p key={name} className={`mt-2 font-extrabold ${show.mode === 'one' ? 'text-4xl' : 'text-2xl'}`}>{name}</p>)}
        <p className="mt-2 text-[15px] text-white/75">{show.total} nombre(s) · {show.mode === 'one' ? 'nombre' : 'página'} {Math.min(show.page + 1, show.pages)} de {show.pages}</p>
      </section>

      <div className="grid grid-cols-3 gap-2">
        <button type="button" onClick={() => control('prev')} className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl border border-[#D9D4C7] bg-white text-lg font-semibold" data-testid="welcome-prev"><ChevronLeft className="h-6 w-6" />Anterior</button>
        <button type="button" onClick={() => control(show.paused ? 'play' : 'pause')} className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl bg-[#132443] text-lg font-semibold text-white" data-testid="welcome-pause">{show.paused ? <><Play className="h-6 w-6" />Reanudar</> : <><Pause className="h-6 w-6" />Pausar</>}</button>
        <button type="button" onClick={() => control('next')} className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl border border-[#D9D4C7] bg-white text-lg font-semibold" data-testid="welcome-next">Siguiente<ChevronRight className="h-6 w-6" /></button>
      </div>

      <section className="space-y-3 rounded-2xl border border-[#E8E5DE] bg-white p-4">
        <div><p className="text-[15px] font-semibold text-[#101D36]">Cómo se muestra</p>
          <div className="mt-1 flex flex-wrap gap-2">
            <button type="button" onClick={() => setState({ mode: 'one' })} className={chip(state.mode === 'one')} data-testid="welcome-mode-one">Uno por uno</button>
            <button type="button" onClick={() => setState({ mode: 'list' })} className={chip(state.mode === 'list')} data-testid="welcome-mode-list">Lista lenta (4 por página)</button>
          </div></div>
        <label className="block text-[15px] font-semibold text-[#101D36]">Segundos en pantalla: {state.seconds}
          <input type="range" min={4} max={30} value={state.seconds} onChange={(event) => setData((current) => ({ ...current, state: { ...current.state, seconds: Number(event.target.value) } }))} onPointerUp={(event) => setState({ seconds: Number(event.target.value) })} onKeyUp={(event) => setState({ seconds: Number(event.target.value) })} className="mt-2 block w-full max-w-md" /></label>
        <div><p className="text-[15px] font-semibold text-[#101D36]">Servicio</p>
          <div className="mt-1 flex flex-wrap items-end gap-2">
            {SERVICES.map(([value, label]) => <button key={value} type="button" onClick={() => setState({ service_kind: value })} className={chip(serviceKind === value)} data-testid={`welcome-service-${value}`}>{label}</button>)}
            <label className="text-sm font-semibold text-slate-700">Fecha<input type="date" value={state.service_date || data.today.date} onChange={(event) => event.target.value && setState({ service_date: event.target.value })} className="mt-1 block h-12 rounded-lg border border-[#D9D4C7] px-2 text-base" /></label>
            {state.service_date && <button type="button" onClick={() => setState({ today: true })} className="min-h-12 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold">Volver a hoy</button>}
          </div></div>
      </section>

      <section className="rounded-2xl border border-[#E8E5DE] bg-white p-4">
        <p className="text-[15px] font-semibold text-[#101D36]">Nombres autorizados ({data.items.length})</p>
        {data.items.length === 0 ? <p className="mt-1 text-[15px] text-slate-600">Todavía nadie de este servicio autorizó {audience === 'tv' ? 'mostrar su nombre en pantallas' : 'que se anuncie su nombre'}.</p> : (
          <ul className="mt-2 divide-y divide-[#EEECE6]" data-testid="welcome-items">{data.items.map((item) => (
            <li key={item.registration_id} className="flex flex-wrap items-center gap-2 py-2" data-testid="welcome-item">
              {editing === item.registration_id ? (
                <form className="flex flex-1 flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); updateItem(item, { display_name: draft }); setEditing(null); }}>
                  <input value={draft} onChange={(event) => setDraft(event.target.value)} className="h-12 min-w-[200px] flex-1 rounded-lg border border-[#D9D4C7] px-3 text-base" autoFocus data-testid="welcome-edit-input" />
                  <button type="submit" disabled={!draft.trim()} className="min-h-12 rounded-lg bg-[#132443] px-4 text-[15px] font-semibold text-white disabled:opacity-50" data-testid="welcome-edit-save">Guardar</button>
                  {item.corrected && <button type="button" onClick={() => { updateItem(item, { reset_name: true }); setEditing(null); }} className="min-h-12 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold">Usar el original ({item.default_name})</button>}
                  <button type="button" onClick={() => setEditing(null)} className="min-h-12 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold">Cancelar</button>
                </form>
              ) : (
                <>
                  <p className={`min-w-0 flex-1 text-lg ${item.hidden ? 'text-slate-400 line-through' : 'font-semibold text-[#101D36]'}`}>{item.name}{item.corrected ? <span className="ml-2 text-sm font-normal text-slate-500">(corregido)</span> : null}{item.hidden ? <span className="ml-2 text-sm font-normal no-underline">quitado de la pantalla</span> : null}</p>
                  <button type="button" onClick={() => { setEditing(item.registration_id); setDraft(item.name.split(' y su familia:')[0]); }} className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold" data-testid="welcome-edit"><Pencil className="h-4 w-4" />Corregir</button>
                  <button type="button" onClick={() => updateItem(item, { hidden: !item.hidden })} className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-[#D9D4C7] px-3 text-[15px] font-semibold" data-testid="welcome-hide">{item.hidden ? <><Eye className="h-4 w-4" />Volver a mostrar</> : <><EyeOff className="h-4 w-4" />Quitar de la pantalla</>}</button>
                </>
              )}
            </li>
          ))}</ul>
        )}
        <p className="mt-2 text-sm text-slate-600">Quitar de la pantalla no borra el registro ni el seguimiento.</p>
      </section>
    </div>
  );
}
