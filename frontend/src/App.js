import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import RegistroConCodigoPage from './pages/RegistroConCodigoPage';
import DashboardJerarquicoPage from './pages/DashboardJerarquicoPage';
import MiEquipoPage from './pages/MiEquipoPage';
import CodigosInvitacionPage from './pages/CodigosInvitacionPage';
import IntroduccionPage from './pages/IntroduccionPage';
import MapaPage from './pages/MapaPage';
import PresentacionHomePage from './pages/PresentacionHomePage';
import PresentacionPresenterPage from './pages/PresentacionPresenterPage';
import PresentacionAudiencePage from './pages/PresentacionAudiencePage';
import PresentacionJoinPage from './pages/PresentacionJoinPage';
import PresentacionImprimirPage from './pages/PresentacionImprimirPage';
import PresentacionNotasPage from './pages/PresentacionNotasPage';
import AppLayout from './components/AppLayout';
import './App.css';

function Loading() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-[#0B1428]">
      <div className="text-lg text-white/70">Cargando...</div>
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" />;
  return children;
}

/** Bloquea rutas para Discipulo (los que solo consumen contenido). */
function PresenterRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" />;
  if (user.rol === 'discipulo') return <Navigate to="/" />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Publicas */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/registro" element={<RegistroConCodigoPage />} />
          <Route path="/registro/:code" element={<RegistroConCodigoPage />} />

          {/* Presentacion full-screen (fuera del AppLayout) */}
          <Route path="/presentacion/presenter" element={<PresenterRoute><PresentacionPresenterPage /></PresenterRoute>} />
          <Route path="/presentacion/audiencia/:code" element={<PresentacionAudiencePage />} />
          <Route path="/presentacion/notas/:code" element={<PresentacionNotasPage />} />
          <Route path="/presentacion/unirse" element={<PresentacionJoinPage />} />
          <Route path="/presentacion/imprimir" element={<PresentacionImprimirPage />} />

          {/* App protegida */}
          <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route index element={<DashboardJerarquicoPage />} />
            <Route path="equipo" element={<PresenterRoute><MiEquipoPage /></PresenterRoute>} />
            <Route path="equipo/codigos" element={<PresenterRoute><CodigosInvitacionPage /></PresenterRoute>} />
            <Route path="introduccion" element={<IntroduccionPage />} />
            <Route path="mapa" element={<MapaPage />} />
            <Route path="presentacion" element={<PresenterRoute><PresentacionHomePage /></PresenterRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        <Toaster position="top-right" richColors />
      </Router>
    </AuthProvider>
  );
}

export default App;
