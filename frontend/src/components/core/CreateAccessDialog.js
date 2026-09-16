import React, { useMemo, useState } from 'react';
import { Eye, EyeOff, KeyRound, UserPlus } from 'lucide-react';

import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const generateTemporaryPassword = () => {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%';
  const values = new Uint32Array(14);
  window.crypto.getRandomValues(values);
  return Array.from(values, (value) => alphabet[value % alphabet.length]).join('');
};

export const CreateAccessDialog = ({ candidates, isPastor, onCreate }) => {
  const [open, setOpen] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ person_id: '', email: '', temporary_password: '', access_level: 'lider' });
  const selected = useMemo(() => candidates.find((item) => item.person_id === form.person_id), [candidates, form.person_id]);

  const updatePerson = (personId) => {
    const person = candidates.find((item) => item.person_id === personId);
    setForm((old) => ({ ...old, person_id: personId, email: person?.email || old.email }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    const created = await onCreate(form);
    setSaving(false);
    if (created) {
      setOpen(false);
      setForm({ person_id: '', email: '', temporary_password: '', access_level: 'lider' });
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="bg-[#D4B871] text-[#101D36] hover:bg-[#E0C982]" data-testid="open-create-access-button">
          <UserPlus className="mr-2 h-4 w-4" />Crear acceso
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[92vh] overflow-y-auto bg-white sm:max-w-xl" data-testid="create-access-dialog">
        <DialogHeader>
          <DialogTitle>Crear acceso desde un Perfil 360</DialogTitle>
          <DialogDescription>La cuenta quedará vinculada a una sola Persona y deberá cambiar su clave al ingresar.</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <div>
            <Label>Persona</Label>
            <Select value={form.person_id} onValueChange={updatePerson}>
              <SelectTrigger data-testid="access-person-select"><SelectValue placeholder="Seleccionar Perfil 360" /></SelectTrigger>
              <SelectContent className="max-h-72 bg-white">
                {candidates.map((item) => <SelectItem key={item.person_id} value={item.person_id}>{item.name} · {item.person_number || 'Sin número'}</SelectItem>)}
              </SelectContent>
            </Select>
            {selected && <p className="mt-1 text-xs text-slate-500" data-testid="access-selected-person">{selected.name}</p>}
          </div>
          <div>
            <Label htmlFor="access-email">Correo de ingreso</Label>
            <Input id="access-email" type="email" value={form.email} onChange={(event) => setForm((old) => ({ ...old, email: event.target.value }))} required data-testid="access-email-input" />
          </div>
          <div>
            <Label>Nivel de acceso</Label>
            <Select value={form.access_level} onValueChange={(value) => setForm((old) => ({ ...old, access_level: value }))}>
              <SelectTrigger data-testid="access-level-select"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-white">
                {isPastor && <SelectItem value="coordinador_general">Coordinador general</SelectItem>}
                <SelectItem value="lider">Líder</SelectItem>
                <SelectItem value="persona">Persona</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="temporary-password">Clave temporal</Label>
            <div className="mt-1 flex gap-2">
              <Input id="temporary-password" type={showPassword ? 'text' : 'password'} value={form.temporary_password} onChange={(event) => setForm((old) => ({ ...old, temporary_password: event.target.value }))} minLength={10} required data-testid="temporary-password-input" />
              <Button type="button" variant="outline" size="icon" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Ocultar clave' : 'Mostrar clave'} data-testid="toggle-temporary-password-button">{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</Button>
              <Button type="button" variant="outline" size="icon" onClick={() => setForm((old) => ({ ...old, temporary_password: generateTemporaryPassword() }))} aria-label="Generar clave segura" data-testid="generate-temporary-password-button"><KeyRound className="h-4 w-4" /></Button>
            </div>
            <p className="mt-1 text-xs text-slate-500">Compártala de forma privada. El sistema exigirá una nueva clave en el primer ingreso.</p>
          </div>
          <Button type="submit" disabled={saving || !form.person_id || !form.email || form.temporary_password.length < 10} className="w-full bg-[#101D36]" data-testid="create-access-submit-button">
            {saving ? 'Creando acceso…' : 'Crear acceso controlado'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
};