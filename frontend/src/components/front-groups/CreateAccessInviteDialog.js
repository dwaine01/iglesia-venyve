import React, { useState } from 'react';
import axios from 'axios';
import { KeyRound, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

// C5: cuenta creada SIN contraseña temporal escrita por quien la crea -> se
// emite un enlace de invitación de un solo uso para que la persona misma
// defina su contraseña.
export const CreateAccessInviteDialog = ({ personId, personName }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false); const [email, setEmail] = useState(''); const [saving, setSaving] = useState(false); const [link, setLink] = useState('');

  const submit = async () => {
    setSaving(true);
    try {
      const response = await axios.post(`${API}/api/core/governance/users`, { person_id: personId, email, access_level: 'persona' }, getAuthHeaders());
      if (response.data.invitation_token) setLink(`${window.location.origin}/aceptar-invitacion?token=${response.data.invitation_token}`);
      toast.success('Cuenta creada');
    } catch (error) {
      toast.error(apiErrorMessage(error, 'No se pudo crear la cuenta'));
    } finally { setSaving(false); }
  };

  const copyLink = () => { if (navigator.clipboard) navigator.clipboard.writeText(link); toast.success('Enlace copiado'); };

  return <Dialog open={open} onOpenChange={(value) => { setOpen(value); if (!value) { setLink(''); setEmail(''); } }}>
    <DialogTrigger asChild><Button size="sm" variant="outline" data-testid={`front-group-create-access-${personId}`}><KeyRound className="h-3.5 w-3.5" />Crear acceso</Button></DialogTrigger>
    <DialogContent className="max-w-md bg-white" data-testid="front-group-create-access-dialog">
      <DialogHeader><DialogTitle>Crear acceso para {personName}</DialogTitle><DialogDescription>Se genera un enlace de invitación de un solo uso; la persona define su propia contraseña.</DialogDescription></DialogHeader>
      {!link ? <div className="space-y-3">
        <div><Label htmlFor="access-email">Correo electrónico</Label><Input id="access-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} data-testid="front-group-create-access-email-input" /></div>
        <Button onClick={submit} disabled={saving || !email.includes('@')} className="w-full bg-slate-900" data-testid="front-group-create-access-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Crear e invitar</Button>
      </div> : <div className="space-y-3">
        <p className="text-sm text-emerald-700">Cuenta creada. Comparta este enlace UNA sola vez:</p>
        <div className="break-all border border-slate-200 bg-slate-50 p-3 text-xs" data-testid="front-group-create-access-link">{link}</div>
        <Button onClick={copyLink} variant="outline" className="w-full" data-testid="front-group-create-access-copy-button">Copiar enlace</Button>
      </div>}
    </DialogContent>
  </Dialog>;
};
