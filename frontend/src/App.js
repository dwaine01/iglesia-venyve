import React, { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useSearchParams } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import AppLayout from './components/AppLayout';
import AccessDeniedPage from './components/AccessDeniedPage';
import { canManageDirectMembership, canManageBaptismEvents, canManageDedicationEvents, canViewCare, canViewFinanceModule, canViewFormation, canViewFrontGroups, canViewGeo, canViewLeadership, canViewLibraryModule, canManageLibraryInventory, canViewLibraryPurchaseOrders, canViewLibraryReports, canViewOperations, canAccessCampaignOperator, canAccessOutreach, canCreateOutreachCampaign, canViewPastoralFrontGroup, canViewProcesses, canViewCellular, canViewDoors, canViewDirectory, canManageInvitationCodes, canWriteEvangelismLog, canViewPresentationManual, hasAnyCapability, isGeneralCoordinator, isPastoralAuthority } from './lib/accessControl';
import { useBoardAccess } from './hooks/useBoardAccess';
import { useMentorAccess } from './hooks/useMentorAccess';
import { lazyPage } from './lib/lazyPage';
import PageSkeleton from './components/PageSkeleton';
import './App.css';

// Cada página se descarga al abrirla (o antes, precargada en segundo plano).
const DashboardPage = lazyPage(() => import('./pages/DashboardPage'));
const DashboardGeneralPage = lazyPage(() => import('./pages/DashboardGeneralPage'));
const MiProgresoPage = lazyPage(() => import('./pages/MiProgresoPage'));
const IntroduccionPage = lazyPage(() => import('./pages/IntroduccionPage'));
const MapaPage = lazyPage(() => import('./pages/MapaPage'));
const SemanaPage = lazyPage(() => import('./pages/SemanaPage'));
const RegistroPage = lazyPage(() => import('./pages/RegistroPage'));
const EstadisticasPage = lazyPage(() => import('./pages/EstadisticasPage'));
const GlobalStatsPage = lazyPage(() => import('./pages/GlobalStatsPage'));
const KioskPage = lazyPage(() => import('./pages/KioskPage'));
const WelcomeScreenPage = lazyPage(() => import('./pages/WelcomeScreenPage'));
const VisitorsAdminPage = lazyPage(() => import('./pages/VisitorsAdminPage'));
const PersonasListPage = lazyPage(() => import('./pages/PersonasListPage'));
const PersonaNuevaPage = lazyPage(() => import('./pages/PersonaNuevaPage'));
const PersonaPerfilPage = lazyPage(() => import('./pages/PersonaPerfilPage'));
const MembershipImportPage = lazyPage(() => import('./pages/MembershipImportPage'));
const OperationsDashboardPage = lazyPage(() => import('./pages/operations/OperationsDashboardPage'));
const PastoralDashboardPage = lazyPage(() => import('./pages/pastoral/PastoralDashboardPage'));
const PastoralCasesInboxPage = lazyPage(() => import('./pages/pastoral/PastoralCasesInboxPage'));
const PastoralExpedienteDetailPage = lazyPage(() => import('./pages/pastoral/PastoralExpedienteDetailPage'));
const Operacion72DashboardPage = lazyPage(() => import('./pages/pastoral/Operacion72DashboardPage'));
const PastoralVisitsPage = lazyPage(() => import('./pages/pastoral/PastoralVisitsPage'));
const OperationsEventsPage = lazyPage(() => import('./pages/operations/OperationsEventsPage'));
const OperationEventDetailPage = lazyPage(() => import('./pages/operations/OperationEventDetailPage'));
const OperationOccurrencePage = lazyPage(() => import('./pages/operations/OperationOccurrencePage'));
const OperationCheckInPage = lazyPage(() => import('./pages/operations/OperationCheckInPage'));
const MinisteriosPage = lazyPage(() => import('./pages/MinisteriosPage'));
const MinisterioDetailPage = lazyPage(() => import('./pages/MinisterioDetailPage'));
const DirectorioTalentosPage = lazyPage(() => import('./pages/DirectorioTalentosPage'));
const BitacoraPage = lazyPage(() => import('./pages/BitacoraPage'));
const PresentacionHomePage = lazyPage(() => import('./pages/PresentacionHomePage'));
const PresentacionPresenterPage = lazyPage(() => import('./pages/PresentacionPresenterPage'));
const PresentacionAudiencePage = lazyPage(() => import('./pages/PresentacionAudiencePage'));
const PresentacionJoinPage = lazyPage(() => import('./pages/PresentacionJoinPage'));
const PresentacionImprimirPage = lazyPage(() => import('./pages/PresentacionImprimirPage'));
const PresentacionNotasPage = lazyPage(() => import('./pages/PresentacionNotasPage'));
const CodigosInvitacionPage = lazyPage(() => import('./pages/CodigosInvitacionPage'));
const AcceptInvitationPage = lazyPage(() => import('./pages/AcceptInvitationPage'));
const CoreGovernancePage = lazyPage(() => import('./pages/CoreGovernancePage'));
const FormationAdminPage = lazyPage(() => import('./pages/formation/FormationAdminPage'));
const FormationCohortPage = lazyPage(() => import('./pages/formation/FormationCohortPage'));
const ChangePasswordPage = lazyPage(() => import('./pages/ChangePasswordPage'));
const AccessOnboardingPage = lazyPage(() => import('./pages/AccessOnboardingPage'));
const MembershipVerificationPage = lazyPage(() => import('./pages/MembershipVerificationPage'));
const BaptismVerificationPage = lazyPage(() => import('./pages/BaptismVerificationPage'));
const BaptismEventsPage = lazyPage(() => import('./pages/BaptismEventsPage'));
const DedicationVerificationPage = lazyPage(() => import('./pages/DedicationVerificationPage'));
const DedicationEventsPage = lazyPage(() => import('./pages/DedicationEventsPage'));
const LibraryDashboardPage = lazyPage(() => import('./pages/library/LibraryDashboardPage'));
const LibraryCatalogPage = lazyPage(() => import('./pages/library/LibraryCatalogPage'));
const LibraryMyInventoryPage = lazyPage(() => import('./pages/library/LibraryMyInventoryPage'));
const LibraryPurchaseOrdersPage = lazyPage(() => import('./pages/library/LibraryPurchaseOrdersPage'));
const LibraryDeficitPage = lazyPage(() => import('./pages/library/LibraryDeficitPage'));
const LibraryScanPage = lazyPage(() => import('./pages/library/LibraryScanPage'));
const LibraryReportsPage = lazyPage(() => import('./pages/library/LibraryReportsPage'));
const LibraryTracePage = lazyPage(() => import('./pages/library/LibraryTracePage'));
const MyWorkPage = lazyPage(() => import('./pages/MyWorkPage'));
const InvasionPresentPage = lazyPage(() => import('./pages/InvasionPresentPage'));
const MyWorkSupervisionPage = lazyPage(() => import('./pages/MyWorkSupervisionPage'));
const PresentReportLauncherPage = lazyPage(() => import('./components/invasions/PresentReportLauncher'));
const LibraryLabelsPage = lazyPage(() => import('./pages/library/LibraryLabelsPage'));
const CampaignControlPage = lazyPage(() => import('./pages/campaign/CampaignControlPage'));
const CampaignScreenPage = lazyPage(() => import('./pages/campaign/CampaignScreenPage'));
const FinanceDashboardPage = lazyPage(() => import('./pages/finance/FinanceDashboardPage'));
const FinanceSetupPage = lazyPage(() => import('./pages/finance/FinanceSetupPage'));
const FinanceJournalsPage = lazyPage(() => import('./pages/finance/FinanceJournalsPage'));
const FinanceContributionsPage = lazyPage(() => import('./pages/finance/FinanceContributionsPage'));
const FinanceContributorsPage = lazyPage(() => import('./pages/finance/FinanceContributorsPage'));
const FinanceOperationsPage = lazyPage(() => import('./pages/finance/FinanceOperationsPage'));
const FinanceReconciliationPage = lazyPage(() => import('./pages/finance/FinanceReconciliationPage'));
const FinanceReportsPage = lazyPage(() => import('./pages/finance/FinanceReportsPage'));
const FinanceIntegrationsPage = lazyPage(() => import('./pages/finance/FinanceIntegrationsPage'));
const ProcessesDashboardPage = lazyPage(() => import('./pages/processes/ProcessesDashboardPage'));
const SevenWeeksPage = lazyPage(() => import('./pages/processes/SevenWeeksPage'));
const SevenWeeksDetailPage = lazyPage(() => import('./pages/processes/SevenWeeksDetailPage'));
const ConsolidationPage = lazyPage(() => import('./pages/processes/ConsolidationPage'));
const ConsolidationDetailPage = lazyPage(() => import('./pages/processes/ConsolidationDetailPage'));
const MentorPanelPage = lazyPage(() => import('./pages/processes/MentorPanelPage'));
const SupervisionPage = lazyPage(() => import('./pages/mentoria/SupervisionPage'));
const AdminDeletionsPage = lazyPage(() => import('./pages/admin/AdminDeletionsPage'));
const MigrationC11Page = lazyPage(() => import('./pages/admin/MigrationC11Page'));
const DiscipleshipPage = lazyPage(() => import('./pages/processes/DiscipleshipPage'));
const LeadershipPage = lazyPage(() => import('./pages/LeadershipPage'));
const MentorshipPage = lazyPage(() => import('./pages/processes/MentorshipPage'));
const OutreachPage = lazyPage(() => import('./pages/OutreachPage'));
const CapPage = lazyPage(() => import('./pages/processes/CapPage'));
const CellularDashboardPage = lazyPage(() => import('./pages/cellular/CellularDashboardPage'));
const CellularNetworksPage = lazyPage(() => import('./pages/cellular/CellularNetworksPage'));
const CellularListPage = lazyPage(() => import('./pages/cellular/CellularListPage'));
const CellularDetailPage = lazyPage(() => import('./pages/cellular/CellularDetailPage'));
const CellularMeetingMobilePage = lazyPage(() => import('./pages/cellular/CellularMeetingMobilePage'));
const CellularReadyPage = lazyPage(() => import('./pages/cellular/CellularReadyPage'));
const CellularNeedsPage = lazyPage(() => import('./pages/cellular/CellularNeedsPage'));
const CellularHealthPage = lazyPage(() => import('./pages/cellular/CellularHealthPage'));
const DoorsDashboardPage = lazyPage(() => import('./pages/doors/DoorsDashboardPage'));
const DoorCasesPage = lazyPage(() => import('./pages/doors/DoorCasesPage'));
const DoorDetailPage = lazyPage(() => import('./pages/doors/DoorDetailPage'));
const BoardDashboardPage = lazyPage(() => import('./pages/board/BoardDashboardPage'));
const BoardMembersPage = lazyPage(() => import('./pages/board/BoardMembersPage'));
const BoardMeetingsPage = lazyPage(() => import('./pages/board/BoardMeetingsPage'));
const BoardMeetingDetailPage = lazyPage(() => import('./pages/board/BoardMeetingDetailPage'));
const BoardMinutesPage = lazyPage(() => import('./pages/board/BoardMinutesPage'));
const MiPerfilPage = lazyPage(() => import('./pages/MiPerfilPage'));
const MiGrupoFrontalPage = lazyPage(() => import('./pages/MiGrupoFrontalPage'));
const GrupoFrontalPage = lazyPage(() => import('./pages/GrupoFrontalPage'));
const MisEstadisticasPage = lazyPage(() => import('./pages/MisEstadisticasPage'));
const GeoMapsPage = lazyPage(() => import('./pages/GeoMapsPage'));
const InvasionReportPage = lazyPage(() => import('./pages/InvasionReportPage'));
const InvasionAttendancePage = lazyPage(() => import('./pages/InvasionAttendancePage'));
const InvasionProgramPage = lazyPage(() => import('./pages/InvasionProgramPage'));
const DoorToDoorPage = lazyPage(() => import('./pages/DoorToDoorPage'));
const InvasionHelpPage = lazyPage(() => import('./pages/InvasionHelpPage'));
const RadioPage = lazyPage(() => import('./pages/RadioPage'));


