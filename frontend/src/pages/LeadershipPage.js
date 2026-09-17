import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Award, Settings2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { EligibilityPanel } from '../components/leadership/EligibilityPanel';
import { LeadershipRequirementDialog } from '../components/leadership/LeadershipRequirementDialog';
import { LeadershipRequirementRow } from '../components/leadership/LeadershipRequirementRow';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

export default function LeadershipPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const [data, setData] = useState({ people: [], groups: [], requirements: [], dashboard: {} });
  const [personId, setPersonId] = useState('');
  const [groupId, setGroupId] = useState('');
  const [eligibility, setEligibility] = useState(null);
  const canManage = user?.rol === 'pastor' || (user?.capabilities || []).includes('leadership.requirements.manage');
  const load = useCallback(async () => {
    const [people, groups, requirements, dashboard] = await Promise.all([
      axios.get(`${API}/api/core/persons?limit=500`, getAuthHeaders()),
      axios.get(`${API}/api/front-groups`, getAuthHeaders()),
      axios.get(`${API}/api/leadership/requirements`, getAuthHeaders()),
      axios.get(`${API}/api/leadership/dashboard`, getAuthHeaders()),
    ]);
    setData({ people: people.data.items || [], groups: groups.data.items || [], requirements: requirements.data.items || [], dashboard: dashboard.data });
  }, [API, getAuthHeaders]);
  useEffect(() => { load().catch(() => toast.error('No se pudo cargar Liderazgo')); }, [load]);
  const evaluate = useCallback(async () => {
    if (!personId) return setEligibility(null);
    const query = groupId ? `?front_group_id=${groupId}` : '';
    const response = await axios.get(`${API}/api/leadership/candidates/${personId}/eligibility${query}`, getAuthHeaders());
    setEligibility(response.data);
  }, [API, getAuthHeaders, groupId, personId]);
  useEffect(() => { evaluate().catch(() => setEligibility(null)); }, [evaluate]);
  return <div className="min-h-screen bg-slate-50" data-testid="leadership-page">
    <header className="border-b border-emerald-950 bg-emerald-950 px-4 py-8 text-white sm:px-8"><div className="mx-auto max-w-7xl"><p className="font-mono text-xs font-semibold uppercase text-amber-300">Autoridad humana · scope ministerial</p><h1 className="font-['Spectral'] text-4xl font-semibold">Ruta de Liderazgo</h1><p className="mt-2 max-w-3xl text-sm text-emerald-100">Evalúe requisitos configurables, conserve el snapshot de decisión y promueva sin modificar el rol administrativo del software.</p></div></header>
    <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-8 xl:grid-cols-[1fr_420px]">
      <section className="space-y-6"><div className="grid gap-3 sm:grid-cols-2"><article className="border bg-white p-4"><Award className="h-5 w-5 text-amber-600" /><strong className="mt-4 block text-3xl">{data.dashboard.leaders_total || 0}</strong><span className="text-xs text-slate-500">Líderes ministeriales</span></article><article className="border bg-white p-4"><ShieldCheck className="h-5 w-5 text-emerald-700" /><strong className="mt-4 block text-3xl">{data.dashboard.promotions_total || 0}</strong><span className="text-xs text-slate-500">Promociones auditadas</span></article></div>
        <div className="border bg-white p-5"><h2 className="font-['Spectral'] text-2xl font-semibold">Evaluar candidato</h2><div className="mt-4 grid gap-3 sm:grid-cols-2"><Select value={personId} onValueChange={setPersonId}><SelectTrigger data-testid="leadership-candidate-select"><SelectValue placeholder="Seleccionar Persona" /></SelectTrigger><SelectContent className="max-h-64 bg-white">{data.people.map((person) => <SelectItem key={person.person_id} value={person.person_id}>{person.nombre} {person.apellido}</SelectItem>)}</SelectContent></Select><Select value={groupId || 'global'} onValueChange={(value) => setGroupId(value === 'global' ? '' : value)}><SelectTrigger data-testid="leadership-front-group-select"><SelectValue placeholder="Ámbito" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="global">Autoridad pastoral global</SelectItem>{data.groups.map((group) => <SelectItem key={group.front_group_id} value={group.front_group_id}>{group.name}</SelectItem>)}</SelectContent></Select></div></div>
        <div className="border bg-white p-5"><EligibilityPanel eligibility={eligibility} frontGroupId={groupId} onUpdated={evaluate} /></div>
      </section>
      <aside className="space-y-5"><section className="border bg-white p-5"><div className="flex items-center justify-between gap-3"><h2 className="flex items-center gap-2 font-['Spectral'] text-2xl font-semibold"><Settings2 className="h-5 w-5" />Requisitos</h2>{canManage && <LeadershipRequirementDialog onCreated={load} />}</div><div className="mt-4 space-y-2">{data.requirements.map((item) => <LeadershipRequirementRow key={item.requirement_id} item={item} canManage={canManage} onUpdated={load} />)}</div></section><section className="border bg-white p-5"><h2 className="font-['Spectral'] text-2xl font-semibold">Promociones recientes</h2><div className="mt-4 space-y-3">{data.dashboard.promotions?.map((item) => <article key={item.promotion_id} className="border-l-2 border-emerald-600 pl-3 text-sm"><b>{item.person_name_snapshot}</b><p className="text-xs text-slate-500">{new Date(item.approved_at).toLocaleString('es-US')} · {item.approved_by_role}</p></article>)}</div></section></aside>
    </main>
  </div>;
}