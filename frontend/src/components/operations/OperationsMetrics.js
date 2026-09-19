import React from 'react';
import { CalendarClock, CheckCheck, UserRoundCheck, UsersRound } from 'lucide-react';

const items = [
  ['upcoming_occurrences', 'Próximas 7 días', CalendarClock, 'text-blue-700 bg-blue-50'],
  ['checkins_today', 'Check-ins hoy', UserRoundCheck, 'text-emerald-700 bg-emerald-50'],
  ['volunteers_confirmed', 'Voluntarios confirmados', CheckCheck, 'text-teal-700 bg-teal-50'],
  ['open_volunteer_slots', 'Cupos por cubrir', UsersRound, 'text-amber-800 bg-amber-50'],
];

export const OperationsMetrics = ({ metrics = {} }) => <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="operations-metrics">{items.map(([key, label, Icon, color]) => <div key={key} className="border bg-white p-4 shadow-sm" data-testid={`operations-metric-${key}`}><div className={`flex h-9 w-9 items-center justify-center ${color}`}><Icon className="h-5 w-5" /></div><strong className="mt-4 block text-3xl text-slate-950">{metrics[key] || 0}</strong><span className="mt-1 block text-xs font-bold uppercase text-slate-500">{label}</span></div>)}</section>;