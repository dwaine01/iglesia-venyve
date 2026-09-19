import React, { useState } from 'react';
import { ChevronRight, Home, List, MapPinOff, X } from 'lucide-react';
import { Button } from '../ui/button';

const statusLabels = { detected: 'Detectada', assigned: 'Asignada', visited: 'Visitada', follow_up: 'Seguimiento', connected: 'Conectada', do_not_visit: 'No visitar' };

export const EvangelismTargetList = ({ items, onSelect }) => {
  const [open, setOpen] = useState(false);
  const select = (item) => {
    onSelect({ type: 'Feature', geometry: item.longitude != null && item.latitude != null ? { type: 'Point', coordinates: [item.longitude, item.latitude] } : null, properties: { entity_kind: 'evangelism_target', entity_id: item.target_id, name: item.full_address, address: item.full_address, ...item } });
    setOpen(false);
  };
  return <div className="absolute bottom-3 left-3 z-20" data-testid="evangelism-target-list-shell">
    <Button type="button" variant="outline" className="border-emerald-300 bg-white shadow-lg" onClick={() => setOpen((value) => !value)} data-testid="evangelism-target-list-button"><List className="h-4 w-4" />Lista de casas <span className="font-bold">{items.length}</span></Button>
    {open && <section className="absolute bottom-12 left-0 max-h-[min(65vh,520px)] w-[min(88vw,390px)] overflow-hidden border bg-white shadow-2xl" data-testid="evangelism-target-list-panel"><header className="flex items-center justify-between border-b bg-slate-950 px-4 py-3 text-white"><div><p className="text-xs uppercase text-emerald-300">Minicenso</p><h2 className="font-['Spectral'] text-lg font-semibold">Casas registradas</h2></div><Button type="button" variant="ghost" size="icon" className="text-white hover:bg-white/10 hover:text-white" onClick={() => setOpen(false)} aria-label="Cerrar lista" data-testid="evangelism-target-list-close-button"><X className="h-4 w-4" /></Button></header><div className="max-h-[430px] divide-y overflow-y-auto">{items.length === 0 ? <p className="p-5 text-sm text-slate-500" data-testid="evangelism-target-list-empty">No hay casas con este filtro.</p> : items.map((item) => <button type="button" key={item.target_id} onClick={() => select(item)} className="flex w-full items-center gap-3 p-3 text-left transition-colors hover:bg-emerald-50" data-testid={`evangelism-target-list-item-${item.target_id}`}><span className={`flex h-9 w-9 shrink-0 items-center justify-center ${item.latitude == null ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}`}>{item.latitude == null ? <MapPinOff className="h-4 w-4" /> : <Home className="h-4 w-4" />}</span><span className="min-w-0 flex-1"><b className="block truncate text-sm text-slate-950">{item.full_address}</b><small className="block text-xs text-slate-500">{statusLabels[item.status] || item.status}{item.assigned_to_name ? ` · ${item.assigned_to_name}` : ''}</small></span><ChevronRight className="h-4 w-4 shrink-0 text-slate-400" /></button>)}</div></section>}
  </div>;
};