function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="text-lg text-muted-foreground">Cargando...</div></div>;
  if (!user) return <Navigate to="/login" />;
  if (user.must_change_password) return <Navigate to="/cambiar-clave" replace />;
  if (user.onboarding_required && !user.onboarding_completed_at) return <Navigate to="/acuerdo-confidencialidad" replace />;
  return children;
}

// Solo para pastores
function PastorOnlyRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="text-lg text-muted-foreground">Cargando...</div></div>;
  if (!user) return <Navigate to="/login" />;
  if (!isPastoralAuthority(user)) return <AccessDeniedPage />;
  return children;
}

// Para pastores y líderes
function StaffRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="text-lg text-muted-foreground">Cargando...</div></div>;
  if (!user) return <Navigate to="/login" />;
  if (!isPastoralAuthority(user) && user.rol !== 'lider') return <AccessDeniedPage />;
  return children;
}

function AccessManagerRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex min-h-screen items-center justify-center">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!hasAnyCapability(user, ['core.access.manage'])) return <AccessDeniedPage />;
  return children;
}

function FinanceRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex min-h-screen items-center justify-center">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!canViewFinanceModule(user)) return <AccessDeniedPage />;
  return children;
}

function FormationRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex min-h-screen items-center justify-center" data-testid="formation-route-loading">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!canViewFormation(user)) return <AccessDeniedPage />;
  return children;
}

