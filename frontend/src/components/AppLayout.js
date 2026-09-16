import React, { useEffect, useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from './ui/sheet';
import { Separator } from './ui/separator';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import {
  LayoutDashboard, BookOpen, Map, Calendar, Users, BarChart3, LogOut, Menu, ChevronRight,
  Crown, Star, Trophy, Presentation, NotebookPen, KeyRound, IdCard, Church, Search, DatabaseZap,
  Activity, BookOpenCheck, Compass, HeartHandshake, RadioTower, DoorOpen, Gavel
} from 'lucide-react';

import { LOGO_IGLESIA } from '../data/presentationData';
import DisplayScaleToggle from './DisplayScaleToggle';
import { ContextGuideButton } from './guides/ContextGuideButton';
import { resolveRouteGuide } from './guides/guideRouteMap';
import { BRAND } from '../config/brand';
const LOGO_URL = LOGO_IGLESIA;

// Menu items by role
const getNavItems = (rol) => {
  if (rol === 'pastor') {
    return [
      { to: '/dashboard-general', icon: Crown, label: 'Panel General', end: true },
      { to: '/nucleo', icon: DatabaseZap, label: 'Gobierno del Núcleo', testId: 'nav-core-governance' },
      { to: '/procesos/dashboard', icon: Activity, label: 'Panel de Procesos', testId: 'nav-process-dashboard' },
      { to: '/procesos/7-semanas', icon: BookOpenCheck, label: 'Ley de las 7 Semanas', testId: 'nav-seven-weeks' },
      { to: '/procesos/consolidacion', icon: Activity, label: 'Consolidación', testId: 'nav-consolidation' },
      { to: '/procesos/mentoria', icon: HeartHandshake, label: 'Mentoría', testId: 'nav-mentorship' },
      { to: '/procesos/cap', icon: Compass, label: 'Encuentra tu lugar para servir', testId: 'nav-cap' },
      { to: '/celulas/dashboard', icon: RadioTower, label: 'Sistema Celular', testId: 'nav-cellular' },
      { to: '/puertas/dashboard', icon: DoorOpen, label: '9 Puertas', testId: 'nav-doors' },
      { to: '/junta/dashboard', icon: Gavel, label: 'Junta Directiva', testId: 'nav-board' },
      { to: '/personas', icon: IdCard, label: 'Personas', testId: 'nav-personas' },
      { to: '/directorio', icon: Search, label: 'Directorio de Talentos', testId: 'nav-directorio-talentos' },
      { to: '/ministerios', icon: Church, label: 'Ministerios', testId: 'nav-ministerios' },
      { to: '/bitacora', icon: NotebookPen, label: 'Bitácora Evangelística' },
      { to: '/codigos', icon: KeyRound, label: 'Códigos de Invitación' },
      { to: '/presentacion', icon: Presentation, label: 'Manual de 7 Semanas' },
      { type: 'separator', label: 'Administración' },
      { to: '/estadisticas', icon: BarChart3, label: 'Estadísticas Globales' },
    ];
  }
  
  if (rol === 'persona') {
    return [
      { to: '/procesos/dashboard', icon: Trophy, label: 'Mi Progreso', end: true },
      { to: '/procesos/7-semanas', icon: BookOpenCheck, label: 'Mis 7 Semanas' },
      { to: '/procesos/mentoria', icon: HeartHandshake, label: 'Mi Mentoría' },
      { to: '/procesos/cap', icon: Compass, label: 'Mi lugar para servir' },
      { to: '/celulas/dashboard', icon: RadioTower, label: 'Mi Célula', testId: 'nav-cellular' },
    ];
  }
  
  // Default: lider
  return [
    { to: '/', icon: LayoutDashboard, label: 'Panel principal', end: true },
    { to: '/procesos/dashboard', icon: Activity, label: 'Panel de Procesos', testId: 'nav-process-dashboard' },
    { to: '/procesos/7-semanas', icon: BookOpenCheck, label: 'Ley de las 7 Semanas', testId: 'nav-seven-weeks' },
    { to: '/procesos/consolidacion', icon: Activity, label: 'Consolidación', testId: 'nav-consolidation' },
    { to: '/procesos/mentoria', icon: HeartHandshake, label: 'Mentoría', testId: 'nav-mentorship' },
    { to: '/procesos/cap', icon: Compass, label: 'Encuentra tu lugar para servir', testId: 'nav-cap' },
    { to: '/celulas/dashboard', icon: RadioTower, label: 'Sistema Celular', testId: 'nav-cellular' },
    { to: '/puertas/dashboard', icon: DoorOpen, label: '9 Puertas', testId: 'nav-doors' },
    { to: '/junta/dashboard', icon: Gavel, label: 'Junta Directiva', testId: 'nav-board' },
    { to: '/personas', icon: IdCard, label: 'Personas', testId: 'nav-personas' },
    { to: '/directorio', icon: Search, label: 'Directorio de Talentos', testId: 'nav-directorio-talentos' },
    { to: '/ministerios', icon: Church, label: 'Ministerios', testId: 'nav-ministerios' },
    { type: 'separator', label: 'Herramientas' },
    { to: '/codigos', icon: KeyRound, label: 'Códigos de Invitación' },
    { to: '/bitacora', icon: NotebookPen, label: 'Bitácora Evangelística' },
    { to: '/presentacion', icon: Presentation, label: 'Manual de 7 Semanas' },
    { to: '/estadisticas', icon: BarChart3, label: 'Estadísticas' },
  ];
};

const breadcrumbMap = {
  '/': 'Panel principal',
  '/dashboard': 'Panel principal',
  '/dashboard-general': 'Panel General',
  '/mi-progreso': 'Mi Progreso',
  '/presentacion': 'Manual de 7 Semanas',
  '/introduccion': 'Introducción del Manual',
  '/mapa': 'Mapa de las 7 Semanas',
  '/registro': 'Registro de Contactos',
  '/bitacora': 'Bitácora Evangelística',
  '/codigos': 'Códigos de Invitación',
  '/estadisticas': 'Estadísticas',
  '/directorio': 'Directorio de Talentos',
  '/ministerios': 'Ministerios',
  '/personas': 'Personas',
  '/personas/nueva': 'Nueva Persona',
  '/nucleo': 'Gobierno del Núcleo',
  '/procesos/dashboard': 'Panel de Procesos',
  '/procesos/7-semanas': 'Ley de las 7 Semanas',
  '/procesos/consolidacion': 'Consolidación',
  '/procesos/mentoria': 'Mentoría',
  '/procesos/cap': 'Encuentra tu lugar para servir',
  '/celulas/dashboard': 'Panel del Sistema Celular',
  '/celulas/redes': 'Redes Celulares',
  '/celulas/lista': 'Lista de Células',
  '/celulas/bandeja-ready': 'Bandeja Celular',
  '/celulas/necesidades': 'Necesidades Celulares',
  '/celulas/salud': 'Salud Celular',
  '/celulas/multiplicacion': 'Multiplicación Celular',
  '/celulas/genealogia': 'Genealogía Celular',
  '/puertas/dashboard': 'Sistema de las 9 Puertas',
  '/puertas/casos': 'Casos de Puertas',
  '/junta/dashboard': 'Junta Directiva',
  '/junta/miembros': 'Miembros de Junta',
  '/junta/reuniones': 'Reuniones de Junta',
  '/junta/minutas': 'Libro de Minutas',
};

function SidebarContent({ onClose, testIdPrefix = '' }) {
  const { user, logout } = useAuth();
  const navItems = getNavItems(user?.rol);

  const getRolLabel = () => {
    if (user?.rol === 'pastor') return 'Pastor (Acceso Maestro)';
    if (user?.rol === 'persona') return 'Consolidado';
    return 'Líder';
  };

  const getRolIcon = () => {
    if (user?.rol === 'pastor') return <Crown className="w-4 h-4 text-yellow-500" />;
    if (user?.rol === 'persona') return <Star className="w-4 h-4 text-[#C8A951]" />;
    return <Users className="w-4 h-4 text-[#1B2A4A]" />;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="p-4 flex items-center gap-3 border-b border-border bg-gradient-to-br from-[#0F1A33] to-[#1B2A4A]">
        <img src={LOGO_URL} alt="Casa de Oración Ven y Ve"
             className="w-11 h-11 object-contain logo-transparent" />
        <div className="flex-1 min-w-0">
          <p className="font-['Spectral'] text-base font-semibold text-white" data-testid={`${testIdPrefix}sidebar-brand-name`}>{BRAND.name}</p>
          <p className="mt-0.5 text-[9px] leading-3 text-[#D8BC61]">{BRAND.subtitle}</p>
          <p className="mt-1 text-[9px] uppercase tracking-wider text-white/50">{BRAND.church}</p>
        </div>
      </div>

      {/* User Info */}
      <div className="p-4 border-b border-border bg-gradient-to-r from-[#F5F0E8] to-[#FAFAF8]">
        <div className="flex items-center gap-2 mb-1">
          {getRolIcon()}
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider" data-testid={`${testIdPrefix}current-user-role`}>
            {getRolLabel()}
          </span>
        </div>
        <p className="text-sm font-semibold text-foreground truncate" data-testid={`${testIdPrefix}current-user-name`}>{user?.nombre || 'Usuario'}</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {navItems.map((item, idx) => {
          if (item.type === 'separator') {
            return (
              <div key={idx} className="pt-4 pb-2">
                <Separator className="mb-2" />
                <p className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {item.label}
                </p>
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
              data-testid={`${testIdPrefix}${item.testId || `nav-${item.to.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '')}`}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-[#1B2A4A] text-white shadow-md'
                    : 'text-muted-foreground hover:bg-[#F5F0E8] hover:text-foreground'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="min-w-0 whitespace-normal leading-5">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="p-3 border-t border-border">
        <Button
          variant="ghost"
          onClick={() => {
            logout();
            onClose?.();
          }}
          className="w-full justify-start text-destructive hover:text-destructive hover:bg-red-50"
          data-testid={`${testIdPrefix}sidebar-logout-button`}
        >
          <LogOut className="w-4 h-4 mr-3" />
          Cerrar Sesión
        </Button>
      </div>
    </div>
  );
}

export default function AppLayout() {
  const { user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const routeGuideKey = resolveRouteGuide(location.pathname, user?.rol);

  const getBreadcrumb = () => {
    const path = location.pathname;
    if (breadcrumbMap[path]) return breadcrumbMap[path];
    if (path.startsWith('/semana/')) return `Semana ${path.split('/')[2]}`;
    if (path.startsWith('/mi-semana/')) return `Mi Semana ${path.split('/')[2]}`;
    if (path.startsWith('/persona/')) return 'Gestión de Persona';
    if (path.startsWith('/personas/')) return 'Perfil 360';
    if (path.startsWith('/ministerios/')) return 'Detalle de Ministerio';
    if (path.startsWith('/procesos/7-semanas/')) return 'Inscripción de 7 Semanas';
    if (path.startsWith('/lider/')) return 'Panel del Líder';
    if (path.startsWith('/celulas/')) return 'Sistema Celular';
    if (path.startsWith('/puertas/')) return 'Sistema de las 9 Puertas';
    if (path.startsWith('/junta/reuniones/')) return 'Reunión de Junta';
    return 'Página';
  };
  const currentBreadcrumb = getBreadcrumb();

  useEffect(() => {
    document.title = `${BRAND.name} | ${currentBreadcrumb}`;
  }, [currentBreadcrumb]);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:flex-col w-64 border-r border-border bg-card">
        <SidebarContent />
      </aside>

      {/* Mobile Sidebar (Sheet) */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="p-0 w-[85vw] max-w-xs" data-testid="mobile-navigation-sheet">
          <VisuallyHidden>
            <SheetTitle>Menú de navegación</SheetTitle>
            <SheetDescription>Accesos disponibles según su rol institucional.</SheetDescription>
          </VisuallyHidden>
          <SidebarContent onClose={() => setMobileOpen(false)} testIdPrefix="mobile-" />
        </SheetContent>
      </Sheet>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {/* Top Bar: hamburger + breadcrumb + logo (mobile) */}
        <div className="sticky top-0 z-20 bg-card/95 backdrop-blur-md border-b border-border">
          <div className="flex items-center gap-2 px-3 py-2.5 lg:px-6 lg:py-3">
            {/* Hamburger - solo mobile */}
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden shrink-0 h-9 w-9"
              onClick={() => setMobileOpen(true)}
              data-testid="btn-menu-mobile"
              aria-label="Abrir menú"
            >
              <Menu className="w-5 h-5" />
            </Button>

            {/* Logo mini - solo mobile */}
            <div className="flex items-center gap-2 lg:hidden shrink-0">
              <div className="w-9 h-9 rounded-md bg-[#0F1A33] flex items-center justify-center p-0.5">
                <img
                  src={LOGO_URL}
                  alt={BRAND.name}
                  className="w-full h-full object-contain logo-transparent"
                />
              </div>
              <span className="font-semibold text-sm text-foreground" style={{ fontFamily: 'Spectral, serif' }}>
                {BRAND.name}
              </span>
            </div>

            {/* Breadcrumb - desktop ve completo, mobile oculto hasta sm */}
            <div className="hidden sm:flex items-center gap-2 text-sm text-muted-foreground min-w-0 flex-1 lg:flex-initial">
              <span className="hidden lg:inline">{BRAND.name}</span>
              <ChevronRight className="w-4 h-4 hidden lg:inline" />
              <span className="text-foreground font-medium truncate" data-testid="current-breadcrumb">{currentBreadcrumb}</span>
            </div>

            {/* Spacer + acciones a la derecha */}
            <div className="flex-1 sm:flex-initial sm:ml-auto flex items-center justify-end gap-1">
              {routeGuideKey && <ContextGuideButton moduleKey={routeGuideKey} compact />}
              <DisplayScaleToggle />
            </div>
          </div>
        </div>

        <Outlet />
      </main>
    </div>
  );
}
