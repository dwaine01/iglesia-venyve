import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowDownToLine, ArrowUpFromLine, CalendarClock, CircleDollarSign, Landmark, ReceiptText, WalletCards } from 'lucide-react';
import { toast } from 'sonner';

import { FinanceEmpty, FinanceShell, Money } from '../../components/finance/FinanceShell';
import { useAuth } from '../../context/AuthContext';

const metrics = [
  ['income_cents', 'Ingresó', ArrowDownToLine],
  ['expense_cents', 'Salió', ArrowUpFromLine],
  ['cash_cents', 'Tenemos', WalletCards],
  ['outstanding_payables_cents', 'Debemos', ReceiptText],
  ['net_cents', 'Resultado neto', CircleDollarSign],
  ['budget_remaining_cents', 'Presupuesto disponible', Landmark],
];

export default function FinanceDashboardPage() {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/api/finance/dashboard`, getAuthHeaders()).then((response) => setData(response.data)).catch(() => toast.error('No se pudo cargar el resumen financiero')); }, [API, getAuthHeaders]);
  return <FinanceShell title="Panorama financiero" description="Ingresos, gastos, efectivo, fondos y obligaciones calculados únicamente desde transacciones reales.">
    {!data ? <p data-testid="finance-dashboard-loading">Cargando…</p> : <><section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" data-testid="finance-dashboard-metrics">{metrics.map(([key, label, Icon]) => <article key={key} className="border bg-white p-5"><div className="flex items-center justify-between"><p className="text-xs uppercase text-slate-500">{label}</p><Icon className="h-4 w-4 text-[#B5953F]" /></div><p className="mt-3 text-2xl font-semibold" data-testid={`dashboard-${key}`}><Money cents={data[key] || 0} /></p></article>)}</section><section className="mt-6 grid gap-5 lg:grid-cols-[1.25fr_0.75fr]"><div className="border bg-white p-5"><h2 className="font-['Spectral'] text-2xl font-semibold">Disponible por fondo</h2><div className="mt-4 space-y-2">{data.fund_balances?.length ? data.fund_balances.map((fund) => <div key={fund.fund_id} className="flex items-center justify-between border-t pt-3 text-sm"><span>{fund.fund_name}</span><b><Money cents={fund.balance_cents} /></b></div>) : <FinanceEmpty>No hay actividad contabilizada por fondo.</FinanceEmpty>}</div></div><div className="border bg-[#102A2D] p-5 text-white"><h2 className="font-['Spectral'] text-2xl font-semibold">Próximos controles</h2><div className="mt-4 space-y-3 text-sm"><p className="flex justify-between"><span>Pagos próximos</span><b data-testid="dashboard-upcoming-payments">{data.upcoming_payments}</b></p><p className="flex justify-between"><span>Asientos pendientes</span><b>{data.pending_entries}</b></p><p className="flex justify-between"><span>Depósitos sin conciliar</span><b>{data.unreconciled_deposits}</b></p><p className="flex justify-between"><span>Cuentas por pagar</span><b>{data.unpaid_expenses}</b></p></div><p className="mt-5 flex items-center gap-2 border-t border-white/20 pt-4 text-xs text-white/60"><CalendarClock className="h-4 w-4" />Pushpay: {data.pushpay_status === 'connected' ? 'Conectado' : 'BLOCKED/MOCKED — credenciales requeridas'}</p></div></section></>}
  </FinanceShell>;
}