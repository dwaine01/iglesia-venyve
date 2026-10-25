import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, BookOpen, Download, Loader2, Route } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { downloadCsv } from '../../lib/csv';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { JourneyDialog } from '../../components/library/JourneyDialog';

// Cifras de cada fila (todas se tocan para ver lo que hay detrás).
const FIGURES = [
  ['received', 'Recibidos'], ['delivered', 'Entregados'], ['available', 'Disponibles', true],
  ['pending', 'Sin conciliar'], ['unidentified', 'Por completar'], ['followup', 'Con seguimiento'],
];
const when = (iso) => (iso ? new Date(iso).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' }) : '');

/** Lo que hay detrás de una cifra (destinatario, dirección, material y seguimiento). */
function ItemsDialog({ query, onClose, onJourney }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const last = useRef(null);
  if (query) last.current = query;
  const current = query || last.current;
  useEffect(() => {
    if (!query) return;
    setData(null);
    axios.get(`${API}/api/library/ledger/trace/items`, { ...getAuthHeaders(), params: { limit: 300, ...query.params } })
      .then((response) => setData(response.data)).catch((error) => setData({ items: [], total: 0, error: apiErrorMessage(error, 'No se pudo cargar') }));
  }, [API, getAuthHeaders, query]);
  if (!current) return null;
  const csv = () => downloadCsv(`libros-${current.params.metric}.csv`, (data?.items || []).map((item) => ({
    material: item.book_name, cantidad: item.quantity, fecha: (item.occurred_at || '').slice(0, 10), mentor: item.mentor_name, destinatario: item.recipient_name || '',
    direccion: [item.address_line1, item.address_line2].filter(Boolean).join(' '), seguimiento: item.followup?.accepted ? 'Sí' : 'No', proxima_accion: item.followup?.next_action || '',
    estado: item.movement_type === 'DELIVERY_PENDING' ? 'Sin conciliar' : 'Descontado',
  })));
  return (
    <Dialog open={Boolean(query)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="bg-white sm:max-w-lg" data-testid="trace-items">
        <DialogHeader><DialogTitle>{current.title}</DialogTitle><DialogDescription>{data ? `${data.total} registro(s)` : 'Cargando…'}</DialogDescription></DialogHeader>
        {data?.items?.length > 0 && <button type="button" onClick={csv} className="inline-flex min-h-11 items-center gap-1 self-start rounded-lg border border-[#D9D4C7] px-3 text-sm font-semibold" data-testid="trace-items-csv"><Download className="h-4 w-4" />CSV</button>}
        {!data ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : data.error ? <p className="text-sm text-red-700">{data.error}</p> : data.items.length === 0 ? <p className="text-base text-slate-500">Sin registros.</p> : (
          <ul className="divide-y divide-[#EEECE6]">
            {data.items.map((item) => (
              <li key={item.movement_id} className="py-2" data-testid={`trace-item-${item.movement_id}`}>
                <p className="text-[15px] font-semibold text-[#101D36]">{item.quantity} × {item.book_name}{item.movement_type === 'DELIVERY_PENDING' && <span className="ml-1 rounded-full bg-amber-100 px-2 text-xs text-amber-900">sin conciliar</span>}</p>
                <p className="text-sm text-slate-700">{current.params.metric === 'received' ? `De ${item.from_label || 'Librería'}` : item.recipient_name || 'Destinatario por completar'}{item.address_line1 ? ` · ${item.address_line1}${item.address_line2 ? ` ${item.address_line2}` : ''}` : ''}</p>
                <p className="text-xs text-slate-500">{when(item.occurred_at)}{item.mentor_name ? ` · ${item.mentor_name}` : ''}{item.followup?.accepted ? ` · Seguimiento: ${item.followup.next_action || 'sí'}` : ''}</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {current.params.metric !== 'received' && <button type="button" onClick={() => onJourney(item.movement_id)} className="inline-flex min-h-10 items-center gap-1 rounded-md border border-[#D9D4C7] px-3 text-sm font-semibold" data-testid="trace-item-journey"><Route className="h-4 w-4" />Recorrido</button>}
                  {item.person_id && <Link to={`/personas/${item.person_id}`} className="inline-flex min-h-10 items-center rounded-md border border-[#D9D4C7] px-3 text-sm font-semibold text-[#0879BE]">Perfil</Link>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** L3 · Libros por mentor o por material, con cada cifra tocable y el recorrido. */
export default function LibraryTracePage() {
  const { API, getAuthHeaders } = useAuth();
  const [params, setParams] = useSearchParams();
  const groupBy = params.get('por') === 'material' ? 'material' : 'mentor';
  const campaignId = params.get('invasion') || '';
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState(null);
  const [journey, setJourney] = useState(null);
  const load = useCallback(() => {
    setData(null); setError('');
    axios.get(`${API}/api/library/ledger/trace/summary`, { ...getAuthHeaders(), params: { group_by: groupBy, ...(campaignId ? { campaign_id: campaignId } : {}) } })
      .then((response) => setData(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar')));
  }, [API, getAuthHeaders, groupBy, campaignId]);
  useEffect(() => { load(); }, [load]);
  const setGroup = (value) => { const next = new URLSearchParams(params); next.set('por', value); setParams(next, { replace: true }); };
  const open = (row, metric, label) => setQuery({ title: `${label} · ${row.name}`, params: { metric, ...(campaignId ? { campaign_id: campaignId } : {}), ...(groupBy === 'mentor' ? { mentor_user_id: row.key } : { book_id: row.key }) } });
  const csv = () => downloadCsv(`libros-por-${groupBy}.csv`, (data?.rows || []).map((row) => ({ [groupBy === 'mentor' ? 'mentor' : 'material']: row.name, recibidos: row.received, entregados: row.delivered, disponibles: row.available, sin_conciliar: row.pending, con_destinatario: row.identified, por_completar: row.unidentified, con_seguimiento: row.followup })));
  return (
    <div className="mx-auto w-full max-w-5xl space-y-4 p-4 sm:p-6" data-testid="library-trace-page">
      <header className="space-y-1">
        <Link to="/libreria" className="inline-flex min-h-10 items-center gap-1 text-sm text-[#0879BE]"><ArrowLeft className="h-4 w-4" />Librería 360</Link>
        <h1 className="flex items-center gap-2 font-['Spectral'] text-2xl font-semibold text-[#101D36]"><BookOpen className="h-6 w-6" />Recorrido de libros</h1>
        <p className="text-sm text-slate-600">{data?.scope === 'mine' ? 'Tus libros: recibidos, entregados y a quién.' : 'Librería → mentor → vivienda o persona → seguimiento.'}{campaignId ? ' Filtrado por invasión.' : ''}</p>
      </header>
      <div className="flex flex-wrap items-center gap-2">
        {data?.scope !== 'mine' && <div className="grid grid-cols-2 gap-1 rounded-xl bg-[#EEECE6] p-1" role="tablist">{[['mentor', 'Por mentor'], ['material', 'Por material']].map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={groupBy === key} onClick={() => setGroup(key)} className={`min-h-11 rounded-lg px-4 text-[15px] font-semibold ${groupBy === key ? 'bg-white shadow' : 'text-slate-600'}`} data-testid={`trace-group-${key}`}>{label}</button>)}</div>}
        {data?.rows?.length > 0 && <button type="button" onClick={csv} className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-[#D9D4C7] bg-white px-3 text-sm font-semibold" data-testid="trace-csv"><Download className="h-4 w-4" />CSV</button>}
      </div>
      {error ? <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</p> : !data ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : data.rows.length === 0 ? <p className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-slate-500">Todavía no hay libros registrados.</p> : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {data.rows.map((row) => (
            <section key={row.key} className="rounded-2xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid={`trace-row-${row.key}`}>
              <p className="font-['Spectral'] text-lg font-semibold text-[#101D36]">{row.name}</p>
              <p className="mb-2 text-sm text-slate-600" data-testid="trace-row-sentence">{row.received} recibidos · {row.delivered} entregados · {row.available} disponibles{row.pending ? ` · ${row.pending} sin conciliar` : ''}</p>
              <div className="grid grid-cols-3 gap-2">
                {FIGURES.map(([metric, label, plain]) => {
                  const value = row[metric];
                  const clickable = !plain && value > 0;
                  const Tag = clickable ? 'button' : 'div';
                  return <Tag key={metric} type={clickable ? 'button' : undefined} onClick={clickable ? () => open(row, metric, label) : undefined} className={`min-h-[64px] rounded-xl border p-2 text-left ${metric === 'pending' && value ? 'border-amber-200 bg-amber-50' : metric === 'unidentified' && value ? 'border-amber-200 bg-amber-50' : 'border-[#EEECE6] bg-[#FBFAF7]'}`} data-testid={`trace-figure-${metric}`}>
                    <span className={`block text-xl font-semibold ${clickable ? 'text-[#1d4ed8]' : 'text-[#101D36]'}`}>{value}</span><span className="block text-[12px] leading-4 text-slate-600">{label}</span>
                  </Tag>;
                })}
              </div>
            </section>
          ))}
        </div>
      )}
      <ItemsDialog query={query} onClose={() => setQuery(null)} onJourney={(id) => setJourney(id)} />
      <JourneyDialog movementId={journey} onClose={() => setJourney(null)} />
    </div>
  );
}
