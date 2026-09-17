import React from 'react';
import { NavLink } from 'react-router-dom';
import { Activity, BookHeart, ChevronRight, Compass, HeartHandshake, LayoutDashboard } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { moduleBrand, MODULE_BRANDS } from '../../config/brand';
import { translateTechnicalText } from '../../lib/displayLabels';

const links = [
  { to: '/procesos/dashboard', label: 'Panel', mobileLabel: 'Panel', icon: LayoutDashboard },
  { to: '/procesos/consolidacion', label: 'Consolidación', mobileLabel: 'Consol.', icon: Activity },
  { to: '/procesos/discipulado', label: 'Discipulado', mobileLabel: 'Discíp.', icon: BookHeart },
  { to: '/procesos/mentoria', label: 'Mentoría', mobileLabel: 'Mentoría', icon: HeartHandshake },
  { to: '/procesos/cap', label: 'Encuentra tu lugar para servir', mobileLabel: 'Servicio', icon: Compass },
];

export const ProcessShell = ({ title, eyebrow, description, actions, children }) => {
  const { user } = useAuth();
  return (
    <div className="min-h-screen bg-slate-50" data-testid="process-shell">
      <header className="border-b border-slate-800 bg-slate-900 px-4 py-7 text-white sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="font-mono text-xs font-semibold uppercase text-amber-400">{moduleBrand(eyebrow || MODULE_BRANDS.processes)}</p>
            <h1 className="mt-1 font-['Spectral'] text-3xl font-semibold sm:text-4xl" data-testid="process-page-title">{title}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{description}</p>
          </div>
          {actions && user?.rol !== 'persona' && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      </header>
      <nav className="sticky top-[53px] z-10 border-b border-slate-200 bg-white/95 px-3 backdrop-blur-md sm:px-6 lg:top-[61px] lg:px-8" data-testid="process-module-navigation">
        <div className="mx-auto grid max-w-7xl grid-cols-5 gap-1 py-2 sm:flex">
          {links.map(({ to, label, mobileLabel, icon: Icon }) => <NavLink key={to} to={to} data-testid={`process-nav-${to.split('/').pop()}`} className={({ isActive }) => `flex min-w-0 flex-col items-center justify-center gap-1 rounded-md px-1 py-2 text-[10px] font-medium transition-colors sm:shrink-0 sm:flex-row sm:gap-2 sm:px-3 sm:text-sm ${isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}><Icon className="h-4 w-4 shrink-0" /><span className="sm:hidden">{mobileLabel}</span><span className="hidden sm:inline">{label}</span><ChevronRight className="hidden h-3 w-3 opacity-40 sm:block" /></NavLink>)}
        </div>
      </nav>
      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
    </div>
  );
};

export const ProcessLoading = ({ testId = 'process-loading-state' }) => <div className="flex min-h-52 items-center justify-center" data-testid={testId}><div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-amber-600" /></div>;
export const ProcessError = ({ message }) => <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" data-testid="process-error-alert">{translateTechnicalText(message)}</div>;