function CapabilityRoute({ children, allowed }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex min-h-screen items-center justify-center" data-testid="capability-route-loading">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!allowed(user)) return <AccessDeniedPage />;
  return children;
}

function BoardAccessRoute({ children }) {
  const { user } = useAuth();
  const access = useBoardAccess();
  if (!user || access.loading) return <div className="flex min-h-screen items-center justify-center" data-testid="board-access-loading">Cargando…</div>;
  if (!access.allowed) return <AccessDeniedPage />;
  return children;
}

function OutreachAccessRoute({ children }) {
  const { user } = useAuth();
  const mentorAccess = useMentorAccess();
  if (!user || mentorAccess.loading) return <div className="flex min-h-screen items-center justify-center" data-testid="outreach-access-loading">Cargando…</div>;
  if (!canAccessOutreach(user, mentorAccess.isActiveMentor)) return <AccessDeniedPage />;
  return children;
}

function SupervisionAccessRoute({ children }) {
  const { user } = useAuth();
  const mentorAccess = useMentorAccess();
  if (!user || mentorAccess.loading) return <div className="flex min-h-screen items-center justify-center" data-testid="supervision-access-loading">Cargando…</div>;
  if (!canAccessOutreach(user, mentorAccess.isActiveMentor) && !canViewFrontGroups(user)) return <AccessDeniedPage />;
  return children;
}

