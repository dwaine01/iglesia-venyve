import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Camera, ImageUp, Loader2, Plus, Trash2, UserRound } from 'lucide-react';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Progress } from './ui/progress';
import { uploadPersonPhoto } from '../lib/personPhotoUpload';

export default function PersonProfileEditor({ open, onOpenChange, personId, header, talents, canEditTalents, API, getAuthHeaders, onChanged }) {
  const [form, setForm] = useState({});
  const [catalog, setCatalog] = useState([]);
  const [occupationId, setOccupationId] = useState('');
  const [skillIds, setSkillIds] = useState([]);
  const [newTalent, setNewTalent] = useState('');
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
      genero: header.genero || 'no_especificado',
      estado_civil: header.estado_civil || 'no_especificado',
    });
    setOccupationId(talents?.ocupacion_principal?.talent_id || '');
    setSkillIds((talents?.habilidades || []).map((item) => item.talent_id));
    setFile(null);
    setProgress(0);
    setError('');
    if (canEditTalents) {
      axios
        .get(`${API}/api/core/talents/catalog`, getAuthHeaders())
        .then((response) => setCatalog(response.data.items || []))
        .catch(() => setCatalog([]));
    }
  }, [API, canEditTalents, getAuthHeaders, header, open, talents]);

  const addTalent = async () => {
    if (newTalent.trim().length < 2) return;
    const response = await axios.post(
      `${API}/api/core/talents/catalog`,
      { nombre: newTalent.trim(), tipo: 'ambos' },
      getAuthHeaders()
    );
    setCatalog((items) => [...items.filter((item) => item.talent_id !== response.data.talent_id), response.data].sort((a, b) => a.nombre.localeCompare(b.nombre)));
    setNewTalent('');
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
      if (canEditTalents) {
        await axios.put(
          `${API}/api/core/persons/${personId}/talents`,
          { ocupacion_principal_id: occupationId || null, habilidad_ids: skillIds },
          getAuthHeaders()
        );
      }
      await uploadPersonPhoto({ file, personId, API, getAuthHeaders, onProgress: setProgress });
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
            <div className="space-y-2"><Label htmlFor="profile-gender">Género</Label><select id="profile-gender" value={form.genero || 'no_especificado'} onChange={(e) => setForm((old) => ({ ...old, genero: e.target.value }))} className="h-9 w-full rounded-md border bg-white px-3 text-sm"><option value="no_especificado">No especificado</option><option value="masculino">Masculino</option><option value="femenino">Femenino</option></select></div>
            <div className="space-y-2"><Label htmlFor="profile-civil">Estado civil</Label><select id="profile-civil" value={form.estado_civil || 'no_especificado'} onChange={(e) => setForm((old) => ({ ...old, estado_civil: e.target.value }))} className="h-9 w-full rounded-md border bg-white px-3 text-sm"><option value="no_especificado">No especificado</option><option value="soltero">Soltero/a</option><option value="casado">Casado/a</option><option value="divorciado">Divorciado/a</option><option value="viudo">Viudo/a</option><option value="separado">Separado/a</option><option value="otro">Otro</option></select></div>
            {canEditTalents && <>
            <div className="space-y-2"><Label htmlFor="profile-occupation">Ocupación principal</Label><select id="profile-occupation" value={occupationId} onChange={(e) => setOccupationId(e.target.value)} className="h-9 w-full rounded-md border bg-white px-3 text-sm"><option value="">No especificada</option>{catalog.map((item) => <option key={item.talent_id} value={item.talent_id}>{item.nombre}</option>)}</select></div>
            <div className="space-y-2"><Label htmlFor="profile-skills">Habilidades / oficios</Label><select id="profile-skills" multiple value={skillIds} onChange={(e) => setSkillIds([...e.target.selectedOptions].map((option) => option.value))} className="min-h-24 w-full rounded-md border bg-white px-3 py-2 text-sm">{catalog.map((item) => <option key={item.talent_id} value={item.talent_id}>{item.nombre}</option>)}</select><p className="text-xs text-gray-500">Ctrl/Cmd para seleccionar varias.</p></div>
            <div className="space-y-2 sm:col-span-2"><Label>Agregar opción al catálogo</Label><div className="flex gap-2"><Input value={newTalent} onChange={(e) => setNewTalent(e.target.value)} placeholder="Nueva ocupación o habilidad" /><Button type="button" variant="outline" onClick={addTalent}><Plus className="mr-2 h-4 w-4" />Agregar</Button></div></div>
            </>}
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
