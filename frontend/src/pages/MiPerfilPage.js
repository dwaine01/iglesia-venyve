import React from 'react';
import { TriangleAlert } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { MyFrontGroupsCard } from '../components/front-groups/MyFrontGroupsCard';
import PersonaPerfilPage from './PersonaPerfilPage';

// "Mi perfil" — siempre disponible para toda cuenta: muestra la MISMA ficha
// 360 completa (foto, pestañas) más los Grupos Frontales a los que pertenece.
export default function MiPerfilPage() {
  const { user } = useAuth();

  if (!user?.person_id) {
    return (
      <div className="min-h-screen bg-[#F8F6F0] p-4" data-testid="mi-perfil-error">
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><TriangleAlert className="mt-0.5 h-4 w-4" />Esta cuenta no está vinculada a un Perfil 360.</div>
      </div>
    );
  }

  return (
    <div data-testid="mi-perfil-page">
      <PersonaPerfilPage personId={user.person_id} ownProfileExtra={<MyFrontGroupsCard />} />
    </div>
  );
}
