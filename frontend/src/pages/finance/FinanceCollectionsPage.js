import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate, useParams } from 'react-router-dom';
import { Ban, CheckCircle2, FileUp, Link2, Plus, Send } from 'lucide-react';
import { toast } from 'sonner';

import { FinanceEmpty, FinanceShell, Money } from '../../components/finance/FinanceShell';
import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';

const METHODS = { cash: 'Efectivo', zelle: 'Zelle', other: 'Otro' };
const STATUS = { registering: 'Registrando', registered: 'Registrada · falta validar', validated: 'Validada', cash_received: 'Efectivo recibido por Tesorería', deposited: 'Depositada' };
const field = 'h-12 w-full border border-slate-300 bg-white px-3 text-base';
const button = 'inline-flex min-h-12 items-center justify-center gap-2 px-4 text-base font-semibold disabled:opacity-50';
const toCents = (value) => Math.round(Number(String(value || '').replace(/[^0-9.]/g, '')) * 100);
const today = () => new Date().toLocaleDateString('en-CA');

function useApi() {
  const { API, getAuthHeaders } = useAuth();
  return useCallback((method, path, data, extra = {}) => axios({ method, url: `${API}${path}`, data, ...getAuthHeaders(), ...extra }).then((response) => response.data), [API, getAuthHeaders]);
}

/** Nuevo flujo de Finanzas · P2: registro y cuadre de la colecta (efectivo, Zelle y total separados). */
export default function FinanceCollectionsPage() {
  const { collectionId } = useParams();
  const api = useApi();
  const [roles, setRoles] = useState(null);
  useEffect(() => { api('get', '/api/finance/my-roles').then(setRoles).catch(() => setRoles({})); }, [api]);
  if (!roles) return <FinanceShell title="Colecta" description="Registro y cuadre de la colecta."><p>Cargando…</p></FinanceShell>;
  return collectionId ? <CollectionDetail id={collectionId} roles={roles} /> : <CollectionList roles={roles} />;
}

function CollectionList({ roles }) {
  const api = useApi();
  const navigate = useNavigate();
  const [items, setItems] = useState(null);
  const [form, setForm] = useState({ service_date: today(), service_name: 'Servicio del domingo', is_test: false });
  const [showTest, setShowTest] = useState(false);
  const load = useCallback(() => api('get', `/api/finance/collections?include_test=${showTest}`).then((data) => setItems(data.items)).catch((error) => toast.error(apiErrorMessage(error, 'No se pudieron cargar las colectas'))), [api, showTest]);
  useEffect(() => { load(); }, [load]);
  const open = async (event) => {
    event.preventDefault();
    try { const data = await api('post', '/api/finance/collections', form); navigate(`/finanzas/colecta/${data.collection_id}`); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo abrir la colecta')); }
  };
  return (
    <FinanceShell title="Colecta" description="Cada colecta pasa por: Registrada › Validada por segunda persona › Efectivo recibido por Tesorería › Depositada.">
      {roles.record && (
        <form onSubmit={open} className="mb-6 grid gap-3 border bg-white p-4 sm:grid-cols-[1fr_2fr_auto_auto]" data-testid="collection-open-form">
          <input type="date" className={field} value={form.service_date} onChange={(event) => setForm({ ...form, service_date: event.target.value })} required />
          <input className={field} value={form.service_name} onChange={(event) => setForm({ ...form, service_name: event.target.value })} placeholder="Servicio" required />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_test} onChange={(event) => setForm({ ...form, is_test: event.target.checked })} />Prueba</label>
          <button className={`${button} bg-[#102A2D] text-white`} data-testid="collection-open"><Plus className="h-5 w-5" />Abrir colecta</button>
        </form>
      )}
      <label className="mb-3 flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={showTest} onChange={(event) => setShowTest(event.target.checked)} />Mostrar colectas de prueba</label>
      {!items ? <p>Cargando…</p> : items.length === 0 ? <FinanceEmpty>Todavía no hay colectas.</FinanceEmpty> : (
        <ul className="space-y-2" data-testid="collection-list">{items.map((item) => (
          <li key={item.collection_id}><button type="button" onClick={() => navigate(`/finanzas/colecta/${item.collection_id}`)} className="flex w-full flex-wrap items-center justify-between gap-2 border bg-white p-4 text-left hover:border-[#B5953F]">
            <span><b className="block text-[#102A2D]">{item.service_name} · {item.service_date}{item.is_test ? ' · PRUEBA' : ''}</b><span className="text-sm text-slate-600">{STATUS[item.status] || item.status}</span></span>
            <span className="text-right text-sm">Total <b><Money cents={item.summary.total_cents} /></b><span className="block text-slate-500">Efectivo <Money cents={item.summary.cash_detail_cents} /> · Zelle <Money cents={item.summary.zelle_cents} /></span></span>
          </button></li>
        ))}</ul>
      )}
      {(roles.record || roles.treasury) && <ZellePanel />}
    </FinanceShell>
  );
}

