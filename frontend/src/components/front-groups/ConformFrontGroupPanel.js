import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { PersonQuickPicker } from './PersonQuickPicker';

// A4: el líder designado abre "Conformar mi grupo frontal" (reutiliza el
// mismo grupo pending_formation; nunca crea otro).
export const ConformFrontGroupPanel = ({ group, onConformed }) => {
  const { API, getAuthHeaders, user } = useAuth();
  const [name, setName] = useState(''); const [members, setMembers] = useState([]); const [saving, setSaving] = useState(false);
  const isDesignatedLeader = Boolean(user?.person_id) && user.person_id === group.primary_leader_person_id;

  const addMember = (person) => setMembers((current) => (current.some((item) => item.person_id === person.person_id) ? current : [...current, person]));
  const removeMember = (personId) => setMembers((current) => current.filter((item) => item.person_id !== personId));

  const submit = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/api/front-groups/${group.front_group_id}/conform`, {
        name: name || null, member_person_ids: members.map((item) => item.person_id),
      }, getAuthHeaders());
      toast.success('¡Grupo conformado!');
      await onConformed();
    } catch (error) {
      toast.error(apiErrorMessage(error, 'No se pudo conformar el grupo'));
    } finally { setSaving(false); }
  };

  return <section className="space-y-4 border border-amber-300 bg-amber-50 p-5" data-testid="front-group-conform-panel">
    <div className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-amber-700" /><h3 className="font-['Spectral'] text-xl font-semibold text-amber-900">Pendiente de conformación</h3></div>
    <p className="text-sm text-amber-800">{isDesignatedLeader ? 'Usted fue designado líder de este grupo. Agregue un nombre (opcional) e integrantes, y confórmelo cuando esté listo.' : 'Este grupo aún no ha sido conformado por su líder designado.'}</p>
    {isDesignatedLeader && <>
      <div><Label htmlFor="conform-name">Nombre del grupo (opcional)</Label><Input id="conform-name" value={name} onChange={(event) => setName(event.target.value)} placeholder={`Equipo de ${group.primary_leader_name || ''}`} data-testid="front-group-conform-name-input" /></div>
      <div><Label>Integrantes iniciales</Label><PersonQuickPicker groupId={group.front_group_id} onPicked={addMember} />
        {members.length > 0 && <ul className="mt-2 space-y-1">{members.map((person) => <li key={person.person_id} className="flex items-center justify-between border border-slate-200 bg-white px-3 py-1.5 text-sm" data-testid={`front-group-conform-member-${person.person_id}`}><span>{person.nombre} {person.apellido}</span><button type="button" onClick={() => removeMember(person.person_id)} className="text-xs text-red-600 underline">Quitar</button></li>)}</ul>}
      </div>
      <Button onClick={submit} disabled={saving} className="w-full bg-amber-700 text-white hover:bg-amber-800" data-testid="front-group-conform-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Conformar mi grupo frontal</Button>
    </>}
  </section>;
};
