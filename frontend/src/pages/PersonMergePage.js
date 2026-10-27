import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { GitMerge, Loader2, Undo2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';

const LABELS = { process_enrollments: 'Expedientes', outreach_visits: 'Visitas', library_movements: 'Libros', person_contacts: 'Contactos', person_addresses: 'Direcciones',
  person_attendance: 'Asistencias', visitor_registrations: 'Registros de visitante', front_group_assignments: 'Grupos frontales', mentor_assignments: 'Mentorías', users: 'Cuenta' };
const refLabel = (key) => { const [collection] = key.split('.'); return LABELS[collection] || collection.replace(/_/g, ' '); };

/** Fusión guiada y reversible de personas duplicadas (auditoría 10/10). Nada se borra: la duplicada queda archivada. */
export default function PersonMergePage() {
  const { API, getAuthHeaders } = useAuth();
  const [groups, setGroups] = useState(null);
  const [dismissed, setDismissed] = useState([]);
  const [history, setHistory] = useState([]);
  const [plan, setPlan] = useState(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    axios.get(`${API}/api/person-merge/candidates`, getAuthHeaders()).then((response) => { setGroups(response.data.groups); setDismissed(response.data.dismissed || []); }).catch((error) => toast.error(apiErrorMessage(error, 'No se pudieron cargar los posibles duplicados')));
    axios.get(`${API}/api/person-merge/history`, getAuthHeaders()).then((response) => setHistory(response.data.items)).catch(() => setHistory([]));
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);

  const notDuplicate = async (group) => {
    const why = window.prompt('¿Por qué no es la misma persona? (p. ej. «Son madre e hijo, comparten teléfono»)', 'Familia: comparten teléfono');
    if (!why || why.trim().length < 3) return;
    setBusy(true);
    try { await axios.post(`${API}/api/person-merge/not-duplicate`, { person_ids: group.people.map((person) => person.person_id), reason: why.trim() }, getAuthHeaders()); toast.success('Marcado: no es duplicado (se puede deshacer)'); load(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo marcar')); } finally { setBusy(false); }
  };
  const restore = async (signature) => {
    setBusy(true);
    try { await axios.post(`${API}/api/person-merge/not-duplicate/undo`, { signature }, getAuthHeaders()); toast.success('El grupo vuelve a la lista'); load(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo deshacer')); } finally { setBusy(false); }
  };
  const review = async (keep, merged) => {
    setBusy(true);
    try { setPlan((await axios.post(`${API}/api/person-merge/preview`, { keep_person_id: keep, merged_person_id: merged }, getAuthHeaders())).data); setReason(''); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo revisar')); } finally { setBusy(false); }
  };
  const confirm = async () => {
    setBusy(true);
    try {
      const response = await axios.post(`${API}/api/person-merge`, { keep_person_id: plan.keep.person_id, merged_person_id: plan.merged.person_id, reason }, getAuthHeaders());
      toast.success(`Fusionadas: se movieron ${response.data.moved} registros${response.data.conflicts.length ? ` (${response.data.conflicts.length} quedaron con la duplicada)` : ''}`);
      setPlan(null); load();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo fusionar')); } finally { setBusy(false); }
  };
  const undo = async (mergeId) => {
    setBusy(true);
    try { const response = await axios.post(`${API}/api/person-merge/${mergeId}/undo`, {}, getAuthHeaders()); toast.success(`Fusión deshecha: ${response.data.restored} registros devueltos`); load(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo deshacer')); } finally { setBusy(false); }
  };

  const button = 'inline-flex min-h-11 items-center gap-1.5 rounded-lg border px-3 text-sm font-semibold disabled:opacity-50';
  return (
    <div className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6" data-testid="person-merge-page">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 font-['Spectral'] text-2xl font-semibold text-[#101D36]"><GitMerge className="h-6 w-6 text-[#9A7A2F]" />Personas duplicadas</h1>
        <p className="text-sm text-slate-600">Elija cuál se conserva, revise qué se mueve y confirme. La duplicada no se borra (queda archivada) y la fusión se puede deshacer.</p>
      </header>

      {plan && (
        <section className="space-y-3 rounded-xl border-2 border-[#C8A951] bg-[#FFFBEF] p-4" data-testid="person-merge-plan">
          <p className="text-base text-[#101D36]">Se conserva <b>{plan.keep.name}</b> ({plan.keep.person_number}). Pasa a ella todo lo de <b>{plan.merged.name}</b> ({plan.merged.person_number}):</p>
          <ul className="grid gap-1 text-sm sm:grid-cols-2">{Object.entries(plan.references).map(([key, count]) => <li key={key}>{refLabel(key)}: <b>{count}</b></li>)}</ul>
          {plan.total === 0 && <p className="text-sm text-slate-600">La duplicada no tiene registros: solo se archiva.</p>}
          {plan.conflicts.map((text) => <p key={text} className="rounded-lg bg-amber-100 p-2 text-sm text-amber-900">{text}</p>)}
          <label className="block text-sm font-semibold text-slate-700">¿Por qué son la misma persona?
            <input value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base font-normal" placeholder="Mismo teléfono y fecha de nacimiento…" data-testid="person-merge-reason" />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={`${button} border-[#132443] bg-[#132443] text-white`} disabled={busy || reason.trim().length < 3} onClick={confirm} data-testid="person-merge-confirm">{busy && <Loader2 className="h-4 w-4 animate-spin" />}Fusionar</button>
            <button type="button" className={button} onClick={() => setPlan(null)}>Cancelar</button>
          </div>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-[#101D36]">Posibles duplicados {groups ? `(${groups.length})` : ''}</h2>
        {!groups && <Loader2 className="h-5 w-5 animate-spin text-slate-400" />}
        {groups && groups.length === 0 && <p className="text-sm text-slate-500">No se encontraron personas con el mismo teléfono o nombre.</p>}
        {(groups || []).map((group) => (
          <div key={`${group.reason}-${group.key}`} className="rounded-xl border border-[#E8E5DE] bg-white p-3" data-testid="person-merge-group">
            <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{group.reason}: {group.key}</p>
              <button type="button" className={button} disabled={busy} onClick={() => notDuplicate(group)} data-testid="person-not-duplicate">No es duplicado</button></div>
            {group.suggest_merge === false && <p className="mt-1 text-xs text-slate-600" data-testid="person-merge-family-hint">Nombres distintos con el mismo teléfono: suele ser familia. No se sugiere fusionar.</p>}
            <ul className="mt-2 divide-y">{group.people.map((person, index) => (
              <li key={person.person_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span><a href={`/personas/${person.person_id}`} className="font-semibold text-[#101D36] hover:underline">{person.name}</a>
                  <span className="block text-xs text-slate-500">{[person.person_number, person.fecha_nacimiento, person.created_at && `creada ${person.created_at.slice(0, 10)}`].filter(Boolean).join(' · ')}</span></span>
                {index > 0 && group.suggest_merge !== false && <button type="button" className={button} disabled={busy} onClick={() => review(group.people[0].person_id, person.person_id)}>Fusionar con {group.people[0].name.split(' ')[0]} (la más antigua)</button>}
                {index === 0 && group.people.length === 2 && group.suggest_merge !== false && <button type="button" className={button} disabled={busy} onClick={() => review(group.people[1].person_id, person.person_id)}>Conservar la otra</button>}
              </li>
            ))}</ul>
          </div>
        ))}
      </section>

      {dismissed.length > 0 && (
        <section className="space-y-2 rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid="person-not-duplicate-list">
          <h2 className="text-lg font-semibold text-[#101D36]">Marcados «No es duplicado» ({dismissed.length})</h2>
          <ul className="divide-y">{dismissed.map((row) => (
            <li key={row.signature} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span>{row.people.join(' · ')}{row.reason ? ` — ${row.reason}` : ''}</span>
              <button type="button" className={button} disabled={busy} onClick={() => restore(row.signature)}><Undo2 className="h-4 w-4" />Volver a revisar</button>
            </li>
          ))}</ul>
        </section>
      )}

      {history.length > 0 && (
        <section className="space-y-2 rounded-xl border border-[#E8E5DE] bg-white p-4">
          <h2 className="text-lg font-semibold text-[#101D36]">Fusiones hechas</h2>
          <ul className="divide-y">{history.map((row) => (
            <li key={row.merge_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span>{row.merged_name || 'Persona'} → {row.keep_name || 'Persona'} · {row.at.slice(0, 10)} · {row.status === 'undone' ? 'Deshecha' : `${row.moved ?? 0} registros`}</span>
              {row.status === 'done' && <button type="button" className={button} disabled={busy} onClick={() => undo(row.merge_id)} data-testid="person-merge-undo"><Undo2 className="h-4 w-4" />Deshacer</button>}
            </li>
          ))}</ul>
        </section>
      )}
    </div>
  );
}
