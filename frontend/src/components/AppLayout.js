import React, { Suspense, useEffect, useState } from 'react';
import axios from 'axios';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { prefetchPages } from '../lib/lazyPage';
import PageSkeleton from './PageSkeleton';
import { Button } from './ui/button';
import { Separator } from './ui/separator';
import {
  LayoutDashboard, BookOpen, Map, Calendar, Users, BarChart3, LogOut, Menu, ChevronRight,
  Crown, Star, Trophy, Presentation, NotebookPen, KeyRound, IdCard, Church, Search, DatabaseZap,
  Activity, Award, BookHeart, Compass, GraduationCap, HeartHandshake, Network, RadioTower, DoorOpen, Gavel, Landmark, MapPinned,
  PanelLeftClose, PanelLeftOpen, ShieldCheck, Droplets, Baby, Bus, Footprints, ClipboardCheck, Trash2, DatabaseBackup, UserCircle, UserPlus
} from 'lucide-react';

import { LOGO_IGLESIA } from '../data/presentationData';
import PortalNotificationsBell from './PortalNotificationsBell';
import MobileBottomBar from './mobile/MobileBottomNav';
import { HelpButton } from './invasions/HelpButton';
import { RadioButton } from './invasions/RadioButton';
import { InvasionTodayProvider } from '../context/InvasionTodayContext';
import { RadioProvider } from '../context/RadioContext';
import { RadioBanner, RadioPTT } from './invasions/RadioDock';
import { ContextGuideButton } from './guides/ContextGuideButton';
import { FloatingLibraryScanButton } from './library/FloatingLibraryScanButton';
import { resolveRouteGuide } from './guides/guideRouteMap';
import { BRAND } from '../config/brand';
import { canManageBaptismEvents, canManageDedicationEvents, canViewCare, canViewFinanceModule, canViewFormation, canViewFrontGroups, canViewGeo, canViewLeadership, canViewLibraryModule, canViewOperations, canAccessCampaignOperator, canAccessOutreach, canCreateOutreachCampaign, canViewPastoralFrontGroup, canViewProcesses, canViewCellular, canViewDoors, canViewDirectory, canManageInvitationCodes, canWriteEvangelismLog, canViewPresentationManual, hasAnyCapability, hasCapability, isGeneralCoordinator, isPastoralAuthority } from '../lib/accessControl';
import { useBoardAccess } from '../hooks/useBoardAccess';
import { useMentorAccess } from '../hooks/useMentorAccess';
const LOGO_URL = LOGO_IGLESIA;

// Menu items by role
const consolidationDetailMatch = (pathname) => /^\/procesos\/consolidacion\/(?!mi-panel$)[^/]+$/.test(pathname);

