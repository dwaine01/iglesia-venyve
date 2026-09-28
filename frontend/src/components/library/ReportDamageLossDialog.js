import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { AlertOctagon, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';

export const ReportDamageLossDialog = ({ onReported }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [books, setBooks] = useState([]);
  const [form, setForm] = useState({ book_id: '', movement_type: 'DAMAGE', quantity: '1', notes: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) axios.get(`${API}/api/library/books`, getAuthHeaders()).then((r) => setBooks(r.data.items || [])); }, [open, API]);

  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      await axios.post(`${API}/api/library/movements`, { book_id: form.book_id, movement_type: form.movement_type, quantity: Number(form.quantity), from_holder: { type: 'warehouse', id: 'central' }, notes: form.notes }, getAuthHeaders());
      toast.success('Registrado'); setOpen(false); await onReported();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo registrar'); }
    finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline" data-testid="open-damage-loss-button"><AlertOctagon className="h-4 w-4" />Dañado / perdido</Button></DialogTrigger>
    <DialogContent data-testid="damage-loss-dialog"><DialogHeader><DialogTitle>Reportar material dañado o perdido (desde Central)</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="space-y-3">
        <div><Label>Material</Label><Select value={form.book_id} onValueChange={(v) => setForm({ ...form, book_id: v })}><SelectTrigger data-testid="damage-loss-book-select"><SelectValue placeholder="Seleccione material" /></SelectTrigger><SelectContent className="bg-white">{books.map((b) => <SelectItem key={b.book_id} value={b.book_id}>{b.name}</SelectItem>)}</SelectContent></Select></div>
        <div><Label>Tipo</Label><Select value={form.movement_type} onValueChange={(v) => setForm({ ...form, movement_type: v })}><SelectTrigger data-testid="damage-loss-type-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="DAMAGE">Dañado</SelectItem><SelectItem value="LOSS">Perdido</SelectItem></SelectContent></Select></div>
        <div><Label>Cantidad</Label><Input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} data-testid="damage-loss-quantity-input" /></div>
        <div><Label>Observación</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="damage-loss-notes-input" /></div>
        <Button type="submit" disabled={saving || !form.book_id} className="w-full bg-[#132443]" data-testid="confirm-damage-loss-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Registrar</Button>
      </form>
    </DialogContent>
  </Dialog>;
};
