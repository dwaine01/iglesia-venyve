import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Route, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const modes = [
  ['complete_cycle', 'Ciclo completo', 'Oración e Invasión'],
  ['direct_church', 'Entrada directa', 'Desde la iglesia'],
  ['cell', 'Desde célula', 'Conserva célula de origen'],
  ['visitor_followup', 'Visitante', 'Seguimiento antes de iniciar'],
];

export const ConsolidationIntakeDialog = ({ groups, assignees, onCreated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [people, setPeople] = useState([]);
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ entry_mode: 'visitor_followup', person_id: '', front_group_id: '', mentor_person_id: '', source_cell_id: '', next_followup_at: '', initial_result: '' });
  useEffect(() => {
    if (!open) return;
    axios.get(`${API}/api/core/persons?limit=100`, getAuthHeaders()).then((response) => setPeople(response.data.items || [])).catch(() => setPeople([]));
  }, [API, getAuthHeaders, open]);
  const visible = people.filter((person) => `${person.nombre} ${person.apellido} ${person.person_number}`.toLowerCase().includes(search.toLowerCase()));
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      const payload = { ...form, front_group_id: form.front_group_id || null, mentor_person_id: form.mentor_person_id || null, source_cell_id: form.source_cell_id || null, next_followup_at: form.next_followup_at ? new Date(form.next_followup_at).toISOString() : null };
      await axios.post(`${API}/api/processes/consolidation/intakes`, payload, getAuthHeaders());
      toast.success('Ruta de Consolidación creada'); setOpen(false); await onCreated();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo iniciar la ruta'); } finally { setSaving(false); }
  };
  const needsMentor = form.entry_mode !== 'visitor_followup';
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button className="bg-amber-600 text-white hover:bg-amber-700" data-testid="open-consolidation-intake-button"><UserPlus className="h-4 w-4" />Nueva ruta</Button></DialogTrigger>
    <DialogContent className="max-h-[88vh] max-w-2xl overflow-y-auto bg-white" data-testid="consolidation-intake-dialog">
      <DialogHeader><DialogTitle className="flex items-center gap-2"><Route className="h-5 w-5 text-amber-600" />Iniciar ruta de Consolidación</DialogTitle><DialogDescription>Seleccione una Persona 360 existente, conserve su puerta de entrada y asigne responsabilidad.</DialogDescription></DialogHeader>
      <form onSubmit={submit} className="space-y-5">
        <div className="grid gap-2 sm:grid-cols-2">{modes.map(([value, title, detail]) => <button type="button" key={value} onClick={() => update('entry_mode', value)} className={`border p-3 text-left transition-colors ${form.entry_mode === value ? 'border-amber-500 bg-amber-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`} data-testid={`entry-mode-${value}`}><b className="block text-sm">{title}</b><span className="text-xs text-slate-500">{detail}</span></button>)}</div>
        <div className="space-y-2"><Label htmlFor="intake-person-search">Buscar Persona</Label><Input id="intake-person-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Nombre o número VV" data-testid="consolidation-person-search-input" /></div>
        <div className="space-y-2"><Label>Persona 360</Label><Select value={form.person_id} onValueChange={(value) => update('person_id', value)}><SelectTrigger data-testid="consolidation-person-select"><SelectValue placeholder="Seleccionar Persona" /></SelectTrigger><SelectContent className="max-h-64 bg-white">{visible.map((person) => <SelectItem key={person.person_id} value={person.person_id}>{person.nombre} {person.apellido} · {person.person_number}</SelectItem>)}</SelectContent></Select></div>
        <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><Label>Grupo Frontal</Label><Select value={form.front_group_id || 'none'} onValueChange={(value) => update('front_group_id', value === 'none' ? '' : value)}><SelectTrigger data-testid="consolidation-front-group-select"><SelectValue placeholder="Sin Grupo Frontal" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="none">Sin Grupo Frontal</SelectItem>{groups.map((group) => <SelectItem key={group.front_group_id} value={group.front_group_id}>{group.name}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label>Mentor {needsMentor ? '*' : '(al responder)'}</Label><Select value={form.mentor_person_id || 'none'} onValueChange={(value) => update('mentor_person_id', value === 'none' ? '' : value)}><SelectTrigger data-testid="consolidation-mentor-select"><SelectValue placeholder="Seleccionar mentor" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="none">Pendiente</SelectItem>{assignees.map((item) => <SelectItem key={item.person_id} value={item.person_id}>{item.name}</SelectItem>)}</SelectContent></Select></div></div>
        {form.entry_mode === 'cell' && <div className="space-y-2"><Label htmlFor="source-cell-id">Célula de origen</Label><Input id="source-cell-id" value={form.source_cell_id} onChange={(event) => update('source_cell_id', event.target.value)} data-testid="consolidation-source-cell-input" /></div>}
        {form.entry_mode === 'visitor_followup' && <div className="space-y-2"><Label htmlFor="followup-at">Próximo seguimiento</Label><Input id="followup-at" type="datetime-local" value={form.next_followup_at} onChange={(event) => update('next_followup_at', event.target.value)} data-testid="consolidation-followup-date-input" /></div>}
        <div className="space-y-2"><Label htmlFor="initial-result">Nota o resultado inicial</Label><Input id="initial-result" value={form.initial_result} onChange={(event) => update('initial_result', event.target.value)} data-testid="consolidation-initial-result-input" /></div>
        <Button className="w-full bg-slate-900 text-white hover:bg-slate-800" disabled={saving || !form.person_id || needsMentor && !form.mentor_person_id || form.entry_mode === 'cell' && !form.source_cell_id} data-testid="consolidation-intake-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Iniciar ruta</Button>
      </form>
    </DialogContent>
  </Dialog>;
};