import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../ui/alert-dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

export const DeleteFrontGroupDialog = ({ groupId, groupName, onDeleted }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false); const [reason, setReason] = useState(''); const [saving, setSaving] = useState(false);

  const confirm = async () => {
    if (reason.trim().length < 3) { toast.error('Indique un motivo (mínimo 3 caracteres)'); return; }
    setSaving(true);
    try {
      await axios.delete(`${API}/api/front-groups/${groupId}`, { ...getAuthHeaders(), data: { reason } });
      toast.success('Grupo Frontal borrado'); setOpen(false); setReason(''); await onDeleted();
    } catch (error) {
      toast.error(apiErrorMessage(error, 'No se pudo borrar'));
    } finally { setSaving(false); }
  };

  return <>
    <Button variant="outline" onClick={() => setOpen(true)} className="border-red-300 text-red-700 hover:bg-red-50" data-testid="front-group-delete-button"><Trash2 className="h-4 w-4" />Borrar</Button>
    <AlertDialog open={open} onOpenChange={(value) => { setOpen(value); if (!value) setReason(''); }}>
      <AlertDialogContent className="bg-white" data-testid="front-group-delete-dialog">
        <AlertDialogHeader><AlertDialogTitle>Borrar "{groupName}" para siempre</AlertDialogTitle><AlertDialogDescription>Esto es un borrado TOTAL y permanente: el grupo, su líder/colíder y todos sus integrantes desaparecen (no se puede deshacer). Se bloquea si tiene subramas o procesos de Consolidación activos debajo. Indique el motivo.</AlertDialogDescription></AlertDialogHeader>
        <div><Label htmlFor="front-group-delete-reason">Motivo</Label><Input id="front-group-delete-reason" value={reason} onChange={(event) => setReason(event.target.value)} data-testid="front-group-delete-reason-input" /></div>
        <AlertDialogFooter>
          <Button variant="outline" onClick={() => { setOpen(false); setReason(''); }} data-testid="front-group-delete-cancel-button">Cancelar</Button>
          <Button onClick={confirm} disabled={saving} className="bg-red-700 text-white hover:bg-red-800" data-testid="front-group-delete-confirm-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Borrar para siempre</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </>;
};
