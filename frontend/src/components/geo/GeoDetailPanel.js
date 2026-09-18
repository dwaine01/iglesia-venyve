import React from 'react';
import { ExternalLink, MapPin, Users, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/button';

export const GeoDetailPanel = ({ feature, onClose }) => {
  if (!feature) return null;
  const item = feature.properties || {};
  return <aside className="absolute bottom-4 left-4 right-4 z-10 max-h-[70%] overflow-y-auto border bg-white p-4 shadow-2xl md:left-auto md:right-4 md:top-4 md:w-80" data-testid="geo-feature-detail-panel">
    <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase text-amber-700">{item.entity_kind === 'cell' ? 'Célula' : item.person_number || 'Persona 360'}</p><h3 className="font-['Spectral'] text-xl font-semibold" data-testid="geo-feature-name">{item.name || `${item.count || 0} ubicaciones`}</h3></div><Button variant="ghost" size="icon" onClick={onClose} aria-label="Cerrar detalle" data-testid="close-geo-feature-detail"><X className="h-4 w-4" /></Button></div>
    <div className="mt-4 space-y-2 text-sm"><p className="flex items-start gap-2"><MapPin className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" /><span>{item.address || `Zona ${item.zone || 'sin asignar'}`}</span></p>{item.entity_kind === 'cell' && <><p><b>Líder:</b> {item.leader || 'Pendiente'}</p><p><b>Reunión:</b> {item.meeting_day || '—'} {item.meeting_time || ''}</p><p className="flex items-center gap-2"><Users className="h-4 w-4" />{item.members || 0} / {item.capacity || '—'} personas</p></>}{item.entity_kind === 'person' && <><p><b>Categorías:</b> {(Array.isArray(item.categories) ? item.categories : []).join(', ') || 'Sin categoría'}</p><p><b>Etapa:</b> {item.stage || 'Sin proceso activo'}</p>{item.phone && <p><b>Teléfono:</b> {item.phone}</p>}</>}</div>
    {item.entity_id && <Button asChild className="mt-4 w-full" data-testid="open-geo-feature-record"><Link to={item.entity_kind === 'cell' ? `/celulas/${item.entity_id}` : `/personas/${item.entity_id}`}><ExternalLink className="h-4 w-4" />Abrir ficha</Link></Button>}
  </aside>;
};