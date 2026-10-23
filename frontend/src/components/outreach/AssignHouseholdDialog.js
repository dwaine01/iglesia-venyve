import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, UserCheck } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

export const AssignHouseholdDialog = ({ open, onOpenChange, household, mentorOptions, onAssigned }) => {
  const { API, getAuthHeaders } = useAuth();
  const [mentorId, setMentorId] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!mentorId) { toast.error('Seleccione un mentor'); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/households/${household.household_id}/assign`, { mentor_person_id: mentorId }, getAuthHeaders());
      toast.success('Casa asignada');
      setMentorId('');
      onOpenChange(false);
      if (onAssigned) onAssigned();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo asignar la casa'));
    } finally {
      setSaving(false);
    }
  };

  const address = household ? [household.address_line1, household.sector].filter(Boolean).join(' · ') : '';

  return (
    <Dialog open={open} onOpenChange={(value) => { if (!value) setMentorId(''); onOpenChange(value); }}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="outreach-assign-household-dialog">
        <DialogHeader><DialogTitle>Asignar casa — {address}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <Select value={mentorId} onValueChange={setMentorId}>
            <SelectTrigger data-testid="outreach-assign-household-mentor-select"><SelectValue placeholder="Seleccione mentor" /></SelectTrigger>
            <SelectContent className="bg-white">
              {(mentorOptions || []).map((mentor) => (
                <SelectItem key={mentor.person_id} value={mentor.person_id} data-testid={`outreach-assign-household-mentor-option-${mentor.person_id}`}>{mentor.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {(mentorOptions || []).length === 0 && <p className="text-xs text-slate-500">Esta invasión todavía no tiene mentores en su roster.</p>}
          <Button className="w-full bg-[#132443]" disabled={saving} onClick={submit} data-testid="outreach-assign-household-submit">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserCheck className="h-4 w-4" />} Asignar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
