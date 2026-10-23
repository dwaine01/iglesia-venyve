import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Crown, Loader2, Pencil, TriangleAlert, X } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { PersonQuickPicker } from '../components/front-groups/PersonQuickPicker';
import { GroupRosterEditor, rosterToEntries } from '../components/front-groups/GroupRosterEditor';
import { GroupRosterView } from '../components/front-groups/GroupRosterView';

const PROCESS_LABELS = { consolidation: 'Consolidación', seven_weeks: 'Ley de las 7 Semanas', discipleship: 'Discipulado', mentorship: 'Mentoría', cap: 'CAP', outreach_invasion: 'Invasión' };

function ActivityBlock({ title, data }) {
  if (!data) return null;
  const items = [
    ['Hogares visitados', data.invasion?.households_visited], ['Visitas', data.invasion?.visits_total],
    ['Intentos registrados', data.invasion?.attempts_total], ['Personas contactadas', data.invasion?.unique_persons_contacted],
    ['Aceptaron consolidación', data.consolidation?.accepted], ['Actividades vencidas', data.consolidation?.activities_overdue],
  ];
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase text-slate-500">{title}</h4>
      <div className="mt-1 grid grid-cols-2 gap-2">{items.map(([label, value]) => <div key={label} className="rounded-lg border border-[#EEECE6] p-2"><div className="text-lg font-semibold text-[#101D36]">{value ?? 0}</div><div className="text-[11px] text-slate-500">{label}</div></div>)}</div>
    </div>
  );
}

// Actividad de un integrante como persona, líder y mentor (mismos registros
// de Supervisión; solo la pastora y el coordinador general lo consultan).
function MemberActivity({ person, onClose }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    axios.get(`${API}/api/pastoral-front-group/members/${person.person_id}/activity`, getAuthHeaders())
      .then((response) => setData(response.data))
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar la actividad')));
  }, [API, getAuthHeaders, person.person_id]);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center" role="dialog" aria-modal="true" data-testid="member-activity-sheet">
      <div className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-white p-4 sm:rounded-2xl">
        <div className="flex items-start justify-between gap-2">
          <div><p className="text-xs font-semibold uppercase text-[#9A7A2F]">Actividad</p><h3 className="font-['Spectral'] text-xl font-semibold text-[#101D36]">{person.name}</h3></div>
          <button type="button" onClick={onClose} className="grid h-11 w-11 place-items-center rounded-md hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        {!data && !error && <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-[#9A7A2F]" /></div>}
        {data && <div className="mt-3 space-y-4">
          <div>
            <h4 className="text-xs font-semibold uppercase text-slate-500">Como persona</h4>
            {data.as_person.processes.length ? <ul className="mt-1 space-y-1 text-sm">{data.as_person.processes.map((item, index) => <li key={`${item.process_key}-${index}`} className="rounded-lg bg-[#FBFAF7] px-3 py-2">{PROCESS_LABELS[item.process_key] || item.process_key} · {item.status}{item.current_stage_name ? ` · ${item.current_stage_name}` : ''}</li>)}</ul> : <p className="mt-1 text-sm text-slate-400">Sin procesos registrados.</p>}
          </div>
          <ActivityBlock title="Como mentor" data={data.as_mentor} />
          {data.as_leader ? <ActivityBlock title={`Como líder (${data.as_leader.led_group_count} grupo/s y su rama)`} data={data.as_leader} /> : <p className="text-sm text-slate-400">Aún no lidera un grupo.</p>}
          <Link to={`/personas/${person.person_id}`} className="flex min-h-11 items-center justify-center rounded-md border border-[#D9CFB4] text-sm font-semibold text-[#7A5F22]">Abrir Persona 360</Link>
        </div>}
      </div>
    </div>
  );
}

