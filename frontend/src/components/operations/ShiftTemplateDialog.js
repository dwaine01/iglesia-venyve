import React, { useState } from 'react';
import { Clock3, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';

const initial = { name: '', role_name: '', scope: 'all_occurrences', start_offset_minutes: -60, duration_minutes: 180, required_volunteers: 2, instructions: '' };

export const ShiftTemplateDialog = ({ open, onOpenChange, onCreate, saving, error }) => {
  const [form, setForm] = useState(initial); const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));
  const submit = (event) => { event.preventDefault(); onCreate({ ...form, start_offset_minutes: Number(form.start_offset_minutes), duration_minutes: Number(form.duration_minutes), required_volunteers: Number(form.required_volunteers), instructions: form.instructions || null }); };
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="bg-white" data-testid="shift-template-dialog"><DialogHeader><DialogTitle className="flex items-center gap-2 font-['Spectral'] text-2xl"><Clock3 className="h-5 w-5 text-blue-700" />Nuevo turno</DialogTitle><DialogDescription>El turno se aplicará a cada ocurrencia presente y futura del evento.</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-4">
    {error && <p className="border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="shift-template-error">{error}</p>}
    <div className="grid gap-3 sm:grid-cols-2"><div><Label htmlFor="shift-name">Equipo *</Label><Input id="shift-name" required value={form.name} onChange={update('name')} placeholder="Recepción" data-testid="shift-name-input" /></div><div><Label htmlFor="shift-role">Rol *</Label><Input id="shift-role" required value={form.role_name} onChange={update('role_name')} placeholder="Anfitrión" data-testid="shift-role-input" /></div></div>
    <div className="grid grid-cols-3 gap-3"><div><Label htmlFor="shift-offset">Inicio (min)</Label><Input id="shift-offset" type="number" value={form.start_offset_minutes} onChange={update('start_offset_minutes')} data-testid="shift-offset-input" /></div><div><Label htmlFor="shift-duration">Duración</Label><Input id="shift-duration" type="number" min="15" value={form.duration_minutes} onChange={update('duration_minutes')} data-testid="shift-duration-input" /></div><div><Label htmlFor="shift-required">Cupos</Label><Input id="shift-required" type="number" min="1" value={form.required_volunteers} onChange={update('required_volunteers')} data-testid="shift-required-input" /></div></div>
    <div><Label htmlFor="shift-instructions">Instrucciones</Label><Textarea id="shift-instructions" value={form.instructions} onChange={update('instructions')} rows={3} data-testid="shift-instructions-input" /></div>
    <DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)} data-testid="shift-cancel-button">Cancelar</Button><Button type="submit" disabled={saving} className="bg-blue-700 hover:bg-blue-800" data-testid="shift-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Crear turno recurrente</Button></DialogFooter>
  </form></DialogContent></Dialog>;
};