import React from 'react';
import { Link } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { Button } from './ui/button';

// ETAPA 5A: una URL escrita a mano sin permiso muestra este mensaje — nunca
// el contenido del módulo. Nunca redirige en silencio.
export default function AccessDeniedPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-[#F8F6F0] px-6 text-center" data-testid="access-denied-page">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#101D36]/10 text-[#101D36]"><Lock className="h-6 w-6" /></div>
      <h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]" data-testid="access-denied-title">No tienes acceso</h1>
      <p className="max-w-sm text-sm text-slate-500">Esta cuenta no tiene asignado este módulo. Si crees que deberías verlo, pide a tu pastor o coordinador que te lo habilite desde Gestión de accesos.</p>
      <Button asChild className="mt-2 bg-[#101D36]"><Link to="/" data-testid="access-denied-home-link">Volver al panel principal</Link></Button>
    </div>
  );
}
