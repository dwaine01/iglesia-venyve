import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, BarChart3, ChevronDown, ChevronRight, GitBranch, Loader2, Network, Settings2, TriangleAlert } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { GroupStatsPanel } from '../components/front-groups/GroupStatsPanel';
import { GroupActivityPanel } from '../components/front-groups/GroupActivityPanel';
import { FrontGroupDetailPanel } from '../components/front-groups/FrontGroupDetailPanel';
import { FrontGroupDialog } from '../components/front-groups/FrontGroupDialog';
import { isPastoralAuthority } from '../lib/accessControl';

export const plural = (count, one, many) => `${count ?? 0} ${count === 1 ? one : many}`;

const Tile = ({ label, value, testId }) => (
  <div className="rounded-lg border border-[#EEECE6] bg-white p-2.5" data-testid={testId}>
    <div className="text-xl font-semibold text-[#101D36]">{value ?? 0}</div>
    <div className="text-[11px] leading-tight text-slate-500">{label}</div>
  </div>
);

export function GroupCardButton({ group, onOpen }) {
  return (
    <button type="button" onClick={() => onOpen(group.front_group_id)} className="flex min-h-16 w-full items-center gap-3 rounded-xl border border-[#E8E5DE] bg-white p-3 text-left shadow-sm hover:border-[#D9CFB4] hover:bg-[#FBF6EA]" data-testid={`structure-group-${group.front_group_id}`}>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 font-semibold text-[#101D36]"><span className="truncate">{group.name}</span>{group.status === 'pending_formation' && <span className="shrink-0 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-800">Por crear</span>}</p>
        <p className="truncate text-xs text-slate-500">Líder: {group.leader?.name || 'Por definir'}{group.co_leader?.name ? ` · Colíder: ${group.co_leader.name}` : ''}</p>
        <p className="mt-1 text-xs text-slate-600">{plural(group.direct.people, 'persona', 'personas')} · {plural(group.direct.pairs, 'equipo', 'equipos')} · rama: {plural(group.branch.people, 'persona', 'personas')} en {plural(group.branch.groups, 'grupo', 'grupos')}</p>
      </div>
      <ChevronRight className="h-5 w-5 shrink-0 text-slate-400" />
    </button>
  );
}

// ETAPA 5C-2: explorar la estructura por niveles — Grupo de la pastora →
// líder → grupo del líder → otros líderes → sus grupos → integrante final.
// El backend decide qué ramas puede abrir cada quien.
export default function EstructuraFrontalPage() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const { API, getAuthHeaders, user } = useAuth();
  const [start, setStart] = useState(null);
  const [node, setNode] = useState(null);
  const [error, setError] = useState('');
  const [moreStats, setMoreStats] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [allGroups, setAllGroups] = useState([]);
  const [reloadKey, setReloadKey] = useState(0);

  const open = useCallback((id) => navigate(`/estructura-frontal/${id}`), [navigate]);

  useEffect(() => {
    setError(''); setNode(null); setStart(null); setMoreStats(false); setAdminOpen(false);
    if (!groupId) {
      axios.get(`${API}/api/front-group-structure/start`, getAuthHeaders())
        .then((response) => {
          if (response.data.groups.length === 1) navigate(`/estructura-frontal/${response.data.groups[0].front_group_id}`, { replace: true });
          else setStart(response.data);
        })
        .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar la estructura.')));
      return;
    }
    axios.get(`${API}/api/front-group-structure/groups/${groupId}`, getAuthHeaders())
      .then((response) => setNode(response.data))
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo abrir este grupo.')));
  }, [API, getAuthHeaders, groupId, navigate, reloadKey]);

  // Herramientas de administración del módulo anterior (trabajo, integrantes, células,
  // historial, archivar/borrar, subgrupos): se cargan solo al abrirlas.
  useEffect(() => {
    if (!adminOpen) return;
    axios.get(`${API}/api/front-groups`, getAuthHeaders()).then((response) => setAllGroups(response.data.items || [])).catch(() => setAllGroups([]));
  }, [API, getAuthHeaders, adminOpen]);

  const group = node?.group;
  const backTarget = node?.parent?.explorable ? `/estructura-frontal/${node.parent.front_group_id}` : null;

  return (
    <div className="min-h-screen bg-[#F8F6F0] pb-10" data-testid="estructura-frontal-page">
      <header className="bg-[#101D36] px-4 py-5 text-white sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-[1600px]">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase text-[#D4B871]"><Network className="h-3.5 w-3.5" />Estructura por niveles</p>
          <h1 className="mt-1 font-['Spectral'] text-2xl font-bold" data-testid="estructura-titulo">{group?.name || 'Explorar mi rama'}</h1>
          {group && <p className="mt-1 text-sm text-white/70">Líder: {group.leader?.name || 'Por definir'} · Colíder: {group.co_leader?.name || 'Por definir'}</p>}
        </div>
      </header>
      <div className="mx-auto w-full max-w-[1600px] space-y-4 px-4 py-4 sm:px-6 lg:px-8">
        {error && <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
        {!error && !node && !start && <div className="flex justify-center py-16"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>}

        {start && isPastoralAuthority(user) && <div className="flex justify-end" data-testid="estructura-crear-raiz"><FrontGroupDialog root groups={start.groups} onCreated={() => setReloadKey((value) => value + 1)} /></div>}
        {start && (start.groups.length ? (
          <div className="space-y-2">{start.groups.map((item) => <GroupCardButton key={item.front_group_id} group={item} onOpen={open} />)}</div>
        ) : <p className="rounded-xl border border-[#E8E5DE] bg-white p-4 text-sm text-slate-500" data-testid="estructura-sin-rama">No lideras ningún grupo frontal. Cuando te asignen como líder podrás explorar tu rama aquí.</p>)}

        {node && <>
          <nav className="space-y-2" aria-label="Niveles">
            {backTarget
              ? <Link to={backTarget} className="flex min-h-12 items-center gap-2 rounded-xl border border-[#E8E5DE] bg-white px-4 text-sm font-semibold text-[#101D36] shadow-sm" data-testid="estructura-volver"><ArrowLeft className="h-4 w-4" />Atrás · {node.parent.name || 'nivel anterior'}</Link>
              : <button type="button" onClick={() => navigate(-1)} className="flex min-h-12 w-full items-center gap-2 rounded-xl border border-[#E8E5DE] bg-white px-4 text-sm font-semibold text-[#101D36] shadow-sm" data-testid="estructura-atras"><ArrowLeft className="h-4 w-4" />Atrás</button>}
            {!backTarget && node.parent && <p className="flex items-center gap-1.5 text-xs text-[#7A5F22]" data-testid="estructura-proviene"><GitBranch className="h-3.5 w-3.5" />Proviene de: {node.parent.name}{node.parent.pastoral_main ? ' (grupo de la pastora)' : ''}</p>}
            {node.breadcrumbs.length > 0 && <ol className="flex gap-1 overflow-x-auto pb-1 text-xs" data-testid="estructura-migas">{node.breadcrumbs.map((crumb) => <li key={crumb.front_group_id} className="flex shrink-0 items-center gap-1"><Link to={`/estructura-frontal/${crumb.front_group_id}`} className="inline-flex min-h-9 items-center rounded-full bg-white px-3 text-[#101D36] shadow-sm">{crumb.name}</Link><ChevronRight className="h-3.5 w-3.5 text-slate-400" /></li>)}<li className="inline-flex min-h-9 shrink-0 items-center rounded-full bg-[#101D36] px-3 text-white">{group.name}</li></ol>}
          </nav>

          <GroupActivityPanel key={`panel-${group.front_group_id}`} groupId={group.front_group_id} onOpenGroup={open} />

          <section className="rounded-xl border border-[#E8E5DE] bg-[#FBFAF7] p-3" data-testid="estructura-totales">
            <h2 className="text-xs font-semibold uppercase text-slate-500">Este grupo</h2>
            <div className="mt-2 grid grid-cols-3 gap-2"><Tile label="Personas" value={group.direct.people} testId="tot-grupo-personas" /><Tile label="Equipos" value={group.direct.pairs} /><Tile label="Individuales" value={group.direct.individuals} /></div>
            <h2 className="mt-3 text-xs font-semibold uppercase text-slate-500">Toda la rama (sin contar dos veces)</h2>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4"><Tile label="Grupos" value={group.branch.groups} /><Tile label="Personas" value={group.branch.people} testId="tot-rama-personas" /><Tile label="Equipos" value={group.branch.pairs} /><Tile label="Líderes y colíderes" value={group.branch.leaders} /></div>
          </section>

          <section className="space-y-2" data-testid="estructura-hijos">
            <h2 className="flex items-center gap-2 font-semibold text-[#101D36]"><GitBranch className="h-4 w-4 text-[#9A7A2F]" />Grupos de sus líderes ({node.children.length})</h2>
            {node.children.length ? <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{node.children.map((child) => <GroupCardButton key={child.front_group_id} group={child} onOpen={open} />)}</div> : <p className="text-sm text-slate-400">Ningún líder de este grupo ha formado su grupo todavía.</p>}
          </section>

          <section className="rounded-xl border border-[#E8E5DE] bg-white shadow-sm" data-testid="estructura-administracion">
            <button type="button" onClick={() => setAdminOpen((value) => !value)} aria-expanded={adminOpen} className="flex min-h-12 w-full items-center justify-between gap-2 px-4 text-left text-sm font-semibold text-[#101D36]" data-testid="estructura-administracion-toggle"><span className="flex items-center gap-2"><Settings2 className="h-4 w-4 shrink-0 text-[#9A7A2F]" />Administración del grupo: trabajo, integrantes, células, historial, subgrupos, archivar</span><ChevronDown className={`h-4 w-4 shrink-0 transition ${adminOpen ? 'rotate-180' : ''}`} /></button>
            {adminOpen && <div className="border-t border-[#E8E5DE] p-3"><FrontGroupDetailPanel key={`admin-${group.front_group_id}`} group={{ front_group_id: group.front_group_id }} groups={allGroups} onUpdated={async () => setReloadKey((value) => value + 1)} /></div>}
          </section>

          <section className="rounded-xl border border-[#E8E5DE] bg-white shadow-sm" data-testid="estructura-mas-estadisticas">
            <button type="button" onClick={() => setMoreStats((value) => !value)} aria-expanded={moreStats} className="flex min-h-12 w-full items-center justify-between gap-2 px-4 text-sm font-semibold text-[#101D36]"><span className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-[#9A7A2F]" />Más estadísticas de toda la rama</span><ChevronDown className={`h-4 w-4 transition ${moreStats ? 'rotate-180' : ''}`} /></button>
            {moreStats && <div className="border-t border-[#E8E5DE] p-3"><GroupStatsPanel key={group.front_group_id} groupId={group.front_group_id} onOpenGroup={open} /></div>}
          </section>
        </>}
      </div>
    </div>
  );
}
