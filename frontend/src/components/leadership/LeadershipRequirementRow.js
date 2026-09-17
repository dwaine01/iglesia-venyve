import React, { useState } from 'react';
import axios from 'axios';
import { Pencil, Power, Save, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';

export const LeadershipRequirementRow = ({ item, canManage, onUpdated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(item);
  const save = async () => {
    try { await axios.put(`${API}/api/leadership/requirements/${item.requirement_id}`, { name: form.name, description: form.description || null, source_type: form.source_type, required: form.required, active: form.active, order: Number(form.order) }, getAuthHeaders()); toast.success('Requisito actualizado'); setOpen(false); await onUpdated(); }
    catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo actualizar'); }
  };
  const remove = async () => { try { await axios.delete(`${API}/api/leadership/requirements/${item.requirement_id}`, getAuthHeaders()); toast.success('Requisito retirado'); await onUpdated(); } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo retirar'); } };
  return <article className={`border p-3 ${item.active ? 'bg-white' : 'bg-slate-50 opacity-70'}`} data-testid={`leadership-requirement-row-${item.requirement_id}`}><div className="flex justify-between gap-2"><div><b className="text-sm">{item.name}</b><p className="text-xs text-slate-500">{item.source_type} · {item.required ? 'obligatorio' : 'informativo'} · {item.active ? 'activo' : 'inactivo'}</p></div>{canManage && <div className="flex gap-1"><Button size="icon" variant="ghost" onClick={() => axios.put(`${API}/api/leadership/requirements/${item.requirement_id}`, { active: !item.active }, getAuthHeaders()).then(onUpdated)} data-testid={`toggle-leadership-requirement-${item.requirement_id}`}><Power className="h-4 w-4" /><span className="sr-only">Cambiar estado</span></Button><Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button size="icon" variant="ghost" data-testid={`edit-leadership-requirement-${item.requirement_id}`}><Pencil className="h-4 w-4" /><span className="sr-only">Editar</span></Button></DialogTrigger><DialogContent className="bg-white"><DialogHeader><DialogTitle>Editar requisito</DialogTitle></DialogHeader><div className="space-y-3"><div><Label>Nombre</Label><Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} data-testid="edit-requirement-name-input" /></div><div><Label>Descripción</Label><Textarea value={form.description || ''} onChange={(event) => setForm({ ...form, description: event.target.value })} data-testid="edit-requirement-description-input" /></div><Select value={form.source_type} onValueChange={(value) => setForm({ ...form, source_type: value })}><SelectTrigger data-testid="edit-requirement-source-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="manual">Manual</SelectItem><SelectItem value="membership_active">Membresía</SelectItem><SelectItem value="formation_completed">Formación</SelectItem><SelectItem value="cap_completed">CAP</SelectItem><SelectItem value="ministry_service_active">Servicio</SelectItem></SelectContent></Select><label className="flex items-center gap-2 text-sm"><Checkbox checked={form.required} onCheckedChange={(checked) => setForm({ ...form, required: checked })} data-testid="edit-requirement-required-checkbox" />Obligatorio</label><Button className="w-full" onClick={save} data-testid="save-requirement-edit-button"><Save className="h-4 w-4" />Guardar cambios</Button></div></DialogContent></Dialog><Button size="icon" variant="ghost" onClick={remove} data-testid={`delete-leadership-requirement-${item.requirement_id}`}><Trash2 className="h-4 w-4 text-red-600" /><span className="sr-only">Retirar</span></Button></div>}</div></article>;
};