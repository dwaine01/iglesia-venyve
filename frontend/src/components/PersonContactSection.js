import React, { useState } from 'react';
import axios from 'axios';
import { Mail, MessageCircle, Pencil, Phone, Plus, Star, Trash2 } from 'lucide-react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';

const EMPTY_CONTACT = {
  tipo: 'telefono',
  valor: '',
  etiqueta: '',
  es_principal: false,
  notas: '',
};

const TYPE_LABELS = {
  telefono: 'Teléfono',
  email: 'Correo',
  whatsapp: 'WhatsApp',
  otro: 'Otro',
};

const ContactIcon = ({ tipo }) => {
  if (tipo === 'email') return <Mail className="h-5 w-5" />;
  if (tipo === 'whatsapp') return <MessageCircle className="h-5 w-5" />;
  return <Phone className="h-5 w-5" />;
};

export default function PersonContactSection({ personId, domain, API, getAuthHeaders, onChanged }) {
  const items = domain?.items || [];
  const canWrite = Boolean(domain?.can_write);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_CONTACT);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_CONTACT);
    setError('');
    setOpen(true);
  };

  const openEdit = (item) => {
    setEditingId(item.contact_id);
    setForm({
      tipo: item.tipo,
      valor: item.valor,
      etiqueta: item.etiqueta || '',
      es_principal: item.es_principal,
      notas: item.notas || '',
    });
    setError('');
    setOpen(true);
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const url = editingId
        ? `${API}/api/core/persons/${personId}/contacts/${editingId}`
        : `${API}/api/core/persons/${personId}/contacts`;
      await axios({
        method: editingId ? 'put' : 'post',
        url,
        data: form,
        ...getAuthHeaders(),
      });
      setOpen(false);
      await onChanged();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo guardar el contacto.');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item) => {
    if (!window.confirm(`¿Eliminar ${item.valor}?`)) return;
    setError('');
    try {
      await axios.delete(
        `${API}/api/core/persons/${personId}/contacts/${item.contact_id}`,
        getAuthHeaders()
      );
      await onChanged();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo eliminar el contacto.');
    }
  };

  return (
    <div className="space-y-4" data-testid="person-contacts-section">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Contactos</h3>
          <p className="text-sm text-gray-500">Canales directos para cuidar y acompañar a esta persona.</p>
        </div>
        {canWrite && (
          <Button onClick={openCreate} className="bg-[#8A6D2F] hover:bg-[#705723]" data-testid="add-contact-button">
            <Plus className="mr-2 h-4 w-4" /> Agregar contacto
          </Button>
        )}
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#C8A951]/50 bg-[#FBF8F1] px-6 py-10 text-center">
          <Phone className="mx-auto mb-3 h-9 w-9 text-[#B99A4B]" />
          <p className="font-medium text-gray-800">Aún no hay contactos registrados</p>
          <p className="mt-1 text-sm text-gray-500">Agrega un teléfono, correo o WhatsApp para comenzar.</p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((item) => (
            <Card key={item.contact_id} className="border-gray-200 shadow-sm" data-testid={`contact-card-${item.contact_id}`}>
              <CardContent className="flex gap-3 p-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#F5F0E8] text-[#8A6D2F]">
                  <ContactIcon tipo={item.tipo} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="break-all font-medium text-gray-900">{item.valor}</p>
                    {item.es_principal && (
                      <Badge className="bg-[#EEE5C9] text-[#705723] hover:bg-[#EEE5C9]">
                        <Star className="mr-1 h-3 w-3 fill-current" /> Principal
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    {TYPE_LABELS[item.tipo]}{item.etiqueta ? ` · ${item.etiqueta}` : ''}
                  </p>
                  {item.notas && <p className="mt-2 text-sm text-gray-600">{item.notas}</p>}
                </div>
                {canWrite && (
                  <div className="flex shrink-0 gap-1">
                    <Button variant="ghost" size="icon" onClick={() => openEdit(item)} aria-label={`Editar ${item.valor}`}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => remove(item)} aria-label={`Eliminar ${item.valor}`} className="text-red-600 hover:text-red-700">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
          <form onSubmit={save} className="space-y-4">
            <DialogHeader>
              <DialogTitle>{editingId ? 'Editar contacto' : 'Nuevo contacto'}</DialogTitle>
              <DialogDescription>Registra información vigente y marca un canal principal.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="contact-type">Tipo</Label>
                <select
                  id="contact-type"
                  value={form.tipo}
                  onChange={(e) => setForm((old) => ({ ...old, tipo: e.target.value }))}
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                >
                  {Object.entries(TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="contact-label">Etiqueta</Label>
                <Input id="contact-label" value={form.etiqueta} onChange={(e) => setForm((old) => ({ ...old, etiqueta: e.target.value }))} placeholder="Personal, trabajo..." />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="contact-value">Contacto</Label>
              <Input id="contact-value" value={form.valor} onChange={(e) => setForm((old) => ({ ...old, valor: e.target.value }))} placeholder="Teléfono o correo" required minLength={3} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contact-notes">Notas</Label>
              <Textarea id="contact-notes" value={form.notas} onChange={(e) => setForm((old) => ({ ...old, notas: e.target.value }))} placeholder="Preferencias de contacto u observaciones" />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={form.es_principal} onChange={(e) => setForm((old) => ({ ...old, es_principal: e.target.checked }))} />
              Usar como contacto principal
            </label>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={saving} className="bg-[#8A6D2F] hover:bg-[#705723]">
                {saving ? 'Guardando...' : 'Guardar contacto'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
