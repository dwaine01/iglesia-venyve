import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Check, Loader2, Route, Search, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const modes = [
  ['complete_cycle', 'Ciclo completo', 'Oración e Invasión'], ['direct_church', 'Entrada directa', 'Desde la iglesia'],
  ['cell', 'Desde célula', 'Conserva célula de origen'], ['visitor_followup', 'Visitante', 'Seguimiento antes de iniciar'],
];

export const ConsolidationIntakeDialog = ({ groups, assignees, onCreated, canAssign = false, routing = null }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false); const [people, setPeople] = useState([]);
  const [search, setSearch] = useState(''); const [searching, setSearching] = useState(false);
  const [selectedName, setSelectedName] = useState(''); const [saving, setSaving] = useState(false);
  const [cells, setCells] = useState([]);
  const [form, setForm] = useState({ entry_mode: 'visitor_followup', person_id: '', front_group_id: '', mentor_person_id: '', source_cell_id: '', next_followup_at: '', initial_result: '', assignment_reason: 'Confirmación de Consolidación' });
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    if (!open || search.trim().length < 2 || selectedName === search) { setPeople([]); return undefined; }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const response = await axios.get(`${API}/api/processes/consolidation/intake-candidates`, { ...getAuthHeaders(), params: { search: search.trim(), limit: 20 } });
        setPeople(response.data.items || []);
      } catch (error) { toast.error(apiErrorMessage(error, 'No se pudieron buscar Personas')); setPeople([]); }
      finally { setSearching(false); }
    }, 250);
    return () => clearTimeout(timer);
  }, [API, getAuthHeaders, open, search, selectedName]);
  useEffect(() => { if (!open) return; axios.get(`${API}/api/cellular/cells`, getAuthHeaders()).then((response) => setCells(response.data.items || [])).catch(() => setCells([])); }, [API, getAuthHeaders, open]);
  useEffect(() => { if (open && canAssign && routing?.week?.selected_group_id) update('front_group_id', routing.week.selected_group_id); }, [canAssign, open, routing]); // eslint-disable-line react-hooks/exhaustive-deps

  const choosePerson = (person) => {
    update('person_id', person.person_id); setSelectedName(person.name); setSearch(person.name); setPeople([]);
  };
  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      const payload = { ...form, front_group_id: form.front_group_id || null, mentor_person_id: form.mentor_person_id || null, source_cell_id: form.source_cell_id || null, routing_policy_id: routing?.policy?.policy_id || null, next_followup_at: form.next_followup_at ? new Date(form.next_followup_at).toISOString() : null };
      await axios.post(`${API}/api/processes/consolidation/intakes`, payload, getAuthHeaders());
      toast.success('Ruta de Consolidación creada'); setOpen(false); await onCreated();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo iniciar la ruta')); } finally { setSaving(false); }
  };
  const needsMentor = form.entry_mode !== 'visitor_followup';
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button className="bg-amber-600 text-white hover:bg-amber-700" data-testid="open-consolidation-intake-button"><UserPlus className="h-4 w-4" />Nueva ruta</Button></DialogTrigger>
    <DialogContent className="max-h-[88vh] max-w-2xl overflow-y-auto bg-white" data-testid="consolidation-intake-dialog">
      <DialogHeader><DialogTitle className="flex items-center gap-2"><Route className="h-5 w-5 text-amber-600" />Iniciar ruta de Consolidación</DialogTitle><DialogDescription>Busque una Persona 360 elegible y asigne su puerta de entrada.</DialogDescription></DialogHeader>
      <form onSubmit={submit} className="space-y-5">
        <div className="grid gap-2 sm:grid-cols-2">{modes.map(([value, title, detail]) => <button type="button" key={value} onClick={() => update('entry_mode', value)} className={`border p-3 text-left transition-colors ${form.entry_mode === value ? 'border-amber-500 bg-amber-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`} data-testid={`entry-mode-${value}`}><b className="block text-sm">{title}</b><span className="text-xs text-slate-500">{detail}</span></button>)}</div>
        <div className="relative space-y-2"><Label htmlFor="intake-person-search">Persona 360</Label><div className="relative"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input id="intake-person-search" className="pl-9 pr-9" value={search} onChange={(event) => { setSearch(event.target.value); setSelectedName(''); update('person_id', ''); }} placeholder="Escriba nombre, teléfono o número VV" autoComplete="off" data-testid="consolidation-autocomplete-input" />{searching && <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-amber-600" data-testid="consolidation-autocomplete-loading" />}</div>{people.length > 0 && <div className="absolute z-50 mt-1 max-h-64 w-full overflow-y-auto border bg-white shadow-xl" data-testid="consolidation-autocomplete-results">{people.map((person) => <button type="button" key={person.person_id} onClick={() => choosePerson(person)} className="flex w-full items-center justify-between border-b px-3 py-3 text-left hover:bg-amber-50" data-testid={`consolidation-candidate-${person.person_id}`}><span><b className="block text-sm">{person.name}</b><small className="text-slate-500">{person.person_number}{person.phone ? ` · ${person.phone}` : ''}</small></span><Check className="h-4 w-4 text-amber-700" /></button>)}</div>}{search.trim().length >= 2 && !searching && people.length === 0 && !form.person_id && <p className="text-xs text-slate-500" data-testid="consolidation-autocomplete-empty">No hay Personas elegibles con esa búsqueda.</p>}</div>
        <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><Label>Grupo Frontal</Label><Select value={form.front_group_id || 'none'} onValueChange={(value) => update('front_group_id', value === 'none' ? '' : value)}><SelectTrigger data-testid="consolidation-front-group-select"><SelectValue placeholder="Sin Grupo Frontal" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="none">Sin Grupo Frontal</SelectItem>{groups.map((group) => <SelectItem key={group.front_group_id} value={group.front_group_id}>{group.name}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label>Mentor {needsMentor ? '*' : '(al responder)'}</Label><Select value={form.mentor_person_id || 'none'} onValueChange={(value) => update('mentor_person_id', value === 'none' ? '' : value)}><SelectTrigger data-testid="consolidation-mentor-select"><SelectValue placeholder="Seleccionar mentor" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="none">Pendiente</SelectItem>{assignees.map((item) => <SelectItem key={item.person_id} value={item.person_id}>{item.name}</SelectItem>)}</SelectContent></Select></div></div>
        {form.entry_mode === 'cell' && <div className="space-y-2"><Label>Célula de origen</Label><Select value={form.source_cell_id} onValueChange={(value) => update('source_cell_id', value)}><SelectTrigger data-testid="consolidation-source-cell-select"><SelectValue placeholder="Seleccionar Célula" /></SelectTrigger><SelectContent className="bg-white">{cells.map((cell) => <SelectItem key={cell.cell_id} value={cell.cell_id}>{cell.name || cell.cell_name || cell.cell_id}</SelectItem>)}</SelectContent></Select></div>}
        {canAssign && form.front_group_id && routing?.week?.selected_group_id !== form.front_group_id && <div className="space-y-2"><Label htmlFor="intake-assignment-reason">Motivo de modificación</Label><Input id="intake-assignment-reason" value={form.assignment_reason} onChange={(event) => update('assignment_reason', event.target.value)} data-testid="consolidation-assignment-reason-input" /></div>}
        {form.entry_mode === 'visitor_followup' && <div className="space-y-2"><Label htmlFor="followup-at">Próximo seguimiento</Label><Input id="followup-at" type="datetime-local" value={form.next_followup_at} onChange={(event) => update('next_followup_at', event.target.value)} data-testid="consolidation-followup-date-input" /></div>}
        <div className="space-y-2"><Label htmlFor="initial-result">Nota o resultado inicial</Label><Input id="initial-result" value={form.initial_result} onChange={(event) => update('initial_result', event.target.value)} data-testid="consolidation-initial-result-input" /></div>
        <Button className="w-full bg-slate-900 text-white hover:bg-slate-800" disabled={saving || !form.person_id || (needsMentor && !form.mentor_person_id && !canAssign) || (form.entry_mode === 'cell' && !form.source_cell_id)} data-testid="consolidation-intake-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Iniciar ruta</Button>
      </form>
    </DialogContent>
  </Dialog>;
};