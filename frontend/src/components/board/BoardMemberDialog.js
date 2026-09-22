import React, { useState } from 'react';
import axios from 'axios';
import { ShieldCheck, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { PersonSelect } from '../cellular/CellularFields';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const rolePermissions = {
  president: ['Reuniones y agenda', 'Votaciones', 'Acuerdos y tareas'],
  vice_president: ['Reuniones y agenda', 'Votaciones', 'Acuerdos y tareas'],
  secretary: ['Reuniones y agenda', 'Notas y minutas', 'Grabaciones', 'Acuerdos y tareas'],
  treasurer: ['Información institucional', 'Documentos compartidos', 'Votaciones'],
  vocal: ['Información institucional', 'Tareas/documentos asignados', 'Votaciones'],
  member: ['Información institucional', 'Tareas/documentos asignados', 'Votaciones'],
};

export const BoardMemberDialog = ({ people, positions, doors, onSaved }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ person_id: '', position_key: '', voting_rights: true, supervised_door_keys: [], ministry_ids: [] });
  const toggleDoor = (value) => setForm((old) => ({ ...old, supervised_door_keys: old.supervised_door_keys.includes(value) ? old.supervised_door_keys.filter((item) => item !== value) : [...old.supervised_door_keys, value] }));
  const submit = async (event) => {
    event.preventDefault();
    try {
      await axios.post(`${API}/api/board/members`, form, getAuthHeaders());
      toast.success('Miembro incorporado con permisos según su cargo'); setOpen(false); await onSaved();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo incorporar'); }
  };
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button className="bg-[#C8A951] text-[#14213D]" data-testid="open-add-board-member-button"><UserPlus className="mr-2 h-4 w-4" />Añadir miembro</Button></DialogTrigger><DialogContent className="max-h-[90vh] overflow-y-auto bg-white"><DialogHeader><DialogTitle>Membresía formal de Junta</DialogTitle><DialogDescription>El cargo aplica una matriz cerrada. No concede acceso a datos pastorales privados.</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-5"><PersonSelect id="board-member-person-select" label="Persona" items={people} value={form.person_id} onChange={(value) => setForm((old) => ({ ...old, person_id: value }))} /><div><Label>Cargo institucional</Label><Select value={form.position_key} onValueChange={(value) => setForm((old) => ({ ...old, position_key: value }))}><SelectTrigger data-testid="board-member-position-select"><SelectValue placeholder="Seleccionar cargo" /></SelectTrigger><SelectContent className="bg-white">{positions.map((item) => <SelectItem key={item.position_key} value={item.position_key}>{item.name}</SelectItem>)}</SelectContent></Select></div>{form.position_key && <div className="border border-emerald-200 bg-emerald-50 p-3" data-testid="board-role-permissions-summary"><p className="flex items-center gap-2 text-sm font-semibold text-emerald-900"><ShieldCheck className="h-4 w-4" />Permisos del cargo</p><p className="mt-1 text-xs text-emerald-800">{(rolePermissions[form.position_key] || ['Consulta institucional']).join(' · ')}</p></div>}<label className="flex min-h-12 items-center gap-3 border p-3 text-sm"><Checkbox checked={form.voting_rights} onCheckedChange={(value) => setForm((old) => ({ ...old, voting_rights: value }))} data-testid="board-member-voting-checkbox" />Tiene derecho a voto</label><fieldset><legend className="text-sm font-medium">Puertas supervisadas</legend><div className="mt-2 grid gap-2 sm:grid-cols-3">{doors.map((door) => <label key={door.door_key} className="flex min-h-11 items-center gap-2 border p-2 text-xs"><Checkbox checked={form.supervised_door_keys.includes(door.door_key)} onCheckedChange={() => toggleDoor(door.door_key)} data-testid={`board-door-${door.door_key}`} />{door.number}. {door.name}</label>)}</div></fieldset><Button type="submit" disabled={!form.person_id || !form.position_key} className="w-full bg-[#14213D]" data-testid="add-board-member-submit-button">Guardar membresía</Button></form></DialogContent></Dialog>;
};