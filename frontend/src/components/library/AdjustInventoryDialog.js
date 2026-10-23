import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, SlidersHorizontal } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';

export const AdjustInventoryDialog = ({ onAdjusted }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [books, setBooks] = useState([]);
  const [form, setForm] = useState({ book_id: '', direction: 'increase', quantity: '1', reason: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) axios.get(`${API}/api/library/books`, getAuthHeaders()).then((r) => setBooks(r.data.items || [])); }, [open, API]);

  const submit = async (event) => {
    event.preventDefault();
    if (!form.reason.trim()) { toast.error('Indique el motivo del ajuste'); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/api/library/adjustments`, { book_id: form.book_id, direction: form.direction, quantity: Number(form.quantity), reason: form.reason }, getAuthHeaders());
      toast.success('Ajuste registrado'); setOpen(false); setForm({ book_id: '', direction: 'increase', quantity: '1', reason: '' }); await onAdjusted();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo registrar el ajuste'); }
    finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline" data-testid="open-adjust-inventory-button"><SlidersHorizontal className="h-4 w-4" />Ajustar existencias</Button></DialogTrigger>
    <DialogContent data-testid="adjust-inventory-dialog"><DialogHeader><DialogTitle>Ajustar existencias de Central</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="space-y-3">
        <div><Label>Material</Label><Select value={form.book_id} onValueChange={(v) => setForm({ ...form, book_id: v })}><SelectTrigger data-testid="adjust-inventory-book-select"><SelectValue placeholder="Seleccione material" /></SelectTrigger><SelectContent className="bg-white">{books.map((b) => <SelectItem key={b.book_id} value={b.book_id}>{b.name}</SelectItem>)}</SelectContent></Select></div>
        <div><Label>Dirección</Label><Select value={form.direction} onValueChange={(v) => setForm({ ...form, direction: v })}><SelectTrigger data-testid="adjust-inventory-direction-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="increase">Aumentar</SelectItem><SelectItem value="decrease">Disminuir</SelectItem></SelectContent></Select></div>
        <div><Label>Cantidad</Label><Input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} data-testid="adjust-inventory-quantity-input" /></div>
        <div><Label>Motivo (obligatorio)</Label><Textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} data-testid="adjust-inventory-reason-input" /></div>
        <Button type="submit" disabled={saving || !form.book_id} className="w-full bg-[#132443]" data-testid="confirm-adjust-inventory-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Registrar ajuste</Button>
      </form>
    </DialogContent>
  </Dialog>;
};
