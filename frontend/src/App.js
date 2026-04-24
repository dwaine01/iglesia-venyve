import React from 'react';
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
import BitacoraPage from './pages/BitacoraPage';
import PresentacionHomePage from './pages/PresentacionHomePage';
import PresentacionPresenterPage from './pages/PresentacionPresenterPage';
import PresentacionAudiencePage from './pages/PresentacionAudiencePage';
import PresentacionJoinPage from './pages/PresentacionJoinPage';
import PresentacionImprimirPage from './pages/PresentacionImprimirPage';
import CodigosInvitacionPage from './pages/CodigosInvitacionPage';
import AppLayout from './components/AppLayout';
import './App.css';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="text-lg text-muted-foreground">Cargando...</div></div>;
  if (!user) return <Navigate to="/login" />;
  return children;
}

// Solo para pastores
function PastorOnlyRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="text-lg text-muted-foreground">Cargando...</div></div>;
  if (!user) return <Navigate to="/login" />;
  if (user.rol !== 'pastor') return <Navigate to="/" />;
  return children;
}

// Para pastores y líderes
function StaffRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="text-lg text-muted-foreground">Cargando...</div></div>;
  if (!user) return <Navigate to="/login" />;
  if (user.rol !== 'pastor' && user.rol !== 'lider') return <Navigate to="/" />;
  return children;
}

// Redirect to correct dashboard based on role
function RoleDashboard() {
  const { user } = useAuth();
  if (user?.rol === 'pastor') return <Navigate to="/dashboard-general" />;
  if (user?.rol === 'persona') return <Navigate to="/mi-progreso" />;
  return <DashboardPage />;
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          {/* Rutas de presentación full-screen (fuera del AppLayout) */}
          <Route path="/presentacion/presenter" element={<StaffRoute><PresentacionPresenterPage /></StaffRoute>} />
          <Route path="/presentacion/audiencia/:code" element={<PresentacionAudiencePage />} />
          <Route path="/presentacion/unirse" element={<PresentacionJoinPage />} />
          <Route path="/presentacion/imprimir" element={<PresentacionImprimirPage />} />
          <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route index element={<RoleDashboard />} />
            
            {/* Pastor routes */}
            <Route path="dashboard-general" element={<DashboardGeneralPage />} />
            <Route path="lider/:liderId/dashboard" element={<DashboardPage />} />
            
            {/* Lider routes */}
            <Route path="introduccion" element={<IntroduccionPage />} />
            <Route path="mapa" element={<MapaPage />} />
            <Route path="semana/:weekNum" element={<SemanaPage />} />
            <Route path="persona/:personId/semana/:weekNum" element={<SemanaPage />} />
            <Route path="registro" element={<StaffRoute><RegistroPage /></StaffRoute>} />
            <Route path="bitacora" element={<StaffRoute><BitacoraPage /></StaffRoute>} />
            <Route path="codigos" element={<StaffRoute><CodigosInvitacionPage /></StaffRoute>} />
            <Route path="estadisticas" element={<EstadisticasPage />} />
            <Route path="presentacion" element={<PresentacionHomePage />} />
            
            {/* Persona routes */}
            <Route path="mi-progreso" element={<MiProgresoPage />} />
            <Route path="mi-semana/:weekNum" element={<SemanaPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        <Toaster position="top-right" richColors />
      </Router>
    </AuthProvider>
  );
}

export default App;
