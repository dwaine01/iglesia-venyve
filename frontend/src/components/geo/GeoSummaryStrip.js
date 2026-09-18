import React from 'react';
import { CircleAlert, MapPin, RadioTower, Users } from 'lucide-react';

export const GeoSummaryStrip = ({ summary }) => {
  const cards = [
    ['people', Users, 'Personas ubicadas', summary.people_total || 0],
    ['cells', RadioTower, 'Células ubicadas', summary.cells_total || 0],
    ['review', CircleAlert, 'Por verificar', summary.review_total || 0],
    ['pending', MapPin, 'Procesando', summary.pending_total || 0],
  ];
  return <section className="grid grid-cols-2 gap-px border bg-slate-200 lg:grid-cols-4" data-testid="geo-summary-strip">{cards.map(([key, Icon, label, value]) => <article key={key} className="bg-white p-4" data-testid={`geo-summary-${key}`}><div className="flex items-center gap-2 text-slate-500"><Icon className="h-4 w-4" /><span className="text-xs font-semibold uppercase">{label}</span></div><b className="mt-2 block font-['Spectral'] text-3xl text-slate-900">{value}</b></article>)}</section>;
};