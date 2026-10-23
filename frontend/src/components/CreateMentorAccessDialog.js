import React, { useState } from 'react';
import axios from 'axios';
import { KeyRound, Loader2, UserRoundPlus } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { errorDetailText } from '../lib/errorText';

export default function CreateMentorAccessDialog({ open, onOpenChange, personId, API, getAuthHeaders, onCreated }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setEmail('');
    setPassword('');
    setConfirmPassword('');
  };

  const close = (value) => {
    if (!value) reset();
    onOpenChange(value);
  };

  const submit = async () => {
    if (!email.trim()) {
      toast.error('Escriba el correo de acceso del mentor');
      return;
    }
    if (password.length < 10) {
      toast.error('La contraseña temporal debe tener al menos 10 caracteres');
      return;
    }
    if (password !== confirmPassword) {
      toast.error('Las contraseñas no coinciden');
      return;
    }
    setSaving(true);
    try {
      await axios.post(
        `${API}/api/core/governance/users`,
        { person_id: personId, email: email.trim(), temporary_password: password, access_level: 'persona', mentor_access: true },
        getAuthHeaders()
      );
      toast.success('Acceso de mentor creado. Comparte la contraseña temporal por un canal seguro.');
      close(false);
      if (onCreated) onCreated();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo crear el acceso de mentor'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="create-mentor-access-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Spectral, serif' }}>
            <KeyRound className="h-5 w-5 text-[#132443]" /> Crear acceso de mentor
          </DialogTitle>
          <DialogDescription>
            Esta persona podrá entrar con su propio usuario y ver solo su panel "Mis Visitas". Deberá cambiar la
            contraseña en su primer ingreso.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label htmlFor="mentor-access-email">Correo de acceso</Label>
            <Input
              id="mentor-access-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="nombre@ejemplo.com"
              data-testid="create-mentor-access-email-input"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="mentor-access-password">Contraseña temporal</Label>
            <Input
              id="mentor-access-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Mínimo 10 caracteres"
              autoComplete="new-password"
              data-testid="create-mentor-access-password-input"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="mentor-access-password-confirm">Confirmar contraseña</Label>
            <Input
              id="mentor-access-password-confirm"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Repite la contraseña"
              autoComplete="new-password"
              data-testid="create-mentor-access-password-confirm-input"
            />
            <p className="text-[11px] text-muted-foreground">
              Comparte esta contraseña con el mentor por un canal seguro; no queda registrada aquí.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => close(false)} disabled={saving}>Cancelar</Button>
          <Button onClick={submit} disabled={saving} className="bg-[#132443]" data-testid="create-mentor-access-submit">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserRoundPlus className="h-4 w-4" />} Crear acceso
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
