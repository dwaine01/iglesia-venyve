import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, CheckCircle2, Loader2, Scale } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';

const fmt = (iso) => (iso ? new Date(iso).toLocaleString('es', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '');

/** Mi saldo calculado de la bitácora: recibidos − entregados − devueltos ± transferidos.
 * Las entregas sin descuento quedan aparte hasta que Librería las concilie. */
export function MyLedgerBalance() {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/api/library/ledger/my-balance`, getAuthHeaders()).then((response) => setData(response.data)).catch(() => setData({ items: [] })); }, [API, getAuthHeaders]);
  if (!data) return null;
  if (!data.items.length) return null;
  return (
    <section className="rounded-2xl border border-[#E8E5DE] bg-white p-4" data-testid="ledger-my-balance">
      <h2 className="flex items-center gap-2 font-serif text-xl text-[#132443]"><Scale className="h-5 w-5" />Mi saldo de libros</h2>
      <p className="mb-3 text-sm text-slate-600">Recibidos − entregados − devueltos ± transferidos, según la bitácora de Librería.</p>
      <div className="space-y-2">
        {data.items.map((item) => (
          <div key={item.book_id || item.name} className="rounded-xl border border-[#EEECE6] p-3" data-testid={`ledger-row-${item.book_id || 'sin-cargar'}`}>
            <p className="font-semibold text-[#132443]">{item.name}</p>
            <div className="mt-1 grid grid-cols-3 gap-2 text-center text-sm sm:grid-cols-6">
              {[['Recibidos', item.received + item.transferred_in], ['Entregados', item.delivered], ['Devueltos', item.returned], ['Transferidos', item.transferred_out], ['Saldo', item.balance], ['Sin conciliar', item.pending_delivered]].map(([label, value]) => (
                <div key={label} className={`rounded-lg p-2 ${label === 'Saldo' ? 'bg-[#eef5f0] font-semibold' : label === 'Sin conciliar' && value ? 'bg-amber-50 text-amber-900' : 'bg-[#FBFAF7]'}`}><p className="text-lg">{value}</p><p className="text-[11px] text-slate-600">{label}</p></div>
              ))}
            </div>
            {item.discrepancy ? <p className="mt-1 text-xs text-amber-800">El resumen de inventario dice {item.cached_on_hand}; Librería lo revisará.</p> : null}
          </div>
        ))}
      </div>
      {data.pending_total > 0 && <p className="mt-2 text-xs text-slate-500">«Sin conciliar» = libros entregados sin descuento de inventario. No restan de tu saldo hasta que Librería los concilie.</p>}
    </section>
  );
}

/** Librería: diferencias resumen vs bitácora y entregas pendientes de conciliar. Nada se corrige solo. */
export function ReconciliationPanel({ canReconcile }) {
  const { API, getAuthHeaders } = useAuth();
  const [report, setReport] = useState(null);
  const [pending, setPending] = useState([]);
  const [books, setBooks] = useState([]);
  const [target, setTarget] = useState(null);
  const [form, setForm] = useState({ book_id: '', register_missing_assignment: false, notes: '' });
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const load = useCallback(async () => {
    try {
      const [diff, list] = await Promise.all([axios.get(`${API}/api/library/ledger/discrepancies`, getAuthHeaders()), axios.get(`${API}/api/library/ledger/pending`, getAuthHeaders())]);
      setReport(diff.data); setPending(list.data.items || []);
    } catch (error) { setReport(null); }
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (target && !books.length) axios.get(`${API}/api/library/books`, getAuthHeaders()).then((response) => setBooks(response.data.items || [])).catch(() => {}); }, [target, books.length, API, getAuthHeaders]);
  if (!report) return null;
  const open = (item) => { setForm({ book_id: item.book_id || '', register_missing_assignment: false, notes: '' }); setTarget(item); };
  const reconcile = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/library/ledger/pending/${target.movement_id}/reconcile`, { ...form, book_id: form.book_id || null }, getAuthHeaders());
      toast.success('Entrega conciliada'); setTarget(null); load();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo conciliar')); } finally { setBusy(false); }
  };
  return (
    <section className="space-y-3 rounded-2xl border border-[#E8E5DE] bg-white p-4" data-testid="ledger-reconciliation">
      <h2 className="flex items-center gap-2 font-serif text-xl text-[#132443]"><Scale className="h-5 w-5" />Conciliación de libros</h2>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-xl bg-[#FBFAF7] p-3"><p className="text-2xl font-semibold text-[#132443]" data-testid="ledger-pending-total">{report.pending_total}</p><p className="text-xs text-slate-600">Libros entregados sin descuento (por conciliar)</p></div>
        <div className={`rounded-xl p-3 ${report.differences.length ? 'bg-amber-50' : 'bg-[#eef5f0]'}`}><p className="text-2xl font-semibold text-[#132443]" data-testid="ledger-differences-total">{report.differences.length}</p><p className="text-xs text-slate-600">Diferencias entre el resumen y la bitácora</p></div>
      </div>
      {report.differences.length > 0 && <div><p className="mb-1 flex items-center gap-1 text-sm font-semibold text-amber-900"><AlertTriangle className="h-4 w-4" />Diferencias (no se corrigen solas)</p>
        <ul className="space-y-1 text-sm">{report.differences.slice(0, showAll ? 500 : 10).map((row) => <li key={`${row.user_id}-${row.book_id}`} className="rounded-lg border border-amber-200 bg-amber-50 p-2">{row.user_name} · {row.book_name}: bitácora {row.ledger_balance}, resumen {row.cached_on_hand} ({row.difference > 0 ? '+' : ''}{row.difference})</li>)}</ul>
        {report.differences.length > 10 && <button type="button" onClick={() => setShowAll((value) => !value)} className="mt-1 min-h-11 text-sm font-semibold text-[#0879BE] underline" data-testid="ledger-differences-toggle">{showAll ? 'Ver menos' : `Ver las ${report.differences.length} diferencias`}</button>}</div>}
      {pending.length > 0 && <div><p className="mb-1 text-sm font-semibold text-[#132443]">Entregas por conciliar</p>
        <ul className="space-y-2">{pending.map((item) => (
          <li key={item.movement_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#EEECE6] p-2 text-sm" data-testid={`ledger-pending-${item.movement_id}`}>
            <span className="min-w-0"><b>{item.quantity} × {item.book_name}</b> · {item.from_holder_label} → {item.to_holder_label}<span className="block text-xs text-slate-500">{fmt(item.occurred_at)} · {item.pending_reason}</span></span>
            {canReconcile && <button type="button" onClick={() => open(item)} className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-[#132443] px-3 font-semibold text-[#132443]" data-testid="ledger-reconcile-open"><CheckCircle2 className="h-4 w-4" />Conciliar</button>}
          </li>))}</ul></div>}
      <Dialog open={Boolean(target)} onOpenChange={(value) => { if (!value) setTarget(null); }}>
        <DialogContent className="bg-white sm:max-w-md" data-testid="ledger-reconcile-dialog">
          <DialogHeader><DialogTitle>Conciliar entrega</DialogTitle><DialogDescription>{target ? `${target.quantity} × ${target.book_name} · ${target.from_holder_label}` : ''}</DialogDescription></DialogHeader>
          <label className="block"><span className="text-sm font-semibold text-slate-700">Libro del catálogo</span>
            <select value={form.book_id} onChange={(event) => setForm((current) => ({ ...current, book_id: event.target.value }))} className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" data-testid="ledger-reconcile-book">
              <option value="">Elegir…</option>{books.map((book) => <option key={book.book_id} value={book.book_id}>{book.name}{book.sku ? ` (${book.sku})` : ''}</option>)}
            </select></label>
          <label className="flex min-h-12 items-center gap-3 text-[15px]"><input type="checkbox" checked={form.register_missing_assignment} onChange={(event) => setForm((current) => ({ ...current, register_missing_assignment: event.target.checked }))} className="h-5 w-5 accent-[#132443]" data-testid="ledger-reconcile-assign" />Registrar la asignación que faltaba (Central → mentor)</label>
          <div className="sticky-actions"><button type="button" onClick={reconcile} disabled={busy || !form.book_id} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-50" data-testid="ledger-reconcile-run">{busy && <Loader2 className="h-5 w-5 animate-spin" />}Conciliar</button></div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
