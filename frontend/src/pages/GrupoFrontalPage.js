import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { BarChart3, ChevronDown, ChevronRight, GitBranch, Loader2, Network, Pencil, Settings2, Sparkles, TriangleAlert, Users } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { isGeneralCoordinator, isPastoralAuthority } from '../lib/accessControl';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { GroupActivityPanel } from '../components/front-groups/GroupActivityPanel';
import { GroupStatsPanel } from '../components/front-groups/GroupStatsPanel';
import { FrontGroupDetailPanel } from '../components/front-groups/FrontGroupDetailPanel';
import { FrontGroupDialog } from '../components/front-groups/FrontGroupDialog';
import { GroupRosterEditor, rosterToEntries } from '../components/front-groups/GroupRosterEditor';
import { GroupRosterView } from '../components/front-groups/GroupRosterView';
import { PersonQuickPicker } from '../components/front-groups/PersonQuickPicker';
import { LeaderWorkDetail } from '../components/LeaderWorkDetail';

/* Grupo Frontal (un solo botón de menú). Es un ÁRBOL: la pastora → sus equipos
 * (líder + colíder) → el grupo de cada líder → sus integrantes → … hacia abajo.
 * Pestañas: «Mi grupo» (resumen, equipos, impacto, ranking), «Mis ramas» (árbol
 * expandible) y «Administrar». El backend decide qué ramas ve cada quien. */

const TABS = [['mi-grupo', 'Mi grupo', Users], ['ramas', 'Mis ramas', GitBranch], ['administrar', 'Administrar', Settings2]];
const plural = (count, one, many) => `${count ?? 0} ${count === 1 ? one : many}`;
const teamNames = (team) => team.people.map((item) => item.name).join(' y ');

