import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, PackagePlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';

export const ReceiveInventoryDialog = ({ onReceived }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [books, setBooks] = useState([]);
  const [form, setForm] = useState({ book_id: '', quantity: '10', notes: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) axios.get(`${API}/api/library/books`, getAuthHeaders()).then((r) => setBooks(r.data.items || [])); }, [open, API]);

  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      await axios.post(`${API}/api/library/movements`, { book_id: form.book_id, movement_type: 'PURCHASE_RECEIPT', quantity: Number(form.quantity), to_holder: { type: 'warehouse', id: 'central' }, notes: form.notes }, getAuthHeaders());
      toast.success('Inventario recibido en Central'); setOpen(false); await onReceived();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo registrar la recepción'); }
    finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline" data-testid="open-receive-inventory-button"><PackagePlus className="h-4 w-4" />Recibir inventario</Button></DialogTrigger>
    <DialogContent data-testid="receive-inventory-dialog"><DialogHeader><DialogTitle>Recibir inventario en Central</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="space-y-3">
        <div><Label>Material</Label><Select value={form.book_id} onValueChange={(v) => setForm({ ...form, book_id: v })}><SelectTrigger data-testid="receive-inventory-book-select"><SelectValue placeholder="Seleccione material" /></SelectTrigger><SelectContent className="bg-white">{books.map((b) => <SelectItem key={b.book_id} value={b.book_id}>{b.name}</SelectItem>)}</SelectContent></Select></div>
        <div><Label>Cantidad recibida</Label><Input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} data-testid="receive-inventory-quantity-input" /></div>
        <div><Label>Notas (proveedor, factura, etc.)</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="receive-inventory-notes-input" /></div>
        <Button type="submit" disabled={saving || !form.book_id} className="w-full bg-[#132443]" data-testid="confirm-receive-inventory-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Registrar recepción</Button>
      </form>
    </DialogContent>
  </Dialog>;
};
