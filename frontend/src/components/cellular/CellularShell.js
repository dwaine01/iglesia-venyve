import React from 'react';
import { NavLink } from 'react-router-dom';
import { Activity, GitFork, LayoutDashboard, Network, RadioTower, UsersRound } from 'lucide-react';
import { ContextGuideButton } from '../guides/ContextGuideButton';
import { useAuth } from '../../context/AuthContext';
import { moduleBrand, MODULE_BRANDS } from '../../config/brand';
import { translateTechnicalText } from '../../lib/displayLabels';

const links = [
  ['/celulas/dashboard', 'Panel', LayoutDashboard, false], ['/celulas/redes', 'Redes', Network, true], ['/celulas/lista', 'Células', RadioTower, false],
  ['/celulas/bandeja-ready', 'Bandeja', UsersRound, true], ['/celulas/necesidades', 'Necesidades', Activity, true], ['/celulas/salud', 'Salud', GitFork, false],
];

export const CellularShell = ({ title, description, guideKey, actions, children }) => { const { user } = useAuth(); const visibleLinks = links.filter(([, , , staffOnly]) => !staffOnly || user?.rol !== 'persona'); return <div className="min-h-screen bg-[#F8F6F0]" data-testid="cellular-shell"><header className="relative overflow-hidden border-b border-[#30405F] bg-[#0F1A33] px-4 py-7 text-white sm:px-6 lg:px-8"><div className="absolute inset-0 opacity-[.07] [background-image:linear-gradient(rgba(255,255,255,.6)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.6)_1px,transparent_1px)] [background-size:28px_28px]" /><div className="relative mx-auto flex max-w-7xl flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div><p className="font-mono text-xs uppercase text-[#C8A951]">{moduleBrand(MODULE_BRANDS.cellular)}</p><h1 className="mt-1 font-['Spectral'] text-3xl font-semibold sm:text-4xl" data-testid="cellular-page-title">{title}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{description}</p></div><div className="flex flex-wrap gap-2"><ContextGuideButton moduleKey={guideKey} />{actions}</div></div></header><nav className="sticky top-[53px] z-10 border-b border-[#E2D9CC] bg-white/95 px-3 backdrop-blur-md lg:top-[61px]" data-testid="cellular-module-navigation"><div className="mx-auto grid max-w-7xl grid-cols-3 gap-1 py-2 sm:flex">{visibleLinks.map(([to, label, Icon]) => <NavLink key={to} to={to} data-testid={`cellular-nav-${to.split('/').pop()}`} className={({ isActive }) => `flex min-w-0 items-center justify-center gap-1 rounded-md px-2 py-2 text-[11px] font-semibold transition-colors sm:gap-2 sm:text-sm ${isActive ? 'bg-[#1B2A4A] text-white' : 'text-[#4A5568] hover:bg-[#F5F0E8]'}`}><Icon className="h-4 w-4 shrink-0" /><span className="truncate">{label}</span></NavLink>)}</div></nav><main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">{children}</main></div>; };

export const CellularLoading = () => <div className="flex min-h-52 items-center justify-center" data-testid="cellular-loading"><div className="h-9 w-9 animate-spin rounded-full border-2 border-[#E2D9CC] border-t-[#C8A951]" /></div>;
export const CellularError = ({ message }) => <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-800" data-testid="cellular-error-alert">{translateTechnicalText(message)}</div>;
export const EmptyState = ({ children, testId }) => <div className="border border-dashed border-[#D4C7B7] bg-white p-8 text-center text-sm text-[#718096]" data-testid={testId}>{children}</div>;