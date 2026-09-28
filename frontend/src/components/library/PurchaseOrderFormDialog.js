import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const EMPTY_LINE = { book_id: '', quantity: '10', unit_cost: '0' };

export const PurchaseOrderFormDialog = ({ po, onSaved }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [books, setBooks] = useState([]);
  const [providerName, setProviderName] = useState(po?.provider_name || '');
  const [tax, setTax] = useState(po ? String((po.tax_cents / 100).toFixed(2)) : '0');
  const [shipping, setShipping] = useState(po ? String((po.shipping_cents / 100).toFixed(2)) : '0');
  const [expectedDate, setExpectedDate] = useState(po?.expected_date || '');
  const [lines, setLines] = useState(po ? po.lines.map((l) => ({ book_id: l.book_id, quantity: String(l.quantity_ordered), unit_cost: String((l.unit_cost_cents / 100).toFixed(2)) })) : [EMPTY_LINE]);
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) axios.get(`${API}/api/library/books`, getAuthHeaders()).then((r) => setBooks(r.data.items || [])); }, [open, API]);

  const updateLine = (index, field, value) => setLines(lines.map((l, i) => (i === index ? { ...l, [field]: value } : l)));
  const addLine = () => setLines([...lines, EMPTY_LINE]);
  const removeLine = (index) => setLines(lines.filter((_, i) => i !== index));
  const total = lines.reduce((sum, l) => sum + Number(l.quantity || 0) * Number(l.unit_cost || 0), 0) + Number(tax || 0) + Number(shipping || 0);

  const submit = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      const payload = {
        provider_name: providerName, expected_date: expectedDate || null,
        tax_cents: Math.round(Number(tax || 0) * 100), shipping_cents: Math.round(Number(shipping || 0) * 100),
        lines: lines.filter((l) => l.book_id).map((l) => ({ book_id: l.book_id, quantity: Number(l.quantity), unit_cost_cents: Math.round(Number(l.unit_cost || 0) * 100) })),
      };
      if (po) await axios.put(`${API}/api/library/purchase-orders/${po.po_id}`, payload, getAuthHeaders());
      else await axios.post(`${API}/api/library/purchase-orders`, payload, getAuthHeaders());
      toast.success(po ? 'Orden actualizada' : 'Orden de compra creada como borrador'); setOpen(false); await onSaved();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo guardar la orden'); }
    finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button className="bg-[#132443]" data-testid={po ? `edit-po-${po.po_id}` : 'open-new-po-button'}><Plus className="h-4 w-4" />{po ? 'Editar orden' : 'Nueva orden de compra'}</Button></DialogTrigger>
    <DialogContent className="max-w-2xl" data-testid="po-form-dialog"><DialogHeader><DialogTitle>{po ? `Editar ${po.po_number}` : 'Nueva orden de compra'}</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div><Label>Proveedor</Label><Input value={providerName} onChange={(e) => setProviderName(e.target.value)} required data-testid="po-provider-input" /></div>
          <div><Label>Fecha esperada</Label><Input type="date" value={expectedDate} onChange={(e) => setExpectedDate(e.target.value)} data-testid="po-expected-date-input" /></div>
        </div>
        <div className="space-y-2">
          <Label>Materiales</Label>
          {lines.map((line, index) => <div key={index} className="grid grid-cols-[1fr_80px_100px_auto] gap-2" data-testid={`po-line-${index}`}>
            <Select value={line.book_id} onValueChange={(v) => updateLine(index, 'book_id', v)}><SelectTrigger data-testid={`po-line-book-select-${index}`}><SelectValue placeholder="Material" /></SelectTrigger><SelectContent className="bg-white">{books.map((b) => <SelectItem key={b.book_id} value={b.book_id}>{b.name}</SelectItem>)}</SelectContent></Select>
            <Input type="number" min="1" placeholder="Cant." value={line.quantity} onChange={(e) => updateLine(index, 'quantity', e.target.value)} data-testid={`po-line-quantity-${index}`} />
            <Input type="number" min="0" step="0.01" placeholder="Costo unit." value={line.unit_cost} onChange={(e) => updateLine(index, 'unit_cost', e.target.value)} data-testid={`po-line-cost-${index}`} />
            <Button type="button" variant="ghost" size="sm" onClick={() => removeLine(index)} data-testid={`po-line-remove-${index}`}><Trash2 className="h-4 w-4" /></Button>
          </div>)}
          <Button type="button" variant="outline" size="sm" onClick={addLine} data-testid="po-add-line-button"><Plus className="h-4 w-4" />Agregar material</Button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><Label>Impuestos (USD)</Label><Input type="number" min="0" step="0.01" value={tax} onChange={(e) => setTax(e.target.value)} data-testid="po-tax-input" /></div>
          <div><Label>Envío (USD)</Label><Input type="number" min="0" step="0.01" value={shipping} onChange={(e) => setShipping(e.target.value)} data-testid="po-shipping-input" /></div>
        </div>
        <p className="text-right text-sm font-semibold" data-testid="po-total-preview">Total estimado: ${total.toFixed(2)}</p>
        <Button type="submit" disabled={saving} className="w-full bg-[#132443]" data-testid="save-po-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Guardar borrador</Button>
      </form>
    </DialogContent>
  </Dialog>;
};
