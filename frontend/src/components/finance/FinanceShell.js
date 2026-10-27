import React from 'react';
import { NavLink } from 'react-router-dom';
import { BookOpenCheck, HandCoins, ChartNoAxesCombined, CircleDollarSign, FileInput, Landmark, ReceiptText, Scale, Settings2, UserRoundSearch } from 'lucide-react';
import { moduleBrand, MODULE_BRANDS } from '../../config/brand';
import { useAuth } from '../../context/AuthContext';
import { isPastoralAuthority } from '../../lib/accessControl';

// Decisión del dueño: la pastora solo consulta Finanzas (el servidor rechaza cualquier cambio suyo).
const PastoralReadOnly = () => { const { user } = useAuth(); return isPastoralAuthority(user) ? <p className="mb-4 border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900" data-testid="finance-pastoral-read-only">Solo lectura: la pastora consulta todo Finanzas. Registrar, validar, aprobar, recibir, depositar, pagar, anular, cerrar o migrar lo hace el equipo de Finanzas con su rol.</p> : null; };

const items = [
  ['/finanzas', Landmark, 'Resumen'], ['/finanzas/colecta', HandCoins, 'Colecta'], ['/finanzas/configuracion', Settings2, 'Configuración'], ['/finanzas/asientos', BookOpenCheck, 'Asientos y libro'], ['/finanzas/contribuciones', CircleDollarSign, 'Contribuciones'], ['/finanzas/contribuyentes', UserRoundSearch, 'Contribuyentes'], ['/finanzas/operaciones', ReceiptText, 'Operación'], ['/finanzas/conciliacion', Scale, 'Conciliación'], ['/finanzas/reportes', ChartNoAxesCombined, 'Reportes'], ['/finanzas/integraciones', FileInput, 'Integraciones'],
];

export const FinanceShell = ({ title, description, actions, children }) => <div className="min-h-full bg-[#F3F5F4]" data-testid="finance-shell"><header className="border-b bg-[#132A2C] px-4 py-8 text-white sm:px-6 lg:px-8"><div className="mx-auto flex max-w-7xl flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div><p className="text-xs font-semibold uppercase text-[#D6BE70]">{moduleBrand(MODULE_BRANDS.finance)}</p><h1 className="mt-2 font-['Spectral'] text-4xl font-semibold" data-testid="finance-page-title">{title}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-white/70">{description}</p></div>{actions}</div></header><nav className="border-b bg-white" data-testid="finance-navigation"><div className="mx-auto flex max-w-7xl flex-wrap gap-1 px-4">{items.map(([to, Icon, label]) => <NavLink key={to} to={to} end={to === '/finanzas'} className={({ isActive }) => `flex items-center gap-2 border-b-2 px-3 py-3 text-sm ${isActive ? 'border-[#B5953F] text-[#102A2D]' : 'border-transparent text-slate-500 hover:text-[#102A2D]'}`} data-testid={`finance-nav-${to.split('/').pop() || 'home'}`}><Icon className="h-4 w-4" />{label}</NavLink>)}</div></nav><main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8"><PastoralReadOnly />{children}</main></div>;

export const Money = ({ cents = 0, testId }) => <span data-testid={testId}>{new Intl.NumberFormat('es-US', { style: 'currency', currency: 'USD' }).format(cents / 100)}</span>;
export const FinanceEmpty = ({ children }) => <div className="border border-dashed bg-white p-8 text-center text-sm text-slate-500">{children}</div>;