import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BadgeCheck, Loader2, Power, UserCog, UsersRound } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { apiErrorMessage } from '../../lib/apiErrors';

export const FrontGroupDetailPanel = ({ group, canManage, onUpdated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [detail, setDetail] = useState(null);
  const [people, setPeople] = useState([]);
  const [personId, setPersonId] = useState('');
  const [role, setRole] = useState('team');
  const [reason, setReason] = useState('Asignación pastoral');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const load = async () => {
    const requests = [axios.get(`${API}/api/front-groups/${group.front_group_id}`, getAuthHeaders())];
    if (canManage) requests.push(axios.get(`${API}/api/core/persons?limit=100`, getAuthHeaders()));
    const [groupResponse, peopleResponse] = await Promise.all(requests);
    setDetail(groupResponse.data); setPeople(peopleResponse?.data?.items || []); setError('');
  };
  useEffect(() => { load().catch((requestError) => { setDetail(null); setError(apiErrorMessage(requestError, 'No se pudo cargar el Grupo Frontal')); }); }, [group.front_group_id, canManage]); // eslint-disable-line react-hooks/exhaustive-deps
  const act = async (key, request) => {
    setBusy(key);
    try { await request(); toast.success('Grupo Frontal actualizado'); setPersonId(''); await load(); await onUpdated(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo actualizar el Grupo Frontal')); }
    finally { setBusy(''); }
  };
  if (error) return <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-700" data-testid="front-group-detail-error-alert">{error}</div>;
  if (!detail) return <div className="flex min-h-64 items-center justify-center" data-testid="front-group-detail-loading"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  return <section className="space-y-6" data-testid="front-group-detail-panel"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-[10px] font-semibold uppercase text-amber-700">Grupo Frontal · {detail.status}</p><h2 className="font-['Spectral'] text-3xl font-semibold">{detail.name}</h2><p className="mt-1 text-sm text-slate-500">{detail.description || 'Sin descripción'}</p></div>{canManage && <Button variant="outline" onClick={() => act('status', () => axios.put(`${API}/api/front-groups/${group.front_group_id}`, { status: detail.status === 'active' ? 'inactive' : 'active' }, getAuthHeaders()))} data-testid="front-group-status-button"><Power className="h-4 w-4" />{detail.status === 'active' ? 'Desactivar' : 'Activar'}</Button>}</div><div className="grid gap-3 sm:grid-cols-3"><article className="border p-4"><strong className="text-2xl">{detail.stats?.people_reached || 0}</strong><span className="block text-xs text-slate-500">Personas alcanzadas</span></article><article className="border p-4"><strong className="text-2xl">{detail.stats?.active_processes || 0}</strong><span className="block text-xs text-slate-500">Consolidaciones activas</span></article><article className="border p-4"><strong className="text-2xl">{detail.stats?.leaders_promoted || 0}</strong><span className="block text-xs text-slate-500">Líderes promovidos</span></article></div><div className="grid gap-5 xl:grid-cols-2"><article className="border p-4"><h3 className="flex items-center gap-2 font-semibold"><UsersRound className="h-4 w-4" />Equipo e historial</h3><div className="mt-4 max-h-72 space-y-2 overflow-y-auto">{detail.assignments?.map((item) => <div key={item.assignment_id} className="flex justify-between border-b py-2 text-sm"><span>{item.person_name || item.person_id}<small className="block text-slate-500">{item.role} · {item.notes}</small></span><b>{item.active ? 'Activo' : 'Histórico'}</b></div>)}</div></article>{canManage && <article className="space-y-3 border p-4"><h3 className="flex items-center gap-2 font-semibold"><UserCog className="h-4 w-4" />Asignar estructura</h3><div className="space-y-2"><Label>Persona</Label><Select value={personId} onValueChange={setPersonId}><SelectTrigger data-testid="front-group-person-select"><SelectValue placeholder="Seleccionar Persona" /></SelectTrigger><SelectContent className="max-h-64 bg-white">{people.map((person) => <SelectItem key={person.person_id} value={person.person_id}>{person.nombre} {person.apellido}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label>Rol</Label><Select value={role} onValueChange={setRole}><SelectTrigger data-testid="front-group-role-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="team">Equipo</SelectItem><SelectItem value="mentor">Mentor</SelectItem><SelectItem value="leader">Líder principal</SelectItem></SelectContent></Select></div><Input value={reason} onChange={(event) => setReason(event.target.value)} data-testid="front-group-assignment-reason-input" /><Button disabled={!personId || Boolean(busy)} onClick={() => act('assign', () => role === 'leader' ? axios.post(`${API}/api/front-groups/${group.front_group_id}/leader`, { person_id: personId, reason }, getAuthHeaders()) : axios.post(`${API}/api/front-groups/${group.front_group_id}/members`, { person_id: personId, role, notes: reason }, getAuthHeaders()))} data-testid="front-group-assign-button"><BadgeCheck className="h-4 w-4" />Asignar</Button>{role === 'mentor' && <Button variant="outline" disabled={!personId || Boolean(busy)} onClick={() => act('qualify', () => axios.put(`${API}/api/front-groups/mentors/${personId}/qualification`, { front_group_id: group.front_group_id, can_teach_lbs: true, notes: reason }, getAuthHeaders()))} data-testid="qualify-lbs-mentor-button">Autorizar para LBS</Button>}</article>}</div></section>;
};