import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Save } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Switch } from '../ui/switch';
import { Textarea } from '../ui/textarea';
import { BookThumbnail } from './BookThumbnail';

const EMPTY = {
  sku: '', name: '', description: '', item_type: 'libro', process_key: '', level: '', edition: '', provider: '',
  cost_price: '0', member_price: '0', inventory_kind: 'consumable', is_active: true, min_stock: '10', ideal_stock: '40',
  location: '', qr_code: '', cover_image_url: '',
};

const centsToDollars = (cents) => String(((cents || 0) / 100).toFixed(2));

export const LibraryBookFormDialog = ({ open, onOpenChange, book, onSaved }) => {
  const { API, getAuthHeaders } = useAuth();
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [coverFile, setCoverFile] = useState(null);

  useEffect(() => {
    if (book) {
      setForm({ ...EMPTY, ...book, cost_price: centsToDollars(book.cost_price_cents), member_price: centsToDollars(book.member_price_cents), min_stock: String(book.min_stock), ideal_stock: String(book.ideal_stock) });
    } else {
      setForm(EMPTY);
    }
    setCoverFile(null);
  }, [book, open]);

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form, cost_price_cents: Math.round(Number(form.cost_price || 0) * 100), member_price_cents: Math.round(Number(form.member_price || 0) * 100),
        min_stock: Number(form.min_stock || 0), ideal_stock: Number(form.ideal_stock || 0),
        sku: form.sku || null, process_key: form.process_key || null, level: form.level || null, edition: form.edition || null,
        provider: form.provider || null, location: form.location || null, qr_code: form.qr_code || null, cover_image_url: form.cover_image_url || null,
      };
      let bookId = book?.book_id;
      if (book) await axios.put(`${API}/api/library/books/${bookId}`, payload, getAuthHeaders());
      else { const { data } = await axios.post(`${API}/api/library/books`, payload, getAuthHeaders()); bookId = data.book_id; }
      if (coverFile) {
        const formData = new FormData(); formData.append('file', coverFile);
        await axios.post(`${API}/api/library/files/cover/${bookId}`, formData, getAuthHeaders());
      }
      toast.success(book ? 'Material actualizado' : 'Material agregado al catálogo');
      onOpenChange(false); await onSaved();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo guardar el material'); }

    finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="max-w-2xl" data-testid="library-book-form-dialog">
      <DialogHeader><DialogTitle>{book ? 'Editar material' : 'Nuevo material'}</DialogTitle></DialogHeader>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><Label>Nombre</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="library-book-name-input" /></div>
        <div className="flex items-center gap-3 sm:col-span-2">
          <BookThumbnail fileId={book?.cover_file_id} size={64} />
          <div><Label>Foto de portada (JPG, PNG, WebP)</Label><Input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setCoverFile(e.target.files?.[0] || null)} data-testid="library-book-cover-input" /></div>
        </div>
        <div><Label>SKU / Código</Label><Input value={form.sku || ''} onChange={(e) => setForm({ ...form, sku: e.target.value })} data-testid="library-book-sku-input" /></div>
        <div><Label>Código QR / barras</Label><Input value={form.qr_code || ''} onChange={(e) => setForm({ ...form, qr_code: e.target.value })} data-testid="library-book-qr-input" /></div>
        <div><Label>Tipo</Label><Select value={form.item_type} onValueChange={(v) => setForm({ ...form, item_type: v })}><SelectTrigger data-testid="library-book-type-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">
          <SelectItem value="libro">Libro</SelectItem><SelectItem value="manual">Manual</SelectItem><SelectItem value="cuaderno">Cuaderno</SelectItem>
          <SelectItem value="guia">Guía</SelectItem><SelectItem value="material_retiro">Material de retiro</SelectItem><SelectItem value="otro">Otro</SelectItem>
        </SelectContent></Select></div>
        <div><Label>Tipo de inventario</Label><Select value={form.inventory_kind} onValueChange={(v) => setForm({ ...form, inventory_kind: v })}><SelectTrigger data-testid="library-book-kind-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">
          <SelectItem value="consumable">Consumible (se entrega)</SelectItem><SelectItem value="loanable">Prestado (debe regresar)</SelectItem>
        </SelectContent></Select></div>
        <div><Label>Proceso</Label><Input value={form.process_key || ''} onChange={(e) => setForm({ ...form, process_key: e.target.value })} placeholder="seven_weeks, discipleship…" data-testid="library-book-process-input" /></div>
        <div><Label>Nivel / Edición</Label><Input value={form.level || ''} onChange={(e) => setForm({ ...form, level: e.target.value })} data-testid="library-book-level-input" /></div>
        <div><Label>Proveedor</Label><Input value={form.provider || ''} onChange={(e) => setForm({ ...form, provider: e.target.value })} data-testid="library-book-provider-input" /></div>
        <div><Label>Ubicación física</Label><Input value={form.location || ''} onChange={(e) => setForm({ ...form, location: e.target.value })} data-testid="library-book-location-input" /></div>
        <div><Label>Costo de compra (USD)</Label><Input type="number" min="0" step="0.01" value={form.cost_price} onChange={(e) => setForm({ ...form, cost_price: e.target.value })} data-testid="library-book-cost-input" /></div>
        <div><Label>Precio al miembro (USD, 0 = gratis)</Label><Input type="number" min="0" step="0.01" value={form.member_price} onChange={(e) => setForm({ ...form, member_price: e.target.value })} data-testid="library-book-price-input" /></div>
        <div><Label>Stock mínimo</Label><Input type="number" min="0" value={form.min_stock} onChange={(e) => setForm({ ...form, min_stock: e.target.value })} data-testid="library-book-min-stock-input" /></div>
        <div><Label>Stock ideal</Label><Input type="number" min="0" value={form.ideal_stock} onChange={(e) => setForm({ ...form, ideal_stock: e.target.value })} data-testid="library-book-ideal-stock-input" /></div>
        <div className="sm:col-span-2"><Label>Descripción</Label><Textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="library-book-description-input" /></div>
        <div className="flex items-center gap-2 sm:col-span-2"><Switch checked={form.is_active} onCheckedChange={(v) => setForm({ ...form, is_active: v })} data-testid="library-book-active-switch" /><Label>Activo en el catálogo</Label></div>
        <Button type="submit" disabled={saving} className="justify-self-end bg-[#132443] sm:col-span-2" data-testid="save-library-book-button">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}Guardar material</Button>
      </form>
    </DialogContent>
  </Dialog>;
};
