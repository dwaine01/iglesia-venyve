import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, MapPin, Search, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { mentorAccessDisabled, mentorAccessHint, mentorAccessSuffix } from '../../lib/accessControl';

const NO_CAMPAIGN = '__none__';

// `defaultCampaignId` + `invasionDay`: la invasión activa de hoy queda
// seleccionada y fija; solo cambia si la persona toca "Cambiar" a conciencia.
export const AddVisitDialog = ({ open, onOpenChange, campaigns, mentorOptions, forcedMentorId, onCreated, defaultCampaignId = '', invasionDay = null, invasionLabel = '' }) => {
  const { API, getAuthHeaders } = useAuth();
  const [contactType, setContactType] = useState('new');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [zone, setZone] = useState('');
  const [campaignId, setCampaignId] = useState(defaultCampaignId);
  const [changingCampaign, setChangingCampaign] = useState(false);
  const [mentorId, setMentorId] = useState(forcedMentorId || '');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) { setCampaignId(defaultCampaignId); setChangingCampaign(false); } }, [open, defaultCampaignId]);
  const lockedCampaign = !changingCampaign && defaultCampaignId && campaignId === defaultCampaignId ? (campaigns || []).find((item) => item.campaign_id === defaultCampaignId) : null;

  const search = async (value) => {
    setQuery(value);
    setSelectedPerson(null);
    if (value.trim().length < 2) { setResults([]); return; }
    setSearching(true);
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/person-search?q=${encodeURIComponent(value.trim())}`, getAuthHeaders());
      setResults(response.data.items || []);
    } finally {
      setSearching(false);
    }
  };

  const reset = () => {
    setContactType('new'); setName(''); setPhone(''); setZone(''); setCampaignId(defaultCampaignId); setChangingCampaign(false); setMentorId(forcedMentorId || '');
    setQuery(''); setResults([]); setSelectedPerson(null);
  };

  const submit = async () => {
    if (contactType === 'existing' && !selectedPerson) { toast.error('Seleccione una persona existente'); return; }
    if (contactType === 'new' && !name.trim()) { toast.error('Escriba el nombre del contacto'); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/visits`, {
        contact_type: contactType,
        person_id: contactType === 'existing' ? selectedPerson.person_id : null,
        contact_name: contactType === 'new' ? name.trim() : null,
        contact_phone: contactType === 'new' ? (phone || null) : null,
        contact_zone: contactType === 'new' ? (zone || null) : null,
        campaign_id: campaignId || null,
        invasion_day: campaignId && campaignId === defaultCampaignId ? invasionDay : null,
        mentor_person_id: mentorId || null,
      }, getAuthHeaders());
      toast.success('Visita agregada');
      reset();
      onOpenChange(false);
      if (onCreated) onCreated();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'No se pudo agregar la visita');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(value) => { if (!value) reset(); onOpenChange(value); }}>
      <DialogContent className="bg-white sm:max-w-lg" data-testid="outreach-add-visit-dialog">
        <DialogHeader><DialogTitle>Agregar visita</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="flex gap-2">
            <Button type="button" size="sm" variant={contactType === 'new' ? 'default' : 'outline'} onClick={() => setContactType('new')} className={contactType === 'new' ? 'bg-[#132443]' : ''} data-testid="outreach-contact-type-new">Contacto nuevo</Button>
            <Button type="button" size="sm" variant={contactType === 'existing' ? 'default' : 'outline'} onClick={() => setContactType('existing')} className={contactType === 'existing' ? 'bg-[#132443]' : ''} data-testid="outreach-contact-type-existing">Persona existente</Button>
          </div>

          {contactType === 'new' ? (
            <div className="space-y-3">
              <div className="space-y-1.5"><Label>Nombre</Label><Input value={name} onChange={(event) => setName(event.target.value)} data-testid="outreach-contact-name-input" /></div>
              <div className="space-y-1.5"><Label>Teléfono</Label><Input value={phone} onChange={(event) => setPhone(event.target.value)} data-testid="outreach-contact-phone-input" /></div>
              <div className="space-y-1.5"><Label>Dirección / zona</Label><Input value={zone} onChange={(event) => setZone(event.target.value)} data-testid="outreach-contact-zone-input" /></div>
            </div>
          ) : (
            <div className="space-y-1.5">
              <Label>Buscar persona</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                <Input className="pl-8" value={query} onChange={(event) => search(event.target.value)} placeholder="Nombre o apellido" data-testid="outreach-person-search-input" />
              </div>
              {searching && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
              {results.length > 0 && (
                <div className="max-h-40 overflow-y-auto rounded-lg border border-slate-200" data-testid="outreach-person-search-results">
                  {results.map((item) => (
                    <button type="button" key={item.person_id} onClick={() => { setSelectedPerson(item); setQuery(item.name); setResults([]); }} className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50 max-lg:min-h-11 max-lg:text-base" data-testid={`outreach-person-search-result-${item.person_id}`}>
                      {item.name}
                    </button>
                  ))}
                </div>
              )}
              {selectedPerson && <p className="text-xs text-emerald-700" data-testid="outreach-person-selected">Seleccionado: {selectedPerson.name}</p>}
            </div>
          )}

          {lockedCampaign ? (
            <div className="flex items-start justify-between gap-3 rounded-lg border border-[#bcd8c4] bg-[#eef5f0] p-3" data-testid="outreach-campaign-locked">
              <div className="min-w-0">
                <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-[#2f6e47]"><MapPin className="h-3.5 w-3.5" />Se registra en la invasión</p>
                <p className="text-base font-semibold text-[#101D36]">{lockedCampaign.name}</p>
                {invasionLabel && <p className="text-sm text-slate-600">{invasionLabel}</p>}
              </div>
              <Button type="button" variant="outline" size="sm" className="shrink-0 bg-white" onClick={() => setChangingCampaign(true)} data-testid="outreach-campaign-change">Cambiar</Button>
            </div>
          ) : campaigns?.length > 0 && (
            <div className="space-y-1.5">
              <Label>Campaña {defaultCampaignId ? '' : '(opcional)'}</Label>
              <Select value={campaignId || NO_CAMPAIGN} onValueChange={(value) => setCampaignId(value === NO_CAMPAIGN ? '' : value)}>
                <SelectTrigger data-testid="outreach-campaign-select"><SelectValue placeholder="Sin campaña" /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value={NO_CAMPAIGN}>Sin campaña</SelectItem>
                  {campaigns.map((campaign) => <SelectItem key={campaign.campaign_id} value={campaign.campaign_id}>{campaign.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}

          {mentorOptions && (
            <div className="space-y-1.5">
              <Label>Mentor responsable</Label>
              <Select value={mentorId} onValueChange={setMentorId}>
                <SelectTrigger data-testid="outreach-mentor-select"><SelectValue placeholder="Seleccione mentor" /></SelectTrigger>
                <SelectContent className="bg-white">
                  {mentorOptions.map((mentor) => <SelectItem key={mentor.person_id} value={mentor.person_id} disabled={mentorAccessDisabled(mentor)} data-testid={`outreach-mentor-option-${mentor.person_id}`}>{mentor.name}{mentorAccessSuffix(mentor)}</SelectItem>)}
                </SelectContent>
              </Select>
              {mentorOptions.some(mentorAccessDisabled) && <p className="text-xs text-slate-500" data-testid="outreach-mentor-access-hint">{mentorAccessHint}</p>}
            </div>
          )}

          <Button className="w-full bg-[#132443] max-lg:min-h-12" disabled={saving} onClick={submit} data-testid="outreach-add-visit-submit">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />} Agregar visita
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
