import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Repeat } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { mentorAccessDisabled, mentorAccessHint, mentorAccessSuffix } from '../../lib/accessControl';

export const TransferVisitDialog = ({ visit, onClose, onTransferred }) => {
  const { API, getAuthHeaders } = useAuth();
  const [mentors, setMentors] = useState([]);
  const [newMentorId, setNewMentorId] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!visit) return;
    axios.get(`${API}/api/mentorship/mentors`, getAuthHeaders()).then((response) => {
      setMentors((response.data.items || []).filter((item) => item.lbs_qualified && item.person_id !== visit.mentor_person_id));
    }).catch((error) => { toast.error(error?.response?.data?.detail || 'No se pudo cargar la lista de mentores'); setMentors([]); });
  }, [visit, API, getAuthHeaders]);

  if (!visit) return null;

  const submit = async () => {
    if (!newMentorId) { toast.error('Seleccione el nuevo mentor'); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/visits/${visit.visit_id}/transfer`, { new_mentor_person_id: newMentorId, reason: reason || null }, getAuthHeaders());
      toast.success('Visita transferida');
      setNewMentorId(''); setReason('');
      onClose();
      if (onTransferred) onTransferred();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'No se pudo transferir la visita');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={Boolean(visit)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="outreach-transfer-dialog">
        <DialogHeader><DialogTitle>Transferir a mentor capacitado en LBS</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <Select value={newMentorId} onValueChange={setNewMentorId}>
            <SelectTrigger data-testid="outreach-transfer-mentor-select"><SelectValue placeholder="Mentor con LBS" /></SelectTrigger>
            <SelectContent className="bg-white">
              {mentors.map((mentor) => <SelectItem key={mentor.person_id} value={mentor.person_id} disabled={mentorAccessDisabled(mentor)} data-testid={`outreach-transfer-mentor-option-${mentor.person_id}`}>{mentor.name}{mentorAccessSuffix(mentor)}</SelectItem>)}
            </SelectContent>
          </Select>
          {mentors.length === 0 && <p className="text-xs text-amber-700" data-testid="outreach-transfer-no-mentors">No hay otros mentores capacitados para LBS disponibles.</p>}
          {mentors.some(mentorAccessDisabled) && <p className="text-xs text-slate-500" data-testid="outreach-transfer-access-hint">{mentorAccessHint}</p>}
          <Textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Motivo de la transferencia" data-testid="outreach-transfer-reason-input" />
          <Button className="w-full bg-[#132443]" disabled={saving || !newMentorId} onClick={submit} data-testid="outreach-transfer-submit">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Repeat className="h-4 w-4" />} Confirmar transferencia
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