function PersonPicker({ value, onChange }) {
  const api = useApi();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  useEffect(() => {
    if (value || query.trim().length < 2) { setResults([]); return undefined; }
    const timer = setTimeout(() => api('get', `/api/finance/contributors/search?search=${encodeURIComponent(query.trim())}`).then((data) => setResults(data.items || [])).catch(() => setResults([])), 250);
    return () => clearTimeout(timer);
  }, [api, query, value]);
  if (value) return <div className="flex items-center justify-between border bg-slate-50 px-3 py-2"><b>{value.name}</b><button type="button" className="text-sm underline" onClick={() => { onChange(null); setQuery(''); }}>Cambiar</button></div>;
  return (
    <div className="relative">
      <input className={field} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar persona" data-testid="collection-person-search" />
      {results.length > 0 && <div className="absolute z-20 mt-1 max-h-60 w-full overflow-y-auto border bg-white shadow-lg">{results.map((person) => <button type="button" key={person.person_id} className="block w-full border-b px-3 py-2 text-left hover:bg-slate-50" onClick={() => onChange(person)}>{person.name}</button>)}</div>}
    </div>
  );
}

function CollectionDetail({ id, roles }) {
  const api = useApi();
  const [data, setData] = useState(null);
  const [catalog, setCatalog] = useState({ funds: [], contribution_types: [] });
  const [zelle, setZelle] = useState([]);
  const empty = { person: null, anonymous: false, contribution_type: 'tithe', fund_id: '', amount: '', method: 'cash', reference: '' };
  const [item, setItem] = useState(empty);
  const [count, setCount] = useState({ cash: '', envelopes: '' });
  const [notes, setNotes] = useState({});
  const load = useCallback(() => api('get', `/api/finance/collections/${id}`).then(setData).catch((error) => toast.error(apiErrorMessage(error, 'No se pudo cargar la colecta'))), [api, id]);
  useEffect(() => { load(); api('get', '/api/finance/catalog').then((value) => { setCatalog(value); setItem((old) => ({ ...old, fund_id: old.fund_id || value.funds.find((fund) => fund.code === 'GENERAL')?.fund_id || '' })); }); }, [api, load]);
  useEffect(() => { if (data && roles.record) api('get', `/api/finance/zelle?unmatched=true&include_test=${Boolean(data.is_test)}`).then((value) => setZelle(value.items)).catch(() => setZelle([])); }, [api, data, roles.record]);
  if (!data) return <FinanceShell title="Colecta" description=""><p>Cargando…</p></FinanceShell>;
  const editable = roles.record && data.status === 'registering';
  // P3: enviada o validada → solo correcciones (guardan valor anterior, motivo y quién; piden validar otra vez).
  const correcting = roles.record && ['registered', 'validated'].includes(data.status);
  const canEdit = editable || correcting;
  const askReason = (text) => { const reason = window.prompt(text || 'Motivo de la corrección'); return reason && reason.trim().length >= 5 ? reason.trim() : null; };
  const correction = (body, message) => run(api('post', `/api/finance/collections/${id}/corrections`, body), message || 'Corrección guardada: falta validar otra vez');
  const run = async (promise, message) => { try { setData(await promise); if (message) toast.success(message); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); } };
  const itemBody = () => ({ person_id: item.anonymous ? null : item.person?.person_id, anonymous: item.anonymous, contribution_type: item.contribution_type, fund_id: item.fund_id, amount_cents: toCents(item.amount), method: item.method, reference: item.reference || null });
  const addItem = (event) => {
    event.preventDefault();
    const reset = () => setItem((old) => ({ ...empty, fund_id: old.fund_id, method: old.method }));
    if (correcting) { const reason = askReason('Motivo para agregar este aporte'); if (reason) correction({ action: 'add', reason, item: itemBody() }).then(reset); return; }
    run(api('post', `/api/finance/collections/${id}/items`, itemBody()), 'Aporte registrado').then(reset);
  };
  const correctAmount = (row) => {
    const amount = window.prompt('Monto correcto en dólares', (row.amount_cents / 100).toFixed(2)); if (!amount) return;
    const reason = askReason(); if (!reason) return;
    correction({ action: 'update', item_id: row.item_id, reason, item: { person_id: row.person_id || null, anonymous: Boolean(row.anonymous), contribution_type: row.contribution_type, fund_id: row.fund_id, amount_cents: toCents(amount), method: row.method, reference: row.reference || null } });
  };
  const s = data.summary;
  const typeName = (key) => catalog.contribution_types.find((row) => row.type_key === key)?.name || key;
  const fundName = (key) => catalog.funds.find((row) => row.fund_id === key)?.name || 'Fondo';
  return (
    <FinanceShell title={`${data.service_name} · ${data.service_date}${data.is_test ? ' · PRUEBA' : ''}`} description={STATUS[data.status] || data.status}>
      <ol className="mb-5 flex flex-wrap gap-2 text-sm" data-testid="collection-timeline">{data.timeline.map((stage) => <li key={`${stage.stage}-${stage.at}`} className="border bg-white px-3 py-2"><b>{stage.label}</b> · {stage.by_name || 'Usuario'} · {new Date(stage.at).toLocaleString('es')}</li>)}</ol>
      <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6" data-testid="collection-summary">
        {[['Efectivo (detalle)', s.cash_detail_cents], ['Efectivo contado', s.cash_counted_cents], ['Zelle', s.zelle_cents], ['Otros medios', s.other_cents], ['Total general', s.total_cents]].map(([label, cents]) => <article key={label} className="border bg-white p-4"><p className="text-xs uppercase text-slate-500">{label}</p><p className="mt-1 text-xl font-semibold">{cents == null ? '—' : <Money cents={cents} />}</p></article>)}
        <article className="border bg-white p-4"><p className="text-xs uppercase text-slate-500">Sobres</p><p className="mt-1 text-xl font-semibold">{s.envelopes_counted ?? '—'} / {s.envelopes_registered}</p></article>
      </section>

      {s.differences.length > 0 && (
        <section className="mt-5 space-y-2 border border-amber-300 bg-amber-50 p-4" data-testid="collection-differences">
          <h2 className="text-lg font-semibold">Diferencias</h2>
          {s.differences.map((diff) => (
            <div key={diff.kind} className="space-y-1 border-t border-amber-200 pt-2 text-sm">
              <p><b>{diff.label}</b>{diff.difference_cents != null && <> · <Money cents={diff.difference_cents} /></>}{diff.difference != null && ` · ${diff.difference}`}{diff.amount_cents != null && <> · <Money cents={diff.amount_cents} /></>}</p>
              {diff.explanation ? <p className="text-slate-700">Explicación: {diff.explanation.note} ({diff.explanation.by_name})</p> : (editable || (roles.record && data.status === 'registered')) && (
                <div className="flex flex-wrap gap-2"><input className={`${field} flex-1`} value={notes[diff.kind] || ''} onChange={(event) => setNotes({ ...notes, [diff.kind]: event.target.value })} placeholder="¿Por qué hay esta diferencia?" /><button type="button" className={`${button} bg-amber-700 text-white`} disabled={(notes[diff.kind] || '').trim().length < 5} onClick={() => run(api('post', `/api/finance/collections/${id}/explanations`, { kind: diff.kind, note: notes[diff.kind] }), 'Diferencia documentada')}>Documentar</button></div>
              )}
            </div>
          ))}
        </section>
      )}

      {correcting && <p className="mt-5 border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">La colecta ya se envió: cada cambio es una corrección con motivo, queda el valor anterior y otra persona debe validar otra vez.</p>}
      {canEdit && (
        <form onSubmit={addItem} className="mt-5 grid gap-3 border bg-white p-4 md:grid-cols-2 lg:grid-cols-4" data-testid="collection-item-form">
          <div className="md:col-span-2">{item.anonymous ? <p className="flex h-12 items-center border bg-slate-50 px-3 font-semibold">ANÓNIMO</p> : <PersonPicker value={item.person} onChange={(person) => setItem({ ...item, person })} />}</div>
          <label className="flex items-center gap-2 text-base"><input type="checkbox" checked={item.anonymous} onChange={(event) => setItem({ ...item, anonymous: event.target.checked, person: null })} />Anónimo</label>
          <select className={field} value={item.contribution_type} onChange={(event) => setItem({ ...item, contribution_type: event.target.value })}>{catalog.contribution_types.filter((row) => row.active).map((row) => <option key={row.type_key} value={row.type_key}>{row.name}</option>)}</select>
          <select className={field} value={item.fund_id} onChange={(event) => setItem({ ...item, fund_id: event.target.value })}>{catalog.funds.filter((row) => row.active).map((row) => <option key={row.fund_id} value={row.fund_id}>{row.name}</option>)}</select>
          <input className={field} inputMode="decimal" value={item.amount} onChange={(event) => setItem({ ...item, amount: event.target.value })} placeholder="Monto $" required />
          <select className={field} value={item.method} onChange={(event) => setItem({ ...item, method: event.target.value })}>{Object.entries(METHODS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
          <input className={field} value={item.reference} onChange={(event) => setItem({ ...item, reference: event.target.value })} placeholder={item.method === 'zelle' ? 'Confirmación Zelle' : 'Número de sobre'} />
          <button className={`${button} bg-[#102A2D] text-white lg:col-span-4`} disabled={!toCents(item.amount) || (!item.anonymous && !item.person)} data-testid="collection-item-add"><Plus className="h-5 w-5" />{correcting ? 'Agregar aporte (corrección)' : 'Registrar aporte'}</button>
        </form>
      )}

      <section className="mt-5 overflow-x-auto border bg-white" data-testid="collection-items">
        <table className="w-full min-w-[760px] text-sm"><thead><tr className="border-b bg-slate-50 text-left"><th className="p-3">Persona</th><th className="p-3">Concepto</th><th className="p-3">Fondo</th><th className="p-3">Medio</th><th className="p-3">Referencia</th><th className="p-3 text-right">Monto</th><th className="p-3" /></tr></thead>
          <tbody>{data.items.map((row) => (
            <tr key={row.item_id} className={`border-b ${row.status !== 'active' ? 'text-slate-400 line-through' : ''}`}>
              <td className="p-3">{row.person_name}</td><td className="p-3">{typeName(row.contribution_type)}</td><td className="p-3">{fundName(row.fund_id)}</td>
              <td className="p-3">{METHODS[row.method]}{row.method === 'zelle' && row.status === 'active' && (row.zelle_tx_id ? <span className="ml-1 text-emerald-700">· verificado</span> : <span className="ml-1 text-amber-700">· sin verificar</span>)}</td>
              <td className="p-3">{row.reference || '—'}</td><td className="p-3 text-right font-semibold"><Money cents={row.amount_cents} /></td>
              <td className="p-3">{correcting && row.status === 'active' && (
                <span className="flex flex-wrap justify-end gap-1">
                  <button type="button" className="inline-flex min-h-10 items-center gap-1 border px-2" onClick={() => correctAmount(row)}>Corregir monto</button>
                  <button type="button" className="inline-flex min-h-10 items-center gap-1 border px-2 text-red-700" onClick={() => { const reason = askReason('Motivo para anular este aporte'); if (reason) correction({ action: 'void', item_id: row.item_id, reason }); }}><Ban className="h-4 w-4" />Anular</button>
                </span>
              )}{editable && row.status === 'active' && (
                <span className="flex flex-wrap justify-end gap-1">
                  {row.method === 'zelle' && !row.zelle_tx_id && zelle.filter((tx) => tx.amount_cents === row.amount_cents).slice(0, 3).map((tx) => <button key={tx.tx_id} type="button" className="inline-flex min-h-10 items-center gap-1 border px-2" title={`${tx.received_date} · ${tx.sender_name}`} onClick={() => run(api('post', `/api/finance/collections/${id}/items/${row.item_id}/match-zelle`, { tx_id: tx.tx_id }), 'Zelle verificado')}><Link2 className="h-4 w-4" />{tx.received_date} {tx.sender_name}</button>)}
                  <button type="button" className="inline-flex min-h-10 items-center gap-1 border px-2 text-red-700" onClick={() => { const reason = window.prompt('Motivo para anular este aporte'); if (reason && reason.trim().length >= 3) run(api('post', `/api/finance/collections/${id}/items/${row.item_id}/void`, { reason }), 'Aporte anulado'); }}><Ban className="h-4 w-4" />Anular</button>
                </span>
              )}{row.status !== 'active' && <span className="text-xs">Anulado: {row.void_reason}</span>}</td>
            </tr>
          ))}</tbody></table>
      </section>

      {editable && (
        <section className="mt-5 grid gap-3 border bg-white p-4 sm:grid-cols-[1fr_1fr_auto]" data-testid="collection-cash-count">
          <input className={field} inputMode="decimal" value={count.cash} onChange={(event) => setCount({ ...count, cash: event.target.value })} placeholder="Efectivo contado $" />
          <input className={field} inputMode="numeric" value={count.envelopes} onChange={(event) => setCount({ ...count, envelopes: event.target.value })} placeholder="Sobres contados" />
          <button type="button" className={`${button} border border-[#102A2D]`} onClick={() => run(api('post', `/api/finance/collections/${id}/cash-count`, { counted_cash_cents: toCents(count.cash), envelope_count: count.envelopes === '' ? null : Number(count.envelopes) }), 'Conteo guardado')}><CheckCircle2 className="h-5 w-5" />Guardar conteo</button>
        </section>
      )}
      {correcting && (
        <button type="button" className={`${button} mt-5 border border-[#102A2D]`} onClick={() => { const cash = window.prompt('Efectivo contado correcto en dólares'); if (!cash) return; const envelopes = window.prompt('Sobres contados', String(s.envelopes_counted ?? '')); const reason = askReason(); if (reason) correction({ action: 'cash_count', reason, cash_count: { counted_cash_cents: toCents(cash), envelope_count: envelopes === '' || envelopes == null ? null : Number(envelopes) } }); }}>Corregir conteo de efectivo</button>
      )}
      {roles.verify && data.status === 'registered' && (
        <section className="mt-5 flex flex-wrap gap-3 border border-emerald-300 bg-emerald-50 p-4" data-testid="collection-verify">
          <p className="w-full text-sm text-emerald-900">Segunda persona: revise el conteo y el detalle. Quien registró o corrigió la colecta no puede validarla.</p>
          <button type="button" className={`${button} bg-emerald-700 text-white`} disabled={s.pending_explanations.length > 0} onClick={() => run(api('post', `/api/finance/collections/${id}/validate`), 'Cuadre confirmado')} data-testid="collection-validate"><CheckCircle2 className="h-5 w-5" />Confirmar cuadre</button>
          <button type="button" className={`${button} border border-amber-700 text-amber-800`} onClick={() => { const note = askReason('¿Qué debe revisar Finanzas?'); if (note) run(api('post', `/api/finance/collections/${id}/return`, { note }), 'Devuelta a Finanzas'); }}>Devolver con observaciones</button>
        </section>
      )}
      <CashHandover data={data} roles={roles} run={run} api={api} id={id} />
      <Deposits data={data} roles={roles} run={run} api={api} id={id} accounts={catalog.accounts || []} />
      {(data.corrections || []).length > 0 && (
        <section className="mt-5 border bg-white p-4" data-testid="collection-corrections"><h2 className="text-lg font-semibold">Correcciones</h2>
          <ul className="mt-2 divide-y text-sm">{data.corrections.map((row) => <li key={row.correction_id} className="py-2"><b>{row.by_name}</b> · {new Date(row.at).toLocaleString('es')} · {row.reason}{row.before?.amount_cents != null && <> · antes <Money cents={row.before.amount_cents} /></>}{row.after?.amount_cents != null && <> · después <Money cents={row.after.amount_cents} /></>}{row.before?.counted_cash_cents != null && <> · conteo antes <Money cents={row.before.counted_cash_cents} /></>}</li>)}</ul>
        </section>
      )}
      {editable && <button type="button" className={`${button} mt-5 w-full bg-emerald-700 text-white`} disabled={s.pending_explanations.length > 0 || !s.items} onClick={() => run(api('post', `/api/finance/collections/${id}/submit`), 'Enviada: falta que otra persona valide el cuadre')} data-testid="collection-submit"><Send className="h-5 w-5" />Enviar a validación</button>}
    </FinanceShell>
  );
}

/** P4: Finanzas entrega el efectivo; Tesorería cuenta y confirma desde su usuario (el Zelle no es efectivo). */
function CashHandover({ data, roles, run, api, id }) {
  const expected = data.validated_summary?.cash_detail_cents ?? data.summary.cash_detail_cents;
  const [amount, setAmount] = useState((expected / 100).toFixed(2));
  const [received, setReceived] = useState('');
  const [note, setNote] = useState('');
  const handover = data.handover;
  const reception = data.reception;
  if (!['validated', 'cash_received', 'deposited'].includes(data.status)) return null;
  return (
    <section className="mt-5 space-y-3 border bg-white p-4" data-testid="collection-handover">
      <h2 className="text-lg font-semibold">Entrega del efectivo a Tesorería</h2>
      <p className="text-sm text-slate-600">Efectivo validado: <b><Money cents={expected} /></b>. El Zelle (<Money cents={data.summary.zelle_cents} />) es parte de la colecta pero no del efectivo que se entrega.</p>
      {handover && <p className="text-sm">Entregó <b>{handover.delivered_by_name}</b>: <Money cents={handover.delivered_cents} /> · {new Date(handover.delivered_at).toLocaleString('es')}</p>}
      {roles.record && data.status === 'validated' && (
        <div className="flex flex-wrap gap-2"><input className={`${field} max-w-[12rem]`} inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} /><button type="button" className={`${button} bg-[#102A2D] text-white`} onClick={() => run(api('post', `/api/finance/collections/${id}/handover`, { delivered_cents: toCents(amount) }), 'Entrega registrada: falta que Tesorería confirme')} data-testid="collection-handover-register">{handover ? 'Cambiar entrega' : 'Registrar entrega'}</button></div>
      )}
      {roles.treasury && data.status === 'validated' && handover && (
        <div className="flex flex-wrap gap-2 border-t pt-3"><input className={`${field} max-w-[12rem]`} inputMode="decimal" value={received} onChange={(event) => setReceived(event.target.value)} placeholder="Recibí $" /><input className={`${field} flex-1`} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Nota (opcional)" /><button type="button" className={`${button} bg-emerald-700 text-white`} disabled={received === ''} onClick={() => run(api('post', `/api/finance/collections/${id}/receive`, { received_cents: toCents(received), note: note || null }), 'Recepción confirmada')} data-testid="collection-receive">Confirmar lo que recibí</button></div>
      )}
      {reception && (
        <div className="border-t pt-3 text-sm">
          <p>Recibió <b>{reception.received_by_name}</b>: <Money cents={reception.received_cents} /> · {new Date(reception.received_at).toLocaleString('es')}{reception.note ? ` · ${reception.note}` : ''}</p>
          {reception.difference_status === 'pending' && (
            <div className="mt-2 space-y-2 border border-amber-300 bg-amber-50 p-3"><p className="font-semibold text-amber-900">Diferencia pendiente de aclarar: <Money cents={reception.difference_cents} /> frente a lo entregado</p>
              {(roles.record || roles.treasury) && <button type="button" className={`${button} border border-amber-700 text-amber-800`} onClick={() => { const text = window.prompt('¿Qué pasó con la diferencia?'); if (text && text.trim().length >= 5) run(api('post', `/api/finance/collections/${id}/clarify-cash`, { note: text }), 'Diferencia aclarada'); }}>Aclarar diferencia</button>}
            </div>
          )}
          {reception.difference_status === 'clarified' && <p className="mt-1 text-slate-700">Diferencia aclarada por {reception.clarification.by_name}: {reception.clarification.note}</p>}
        </div>
      )}
    </section>
  );
}