export default function GrupoFrontalPastoralPage() {
  const { API, getAuthHeaders } = useAuth();
  const [view, setView] = useState(null);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [editingList, setEditingList] = useState(false);
  const [changingCoLeader, setChangingCoLeader] = useState(false);
  const [activityPerson, setActivityPerson] = useState(null);

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
      setEditingList(false); toast.success('Lista guardada'); await load();
    } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo guardar la lista')); }
  };

  const group = view?.group;
  const canEdit = view?.can_edit === true;

  return (
    <div className="min-h-screen bg-[#F8F6F0] pb-10" data-testid="grupo-frontal-pastoral-page">
      <header className="bg-[#101D36] px-4 py-6 text-white sm:px-6">
        <div className="mx-auto max-w-2xl">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase text-[#D4B871]"><Crown className="h-3.5 w-3.5" />Grupo frontal principal</p>
          <h1 className="mt-1 font-['Spectral'] text-2xl font-bold">{group?.name || 'Mi grupo frontal'}</h1>
          {group && <p className="mt-1 text-sm text-white/70">Líder: {group.leader?.name || '—'} · Colíder: {group.co_leader?.name || 'Por definir'}</p>}
        </div>
      </header>
      <div className="mx-auto max-w-2xl space-y-4 px-4 py-5 sm:px-6">
        {error && <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
        {!view && !error && <div className="flex justify-center py-16"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>}
        {view && !group && (canEdit ? (
          <section className="space-y-3 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid="crear-grupo-pastoral">
            <h2 className="font-semibold text-[#101D36]">Crear mi grupo frontal</h2>
            <p className="text-sm text-slate-600">Tú quedas como líder. Después agregas personas desde Persona 360, como individuos o parejas.</p>
            <Label htmlFor="pastoral-group-name">Nombre del grupo</Label>
            <Input id="pastoral-group-name" value={name} onChange={(event) => setName(event.target.value)} className="h-11" data-testid="pastoral-group-name-input" />
            <Button className="h-11 w-full bg-amber-700 text-white hover:bg-amber-800" onClick={() => saveGroup(null)} disabled={saving} data-testid="pastoral-group-create">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Crear mi grupo frontal</Button>
          </section>
        ) : <p className="rounded-xl border border-[#E8E5DE] bg-white p-4 text-sm text-slate-500">La pastora aún no ha creado su grupo frontal principal.</p>)}
        {group && canEdit && (
          <section className="space-y-3 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid="pastoral-group-settings">
            <Label htmlFor="pastoral-group-rename">Nombre del grupo</Label>
            <div className="flex gap-2"><Input id="pastoral-group-rename" value={name} onChange={(event) => setName(event.target.value)} className="h-11" /><Button variant="outline" className="h-11" onClick={() => saveGroup(null)} disabled={saving || name === group.name}>Guardar</Button></div>
            {changingCoLeader
              ? <PersonQuickPicker groupId={group.front_group_id} assign={false} placeholder="Buscar colíder en Persona 360…" onPicked={(person) => saveGroup(person.person_id)} />
              : <button type="button" onClick={() => setChangingCoLeader(true)} className="min-h-10 text-sm font-semibold text-[#7A5F22] underline" data-testid="pastoral-group-colider">{group.co_leader ? 'Cambiar colíder del grupo' : 'Elegir colíder del grupo'}</button>}
          </section>
        )}
        {group && (editingList
          ? <GroupRosterEditor groupId={group.front_group_id} initialEntries={rosterToEntries(view.roster)} excludedIds={[group.leader?.person_id, group.co_leader?.person_id].filter(Boolean)} onSave={saveRoster} onCancel={() => setEditingList(false)} />
          : <>
            {canEdit && <button type="button" onClick={() => setEditingList(true)} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-[#101D36] text-sm font-semibold text-white" data-testid="pastoral-group-edit-list"><Pencil className="h-4 w-4" />Agregar u organizar personas y parejas</button>}
            <GroupRosterView groupId={group.front_group_id} roster={view.roster} canManage={canEdit} onChanged={load} onShowActivity={setActivityPerson} />
          </>)}
      </div>
      {activityPerson && <MemberActivity person={activityPerson} onClose={() => setActivityPerson(null)} />}
    </div>
  );
}
