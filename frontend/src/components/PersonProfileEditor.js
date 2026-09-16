import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Camera, ImageUp, Loader2, Trash2, UserRound } from 'lucide-react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Progress } from './ui/progress';

const CHUNK_SIZE = 512 * 1024;

export default function PersonProfileEditor({ open, onOpenChange, personId, header, API, getAuthHeaders, onChanged }) {
  const [form, setForm] = useState({});
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setForm({
      nombre: header.nombre || '',
      apellido: header.apellido || '',
      fecha_nacimiento: header.fecha_nacimiento || '',
      genero: header.genero || '',
      estado_civil: header.estado_civil || '',
      ocupacion: header.ocupacion || '',
    });
    setFile(null);
    setProgress(0);
    setError('');
  }, [header, open]);

  const uploadPhoto = async () => {
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      throw new Error('Usa una imagen JPG, PNG o WebP.');
    }
    if (file.size > 5 * 1024 * 1024) throw new Error('La fotografía no puede superar 5 MB.');
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    const init = await axios.post(
      `${API}/api/core/persons/${personId}/photo/uploads`,
      { content_type: file.type, total_size: file.size, total_chunks: totalChunks },
      getAuthHeaders()
    );
    for (let index = 0; index < totalChunks; index += 1) {
      const chunk = file.slice(index * CHUNK_SIZE, Math.min((index + 1) * CHUNK_SIZE, file.size));
      await axios.put(
        `${API}/api/core/persons/${personId}/photo/uploads/${init.data.upload_id}/chunks/${index}`,
        chunk,
        { ...getAuthHeaders(), headers: { ...getAuthHeaders().headers, 'Content-Type': 'application/octet-stream' } }
      );
      setProgress(Math.round(((index + 1) / totalChunks) * 90));
    }
    await axios.post(
      `${API}/api/core/persons/${personId}/photo/uploads/${init.data.upload_id}/complete`,
      {},
      getAuthHeaders()
    );
    setProgress(100);
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await axios.put(
        `${API}/api/core/persons/${personId}/profile-basics`,
        form,
        getAuthHeaders()
      );
      await uploadPhoto();
      await onChanged();
      onOpenChange(false);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'No se pudo actualizar el perfil.');
    } finally {
      setSaving(false);
    }
  };

  const removePhoto = async () => {
    if (!window.confirm('¿Eliminar la fotografía actual?')) return;
    setSaving(true);
    try {
      await axios.delete(`${API}/api/core/persons/${personId}/photo`, getAuthHeaders());
      await onChanged();
      onOpenChange(false);
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo eliminar la fotografía.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
        <form onSubmit={save} className="space-y-5">
          <DialogHeader>
            <DialogTitle>Editar perfil de Persona</DialogTitle>
            <DialogDescription>Actualiza identidad y fotografía. Contactos y direcciones se editan en sus propios módulos.</DialogDescription>
          </DialogHeader>

          <div className="rounded-xl border border-dashed border-[#C8A951]/60 bg-[#FBF8EF] p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg bg-[#EFE5C7] text-[#785E24]">
                {file ? <ImageUp className="h-7 w-7" /> : <Camera className="h-7 w-7" />}
              </div>
              <div className="flex-1">
                <Label htmlFor="profile-photo">Fotografía tipo ficha/pasaporte</Label>
                <Input id="profile-photo" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setFile(event.target.files?.[0] || null)} className="mt-2 bg-white" />
                <p className="mt-1 text-xs text-gray-500">JPG, PNG o WebP · máximo 5 MB · carga segura por fragmentos</p>
              </div>
              {header.photo_available && (
                <Button type="button" variant="outline" size="sm" onClick={removePhoto} className="text-red-600">
                  <Trash2 className="mr-2 h-4 w-4" /> Quitar
                </Button>
              )}
            </div>
            {progress > 0 && <Progress value={progress} className="mt-4 h-2" />}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label htmlFor="profile-name">Nombre</Label><Input id="profile-name" value={form.nombre || ''} onChange={(e) => setForm((old) => ({ ...old, nombre: e.target.value }))} required /></div>
            <div className="space-y-2"><Label htmlFor="profile-lastname">Apellido</Label><Input id="profile-lastname" value={form.apellido || ''} onChange={(e) => setForm((old) => ({ ...old, apellido: e.target.value }))} required /></div>
            <div className="space-y-2"><Label htmlFor="profile-birth">Fecha de nacimiento</Label><Input id="profile-birth" type="date" value={form.fecha_nacimiento || ''} onChange={(e) => setForm((old) => ({ ...old, fecha_nacimiento: e.target.value }))} /></div>
            <div className="space-y-2"><Label htmlFor="profile-gender">Género</Label><Input id="profile-gender" value={form.genero || ''} onChange={(e) => setForm((old) => ({ ...old, genero: e.target.value }))} placeholder="Ej. femenino" /></div>
            <div className="space-y-2"><Label htmlFor="profile-civil">Estado civil</Label><Input id="profile-civil" value={form.estado_civil || ''} onChange={(e) => setForm((old) => ({ ...old, estado_civil: e.target.value }))} placeholder="Ej. casada" /></div>
            <div className="space-y-2"><Label htmlFor="profile-occupation">Ocupación</Label><Input id="profile-occupation" value={form.ocupacion || ''} onChange={(e) => setForm((old) => ({ ...old, ocupacion: e.target.value }))} /></div>
          </div>

          {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{typeof error === 'string' ? error : 'Revisa los datos.'}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancelar</Button>
            <Button type="submit" disabled={saving} className="bg-[#132443] hover:bg-[#1C3157]">
              {saving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Guardando</> : <><UserRound className="mr-2 h-4 w-4" /> Guardar perfil</>}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
