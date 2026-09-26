import React, { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import DashboardGeneralPage from './pages/DashboardGeneralPage';
import MiProgresoPage from './pages/MiProgresoPage';
import IntroduccionPage from './pages/IntroduccionPage';
import MapaPage from './pages/MapaPage';
import SemanaPage from './pages/SemanaPage';
import RegistroPage from './pages/RegistroPage';
import EstadisticasPage from './pages/EstadisticasPage';
import PersonasListPage from './pages/PersonasListPage';
import PersonaNuevaPage from './pages/PersonaNuevaPage';
import PersonaPerfilPage from './pages/PersonaPerfilPage';
import MembershipImportPage from './pages/MembershipImportPage';
import OperationsDashboardPage from './pages/operations/OperationsDashboardPage';
import PastoralDashboardPage from './pages/pastoral/PastoralDashboardPage';
import PastoralCasesInboxPage from './pages/pastoral/PastoralCasesInboxPage';
import PastoralExpedienteDetailPage from './pages/pastoral/PastoralExpedienteDetailPage';
import Operacion72DashboardPage from './pages/pastoral/Operacion72DashboardPage';
import PastoralVisitsPage from './pages/pastoral/PastoralVisitsPage';
import OperationsEventsPage from './pages/operations/OperationsEventsPage';
import OperationEventDetailPage from './pages/operations/OperationEventDetailPage';
import OperationOccurrencePage from './pages/operations/OperationOccurrencePage';
import OperationCheckInPage from './pages/operations/OperationCheckInPage';
import MinisteriosPage from './pages/MinisteriosPage';
import MinisterioDetailPage from './pages/MinisterioDetailPage';
import DirectorioTalentosPage from './pages/DirectorioTalentosPage';
import BitacoraPage from './pages/BitacoraPage';
import PresentacionHomePage from './pages/PresentacionHomePage';
import PresentacionPresenterPage from './pages/PresentacionPresenterPage';
import PresentacionAudiencePage from './pages/PresentacionAudiencePage';
import PresentacionJoinPage from './pages/PresentacionJoinPage';
import PresentacionImprimirPage from './pages/PresentacionImprimirPage';
import PresentacionNotasPage from './pages/PresentacionNotasPage';
import CodigosInvitacionPage from './pages/CodigosInvitacionPage';
import CoreGovernancePage from './pages/CoreGovernancePage';
import FormationAdminPage from './pages/formation/FormationAdminPage';
import FormationCohortPage from './pages/formation/FormationCohortPage';
import ChangePasswordPage from './pages/ChangePasswordPage';
import AccessOnboardingPage from './pages/AccessOnboardingPage';
import MembershipVerificationPage from './pages/MembershipVerificationPage';
import BaptismVerificationPage from './pages/BaptismVerificationPage';
import BaptismEventsPage from './pages/BaptismEventsPage';
import FinanceDashboardPage from './pages/finance/FinanceDashboardPage';
import FinanceSetupPage from './pages/finance/FinanceSetupPage';
import FinanceJournalsPage from './pages/finance/FinanceJournalsPage';
import FinanceContributionsPage from './pages/finance/FinanceContributionsPage';
import FinanceContributorsPage from './pages/finance/FinanceContributorsPage';
import FinanceOperationsPage from './pages/finance/FinanceOperationsPage';
import FinanceReconciliationPage from './pages/finance/FinanceReconciliationPage';
import FinanceReportsPage from './pages/finance/FinanceReportsPage';
import FinanceIntegrationsPage from './pages/finance/FinanceIntegrationsPage';
import ProcessesDashboardPage from './pages/processes/ProcessesDashboardPage';
import SevenWeeksPage from './pages/processes/SevenWeeksPage';
import SevenWeeksDetailPage from './pages/processes/SevenWeeksDetailPage';
import ConsolidationPage from './pages/processes/ConsolidationPage';
import ConsolidationDetailPage from './pages/processes/ConsolidationDetailPage';
import DiscipleshipPage from './pages/processes/DiscipleshipPage';
import FrontGroupsPage from './pages/FrontGroupsPage';
import LeadershipPage from './pages/LeadershipPage';
import MentorshipPage from './pages/processes/MentorshipPage';
import CapPage from './pages/processes/CapPage';
import CellularDashboardPage from './pages/cellular/CellularDashboardPage';
import CellularNetworksPage from './pages/cellular/CellularNetworksPage';
import CellularListPage from './pages/cellular/CellularListPage';
import CellularDetailPage from './pages/cellular/CellularDetailPage';
import CellularMeetingMobilePage from './pages/cellular/CellularMeetingMobilePage';
import CellularReadyPage from './pages/cellular/CellularReadyPage';
import CellularNeedsPage from './pages/cellular/CellularNeedsPage';
import CellularHealthPage from './pages/cellular/CellularHealthPage';
import DoorsDashboardPage from './pages/doors/DoorsDashboardPage';
import DoorCasesPage from './pages/doors/DoorCasesPage';
import DoorDetailPage from './pages/doors/DoorDetailPage';
import BoardDashboardPage from './pages/board/BoardDashboardPage';
import BoardMembersPage from './pages/board/BoardMembersPage';
import BoardMeetingsPage from './pages/board/BoardMeetingsPage';
import BoardMeetingDetailPage from './pages/board/BoardMeetingDetailPage';
import BoardMinutesPage from './pages/board/BoardMinutesPage';
import AppLayout from './components/AppLayout';
import { canManageDirectMembership, canManageBaptismEvents, canViewCare, canViewFinanceModule, canViewFormation, canViewFrontGroups, canViewGeo, canViewLeadership, canViewOperations, hasAnyCapability, isPastoralAuthority } from './lib/accessControl';
import { useBoardAccess } from './hooks/useBoardAccess';
import './App.css';

const GeoMapsPage = lazy(() => import('./pages/GeoMapsPage'));

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
  if (!isPastoralAuthority(user)) return <Navigate to="/" />;
  return children;
}