const getNavItems = (user, boardAllowed = false, isActiveMentor = false, hasVisitorAssignments = false) => {
  const rol = user?.rol;
  // MT3: supervisar «Mi Trabajo» por mentor (coordinador general, pastoral, encargados de Consolidación).
  const supervision = isPastoralAuthority(user) || isGeneralCoordinator(user) || hasCapability(user, 'consolidation.assign')
    ? [{ to: '/mi-trabajo/supervision', icon: ClipboardCheck, label: 'Supervisar Mi Trabajo', testId: 'nav-my-work-supervision' }] : [];
  // Registro de visitantes (tabletas de bienvenida): pastoral o con alguna capacidad visitors.*.
  const visitors = isPastoralAuthority(user) || ['visitors.devices.manage', 'visitors.read', 'visitors.followup.manage', 'visitors.welcome.operate', 'visitors.texts.manage'].some((item) => hasCapability(user, item))
    ? [{ to: '/visitantes', icon: UserPlus, label: 'Registro de visitantes', testId: 'nav-visitors' }]
    : hasVisitorAssignments ? [{ to: '/visitantes?tab=seguimiento', icon: UserPlus, label: 'Mis visitantes asignados', testId: 'nav-visitors' }] : [];
  // Invasiones › Reporte para la pastora (Modo Presentar sin pegar enlaces).
  const presentReport = { to: '/invasiones/reporte-pastora', icon: Presentation, label: 'Invasiones · Reporte para la pastora', testId: 'nav-present-report' };
  const BASE_PORTAL_ITEMS = [
    { to: '/mi-perfil', icon: UserCircle, label: 'Mi perfil', testId: 'nav-mi-perfil' },
    { to: '/mis-estadisticas', icon: BarChart3, label: 'Mis estadísticas', testId: 'nav-mis-estadisticas' },
  ];
  if (isPastoralAuthority(user)) {
    const personItems = [
      ...BASE_PORTAL_ITEMS,
      { to: '/grupo-frontal', icon: Network, label: 'Grupo Frontal', testId: 'nav-front-group' },
      { to: '/dashboard-general', icon: Crown, label: 'Panel General', end: true },
      { to: '/nucleo', icon: DatabaseZap, label: 'Gobierno del Núcleo', testId: 'nav-core-governance' },
      { to: '/procesos/dashboard', icon: Activity, label: 'Panel de Procesos', testId: 'nav-process-dashboard' },
      { to: '/procesos/consolidacion', icon: Activity, label: 'Consolidación', testId: 'nav-consolidation', end: true, extraActiveMatch: consolidationDetailMatch },
      { to: '/procesos/discipulado', icon: BookHeart, label: 'Educación / Discipulado', testId: 'nav-discipleship' },
      { to: '/bautismos', icon: Droplets, label: 'Bautismos', testId: 'nav-baptism' },
      { to: '/presentaciones', icon: Baby, label: 'Presentación de Niños', testId: 'nav-dedication' },
      { to: '/formacion', icon: GraduationCap, label: 'Formación', testId: 'nav-formation' },
      { to: '/libreria', icon: BookOpen, label: 'Librería 360', testId: 'nav-library' },
      { to: '/campanas/ven-y-come/control', icon: Bus, label: 'Campaña Ven y Come', testId: 'nav-campaign-venycome' },
      { to: '/mentoria/visitas', icon: Footprints, label: 'Visitas e Invasiones', testId: 'nav-outreach' },
      { to: '/mentoria/supervision', icon: BarChart3, label: 'Supervisión de Invasiones', testId: 'nav-supervision' },
      presentReport,
      { to: '/liderazgo', icon: Award, label: 'Liderazgo', testId: 'nav-leadership' },
      { to: '/mapas', icon: MapPinned, label: 'Mapa 360', testId: 'nav-geo-maps' },
      { to: '/operaciones', icon: Calendar, label: 'Operaciones', testId: 'nav-operations' },
      { to: '/cuidado-pastoral', icon: ShieldCheck, label: 'Cuidado Pastoral', testId: 'nav-pastoral-care' },
      { to: '/procesos/mentoria', icon: HeartHandshake, label: 'Mentoría', testId: 'nav-mentorship' },
      { to: '/procesos/cap', icon: Compass, label: 'Encuentra tu lugar para servir', testId: 'nav-cap' },
      { to: '/celulas/dashboard', icon: RadioTower, label: 'Sistema Celular', testId: 'nav-cellular' },
      { to: '/puertas/dashboard', icon: DoorOpen, label: '9 Puertas', testId: 'nav-doors' },
      { to: '/junta/dashboard', icon: Gavel, label: 'Junta Directiva', testId: 'nav-board' },
      { to: '/finanzas', icon: Landmark, label: 'Contabilidad y Finanzas', testId: 'nav-finance' },
      { to: '/personas', icon: IdCard, label: 'Personas', testId: 'nav-personas' },
      { to: '/directorio', icon: Search, label: 'Directorio de Talentos', testId: 'nav-directorio-talentos' },
      { to: '/ministerios', icon: Church, label: 'Ministerios', testId: 'nav-ministerios' },
      { to: '/bitacora', icon: NotebookPen, label: 'Bitácora Evangelística' },
      { to: '/codigos', icon: KeyRound, label: 'Códigos de Invitación' },
      { to: '/presentacion', icon: Presentation, label: 'Manual de 7 Semanas' },
      { type: 'separator', label: 'Administración' },
      { to: '/estadisticas', icon: BarChart3, label: 'Estadísticas Globales' },
      { to: '/admin/datos-de-prueba', icon: FlaskConical, label: 'Datos de prueba', testId: 'nav-test-data' },
      { to: '/admin/historial-borrados', icon: Trash2, label: 'Historial de Borrados', testId: 'nav-admin-deletions' },
      { to: '/admin/migracion-c11', icon: DatabaseBackup, label: 'Migración de Datos (C11)', testId: 'nav-migration-c11' },
    ];
    if (isActiveMentor) {
      personItems.push({ to: '/procesos/consolidacion/mi-panel', icon: ClipboardCheck, label: 'Mi Panel de Mentor', testId: 'nav-mentor-panel' });
    }
    return [...personItems, ...supervision, ...visitors];
  }
  
  if (rol === 'persona') {
    const processesVisible = canViewProcesses(user);
    const personaItems = [
      ...BASE_PORTAL_ITEMS,
      ...(processesVisible ? [
        { to: '/procesos/dashboard', icon: Trophy, label: 'Mi Progreso', end: true },
        // Encargados de Consolidación (C1): el mismo módulo, con alcance completo según sus capacidades.
        { to: '/procesos/consolidacion', icon: Activity, label: hasCapability(user, 'consolidation.assign') ? 'Consolidación' : 'Mi Consolidación', end: true, extraActiveMatch: consolidationDetailMatch },
        { to: '/procesos/discipulado', icon: BookHeart, label: 'Mi Discipulado' },
        { to: '/procesos/mentoria', icon: HeartHandshake, label: 'Mi Mentoría' },
        { to: '/procesos/cap', icon: Compass, label: 'Mi lugar para servir' },
      ] : []),
    ];
    if (canViewFormation(user)) personaItems.push({ to: '/formacion', icon: GraduationCap, label: 'Mi Formación', testId: 'nav-formation' });
    if (canViewCellular(user)) personaItems.push({ to: '/celulas/dashboard', icon: RadioTower, label: 'Mi Célula', testId: 'nav-cellular' });
    personaItems.push({ to: '/mapas', icon: MapPinned, label: 'Casas por visitar', testId: 'nav-geo-maps' });
    if (canViewOperations(user)) personaItems.push({ to: '/operaciones', icon: Calendar, label: 'Eventos y turnos', testId: 'nav-operations' });
    if (canAccessCampaignOperator(user)) {
      personaItems.push({ to: '/campanas/ven-y-come/control', icon: Bus, label: 'Campaña Ven y Come', testId: 'nav-campaign-venycome' });
    }
    if (canAccessOutreach(user, isActiveMentor)) {
      personaItems.push({ to: '/mentoria/visitas', icon: Footprints, label: 'Mis Visitas', testId: 'nav-outreach' });
      personaItems.push({ to: '/mentoria/supervision', icon: BarChart3, label: 'Mi Progreso en Invasión', testId: 'nav-supervision' });
    }
    if (isActiveMentor) {
      personaItems.push({ to: '/procesos/consolidacion/mi-panel', icon: ClipboardCheck, label: 'Mi Panel de Mentor', testId: 'nav-mentor-panel' });
      personaItems.unshift({ to: '/mi-trabajo', icon: ClipboardCheck, label: 'Mi Trabajo', testId: 'nav-my-work' });
    }
    if (canViewFrontGroups(user)) {
      personaItems.push({ to: '/grupo-frontal', icon: Network, label: 'Grupo Frontal', testId: 'nav-front-group' });
      if (!canAccessOutreach(user, isActiveMentor)) {
        personaItems.push({ to: '/mentoria/supervision', icon: BarChart3, label: 'Supervisión de mi Rama', testId: 'nav-supervision' });
      }
    }
    return [...personaItems, ...supervision, ...visitors];
  }
  
  // Default: lider
  const items = [
    ...BASE_PORTAL_ITEMS,
    ...((canViewPastoralFrontGroup(user) || canViewFrontGroups(user)) ? [{ to: '/grupo-frontal', icon: Network, label: 'Grupo Frontal', testId: 'nav-front-group' }] : []),
    { to: '/', icon: LayoutDashboard, label: 'Panel principal', end: true },
    { to: '/procesos/dashboard', icon: Activity, label: 'Panel de Procesos', testId: 'nav-process-dashboard' },
    { to: '/procesos/consolidacion', icon: Activity, label: 'Consolidación', testId: 'nav-consolidation', end: true, extraActiveMatch: consolidationDetailMatch },
    { to: '/procesos/discipulado', icon: BookHeart, label: 'Educación / Discipulado', testId: 'nav-discipleship' },
    { to: '/bautismos', icon: Droplets, label: 'Bautismos', testId: 'nav-baptism' },
    { to: '/presentaciones', icon: Baby, label: 'Presentación de Niños', testId: 'nav-dedication' },
    { to: '/formacion', icon: GraduationCap, label: 'Formación', testId: 'nav-formation' },
    { to: '/libreria', icon: BookOpen, label: 'Librería 360', testId: 'nav-library' },
    { to: '/campanas/ven-y-come/control', icon: Bus, label: 'Campaña Ven y Come', testId: 'nav-campaign-venycome' },
    { to: '/mentoria/visitas', icon: Footprints, label: 'Visitas e Invasiones', testId: 'nav-outreach' },
    { to: '/mentoria/supervision', icon: BarChart3, label: 'Supervisión de Invasiones', testId: 'nav-supervision' },
    ...(isGeneralCoordinator(user) ? [presentReport] : []),
    { to: '/liderazgo', icon: Award, label: 'Liderazgo', testId: 'nav-leadership' },
    { to: '/mapas', icon: MapPinned, label: 'Mapa 360', testId: 'nav-geo-maps' },
    { to: '/operaciones', icon: Calendar, label: 'Operaciones', testId: 'nav-operations' },
    { to: '/cuidado-pastoral', icon: ShieldCheck, label: 'Cuidado Pastoral', testId: 'nav-pastoral-care' },
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
    ...(isGeneralCoordinator(user) || hasCapability(user, 'consolidation.assign') ? [{ to: '/estadisticas', icon: BarChart3, label: 'Estadísticas Globales' }] : []),
    ...(isGeneralCoordinator(user) ? [{ to: '/admin/datos-de-prueba', icon: FlaskConical, label: 'Datos de prueba', testId: 'nav-test-data' }] : []),
    ...visitors,
  ];
  if (hasAnyCapability(user, ['core.access.manage'])) {
    items.splice(1, 0, { to: '/nucleo', icon: DatabaseZap, label: 'Gestión de accesos', testId: 'nav-core-governance' });
  }
  if (canViewFinanceModule(user) && !items.some((item) => item.to === '/finanzas')) {
    items.splice(1, 0, { to: '/finanzas', icon: Landmark, label: 'Contabilidad y Finanzas', testId: 'nav-finance' });
  }
  if (isActiveMentor) {
    items.push({ to: '/procesos/consolidacion/mi-panel', icon: ClipboardCheck, label: 'Mi Panel de Mentor', testId: 'nav-mentor-panel' });
    // MT2: «Mi Trabajo» primero (inicio del mentor); Mi perfil y los demás módulos siguen igual.
    items.unshift({ to: '/mi-trabajo', icon: ClipboardCheck, label: 'Mi Trabajo', testId: 'nav-my-work' });
  }
  if (canCreateOutreachCampaign(user)) {
    items.push({ to: '/admin/historial-borrados', icon: Trash2, label: 'Historial de Borrados', testId: 'nav-admin-deletions' });
    items.push({ to: '/admin/migracion-c11', icon: DatabaseBackup, label: 'Migración de Datos (C11)', testId: 'nav-migration-c11' });
  }
  items.push(...supervision);
  return items.filter((item) => (
    (item.to !== '/grupo-frontal' || isPastoralAuthority(user) || canViewFrontGroups(user) || canViewPastoralFrontGroup(user))
  ) && (
    item.to !== '/libreria' || canViewLibraryModule(user)
  ) && (
    item.to !== '/liderazgo' || canViewLeadership(user)
  ) && (
    item.to !== '/mapas' || canViewGeo(user)
  ) && (
    item.to !== '/operaciones' || canViewOperations(user)
  ) && (
    item.to !== '/cuidado-pastoral' || canViewCare(user)
  ) && (
    item.to !== '/junta/dashboard' || boardAllowed
  ) && (
    item.to !== '/formacion' || canViewFormation(user)
  ) && (
    item.to !== '/bautismos' || canManageBaptismEvents(user)
  ) && (
    item.to !== '/presentaciones' || canManageDedicationEvents(user)
  ) && (
    item.to !== '/campanas/ven-y-come/control' || canAccessCampaignOperator(user)
  ) && (
    item.to !== '/mentoria/visitas' || canAccessOutreach(user, isActiveMentor)
  ) && (
    item.to !== '/mentoria/supervision' || canAccessOutreach(user, isActiveMentor) || canViewFrontGroups(user)
  ) && (
    !['/procesos/dashboard', '/procesos/consolidacion', '/procesos/discipulado', '/procesos/mentoria', '/procesos/cap'].includes(item.to) || canViewProcesses(user)
  ) && (
    item.to !== '/celulas/dashboard' || canViewCellular(user)
  ) && (
    item.to !== '/puertas/dashboard' || canViewDoors(user)
  ) && (
    !['/personas', '/directorio', '/ministerios'].includes(item.to) || canViewDirectory(user)
  ) && (
    item.to !== '/codigos' || canManageInvitationCodes(user)
  ) && (
    item.to !== '/bitacora' || canWriteEvangelismLog(user)
  ) && (
    item.to !== '/presentacion' || canViewPresentationManual(user)
  ) && (
    item.to !== '/estadisticas' || isPastoralAuthority(user) || isGeneralCoordinator(user) || hasCapability(user, 'consolidation.assign')
  ) && (
    item.to !== '/' || canViewProcesses(user)
  )).filter((item, index, all) => item.type !== 'separator' || all.slice(index + 1).some((next) => next.type !== 'separator'));
};

