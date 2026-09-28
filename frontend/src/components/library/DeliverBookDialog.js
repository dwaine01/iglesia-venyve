import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BookOpen, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { BookThumbnail } from './BookThumbnail';

const EMPTY = { book_id: '', quantity: '1', payment_status: 'no_aplica', amount_paid: '0', payment_method: 'efectivo', notes: '', as_loan: false, due_date: '' };

export const DeliverBookDialog = ({ personId, trigger, onDelivered }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [books, setBooks] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    axios.get(`${API}/api/library/books`, { ...getAuthHeaders(), params: { active: true } }).then((r) => setBooks(r.data.items || [])).catch(() => setBooks([]));
  }, [open, API]);

  const selectedBook = books.find((b) => b.book_id === form.book_id);

  const onSelectBook = (bookId) => {
    const book = books.find((b) => b.book_id === bookId);
    setForm((old) => ({ ...old, book_id: bookId, payment_status: book?.member_price_cents ? 'pendiente' : 'no_aplica', amount_paid: book?.member_price_cents ? String((book.member_price_cents / 100).toFixed(2)) : '0' }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.book_id) return toast.error('Seleccione un material');
    setSaving(true);
    try {
      await axios.post(`${API}/api/library/persons/${personId}/deliver`, {
        book_id: form.book_id, quantity: Number(form.quantity || 1), payment_status: form.payment_status,
        amount_paid_cents: form.payment_status === 'pagado' || form.payment_status === 'pago_parcial' ? Math.round(Number(form.amount_paid || 0) * 100) : 0,
        payment_method: form.payment_method, notes: form.notes, as_loan: form.as_loan, due_date: form.as_loan ? (form.due_date || null) : null,
      }, getAuthHeaders());
      toast.success('Material entregado y registrado en Persona 360');
      setForm(EMPTY); setOpen(false); await onDelivered();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo entregar el material'); }
    finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild>{trigger || <Button className="bg-[#132443]" data-testid="open-deliver-book-button"><BookOpen className="h-4 w-4" />Entregar libro</Button>}</DialogTrigger>
    <DialogContent data-testid="deliver-book-dialog">
      <DialogHeader><DialogTitle>Entregar material</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="space-y-3">
        <div><Label>Material</Label><Select value={form.book_id} onValueChange={onSelectBook}><SelectTrigger data-testid="deliver-book-select"><SelectValue placeholder="Seleccione un material" /></SelectTrigger><SelectContent className="bg-white">
          {books.map((book) => <SelectItem key={book.book_id} value={book.book_id}>{book.name}{book.member_price_cents ? ` · $${(book.member_price_cents / 100).toFixed(2)}` : ' · Gratis'}</SelectItem>)}
        </SelectContent></Select></div>
        <div className="grid grid-cols-2 gap-3">
          <div><Label>Cantidad</Label><Input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} data-testid="deliver-book-quantity-input" /></div>
          <div className="flex items-center gap-2 pt-6"><Checkbox checked={form.as_loan} onCheckedChange={(v) => setForm({ ...form, as_loan: Boolean(v) })} data-testid="deliver-book-loan-checkbox" /><Label>Es préstamo (debe regresar)</Label></div>
        </div>
        {form.as_loan && <div><Label>Fecha esperada de devolución</Label><Input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} data-testid="deliver-book-due-date-input" /></div>}
        <div className="grid grid-cols-2 gap-3">
          <div><Label>Estado de pago</Label><Select value={form.payment_status} onValueChange={(v) => setForm({ ...form, payment_status: v })}><SelectTrigger data-testid="deliver-book-payment-status-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">
            <SelectItem value="no_aplica">No aplica pago</SelectItem><SelectItem value="pagado">Pagado</SelectItem><SelectItem value="pendiente">Pendiente</SelectItem>
            <SelectItem value="exonerado">Exonerado</SelectItem><SelectItem value="beca">Beca</SelectItem><SelectItem value="descuento">Descuento autorizado</SelectItem><SelectItem value="pago_parcial">Pago parcial</SelectItem>
          </SelectContent></Select></div>
          <div><Label>Monto pagado (USD)</Label><Input type="number" min="0" step="0.01" value={form.amount_paid} onChange={(e) => setForm({ ...form, amount_paid: e.target.value })} disabled={!['pagado', 'pago_parcial'].includes(form.payment_status)} data-testid="deliver-book-amount-paid-input" /></div>
        </div>
        {['pagado', 'pago_parcial'].includes(form.payment_status) && <div><Label>Forma de pago</Label><Select value={form.payment_method} onValueChange={(v) => setForm({ ...form, payment_method: v })}><SelectTrigger data-testid="deliver-book-payment-method-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">
          <SelectItem value="efectivo">Efectivo</SelectItem><SelectItem value="tarjeta">Tarjeta</SelectItem><SelectItem value="transferencia">Transferencia</SelectItem><SelectItem value="zelle">Zelle</SelectItem><SelectItem value="cheque">Cheque</SelectItem>
        </SelectContent></Select></div>}
        <div><Label>Notas (opcional)</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="deliver-book-notes-input" /></div>
        {selectedBook && <p className="flex items-center gap-2 text-xs text-slate-500" data-testid="deliver-book-selected-info"><BookThumbnail fileId={selectedBook.cover_file_id} size={28} />Inventario tipo: {selectedBook.inventory_kind === 'loanable' ? 'Prestado' : 'Consumible'} · Precio de lista: {selectedBook.member_price_cents ? `$${(selectedBook.member_price_cents / 100).toFixed(2)}` : 'Gratis'}</p>}
        <Button type="submit" disabled={saving} className="w-full bg-[#132443]" data-testid="confirm-deliver-book-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Confirmar entrega</Button>
      </form>
    </DialogContent>
  </Dialog>;
};
