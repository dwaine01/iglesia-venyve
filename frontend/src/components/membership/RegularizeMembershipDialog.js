import React, { useState } from 'react';
import axios from 'axios';
import { BadgeCheck, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';

export const RegularizeMembershipDialog = ({ personId, onChanged }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ existing_member_number: '', historical_membership_date: '', historical_date_precision: 'unknown', reason: '' });
  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      await axios.post(`${API}/api/membership/persons/${personId}/regularize`, { ...form, existing_member_number: form.existing_member_number || null, historical_membership_date: form.historical_membership_date || null, historical_date_precision: form.historical_membership_date ? form.historical_date_precision : 'unknown' }, getAuthHeaders());
      toast.success('Membresía histórica regularizada'); setOpen(false); await onChanged();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo regularizar la membresía'); }
    finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button data-testid="open-regularize-membership-button"><BadgeCheck className="h-4 w-4" />Activar / Regularizar membresía existente</Button></DialogTrigger>
    <DialogContent data-testid="regularize-membership-dialog"><DialogHeader><DialogTitle>Regularizar miembro existente</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-slate-600">Activa la membresía sin fabricar Consolidación, firma ni cursos anteriores.</p>
        <div className="space-y-2"><Label>Número histórico, si existe</Label><Input value={form.existing_member_number} onChange={(event) => setForm({ ...form, existing_member_number: event.target.value })} data-testid="regularization-member-number-input" /></div>
        <div className="grid gap-3 sm:grid-cols-2"><div className="space-y-2"><Label>Fecha histórica conocida</Label><Input type="date" value={form.historical_membership_date} onChange={(event) => setForm({ ...form, historical_membership_date: event.target.value })} data-testid="regularization-date-input" /></div><div className="space-y-2"><Label>Precisión</Label><Select value={form.historical_date_precision} onValueChange={(value) => setForm({ ...form, historical_date_precision: value })} disabled={!form.historical_membership_date}><SelectTrigger data-testid="regularization-date-precision-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="exact">Fecha exacta</SelectItem><SelectItem value="month">Mes aproximado</SelectItem><SelectItem value="year">Año aproximado</SelectItem><SelectItem value="unknown">Desconocida</SelectItem></SelectContent></Select></div></div>
        <div className="space-y-2"><Label>Motivo / evidencia de regularización</Label><Textarea required minLength={3} value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} data-testid="regularization-reason-input" /></div>
        <Button type="submit" disabled={saving} className="w-full" data-testid="confirm-regularize-membership-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Confirmar regularización</Button>
      </form>
    </DialogContent>
  </Dialog>;
};