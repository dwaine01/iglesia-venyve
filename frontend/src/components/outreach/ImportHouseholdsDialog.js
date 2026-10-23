import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, UploadCloud } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Textarea } from '../ui/textarea';

export const ImportHouseholdsDialog = ({ open, onOpenChange, campaign, onImported }) => {
  const { API, getAuthHeaders } = useAuth();
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);

  const reset = () => setText('');

  const submit = async () => {
    const entries = text
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [address, sector] = line.split('|').map((part) => (part || '').trim());
        return { address_line1: address || null, sector: sector || null };
      });
    if (entries.length === 0) {
      toast.error('Escriba al menos una dirección o sector, una por línea');
      return;
    }
    setSaving(true);
    try {
      const { data } = await axios.post(`${API}/api/mentorship/outreach/campaigns/${campaign.campaign_id}/households/import`, { entries }, getAuthHeaders());
      toast.success(`${data.created} casa(s) disponible(s) agregada(s)${data.skipped ? ` · ${data.skipped} línea(s) vacía(s) omitida(s)` : ''}`);
      reset();
      onOpenChange(false);
      if (onImported) onImported();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudieron importar las casas'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(value) => { if (!value) reset(); onOpenChange(value); }}>
      <DialogContent className="bg-white sm:max-w-lg" data-testid="outreach-import-households-dialog">
        <DialogHeader><DialogTitle>Importar casas disponibles — {campaign?.name}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <p className="text-xs text-slate-500">Una casa por línea: dirección y, opcionalmente, sector separado por "|". Ejemplo: <code>Calle 5 #12 | Villa Mella</code></p>
          <Textarea
            rows={8}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={'Calle 5 #12 | Villa Mella\nCalle 8, casa azul | Villa Mella'}
            data-testid="outreach-import-households-textarea"
          />
          <Button className="w-full bg-[#132443]" disabled={saving} onClick={submit} data-testid="outreach-import-households-submit">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />} Importar como disponibles
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
