import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowDownToLine, ArrowUpFromLine, CalendarClock, CircleDollarSign, Landmark, ReceiptText, WalletCards } from 'lucide-react';
import { toast } from 'sonner';

import { FinanceEmpty, FinanceShell, Money } from '../../components/finance/FinanceShell';
import { useFinanceRoles } from '../../components/finance/useFinanceRoles';
import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { hasCapability } from '../../lib/accessControl';

const metrics = [
  ['income_cents', 'Ingresó', ArrowDownToLine],
  ['expense_cents', 'Salió', ArrowUpFromLine],
  ['bank_and_cash_cents', 'En banco y caja', WalletCards],
  ['undeposited_cents', 'Recibido por depositar', WalletCards],
  ['outstanding_payables_cents', 'Debemos', ReceiptText],
  ['net_cents', 'Resultado neto', CircleDollarSign],
  ['budget_remaining_cents', 'Presupuesto disponible del año fiscal', Landmark],
];

/** F2: depósitos que quedaron en «ajuste requerido» porque se corrigió una contribución ya depositada. */
function DepositAdjustments({ onDone }) {
  const { API, getAuthHeaders, user } = useAuth();
  const [items, setItems] = useState([]);
  const [reason, setReason] = useState({});
  const [busy, setBusy] = useState('');
  const roles = useFinanceRoles();
  const load = useCallback(() => axios.get(`${API}/api/finance/deposits`, getAuthHeaders()).then((response) => setItems((response.data.items || []).filter((item) => item.status === 'adjustment_required'))).catch(() => setItems([])), [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  if (!items.length || !hasCapability(user, 'finance.manage')) return null;
  const resolve = async (depositId) => {
    setBusy(depositId);
    try { await axios.post(`${API}/api/finance/deposits/${depositId}/resolve-adjustment`, { reason: reason[depositId] || '' }, getAuthHeaders()); toast.success('Ajuste registrado: el asiento pasa a revisión y aprobación'); load(); onDone(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo registrar el ajuste')); } finally { setBusy(''); }
  };
  return <section className="mt-6 border border-amber-300 bg-amber-50 p-5" data-testid="finance-deposit-adjustments"><h2 className="font-['Spectral'] text-2xl font-semibold">Depósitos con ajuste pendiente</h2><p className="mt-1 text-sm text-slate-600">Se corrigió una contribución que ya estaba depositada. Registre el ajuste: el reemplazo queda en el mismo depósito y, si cambió el fondo o el monto, se crea un asiento de ajuste.</p>
    <ul className="mt-3 space-y-3">{items.map((item) => <li key={item.deposit_id} className="flex flex-wrap items-center gap-2 border-t pt-3 text-sm"><span className="min-w-[10rem] font-semibold">{item.deposit_date} · <Money cents={item.total_cents || 0} /></span>{roles.treasury && <><input value={reason[item.deposit_id] || ''} onChange={(event) => setReason((old) => ({ ...old, [item.deposit_id]: event.target.value }))} placeholder="Motivo del ajuste" className="h-11 min-w-[14rem] flex-1 border px-3" /><button type="button" disabled={busy === item.deposit_id || (reason[item.deposit_id] || '').trim().length < 5} onClick={() => resolve(item.deposit_id)} className="min-h-11 bg-[#102A2D] px-4 font-semibold text-white disabled:opacity-50" data-testid="finance-deposit-adjust">Registrar ajuste</button></>}</li>)}</ul></section>;
}

export default function FinanceDashboardPage() {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const load = useCallback(() => { axios.get(`${API}/api/finance/dashboard`, getAuthHeaders()).then((response) => setData(response.data)).catch(() => toast.error('No se pudo cargar el resumen financiero')); }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  return <FinanceShell title="Panorama financiero" description="Ingresos, gastos, efectivo, fondos y obligaciones calculados únicamente desde transacciones reales.">
    {!data ? <p data-testid="finance-dashboard-loading">Cargando…</p> : <><section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" data-testid="finance-dashboard-metrics">{metrics.map(([key, label, Icon]) => <article key={key} className="border bg-white p-5"><div className="flex items-center justify-between"><p className="text-xs uppercase text-slate-500">{label}</p><Icon className="h-4 w-4 text-[#B5953F]" /></div><p className="mt-3 text-2xl font-semibold" data-testid={`dashboard-${key}`}><Money cents={data[key] || 0} /></p>{key === 'budget_remaining_cents' && data.fiscal_year_from && <p className="mt-1 text-xs text-slate-500">Año fiscal {data.fiscal_year_from} a {data.fiscal_year_to}</p>}</article>)}<article className="border border-amber-300 bg-amber-50 p-5" data-testid="dashboard-pending-to-post"><div className="flex items-center justify-between"><p className="text-xs uppercase text-amber-900">Pendiente de contabilizar</p><ArrowDownToLine className="h-4 w-4 text-amber-700" /></div><p className="mt-3 text-2xl font-semibold text-amber-950"><Money cents={data.pending_to_post?.cents || 0} /></p><p className="mt-1 text-xs text-amber-900">{data.pending_to_post?.count || 0} aporte(s) registrados que aún no valida una segunda persona. No suman en «Ingresó».</p></article></section><section className="mt-6 grid gap-5 lg:grid-cols-[1.25fr_0.75fr]"><div className="border bg-white p-5"><h2 className="font-['Spectral'] text-2xl font-semibold">Disponible por fondo</h2><div className="mt-4 space-y-2">{data.fund_balances?.length ? data.fund_balances.map((fund) => <div key={fund.fund_id} className="flex items-center justify-between border-t pt-3 text-sm"><span>{fund.fund_name}</span><b><Money cents={fund.balance_cents} /></b></div>) : <FinanceEmpty>No hay actividad contabilizada por fondo.</FinanceEmpty>}</div></div><div className="border bg-[#102A2D] p-5 text-white"><h2 className="font-['Spectral'] text-2xl font-semibold">Próximos controles</h2><div className="mt-4 space-y-3 text-sm"><p className="flex justify-between"><span>Pagos próximos</span><b data-testid="dashboard-upcoming-payments">{data.upcoming_payments}</b></p><p className="flex justify-between"><span>Asientos pendientes</span><b>{data.pending_entries}</b></p><p className="flex justify-between"><span>Depósitos sin conciliar</span><b>{data.unreconciled_deposits}</b></p><p className="flex justify-between"><span>Cuentas por pagar</span><b>{data.unpaid_expenses}</b></p></div><p className="mt-5 flex items-center gap-2 border-t border-white/20 pt-4 text-xs text-white/60"><CalendarClock className="h-4 w-4" />Pushpay: {data.pushpay_status === 'connected' ? 'Conectado' : 'Apagado'}</p></div></section><DepositAdjustments onDone={load} /></>}
  </FinanceShell>;
}