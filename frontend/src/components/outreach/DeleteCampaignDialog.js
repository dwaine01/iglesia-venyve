import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../ui/alert-dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

export const DeleteCampaignDialog = ({ campaignId, campaignName, onDeleted }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false); const [reason, setReason] = useState(''); const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null); const [loadingPreview, setLoadingPreview] = useState(false);

  const openDialog = async () => {
    setOpen(true); setLoadingPreview(true);
    try {
      const { data } = await axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/delete-preview`, getAuthHeaders());
      setPreview(data);
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo calcular qué se borraría'));
    } finally { setLoadingPreview(false); }
  };

  const confirm = async () => {
    if (reason.trim().length < 3) { toast.error('Indique un motivo (mínimo 3 caracteres)'); return; }
    setSaving(true);
    try {
      await axios.delete(`${API}/api/mentorship/outreach/campaigns/${campaignId}`, { ...getAuthHeaders(), data: { reason } });
      toast.success('Invasión borrada'); setOpen(false); setReason(''); await onDeleted();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo borrar la invasión'));
    } finally { setSaving(false); }
  };

  return <>
    <Button size="sm" variant="outline" onClick={openDialog} className="border-red-300 text-red-700 hover:bg-red-50" data-testid={`outreach-campaign-delete-button-${campaignId}`}><Trash2 className="h-4 w-4" />Borrar</Button>
    <AlertDialog open={open} onOpenChange={(value) => { setOpen(value); if (!value) { setReason(''); setPreview(null); } }}>
      <AlertDialogContent className="bg-white" data-testid="outreach-campaign-delete-dialog">
        <AlertDialogHeader><AlertDialogTitle>Borrar "{campaignName}" para siempre</AlertDialogTitle><AlertDialogDescription>Esto borra la invasión y TODOS sus hogares, visitas e intentos registrados (no se puede deshacer). Las personas que ya iniciaron la Ley de las 7 Semanas conservan su expediente de Consolidación. Indique el motivo.</AlertDialogDescription></AlertDialogHeader>
        {loadingPreview && <p className="text-sm text-slate-500" data-testid="outreach-campaign-delete-preview-loading">Calculando qué se va a borrar…</p>}
        {preview && (
          <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900" data-testid="outreach-campaign-delete-preview">
            Se borrarán <strong>{preview.households}</strong> hogares, <strong>{preview.visits}</strong> visitas, <strong>{preview.attempts}</strong> intentos y <strong>{preview.participations}</strong> participaciones de mentores.
          </div>
        )}
        <div><Label htmlFor="outreach-campaign-delete-reason">Motivo</Label><Input id="outreach-campaign-delete-reason" value={reason} onChange={(event) => setReason(event.target.value)} data-testid="outreach-campaign-delete-reason-input" /></div>
        <AlertDialogFooter>
          <Button variant="outline" onClick={() => { setOpen(false); setReason(''); setPreview(null); }} data-testid="outreach-campaign-delete-cancel-button">Cancelar</Button>
          <Button onClick={confirm} disabled={saving} className="bg-red-700 text-white hover:bg-red-800" data-testid="outreach-campaign-delete-confirm-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Borrar para siempre</Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </>;
};
