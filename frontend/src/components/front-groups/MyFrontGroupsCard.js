import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Crown, Network, Sparkles, TriangleAlert } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { translateTechnicalText } from '../../lib/displayLabels';

const ROLE_LABELS = { leader: 'líder', co_leader: 'colíder' };

// ETAPA 5C: a qué Grupo(s) Frontal(es) pertenece la persona — SOLO nombre,
// líder y colíder (el backend nunca entrega a los demás integrantes). Si la
// pastora la autorizó a formar su grupo, ofrece "Crear mi grupo frontal".
export function MyFrontGroupsCard() {
  const { API, getAuthHeaders, user } = useAuth();
  const [groups, setGroups] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user?.person_id) return;
    axios.get(`${API}/api/core/me/front-groups`, getAuthHeaders())
      .then((response) => setGroups(response.data?.items || []))
      .catch((requestError) => setError(translateTechnicalText(requestError?.response?.data?.detail || 'No se pudieron cargar tus Grupos Frontales.')));
  }, [API, getAuthHeaders, user?.person_id]);

  if (!user?.person_id) return null;
  if (error) return <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>;
  if (!groups) return null;

  return (
    <section className="rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid="mi-perfil-grupos-frontales">
      <h2 className="flex items-center gap-2 font-['Spectral'] text-lg font-semibold text-[#101D36]"><Network className="h-4 w-4 text-[#9A7A2F]" />Mis Grupos Frontales</h2>
      {groups.length ? (
        <ul className="mt-3 grid gap-3 sm:grid-cols-2">
          {groups.map((group) => (
            <li key={group.front_group_id} className={`rounded-lg border p-3 text-sm text-slate-700 ${group.can_create ? 'border-amber-300 bg-amber-50' : 'border-[#EEECE6] bg-[#FBFAF7]'}`} data-testid={`mi-perfil-grupo-${group.front_group_id}`}>
              {group.pastoral_main && <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-[#7A5F22]" data-testid="mi-grupo-pastora-badge"><Crown className="h-3.5 w-3.5" />Perteneces al grupo frontal de la pastora</p>}
              {group.can_create ? (
                <>
                  <b className="block text-[#101D36]">Ahora eres Líder de Grupo Frontal</b>
                  <p className="mt-1 text-xs text-amber-800" data-testid="mi-privilegio-lider">{group.assigned_by_name ? `Asignado por ${group.assigned_by_name}` : 'Te asignaron como líder'}{group.from_group_name ? ` desde ${group.from_group_name}` : ''}. Ya puedes formar tu propio grupo.</p>
                  <Link to={`/mi-grupo-frontal/${group.front_group_id}`} className="mt-3 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-md bg-amber-700 px-3 text-sm font-semibold text-white hover:bg-amber-800" data-testid="crear-mi-grupo-frontal-link"><Sparkles className="h-4 w-4" />Crear mi grupo frontal</Link>
                </>
              ) : (
                <>
                  <b className="block text-[#101D36]">{group.name || 'Grupo Frontal'}</b>
                  {ROLE_LABELS[group.my_role] && <span className="mt-1 inline-block rounded-full bg-[#F3EBD7] px-2 py-0.5 text-xs font-medium text-[#7A5F22]">Eres {ROLE_LABELS[group.my_role]}</span>}
                  {group.from_group_name && <p className="mt-1 text-[11px] text-slate-500">Proviene de: {group.from_group_name}{group.from_pastoral_main ? ' (grupo de la pastora)' : ''}</p>}
                  <dl className="mt-2 space-y-0.5 text-xs text-slate-600">
                    <div><dt className="inline font-medium">Líder: </dt><dd className="inline">{group.leader_name || 'Por definir'}</dd></div>
                    <div><dt className="inline font-medium">Colíder: </dt><dd className="inline">{group.co_leader_name || 'Por definir'}</dd></div>
                  </dl>
                  {group.can_manage && <div className="mt-3 grid grid-cols-2 gap-2">
                    <Link to={`/mi-grupo-frontal/${group.front_group_id}`} className="inline-flex min-h-10 items-center justify-center rounded-md border border-[#D9CFB4] bg-white px-2 text-sm font-semibold text-[#7A5F22] hover:bg-[#FBF6EA]" data-testid={`administrar-grupo-${group.front_group_id}`}>Administrar</Link>
                    <Link to={`/grupo-frontal?grupo=${group.front_group_id}&tab=ramas`} className="inline-flex min-h-10 items-center justify-center rounded-md bg-[#101D36] px-2 text-sm font-semibold text-white" data-testid={`explorar-rama-${group.front_group_id}`}>Mis ramas</Link>
                  </div>}
                </>
              )}
            </li>
          ))}
        </ul>
      ) : <p className="mt-2 text-sm text-slate-400">Aún no perteneces a ningún Grupo Frontal.</p>}
      {groups.length > 0 && <Link to="/grupo-frontal" className="mt-3 inline-flex min-h-11 w-full items-center justify-center rounded-md border border-[#D9CFB4] bg-white text-sm font-semibold text-[#7A5F22]" data-testid="mi-perfil-abrir-grupo-frontal">Abrir Grupo Frontal (mi equipo y mis ramas)</Link>}
    </section>
  );
}