/** P5: Tesorería deposita (monto, fecha, cuenta y comprobante); el sistema muestra el saldo pendiente. */
function Deposits({ data, roles, run, api, id, accounts }) {
  const banks = accounts.filter((account) => account.account_type === 'asset' && account.active && !['1010', '1090'].includes(account.code));
  const [form, setForm] = useState({ deposit_date: today(), bank_account_id: '', amount: '', reference: '' });
  const [file, setFile] = useState(null);
  if (!['cash_received', 'deposited'].includes(data.status)) return null;
  const save = async () => {
    try {
      const result = await api('post', `/api/finance/collections/${id}/deposits`, { deposit_date: form.deposit_date, bank_account_id: form.bank_account_id, amount_cents: toCents(form.amount), reference: form.reference || null });
      const depositId = result.deposits[result.deposits.length - 1].deposit_id;
      if (file) { const body = new FormData(); body.append('file', file); body.append('entity_type', 'deposit'); body.append('entity_id', depositId); await api('post', '/api/finance/documents', body); }
      setForm({ ...form, amount: '', reference: '' }); setFile(null);
      run(Promise.resolve(result), file ? 'Depósito y comprobante guardados' : 'Depósito guardado (puede subir el comprobante después)');
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo registrar el depósito')); }
  };
  return (
    <section className="mt-5 space-y-3 border bg-white p-4" data-testid="collection-deposits">
      <h2 className="text-lg font-semibold">Depósito</h2>
      <p className="text-sm">Efectivo recibido por Tesorería: <b><Money cents={data.reception?.received_cents || 0} /></b> · Pendiente de depositar: <b data-testid="collection-deposit-pending"><Money cents={data.deposit_pending_cents || 0} /></b></p>
      <ul className="divide-y text-sm">{(data.deposits || []).map((deposit) => <li key={deposit.deposit_id} className="py-2"><b><Money cents={deposit.total_cents} /></b> · {deposit.deposit_date} · {deposit.bank_name}{deposit.reference ? ` · ${deposit.reference}` : ''} · {deposit.created_by_name}</li>)}</ul>
      {roles.treasury && data.status === 'cash_received' && (
        <div className="grid gap-2 md:grid-cols-[1fr_2fr_1fr_1fr]">
          <input type="date" className={field} value={form.deposit_date} onChange={(event) => setForm({ ...form, deposit_date: event.target.value })} />
          <select className={field} value={form.bank_account_id} onChange={(event) => setForm({ ...form, bank_account_id: event.target.value })}><option value="">Banco o cuenta</option>{banks.map((account) => <option key={account.account_id} value={account.account_id}>{account.code} · {account.name}</option>)}</select>
          <input className={field} inputMode="decimal" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} placeholder="Monto $" />
          <input className={field} value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} placeholder="Número de boleta" />
          <label className={`${button} cursor-pointer border border-[#102A2D] md:col-span-2`}><FileUp className="h-5 w-5" />{file ? file.name : 'Comprobante (PDF o foto)'}<input type="file" accept="application/pdf,image/jpeg,image/png" className="hidden" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
          <button type="button" className={`${button} bg-emerald-700 text-white md:col-span-2`} disabled={!form.bank_account_id || !toCents(form.amount)} onClick={save} data-testid="collection-deposit-save">Registrar depósito</button>
        </div>
      )}
    </section>
  );
}