// Para pastores y líderes
function StaffRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="text-lg text-muted-foreground">Cargando...</div></div>;
  if (!user) return <Navigate to="/login" />;
  if (!isPastoralAuthority(user) && user.rol !== 'lider') return <Navigate to="/" />;
  return children;
}

function AccessManagerRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex min-h-screen items-center justify-center">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!hasAnyCapability(user, ['core.access.manage'])) return <Navigate to="/" replace />;
  return children;
}

function FinanceRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex min-h-screen items-center justify-center">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!canViewFinanceModule(user)) return <Navigate to="/" replace />;
  return children;
}

function FormationRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex min-h-screen items-center justify-center" data-testid="formation-route-loading">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!canViewFormation(user)) return <Navigate to="/" replace />;
  return children;
}

function CapabilityRoute({ children, allowed }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex min-h-screen items-center justify-center" data-testid="capability-route-loading">Cargando…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!allowed(user)) return <Navigate to="/" replace />;
  return children;
}

function BoardAccessRoute({ children }) {
  const { user } = useAuth();
  const access = useBoardAccess();
  if (!user || access.loading) return <div className="flex min-h-screen items-center justify-center" data-testid="board-access-loading">Cargando…</div>;
  if (!access.allowed) return <Navigate to="/" replace />;
  return children;
}

