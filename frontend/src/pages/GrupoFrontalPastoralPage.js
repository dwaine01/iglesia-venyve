import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronDown, Crown, Loader2, Pencil, Settings2, TriangleAlert } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { PersonQuickPicker } from '../components/front-groups/PersonQuickPicker';
import { GroupRosterEditor, rosterToEntries } from '../components/front-groups/GroupRosterEditor';
import { GroupRosterView } from '../components/front-groups/GroupRosterView';
import { GroupActivityPanel } from '../components/front-groups/GroupActivityPanel';

export default function GrupoFrontalPastoralPage() {
  const { API, getAuthHeaders } = useAuth();
  const [view, setView] = useState(null);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [editingList, setEditingList] = useState(false);
  const [changingCoLeader, setChangingCoLeader] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [panelKey, setPanelKey] = useState(0);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/api/pastoral-front-group`, getAuthHeaders());
      setView(response.data); setName(response.data.group?.name || ''); setError('');
    } catch (requestError) { setError(apiErrorMessage(requestError, 'No se pudo cargar tu grupo frontal.')); }
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);

  const saveGroup = async (coLeaderId) => {
    if (name.trim().length < 2) { toast.error('Escribe un nombre para tu grupo'); return; }
    setSaving(true);
    try {
      const response = await axios.put(`${API}/api/pastoral-front-group`, { name: name.trim(), co_leader_person_id: coLeaderId || view?.group?.co_leader?.person_id || null }, getAuthHeaders());
      setView(response.data); setChangingCoLeader(false); toast.success('Grupo frontal guardado');
    } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo guardar')); } finally { setSaving(false); }
  };
  const saveRoster = async (entries) => {
    try {
      await axios.put(`${API}/api/front-groups/${view.group.front_group_id}/roster`, { entries }, getAuthHeaders());
      setEditingList(false); toast.success('Lista guardada'); await load(); setPanelKey((value) => value + 1);
    } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo guardar la lista')); }
  };

  const group = view?.group;
  const canEdit = view?.can_edit === true;

  return (
    <div className="min-h-screen bg-[#F8F6F0] pb-10" data-testid="grupo-frontal-pastoral-page">
      <header className="bg-[#101D36] px-4 py-6 text-white sm:px-6 lg:px-8">
        <div className="mx-auto w-full max-w-[1600px]">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase text-[#D4B871]"><Crown className="h-3.5 w-3.5" />Grupo frontal principal</p>
          <h1 className="mt-1 font-['Spectral'] text-2xl font-bold">{group?.name || 'Mi grupo frontal'}</h1>
          {group && <p className="mt-1 text-sm text-white/70">Líder: {group.leader?.name || '—'} · Colíder: {group.co_leader?.name || 'Por definir'}</p>}
        </div>
      </header>
      <div className="mx-auto w-full max-w-[1600px] space-y-4 px-4 py-5 sm:px-6 lg:px-8">
        {error && <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
        {!view && !error && <div className="flex justify-center py-16"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>}
        {view && !group && (canEdit ? (
          <section className="space-y-3 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid="crear-grupo-pastoral">
            <h2 className="font-semibold text-[#101D36]">Crear mi grupo frontal</h2>
            <p className="text-sm text-slate-600">Tú quedas como líder. Después agregas personas desde Persona 360, como individuos o en equipos de servicio.</p>
            <Label htmlFor="pastoral-group-name">Nombre del grupo</Label>
            <Input id="pastoral-group-name" value={name} onChange={(event) => setName(event.target.value)} className="h-11" data-testid="pastoral-group-name-input" />
            <Button className="h-11 w-full bg-amber-700 text-white hover:bg-amber-800" onClick={() => saveGroup(null)} disabled={saving} data-testid="pastoral-group-create">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Crear mi grupo frontal</Button>
          </section>
        ) : <p className="rounded-xl border border-[#E8E5DE] bg-white p-4 text-sm text-slate-500">La pastora aún no ha creado su grupo frontal principal.</p>)}
        {group && <GroupActivityPanel key={panelKey} groupId={group.front_group_id} onOpenGroup={(id) => navigate(`/estructura-frontal/${id}`)} />}
        {group && <Link to={`/estructura-frontal/${group.front_group_id}`} className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-[#101D36] text-sm font-semibold text-white" data-testid="pastoral-ver-estructura">Explorar la estructura hacia abajo</Link>}
        {group && (
          <section className="rounded-xl border border-[#E8E5DE] bg-white shadow-sm" data-testid="pastoral-group-admin">
            <button type="button" onClick={() => setAdminOpen((value) => !value)} aria-expanded={adminOpen} className="flex min-h-12 w-full items-center justify-between gap-2 px-4 text-sm font-semibold text-[#101D36]" data-testid="pastoral-group-admin-toggle"><span className="flex items-center gap-2"><Settings2 className="h-4 w-4 text-[#9A7A2F]" />Administrar el grupo (equipos de servicio y líderes)</span><ChevronDown className={`h-4 w-4 transition ${adminOpen ? 'rotate-180' : ''}`} /></button>
            {adminOpen && <div className="space-y-3 border-t border-[#E8E5DE] p-3">
              {canEdit && <div className="space-y-3" data-testid="pastoral-group-settings">
                <Label htmlFor="pastoral-group-rename">Nombre del grupo</Label>
                <div className="flex gap-2"><Input id="pastoral-group-rename" value={name} onChange={(event) => setName(event.target.value)} className="h-11" /><Button variant="outline" className="h-11" onClick={() => saveGroup(null)} disabled={saving || name === group.name}>Guardar</Button></div>
                {changingCoLeader
                  ? <PersonQuickPicker groupId={group.front_group_id} assign={false} placeholder="Buscar colíder en Persona 360…" onPicked={(person) => saveGroup(person.person_id)} />
                  : <button type="button" onClick={() => setChangingCoLeader(true)} className="min-h-10 text-sm font-semibold text-[#7A5F22] underline" data-testid="pastoral-group-colider">{group.co_leader ? 'Cambiar colíder del grupo' : 'Elegir colíder del grupo'}</button>}
              </div>}
              {editingList
                ? <GroupRosterEditor groupId={group.front_group_id} initialEntries={rosterToEntries(view.roster)} excludedIds={[group.leader?.person_id, group.co_leader?.person_id].filter(Boolean)} onSave={saveRoster} onCancel={() => setEditingList(false)} />
                : <>
                  {canEdit && <button type="button" onClick={() => setEditingList(true)} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-[#101D36] text-sm font-semibold text-white" data-testid="pastoral-group-edit-list"><Pencil className="h-4 w-4" />Agregar personas o crear equipos</button>}
                  <GroupRosterView groupId={group.front_group_id} roster={view.roster} canManage={canEdit} onChanged={async () => { await load(); setPanelKey((value) => value + 1); }} title="Equipos registrados y líderes" />
                </>}
            </div>}
          </section>
        )}
      </div>
    </div>
  );
}