const breadcrumbMap = {
  '/': 'Panel principal',
  '/dashboard': 'Panel principal',
  '/dashboard-general': 'Panel General',
  '/mi-perfil': 'Mi perfil',
  '/mi-trabajo': 'Mi Trabajo',
  '/mi-trabajo/supervision': 'Supervisar Mi Trabajo',
  '/invasiones/reporte-pastora': 'Reporte para la pastora',
  '/grupo-frontal': 'Grupo Frontal',
  '/mis-estadisticas': 'Mis estadísticas',
  '/mi-progreso': 'Mi Progreso',
  '/presentacion': 'Manual de 7 Semanas',
  '/introduccion': 'Introducción del Manual',
  '/mapa': 'Mapa de las 7 Semanas',
  '/registro': 'Registro de Contactos',
  '/bitacora': 'Bitácora Evangelística',
  '/codigos': 'Códigos de Invitación',
  '/estadisticas': 'Estadísticas Globales',
  '/admin/datos-de-prueba': 'Datos de prueba',
  '/visitantes': 'Registro de visitantes',
  '/mis-estadisticas/manual': 'Mi progreso del Manual de 7 Semanas',
  '/directorio': 'Directorio de Talentos',
  '/ministerios': 'Ministerios',
  '/personas': 'Personas',
  '/personas/nueva': 'Nueva Persona',
  '/personas/importar': 'Importar membresía',
  '/bautismos': 'Bautismos',
  '/presentaciones': 'Presentación de Niños',
  '/operaciones': 'Operaciones',
  '/operaciones/eventos': 'Eventos',
  '/cuidado-pastoral': 'Cuidado Pastoral',
  '/cuidado-pastoral/casos': 'Casos pastorales',
  '/cuidado-pastoral/operacion-72': 'Operación 72',
  '/cuidado-pastoral/visitas': 'Visitas pastorales',
  '/nucleo': 'Gobierno del Núcleo',
  '/procesos/dashboard': 'Panel de Procesos',
  '/procesos/7-semanas': 'Ley de las 7 Semanas',
  '/procesos/consolidacion': 'Consolidación',
  '/procesos/consolidacion/mi-panel': 'Mi Panel de Mentor',
  '/procesos/discipulado': 'Educación / Discipulado',
  '/grupos-frontales': 'Grupos Frontales',
  '/liderazgo': 'Liderazgo',
  '/mapas': 'Mapa 360',
  '/procesos/mentoria': 'Mentoría',
  '/mentoria/visitas': 'Visitas e Invasiones',
  '/mentoria/puerta-a-puerta': 'Puerta a puerta',
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

// ¿Tiene visitantes asignados para seguimiento? (una sola consulta por sesión)
let visitorAssignmentsCache = { userId: null, promise: null };
function useVisitorAssignments(user) {
  const { API, getAuthHeaders } = useAuth();
  const [value, setValue] = useState(false);
  useEffect(() => {
    if (!user?.id && !user?.user_id) return undefined;
    const userId = user.id || user.user_id;
    if (visitorAssignmentsCache.userId !== userId) {
      visitorAssignmentsCache = { userId, promise: axios.get(`${API}/api/visitors/followup/mine-count`, getAuthHeaders()).then((response) => response.data.count > 0).catch(() => false) };
    }
    let alive = true;
    visitorAssignmentsCache.promise.then((result) => { if (alive) setValue(result); });
    return () => { alive = false; };
  }, [API, getAuthHeaders, user?.id, user?.user_id]); // eslint-disable-line react-hooks/exhaustive-deps
  return value;
}

function SidebarContent({ onClose, testIdPrefix = '', boardAllowed = false, isActiveMentor = false }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const hasVisitorAssignments = useVisitorAssignments(user);
  const navItems = getNavItems(user, boardAllowed, isActiveMentor, hasVisitorAssignments);

  const getRolLabel = () => {
    if (isPastoralAuthority(user)) return 'Pastor (Acceso Maestro)';
    if (user?.access_level === 'coordinador_general') return 'Coordinador general';
    if (user?.rol === 'persona') return canViewProcesses(user) ? 'Consolidado' : 'Miembro';
    return 'Líder';
  };

  const getRolIcon = () => {
    if (isPastoralAuthority(user)) return <Crown className="w-4 h-4 text-yellow-500" />;
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
              className={({ isActive }) => {
                const active = isActive || (item.extraActiveMatch && item.extraActiveMatch(location.pathname));
                return `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  active
                    ? 'bg-[#1B2A4A] text-white shadow-md'
                    : 'text-muted-foreground hover:bg-[#F5F0E8] hover:text-foreground'
                }`;
              }}
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
  const boardAccess = useBoardAccess();
  const mentorAccess = useMentorAccess();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mapSidebarOpen, setMapSidebarOpen] = useState(false);
  const location = useLocation();
  // Con la sesión abierta, precarga en segundo plano el código de los módulos.
  useEffect(() => { if (user) prefetchPages(); }, [user]);
  const isMapRoute = location.pathname === '/mapas';
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
    if (path.startsWith('/cuidado-pastoral/casos/')) return 'Expediente pastoral';
    if (path.startsWith('/junta/reuniones/')) return 'Reunión de Junta';
    if (path.startsWith('/invasiones/') && path.endsWith('/reporte')) return 'Reporte de invasión';
    if (path.startsWith('/invasiones/') && path.endsWith('/asistencia')) return 'Asistencia de invasión';
    if (path.startsWith('/invasiones/') && path.endsWith('/programa')) return 'Programa de invasión';
    if (path.startsWith('/invasiones/') && path.endsWith('/ayuda')) return 'Alertas de ayuda';
    if (path.startsWith('/invasiones/') && path.endsWith('/radio')) return 'Radio';
    return 'Página';
  };
  const currentBreadcrumb = getBreadcrumb();

  useEffect(() => {
    document.title = `${BRAND.name} | ${currentBreadcrumb}`;
  }, [currentBreadcrumb]);

  useEffect(() => {
    if (isMapRoute) setMapSidebarOpen(false);
  }, [isMapRoute]);

  return (
    <InvasionTodayProvider>
    <RadioProvider>
    <div className="app-shell-height flex overflow-hidden bg-background print:block print:h-auto print:overflow-visible">
      {/* Desktop Sidebar */}
      {(!isMapRoute || mapSidebarOpen) && <aside className="hidden lg:flex lg:w-64 lg:flex-col border-r border-border bg-card" data-testid="desktop-sidebar" data-print-hide>
        <SidebarContent boardAllowed={boardAccess.allowed} isActiveMentor={mentorAccess.isActiveMentor} />
      </aside>}

      {mobileOpen && <div className="fixed inset-0 z-50 lg:hidden" data-testid="mobile-navigation-overlay"><button type="button" className="absolute inset-0 bg-black/45" onClick={() => setMobileOpen(false)} aria-label="Cerrar menú" data-testid="close-mobile-navigation-backdrop" /><aside id="mobile-navigation-sheet" className="relative h-full w-[85vw] max-w-xs bg-white shadow-2xl" data-testid="mobile-navigation-sheet" aria-label="Menú de navegación"><SidebarContent onClose={() => setMobileOpen(false)} testIdPrefix="mobile-" boardAllowed={boardAccess.allowed} isActiveMentor={mentorAccess.isActiveMentor} /></aside></div>}

      {/* Main Content */}
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden" data-print-main>
        {/* Top Bar: hamburger + breadcrumb + logo (mobile) */}
        <div className="z-20 shrink-0 border-b border-border bg-card/95 backdrop-blur-md" data-print-hide>
          <div className="flex items-center gap-2 px-3 py-2.5 lg:px-6 lg:py-3">
            {isMapRoute && <Button type="button" variant="ghost" size="icon" className="hidden h-9 w-9 shrink-0 lg:inline-flex" onClick={() => setMapSidebarOpen((value) => !value)} data-testid="toggle-map-sidebar-button" aria-label={mapSidebarOpen ? 'Ocultar menú lateral' : 'Mostrar menú lateral'}>{mapSidebarOpen ? <PanelLeftClose className="h-5 w-5" /> : <PanelLeftOpen className="h-5 w-5" />}</Button>}
            {/* Hamburger - solo mobile */}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="lg:hidden shrink-0 h-11 w-11"
              onClick={() => setMobileOpen(true)}
              data-testid="btn-menu-mobile"
              aria-label="Abrir menú"
              aria-expanded={mobileOpen}
              aria-controls="mobile-navigation-sheet"
            >
              <Menu className="w-5 h-5" />
            </Button>

            {/* Logo mini - solo mobile */}
            <div className="flex min-w-0 items-center gap-2 lg:hidden">
              <div className="w-9 h-9 shrink-0 rounded-md bg-[#0F1A33] flex items-center justify-center p-0.5">
                <img
                  src={LOGO_URL}
                  alt={BRAND.name}
                  className="w-full h-full object-contain logo-transparent"
                />
              </div>
              {/* Se acorta (o se oculta en pantallas muy angostas) para dejar lugar a Radio y Ayuda. */}
              <span className="min-w-0 truncate font-semibold text-sm text-foreground max-[359px]:hidden" style={{ fontFamily: 'Spectral, serif' }}>
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
              {/* Botón rojo de ayuda: solo para participantes de una invasión activa hoy. */}
              <RadioButton />
              <HelpButton />
              <PortalNotificationsBell />
            </div>
          </div>
        </div>

        {/* Radio global: quién habla / activar audio, en cualquier pantalla. */}
        <RadioBanner />
        <div className={`min-h-0 flex-1 ${isMapRoute ? 'overflow-hidden' : 'overflow-y-auto'}`} data-testid="app-page-scroll-container">
          <Suspense fallback={<PageSkeleton />}><Outlet /></Suspense>
        </div>
        {/* Barra inferior tipo app (solo < 1024 px): ocupa su propio espacio, no tapa el contenido. */}
        <MobileBottomBar isActiveMentor={mentorAccess.isActiveMentor} menuOpen={mobileOpen} onOpenMenu={() => setMobileOpen(true)} />
        <div data-print-hide><FloatingLibraryScanButton /></div>
        <RadioPTT />
      </main>
    </div>
    </RadioProvider>
    </InvasionTodayProvider>
  );
}
