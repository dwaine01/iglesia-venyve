import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Send } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';

export const TransferBookDialog = ({ onTransferred }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [books, setBooks] = useState([]);
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ book_id: '', to_user_id: '', quantity: '5', notes: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    axios.get(`${API}/api/library/books`, { ...getAuthHeaders(), params: { active: true } }).then((r) => setBooks(r.data.items || []));
    axios.get(`${API}/api/core/governance/users`, getAuthHeaders()).then((r) => setUsers(r.data.items || []));
  }, [open, API]);

  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      await axios.post(`${API}/api/library/movements`, { book_id: form.book_id, movement_type: 'TRANSFER', quantity: Number(form.quantity), from_holder: { type: 'warehouse', id: 'central' }, to_holder: { type: 'user', id: form.to_user_id }, notes: form.notes }, getAuthHeaders());
      toast.success('Materiales transferidos'); setOpen(false); await onTransferred();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo transferir'); }
    finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline" data-testid="open-transfer-book-button"><Send className="h-4 w-4" />Transferir a líder</Button></DialogTrigger>
    <DialogContent data-testid="transfer-book-dialog"><DialogHeader><DialogTitle>Transferir de Central a un líder</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="space-y-3">
        <div><Label>Material</Label><Select value={form.book_id} onValueChange={(v) => setForm({ ...form, book_id: v })}><SelectTrigger data-testid="transfer-book-select"><SelectValue placeholder="Seleccione material" /></SelectTrigger><SelectContent className="bg-white">{books.map((b) => <SelectItem key={b.book_id} value={b.book_id}>{b.name}</SelectItem>)}</SelectContent></Select></div>
        <div><Label>Líder / responsable</Label><Select value={form.to_user_id} onValueChange={(v) => setForm({ ...form, to_user_id: v })}><SelectTrigger data-testid="transfer-book-user-select"><SelectValue placeholder="Seleccione responsable" /></SelectTrigger><SelectContent className="bg-white">{users.map((u) => <SelectItem key={u.user_id} value={u.user_id}>{u.nombre} · {u.email}</SelectItem>)}</SelectContent></Select></div>
        <div><Label>Cantidad</Label><Input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} data-testid="transfer-book-quantity-input" /></div>
        <div><Label>Notas</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="transfer-book-notes-input" /></div>
        <Button type="submit" disabled={saving || !form.book_id || !form.to_user_id} className="w-full bg-[#132443]" data-testid="confirm-transfer-book-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Transferir</Button>
      </form>
    </DialogContent>
  </Dialog>;
};