function ZellePanel() {
  const api = useApi();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ received_date: today(), amount: '', sender_name: '', confirmation: '', is_test: false });
  const load = useCallback(() => api('get', '/api/finance/zelle?include_test=true').then((data) => setItems(data.items)).catch(() => setItems([])), [api]);
  useEffect(() => { load(); }, [load]);
  const add = async (event) => {
    event.preventDefault();
    try { await api('post', '/api/finance/zelle', { received_date: form.received_date, amount_cents: toCents(form.amount), sender_name: form.sender_name, confirmation: form.confirmation || null, is_test: form.is_test }); toast.success('Zelle registrado'); setForm({ ...form, amount: '', sender_name: '', confirmation: '' }); load(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo registrar el Zelle')); }
  };
  const upload = async (file) => {
    if (!file) return;
    const body = new FormData(); body.append('file', file);
    try { const data = await api('post', `/api/finance/zelle/import-csv?is_test=${form.is_test}`, body); toast.success(`CSV: ${data.loaded} nuevos, ${data.repeated} repetidos${data.rejected.length ? `, ${data.rejected.length} con error` : ''}`); load(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo leer el CSV')); }
  };
  return (
    <section className="mt-8 space-y-3 border bg-white p-4" data-testid="zelle-panel">
      <h2 className="font-['Spectral'] text-2xl font-semibold">Zelle recibidos</h2>
      <p className="text-sm text-slate-600">Escríbalos a mano o suba el CSV del banco (montos en dólares). Una transacción repetida no entra dos veces y cada una solo puede coincidir con un aporte.</p>
      <form onSubmit={add} className="grid gap-2 md:grid-cols-[1fr_1fr_2fr_1fr_auto]">
        <input type="date" className={field} value={form.received_date} onChange={(event) => setForm({ ...form, received_date: event.target.value })} required />
        <input className={field} inputMode="decimal" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} placeholder="Monto $" required />
        <input className={field} value={form.sender_name} onChange={(event) => setForm({ ...form, sender_name: event.target.value })} placeholder="Nombre de quien envía" required />
        <input className={field} value={form.confirmation} onChange={(event) => setForm({ ...form, confirmation: event.target.value })} placeholder="Confirmación" />
        <button className={`${button} bg-[#102A2D] text-white`}>Agregar</button>
      </form>
      <div className="flex flex-wrap items-center gap-3">
        <label className={`${button} cursor-pointer border border-[#102A2D]`}><FileUp className="h-5 w-5" />Subir CSV del banco<input type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => upload(event.target.files?.[0])} data-testid="zelle-csv" /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_test} onChange={(event) => setForm({ ...form, is_test: event.target.checked })} />Datos de prueba</label>
      </div>
      <ul className="divide-y text-sm">{items.slice(0, 50).map((tx) => <li key={tx.tx_id} className="flex flex-wrap justify-between gap-2 py-2"><span>{tx.received_date} · {tx.sender_name}{tx.confirmation ? ` · ${tx.confirmation}` : ''}{tx.is_test ? ' · PRUEBA' : ''}</span><span><Money cents={tx.amount_cents} /> · {tx.matched_item_id ? 'Coincide con un aporte' : 'Sin aporte'}</span></li>)}</ul>
    </section>
  );
}
