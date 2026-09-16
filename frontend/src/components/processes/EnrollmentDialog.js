import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, UserPlus } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { roleLabel } from '../../lib/displayLabels';

export const EnrollmentDialog = ({ processKey, cycles = [], assignees = [], onCreated, triggerLabel = 'Inscribir Persona' }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [people, setPeople] = useState([]);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [form, setForm] = useState({ person_id: '', cycle_id: '', responsible_person_id: '', next_action: '', next_action_at: '' });
  useEffect(() => {
    if (!open) return;
    axios.get(`${API}/api/core/persons?limit=100`, getAuthHeaders()).then((response) => setPeople(response.data.items || [])).catch(() => setPeople([]));
  }, [API, getAuthHeaders, open]);
  const visible = people.filter((item) => `${item.nombre} ${item.apellido} ${item.person_number}`.toLowerCase().includes(search.toLowerCase()));
  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      await axios.post(`${API}/api/processes/enrollments`, { process_key: processKey, person_id: form.person_id, cycle_id: processKey === 'seven_weeks' ? form.cycle_id : null, responsible_person_id: form.responsible_person_id || null, next_action: form.next_action || null, next_action_at: form.next_action_at ? new Date(form.next_action_at).toISOString() : null }, getAuthHeaders());
      toast.success('Persona inscrita desde su Perfil 360'); setOpen(false); setForm({ person_id: '', cycle_id: '', responsible_person_id: '', next_action: '', next_action_at: '' }); await onCreated();
    } catch (error) { toast.error(typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : error?.response?.data?.detail?.message || 'No se pudo crear la inscripción'); } finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button className="bg-amber-600 text-white hover:bg-amber-700" data-testid={`open-${processKey}-enrollment-button`}><UserPlus className="mr-2 h-4 w-4" />{triggerLabel}</Button></DialogTrigger><DialogContent className="max-w-xl bg-white"><DialogHeader><DialogTitle>Inscribir Persona</DialogTitle><DialogDescription>Seleccione un Perfil 360 existente. Este proceso nunca crea una identidad paralela.</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4">
    <div className="space-y-2"><Label htmlFor="process-person-search">Buscar Persona</Label><Input id="process-person-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Nombre o número VV" data-testid="process-person-search-input" /></div>
    <div className="space-y-2"><Label>Perfil 360</Label><Select value={form.person_id} onValueChange={(value) => setForm((old) => ({ ...old, person_id: value }))}><SelectTrigger data-testid="process-person-select"><SelectValue placeholder="Seleccionar Persona" /></SelectTrigger><SelectContent className="max-h-64 bg-white">{visible.map((item) => <SelectItem key={item.person_id} value={item.person_id}>{item.nombre} {item.apellido} · {item.person_number}</SelectItem>)}</SelectContent></Select></div>
    {processKey === 'seven_weeks' && <div className="space-y-2"><Label>Ciclo</Label><Select value={form.cycle_id} onValueChange={(value) => setForm((old) => ({ ...old, cycle_id: value }))}><SelectTrigger data-testid="process-cycle-select"><SelectValue placeholder="Seleccionar ciclo" /></SelectTrigger><SelectContent className="bg-white">{cycles.filter((item) => ['planned', 'active'].includes(item.status)).map((item) => <SelectItem key={item.cycle_id} value={item.cycle_id}>{item.name}</SelectItem>)}</SelectContent></Select></div>}
    <div className="space-y-2"><Label>Responsable</Label><Select value={form.responsible_person_id} onValueChange={(value) => setForm((old) => ({ ...old, responsible_person_id: value }))}><SelectTrigger data-testid="process-responsible-select"><SelectValue placeholder="Asignar responsable" /></SelectTrigger><SelectContent className="bg-white">{assignees.map((item) => <SelectItem key={item.person_id} value={item.person_id}>{item.name} · {roleLabel(item.role)}</SelectItem>)}</SelectContent></Select></div>
    <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label htmlFor="process-next-action">Próxima acción</Label><Input id="process-next-action" value={form.next_action} onChange={(event) => setForm((old) => ({ ...old, next_action: event.target.value }))} data-testid="process-next-action-input" /></div><div className="space-y-2"><Label htmlFor="process-next-date">Fecha</Label><Input id="process-next-date" type="datetime-local" value={form.next_action_at} onChange={(event) => setForm((old) => ({ ...old, next_action_at: event.target.value }))} data-testid="process-next-action-date-input" /></div></div>
    <Button type="submit" disabled={saving || !form.person_id || (processKey === 'seven_weeks' && !form.cycle_id)} className="w-full bg-slate-900 text-white hover:bg-slate-800" data-testid="process-enrollment-submit-button">{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Crear inscripción</Button>
  </form></DialogContent></Dialog>;
};