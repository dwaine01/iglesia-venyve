import React from 'react';
import { NavLink } from 'react-router-dom';
import { BellRing, ClipboardList, Clock3, Home, LockKeyhole, ShieldCheck } from 'lucide-react';

const links = [
  { to: '/cuidado-pastoral', label: 'Tablero', icon: Home, end: true, id: 'dashboard' },
  { to: '/cuidado-pastoral/casos', label: 'Casos', icon: ClipboardList, id: 'cases' },
  { to: '/cuidado-pastoral/operacion-72', label: 'Operación 72', icon: Clock3, id: 'op72' },
  { to: '/cuidado-pastoral/visitas', label: 'Visitas', icon: BellRing, id: 'visits' },
];

export const PastoralShell = ({ eyebrow = 'Bóveda institucional', title, description, actions, children }) => (
  <div className="min-h-full bg-[#F7F5EF]" data-testid="pastoral-module-shell">
    <header className="border-b border-[#C8A951]/30 bg-[#0B1428] px-4 py-7 text-white sm:px-7 lg:px-10">
      <div className="mx-auto flex max-w-[1320px] flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase text-[#D8BC61]" data-testid="pastoral-shell-eyebrow"><ShieldCheck className="h-4 w-4" />{eyebrow}</p>
          <h1 className="mt-2 font-['Spectral'] text-3xl font-semibold sm:text-4xl" data-testid="pastoral-shell-title">{title}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300" data-testid="pastoral-shell-description">{description}</p>
        </div>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>
    </header>
    <div className="border-b bg-white px-3 sm:px-7 lg:px-10">
      <nav className="mx-auto grid max-w-[1320px] grid-cols-2 gap-1 py-2 sm:flex" aria-label="Cuidado Pastoral" data-testid="pastoral-subnavigation">
        {links.map(({ to, label, icon: Icon, end, id }) => <NavLink key={to} to={to} end={end} data-testid={`pastoral-nav-${id}`} className={({ isActive }) => `flex min-w-0 items-center justify-center gap-2 border-b-2 px-2 py-2 text-center text-sm font-semibold transition-colors sm:justify-start sm:px-3 ${isActive ? 'border-[#C8A951] text-[#0B1428]' : 'border-transparent text-slate-500 hover:text-slate-900'}`}><Icon className="h-4 w-4 shrink-0" /><span className="min-w-0">{label}</span></NavLink>)}
        <span className="ml-auto hidden items-center gap-2 text-xs text-slate-400 lg:flex" data-testid="pastoral-vault-status"><LockKeyhole className="h-4 w-4 text-[#9A7E32]" />Acceso confidencial auditado</span>
      </nav>
    </div>
    <main className="mx-auto w-full min-w-0 max-w-[1320px] p-4 sm:p-7 lg:p-10">{children}</main>
  </div>
);