// Redirect to correct dashboard based on role
function RoleDashboard() {
  const { user } = useAuth();
  if (isPastoralAuthority(user)) return <Navigate to="/dashboard-general" />;
  if (user?.rol === 'persona') return <Navigate to="/procesos/dashboard" />;
  return <ProcessesDashboardPage />;
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/cambiar-clave" element={<ChangePasswordPage />} />
          <Route path="/acuerdo-confidencialidad" element={<AccessOnboardingPage />} />
          <Route path="/verificar/carnet/:token" element={<MembershipVerificationPage />} />
          <Route path="/verificar/bautismo/:token" element={<BaptismVerificationPage />} />
          {/* Rutas de presentación full-screen (fuera del AppLayout) */}
          <Route path="/presentacion/presenter" element={<StaffRoute><PresentacionPresenterPage /></StaffRoute>} />
          <Route path="/presentacion/audiencia/:code" element={<PresentacionAudiencePage />} />
          <Route path="/presentacion/notas/:code" element={<PresentacionNotasPage />} />
          <Route path="/presentacion/unirse" element={<PresentacionJoinPage />} />
          <Route path="/presentacion/imprimir" element={<PresentacionImprimirPage />} />
          <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route index element={<RoleDashboard />} />
            
            {/* Pastor routes */}
            <Route path="dashboard-general" element={<DashboardGeneralPage />} />
            <Route path="nucleo" element={<AccessManagerRoute><CoreGovernancePage /></AccessManagerRoute>} />
            <Route path="procesos/dashboard" element={<ProcessesDashboardPage />} />
            <Route path="procesos/7-semanas" element={<SevenWeeksPage />} />
            <Route path="procesos/7-semanas/:enrollmentId" element={<SevenWeeksDetailPage />} />
            <Route path="procesos/consolidacion" element={<ConsolidationPage />} />
            <Route path="procesos/consolidacion/:enrollmentId" element={<ConsolidationDetailPage />} />
            <Route path="procesos/discipulado" element={<DiscipleshipPage />} />
            <Route path="formacion" element={<FormationRoute><FormationAdminPage /></FormationRoute>} />
            <Route path="formacion/cohortes/:cohortId" element={<FormationRoute><FormationCohortPage /></FormationRoute>} />
            <Route path="grupos-frontales" element={<CapabilityRoute allowed={canViewFrontGroups}><FrontGroupsPage /></CapabilityRoute>} />
            <Route path="liderazgo" element={<CapabilityRoute allowed={canViewLeadership}><LeadershipPage /></CapabilityRoute>} />
            <Route path="mapas" element={<CapabilityRoute allowed={canViewGeo}><Suspense fallback={<div className="flex min-h-[60vh] items-center justify-center" data-testid="geo-page-loading">Cargando Mapa 360…</div>}><GeoMapsPage /></Suspense></CapabilityRoute>} />
            <Route path="procesos/mentoria" element={<MentorshipPage />} />
            <Route path="procesos/cap" element={<CapPage />} />
            <Route path="celulas/dashboard" element={<CellularDashboardPage />} />
            <Route path="celulas/redes" element={<StaffRoute><CellularNetworksPage /></StaffRoute>} />
            <Route path="celulas/lista" element={<CellularListPage />} />
            <Route path="celulas/bandeja-ready" element={<StaffRoute><CellularReadyPage /></StaffRoute>} />
            <Route path="celulas/necesidades" element={<StaffRoute><CellularNeedsPage /></StaffRoute>} />
            <Route path="celulas/salud" element={<CellularHealthPage mode="health" />} />
            <Route path="celulas/multiplicacion" element={<StaffRoute><CellularHealthPage mode="multiplication" /></StaffRoute>} />
            <Route path="celulas/genealogia" element={<CellularHealthPage mode="genealogy" />} />
            <Route path="celulas/:id/reunion-movil" element={<StaffRoute><CellularMeetingMobilePage /></StaffRoute>} />
            <Route path="celulas/:id" element={<CellularDetailPage />} />
            <Route path="puertas/dashboard" element={<StaffRoute><DoorsDashboardPage /></StaffRoute>} />
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
            <Route path="personas" element={<StaffRoute><PersonasListPage /></StaffRoute>} />
            <Route path="personas/nueva" element={<StaffRoute><PersonaNuevaPage /></StaffRoute>} />
            <Route path="personas/importar" element={<CapabilityRoute allowed={canManageDirectMembership}><MembershipImportPage /></CapabilityRoute>} />
            <Route path="bautismos" element={<CapabilityRoute allowed={canManageBaptismEvents}><BaptismEventsPage /></CapabilityRoute>} />
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
            <Route path="personas/:personId" element={<PersonaPerfilPage />} />
            <Route path="directorio" element={<DirectorioTalentosPage />} />
            <Route path="ministerios" element={<MinisteriosPage />} />
            <Route path="ministerios/:ministryId" element={<MinisterioDetailPage />} />
            <Route path="bitacora" element={<StaffRoute><BitacoraPage /></StaffRoute>} />
            <Route path="codigos" element={<StaffRoute><CodigosInvitacionPage /></StaffRoute>} />
            <Route path="estadisticas" element={<EstadisticasPage />} />
            <Route path="presentacion" element={<PresentacionHomePage />} />
            
            {/* Persona routes */}
            <Route path="mi-progreso" element={<Navigate to="/procesos/dashboard" replace />} />
            <Route path="mi-semana/:weekNum" element={<Navigate to="/procesos/7-semanas" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        <Toaster position="top-right" richColors />
      </Router>
    </AuthProvider>
  );
}

export default App;