// Redirect to correct dashboard based on role
function RoleDashboard() {
  const { user } = useAuth();
  const mentor = useMentorAccess();
  if (isPastoralAuthority(user)) return <Navigate to="/dashboard-general" />;
  // MT2: el mentor activo entra a «Mi Trabajo»; coordinadores generales siguen en su panel.
  if (mentor.loading) return <PageSkeleton />;
  if (mentor.isActiveMentor && !isGeneralCoordinator(user)) return <Navigate to="/mi-trabajo" replace />;
  if (!canViewProcesses(user)) return <Navigate to="/mi-perfil" replace />;
  if (user?.rol === 'persona') return <Navigate to="/procesos/dashboard" />;
  return <ProcessesDashboardPage />;
}

// La PROPIA ficha siempre abre completa, sin permiso de directorio. Ver el
// Perfil 360 de OTRA persona exige la capability de directorio (el backend
// vuelve a validar alcance y permisos).
function PersonProfileRoute({ children }) {
  const { user, loading } = useAuth();
  const { personId } = useParams();
  if (loading) return <div className="flex min-h-screen items-center justify-center" data-testid="person-profile-route-loading">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (personId && personId === user.person_id) return children;
  // Sin directorio, la ficha igual abre: el backend decide (p. ej. el mentor
  // que contactó a la persona ve una vista mínima; los demás reciben 403).
  return children;
}

// El módulo anterior de Grupos Frontales se integró en la Estructura por niveles:
// la ruta vieja (y sus enlaces ?group=…) redirige al panel nuevo.
function LegacyFrontGroupsRedirect() {
  const [searchParams] = useSearchParams();
  const groupId = searchParams.get('group');
  return <Navigate to={groupId ? `/grupo-frontal?grupo=${groupId}&tab=ramas` : '/grupo-frontal?tab=ramas'} replace />;
}

