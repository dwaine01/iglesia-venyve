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
  const [preview, setPreview] = useState(null); const [loadingPreview, setLoadingPreview] = useState(false);

  const openDialog = async () => {
    setOpen(true); setLoadingPreview(true);
    try {
      const { data } = await axios.get(`${API}/api/front-groups/${groupId}/delete-preview`, getAuthHeaders());
      setPreview(data);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'No se pudo calcular qué se borraría'));
    } finally { setLoadingPreview(false); }
  };

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
    <Button variant="outline" onClick={openDialog} className="border-red-300 text-red-700 hover:bg-red-50" data-testid="front-group-delete-button"><Trash2 className="h-4 w-4" />Borrar</Button>
    <AlertDialog open={open} onOpenChange={(value) => { setOpen(value); if (!value) { setReason(''); setPreview(null); } }}>
      <AlertDialogContent className="bg-white" data-testid="front-group-delete-dialog">
        <AlertDialogHeader><AlertDialogTitle>Borrar "{groupName}" para siempre</AlertDialogTitle><AlertDialogDescription>Esto es un borrado TOTAL y permanente: el grupo, su líder/colíder y todos sus integrantes desaparecen (no se puede deshacer). Se bloquea si tiene subramas o procesos de Consolidación activos debajo. Indique el motivo.</AlertDialogDescription></AlertDialogHeader>
        {loadingPreview && <p className="text-sm text-slate-500" data-testid="front-group-delete-preview-loading">Calculando qué se va a borrar…</p>}
        {preview && (
          <div className={`rounded-md border p-3 text-sm ${preview.blocked ? 'border-amber-300 bg-amber-50 text-amber-900' : 'border-red-200 bg-red-50 text-red-900'}`} data-testid="front-group-delete-preview">
            {preview.blocked
              ? <>No se puede borrar todavía: tiene <strong>{preview.dependent_group_count}</strong> subrama(s) y/o <strong>{preview.active_process_count}</strong> proceso(s) de Consolidación activos debajo. Bórrelos o muévalos primero.</>
              : <>Se borrarán <strong>{preview.assignments}</strong> integrante(s) (líder, colíder y miembros) de este grupo.</>}
          </div>
        )}
        <div><Label htmlFor="front-group-delete-reason">Motivo</Label><Input id="front-group-delete-reason" value={reason} onChange={(event) => setReason(event.target.value)} data-testid="front-group-delete-reason-input" /></div>
        <AlertDialogFooter>
          <Button variant="outline" onClick={() => { setOpen(false); setReason(''); setPreview(null); }} data-testid="front-group-delete-cancel-button">Cancelar</Button>
          <Button onClick={confirm} disabled={saving || (preview && preview.blocked)} className="bg-red-700 text-white hover:bg-red-800" data-testid="front-group-delete-confirm-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Borrar para siempre</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </>;
};
