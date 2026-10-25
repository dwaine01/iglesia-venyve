import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ChevronDown, Loader2, ShieldCheck, Trash2, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { PersonPicker } from '../outreach/CreateCampaignDialog';

const CAPABILITY_LABELS = {
  'processes.read': 'Ver Consolidación y sus personas', 'processes.write': 'Registrar avance', 'consolidation.assign': 'Asignar mentores',
  'consolidation.mentor.transfer': 'Reasignar pendientes', 'processes.alerts.manage': 'Atender alertas del proceso',
  'person.directory.search': 'Buscar personas', 'person.contacts.read': 'Ver contactos de las personas',
};
const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' }) : '');

/** C1 · Encargados de Consolidación (autoridad pastoral). El backend aplica
 * el límite y solo da/retira capacidades del catálogo 5A. */
export function ConsolidationLeadsPanel() {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [person, setPerson] = useState(null);
  const [needsAccount, setNeedsAccount] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState('');
  const [limit, setLimit] = useState(3);
  const [showHistory, setShowHistory] = useState(false);
  const load = useCallback(() => {
    axios.get(`${API}/api/consolidation/leads`, getAuthHeaders()).then((response) => { setData(response.data); setLimit(response.data.limit); }).catch(() => setData(null));
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  if (!data) return null;

  const designate = async () => {
    if (!person) return;
    setBusy('add');
    try {
      await axios.post(`${API}/api/consolidation/leads`, { person_id: person.person_id, ...(needsAccount ? { email: email.trim(), temporary_password: password } : {}) }, getAuthHeaders());
      toast.success(`${person.name} ahora es encargado de Consolidación`);
      setPerson(null); setNeedsAccount(false); setEmail(''); setPassword(''); load();
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (error?.response?.status === 422 && detail?.needs_account) { setNeedsAccount(true); toast.message(detail.message); }
      else toast.error(apiErrorMessage(error, 'No se pudo designar'));
    } finally { setBusy(''); }
  };
  const remove = async (item) => {
    if (!window.confirm(`¿Quitar a ${item.name} como encargado de Consolidación? Se retiran los permisos que se le dieron con esta designación.`)) return;
    setBusy(item.designation_id);
    try { await axios.delete(`${API}/api/consolidation/leads/${item.designation_id}`, getAuthHeaders()); toast.success('Encargado retirado'); load(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo quitar')); } finally { setBusy(''); }
  };
  const saveLimit = async () => {
    setBusy('limit');
    try { await axios.put(`${API}/api/consolidation/leads/settings`, { limit: Number(limit) }, getAuthHeaders()); toast.success('Límite actualizado'); load(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo cambiar el límite')); } finally { setBusy(''); }
  };
  const full = data.items.length >= data.limit;
  return (
    <section className="mx-4 mt-6 rounded-xl border border-[#E8E5DE] bg-white p-4 sm:mx-6 sm:p-5 lg:mx-8" data-testid="consolidation-leads-panel">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 font-['Spectral'] text-xl font-semibold text-[#101D36]"><ShieldCheck className="h-5 w-5 text-[#9A7A2F]" />Encargados de Consolidación</h2>
          <p className="text-sm text-slate-600">{data.items.length} de {data.limit} · Ven el panorama completo y gestionan asignación, reasignación y avance.</p>
        </div>
        {data.can_manage && <div className="flex items-center gap-2"><label className="text-sm text-slate-600" htmlFor="leads-limit">Límite</label><input id="leads-limit" type="number" min={1} max={10} value={limit} onChange={(event) => setLimit(event.target.value)} className="h-11 w-20 rounded-lg border border-[#D9D4C7] px-2 text-base" data-testid="leads-limit" /><button type="button" onClick={saveLimit} disabled={busy === 'limit' || Number(limit) === data.limit} className="min-h-11 rounded-lg border border-[#D9D4C7] px-3 text-sm font-semibold text-[#101D36] disabled:opacity-50" data-testid="leads-limit-save">Guardar</button></div>}
      </div>

      <ul className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
        {data.items.length === 0 && <li className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">Aún no hay encargados designados.</li>}
        {data.items.map((item) => (
          <li key={item.designation_id} className="flex items-start justify-between gap-2 rounded-lg border border-[#EEECE6] bg-[#FBFAF7] p-3" data-testid={`lead-${item.person_id}`}>
            <div className="min-w-0"><p className="truncate text-base font-semibold text-[#101D36]">{item.name}</p><p className="truncate text-xs text-slate-500">{item.email || 'Sin correo'}{item.account_created ? ' · cuenta creada al designar' : ''}</p><p className="text-xs text-slate-500">Desde {fmt(item.designated_at)}{item.designated_by_name ? ` · por ${item.designated_by_name}` : ''}</p></div>
            {data.can_manage && <button type="button" onClick={() => remove(item)} disabled={busy === item.designation_id} className="grid h-11 w-11 shrink-0 place-items-center rounded-md text-[#8f382f] hover:bg-red-50" aria-label={`Quitar a ${item.name}`} data-testid={`lead-remove-${item.person_id}`}>{busy === item.designation_id ? <Loader2 className="h-5 w-5 animate-spin" /> : <Trash2 className="h-5 w-5" />}</button>}
          </li>
        ))}
      </ul>

      {data.can_manage && (full
        ? <p className="mt-3 text-sm text-amber-800">Se alcanzó el límite. Quita a alguien o sube el límite para designar otro encargado.</p>
        : <div className="mt-4 space-y-2 rounded-lg border border-[#EEECE6] p-3" data-testid="leads-add">
            <p className="text-sm font-semibold text-[#101D36]">Designar encargado (desde Persona 360)</p>
            <PersonPicker value={person} onChange={(value) => { setPerson(value); setNeedsAccount(false); }} testId="leads-person" />
            {needsAccount && <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" data-testid="leads-account">
              <p className="text-sm text-slate-600 sm:col-span-2">Esta persona no tiene cuenta. Se creará una cuenta de nivel persona con los permisos de encargado.</p>
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Correo" className="h-12 rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="leads-email" />
              <input type="text" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Contraseña temporal (mín. 10)" className="h-12 rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="leads-password" />
            </div>}
            <button type="button" onClick={designate} disabled={!person || busy === 'add' || (needsAccount && (!email.trim() || password.length < 10))} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#101D36] px-4 text-base font-semibold text-white disabled:opacity-50 sm:w-auto" data-testid="leads-designate">{busy === 'add' ? <Loader2 className="h-5 w-5 animate-spin" /> : <UserPlus className="h-5 w-5" />}{needsAccount ? 'Crear cuenta y designar' : 'Designar'}</button>
          </div>)}

      <details className="mt-3 text-sm text-slate-600"><summary className="min-h-10 cursor-pointer py-2 font-semibold text-[#101D36]">Permisos que recibe un encargado</summary><ul className="list-disc pl-5">{data.capabilities.map((key) => <li key={key}>{CAPABILITY_LABELS[key] || key}</li>)}</ul><p className="mt-1 text-xs">Al quitarlo se retiran solo los que se le dieron con la designación.</p></details>
      {data.history.length > 0 && <div className="mt-2">
        <button type="button" onClick={() => setShowHistory(!showHistory)} className="inline-flex min-h-10 items-center gap-1 text-sm font-semibold text-[#101D36]" data-testid="leads-history-toggle">Historial ({data.history.length})<ChevronDown className={`h-4 w-4 transition ${showHistory ? 'rotate-180' : ''}`} /></button>
        {showHistory && <ul className="mt-1 space-y-1 text-sm text-slate-600" data-testid="leads-history">{data.history.map((item) => <li key={item.designation_id}>{item.name}: {fmt(item.designated_at)} → {fmt(item.removed_at)}{item.removed_by_name ? ` (retirado por ${item.removed_by_name})` : ''}</li>)}</ul>}
      </div>}
    </section>
  );
}
