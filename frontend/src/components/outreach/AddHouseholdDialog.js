import React, { useState } from 'react';
import axios from 'axios';
import { Home, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { errorDetailText } from '../../lib/errorText';

export const AddHouseholdDialog = ({ open, onOpenChange, campaigns, forcedMentorId, onCreated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [addressLine1, setAddressLine1] = useState('');
  const [sector, setSector] = useState('');
  const [campaignId, setCampaignId] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  const reset = () => { setAddressLine1(''); setSector(''); setCampaignId(''); setNote(''); };

  const activeCampaign = campaigns?.find((item) => item.campaign_id === campaignId);

  const submit = async () => {
    if (!addressLine1.trim() && !sector.trim()) {
      toast.error('Indique al menos la dirección o el sector del hogar');
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/households`, {
        campaign_id: campaignId || null, mentor_person_id: forcedMentorId || null,
        address_line1: addressLine1 || null, sector: sector || null, note: note || null,
      }, getAuthHeaders());
      toast.success('Hogar agregado');
      reset();
      onOpenChange(false);
      if (onCreated) onCreated();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo agregar el hogar'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(value) => { if (!value) reset(); onOpenChange(value); }}>
      <DialogContent className="bg-white sm:max-w-lg" data-testid="outreach-add-household-dialog">
        <DialogHeader><DialogTitle>Agregar hogar</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5"><Label>Dirección</Label><Input value={addressLine1} onChange={(event) => setAddressLine1(event.target.value)} placeholder="Calle y número" data-testid="outreach-household-address-input" /></div>
          <div className="space-y-1.5"><Label>Sector</Label><Input value={sector} onChange={(event) => setSector(event.target.value)} placeholder="Nombre del sector o barrio" data-testid="outreach-household-sector-input" /></div>

          {campaigns?.length > 0 && (
            <div className="space-y-1.5">
              <Label>Campaña (opcional)</Label>
              <Select value={campaignId} onValueChange={setCampaignId}>
                <SelectTrigger data-testid="outreach-household-campaign-select"><SelectValue placeholder="Sin campaña" /></SelectTrigger>
                <SelectContent className="bg-white">
                  {campaigns.map((campaign) => <SelectItem key={campaign.campaign_id} value={campaign.campaign_id}>{campaign.name}</SelectItem>)}
                </SelectContent>
              </Select>
              {activeCampaign?.instructions && (
                <p className="rounded-md border border-dashed border-[#D8D3C8] bg-[#FAF9F5] p-2 text-xs text-slate-600" data-testid="outreach-household-campaign-instructions">{activeCampaign.instructions}</p>
              )}
            </div>
          )}

          <div className="space-y-1.5"><Label>Nota (opcional)</Label><Textarea value={note} onChange={(event) => setNote(event.target.value)} data-testid="outreach-household-note-input" /></div>

          <Button className="w-full bg-[#132443]" disabled={saving} onClick={submit} data-testid="outreach-household-submit">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Home className="h-4 w-4" />} Agregar hogar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
