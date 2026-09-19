import React from 'react';
import { CalendarDays, LayoutDashboard, RadioTower } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const links = [
  { to: '/operaciones', label: 'Tablero', icon: LayoutDashboard, end: true, testId: 'operations-nav-dashboard' },
  { to: '/operaciones/eventos', label: 'Eventos', icon: CalendarDays, testId: 'operations-nav-events' },
];

export const OperationsShell = ({ eyebrow = 'Mega‑Bloque E', title, description, actions, children }) => (
  <main className="min-h-full bg-[#F3F0E8] pb-12" data-testid="operations-shell">
    <header className="border-b border-slate-800 bg-[#101820] px-4 py-5 text-white sm:px-6 lg:px-8"><div className="mx-auto flex max-w-7xl flex-wrap items-end justify-between gap-5"><div className="max-w-3xl"><p className="flex items-center gap-2 text-xs font-bold uppercase text-[#E5B94B]"><RadioTower className="h-4 w-4" />{eyebrow}</p><h1 className="mt-2 font-['Spectral'] text-3xl font-semibold sm:text-4xl" data-testid="operations-page-title">{title}</h1>{description && <p className="mt-2 text-sm leading-6 text-slate-300">{description}</p>}</div>{actions && <div className="flex flex-wrap gap-2">{actions}</div>}</div></header>
    <nav className="border-b bg-white px-4 sm:px-6 lg:px-8" aria-label="Navegación de Operaciones"><div className="mx-auto flex max-w-7xl gap-6 overflow-x-auto">{links.map(({ to, label, icon: Icon, end, testId }) => <NavLink key={to} to={to} end={end} data-testid={testId} className={({ isActive }) => `flex h-12 shrink-0 items-center gap-2 border-b-2 px-1 text-sm font-semibold transition-colors ${isActive ? 'border-emerald-700 text-emerald-800' : 'border-transparent text-slate-500 hover:text-slate-950'}`}><Icon className="h-4 w-4" />{label}</NavLink>)}</div></nav>
    <div className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8">{children}</div>
  </main>
);