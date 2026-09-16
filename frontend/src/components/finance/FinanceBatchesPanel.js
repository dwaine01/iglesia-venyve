/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Landmark, Scale } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { useAuth } from '../../context/AuthContext';
import { displayLabel } from '../../lib/displayLabels';
import { FinanceEmpty, Money } from './FinanceShell';

const today = () => new Date().toISOString().slice(0, 10);

export const FinanceBatchesPanel = () => {
  const { API, getAuthHeaders, user } = useAuth();
  const [items, setItems] = useState([]);
  const [contributions, setContributions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [selected, setSelected] = useState([]);
  const [form, setForm] = useState({ service_name: 'Servicio domingo', batch_date: today(), expected_envelope_count: '', location: '', notes: '' });
  const [counts, setCounts] = useState({});
  const [depositForms, setDepositForms] = useState({});
  const [varianceReasons, setVarianceReasons] = useState({});

  const load = async () => {
    const [batchesResponse, contributionsResponse, catalogResponse] = await Promise.all([
      axios.get(`${API}/api/finance/batches`, getAuthHeaders()),
      axios.get(`${API}/api/finance/contributions`, getAuthHeaders()),
      axios.get(`${API}/api/finance/catalog`, getAuthHeaders()),
    ]);
    setItems(batchesResponse.data.items || []);
    setContributions((contributionsResponse.data.items || []).filter((item) => !item.batch_id && item.status !== 'corrected'));
    setAccounts((catalogResponse.data.accounts || []).filter((item) => item.account_type === 'asset' && item.code !== '1010'));
  };
  useEffect(() => { load().catch(() => toast.error('No se pudieron cargar los conteos')); }, []);
  const selectedTotal = useMemo(() => contributions.filter((item) => selected.includes(item.contribution_id)).reduce((sum, item) => sum + item.amount_cents, 0), [contributions, selected]);
  const createBatch = async (event) => {
    event.preventDefault();
    if (!selected.length) return toast.error('Seleccione contribuciones');
    try {
      await axios.post(`${API}/api/finance/batches`, { ...form, service_date: form.batch_date, expected_envelope_count: form.expected_envelope_count === '' ? null : Number(form.expected_envelope_count), contribution_ids: selected }, getAuthHeaders());
      toast.success('Sesión de conteo abierta'); setSelected([]); await load();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo abrir el conteo'); }
  };
  const addCount = async (batchId) => {
    const count = counts[batchId] || {};
    try {
      await axios.post(`${API}/api/finance/batches/${batchId}/counts`, { cash_cents: Math.round(Number(count.cash || 0) * 100), check_cents: Math.round(Number(count.check || 0) * 100), other_cents: Math.round(Number(count.other || 0) * 100), envelope_count: count.envelopes === '' || count.envelopes === undefined ? null : Number(count.envelopes), notes: count.notes || null }, getAuthHeaders());
      toast.success('Conteo guardado'); setCounts({ ...counts, [batchId]: {} }); await load();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo guardar el conteo'); }
  };
  const resolveVariance = async (batchId) => {
    try { await axios.post(`${API}/api/finance/batches/${batchId}/resolve-variance`, { reason: varianceReasons[batchId] }, getAuthHeaders()); toast.success('Diferencia documentada'); await load(); } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo resolver la diferencia'); }
  };
  const createDeposit = async (batch) => {
    const deposit = depositForms[batch.batch_id] || {};
    if (!deposit.bank_account_id) return toast.error('Seleccione cuenta bancaria');
    try {
      await axios.post(`${API}/api/finance/deposits`, { deposit_date: deposit.deposit_date || today(), bank_account_id: deposit.bank_account_id, contribution_ids: batch.contribution_ids, batch_id: batch.batch_id, reference: deposit.reference || null }, getAuthHeaders());
      toast.success('Depósito creado sin duplicar el ingreso'); await load();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo crear el depósito'); }
  };
  return <section className="space-y-5" data-testid="finance-batches-panel">
    <form onSubmit={createBatch} className="border bg-white p-4 sm:p-5" data-testid="batch-create-form"><div className="grid gap-3 md:grid-cols-4"><div><Label>Servicio / sesión</Label><Input className="mt-1" value={form.service_name} onChange={(event) => setForm({ ...form, service_name: event.target.value })} data-testid="batch-service-name-input" /></div><div><Label>Fecha</Label><Input className="mt-1" type="date" value={form.batch_date} onChange={(event) => setForm({ ...form, batch_date: event.target.value })} data-testid="batch-date-input" /></div><div><Label>Sobres esperados</Label><Input className="mt-1" type="number" min="0" value={form.expected_envelope_count} onChange={(event) => setForm({ ...form, expected_envelope_count: event.target.value })} data-testid="batch-envelope-count-input" /></div><div><Label>Lugar</Label><Input className="mt-1" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} data-testid="batch-location-input" /></div></div><Textarea className="mt-3" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} placeholder="Notas del servicio" data-testid="batch-notes-input" />
      <div className="mt-4 max-h-64 overflow-y-auto border" data-testid="batch-contribution-selector">{contributions.length ? contributions.map((item) => <label key={item.contribution_id} className="flex items-center justify-between gap-3 border-b p-3 text-sm"><span className="flex items-center gap-2"><Checkbox checked={selected.includes(item.contribution_id)} onCheckedChange={(checked) => setSelected(checked ? [...selected, item.contribution_id] : selected.filter((id) => id !== item.contribution_id))} data-testid={`select-batch-contribution-${item.contribution_id}`} />{item.received_date} · {displayLabel(item.payment_method)} · {item.envelope_number ? `Sobre ${item.envelope_number}` : 'Sin sobre'}</span><Money cents={item.amount_cents} /></label>) : <FinanceEmpty>No hay contribuciones pendientes de conteo.</FinanceEmpty>}</div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="font-semibold">{selected.length} registros iniciales · <Money cents={selectedTotal} /></p><Button data-testid="create-batch-button"><Scale className="h-4 w-4" />Abrir sesión</Button></div>
    </form>
    {items.map((batch) => { const count = counts[batch.batch_id] || {}; const deposit = depositForms[batch.batch_id] || {}; return <article key={batch.batch_id} className="border bg-white p-4 sm:p-5" data-testid={`batch-card-${batch.batch_id}`}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase text-slate-500">{displayLabel(batch.status)}</p><h3 className="font-['Spectral'] text-xl font-semibold">{batch.service_name || 'Sesión de conteo'}</h3><p className="text-sm text-slate-500">{batch.service_date || batch.batch_date} · {batch.registered_envelope_count} registrados / {batch.expected_envelope_count} esperados</p></div><p className="text-xl font-semibold"><Money cents={batch.expected_total_cents} /></p></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="border bg-slate-50 p-3"><p className="text-xs uppercase text-slate-500">Por método</p>{Object.entries(batch.expected_payment_totals || {}).map(([key, value]) => <p key={key} className="mt-1 flex justify-between text-sm"><span>{displayLabel(key)}</span><Money cents={value} /></p>)}</div><div className="border bg-slate-50 p-3"><p className="text-xs uppercase text-slate-500">Por concepto</p>{Object.entries(batch.expected_concept_totals || {}).map(([key, value]) => <p key={key} className="mt-1 flex justify-between text-sm"><span>{displayLabel(key)}</span><Money cents={value} /></p>)}</div></div>
      {batch.status === 'collecting' && <div className="mt-4 flex flex-wrap gap-2 border-l-4 border-[#B5953F] bg-[#FFFDF7] p-4"><Button asChild><Link to={`/finanzas/contribuciones?batch_id=${batch.batch_id}`} data-testid={`register-batch-contribution-${batch.batch_id}`}>Registrar sobres</Link></Button><Button type="button" variant="outline" onClick={async () => { try { await axios.post(`${API}/api/finance/batches/${batch.batch_id}/start-count`, {}, getAuthHeaders()); toast.success('Captura cerrada; inicie doble conteo'); await load(); } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo iniciar conteo'); } }} data-testid={`start-batch-count-${batch.batch_id}`}>Cerrar captura e iniciar conteo</Button></div>}
      {['awaiting_first_count', 'awaiting_second_count'].includes(batch.status) && <div className="mt-4 grid gap-2 md:grid-cols-5"><Input type="number" step="0.01" placeholder="Efectivo" value={count.cash || ''} onChange={(event) => setCounts({ ...counts, [batch.batch_id]: { ...count, cash: event.target.value } })} data-testid={`batch-cash-${batch.batch_id}`} /><Input type="number" step="0.01" placeholder="Cheques" value={count.check || ''} onChange={(event) => setCounts({ ...counts, [batch.batch_id]: { ...count, check: event.target.value } })} data-testid={`batch-check-${batch.batch_id}`} /><Input type="number" step="0.01" placeholder="Otros" value={count.other || ''} onChange={(event) => setCounts({ ...counts, [batch.batch_id]: { ...count, other: event.target.value } })} data-testid={`batch-other-${batch.batch_id}`} /><Input type="number" placeholder="Sobres" value={count.envelopes || ''} onChange={(event) => setCounts({ ...counts, [batch.batch_id]: { ...count, envelopes: event.target.value } })} data-testid={`batch-envelopes-${batch.batch_id}`} /><Button type="button" onClick={() => addCount(batch.batch_id)} data-testid={`submit-batch-count-${batch.batch_id}`}>Guardar conteo</Button></div>}
      {batch.status === 'variance_review' && <div className="mt-4 border-l-4 border-amber-500 bg-amber-50 p-4"><p className="font-semibold">Diferencia de conteo</p><p className="text-sm">Debe recontarse o documentarse antes de depositar.</p>{user?.rol === 'pastor' && <div className="mt-3 flex flex-col gap-2 sm:flex-row"><Input value={varianceReasons[batch.batch_id] || ''} onChange={(event) => setVarianceReasons({ ...varianceReasons, [batch.batch_id]: event.target.value })} placeholder="Justificación autorizada" data-testid={`batch-variance-reason-${batch.batch_id}`} /><Button type="button" onClick={() => resolveVariance(batch.batch_id)} data-testid={`resolve-batch-variance-${batch.batch_id}`}>Autorizar diferencia</Button></div>}</div>}
      {batch.status === 'ready_for_deposit' && <div className="mt-4 grid gap-2 border-l-4 border-emerald-600 bg-emerald-50 p-4 md:grid-cols-[1fr_1fr_1fr_auto]"><Input type="date" value={deposit.deposit_date || today()} onChange={(event) => setDepositForms({ ...depositForms, [batch.batch_id]: { ...deposit, deposit_date: event.target.value } })} data-testid={`deposit-date-${batch.batch_id}`} /><Select value={deposit.bank_account_id || ''} onValueChange={(value) => setDepositForms({ ...depositForms, [batch.batch_id]: { ...deposit, bank_account_id: value } })}><SelectTrigger data-testid={`deposit-account-${batch.batch_id}`}><SelectValue placeholder="Cuenta bancaria" /></SelectTrigger><SelectContent className="bg-white">{accounts.map((account) => <SelectItem key={account.account_id} value={account.account_id}>{account.code} · {account.name}</SelectItem>)}</SelectContent></Select><Input value={deposit.reference || ''} onChange={(event) => setDepositForms({ ...depositForms, [batch.batch_id]: { ...deposit, reference: event.target.value } })} placeholder="Comprobante / referencia" data-testid={`deposit-reference-${batch.batch_id}`} /><Button type="button" onClick={() => createDeposit(batch)} data-testid={`create-deposit-${batch.batch_id}`}><Landmark className="h-4 w-4" />Depositar</Button></div>}
      {batch.status === 'deposited' && <p className="mt-4 flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4" />Depositado · trazabilidad conservada</p>}</article>; })}
  </section>;
};