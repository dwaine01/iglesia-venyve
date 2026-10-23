import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Network, TriangleAlert } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { translateTechnicalText } from '../lib/displayLabels';
import PersonaPerfilPage from './PersonaPerfilPage';

const ROLE_LABELS = { leader: 'Líder', co_leader: 'Colíder' };

// "Mi perfil" — siempre disponible para toda cuenta: muestra la MISMA ficha
// 360 completa (foto, pestañas) más los Grupos Frontales a los que pertenece.
function MyFrontGroups({ groups }) {
  return (
    <section className="rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid="mi-perfil-grupos-frontales">
      <h2 className="flex items-center gap-2 font-['Spectral'] text-lg font-semibold text-[#101D36]"><Network className="h-4 w-4 text-[#9A7A2F]" />Mis Grupos Frontales</h2>
      {groups?.length ? (
        <ul className="mt-3 grid gap-3 sm:grid-cols-2">
          {groups.map((group) => (
            <li key={group.front_group_id} className="rounded-lg border border-[#EEECE6] bg-[#FBFAF7] p-3 text-sm text-slate-700" data-testid={`mi-perfil-grupo-${group.front_group_id}`}>
              <b className="block text-[#101D36]">{group.name}</b>
              {ROLE_LABELS[group.my_role] && <span className="mt-1 inline-block rounded-full bg-[#F3EBD7] px-2 py-0.5 text-xs font-medium text-[#7A5F22]">Eres {ROLE_LABELS[group.my_role].toLowerCase()}</span>}
              <dl className="mt-2 space-y-0.5 text-xs text-slate-600">
                <div><dt className="inline font-medium">Líder: </dt><dd className="inline">{group.leader_name || 'Por definir'}</dd></div>
                <div><dt className="inline font-medium">Colíder: </dt><dd className="inline">{group.co_leader_name || 'Por definir'}</dd></div>
              </dl>
            </li>
          ))}
        </ul>
      ) : <p className="mt-2 text-sm text-slate-400">Aún no perteneces a ningún Grupo Frontal.</p>}
    </section>
  );
}

export default function MiPerfilPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const [groups, setGroups] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user?.person_id) return;
    axios.get(`${API}/api/core/me/profile`, getAuthHeaders())
      .then((response) => setGroups(response.data?.front_groups || []))
      .catch((requestError) => setError(translateTechnicalText(requestError?.response?.data?.detail || 'No se pudieron cargar tus Grupos Frontales.')));
  }, [API, getAuthHeaders, user?.person_id]);

  if (!user?.person_id) {
    return (
      <div className="min-h-screen bg-[#F8F6F0] p-4" data-testid="mi-perfil-error">
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><TriangleAlert className="mt-0.5 h-4 w-4" />Esta cuenta no está vinculada a un Perfil 360.</div>
      </div>
    );
  }

  const extra = error
    ? <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4" />{error}</div>
    : groups && <MyFrontGroups groups={groups} />;

  return (
    <div data-testid="mi-perfil-page">
      <PersonaPerfilPage personId={user.person_id} ownProfileExtra={extra} />
    </div>
  );
}