// Enlaces antiguos (marcadores): «Estructura de grupos» y «Mi grupo frontal» de la pastora
// abren ahora el único «Grupo Frontal» en la pestaña que corresponde.
function LegacyStructureRedirect() {
  const { groupId } = useParams();
  return <Navigate to={groupId ? `/grupo-frontal?grupo=${groupId}&tab=ramas` : '/grupo-frontal?tab=ramas'} replace />;
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Suspense fallback={<PageSkeleton />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/aceptar-invitacion" element={<AcceptInvitationPage />} />
          <Route path="/cambiar-clave" element={<ChangePasswordPage />} />
          <Route path="/acuerdo-confidencialidad" element={<AccessOnboardingPage />} />
          <Route path="/verificar/carnet/:token" element={<MembershipVerificationPage />} />
          <Route path="/verificar/bautismo/:token" element={<BaptismVerificationPage />} />
          <Route path="/verificar/presentacion/:token" element={<DedicationVerificationPage />} />
          {/* Quiosco de visitantes: sin menú ni sesión de personal (token de la tableta). */}
          {/* Enlaces cortos de visitantes: /r/CÓDIGO (tabletas) y /b/CÓDIGO (pantalla de bienvenida). */}
          <Route path="/r" element={<KioskPage />} />
          <Route path="/r/:token" element={<KioskPage />} />
          <Route path="/b" element={<WelcomeScreenPage />} />
          <Route path="/b/:token" element={<WelcomeScreenPage />} />
          <Route path="/quiosco" element={<KioskPage />} />
          <Route path="/quiosco/:token" element={<KioskPage />} />
          <Route path="/pantalla-bienvenida" element={<WelcomeScreenPage />} />
          <Route path="/pantalla-bienvenida/:token" element={<WelcomeScreenPage />} />
          {/* Rutas de presentación full-screen (fuera del AppLayout) */}
          <Route path="/presentacion/presenter" element={<StaffRoute><PresentacionPresenterPage /></StaffRoute>} />
          <Route path="/presentacion/audiencia/:code" element={<PresentacionAudiencePage />} />
          <Route path="/presentacion/notas/:code" element={<PresentacionNotasPage />} />
          <Route path="/presentacion/unirse" element={<PresentacionJoinPage />} />
          <Route path="/presentacion/imprimir" element={<PresentacionImprimirPage />} />
          <Route path="/campanas/ven-y-come/pantalla" element={<CampaignScreenPage />} />
          {/* Modo Presentar del reporte: pantalla completa, sin menú (el backend valida el permiso). */}
          <Route path="/invasiones/:campaignId/reporte/presentar" element={<ProtectedRoute><InvasionPresentPage /></ProtectedRoute>} />
          <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route index element={<RoleDashboard />} />
            
            {/* Pastor routes */}
            <Route path="dashboard-general" element={<DashboardGeneralPage />} />
            <Route path="nucleo" element={<AccessManagerRoute><CoreGovernancePage /></AccessManagerRoute>} />
            <Route path="procesos/dashboard" element={<CapabilityRoute allowed={canViewProcesses}><ProcessesDashboardPage /></CapabilityRoute>} />
            <Route path="procesos/7-semanas" element={<SevenWeeksPage />} />
            <Route path="procesos/7-semanas/:enrollmentId" element={<SevenWeeksDetailPage />} />
            <Route path="procesos/consolidacion" element={<CapabilityRoute allowed={canViewProcesses}><ConsolidationPage /></CapabilityRoute>} />
            <Route path="procesos/consolidacion/mi-panel" element={<MentorPanelPage />} />
            <Route path="procesos/consolidacion/:enrollmentId" element={<ConsolidationDetailPage />} />
            <Route path="procesos/discipulado" element={<CapabilityRoute allowed={canViewProcesses}><DiscipleshipPage /></CapabilityRoute>} />
            <Route path="formacion" element={<FormationRoute><FormationAdminPage /></FormationRoute>} />
            <Route path="formacion/cohortes/:cohortId" element={<FormationRoute><FormationCohortPage /></FormationRoute>} />
            <Route path="grupos-frontales" element={<LegacyFrontGroupsRedirect />} />
            <Route path="liderazgo" element={<CapabilityRoute allowed={canViewLeadership}><LeadershipPage /></CapabilityRoute>} />
            <Route path="mapas" element={<CapabilityRoute allowed={canViewGeo}><Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center" data-testid="geo-page-loading">Cargando Mapa 360…</div>}><GeoMapsPage /></Suspense></CapabilityRoute>} />
            <Route path="procesos/mentoria" element={<CapabilityRoute allowed={canViewProcesses}><MentorshipPage /></CapabilityRoute>} />
            <Route path="procesos/cap" element={<CapabilityRoute allowed={canViewProcesses}><CapPage /></CapabilityRoute>} />
            <Route path="celulas/dashboard" element={<CapabilityRoute allowed={canViewCellular}><CellularDashboardPage /></CapabilityRoute>} />
            <Route path="celulas/redes" element={<StaffRoute><CellularNetworksPage /></StaffRoute>} />
            <Route path="celulas/lista" element={<CellularListPage />} />
            <Route path="celulas/bandeja-ready" element={<StaffRoute><CellularReadyPage /></StaffRoute>} />
            <Route path="celulas/necesidades" element={<StaffRoute><CellularNeedsPage /></StaffRoute>} />
            <Route path="celulas/salud" element={<CellularHealthPage mode="health" />} />
            <Route path="celulas/multiplicacion" element={<StaffRoute><CellularHealthPage mode="multiplication" /></StaffRoute>} />
            <Route path="celulas/genealogia" element={<CellularHealthPage mode="genealogy" />} />
            <Route path="celulas/:id/reunion-movil" element={<StaffRoute><CellularMeetingMobilePage /></StaffRoute>} />
            <Route path="celulas/:id" element={<CellularDetailPage />} />
            <Route path="puertas/dashboard" element={<CapabilityRoute allowed={canViewDoors}><DoorsDashboardPage /></CapabilityRoute>} />
            <Route path="puertas/casos" element={<StaffRoute><DoorCasesPage /></StaffRoute>} />
            <Route path="puertas/:doorKey" element={<StaffRoute><DoorDetailPage /></StaffRoute>} />
            <Route path="junta/dashboard" element={<BoardAccessRoute><BoardDashboardPage /></BoardAccessRoute>} />
            <Route path="junta/miembros" element={<BoardAccessRoute><BoardMembersPage /></BoardAccessRoute>} />
            <Route path="junta/reuniones" element={<BoardAccessRoute><BoardMeetingsPage /></BoardAccessRoute>} />
            <Route path="junta/reuniones/:meetingId" element={<BoardAccessRoute><BoardMeetingDetailPage /></BoardAccessRoute>} />
            <Route path="junta/minutas" element={<BoardAccessRoute><BoardMinutesPage /></BoardAccessRoute>} />
            <Route path="finanzas" element={<FinanceRoute><FinanceDashboardPage /></FinanceRoute>} />
            <Route path="finanzas/configuracion" element={<FinanceRoute><FinanceSetupPage /></FinanceRoute>} />
            <Route path="finanzas/asientos" element={<FinanceRoute><FinanceJournalsPage /></FinanceRoute>} />
            <Route path="finanzas/contribuciones" element={<FinanceRoute><FinanceContributionsPage /></FinanceRoute>} />
            <Route path="finanzas/contribuyentes" element={<FinanceRoute><FinanceContributorsPage /></FinanceRoute>} />
            <Route path="finanzas/contribuyentes/:personId" element={<FinanceRoute><FinanceContributorsPage /></FinanceRoute>} />
            <Route path="finanzas/operaciones" element={<FinanceRoute><FinanceOperationsPage /></FinanceRoute>} />
            <Route path="finanzas/conciliacion" element={<FinanceRoute><FinanceReconciliationPage /></FinanceRoute>} />
            <Route path="finanzas/reportes" element={<FinanceRoute><FinanceReportsPage /></FinanceRoute>} />
            <Route path="finanzas/integraciones" element={<FinanceRoute><FinanceIntegrationsPage /></FinanceRoute>} />
            <Route path="lider/:liderId/dashboard" element={<DashboardPage />} />
            
            {/* Lider routes */}
            <Route path="introduccion" element={<IntroduccionPage />} />
            <Route path="mapa" element={<MapaPage />} />
            <Route path="semana/:weekNum" element={<Navigate to="/procesos/7-semanas" replace />} />
            <Route path="persona/:personId/semana/:weekNum" element={<Navigate to="/procesos/7-semanas" replace />} />
            <Route path="registro" element={<Navigate to="/procesos/consolidacion" replace />} />
            <Route path="personas" element={<CapabilityRoute allowed={canViewDirectory}><PersonasListPage /></CapabilityRoute>} />
            <Route path="personas/nueva" element={<StaffRoute><PersonaNuevaPage /></StaffRoute>} />
            <Route path="personas/importar" element={<CapabilityRoute allowed={canManageDirectMembership}><MembershipImportPage /></CapabilityRoute>} />
            <Route path="bautismos" element={<CapabilityRoute allowed={canManageBaptismEvents}><BaptismEventsPage /></CapabilityRoute>} />
            <Route path="presentaciones" element={<CapabilityRoute allowed={canManageDedicationEvents}><DedicationEventsPage /></CapabilityRoute>} />
            <Route path="libreria" element={<CapabilityRoute allowed={canViewLibraryModule}><LibraryDashboardPage /></CapabilityRoute>} />
            <Route path="libreria/catalogo" element={<CapabilityRoute allowed={canManageLibraryInventory}><LibraryCatalogPage /></CapabilityRoute>} />
            <Route path="libreria/mi-inventario" element={<CapabilityRoute allowed={canViewLibraryModule}><LibraryMyInventoryPage /></CapabilityRoute>} />
            <Route path="libreria/ordenes-compra" element={<CapabilityRoute allowed={canViewLibraryPurchaseOrders}><LibraryPurchaseOrdersPage /></CapabilityRoute>} />
            <Route path="libreria/reserva-automatica" element={<CapabilityRoute allowed={canManageLibraryInventory}><LibraryDeficitPage /></CapabilityRoute>} />
            <Route path="libreria/escanear" element={<CapabilityRoute allowed={canViewLibraryModule}><LibraryScanPage /></CapabilityRoute>} />
            <Route path="libreria/reportes" element={<CapabilityRoute allowed={canViewLibraryReports}><LibraryReportsPage /></CapabilityRoute>} />
            {/* L3: cualquier cuenta entra; el backend muestra solo lo propio salvo a Librería/encargados. */}
            <Route path="libreria/recorrido" element={<LibraryTracePage />} />
            <Route path="mi-trabajo" element={<MyWorkPage />} />
            <Route path="mi-trabajo/supervision" element={<MyWorkSupervisionPage />} />
            <Route path="libreria/etiquetas" element={<CapabilityRoute allowed={canManageLibraryInventory}><LibraryLabelsPage /></CapabilityRoute>} />
            <Route path="campanas/ven-y-come/control" element={<CapabilityRoute allowed={canAccessCampaignOperator}><CampaignControlPage /></CapabilityRoute>} />
            <Route path="mentoria/visitas" element={<OutreachAccessRoute><OutreachPage /></OutreachAccessRoute>} />
            <Route path="mentoria/puerta-a-puerta" element={<OutreachAccessRoute><DoorToDoorPage /></OutreachAccessRoute>} />
            <Route path="mentoria/supervision" element={<SupervisionAccessRoute><SupervisionPage /></SupervisionAccessRoute>} />
            <Route path="admin/historial-borrados" element={<CapabilityRoute allowed={canCreateOutreachCampaign}><AdminDeletionsPage /></CapabilityRoute>} />
            <Route path="admin/migracion-c11" element={<CapabilityRoute allowed={canCreateOutreachCampaign}><MigrationC11Page /></CapabilityRoute>} />
            <Route path="operaciones" element={<CapabilityRoute allowed={canViewOperations}><OperationsDashboardPage /></CapabilityRoute>} />
            <Route path="operaciones/eventos" element={<CapabilityRoute allowed={canViewOperations}><OperationsEventsPage /></CapabilityRoute>} />
            <Route path="operaciones/eventos/:eventId" element={<CapabilityRoute allowed={canViewOperations}><OperationEventDetailPage /></CapabilityRoute>} />
            <Route path="operaciones/ocurrencias/:occurrenceId" element={<CapabilityRoute allowed={canViewOperations}><OperationOccurrencePage /></CapabilityRoute>} />
            <Route path="operaciones/checkin/:occurrenceId" element={<CapabilityRoute allowed={canViewOperations}><OperationCheckInPage /></CapabilityRoute>} />
            <Route path="cuidado-pastoral" element={<CapabilityRoute allowed={canViewCare}><PastoralDashboardPage /></CapabilityRoute>} />
            <Route path="cuidado-pastoral/casos" element={<CapabilityRoute allowed={canViewCare}><PastoralCasesInboxPage /></CapabilityRoute>} />
            <Route path="cuidado-pastoral/casos/:caseId" element={<CapabilityRoute allowed={canViewCare}><PastoralExpedienteDetailPage /></CapabilityRoute>} />
            <Route path="cuidado-pastoral/operacion-72" element={<CapabilityRoute allowed={canViewCare}><Operacion72DashboardPage /></CapabilityRoute>} />
            <Route path="cuidado-pastoral/visitas" element={<CapabilityRoute allowed={canViewCare}><PastoralVisitsPage /></CapabilityRoute>} />
            <Route path="personas/:personId" element={<PersonProfileRoute><PersonaPerfilPage /></PersonProfileRoute>} />
            <Route path="directorio" element={<CapabilityRoute allowed={canViewDirectory}><DirectorioTalentosPage /></CapabilityRoute>} />
            <Route path="ministerios" element={<CapabilityRoute allowed={canViewDirectory}><MinisteriosPage /></CapabilityRoute>} />
            <Route path="ministerios/:ministryId" element={<CapabilityRoute allowed={canViewDirectory}><MinisterioDetailPage /></CapabilityRoute>} />
            <Route path="bitacora" element={<CapabilityRoute allowed={canWriteEvangelismLog}><BitacoraPage /></CapabilityRoute>} />
            <Route path="codigos" element={<CapabilityRoute allowed={canManageInvitationCodes}><CodigosInvitacionPage /></CapabilityRoute>} />
            <Route path="estadisticas" element={<GlobalStatsPage />} />
            <Route path="visitantes" element={<VisitorsAdminPage />} />
            <Route path="mis-estadisticas/manual" element={<EstadisticasPage />} />
            <Route path="presentacion" element={<CapabilityRoute allowed={canViewPresentationManual}><PresentacionHomePage /></CapabilityRoute>} />
            <Route path="mi-perfil" element={<MiPerfilPage />} />
            <Route path="mi-grupo-frontal/:groupId" element={<MiGrupoFrontalPage />} />
            <Route path="grupo-frontal" element={<GrupoFrontalPage />} />
            <Route path="estructura-frontal" element={<LegacyStructureRedirect />} />
            <Route path="estructura-frontal/:groupId" element={<LegacyStructureRedirect />} />
            <Route path="grupo-frontal-pastoral" element={<Navigate to="/grupo-frontal" replace />} />
            <Route path="mis-estadisticas" element={<MisEstadisticasPage />} />
            {/* Reporte de invasión: el backend decide si es completo, personal o sin acceso. */}
            <Route path="invasiones/reporte-pastora" element={<PresentReportLauncherPage />} />
            <Route path="invasiones/:campaignId/reporte" element={<InvasionReportPage />} />
            <Route path="invasiones/asistencia" element={<InvasionAttendancePage />} />
            <Route path="invasiones/:campaignId/asistencia" element={<InvasionAttendancePage />} />
            <Route path="invasiones/:campaignId/programa" element={<InvasionProgramPage />} />
            <Route path="invasiones/:campaignId/ayuda" element={<InvasionHelpPage />} />
            <Route path="invasiones/:campaignId/radio" element={<RadioPage />} />
            
            {/* Persona routes */}
            <Route path="mi-progreso" element={<Navigate to="/procesos/dashboard" replace />} />
            <Route path="mi-semana/:weekNum" element={<Navigate to="/procesos/7-semanas" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        </Suspense>
        <Toaster position="top-right" richColors />
      </Router>
    </AuthProvider>
  );
}

export default App;
