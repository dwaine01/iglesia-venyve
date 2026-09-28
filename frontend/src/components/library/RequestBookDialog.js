import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ClipboardList, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { BookThumbnail } from './BookThumbnail';

export const RequestBookDialog = ({ onRequested }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [books, setBooks] = useState([]);
  const [form, setForm] = useState({ book_id: '', quantity: '10', notes: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) axios.get(`${API}/api/library/books`, { ...getAuthHeaders(), params: { active: true } }).then((r) => setBooks(r.data.items || [])); }, [open, API]);

  const selectedBook = books.find((b) => b.book_id === form.book_id);

  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      await axios.post(`${API}/api/library/requests`, { book_id: form.book_id, quantity: Number(form.quantity), notes: form.notes }, getAuthHeaders());
      toast.success('Solicitud enviada a Librería'); setOpen(false); await onRequested();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo enviar la solicitud'); }
    finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline" data-testid="open-request-book-button"><ClipboardList className="h-4 w-4" />Solicitar libros</Button></DialogTrigger>
    <DialogContent data-testid="request-book-dialog"><DialogHeader><DialogTitle>Solicitar materiales a Librería</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="space-y-3">
        <div><Label>Material</Label><Select value={form.book_id} onValueChange={(v) => setForm({ ...form, book_id: v })}><SelectTrigger data-testid="request-book-select"><SelectValue placeholder="Seleccione material" /></SelectTrigger><SelectContent className="bg-white">{books.map((b) => <SelectItem key={b.book_id} value={b.book_id}>{b.name}</SelectItem>)}</SelectContent></Select></div>
        {selectedBook && <p className="flex items-center gap-2 text-xs text-slate-500" data-testid="request-book-selected-preview"><BookThumbnail fileId={selectedBook.cover_file_id} size={28} />{selectedBook.name}</p>}
        <div><Label>Cantidad solicitada</Label><Input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} data-testid="request-book-quantity-input" /></div>
        <div><Label>Notas</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Ej. Grupo Frontal #4, 15 participantes nuevos" data-testid="request-book-notes-input" /></div>
        <Button type="submit" disabled={saving || !form.book_id} className="w-full bg-[#132443]" data-testid="confirm-request-book-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Enviar solicitud</Button>
      </form>
    </DialogContent>
  </Dialog>;
};
