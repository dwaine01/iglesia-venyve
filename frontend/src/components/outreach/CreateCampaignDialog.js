import React, { useState } from 'react';
import axios from 'axios';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { mentorAccessDisabled, mentorAccessHint, mentorAccessSuffix } from '../../lib/accessControl';

export const CreateCampaignDialog = ({ open, onOpenChange, mentorOptions, onCreated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [startDate, setStartDate] = useState('');
  const [selectedMentors, setSelectedMentors] = useState([]);
  const [saving, setSaving] = useState(false);

  const reset = () => { setName(''); setLocation(''); setStartDate(''); setSelectedMentors([]); };

  const toggleMentor = (personId) => {
    setSelectedMentors((prev) => (prev.includes(personId) ? prev.filter((id) => id !== personId) : [...prev, personId]));
  };

  const submit = async () => {
    if (!name.trim() || !location.trim() || !startDate) {
      toast.error('Completa el lugar, el nombre y la fecha de la invasión');
      return;
    }
    setSaving(true);
    try {
      await axios.post(
        `${API}/api/mentorship/outreach/campaigns`,
        { name: name.trim(), location: location.trim(), start_date: startDate, assigned_mentor_ids: selectedMentors },
        getAuthHeaders(),
      );
      toast.success('Invasión creada');
      reset();
      onOpenChange(false);
      if (onCreated) onCreated();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'No se pudo crear la invasión');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => { onOpenChange(next); if (!next) reset(); }}>
      <DialogContent className="bg-white" data-testid="create-campaign-dialog">
        <DialogHeader>
          <DialogTitle>Crear invasión</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Nombre de la invasión</Label>
            <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Invasión Sector Norte" data-testid="create-campaign-name-input" />
          </div>
          <div className="space-y-1.5">
            <Label>Lugar</Label>
            <Input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Barrio, sector o dirección general" data-testid="create-campaign-location-input" />
          </div>
          <div className="space-y-1.5">
            <Label>Fecha</Label>
            <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} data-testid="create-campaign-date-input" />
          </div>
          <div className="space-y-1.5">
            <Label>Mentores asignados a esta invasión</Label>
            <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-[#E8E5DE] p-2" data-testid="create-campaign-mentor-list">
              {mentorOptions.map((mentor) => {
                const disabled = mentorAccessDisabled(mentor);
                return (
                  <label key={mentor.person_id} className={`flex items-center gap-2 rounded px-1 py-1 text-sm ${disabled ? 'cursor-not-allowed text-slate-400' : 'cursor-pointer text-[#101D36] hover:bg-[#F6F4EF]'}`}>
                    <input
                      type="checkbox"
                      checked={selectedMentors.includes(mentor.person_id)}
                      disabled={disabled}
                      onChange={() => toggleMentor(mentor.person_id)}
                      data-testid={`create-campaign-mentor-checkbox-${mentor.person_id}`}
                    />
                    {mentor.name}{mentorAccessSuffix(mentor)}
                  </label>
                );
              })}
              {mentorOptions.length === 0 && <p className="text-xs text-slate-400">Sin mentores con insignia activa todavía.</p>}
            </div>
            {mentorOptions.some(mentorAccessDisabled) && <p className="text-xs text-slate-500" data-testid="create-campaign-mentor-access-hint">{mentorAccessHint}</p>}
          </div>
          <Button disabled={saving} onClick={submit} className="w-full bg-[#132443]" data-testid="create-campaign-submit-button">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Crear invasión'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