function WorkDialog({ person, onClose }) {
  return (
    <Dialog open={Boolean(person)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="max-h-[90vh] overflow-y-auto bg-white sm:max-w-4xl" data-testid="branch-work-dialog">
        <DialogHeader><DialogTitle>Trabajo de {person?.name}</DialogTitle><DialogDescription>Hoy, esta semana y total: viviendas, personas, libros, Consolidación y pendientes.</DialogDescription></DialogHeader>
        {person && <LeaderWorkDetail mentorPersonId={person.person_id} />}
      </DialogContent>
    </Dialog>
  );
}

/** Un nivel del árbol: el grupo y sus equipos (cada equipo abre su propio grupo). */
function BranchNode({ group, depth, expanded, toggle, onWork, onOpenGroup, onForm }) {
  return (
    <div className={depth ? 'border-l-2 border-[#E8DCC0] pl-3 sm:pl-4' : ''} data-testid={`branch-node-${group.front_group_id}`}>
      <div className="rounded-xl border border-[#E8E5DE] bg-white p-3 shadow-sm">
        <p className="font-['Spectral'] text-lg font-semibold text-[#101D36]">{group.name}</p>
        <p className="text-[15px] text-slate-700">Líder: {group.leader?.name || 'Por definir'} · Colíder: {group.co_leader?.name || 'Por definir'}</p>
        <p className="mt-1 text-[15px] text-[#132443]" data-testid="branch-node-totals">{plural(group.people_branch, 'persona', 'personas')} en toda la rama · {plural(group.teams_total, 'equipo', 'equipos')} · {plural(group.groups_formed, 'grupo formado', 'grupos formados')}{group.progress != null ? ` · Avance de la rama: ${group.progress} %` : ''}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {group.leader && <button type="button" onClick={() => onWork(group.leader)} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg border border-[#D9D4C7] bg-white px-3 text-[15px] font-semibold text-[#101D36]" data-testid="branch-work"><BarChart3 className="h-4 w-4" />Ver el trabajo del líder</button>}
          {depth > 0 && <button type="button" onClick={() => onOpenGroup(group.front_group_id)} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg bg-[#101D36] px-3 text-[15px] font-semibold text-white" data-testid="branch-open">Abrir este grupo</button>}
        </div>
      </div>
      {group.teams.length > 0 && <ul className="mt-2 space-y-2">
        {group.teams.map((team) => {
          const key = `${group.front_group_id}:${team.key}`;
          const open = expanded.has(key);
          return (
            <li key={key} data-testid={`branch-team-${team.status}`}>
              <div className="rounded-xl border border-[#EEECE6] bg-[#FBFAF7] p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold text-[#101D36]">Equipo: {teamNames(team)}</p>
                    <p className="text-sm text-slate-600">Líder: {team.leader?.name || 'Por definir'}{team.co_leader ? ` · Colíder: ${team.co_leader.name}` : ''}</p>
                    {team.status === 'formed'
                      ? <p className="text-sm text-[#132443]">Su grupo: {team.group.name} · {plural(team.group.people_branch, 'persona', 'personas')}{team.group.progress != null ? ` · Avance: ${team.group.progress} %` : ''}</p>
                      : <p className="text-sm font-semibold text-amber-800" data-testid="branch-not-formed">Todavía no ha formado su grupo</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {team.leader && <button type="button" onClick={() => onWork(team.leader)} className="inline-flex min-h-11 items-center gap-1 rounded-lg border border-[#D9D4C7] bg-white px-3 text-sm font-semibold text-[#101D36]">Ver el trabajo del líder</button>}
                    {team.status !== 'formed' && team.can_form && <button type="button" onClick={() => onForm(group, team)} className="inline-flex min-h-11 items-center gap-1 rounded-lg bg-amber-700 px-3 text-sm font-semibold text-white" data-testid="branch-form"><Sparkles className="h-4 w-4" />Formar grupo</button>}
                    {team.status === 'formed' && <button type="button" onClick={() => toggle(key)} aria-expanded={open} className="inline-flex min-h-11 items-center gap-1 rounded-lg bg-[#101D36] px-3 text-sm font-semibold text-white" data-testid="branch-expand">{open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}{open ? 'Ocultar su rama' : 'Ver su rama'}</button>}
                  </div>
                </div>
              </div>
              {open && team.group && <div className="mt-2"><BranchNode group={team.group} depth={depth + 1} expanded={expanded} toggle={toggle} onWork={onWork} onOpenGroup={onOpenGroup} onForm={onForm} /></div>}
            </li>
          );
        })}
      </ul>}
      {group.individuals.length > 0 && <p className="mt-2 text-sm text-slate-600">Integrantes individuales: {group.individuals.map((item) => item.name).join(', ')}</p>}
      {group.teams.length === 0 && group.individuals.length === 0 && <p className="mt-2 text-sm text-slate-500">Este grupo todavía no tiene integrantes.</p>}
    </div>
  );
}

function BranchTree({ groupId, onOpenGroup, reloadKey }) {
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(new Set());
  const [work, setWork] = useState(null);
  useEffect(() => {
    setData(null); setError('');
    axios.get(`${API}/api/front-group-structure/tree`, { ...getAuthHeaders(), params: groupId ? { root: groupId } : {} })
      .then((response) => setData(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar el árbol')));
  }, [API, getAuthHeaders, groupId, reloadKey]);
  const toggle = (key) => setExpanded((current) => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  const form = async (parent, team) => {
    if (team.pending_group_id) { navigate(`/mi-grupo-frontal/${team.pending_group_id}?formar=1`); return; }
    try {
      const response = await axios.post(`${API}/api/front-group-structure/form`, { parent_group_id: parent.front_group_id, person_ids: team.people.map((item) => item.person_id) }, getAuthHeaders());
      navigate(`/mi-grupo-frontal/${response.data.front_group_id}?formar=1`);
    } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo formar el grupo')); }
  };
  if (error) return <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</p>;
  if (!data) return <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />;
  return (
    <section className="space-y-3" data-testid="branch-tree">
      <p className="text-[15px] text-slate-700">Cada equipo (líder y colíder) abre su propio Grupo Frontal con otros integrantes. Toca «Ver su rama» para bajar un nivel. Las personas de cada rama se cuentan una sola vez. Avance = el mismo indicador del resumen del grupo ({data.period?.label || 'este mes'}).</p>
      {data.direct_leader && <p className="text-sm text-[#7A5F22]" data-testid="branch-direct-leader">Tu líder directo: {data.direct_leader.name}</p>}
      <BranchNode group={data.root} depth={0} expanded={expanded} toggle={toggle} onWork={setWork} onOpenGroup={onOpenGroup} onForm={form} />
      <WorkDialog person={work} onClose={() => setWork(null)} />
    </section>
  );
}

/** Administrar: lista (equipos y líderes), colíder, nombre y las herramientas del módulo (trabajo, integrantes, células, historial, archivar). */
function AdminGroup({ group, onChanged }) {
  const { API, getAuthHeaders, user } = useAuth();
  const [detail, setDetail] = useState(null);
  const [roster, setRoster] = useState(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(group.name || '');
  const [changingCoLeader, setChangingCoLeader] = useState(false);
  const [allGroups, setAllGroups] = useState([]);
  const load = useCallback(async () => {
    const [detailResponse, rosterResponse] = await Promise.all([
      axios.get(`${API}/api/front-groups/${group.front_group_id}`, getAuthHeaders()),
      axios.get(`${API}/api/front-groups/${group.front_group_id}/roster`, getAuthHeaders()),
    ]);
    setDetail(detailResponse.data); setRoster(rosterResponse.data);
  }, [API, getAuthHeaders, group.front_group_id]);
  useEffect(() => { load().catch((error) => toast.error(apiErrorMessage(error, 'No se pudo cargar la administración'))); }, [load]);
  useEffect(() => { axios.get(`${API}/api/front-groups`, getAuthHeaders()).then((response) => setAllGroups(response.data.items || [])).catch(() => setAllGroups([])); }, [API, getAuthHeaders]);
  const canManage = detail?.permissions?.manage === true || isPastoralAuthority(user);
  const pastoralMain = group.pastoral_main && isPastoralAuthority(user);
  const saveRoster = async (entries) => {
    try { await axios.put(`${API}/api/front-groups/${group.front_group_id}/roster`, { entries }, getAuthHeaders()); setEditing(false); toast.success('Lista guardada'); await load(); onChanged(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar la lista')); }
  };
  const savePastoral = async (coLeaderId) => {
    try { await axios.put(`${API}/api/pastoral-front-group`, { name: name.trim(), co_leader_person_id: coLeaderId || group.co_leader?.person_id || null }, getAuthHeaders()); setChangingCoLeader(false); toast.success('Grupo guardado'); onChanged(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); }
  };
  const setCoLeader = async (person) => {
    if (pastoralMain) { await savePastoral(person.person_id); return; }
    try { await axios.post(`${API}/api/front-groups/${group.front_group_id}/co-leader`, { person_id: person.person_id, reason: 'Elegido por el líder del grupo' }, getAuthHeaders()); setChangingCoLeader(false); toast.success('Colíder actualizado'); onChanged(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo cambiar el colíder')); }
  };
  if (!detail || !roster) return <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />;
  return (
    <section className="space-y-4" data-testid="group-admin">
      {pastoralMain && <div className="space-y-2 rounded-xl border border-[#E8E5DE] bg-white p-4">
        <Label htmlFor="group-admin-name">Nombre del grupo</Label>
        <div className="flex gap-2"><Input id="group-admin-name" value={name} onChange={(event) => setName(event.target.value)} className="h-11" /><button type="button" onClick={() => savePastoral(null)} disabled={name.trim().length < 2 || name === group.name} className="min-h-11 rounded-lg border border-[#D9D4C7] px-4 text-[15px] font-semibold disabled:opacity-50">Guardar</button></div>
      </div>}
      {canManage && <div className="rounded-xl border border-[#E8E5DE] bg-white p-4">
        {changingCoLeader ? <PersonQuickPicker groupId={group.front_group_id} assign={false} placeholder="Buscar colíder en Persona 360…" onPicked={setCoLeader} />
          : <button type="button" onClick={() => setChangingCoLeader(true)} className="min-h-11 text-[15px] font-semibold text-[#7A5F22] underline" data-testid="group-admin-colider">{group.co_leader ? `Cambiar colíder (ahora: ${group.co_leader.name})` : 'Elegir colíder del grupo'}</button>}
      </div>}
      <div className="space-y-3 rounded-xl border border-[#E8E5DE] bg-white p-4">
        <h3 className="text-base font-semibold text-[#101D36]">Equipos de servicio, líderes e integrantes</h3>
        {editing
          ? <GroupRosterEditor groupId={group.front_group_id} initialEntries={rosterToEntries(roster)} excludedIds={[group.leader?.person_id, group.co_leader?.person_id].filter(Boolean)} onSave={saveRoster} onCancel={() => setEditing(false)} />
          : <>
            {canManage && <button type="button" onClick={() => setEditing(true)} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#101D36] text-[15px] font-semibold text-white" data-testid="group-admin-edit-list"><Pencil className="h-4 w-4" />Agregar personas o crear equipos</button>}
            <GroupRosterView groupId={group.front_group_id} roster={roster} canManage={canManage} onChanged={async () => { await load(); onChanged(); }} title="Equipos registrados y líderes" />
          </>}
      </div>
      <div className="rounded-xl border border-[#E8E5DE] bg-white p-4">
        <h3 className="mb-2 text-base font-semibold text-[#101D36]">Trabajo, integrantes, células, historial y archivar</h3>
        <FrontGroupDetailPanel group={{ front_group_id: group.front_group_id }} groups={allGroups} onUpdated={async () => onChanged()} />
      </div>
    </section>
  );
}

export default function GrupoFrontalPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = TABS.some(([key]) => key === params.get('tab')) ? params.get('tab') : 'mi-grupo';
  const [start, setStart] = useState(null);
  const [node, setNode] = useState(null);
  const [myTeam, setMyTeam] = useState(null);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [moreStats, setMoreStats] = useState(false);
  const groupId = params.get('grupo') || start?.groups?.[0]?.front_group_id || null;
  const setParam = (changes) => { const next = new URLSearchParams(params); Object.entries(changes).forEach(([key, value]) => { if (value) next.set(key, value); else next.delete(key); }); setParams(next); };
  const openGroup = (id) => setParam({ grupo: id, tab: 'mi-grupo' });

  useEffect(() => {
    axios.get(`${API}/api/front-group-structure/start`, getAuthHeaders()).then((response) => setStart(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar el Grupo Frontal')));
  }, [API, getAuthHeaders, reloadKey]);
  useEffect(() => {
    if (!start) return;
    if (!groupId) {
      axios.get(`${API}/api/front-group-structure/tree`, getAuthHeaders()).then((response) => setMyTeam(response.data.my_team || null)).catch(() => setMyTeam(null));
      return;
    }
    setNode(null);
    axios.get(`${API}/api/front-group-structure/groups/${groupId}`, getAuthHeaders()).then((response) => setNode(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo abrir este grupo')));
  }, [API, getAuthHeaders, start, groupId, reloadKey]);

  const formMine = async () => {
    if (myTeam.pending_group_id) { navigate(`/mi-grupo-frontal/${myTeam.pending_group_id}?formar=1`); return; }
    try {
      const response = await axios.post(`${API}/api/front-group-structure/form`, { parent_group_id: myTeam.parent_group_id, person_ids: myTeam.people.map((item) => item.person_id) }, getAuthHeaders());
      navigate(`/mi-grupo-frontal/${response.data.front_group_id}?formar=1`);
    } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo formar el grupo')); }
  };

  const group = node?.group;
  return (
    <div className="min-h-screen bg-[#F8F6F0] pb-10" data-testid="grupo-frontal-page">
      <header className="bg-[#101D36] px-4 py-6 text-white sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-[1600px]">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[#D4B871]"><Network className="h-3.5 w-3.5" />Grupo Frontal{group?.pastoral_main ? ' · grupo de la pastora' : ''}</p>
          <h1 className="mt-1 font-['Spectral'] text-2xl font-bold" data-testid="grupo-frontal-titulo">{group?.name || 'Mi Grupo Frontal'}</h1>
          {group && <p className="mt-1 text-[15px] text-white/80">Líder: {group.leader?.name || 'Por definir'} · Colíder: {group.co_leader?.name || 'Por definir'}</p>}
          {node?.parent && <p className="mt-1 text-sm text-[#E7D28D]">Proviene de: {node.parent.name}{node.parent.explorable ? <> · <button type="button" onClick={() => openGroup(node.parent.front_group_id)} className="underline">ir al nivel anterior</button></> : ''}</p>}
        </div>
      </header>
      <div className="mx-auto w-full max-w-[1600px] space-y-4 px-4 py-4 sm:px-6 lg:px-8">
        {error && <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
        {!error && !start && <div className="flex justify-center py-16"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>}

        {start && !groupId && <div className="space-y-3">
          {myTeam ? (
            <section className="rounded-xl border border-amber-300 bg-amber-50 p-4" data-testid="grupo-frontal-my-team">
              <p className="text-base font-semibold text-[#101D36]">Tu equipo: {myTeam.people.map((item) => item.name).join(' y ')}</p>
              <p className="text-[15px] text-slate-700">Perteneces a {myTeam.parent_name || 'un Grupo Frontal'}{myTeam.direct_leader ? ` (líder: ${myTeam.direct_leader})` : ''}.</p>
              <p className="mt-1 text-[15px] font-semibold text-amber-900">Todavía no has formado tu grupo.</p>
              <button type="button" onClick={formMine} className="mt-3 inline-flex min-h-12 items-center gap-2 rounded-xl bg-amber-700 px-4 text-base font-semibold text-white" data-testid="grupo-frontal-form-mine"><Sparkles className="h-5 w-5" />Formar grupo</button>
            </section>
          ) : <p className="rounded-xl border border-[#E8E5DE] bg-white p-4 text-[15px] text-slate-600" data-testid="grupo-frontal-sin-grupo">Todavía no lideras ningún Grupo Frontal. Cuando formes tu grupo o te asignen como líder, aparecerá aquí con sus ramas.</p>}
          {isPastoralAuthority(user) && <FrontGroupDialog root groups={[]} onCreated={() => setReloadKey((value) => value + 1)} />}
        </div>}

        {start && start.groups.length > 1 && !params.get('grupo') && <label className="block"><span className="text-sm font-semibold text-slate-700">Grupo</span>
          <select value={groupId || ''} onChange={(event) => openGroup(event.target.value)} className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base">{start.groups.map((item) => <option key={item.front_group_id} value={item.front_group_id}>{item.name}</option>)}</select></label>}

        {groupId && <>
          <div className="grid grid-cols-3 gap-1 rounded-xl bg-[#EEECE6] p-1" role="tablist" data-testid="grupo-frontal-tabs">
            {TABS.map(([key, label, Icon]) => <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setParam({ tab: key === 'mi-grupo' ? null : key })} className={`inline-flex min-h-12 min-w-0 items-center justify-center gap-1.5 rounded-lg px-1 text-[15px] font-semibold ${tab === key ? 'bg-white text-[#101D36] shadow' : 'text-slate-600'}`} data-testid={`grupo-frontal-tab-${key}`}><Icon className="h-4 w-4 shrink-0 max-[439px]:hidden" />{label}</button>)}
          </div>
          {tab === 'mi-grupo' && <>
            <GroupActivityPanel key={`panel-${groupId}-${reloadKey}`} groupId={groupId} onOpenGroup={openGroup} />
            <section className="rounded-xl border border-[#E8E5DE] bg-white shadow-sm">
              <button type="button" onClick={() => setMoreStats((value) => !value)} aria-expanded={moreStats} className="flex min-h-12 w-full items-center justify-between gap-2 px-4 text-[15px] font-semibold text-[#101D36]"><span className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-[#9A7A2F]" />Más estadísticas de toda la rama</span><ChevronDown className={`h-4 w-4 transition ${moreStats ? 'rotate-180' : ''}`} /></button>
              {moreStats && <div className="border-t border-[#E8E5DE] p-3"><GroupStatsPanel key={groupId} groupId={groupId} onOpenGroup={openGroup} /></div>}
            </section>
          </>}
          {tab === 'ramas' && <BranchTree groupId={groupId} onOpenGroup={openGroup} reloadKey={reloadKey} />}
          {tab === 'administrar' && (group ? <AdminGroup key={groupId} group={group} onChanged={() => setReloadKey((value) => value + 1)} /> : <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />)}
          {(isPastoralAuthority(user) || isGeneralCoordinator(user)) && <p className="text-sm text-slate-500">Ves todo el árbol. Cada líder ve solo su grupo y sus ramas hacia abajo.</p>}
          {params.get('grupo') && start.groups.every((item) => item.front_group_id !== params.get('grupo')) && <Link to="/grupo-frontal" className="inline-flex min-h-11 items-center text-[15px] font-semibold text-[#0879BE] underline">Volver a mi grupo</Link>}
        </>}
      </div>
    </div>
  );
}
