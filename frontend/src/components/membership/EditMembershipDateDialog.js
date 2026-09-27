import React, { useState } from 'react';
import axios from 'axios';
import { CalendarClock, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { formatMembershipDate, membershipDate } from './membershipDocumentUtils';

export const EditMembershipDateDialog = ({ personId, membership, onChanged }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const currentDate = membership?.historical_membership_date || '';
  const [form, setForm] = useState({ historical_membership_date: currentDate, historical_date_precision: membership?.historical_date_precision || 'unknown', reason: '' });
  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      await axios.put(`${API}/api/membership/persons/${personId}/membership-date`, { ...form, historical_membership_date: form.historical_membership_date || null, historical_date_precision: form.historical_membership_date ? form.historical_date_precision : 'unknown' }, getAuthHeaders());
      toast.success('Fecha de membresía actualizada'); setOpen(false); await onChanged();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo actualizar la fecha'); }
    finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline" data-testid="open-edit-membership-date-button"><CalendarClock className="h-4 w-4" />Editar fecha de membresía</Button></DialogTrigger>
    <DialogContent data-testid="edit-membership-date-dialog"><DialogHeader><DialogTitle>Editar fecha de membresía</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-slate-600" data-testid="edit-membership-date-current">Fecha mostrada actualmente en el certificado: <strong>{formatMembershipDate(membershipDate(membership))}</strong></p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2"><Label>Fecha de ingreso / activación</Label><Input type="date" value={form.historical_membership_date} onChange={(event) => setForm({ ...form, historical_membership_date: event.target.value })} data-testid="edit-membership-date-input" /></div>
          <div className="space-y-2"><Label>Precisión</Label><Select value={form.historical_date_precision} onValueChange={(value) => setForm({ ...form, historical_date_precision: value })} disabled={!form.historical_membership_date}><SelectTrigger data-testid="edit-membership-date-precision-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="exact">Fecha exacta</SelectItem><SelectItem value="month">Mes aproximado</SelectItem><SelectItem value="year">Año aproximado</SelectItem><SelectItem value="unknown">Desconocida</SelectItem></SelectContent></Select></div>
        </div>
        <div className="space-y-2"><Label>Motivo del cambio (opcional)</Label><Textarea value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} data-testid="edit-membership-date-reason-input" /></div>
        <Button type="submit" disabled={saving} className="w-full" data-testid="confirm-edit-membership-date-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Guardar fecha</Button>
      </form>
    </DialogContent>
  </Dialog>;
};
