import React, { useState } from 'react';
import axios from 'axios';
import { Archive, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../ui/alert-dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

export const ArchiveFrontGroupDialog = ({ groupId, onArchived }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false); const [reason, setReason] = useState(''); const [saving, setSaving] = useState(false);

  const confirm = async () => {
    if (reason.trim().length < 3) { toast.error('Indique un motivo (mínimo 3 caracteres)'); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/api/front-groups/${groupId}/archive`, { reason }, getAuthHeaders());
      toast.success('Grupo archivado'); setOpen(false); setReason(''); await onArchived();
    } catch (error) {
      toast.error(apiErrorMessage(error, 'No se pudo archivar'));
    } finally { setSaving(false); }
  };

  return <>
    <Button variant="outline" onClick={() => setOpen(true)} className="border-red-200 text-red-700 hover:bg-red-50" data-testid="front-group-archive-button"><Archive className="h-4 w-4" />Archivar</Button>
    <AlertDialog open={open} onOpenChange={(value) => { setOpen(value); if (!value) setReason(''); }}>
      <AlertDialogContent className="bg-white" data-testid="front-group-archive-dialog">
        <AlertDialogHeader><AlertDialogTitle>Archivar Grupo Frontal</AlertDialogTitle><AlertDialogDescription>Se bloquea si tiene grupos dependientes o procesos de Consolidación activos. Indique el motivo.</AlertDialogDescription></AlertDialogHeader>
        <div><Label htmlFor="front-group-archive-reason">Motivo</Label><Input id="front-group-archive-reason" value={reason} onChange={(event) => setReason(event.target.value)} data-testid="front-group-archive-reason-input" /></div>
        <AlertDialogFooter>
          <Button variant="outline" onClick={() => { setOpen(false); setReason(''); }} data-testid="front-group-archive-cancel-button">Cancelar</Button>
          <Button onClick={confirm} disabled={saving} className="bg-red-700 text-white hover:bg-red-800" data-testid="front-group-archive-confirm-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Archivar</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </>;
};
