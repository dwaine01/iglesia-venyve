import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Network, UsersRound } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { FrontGroupDialog } from '../components/front-groups/FrontGroupDialog';
import { FrontGroupDetailPanel } from '../components/front-groups/FrontGroupDetailPanel';

export default function FrontGroupsPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const [groups, setGroups] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { const response = await axios.get(`${API}/api/front-groups`, getAuthHeaders()); setGroups(response.data.items || []); setSelected((current) => current || response.data.items?.[0] || null); setError(''); }
    catch (requestError) { setError(requestError?.response?.data?.detail || 'No se pudieron cargar los Grupos Frontales'); }
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  const canManage = user?.rol === 'pastor' || (user?.capabilities || []).includes('front_groups.manage');
  return <div className="min-h-screen bg-slate-50" data-testid="front-groups-page"><header className="border-b border-slate-800 bg-slate-900 px-4 py-8 text-white sm:px-8"><div className="mx-auto flex max-w-7xl flex-wrap items-end justify-between gap-5"><div><p className="font-mono text-xs font-semibold uppercase text-amber-400">Estructura ministerial propia</p><h1 className="font-['Spectral'] text-4xl font-semibold">Grupos Frontales</h1><p className="mt-2 max-w-2xl text-sm text-slate-300">Organización, equipo, mentores, procesos y autoridad scoped sin confundirse con Redes, Puertas, Ministerios o Células.</p></div>{canManage && <FrontGroupDialog onCreated={load} />}</div></header><main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-8 lg:grid-cols-[300px_1fr]">{error ? <div className="border border-red-200 bg-red-50 p-4 text-red-700" data-testid="front-group-error-alert">{error}</div> : <><aside className="space-y-2"><h2 className="mb-4 flex items-center gap-2 font-semibold"><Network className="h-4 w-4" />Catálogo</h2>{groups.map((group) => <button key={group.front_group_id} onClick={() => setSelected(group)} className={`w-full border p-3 text-left ${selected?.front_group_id === group.front_group_id ? 'border-amber-500 bg-amber-50' : 'border-slate-200 bg-white'}`} data-testid={`front-group-select-${group.front_group_id}`}><b className="block">{group.name}</b><span className="text-xs text-slate-500"><UsersRound className="mr-1 inline h-3 w-3" />{group.team_count || 0} personas · {group.active_process_count || 0} procesos</span></button>)}{!groups.length && <div className="border border-dashed p-6 text-center text-sm text-slate-500">Cree el primer Grupo Frontal.</div>}</aside><section className="border border-slate-200 bg-white p-5 sm:p-7">{selected ? <FrontGroupDetailPanel group={selected} canManage={canManage} onUpdated={load} /> : <p className="text-sm text-slate-500">Seleccione un Grupo Frontal.</p>}</section></>}</main></div>;
}