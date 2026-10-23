import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, ChevronDown, GitBranch, Loader2, Pencil, Settings2, TriangleAlert } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { PersonQuickPicker } from '../components/front-groups/PersonQuickPicker';
import { GroupRosterEditor, rosterToEntries } from '../components/front-groups/GroupRosterEditor';
import { GroupRosterView } from '../components/front-groups/GroupRosterView';
import { GroupActivityPanel } from '../components/front-groups/GroupActivityPanel';
import { InvasionHub } from '../components/invasions/InvasionHub';

const fullName = (person) => person?.name || [person?.nombre, person?.apellido].filter(Boolean).join(' ') || 'Persona';

const Card = ({ children, testId }) => <section className="rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid={testId}>{children}</section>;

function CoLeaderPicker({ groupId, value, onChange }) {
  return value ? (
    <div className="mt-2 flex min-h-11 items-center justify-between gap-2 rounded-lg bg-[#FBFAF7] px-3 text-sm"><span data-testid="mi-grupo-colider-elegido">{fullName(value)}</span><button type="button" onClick={() => onChange(null)} className="h-9 px-2 text-xs text-red-600 underline">Cambiar</button></div>
  ) : <div className="mt-2"><PersonQuickPicker groupId={groupId} assign={false} placeholder="Buscar colíder en Persona 360…" onPicked={onChange} /></div>;
}

// ETAPA 5C: "Crear mi grupo frontal" — el líder autorizado nombra su grupo,
// elige colíder y arma su lista (individuos o equipos) con revisión previa.
function CreateMyGroup({ detail, onDone }) {
  const { API, getAuthHeaders } = useAuth();
  const [name, setName] = useState('');
  const [coLeader, setCoLeader] = useState(detail.co_leader_person_id ? { person_id: detail.co_leader_person_id, name: detail.co_leader_name } : null);

  const save = async (entries) => {
    try {
      await axios.put(`${API}/api/front-groups/${detail.front_group_id}/conform`, { name: name.trim() || null, co_leader_person_id: coLeader?.person_id || null }, getAuthHeaders());
      await axios.put(`${API}/api/front-groups/${detail.front_group_id}/roster`, { entries }, getAuthHeaders());
      toast.success('¡Tu grupo frontal quedó creado!');
      await onDone();
    } catch (error) {
      toast.error(apiErrorMessage(error, 'No se pudo crear tu grupo'));
    }
  };

  return (
    <div className="space-y-4">
      <Card testId="crear-grupo-nombre">
        <Label htmlFor="mi-grupo-nombre">Nombre de tu grupo</Label>
        <Input id="mi-grupo-nombre" value={name} onChange={(event) => setName(event.target.value)} placeholder={`Equipo de ${detail.primary_leader_name || ''}`} className="mt-1 h-11" data-testid="mi-grupo-nombre-input" />
        <p className="mt-2 text-xs text-slate-500">Tú quedas como líder del grupo.</p>
      </Card>
      <Card testId="crear-grupo-colider">
        <h3 className="font-semibold text-[#101D36]">Tu colíder</h3>
        <CoLeaderPicker groupId={detail.front_group_id} value={coLeader} onChange={setCoLeader} />
      </Card>
      <GroupRosterEditor groupId={detail.front_group_id} excludedIds={[detail.primary_leader_person_id, coLeader?.person_id].filter(Boolean)} onSave={save} saveLabel="Confirmar y crear mi grupo" />
    </div>
  );
}

