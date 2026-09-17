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

export const LeadershipRequirementDialog = ({ onCreated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', source_type: 'manual', order: 10 });
  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try { await axios.post(`${API}/api/leadership/requirements`, { ...form, order: Number(form.order), required: true, active: true }, getAuthHeaders()); toast.success('Requisito añadido'); setOpen(false); await onCreated(); }
    catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo crear el requisito'); }
    finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button size="sm" variant="outline" data-testid="open-leadership-requirement-dialog"><Plus className="h-4 w-4" />Añadir requisito</Button></DialogTrigger><DialogContent className="max-w-lg bg-white" data-testid="leadership-requirement-dialog"><DialogHeader><DialogTitle>Nuevo requisito</DialogTitle><DialogDescription>Los requisitos viven en catálogo y pueden cambiar sin modificar código.</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4"><div className="space-y-2"><Label htmlFor="leadership-requirement-name">Nombre</Label><Input id="leadership-requirement-name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} data-testid="leadership-requirement-name-input" /></div><div className="space-y-2"><Label htmlFor="leadership-requirement-description">Descripción</Label><Textarea id="leadership-requirement-description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} data-testid="leadership-requirement-description-input" /></div><div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label>Fuente</Label><Select value={form.source_type} onValueChange={(value) => setForm({ ...form, source_type: value })}><SelectTrigger data-testid="leadership-requirement-source-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="manual">Evaluación manual</SelectItem><SelectItem value="membership_active">Membresía activa</SelectItem><SelectItem value="formation_completed">Formación completada</SelectItem><SelectItem value="cap_completed">CAP completado</SelectItem><SelectItem value="ministry_service_active">Servicio activo</SelectItem></SelectContent></Select></div><div className="space-y-2"><Label htmlFor="leadership-requirement-order">Orden</Label><Input id="leadership-requirement-order" type="number" min="1" value={form.order} onChange={(event) => setForm({ ...form, order: event.target.value })} data-testid="leadership-requirement-order-input" /></div></div><Button className="w-full bg-slate-900 text-white" disabled={saving || form.name.trim().length < 2} data-testid="leadership-requirement-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Guardar requisito</Button></form></DialogContent></Dialog>;
};