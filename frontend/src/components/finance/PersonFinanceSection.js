import React, { useEffect, useState } from 'react';
import axios from 'axios';

import { FinanceEmpty, Money } from './FinanceShell';
import { useAuth } from '../../context/AuthContext';
import { displayLabel } from '../../lib/displayLabels';
import { churchToday } from '../../lib/churchDate';

const iso = (value) => churchToday(value);
const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const monthLabel = (key) => `${MONTHS[Number(key.slice(5, 7)) - 1]} ${key.slice(0, 4)}`;

/** Perfil 360 · Finanzas (decisión del dueño): historial de diezmos, ofrendas y donaciones, último diezmo,
 * totales del período elegido y meses sin registros. Solo suma lo contabilizado; lo pendiente y las promesas van aparte. Solo lectura, sin etiquetas automáticas. La ven la pastora
 * y quien ella autorice; cada consulta queda registrada en el servidor. */
export const PersonFinanceSection = ({ personId }) => {
  const { API, getAuthHeaders } = useAuth();
  const now = new Date();
  const [scope, setScope] = useState('person');
  const [range, setRange] = useState({ start: `${now.getFullYear()}-01-01`, end: iso(now) });
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    setData(null); setError('');
    axios.get(`${API}/api/finance/persons/${personId}/contributions`, { ...getAuthHeaders(), params: { scope, start: range.start, end: range.end } })
      .then((response) => setData(response.data)).catch((err) => setError(err?.response?.data?.detail || 'No se pudo cargar'));
  }, [API, getAuthHeaders, personId, scope, range]);
  const preset = (months) => { const start = new Date(); start.setMonth(start.getMonth() - months + 1, 1); setRange({ start: iso(start), end: iso(new Date()) }); };
  const chip = (active) => `min-h-11 rounded-lg border px-3 text-sm font-semibold ${active ? 'border-[#102A2D] bg-[#102A2D] text-white' : 'border-slate-300 bg-white text-[#102A2D]'}`;
  return (
    <section className="space-y-4" data-testid="person-finance-section">
      <div>
        <h2 className="font-['Spectral'] text-2xl font-semibold text-[#102A2D]">Finanzas</h2>
        <p className="text-sm text-slate-500">Solo lectura. La ven la pastora y quien ella autorice; cada consulta queda registrada.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={chip(scope === 'person')} onClick={() => setScope('person')} data-testid="person-contributions-button">Persona</button>
        <button type="button" className={chip(scope === 'family')} onClick={() => setScope('family')} data-testid="family-contributions-button">Familia</button>
        <span className="mx-1 border-l" />
        <button type="button" className={chip(false)} onClick={() => setRange({ start: `${now.getFullYear()}-01-01`, end: iso(now) })}>Este año</button>
        <button type="button" className={chip(false)} onClick={() => preset(12)}>Últimos 12 meses</button>
        <input type="date" className="min-h-11 border px-2" value={range.start} onChange={(event) => setRange({ ...range, start: event.target.value })} aria-label="Desde" />
        <input type="date" className="min-h-11 border px-2" value={range.end} onChange={(event) => setRange({ ...range, end: event.target.value })} aria-label="Hasta" />
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      {data && (
        <>
          <div className="grid gap-3 sm:grid-cols-3" data-testid="person-finance-summary">
            <article className="border bg-white p-4"><p className="text-xs uppercase text-slate-500">Total del período</p><p className="mt-1 text-2xl font-semibold" data-testid="person-contributions-total"><Money cents={data.total_cents} /></p></article>
            <article className="border bg-white p-4"><p className="text-xs uppercase text-slate-500">Último diezmo</p><p className="mt-1 text-lg font-semibold" data-testid="person-last-tithe">{data.last_tithe ? <>{data.last_tithe.received_date} · <Money cents={data.last_tithe.amount_cents} /></> : 'Sin registros'}</p></article>
            <article className="border bg-white p-4"><p className="text-xs uppercase text-slate-500">Meses sin registros</p><p className="mt-1 text-lg font-semibold">{data.months_without_records.length} de {data.months_in_period}</p></article>
          </div>
          {Object.keys(data.totals_by_type).length > 0 && <p className="text-sm text-slate-700">{Object.entries(data.totals_by_type).map(([key, cents]) => <span key={key} className="mr-3 inline-block">{displayLabel(key)}: <b><Money cents={cents} /></b></span>)}</p>}
          {data.months_without_records.length > 0 && <p className="text-sm text-slate-600" data-testid="person-months-without">Sin registros en: {data.months_without_records.map(monthLabel).join(', ')}</p>}
          <div className="overflow-x-auto border bg-white">
            <table className="w-full min-w-[480px] text-sm"><thead><tr className="border-b bg-slate-50 text-left"><th className="p-3">Fecha</th><th className="p-3">Concepto</th><th className="p-3 text-right">Monto</th></tr></thead>
              <tbody>{data.items.map((item) => <tr key={item.contribution_id} className="border-b"><td className="p-3">{item.received_date}</td><td className="p-3">{displayLabel(item.contribution_type)}{item.campaign_name ? ` · ${item.campaign_name}` : ''}</td><td className="p-3 text-right"><Money cents={item.amount_cents} /></td></tr>)}</tbody>
            </table>
            {!data.items.length && <FinanceEmpty>No hay registros en este período.</FinanceEmpty>}
          </div>
          {data.pending?.items?.length > 0 && (
            <div className="border border-amber-300 bg-amber-50 p-4" data-testid="person-finance-pending">
              <p className="font-semibold text-amber-950">Pendiente de contabilizar · <Money cents={data.pending.cents} /></p>
              <p className="text-xs text-amber-900">Registrado, pero aún no lo valida una segunda persona: no suma en el total ni en el Resumen de Finanzas.</p>
              <ul className="mt-2 space-y-1 text-sm">{data.pending.items.map((item) => <li key={item.contribution_id || item.item_id}>{item.received_date || '—'} · {displayLabel(item.contribution_type)}{item.campaign_name ? ` · ${item.campaign_name}` : ''} · <b><Money cents={item.amount_cents} /></b> <span className="text-xs text-amber-900">({item.label})</span></li>)}</ul>
            </div>
          )}
          {data.pledges?.length > 0 && (
            <div className="border border-sky-200 bg-sky-50 p-4" data-testid="person-finance-pledges">
              <p className="font-semibold text-sky-950">Promesa pendiente · <Money cents={data.pledges.reduce((sum, item) => sum + item.amount_cents, 0)} /></p>
              <p className="text-xs text-sky-900">Prometido en la campaña y aún no recibido. Nunca suma como ingreso.</p>
              <ul className="mt-2 space-y-1 text-sm">{data.pledges.map((item) => <li key={item.donation_id}>{(item.promised_at || '').slice(0, 10)} · {item.campaign} · <b><Money cents={item.amount_cents} /></b></li>)}</ul>
            </div>
          )}
        </>
      )}
    </section>
  );
};
