import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Archive, ChevronDown, Loader2, RotateCcw, SearchCheck } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';

const STATUS = { completed: 'Completado', closed: 'Cerrado', cancelled: 'Cancelado', active: 'Activo', paused: 'En pausa', planned: 'Planificado' };
const fmt = (iso) => (iso ? new Date(iso).toLocaleString('es', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

/** Limpieza de expedientes duplicados (solo autoridad pastoral). El
 * diagnóstico no cambia nada; archivar NO borra (reversible, con auditoría);
 * el borrado definitivo lo decide el dueño después. */
export function EnrollmentCleanupPanel() {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [batches, setBatches] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [confirm, setConfirm] = useState(null); // { kind: 'archive' | 'restore', batch? }
  const [text, setText] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setData(null);
    try {
      const [diag, history] = await Promise.all([
        axios.get(`${API}/api/processes/cleanup/diagnostic`, { ...getAuthHeaders(), params: { limit: 1000 } }),
        axios.get(`${API}/api/processes/cleanup/batches`, getAuthHeaders()),
      ]);
      setData(diag.data); setBatches(history.data.items || []); setSelected(new Set());
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo cargar el diagnóstico')); setOpen(false); }
  }, [API, getAuthHeaders]);
  useEffect(() => { if (open) load(); }, [open, load]);
  const byPerson = useMemo(() => {
    const groups = new Map();
    (data?.candidates || []).forEach((row) => { if (!groups.has(row.person_id)) groups.set(row.person_id, []); groups.get(row.person_id).push(row); });
    return Array.from(groups.entries());
  }, [data]);
  const toggle = (ids, on) => setSelected((current) => { const next = new Set(current); ids.forEach((id) => (on ? next.add(id) : next.delete(id))); return next; });
  const expected = confirm?.kind === 'archive' ? `ARCHIVAR ${selected.size}` : 'RESTAURAR';
  const run = async () => {
    setBusy(true);
    try {
      if (confirm.kind === 'archive') {
        const response = await axios.post(`${API}/api/processes/cleanup/archive`, { enrollment_ids: Array.from(selected), confirm_text: text, note: note || null }, getAuthHeaders());
        toast.success(`${response.data.archived} expediente(s) archivado(s)${response.data.skipped.length ? ` · ${response.data.skipped.length} ya no eran candidatos` : ''}`);
      } else {
        const response = await axios.post(`${API}/api/processes/cleanup/restore`, { batch_id: confirm.batch.batch_id, confirm_text: text }, getAuthHeaders());
        toast.success(`${response.data.restored} expediente(s) restaurado(s)`);
      }
      setConfirm(null); setText(''); setNote(''); load();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo completar')); } finally { setBusy(false); }
  };

  return (
    <section className="rounded-2xl border border-[#E8E5DE] bg-white p-4" data-testid="cleanup-panel">
      <button type="button" onClick={() => setOpen((value) => !value)} className="flex min-h-12 w-full items-center justify-between gap-2 text-left" data-testid="cleanup-toggle">
        <span className="min-w-0"><span className="flex items-center gap-2 font-['Spectral'] text-xl font-semibold text-[#101D36]"><SearchCheck className="h-5 w-5 shrink-0" />Limpieza de expedientes duplicados</span><span className="block text-sm text-slate-600">Detecta expedientes repetidos de una misma persona (restos de pruebas) y los archiva sin borrarlos.</span></span>
        <ChevronDown className={`h-5 w-5 shrink-0 transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (!data ? <Loader2 className="mx-auto my-6 h-6 w-6 animate-spin text-slate-400" /> : (
        <div className="mt-3 space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="cleanup-summary">
            {[['Expedientes de Consolidación', data.enrollments], ['Personas únicas', data.people_processes], ['Personas con repetidos', data.with_duplicates], ['Candidatos a archivar', data.candidates_total]].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-[#EEECE6] bg-[#FBFAF7] p-3"><p className="text-2xl font-semibold text-[#101D36]">{value}</p><p className="text-xs text-slate-600">{label}</p></div>
            ))}
          </div>
          {data.open_duplicates.length > 0 && <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{data.open_duplicates.length} persona(s) con más de un expediente ABIERTO: no se archivan automáticamente; revísalos uno por uno.</p>}
          <p className="text-xs text-slate-500">Índice que impide dos expedientes activos de la misma persona y proceso: {data.unique_active_index ? 'activo' : 'NO encontrado'}.</p>

          {data.people.length > 0 && <div className="overflow-x-auto"><table className="w-full min-w-[480px] text-sm"><thead><tr className="border-b text-left text-xs uppercase text-slate-500"><th className="px-2 py-2">Persona</th><th className="px-2 py-2">Expedientes</th><th className="px-2 py-2">Por estado</th><th className="px-2 py-2">Candidatos</th></tr></thead>
            <tbody>{data.people.slice(0, 10).map((row) => <tr key={`${row.person_id}-${row.process_key}`} className="border-b border-[#F1EFEA]"><td className="px-2 py-2 font-semibold">{row.name}</td><td className="px-2 py-2">{row.total}</td><td className="px-2 py-2 text-xs text-slate-600">{Object.entries(row.by_status).map(([key, value]) => `${STATUS[key] || key}: ${value}`).join(' · ')}</td><td className="px-2 py-2">{row.candidates}</td></tr>)}</tbody></table></div>}

          {byPerson.length === 0 ? <p className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-sm text-slate-500" data-testid="cleanup-empty">No hay duplicados claros para archivar.</p> : <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="flex min-h-11 items-center gap-2 text-sm font-semibold"><input type="checkbox" className="h-5 w-5 accent-[#132443]" checked={selected.size === data.candidates.length} onChange={(event) => toggle(data.candidates.map((row) => row.enrollment_id), event.target.checked)} data-testid="cleanup-select-all" />Seleccionar todos ({data.candidates.length})</label>
              <button type="button" disabled={!selected.size} onClick={() => { setText(''); setConfirm({ kind: 'archive' }); }} className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-[#132443] px-4 text-sm font-semibold text-white disabled:opacity-50" data-testid="cleanup-archive"><Archive className="h-4 w-4" />Archivar {selected.size}</button>
            </div>
            <div className="space-y-2">
              {byPerson.map(([personId, rows]) => (
                <details key={personId} className="rounded-xl border border-[#E8E5DE] p-3" data-testid={`cleanup-person-${personId}`}>
                  <summary className="flex min-h-11 cursor-pointer items-center justify-between gap-2"><span className="min-w-0 truncate font-semibold text-[#101D36]">{rows[0].name} · {rows.length} candidato(s)</span>
                    <input type="checkbox" className="h-5 w-5 shrink-0 accent-[#132443]" checked={rows.every((row) => selected.has(row.enrollment_id))} onClick={(event) => event.stopPropagation()} onChange={(event) => toggle(rows.map((row) => row.enrollment_id), event.target.checked)} aria-label={`Seleccionar los de ${rows[0].name}`} /></summary>
                  <p className="mt-1 text-xs text-slate-600">Razón: {rows[0].reasons.join(' · ')}</p>
                  <ul className="mt-2 max-h-56 space-y-1 overflow-y-auto text-xs text-slate-600">{rows.map((row) => <li key={row.enrollment_id} className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-[#132443]" checked={selected.has(row.enrollment_id)} onChange={(event) => toggle([row.enrollment_id], event.target.checked)} />{STATUS[row.status] || row.status} · {fmt(row.created_at)}{row.mentor_name ? ` · ${row.mentor_name}` : ''}{row.test_mentor ? ' (prueba)' : ''}</li>)}</ul>
                </details>
              ))}
            </div>
          </>}

          {batches.length > 0 && <div><p className="mb-1 text-sm font-semibold text-[#101D36]">Lotes archivados (reversibles)</p><ul className="space-y-1">{batches.map((batch) => (
            <li key={batch.batch_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#EEECE6] p-2 text-sm" data-testid={`cleanup-batch-${batch.batch_id}`}>
              <span>{fmt(batch.created_at)} · {batch.count} expediente(s){batch.actor_name ? ` · ${batch.actor_name}` : ''}{batch.restored_at ? ' · restaurado' : ''}{batch.note ? ` · ${batch.note}` : ''}</span>
              {!batch.restored_at && <button type="button" onClick={() => { setText(''); setConfirm({ kind: 'restore', batch }); }} className="inline-flex min-h-10 items-center gap-1 rounded-md border border-[#D9D4C7] px-3 text-xs font-semibold" data-testid="cleanup-restore"><RotateCcw className="h-3.5 w-3.5" />Restaurar</button>}
            </li>))}</ul></div>}
        </div>
      ))}

      <Dialog open={Boolean(confirm)} onOpenChange={(value) => { if (!value) setConfirm(null); }}>
        <DialogContent className="bg-white sm:max-w-md" data-testid="cleanup-confirm">
          <DialogHeader><DialogTitle>{confirm?.kind === 'archive' ? `Archivar ${selected.size} expediente(s)` : 'Restaurar lote'}</DialogTitle>
            <DialogDescription>{confirm?.kind === 'archive' ? 'No se borra nada: salen de los listados y de las cifras, queda auditoría y se puede restaurar.' : 'Cada expediente vuelve a su estado anterior.'}</DialogDescription></DialogHeader>
          {confirm?.kind === 'archive' && <label className="block"><span className="text-sm font-semibold text-slate-700">Nota (opcional)</span><input value={note} onChange={(event) => setNote(event.target.value)} className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" placeholder="Ej.: restos de pruebas de QA" /></label>}
          <label className="block"><span className="text-sm font-semibold text-slate-700">Escribe <b>{expected}</b> para confirmar</span><input value={text} onChange={(event) => setText(event.target.value)} autoComplete="off" className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="cleanup-confirm-text" /></label>
          <div className="sticky-actions"><button type="button" onClick={run} disabled={busy || text.trim().toUpperCase() !== expected} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-50" data-testid="cleanup-confirm-run">{busy && <Loader2 className="h-5 w-5 animate-spin" />}{confirm?.kind === 'archive' ? 'Archivar' : 'Restaurar'}</button></div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
