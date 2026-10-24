import React, { useEffect, useState } from 'react';
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
import { LocationCapture } from './LocationCapture';

export const AddHouseholdDialog = ({ open, onOpenChange, campaigns, forcedMentorId, onCreated, defaultCampaignId = '', initialLocation = null }) => {
  const { API, getAuthHeaders } = useAuth();
  const [addressLine1, setAddressLine1] = useState('');
  const [sector, setSector] = useState('');
  const [campaignId, setCampaignId] = useState(defaultCampaignId);
  const [note, setNote] = useState('');
  const [location, setLocation] = useState(initialLocation);
  const [reference, setReference] = useState('');
  const [duplicates, setDuplicates] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) { setCampaignId(defaultCampaignId); setLocation(initialLocation); } }, [open, defaultCampaignId, initialLocation]);
  const reset = () => { setAddressLine1(''); setSector(''); setCampaignId(defaultCampaignId); setNote(''); setLocation(null); setReference(''); setDuplicates(null); };

  const activeCampaign = campaigns?.find((item) => item.campaign_id === campaignId);

  const submit = async (confirmed = false) => {
    if (!addressLine1.trim() && !sector.trim()) {
      toast.error('Indique al menos la dirección o el sector del hogar');
      return;
    }
    setSaving(true);
    try {
      // Evita duplicados: misma dirección o a menos de 25 m en esta invasión.
      if (campaignId && !confirmed) {
        const check = await axios.post(`${API}/api/mentorship/outreach/households/duplicates-check`, {
          campaign_id: campaignId, address_line1: addressLine1 || null, latitude: location?.latitude ?? null, longitude: location?.longitude ?? null,
        }, getAuthHeaders());
        if (check.data.items.length || check.data.hidden) { setDuplicates(check.data); return; }
      }
      await axios.post(`${API}/api/mentorship/outreach/households`, {
        campaign_id: campaignId || null, mentor_person_id: forcedMentorId || null,
        address_line1: addressLine1 || null, sector: sector || null, note: note || null,
        location_reference: reference.trim() || null,
        ...(location ? { latitude: location.latitude, longitude: location.longitude, location_accuracy_m: location.accuracy_m, location_source: 'gps' } : {}),
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
      <DialogContent className="max-h-[92vh] overflow-y-auto bg-white sm:max-w-lg" data-testid="outreach-add-household-dialog">
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

          <div className="space-y-1.5"><Label>Ubicación en el mapa</Label>
            <LocationCapture value={location} onChange={(value) => { setLocation(value); setDuplicates(null); }} reference={reference} onReferenceChange={setReference} testId="outreach-household-location" />
            {!location && addressLine1.trim() && <p className="text-xs text-slate-500">Sin ubicación del celular se ubicará por la dirección automáticamente.</p>}
          </div>

          {duplicates && <div className="space-y-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" role="alert" data-testid="outreach-household-duplicates">
            <p className="font-semibold">Puede que esta casa ya esté registrada</p>
            <ul className="list-disc space-y-1 pl-5">{duplicates.items.map((item) => <li key={item.household_id}>{item.address_line1 || item.location_reference || 'Casa sin dirección'}{item.distance_m != null ? ` · a ${Math.round(item.distance_m)} m` : ''}{item.same_address ? ' · misma dirección' : ''}{item.category === 'available' ? ' (disponible: tómala en el mapa)' : item.category === 'mine' ? ' (ya es tuya)' : ''}</li>)}
              {duplicates.hidden > 0 && <li>{duplicates.hidden} casa(s) de otro mentor en el mismo punto o dirección.</li>}</ul>
            <div className="grid grid-cols-2 gap-2"><Button type="button" variant="outline" onClick={() => setDuplicates(null)}>Revisar</Button><Button type="button" className="bg-[#132443]" disabled={saving} onClick={() => submit(true)} data-testid="outreach-household-add-anyway">Agregar igual</Button></div>
          </div>}

          <div className="space-y-1.5"><Label>Nota (opcional)</Label><Textarea value={note} onChange={(event) => setNote(event.target.value)} data-testid="outreach-household-note-input" /></div>

          <Button className="min-h-12 w-full bg-[#132443]" disabled={saving} onClick={() => submit(false)} data-testid="outreach-household-submit">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Home className="h-4 w-4" />} Agregar hogar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
