import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { BookOpen, DoorClosed, DoorOpen, Home, Loader2, MessagesSquare, Sprout } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';

export const METRICS = [
  { key: 'visited', label: 'Viviendas visitadas', icon: Home },
  { key: 'no_answer', label: 'No abrieron', icon: DoorClosed },
  { key: 'opened', label: 'Abrieron', icon: DoorOpen },
  { key: 'conversed', label: 'Conversamos', icon: MessagesSquare },
  { key: 'books', label: 'Libros entregados', icon: BookOpen },
  { key: 'consolidation', label: 'En consolidación', icon: Sprout },
];
export const DOOR_STATUS = {
  pending_revisit: { label: 'Pendiente de nueva visita', className: 'bg-amber-50 text-amber-800 border-amber-200' },
  opened: { label: 'Abrieron', className: 'bg-[#eef5f0] text-[#2f6e47] border-[#bcd8c4]' },
  followup_scheduled: { label: 'Seguimiento programado', className: 'bg-[#e8eefb] text-[#1d4ed8] border-[#c3d3f5]' },
};
const when = (iso) => (iso ? new Date(iso).toLocaleString('es', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '');

// Listado que compone una cifra (direcciones y registros), paginado en el servidor.
function MetricList({ campaignId, metric: openMetric, onClose }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  // Se conserva el último indicador mientras el diálogo termina de cerrarse.
  const last = useRef(null);
  if (openMetric) last.current = openMetric;
  const metric = openMetric || last.current;
  useEffect(() => {
    if (!openMetric) return;
    setData(null);
    axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/door-summary/${openMetric.key}`, { ...getAuthHeaders(), params: { limit: 100 } })
      .then((response) => setData(response.data)).catch(() => setData({ items: [], total: 0 }));
  }, [API, getAuthHeaders, campaignId, openMetric]);
  if (!metric) return null;
  return (
    <Dialog open={Boolean(openMetric)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="bg-white sm:max-w-lg" data-testid="door-metric-list">
        <DialogHeader><DialogTitle>{metric?.label}</DialogTitle><DialogDescription>{data ? `${data.total} registro(s)` : 'Cargando…'}</DialogDescription></DialogHeader>
        {!data ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : data.items.length === 0 ? <p className="text-base text-slate-500">Aún sin registros.</p> : (
          <ul className="divide-y divide-[#EEECE6]">
            {data.items.map((item) => metric.key === 'consolidation'
              ? <li key={item.visit_id} className="py-2"><p className="text-base font-semibold text-[#101D36]">{item.contact_name || item.person_name || 'Persona'}</p><p className="text-sm text-slate-500">{item.address_line1 || item.contact_zone || 'Sin dirección'}</p></li>
              : <li key={item.household_id} className="py-2" data-testid={`door-metric-item-${item.household_id}`}>
                  <p className="text-base font-semibold text-[#101D36]">{item.address_line1}{item.address_line2 ? ` · ${item.address_line2}` : ''}</p>
                  <p className="text-sm text-slate-600">{DOOR_STATUS[item.door_status]?.label || '—'} · {item.attempts_count} intento(s){metric.key === 'books' ? ` · ${item.books_total} libro(s)` : ''}</p>
                  <p className="text-xs text-slate-500">Última visita: {when(item.last_attempt_at)}</p>
                </li>)}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Resumen compacto arriba: cada cifra se toca para ver lo que la compone. */
export function DoorStats({ campaignId, summary }) {
  const [open, setOpen] = useState(null);
  return (
    <section data-testid="door-stats">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
        {METRICS.map((metric) => {
          const Icon = metric.icon;
          return (
            <button key={metric.key} type="button" onClick={() => setOpen(metric)} className="flex min-h-[72px] items-center gap-3 rounded-xl border border-[#E8E5DE] bg-white p-3 text-left shadow-sm active:bg-[#FBFAF7]" data-testid={`door-stat-${metric.key}`}>
              <Icon className="h-6 w-6 shrink-0 text-[#9A7A2F]" />
              <span className="min-w-0"><span className="block text-2xl font-semibold leading-7 text-[#101D36]">{summary ? summary[metric.key] : '—'}</span><span className="block text-[13px] leading-4 text-slate-600">{metric.label}</span></span>
            </button>
          );
        })}
      </div>
      {summary && summary.attempts > summary.visited && <p className="mt-1 text-xs text-slate-500">{summary.attempts} intentos en {summary.visited} viviendas · {summary.pending_revisit} pendiente(s) de nueva visita</p>}
      <MetricList campaignId={campaignId} metric={open} onClose={() => setOpen(null)} />
    </section>
  );
}
