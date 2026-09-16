/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

import { FinanceEmpty, FinanceShell, Money } from '../../components/finance/FinanceShell';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { useAuth } from '../../context/AuthContext';
import { displayLabel } from '../../lib/displayLabels';

const reportOptions = ['income-expense', 'fund-balances', 'budget-vs-actual', 'activity', 'financial-position', 'cash-flow', 'contributions', 'contributions-by-family', 'expenses-by-ministry', 'payables', 'deposits', 'reconciliations', 'recurring', 'audit'];

const moneyKeys = new Set(['amount_cents', 'debit_cents', 'credit_cents', 'budget_cents', 'actual_cents', 'variance_cents', 'total_cents', 'difference_cents', 'statement_ending_balance_cents']);

export default function FinanceReportsPage() {
  const { API, getAuthHeaders } = useAuth();
  const [reportKey, setReportKey] = useState('income-expense');
  const [dates, setDates] = useState({ start: '', end: '' });
  const [data, setData] = useState(null);
  const load = async () => { const params = new URLSearchParams(); if (dates.start) params.set('start', dates.start); if (dates.end) params.set('end', dates.end); const response = await axios.get(`${API}/api/finance/reports/${reportKey}?${params}`, getAuthHeaders()); setData(response.data); };
  useEffect(() => { load().catch(() => toast.error('No se pudo cargar el reporte')); }, [reportKey]);
  const rows = data?.items || data?.balances || data?.data || [];
  const normalizedRows = rows.map((row) => ({ ...(typeof row._id === 'object' ? row._id : {}), ...row, _id: undefined }));
  const keys = normalizedRows.length ? Object.keys(normalizedRows[0]).filter((key) => key !== '_id' && typeof normalizedRows[0][key] !== 'object') : [];
  return <FinanceShell title="Reportes financieros" description="Reportes operativos, ejecutivos y de auditoría con acceso financiero protegido."><section className="border bg-white p-4" data-testid="finance-report-controls"><div className="grid gap-2 sm:grid-cols-[1fr_180px_180px_auto]"><Select value={reportKey} onValueChange={setReportKey}><SelectTrigger data-testid="report-type-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{reportOptions.map((item) => <SelectItem key={item} value={item}>{displayLabel(item)}</SelectItem>)}</SelectContent></Select><Input type="date" value={dates.start} onChange={(event) => setDates({ ...dates, start: event.target.value })} data-testid="report-start-date" /><Input type="date" value={dates.end} onChange={(event) => setDates({ ...dates, end: event.target.value })} data-testid="report-end-date" /><Button onClick={load} data-testid="run-finance-report">Actualizar</Button></div></section><section className="mt-5 overflow-x-auto border bg-white" data-testid="finance-report-results">{normalizedRows.length ? <table className="w-full min-w-[760px] text-sm"><thead><tr className="border-b bg-slate-50">{keys.map((key) => <th key={key} className="p-3 text-left">{displayLabel(key)}</th>)}</tr></thead><tbody>{normalizedRows.map((row, index) => <tr key={row.entry_id || row.expense_id || row.deposit_id || row.reconciliation_id || index} className="border-b">{keys.map((key) => <td key={key} className="p-3">{moneyKeys.has(key) ? <Money cents={row[key]} /> : String(row[key] ?? '—')}</td>)}</tr>)}</tbody></table> : <FinanceEmpty>No hay datos reales para este reporte y período.</FinanceEmpty>}</section></FinanceShell>;
}