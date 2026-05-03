import React, { useState } from 'react';
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { Sheet, SheetContent, SheetTrigger } from './ui/sheet';
import { Separator } from './ui/separator';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import {
  LayoutDashboard, Users2, KeyRound, BookOpen, Map, Presentation, LogOut,
  Menu, ChevronRight, UserCircle
} from 'lucide-react';
import { LOGO_IGLESIA } from '../data/presentationData';
import DisplayScaleToggle from './DisplayScaleToggle';
import { RoleBadge } from './RoleBadge';

const LOGO_URL = LOGO_IGLESIA;

/**
 * Items del sidebar segun el rol del usuario en la jerarquia de 5 niveles.
 * - Maestro/Supervisor/Lider/Obrero: gestionan equipo + ven el manual
 * - Discipulo: solo ve el manual y sus tareas (Phase 7)
 */
function getNavItems(rol) {
  const base = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
  ];

  if (rol !== 'discipulo') {
    base.push(
      { to: '/equipo', icon: Users2, label: 'Mi Equipo' },
      { to: '/equipo/codigos', icon: KeyRound, label: 'Códigos de Invitación' },
    );
  }

  base.push(
    { type: 'separator', label: 'Manual' },
    { to: '/introduccion', icon: BookOpen, label: 'Introducción' },
    { to: '/mapa', icon: Map, label: 'Mapa 7 Semanas' },
  );

  if (rol !== 'discipulo') {
    base.push({ to: '/presentacion', icon: Presentation, label: 'Presentar Manual' });
  }

  return base;
}

const breadcrumbMap = {
  '/': 'Dashboard',
  '/equipo': 'Mi Equipo',
  '/equipo/codigos': 'Códigos de Invitación',
  '/introduccion': 'Introducción',
  '/mapa': 'Mapa de las 7 Semanas',
  '/presentacion': 'Manual 7 Semanas',
  '/cuenta': 'Mi Cuenta',
};

function SidebarContent({ onClose }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items = getNavItems(user?.rol);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex flex-col h-full bg-[#0F1A33] text-white">
      {/* Header con logo + identidad */}
      <div className="px-5 py-5 border-b border-white/10">
        <div className="flex items-center gap-3 mb-3">
          <img
            src={LOGO_URL}
            alt="Ven y Ve"
            className="w-12 h-12 rounded-full bg-white/5 p-0.5"
            style={{ mixBlendMode: 'screen' }}
          />
          <div className="min-w-0">
            <p className="text-sm font-bold leading-tight" style={{ fontFamily: 'Spectral, serif' }}>Ven y Ve</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-white/50">Casa de Oración</p>
          </div>
        </div>

        {/* Identidad del usuario */}
        {user && (
          <div className="bg-white/5 border border-white/10 rounded-lg p-3" data-testid="sidebar-user-card">
            <div className="flex items-center gap-2 mb-2">
              <UserCircle className="w-5 h-5 text-[#C8A951] shrink-0" />
              <p className="text-sm font-semibold truncate" data-testid="sidebar-user-name">{user.nombre}</p>
            </div>
            <RoleBadge rol={user.rol} size="sm" />
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {items.map((item, idx) => {
          if (item.type === 'separator') {
            return (
              <div key={`sep-${idx}`} className="pt-4 pb-1 px-3">
                <p className="text-[10px] uppercase tracking-[0.25em] text-[#C8A951]/70 font-bold">{item.label}</p>
              </div>
            );
          }
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onClose}
              data-testid={`nav-${item.to.replace(/\//g, '-')}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-[#C8A951] text-[#1B2A4A]'
                    : 'text-white/80 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="truncate">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-white/10 space-y-2">
        <DisplayScaleToggle />
        <Button
          onClick={handleLogout}
          variant="ghost"
          className="w-full justify-start text-white/80 hover:text-white hover:bg-white/10"
          data-testid="logout-button"
        >
          <LogOut className="w-4 h-4 mr-2" />
          Cerrar sesión
        </Button>
      </div>
    </div>
  );
}

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  const location = useLocation();
  const breadcrumb = breadcrumbMap[location.pathname] || ' ';

  return (
    <div className="min-h-screen bg-[#FAFAF8] flex">
      {/* Sidebar desktop */}
      <aside className="hidden lg:flex lg:w-72 lg:flex-col lg:fixed lg:inset-y-0 z-30">
        <SidebarContent />
      </aside>

      {/* Mobile header + drawer */}
      <div className="lg:hidden fixed top-0 inset-x-0 z-40 bg-[#0F1A33] text-white px-4 py-3 flex items-center justify-between border-b border-white/10">
        <div className="flex items-center gap-2">
          <img src={LOGO_URL} alt="Ven y Ve" className="w-8 h-8 rounded-full" style={{ mixBlendMode: 'screen' }} />
          <span className="text-sm font-bold" style={{ fontFamily: 'Spectral, serif' }}>Ven y Ve</span>
        </div>
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="text-white" data-testid="mobile-menu-button">
              <Menu className="w-5 h-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-72 bg-[#0F1A33] border-r-0">
            <VisuallyHidden>Menu</VisuallyHidden>
            <SidebarContent onClose={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
      </div>

      {/* Content area */}
      <main className="flex-1 lg:ml-72 pt-14 lg:pt-0">
        {/* Top bar */}
        <div className="sticky top-14 lg:top-0 z-20 bg-white/95 backdrop-blur border-b border-[#E7E2D6] px-4 sm:px-8 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Inicio</span>
            <ChevronRight className="w-3.5 h-3.5" />
            <span className="text-[#1B2A4A] font-semibold" data-testid="breadcrumb-current">{breadcrumb}</span>
          </div>
          {user && (
            <div className="hidden sm:flex items-center gap-3">
              <span className="text-sm text-[#1B2A4A] font-medium">{user.nombre}</span>
              <RoleBadge rol={user.rol} size="sm" />
            </div>
          )}
        </div>

        <div className="max-w-7xl mx-auto px-4 sm:px-8 py-6 sm:py-10">
          <Outlet />
          <Separator className="my-10 opacity-30" />
          <p className="text-center text-xs text-muted-foreground">
            Casa de Oración Ven y Ve · Primera Iglesia del Nazareno
          </p>
        </div>
      </main>
    </div>
  );
}
