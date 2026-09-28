import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ScanLine } from 'lucide-react';

/** Acceso rápido al escáner visible en cualquier pantalla de Librería 360.
 * Solo navega a /libreria/escanear — el backend sigue validando el RBAC de
 * cada acción (entregar/transferir/recibir/etc.), este botón no otorga
 * permisos adicionales. */
export const FloatingLibraryScanButton = () => {
  const location = useLocation();
  const navigate = useNavigate();
  if (!location.pathname.startsWith('/libreria') || location.pathname === '/libreria/escanear') return null;
  return <button type="button" onClick={() => navigate('/libreria/escanear')}
    className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-[#132443] text-white shadow-lg transition-transform hover:scale-105"
    data-testid="floating-library-scan-button" title="Escanear">
    <ScanLine className="h-6 w-6" />
  </button>;
};
