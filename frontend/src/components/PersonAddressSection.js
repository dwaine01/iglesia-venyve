import React, { useState } from 'react';
import axios from 'axios';
import { Building2, CircleAlert, CircleCheck, Clock3, Home, MapPin, Pencil, Plus, Star, Trash2 } from 'lucide-react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';

const EMPTY_ADDRESS = {
  tipo: 'casa',
  linea1: '',
  linea2: '',
  sector: '',
  ciudad: '',
  provincia: '',
  codigo_postal: '',
  pais: 'Estados Unidos',
  es_principal: false,
  notas: '',
};

const TYPE_LABELS = { casa: 'Casa', trabajo: 'Trabajo', otra: 'Otra' };

export default function PersonAddressSection({ personId, domain, API, getAuthHeaders, onChanged }) {
  const items = domain?.items || [];
  const canWrite = Boolean(domain?.can_write);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_ADDRESS);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_ADDRESS);
    setError('');
    setOpen(true);
  };

  const openEdit = (item) => {
    setEditingId(item.address_id);
    setForm({
      tipo: item.tipo,
      linea1: item.linea1,
      linea2: item.linea2 || '',
      sector: item.sector || '',
      ciudad: item.ciudad,
      provincia: item.provincia || '',
      codigo_postal: item.codigo_postal || '',
      pais: item.pais || 'Estados Unidos',
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
        ? `${API}/api/core/persons/${personId}/addresses/${editingId}`
        : `${API}/api/core/persons/${personId}/addresses`;
      await axios({
        method: editingId ? 'put' : 'post',
        url,
        data: form,
        ...getAuthHeaders(),
      });
      setOpen(false);
      await onChanged();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo guardar la dirección.');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item) => {
    if (!window.confirm(`¿Eliminar la dirección ${item.linea1}?`)) return;
    setError('');
    try {
      await axios.delete(
        `${API}/api/core/persons/${personId}/addresses/${item.address_id}`,
        getAuthHeaders()
      );
      await onChanged();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo eliminar la dirección.');
    }
  };

  return (
    <div className="space-y-4" data-testid="person-addresses-section">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Direcciones</h3>
          <p className="text-sm text-gray-500">Ubicaciones útiles para visitas y acompañamiento presencial.</p>
        </div>
        {canWrite && (
          <Button onClick={openCreate} className="bg-[#8A6D2F] hover:bg-[#705723]" data-testid="add-address-button">
            <Plus className="mr-2 h-4 w-4" /> Agregar dirección
          </Button>
        )}
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#C8A951]/50 bg-[#FBF8F1] px-6 py-10 text-center">
          <MapPin className="mx-auto mb-3 h-9 w-9 text-[#B99A4B]" />
          <p className="font-medium text-gray-800">Aún no hay direcciones registradas</p>
          <p className="mt-1 text-sm text-gray-500">Agrega una ubicación para mostrarla en el perfil 360°.</p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((item) => (
            <Card key={item.address_id} className="border-gray-200 shadow-sm" data-testid={`address-card-${item.address_id}`}>
              <CardContent className="flex gap-3 p-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#F5F0E8] text-[#8A6D2F]">
                  {item.tipo === 'trabajo' ? <Building2 className="h-5 w-5" /> : <Home className="h-5 w-5" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-gray-900">{item.linea1}</p>
                    {item.es_principal && (
                      <Badge className="bg-[#EEE5C9] text-[#705723] hover:bg-[#EEE5C9]">
                        <Star className="mr-1 h-3 w-3 fill-current" /> Principal
                      </Badge>
                    )}
                  </div>
                  {item.linea2 && <p className="text-sm text-gray-600">{item.linea2}</p>}
                  <p className="mt-1 text-sm text-gray-600">
                    {[item.sector, item.ciudad, item.provincia].filter(Boolean).join(', ')}
                  </p>
                  <p className="mt-1 text-xs text-gray-500">{TYPE_LABELS[item.tipo]} · {item.pais}</p>
                  <div className="mt-2 flex items-center gap-2 text-xs" data-testid={`address-geocoding-status-${item.address_id}`}>
                    {item.verification_status === 'verified' && <><CircleCheck className="h-3.5 w-3.5 text-emerald-600" /><span className="text-emerald-700">Ubicación verificada · Zona {item.subzone_key || item.zone_number || 'pendiente'}</span></>}
                    {item.verification_status === 'manual_verified' && <><MapPin className="h-3.5 w-3.5 text-blue-600" /><span className="text-blue-700">Pin corregido · Zona {item.subzone_key || item.zone_number || 'pendiente'}</span></>}
                    {item.verification_status === 'needs_verification' && <><CircleAlert className="h-3.5 w-3.5 text-amber-600" /><span className="text-amber-700">Ubicación necesita verificación</span></>}
                    {(!item.verification_status || item.verification_status === 'pending') && <><Clock3 className="h-3.5 w-3.5 text-slate-500" /><span className="text-slate-500">Geocodificación pendiente</span></>}
                  </div>
                  {item.notas && <p className="mt-2 text-sm text-gray-600">{item.notas}</p>}
                </div>
                {canWrite && (
                  <div className="flex shrink-0 gap-1">
                    <Button variant="ghost" size="icon" onClick={() => openEdit(item)} aria-label={`Editar ${item.linea1}`} data-testid={`edit-address-${item.address_id}`}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => remove(item)} aria-label={`Eliminar ${item.linea1}`} className="text-red-600 hover:text-red-700" data-testid={`delete-address-${item.address_id}`}>
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
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <form onSubmit={save} className="space-y-4">
            <DialogHeader>
              <DialogTitle>{editingId ? 'Editar dirección' : 'Nueva dirección'}</DialogTitle>
              <DialogDescription>Registra una ubicación vigente para esta persona.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="address-type">Tipo</Label>
                <select id="address-type" value={form.tipo} onChange={(e) => setForm((old) => ({ ...old, tipo: e.target.value }))} className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm">
                  {Object.entries(TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="address-country">País</Label>
                <Input id="address-country" value={form.pais} onChange={(e) => setForm((old) => ({ ...old, pais: e.target.value }))} required />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="address-line1">Dirección</Label>
              <Input id="address-line1" value={form.linea1} onChange={(e) => setForm((old) => ({ ...old, linea1: e.target.value }))} placeholder="Calle, número, edificio" required minLength={3} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="address-line2">Complemento</Label>
              <Input id="address-line2" value={form.linea2} onChange={(e) => setForm((old) => ({ ...old, linea2: e.target.value }))} placeholder="Apartamento, referencia" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="address-sector">Sector</Label>
                <Input id="address-sector" value={form.sector} onChange={(e) => setForm((old) => ({ ...old, sector: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="address-city">Ciudad</Label>
                <Input id="address-city" value={form.ciudad} onChange={(e) => setForm((old) => ({ ...old, ciudad: e.target.value }))} required minLength={2} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="address-province">Provincia</Label>
                <Input id="address-province" value={form.provincia} onChange={(e) => setForm((old) => ({ ...old, provincia: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="address-postal">Código postal</Label>
                <Input id="address-postal" value={form.codigo_postal} onChange={(e) => setForm((old) => ({ ...old, codigo_postal: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="address-notes">Notas</Label>
              <Textarea id="address-notes" value={form.notas} onChange={(e) => setForm((old) => ({ ...old, notas: e.target.value }))} placeholder="Indicaciones para llegar u observaciones" />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={form.es_principal} onChange={(e) => setForm((old) => ({ ...old, es_principal: e.target.checked }))} />
              Usar como dirección principal
            </label>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancelar</Button>
              <Button type="submit" disabled={saving} className="bg-[#8A6D2F] hover:bg-[#705723]">
                {saving ? 'Guardando...' : 'Guardar dirección'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
