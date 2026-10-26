import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { BookOpen, Loader2, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { PersonPicker } from '../outreach/CreateCampaignDialog';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';

const when = (iso) => (iso ? new Date(iso).toLocaleString('es', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '');

/** Tareas «completar nombre»: libros entregados en una vivienda sin saber a
 * quién. Completar vincula a la persona (misma revisión de duplicados) y NO
 * vuelve a descontar el libro. */
export function RecipientTasks({ refreshKey = 0, onChanged }) {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]);
  const [target, setTarget] = useState(null);
  const [mode, setMode] = useState('new');
  const [form, setForm] = useState({ name: '', phone: '', person: null });
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    axios.get(`${API}/api/library/ledger/unidentified`, getAuthHeaders()).then((response) => setItems(response.data.items || [])).catch(() => setItems([]));
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load, refreshKey]);
  if (!items.length) return null;
  const open = (item) => { setForm({ name: '', phone: '', person: null }); setMode('new'); setTarget(item); };
  const save = async () => {
    setBusy(true);
    try {
      const body = mode === 'existing' ? { contact_type: 'existing', person_id: form.person?.person_id, contact_phone: form.phone.trim() || null } : { contact_type: 'new', contact_name: form.name.trim(), contact_phone: form.phone.trim() || null };
      await axios.post(`${API}/api/library/ledger/movements/${target.movement_id}/recipient`, body, getAuthHeaders());
      toast.success('Destinatario completado (el libro no se volvió a descontar)');
      setTarget(null); load(); onChanged?.();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo completar el destinatario')); } finally { setBusy(false); }
  };
  const ready = mode === 'existing' ? Boolean(form.person) : form.name.trim().length >= 2;
  return (
    <section className="space-y-2 rounded-2xl border border-amber-200 bg-amber-50 p-3" data-testid="recipient-tasks">
      <p className="flex items-center gap-2 text-base font-semibold text-amber-900"><BookOpen className="h-5 w-5" />Completar a quién se entregó ({items.length})</p>
      <ul className="space-y-2">{items.map((item) => (
        <li key={item.movement_id} className="flex items-center justify-between gap-2 rounded-xl border border-amber-200 bg-white p-3" data-testid={`recipient-task-${item.movement_id}`}>
          <span className="min-w-0"><span className="block truncate text-[15px] font-semibold text-[#101D36]">{item.address_line1 || 'Vivienda'}{item.address_line2 ? ` · ${item.address_line2}` : ''}</span><span className="block text-sm text-slate-600">{item.quantity} × {item.book_name} · {when(item.occurred_at)}</span></span>
          <button type="button" onClick={() => open(item)} className="inline-flex min-h-11 shrink-0 items-center gap-1 rounded-lg bg-[#132443] px-3 text-[15px] font-semibold text-white" data-testid="recipient-task-open"><UserPlus className="h-4 w-4" />Completar</button>
        </li>))}</ul>
      <Dialog open={Boolean(target)} onOpenChange={(value) => { if (!value) setTarget(null); }}>
        <DialogContent className="vv-fit bg-white sm:max-w-md" data-testid="recipient-dialog">
          <DialogHeader><DialogTitle>¿A quién se entregó?</DialogTitle><DialogDescription>{target ? `${target.quantity} × ${target.book_name} · ${target.address_line1 || ''}` : ''}</DialogDescription></DialogHeader>
          <div className="grid grid-cols-2 gap-1 rounded-xl bg-[#EEECE6] p-1">{[['new', 'Persona nueva'], ['existing', 'Ya está en Persona 360']].map(([key, label]) => <button key={key} type="button" onClick={() => setMode(key)} className={`min-h-11 rounded-lg text-[15px] font-semibold ${mode === key ? 'bg-white shadow' : 'text-slate-600'}`} data-testid={`recipient-mode-${key}`}>{label}</button>)}</div>
          {mode === 'new' ? <>
            <label className="block"><span className="text-sm font-semibold text-slate-700">Nombre</span><input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} autoComplete="off" className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="recipient-name" /></label>
            <label className="block"><span className="text-sm font-semibold text-slate-700">Teléfono (opcional)</span><input value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} inputMode="tel" autoComplete="off" className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="recipient-phone" /></label>
          </> : <>
            <PersonPicker value={form.person} onChange={(person) => setForm((current) => ({ ...current, person }))} testId="recipient-person" />
            {form.person && <label className="block"><span className="text-sm font-semibold text-slate-700">Teléfono de la persona</span><input value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} inputMode="tel" autoComplete="off" placeholder="El que tiene registrado" className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="recipient-existing-phone" /></label>}
          </>}
          <div className="sticky-actions"><button type="button" onClick={save} disabled={busy || !ready} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-50" data-testid="recipient-save">{busy && <Loader2 className="h-5 w-5 animate-spin" />}Guardar destinatario</button></div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
