import React, { useState } from 'react';
import axios from 'axios';
import { ClipboardPlus, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';

export const FrontGroupTaskDialog = ({ group, onCreated }) => {
  const { API, getAuthHeaders } = useAuth(); const [open, setOpen] = useState(false); const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ title: '', description: '', due_at: '', reason: 'Asignación directa del Grupo Frontal' });
  const submit = async (event) => { event.preventDefault(); setSaving(true); try { await axios.post(`${API}/api/front-group-work`, { ...form, source_type: 'direct_task', assigned_group_id: group.front_group_id, due_at: form.due_at ? new Date(form.due_at).toISOString() : null }, getAuthHeaders()); toast.success('Tarea asignada al Grupo'); setOpen(false); setForm({ title: '', description: '', due_at: '', reason: 'Asignación directa del Grupo Frontal' }); await onCreated(); } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo crear la tarea')); } finally { setSaving(false); } };
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button variant="outline" data-testid="front-group-new-task-button"><ClipboardPlus className="h-4 w-4" />Nueva tarea</Button></DialogTrigger><DialogContent className="bg-white" data-testid="front-group-task-dialog"><DialogHeader><DialogTitle>Asignar tarea al Grupo</DialogTitle><DialogDescription>{group.name}</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4"><div><Label htmlFor="fg-task-title">Título</Label><Input id="fg-task-title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} data-testid="front-group-task-title-input" /></div><div><Label htmlFor="fg-task-description">Detalle operativo</Label><Textarea id="fg-task-description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} data-testid="front-group-task-description-input" /></div><div><Label htmlFor="fg-task-due">Fecha límite</Label><Input id="fg-task-due" type="datetime-local" value={form.due_at} onChange={(event) => setForm({ ...form, due_at: event.target.value })} data-testid="front-group-task-due-input" /></div><Button type="submit" className="w-full bg-slate-900" disabled={saving || form.title.trim().length < 2} data-testid="front-group-task-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Asignar tarea</Button></form></DialogContent></Dialog>;
};