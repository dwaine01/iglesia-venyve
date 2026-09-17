import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, Plus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';

export const FrontGroupDialog = ({ onCreated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', link_type: '', link_id: '', link_label: '' });
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      const linked_structures = form.link_type && form.link_id ? [{ type: form.link_type, id: form.link_id, label: form.link_label || null }] : [];
      await axios.post(`${API}/api/front-groups`, { name: form.name, description: form.description || null, linked_structures }, getAuthHeaders());
      toast.success('Grupo Frontal creado'); setOpen(false); await onCreated();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo crear el Grupo Frontal'); } finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button className="bg-amber-600 text-white hover:bg-amber-700" data-testid="open-front-group-dialog"><Plus className="h-4 w-4" />Nuevo Grupo Frontal</Button></DialogTrigger><DialogContent className="max-w-xl bg-white" data-testid="front-group-dialog"><DialogHeader><DialogTitle>Crear Grupo Frontal</DialogTitle><DialogDescription>Estructura propia con scope independiente; puede enlazarse sin convertirse en Red, Ministerio, Puerta o Célula.</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4"><div className="space-y-2"><Label htmlFor="front-group-name">Nombre</Label><Input id="front-group-name" value={form.name} onChange={(event) => update('name', event.target.value)} data-testid="front-group-name-input" /></div><div className="space-y-2"><Label htmlFor="front-group-description">Descripción</Label><Textarea id="front-group-description" value={form.description} onChange={(event) => update('description', event.target.value)} data-testid="front-group-description-input" /></div><div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label>Estructura enlazada</Label><Select value={form.link_type || 'none'} onValueChange={(value) => update('link_type', value === 'none' ? '' : value)}><SelectTrigger data-testid="front-group-link-type-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="none">Ninguna</SelectItem><SelectItem value="network">Red</SelectItem><SelectItem value="ministry">Ministerio</SelectItem><SelectItem value="door">Puerta</SelectItem><SelectItem value="cell">Célula</SelectItem></SelectContent></Select></div><div className="space-y-2"><Label htmlFor="front-group-link-id">ID relacionado</Label><Input id="front-group-link-id" value={form.link_id} onChange={(event) => update('link_id', event.target.value)} disabled={!form.link_type} data-testid="front-group-link-id-input" /></div></div><Button className="w-full bg-slate-900 text-white" disabled={saving || form.name.trim().length < 2} data-testid="front-group-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Crear Grupo Frontal</Button></form></DialogContent></Dialog>;
};