function ManageMyGroup({ detail, onChanged }) {
  const { API, getAuthHeaders } = useAuth();
  const canManage = detail.permissions?.manage === true;
  const [roster, setRoster] = useState(null);
  const [editing, setEditing] = useState(false);
  const [changingCoLeader, setChangingCoLeader] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [panelKey, setPanelKey] = useState(0);
  const navigate = useNavigate();

  const loadRoster = useCallback(async () => {
    const response = await axios.get(`${API}/api/front-groups/${detail.front_group_id}/roster`, getAuthHeaders());
    setRoster(response.data);
  }, [API, getAuthHeaders, detail.front_group_id]);
  useEffect(() => { loadRoster().catch((error) => toast.error(apiErrorMessage(error, 'No se pudo cargar la lista'))); }, [loadRoster]);

  const saveRoster = async (entries) => {
    try {
      const response = await axios.put(`${API}/api/front-groups/${detail.front_group_id}/roster`, { entries }, getAuthHeaders());
      setRoster(response.data); setEditing(false); setPanelKey((value) => value + 1); toast.success('Lista guardada');
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar la lista')); }
  };
  const setCoLeader = async (person) => {
    if (!person) return;
    try {
      await axios.post(`${API}/api/front-groups/${detail.front_group_id}/co-leader`, { person_id: person.person_id, reason: 'Elegido por el líder del grupo' }, getAuthHeaders());
      setChangingCoLeader(false); toast.success('Colíder actualizado'); await onChanged(); await loadRoster(); setPanelKey((value) => value + 1);
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo cambiar el colíder')); }
  };

  return (
    <div className="space-y-4">
      <Card testId="mi-grupo-liderazgo">
        {detail.parent_group_name && <p className="mb-2 flex items-center gap-1.5 text-xs text-[#7A5F22]" data-testid="mi-grupo-proviene"><GitBranch className="h-3.5 w-3.5" />Proviene de: {detail.parent_group_name}{detail.parent_is_pastoral_main ? ' (grupo de la pastora)' : ''}</p>}
        <dl className="space-y-1 text-sm text-slate-700">
          <div><dt className="inline font-medium">Líder: </dt><dd className="inline">{detail.primary_leader_name || 'Por definir'}</dd></div>
          <div><dt className="inline font-medium">Colíder: </dt><dd className="inline" data-testid="mi-grupo-colider-actual">{detail.co_leader_name || 'Por definir'}</dd></div>
        </dl>
      </Card>
      <InvasionHub showAction />
      <GroupActivityPanel key={panelKey} groupId={detail.front_group_id} onOpenGroup={(id) => navigate(`/estructura-frontal/${id}`)} />
      <Link to={`/estructura-frontal/${detail.front_group_id}`} className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-[#101D36] text-sm font-semibold text-white" data-testid="mi-grupo-explorar-rama">Explorar mi rama hacia abajo</Link>
      <section className="rounded-xl border border-[#E8E5DE] bg-white shadow-sm" data-testid="mi-grupo-admin">
        <button type="button" onClick={() => setAdminOpen((value) => !value)} aria-expanded={adminOpen} className="flex min-h-12 w-full items-center justify-between gap-2 px-4 text-sm font-semibold text-[#101D36]" data-testid="mi-grupo-admin-toggle"><span className="flex items-center gap-2"><Settings2 className="h-4 w-4 text-[#9A7A2F]" />Administrar mi grupo</span><ChevronDown className={`h-4 w-4 transition ${adminOpen ? 'rotate-180' : ''}`} /></button>
        {adminOpen && <div className="space-y-3 border-t border-[#E8E5DE] p-3">
          {canManage && (changingCoLeader
          ? <CoLeaderPicker groupId={detail.front_group_id} value={null} onChange={setCoLeader} />
          : <button type="button" onClick={() => setChangingCoLeader(true)} className="mt-2 min-h-10 text-sm font-semibold text-[#7A5F22] underline" data-testid="mi-grupo-cambiar-colider">{detail.co_leader_name ? 'Cambiar colíder' : 'Elegir colíder'}</button>)}
          {!roster && <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-[#9A7A2F]" /></div>}
          {roster && (editing
            ? <GroupRosterEditor groupId={detail.front_group_id} initialEntries={rosterToEntries(roster)} excludedIds={[detail.primary_leader_person_id, detail.co_leader_person_id].filter(Boolean)} onSave={saveRoster} onCancel={() => setEditing(false)} />
            : <>
              {canManage && <button type="button" onClick={() => setEditing(true)} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md border border-[#D9CFB4] bg-white text-sm font-semibold text-[#7A5F22]" data-testid="mi-grupo-editar-lista"><Pencil className="h-4 w-4" />Editar lista (personas y equipos)</button>}
              <GroupRosterView groupId={detail.front_group_id} roster={roster} canManage={canManage} onChanged={async () => { await loadRoster(); setPanelKey((value) => value + 1); }} title="Equipos registrados y líderes" />
            </>)}
        </div>}
      </section>
    </div>
  );
}

export default function MiGrupoFrontalPage() {
  const { groupId } = useParams();
  const { API, getAuthHeaders, user } = useAuth();
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/api/front-groups/${groupId}`, getAuthHeaders());
      setDetail(response.data); setError('');
    } catch (requestError) {
      setError(apiErrorMessage(requestError, 'No se pudo cargar el grupo.'));
    }
  }, [API, getAuthHeaders, groupId]);

  useEffect(() => { load(); }, [load]);

  const isPending = detail?.status === 'pending_formation';
  const isDesignatedLeader = Boolean(user?.person_id) && detail?.primary_leader_person_id === user.person_id;

  return (
    <div className="min-h-screen bg-[#F8F6F0] pb-10" data-testid="mi-grupo-frontal-page">
      <header className="bg-[#101D36] px-4 py-6 text-white sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-[1600px]">
          <Link to="/mi-perfil" className="inline-flex min-h-9 items-center gap-1 text-xs text-white/70 hover:text-white"><ArrowLeft className="h-3.5 w-3.5" />Mi perfil</Link>
          <p className="mt-2 text-xs font-semibold uppercase text-[#D4B871]">{isPending ? 'Crear mi grupo frontal' : 'Mi grupo frontal'}</p>
          <h1 className="mt-1 font-['Spectral'] text-2xl font-bold" data-testid="mi-grupo-titulo">{detail?.display_name || detail?.name || 'Grupo Frontal'}</h1>
        </div>
      </header>
      <div className="mx-auto w-full max-w-[1600px] space-y-4 px-4 py-5 sm:px-6 lg:px-8">
        {error && <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
        {!detail && !error && <div className="flex justify-center py-16"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>}
        {detail?.member_view && <Card testId="mi-grupo-vista-miembro"><p className="text-sm text-slate-700">Líder: {detail.primary_leader_name || 'Por definir'} · Colíder: {detail.co_leader_name || 'Por definir'}</p></Card>}
        {detail && !detail.member_view && isPending && (isDesignatedLeader
          ? <CreateMyGroup detail={detail} onDone={load} />
          : <Card testId="mi-grupo-pendiente"><p className="text-sm text-slate-600">Este grupo aún no ha sido creado por su líder designado.</p></Card>)}
        {detail && !detail.member_view && !isPending && <ManageMyGroup detail={detail} onChanged={load} />}
      </div>
    </div>
  );
}
